"""
Order formatting utilities for the Hyperliquid CLI.

This module provides formatting utilities for displaying order information
in a user-friendly way.
"""

from typing import Union
from .base import Formatter
from models import MarketOrder, LimitOrder


class OrderFormatter(Formatter[Union[MarketOrder, LimitOrder]]):
    """
    Formatter class for order data display.
    """

    def format(self, data: Union[MarketOrder, LimitOrder], **kwargs) -> str:
        """
        Format an order for display.

        Args:
            order: The order to format
            **kwargs: Additional formatting options (unused for now)

        Returns:
            str: Formatted order summary
        """
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


__all__ = [
    "OrderFormatter",
]
