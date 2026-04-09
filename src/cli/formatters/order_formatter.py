"""
Order formatting utilities for the Hyperliquid CLI.

This module provides formatting utilities for displaying order information
in a user-friendly way.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from models import LimitOrder, MarketOrder
from models.order import OrderHistoryEntry, OrderInfo, OrderResult, OrderStatus

from .base import Formatter
from .table_formatter import TableFormatter


class OrderFormatter(
    Formatter[
        MarketOrder
        | LimitOrder
        | OrderInfo
        | OrderResult
        | list[OrderInfo]
        | list[OrderHistoryEntry]
    ]
):
    """
    Formatter class for order data display.
    """

    def format(
        self,
        data: (
            MarketOrder
            | LimitOrder
            | OrderInfo
            | OrderResult
            | list[OrderInfo]
            | list[OrderHistoryEntry]
        ),
        **kwargs: Any,
    ) -> str:
        """
        Format an order for display.

        Args:
            data: The order to format (MarketOrder, LimitOrder, OrderInfo,
                OrderResult, or List[OrderInfo])
            **kwargs: Additional formatting options (unused for now)

        Returns:
            str: Formatted order summary, status, or result information
        """
        # Handle List[OrderInfo] objects (multiple orders display)
        if isinstance(data, list) and all(isinstance(item, OrderInfo) for item in data):
            return self._format_order_infos(data)  # type: ignore

        # Handle List[OrderHistoryEntry] objects (filled order history display)
        if isinstance(data, list) and all(isinstance(item, OrderHistoryEntry) for item in data):
            return self._format_order_history(data)  # type: ignore

        # Handle OrderResult objects (order submission result)
        if isinstance(data, OrderResult):
            return self._format_order_result(data)

        # Handle OrderInfo objects (order status display)
        if isinstance(data, OrderInfo):
            return self._format_order_info(data)

        # Handle MarketOrder and LimitOrder objects (order creation summary)
        if isinstance(data, (MarketOrder, LimitOrder)):
            lines = []
            lines.append("=" * 40)
            lines.append("ORDER SUMMARY")
            lines.append("=" * 40)

            lines.append(self._format_field("Side", data.side.upper()))
            lines.append(self._format_field("Coin", data.coin))
            lines.append(self._format_field("Quantity", data.quantity))

            if isinstance(data, LimitOrder):
                lines.append(self._format_field("Type", "Limit Order"))
                lines.append(self._format_field("Price", f"${data.price}"))
                lines.append(self._format_field("TIF", data.time_in_force.value))
            else:
                lines.append(self._format_field("Type", "Market Order"))

            lines.append(self._format_field("Reduce Only", "Yes" if data.reduce_only else "No"))
            lines.append("=" * 40)

            return "\n".join(lines)

        raise ValueError(
            f"Unsupported data type: {type(data)}. Expected MarketOrder, "
            "LimitOrder, OrderInfo, OrderResult, List[OrderInfo], "
            "or List[OrderHistoryEntry]."
        )

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
        lines.append(self._format_field("Order ID", order.order_id))
        lines.append(self._format_field("Coin", order.coin))
        lines.append(self._format_field("Side", order.side.upper()))
        lines.append(self._format_field("Type", order.order_type.upper()))
        lines.append(self._format_field("Status", self._format_status(order.status)))

        # Quantity information
        lines.append(self._format_field("Quantity", order.quantity))
        lines.append(self._format_field("Filled", order.filled_quantity))
        lines.append(self._format_field("Remaining", order.remaining_quantity))

        # Price information
        if order.price is not None:
            lines.append(self._format_field("Limit Price", f"${order.price}"))
        else:
            lines.append(self._format_field("Limit Price", "N/A (Market Order)"))

        if order.average_fill_price is not None:
            lines.append(self._format_field("Avg Fill", f"${order.average_fill_price}"))
        else:
            lines.append(self._format_field("Avg Fill", "N/A"))

        # Additional information
        if order.time_in_force is not None:
            lines.append(self._format_field("TIF", order.time_in_force.value))
        if order.trigger is not None:
            lines.append(self._format_field("Trigger Type", order.trigger.trigger_type.name))
            lines.append(self._format_field("Trigger Px", f"${order.trigger.trigger_price}"))
        lines.append(self._format_field("Reduce Only", "Yes" if order.reduce_only else "No"))
        lines.append(self._format_field("Timestamp", order.timestamp))

        lines.append("=" * 50)

        return "\n".join(lines)

    def _format_order_result(self, result: OrderResult) -> str:
        """
        Format OrderResult objects for order submission result display.

        Args:
            result: OrderResult object to format

        Returns:
            str: Formatted order submission result information
        """
        lines = []

        if result.success:
            lines.append("✅ Order submitted successfully!")
            if result.order_id is not None:
                lines.append(f"📋 Order ID: {result.order_id}")
            lines.append(f"📊 Status: {self._format_status(result.status)}")
            lines.append(f"💬 Message: {result.message}")
        else:
            lines.append("❌ Order submission failed")
            lines.append(f"💬 Message: {result.message}")
            if result.error:
                lines.append(f"🔍 Error details: {result.error}")

        return "\n".join(lines)

    def _format_status(self, status: OrderStatus, monospace: bool = False) -> str:
        """
        Format order status with appropriate indicators.

        Args:
            status: OrderStatus enum value
            monospace: Whether to use monospace-compatible status indicators

        Returns:
            str: Formatted status string
        """
        if monospace:
            status_map = {
                OrderStatus.OPEN: "+ OPEN",
                OrderStatus.FILLED: "* FILLED",
                OrderStatus.CANCELLED: "- CANCELLED",
                OrderStatus.REJECTED: "! REJECTED",
                OrderStatus.PARTIALLY_FILLED: "~ PARTIAL",
            }
        else:
            status_map = {
                OrderStatus.OPEN: "🟢 OPEN",
                OrderStatus.FILLED: "✅ FILLED",
                OrderStatus.CANCELLED: "❌ CANCELLED",
                OrderStatus.REJECTED: "🚫 REJECTED",
                OrderStatus.PARTIALLY_FILLED: "🟡 PARTIALLY FILLED",
            }
        return status_map.get(status, status.value.upper())

    def _format_field(self, label: str, value: Any) -> str:
        """Format a label-value pair with right-aligned labels."""
        return f"{label.ljust(12)}: {value}"

    def _format_order_infos(self, orders: list[OrderInfo]) -> str:
        """
        Format a list of OrderInfo objects as a table using TableFormatter.

        Args:
            orders: List of OrderInfo objects to format

        Returns:
            str: Formatted table of orders
        """
        if not orders:
            return "\nNo open orders found."

        # Define table headers
        headers = [
            "Order ID",
            "Coin",
            "Side",
            "Type",
            "Status",
            "Quantity",
            "Price",
            "Filled",
            "Remaining",
            "TIF",
        ]
        show_trigger_columns = any(order.trigger is not None for order in orders)
        if show_trigger_columns:
            headers.extend(["Trigger Type", "Trigger Px"])

        # Convert OrderInfo objects to table rows
        rows = []
        for order in orders:
            # Format price (handle market orders)
            price_str = f"${order.price}" if order.price is not None else "Market"

            # Format TIF (handle null values)
            tif_str = order.time_in_force.value if order.time_in_force else "N/A"

            row = [
                str(order.order_id),
                order.coin,
                order.side.upper(),
                order.order_type.upper(),
                self._format_status(order.status, monospace=True),
                str(order.quantity),
                price_str,
                str(order.filled_quantity),
                str(order.remaining_quantity),
                tif_str,
            ]
            if show_trigger_columns:
                row.extend(
                    [
                        order.trigger.trigger_type.name if order.trigger is not None else "",
                        (f"${order.trigger.trigger_price}" if order.trigger is not None else ""),
                    ]
                )
            rows.append(row)

        # Use TableFormatter to create the table
        table_formatter = TableFormatter()
        return table_formatter.format((headers, rows), title=f"Open Orders ({len(orders)})")

    def _format_order_history(self, entries: list[OrderHistoryEntry]) -> str:
        """Format filled-order history as a table."""
        if not entries:
            return "No filled orders found."

        headers = ["Time", "Coin", "Direction", "Price", "Size", "Value", "Fee", "Closed PnL"]
        rows = [
            [
                self._format_timestamp(entry.time),
                entry.coin,
                entry.direction,
                self._format_price(entry.price),
                f"{entry.size:,.6f}",
                f"${entry.notional:,.2f}",
                self._format_fee(entry.fee, entry.fee_token),
                f"${entry.closed_pnl:+,.2f}",
            ]
            for entry in entries
        ]

        table_formatter = TableFormatter()
        return table_formatter.format((headers, rows), title=f"Order History ({len(entries)})")

    def _format_fee(self, fee: Decimal, fee_token: str) -> str:
        """Format fee with token symbol."""
        return f"{fee:,.6f} {fee_token}".rstrip("0").rstrip(".")

    def _format_price(self, price: Decimal) -> str:
        """Format a price with grouping and variable precision."""
        price_str = f"{price:,.6f}".rstrip("0").rstrip(".")
        return f"${price_str or '0'}"

    def _format_timestamp(self, timestamp_ms: int) -> str:
        """Format an exchange timestamp in local time."""
        return datetime.fromtimestamp(timestamp_ms / 1000).strftime("%m/%d/%Y %H:%M:%S")


__all__ = [
    "OrderFormatter",
]
