"""
Coverage Badge Generator

Generates SVG badges for code coverage reports.
Usage: python scripts/generate_coverage_badge.py
"""

import json
import sys
from pathlib import Path


def get_coverage_percentage():
    """Extract coverage percentage from coverage.json or .coverage file."""
    coverage_file = Path("coverage.json")

    if not coverage_file.exists():
        print(
            "Error: coverage.json not found. Run 'coverage json' first.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        with open(coverage_file, "r") as f:
            coverage_data = json.load(f)

        # Get total coverage percentage
        total_coverage = coverage_data["totals"]["percent_covered_display"]
        return float(total_coverage)
    except (json.JSONDecodeError, KeyError, FileNotFoundError) as e:
        print(f"Error reading coverage data: {e}", file=sys.stderr)
        sys.exit(1)


def get_color(coverage):
    """Determine badge color based on coverage percentage."""
    if coverage >= 90:
        return "#4c1"  # bright green
    elif coverage >= 80:
        return "#97ca00"  # green
    elif coverage >= 70:
        return "#a4a61d"  # yellow-green
    elif coverage >= 60:
        return "#dfb317"  # yellow
    elif coverage >= 50:
        return "#fe7d37"  # orange
    else:
        return "#e05d44"  # red


def generate_badge_svg(coverage, color):
    coverage_text = f"{coverage:.0f}%"

    # Text widths (approx) and padding for nicer spacing
    left_label = "coverage"
    font_w = 6  # rough per-character width at 11px Verdana
    pad = 16
    left_width = min(70, len(left_label) * font_w + pad)
    right_width = min(38, len(coverage_text) * font_w + pad)

    total_width = left_width + right_width
    radius = 3

    # Build a single background path (left dark + right color) under one rounded clip
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="20" role="img" aria-label="coverage: {coverage_text}">
  <title>coverage: {coverage_text}</title>
  <defs>
    <clipPath id="r">
      <rect width="{total_width}" height="20" rx="{radius}" ry="{radius}"/>
    </clipPath>
  </defs>
  <g clip-path="url(#r)">
    <rect width="{left_width}" height="20" fill="#555"/>
    <rect x="{left_width}" width="{right_width}" height="20" fill="{color}"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
    <text x="{left_width/2:.1f}" y="14">{left_label}</text>
    <text x="{left_width + right_width/2:.1f}" y="14">{coverage_text}</text>
  </g>
</svg>"""
    return svg


def main():
    """Main function to generate coverage badge."""
    # Get coverage percentage
    coverage = get_coverage_percentage()

    # Get color based on coverage
    color = get_color(coverage)

    # Generate SVG badge
    badge_svg = generate_badge_svg(coverage, color)

    # Create badges directory if it doesn't exist
    badges_dir = Path("badges")
    badges_dir.mkdir(exist_ok=True)

    # Save badge
    badge_file = badges_dir / "coverage.svg"
    with open(badge_file, "w") as f:
        f.write(badge_svg)

    print(f"Coverage badge generated: {badge_file}")
    print(f"Coverage: {coverage:.0f}%")

    # Also generate markdown for README
    md_badge = f"[![Coverage](https://raw.githubusercontent.com/zydtiger/hyperliquid-cli/main/badges/coverage.svg)](https://github.com/zydtiger/hyperliquid-cli/actions/workflows/ci.yml)"
    print(f"\nMarkdown for README:")
    print(md_badge)


if __name__ == "__main__":
    main()
