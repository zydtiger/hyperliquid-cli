"""
Fullscreen TUI for rendering PnL history charts.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from itertools import pairwise

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import UIContent, UIControl
from prompt_toolkit.styles import Style

from models.api import PNL_WINDOW_ORDER, PnlHistory, PnlHistoryCatalog, PnlPoint

BRAILLE_BITS = {
    (0, 0): 0x01,
    (0, 1): 0x02,
    (0, 2): 0x04,
    (0, 3): 0x40,
    (1, 0): 0x08,
    (1, 1): 0x10,
    (1, 2): 0x20,
    (1, 3): 0x80,
}
MIN_PANEL_HEIGHT = 6
PANEL_GAP = 1
HEADER_LINES = 3
FOOTER_LINES = 2


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
        def _next_window(event) -> None:  # type: ignore[no-untyped-def]
            self.control.advance_window(-1)
            event.app.invalidate()

        @bindings.add("-")
        @bindings.add("_")
        def _previous_window(event) -> None:  # type: ignore[no-untyped-def]
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

        def get_line(index: int) -> list[tuple[str, str]]:
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

    def current_window(self) -> str:
        """Return the active PnL window key."""
        return PNL_WINDOW_ORDER[self.current_window_index]

    def current_history(self) -> PnlHistory:
        """Return the active PnL history, defaulting to an empty history."""
        window = self.current_window()
        return self.history_by_window.get(window, PnlHistory(window=window, points=[]))

    def _build_lines(self, width: int, height: int) -> list[list[tuple[str, str]]]:
        history = self.current_history()
        active_label = window_label(history.window)
        latest = history.points[-1] if history.points else None
        lines: list[list[tuple[str, str]]] = [
            [("class:header", self._pad(f" Hyperliquid PnL TUI - {active_label} ", width))],
            [("class:summary", self._pad(self._summary_line(active_label, latest), width))],
            [("class:footer", self._pad(" - prev  + next  q / Esc / Enter / Ctrl-C exit ", width))],
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
    ) -> list[list[tuple[str, str]]]:
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
        panel_lines = [[("class:root", self._pad(top_line, width))]]

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
    ) -> list[list[tuple[str, str]]]:
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

        panel_lines = [[("class:root", self._pad(top_line, width))]]
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


def render_braille_plot(values: list[Decimal], width: int, height: int) -> list[str]:
    """Render a line chart using Unicode braille cells."""
    if not values:
        return [" " * width for _ in range(height)]

    pixel_width = max(width * 2, 2)
    pixel_height = max(height * 4, 4)
    pixels = [[False for _ in range(pixel_width)] for _ in range(pixel_height)]
    points = _series_to_pixel_points(values, pixel_width, pixel_height)

    for (x1, y1), (x2, y2) in pairwise(points):
        _draw_pixel_line(pixels, x1, y1, x2, y2)

    for x, y in points:
        pixels[y][x] = True

    return _pixels_to_braille_lines(pixels, width, height)


def _series_to_pixel_points(
    values: list[Decimal],
    pixel_width: int,
    pixel_height: int,
) -> list[tuple[int, int]]:
    """Map numeric values into the high-resolution braille grid."""
    if len(values) == 1:
        return [(0, pixel_height // 2)]

    min_value = min(values)
    max_value = max(values)
    span = max_value - min_value
    points: list[tuple[int, int]] = []

    for index, value in enumerate(values):
        x = round(index * (pixel_width - 1) / (len(values) - 1))
        if span == 0:
            y = pixel_height // 2
        else:
            normalized = (value - min_value) / span
            y = pixel_height - 1 - round(float(normalized) * (pixel_height - 1))
        points.append((x, y))

    return points


def _draw_pixel_line(
    pixels: list[list[bool]],
    x1: int,
    y1: int,
    x2: int,
    y2: int,
) -> None:
    """Draw a line across the high-resolution pixel grid."""
    dx = x2 - x1
    dy = y2 - y1
    steps = max(abs(dx), abs(dy), 1)

    for step in range(steps + 1):
        x = round(x1 + dx * step / steps)
        y = round(y1 + dy * step / steps)
        pixels[y][x] = True


def _pixels_to_braille_lines(
    pixels: list[list[bool]],
    width: int,
    height: int,
) -> list[str]:
    """Convert a 2x4 pixel grid into braille characters."""
    lines: list[str] = []

    for cell_y in range(height):
        row_chars = []
        for cell_x in range(width):
            cell = 0
            for dot_x in range(2):
                for dot_y in range(4):
                    pixel_x = cell_x * 2 + dot_x
                    pixel_y = cell_y * 4 + dot_y
                    if pixel_y < len(pixels) and pixel_x < len(pixels[pixel_y]):
                        if pixels[pixel_y][pixel_x]:
                            cell |= BRAILLE_BITS[(dot_x, dot_y)]
            row_chars.append(chr(0x2800 + cell) if cell else " ")
        lines.append("".join(row_chars))

    return lines


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
