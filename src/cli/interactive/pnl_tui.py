"""
Fullscreen TUI for rendering PnL history charts.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import TypeAlias

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import UIContent, UIControl
from prompt_toolkit.mouse_events import MouseEvent
from prompt_toolkit.styles import Style

from models.api import PNL_WINDOW_ORDER, PnlHistory, PnlHistoryCatalog, PnlPoint, PnlWindow

from .charting import render_braille_plot

MIN_PANEL_HEIGHT = 6
PANEL_GAP = 1
HEADER_LINES = 3
FOOTER_LINES = 2
DisplayFragment: TypeAlias = tuple[str, str] | tuple[str, str, Callable[[MouseEvent], object]]
DisplayLine: TypeAlias = list[DisplayFragment]


class PnlTUI:
    """Launch a fullscreen TUI for multi-window PnL history."""

    def __init__(self, history_catalog: PnlHistoryCatalog):
        self.control = PnlScreenControl(history_catalog)

    def run(self) -> None:
        """Run the fullscreen TUI application."""
        self._build_application().run()

    def _build_application(self) -> Application[None]:
        """Create the fullscreen application."""
        bindings = KeyBindings()

        @bindings.add("q")
        @bindings.add("escape")
        @bindings.add("enter")
        @bindings.add("c-c")
        def _exit(event) -> None:  # type: ignore[no-untyped-def]
            event.app.exit()

        @bindings.add("+")
        @bindings.add("=")
        def _zoom_in(event) -> None:  # type: ignore[no-untyped-def]
            self.control.advance_window(-1)
            event.app.invalidate()

        @bindings.add("-")
        @bindings.add("_")
        def _zoom_out(event) -> None:  # type: ignore[no-untyped-def]
            self.control.advance_window(1)
            event.app.invalidate()

        return Application(
            layout=Layout(
                Window(
                    content=self.control,
                    always_hide_cursor=True,
                )
            ),
            key_bindings=bindings,
            full_screen=True,
            erase_when_done=True,
            mouse_support=False,
            style=Style.from_dict(
                {
                    "root": "bg:#101418 #d7dadc",
                    "header": "bold #8be9fd",
                    "summary": "#f8f8f2",
                    "footer": "#7f8c8d",
                    "panel-total": "#50fa7b",
                    "panel-perp": "#ffb86c",
                    "panel-spot": "#bd93f9",
                }
            ),
        )


class PnlScreenControl(UIControl):
    """Custom control that draws the full PnL screen."""

    def __init__(self, history_catalog: PnlHistoryCatalog):
        self.history_catalog = history_catalog
        self.history_by_window = {history.window: history for history in history_catalog.histories}
        default_window = history_catalog.default_window
        default_index = (
            PNL_WINDOW_ORDER.index(default_window) if default_window in PNL_WINDOW_ORDER else 0
        )
        self.current_window_index = default_index

    def create_content(self, width: int, height: int) -> UIContent:
        """Render the TUI content for the current terminal size."""
        lines = self._build_lines(max(width, 20), max(height, 12))

        def get_line(index: int) -> DisplayLine:
            if 0 <= index < len(lines):
                return lines[index]
            return [("class:root", " " * width)]

        return UIContent(get_line=get_line, line_count=len(lines), show_cursor=False)

    def is_focusable(self) -> bool:
        """The graph view does not take focus."""
        return False

    def advance_window(self, delta: int) -> None:
        """Move backward or forward through the supported PnL windows."""
        next_index = self.current_window_index + delta
        self.current_window_index = min(max(next_index, 0), len(PNL_WINDOW_ORDER) - 1)

    def current_window(self) -> PnlWindow:
        """Return the active PnL window key."""
        return PNL_WINDOW_ORDER[self.current_window_index]

    def current_history(self) -> PnlHistory:
        """Return the active PnL history, defaulting to an empty history."""
        window = self.current_window()
        return self.history_by_window.get(window, PnlHistory(window=window, points=[]))

    def _build_lines(self, width: int, height: int) -> list[DisplayLine]:
        history = self.current_history()
        active_label = window_label(history.window)
        latest = history.points[-1] if history.points else None
        lines: list[DisplayLine] = [
            [("class:header", self._pad(f" Hyperliquid PnL TUI - {active_label} ", width))],
            [("class:summary", self._pad(self._summary_line(active_label, latest), width))],
            [
                (
                    "class:footer",
                    self._pad(" + zoom in  - zoom out  q / Esc / Enter / Ctrl-C exit ", width),
                )
            ],
        ]

        available_height = max(height - HEADER_LINES - FOOTER_LINES, MIN_PANEL_HEIGHT * 3)
        panel_height = max((available_height - (2 * PANEL_GAP)) // 3, MIN_PANEL_HEIGHT)
        plot_height = max(panel_height - 2, 3)
        plot_width = max(width - 2, 8)

        panels = [
            ("Total PnL", [point.total_pnl for point in history.points], "panel-total"),
            ("Perp PnL", [point.perp_pnl for point in history.points], "panel-perp"),
            ("Spot PnL", [point.spot_pnl for point in history.points], "panel-spot"),
        ]

        for index, (title, values, style) in enumerate(panels):
            lines.extend(self._render_panel(title, values, style, width, plot_width, plot_height))
            if index < len(panels) - 1:
                lines.append([("class:root", " " * width)])

        lines.append([("class:footer", self._pad(self._time_axis_line(history, width), width))])
        lines.append(
            [
                (
                    "class:footer",
                    self._pad(" Perp and spot use independent y-scales per active window ", width),
                )
            ]
        )
        return lines[:height]

    def _render_panel(
        self,
        title: str,
        values: list[Decimal],
        style: str,
        width: int,
        plot_width: int,
        plot_height: int,
    ) -> list[DisplayLine]:
        if not values:
            return self._render_empty_panel(title, style, width, plot_width, plot_height)

        plot_lines = render_braille_plot(values, plot_width, plot_height)
        top_line = self._build_border_line(
            left="┌",
            content=f" {title}  last {format_money(values[-1])}  max {format_money(max(values))} ",
            right="┐",
            width=width,
        )
        bottom_line = self._build_border_line(
            left="└",
            content=f" min {format_money(min(values))}",
            right="┘",
            width=width,
        )
        panel_lines: list[DisplayLine] = [[("class:root", self._pad(top_line, width))]]

        for line in plot_lines:
            panel_lines.append(
                [
                    ("class:root", "│"),
                    (f"class:{style}", line.ljust(plot_width)),
                    ("class:root", "│"),
                ]
            )

        panel_lines.append([("class:root", self._pad(bottom_line, width))])
        return panel_lines

    def _render_empty_panel(
        self,
        title: str,
        style: str,
        width: int,
        plot_width: int,
        plot_height: int,
    ) -> list[DisplayLine]:
        """Render an empty state for windows that have no points."""
        top_line = self._build_border_line(
            left="┌",
            content=f" {title}  no data for selected window ",
            right="┐",
            width=width,
        )
        bottom_line = self._build_border_line(
            left="└", content=" no samples ", right="┘", width=width
        )
        empty_lines = [" " * plot_width for _ in range(plot_height)]
        message_row = plot_height // 2
        message = "No PnL samples in this window"
        empty_lines[message_row] = message.center(plot_width)[:plot_width].ljust(plot_width)

        panel_lines: list[DisplayLine] = [[("class:root", self._pad(top_line, width))]]
        for line in empty_lines:
            panel_lines.append(
                [
                    ("class:root", "│"),
                    (f"class:{style}", line),
                    ("class:root", "│"),
                ]
            )
        panel_lines.append([("class:root", self._pad(bottom_line, width))])
        return panel_lines

    def _summary_line(self, active_label: str, latest: PnlPoint | None) -> str:
        if latest is None:
            return f" {active_label}  no data in selected window "

        return (
            f" {active_label}   Total {format_money(latest.total_pnl)}   "
            f"Perp {format_money(latest.perp_pnl)}   "
            f"Spot {format_money(latest.spot_pnl)} "
        )

    def _pad(self, value: str, width: int) -> str:
        return value[:width].ljust(width)

    def _build_border_line(self, left: str, content: str, right: str, width: int) -> str:
        """Build a single-line frame border with exact terminal width."""
        inner_width = max(width - len(left) - len(right), 0)
        trimmed_content = content[:inner_width]
        fill = "─" * max(inner_width - len(trimmed_content), 0)
        return f"{left}{trimmed_content}{fill}{right}"

    def _format_date(self, timestamp_ms: int) -> str:
        return datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC).strftime("%m-%d")

    def _time_axis_line(self, history: PnlHistory, width: int) -> str:
        """Render the shared time axis labels for the active window."""
        if not history.points:
            return " No timestamps available "

        start_label = self._format_date(history.points[0].time)
        end_label = self._format_date(history.points[-1].time)
        spacing = max(width - len(start_label) - len(end_label) - 2, 1)
        return f" {start_label}{' ' * spacing}{end_label} "


def format_money(value: Decimal) -> str:
    """Format currency values with a sign."""
    return f"${value:+,.2f}"


def window_label(window: str) -> str:
    """Map window keys to user-facing labels."""
    labels = {
        "1d": "1D",
        "3d": "3D",
        "7d": "7D",
        "1m": "1M",
        "3m": "3M",
        "6m": "6M",
        "1y": "1Y",
        "all": "ALL-TIME",
    }
    return labels.get(window, window.upper())


__all__ = ["PnlScreenControl", "PnlTUI", "format_money", "render_braille_plot", "window_label"]
