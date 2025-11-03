"""
Order formatting utilities for the Hyperliquid CLI.

This module provides formatting utilities for displaying order information
in a user-friendly way.
"""

from typing import Union
from .base import Formatter
from models import MarketOrder, LimitOrder
from models.order import OrderInfo, OrderStatus


class OrderFormatter(Formatter[Union[MarketOrder, LimitOrder, OrderInfo]]):
    """
    Formatter class for order data display.
    """

    def format(self, data: Union[MarketOrder, LimitOrder, OrderInfo], **kwargs) -> str:
        """
        Format an order for display.

        Args:
            data: The order to format (MarketOrder, LimitOrder, or OrderInfo)
            **kwargs: Additional formatting options (unused for now)

        Returns:
            str: Formatted order summary or status information
        """
        # Handle OrderInfo objects (order status display)
        if isinstance(data, OrderInfo):
            return self._format_order_info(data)

        # Handle MarketOrder and LimitOrder objects (order creation summary)
        lines = []
        lines.append("=" * 40)
        lines.append("ORDER SUMMARY")
        lines.append("=" * 40)

        lines.append(f"Side:        {data.side.upper()}")
        lines.append(f"Coin:        {data.coin}")
        lines.append(f"Quantity:    {data.quantity}")

        if isinstance(data, LimitOrder):
            lines.append(f"Type:        Limit Order")
            lines.append(f"Price:       ${data.price}")
            lines.append(f"TIF:         {data.time_in_force.value}")
        else:
            lines.append(f"Type:        Market Order")

        lines.append(f"Reduce Only: {'Yes' if data.reduce_only else 'No'}")
        lines.append("=" * 40)

        return "\n".join(lines)

    def _format_order_info(self, order: OrderInfo) -> str:
        """
        Format OrderInfo objects for order status display.

        Args:
            order: OrderInfo object to format

        Returns:
            str: Formatted order status information
        """
        lines = []
        lines.append("=" * 50)
        lines.append("ORDER STATUS")
        lines.append("=" * 50)

        # Basic order information
        lines.append(f"Order ID:    {order.order_id}")
        lines.append(f"Coin:        {order.coin}")
        lines.append(f"Side:        {order.side.upper()}")
        lines.append(f"Type:        {order.order_type.upper()}")
        lines.append(f"Status:      {self._format_status(order.status)}")

        # Quantity information
        lines.append(f"Quantity:    {order.quantity}")
        lines.append(f"Filled:      {order.filled_quantity}")
        lines.append(f"Remaining:   {order.remaining_quantity}")

        # Price information
        if order.price is not None:
            lines.append(f"Limit Price: ${order.price}")
        else:
            lines.append(f"Limit Price: N/A (Market Order)")

        if order.average_fill_price is not None:
            lines.append(f"Avg Fill:    ${order.average_fill_price}")
        else:
            lines.append(f"Avg Fill:    N/A")

        # Additional information
        if order.time_in_force is not None:
            lines.append(f"TIF:         {order.time_in_force.value}")
        lines.append(f"Reduce Only: {'Yes' if order.reduce_only else 'No'}")
        lines.append(f"Timestamp:   {order.timestamp}")

        lines.append("=" * 50)

        return "\n".join(lines)

    def _format_status(self, status: OrderStatus) -> str:
        """
        Format order status with appropriate indicators.

        Args:
            status: OrderStatus enum value

        Returns:
            str: Formatted status string
        """
        status_map = {
            OrderStatus.OPEN: "🟢 OPEN",
            OrderStatus.FILLED: "✅ FILLED",
            OrderStatus.CANCELLED: "❌ CANCELLED",
            OrderStatus.REJECTED: "🚫 REJECTED",
            OrderStatus.PARTIALLY_FILLED: "🟡 PARTIALLY FILLED",
        }
        return status_map.get(status, status.value.upper())


__all__ = [
    "OrderFormatter",
]
