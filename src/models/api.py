"""
API response models and error types for the Hyperliquid CLI.

This module provides Pydantic models and exception classes used for
API communication between the CLI frontend and backend service.
"""

from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

PnlWindow = Literal["1d", "3d", "7d", "1m", "3m", "6m", "1y", "all"]
PNL_WINDOW_ORDER: tuple[PnlWindow, ...] = ("1d", "3d", "7d", "1m", "3m", "6m", "1y", "all")
DEFAULT_PNL_WINDOW: PnlWindow = "7d"
WatchInterval = Literal["1m", "5m", "15m", "1h", "4h", "1d"]
WATCH_INTERVAL_ORDER: tuple[WatchInterval, ...] = ("1m", "5m", "15m", "1h", "4h", "1d")
DEFAULT_WATCH_INTERVAL: WatchInterval = "5m"
WATCH_INTERVAL_MS: dict[WatchInterval, int] = {
    "1m": 60_000,
    "5m": 5 * 60_000,
    "15m": 15 * 60_000,
    "1h": 60 * 60_000,
    "4h": 4 * 60 * 60_000,
    "1d": 24 * 60 * 60_000,
}
DEFAULT_WATCH_ORDER_BOOK_DEPTH = 10
MIN_WATCH_ORDER_BOOK_DEPTH = 1
MAX_WATCH_ORDER_BOOK_DEPTH = 50

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
    open_interest: Decimal | None = Field(
        ...,
        description="Current open interest in USD notional for perps, null for spot markets",
    )


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


class StakingDelegation(BaseModel):
    """Active staking delegation for a specific validator."""

    validator: str = Field(..., description="Validator identifier")
    name: str = Field(..., description="Validator display name")
    commission: Decimal | None = Field(None, description="Validator commission rate")
    amount: Decimal = Field(..., description="Delegated HYPE amount")


class StakingStatus(BaseModel):
    """Dedicated staking status view for the configured account."""

    total_staked: Decimal = Field(..., description="Total staked HYPE amount")
    total_reward: Decimal = Field(..., description="Total rewarded HYPE amount")
    delegations: list[StakingDelegation] = Field(
        default_factory=list,
        description="Active validator delegations with positive amounts",
    )


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


class PnlPoint(BaseModel):
    """Single point in a PnL history series."""

    time: int = Field(..., description="Unix timestamp in milliseconds")
    total_pnl: Decimal = Field(..., description="Total account PnL at this time")
    perp_pnl: Decimal = Field(..., description="Perpetuals-only PnL at this time")
    spot_pnl: Decimal = Field(..., description="Spot-only PnL at this time")


class PnlHistory(BaseModel):
    """Time series of account PnL values for a fixed window."""

    window: PnlWindow = Field(..., description="Window label for the PnL series")
    points: list[PnlPoint] = Field(default_factory=list, description="Ordered PnL samples")


class PnlHistoryCatalog(BaseModel):
    """Ordered collection of PnL histories for all supported windows."""

    default_window: PnlWindow = Field(..., description="Initial window shown in the TUI")
    histories: list[PnlHistory] = Field(
        default_factory=list,
        description="Ordered PnL history windows supported by the frontend",
    )


class OrderBookLevel(BaseModel):
    """Single order book level."""

    price: Decimal = Field(..., description="Order book price level")
    size: Decimal = Field(..., description="Aggregated size at this level")


class WatchCandle(BaseModel):
    """Single OHLC candle for the watch TUI."""

    open_time: int = Field(..., description="Candle open time in Unix milliseconds")
    close_time: int = Field(..., description="Candle close time in Unix milliseconds")
    open: Decimal = Field(..., description="Candle open price")
    high: Decimal = Field(..., description="Candle high price")
    low: Decimal = Field(..., description="Candle low price")
    close: Decimal = Field(..., description="Candle close price")
    is_closed: bool = Field(..., description="Whether the candle is finalized")


class WatchSnapshot(BaseModel):
    """Normalized live watch snapshot for a single supported market."""

    coin: str = Field(..., description="Supported market symbol")
    interval: WatchInterval = Field(..., description="Requested candle interval")
    mark_price: Decimal = Field(..., description="Current mark price")
    open_interest: Decimal | None = Field(
        ...,
        description="Current open interest in USD notional for perps, null for spot markets",
    )
    updated_at: int = Field(..., description="Last snapshot update time in Unix milliseconds")
    candles: list[WatchCandle] = Field(
        default_factory=list,
        description="Ordered watch candles from oldest to newest",
    )
    bids: list[OrderBookLevel] = Field(
        default_factory=list,
        description="Top bid levels ordered from highest to lowest price",
    )
    asks: list[OrderBookLevel] = Field(
        default_factory=list,
        description="Top ask levels ordered from lowest to highest price",
    )
    order_book_depth: int = Field(
        default=DEFAULT_WATCH_ORDER_BOOK_DEPTH,
        description="Effective per-side order book depth returned in this snapshot",
    )
    default_interval: WatchInterval = Field(
        default=DEFAULT_WATCH_INTERVAL,
        description="Initial candle interval shown in the watch TUI",
    )
    supported_intervals: list[WatchInterval] = Field(
        default_factory=lambda: list(WATCH_INTERVAL_ORDER),
        description="Supported candle intervals for the watch TUI",
    )
