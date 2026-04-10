"""
Pure helpers for the live watch TUI.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from models.api import (
    WATCH_INTERVAL_MS,
    WATCH_INTERVAL_ORDER,
    OrderBookLevel,
    WatchCandle,
    WatchInterval,
)

ORDER_BOOK_DEPTH = 10


def candle_close_series(candles: list[WatchCandle]) -> list[Decimal]:
    """Extract ordered candle close prices for chart rendering."""
    return [candle.close for candle in candles]


def candle_price_range(candles: list[WatchCandle]) -> tuple[Decimal, Decimal] | None:
    """Return the min low and max high across a candle list."""
    if not candles:
        return None
    return min(candle.low for candle in candles), max(candle.high for candle in candles)


def normalize_order_book_levels(
    levels: list[OrderBookLevel],
    *,
    descending: bool,
    depth: int = ORDER_BOOK_DEPTH,
) -> list[OrderBookLevel | None]:
    """Sort, truncate, and pad order book rows to a stable fixed depth."""
    ordered = sorted(levels, key=lambda level: level.price, reverse=descending)[:depth]
    padded: list[OrderBookLevel | None] = list(ordered)
    padded.extend([None] * max(depth - len(padded), 0))
    return padded


def format_price_header(value: Decimal) -> str:
    """Format the live mark price for the watch header."""
    return f"Price ${value:,.4f}"


def format_open_interest_header(value: Decimal | None) -> str:
    """Format the live open interest for the watch header."""
    if value is None:
        return ""
    return f"OI ${value:,.2f}"


def format_watch_axis_label(timestamp_ms: int, interval: WatchInterval) -> str:
    """Format an x-axis label based on the active watch interval."""
    timestamp = datetime.fromtimestamp(timestamp_ms / 1000)
    if interval in {"1h", "4h", "1d"}:
        return timestamp.strftime("%m-%d")
    return timestamp.strftime("%H:%M")


def next_watch_refresh_seconds(interval: WatchInterval, now_ms: int) -> float:
    """Return the seconds remaining until the next interval boundary."""
    interval_ms = WATCH_INTERVAL_MS[interval]
    return (interval_ms - (now_ms % interval_ms)) / 1000


def watch_interval_index(interval: WatchInterval) -> int:
    """Return the current watch interval index."""
    return WATCH_INTERVAL_ORDER.index(interval)


__all__ = [
    "ORDER_BOOK_DEPTH",
    "candle_close_series",
    "candle_price_range",
    "format_open_interest_header",
    "format_price_header",
    "format_watch_axis_label",
    "next_watch_refresh_seconds",
    "normalize_order_book_levels",
    "watch_interval_index",
]
