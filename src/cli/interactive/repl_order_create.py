"""Quick-order and wizard order creation mixin for the interactive CLI."""

from __future__ import annotations

from contextlib import AbstractContextManager
from decimal import Decimal, InvalidOperation

from exchange import HyperliquidClient
from models.order import LimitOrder, MarketOrder, OrderInfo, OrderResult, OrderSide, OrderTif

from ..commands.parsers import build_tp_sl_orders

QUICK_ORDER_ARGS = 3
TAKE_PROFIT_FLAG = "--tp"
STOP_LOSS_FLAG = "--sl"


class ReplOrderCreateMixin:
    """Provides quick-order parsing and the ``order`` command for InteractiveCLI."""

    def _client_scope(self) -> AbstractContextManager[HyperliquidClient]:
        raise NotImplementedError

    def _run_order_wizard(self, client: HyperliquidClient) -> MarketOrder | LimitOrder:
        raise NotImplementedError

    def _print_order_output(
        self,
        data: OrderResult | OrderInfo | list[OrderInfo],
        **kwargs: str,
    ) -> None:
        raise NotImplementedError

    def _parse_positive_decimal(self, value: str, label: str) -> Decimal:
        """Parse and validate a positive decimal value."""
        try:
            parsed_value = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(f"{label} must be a valid decimal value") from exc

        if parsed_value <= 0:
            raise ValueError(f"{label} must be greater than 0")
        return parsed_value

    def _parse_quick_order_flags(self, parts: list[str]) -> tuple[Decimal | None, Decimal | None]:
        """Parse optional quick-order TP/SL flags."""
        take_profit: Decimal | None = None
        stop_loss: Decimal | None = None
        index = 0

        while index < len(parts):
            flag = parts[index]
            if flag not in {TAKE_PROFIT_FLAG, STOP_LOSS_FLAG}:
                raise ValueError(f"Unknown quick-order flag: {flag}")

            if index + 1 >= len(parts) or parts[index + 1].startswith("--"):
                raise ValueError(f"{flag} requires a price value")

            price_label = "Take-profit price" if flag == TAKE_PROFIT_FLAG else "Stop-loss price"
            price = self._parse_positive_decimal(parts[index + 1], price_label)

            if flag == TAKE_PROFIT_FLAG:
                if take_profit is not None:
                    raise ValueError(f"Duplicate quick-order flag: {TAKE_PROFIT_FLAG}")
                take_profit = price
            else:
                if stop_loss is not None:
                    raise ValueError(f"Duplicate quick-order flag: {STOP_LOSS_FLAG}")
                stop_loss = price

            index += 2

        return take_profit, stop_loss

    def _build_quick_order(
        self,
        side: OrderSide,
        coin: str,
        quantity_spec: str,
    ) -> MarketOrder | LimitOrder:
        """Build the primary quick order from positional arguments."""
        if "@" not in quantity_spec:
            quantity = self._parse_positive_decimal(quantity_spec, "Quantity")
            return MarketOrder(coin=coin, side=side, quantity=quantity, reduce_only=False)

        quantity_text, price_text = quantity_spec.split("@", maxsplit=1)
        if not quantity_text or not price_text:
            raise ValueError("Limit orders must use the format <quantity>@<price>")

        quantity = self._parse_positive_decimal(quantity_text, "Quantity")
        price = self._parse_positive_decimal(price_text, "Price")
        return LimitOrder(
            coin=coin,
            side=side,
            quantity=quantity,
            price=price,
            reduce_only=False,
            time_in_force=OrderTif.GTC,
        )

    def _parse_quick_order(
        self,
        args: str,
    ) -> tuple[MarketOrder | LimitOrder, list[tuple[str, MarketOrder]]]:
        """Parse quick-order arguments into a primary order plus optional TP/SL orders."""
        parts = args.strip().split()
        if len(parts) < QUICK_ORDER_ARGS:
            raise ValueError("Quick order requires at least 3 arguments")

        try:
            side = OrderSide(parts[0].lower())
        except ValueError as exc:
            raise ValueError("Side must be 'buy' or 'sell'") from exc

        coin = parts[1].upper()
        quantity_spec = parts[2]
        primary_order = self._build_quick_order(side, coin, quantity_spec)
        take_profit, stop_loss = self._parse_quick_order_flags(parts[QUICK_ORDER_ARGS:])
        return primary_order, build_tp_sl_orders(primary_order, take_profit, stop_loss)

    def _submit_single_order(
        self,
        client: HyperliquidClient,
        order: MarketOrder | LimitOrder,
    ) -> OrderResult:
        """Submit one order through HyperliquidClient."""
        if isinstance(order, LimitOrder):
            return client.submit_limit_order(order)
        return client.submit_market_order(order)

    def _submit_order(self, client: HyperliquidClient, order: MarketOrder | LimitOrder) -> None:
        """Submit an order and print the formatted result."""
        print("⏳ Submitting order...")
        try:
            result = self._submit_single_order(client, order)
            self._print_order_output(result)
        except Exception as submission_err:
            print(f"❌ Failed to submit order: {submission_err}")

    def _submit_quick_order(
        self,
        client: HyperliquidClient,
        primary_order: MarketOrder | LimitOrder,
        trigger_orders: list[tuple[str, MarketOrder]],
    ) -> None:
        """Submit a quick order and any requested TP/SL trigger orders."""
        print("⏳ Submitting order...")
        try:
            primary_result = self._submit_single_order(client, primary_order)
            if not primary_result.success:
                self._print_order_output(primary_result)
                return

            successful_orders: list[tuple[str, int]] = []
            failed_results: list[tuple[str, OrderResult]] = []

            if primary_result.order_id is not None:
                successful_orders.append(("Primary Order", primary_result.order_id))
            else:
                failed_results.append(("Primary Order", primary_result))

            for label, trigger_order in trigger_orders:
                trigger_result = self._submit_single_order(client, trigger_order)
                if trigger_result.success and trigger_result.order_id is not None:
                    successful_orders.append((label, trigger_result.order_id))
                else:
                    failed_results.append((label, trigger_result))

            order_statuses: list[OrderInfo] = []
            for label, order_id in successful_orders:
                try:
                    order_statuses.append(client.get_order_status(order_id))
                except Exception as status_err:
                    print(
                        "❌ Failed to fetch "
                        f"{label.lower()} status for order {order_id}: {status_err}"
                    )

            if order_statuses:
                self._print_order_output(
                    order_statuses,
                    title=f"Submitted Orders ({len(order_statuses)})",
                )

            for label, result in failed_results:
                print()
                print(f"{label}:")
                self._print_order_output(result)
        except Exception as submission_err:
            print(f"❌ Failed to submit order: {submission_err}")

    def do_order(self, args: str) -> None:
        """Place a new order using quick args or the interactive wizard."""
        try:
            with self._client_scope() as client:
                if args.strip():
                    order, trigger_orders = self._parse_quick_order(args)
                else:
                    order = self._run_order_wizard(client)
                    trigger_orders = []

                if trigger_orders:
                    self._submit_quick_order(client, order, trigger_orders)
                else:
                    self._submit_order(client, order)
        except KeyboardInterrupt:
            print("❌ Order creation cancelled")
        except ValueError as e:
            print(f"❌ Error: {e}")
            print("Usage: order")
            print(
                "   or: order <buy|sell> <coin> <quantity|quantity@price> "
                "[--tp <price>] [--sl <price>]"
            )
        except Exception as e:
            print(f"❌ Failed to create order: {e}")
        finally:
            print()
