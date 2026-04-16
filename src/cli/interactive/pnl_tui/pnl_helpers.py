"""
Formatting helpers for the fullscreen PnL TUI.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from models.api import PnlPoint


def format_money(value: Decimal) -> str:
    """Format summary currency values with an explicit sign."""
    return f"${value:+,.2f}"


def format_axis_money(value: Decimal) -> str:
    """Format y-axis tick labels without forcing a leading plus sign."""
    if value < 0:
        return f"-${abs(value):,.2f}"
    return f"${value:,.2f}"


def format_pnl_date(timestamp_ms: int) -> str:
    """Format a PnL timestamp in local time for the shared x-axis."""
    return datetime.fromtimestamp(timestamp_ms / 1000).strftime("%m-%d")


def summary_line(active_label: str, latest: PnlPoint | None) -> str:
    """Build the current PnL summary banner."""
    if latest is None:
        return f" {active_label}  no data in selected window "

    return (
        f" {active_label}   Total {format_money(latest.total_pnl)}   "
        f"Perp {format_money(latest.perp_pnl)}   "
        f"Spot {format_money(latest.spot_pnl)} "
    )


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


__all__ = [
    "format_axis_money",
    "format_money",
    "format_pnl_date",
    "summary_line",
    "window_label",
]
