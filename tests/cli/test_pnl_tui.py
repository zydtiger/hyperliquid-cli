"""
Tests for the fullscreen PnL TUI renderer.
"""

from datetime import datetime
from decimal import Decimal

from cli.interactive.pnl_tui import PnlScreenControl, render_braille_plot, window_label
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


def test_render_braille_plot_uses_braille_glyphs():
    """The plot renderer should emit non-ASCII braille glyphs for chart lines."""
    lines = render_braille_plot(
        [Decimal("0.0"), Decimal("10.5"), Decimal("6.0")],
        width=20,
        height=6,
    )

    rendered = "".join(lines)
    assert len(lines) == 6
    assert any(ord(char) >= 0x2800 for char in rendered if char.strip())


def test_pnl_screen_control_renders_panel_titles():
    """The screen control should render all panel labels into the content."""
    control = PnlScreenControl(_sample_history())
    content = control.create_content(width=80, height=30)
    lines = ["".join(fragment for _, fragment in content.get_line(index)) for index in range(30)]
    rendered = "\n".join(lines)

    assert "Hyperliquid PnL TUI - 7D" in rendered
    assert "Total PnL" in rendered
    assert "Perp PnL" in rendered
    assert "Spot PnL" in rendered


def test_pnl_screen_control_keeps_panel_borders_aligned():
    """Panel borders should span exactly the requested width with intact corners."""
    width = 80
    control = PnlScreenControl(_sample_history())
    content = control.create_content(width=width, height=30)
    lines = ["".join(fragment for _, fragment in content.get_line(index)) for index in range(30)]

    panel_border_lines = [line for line in lines if line.startswith("┌") or line.startswith("└")]
    assert panel_border_lines
    assert all(len(line) == width for line in panel_border_lines)
    assert all(line.endswith("┐") for line in panel_border_lines if line.startswith("┌"))
    assert all(line.endswith("┘") for line in panel_border_lines if line.startswith("└"))


def test_pnl_screen_control_advances_between_windows():
    """The control should clamp and update the active range while rendering."""
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


def test_pnl_screen_control_renders_empty_window_message():
    """Selecting an empty range should keep the TUI alive with an empty-state panel."""
    control = PnlScreenControl(_sample_history())
    control.advance_window(-1)
    content = control.create_content(width=80, height=30)
    lines = ["".join(fragment for _, fragment in content.get_line(index)) for index in range(30)]
    rendered = "\n".join(lines)

    assert "Hyperliquid PnL TUI - 3D" in rendered
    assert "No PnL samples in this window" in rendered


def test_window_label_maps_all_time():
    """The window label helper should expose the expected display names."""
    assert window_label("all") == "ALL-TIME"


def test_pnl_screen_control_renders_zoom_controls():
    """The controls line should describe zooming in and out."""
    control = PnlScreenControl(_sample_history())
    content = control.create_content(width=80, height=30)
    controls_line = "".join(fragment for _, fragment in content.get_line(2))

    assert "+ zoom in" in controls_line
    assert "- zoom out" in controls_line


def test_pnl_screen_control_keeps_footer_visible_on_short_terminal():
    """Shorter terminals should still show complete panels and both footer lines."""
    control = PnlScreenControl(_sample_history())
    content = control.create_content(width=40, height=20)
    lines = ["".join(fragment for _, fragment in content.get_line(index)) for index in range(20)]

    assert content.line_count == 20
    assert lines[-2].strip().startswith("03-13")
    assert "y-scales" in lines[-1]
    assert lines[-1].strip()


def test_pnl_screen_control_formats_dates_in_local_time():
    """The PnL x-axis formatter should use local time rather than UTC."""
    control = PnlScreenControl(_sample_history())
    timestamp_ms = 1741973030493

    assert control._format_date(timestamp_ms) == datetime.fromtimestamp(
        timestamp_ms / 1000
    ).strftime("%m-%d")
