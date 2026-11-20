"""Order query, cancel, and modify command mixin for the interactive CLI."""

from __future__ import annotations

from contextlib import AbstractContextManager

from exchange import HyperliquidClient
from models.order import ModifyOrderRequest, OrderInfo, OrderResult

from .repl_help import DEFAULT_ORDER_HISTORY_LIMIT


class ReplOrdersMixin:
    """Provides order_status, open_orders, order_history, cancel_order, modify_order."""

    def _client_scope(self) -> AbstractContextManager[HyperliquidClient]:
        raise NotImplementedError

    def _run_modify_wizard(self, client: HyperliquidClient, order_id: int) -> ModifyOrderRequest:
        raise NotImplementedError

    def _print_order_output(
        self,
        data: OrderResult | OrderInfo | list[OrderInfo],
        **kwargs: str,
    ) -> None:
        raise NotImplementedError

    def _format_order_history_output(self, history: list[object]) -> str:
        raise NotImplementedError

    def do_order_status(self, args: str) -> None:
        """Get status and details of a specific order."""
        if not args.strip():
            print("❌ Error: Order ID is required")
            print("Usage: order_status <order_id>")
            print("Example: order_status 12345")
            return

        try:
            order_id = int(args.strip())
            if order_id <= 0:
                raise ValueError("Order ID must be a positive integer")
        except ValueError as e:
            print(f"❌ Invalid order ID: {e}")
            print("Order ID must be a positive integer")
            return

        try:
            with self._client_scope() as client:
                order_info = client.get_order_status(order_id)
                print()
                self._print_order_output(order_info)
                print()
        except Exception as e:
            print(f"❌ Error fetching order status: {e}")

    def do_open_orders(self, args: str) -> None:
        """Get all open orders for the account."""
        try:
            with self._client_scope() as client:
                orders = client.get_open_orders()
                self._print_order_output(orders)
                print()
        except Exception as e:
            print(f"❌ Error fetching open orders: {e}")

    def do_order_history(self, args: str) -> None:
        """Get recent filled-order history for the account."""
        parts = args.strip().split()
        if len(parts) > 1:
            print("❌ Error: Too many arguments")
            print("Usage: order_history [N]")
            print("Example: order_history 5")
            return

        limit = DEFAULT_ORDER_HISTORY_LIMIT
        if parts:
            try:
                limit = int(parts[0])
                if limit <= 0:
                    raise ValueError("N must be a positive integer")
            except ValueError as e:
                print(f"❌ Invalid history limit: {e}")
                print("Usage: order_history [N]")
                print("Example: order_history 5")
                return

        try:
            with self._client_scope() as client:
                history = client.get_order_history(limit)
                if history:
                    print(self._format_order_history_output(list(history)))
                else:
                    print("No filled orders found.")
                print()
        except Exception as e:
            print(f"❌ Error fetching order history: {e}")

    def do_cancel_order(self, args: str) -> None:
        """Cancel a specific order or all open orders."""
        if not args.strip():
            print("❌ Error: Order ID or 'all' is required")
            print("Usage: cancel_order <order_id|all>")
            print("Examples:")
            print("  cancel_order 12345    # Cancel specific order")
            print("  cancel_order all      # Cancel all open orders")
            return

        arg = args.strip().lower()
        try:
            if arg == "all":
                print("⏳ Cancelling all open orders...")
                with self._client_scope() as client:
                    result = client.cancel_order("all")
            else:
                try:
                    order_id = int(arg)
                    if order_id <= 0:
                        print("❌ Order ID must be a positive integer")
                        return
                except ValueError:
                    print(f"❌ Invalid argument: {arg}")
                    print("Must be a positive integer order ID or 'all'")
                    return

                print(f"⏳ Cancelling order {order_id}...")
                with self._client_scope() as client:
                    result = client.cancel_order(order_id)

            if result.success:
                print(f"✅ {result.message}")
                print()
            else:
                print(f"❌ Error: {result.error or result.message}")
        except Exception as e:
            print(f"❌ Failed to cancel order: {e}")

    def do_modify_order(self, args: str) -> None:
        """Modify an existing order using interactive wizard."""
        if not args.strip():
            print("❌ Error: Order ID is required")
            print("Usage: modify_order <order_id>")
            print("Example: modify_order 12345")
            return

        try:
            order_id = int(args.strip())
            if order_id <= 0:
                raise ValueError("Order ID must be a positive integer")
        except ValueError as e:
            print(f"❌ Invalid order ID: {e}")
            print("Order ID must be a positive integer")
            return

        try:
            with self._client_scope() as client:
                modify_request = self._run_modify_wizard(client, order_id)
                print("⏳ Modifying order...")
                result = client.modify_order(
                    modify_request.order_id,
                    price=modify_request.price,
                    quantity=modify_request.quantity,
                )
                self._print_order_output(result)
        except KeyboardInterrupt:
            print("❌ Order modification cancelled")
        except Exception as e:
            print(f"❌ Failed to modify order: {e}")
        finally:
            print()
