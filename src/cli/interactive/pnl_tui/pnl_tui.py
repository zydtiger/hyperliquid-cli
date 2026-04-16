"""Textual fullscreen PnL UI."""

from __future__ import annotations

from decimal import Decimal
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.widgets import Static

from models.api import PNL_WINDOW_ORDER, PnlHistory, PnlHistoryCatalog, PnlWindow

from ..plotting import BrailleChart, build_time_ticks
from .pnl_helpers import (
    format_axis_money,
    format_money,
    format_pnl_date,
    summary_line,
    window_label,
)

PANEL_SPECS = (("total", "Total PnL"), ("perp", "Perp PnL"), ("spot", "Spot PnL"))


class PnlScreenControl:
    """State and formatting helpers for the Textual PnL app."""

    def __init__(self, history_catalog: PnlHistoryCatalog):
        self.history_by_window = {history.window: history for history in history_catalog.histories}
        default_window = history_catalog.default_window
        self.current_window_index = (
            PNL_WINDOW_ORDER.index(default_window) if default_window in PNL_WINDOW_ORDER else 0
        )

    def advance_window(self, delta: int) -> None:
        next_index = self.current_window_index + delta
        self.current_window_index = min(max(next_index, 0), len(PNL_WINDOW_ORDER) - 1)

    def current_window(self) -> PnlWindow:
        return PNL_WINDOW_ORDER[self.current_window_index]

    def current_history(self) -> PnlHistory:
        window = self.current_window()
        return self.history_by_window.get(window, PnlHistory(window=window, points=[]))

    def header_title(self) -> str:
        return f"Hyperliquid PnL TUI - {window_label(self.current_window())}"

    def header_summary(self) -> str:
        history = self.current_history()
        latest = history.points[-1] if history.points else None
        return summary_line(window_label(history.window), latest)

    def panel_values(self) -> dict[str, list[Decimal]]:
        history = self.current_history()
        return {
            "total": [point.total_pnl for point in history.points],
            "perp": [point.perp_pnl for point in history.points],
            "spot": [point.spot_pnl for point in history.points],
        }

    def panel_times(self) -> list[int]:
        return [point.time for point in self.current_history().points]


class PnlApp(App[None]):
    """Textual app that renders the multi-window PnL charts."""

    CSS = """
    Screen { layout: vertical; background: #101418; color: #d7dadc; }
    #header { padding: 0 1; color: #8be9fd; text-style: bold; }
    .summary { padding: 0 1; color: #f8f8f2; }
    .footer { padding: 0 1; color: #7f8c8d; }
    .plot-panel { height: 1fr; layout: vertical; padding: 0 1; }
    .panel-title { height: auto; padding: 0 1; color: #f8f8f2; text-style: bold; }
    .panel-summary { height: auto; padding: 0 1; color: #7aa2f7; }
    BrailleChart { height: 1fr; min-height: 8; }
    """
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "quit_view", show=False),
        Binding("escape", "quit_view", show=False),
        Binding("enter", "quit_view", show=False),
        Binding("ctrl+c", "quit_view", show=False),
        Binding("+", "zoom_in", show=False),
        Binding("=", "zoom_in", show=False),
        Binding("-", "zoom_out", show=False),
        Binding("_", "zoom_out", show=False),
    ]

    def __init__(self, tui: PnlTUI):
        super().__init__()
        self.tui = tui

    def compose(self) -> ComposeResult:
        yield Static("", id="header")
        yield Static("", classes="summary", id="header-summary")
        yield Static("+ zoom in  - zoom out  q / Esc / Enter / Ctrl-C exit", classes="footer")
        for panel_id, title in PANEL_SPECS:
            with Vertical(classes="plot-panel", id=f"{panel_id}-panel"):
                yield Static(title, classes="panel-title", id=f"{panel_id}-title")
                yield Static("", classes="panel-summary", id=f"{panel_id}-summary")
                yield BrailleChart(
                    widget_id=f"{panel_id}-plot",
                    y_label_formatter=format_axis_money,
                    line_style=self._line_style(panel_id),
                    show_x_ticks=panel_id == "spot",
                )
        yield Static("Perp and spot use independent y-scales per active window", classes="footer")

    def on_mount(self) -> None:
        self._refresh_view()

    def action_quit_view(self) -> None:
        self.exit()

    def action_zoom_in(self) -> None:
        self.tui.control.advance_window(-1)
        self._refresh_view()

    def action_zoom_out(self) -> None:
        self.tui.control.advance_window(1)
        self._refresh_view()

    def _refresh_view(self) -> None:
        control = self.tui.control
        self.query_one("#header", Static).update(control.header_title())
        self.query_one("#header-summary", Static).update(control.header_summary())
        panel_values = control.panel_values()
        timestamps = control.panel_times()
        x_tick_indices, x_tick_labels = (
            build_time_ticks(timestamps, format_pnl_date) if timestamps else ([], [])
        )
        for panel_id, title in PANEL_SPECS:
            values = panel_values[panel_id]
            self.query_one(f"#{panel_id}-title", Static).update(title)
            self.query_one(f"#{panel_id}-summary", Static).update(self._panel_summary(values))
            self.query_one(f"#{panel_id}-plot", BrailleChart).set_data(
                values,
                x_tick_indices=x_tick_indices,
                x_tick_labels=x_tick_labels,
                empty_message="No PnL samples in this window",
            )

    def _panel_summary(self, values: list[Decimal]) -> str:
        if not values:
            return "No PnL samples in this window"
        return (
            f"last {format_money(values[-1])}   "
            f"max {format_money(max(values))}   "
            f"min {format_money(min(values))}"
        )

    def _line_style(self, panel_id: str) -> str:
        return {"total": "#50fa7b", "perp": "#ffb86c", "spot": "#bd93f9"}[panel_id]


class PnlTUI:
    """Launch the Textual fullscreen PnL history view."""

    def __init__(self, history_catalog: PnlHistoryCatalog):
        self.control = PnlScreenControl(history_catalog)

    def run(self) -> None:
        self._build_app().run()

    def _build_app(self) -> PnlApp:
        return PnlApp(self)
