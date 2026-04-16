"""Textual widget for single-series braille charts."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from rich.text import Text
from textual.widget import Widget

from .braille_rendering import render_braille_plot
from .chart_ticks import (
    build_plot_border_line,
    build_plot_columns,
    build_x_axis_labels_line,
    build_y_axis_labels,
)

AXIS_STYLE = "#3b4261"


class BrailleChart(Widget):
    """Textual widget that renders a single-series braille chart with tick labels."""

    DEFAULT_CSS = """
    BrailleChart {
        width: 1fr;
        height: 1fr;
    }
    """

    def __init__(
        self,
        *,
        y_label_formatter: Callable[[Decimal], str],
        line_style: str,
        show_x_ticks: bool = True,
        widget_id: str | None = None,
    ) -> None:
        super().__init__(id=widget_id)
        self._y_label_formatter = y_label_formatter
        self._line_style = line_style
        self._show_x_ticks = show_x_ticks
        self._values: list[Decimal] = []
        self._x_tick_indices: list[int] = []
        self._x_tick_labels: list[str] = []
        self._empty_message = ""

    def set_data(
        self,
        values: list[Decimal],
        *,
        x_tick_indices: list[int] | None = None,
        x_tick_labels: list[str] | None = None,
        empty_message: str = "",
    ) -> None:
        self._values = values
        self._x_tick_indices = x_tick_indices or []
        self._x_tick_labels = x_tick_labels or []
        self._empty_message = empty_message
        self.refresh()

    def render(self) -> Text:
        width = max(self.size.width, 8)
        height = max(self.size.height, 3)
        if not self._values:
            return self._render_empty(width, height)

        show_x_ticks = self._show_x_ticks and bool(self._x_tick_indices and self._x_tick_labels)
        plot_height = max(height - 2 - (1 if show_x_ticks else 0), 1)
        axis_labels, axis_min, axis_max = build_y_axis_labels(
            min(self._values),
            max(self._values),
            plot_height,
            self._y_label_formatter,
        )
        axis_width = len(axis_labels[0]) if axis_labels else 0
        axis_width = min(axis_width, max(width - 3, 0))
        plot_offset = axis_width + 1
        plot_width = max(width - axis_width - 2, 1)
        trimmed_axis_labels = [label[-axis_width:] if axis_width else "" for label in axis_labels]
        plot_lines = render_braille_plot(
            self._values,
            plot_width,
            plot_height,
            min_value=axis_min,
            max_value=axis_max,
        )

        rendered = Text()
        if axis_width:
            rendered.append(" " * axis_width, AXIS_STYLE)
        rendered.append(
            build_plot_border_line(
                total_width=width,
                plot_offset=plot_offset,
                plot_width=plot_width,
                left_corner="┌",
                right_corner="┐",
            )[axis_width:],
            AXIS_STYLE,
        )
        rendered.append("\n")

        for row, plot_line in enumerate(plot_lines):
            if axis_width:
                rendered.append(trimmed_axis_labels[row].rjust(axis_width), AXIS_STYLE)
            axis_char = "┤" if trimmed_axis_labels[row].strip() else "│"
            rendered.append(axis_char, AXIS_STYLE)
            rendered.append(plot_line.ljust(plot_width), self._line_style)
            rendered.append("│", AXIS_STYLE)
            rendered.append("\n")

        plot_columns = (
            build_plot_columns(self._x_tick_indices, len(self._values), plot_width)
            if show_x_ticks
            else []
        )
        rendered.append(
            build_plot_border_line(
                total_width=width,
                plot_offset=plot_offset,
                plot_width=plot_width,
                left_corner="└",
                right_corner="┘",
                tick_columns=plot_columns,
            ),
            AXIS_STYLE,
        )

        if show_x_ticks:
            rendered.append("\n")
            rendered.append(
                build_x_axis_labels_line(
                    total_width=width,
                    plot_offset=plot_offset,
                    plot_width=plot_width,
                    tick_columns=plot_columns,
                    tick_labels=self._x_tick_labels,
                ),
                AXIS_STYLE,
            )

        return rendered

    def _render_empty(self, width: int, height: int) -> Text:
        plot_height = max(height - 2, 1)
        plot_width = max(width - 2, 1)
        lines = [
            build_plot_border_line(
                total_width=width,
                plot_offset=1,
                plot_width=plot_width,
                left_corner="┌",
                right_corner="┐",
            )
        ]
        for row in range(plot_height):
            message = ""
            if self._empty_message and row == plot_height // 2:
                message = self._empty_message.center(plot_width)[:plot_width]
            lines.append(f"│{message.ljust(plot_width)}│")
        lines.append(
            build_plot_border_line(
                total_width=width,
                plot_offset=1,
                plot_width=plot_width,
                left_corner="└",
                right_corner="┘",
            )
        )
        rendered = Text()
        rendered.append(lines[0], AXIS_STYLE)
        for line in lines[1:-1]:
            rendered.append("\n")
            rendered.append("│", AXIS_STYLE)
            rendered.append(line[1:-1], "#7f8c8d")
            rendered.append("│", AXIS_STYLE)
        rendered.append("\n")
        rendered.append(lines[-1], AXIS_STYLE)
        return rendered
