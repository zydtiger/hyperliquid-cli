"""
Order-related models and enums for the Hyperliquid CLI.

This module provides enumerations for order time-in-force settings and other
order-related configurations used in the Hyperliquid trading system.
"""

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field

# ============================================================================
# ORDER ENUMS
# ============================================================================


class OrderSide(str, Enum):
    """Enumeration of order sides."""

    BUY = "buy"
    SELL = "sell"


class OrderTif(Enum):
    """Order Time-in-Force values for Hyperliquid orders."""

    ALO = "ALO"  # At Limit Order - active until cancelled
    IOC = "IOC"  # Immediate or Cancel - execute immediately or cancel
    GTC = "GTC"  # Good Till Cancelled - active until filled or cancelled


class OrderStatus(str, Enum):
    """Order status enumeration."""

    OPEN = "open"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    PARTIALLY_FILLED = "partially_filled"


class OrderType(str, Enum):
    """Order type enumeration."""

    LIMIT = "limit"
    MARKET = "market"


class TriggerType(str, Enum):
    """Trigger order type enumeration."""

    STOP = "stop"
    TAKE = "take"


class OrderTrigger(BaseModel):
    """Trigger configuration for an order."""

    trigger_price: Decimal = Field(..., gt=0, description="Trigger price")
    trigger_type: TriggerType = Field(..., description="Trigger direction semantics")


# ============================================================================
# ORDER MODELS
# ============================================================================


class MarketOrder(BaseModel):
    """Market order model."""

    coin: str = Field(..., description="Trading pair symbol")
    side: OrderSide = Field(..., description="Order side (buy or sell)")
    quantity: Decimal = Field(..., gt=0, description="Order quantity")
    reduce_only: bool = Field(default=False, description="Whether the order is reduce-only")
    trigger: OrderTrigger | None = Field(default=None, description="Optional trigger configuration")


class LimitOrder(BaseModel):
    """Limit order model."""

    coin: str = Field(..., description="Trading pair symbol")
    side: OrderSide = Field(..., description="Order side (buy or sell)")
    quantity: Decimal = Field(..., gt=0, description="Order quantity")
    price: Decimal = Field(..., gt=0, description="Order price")
    reduce_only: bool = Field(default=False, description="Whether the order is reduce-only")
    time_in_force: OrderTif = Field(default=OrderTif.GTC, description="Order time-in-force policy")
    trigger: OrderTrigger | None = Field(default=None, description="Optional trigger configuration")


class OrderResult(BaseModel):
    """Result of an order submission."""

    success: bool = Field(..., description="Whether the order was successfully submitted")
    order_id: int | None = Field(default=None, description="Order ID if submission was successful")
    status: OrderStatus = Field(..., description="Order status")
    message: str = Field(..., description="Response message from exchange")
    error: str | None = Field(default=None, description="Error message if submission failed")


class OrderInfo(BaseModel):
    """Detailed information about an order."""

    order_id: int = Field(..., description="Order identifier")
    coin: str = Field(..., description="Trading pair symbol")
    side: OrderSide = Field(..., description="Order side (buy or sell)")
    order_type: OrderType = Field(..., description="Order type (limit/market)")
    quantity: Decimal = Field(..., description="Order quantity")
    price: Decimal | None = Field(None, description="Order price (None for market orders)")
    filled_quantity: Decimal = Field(..., description="Quantity already filled")
    remaining_quantity: Decimal = Field(..., description="Quantity remaining to be filled")
    average_fill_price: Decimal | None = Field(None, description="Average fill price")
    status: OrderStatus = Field(..., description="Current order status")
    timestamp: int = Field(..., description="Order creation timestamp")
    reduce_only: bool = Field(..., description="Whether the order is reduce-only")
    time_in_force: OrderTif | None = Field(None, description="Time-in-force policy")


class CancelOrderRequest(BaseModel):
    """Request model for cancel order endpoint."""

    order_id: int | str = Field(
        ..., description="Order ID (int) to cancel, or 'all' to cancel all open orders"
    )


class ModifyOrderRequest(BaseModel):
    """Request model for modify order endpoint."""

    order_id: int = Field(..., description="Order ID to modify")
    price: Decimal | None = Field(None, description="New price (None to keep current price)")
    quantity: Decimal | None = Field(
        None, description="New quantity (None to keep current quantity)"
    )


__all__ = [
    "CancelOrderRequest",
    "LimitOrder",
    "MarketOrder",
    "ModifyOrderRequest",
    "OrderInfo",
    "OrderResult",
    "OrderSide",
    "OrderStatus",
    "OrderTif",
    "OrderTrigger",
    "OrderType",
    "TriggerType",
]
