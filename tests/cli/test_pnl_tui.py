"""
Tests for the Textual fullscreen PnL TUI.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

from cli.interactive.plotting.braille_chart import BrailleChart
from cli.interactive.pnl_tui.pnl_helpers import format_pnl_date
from cli.interactive.pnl_tui.pnl_tui import PnlScreenControl, PnlTUI, format_money, window_label
from models.api import DEFAULT_PNL_WINDOW, PnlHistory, PnlHistoryCatalog, PnlPoint


def _sample_history() -> PnlHistoryCatalog:
    return PnlHistoryCatalog(
        default_window=DEFAULT_PNL_WINDOW,
        histories=[
            PnlHistory(
                window="1d",
                points=[
                    PnlPoint(
                        time=1741973030493,
                        total_pnl=Decimal("10.5"),
                        perp_pnl=Decimal("7.0"),
                        spot_pnl=Decimal("3.5"),
                    )
                ],
            ),
            PnlHistory(
                window="3d",
                points=[],
            ),
            PnlHistory(
                window="7d",
                points=[
                    PnlPoint(
                        time=1741886630493,
                        total_pnl=Decimal("0.0"),
                        perp_pnl=Decimal("0.0"),
                        spot_pnl=Decimal("0.0"),
                    ),
                    PnlPoint(
                        time=1741973030493,
                        total_pnl=Decimal("10.5"),
                        perp_pnl=Decimal("7.0"),
                        spot_pnl=Decimal("3.5"),
                    ),
                    PnlPoint(
                        time=1742059430493,
                        total_pnl=Decimal("6.0"),
                        perp_pnl=Decimal("8.5"),
                        spot_pnl=Decimal("-2.5"),
                    ),
                ],
            ),
        ],
    )


def _mixed_axis_width_history() -> PnlHistoryCatalog:
    return PnlHistoryCatalog(
        default_window="1d",
        histories=[
            PnlHistory(
                window="1d",
                points=[
                    PnlPoint(
                        time=1741886630493,
                        total_pnl=Decimal("200"),
                        perp_pnl=Decimal("25"),
                        spot_pnl=Decimal("-3"),
                    ),
                    PnlPoint(
                        time=1741973030493,
                        total_pnl=Decimal("10000"),
                        perp_pnl=Decimal("175"),
                        spot_pnl=Decimal("12"),
                    ),
                ],
            )
        ],
    )


def test_pnl_screen_control_formats_header_and_summary() -> None:
    """The PnL control should expose the active window title and latest totals."""
    control = PnlScreenControl(_sample_history())

    assert control.header_title() == "Hyperliquid PnL TUI - 7D"
    assert "Total $+6.00" in control.header_summary()
    assert "Perp $+8.50" in control.header_summary()
    assert "Spot $-2.50" in control.header_summary()


def test_pnl_screen_control_advances_between_windows() -> None:
    """The PnL control should clamp while switching the active window."""
    control = PnlScreenControl(_sample_history())

    assert control.current_window() == "7d"
    control.advance_window(-1)
    assert control.current_window() == "3d"
    control.advance_window(1)
    assert control.current_window() == "7d"
    control.advance_window(10)
    assert control.current_window() == "all"
    control.advance_window(-10)
    assert control.current_window() == "1d"


def test_pnl_textual_app_renders_y_ticks_and_shared_bottom_x_ticks() -> None:
    """The Textual PnL app should render inline axes and x ticks only on the spot chart."""

    async def scenario() -> None:
        tui = PnlTUI(_sample_history())
        app = tui._build_app()

        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            total_rendered = app.query_one("#total-plot", BrailleChart).render()
            perp_rendered = app.query_one("#perp-plot", BrailleChart).render()
            spot_rendered = app.query_one("#spot-plot", BrailleChart).render()
            total_plot = total_rendered.plain
            perp_plot = perp_rendered.plain
            spot_plot = spot_rendered.plain

            assert "$15.00" in total_plot
            assert "$10.00" in perp_plot
            assert "$4.00" in spot_plot
            assert "-$4.00" in spot_plot
            assert "┌" in total_plot
            assert "┐" in total_plot
            assert "┘" in spot_plot
            assert "┤" in total_plot
            assert "│" in total_plot
            assert "├" not in total_plot
            assert any(ord(char) >= 0x2800 for char in total_plot if char.strip())
            # Axis labels are rendered in local time, so derive them with the
            # same helper the chart uses rather than pinning one timezone.
            first_day = format_pnl_date(1741886630493)
            last_day = format_pnl_date(1742059430493)

            assert first_day not in total_plot
            assert last_day not in perp_plot
            assert "└" in total_plot
            assert "└" in perp_plot
            assert "┬" not in total_plot
            assert "┬" not in perp_plot
            assert "└" in spot_plot
            assert "┬" in spot_plot
            assert first_day in spot_plot
            assert last_day in spot_plot
            assert any("3b4261" in str(span.style) for span in total_rendered.spans)

    asyncio.run(scenario())


def test_pnl_textual_app_keeps_empty_window_message() -> None:
    """Empty ranges should keep a visible no-data summary in the active panel set."""

    async def scenario() -> None:
        tui = PnlTUI(_sample_history())
        tui.control.advance_window(-1)
        app = tui._build_app()

        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            summary = str(app.query_one("#total-summary").render())

            assert summary == "No PnL samples in this window"

    asyncio.run(scenario())


def test_pnl_textual_app_aligns_left_y_axes_for_mixed_currency_widths() -> None:
    """All PnL panels should share the same left-axis offset for mixed tick widths."""

    async def scenario() -> None:
        tui = PnlTUI(_mixed_axis_width_history())
        app = tui._build_app()

        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            total_lines = app.query_one("#total-plot", BrailleChart).render().plain.splitlines()
            perp_lines = app.query_one("#perp-plot", BrailleChart).render().plain.splitlines()
            spot_lines = app.query_one("#spot-plot", BrailleChart).render().plain.splitlines()

            offsets = {lines[0].index("┌") for lines in (total_lines, perp_lines, spot_lines)}

            assert offsets == {10}
            assert total_lines[1][:10].strip() == "$10,000.00"
            assert perp_lines[1][:10].strip() == "$200.00"
            assert spot_lines[1][:10].strip() == "$15.00"

    asyncio.run(scenario())


def test_window_label_and_money_helpers_are_stable() -> None:
    """Basic PnL formatting helpers should keep their current user-facing labels."""
    assert window_label("all") == "ALL-TIME"
    assert format_money(Decimal("10.5")) == "$+10.50"
