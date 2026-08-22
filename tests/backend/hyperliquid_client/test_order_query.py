"""
Test cases for HyperliquidClient order query functionality.

This module provides comprehensive tests for order status queries
and open orders retrieval operations.
"""

from collections.abc import Callable
from decimal import Decimal
from typing import Any
from unittest.mock import Mock

import pytest

from backend.exchange.hyperliquid_client import HyperliquidClient
from models.api import ExchangeError
from models.order import (
    OrderHistoryEntry,
    OrderInfo,
    OrderSide,
    OrderStatus,
    OrderTif,
    OrderTrigger,
    OrderType,
    TriggerType,
)


class TestHyperliquidClientOrderStatus:
    """Test cases for the get_order_status method."""

    def test_get_order_status_success_limit_order(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
        """Test successful order status retrieval for a limit order."""
        # Mock API response matching actual structure
        api_response = {
            "order": {
                "order": {
                    "coin": "ETH",
                    "side": "B",
                    "limitPx": "3700.0",
                    "sz": "0.002",  # remaining quantity
                    "oid": 220717680685,
                    "timestamp": 1762141573004,
                    "reduceOnly": False,
                    "orderType": "Limit",
                    "origSz": "0.003",  # original quantity
                    "tif": "Gtc",
                },
                "status": "open",
                "statusTimestamp": 1762141573004,
            }
        }

        expected_order = OrderInfo(
            order_id=220717680685,
            coin="ETH",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.003"),
            price=Decimal("3700.0"),
            filled_quantity=Decimal("0.001"),  # origSz - sz
            remaining_quantity=Decimal("0.002"),
            average_fill_price=None,
            status=OrderStatus.OPEN,
            timestamp=1762141573004,
            reduce_only=False,
            time_in_force=OrderTif.GTC,
        )

        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.query_order_by_oid.return_value = api_response

        result = client.get_order_status(220717680685)

        assert result == expected_order
        mock_connection.info.query_order_by_oid.assert_called_once_with(
            "0x1234567890123456789012345678901234567890", 220717680685
        )

    def test_get_order_status_success_market_order(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
        """Test successful order status retrieval for a market order."""
        api_response = {
            "order": {
                "order": {
                    "coin": "BTC",
                    "side": "S",
                    "sz": "0.0",  # fully filled
                    "oid": 220717680686,
                    "timestamp": 1762141573005,
                    "reduceOnly": False,
                    "orderType": "Market",
                    "origSz": "0.1",
                    "averageFillPx": "42500.5",
                },
                "status": "filled",
                "statusTimestamp": 1762141573006,
            }
        }

        expected_order = OrderInfo(
            order_id=220717680686,
            coin="BTC",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.1"),
            price=None,  # Market orders have no limit price
            filled_quantity=Decimal("0.1"),
            remaining_quantity=Decimal("0.0"),
            average_fill_price=Decimal("42500.5"),
            status=OrderStatus.FILLED,
            timestamp=1762141573005,
            reduce_only=False,
            time_in_force=None,  # Market orders typically don't have TIF
        )

        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.query_order_by_oid.return_value = api_response

        result = client.get_order_status(220717680686)

        assert result == expected_order

    def test_get_order_status_market_order_ignores_exchange_limit_price(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
        """Test market orders normalize exchange limit caps to a null price."""
        api_response = {
            "order": {
                "order": {
                    "coin": "ETH",
                    "side": "B",
                    "limitPx": "43000.0",
                    "sz": "0.0",
                    "oid": 220717680689,
                    "timestamp": 1762141573010,
                    "reduceOnly": False,
                    "orderType": "Market",
                    "origSz": "0.2",
                    "averageFillPx": "42500.5",
                    "tif": "Ioc",
                },
                "status": "filled",
                "statusTimestamp": 1762141573011,
            }
        }

        expected_order = OrderInfo(
            order_id=220717680689,
            coin="ETH",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.2"),
            price=None,
            filled_quantity=Decimal("0.2"),
            remaining_quantity=Decimal("0.0"),
            average_fill_price=Decimal("42500.5"),
            status=OrderStatus.FILLED,
            timestamp=1762141573010,
            reduce_only=False,
            time_in_force=OrderTif.IOC,
        )

        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.query_order_by_oid.return_value = api_response

        result = client.get_order_status(220717680689)

        assert result == expected_order

    def test_get_order_status_partially_filled(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
        """Test order status retrieval for a partially filled order."""
        api_response = {
            "order": {
                "order": {
                    "coin": "SOL",
                    "side": "B",
                    "limitPx": "150.0",
                    "sz": "0.5",  # remaining quantity
                    "oid": 220717680687,
                    "timestamp": 1762141573007,
                    "reduceOnly": False,
                    "orderType": "Limit",
                    "origSz": "1.0",  # original quantity
                    "tif": "Ioc",
                    "averageFillPx": "149.8",
                },
                "status": "partially_filled",
                "statusTimestamp": 1762141573008,
            }
        }

        expected_order = OrderInfo(
            order_id=220717680687,
            coin="SOL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("1.0"),
            price=Decimal("150.0"),
            filled_quantity=Decimal("0.5"),
            remaining_quantity=Decimal("0.5"),
            average_fill_price=Decimal("149.8"),
            status=OrderStatus.PARTIALLY_FILLED,
            timestamp=1762141573007,
            reduce_only=False,
            time_in_force=OrderTif.IOC,
        )

        mock_connection.retry_operation.return_value = expected_order
        mock_connection.info.query_order_by_oid.return_value = api_response

        result = client.get_order_status(220717680687)

        assert result == expected_order

    def test_get_order_status_success_trigger_order(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
        """Test trigger order status includes trigger type and price."""
        api_response = {
            "order": {
                "order": {
                    "coin": "DOGE",
                    "side": "S",
                    "limitPx": "0.099141",
                    "sz": "30000.0",
                    "oid": 367120653089,
                    "timestamp": 1762141573007,
                    "triggerCondition": "triggeredAbove",
                    "isTrigger": True,
                    "triggerPx": "0.1",
                    "reduceOnly": False,
                    "orderType": "Limit",
                    "origSz": "30000.0",
                },
                "status": "open",
                "statusTimestamp": 1762141573008,
            }
        }

        expected_order = OrderInfo(
            order_id=367120653089,
            coin="DOGE",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=Decimal("30000.0"),
            price=Decimal("0.099141"),
            filled_quantity=Decimal("0.0"),
            remaining_quantity=Decimal("30000.0"),
            average_fill_price=None,
            status=OrderStatus.OPEN,
            timestamp=1762141573007,
            reduce_only=False,
            time_in_force=None,
            trigger=OrderTrigger(
                trigger_type=TriggerType.TAKE,
                trigger_price=Decimal("0.1"),
            ),
        )

        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.query_order_by_oid.return_value = api_response

        result = client.get_order_status(367120653089)

        assert result == expected_order

    def test_get_order_status_not_found(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
        """Test order status retrieval when order is not found."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.query_order_by_oid.return_value = None

        with pytest.raises(ExchangeError) as exc_info:
            client.get_order_status(999999999)

        assert "Order 999999999 not found" in str(exc_info.value)

    def test_get_order_status_api_error(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
        """Test order status retrieval when API returns an error."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.query_order_by_oid.side_effect = Exception("API Error")

        with pytest.raises(ExchangeError) as exc_info:
            client.get_order_status(123456)

        assert "Failed to get order status: API Error" in str(exc_info.value)

    def test_get_order_status_resolves_spot_symbol(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
        """Test spot order status returns the human-readable pair symbol."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.query_order_by_oid.return_value = {
            "order": {
                "order": {
                    "coin": "@142",
                    "side": "B",
                    "limitPx": "87000.0",
                    "sz": "0.001",
                    "oid": 220717680699,
                    "timestamp": 1762141573999,
                    "reduceOnly": False,
                    "orderType": "Limit",
                    "origSz": "0.001",
                    "tif": "Gtc",
                },
                "status": "open",
                "statusTimestamp": 1762141574000,
            }
        }
        mock_connection.info.spot_meta.return_value = {
            "universe": [{"tokens": [0, 1], "name": "@142", "index": 142, "isCanonical": True}],
            "tokens": [
                {"name": "BTC", "szDecimals": 5, "weiDecimals": 8, "index": 0},
                {"name": "USDC", "szDecimals": 6, "weiDecimals": 6, "index": 1},
            ],
        }

        result = client.get_order_status(220717680699)

        assert result.coin == "BTC/USDC"
        mock_connection.info.spot_meta.assert_called_once_with()


class TestHyperliquidClientGetOpenOrders:
    """Test cases for the get_open_orders method."""

    def test_get_open_orders_success(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
        sample_open_orders_response: list[dict[str, Any]],
        sample_order_status_responses: dict[int, dict[str, Any]],
        expected_open_orders: list[OrderInfo],
    ) -> None:
        """Test successful open orders retrieval with multiple orders."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.open_orders.return_value = sample_open_orders_response

        # Mock the get_order_status calls
        def mock_query_order_by_oid(user_address: str, order_id: int) -> dict[str, Any]:
            return sample_order_status_responses[order_id]

        mock_connection.info.query_order_by_oid.side_effect = mock_query_order_by_oid

        result = client.get_open_orders()

        assert len(result) == 3
        assert result == expected_open_orders

        # Verify open_orders was called once
        mock_connection.info.open_orders.assert_called_once_with(
            "0x1234567890123456789012345678901234567890"
        )

        # Verify query_order_by_oid was called for each order ID
        expected_order_ids = [222605232959, 222605232960, 222605232961]
        assert mock_connection.info.query_order_by_oid.call_count == 3

        for call in mock_connection.info.query_order_by_oid.call_args_list:
            args, _kwargs = call
            assert args[0] == "0x1234567890123456789012345678901234567890"  # user address
            assert args[1] in expected_order_ids  # order ID

    def test_get_open_orders_empty(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
        sample_open_orders_empty_response: list[dict[str, Any]],
    ) -> None:
        """Test open orders retrieval when no orders are open."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.open_orders.return_value = sample_open_orders_empty_response

        result = client.get_open_orders()

        assert result == []
        mock_connection.info.open_orders.assert_called_once_with(
            "0x1234567890123456789012345678901234567890"
        )
        # query_order_by_oid should not be called since there are no orders
        mock_connection.info.query_order_by_oid.assert_not_called()

    def test_get_open_orders_api_error(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
        """Test open orders retrieval when API returns an error."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.open_orders.side_effect = Exception("API Error")

        with pytest.raises(ExchangeError) as exc_info:
            client.get_open_orders()

        assert "Failed to get open orders: API Error" in str(exc_info.value)

    def test_get_open_orders_order_status_error(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
        sample_open_orders_response: list[dict[str, Any]],
    ) -> None:
        """Test open orders retrieval when get_order_status fails for one order."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.open_orders.return_value = sample_open_orders_response

        # Mock query_order_by_oid to fail for one specific order
        def mock_query_order_by_oid_with_error(user_address: str, order_id: int) -> dict[str, Any]:
            if order_id == 222605232960:
                raise Exception("Order not found")
            return {
                "order": {
                    "order": {
                        "coin": "ETH",
                        "side": "B",
                        "limitPx": "3000.0",
                        "sz": "0.003",
                        "oid": order_id,
                        "timestamp": 1762271506632,
                        "reduceOnly": False,
                        "orderType": "Limit",
                        "origSz": "0.003",
                        "tif": "Gtc",
                    },
                    "status": "open",
                    "statusTimestamp": 1762271506632,
                }
            }

        mock_connection.info.query_order_by_oid.side_effect = mock_query_order_by_oid_with_error

        with pytest.raises(ExchangeError) as exc_info:
            client.get_open_orders()

        assert "Failed to get order status: Order not found" in str(exc_info.value)

    def test_get_open_orders_single_order(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
        """Test open orders retrieval with a single open order."""
        single_order_response = [
            {
                "coin": "ETH",
                "side": "B",
                "limitPx": "3000.0",
                "sz": "0.003",
                "oid": 222605232959,
                "timestamp": 1762271506632,
                "origSz": "0.003",
            }
        ]

        expected_single_order = OrderInfo(
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
        )

        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.open_orders.return_value = single_order_response
        mock_connection.info.query_order_by_oid.return_value = {
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
        }

        result = client.get_open_orders()

        assert len(result) == 1
        assert result == [expected_single_order]


class TestHyperliquidClientGetOrderHistory:
    """Test cases for the get_order_history method."""

    def test_get_order_history_success(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
        sample_historical_orders_response: list[dict[str, Any]],
        sample_user_fills_response: list[dict[str, Any]],
        expected_order_history: list[OrderHistoryEntry],
    ) -> None:
        """Test successful filled-order history aggregation."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.historical_orders.return_value = sample_historical_orders_response
        mock_connection.info.user_fills_by_time.return_value = sample_user_fills_response

        result = client.get_order_history(10)

        assert result == expected_order_history
        mock_connection.info.historical_orders.assert_called_once_with(
            "0x1234567890123456789012345678901234567890"
        )
        mock_connection.info.user_fills_by_time.assert_called_once()
        call_args = mock_connection.info.user_fills_by_time.call_args[0]
        assert call_args[0] == "0x1234567890123456789012345678901234567890"
        assert call_args[1] == 1762271504000

    def test_get_order_history_applies_limit(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
        sample_historical_orders_response: list[dict[str, Any]],
        sample_user_fills_response: list[dict[str, Any]],
        expected_order_history: list[OrderHistoryEntry],
    ) -> None:
        """Test history retrieval applies the requested limit."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.historical_orders.return_value = sample_historical_orders_response
        mock_connection.info.user_fills_by_time.return_value = sample_user_fills_response

        result = client.get_order_history(1)

        assert result == [expected_order_history[0]]
        mock_connection.info.user_fills_by_time.assert_called_once_with(
            "0x1234567890123456789012345678901234567890",
            1762271507000,
        )

    def test_get_order_history_expands_until_limit_is_reached(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
        sample_historical_orders_response: list[dict[str, Any]],
        sample_user_fills_response: list[dict[str, Any]],
        expected_order_history: list[OrderHistoryEntry],
    ) -> None:
        """Test history retrieval widens the fill query until enough rows are found."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.historical_orders.return_value = sample_historical_orders_response

        def fills_for_start_time(_address: str, start_time: int) -> list[dict[str, Any]]:
            if start_time == 1762271506000:
                return sample_user_fills_response[:2]
            if start_time == 1762271504000:
                return sample_user_fills_response
            raise AssertionError(f"Unexpected start_time: {start_time}")

        mock_connection.info.user_fills_by_time.side_effect = fills_for_start_time

        result = client.get_order_history(2)

        assert result == expected_order_history
        assert mock_connection.info.user_fills_by_time.call_args_list[0].args == (
            "0x1234567890123456789012345678901234567890",
            1762271506000,
        )
        assert mock_connection.info.user_fills_by_time.call_args_list[1].args == (
            "0x1234567890123456789012345678901234567890",
            1762271504000,
        )

    def test_get_order_history_empty(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
        """Test history retrieval when no filled entries are available."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.historical_orders.return_value = []
        mock_connection.info.user_fills_by_time.return_value = []

        result = client.get_order_history(10)

        assert result == []

    def test_get_order_history_historical_orders_error(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
        """Test history retrieval when historical_orders fails."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.historical_orders.side_effect = Exception("API Error")

        with pytest.raises(ExchangeError) as exc_info:
            client.get_order_history(10)

        assert "Failed to get order history: API Error" in str(exc_info.value)

    def test_get_order_history_user_fills_error(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
        sample_historical_orders_response: list[dict[str, Any]],
    ) -> None:
        """Test history retrieval when user_fills_by_time fails."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.historical_orders.return_value = sample_historical_orders_response
        mock_connection.info.user_fills_by_time.side_effect = Exception("Fill API Error")

        with pytest.raises(ExchangeError) as exc_info:
            client.get_order_history(10)

        assert "Failed to get order history: Fill API Error" in str(exc_info.value)

    def test_get_order_history_resolves_spot_symbol_and_fee_conversion(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
        """Test spot fills resolve to pair symbols before fee conversion."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.historical_orders.return_value = [
            {
                "status": "filled",
                "statusTimestamp": 1762271507000,
                "order": {"coin": "@142", "side": "B", "oid": 333142},
            }
        ]
        mock_connection.info.user_fills_by_time.return_value = [
            {
                "oid": 333142,
                "coin": "@142",
                "dir": "Open Long",
                "px": "50000.0",
                "sz": "0.010000",
                "fee": "0.000010",
                "feeToken": "BTC",
                "closedPnl": "0.000000",
                "time": 1762271506900,
            }
        ]
        mock_connection.info.spot_meta.return_value = {
            "universe": [{"tokens": [0, 1], "name": "@142", "index": 142, "isCanonical": True}],
            "tokens": [
                {"name": "BTC", "szDecimals": 5, "weiDecimals": 8, "index": 0},
                {"name": "USDC", "szDecimals": 6, "weiDecimals": 6, "index": 1},
            ],
        }

        result = client.get_order_history(10)

        assert len(result) == 1
        assert result[0].coin == "BTC/USDC"
        assert result[0].fee_usdc == Decimal("0.500000")
