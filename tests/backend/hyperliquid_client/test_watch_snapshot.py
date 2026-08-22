"""
Tests for the live watch snapshot registry and client method.
"""

from collections.abc import Callable
from decimal import Decimal
from unittest.mock import Mock

from backend.exchange.watch_snapshot import LiveWatchRegistry
from models.api import (
    DEFAULT_WATCH_ORDER_BOOK_DEPTH,
    MAX_WATCH_ORDER_BOOK_DEPTH,
    Ticker,
    WatchSnapshot,
)


def _raw_candle(
    open_time: int,
    interval_ms: int,
    open_price: str,
    high: str,
    low: str,
    close: str,
) -> dict[str, str | int]:
    return {
        "t": open_time,
        "T": open_time + interval_ms,
        "o": open_price,
        "h": high,
        "l": low,
        "c": close,
    }


def test_watch_registry_builds_seeded_snapshot_from_ticker_l2_book_and_candles():
    """The first snapshot should seed from REST ticker data, L2 data, and candle history."""
    info = Mock()
    info.l2_snapshot.return_value = {
        "time": 1_234_567,
        "levels": [
            [{"px": "99", "sz": "2"}, {"px": "98", "sz": "1"}],
            [{"px": "101", "sz": "3"}, {"px": "102", "sz": "4"}],
        ],
    }
    info.candles_snapshot.return_value = [
        _raw_candle(900_000, 300_000, "95", "101", "94", "100"),
        _raw_candle(1_200_000, 300_000, "100", "103", "99", "101"),
    ]
    callbacks: dict[str, Callable[..., None]] = {}

    def subscribe(subscription, callback):
        callbacks[subscription["type"]] = callback
        return len(callbacks)

    info.subscribe.side_effect = subscribe
    ticker_fetcher = Mock(
        return_value=Ticker(
            coin="BTC",
            mark_price=Decimal("101"),
            funding_rate=Decimal("0.001"),
            open_interest=Decimal("1234"),
        )
    )
    registry = LiveWatchRegistry(info, ticker_fetcher, clock_ms=lambda: 1_234_567)

    snapshot = registry.get_snapshot("BTC", "5m")

    assert snapshot.coin == "BTC"
    assert snapshot.interval == "5m"
    assert snapshot.mark_price == Decimal("101")
    assert snapshot.open_interest == Decimal("1234")
    assert len(snapshot.candles) == 2
    assert snapshot.candles[0].is_closed is True
    assert snapshot.candles[-1].open_time == 1_200_000
    assert snapshot.candles[-1].is_closed is False
    assert [level.price for level in snapshot.bids] == [Decimal("99"), Decimal("98")]
    assert [level.price for level in snapshot.asks] == [Decimal("101"), Decimal("102")]
    assert snapshot.order_book_depth == DEFAULT_WATCH_ORDER_BOOK_DEPTH
    assert set(callbacks) == {"activeAssetCtx", "l2Book"}


def test_watch_registry_updates_live_candle_ohlc_from_active_asset_ctx():
    """Active asset context updates should keep the current candle dynamic."""
    info = Mock()
    info.l2_snapshot.return_value = {"time": 1_000, "levels": [[], []]}
    info.candles_snapshot.return_value = [_raw_candle(0, 300_000, "99", "100", "98", "100")]
    callbacks: dict[str, Callable[..., None]] = {}

    def subscribe(subscription, callback):
        callbacks[subscription["type"]] = callback
        return len(callbacks)

    info.subscribe.side_effect = subscribe
    now = {"value": 310_000}
    registry = LiveWatchRegistry(
        info,
        lambda coin: Ticker(
            coin=coin,
            mark_price=Decimal("101"),
            funding_rate=Decimal("0"),
            open_interest=Decimal("10"),
        ),
        clock_ms=lambda: now["value"],
    )
    registry.get_snapshot("BTC", "5m")

    now["value"] = 320_000
    callbacks["activeAssetCtx"]({"data": {"ctx": {"markPx": "105", "openInterest": "12"}}})
    now["value"] = 330_000
    callbacks["activeAssetCtx"]({"data": {"ctx": {"markPx": "97", "openInterest": "13"}}})

    snapshot = registry.get_snapshot("BTC", "5m")
    live = snapshot.candles[-1]

    assert snapshot.open_interest == Decimal("1261")
    assert live.open_time == 300_000
    assert live.open == Decimal("101")
    assert live.high == Decimal("105")
    assert live.low == Decimal("97")
    assert live.close == Decimal("97")
    assert live.is_closed is False


def test_watch_registry_rolls_candles_forward_when_interval_changes():
    """A new bucket should close the previous live candle and append the next live candle."""
    info = Mock()
    info.l2_snapshot.return_value = {"time": 1_000, "levels": [[], []]}
    info.candles_snapshot.return_value = [_raw_candle(0, 60_000, "99", "100", "98", "100")]
    callbacks: dict[str, Callable[..., None]] = {}

    def subscribe(subscription, callback):
        callbacks[subscription["type"]] = callback
        return len(callbacks)

    info.subscribe.side_effect = subscribe
    now = {"value": 70_000}
    registry = LiveWatchRegistry(
        info,
        lambda coin: Ticker(
            coin=coin,
            mark_price=Decimal("101"),
            funding_rate=Decimal("0"),
            open_interest=Decimal("10"),
        ),
        clock_ms=lambda: now["value"],
    )
    registry.get_snapshot("BTC", "1m")

    now["value"] = 125_000
    callbacks["activeAssetCtx"]({"data": {"ctx": {"markPx": "103", "openInterest": "11"}}})

    snapshot = registry.get_snapshot("BTC", "1m")

    assert [candle.open_time for candle in snapshot.candles] == [0, 60_000, 120_000]
    assert snapshot.candles[-2].is_closed is True
    assert snapshot.candles[-2].close == Decimal("101")
    assert snapshot.candles[-1].is_closed is False
    assert snapshot.candles[-1].open == Decimal("103")
    assert snapshot.candles[-1].close == Decimal("103")


def test_watch_registry_truncates_to_99_historical_candles_plus_live_candle():
    """Snapshots should include 99 completed candles plus one live candle."""
    info = Mock()
    info.l2_snapshot.return_value = {"time": 1_000, "levels": [[], []]}
    interval_ms = 300_000
    info.candles_snapshot.return_value = [
        _raw_candle(index * interval_ms, interval_ms, "100", "101", "99", "100")
        for index in range(120)
    ]
    callbacks: dict[str, Callable[..., None]] = {}

    def subscribe(subscription, callback):
        callbacks[subscription["type"]] = callback
        return len(callbacks)

    info.subscribe.side_effect = subscribe
    registry = LiveWatchRegistry(
        info,
        lambda coin: Ticker(
            coin=coin,
            mark_price=Decimal("111"),
            funding_rate=Decimal("0"),
            open_interest=Decimal("10"),
        ),
        clock_ms=lambda: 36_300_000,
    )

    snapshot = registry.get_snapshot("BTC", "5m")

    assert len(snapshot.candles) == 100
    assert all(candle.is_closed for candle in snapshot.candles[:-1])
    assert snapshot.candles[-1].is_closed is False


def test_watch_registry_returns_requested_order_book_depth():
    """Snapshots should return only the requested number of levels per side."""
    info = Mock()
    info.l2_snapshot.return_value = {
        "time": 1_000,
        "levels": [
            [{"px": str(100 - index), "sz": "1"} for index in range(20)],
            [{"px": str(101 + index), "sz": "1"} for index in range(20)],
        ],
    }
    info.candles_snapshot.return_value = []
    info.subscribe.side_effect = lambda subscription, callback: 1
    registry = LiveWatchRegistry(
        info,
        lambda coin: Ticker(
            coin=coin,
            mark_price=Decimal("101"),
            funding_rate=Decimal("0"),
            open_interest=Decimal("10"),
        ),
        clock_ms=lambda: 1_000,
    )

    snapshot = registry.get_snapshot("BTC", "5m", 12)

    assert len(snapshot.bids) == 12
    assert len(snapshot.asks) == 12
    assert snapshot.order_book_depth == 12
    assert snapshot.bids[0].price == Decimal("100")
    assert snapshot.asks[0].price == Decimal("101")


def test_watch_registry_caps_stored_order_book_depth_to_maximum():
    """Snapshots should never store or return more than the configured maximum depth."""
    info = Mock()
    info.l2_snapshot.return_value = {
        "time": 1_000,
        "levels": [
            [{"px": str(100 - index), "sz": "1"} for index in range(80)],
            [{"px": str(101 + index), "sz": "1"} for index in range(80)],
        ],
    }
    info.candles_snapshot.return_value = []
    info.subscribe.side_effect = lambda subscription, callback: 1
    registry = LiveWatchRegistry(
        info,
        lambda coin: Ticker(
            coin=coin,
            mark_price=Decimal("101"),
            funding_rate=Decimal("0"),
            open_interest=Decimal("10"),
        ),
        clock_ms=lambda: 1_000,
    )

    snapshot = registry.get_snapshot("BTC", "5m", MAX_WATCH_ORDER_BOOK_DEPTH + 10)

    assert len(snapshot.bids) == MAX_WATCH_ORDER_BOOK_DEPTH
    assert len(snapshot.asks) == MAX_WATCH_ORDER_BOOK_DEPTH
    assert snapshot.order_book_depth == MAX_WATCH_ORDER_BOOK_DEPTH


def test_get_watch_snapshot_supports_spot_markets(
    client,
    mock_connection,
    mock_retry_operation,
):
    """Spot pairs should route through the shared watch registry."""
    mock_connection.info.meta.return_value = {"universe": [{"name": "BTC"}]}
    mock_connection.info.spot_meta.return_value = {
        "universe": [{"tokens": [441, 360], "name": "@441", "index": 441, "isCanonical": True}],
        "tokens": [{}] * 442,
    }
    mock_connection.info.spot_meta.return_value["tokens"][360] = {
        "name": "USDC",
        "szDecimals": 6,
        "weiDecimals": 6,
        "index": 360,
    }
    mock_connection.info.spot_meta.return_value["tokens"][441] = {
        "name": "UBTC",
        "szDecimals": 5,
        "weiDecimals": 8,
        "index": 441,
    }
    mock_connection.retry_operation.side_effect = mock_retry_operation
    expected = WatchSnapshot(
        coin="UBTC/USDC",
        interval="5m",
        mark_price=Decimal("100"),
        open_interest=None,
        updated_at=1_000,
        candles=[],
        bids=[],
        asks=[],
        size_decimals=5,
        order_book_depth=DEFAULT_WATCH_ORDER_BOOK_DEPTH,
    )
    client._watch_registry = Mock()
    client._watch_registry.get_snapshot.return_value = expected.model_copy(
        update={"size_decimals": 0}
    )

    result = client.get_watch_snapshot("UBTC/USDC")

    assert result == expected
    client._watch_registry.get_snapshot.assert_called_once_with("UBTC/USDC", "5m", 10)


def test_get_watch_snapshot_returns_registry_snapshot(
    client,
    mock_connection,
    mock_retry_operation,
):
    """The client should delegate watch snapshots through the shared registry."""
    mock_connection.info.meta.return_value = {
        "universe": [{"name": "BTC", "maxLeverage": 50, "szDecimals": 5}]
    }
    mock_connection.info.spot_meta.return_value = {"universe": [], "tokens": []}
    mock_connection.retry_operation.side_effect = mock_retry_operation
    expected = WatchSnapshot(
        coin="BTC",
        interval="5m",
        mark_price=Decimal("100"),
        open_interest=Decimal("10"),
        updated_at=1_000,
        candles=[],
        bids=[],
        asks=[],
        size_decimals=5,
        order_book_depth=DEFAULT_WATCH_ORDER_BOOK_DEPTH,
    )
    client._watch_registry = Mock()
    client._watch_registry.get_snapshot.return_value = expected.model_copy(
        update={"size_decimals": 0}
    )

    result = client.get_watch_snapshot("BTC")

    assert result == expected
    client._watch_registry.get_snapshot.assert_called_once_with("BTC", "5m", 10)


def test_get_watch_snapshot_passes_requested_interval(
    client,
    mock_connection,
    mock_retry_operation,
):
    """The client should forward custom watch intervals to the registry."""
    mock_connection.info.meta.return_value = {
        "universe": [{"name": "BTC", "maxLeverage": 50, "szDecimals": 5}]
    }
    mock_connection.retry_operation.side_effect = mock_retry_operation
    client._watch_registry = Mock()
    client._watch_registry.get_snapshot.return_value = WatchSnapshot(
        coin="BTC",
        interval="1h",
        mark_price=Decimal("100"),
        open_interest=Decimal("10"),
        updated_at=1_000,
        candles=[],
        bids=[],
        asks=[],
        order_book_depth=12,
    )

    result = client.get_watch_snapshot("BTC", "1h", 12)

    assert result.size_decimals == 5
    client._watch_registry.get_snapshot.assert_called_once_with("BTC", "1h", 12)


def test_watch_registry_exposes_extended_supported_intervals():
    """Snapshots should advertise the full watch interval list, including 4h and 1d."""
    info = Mock()
    info.l2_snapshot.return_value = {"time": 1_000, "levels": [[], []]}
    info.candles_snapshot.return_value = []
    info.subscribe.side_effect = lambda subscription, callback: 1
    registry = LiveWatchRegistry(
        info,
        lambda coin: Ticker(
            coin=coin,
            mark_price=Decimal("101"),
            funding_rate=Decimal("0"),
            open_interest=Decimal("10"),
        ),
        clock_ms=lambda: 1_000,
    )

    snapshot = registry.get_snapshot("BTC", "1d")

    assert snapshot.interval == "1d"
    assert snapshot.supported_intervals == ["1m", "5m", "15m", "1h", "4h", "1d"]


def test_watch_registry_keeps_spot_open_interest_as_none_on_asset_updates():
    """Spot watch snapshots should keep open interest unset when asset updates omit it."""
    info = Mock()
    info.l2_snapshot.return_value = {"time": 1_000, "levels": [[], []]}
    info.candles_snapshot.return_value = []
    callbacks: dict[str, Callable[..., None]] = {}

    def subscribe(subscription, callback):
        callbacks[subscription["type"]] = callback
        return len(callbacks)

    info.subscribe.side_effect = subscribe
    now = {"value": 1_000}
    registry = LiveWatchRegistry(
        info,
        lambda coin: Ticker(
            coin=coin,
            mark_price=Decimal("101"),
            funding_rate=Decimal("0"),
            open_interest=None,
        ),
        clock_ms=lambda: now["value"],
    )

    registry.get_snapshot("UBTC/USDC", "5m")
    now["value"] = 2_000
    callbacks["activeAssetCtx"]({"data": {"ctx": {"markPx": "105"}}})

    snapshot = registry.get_snapshot("UBTC/USDC", "5m")

    assert snapshot.open_interest is None
