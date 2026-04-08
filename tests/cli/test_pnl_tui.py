"""
Tests for the fullscreen PnL TUI renderer.
"""

from decimal import Decimal

from cli.interactive.pnl_tui import PnlScreenControl, render_braille_plot
from models.api import PnlHistory, PnlPoint


def _sample_history() -> PnlHistory:
    return PnlHistory(
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

    assert "Hyperliquid PnL 7D TUI" in rendered
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
