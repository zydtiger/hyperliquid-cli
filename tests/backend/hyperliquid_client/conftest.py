"""
Shared fixtures and utilities for HyperliquidClient tests.

This module provides comprehensive fixtures and utilities that are shared
across all test modules in the hyperliquid_client test package.
"""

from collections.abc import Callable
from decimal import Decimal
from typing import Any
from unittest.mock import Mock, patch

import pytest

from backend.exchange.hyperliquid_client import HyperliquidClient
from backend.exchange.hyperliquid_connection import HyperliquidConnection
from models.api import (
    BalanceInfo,
    SpotBalance,
    StakingDelegation,
    StakingInfo,
    StakingStatus,
)
from models.config import Config, HyperliquidConfig, NetworkType, TradingConfig
from models.order import (
    LimitOrder,
    MarketOrder,
    OrderHistoryEntry,
    OrderInfo,
    OrderSide,
    OrderStatus,
    OrderTif,
    OrderType,
)


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
    with patch(
        "backend.exchange.hyperliquid_client.HyperliquidConnection",
        return_value=mock_connection,
    ):
        return HyperliquidClient(mock_config)


@pytest.fixture
def sample_meta_response() -> dict[str, Any]:
    """Sample response from meta API."""
    return {
        "universe": [
            {"name": "BTC", "szDecimals": 8, "maxLeverage": 50},
            {"name": "ETH", "szDecimals": 6, "maxLeverage": 25},
            {"name": "SOL", "szDecimals": 4, "maxLeverage": 20},
        ]
    }


@pytest.fixture
def sample_asset_ctxs_response() -> list[dict[str, Any]]:
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
def sample_user_state_response() -> dict[str, Any]:
    """Sample response from user state API."""
    return {
        "marginSummary": {
            "accountValue": "3451.743653",
            "totalNtlPos": "10.8642",
            "totalRawUsd": "3440.879453",
            "totalMarginUsed": "5.318932",
        },
        "crossMarginSummary": {
            "accountValue": "3451.324721",
            "totalNtlPos": "0.0",
            "totalRawUsd": "3451.324721",
            "totalMarginUsed": "0.0",
        },
        "withdrawable": "3451.324721",
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
    return MarketOrder(coin="ETH", side=OrderSide.BUY, quantity=Decimal("0.1"), reduce_only=False)


@pytest.fixture
def sample_market_sell_order() -> MarketOrder:
    """Sample market sell order for testing."""
    return MarketOrder(coin="BTC", side=OrderSide.SELL, quantity=Decimal("0.05"), reduce_only=False)


@pytest.fixture
def sample_market_buy_order_reduce_only() -> MarketOrder:
    """Sample market buy order with reduce_only for testing."""
    return MarketOrder(coin="ETH", side=OrderSide.BUY, quantity=Decimal("0.1"), reduce_only=True)


@pytest.fixture
def sample_market_sell_order_reduce_only() -> MarketOrder:
    """Sample market sell order with reduce_only for testing."""
    return MarketOrder(coin="BTC", side=OrderSide.SELL, quantity=Decimal("0.05"), reduce_only=True)


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
def market_success_response_resting() -> dict[str, Any]:
    """Market order response with resting status."""
    return {
        "status": "ok",
        "response": {
            "type": "order",
            "data": {"statuses": [{"resting": {"oid": 123456789}}]},
        },
    }


@pytest.fixture
def market_success_response_filled() -> dict[str, Any]:
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
            },
        },
    }


@pytest.fixture
def limit_success_response_resting() -> dict[str, Any]:
    """Limit order response with resting status."""
    return {
        "status": "ok",
        "response": {
            "type": "order",
            "data": {"statuses": [{"resting": {"oid": 987654321}}]},
        },
    }


@pytest.fixture
def limit_success_response_filled() -> dict[str, Any]:
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
            },
        },
    }


@pytest.fixture
def order_error_response() -> dict[str, Any]:
    """Order response with error status."""
    return {
        "status": "ok",
        "response": {
            "type": "order",
            "data": {"statuses": [{"error": "Insufficient balance"}]},
        },
    }


@pytest.fixture
def cancel_success_response() -> dict[str, Any]:
    """Cancel order response with success status."""
    return {
        "status": "ok",
        "response": {
            "type": "cancel",
            "data": {"statuses": ["success"]},
        },
    }


@pytest.fixture
def cancel_error_response() -> dict[str, Any]:
    """Cancel order response with error status."""
    return {
        "status": "ok",
        "response": {
            "type": "cancel",
            "data": {"statuses": [{"error": "Insufficient balance"}]},
        },
    }


@pytest.fixture
def sample_spot_state() -> dict[str, Any]:
    """Sample spot state response with balance data."""
    return {
        "balances": [
            {
                "coin": "USDC",
                "token": 0,
                "total": "1000.50",
                "hold": "50.25",
                "entryNtl": "0.0",
            },
            {
                "coin": "HYPE",
                "token": 150,
                "total": "500.0",
                "hold": "0.0",
                "entryNtl": "0.0",
            },
            {
                "coin": "UETH",
                "token": 221,
                "total": "0.002998111",
                "hold": "0.0",
                "entryNtl": "10.8831",
            },
            {
                "coin": "BTC",
                "token": 1,
                "total": "0.0",  # Zero balance should be filtered out
                "hold": "0.0",
                "entryNtl": "0.0",
            },
        ]
    }


@pytest.fixture
def sample_staking_summary() -> dict[str, Any]:
    """Sample staking summary response."""
    return {
        "delegated": "100.61607572",
        "undelegated": "25.12345678",
        "totalPendingWithdrawal": "5.0",
        "nPendingWithdrawals": 2,
    }


@pytest.fixture
def sample_staking_delegations() -> list[dict[str, Any]]:
    """Sample staking delegation rows from the exchange."""
    return [
        {
            "validator": "validator-1",
            "amount": "70.50000000",
            "lockedUntilTimestamp": 1762271507000,
        },
        {
            "validator": "validator-2",
            "amount": "30.11607572",
            "lockedUntilTimestamp": 1762271508000,
        },
        {"validator": "validator-3", "amount": "0", "lockedUntilTimestamp": 1762271509000},
    ]


@pytest.fixture
def expected_staking_status() -> StakingStatus:
    """Expected staking status object for testing."""
    return StakingStatus(
        total_staked=Decimal("100.61607572"),
        delegations=[
            StakingDelegation(validator="validator-1", amount=Decimal("70.50000000")),
            StakingDelegation(validator="validator-2", amount=Decimal("30.11607572")),
        ],
    )


@pytest.fixture
def expected_balance_info() -> BalanceInfo:
    """Expected BalanceInfo object for testing."""
    return BalanceInfo(
        perps_account_value=Decimal("3451.743653"),
        perps_total_position_value=Decimal("10.8642"),
        perps_total_raw_usd=Decimal("3440.879453"),
        perps_margin_used=Decimal("5.318932"),
        perps_withdrawable=Decimal("3451.324721"),
        spot_balances=[
            SpotBalance(coin="USDC", total=Decimal("1000.50")),
            SpotBalance(coin="HYPE", total=Decimal("500.0")),
            SpotBalance(coin="UETH", total=Decimal("0.002998111")),
        ],
        staking_info=StakingInfo(
            delegated_amount=Decimal("100.61607572"),
            undelegated_amount=Decimal("25.12345678"),
            pending_withdrawals=Decimal("5.0"),
            pending_withdrawal_count=2,
        ),
    )


# Open orders fixtures for get_open_orders tests
@pytest.fixture
def sample_open_orders_response() -> list[dict[str, Any]]:
    """Sample response from open_orders API."""
    return [
        {
            "coin": "ETH",
            "side": "B",
            "limitPx": "3000.0",
            "sz": "0.003",
            "oid": 222605232959,
            "timestamp": 1762271506632,
            "origSz": "0.003",
        },
        {
            "coin": "BTC",
            "side": "S",
            "limitPx": "50000.0",
            "sz": "0.05",
            "oid": 222605232960,
            "timestamp": 1762271506633,
            "origSz": "0.1",
        },
        {
            "coin": "SOL",
            "side": "B",
            "limitPx": "150.0",
            "sz": "1.0",
            "oid": 222605232961,
            "timestamp": 1762271506634,
            "origSz": "2.0",
        },
    ]


@pytest.fixture
def sample_open_orders_empty_response() -> list[dict[str, Any]]:
    """Sample empty response from open_orders API."""
    return []


@pytest.fixture
def sample_order_status_responses() -> dict[int, dict[str, Any]]:
    """Sample order status responses for the open orders."""
    return {
        222605232959: {
            "order": {
                "order": {
                    "coin": "ETH",
                    "side": "B",
                    "limitPx": "3000.0",
                    "sz": "0.003",
                    "oid": 222605232959,
                    "timestamp": 1762271506632,
                    "reduceOnly": False,
                    "orderType": "Limit",
                    "origSz": "0.003",
                    "tif": "Gtc",
                },
                "status": "open",
                "statusTimestamp": 1762271506632,
            }
        },
        222605232960: {
            "order": {
                "order": {
                    "coin": "BTC",
                    "side": "S",
                    "limitPx": "50000.0",
                    "sz": "0.05",
                    "oid": 222605232960,
                    "timestamp": 1762271506633,
                    "reduceOnly": False,
                    "orderType": "Limit",
                    "origSz": "0.1",
                    "tif": "Gtc",
                },
                "status": "open",
                "statusTimestamp": 1762271506633,
            }
        },
        222605232961: {
            "order": {
                "order": {
                    "coin": "SOL",
                    "side": "B",
                    "limitPx": "150.0",
                    "sz": "1.0",
                    "oid": 222605232961,
                    "timestamp": 1762271506634,
                    "reduceOnly": False,
                    "orderType": "Limit",
                    "origSz": "2.0",
                    "tif": "Gtc",
                },
                "status": "open",
                "statusTimestamp": 1762271506634,
            }
        },
    }


@pytest.fixture
def expected_open_orders() -> list[OrderInfo]:
    """Expected OrderInfo objects for open orders testing."""
    return [
        OrderInfo(
            order_id=222605232959,
            coin="ETH",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.003"),
            price=Decimal("3000.0"),
            filled_quantity=Decimal("0.0"),
            remaining_quantity=Decimal("0.003"),
            average_fill_price=None,
            status=OrderStatus.OPEN,
            timestamp=1762271506632,
            reduce_only=False,
            time_in_force=OrderTif.GTC,
        ),
        OrderInfo(
            order_id=222605232960,
            coin="BTC",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.1"),
            price=Decimal("50000.0"),
            filled_quantity=Decimal("0.05"),
            remaining_quantity=Decimal("0.05"),
            average_fill_price=None,
            status=OrderStatus.OPEN,
            timestamp=1762271506633,
            reduce_only=False,
            time_in_force=OrderTif.GTC,
        ),
        OrderInfo(
            order_id=222605232961,
            coin="SOL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("2.0"),
            price=Decimal("150.0"),
            filled_quantity=Decimal("1.0"),
            remaining_quantity=Decimal("1.0"),
            average_fill_price=None,
            status=OrderStatus.OPEN,
            timestamp=1762271506634,
            reduce_only=False,
            time_in_force=OrderTif.GTC,
        ),
    ]


@pytest.fixture
def sample_historical_orders_response() -> list[dict[str, Any]]:
    """Sample response from historical_orders API."""
    return [
        {
            "status": "filled",
            "statusTimestamp": 1762271507000,
            "order": {"coin": "ETH", "side": "B", "oid": 333001},
        },
        {
            "status": "filled",
            "statusTimestamp": 1762271506000,
            "order": {"coin": "BTC", "side": "S", "oid": 333002},
        },
        {
            "status": "canceled",
            "statusTimestamp": 1762271505000,
            "order": {"coin": "DOGE", "side": "B", "oid": 333003},
        },
        {
            "status": "filled",
            "statusTimestamp": 1762271504000,
            "order": {"coin": "SOL", "side": "B", "oid": 333004},
        },
    ]


@pytest.fixture
def sample_user_fills_response() -> list[dict[str, Any]]:
    """Sample response from user_fills_by_time API."""
    return [
        {
            "oid": 333001,
            "coin": "ETH",
            "dir": "Open Long",
            "px": "2020.0",
            "sz": "0.002",
            "fee": "0.001500",
            "feeToken": "USDC",
            "closedPnl": "0.100000",
            "time": 1762271506500,
        },
        {
            "oid": 333001,
            "coin": "ETH",
            "dir": "Open Long",
            "px": "2021.0",
            "sz": "0.003",
            "fee": "0.002500",
            "feeToken": "USDC",
            "closedPnl": "0.200000",
            "time": 1762271506600,
        },
        {
            "oid": 333002,
            "coin": "BTC",
            "dir": "Close Short",
            "px": "50000.0",
            "sz": "0.010000",
            "fee": "0.000010",
            "feeToken": "BTC",
            "closedPnl": "10.000000",
            "time": 1762271505900,
        },
        {
            "oid": 333003,
            "coin": "DOGE",
            "dir": "Open Long",
            "px": "0.09",
            "sz": "1000.0",
            "fee": "0.050000",
            "feeToken": "USDC",
            "closedPnl": "0.000000",
            "time": 1762271504900,
        },
    ]


@pytest.fixture
def expected_order_history() -> list[OrderHistoryEntry]:
    """Expected order history entries after aggregation."""
    return [
        OrderHistoryEntry(
            time=1762271507000,
            coin="ETH",
            direction="Open Long",
            price=Decimal("2020.6"),
            size=Decimal("0.005"),
            notional=Decimal("10.1030"),
            fee=Decimal("0.004000"),
            fee_usdc=Decimal("0.004000"),
            fee_token="USDC",  # noqa: S106 - fee token symbol, not a credential
            gross_closed_pnl=Decimal("0.300000"),
            closed_pnl=Decimal("0.296000"),
            order_id=333001,
            status=OrderStatus.FILLED,
        ),
        OrderHistoryEntry(
            time=1762271506000,
            coin="BTC",
            direction="Close Short",
            price=Decimal("50000.0"),
            size=Decimal("0.010000"),
            notional=Decimal("500.000000"),
            fee=Decimal("0.000010"),
            fee_usdc=Decimal("0.500000"),
            fee_token="BTC",  # noqa: S106 - fee token symbol, not a credential
            gross_closed_pnl=Decimal("10.000000"),
            closed_pnl=Decimal("9.500000"),
            order_id=333002,
            status=OrderStatus.FILLED,
        ),
    ]
