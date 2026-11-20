"""Order submission command: order."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any

import typer

from exchange import HyperliquidClient
from models.api import ExchangeError
from models.config import Config, NetworkType
from models.order import (
    LimitOrder,
    MarketOrder,
    OrderResult,
    OrderSide,
    OrderTif,
    OrderTrigger,
    TriggerType,
)

from ..formatters import OrderFormatter
from ..runtime import CliValidationError, resolve_options, run_command
from .parsers import (
    ADDRESS_OPTION,
    CONFIG_OPTION,
    JSON_OPTION,
    NETWORK_OPTION,
    build_tp_sl_orders,
    parse_coin,
    parse_order_side,
    parse_order_tif,
    parse_positive_decimal,
    parse_trigger_type,
    validate_quantity_precision,
)


def _submit_one(client: HyperliquidClient, order: MarketOrder | LimitOrder) -> OrderResult:
    if isinstance(order, LimitOrder):
        return client.submit_limit_order(order)
    return client.submit_market_order(order)


def _render_order_human(result: Any, _config: Config) -> None:
    formatter = OrderFormatter()
    if isinstance(result, OrderResult):
        print(formatter.format(result))
        return

    if isinstance(result, dict) and result.get("dry_run"):
        print("[DRY RUN] Order validated (not submitted)")
        print(formatter.format(result["order"]))
        for child in result.get("trigger_orders", []):
            print()
            print(formatter.format(child))
        return

    if isinstance(result, dict) and "primary" in result:
        print(formatter.format(result["primary"]))
        for item in result.get("trigger_results", []):
            print()
            print(f"{item['label']}:")
            print(formatter.format(item["result"]))


def register_order_create_command(app: typer.Typer) -> None:
    """Register the order submission command."""

    @app.command("order")
    def order_command(
        ctx: typer.Context,
        side: Annotated[str, typer.Argument(help="Order side: buy or sell")],
        coin: Annotated[str, typer.Argument(help="Trading symbol (e.g., BTC, ETH)")],
        quantity: Annotated[str, typer.Argument(help="Positive order quantity")],
        price: Annotated[
            str | None,
            typer.Option("--price", help="Limit price (omit for market order)"),
        ] = None,
        tif: Annotated[
            str | None,
            typer.Option("--tif", help="Limit order time-in-force (GTC|IOC|ALO)"),
        ] = None,
        reduce_only: Annotated[
            bool,
            typer.Option("--reduce-only", help="Submit as reduce-only order"),
        ] = False,
        trigger_type: Annotated[
            str | None,
            typer.Option("--trigger-type", help="Trigger type (stop|take)"),
        ] = None,
        trigger_price: Annotated[
            str | None,
            typer.Option("--trigger-price", help="Trigger activation price"),
        ] = None,
        tp: Annotated[
            str | None,
            typer.Option("--tp", help="Optional take-profit trigger-market exit price"),
        ] = None,
        sl: Annotated[
            str | None,
            typer.Option("--sl", help="Optional stop-loss trigger-market exit price"),
        ] = None,
        dry_run: Annotated[
            bool,
            typer.Option(
                "--dry-run",
                help="Validate order inputs and coin rules without signing or submitting",
            ),
        ] = False,
        config_path: Annotated[Path | None, CONFIG_OPTION] = None,
        address: Annotated[str | None, ADDRESS_OPTION] = None,
        network: Annotated[NetworkType | None, NETWORK_OPTION] = None,
        json_output: Annotated[bool, JSON_OPTION] = False,
    ) -> None:
        """Place a market or limit order with optional triggers and TP/SL exits."""
        opts = resolve_options(
            ctx,
            config_path=config_path,
            address=address,
            network=network,
            json_output=json_output,
        )
        parsed: dict[str, Any] = {}

        def _validate() -> None:
            parsed_side: OrderSide = parse_order_side(side)
            parsed_coin = parse_coin(coin)
            parsed_qty = parse_positive_decimal(quantity, "Quantity")
            parsed_price: Decimal | None = (
                parse_positive_decimal(price, "--price") if price is not None else None
            )

            parsed_tif: OrderTif | None = None
            if tif is not None:
                if parsed_price is None:
                    raise CliValidationError("--tif can only be used with --price (limit orders)")
                parsed_tif = parse_order_tif(tif)

            if (trigger_type is None) != (trigger_price is None):
                raise CliValidationError("--trigger-type and --trigger-price must be set together")

            parsed_trigger: OrderTrigger | None = None
            if trigger_type is not None and trigger_price is not None:
                tt: TriggerType = parse_trigger_type(trigger_type)
                tp_val = parse_positive_decimal(trigger_price, "--trigger-price")
                parsed_trigger = OrderTrigger(trigger_type=tt, trigger_price=tp_val)

            parsed_tp = parse_positive_decimal(tp, "--tp") if tp is not None else None
            parsed_sl = parse_positive_decimal(sl, "--sl") if sl is not None else None

            parsed.update(
                {
                    "side": parsed_side,
                    "coin": parsed_coin,
                    "quantity": parsed_qty,
                    "price": parsed_price,
                    "tif": parsed_tif,
                    "trigger": parsed_trigger,
                    "tp": parsed_tp,
                    "sl": parsed_sl,
                }
            )

        def _execute(config: Config, client: HyperliquidClient) -> Any:
            primary: MarketOrder | LimitOrder
            if parsed["price"] is not None:
                primary = LimitOrder(
                    coin=parsed["coin"],
                    side=parsed["side"],
                    quantity=parsed["quantity"],
                    price=parsed["price"],
                    reduce_only=reduce_only,
                    time_in_force=parsed["tif"] or config.trading.default_time_in_force,
                    trigger=parsed["trigger"],
                )
            else:
                primary = MarketOrder(
                    coin=parsed["coin"],
                    side=parsed["side"],
                    quantity=parsed["quantity"],
                    reduce_only=reduce_only,
                    trigger=parsed["trigger"],
                )

            children = build_tp_sl_orders(primary, parsed["tp"], parsed["sl"])

            if dry_run:
                metadata = client.get_metadata(primary.coin)
                validate_quantity_precision(primary.quantity, metadata.size_decimals, metadata.coin)
                return {
                    "dry_run": True,
                    "order_type": "limit" if isinstance(primary, LimitOrder) else "market",
                    "order": primary,
                    "trigger_orders": [child for _, child in children],
                    "metadata": metadata,
                }

            primary_result = _submit_one(client, primary)
            if not primary_result.success:
                raise ExchangeError(primary_result.error or primary_result.message)

            if not children:
                return primary_result

            trigger_results = [
                {"label": label, "result": _submit_one(client, child)} for label, child in children
            ]
            return {
                "primary": primary_result,
                "trigger_results": trigger_results,
            }

        run_command(
            "order",
            opts,
            require_address=not dry_run,
            validate=_validate,
            execute=_execute,
            render_human=_render_order_human,
        )
