"""
Tests for the backend /watch endpoint.
"""

from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from backend.exchange.hyperliquid_client import HyperliquidClient
from backend.service import create_app
from models.api import (
    DEFAULT_WATCH_INTERVAL,
    DEFAULT_WATCH_ORDER_BOOK_DEPTH,
    ExchangeError,
    OrderBookLevel,
    WatchCandle,
    WatchSnapshot,
)
from models.config import Config, HyperliquidConfig, NetworkType


def _sample_candle(open_time: int, close_time: int, close: str, *, is_closed: bool) -> WatchCandle:
    return WatchCandle(
        open_time=open_time,
        close_time=close_time,
        open=Decimal(close),
        high=Decimal(close),
        low=Decimal(close),
        close=Decimal(close),
        is_closed=is_closed,
    )


def mock_config() -> Config:
    """Create a mock configuration object for testing."""
    return Config(
        hyperliquid=HyperliquidConfig(
            account_address="0x1234567890123456789012345678901234567890",
            private_key="0x1234567890123456789012345678901234567890123456789012345678901234",
            network=NetworkType.MAINNET,
        )
    )


def mock_client() -> Mock:
    """Create a mock HyperliquidClient."""
    client = Mock(spec=HyperliquidClient)
    client.test_connection.return_value = True
    return client


def sample_watch_snapshot() -> WatchSnapshot:
    """Sample watch snapshot for the /watch endpoint."""
    return WatchSnapshot(
        coin="BTC",
        interval="5m",
        mark_price=Decimal("43250.50"),
        open_interest=Decimal("1250.75"),
        updated_at=1741973030493,
        candles=[
            _sample_candle(1741972500000, 1741972800000, "43210.25", is_closed=True),
            _sample_candle(1741972800000, 1741973100000, "43250.50", is_closed=False),
        ],
        bids=[
            OrderBookLevel(price=Decimal("43249.50"), size=Decimal("1.25")),
            OrderBookLevel(price=Decimal("43249.00"), size=Decimal("0.75")),
        ],
        asks=[
            OrderBookLevel(price=Decimal("43250.75"), size=Decimal("0.50")),
            OrderBookLevel(price=Decimal("43251.00"), size=Decimal("1.10")),
        ],
        order_book_depth=DEFAULT_WATCH_ORDER_BOOK_DEPTH,
        default_interval=DEFAULT_WATCH_INTERVAL,
    )


def test_watch_endpoint_success():
    """Test successful /watch/{coin} endpoint response."""
    client = mock_client()
    client.get_watch_snapshot.return_value = sample_watch_snapshot()
    config = mock_config()
    with patch("backend.service.HyperliquidClient", return_value=client):
        app = TestClient(create_app(config))
        response = app.get("/watch/BTC")

    assert response.status_code == 200
    assert response.json() == {
        "coin": "BTC",
        "interval": "5m",
        "mark_price": "43250.50",
        "open_interest": "1250.75",
        "updated_at": 1741973030493,
        "candles": [
            {
                "open_time": 1741972500000,
                "close_time": 1741972800000,
                "open": "43210.25",
                "high": "43210.25",
                "low": "43210.25",
                "close": "43210.25",
                "is_closed": True,
            },
            {
                "open_time": 1741972800000,
                "close_time": 1741973100000,
                "open": "43250.50",
                "high": "43250.50",
                "low": "43250.50",
                "close": "43250.50",
                "is_closed": False,
            },
        ],
        "bids": [
            {"price": "43249.50", "size": "1.25"},
            {"price": "43249.00", "size": "0.75"},
        ],
        "asks": [
            {"price": "43250.75", "size": "0.50"},
            {"price": "43251.00", "size": "1.10"},
        ],
        "order_book_depth": 10,
        "default_interval": "5m",
        "supported_intervals": ["1m", "5m", "15m", "1h", "4h", "1d"],
    }
    client.get_watch_snapshot.assert_called_once_with("BTC", "5m", 10)


def test_watch_endpoint_passes_interval_query():
    """The /watch endpoint should pass the requested interval to the client."""
    client = mock_client()
    client.get_watch_snapshot.return_value = sample_watch_snapshot()
    config = mock_config()
    with patch("backend.service.HyperliquidClient", return_value=client):
        app = TestClient(create_app(config))
        response = app.get("/watch/BTC", params={"interval": "1h"})

    assert response.status_code == 200
    client.get_watch_snapshot.assert_called_once_with("BTC", "1h", 10)


def test_watch_endpoint_passes_depth_query():
    """The /watch endpoint should pass the requested order book depth to the client."""
    client = mock_client()
    client.get_watch_snapshot.return_value = sample_watch_snapshot()
    config = mock_config()
    with patch("backend.service.HyperliquidClient", return_value=client):
        app = TestClient(create_app(config))
        response = app.get("/watch/BTC", params={"depth": 12})

    assert response.status_code == 200
    client.get_watch_snapshot.assert_called_once_with("BTC", "5m", 12)


def test_watch_endpoint_accepts_extended_interval_query():
    """The /watch endpoint should accept the newly supported higher intervals."""
    client = mock_client()
    client.get_watch_snapshot.return_value = sample_watch_snapshot()
    config = mock_config()
    with patch("backend.service.HyperliquidClient", return_value=client):
        app = TestClient(create_app(config))
        response = app.get("/watch/BTC", params={"interval": "1d"})

    assert response.status_code == 200
    client.get_watch_snapshot.assert_called_once_with("BTC", "1d", 10)


def test_watch_endpoint_exchange_error():
    """Test /watch/{coin} when the exchange layer rejects the market."""
    client = mock_client()
    client.get_watch_snapshot.side_effect = ExchangeError(
        "Coin 'INVALID/PAIR' not found in available trading pairs"
    )
    config = mock_config()
    with patch("backend.service.HyperliquidClient", return_value=client):
        app = TestClient(create_app(config))
        response = app.get("/watch/INVALID/PAIR")

    assert response.status_code == 400
    assert "not found" in response.json()["detail"]


def test_watch_endpoint_supports_spot_pairs():
    """Test successful /watch/{coin} for a spot pair."""
    client = mock_client()
    client.get_watch_snapshot.return_value = WatchSnapshot(
        coin="UBTC/USDC",
        interval="15m",
        mark_price=Decimal("101234.50"),
        open_interest=None,
        updated_at=1741973030493,
        candles=[_sample_candle(1741972500000, 1741973400000, "101200.25", is_closed=False)],
        bids=[OrderBookLevel(price=Decimal("101230.50"), size=Decimal("0.25"))],
        asks=[OrderBookLevel(price=Decimal("101235.75"), size=Decimal("0.10"))],
        order_book_depth=DEFAULT_WATCH_ORDER_BOOK_DEPTH,
        default_interval=DEFAULT_WATCH_INTERVAL,
    )
    config = mock_config()
    with patch("backend.service.HyperliquidClient", return_value=client):
        app = TestClient(create_app(config))
        response = app.get("/watch/UBTC/USDC")

    assert response.status_code == 200
    assert response.json()["coin"] == "UBTC/USDC"
    assert response.json()["open_interest"] is None
    client.get_watch_snapshot.assert_called_once_with("UBTC/USDC", "5m", 10)


def test_watch_endpoint_rejects_invalid_interval():
    """Invalid intervals should fail FastAPI validation before reaching the client."""
    client = mock_client()
    config = mock_config()
    with patch("backend.service.HyperliquidClient", return_value=client):
        app = TestClient(create_app(config))
        response = app.get("/watch/BTC", params={"interval": "2h"})

    assert response.status_code == 422
    client.get_watch_snapshot.assert_not_called()


@pytest.mark.parametrize("depth", [0, -1, 51])
def test_watch_endpoint_rejects_invalid_depth(depth: int):
    """Invalid depths should fail FastAPI validation before reaching the client."""
    client = mock_client()
    config = mock_config()
    with patch("backend.service.HyperliquidClient", return_value=client):
        app = TestClient(create_app(config))
        response = app.get("/watch/BTC", params={"depth": depth})

    assert response.status_code == 422
    client.get_watch_snapshot.assert_not_called()


def test_watch_endpoint_unexpected_error():
    """Test /watch/{coin} when an unexpected error occurs."""
    client = mock_client()
    client.get_watch_snapshot.side_effect = Exception("Network error")
    config = mock_config()
    with patch("backend.service.HyperliquidClient", return_value=client):
        app = TestClient(create_app(config))
        response = app.get("/watch/BTC")

    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error"


def test_backend_service_closes_client_on_shutdown():
    """The FastAPI shutdown hook should close the shared Hyperliquid client."""
    config = mock_config()
    client = Mock(spec=HyperliquidClient)
    client.test_connection.return_value = True

    with patch("backend.service.HyperliquidClient", return_value=client):
        with TestClient(create_app(config)) as app:
            response = app.get("/health")
            assert response.status_code == 200

    client.close.assert_called_once_with()
