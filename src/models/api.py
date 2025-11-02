"""
API response models and error types for the Hyperliquid CLI.

This module provides Pydantic models and exception classes used for
API communication between the CLI frontend and backend service.
"""

from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================================
# EXCEPTIONS / ERRORS
# ============================================================================


class APIError(Exception):
    """Exception raised when the backend API returns an error response."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class ExchangeError(Exception):
    """Base exception class for exchange-related errors."""


# ============================================================================
# ENUMS / TYPES
# ============================================================================


class HealthStatus(str, Enum):
    """Health status enum."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


class LeverageType(str, Enum):
    """Leverage type for positions."""

    ISOLATED = "isolated"
    CROSS = "cross"


# ============================================================================
# RESPONSE MODELS
# ============================================================================


class HealthResponse(BaseModel):
    """Health check response model."""

    status: HealthStatus


class RootResponse(BaseModel):
    """Root endpoint response model."""

    api: str
    version: str
    status: HealthStatus


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
    leverage_type: LeverageType = Field(
        ..., description="Type of leverage (isolated or cross)"
    )
    margin_used: Decimal = Field(..., description="Margin used for the position")
    cum_funding: Decimal = Field(..., description="Cumulative funding payments")


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Exceptions
    "APIError",
    "ExchangeError",
    # Enums/Types
    "HealthStatus",
    "LeverageType",
    # Response Models
    "HealthResponse",
    "RootResponse",
    "Ticker",
    "CoinMetadata",
    "PositionInfo",
]
