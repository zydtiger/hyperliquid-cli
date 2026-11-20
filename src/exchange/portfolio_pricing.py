"""
Pure pricing, fill-aggregation, and equity accounting helpers for Hyperliquid portfolios.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from typing import Any

from models.api import LeverageType, PositionInfo
from models.portfolio import (
    AllocationBucket,
    PortfolioAllocation,
    TodayTradeSummary,
)

from .helpers import SPOT_PAIR_TOKEN_COUNT, decimal_value, fee_to_usdc, optional_decimal

ZERO = Decimal("0")
HUNDRED = Decimal("100")
USDC_PRICE = Decimal("1")
UNIFIED_ABSTRACTION_MODES = frozenset({"unifiedAccount", "portfolioMargin"})


def share_pct(value: Decimal, total_assets: Decimal) -> Decimal:
    """Calculate percentage share of total_assets, returning 0 when total_assets <= 0."""
    if total_assets <= ZERO:
        return ZERO
    return (value / total_assets) * HUNDRED


def parse_abstraction_mode(raw: Any) -> str | None:
    """Normalize the raw userAbstraction response into a mode string or None."""
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw.strip() or None
    if isinstance(raw, Mapping):
        for key in ("abstraction", "mode", "state"):
            candidate = raw.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    return str(raw)


def _match_spot_ctx(
    raw_name: str,
    pair_idx: int,
    spot_ctxs: Sequence[Mapping[str, Any]],
    ctx_by_coin: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    """Resolve the matching spot context by positional index or coin name."""
    if pair_idx < len(spot_ctxs):
        positional = spot_ctxs[pair_idx]
        if isinstance(positional, Mapping):
            ctx_coin = str(positional.get("coin", ""))
            if not ctx_coin or ctx_coin == raw_name:
                return positional
    return ctx_by_coin.get(raw_name)


def extract_spot_prices_and_symbols(
    spot_meta: Mapping[str, Any],
    spot_ctxs: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Decimal], dict[str, str]]:
    """Build spot token USD prices and raw-id -> display-pair map from spotMetaAndAssetCtxs."""
    token_names: dict[int, str] = {}
    usdc_index = 0
    for idx, token in enumerate(spot_meta.get("tokens", [])):
        if not isinstance(token, Mapping):
            continue
        token_idx = int(token["index"]) if "index" in token else idx
        name = str(token.get("name", ""))
        if name:
            token_names[token_idx] = name
            if name.upper() == "USDC":
                usdc_index = token_idx

    ctx_by_coin = {
        str(ctx.get("coin", "")): ctx
        for ctx in spot_ctxs
        if isinstance(ctx, Mapping) and ctx.get("coin")
    }
    spot_prices: dict[str, Decimal] = {"USDC": USDC_PRICE}
    spot_symbol_map: dict[str, str] = {}

    for pair_idx, pair in enumerate(spot_meta.get("universe", [])):
        if not isinstance(pair, Mapping):
            continue
        raw_name = str(pair.get("name", ""))
        token_indexes = pair.get("tokens", [])
        if not raw_name or len(token_indexes) != SPOT_PAIR_TOKEN_COUNT:
            continue

        base_name = token_names.get(int(token_indexes[0]))
        quote_idx = int(token_indexes[1])
        quote_name = token_names.get(quote_idx)
        if not base_name or not quote_name:
            continue

        spot_symbol_map[raw_name] = f"{base_name}/{quote_name}"
        if quote_name.upper() != "USDC" and quote_idx != usdc_index:
            continue

        ctx = _match_spot_ctx(raw_name, pair_idx, spot_ctxs, ctx_by_coin)
        if ctx is None:
            continue

        price = optional_decimal(ctx.get("markPx")) or optional_decimal(ctx.get("midPx"))
        if price is not None and (base_name not in spot_prices or bool(pair.get("isCanonical"))):
            spot_prices[base_name] = price

    return spot_prices, spot_symbol_map


def resolve_token_price(
    coin: str,
    spot_prices: Mapping[str, Decimal],
    perp_mark_prices: Mapping[str, Decimal],
    all_mids: Mapping[str, Any] | None = None,
    spot_symbol_map: Mapping[str, str] | None = None,
) -> Decimal | None:
    """Resolve a token's USD mark price using spot contexts, perp marks, then allMids."""
    if coin.upper() == "USDC":
        return USDC_PRICE
    if coin in spot_prices:
        return spot_prices[coin]
    if coin in perp_mark_prices:
        return perp_mark_prices[coin]
    if all_mids:
        direct = optional_decimal(all_mids.get(coin))
        if direct is not None:
            return direct
        if spot_symbol_map:
            target_pair = f"{coin}/USDC".upper()
            for raw_symbol, display_symbol in spot_symbol_map.items():
                if display_symbol.upper() == target_pair:
                    mid = optional_decimal(all_mids.get(raw_symbol))
                    if mid is not None:
                        return mid
    return None


def compute_total_assets_and_allocation(
    *,
    abstraction_mode: str | None,
    spot_failed: bool,
    perps_account_value: Decimal,
    cross_account_value: Decimal | None,
    perp_positions: Sequence[PositionInfo],
    spot_total_usd: Decimal,
    spot_usdc: Decimal,
    staking_total_usd: Decimal,
    vaults_total_usd: Decimal,
) -> tuple[Decimal, PortfolioAllocation]:
    """
    Compute total USD equity and non-overlapping allocation buckets.

    - Standard mode (disabled / default / unknown, or when spot fetch failed):
      total_assets = perps_account_value + spot_total_usd + staking_total_usd + vaults_total_usd.
    - Unified Account / Portfolio Margin ("unifiedAccount" / "portfolioMargin"):
      Spot balances (including spot_usdc) are the shared collateral pool for cross-margin
      perps, so perps_account_value overlaps with spot_usdc. We count spot_total_usd plus
      only non-spot perp equity:
        * cross_unrealized_pnl = sum(uPnL of cross perp positions)
        * isolated_perps_equity = ring-fenced isolated equity outside spot_usdc
          (perps_account_value - cross_account_value if crossMarginSummary is present,
          else sum(isolated.margin_used) when isolated positions exist)
      total_assets = spot_total_usd + isolated_perps_equity + cross_unrealized_pnl
                     + staking_total_usd + vaults_total_usd.
    """
    spot_crypto = spot_total_usd - spot_usdc
    is_unified = abstraction_mode in UNIFIED_ABSTRACTION_MODES and not spot_failed

    if is_unified:
        isolated = [pos for pos in perp_positions if pos.leverage_type == LeverageType.ISOLATED]
        cross_upnl = sum(
            (
                pos.unrealized_pnl
                for pos in perp_positions
                if pos.leverage_type == LeverageType.CROSS
            ),
            start=ZERO,
        )
        if not isolated:
            isolated_equity = ZERO
        elif cross_account_value is not None:
            isolated_equity = perps_account_value - cross_account_value
        else:
            isolated_equity = sum((pos.margin_used for pos in isolated), start=ZERO)

        total_assets = (
            spot_total_usd + isolated_equity + cross_upnl + staking_total_usd + vaults_total_usd
        )
        raw_buckets: list[tuple[str, Decimal]] = [
            ("usdc_cash", spot_usdc),
            ("spot_crypto", spot_crypto),
        ]
        if isolated_equity != ZERO:
            raw_buckets.append(("perps_isolated_equity", isolated_equity))
        raw_buckets.extend(
            [
                ("perps_unrealized_pnl", cross_upnl),
                ("staking", staking_total_usd),
                ("vaults", vaults_total_usd),
            ]
        )
    else:
        total_assets = perps_account_value + spot_total_usd + staking_total_usd + vaults_total_usd
        raw_buckets = [
            ("usdc_cash", spot_usdc),
            ("spot_crypto", spot_crypto),
            ("perps_equity", perps_account_value),
            ("staking", staking_total_usd),
            ("vaults", vaults_total_usd),
        ]

    buckets = [
        AllocationBucket(name=name, value=value, share_pct=share_pct(value, total_assets))
        for name, value in raw_buckets
    ]
    return total_assets, PortfolioAllocation(total_assets=total_assets, buckets=buckets)


def _is_buy_fill(fill: Mapping[str, Any]) -> bool:
    """Determine whether a Hyperliquid fill represents a buy."""
    side = str(fill.get("side", "")).strip().upper()
    if side == "B":
        return True
    if side in {"A", "S"}:
        return False
    direction = str(fill.get("dir", "")).strip().lower()
    return direction in {"buy", "open long", "close short"}


def aggregate_today_fills(
    fills: Sequence[Mapping[str, Any]],
    start_ms: int,
    resolve_coin: Callable[[str], str],
) -> dict[str, TodayTradeSummary]:
    """Aggregate fills from start_ms onward per resolved trading symbol."""
    totals: dict[str, dict[str, Decimal]] = {}

    for fill in fills:
        if int(fill.get("time", 0)) < start_ms:
            continue
        symbol = resolve_coin(str(fill.get("coin", "")))
        if not symbol:
            continue

        row = totals.setdefault(
            symbol,
            {
                "buy_quantity": ZERO,
                "buy_value": ZERO,
                "sell_quantity": ZERO,
                "sell_value": ZERO,
                "fee_usdc": ZERO,
                "realized_pnl": ZERO,
            },
        )
        size = decimal_value(fill.get("sz"))
        price = decimal_value(fill.get("px"))
        notional = size * price
        fee_usdc = fee_to_usdc(
            decimal_value(fill.get("fee")),
            str(fill.get("feeToken", "USDC")),
            symbol,
            price,
        )

        if _is_buy_fill(fill):
            row["buy_quantity"] += size
            row["buy_value"] += notional
        else:
            row["sell_quantity"] += size
            row["sell_value"] += notional

        row["fee_usdc"] += fee_usdc
        row["realized_pnl"] += decimal_value(fill.get("closedPnl"))

    return {symbol: TodayTradeSummary(symbol=symbol, **values) for symbol, values in totals.items()}
