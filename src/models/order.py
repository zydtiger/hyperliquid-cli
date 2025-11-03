"""
Order-related models and enums for the Hyperliquid CLI.

This module provides enumerations for order time-in-force settings and other
order-related configurations used in the Hyperliquid trading system.
"""

from enum import Enum
from pydantic import BaseModel, Field
from decimal import Decimal


class OrderSide(str, Enum):
    """Enumeration of order sides."""

    BUY = "buy"
    SELL = "sell"


class OrderTif(Enum):
    """Order Time-in-Force values for Hyperliquid orders."""

    ALO = "ALO"  # At Limit Order - active until cancelled
    IOC = "IOC"  # Immediate or Cancel - execute immediately or cancel
    GTC = "GTC"  # Good Till Cancelled - active until filled or cancelled


class MarketOrder(BaseModel):
    coin: str = Field(..., description="Trading pair symbol")
    side: OrderSide = Field(..., description="Order side (buy or sell)")
    quantity: Decimal = Field(..., gt=0, description="Order quantity")
    reduce_only: bool = Field(
        default=False, description="Whether the order is reduce-only"
    )


class LimitOrder(BaseModel):
    coin: str = Field(..., description="Trading pair symbol")
    side: OrderSide = Field(..., description="Order side (buy or sell)")
    quantity: Decimal = Field(..., gt=0, description="Order quantity")
    price: Decimal = Field(..., gt=0, description="Order price")
    reduce_only: bool = Field(
        default=False, description="Whether the order is reduce-only"
    )
    time_in_force: OrderTif = Field(
        default=OrderTif.GTC, description="Order time-in-force policy"
    )


__all__ = [
    "OrderSide",
    "OrderTif",
    "MarketOrder",
    "LimitOrder",
]
