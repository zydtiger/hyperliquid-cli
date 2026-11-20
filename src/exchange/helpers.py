"""
Pure helper functions for Hyperliquid symbol resolution, fills, and margin calculations.
"""

from collections.abc import Callable, Mapping
from decimal import Decimal
from typing import Any

from models.api import LeverageType
from models.order import OrderHistoryEntry, OrderStatus

SPOT_PAIR_TOKEN_COUNT = 2


def decimal_value(value: Any) -> Decimal:
    """Convert optional API numeric values to Decimal."""
    if value in (None, ""):
        return Decimal("0")
    return Decimal(str(value))


def optional_decimal(value: Any) -> Decimal | None:
    """Convert optional API numeric values to Decimal or None."""
    if value in (None, ""):
        return None
    return Decimal(str(value))


def perp_open_interest_value(mark_price: Decimal, open_interest: Any) -> Decimal:
    """Convert perp open interest from base units into USD notional."""
    return mark_price * decimal_value(open_interest)


def fee_to_usdc(fee: Decimal, fee_token: str, coin: str, price: Decimal) -> Decimal:
    """Convert a fee to USDC when the exchange reports it in base units."""
    if fee_token.upper() == "USDC":
        return fee

    base_coin = coin.split("/", maxsplit=1)[0].upper()
    if fee_token.upper() == base_coin:
        return fee * price

    return fee


def build_spot_symbol_map(spot_meta: Mapping[str, Any]) -> dict[str, str]:
    """Build a map from raw Hyperliquid spot ids to display symbols."""
    symbol_map: dict[str, str] = {}
    tokens = spot_meta.get("tokens", [])

    for spot_info in spot_meta.get("universe", []):
        raw_symbol = str(spot_info.get("name", ""))
        token_indexes = spot_info.get("tokens", [])
        if not raw_symbol or len(token_indexes) != SPOT_PAIR_TOKEN_COUNT:
            continue

        try:
            base_info = tokens[token_indexes[0]]
            quote_info = tokens[token_indexes[1]]
        except (IndexError, TypeError):
            continue

        base = str(base_info.get("name", ""))
        quote = str(quote_info.get("name", ""))
        if base and quote:
            symbol_map[raw_symbol] = f"{base}/{quote}"

    return symbol_map


def resolve_spot_symbol(coin: str, spot_symbol_map: Mapping[str, str]) -> str:
    """Resolve a raw Hyperliquid spot coin id like @142 to BTC/USDC."""
    return spot_symbol_map.get(coin, coin)


def normalize_spot_order_symbol(coin: str, spot_symbol_map: Mapping[str, str]) -> str:
    """Resolve a user-facing spot pair symbol like BTC/USDC to the raw spot id."""
    if coin.startswith("@"):
        return coin

    normalized_coin = coin.upper()
    for raw_symbol, display_symbol in spot_symbol_map.items():
        if display_symbol.upper() == normalized_coin:
            return raw_symbol

    return coin


def aggregate_fills_by_order(fills: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Aggregate fill-level data into order-level history rows."""
    aggregated: dict[int, dict[str, Any]] = {}

    for fill in fills:
        oid = fill.get("oid")
        if oid is None:
            continue

        order_id = int(oid)
        row = aggregated.setdefault(
            order_id,
            {
                "coin": str(fill.get("coin", "")),
                "gross_closed_pnl": Decimal("0"),
                "net_closed_pnl": Decimal("0"),
                "fee": Decimal("0"),
                "fee_usdc": Decimal("0"),
                "fee_token": str(fill.get("feeToken", "USDC")),
                "size": Decimal("0"),
                "notional": Decimal("0"),
                "dir": str(fill.get("dir", "")),
                "last_fill_time": 0,
            },
        )
        size = decimal_value(fill.get("sz"))
        price = decimal_value(fill.get("px"))
        fee = decimal_value(fill.get("fee"))
        gross_closed_pnl = decimal_value(fill.get("closedPnl"))
        fee_usdc = fee_to_usdc(
            fee,
            str(fill.get("feeToken", "USDC")),
            str(fill.get("coin", "")),
            price,
        )

        row["gross_closed_pnl"] += gross_closed_pnl
        row["net_closed_pnl"] += gross_closed_pnl - fee_usdc
        row["fee"] += fee
        row["fee_usdc"] += fee_usdc
        row["size"] += size
        row["notional"] += size * price
        row["last_fill_time"] = max(row["last_fill_time"], int(fill.get("time", 0)))
        if not row["coin"]:
            row["coin"] = str(fill.get("coin", ""))
        if not row["dir"]:
            row["dir"] = str(fill.get("dir", ""))
        if not row["fee_token"]:
            row["fee_token"] = str(fill.get("feeToken", "USDC"))

    return aggregated


def build_order_history_entries(
    historical_orders: list[dict[str, Any]],
    fills_by_order: dict[int, dict[str, Any]],
    limit: int,
    resolve_coin: Callable[[str], str] | None = None,
) -> list[OrderHistoryEntry]:
    """Build filled-order history entries from historical orders and aggregated fills."""
    rows: list[OrderHistoryEntry] = []

    for entry in historical_orders:
        status = str(entry.get("status", "")).lower()
        if status != OrderStatus.FILLED.value:
            continue

        order = entry.get("order", {})
        order_id = int(order["oid"])
        fill_summary = fills_by_order.get(order_id)
        if fill_summary is None:
            continue

        filled_size = fill_summary["size"]
        avg_price = fill_summary["notional"] / filled_size if filled_size > 0 else Decimal("0")

        coin = str(order.get("coin", ""))
        if resolve_coin is not None:
            coin = resolve_coin(coin)

        rows.append(
            OrderHistoryEntry(
                time=int(entry.get("statusTimestamp") or fill_summary["last_fill_time"]),
                coin=coin,
                direction=fill_summary["dir"] or str(order.get("side", "")),
                price=avg_price,
                size=filled_size,
                notional=fill_summary["notional"],
                fee=fill_summary["fee"],
                fee_usdc=fill_summary["fee_usdc"],
                fee_token=fill_summary["fee_token"],
                gross_closed_pnl=fill_summary["gross_closed_pnl"],
                closed_pnl=fill_summary["net_closed_pnl"],
                order_id=order_id,
                status=OrderStatus.FILLED,
            )
        )
        if len(rows) >= limit:
            break

    return rows


def build_order_history_from_fills(
    fills_by_order: dict[int, dict[str, Any]],
    limit: int,
) -> list[OrderHistoryEntry]:
    """Build filled-order history entries directly from aggregated user fills."""
    sorted_items = sorted(
        fills_by_order.items(),
        key=lambda item: (int(item[1]["last_fill_time"]), item[0]),
        reverse=True,
    )
    rows: list[OrderHistoryEntry] = []
    for order_id, fill_summary in sorted_items[:limit]:
        filled_size = fill_summary["size"]
        avg_price = fill_summary["notional"] / filled_size if filled_size > 0 else Decimal("0")
        rows.append(
            OrderHistoryEntry(
                time=int(fill_summary["last_fill_time"]),
                coin=str(fill_summary.get("coin", "")),
                direction=str(fill_summary["dir"]),
                price=avg_price,
                size=filled_size,
                notional=fill_summary["notional"],
                fee=fill_summary["fee"],
                fee_usdc=fill_summary["fee_usdc"],
                fee_token=fill_summary["fee_token"],
                gross_closed_pnl=fill_summary["gross_closed_pnl"],
                closed_pnl=fill_summary["net_closed_pnl"],
                order_id=order_id,
                status=OrderStatus.FILLED,
            )
        )
    return rows


def calculate_removable_margin(
    position_value: Decimal,
    leverage: int,
    margin_used: Decimal,
    leverage_type: LeverageType,
) -> Decimal | None:
    """Estimate removable isolated margin from current position requirements."""
    if leverage_type != LeverageType.ISOLATED:
        return None

    removable_margin = margin_used - (position_value / Decimal(leverage))
    return max(removable_margin, Decimal("0"))
