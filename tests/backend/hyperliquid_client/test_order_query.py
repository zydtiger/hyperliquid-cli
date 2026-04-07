"""
Test cases for HyperliquidClient order query functionality.

This module provides comprehensive tests for order status queries
and open orders retrieval operations.
"""

from decimal import Decimal

import pytest

from models.api import ExchangeError
from models.order import (
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
        client,
        mock_connection,
        mock_retry_operation,
    ):
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
        client,
        mock_connection,
        mock_retry_operation,
    ):
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

    def test_get_order_status_partially_filled(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
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
        client,
        mock_connection,
        mock_retry_operation,
    ):
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
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test order status retrieval when order is not found."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.query_order_by_oid.return_value = None

        with pytest.raises(ExchangeError) as exc_info:
            client.get_order_status(999999999)

        assert "Order 999999999 not found" in str(exc_info.value)

    def test_get_order_status_api_error(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test order status retrieval when API returns an error."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.query_order_by_oid.side_effect = Exception("API Error")

        with pytest.raises(ExchangeError) as exc_info:
            client.get_order_status(123456)

        assert "Failed to get order status: API Error" in str(exc_info.value)


class TestHyperliquidClientGetOpenOrders:
    """Test cases for the get_open_orders method."""

    def test_get_open_orders_success(
        self,
        client,
        mock_connection,
        mock_retry_operation,
        sample_open_orders_response,
        sample_order_status_responses,
        expected_open_orders,
    ):
        """Test successful open orders retrieval with multiple orders."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.open_orders.return_value = sample_open_orders_response

        # Mock the get_order_status calls
        def mock_query_order_by_oid(user_address, order_id):
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
        client,
        mock_connection,
        mock_retry_operation,
        sample_open_orders_empty_response,
    ):
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
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test open orders retrieval when API returns an error."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.open_orders.side_effect = Exception("API Error")

        with pytest.raises(ExchangeError) as exc_info:
            client.get_open_orders()

        assert "Failed to get open orders: API Error" in str(exc_info.value)

    def test_get_open_orders_order_status_error(
        self,
        client,
        mock_connection,
        mock_retry_operation,
        sample_open_orders_response,
    ):
        """Test open orders retrieval when get_order_status fails for one order."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.open_orders.return_value = sample_open_orders_response

        # Mock query_order_by_oid to fail for one specific order
        def mock_query_order_by_oid_with_error(user_address, order_id):
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
        client,
        mock_connection,
        mock_retry_operation,
    ):
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
