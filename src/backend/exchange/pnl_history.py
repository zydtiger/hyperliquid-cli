"""
Helpers for parsing Hyperliquid portfolio PnL history.
"""

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from models.api import (
    DEFAULT_PNL_WINDOW,
    PNL_WINDOW_ORDER,
    PnlHistory,
    PnlHistoryCatalog,
    PnlPoint,
    PnlWindow,
)

MIN_BUCKET_ENTRY_ITEMS = 2
MIN_PNL_SAMPLE_ITEMS = 2
DAY_MS = 24 * 60 * 60 * 1000
PnlSample = tuple[int, Decimal]

TOTAL_BUCKET_BY_WINDOW: dict[PnlWindow, str] = {
    "1d": "day",
    "3d": "week",
    "7d": "week",
    "1m": "month",
    "3m": "allTime",
    "6m": "allTime",
    "1y": "allTime",
    "all": "allTime",
}
PERP_BUCKET_BY_WINDOW: dict[PnlWindow, str] = {
    "1d": "perpDay",
    "3d": "perpWeek",
    "7d": "perpWeek",
    "1m": "perpMonth",
    "3m": "perpAllTime",
    "6m": "perpAllTime",
    "1y": "perpAllTime",
    "all": "perpAllTime",
}
DURATION_MS_BY_WINDOW: dict[PnlWindow, int | None] = {
    "1d": 1 * DAY_MS,
    "3d": 3 * DAY_MS,
    "7d": 7 * DAY_MS,
    "1m": 30 * DAY_MS,
    "3m": 90 * DAY_MS,
    "6m": 180 * DAY_MS,
    "1y": 365 * DAY_MS,
    "all": None,
}


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

        try:
            samples.append((int(sample[0]), Decimal(str(sample[1]))))
        except (ArithmeticError, TypeError, ValueError):
            continue

    samples.sort(key=lambda item: item[0])
    return samples


def _filter_samples_by_duration(
    samples: list[PnlSample], duration_ms: int | None
) -> list[PnlSample]:
    """Filter samples to a trailing time window while preserving order."""
    if not samples or duration_ms is None:
        return list(samples)

    latest_time = samples[-1][0]
    earliest_time = latest_time - duration_ms
    return [sample for sample in samples if sample[0] >= earliest_time]


def _build_history(
    window: PnlWindow, total_samples: list[PnlSample], perp_samples: list[PnlSample]
) -> PnlHistory:
    """Build a single PnL history window from aligned sample sets."""
    if not total_samples:
        return PnlHistory(window=window, points=[])

    points: list[PnlPoint] = []
    perp_index = 0
    latest_perp = Decimal("0")

    for timestamp, total_pnl in total_samples:
        while perp_index < len(perp_samples) and perp_samples[perp_index][0] <= timestamp:
            latest_perp = perp_samples[perp_index][1]
            perp_index += 1

        points.append(
            PnlPoint(
                time=timestamp,
                total_pnl=total_pnl,
                perp_pnl=latest_perp,
                spot_pnl=total_pnl - latest_perp,
            )
        )

    return PnlHistory(window=window, points=points)


def build_pnl_history_catalog(portfolio_data: Any) -> PnlHistoryCatalog:
    """Build all supported PnL history windows from one portfolio response."""
    bucket_map = _coerce_bucket_map(portfolio_data)
    parsed_total_buckets = {
        bucket_name: _parse_pnl_samples(bucket_map.get(bucket_name))
        for bucket_name in set(TOTAL_BUCKET_BY_WINDOW.values())
    }
    parsed_perp_buckets = {
        bucket_name: _parse_pnl_samples(bucket_map.get(bucket_name))
        for bucket_name in set(PERP_BUCKET_BY_WINDOW.values())
    }

    histories: list[PnlHistory] = []
    for window in PNL_WINDOW_ORDER:
        duration_ms = DURATION_MS_BY_WINDOW[window]
        total_bucket = parsed_total_buckets[TOTAL_BUCKET_BY_WINDOW[window]]
        perp_bucket = parsed_perp_buckets[PERP_BUCKET_BY_WINDOW[window]]
        histories.append(
            _build_history(
                window,
                _filter_samples_by_duration(total_bucket, duration_ms),
                _filter_samples_by_duration(perp_bucket, duration_ms),
            )
        )

    return PnlHistoryCatalog(default_window=DEFAULT_PNL_WINDOW, histories=histories)
