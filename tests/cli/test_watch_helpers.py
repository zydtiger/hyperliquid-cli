"""
Tests for shared watch/chart helper functions.
"""

from decimal import Decimal

from cli.interactive.charting import render_braille_plot
from cli.interactive.watch_helpers import (
    candle_close_series,
    candle_price_range,
    format_order_book_row,
    normalize_order_book_levels,
)
from models.api import OrderBookLevel, WatchCandle


def test_shared_render_braille_plot_uses_braille_glyphs():
    """The shared chart helper should emit braille glyphs for line plots."""
    lines = render_braille_plot(
        [Decimal("0.0"), Decimal("10.5"), Decimal("6.0")],
        width=20,
        height=6,
    )

    rendered = "".join(lines)
    assert len(lines) == 6
    assert any(ord(char) >= 0x2800 for char in rendered if char.strip())


def test_watch_helpers_extract_close_series_and_price_range():
    """The watch helpers should expose close prices and the overall candle range."""
    candles = [
        WatchCandle(
            open_time=1_000,
            close_time=61_000,
            open=Decimal("100"),
            high=Decimal("104"),
            low=Decimal("99"),
            close=Decimal("102"),
            is_closed=True,
        ),
        WatchCandle(
            open_time=61_000,
            close_time=121_000,
            open=Decimal("102"),
            high=Decimal("105"),
            low=Decimal("101"),
            close=Decimal("103"),
            is_closed=False,
        ),
    ]

    assert candle_close_series(candles) == [Decimal("102"), Decimal("103")]
    assert candle_price_range(candles) == (Decimal("99"), Decimal("105"))


def test_normalize_order_book_levels_sorts_truncates_and_pads():
    """Order book rows should be stable at the requested fixed depth."""
    asks = [
        OrderBookLevel(price=Decimal("102"), size=Decimal("3")),
        OrderBookLevel(price=Decimal("100"), size=Decimal("1")),
        OrderBookLevel(price=Decimal("101"), size=Decimal("2")),
    ]
    bids = [
        OrderBookLevel(price=Decimal("98"), size=Decimal("1")),
        OrderBookLevel(price=Decimal("99"), size=Decimal("2")),
        OrderBookLevel(price=Decimal("97"), size=Decimal("3")),
    ]

    normalized_asks = normalize_order_book_levels(asks, descending=False)
    normalized_bids = normalize_order_book_levels(bids, descending=True)

    assert [level.price for level in normalized_asks[:3] if level is not None] == [
        Decimal("100"),
        Decimal("101"),
        Decimal("102"),
    ]
    assert [level.price for level in normalized_bids[:3] if level is not None] == [
        Decimal("99"),
        Decimal("98"),
        Decimal("97"),
    ]
    assert len(normalized_asks) == 10
    assert len(normalized_bids) == 10
    assert normalized_asks[-1] is None
    assert normalized_bids[-1] is None


def test_format_order_book_row_renders_proportional_size_bars():
    """Order book rows should keep the price text and scale the size as an ASCII bar."""
    small = OrderBookLevel(price=Decimal("100"), size=Decimal("1"))
    large = OrderBookLevel(price=Decimal("101"), size=Decimal("4"))

    small_row = format_order_book_row(small, width=18, max_size=Decimal("4"))
    large_row = format_order_book_row(large, width=18, max_size=Decimal("4"))

    assert "100.00" in small_row
    assert "101.00" in large_row
    assert small_row.count("#") < large_row.count("#")
    assert large_row.count("#") > 0
