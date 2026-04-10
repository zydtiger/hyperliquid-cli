"""
Live watch snapshot registry backed by Hyperliquid websocket subscriptions.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from decimal import Decimal
from threading import Lock
from time import time
from typing import Any

from models.api import (
    DEFAULT_WATCH_WINDOW,
    WATCH_WINDOW_ORDER,
    OrderBookLevel,
    PriceSample,
    Ticker,
    WatchSnapshot,
)

ORDER_BOOK_DEPTH = 10
PRICE_SAMPLE_INTERVAL_MS = 1_000
PRICE_HISTORY_RETENTION_MS = 60 * 60_000


@dataclass(slots=True)
class _WatchState:
    coin: str
    mark_price: Decimal
    open_interest: Decimal
    updated_at: int
    price_history: deque[PriceSample] = field(default_factory=deque)
    bids: list[OrderBookLevel] = field(default_factory=list)
    asks: list[OrderBookLevel] = field(default_factory=list)
    asset_ctx_subscription_id: int | None = None
    l2_book_subscription_id: int | None = None


class LiveWatchRegistry:
    """Maintain live in-memory watch snapshots keyed by coin."""

    def __init__(
        self,
        info: Any,
        ticker_fetcher: Callable[[str], Ticker],
        clock_ms: Callable[[], int] | None = None,
    ) -> None:
        self._info = info
        self._ticker_fetcher = ticker_fetcher
        self._clock_ms = clock_ms or _current_time_ms
        self._lock = Lock()
        self._states: dict[str, _WatchState] = {}

    def get_snapshot(self, coin: str) -> WatchSnapshot:
        """Return the current watch snapshot, creating subscriptions on first access."""
        state = self._ensure_state(coin)
        with self._lock:
            return WatchSnapshot(
                coin=state.coin,
                mark_price=state.mark_price,
                open_interest=state.open_interest,
                updated_at=state.updated_at,
                price_history=list(state.price_history),
                bids=list(state.bids),
                asks=list(state.asks),
                default_window=DEFAULT_WATCH_WINDOW,
                supported_windows=list(WATCH_WINDOW_ORDER),
            )

    def close(self) -> None:
        """Unsubscribe active coin watchers when the backend shuts down."""
        with self._lock:
            states = list(self._states.values())
            self._states.clear()

        for state in states:
            if state.asset_ctx_subscription_id is not None:
                self._unsubscribe({"type": "activeAssetCtx", "coin": state.coin}, state)
            if state.l2_book_subscription_id is not None:
                self._unsubscribe({"type": "l2Book", "coin": state.coin}, state)

    def _ensure_state(self, coin: str) -> _WatchState:
        with self._lock:
            existing = self._states.get(coin)
            if existing is not None:
                return existing

        seeded = self._seed_state(coin)
        with self._lock:
            existing = self._states.setdefault(coin, seeded)
            if existing is not seeded:
                return existing

        self._subscribe(seeded)
        return seeded

    def _seed_state(self, coin: str) -> _WatchState:
        ticker = self._ticker_fetcher(coin)
        book = self._info.l2_snapshot(coin)
        now_ms = self._clock_ms()
        bids, asks = _parse_l2_book(book)
        state = _WatchState(
            coin=coin,
            mark_price=ticker.mark_price,
            open_interest=ticker.open_interest,
            updated_at=now_ms,
            bids=bids,
            asks=asks,
        )
        _append_price_sample(state.price_history, ticker.mark_price, now_ms)
        return state

    def _subscribe(self, state: _WatchState) -> None:
        asset_ctx_subscription = {"type": "activeAssetCtx", "coin": state.coin}
        l2_book_subscription = {"type": "l2Book", "coin": state.coin}
        asset_ctx_id = self._info.subscribe(
            asset_ctx_subscription,
            lambda message: self._handle_asset_ctx(state.coin, message),
        )
        l2_book_id = self._info.subscribe(
            l2_book_subscription,
            lambda message: self._handle_l2_book(state.coin, message),
        )

        with self._lock:
            current = self._states.get(state.coin)
            if current is None:
                return
            current.asset_ctx_subscription_id = asset_ctx_id
            current.l2_book_subscription_id = l2_book_id

    def _handle_asset_ctx(self, coin: str, message: Any) -> None:
        ctx = message["data"]["ctx"]
        mark_price = Decimal(str(ctx["markPx"]))
        updated_at = self._clock_ms()

        with self._lock:
            state = self._states.get(coin)
            if state is None:
                return
            state.mark_price = mark_price
            if "openInterest" in ctx:
                state.open_interest = Decimal(str(ctx["openInterest"]))
            state.updated_at = updated_at
            _append_price_sample(state.price_history, mark_price, updated_at)

    def _handle_l2_book(self, coin: str, message: Any) -> None:
        bids, asks = _parse_l2_book(message["data"])
        updated_at = int(message["data"].get("time", self._clock_ms()))

        with self._lock:
            state = self._states.get(coin)
            if state is None:
                return
            state.bids = bids
            state.asks = asks
            state.updated_at = updated_at

    def _unsubscribe(self, subscription: dict[str, str], state: _WatchState) -> None:
        subscription_id = (
            state.asset_ctx_subscription_id
            if subscription["type"] == "activeAssetCtx"
            else state.l2_book_subscription_id
        )
        if subscription_id is None:
            return

        with suppress(Exception):
            self._info.unsubscribe(subscription, subscription_id)


def _append_price_sample(
    history: deque[PriceSample],
    price: Decimal,
    timestamp_ms: int,
) -> None:
    bucket_time = timestamp_ms - (timestamp_ms % PRICE_SAMPLE_INTERVAL_MS)
    sample = PriceSample(time=bucket_time, price=price)
    if history and history[-1].time == bucket_time:
        history[-1] = sample
    else:
        history.append(sample)

    cutoff = bucket_time - PRICE_HISTORY_RETENTION_MS
    while history and history[0].time < cutoff:
        history.popleft()


def _parse_l2_book(book: Any) -> tuple[list[OrderBookLevel], list[OrderBookLevel]]:
    levels = book.get("levels", [[], []])
    raw_bids = levels[0] if len(levels) > 0 else []
    raw_asks = levels[1] if len(levels) > 1 else []
    bids = _parse_levels(raw_bids, descending=True)
    asks = _parse_levels(raw_asks, descending=False)
    return bids, asks


def _parse_levels(levels: list[dict[str, Any]], descending: bool) -> list[OrderBookLevel]:
    parsed = [
        OrderBookLevel(
            price=Decimal(str(level["px"])),
            size=Decimal(str(level["sz"])),
        )
        for level in levels
    ]
    parsed.sort(key=lambda level: level.price, reverse=descending)
    return parsed[:ORDER_BOOK_DEPTH]


def _current_time_ms() -> int:
    return int(time() * 1000)


__all__ = ["LiveWatchRegistry"]
