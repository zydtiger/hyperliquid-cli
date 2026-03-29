"""
API response models and error types for the Hyperliquid CLI.

This module provides Pydantic models and exception classes used for
API communication between the CLI frontend and backend service.
"""

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field

# ============================================================================
# EXCEPTIONS / ERRORS
# ============================================================================


class APIError(Exception):
    """Exception raised when the backend API returns an error response."""

    def __init__(self, message: str, status_code: int | None = None):
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
    size: Decimal = Field(..., description="Position size (positive for long, negative for short)")
    entry_price: Decimal = Field(..., description="Average entry price")
    mark_price: Decimal = Field(..., description="Current mark price")
    unrealized_pnl: Decimal = Field(..., description="Unrealized profit and loss")
    leverage: int = Field(..., description="Position leverage")
    leverage_type: LeverageType = Field(..., description="Type of leverage (isolated or cross)")
    margin_used: Decimal = Field(..., description="Margin used for the position")
    removable_margin: Decimal | None = Field(
        None,
        description=(
            "Estimated removable isolated margin based on current position margin "
            "requirements; null for cross positions"
        ),
    )
    cum_funding: Decimal = Field(..., description="Cumulative funding payments")


class SpotBalance(BaseModel):
    """Spot balance information for a specific coin."""

    coin: str = Field(..., description="Symbol of the cryptocurrency")
    total: Decimal = Field(..., description="Total balance")


class StakingInfo(BaseModel):
    """Staking information including delegations and rewards."""

    delegated_amount: Decimal = Field(..., description="Total delegated amount")
    undelegated_amount: Decimal = Field(..., description="Total undelegated amount")
    pending_withdrawals: Decimal = Field(..., description="Total pending withdrawal amount")
    pending_withdrawal_count: int = Field(..., description="Number of pending withdrawals")


class BalanceInfo(BaseModel):
    """Comprehensive balance information for a Hyperliquid account."""

    # Perpetuals Account (from user_state)
    perps_account_value: Decimal = Field(..., description="Perpetuals account value")
    perps_total_position_value: Decimal = Field(..., description="Total notional position size")
    perps_total_raw_usd: Decimal = Field(..., description="Remaining Raw USD")
    perps_margin_used: Decimal = Field(..., description="Total margin used by perpetual positions")
    perps_withdrawable: Decimal = Field(..., description="Available withdrawal amount")

    # Spot Balances
    spot_balances: list[SpotBalance] = Field(default_factory=list, description="Spot coin balances")

    # Staking Information
    staking_info: StakingInfo | None = Field(None, description="Staking delegations and rewards")


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "APIError",
    "BalanceInfo",
    "CoinMetadata",
    "ExchangeError",
    "HealthResponse",
    "HealthStatus",
    "LeverageType",
    "PositionInfo",
    "RootResponse",
    "SpotBalance",
    "StakingInfo",
    "Ticker",
]
