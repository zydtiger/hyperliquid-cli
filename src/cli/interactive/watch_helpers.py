"""
Pure helpers for the live watch TUI.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from models.api import (
    DEFAULT_WATCH_ORDER_BOOK_DEPTH,
    MAX_WATCH_ORDER_BOOK_DEPTH,
    WATCH_INTERVAL_ORDER,
    OrderBookLevel,
    WatchCandle,
    WatchInterval,
    WatchSnapshot,
)


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
    depth: int = DEFAULT_WATCH_ORDER_BOOK_DEPTH,
) -> list[OrderBookLevel | None]:
    """Sort, truncate, and pad order book rows to a stable fixed depth."""
    ordered = sorted(levels, key=lambda level: level.price, reverse=descending)[:depth]
    padded: list[OrderBookLevel | None] = list(ordered)
    padded.extend([None] * max(depth - len(padded), 0))
    return padded


def visible_order_book_depth(panel_height: int) -> int:
    """Return the per-side order book depth that fits the visible panel height."""
    return min(max((panel_height - 1) // 2, 1), MAX_WATCH_ORDER_BOOK_DEPTH)


def format_order_book_price(price: Decimal, width: int) -> str:
    """Format an order book price label that fits the available panel width."""
    for pattern in (f"{price:,.2f}", f"{price:.2f}", f"{price:,.0f}", f"{price:.0f}"):
        if len(pattern) <= width:
            return pattern
    return f"{price:.0f}"[-width:]


def format_order_book_row(level: OrderBookLevel | None, width: int, max_size: Decimal) -> str:
    """Format a price label plus a proportional size bar that fits the panel width."""
    if level is None:
        return " " * width
    price_width = min(max(width // 2, 8), max(width - 2, 1))
    price_text = format_order_book_price(level.price, price_width)
    bar_width = max(width - len(price_text) - 1, 0)
    if bar_width == 0:
        return price_text.rjust(width)
    filled = 0
    if max_size > 0:
        filled = int((level.size / max_size) * bar_width)
        if level.size > 0 and filled == 0:
            filled = 1
    bar = "#" * min(filled, bar_width)
    return f"{price_text} {bar}".ljust(width)


def format_order_book_midline(mark_price: Decimal, width: int) -> str:
    """Format the order book mid-price separator."""
    return f" Mid {mark_price:,.2f} ".center(width)[:width].ljust(width)


def format_order_book_footer(snapshot: WatchSnapshot | None, width: int) -> str:
    """Format the order book footer with the top-of-book spread."""
    if snapshot is None or not snapshot.asks or not snapshot.bids:
        return " spread n/a "[:width].ljust(width)
    spread = snapshot.asks[0].price - snapshot.bids[0].price
    return f" spread {spread:,.2f} "[:width].ljust(width)


def render_order_book_lines(
    snapshot: WatchSnapshot | None, width: int, height: int, depth: int
) -> list[tuple[str, str]]:
    """Render fixed-height order book rows for the TUI panel."""
    if snapshot is None:
        message = "Loading book".center(width)[:width].ljust(width)
        return [
            ("class:mid", message if index == height // 2 else " " * width)
            for index in range(height)
        ]
    asks = list(reversed(normalize_order_book_levels(snapshot.asks, descending=False, depth=depth)))
    bids = normalize_order_book_levels(snapshot.bids, descending=True, depth=depth)
    visible_levels = [level for level in [*asks, *bids] if level is not None]
    max_size = max((level.size for level in visible_levels), default=Decimal("0"))
    lines = [("class:ask", format_order_book_row(level, width, max_size)) for level in asks]
    lines.append(("class:mid", format_order_book_midline(snapshot.mark_price, width)))
    lines.extend(("class:bid", format_order_book_row(level, width, max_size)) for level in bids)
    padding = max(height - len(lines), 0)
    top_padding = padding // 2
    bottom_padding = padding - top_padding
    return (
        [("class:root", " " * width)] * top_padding
        + lines[:height]
        + [("class:root", " " * width)] * bottom_padding
    )


def watch_panel_widths(width: int) -> tuple[int, int]:
    """Split the watch window into roughly 80/20 chart and order book panels."""
    order_book_width = max(width // 5, 18)
    order_book_width = min(order_book_width, max(width - 18, 0))
    return width - order_book_width, order_book_width


def pad_line(value: str, width: int) -> str:
    """Trim and right-pad a line to the available width."""
    return value[:width].ljust(width)


def border_line(left: str, content: str, right: str, width: int) -> str:
    """Build a bordered panel line that exactly fits the target width."""
    inner_width = max(width - len(left) - len(right), 0)
    trimmed = content[:inner_width]
    return f"{left}{trimmed}{'─' * max(inner_width - len(trimmed), 0)}{right}"


def empty_panel_lines(width: int, height: int, message: str, style: str) -> list[tuple[str, str]]:
    """Render an empty panel state with a centered message."""
    lines = [(" " * width) for _ in range(height)]
    if lines:
        lines[len(lines) // 2] = message.center(width)[:width].ljust(width)
    return [(style, line) for line in lines]


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


def watch_interval_index(interval: WatchInterval) -> int:
    """Return the current watch interval index."""
    return WATCH_INTERVAL_ORDER.index(interval)


__all__ = [
    "DEFAULT_WATCH_ORDER_BOOK_DEPTH",
    "border_line",
    "candle_close_series",
    "candle_price_range",
    "empty_panel_lines",
    "format_open_interest_header",
    "format_order_book_footer",
    "format_order_book_midline",
    "format_order_book_price",
    "format_order_book_row",
    "format_price_header",
    "format_watch_axis_label",
    "normalize_order_book_levels",
    "pad_line",
    "render_order_book_lines",
    "visible_order_book_depth",
    "watch_interval_index",
    "watch_panel_widths",
]
