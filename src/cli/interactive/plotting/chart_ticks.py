"""Axis helpers for Textual braille charts."""

from __future__ import annotations

import math
from collections.abc import Callable
from decimal import Decimal

DEFAULT_AXIS_TICK_COUNT = 5
DEFAULT_X_TICK_COUNT = 3


def build_y_axis_labels(
    min_value: Decimal,
    max_value: Decimal,
    height: int,
    formatter: Callable[[Decimal], str],
    max_ticks: int = DEFAULT_AXIS_TICK_COUNT,
) -> tuple[list[str], Decimal, Decimal]:
    """Build rounded y-axis tick labels and the scale they represent."""
    if height <= 0:
        return [], min_value, max_value

    axis_min, axis_max, ticks = _build_axis_ticks(min_value, max_value, max_ticks)
    label_width = max((len(formatter(tick)) for tick in ticks), default=0)
    labels = [" " * label_width for _ in range(height)]

    for tick in ticks:
        row = _tick_row_for_value(tick, axis_min, axis_max, height)
        labels[row] = formatter(tick).rjust(label_width)

    return labels, axis_min, axis_max


def build_plot_columns(indices: list[int], series_length: int, plot_width: int) -> list[int]:
    """Map series indices into rendered plot columns."""
    if not indices:
        return []
    if series_length <= 1:
        return [0 for _ in indices]
    return [round(index * (plot_width - 1) / (series_length - 1)) for index in indices]


def build_x_axis_labels_line(
    *,
    total_width: int,
    plot_offset: int,
    plot_width: int,
    tick_columns: list[int],
    tick_labels: list[str],
) -> str:
    """Lay out centered x-axis labels without overlapping adjacent ticks."""
    chars = [" "] * total_width
    last_end = -1

    for column, label in zip(tick_columns, tick_labels, strict=True):
        if not label:
            continue
        start = plot_offset + column - (len(label) // 2)
        start = max(start, plot_offset)
        start = min(start, max(plot_offset + plot_width - len(label), plot_offset))
        end = start + len(label) - 1
        if start <= last_end or end >= total_width:
            continue
        for index, char in enumerate(label):
            chars[start + index] = char
        last_end = end

    return "".join(chars)


def build_plot_border_line(
    *,
    total_width: int,
    plot_offset: int,
    plot_width: int,
    left_corner: str,
    right_corner: str,
    tick_columns: list[int] | None = None,
) -> str:
    """Build a horizontal plot border, optionally with x-axis tick marks."""
    chars = [" "] * total_width
    left_border = plot_offset - 1
    right_border = plot_offset + plot_width

    if 0 <= left_border < total_width:
        chars[left_border] = left_corner
    if 0 <= right_border < total_width:
        chars[right_border] = right_corner

    for column in range(plot_width):
        position = plot_offset + column
        if position >= total_width:
            break
        chars[position] = "─"

    for column in tick_columns or []:
        position = plot_offset + column
        if plot_offset <= position < min(plot_offset + plot_width, total_width):
            chars[position] = "┬"

    return "".join(chars)


def build_time_ticks(
    timestamps_ms: list[int],
    formatter: Callable[[int], str],
    max_ticks: int = DEFAULT_X_TICK_COUNT,
) -> tuple[list[int], list[str]]:
    """Build evenly spaced x-axis tick positions and labels for a time series."""
    indices = _build_evenly_spaced_indices(len(timestamps_ms), max_ticks)
    return indices, [formatter(timestamps_ms[index]) for index in indices]


def _build_evenly_spaced_indices(length: int, max_ticks: int) -> list[int]:
    """Return evenly spaced index positions including both ends where possible."""
    if length <= 0 or max_ticks <= 0:
        return []
    if length == 1 or max_ticks == 1:
        return [0]

    positions = {round(index * (length - 1) / (max_ticks - 1)) for index in range(max_ticks)}
    return sorted(positions)


def _build_axis_ticks(
    min_value: Decimal,
    max_value: Decimal,
    max_ticks: int,
) -> tuple[Decimal, Decimal, list[Decimal]]:
    """Round an axis range to visually stable tick marks."""
    if min_value == max_value or max_ticks <= 1:
        return min_value, max_value, [max_value]

    step = _nice_step((max_value - min_value) / Decimal(max(max_ticks - 1, 1)))
    axis_min = min_value
    axis_max = max_value

    while True:
        axis_min = Decimal(math.floor(float(min_value / step))) * step
        axis_max = Decimal(math.ceil(float(max_value / step))) * step
        tick_count = round(float((axis_max - axis_min) / step)) + 1
        if tick_count <= max_ticks:
            break
        step = _nice_step(step * Decimal("1.01"))

    ticks = [axis_max - (step * index) for index in range(tick_count)]
    return axis_min, axis_max, ticks


def _nice_step(raw_step: Decimal) -> Decimal:
    """Round a raw axis step up to a human-friendly interval."""
    raw = abs(float(raw_step))
    if raw == 0:
        return Decimal("1")

    exponent = math.floor(math.log10(raw))
    scale = Decimal(f"1e{exponent}")
    fraction = raw / (10**exponent)

    for candidate in (1, 2, 2.5, 5, 10):
        if fraction <= candidate:
            return Decimal(str(candidate)) * scale

    return Decimal("10") * scale


def _tick_row_for_value(
    tick: Decimal,
    axis_min: Decimal,
    axis_max: Decimal,
    height: int,
) -> int:
    """Map a y-axis tick value onto a rendered row."""
    if height <= 1 or axis_min == axis_max:
        return 0

    ratio = float((axis_max - tick) / (axis_max - axis_min))
    return round(ratio * (height - 1))
