"""
Helpers for parsing Hyperliquid portfolio PnL history.
"""

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from models.api import PnlHistory, PnlPoint

TOTAL_PNL_BUCKET = "week"
PERP_PNL_BUCKET = "perpWeek"
MIN_BUCKET_ENTRY_ITEMS = 2
MIN_PNL_SAMPLE_ITEMS = 2
PnlSample = tuple[int, Decimal]


def _coerce_bucket_map(portfolio_data: Any) -> dict[str, Mapping[str, Any]]:
    """Normalize the exchange portfolio payload into a bucket map."""
    if not isinstance(portfolio_data, Sequence):
        return {}

    bucket_map: dict[str, Mapping[str, Any]] = {}
    for entry in portfolio_data:
        if (
            isinstance(entry, Sequence)
            and len(entry) >= MIN_BUCKET_ENTRY_ITEMS
            and isinstance(entry[0], str)
            and isinstance(entry[1], Mapping)
        ):
            bucket_map[entry[0]] = entry[1]
    return bucket_map


def _parse_pnl_samples(bucket: Mapping[str, Any] | None) -> list[PnlSample]:
    """Extract and sort `(timestamp, pnl)` pairs from a bucket."""
    if not isinstance(bucket, Mapping):
        return []

    raw_history = bucket.get("pnlHistory", [])
    if not isinstance(raw_history, Sequence):
        return []

    samples: list[PnlSample] = []
    for sample in raw_history:
        if not isinstance(sample, Sequence) or len(sample) < MIN_PNL_SAMPLE_ITEMS:
            continue
        timestamp = sample[0]
        value = sample[1]
        try:
            samples.append((int(timestamp), Decimal(str(value))))
        except (ArithmeticError, TypeError, ValueError):
            continue

    samples.sort(key=lambda item: item[0])
    return samples


def build_pnl_history(portfolio_data: Any) -> PnlHistory:
    """Build the 7-day total/perp/spot PnL history from portfolio data."""
    bucket_map = _coerce_bucket_map(portfolio_data)
    total_samples = _parse_pnl_samples(bucket_map.get(TOTAL_PNL_BUCKET))
    if not total_samples:
        return PnlHistory(window="7d", points=[])

    perp_samples = _parse_pnl_samples(bucket_map.get(PERP_PNL_BUCKET))
    points: list[PnlPoint] = []
    perp_index = 0
    latest_perp = Decimal("0")

    for timestamp, total_pnl in total_samples:
        while perp_index < len(perp_samples) and perp_samples[perp_index][0] <= timestamp:
            latest_perp = perp_samples[perp_index][1]
            perp_index += 1

        spot_pnl = total_pnl - latest_perp
        points.append(
            PnlPoint(
                time=timestamp,
                total_pnl=total_pnl,
                perp_pnl=latest_perp,
                spot_pnl=spot_pnl,
            )
        )

    return PnlHistory(window="7d", points=points)
