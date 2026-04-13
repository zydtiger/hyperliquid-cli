"""
Tests for the live watch TUI renderer.
"""

from datetime import datetime
from decimal import Decimal
from threading import Event, Thread

import pytest

from cli.interactive.watch_helpers import (
    format_watch_axis_label,
    visible_order_book_depth,
    watch_panel_widths,
)
from cli.interactive.watch_tui import WatchScreenControl, WatchTUI
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
        order_book_depth=DEFAULT_WATCH_ORDER_BOOK_DEPTH,
    )


def test_watch_screen_control_renders_header_and_interval_label():
    """The watch screen should render the price/open-interest header and chart title."""
    control = WatchScreenControl("BTC")
    control.set_snapshot(_sample_snapshot())
    content = control.create_content(width=100, height=30)
    lines = ["".join(fragment for _, fragment in content.get_line(index)) for index in range(30)]
    rendered = "\n".join(lines)

    assert "Price $43,250.5000" in rendered
    assert "OI $1,250.75" in rendered
    assert "Price Chart - 5M Interval" in rendered


@pytest.mark.parametrize("width", [60, 70, 80, 100])
def test_watch_screen_control_keeps_lines_within_terminal_width(width: int):
    """Every rendered row should fit the terminal width to avoid wrapping artifacts."""
    control = WatchScreenControl("BTC")
    control.set_snapshot(_sample_snapshot())
    content = control.create_content(width=width, height=20)
    lines = ["".join(fragment for _, fragment in content.get_line(index)) for index in range(20)]

    assert all(len(line) == width for line in lines)


def test_watch_screen_control_renders_chart_and_order_book_panels():
    """The watch screen should render a close-price chart beside the live order book."""
    control = WatchScreenControl("BTC")
    control.set_snapshot(_sample_snapshot())
    content = control.create_content(width=100, height=30)
    lines = ["".join(fragment for _, fragment in content.get_line(index)) for index in range(30)]
    rendered = "\n".join(lines)

    assert "Price Chart - 5M Interval" in rendered
    assert "last 43,250.5000  max 43,250.5000" in rendered
    assert "Order Book" in rendered
    assert "43,251.00" in rendered
    assert "43,249.50" in rendered
    assert "#" in rendered
    assert "Mid 43,250.50" in rendered
    assert any(ord(char) >= 0x2800 for char in rendered if char.strip())


def test_watch_screen_control_uses_chart_style_for_braille_fragments():
    """The watch screen should style the close-price chart as a single braille plot."""
    control = WatchScreenControl("BTC")
    control.set_snapshot(_sample_snapshot())
    content = control.create_content(width=100, height=30)
    fragments = [fragment for index in range(30) for fragment in content.get_line(index)]

    assert any(
        style == "class:chart" and any(ord(char) >= 0x2800 for char in text)
        for style, text in fragments
    )


def test_watch_screen_control_clamps_interval_navigation():
    """The watch interval selector should clamp at the shortest and longest ranges."""
    control = WatchScreenControl("BTC")

    assert control.current_interval() == "5m"
    control.advance_interval(-1)
    assert control.current_interval() == "1m"
    control.advance_interval(-1)
    assert control.current_interval() == "1m"
    control.advance_interval(10)
    assert control.current_interval() == "1d"


def test_watch_screen_control_renders_loading_and_sparse_states():
    """The watch screen should keep rendering even without fetched data yet."""
    control = WatchScreenControl("BTC")
    content = control.create_content(width=100, height=30)
    lines = ["".join(fragment for _, fragment in content.get_line(index)) for index in range(30)]
    rendered = "\n".join(lines)

    assert "loading live candle stream" in rendered
    assert "Loading live market data" in rendered
    assert "Polling backend every 500ms" in rendered
    assert "Loading book" in rendered

    control.set_snapshot(
        WatchSnapshot(
            coin="BTC",
            interval="5m",
            mark_price=Decimal("1"),
            open_interest=Decimal("2"),
            updated_at=1,
            candles=[],
            asks=[],
            bids=[],
        )
    )
    content = control.create_content(width=100, height=30)
    lines = ["".join(fragment for _, fragment in content.get_line(index)) for index in range(30)]
    rendered = "\n".join(lines)

    assert "No live candles yet" in rendered
    assert "Order Book" in rendered


def test_watch_screen_control_renders_na_open_interest_for_spot():
    """Spot watch headers should render n/a when open interest is unavailable."""
    control = WatchScreenControl("UBTC/USDC")
    control.set_snapshot(_sample_snapshot().model_copy(update={"open_interest": None}))

    rendered = "\n".join(
        "".join(
            fragment for _, fragment in control.create_content(width=100, height=30).get_line(index)
        )
        for index in range(30)
    )

    assert "OI $" not in rendered


def test_watch_tui_fetches_with_current_interval_and_refetches_on_interval_change():
    """The watch TUI should request the currently selected backend interval."""
    calls = []

    def fetcher(coin: str, interval: str, depth: int) -> WatchSnapshot:
        calls.append((coin, interval, depth))
        return _sample_snapshot()

    tui = WatchTUI("BTC", fetcher)

    tui._refresh_snapshot()
    tui.control.create_content(width=100, height=30)
    tui._change_interval(-1)
    tui._change_interval(10)

    assert calls == [("BTC", "5m", 10), ("BTC", "1m", 11), ("BTC", "1d", 11)]


def test_watch_tui_refetches_immediately_when_resize_changes_visible_depth():
    """A resize that changes visible order book depth should trigger an immediate refetch."""
    calls = []
    refetched = Event()

    def fetcher(coin: str, interval: str, depth: int) -> WatchSnapshot:
        calls.append((coin, interval, depth))
        if len(calls) == 2:
            refetched.set()
        return _sample_snapshot().model_copy(update={"order_book_depth": depth})

    class DummyApp:
        def __init__(self) -> None:
            self.invalidations = 0

        def invalidate(self) -> None:
            self.invalidations += 1

    tui = WatchTUI("BTC", fetcher, poll_interval_seconds=60.0)
    app = DummyApp()
    tui._refresh_snapshot()
    poller = Thread(target=tui._poll_loop, args=(app,), daemon=True)
    poller.start()

    try:
        tui.control.create_content(width=100, height=30)
        assert refetched.wait(timeout=1.0)
    finally:
        tui._stop_event.set()
        tui._wake_event.set()
        poller.join(timeout=1.0)

    assert calls == [("BTC", "5m", 10), ("BTC", "5m", 11)]
    assert app.invalidations == 1


@pytest.mark.parametrize(("interval", "expected"), [("5m", "11:25"), ("1h", "03-14")])
def test_format_watch_axis_label_uses_interval_specific_format(interval: str, expected: str):
    """The watch x-axis should switch to dates for higher timeframes."""
    timestamp_ms = 1741973100000
    if interval == "5m":
        expected = datetime.fromtimestamp(timestamp_ms / 1000).strftime("%H:%M")
    else:
        expected = datetime.fromtimestamp(timestamp_ms / 1000).strftime("%m-%d")
    assert format_watch_axis_label(timestamp_ms, interval) == expected


def test_watch_screen_control_uses_date_labels_for_daily_style_intervals():
    """Higher timeframes should render date labels on the watch x-axis."""
    control = WatchScreenControl("BTC")
    snapshot = _sample_snapshot().model_copy(update={"interval": "1d"})
    control.set_snapshot(snapshot)
    control.current_interval_index = 5

    rendered = control._time_axis_line(60)

    assert "03-14" in rendered


def test_watch_screen_control_prefers_roughly_eighty_twenty_split():
    """The watch body should reserve roughly 20 percent of the width for the order book."""
    chart_width, order_book_width = watch_panel_widths(100)

    assert chart_width == 80
    assert order_book_width == 20


def test_visible_order_book_depth_matches_panel_capacity():
    """Visible order book depth should follow the rendered per-side row capacity."""
    assert visible_order_book_depth(23) == 11
