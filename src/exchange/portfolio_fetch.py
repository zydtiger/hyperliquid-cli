"""
Read-only Hyperliquid REST `/info` fetch helpers for portfolio aggregation.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, TypeVar

from models.api import ExchangeError, PositionInfo, StakingDelegation
from models.order import OrderInfo, OrderStatus
from models.portfolio import TodayTradeSummary

from .account_ops import build_active_delegations, extract_mark_prices, parse_positions
from .helpers import decimal_value
from .order_parsing import parse_order_info
from .portfolio_pricing import (
    USDC_PRICE,
    ZERO,
    aggregate_today_fills,
    extract_spot_prices_and_symbols,
)

if TYPE_CHECKING:
    from .hyperliquid_client import HyperliquidClient

T = TypeVar("T")


def _error_text(exc: Exception) -> str:
    """Format an exception cleanly for per-section error reporting."""
    return str(exc) or repr(exc)


def fetch_optional(
    client: HyperliquidClient,
    operation: Callable[[], T],
) -> tuple[T | None, str | None]:
    """Run an optional read-only query with retries, returning (result, error)."""
    try:
        return client.connection.retry_operation(operation), None
    except Exception as exc:
        return None, _error_text(exc)


def fetch_core_perp_state(
    client: HyperliquidClient,
    address: str,
) -> tuple[Mapping[str, Any], list[PositionInfo], dict[str, Decimal]]:
    """Fetch required user_state and active perp positions (single meta call if active)."""

    def _load() -> tuple[Mapping[str, Any], list[PositionInfo], dict[str, Decimal]]:
        try:
            user_state = client.connection.info.user_state(address)
            has_active = any(
                Decimal(str(entry["position"]["szi"])) != ZERO
                for entry in user_state.get("assetPositions", [])
            )
            if not has_active:
                return user_state, [], {}
            meta, asset_ctxs = client.connection.info.meta_and_asset_ctxs()
            perp_marks = extract_mark_prices(meta, asset_ctxs)
            return user_state, parse_positions(user_state, perp_marks), perp_marks
        except ExchangeError:
            raise
        except Exception as exc:
            raise ExchangeError(f"Failed to get portfolio account state: {exc}") from exc

    return client.connection.retry_operation(_load)


def fetch_spot_market_data(
    client: HyperliquidClient,
) -> tuple[dict[str, Decimal], dict[str, str], str | None]:
    """Fetch spot prices and symbol mappings via a single spot_meta_and_asset_ctxs call."""
    payload, error = fetch_optional(client, client.connection.info.spot_meta_and_asset_ctxs)
    if error is not None or payload is None:
        return {"USDC": USDC_PRICE}, {}, error
    spot_meta, spot_ctxs = payload
    spot_prices, spot_symbol_map = extract_spot_prices_and_symbols(spot_meta, spot_ctxs)
    if spot_symbol_map and client._spot_symbol_map is None:
        client._spot_symbol_map = spot_symbol_map
    return spot_prices, spot_symbol_map, None


def load_fallback_prices(
    client: HyperliquidClient,
    needed_coins: set[str],
    spot_prices: Mapping[str, Decimal],
    perp_mark_prices: dict[str, Decimal],
) -> Mapping[str, Any] | None:
    """Lazily load perp marks and all_mids only when any needed coin lacks a spot price."""
    missing = {coin for coin in needed_coins if coin.upper() != "USDC" and coin not in spot_prices}
    if not missing:
        return None

    if not perp_mark_prices:
        meta_payload, _ = fetch_optional(client, client.connection.info.meta_and_asset_ctxs)
        if meta_payload is not None:
            meta, asset_ctxs = meta_payload
            perp_mark_prices.update(extract_mark_prices(meta, asset_ctxs))

    if not {coin for coin in missing if coin not in perp_mark_prices}:
        return None

    mids, _ = fetch_optional(client, client.connection.info.all_mids)
    return mids if isinstance(mids, Mapping) else None


def fetch_raw_staking(
    client: HyperliquidClient,
    address: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """Fetch staking summary, rewards, and active validator delegations."""
    summary, summary_error = fetch_optional(
        client,
        lambda: client.connection.info.user_staking_summary(address),
    )
    if summary_error is not None or not isinstance(summary, Mapping):
        return None, summary_error or "Empty staking summary response"

    delegated = decimal_value(summary.get("delegated"))
    undelegated = decimal_value(summary.get("undelegated"))
    pending = decimal_value(summary.get("totalPendingWithdrawal"))
    pending_count = int(summary.get("nPendingWithdrawals") or 0)

    partial_errors: list[str] = []
    delegations_raw, deleg_err = fetch_optional(
        client,
        lambda: client.connection.info.user_staking_delegations(address),
    )
    if deleg_err is not None:
        partial_errors.append(f"delegations: {deleg_err}")

    rewards_raw, rewards_err = fetch_optional(
        client,
        lambda: client.connection.info.user_staking_rewards(address),
    )
    if rewards_err is not None:
        partial_errors.append(f"rewards: {rewards_err}")

    active_delegations: list[StakingDelegation] = []
    positive_delegations = [
        row for row in (delegations_raw or []) if decimal_value(row.get("amount")) > ZERO
    ]
    if positive_delegations:
        validators_raw, val_err = fetch_optional(
            client,
            lambda: client.connection.info.post("/info", {"type": "validatorSummaries"}),
        )
        if val_err is not None:
            partial_errors.append(f"validators: {val_err}")
        active_delegations = build_active_delegations(
            positive_delegations,
            validators_raw if isinstance(validators_raw, Sequence) else [],
        )

    return {
        "delegated": delegated,
        "undelegated": undelegated,
        "pending_withdrawals": pending,
        "pending_withdrawal_count": pending_count,
        "total_hype": delegated + undelegated + pending,
        "total_reward": sum(
            (decimal_value(row.get("totalAmount")) for row in (rewards_raw or [])),
            start=ZERO,
        ),
        "delegations": active_delegations,
    }, ("; ".join(partial_errors) if partial_errors else None)


def fetch_raw_vaults(
    client: HyperliquidClient,
    address: str,
) -> tuple[list[tuple[str, Decimal]], str | None]:
    """Fetch positive-equity vault deposits for the account."""
    vaults_raw, error = fetch_optional(
        client,
        lambda: client.connection.info.user_vault_equities(address),
    )
    if error is not None:
        return [], error

    vaults: list[tuple[str, Decimal]] = []
    for entry in vaults_raw or []:
        if not isinstance(entry, Mapping):
            continue
        vault_address = str(entry.get("vaultAddress", ""))
        equity = decimal_value(entry.get("equity"))
        if vault_address and equity > ZERO:
            vaults.append((vault_address, equity))
    vaults.sort(key=lambda item: (-item[1], item[0]))
    return vaults, None


def fetch_open_orders(
    client: HyperliquidClient,
    address: str,
    resolve_coin: Callable[[str], str],
) -> tuple[list[OrderInfo], str | None]:
    """Fetch and parse active resting open orders."""
    orders_raw, error = fetch_optional(
        client,
        lambda: client.connection.info.frontend_open_orders(address),
    )
    if error is not None:
        return [], error
    return [
        parse_order_info(order_data, status=OrderStatus.OPEN, resolve_coin=resolve_coin)
        for order_data in (orders_raw or [])
    ], None


def fetch_today_fills(
    client: HyperliquidClient,
    address: str,
    now: datetime,
    resolve_coin: Callable[[str], str],
) -> tuple[dict[str, TodayTradeSummary], str | None]:
    """Fetch and aggregate today's local-day fills per resolved symbol."""
    start_ms = int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
    fills_raw, error = fetch_optional(
        client,
        lambda: client.connection.info.user_fills_by_time(address, start_ms),
    )
    if error is not None:
        return {}, error
    return aggregate_today_fills(fills_raw or [], start_ms, resolve_coin), None
