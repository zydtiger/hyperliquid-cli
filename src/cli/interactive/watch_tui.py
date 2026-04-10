"""
Fullscreen TUI for monitoring a live perpetual market.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from threading import Event, Thread
from typing import TypeAlias

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import UIContent, UIControl
from prompt_toolkit.mouse_events import MouseEvent
from prompt_toolkit.styles import Style

from models.api import (
    DEFAULT_WATCH_INTERVAL,
    WATCH_INTERVAL_ORDER,
    WatchInterval,
    WatchSnapshot,
)

from .charting import render_braille_plot
from .watch_helpers import (
    candle_close_series,
    candle_price_range,
    format_open_interest_header,
    format_price_header,
)

HEADER_LINES = 3
FOOTER_LINES = 2
MIN_PANEL_HEIGHT = 8
DisplayFragment: TypeAlias = tuple[str, str] | tuple[str, str, Callable[[MouseEvent], object]]
DisplayLine: TypeAlias = list[DisplayFragment]


class WatchTUI:
    """Launch a fullscreen TUI for a live perpetual market snapshot."""

    def __init__(
        self,
        coin: str,
        snapshot_fetcher: Callable[[str, WatchInterval], WatchSnapshot],
        poll_interval_seconds: float = 0.5,
    ) -> None:
        self.coin = coin
        self.snapshot_fetcher = snapshot_fetcher
        self.poll_interval_seconds = poll_interval_seconds
        self.control = WatchScreenControl(coin)
        self._stop_event = Event()

    def run(self) -> None:
        """Run the watch TUI and poll the backend until the user exits."""
        app = self._build_application()
        self._refresh_snapshot()
        poller = Thread(target=self._poll_loop, args=(app,), daemon=True)
        poller.start()
        try:
            app.run()
        finally:
            self._stop_event.set()
            poller.join(timeout=1.0)

    def _poll_loop(self, app: Application[None]) -> None:
        while not self._stop_event.wait(self.poll_interval_seconds):
            self._refresh_snapshot()
            app.invalidate()

    def _refresh_snapshot(self) -> None:
        try:
            self.control.set_snapshot(
                self.snapshot_fetcher(self.coin, self.control.current_interval())
            )
        except Exception as exc:
            self.control.set_error(str(exc))

    def _change_interval(self, delta: int) -> None:
        previous_interval = self.control.current_interval()
        self.control.advance_interval(delta)
        if self.control.current_interval() != previous_interval:
            self._refresh_snapshot()

    def _build_application(self) -> Application[None]:
        bindings = KeyBindings()

        @bindings.add("q")
        @bindings.add("escape")
        @bindings.add("enter")
        @bindings.add("c-c")
        def _exit(event) -> None:  # type: ignore[no-untyped-def]
            self._stop_event.set()
            event.app.exit()

        @bindings.add("+")
        @bindings.add("=")
        def _shorter_interval(event) -> None:  # type: ignore[no-untyped-def]
            self._change_interval(-1)
            event.app.invalidate()

        @bindings.add("-")
        @bindings.add("_")
        def _longer_interval(event) -> None:  # type: ignore[no-untyped-def]
            self._change_interval(1)
            event.app.invalidate()

        return Application(
            layout=Layout(Window(content=self.control, always_hide_cursor=True)),
            key_bindings=bindings,
            full_screen=True,
            erase_when_done=True,
            mouse_support=False,
            style=Style.from_dict(
                {
                    "root": "bg:#101418 #d7dadc",
                    "header": "bold #f8f8f2",
                    "subheader": "#8be9fd",
                    "footer": "#7f8c8d",
                    "chart": "#8be9fd",
                    "ask": "#ff6b6b",
                    "bid": "#50fa7b",
                    "mid": "bold #f1fa8c",
                    "error": "#ff5555",
                }
            ),
        )


class WatchScreenControl(UIControl):
    """Custom control that draws the full live watch screen."""

    def __init__(self, coin: str) -> None:
        self.coin = coin
        self.snapshot: WatchSnapshot | None = None
        self.error_message: str | None = None
        self.current_interval_index = WATCH_INTERVAL_ORDER.index(DEFAULT_WATCH_INTERVAL)

    def create_content(self, width: int, height: int) -> UIContent:
        lines = self._build_lines(max(width, 1), max(height, 12))

        def get_line(index: int) -> DisplayLine:
            if 0 <= index < len(lines):
                return lines[index]
            return [("class:root", " " * width)]

        return UIContent(get_line=get_line, line_count=len(lines), show_cursor=False)

    def is_focusable(self) -> bool:
        return False

    def current_interval(self) -> WatchInterval:
        return WATCH_INTERVAL_ORDER[self.current_interval_index]

    def advance_interval(self, delta: int) -> None:
        next_index = self.current_interval_index + delta
        self.current_interval_index = min(max(next_index, 0), len(WATCH_INTERVAL_ORDER) - 1)

    def set_snapshot(self, snapshot: WatchSnapshot) -> None:
        self.snapshot = snapshot
        self.error_message = None

    def set_error(self, message: str) -> None:
        self.error_message = message

    def _build_lines(self, width: int, height: int) -> list[DisplayLine]:
        lines: list[DisplayLine] = [
            [("class:header", self._pad(f" Hyperliquid Watch - {self.coin} ", width))],
            [("class:subheader", self._pad(self._header_summary(), width))],
            [
                (
                    "class:footer",
                    self._pad(
                        " + shorter interval  - longer interval  q / Esc / Enter / Ctrl-C exit ",
                        width,
                    ),
                )
            ],
        ]

        body_height = max(height - HEADER_LINES - FOOTER_LINES, MIN_PANEL_HEIGHT)
        plot_height = max(body_height - 2, 3)
        plot_width = max(width - 2, 8)
        lines.extend(self._render_chart_panel(width, plot_width, plot_height))
        lines.append([("class:footer", self._pad(self._time_axis_line(width), width))])
        lines.append([("class:footer", self._pad(self._status_line(), width))])
        return lines

    def _render_chart_panel(
        self,
        width: int,
        plot_width: int,
        plot_height: int,
    ) -> list[DisplayLine]:
        title = (
            f" Price Chart - {self.current_interval().upper()} Interval  {self._chart_footer()} "
        )
        top_line = self._border_line("┌", title, "┐", width)
        bottom_line = self._border_line("└", self._chart_bottom_line(), "┘", width)
        closes = self._close_prices()
        if self.snapshot is None:
            plot_lines = self._empty_lines(plot_width, plot_height, "Loading live market data")
        elif closes:
            plot_lines = render_braille_plot(closes, plot_width, plot_height)
        else:
            plot_lines = self._empty_lines(plot_width, plot_height, "No live candles yet")

        panel_lines: list[DisplayLine] = [[("class:root", self._pad(top_line, width))]]
        panel_lines.extend(
            [("class:root", "│"), ("class:chart", line.ljust(plot_width)), ("class:root", "│")]
            for line in plot_lines
        )
        panel_lines.append([("class:root", self._pad(bottom_line, width))])
        return panel_lines

    def _header_summary(self) -> str:
        if self.snapshot is None:
            return f" {self.coin}  loading live candle stream "
        if self.error_message:
            return f" {format_price_header(self.snapshot.mark_price)}   {self.error_message} "
        return (
            f" {format_price_header(self.snapshot.mark_price)}   "
            f"{format_open_interest_header(self.snapshot.open_interest)} "
        )

    def _chart_footer(self) -> str:
        closes = self._close_prices()
        if not closes:
            return "awaiting first live candles"
        return f"last {closes[-1]:,.4f}  max {max(closes):,.4f}"

    def _chart_bottom_line(self) -> str:
        price_range = self._price_range()
        if price_range is None:
            return " min n/a "
        return f" min {price_range[0]:,.4f} "

    def _time_axis_line(self, width: int) -> str:
        if self.snapshot is None or not self.snapshot.candles:
            return " No timestamps available "
        start_label = self._format_time(self.snapshot.candles[0].open_time)
        end_label = self._format_time(self.snapshot.candles[-1].close_time)
        spacing = max(width - len(start_label) - len(end_label) - 2, 1)
        return f" {start_label}{' ' * spacing}{end_label} "

    def _status_line(self) -> str:
        if self.error_message:
            return f" Last fetch error: {self.error_message} "
        if self.snapshot is None:
            return " Polling backend every 500ms "
        candle_count = len(self.snapshot.candles)
        return (
            f" Updated at {self.snapshot.updated_at}  "
            f"{candle_count} candles  Order book temporarily hidden "
        )

    def _close_prices(self) -> list[Decimal]:
        if self.snapshot is None:
            return []
        return candle_close_series(self.snapshot.candles)

    def _price_range(self) -> tuple[Decimal, Decimal] | None:
        if self.snapshot is None:
            return None
        return candle_price_range(self.snapshot.candles)

    def _pad(self, value: str, width: int) -> str:
        return value[:width].ljust(width)

    def _border_line(self, left: str, content: str, right: str, width: int) -> str:
        inner_width = max(width - len(left) - len(right), 0)
        trimmed = content[:inner_width]
        return f"{left}{trimmed}{'─' * max(inner_width - len(trimmed), 0)}{right}"

    def _empty_lines(self, width: int, height: int, message: str) -> list[str]:
        lines = [" " * width for _ in range(height)]
        if lines:
            lines[len(lines) // 2] = message.center(width)[:width].ljust(width)
        return lines

    def _format_time(self, timestamp_ms: int) -> str:
        return datetime.fromtimestamp(timestamp_ms / 1000).strftime("%H:%M:%S")


__all__ = ["WatchScreenControl", "WatchTUI"]
