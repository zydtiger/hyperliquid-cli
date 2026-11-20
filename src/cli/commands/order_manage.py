"""Order cancellation and modification commands: cancel-order, modify-order."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any

import typer

from exchange import HyperliquidClient
from models.api import ExchangeError
from models.config import Config, NetworkType
from models.order import OrderInfo, OrderResult, OrderStatus, OrderType

from ..formatters import OrderFormatter, TableFormatter
from ..runtime import CliValidationError, resolve_options, run_command
from .parsers import (
    ADDRESS_OPTION,
    CONFIG_OPTION,
    JSON_OPTION,
    NETWORK_OPTION,
    parse_coin,
    parse_positive_decimal,
    parse_positive_int,
    validate_quantity_precision,
)


def _render_cancel_human(result: Any, _config: Config) -> None:
    if isinstance(result, OrderResult):
        print(f"✅ {result.message}")
        return
    if isinstance(result, dict) and result.get("dry_run"):
        orders: list[OrderInfo] = result["would_cancel"]
        print(f"[DRY RUN] Would cancel {len(orders)} order(s)")
        if orders:
            print(OrderFormatter().format(orders, title=f"Orders to Cancel ({len(orders)})"))


def _render_modify_human(result: Any, _config: Config) -> None:
    if isinstance(result, OrderResult):
        print(OrderFormatter().format(result))
        return
    if isinstance(result, dict) and result.get("dry_run"):
        rows = [
            ["Order ID", str(result["order_id"])],
            ["Coin", result["coin"]],
            ["Price", f"{result['current_price']} -> {result['new_price']}"],
            ["Quantity", f"{result['current_quantity']} -> {result['new_quantity']}"],
        ]
        print(
            TableFormatter().format(
                (["Field", "Change"], rows),
                title="[DRY RUN] Order Modification",
            )
        )


def _cancel_dry_run(
    client: HyperliquidClient,
    order_id: int | None,
    target_coin: str | None,
) -> dict[str, Any]:
    if order_id is not None:
        order_info = client.get_order_status(order_id)
        if order_info.status != OrderStatus.OPEN:
            raise ExchangeError(
                f"Order {order_id} is {order_info.status.value} and cannot be cancelled"
            )
        return {
            "dry_run": True,
            "scope": "single",
            "count": 1,
            "would_cancel": [order_info],
        }

    open_orders = client.get_open_orders()
    if target_coin is not None:
        open_orders = [o for o in open_orders if o.coin.upper() == target_coin]
    return {
        "dry_run": True,
        "scope": "coin" if target_coin is not None else "all",
        "coin": target_coin,
        "count": len(open_orders),
        "would_cancel": open_orders,
    }


def _cancel_live(
    client: HyperliquidClient,
    order_id: int | None,
    target_coin: str | None,
) -> OrderResult:
    if order_id is not None:
        result = client.cancel_order(order_id)
        if not result.success:
            raise ExchangeError(result.error or result.message)
        return result

    if target_coin is None:
        result = client.cancel_order("all")
        if not result.success:
            raise ExchangeError(result.error or result.message)
        return result

    matching_orders = [
        order for order in client.get_open_orders() if order.coin.upper() == target_coin
    ]
    cancelled = 0
    failed = 0
    for order in matching_orders:
        item_result = client.cancel_order(order.order_id)
        if item_result.success:
            cancelled += 1
        else:
            failed += 1

    summary = OrderResult(
        success=failed == 0,
        status=OrderStatus.CANCELLED,
        message=f"Cancelled {cancelled} {target_coin} orders, {failed} failed",
        error=f"{failed} orders failed to cancel" if failed else None,
    )
    if not summary.success:
        raise ExchangeError(summary.error or summary.message)
    return summary


def cancel_order_command(
    ctx: typer.Context,
    order_id: Annotated[
        int | None,
        typer.Argument(help="Positive integer order ID to cancel"),
    ] = None,
    cancel_all: Annotated[
        bool,
        typer.Option("--all", help="Cancel all open orders (optionally filtered by --coin)"),
    ] = False,
    coin: Annotated[
        str | None,
        typer.Option("--coin", help="Restrict --all cancellation to one coin"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview orders to cancel without signing"),
    ] = False,
    config_path: Annotated[Path | None, CONFIG_OPTION] = None,
    address: Annotated[str | None, ADDRESS_OPTION] = None,
    network: Annotated[NetworkType | None, NETWORK_OPTION] = None,
    json_output: Annotated[bool, JSON_OPTION] = False,
) -> None:
    """Cancel a specific order or all open orders."""
    opts = resolve_options(
        ctx,
        config_path=config_path,
        address=address,
        network=network,
        json_output=json_output,
    )
    parsed_coin: list[str | None] = [None]

    def _validate() -> None:
        if order_id is None and not cancel_all:
            raise CliValidationError("Provide either ORDER_ID or --all")
        if order_id is not None and cancel_all:
            raise CliValidationError("Cannot combine ORDER_ID with --all")
        if order_id is not None:
            parse_positive_int(order_id, "Order ID")
            if coin is not None:
                raise CliValidationError("--coin can only be used with --all")
        elif coin is not None:
            parsed_coin[0] = parse_coin(coin)

    def _execute(_config: Config, client: HyperliquidClient) -> Any:
        if dry_run:
            return _cancel_dry_run(client, order_id, parsed_coin[0])
        return _cancel_live(client, order_id, parsed_coin[0])

    run_command(
        "cancel-order",
        opts,
        require_address=True,
        validate=_validate,
        execute=_execute,
        render_human=_render_cancel_human,
    )


def modify_order_command(
    ctx: typer.Context,
    order_id: Annotated[int, typer.Argument(help="Positive integer order ID to modify")],
    price: Annotated[
        str | None,
        typer.Option("--price", help="New limit price"),
    ] = None,
    quantity: Annotated[
        str | None,
        typer.Option("--quantity", help="New order quantity"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Validate modification without signing"),
    ] = False,
    config_path: Annotated[Path | None, CONFIG_OPTION] = None,
    address: Annotated[str | None, ADDRESS_OPTION] = None,
    network: Annotated[NetworkType | None, NETWORK_OPTION] = None,
    json_output: Annotated[bool, JSON_OPTION] = False,
) -> None:
    """Modify price and/or quantity of an existing open limit order."""
    opts = resolve_options(
        ctx,
        config_path=config_path,
        address=address,
        network=network,
        json_output=json_output,
    )
    parsed_price: list[Decimal | None] = [None]
    parsed_qty: list[Decimal | None] = [None]

    def _validate() -> None:
        parse_positive_int(order_id, "Order ID")
        if price is None and quantity is None:
            raise CliValidationError("Provide at least one of --price or --quantity")
        if price is not None:
            parsed_price[0] = parse_positive_decimal(price, "--price")
        if quantity is not None:
            parsed_qty[0] = parse_positive_decimal(quantity, "--quantity")

    def _execute(_config: Config, client: HyperliquidClient) -> Any:
        new_price = parsed_price[0]
        new_qty = parsed_qty[0]
        if dry_run:
            current = client.get_order_status(order_id)
            if current.status != OrderStatus.OPEN:
                raise ExchangeError(
                    f"Order {order_id} is {current.status.value} and cannot be modified"
                )
            if current.order_type != OrderType.LIMIT:
                raise ExchangeError(
                    f"Order {order_id} is a {current.order_type.value} order "
                    "(only limit orders can be modified)"
                )
            metadata = client.get_metadata(current.coin)
            if new_qty is not None:
                validate_quantity_precision(new_qty, metadata.size_decimals, metadata.coin)
            return {
                "dry_run": True,
                "order_id": order_id,
                "coin": current.coin,
                "current_price": current.price,
                "new_price": new_price if new_price is not None else current.price,
                "current_quantity": current.remaining_quantity,
                "new_quantity": new_qty if new_qty is not None else current.remaining_quantity,
                "metadata": metadata,
            }

        result = client.modify_order(order_id, price=new_price, quantity=new_qty)
        if not result.success:
            raise ExchangeError(result.error or result.message)
        return result

    run_command(
        "modify-order",
        opts,
        require_address=True,
        validate=_validate,
        execute=_execute,
        render_human=_render_modify_human,
    )


def register_order_manage_commands(app: typer.Typer) -> None:
    """Register cancel-order and modify-order commands."""
    app.command("cancel-order")(cancel_order_command)
    app.command("modify-order")(modify_order_command)
