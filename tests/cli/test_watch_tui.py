"""
Tests for the Textual live watch TUI.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from decimal import Decimal

from textual.widgets import Static

from cli.interactive.plotting.braille_chart import BrailleChart
from cli.interactive.watch_tui.watch_helpers import format_watch_axis_label
from cli.interactive.watch_tui.watch_tui import (
    OrderBookView,
    WatchApp,
    WatchScreenControl,
    WatchTUI,
)
from models.api import DEFAULT_WATCH_ORDER_BOOK_DEPTH, OrderBookLevel, WatchCandle, WatchSnapshot


def _sample_snapshot() -> WatchSnapshot:
    return WatchSnapshot(
        coin="BTC",
        interval="5m",
        mark_price=Decimal("43250.50"),
        open_interest=Decimal("1250.75"),
        updated_at=1741973030493,
        candles=[
            WatchCandle(
                open_time=1741972200000,
                close_time=1741972500000,
                open=Decimal("43210.25"),
                high=Decimal("43240.25"),
                low=Decimal("43205.25"),
                close=Decimal("43230.50"),
                is_closed=True,
            ),
            WatchCandle(
                open_time=1741972500000,
                close_time=1741972800000,
                open=Decimal("43230.50"),
                high=Decimal("43245.00"),
                low=Decimal("43210.50"),
                close=Decimal("43218.75"),
                is_closed=True,
            ),
            WatchCandle(
                open_time=1741972800000,
                close_time=1741973100000,
                open=Decimal("43218.75"),
                high=Decimal("43260.00"),
                low=Decimal("43215.50"),
                close=Decimal("43250.50"),
                is_closed=False,
            ),
        ],
        asks=[
            OrderBookLevel(price=Decimal("43250.75"), size=Decimal("0.50")),
            OrderBookLevel(price=Decimal("43251.00"), size=Decimal("1.10")),
        ],
        bids=[
            OrderBookLevel(price=Decimal("43249.50"), size=Decimal("1.25")),
            OrderBookLevel(price=Decimal("43249.00"), size=Decimal("0.75")),
        ],
        size_decimals=5,
        order_book_depth=DEFAULT_WATCH_ORDER_BOOK_DEPTH,
    )


def test_watch_screen_control_formats_header_summary_and_status():
    """The watch control should expose formatted header and chart metadata."""
    control = WatchScreenControl("BTC")
    control.set_snapshot(_sample_snapshot())

    assert "Price $43,250.5" in control.header_summary()
    assert "OI $1,250.75" in control.header_summary()
    assert control.chart_title() == "Price Chart - 5M Interval"
    assert "last 43,250.5" in control.chart_summary()
    assert "max 43,250.5" in control.chart_summary()
    assert "min 43,205.2" in control.chart_summary()
    assert "3 candles" in control.status_line()


def test_watch_screen_control_clamps_interval_navigation():
    """The watch interval selector should clamp at the supported bounds."""
    control = WatchScreenControl("BTC")

    assert control.current_interval() == "5m"
    control.advance_interval(-1)
    assert control.current_interval() == "1m"
    control.advance_interval(-1)
    assert control.current_interval() == "1m"
    control.advance_interval(10)
    assert control.current_interval() == "1d"


def test_watch_tui_fetches_with_current_interval_and_refetches_on_interval_change():
    """The watch wrapper should keep fetches aligned with the current interval state."""
    calls = []

    def fetcher(coin: str, interval: str, depth: int) -> WatchSnapshot:
        calls.append((coin, interval, depth))
        return _sample_snapshot()

    tui = WatchTUI("BTC", fetcher)
    tui._refresh_snapshot()
    tui._change_interval(-1)
    tui._change_interval(10)

    assert calls == [("BTC", "5m", 10), ("BTC", "1m", 10), ("BTC", "1d", 10)]


def test_watch_textual_app_renders_real_axis_labels_and_order_book():
    """The Textual watch app should render inline axes and order book rows."""

    async def scenario() -> None:
        def fetcher(coin: str, interval: str, depth: int) -> WatchSnapshot:
            assert coin == "BTC"
            assert interval == "5m"
            assert depth >= 1
            return _sample_snapshot()

        tui = WatchTUI("BTC", fetcher, poll_interval_seconds=60.0)
        app = tui._build_app()

        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            plot = app.query_one("#watch-plot", BrailleChart)
            rendered_text = plot.render()
            rendered_plot = rendered_text.plain
            rendered_book = app.query_one(OrderBookView).render()
            rendered_book_plain = rendered_book.plain

            assert "43,260" in rendered_plot
            assert "43,240" in rendered_plot
            assert "┌" in rendered_plot
            assert "┐" in rendered_plot
            assert "┤" in rendered_plot
            assert "│" in rendered_plot
            assert "├" not in rendered_plot
            assert "└" in rendered_plot
            assert "┘" in rendered_plot
            assert "┬" in rendered_plot
            assert "13:15" in rendered_plot
            assert "13:25" in rendered_plot
            assert any(ord(char) >= 0x2800 for char in rendered_plot if char.strip())
            assert any("3b4261" in str(span.style) for span in rendered_text.spans)
            assert "43,251.0" in rendered_book_plain
            assert "43,249.5" in rendered_book_plain
            assert "Spread 1.2" in rendered_book_plain
            assert "Mid" not in rendered_book_plain
            assert any("f7768e" in str(span.style) for span in rendered_book.spans)
            assert any("9ece6a" in str(span.style) for span in rendered_book.spans)
            assert any("e0af68" in str(span.style) for span in rendered_book.spans)
            assert any(
                "bold" in str(span.style) and "e0af68" in str(span.style)
                for span in rendered_book.spans
            )
            assert "border: solid #3b4261;" in WatchApp.CSS

    asyncio.run(scenario())


def test_watch_textual_app_aligns_order_book_with_chart_frame():
    """The order book panel should align with the chart frame at top and bottom."""

    async def scenario() -> None:
        def fetcher(coin: str, interval: str, depth: int) -> WatchSnapshot:
            assert coin == "BTC"
            assert interval == "5m"
            assert depth >= 1
            return _sample_snapshot()

        tui = WatchTUI("BTC", fetcher, poll_interval_seconds=60.0)
        app = tui._build_app()

        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            plot = app.query_one("#watch-plot", BrailleChart)
            book = app.query_one(OrderBookView)
            book_footer_spacer = app.query_one("#book-footer-spacer", Static)

            assert plot.region.y == book.region.y
            assert plot.region.height == book.region.height + book_footer_spacer.region.height

    asyncio.run(scenario())


def test_watch_screen_control_renders_na_open_interest_for_spot():
    """Spot watch headers should omit open interest when it is unavailable."""
    control = WatchScreenControl("UBTC/USDC")
    control.set_snapshot(_sample_snapshot().model_copy(update={"open_interest": None}))

    assert "OI $" not in control.header_summary()


def test_format_watch_axis_label_uses_interval_specific_format():
    """The watch x-axis should switch to dates for higher timeframes."""
    timestamp_ms = 1741973100000

    assert format_watch_axis_label(timestamp_ms, "5m") == datetime.fromtimestamp(
        timestamp_ms / 1000
    ).strftime("%H:%M")
    assert format_watch_axis_label(timestamp_ms, "1h") == datetime.fromtimestamp(
        timestamp_ms / 1000
    ).strftime("%m-%d")
