"""
Order cancellation and modification operations for HyperliquidClient.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from models.order import OrderResult, OrderSide, OrderStatus, OrderTif, OrderType

from .order_parsing import convert_tif_value

if TYPE_CHECKING:
    from .hyperliquid_client import HyperliquidClient


def cancel_order(client: HyperliquidClient, order_id: int | str) -> OrderResult:
    """Cancel a specific order or all open orders."""
    if order_id == "all":
        _ = client.connection.exchange
        return client.connection.retry_operation(lambda: cancel_all_orders(client))

    if isinstance(order_id, int) and not isinstance(order_id, bool) and order_id > 0:
        _ = client.connection.exchange
        return client.connection.retry_operation(lambda: cancel_specific_order(client, order_id))

    raise ValueError("order_id must be positive integer or 'all'")


def cancel_specific_order(client: HyperliquidClient, order_id: int) -> OrderResult:
    """Cancel a specific order by ID."""
    order_info = client.get_order_status(order_id)

    if order_info.status != OrderStatus.OPEN:
        if order_info.status == OrderStatus.CANCELLED:
            error_msg = f"Order {order_id} is already cancelled"
        elif order_info.status == OrderStatus.FILLED:
            error_msg = f"Order {order_id} is already filled"
        elif order_info.status == OrderStatus.REJECTED:
            error_msg = f"Order {order_id} was already rejected"
        else:
            error_msg = f"Order {order_id} is {order_info.status.value} and cannot be cancelled"
        return OrderResult(
            success=False,
            order_id=order_id,
            status=order_info.status,
            message=f"Order {order_id} cancellation failed",
            error=error_msg,
        )

    result = client.connection.exchange.cancel(order_info.coin, order_id)

    if result.get("status") == "ok":
        statuses = result.get("response", {}).get("data", {}).get("statuses", [])
        for status in statuses:
            if status == "success":
                return OrderResult(
                    success=True,
                    order_id=order_id,
                    status=OrderStatus.CANCELLED,
                    message=f"Order {order_id} cancelled successfully",
                )
            if isinstance(status, dict) and "error" in status:
                return OrderResult(
                    success=False,
                    order_id=order_id,
                    status=OrderStatus.REJECTED,
                    message="Order cancellation failed",
                    error=status["error"],
                )

        return OrderResult(
            success=True,
            order_id=order_id,
            status=OrderStatus.CANCELLED,
            message=f"Order {order_id} cancelled successfully",
        )

    return OrderResult(
        success=False,
        order_id=order_id,
        status=OrderStatus.REJECTED,
        message="Order cancellation failed",
        error=result.get("response", "Unknown error"),
    )


def cancel_all_orders(client: HyperliquidClient) -> OrderResult:
    """Cancel all open orders."""
    open_orders = client.get_open_orders()
    cancelled_count = 0
    failed_count = 0

    for order_info in open_orders:
        try:
            result = cancel_specific_order(client, order_info.order_id)
            if result.success:
                cancelled_count += 1
            else:
                failed_count += 1
        except Exception:
            failed_count += 1

    return OrderResult(
        success=failed_count == 0,
        status=OrderStatus.CANCELLED,
        message=f"Cancelled {cancelled_count} orders, {failed_count} failed",
        error=f"{failed_count} orders failed to cancel" if failed_count else None,
    )


def modify_order(
    client: HyperliquidClient,
    order_id: int,
    price: Decimal | None = None,
    quantity: Decimal | None = None,
) -> OrderResult:
    """Modify price and/or quantity of an existing open limit order."""
    if price is None and quantity is None:
        return OrderResult(
            success=False,
            order_id=order_id,
            status=OrderStatus.REJECTED,
            message="Order modification failed",
            error="No changes requested - both price and quantity are None",
        )

    exchange = client.connection.exchange

    def _modify_order() -> OrderResult:
        try:
            current_order = client.get_order_status(order_id)
            if current_order.status != OrderStatus.OPEN:
                if current_order.status == OrderStatus.CANCELLED:
                    raise ValueError(
                        f"Order {order_id} is already cancelled and cannot be modified"
                    )
                if current_order.status == OrderStatus.FILLED:
                    raise ValueError(f"Order {order_id} is already filled and cannot be modified")
                if current_order.status == OrderStatus.REJECTED:
                    raise ValueError(f"Order {order_id} was rejected and cannot be modified")
                raise ValueError(
                    f"Order {order_id} is {current_order.status.value} and cannot be modified"
                )

            if current_order.order_type != OrderType.LIMIT:
                raise ValueError(
                    f"Order {order_id} is a {current_order.order_type.value} "
                    "order and cannot be modified (only limit orders can be modified)"
                )

            new_price = price if price is not None else current_order.price
            new_quantity = quantity if quantity is not None else current_order.remaining_quantity
            if new_price is None:
                raise ValueError("Price is required for limit order modification")
            if new_quantity <= 0:
                raise ValueError("Quantity must be greater than 0")

            result = exchange.modify_order(
                oid=order_id,
                name=current_order.coin,
                is_buy=current_order.side == OrderSide.BUY,
                sz=float(new_quantity),
                limit_px=float(new_price),
                order_type={
                    "limit": {"tif": convert_tif_value(current_order.time_in_force or OrderTif.GTC)}
                },
            )

            if result.get("status") == "ok":
                statuses = result.get("response", {}).get("data", {}).get("statuses", [])
                for status in statuses:
                    if "resting" in status:
                        new_order_id = status["resting"].get("oid", order_id)
                        return OrderResult(
                            success=True,
                            order_id=new_order_id,
                            status=OrderStatus.OPEN,
                            message=(
                                f"Order {order_id} modified successfully - "
                                f"price: {new_price}, quantity: {new_quantity}"
                            ),
                        )
                    if "error" in status:
                        return OrderResult(
                            success=False,
                            order_id=order_id,
                            status=OrderStatus.REJECTED,
                            message="Order modification failed",
                            error=status["error"],
                        )

                return OrderResult(
                    success=True,
                    order_id=order_id,
                    status=OrderStatus.OPEN,
                    message=(
                        f"Order {order_id} modified successfully - "
                        f"price: {new_price}, quantity: {new_quantity}"
                    ),
                )

            return OrderResult(
                success=False,
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message="Order modification failed",
                error=result.get("response", "Unknown error"),
            )
        except Exception as e:
            return OrderResult(
                success=False,
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message="Order modification failed",
                error=str(e),
            )

    return client.connection.retry_operation(_modify_order)
