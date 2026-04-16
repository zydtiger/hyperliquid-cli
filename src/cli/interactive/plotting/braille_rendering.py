"""Braille-grid rendering primitives for Textual charts."""

from __future__ import annotations

from decimal import Decimal
from itertools import pairwise

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


def render_braille_plot(
    values: list[Decimal],
    width: int,
    height: int,
    *,
    min_value: Decimal | None = None,
    max_value: Decimal | None = None,
) -> list[str]:
    """Render a line chart using Unicode braille cells."""
    if not values:
        return [" " * width for _ in range(height)]

    pixel_width = max(width * 2, 2)
    pixel_height = max(height * 4, 4)
    pixels = [[False for _ in range(pixel_width)] for _ in range(pixel_height)]
    points = _series_to_pixel_points(
        values,
        pixel_width,
        pixel_height,
        min_value=min_value,
        max_value=max_value,
    )

    for (x1, y1), (x2, y2) in pairwise(points):
        _draw_pixel_line(pixels, x1, y1, x2, y2)

    for x, y in points:
        pixels[y][x] = True

    return _pixels_to_braille_lines(pixels, width, height)


def _series_to_pixel_points(
    values: list[Decimal],
    pixel_width: int,
    pixel_height: int,
    *,
    min_value: Decimal | None = None,
    max_value: Decimal | None = None,
) -> list[tuple[int, int]]:
    """Map numeric values into the high-resolution braille grid."""
    if len(values) == 1:
        return [(0, pixel_height // 2)]

    lower_bound = min(values) if min_value is None else min_value
    upper_bound = max(values) if max_value is None else max_value
    span = upper_bound - lower_bound
    points: list[tuple[int, int]] = []

    for index, value in enumerate(values):
        x = round(index * (pixel_width - 1) / (len(values) - 1))
        if span == 0:
            y = pixel_height // 2
        else:
            normalized = (value - lower_bound) / span
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
