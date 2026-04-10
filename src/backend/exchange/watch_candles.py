"""
Helpers for building and maintaining watch candles.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from models.api import WATCH_INTERVAL_MS, OrderBookLevel, WatchCandle, WatchInterval

HISTORICAL_CANDLE_COUNT = 49
WATCH_CANDLE_COUNT = HISTORICAL_CANDLE_COUNT + 1
SNAPSHOT_LOOKBACK_CANDLES = WATCH_CANDLE_COUNT + 10
ORDER_BOOK_DEPTH = 10


@dataclass(slots=True)
class IntervalState:
    candles: deque[WatchCandle] = field(default_factory=lambda: deque(maxlen=WATCH_CANDLE_COUNT))


def seed_interval_state(
    raw_candles: Any,
    interval: WatchInterval,
    mark_price: Decimal,
    now_ms: int,
) -> IntervalState:
    """Build a new interval state from historical candles plus one live candle."""
    current_open_time = interval_open_time(now_ms, interval)
    parsed = parse_snapshot_candles(raw_candles, interval)
    historical = [candle for candle in parsed if candle.open_time < current_open_time]
    current_seed = next(
        (candle for candle in reversed(parsed) if candle.open_time == current_open_time),
        None,
    )
    candles = deque(historical[-HISTORICAL_CANDLE_COUNT:], maxlen=WATCH_CANDLE_COUNT)
    candles.append(seed_live_candle(interval, current_open_time, mark_price, current_seed))
    return IntervalState(candles=candles)


def advance_interval_state(
    interval_state: IntervalState,
    interval: WatchInterval,
    price: Decimal,
    timestamp_ms: int,
) -> None:
    """Roll an interval forward and keep the active candle live."""
    current_open_time = interval_open_time(timestamp_ms, interval)
    if not interval_state.candles:
        interval_state.candles.append(
            build_candle(interval, current_open_time, price, price, price, price, False)
        )
        return

    interval_ms = WATCH_INTERVAL_MS[interval]
    while interval_state.candles[-1].open_time < current_open_time:
        previous = interval_state.candles.pop()
        interval_state.candles.append(close_candle(previous))
        next_open_time = previous.open_time + interval_ms
        while next_open_time < current_open_time:
            flat_price = interval_state.candles[-1].close
            interval_state.candles.append(
                build_candle(
                    interval,
                    next_open_time,
                    flat_price,
                    flat_price,
                    flat_price,
                    flat_price,
                    True,
                )
            )
            next_open_time += interval_ms
        interval_state.candles.append(
            build_candle(interval, current_open_time, price, price, price, price, False)
        )

    latest = interval_state.candles.pop()
    interval_state.candles.append(
        build_candle(
            interval,
            latest.open_time,
            latest.open,
            max(latest.high, price),
            min(latest.low, price),
            price,
            False,
        )
    )


def parse_snapshot_candles(raw_candles: Any, interval: WatchInterval) -> list[WatchCandle]:
    """Normalize raw candle snapshot entries into ordered watch candles."""
    if not isinstance(raw_candles, list):
        return []

    candles: list[WatchCandle] = []
    interval_ms = WATCH_INTERVAL_MS[interval]
    for entry in raw_candles:
        if not isinstance(entry, dict):
            continue
        try:
            open_time = int(entry["t"])
            close_time = int(entry.get("T", open_time + interval_ms))
            candles.append(
                WatchCandle(
                    open_time=open_time,
                    close_time=close_time,
                    open=Decimal(str(entry["o"])),
                    high=Decimal(str(entry["h"])),
                    low=Decimal(str(entry["l"])),
                    close=Decimal(str(entry["c"])),
                    is_closed=True,
                )
            )
        except (ArithmeticError, KeyError, TypeError, ValueError):
            continue
    candles.sort(key=lambda candle: candle.open_time)
    return candles


def seed_live_candle(
    interval: WatchInterval,
    open_time: int,
    mark_price: Decimal,
    seed: WatchCandle | None,
) -> WatchCandle:
    """Create the live candle for the current interval bucket."""
    if seed is None:
        return build_candle(
            interval, open_time, mark_price, mark_price, mark_price, mark_price, False
        )
    return build_candle(
        interval,
        open_time,
        seed.open,
        max(seed.high, mark_price),
        min(seed.low, mark_price),
        mark_price,
        False,
    )


def build_candle(
    interval: WatchInterval,
    open_time: int,
    open_price: Decimal,
    high: Decimal,
    low: Decimal,
    close: Decimal,
    is_closed: bool,
) -> WatchCandle:
    """Construct a watch candle with normalized close time."""
    return WatchCandle(
        open_time=open_time,
        close_time=open_time + WATCH_INTERVAL_MS[interval],
        open=open_price,
        high=high,
        low=low,
        close=close,
        is_closed=is_closed,
    )


def close_candle(candle: WatchCandle) -> WatchCandle:
    """Return a closed copy of a candle."""
    return WatchCandle(
        open_time=candle.open_time,
        close_time=candle.close_time,
        open=candle.open,
        high=candle.high,
        low=candle.low,
        close=candle.close,
        is_closed=True,
    )


def interval_open_time(timestamp_ms: int, interval: WatchInterval) -> int:
    """Return the bucket start time for an interval."""
    interval_ms = WATCH_INTERVAL_MS[interval]
    return timestamp_ms - (timestamp_ms % interval_ms)


def parse_l2_book(book: Any) -> tuple[list[OrderBookLevel], list[OrderBookLevel]]:
    """Normalize bids and asks from an L2 snapshot or update."""
    levels = book.get("levels", [[], []])
    raw_bids = levels[0] if len(levels) > 0 else []
    raw_asks = levels[1] if len(levels) > 1 else []
    return parse_levels(raw_bids, descending=True), parse_levels(raw_asks, descending=False)


def parse_levels(levels: list[dict[str, Any]], descending: bool) -> list[OrderBookLevel]:
    """Normalize and sort one side of the order book."""
    parsed = [
        OrderBookLevel(price=Decimal(str(level["px"])), size=Decimal(str(level["sz"])))
        for level in levels
    ]
    parsed.sort(key=lambda level: level.price, reverse=descending)
    return parsed[:ORDER_BOOK_DEPTH]


__all__ = [
    "HISTORICAL_CANDLE_COUNT",
    "SNAPSHOT_LOOKBACK_CANDLES",
    "WATCH_CANDLE_COUNT",
    "IntervalState",
    "advance_interval_state",
    "interval_open_time",
    "parse_l2_book",
    "seed_interval_state",
]
