"""
Pure helpers for the live watch TUI.
"""

from __future__ import annotations

from decimal import Decimal

from models.api import WATCH_WINDOW_ORDER, OrderBookLevel, PriceSample, WatchWindow

ORDER_BOOK_DEPTH = 10
WATCH_WINDOW_MS: dict[WatchWindow, int] = {
    "1m": 60_000,
    "5m": 5 * 60_000,
    "15m": 15 * 60_000,
    "1h": 60 * 60_000,
}


def slice_price_history(
    samples: list[PriceSample],
    window: WatchWindow,
) -> list[PriceSample]:
    """Return the most recent samples that fall within the selected window."""
    if not samples:
        return []

    latest_time = samples[-1].time
    cutoff = latest_time - WATCH_WINDOW_MS[window]
    sliced = [sample for sample in samples if sample.time >= cutoff]
    return sliced or [samples[-1]]


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


def format_open_interest_header(value: Decimal) -> str:
    """Format the live open interest for the watch header."""
    return f"OI {value:,.2f}"


def watch_window_index(window: WatchWindow) -> int:
    """Return the current watch window index."""
    return WATCH_WINDOW_ORDER.index(window)


__all__ = [
    "ORDER_BOOK_DEPTH",
    "WATCH_WINDOW_MS",
    "format_open_interest_header",
    "format_price_header",
    "normalize_order_book_levels",
    "slice_price_history",
    "watch_window_index",
]
