"""
Portfolio aggregation models for the Hyperliquid CLI.

Provides typed Pydantic models for USD-enriched Hyperliquid portfolio
snapshots and JSON serialization compatible with downstream portfolio
research adapters.
"""

from decimal import Decimal
from enum import Enum
from typing import Any, Literal, cast

from pydantic import BaseModel, Field

from .api import LeverageType, StakingDelegation
from .order import OrderInfo

PortfolioBucket = Literal["spot", "staking", "perp", "vault"]
PositionSide = Literal["LONG", "SHORT"]


def _to_json_value(value: Any) -> Any:
    """Recursively convert Decimals and Enums into JSON-serializable primitives."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _to_json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_value(item) for item in value]
    return value


class PortfolioSource(BaseModel):
    """Source metadata describing how the portfolio snapshot was fetched."""

    provider: str = Field(default="hyperliquid-cli", description="Adapter provider identifier")
    network: str = Field(..., description="Hyperliquid network name (mainnet or testnet)")
    account_address: str = Field(..., description="Queried Hyperliquid account address")
    abstraction_mode: str | None = Field(
        default=None,
        description="Hyperliquid account abstraction mode reported by userAbstraction",
    )


class PerpsAccountSummary(BaseModel):
    """Perpetuals clearinghouse margin and equity summary in USD."""

    account_value: Decimal = Field(..., description="Perpetuals clearinghouse account value")
    total_position_value: Decimal = Field(..., description="Total perpetual notional exposure")
    total_raw_usd: Decimal = Field(..., description="Perpetuals clearinghouse raw USD value")
    margin_used: Decimal = Field(..., description="Total margin used by perpetual positions")
    cross_maintenance_margin_used: Decimal = Field(
        default=Decimal("0"),
        description="Cross-margin maintenance margin currently required",
    )
    withdrawable: Decimal = Field(..., description="Withdrawable USD reported by user_state")


class PortfolioAccountSummary(BaseModel):
    """Account-level USD equity summary across perps, spot, staking, and vaults."""

    currency: str = Field(default="USD", description="Reporting currency")
    total_assets: Decimal = Field(
        ...,
        description=(
            "Total USD equity across perps, spot, staking, and vaults without "
            "double-counting shared USDC in unified/portfolio-margin modes"
        ),
    )
    perps: PerpsAccountSummary = Field(..., description="Perpetuals margin summary")
    spot_total_usd: Decimal = Field(..., description="Total USD value of all spot balances")
    spot_usdc: Decimal = Field(..., description="Spot USDC balance in USD")
    staking_total_usd: Decimal = Field(..., description="Total USD value of staked HYPE")
    vaults_total_usd: Decimal = Field(..., description="Total USD equity across vaults")


class AllocationBucket(BaseModel):
    """Non-overlapping equity bucket inside portfolio allocation."""

    name: str = Field(..., description="Allocation sleeve name")
    value: Decimal = Field(..., description="Bucket equity value in USD")
    share_pct: Decimal = Field(..., description="Share of total_assets in percentage points")


class PortfolioAllocation(BaseModel):
    """Non-overlapping allocation breakdown summing to total_assets."""

    total_assets: Decimal = Field(..., description="Total portfolio assets in USD")
    buckets: list[AllocationBucket] = Field(
        default_factory=list,
        description="Non-overlapping equity buckets summing to total_assets",
    )


class TodayTradeSummary(BaseModel):
    """Aggregated filled-order activity for one symbol during the current local day."""

    symbol: str = Field(..., description="Resolved trading symbol")
    buy_quantity: Decimal = Field(default=Decimal("0"), description="Total bought quantity today")
    buy_value: Decimal = Field(default=Decimal("0"), description="Total bought notional in USD")
    sell_quantity: Decimal = Field(default=Decimal("0"), description="Total sold quantity today")
    sell_value: Decimal = Field(default=Decimal("0"), description="Total sold notional in USD")
    fee_usdc: Decimal = Field(default=Decimal("0"), description="Total fees converted to USDC")
    realized_pnl: Decimal = Field(
        default=Decimal("0"),
        description="Total realized closed PnL in USDC",
    )


class PortfolioRow(BaseModel):
    """Unified holding or position row across spot, staking, perp, and vault sleeves."""

    bucket: PortfolioBucket = Field(..., description="Asset sleeve type")
    symbol: str = Field(..., description="Asset symbol or vault address")
    side: PositionSide = Field(..., description="Exposure direction (LONG or SHORT)")
    quantity: Decimal = Field(..., description="Unsigned token quantity or position size")
    mark_price: Decimal | None = Field(default=None, description="Current mark price in USD")
    market_value: Decimal = Field(
        ...,
        description="USD market value for spot/staking/vault, or gross notional USD for perps",
    )
    equity_value: Decimal = Field(
        ...,
        description="USD net equity (market_value for spot/staking/vault; margin + uPnL for perps)",
    )
    share_pct: Decimal = Field(
        ...,
        description="Exposure share of total_assets in percentage points",
    )
    unrealized_pnl: Decimal | None = Field(
        default=None,
        description="Unrealized PnL in USD when applicable",
    )
    today: TodayTradeSummary | None = Field(
        default=None,
        description="Aggregated today's fills for this holding or position",
    )


class PortfolioPerpPosition(BaseModel):
    """Detailed perpetual position entry inside a portfolio snapshot."""

    coin: str = Field(..., description="Perpetual market symbol")
    side: PositionSide = Field(..., description="Position direction (LONG or SHORT)")
    size: Decimal = Field(..., description="Signed position size (positive long, negative short)")
    entry_price: Decimal = Field(..., description="Average entry price in USD")
    mark_price: Decimal = Field(..., description="Current mark price in USD")
    position_value: Decimal = Field(..., description="Gross notional position value in USD")
    unrealized_pnl: Decimal = Field(..., description="Unrealized PnL in USD")
    return_on_equity: Decimal | None = Field(default=None, description="Return on equity ratio")
    leverage: int = Field(..., description="Position leverage")
    leverage_type: LeverageType = Field(..., description="Leverage mode (cross or isolated)")
    max_leverage: int | None = Field(default=None, description="Maximum allowed leverage")
    margin_used: Decimal = Field(..., description="Allocated margin used in USD")
    removable_margin: Decimal | None = Field(
        default=None,
        description="Estimated removable isolated margin in USD (null for cross)",
    )
    liquidation_price: Decimal | None = Field(
        default=None,
        description="Estimated liquidation price in USD",
    )
    cum_funding_all_time: Decimal = Field(..., description="Cumulative funding payments all-time")
    funding_since_open: Decimal | None = Field(
        default=None,
        description="Cumulative funding payments since position opened",
    )
    share_pct: Decimal = Field(
        ...,
        description="Gross notional share of total_assets in percentage points",
    )
    today: TodayTradeSummary | None = Field(
        default=None,
        description="Aggregated today's fills for this perp symbol",
    )


class PortfolioSpotBalance(BaseModel):
    """USD-valued spot token balance entry inside a portfolio snapshot."""

    coin: str = Field(..., description="Spot token symbol")
    total: Decimal = Field(..., description="Total spot token balance")
    hold: Decimal = Field(..., description="Balance currently on hold")
    available: Decimal = Field(..., description="Available balance (total - hold)")
    entry_ntl: Decimal | None = Field(default=None, description="Spot entry notional in USD")
    mark_price: Decimal | None = Field(default=None, description="Current spot mark price in USD")
    market_value: Decimal | None = Field(
        default=None,
        description="Current USD market value (null if token could not be priced)",
    )
    share_pct: Decimal = Field(..., description="Share of total_assets in percentage points")
    today: TodayTradeSummary | None = Field(
        default=None,
        description="Aggregated today's spot fills for this token",
    )


class PortfolioStaking(BaseModel):
    """USD-valued HYPE staking state inside a portfolio snapshot."""

    delegated: Decimal = Field(..., description="Delegated HYPE amount")
    undelegated: Decimal = Field(..., description="Undelegated staking HYPE amount")
    pending_withdrawals: Decimal = Field(..., description="Pending unstaking withdrawal HYPE")
    pending_withdrawal_count: int = Field(..., description="Number of pending staking withdrawals")
    total_hype: Decimal = Field(
        ...,
        description="Total HYPE in staking (delegated + undelegated + pending_withdrawals)",
    )
    total_reward: Decimal = Field(..., description="Total rewarded HYPE amount")
    mark_price: Decimal | None = Field(default=None, description="Current HYPE mark price in USD")
    market_value: Decimal | None = Field(
        default=None,
        description="Total USD market value of staking HYPE",
    )
    share_pct: Decimal = Field(..., description="Share of total_assets in percentage points")
    delegations: list[StakingDelegation] = Field(
        default_factory=list,
        description="Active validator delegations with positive amounts",
    )


class PortfolioVault(BaseModel):
    """Vault or HLP deposit equity entry inside a portfolio snapshot."""

    vault_address: str = Field(..., description="Vault contract address")
    equity: Decimal = Field(..., description="Current vault equity in USD")
    share_pct: Decimal = Field(..., description="Share of total_assets in percentage points")


class PortfolioErrors(BaseModel):
    """Per-section error map (null when the section succeeded or was skipped)."""

    spot: str | None = Field(default=None, description="Spot balance/pricing error")
    staking: str | None = Field(default=None, description="Staking query error")
    vaults: str | None = Field(default=None, description="Vault equities query error")
    open_orders: str | None = Field(default=None, description="Open orders query error")
    today: str | None = Field(default=None, description="Today's fills query error")
    abstraction: str | None = Field(default=None, description="Abstraction mode query error")


class PortfolioSnapshot(BaseModel):
    """Complete Hyperliquid account and portfolio snapshot."""

    ok: bool = Field(default=True, description="Success flag")
    as_of: str = Field(..., description="Local ISO-8601 snapshot timestamp")
    source: PortfolioSource = Field(..., description="Snapshot source metadata")
    account: PortfolioAccountSummary = Field(..., description="USD account totals")
    allocation: PortfolioAllocation = Field(..., description="Non-overlapping allocation buckets")
    portfolio: list[PortfolioRow] = Field(
        default_factory=list,
        description="Unified holdings and positions sorted by descending share_pct",
    )
    perp_positions: list[PortfolioPerpPosition] = Field(
        default_factory=list,
        description="Detailed open perpetual positions",
    )
    spot_balances: list[PortfolioSpotBalance] = Field(
        default_factory=list,
        description="Detailed USD-valued spot token balances",
    )
    staking: PortfolioStaking | None = Field(
        default=None,
        description="Staking state and USD valuation (null if staking query failed)",
    )
    vaults: list[PortfolioVault] = Field(
        default_factory=list,
        description="Vault and HLP equity positions",
    )
    open_orders: list[OrderInfo] = Field(
        default_factory=list,
        description="Active resting open orders",
    )
    closed_today: list[TodayTradeSummary] = Field(
        default_factory=list,
        description="Today's aggregated fills for symbols not currently held",
    )
    errors: PortfolioErrors = Field(
        default_factory=PortfolioErrors,
        description="Per-section error map",
    )

    def to_json_dict(self) -> dict[str, Any]:
        """Serialize snapshot to JSON-compatible dict with float numeric values."""
        serialized = _to_json_value(self.model_dump(mode="python"))
        return cast(dict[str, Any], serialized)
