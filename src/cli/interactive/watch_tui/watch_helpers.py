"""
Pure helpers for the live watch TUI.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from rich.text import Text

from models.api import (
    DEFAULT_WATCH_ORDER_BOOK_DEPTH,
    MAX_WATCH_ORDER_BOOK_DEPTH,
    OrderBookLevel,
    WatchCandle,
    WatchInterval,
    WatchSnapshot,
)

ASK_STYLE = "#f7768e"
BID_STYLE = "#9ece6a"
SPREAD_STYLE = "#e0af68"
EMPTY_STYLE = "#7f8c8d"


def watch_price_decimals(size_decimals: int) -> int:
    """Return the display precision for watch prices from coin size decimals."""
    return max(6 - size_decimals, 0)


def format_watch_price(value: Decimal, size_decimals: int) -> str:
    """Format a watch price using derived display precision."""
    decimals = watch_price_decimals(size_decimals)
    return f"{value:,.{decimals}f}"


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


def format_order_book_price(price: Decimal, width: int, size_decimals: int) -> str:
    """Format an order book price label that fits the available panel width."""
    decimals = watch_price_decimals(size_decimals)
    formatted = format_watch_price(price, size_decimals)
    candidates = [formatted, formatted.replace(",", "")]
    if decimals > 0:
        rounded = f"{price:,.{min(decimals, 2)}f}"
        candidates.extend([rounded, rounded.replace(",", "")])
    candidates.extend([f"{price:,.0f}", f"{price:.0f}"])
    for pattern in candidates:
        if len(pattern) <= width:
            return pattern
    return f"{price:.0f}"[-width:]


def format_order_book_row(
    level: OrderBookLevel | None, width: int, max_size: Decimal, size_decimals: int
) -> str:
    """Format a price label plus a proportional size bar that fits the panel width."""
    if level is None:
        return " " * width
    price_width = min(max(width // 2, 8), max(width - 2, 1))
    price_text = format_order_book_price(level.price, price_width, size_decimals)
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


def format_order_book_spreadline(snapshot: WatchSnapshot | None, width: int) -> str:
    """Format the order book spread separator."""
    if snapshot is None or not snapshot.asks or not snapshot.bids:
        return " Spread n/a ".center(width)[:width].ljust(width)
    spread = snapshot.asks[0].price - snapshot.bids[0].price
    spread_text = format_watch_price(spread, snapshot.size_decimals)
    return f" Spread {spread_text} ".center(width)[:width].ljust(width)


def render_order_book_lines(
    snapshot: WatchSnapshot | None, width: int, height: int, depth: int
) -> list[str]:
    """Render fixed-height order book rows for the TUI panel."""
    if snapshot is None:
        message = "Loading book".center(width)[:width].ljust(width)
        return [message if index == height // 2 else " " * width for index in range(height)]
    asks = list(reversed(normalize_order_book_levels(snapshot.asks, descending=False, depth=depth)))
    bids = normalize_order_book_levels(snapshot.bids, descending=True, depth=depth)
    visible_levels = [level for level in [*asks, *bids] if level is not None]
    max_size = max((level.size for level in visible_levels), default=Decimal("0"))
    lines = [
        format_order_book_row(level, width, max_size, snapshot.size_decimals) for level in asks
    ]
    lines.append(format_order_book_spreadline(snapshot, width))
    lines.extend(
        format_order_book_row(level, width, max_size, snapshot.size_decimals) for level in bids
    )
    padding = max(height - len(lines), 0)
    top_padding = padding // 2
    bottom_padding = padding - top_padding
    return [" " * width] * top_padding + lines[:height] + [" " * width] * bottom_padding


def render_order_book_text(
    snapshot: WatchSnapshot | None, width: int, height: int, depth: int
) -> Text:
    """Render a styled order book for the Textual watch panel."""
    if snapshot is None:
        message = "Loading book".center(width)[:width].ljust(width)
        lines = [message if index == height // 2 else " " * width for index in range(height)]
        return Text("\n".join(lines), style=EMPTY_STYLE)

    asks = list(reversed(normalize_order_book_levels(snapshot.asks, descending=False, depth=depth)))
    bids = normalize_order_book_levels(snapshot.bids, descending=True, depth=depth)
    visible_levels = [level for level in [*asks, *bids] if level is not None]
    max_size = max((level.size for level in visible_levels), default=Decimal("0"))
    rows = [
        (format_order_book_row(level, width, max_size, snapshot.size_decimals), ASK_STYLE)
        for level in asks
    ]
    rows.append((format_order_book_spreadline(snapshot, width), SPREAD_STYLE))
    rows.extend(
        (format_order_book_row(level, width, max_size, snapshot.size_decimals), BID_STYLE)
        for level in bids
    )
    padding = max(height - len(rows), 0)
    top_padding = padding // 2
    bottom_padding = padding - top_padding
    styled_rows = (
        [(" " * width, EMPTY_STYLE)] * top_padding
        + rows[:height]
        + [(" " * width, EMPTY_STYLE)] * bottom_padding
    )

    rendered = Text()
    spread_value = (
        "n/a"
        if not snapshot.asks or not snapshot.bids
        else format_watch_price(
            snapshot.asks[0].price - snapshot.bids[0].price, snapshot.size_decimals
        )
    )
    for index, (line, style) in enumerate(styled_rows):
        if index:
            rendered.append("\n")
        rendered.append(line, style)
        if style == SPREAD_STYLE:
            start = line.find(spread_value)
            if start >= 0:
                rendered.stylize(
                    f"bold {SPREAD_STYLE}",
                    len(rendered.plain) - len(line) + start,
                    len(rendered.plain) - len(line) + start + len(spread_value),
                )
    return rendered


def format_price_header(value: Decimal, size_decimals: int) -> str:
    """Format the live mark price for the watch header."""
    return f"Price ${format_watch_price(value, size_decimals)}"


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
