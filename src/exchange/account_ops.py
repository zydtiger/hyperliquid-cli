"""
Account, balance, staking, PnL, and position query operations for HyperliquidClient.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from models.api import (
    BalanceInfo,
    ExchangeError,
    LeverageType,
    PnlHistoryCatalog,
    PositionInfo,
    SpotBalance,
    StakingDelegation,
    StakingInfo,
    StakingStatus,
)

from .helpers import calculate_removable_margin, decimal_value, optional_decimal
from .pnl_history import build_pnl_history_catalog

if TYPE_CHECKING:
    from .hyperliquid_client import HyperliquidClient


def extract_mark_prices(meta: Any, asset_ctxs: Any) -> dict[str, Decimal]:
    """Build a coin -> mark_price lookup map from a single meta_and_asset_ctxs payload."""
    if not meta or "universe" not in meta:
        raise ExchangeError("Failed to retrieve market metadata from exchange")

    mark_prices: dict[str, Decimal] = {}
    for asset, ctx in zip(meta["universe"], asset_ctxs, strict=False):
        mark_px = ctx.get("markPx")
        if mark_px is not None:
            mark_prices[asset["name"]] = Decimal(str(mark_px))
    return mark_prices


def build_active_delegations(
    delegations: Sequence[Mapping[str, Any]],
    validator_summaries: Sequence[Mapping[str, Any]],
) -> list[StakingDelegation]:
    """Build positive-amount staking delegations enriched with validator metadata."""
    validators_by_address = {
        str(summary.get("validator", "")): summary for summary in validator_summaries
    }
    active_delegations: list[StakingDelegation] = []
    for delegation in delegations:
        amount = decimal_value(delegation.get("amount"))
        if amount <= 0:
            continue
        validator_id = str(delegation.get("validator", ""))
        validator_meta = validators_by_address.get(validator_id, {})
        commission_raw = validator_meta.get("commission")
        active_delegations.append(
            StakingDelegation(
                validator=validator_id,
                name=str(validator_meta.get("name", validator_id)),
                commission=(decimal_value(commission_raw) if commission_raw is not None else None),
                amount=amount,
            )
        )
    return active_delegations


def parse_positions(
    user_state: Mapping[str, Any],
    mark_prices: Mapping[str, Decimal],
) -> list[PositionInfo]:
    """Parse active perpetual positions from user_state using pre-fetched mark prices."""
    active_entries = [
        entry["position"]
        for entry in user_state.get("assetPositions", [])
        if Decimal(str(entry["position"]["szi"])) != 0
    ]
    positions: list[PositionInfo] = []
    for pos in active_entries:
        coin = str(pos["coin"])
        if coin not in mark_prices:
            raise ExchangeError(f"Coin '{coin}' not found in available trading pairs")

        size = Decimal(str(pos["szi"]))
        entry_price = Decimal(str(pos["entryPx"]))
        position_value = Decimal(str(pos["positionValue"]))
        mark_price = mark_prices[coin]
        unrealized_pnl = Decimal(str(pos["unrealizedPnl"]))
        leverage = int(pos["leverage"]["value"])
        leverage_type = LeverageType(pos["leverage"]["type"])
        margin_used = Decimal(str(pos["marginUsed"]))
        removable_margin = calculate_removable_margin(
            position_value=position_value,
            leverage=leverage,
            margin_used=margin_used,
            leverage_type=leverage_type,
        )
        cum_funding_data = pos.get("cumFunding", {})
        cum_funding = Decimal(str(cum_funding_data.get("allTime", "0")))
        max_leverage_raw = pos.get("maxLeverage")

        positions.append(
            PositionInfo(
                coin=coin,
                size=size,
                entry_price=entry_price,
                mark_price=mark_price,
                unrealized_pnl=unrealized_pnl,
                leverage=leverage,
                leverage_type=leverage_type,
                margin_used=margin_used,
                removable_margin=removable_margin,
                cum_funding=cum_funding,
                position_value=position_value,
                liquidation_price=optional_decimal(pos.get("liquidationPx")),
                return_on_equity=optional_decimal(pos.get("returnOnEquity")),
                max_leverage=int(max_leverage_raw) if max_leverage_raw is not None else None,
                funding_since_open=optional_decimal(cum_funding_data.get("sinceOpen")),
            )
        )

    return positions


def get_balances(client: HyperliquidClient) -> BalanceInfo:
    """Get comprehensive balance information for the configured account."""
    address = client.require_account_address()

    def _get_balances() -> BalanceInfo:
        try:
            user_state = client.connection.info.user_state(address)
            margin_summary = user_state.get("marginSummary", {})
            errors: dict[str, str] = {}

            spot_balances: list[SpotBalance] = []
            try:
                spot_state = client.connection.info.spot_user_state(address)
                for holding in spot_state.get("balances", []):
                    total = Decimal(holding.get("total", "0"))
                    if total != 0:
                        spot_balances.append(
                            SpotBalance(
                                coin=holding["coin"],
                                total=total,
                                hold=decimal_value(holding.get("hold")),
                                entry_ntl=optional_decimal(holding.get("entryNtl")),
                            )
                        )
            except Exception as exc:
                spot_balances = []
                errors["spot"] = str(exc) or repr(exc)

            staking_info: StakingInfo | None = None
            try:
                staking_summary = client.connection.info.user_staking_summary(address)
                staking_info = StakingInfo(
                    delegated_amount=Decimal(staking_summary.get("delegated", "0")),
                    undelegated_amount=Decimal(staking_summary.get("undelegated", "0")),
                    pending_withdrawals=Decimal(staking_summary.get("totalPendingWithdrawal", "0")),
                    pending_withdrawal_count=staking_summary.get("nPendingWithdrawals", 0),
                )
            except Exception as exc:
                staking_info = None
                errors["staking"] = str(exc) or repr(exc)

            return BalanceInfo(
                perps_account_value=Decimal(margin_summary.get("accountValue", "0")),
                perps_total_position_value=Decimal(margin_summary.get("totalNtlPos", "0")),
                perps_total_raw_usd=Decimal(margin_summary.get("totalRawUsd", "0")),
                perps_margin_used=Decimal(margin_summary.get("totalMarginUsed", "0")),
                perps_withdrawable=Decimal(user_state.get("withdrawable", "0")),
                spot_balances=spot_balances,
                staking_info=staking_info,
                errors=errors,
            )

        except Exception as e:
            raise ExchangeError(f"Failed to get balance information: {e}") from e

    return client.connection.retry_operation(_get_balances)


def get_pnl_history(client: HyperliquidClient) -> PnlHistoryCatalog:
    """Get all supported total/perp/spot PnL history windows for the account."""
    address = client.require_account_address()

    def _get_pnl_history() -> PnlHistoryCatalog:
        try:
            portfolio = client.connection.info.portfolio(address)
            return build_pnl_history_catalog(portfolio)
        except Exception as e:
            raise ExchangeError(f"Failed to get PnL history: {e}") from e

    return client.connection.retry_operation(_get_pnl_history)


def get_staking_status(client: HyperliquidClient) -> StakingStatus:
    """Get staking status for the configured account."""
    address = client.require_account_address()

    def _get_staking_status() -> StakingStatus:
        try:
            staking_summary = client.connection.info.user_staking_summary(address)
            delegations = client.connection.info.user_staking_delegations(address)
            rewards = client.connection.info.user_staking_rewards(address)
            validator_summaries = client.connection.info.post(
                "/info", {"type": "validatorSummaries"}
            )
            active_delegations = build_active_delegations(delegations, validator_summaries)
            pending_count_raw = staking_summary.get("nPendingWithdrawals")

            return StakingStatus(
                total_staked=decimal_value(staking_summary.get("delegated")),
                total_reward=sum(
                    (decimal_value(reward.get("totalAmount")) for reward in rewards),
                    start=Decimal("0"),
                ),
                delegations=active_delegations,
                undelegated=optional_decimal(staking_summary.get("undelegated")),
                pending_withdrawals=optional_decimal(staking_summary.get("totalPendingWithdrawal")),
                pending_withdrawal_count=(
                    int(pending_count_raw) if pending_count_raw is not None else None
                ),
            )
        except Exception as e:
            raise ExchangeError(f"Failed to get staking status: {e}") from e

    return client.connection.retry_operation(_get_staking_status)


def get_positions(client: HyperliquidClient) -> list[PositionInfo]:
    """Get current open positions using a single meta_and_asset_ctxs call for mark prices."""
    address = client.require_account_address()

    def _get_positions() -> list[PositionInfo]:
        user_state = client.connection.info.user_state(address)
        has_active = any(
            Decimal(str(entry["position"]["szi"])) != 0
            for entry in user_state.get("assetPositions", [])
        )
        if not has_active:
            return []

        meta, asset_ctxs = client.connection.info.meta_and_asset_ctxs()
        mark_prices = extract_mark_prices(meta, asset_ctxs)
        return parse_positions(user_state, mark_prices)

    return client.connection.retry_operation(_get_positions)
