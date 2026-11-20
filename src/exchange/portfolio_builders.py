"""
Pure assembly builders converting fetched Hyperliquid payloads into PortfolioSnapshot sections.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from models.api import PositionInfo
from models.portfolio import (
    PerpsAccountSummary,
    PortfolioPerpPosition,
    PortfolioRow,
    PortfolioSpotBalance,
    PortfolioStaking,
    PortfolioVault,
    PositionSide,
    TodayTradeSummary,
)

from .helpers import decimal_value, optional_decimal
from .portfolio_pricing import ZERO, resolve_token_price, share_pct

ONE = Decimal("1")

PricedSpotRow = tuple[str, Decimal, Decimal, Decimal | None, Decimal | None, Decimal | None]


def build_perps_summary(
    user_state: Mapping[str, Any],
) -> tuple[PerpsAccountSummary, Decimal | None]:
    """Extract PerpsAccountSummary and optional crossMarginSummary.accountValue."""
    margin_summary = user_state.get("marginSummary", {})
    cross_summary = user_state.get("crossMarginSummary")
    perps_summary = PerpsAccountSummary(
        account_value=decimal_value(margin_summary.get("accountValue")),
        total_position_value=decimal_value(margin_summary.get("totalNtlPos")),
        total_raw_usd=decimal_value(margin_summary.get("totalRawUsd")),
        margin_used=decimal_value(margin_summary.get("totalMarginUsed")),
        cross_maintenance_margin_used=decimal_value(user_state.get("crossMaintenanceMarginUsed")),
        withdrawable=decimal_value(user_state.get("withdrawable")),
    )
    cross_account_value = (
        optional_decimal(cross_summary.get("accountValue"))
        if isinstance(cross_summary, Mapping)
        else None
    )
    return perps_summary, cross_account_value


def price_spot_holdings(
    raw_spot_holdings: Sequence[Mapping[str, Any]],
    spot_prices: Mapping[str, Decimal],
    perp_mark_prices: Mapping[str, Decimal],
    all_mids: Mapping[str, Any] | None,
    spot_symbol_map: Mapping[str, str],
) -> tuple[list[PricedSpotRow], Decimal, Decimal, bool]:
    """Value raw spot holdings in USD, returning rows, spot_total_usd, spot_usdc, unpriced flag."""
    priced_rows: list[PricedSpotRow] = []
    spot_total_usd = ZERO
    spot_usdc = ZERO
    unpriced_non_usdc = False

    for holding in raw_spot_holdings:
        coin = str(holding["coin"])
        total = decimal_value(holding.get("total"))
        hold = decimal_value(holding.get("hold"))
        entry_ntl = optional_decimal(holding.get("entryNtl"))
        mark_price = resolve_token_price(
            coin,
            spot_prices,
            perp_mark_prices,
            all_mids=all_mids,
            spot_symbol_map=spot_symbol_map,
        )
        market_value = total * mark_price if mark_price is not None else None
        if market_value is not None:
            spot_total_usd += market_value
            if coin.upper() == "USDC":
                spot_usdc += market_value
        elif coin.upper() != "USDC":
            unpriced_non_usdc = True
        priced_rows.append((coin, total, hold, entry_ntl, mark_price, market_value))

    return priced_rows, spot_total_usd, spot_usdc, unpriced_non_usdc


def _pop_spot_today(
    coin: str,
    today_by_symbol: dict[str, TodayTradeSummary],
) -> TodayTradeSummary | None:
    """Pop today's spot fill summary for a held non-USDC spot token."""
    if coin.upper() == "USDC":
        return None
    primary = f"{coin}/USDC"
    if primary in today_by_symbol:
        return today_by_symbol.pop(primary)
    prefix = f"{coin}/"
    for key in sorted(today_by_symbol):
        if key.startswith(prefix):
            return today_by_symbol.pop(key)
    return None


def build_perp_positions(
    raw_positions: Sequence[PositionInfo],
    total_assets: Decimal,
    today_by_symbol: dict[str, TodayTradeSummary],
) -> list[PortfolioPerpPosition]:
    """Build detailed PortfolioPerpPosition entries sorted by descending position_value."""
    items: list[PortfolioPerpPosition] = []
    for pos in raw_positions:
        notional = abs(
            pos.position_value if pos.position_value is not None else pos.size * pos.mark_price
        )
        side: PositionSide = "LONG" if pos.size > ZERO else "SHORT"
        items.append(
            PortfolioPerpPosition(
                coin=pos.coin,
                side=side,
                size=pos.size,
                entry_price=pos.entry_price,
                mark_price=pos.mark_price,
                position_value=notional,
                unrealized_pnl=pos.unrealized_pnl,
                return_on_equity=pos.return_on_equity,
                leverage=pos.leverage,
                leverage_type=pos.leverage_type,
                max_leverage=pos.max_leverage,
                margin_used=pos.margin_used,
                removable_margin=pos.removable_margin,
                liquidation_price=pos.liquidation_price,
                cum_funding_all_time=pos.cum_funding,
                funding_since_open=pos.funding_since_open,
                share_pct=share_pct(notional, total_assets),
                today=today_by_symbol.pop(pos.coin, None),
            )
        )
    items.sort(key=lambda item: (-item.position_value, item.coin))
    return items


def build_spot_balances(
    priced_spot: Sequence[PricedSpotRow],
    total_assets: Decimal,
    today_by_symbol: dict[str, TodayTradeSummary],
) -> list[PortfolioSpotBalance]:
    """Build detailed PortfolioSpotBalance entries sorted by descending market_value."""
    items: list[PortfolioSpotBalance] = []
    for coin, total, hold, entry_ntl, mark_price, market_value in priced_spot:
        items.append(
            PortfolioSpotBalance(
                coin=coin,
                total=total,
                hold=hold,
                available=max(total - hold, ZERO),
                entry_ntl=entry_ntl,
                mark_price=mark_price,
                market_value=market_value,
                share_pct=share_pct(market_value or ZERO, total_assets),
                today=_pop_spot_today(coin, today_by_symbol),
            )
        )
    items.sort(
        key=lambda item: (
            item.market_value is None,
            -(item.market_value if item.market_value is not None else ZERO),
            item.coin,
        )
    )
    return items


def build_staking_section(
    raw_staking: Mapping[str, Any] | None,
    hype_price: Decimal | None,
    staking_market_value: Decimal | None,
    staking_total_usd: Decimal,
    total_assets: Decimal,
) -> PortfolioStaking | None:
    """Build PortfolioStaking section or None if staking query failed."""
    if raw_staking is None:
        return None
    return PortfolioStaking(
        delegated=raw_staking["delegated"],
        undelegated=raw_staking["undelegated"],
        pending_withdrawals=raw_staking["pending_withdrawals"],
        pending_withdrawal_count=raw_staking["pending_withdrawal_count"],
        total_hype=raw_staking["total_hype"],
        total_reward=raw_staking["total_reward"],
        mark_price=hype_price,
        market_value=staking_market_value,
        share_pct=share_pct(staking_total_usd, total_assets),
        delegations=raw_staking["delegations"],
    )


def build_vaults(
    raw_vaults: Sequence[tuple[str, Decimal]],
    total_assets: Decimal,
) -> list[PortfolioVault]:
    """Build PortfolioVault entries with portfolio share_pct."""
    return [
        PortfolioVault(
            vault_address=vault_address,
            equity=equity,
            share_pct=share_pct(equity, total_assets),
        )
        for vault_address, equity in raw_vaults
    ]


def build_portfolio_rows(
    spot_balances: Sequence[PortfolioSpotBalance],
    staking: PortfolioStaking | None,
    perp_positions: Sequence[PortfolioPerpPosition],
    vaults: Sequence[PortfolioVault],
) -> list[PortfolioRow]:
    """Assemble unified portfolio rows sorted by descending share_pct."""
    rows: list[PortfolioRow] = []

    for balance in spot_balances:
        if balance.coin.upper() == "USDC":
            continue
        value = balance.market_value if balance.market_value is not None else ZERO
        rows.append(
            PortfolioRow(
                bucket="spot",
                symbol=balance.coin,
                side="LONG",
                quantity=balance.total,
                mark_price=balance.mark_price,
                market_value=value,
                equity_value=value,
                share_pct=balance.share_pct,
                unrealized_pnl=None,
                today=balance.today,
            )
        )

    if staking is not None and staking.total_hype > ZERO:
        staking_value = staking.market_value if staking.market_value is not None else ZERO
        rows.append(
            PortfolioRow(
                bucket="staking",
                symbol="HYPE",
                side="LONG",
                quantity=staking.total_hype,
                mark_price=staking.mark_price,
                market_value=staking_value,
                equity_value=staking_value,
                share_pct=staking.share_pct,
                unrealized_pnl=None,
                today=None,
            )
        )

    for pos in perp_positions:
        rows.append(
            PortfolioRow(
                bucket="perp",
                symbol=pos.coin,
                side=pos.side,
                quantity=abs(pos.size),
                mark_price=pos.mark_price,
                market_value=pos.position_value,
                equity_value=pos.margin_used + pos.unrealized_pnl,
                share_pct=pos.share_pct,
                unrealized_pnl=pos.unrealized_pnl,
                today=pos.today,
            )
        )

    for vault in vaults:
        rows.append(
            PortfolioRow(
                bucket="vault",
                symbol=vault.vault_address,
                side="LONG",
                quantity=ONE,
                mark_price=None,
                market_value=vault.equity,
                equity_value=vault.equity,
                share_pct=vault.share_pct,
                unrealized_pnl=None,
                today=None,
            )
        )

    rows.sort(key=lambda row: (-row.share_pct, -row.market_value, row.bucket, row.symbol))
    return rows
