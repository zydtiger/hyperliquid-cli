"""
Table formatting utilities for CLI output.

This module provides utilities for formatting data in a clean tabular format
for display in the command-line interface.
"""

from typing import List, Any, Tuple
from decimal import Decimal
from .base import Formatter


class TableFormatter(Formatter[Tuple[List[str], List[List[Any]]]]):
    """
    Table formatter for displaying data in a clean tabular format.
    """

    def format(self, data: Tuple[List[str], List[List[Any]]], **kwargs) -> str:
        """
        Format data as a clean table.

        Args:
            data: Tuple of (headers, rows)
            **kwargs: Additional options including 'title'

        Returns:
            Formatted table string
        """
        headers, rows = data
        title = kwargs.get("title")

        if not rows:
            return "No data to display"

        # Convert all values to strings and handle None
        str_rows = []
        for row in rows:
            str_row = []
            for value in row:
                if value is None:
                    str_row.append("N/A")
                elif isinstance(value, Decimal):
                    str_row.append(f"{float(value):.6f}".rstrip("0").rstrip("."))
                else:
                    str_row.append(str(value))
            str_rows.append(str_row)

        # Calculate column widths
        all_rows = [headers] + str_rows
        col_widths = []
        for col_idx in range(len(headers)):
            max_width = max(len(row[col_idx]) for row in all_rows)
            col_widths.append(max_width)

        # Build the table
        lines = []

        # Add title if provided
        if title:
            lines.append(f"\n{title}")
            lines.append("=" * len(title))

        # Add headers
        header_line = " | ".join(
            headers[i].ljust(col_widths[i]) for i in range(len(headers))
        )
        lines.append(header_line)

        # Add separator
        separator = "-+-".join("-" * col_widths[i] for i in range(len(headers)))
        lines.append(separator)

        # Add data rows
        for row in str_rows:
            row_line = " | ".join(row[i].ljust(col_widths[i]) for i in range(len(row)))
            lines.append(row_line)

        return "\n".join(lines)
