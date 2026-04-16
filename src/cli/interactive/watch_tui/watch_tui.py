"""Textual fullscreen watch UI."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from models.api import (
    DEFAULT_WATCH_INTERVAL,
    DEFAULT_WATCH_ORDER_BOOK_DEPTH,
    WATCH_INTERVAL_ORDER,
    WatchInterval,
    WatchSnapshot,
)

from ..plotting import BrailleChart, build_time_ticks
from .watch_helpers import (
    candle_close_series,
    candle_price_range,
    format_open_interest_header,
    format_order_book_footer,
    format_price_header,
    format_watch_axis_label,
    render_order_book_lines,
    visible_order_book_depth,
)


class WatchScreenControl:
    """State and formatting helpers for the Textual watch app."""

    def __init__(self, coin: str):
        self.coin = coin
        self.snapshot: WatchSnapshot | None = None
        self.error_message: str | None = None
        self.current_interval_index = WATCH_INTERVAL_ORDER.index(DEFAULT_WATCH_INTERVAL)
        self.order_book_depth = DEFAULT_WATCH_ORDER_BOOK_DEPTH

    def current_interval(self) -> WatchInterval:
        return WATCH_INTERVAL_ORDER[self.current_interval_index]

    def current_order_book_depth(self) -> int:
        return self.order_book_depth

    def advance_interval(self, delta: int) -> None:
        next_index = self.current_interval_index + delta
        self.current_interval_index = min(max(next_index, 0), len(WATCH_INTERVAL_ORDER) - 1)

    def set_order_book_depth(self, depth: int) -> bool:
        if depth == self.order_book_depth:
            return False
        self.order_book_depth = depth
        return True

    def set_snapshot(self, snapshot: WatchSnapshot) -> None:
        self.snapshot = snapshot
        self.error_message = None

    def set_error(self, message: str) -> None:
        self.error_message = message

    def header_summary(self) -> str:
        if self.snapshot is None:
            return f"{self.coin} loading live candle stream"
        if self.error_message:
            return f"{format_price_header(self.snapshot.mark_price)}   {self.error_message}"
        open_interest = format_open_interest_header(self.snapshot.open_interest)
        return f"{format_price_header(self.snapshot.mark_price)}   {open_interest}".strip()

    def chart_title(self) -> str:
        return f"Price Chart - {self.current_interval().upper()} Interval"

    def chart_summary(self) -> str:
        closes = self.close_prices()
        price_range = self.price_range()
        if not closes or price_range is None:
            return "awaiting first live candles"
        return f"last {closes[-1]:,.4f}   max {max(closes):,.4f}   min {price_range[0]:,.4f}"

    def status_line(self) -> str:
        if self.error_message:
            return f"Last fetch error: {self.error_message}"
        if self.snapshot is None:
            return "Polling backend every 500ms"
        updated_at = datetime.fromtimestamp(self.snapshot.updated_at / 1000).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        return f"Updated at {updated_at}   {len(self.snapshot.candles)} candles"

    def close_prices(self) -> list[Decimal]:
        return [] if self.snapshot is None else candle_close_series(self.snapshot.candles)

    def candle_times(self) -> list[int]:
        return (
            [] if self.snapshot is None else [candle.close_time for candle in self.snapshot.candles]
        )

    def price_range(self) -> tuple[Decimal, Decimal] | None:
        return None if self.snapshot is None else candle_price_range(self.snapshot.candles)


class OrderBookView(Static):
    """Plain-text order book panel for the Textual watch app."""

    def __init__(self, *, widget_id: str | None = None):
        super().__init__("", id=widget_id)
        self.snapshot: WatchSnapshot | None = None
        self.depth = 0

    def set_state(self, snapshot: WatchSnapshot | None, depth: int) -> None:
        self.snapshot = snapshot
        self.depth = depth
        self.refresh()

    def render(self) -> str:
        return "\n".join(
            render_order_book_lines(
                self.snapshot,
                max(self.size.width, 18),
                max(self.size.height, 5),
                self.depth,
            )
        )


class WatchApp(App[None]):
    """Textual app that renders the live watch chart and order book."""

    CSS = """
    Screen { layout: vertical; background: #101418; color: #d7dadc; }
    #header { padding: 0 1; color: #f8f8f2; text-style: bold; }
    .subheader { padding: 0 1; color: #8be9fd; }
    .footer { padding: 0 1; color: #7f8c8d; }
    #watch-body { height: 1fr; }
    #chart-column { width: 4fr; layout: vertical; padding: 0 1; }
    #book-column { width: 1fr; min-width: 20; layout: vertical; padding: 0 1 0 0; }
    .panel-title { height: auto; padding: 0 1; color: #f8f8f2; text-style: bold; }
    .panel-summary { height: auto; padding: 0 1; color: #7aa2f7; }
    BrailleChart, OrderBookView { height: 1fr; min-height: 12; border: round #3b4261; }
    OrderBookView { padding: 0 1; }
    """
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "quit_view", show=False),
        Binding("escape", "quit_view", show=False),
        Binding("enter", "quit_view", show=False),
        Binding("ctrl+c", "quit_view", show=False),
        Binding("+", "shorter_interval", show=False),
        Binding("=", "shorter_interval", show=False),
        Binding("-", "longer_interval", show=False),
        Binding("_", "longer_interval", show=False),
    ]

    def __init__(self, tui: WatchTUI):
        super().__init__()
        self.tui = tui

    def compose(self) -> ComposeResult:
        yield Static(f"Hyperliquid Watch - {self.tui.coin}", id="header")
        yield Static("", classes="subheader", id="summary")
        yield Static(
            "+ shorter interval  - longer interval  q / Esc / Enter / Ctrl-C exit", classes="footer"
        )
        with Horizontal(id="watch-body"):
            with Vertical(id="chart-column"):
                yield Static("", classes="panel-title", id="chart-title")
                yield Static("", classes="panel-summary", id="chart-summary")
                yield BrailleChart(
                    widget_id="watch-plot",
                    y_label_formatter=self._format_price_axis,
                    line_style="#8be9fd",
                )
            with Vertical(id="book-column"):
                yield Static("Order Book", classes="panel-title")
                yield OrderBookView(widget_id="order-book")
                yield Static("", classes="footer", id="book-footer")
        yield Static("", classes="footer", id="status")

    def on_mount(self) -> None:
        self.tui._refresh_snapshot()
        self._refresh_view()
        self.call_after_refresh(self._initialize_view)

    def on_resize(self) -> None:
        self.call_after_refresh(self._sync_depth_and_refresh)

    def action_quit_view(self) -> None:
        self.exit()

    def action_shorter_interval(self) -> None:
        self.tui._change_interval(-1)
        self._refresh_view()

    def action_longer_interval(self) -> None:
        self.tui._change_interval(1)
        self._refresh_view()

    def _initialize_view(self) -> None:
        self._sync_depth_and_refresh()
        self.set_interval(self.tui.poll_interval_seconds, self._poll_snapshot)

    def _poll_snapshot(self) -> None:
        self.tui._refresh_snapshot()
        self._refresh_view()

    def _sync_depth_and_refresh(self) -> None:
        depth = visible_order_book_depth(max(self.query_one(OrderBookView).size.height, 3))
        if self.tui.control.set_order_book_depth(depth):
            self.tui._refresh_snapshot()
        self._refresh_view()

    def _refresh_view(self) -> None:
        control = self.tui.control
        self.query_one("#summary", Static).update(control.header_summary())
        self.query_one("#chart-title", Static).update(control.chart_title())
        self.query_one("#chart-summary", Static).update(control.chart_summary())
        self.query_one("#status", Static).update(control.status_line())
        book = self.query_one(OrderBookView)
        book.set_state(control.snapshot, control.current_order_book_depth())
        self.query_one("#book-footer", Static).update(
            format_order_book_footer(control.snapshot, max(book.size.width, 1)).strip()
        )
        plot = self.query_one("#watch-plot", BrailleChart)
        values = control.close_prices()
        if not values:
            plot.set_data(
                [],
                empty_message="Loading live market data"
                if control.snapshot is None
                else "No live candles yet",
            )
            return
        x_tick_indices, x_tick_labels = build_time_ticks(
            control.candle_times(),
            lambda timestamp_ms: format_watch_axis_label(timestamp_ms, control.current_interval()),
        )
        plot.set_data(values, x_tick_indices=x_tick_indices, x_tick_labels=x_tick_labels)

    def _format_price_axis(self, value: Decimal) -> str:
        return f"{value:,.4f}".rstrip("0").rstrip(".")


class WatchTUI:
    """Launch the Textual fullscreen watch view for a live market."""

    def __init__(
        self,
        coin: str,
        snapshot_fetcher: Callable[[str, WatchInterval, int], WatchSnapshot],
        poll_interval_seconds: float = 0.5,
    ):
        self.coin = coin
        self.snapshot_fetcher = snapshot_fetcher
        self.poll_interval_seconds = poll_interval_seconds
        self.control = WatchScreenControl(coin)

    def run(self) -> None:
        self._build_app().run()

    def _build_app(self) -> WatchApp:
        return WatchApp(self)

    def _refresh_snapshot(self) -> None:
        try:
            self.control.set_snapshot(
                self.snapshot_fetcher(
                    self.coin,
                    self.control.current_interval(),
                    self.control.current_order_book_depth(),
                )
            )
        except Exception as exc:
            self.control.set_error(str(exc))

    def _change_interval(self, delta: int) -> None:
        previous_interval = self.control.current_interval()
        self.control.advance_interval(delta)
        if self.control.current_interval() != previous_interval:
            self._refresh_snapshot()
