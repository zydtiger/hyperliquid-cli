"""
Rendering control for the live watch TUI.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import TypeAlias

from prompt_toolkit.layout.controls import UIContent, UIControl
from prompt_toolkit.mouse_events import MouseEvent

from models.api import (
    DEFAULT_WATCH_INTERVAL,
    DEFAULT_WATCH_ORDER_BOOK_DEPTH,
    WATCH_INTERVAL_ORDER,
    WatchInterval,
    WatchSnapshot,
)

from .charting import render_braille_plot
from .watch_helpers import (
    border_line,
    candle_close_series,
    candle_price_range,
    empty_panel_lines,
    format_open_interest_header,
    format_order_book_footer,
    format_price_header,
    format_watch_axis_label,
    pad_line,
    render_order_book_lines,
    visible_order_book_depth,
    watch_panel_widths,
)

HEADER_LINES = 3
FOOTER_LINES = 2
MIN_PANEL_HEIGHT = 8
DisplayFragment: TypeAlias = tuple[str, str] | tuple[str, str, Callable[[MouseEvent], object]]
DisplayLine: TypeAlias = list[DisplayFragment]


class WatchScreenControl(UIControl):
    """Custom control that draws the full live watch screen."""

    def __init__(self, coin: str, on_depth_change: Callable[[], None] | None = None) -> None:
        self.coin = coin
        self.snapshot: WatchSnapshot | None = None
        self.error_message: str | None = None
        self.current_interval_index = WATCH_INTERVAL_ORDER.index(DEFAULT_WATCH_INTERVAL)
        self.order_book_depth = DEFAULT_WATCH_ORDER_BOOK_DEPTH
        self._on_depth_change = on_depth_change

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

    def current_order_book_depth(self) -> int:
        return self.order_book_depth

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
            [("class:header", pad_line(f" Hyperliquid Watch - {self.coin} ", width))],
            [("class:subheader", pad_line(self._header_summary(), width))],
            [
                (
                    "class:footer",
                    pad_line(
                        " + shorter interval  - longer interval  q / Esc / Enter / Ctrl-C exit ",
                        width,
                    ),
                )
            ],
        ]
        body_height = max(height - HEADER_LINES - FOOTER_LINES, MIN_PANEL_HEIGHT)
        chart_width, order_book_width = watch_panel_widths(width)
        panel_height = max(body_height - 2, 3)
        self._sync_order_book_depth(visible_order_book_depth(panel_height))
        lines.extend(self._render_split_panels(chart_width, order_book_width, panel_height))
        lines.append([("class:footer", pad_line(self._time_axis_line(width), width))])
        lines.append([("class:footer", pad_line(self._status_line(), width))])
        return lines

    def _sync_order_book_depth(self, depth: int) -> None:
        if depth == self.order_book_depth:
            return
        self.order_book_depth = depth
        if self._on_depth_change is not None:
            self._on_depth_change()

    def _render_split_panels(
        self, chart_width: int, order_book_width: int, panel_height: int
    ) -> list[DisplayLine]:
        chart_panel = self._render_chart_panel(chart_width, panel_height)
        order_book_panel = self._render_order_book_panel(
            order_book_width, panel_height, self.order_book_depth
        )
        return [
            [*chart_line, *order_book_line]
            for chart_line, order_book_line in zip(chart_panel, order_book_panel, strict=True)
        ]

    def _render_chart_panel(self, width: int, plot_height: int) -> list[DisplayLine]:
        plot_width = max(width - 2, 8)
        title = (
            f" Price Chart - {self.current_interval().upper()} Interval  {self._chart_footer()} "
        )
        top_line = border_line("┌", title, "┐", width)
        bottom_line = border_line("└", self._chart_bottom_line(), "┘", width)
        if self.snapshot is None:
            plot_lines = [
                [line]
                for line in empty_panel_lines(
                    plot_width, plot_height, "Loading live market data", "class:chart"
                )
            ]
        elif self.snapshot.candles:
            plot_lines = [
                [("class:chart", line)]
                for line in render_braille_plot(self._close_prices(), plot_width, plot_height)
            ]
        else:
            plot_lines = [
                [line]
                for line in empty_panel_lines(
                    plot_width, plot_height, "No live candles yet", "class:chart"
                )
            ]
        panel_lines: list[DisplayLine] = [[("class:root", pad_line(top_line, width))]]
        panel_lines.extend([("class:root", "│"), *line, ("class:root", "│")] for line in plot_lines)
        panel_lines.append([("class:root", pad_line(bottom_line, width))])
        return panel_lines

    def _render_order_book_panel(
        self, width: int, panel_height: int, depth: int
    ) -> list[DisplayLine]:
        content_width = max(width - 2, 1)
        top_line = border_line("┌", " Order Book ", "┐", width)
        bottom_line = border_line(
            "└", format_order_book_footer(self.snapshot, content_width), "┘", width
        )
        rows: list[DisplayLine] = [
            [(style, text)]
            for style, text in render_order_book_lines(
                self.snapshot, content_width, panel_height, depth
            )
        ]
        panel_lines: list[DisplayLine] = [[("class:root", pad_line(top_line, width))]]
        panel_lines.extend([("class:root", "│"), *line, ("class:root", "│")] for line in rows)
        panel_lines.append([("class:root", pad_line(bottom_line, width))])
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
        interval = self.current_interval()
        start_label = format_watch_axis_label(self.snapshot.candles[0].open_time, interval)
        end_label = format_watch_axis_label(self.snapshot.candles[-1].close_time, interval)
        spacing = max(width - len(start_label) - len(end_label) - 2, 1)
        return f" {start_label}{' ' * spacing}{end_label} "

    def _status_line(self) -> str:
        if self.error_message:
            return f" Last fetch error: {self.error_message} "
        if self.snapshot is None:
            return " Polling backend every 500ms "
        candle_count = len(self.snapshot.candles)
        updated_at = datetime.fromtimestamp(self.snapshot.updated_at / 1000).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        return f" Updated at {updated_at}  {candle_count} candles "

    def _close_prices(self) -> list[Decimal]:
        if self.snapshot is None:
            return []
        return candle_close_series(self.snapshot.candles)

    def _price_range(self) -> tuple[Decimal, Decimal] | None:
        if self.snapshot is None:
            return None
        return candle_price_range(self.snapshot.candles)


__all__ = [
    "FOOTER_LINES",
    "HEADER_LINES",
    "MIN_PANEL_HEIGHT",
    "DisplayFragment",
    "DisplayLine",
    "WatchScreenControl",
]
