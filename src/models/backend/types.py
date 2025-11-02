"""
Backend type definitions for the Hyperliquid CLI.

This module provides data models and exception classes used throughout the backend
components for consistent behavior and debugging.
"""

from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, Field


class ExchangeError(Exception):
    """Base exception class for exchange-related errors."""


class LeverageType(str, Enum):
    """Leverage type for positions."""

    ISOLATED = "isolated"
    CROSS = "cross"


class Ticker(BaseModel):
    """Market ticker data for a trading pair."""

    coin: str = Field(..., description="Symbol of the cryptocurrency")
    mark_price: Decimal = Field(..., description="Current mark price")
    funding_rate: Decimal = Field(..., description="Current funding rate")
    open_interest: Decimal = Field(..., description="Current open interest")


class CoinMetadata(BaseModel):
    """Metadata for a tradable coin."""

    coin: str = Field(..., description="Symbol of the cryptocurrency")
    size_decimals: int = Field(..., description="Number of decimal places for size")
    max_leverage: int = Field(..., description="Maximum allowed leverage")


class PositionInfo(BaseModel):
    """Information about an open position."""

    coin: str = Field(..., description="Symbol of the cryptocurrency")
    size: Decimal = Field(
        ..., description="Position size (positive for long, negative for short)"
    )
    entry_price: Decimal = Field(..., description="Average entry price")
    mark_price: Decimal = Field(..., description="Current mark price")
    unrealized_pnl: Decimal = Field(..., description="Unrealized profit and loss")
    leverage: int = Field(..., description="Position leverage")
    leverage_type: LeverageType = Field(..., description="Type of leverage (isolated or cross)")
    margin_used: Decimal = Field(..., description="Margin used for the position")
    cum_funding: Decimal = Field(..., description="Cumulative funding payments")


__all__ = [
    "ExchangeError",
    "LeverageType",
    "Ticker",
    "CoinMetadata",
    "PositionInfo",
]
