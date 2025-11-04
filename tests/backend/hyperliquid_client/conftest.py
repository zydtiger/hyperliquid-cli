"""
Shared fixtures and utilities for HyperliquidClient tests.

This module provides comprehensive fixtures and utilities that are shared
across all test modules in the hyperliquid_client test package.
"""

import pytest
from decimal import Decimal
from unittest.mock import Mock
from typing import List, Dict, Any, Callable

from backend.exchange.hyperliquid_client import HyperliquidClient
from backend.exchange.hyperliquid_connection import HyperliquidConnection
from models.api import (
    Ticker,
    CoinMetadata,
    ExchangeError,
    LeverageType,
    PositionInfo,
)
from models.order import (
    MarketOrder,
    LimitOrder,
    OrderInfo,
    OrderResult,
    OrderSide,
    OrderType,
    OrderStatus,
    OrderTif,
)
from models.config import Config, HyperliquidConfig, NetworkType, TradingConfig


@pytest.fixture
def mock_config() -> Config:
    """Create a mock configuration object for testing."""
    hyperliquid_config = HyperliquidConfig(
        account_address="0x1234567890123456789012345678901234567890",
        private_key="0x1234567890123456789012345678901234567890123456789012345678901234",
        network=NetworkType.MAINNET,
    )
    return Config(hyperliquid=hyperliquid_config)


@pytest.fixture
def mock_config_with_slippage() -> Config:
    """Create a mock configuration with slippage setting."""
    hyperliquid_config = HyperliquidConfig(
        account_address="0x1234567890123456789012345678901234567890",
        private_key="0x1234567890123456789012345678901234567890123456789012345678901234",
        network=NetworkType.MAINNET,
    )
    trading_config = TradingConfig(default_slippage=Decimal("0.01"))  # 1% slippage
    return Config(hyperliquid=hyperliquid_config, trading=trading_config)


@pytest.fixture
def mock_connection() -> Mock:
    """Create a mock HyperliquidConnection."""
    connection = Mock(spec=HyperliquidConnection)
    connection.info = Mock()
    connection.exchange = Mock()
    return connection


@pytest.fixture
def mock_retry_operation() -> Callable:
    """Mock retry_operation that executes the function."""

    def mock_retry_operation(func):
        return func()

    return mock_retry_operation


@pytest.fixture
def client(mock_config: Config, mock_connection: Mock) -> HyperliquidClient:
    """Create a HyperliquidClient instance with mocked dependencies."""
    from unittest.mock import patch

    with patch(
        "backend.exchange.hyperliquid_client.HyperliquidConnection",
        return_value=mock_connection,
    ):
        return HyperliquidClient(mock_config)


@pytest.fixture
def sample_meta_response() -> Dict[str, Any]:
    """Sample response from meta API."""
    return {
        "universe": [
            {"name": "BTC", "szDecimals": 8, "maxLeverage": 50},
            {"name": "ETH", "szDecimals": 6, "maxLeverage": 25},
            {"name": "SOL", "szDecimals": 4, "maxLeverage": 20},
        ]
    }


@pytest.fixture
def sample_asset_ctxs_response() -> List[Dict[str, Any]]:
    """Sample response from asset contexts API."""
    return [
        {
            "markPx": "50000.0",
            "funding": "0.0001",
            "openInterest": "1000.0",
        },
        {
            "markPx": "3000.0",
            "funding": "-0.0002",
            "openInterest": "5000.0",
        },
        {
            "markPx": "100.0",
            "funding": "0.0003",
            "openInterest": "2000.0",
        },
    ]


@pytest.fixture
def sample_user_state_response() -> Dict[str, Any]:
    """Sample response from user state API."""
    return {
        "assetPositions": [
            {
                "type": "oneWay",
                "position": {
                    "coin": "ETH",
                    "szi": "0.003",
                    "leverage": {
                        "type": "isolated",
                        "value": 25,
                        "rawUsd": "-11.080576",
                    },
                    "entryPx": "3845.9",
                    "positionValue": "11.4921",
                    "unrealizedPnl": "-0.0456",
                    "returnOnEquity": "-0.0988065212",
                    "liquidationPx": "3768.9034013605",
                    "marginUsed": "0.411524",
                    "maxLeverage": 25,
                    "cumFunding": {
                        "allTime": "87.082076",
                        "sinceOpen": "0.0",
                        "sinceChange": "0.0",
                    },
                },
            },
            {
                "type": "oneWay",
                "position": {
                    "coin": "BTC",
                    "szi": "0.001",
                    "leverage": {
                        "type": "cross",
                        "value": 10,
                        "rawUsd": "50.0",
                    },
                    "entryPx": "49000.0",
                    "positionValue": "49.0",
                    "unrealizedPnl": "1.0",
                    "returnOnEquity": "0.0204081632",
                    "liquidationPx": "44100.0",
                    "marginUsed": "4.9",
                    "maxLeverage": 50,
                    "cumFunding": {
                        "allTime": "120.5",
                        "sinceOpen": "0.5",
                        "sinceChange": "0.1",
                    },
                },
            },
            # Zero-sized position should be ignored
            {
                "type": "oneWay",
                "position": {
                    "coin": "SOL",
                    "szi": "0.0",
                    "leverage": {
                        "type": "isolated",
                        "value": 20,
                        "rawUsd": "0.0",
                    },
                    "entryPx": "100.0",
                    "positionValue": "0.0",
                    "unrealizedPnl": "0.0",
                    "returnOnEquity": "0.0",
                    "liquidationPx": "80.0",
                    "marginUsed": "0.0",
                    "maxLeverage": 20,
                    "cumFunding": {
                        "allTime": "0.0",
                        "sinceOpen": "0.0",
                        "sinceChange": "0.0",
                    },
                },
            },
        ],
    }


# Order fixtures for order submission tests
@pytest.fixture
def sample_market_buy_order() -> MarketOrder:
    """Sample market buy order for testing."""
    return MarketOrder(
        coin="ETH", side=OrderSide.BUY, quantity=Decimal("0.1"), reduce_only=False
    )


@pytest.fixture
def sample_market_sell_order() -> MarketOrder:
    """Sample market sell order for testing."""
    return MarketOrder(
        coin="BTC", side=OrderSide.SELL, quantity=Decimal("0.05"), reduce_only=False
    )


@pytest.fixture
def sample_market_buy_order_reduce_only() -> MarketOrder:
    """Sample market buy order with reduce_only for testing."""
    return MarketOrder(
        coin="ETH", side=OrderSide.BUY, quantity=Decimal("0.1"), reduce_only=True
    )


@pytest.fixture
def sample_market_sell_order_reduce_only() -> MarketOrder:
    """Sample market sell order with reduce_only for testing."""
    return MarketOrder(
        coin="BTC", side=OrderSide.SELL, quantity=Decimal("0.05"), reduce_only=True
    )


@pytest.fixture
def sample_limit_buy_order() -> LimitOrder:
    """Sample limit buy order for testing."""
    return LimitOrder(
        coin="ETH",
        side=OrderSide.BUY,
        quantity=Decimal("0.1"),
        price=Decimal("3000.0"),
        reduce_only=False,
        time_in_force=OrderTif.GTC,
    )


@pytest.fixture
def sample_limit_sell_order() -> LimitOrder:
    """Sample limit sell order for testing."""
    return LimitOrder(
        coin="BTC",
        side=OrderSide.SELL,
        quantity=Decimal("0.05"),
        price=Decimal("50000.0"),
        reduce_only=False,
        time_in_force=OrderTif.GTC,
    )


@pytest.fixture
def sample_limit_buy_order_reduce_only() -> LimitOrder:
    """Sample limit buy order with reduce_only for testing."""
    return LimitOrder(
        coin="ETH",
        side=OrderSide.BUY,
        quantity=Decimal("0.1"),
        price=Decimal("3000.0"),
        reduce_only=True,
        time_in_force=OrderTif.IOC,
    )


@pytest.fixture
def sample_limit_sell_order_reduce_only() -> LimitOrder:
    """Sample limit sell order with reduce_only for testing."""
    return LimitOrder(
        coin="BTC",
        side=OrderSide.SELL,
        quantity=Decimal("0.05"),
        price=Decimal("50000.0"),
        reduce_only=True,
        time_in_force=OrderTif.ALO,
    )


# Response fixtures for order submission tests
@pytest.fixture
def market_success_response_resting() -> Dict[str, Any]:
    """Market order response with resting status."""
    return {
        "status": "ok",
        "response": {
            "type": "order",
            "data": {
                "statuses": [
                    {
                        "resting": {
                            "oid": 123456789
                        }
                    }
                ]
            }
        }
    }

@pytest.fixture
def market_success_response_filled() -> Dict[str, Any]:
    """Market order response with filled status."""
    return {
        "status": "ok",
        "response": {
            "type": "order",
            "data": {
                "statuses": [
                    {
                        "filled": {
                            "totalSz": "0.003",
                            "avgPx": "3593.5",
                            "oid": 221679167225,
                        }
                    }
                ]
            }
        }
    }


@pytest.fixture
def limit_success_response_resting() -> Dict[str, Any]:
    """Limit order response with resting status."""
    return {
        "status": "ok",
        "response": {
            "type": "order",
            "data": {
                "statuses": [
                    {
                        "resting": {
                            "oid": 987654321
                        }
                    }
                ]
            }
        }
    }

@pytest.fixture
def limit_success_response_filled() -> Dict[str, Any]:
    """Limit order response with filled status."""
    return {
        "status": "ok",
        "response": {
            "type": "order",
            "data": {
                "statuses": [
                    {
                        "filled": {
                            "totalSz": "0.05",
                            "avgPx": "51000.0",
                            "oid": 987654322,
                        }
                    }
                ]
            }
        }
    }



@pytest.fixture
def order_error_response() -> Dict[str, Any]:
    """Order response with error status."""
    return {
        "status": "ok",
        "response": {
            "type": "order",
            "data": {
                "statuses": [
                    {
                        "error": "Insufficient balance"
                    }
                ]
            }
        }
    }

