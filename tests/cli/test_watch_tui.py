"""
Tests for the live watch TUI renderer.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from cli.interactive.watch_helpers import format_watch_axis_label, next_watch_refresh_seconds
from cli.interactive.watch_tui import WatchScreenControl, WatchTUI
from models.api import OrderBookLevel, WatchCandle, WatchSnapshot


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


def test_watch_screen_control_renders_single_price_chart_panel():
    """The watch screen should render a close-price braille chart and hide the order book."""
    control = WatchScreenControl("BTC")
    control.set_snapshot(_sample_snapshot())
    content = control.create_content(width=100, height=30)
    lines = ["".join(fragment for _, fragment in content.get_line(index)) for index in range(30)]
    rendered = "\n".join(lines)

    assert "Price Chart - 5M Interval" in rendered
    assert "last 43,250.5000  max 43,250.5000" in rendered
    assert "Order book temporarily hidden" in rendered
    assert "Order Book" not in rendered
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
    assert "Polling backend every 5m" in rendered
    assert "Order book temporarily hidden" not in rendered

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
    assert "Order book temporarily hidden" in rendered


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

    def fetcher(coin: str, interval: str) -> WatchSnapshot:
        calls.append((coin, interval))
        return _sample_snapshot()

    tui = WatchTUI("BTC", fetcher)

    tui._refresh_snapshot()
    tui._change_interval(-1)
    tui._change_interval(10)

    assert calls == [("BTC", "5m"), ("BTC", "1m"), ("BTC", "1d")]


@pytest.mark.parametrize(
    ("interval", "now_ms", "expected"),
    [("1m", 90_000, 30.0), ("5m", 305_000, 295.0), ("1h", 3_700_000, 3_500.0)],
)
def test_next_watch_refresh_seconds_tracks_active_interval(
    interval: str, now_ms: int, expected: float
):
    """The watch refresh cadence should wait until the next interval boundary."""
    assert next_watch_refresh_seconds(interval, now_ms) == expected


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
