"""Textual widget for single-series braille charts."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from rich.text import Text
from textual.widget import Widget

from .braille_rendering import render_braille_plot
from .chart_ticks import (
    build_plot_columns,
    build_x_axis_line,
    build_y_axis_labels,
)


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
        plot_height = max(height - (1 if show_x_ticks else 0), 1)
        axis_labels, axis_min, axis_max = build_y_axis_labels(
            min(self._values),
            max(self._values),
            plot_height,
            self._y_label_formatter,
        )
        axis_width = len(axis_labels[0]) if axis_labels else 0
        axis_width = min(axis_width, max(width - 2, 0))
        plot_width = max(width - axis_width - (1 if axis_width else 0), 1)
        trimmed_axis_labels = [label[-axis_width:] if axis_width else "" for label in axis_labels]
        plot_lines = render_braille_plot(
            self._values,
            plot_width,
            plot_height,
            min_value=axis_min,
            max_value=axis_max,
        )

        rendered = Text()
        for row, plot_line in enumerate(plot_lines):
            if axis_width:
                rendered.append(trimmed_axis_labels[row].rjust(axis_width), "#7aa2f7")
                rendered.append(" ", "#7aa2f7")
            rendered.append(plot_line.ljust(plot_width), self._line_style)
            if row < len(plot_lines) - 1 or show_x_ticks:
                rendered.append("\n")

        if show_x_ticks:
            plot_columns = build_plot_columns(self._x_tick_indices, len(self._values), plot_width)
            rendered.append(
                build_x_axis_line(
                    total_width=width,
                    plot_offset=axis_width + (1 if axis_width else 0),
                    plot_width=plot_width,
                    tick_columns=plot_columns,
                    tick_labels=self._x_tick_labels,
                ),
                "#7aa2f7",
            )

        return rendered

    def _render_empty(self, width: int, height: int) -> Text:
        lines = [" " * width for _ in range(height)]
        if lines and self._empty_message:
            row = len(lines) // 2
            lines[row] = self._empty_message.center(width)[:width].ljust(width)
        return Text("\n".join(lines), style="#7f8c8d")
