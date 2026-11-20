"""
Portfolio aggregation engine for HyperliquidClient.

Builds a USD-enriched, read-only PortfolioSnapshot across perpetuals, spot,
staking, vaults, open orders, and today's fills using only Hyperliquid REST
`/info` endpoints.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from models.order import OrderInfo
from models.portfolio import (
    PortfolioAccountSummary,
    PortfolioErrors,
    PortfolioSnapshot,
    PortfolioSource,
    TodayTradeSummary,
)

from .helpers import decimal_value, resolve_spot_symbol
from .portfolio_builders import (
    build_perp_positions,
    build_perps_summary,
    build_portfolio_rows,
    build_spot_balances,
    build_staking_section,
    build_vaults,
    price_spot_holdings,
)
from .portfolio_fetch import (
    fetch_core_perp_state,
    fetch_open_orders,
    fetch_optional,
    fetch_raw_staking,
    fetch_raw_vaults,
    fetch_spot_market_data,
    fetch_today_fills,
    load_fallback_prices,
)
from .portfolio_pricing import (
    ZERO,
    compute_total_assets_and_allocation,
    parse_abstraction_mode,
    resolve_token_price,
)

if TYPE_CHECKING:
    from .hyperliquid_client import HyperliquidClient


def _value_staking(
    raw_staking: Mapping[str, Any] | None,
    hype_price: Decimal | None,
) -> tuple[Decimal | None, Decimal]:
    """Compute staking (market_value, staking_total_usd) from raw staking and HYPE price."""
    if raw_staking is None:
        return None, ZERO
    total_hype: Decimal = raw_staking["total_hype"]
    if total_hype == ZERO:
        return ZERO, ZERO
    if hype_price is None:
        return None, ZERO
    market_value = total_hype * hype_price
    return market_value, market_value


def get_portfolio(
    client: HyperliquidClient,
    *,
    include_open_orders: bool = True,
    include_today: bool = True,
) -> PortfolioSnapshot:
    """Aggregate the account's full Hyperliquid portfolio into a USD-enriched snapshot."""
    address = client.require_account_address()
    now = datetime.now().astimezone()
    errors = PortfolioErrors()

    user_state, raw_positions, perp_mark_prices = fetch_core_perp_state(client, address)
    abstraction_raw, errors.abstraction = fetch_optional(
        client,
        lambda: client.connection.info.query_user_abstraction_state(address),
    )
    abstraction_mode = parse_abstraction_mode(abstraction_raw)

    spot_state, errors.spot = fetch_optional(
        client,
        lambda: client.connection.info.spot_user_state(address),
    )
    raw_spot_holdings = [
        holding
        for holding in (spot_state.get("balances", []) if isinstance(spot_state, Mapping) else [])
        if decimal_value(holding.get("total")) != ZERO
    ]

    spot_prices, spot_symbol_map, spot_pricing_error = fetch_spot_market_data(client)
    raw_staking, errors.staking = fetch_raw_staking(client, address)
    raw_vaults, errors.vaults = fetch_raw_vaults(client, address)

    needed_coins = {str(h.get("coin", "")) for h in raw_spot_holdings if h.get("coin")}
    if raw_staking is not None and raw_staking["total_hype"] > ZERO:
        needed_coins.add("HYPE")
    all_mids = load_fallback_prices(client, needed_coins, spot_prices, perp_mark_prices)

    def _resolve_coin(raw_coin: str) -> str:
        if not raw_coin.startswith("@"):
            return raw_coin
        return resolve_spot_symbol(raw_coin, spot_symbol_map)

    open_orders: list[OrderInfo] = []
    if include_open_orders:
        open_orders, errors.open_orders = fetch_open_orders(client, address, _resolve_coin)

    today_by_symbol: dict[str, TodayTradeSummary] = {}
    if include_today:
        today_by_symbol, errors.today = fetch_today_fills(client, address, now, _resolve_coin)

    priced_spot, spot_total_usd, spot_usdc, unpriced_non_usdc = price_spot_holdings(
        raw_spot_holdings,
        spot_prices,
        perp_mark_prices,
        all_mids,
        spot_symbol_map,
    )
    if spot_pricing_error is not None and unpriced_non_usdc and errors.spot is None:
        errors.spot = f"spot pricing failed: {spot_pricing_error}"

    hype_price = resolve_token_price(
        "HYPE",
        spot_prices,
        perp_mark_prices,
        all_mids=all_mids,
        spot_symbol_map=spot_symbol_map,
    )
    staking_market_value, staking_total_usd = _value_staking(raw_staking, hype_price)
    vaults_total_usd = sum((equity for _, equity in raw_vaults), start=ZERO)

    perps_summary, cross_account_value = build_perps_summary(user_state)
    total_assets, allocation = compute_total_assets_and_allocation(
        abstraction_mode=abstraction_mode,
        spot_failed=errors.spot is not None and not raw_spot_holdings,
        perps_account_value=perps_summary.account_value,
        cross_account_value=cross_account_value,
        perp_positions=raw_positions,
        spot_total_usd=spot_total_usd,
        spot_usdc=spot_usdc,
        staking_total_usd=staking_total_usd,
        vaults_total_usd=vaults_total_usd,
    )

    perp_positions = build_perp_positions(raw_positions, total_assets, today_by_symbol)
    spot_balances = build_spot_balances(priced_spot, total_assets, today_by_symbol)
    staking = build_staking_section(
        raw_staking, hype_price, staking_market_value, staking_total_usd, total_assets
    )
    vaults = build_vaults(raw_vaults, total_assets)

    return PortfolioSnapshot(
        ok=True,
        as_of=now.isoformat(timespec="seconds"),
        source=PortfolioSource(
            provider="hyperliquid-cli",
            network=client.config.hyperliquid.network.value,
            account_address=address,
            abstraction_mode=abstraction_mode,
        ),
        account=PortfolioAccountSummary(
            currency="USD",
            total_assets=total_assets,
            perps=perps_summary,
            spot_total_usd=spot_total_usd,
            spot_usdc=spot_usdc,
            staking_total_usd=staking_total_usd,
            vaults_total_usd=vaults_total_usd,
        ),
        allocation=allocation,
        portfolio=build_portfolio_rows(spot_balances, staking, perp_positions, vaults),
        perp_positions=perp_positions,
        spot_balances=spot_balances,
        staking=staking,
        vaults=vaults,
        open_orders=open_orders,
        closed_today=[today_by_symbol[key] for key in sorted(today_by_symbol)],
        errors=errors,
    )
