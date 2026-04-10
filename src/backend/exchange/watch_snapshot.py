"""
Live watch snapshot registry backed by Hyperliquid websocket subscriptions.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from decimal import Decimal
from threading import Lock
from time import time
from typing import Any

from models.api import (
    DEFAULT_WATCH_INTERVAL,
    WATCH_INTERVAL_MS,
    WATCH_INTERVAL_ORDER,
    OrderBookLevel,
    Ticker,
    WatchInterval,
    WatchSnapshot,
)

from .watch_candles import (
    SNAPSHOT_LOOKBACK_CANDLES,
    IntervalState,
    advance_interval_state,
    interval_open_time,
    parse_l2_book,
    seed_interval_state,
)

ACTIVE_ASSET_CTX_TYPE = "activeAssetCtx"
L2_BOOK_TYPE = "l2Book"


def _perp_open_interest_value(mark_price: Decimal, open_interest: Any) -> Decimal:
    """Convert perp open interest from base units into USD notional."""
    return mark_price * Decimal(str(open_interest))


@dataclass(slots=True)
class _WatchState:
    coin: str
    mark_price: Decimal
    open_interest: Decimal | None
    updated_at: int
    interval_states: dict[WatchInterval, IntervalState] = field(default_factory=dict)
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

    def get_snapshot(
        self,
        coin: str,
        interval: WatchInterval = DEFAULT_WATCH_INTERVAL,
    ) -> WatchSnapshot:
        """Return the current watch snapshot, creating subscriptions on first access."""
        state = self._ensure_state(coin)
        self._ensure_interval_state(state.coin, interval)
        now_ms = self._clock_ms()
        with self._lock:
            current = self._states[state.coin]
            interval_state = current.interval_states[interval]
            advance_interval_state(interval_state, interval, current.mark_price, now_ms)
            return WatchSnapshot(
                coin=current.coin,
                interval=interval,
                mark_price=current.mark_price,
                open_interest=current.open_interest,
                updated_at=current.updated_at,
                candles=list(interval_state.candles),
                bids=list(current.bids),
                asks=list(current.asks),
                default_interval=DEFAULT_WATCH_INTERVAL,
                supported_intervals=list(WATCH_INTERVAL_ORDER),
            )

    def close(self) -> None:
        """Unsubscribe active coin watchers when the backend shuts down."""
        with self._lock:
            states = list(self._states.values())
            self._states.clear()

        for state in states:
            if state.asset_ctx_subscription_id is not None:
                self._unsubscribe({"type": ACTIVE_ASSET_CTX_TYPE, "coin": state.coin}, state)
            if state.l2_book_subscription_id is not None:
                self._unsubscribe({"type": L2_BOOK_TYPE, "coin": state.coin}, state)

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

    def _ensure_interval_state(self, coin: str, interval: WatchInterval) -> None:
        with self._lock:
            state = self._states[coin]
            if interval in state.interval_states:
                return
            mark_price = state.mark_price

        now_ms = self._clock_ms()
        current_open_time = interval_open_time(now_ms, interval)
        start_time = current_open_time - (SNAPSHOT_LOOKBACK_CANDLES * WATCH_INTERVAL_MS[interval])
        raw_candles = self._info.candles_snapshot(coin, interval, start_time, now_ms)
        seeded = seed_interval_state(raw_candles, interval, mark_price, now_ms)

        with self._lock:
            state = self._states.get(coin)
            if state is None:
                return
            interval_state = state.interval_states.setdefault(interval, seeded)
            advance_interval_state(interval_state, interval, state.mark_price, self._clock_ms())

    def _seed_state(self, coin: str) -> _WatchState:
        ticker = self._ticker_fetcher(coin)
        book = self._info.l2_snapshot(coin)
        now_ms = self._clock_ms()
        bids, asks = parse_l2_book(book)
        return _WatchState(
            coin=coin,
            mark_price=ticker.mark_price,
            open_interest=ticker.open_interest,
            updated_at=now_ms,
            bids=bids,
            asks=asks,
        )

    def _subscribe(self, state: _WatchState) -> None:
        asset_ctx_subscription = {"type": ACTIVE_ASSET_CTX_TYPE, "coin": state.coin}
        l2_book_subscription = {"type": L2_BOOK_TYPE, "coin": state.coin}
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
                state.open_interest = _perp_open_interest_value(mark_price, ctx["openInterest"])
            state.updated_at = updated_at
            for interval, interval_state in state.interval_states.items():
                advance_interval_state(interval_state, interval, mark_price, updated_at)

    def _handle_l2_book(self, coin: str, message: Any) -> None:
        bids, asks = parse_l2_book(message["data"])
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
            if subscription["type"] == ACTIVE_ASSET_CTX_TYPE
            else state.l2_book_subscription_id
        )
        if subscription_id is None:
            return
        with suppress(Exception):
            self._info.unsubscribe(subscription, subscription_id)


def _current_time_ms() -> int:
    return int(time() * 1000)


__all__ = ["LiveWatchRegistry"]
