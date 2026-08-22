"""
Tests for the CLI backend API client helpers.
"""

from decimal import Decimal

import httpx

from cli.api import BackendAPI
from models.api import APIError
from models.config import Config, HyperliquidConfig, NetworkType


def _config() -> Config:
    return Config(
        hyperliquid=HyperliquidConfig(
            account_address="0x1234567890123456789012345678901234567890",
            private_key="0x1234567890123456789012345678901234567890123456789012345678901234",
            network=NetworkType.MAINNET,
        )
    )


def test_backend_api_get_watch_snapshot_parses_response() -> None:
    """The CLI API client should parse /watch responses into WatchSnapshot models."""
    api = BackendAPI.__new__(BackendAPI)
    api.base_url = "http://localhost:8080"
    seen_query = {}

    def handler(incoming: httpx.Request) -> httpx.Response:
        seen_query["interval"] = incoming.url.params.get("interval")
        seen_query["depth"] = incoming.url.params.get("depth")
        return httpx.Response(
            200,
            json={
                "coin": "BTC",
                "interval": "1h",
                "mark_price": "43250.50",
                "open_interest": "1250.75",
                "updated_at": 1741973030493,
                "candles": [
                    {
                        "open_time": 1741969200000,
                        "close_time": 1741972800000,
                        "open": "43000.00",
                        "high": "43300.00",
                        "low": "42950.00",
                        "close": "43210.25",
                        "is_closed": True,
                    },
                    {
                        "open_time": 1741972800000,
                        "close_time": 1741976400000,
                        "open": "43210.25",
                        "high": "43275.00",
                        "low": "43180.00",
                        "close": "43250.50",
                        "is_closed": False,
                    },
                ],
                "bids": [{"price": "43249.50", "size": "1.25"}],
                "asks": [{"price": "43250.75", "size": "0.50"}],
                "size_decimals": 5,
                "order_book_depth": 12,
                "default_interval": "5m",
                "supported_intervals": ["1m", "5m", "15m", "1h", "4h", "1d"],
            },
            request=incoming,
        )

    api.client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="http://localhost:8080",
    )

    snapshot = api.get_watch_snapshot("BTC", "1h", 12)

    assert snapshot.coin == "BTC"
    assert snapshot.interval == "1h"
    assert snapshot.mark_price == Decimal("43250.50")
    assert snapshot.open_interest == Decimal("1250.75")
    assert snapshot.candles[-1].close == Decimal("43250.50")
    assert snapshot.bids[0].price == Decimal("43249.50")
    assert snapshot.size_decimals == 5
    assert snapshot.order_book_depth == 12
    assert seen_query["interval"] == "1h"
    assert seen_query["depth"] == "12"
    api.client.close()


def test_backend_api_get_watch_snapshot_reports_missing_endpoint() -> None:
    """A missing /watch route should raise a restart-focused error."""
    api = BackendAPI.__new__(BackendAPI)
    api.base_url = "http://localhost:8080"
    api.client = httpx.Client(
        transport=httpx.MockTransport(
            lambda incoming: httpx.Response(
                404,
                json={"detail": "Not Found"},
                request=incoming,
            )
        ),
        base_url="http://localhost:8080",
    )

    try:
        api.get_watch_snapshot("BTC")
    except APIError as exc:
        assert exc.status_code == 404
        assert "Restart the backend" in exc.message
    else:
        raise AssertionError("Expected APIError for missing watch endpoint")
    finally:
        api.client.close()


def test_backend_api_get_watch_snapshot_parses_null_open_interest_for_spot() -> None:
    """Spot watch snapshots should preserve null open interest values from the backend."""
    api = BackendAPI.__new__(BackendAPI)
    api.base_url = "http://localhost:8080"
    api.client = httpx.Client(
        transport=httpx.MockTransport(
            lambda incoming: httpx.Response(
                200,
                json={
                    "coin": "UBTC/USDC",
                    "interval": "1h",
                    "mark_price": "101234.50",
                    "open_interest": None,
                    "updated_at": 1741973030493,
                    "candles": [],
                    "bids": [],
                    "asks": [],
                    "size_decimals": 5,
                    "order_book_depth": 10,
                    "default_interval": "5m",
                    "supported_intervals": ["1m", "5m", "15m", "1h", "4h", "1d"],
                },
                request=incoming,
            )
        ),
        base_url="http://localhost:8080",
    )

    try:
        snapshot = api.get_watch_snapshot("UBTC/USDC", "1h")
        assert snapshot.open_interest is None
        assert snapshot.size_decimals == 5
    finally:
        api.client.close()
