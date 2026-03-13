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
    # Shields canonical look (flat with subtle gloss)
    height = 20
    radius = 3
    label = "coverage"
    value = f"{coverage:.0f}%"

    # Estimate text widths for DejaVu Sans 11px (approx)
    def text_len_px(s: str) -> int:
        return int(round(len(s) * 6.5))

    # Padding roughly matching shields
    label_pad_left, label_pad_right = 6, 4
    value_pad_left, value_pad_right = 5, 12

    label_text_w = text_len_px(label)
    value_text_w = text_len_px(value)

    left_w = label_pad_left + label_text_w + label_pad_right
    right_w = value_pad_left + value_text_w + value_pad_right
    total_w = left_w + right_w

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="{height}" role="img" aria-label="{label}: {value}">
  <title>{label}: {value}</title>
  <defs>
    <!-- Subtle vertical gloss gradient applied over entire badge -->
    <linearGradient id="b" x2="0" y2="100%">
      <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
      <stop offset="1" stop-opacity=".1"/>
    </linearGradient>
    <clipPath id="r">
      <rect width="{total_w}" height="{height}" rx="{radius}" ry="{radius}"/>
    </clipPath>
  </defs>

  <g clip-path="url(#r)">
    <!-- Left label background -->
    <rect width="{left_w}" height="{height}" fill="#555"/>
    <!-- Right value background -->
    <rect x="{left_w}" width="{right_w}" height="{height}" fill="{color}"/>
    <!-- Gloss overlay across full width so it covers BOTH sides -->
    <rect width="{total_w}" height="{height}" fill="url(#b)"/>
  </g>

  <!-- Text with shields-like faux shadow -->
  <g font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11" text-anchor="start">
    <!-- Label shadow + text -->
    <text x="{label_pad_left + 1}" y="15" fill="#010101" fill-opacity=".3">{label}</text>
    <text x="{label_pad_left + 1}" y="14" fill="#fff">{label}</text>
    <!-- Value shadow + text -->
    <text x="{left_w + value_pad_left}" y="15" fill="#010101" fill-opacity=".3">{value}</text>
    <text x="{left_w + value_pad_left}" y="14" fill="#fff">{value}</text>
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
    md_badge = "[![Coverage](https://raw.githubusercontent.com/zydtiger/hyperliquid-cli/main/badges/coverage.svg)](https://github.com/zydtiger/hyperliquid-cli/actions/workflows/ci.yml)"
    print("\nMarkdown for README:")
    print(md_badge)


if __name__ == "__main__":
    main()
