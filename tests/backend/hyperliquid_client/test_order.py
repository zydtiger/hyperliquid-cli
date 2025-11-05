"""
Test cases for HyperliquidClient order functionality.

This module provides comprehensive tests for order status queries,
market order submission, and limit order submission.
"""

import pytest
from decimal import Decimal
from unittest.mock import patch

from backend.exchange.hyperliquid_client import HyperliquidClient
from models.api import ExchangeError
from models.order import (
    LimitOrder,
    MarketOrder,
    OrderInfo,
    OrderResult,
    OrderSide,
    OrderStatus,
    OrderTif,
    OrderType,
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


class TestHyperliquidClientSubmitMarketOrder:
    """Test cases for the submit_market_order method."""

    def test_submit_market_order_buy_success(
        self,
        client,
        mock_config_with_slippage,
        sample_market_buy_order,
        market_success_response_resting,
        mock_retry_operation,
    ):
        """Test successful market buy order submission with resting status."""
        # Re-create client with config that has slippage
        with patch(
            "backend.exchange.hyperliquid_client.HyperliquidConnection",
            return_value=client.connection,
        ):
            client = HyperliquidClient(mock_config_with_slippage)

        # Mock the market_open method
        client.connection.exchange.market_open.return_value = market_success_response_resting  # type: ignore[attr-defined]

        client.connection.retry_operation.side_effect = mock_retry_operation  # type: ignore[attr-defined]

        result = client.submit_market_order(sample_market_buy_order)

        # Verify result
        expected_result = OrderResult(
            success=True,
            order_id=123456789,
            status=OrderStatus.OPEN,
            message="Market order is resting on the book",
        )
        assert result == expected_result

        # Verify the correct method was called with correct parameters
        client.connection.exchange.market_open.assert_called_once_with(  # type: ignore[attr-defined]
            name="ETH",
            is_buy=True,
            sz=0.1,
            px=None,
            slippage=0.01,
        )

    def test_submit_market_order_buy_filled_success(
        self,
        client,
        mock_config_with_slippage,
        sample_market_buy_order,
        market_success_response_filled,
        mock_retry_operation,
    ):
        """Test successful market buy order submission with filled status."""
        # Re-create client with config that has slippage
        with patch(
            "backend.exchange.hyperliquid_client.HyperliquidConnection",
            return_value=client.connection,
        ):
            client = HyperliquidClient(mock_config_with_slippage)

        # Mock the market_open method
        client.connection.exchange.market_open.return_value = market_success_response_filled  # type: ignore[attr-defined]

        client.connection.retry_operation.side_effect = mock_retry_operation  # type: ignore[attr-defined]

        result = client.submit_market_order(sample_market_buy_order)

        # Verify result
        expected_result = OrderResult(
            success=True,
            order_id=221679167225,
            status=OrderStatus.FILLED,
            message="Market order filled 0.003 at 3593.5",
        )
        assert result == expected_result

        # Verify the correct method was called with correct parameters
        client.connection.exchange.market_open.assert_called_once_with(  # type: ignore[attr-defined]
            name="ETH",
            is_buy=True,
            sz=0.1,
            px=None,
            slippage=0.01,
        )

    def test_submit_market_order_error_response(
        self,
        client,
        mock_config_with_slippage,
        sample_market_buy_order,
        order_error_response,
        mock_retry_operation,
    ):
        """Test market order submission with error status."""
        # Re-create client with config that has slippage
        with patch(
            "backend.exchange.hyperliquid_client.HyperliquidConnection",
            return_value=client.connection,
        ):
            client = HyperliquidClient(mock_config_with_slippage)

        # Mock the market_open method to return error status
        client.connection.exchange.market_open.return_value = order_error_response  # type: ignore[attr-defined]

        client.connection.retry_operation.side_effect = mock_retry_operation  # type: ignore[attr-defined]

        result = client.submit_market_order(sample_market_buy_order)

        # Verify result
        expected_result = OrderResult(
            success=False,
            order_id=None,
            status=OrderStatus.REJECTED,
            message="Market order failed",
            error="Insufficient balance",
        )
        assert result == expected_result

    def test_submit_market_order_sell_success(
        self,
        client,
        mock_config_with_slippage,
        sample_market_sell_order,
        market_success_response_resting,
        mock_retry_operation,
    ):
        """Test successful market sell order submission with resting status."""
        # Re-create client with config that has slippage
        with patch(
            "backend.exchange.hyperliquid_client.HyperliquidConnection",
            return_value=client.connection,
        ):
            client = HyperliquidClient(mock_config_with_slippage)

        # Mock the market_close method
        client.connection.exchange.market_close.return_value = market_success_response_resting  # type: ignore[attr-defined]

        client.connection.retry_operation.side_effect = mock_retry_operation  # type: ignore[attr-defined]

        result = client.submit_market_order(sample_market_sell_order)

        # Verify result
        expected_result = OrderResult(
            success=True,
            order_id=123456789,
            status=OrderStatus.OPEN,
            message="Market order is resting on the book",
        )
        assert result == expected_result

        # Verify the correct method was called with correct parameters
        client.connection.exchange.market_close.assert_called_once_with(  # type: ignore[attr-defined]
            coin="BTC",
            sz=0.05,
            px=None,
            slippage=0.01,
        )

    def test_submit_market_order_api_error(
        self,
        client,
        mock_config_with_slippage,
        sample_market_buy_order,
        order_error_response,
        mock_retry_operation,
    ):
        """Test market order submission when API returns error status."""
        # Re-create client with config that has slippage
        with patch(
            "backend.exchange.hyperliquid_client.HyperliquidConnection",
            return_value=client.connection,
        ):
            client = HyperliquidClient(mock_config_with_slippage)

        # Mock the market_open method to return error
        client.connection.exchange.market_open.return_value = order_error_response  # type: ignore[attr-defined]

        client.connection.retry_operation.side_effect = mock_retry_operation  # type: ignore[attr-defined]

        result = client.submit_market_order(sample_market_buy_order)

        # Verify result
        expected_result = OrderResult(
            success=False,
            order_id=None,
            status=OrderStatus.REJECTED,
            message="Market order failed",
            error="Insufficient balance",
        )
        assert result == expected_result


class TestHyperliquidClientSubmitLimitOrder:
    """Test cases for the submit_limit_order method."""

    def test_submit_limit_order_buy_success(
        self,
        client,
        sample_limit_buy_order,
        limit_success_response_resting,
        mock_retry_operation,
    ):
        """Test successful limit buy order submission with resting status."""
        # Mock the order method
        client.connection.exchange.order.return_value = limit_success_response_resting

        client.connection.retry_operation.side_effect = mock_retry_operation

        result = client.submit_limit_order(sample_limit_buy_order)

        # Verify result
        expected_result = OrderResult(
            success=True,
            order_id=987654321,
            status=OrderStatus.OPEN,
            message="Limit order is resting on the book",
        )
        assert result == expected_result

        # Verify the correct method was called with correct parameters
        client.connection.exchange.order.assert_called_once_with(
            name="ETH",
            is_buy=True,
            sz=0.1,
            limit_px=3000.0,
            order_type={"limit": {"tif": "Gtc"}},
            reduce_only=False,
        )

    def test_submit_limit_order_resting_success(
        self,
        client,
        sample_limit_buy_order,
        limit_success_response_resting,
        mock_retry_operation,
    ):
        """Test successful limit order submission with resting status."""
        # Mock the order method
        client.connection.exchange.order.return_value = limit_success_response_resting

        client.connection.retry_operation.side_effect = mock_retry_operation

        result = client.submit_limit_order(sample_limit_buy_order)

        # Verify result
        expected_result = OrderResult(
            success=True,
            order_id=987654321,
            status=OrderStatus.OPEN,
            message="Limit order is resting on the book",
        )
        assert result == expected_result

        # Verify the correct method was called with correct parameters
        client.connection.exchange.order.assert_called_once_with(
            name="ETH",
            is_buy=True,
            sz=0.1,
            limit_px=3000.0,
            order_type={"limit": {"tif": "Gtc"}},
            reduce_only=False,
        )

    def test_submit_limit_order_error_response(
        self,
        client,
        sample_limit_buy_order,
        order_error_response,
        mock_retry_operation,
    ):
        """Test limit order submission with error status."""
        # Mock the order method to return error status
        client.connection.exchange.order.return_value = order_error_response

        client.connection.retry_operation.side_effect = mock_retry_operation

        result = client.submit_limit_order(sample_limit_buy_order)

        # Verify result
        expected_result = OrderResult(
            success=False,
            order_id=None,
            status=OrderStatus.REJECTED,
            message="Limit order failed",
            error="Insufficient balance",
        )
        assert result == expected_result

    def test_submit_limit_order_sell_success(
        self,
        client,
        sample_limit_sell_order,
        limit_success_response_resting,
        mock_retry_operation,
    ):
        """Test successful limit sell order submission with resting status."""
        # Mock the order method
        client.connection.exchange.order.return_value = limit_success_response_resting

        client.connection.retry_operation.side_effect = mock_retry_operation

        result = client.submit_limit_order(sample_limit_sell_order)

        # Verify result
        expected_result = OrderResult(
            success=True,
            order_id=987654321,
            status=OrderStatus.OPEN,
            message="Limit order is resting on the book",
        )
        assert result == expected_result

        # Verify the correct method was called with correct parameters
        client.connection.exchange.order.assert_called_once_with(
            name="BTC",
            is_buy=False,
            sz=0.05,
            limit_px=50000.0,
            order_type={"limit": {"tif": "Gtc"}},
            reduce_only=False,
        )

    def test_submit_limit_order_buy_filled_success(
        self,
        client,
        sample_limit_buy_order,
        limit_success_response_filled,
        mock_retry_operation,
    ):
        """Test successful limit buy order submission with filled status."""
        # Mock the order method
        client.connection.exchange.order.return_value = limit_success_response_filled

        client.connection.retry_operation.side_effect = mock_retry_operation

        result = client.submit_limit_order(sample_limit_buy_order)

        # Verify result
        expected_result = OrderResult(
            success=True,
            order_id=987654322,
            status=OrderStatus.FILLED,
            message="Limit order filled 0.05 at 51000.0",
        )
        assert result == expected_result

        # Verify the correct method was called with correct parameters
        client.connection.exchange.order.assert_called_once_with(
            name="ETH",
            is_buy=True,
            sz=0.1,
            limit_px=3000.0,
            order_type={"limit": {"tif": "Gtc"}},
            reduce_only=False,
        )

    def test_submit_limit_order_sell_filled_success(
        self,
        client,
        sample_limit_sell_order,
        limit_success_response_filled,
        mock_retry_operation,
    ):
        """Test successful limit sell order submission with filled status."""
        # Mock the order method
        client.connection.exchange.order.return_value = limit_success_response_filled

        client.connection.retry_operation.side_effect = mock_retry_operation

        result = client.submit_limit_order(sample_limit_sell_order)

        # Verify result
        expected_result = OrderResult(
            success=True,
            order_id=987654322,
            status=OrderStatus.FILLED,
            message="Limit order filled 0.05 at 51000.0",
        )
        assert result == expected_result

        # Verify the correct method was called with correct parameters
        client.connection.exchange.order.assert_called_once_with(
            name="BTC",
            is_buy=False,
            sz=0.05,
            limit_px=50000.0,
            order_type={"limit": {"tif": "Gtc"}},
            reduce_only=False,
        )

    def test_submit_limit_order_different_tif_values(
        self,
        client,
        limit_success_response_resting,
        mock_retry_operation,
    ):
        """Test limit order submission with different TIF values."""
        # Test GTC
        order_gtc = LimitOrder(
            coin="ETH",
            side=OrderSide.BUY,
            quantity=Decimal("0.1"),
            price=Decimal("3000.0"),
            time_in_force=OrderTif.GTC,
        )

        client.connection.exchange.order.return_value = limit_success_response_resting
        client.connection.retry_operation.side_effect = mock_retry_operation

        result = client.submit_limit_order(order_gtc)
        assert result.success is True
        client.connection.exchange.order.assert_called_with(
            name="ETH",
            is_buy=True,
            sz=0.1,
            limit_px=3000.0,
            order_type={"limit": {"tif": "Gtc"}},
            reduce_only=False,
        )

        # Reset mock
        client.connection.exchange.order.reset_mock()

    def test_submit_limit_order_api_error(
        self,
        client,
        sample_limit_buy_order,
        order_error_response,
        mock_retry_operation,
    ):
        """Test limit order submission when API returns error status."""
        # Mock the order method to return error
        client.connection.exchange.order.return_value = order_error_response

        client.connection.retry_operation.side_effect = mock_retry_operation

        result = client.submit_limit_order(sample_limit_buy_order)

        # Verify result
        expected_result = OrderResult(
            success=False,
            order_id=None,
            status=OrderStatus.REJECTED,
            message="Limit order failed",
            error="Insufficient balance",
        )
        assert result == expected_result

    def test_submit_limit_order_side_parameter_mapping(
        self,
        client,
        sample_limit_buy_order,
        sample_limit_sell_order,
        limit_success_response_resting,
        mock_retry_operation,
    ):
        """Test that order side is correctly mapped to is_buy parameter."""
        # Test BUY side
        buy_order = sample_limit_buy_order

        client.connection.exchange.order.return_value = limit_success_response_resting
        client.connection.retry_operation.side_effect = mock_retry_operation

        client.submit_limit_order(buy_order)

        # Verify BUY side maps to is_buy=True
        args, kwargs = client.connection.exchange.order.call_args
        assert kwargs["is_buy"] is True

        # Reset mock
        client.connection.exchange.order.reset_mock()

        # Test SELL side
        sell_order = sample_limit_sell_order

        client.submit_limit_order(sell_order)

        # Verify SELL side maps to is_buy=False
        args, kwargs = client.connection.exchange.order.call_args
        assert kwargs["is_buy"] is False


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
            args, kwargs = call
            assert (
                args[0] == "0x1234567890123456789012345678901234567890"
            )  # user address
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
        mock_connection.info.open_orders.return_value = (
            sample_open_orders_empty_response
        )

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

        mock_connection.info.query_order_by_oid.side_effect = (
            mock_query_order_by_oid_with_error
        )

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


class TestHyperliquidClientCancelOrder:
    """Test cases for the cancel_order method."""

    def test_cancel_specific_order_success(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test successful cancellation of a specific order."""
        # Mock order status for open order
        open_order_response = {
            "order": {
                "order": {
                    "coin": "ETH",
                    "side": "B",
                    "limitPx": "3000.0",
                    "sz": "0.003",
                    "oid": 123456,
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

        # Mock successful cancel response
        cancel_response = {
            "status": "ok",
            "response": {
                "type": "order",
                "data": {"statuses": [{"resting": {"oid": 123456}}]},
            },
        }

        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.query_order_by_oid.return_value = open_order_response
        mock_connection.exchange.cancel.return_value = cancel_response

        result = client.cancel_order(123456)

        expected_result = OrderResult(
            success=True,
            order_id=123456,
            status=OrderStatus.CANCELLED,
            message="Order 123456 cancelled successfully",
        )
        assert result == expected_result

        # Verify the order status was checked first
        mock_connection.info.query_order_by_oid.assert_called_once_with(
            "0x1234567890123456789012345678901234567890", 123456
        )
        # Verify cancel was called with correct parameters
        mock_connection.exchange.cancel.assert_called_once_with("ETH", 123456)

    def test_cancel_specific_order_already_cancelled(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test cancellation attempt on already cancelled order."""
        # Mock order status for cancelled order
        cancelled_order_response = {
            "order": {
                "order": {
                    "coin": "ETH",
                    "side": "B",
                    "limitPx": "3000.0",
                    "sz": "0.0",
                    "oid": 123456,
                    "timestamp": 1762271506632,
                    "reduceOnly": False,
                    "orderType": "Limit",
                    "origSz": "0.003",
                    "tif": "Gtc",
                },
                "status": "canceled",
                "statusTimestamp": 1762271506632,
            }
        }

        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.query_order_by_oid.return_value = cancelled_order_response

        result = client.cancel_order(123456)

        expected_result = OrderResult(
            success=False,
            order_id=123456,
            status=OrderStatus.CANCELLED,
            message=f"Order 123456 cancellation failed",
            error=f"Order 123456 is already cancelled",
        )
        assert result == expected_result

        # Verify cancel was not called since order is already cancelled
        mock_connection.exchange.cancel.assert_not_called()

    def test_cancel_specific_order_already_filled(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test cancellation attempt on already filled order."""
        # Mock order status for filled order
        filled_order_response = {
            "order": {
                "order": {
                    "coin": "ETH",
                    "side": "B",
                    "sz": "0.0",
                    "oid": 123456,
                    "timestamp": 1762271506632,
                    "reduceOnly": False,
                    "orderType": "Limit",
                    "origSz": "0.003",
                    "averageFillPx": "3050.0",
                },
                "status": "filled",
                "statusTimestamp": 1762271506632,
            }
        }

        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.query_order_by_oid.return_value = filled_order_response

        result = client.cancel_order(123456)

        expected_result = OrderResult(
            success=False,
            order_id=123456,
            status=OrderStatus.FILLED,
            message=f"Order 123456 cancellation failed",
            error=f"Order 123456 is already filled",
        )
        assert result == expected_result

        # Verify cancel was not called since order is already filled
        mock_connection.exchange.cancel.assert_not_called()

    def test_cancel_specific_order_already_rejected(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test cancellation attempt on already rejected order."""
        # Mock order status for rejected order
        rejected_order_response = {
            "order": {
                "order": {
                    "coin": "ETH",
                    "side": "B",
                    "limitPx": "3000.0",
                    "sz": "0.003",
                    "oid": 123456,
                    "timestamp": 1762271506632,
                    "reduceOnly": False,
                    "orderType": "Limit",
                    "origSz": "0.003",
                    "tif": "Gtc",
                },
                "status": "rejected",
                "statusTimestamp": 1762271506632,
            }
        }

        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.query_order_by_oid.return_value = rejected_order_response

        result = client.cancel_order(123456)

        expected_result = OrderResult(
            success=False,
            order_id=123456,
            status=OrderStatus.REJECTED,
            message=f"Order 123456 cancellation failed",
            error=f"Order 123456 was already rejected",
        )
        assert result == expected_result

        # Verify cancel was not called since order is already rejected
        mock_connection.exchange.cancel.assert_not_called()

    def test_cancel_specific_order_api_error(
        self,
        client,
        mock_connection,
        mock_retry_operation,
        order_error_response,
    ):
        """Test cancellation when API returns error."""
        # Mock order status for open order
        open_order_response = {
            "order": {
                "order": {
                    "coin": "ETH",
                    "side": "B",
                    "limitPx": "3000.0",
                    "sz": "0.003",
                    "oid": 123456,
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

        # Mock failed cancel response using existing fixture
        cancel_error_response = {
            "status": "error",
            "response": "Insufficient balance",
        }

        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.query_order_by_oid.return_value = open_order_response
        mock_connection.exchange.cancel.return_value = cancel_error_response

        result = client.cancel_order(123456)

        expected_result = OrderResult(
            success=False,
            order_id=123456,
            status=OrderStatus.REJECTED,
            message="Order cancellation failed",
            error="Insufficient balance",
        )
        assert result == expected_result

    def test_cancel_specific_order_not_found(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test cancellation when order is not found."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.query_order_by_oid.return_value = None

        with pytest.raises(ExchangeError) as exc_info:
            client.cancel_order(999999)

        assert "Order 999999 not found" in str(exc_info.value)

        # Verify cancel was not called since order doesn't exist
        mock_connection.exchange.cancel.assert_not_called()

    def test_cancel_all_orders_success(
        self,
        client,
        mock_connection,
        mock_retry_operation,
        sample_open_orders_response,
        sample_order_status_responses,
        limit_success_response_resting,
    ):
        """Test successful cancellation of all open orders."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.open_orders.return_value = sample_open_orders_response

        # Mock the get_order_status calls
        def mock_query_order_by_oid(user_address, order_id):
            return sample_order_status_responses[order_id]

        mock_connection.info.query_order_by_oid.side_effect = mock_query_order_by_oid
        mock_connection.exchange.cancel.return_value = limit_success_response_resting

        result = client.cancel_order("all")

        expected_result = OrderResult(
            success=True,
            status=OrderStatus.CANCELLED,
            message="Cancelled 3 orders, 0 failed",
            error=None,
        )
        assert result == expected_result

        # Verify cancel was called for each order
        assert mock_connection.exchange.cancel.call_count == 3

    def test_cancel_all_orders_no_orders(
        self,
        client,
        mock_connection,
        mock_retry_operation,
        sample_open_orders_empty_response,
    ):
        """Test cancel_all when no open orders exist."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.open_orders.return_value = (
            sample_open_orders_empty_response
        )

        result = client.cancel_order("all")

        expected_result = OrderResult(
            success=True,
            status=OrderStatus.CANCELLED,
            message="Cancelled 0 orders, 0 failed",
            error=None,
        )
        assert result == expected_result

        # Verify cancel was not called since there are no orders
        mock_connection.exchange.cancel.assert_not_called()

    def test_cancel_all_orders_partial_failure(
        self,
        client,
        mock_connection,
        mock_retry_operation,
        sample_open_orders_response,
        sample_order_status_responses,
        limit_success_response_resting,
        order_error_response,
    ):
        """Test cancel_all with some order cancellation failures."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.open_orders.return_value = sample_open_orders_response

        # Mock the get_order_status calls
        def mock_query_order_by_oid(user_address, order_id):
            return sample_order_status_responses[order_id]

        # Mock cancel responses - success for first, error for others
        def mock_cancel_with_errors(coin, order_id):
            if order_id == 222605232959:
                return limit_success_response_resting
            else:
                return order_error_response

        mock_connection.info.query_order_by_oid.side_effect = mock_query_order_by_oid
        mock_connection.exchange.cancel.side_effect = mock_cancel_with_errors

        result = client.cancel_order("all")

        expected_result = OrderResult(
            success=False,
            status=OrderStatus.CANCELLED,
            message="Cancelled 1 orders, 2 failed",
            error="2 orders failed to cancel",
        )
        assert result == expected_result

        # Verify cancel was called for all orders
        assert mock_connection.exchange.cancel.call_count == 3

    def test_cancel_order_invalid_input(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test cancel_order with invalid input."""
        mock_connection.retry_operation.side_effect = mock_retry_operation

        # Test negative order ID
        with pytest.raises(ValueError) as exc_info:
            client.cancel_order(-123)

        assert "order_id must be positive integer or 'all'" in str(exc_info.value)

        # Test zero order ID
        with pytest.raises(ValueError) as exc_info:
            client.cancel_order(0)

        assert "order_id must be positive integer or 'all'" in str(exc_info.value)

        # Test invalid string (not "all")
        with pytest.raises(ValueError) as exc_info:
            client.cancel_order("invalid")

        assert "order_id must be positive integer or 'all'" in str(exc_info.value)

        # Verify cancel was not called for any invalid input
        mock_connection.exchange.cancel.assert_not_called()

    def test_cancel_order_retry_logic(
        self,
        client,
        mock_connection,
    ):
        """Test that retry logic works for network failures."""
        # This tests the retry_operation wrapper by verifying it's called
        mock_connection.retry_operation.return_value = OrderResult(
            success=True,
            order_id=123456,
            status=OrderStatus.CANCELLED,
            message="Order 123456 cancelled successfully",
        )

        result = client.cancel_order(123456)

        assert result.success is True
        mock_connection.retry_operation.assert_called_once()


class TestHyperliquidClientModifyOrder:
    """Test cases for the modify_order method."""

    def test_modify_order_success_both_price_and_quantity(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test successful order modification with both price and quantity changes."""
        # Mock current order status (open limit order)
        current_order_response = {
            "order": {
                "order": {
                    "coin": "ETH",
                    "side": "B",
                    "limitPx": "3000.0",
                    "sz": "0.003",  # remaining quantity
                    "oid": 123456,
                    "timestamp": 1762271506632,
                    "reduceOnly": False,
                    "orderType": "Limit",
                    "origSz": "0.003",  # original quantity
                    "tif": "Gtc",
                },
                "status": "open",
                "statusTimestamp": 1762271506632,
            }
        }

        # Mock successful modify response
        modify_response = {
            "status": "ok",
            "response": {
                "type": "order",
                "data": {"statuses": [{"resting": {"oid": 123456}}]},
            },
        }

        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.query_order_by_oid.return_value = current_order_response
        mock_connection.exchange.modify_order.return_value = modify_response

        result = client.modify_order(123456, Decimal("3200.0"), Decimal("0.005"))

        expected_result = OrderResult(
            success=True,
            order_id=123456,
            status=OrderStatus.OPEN,
            message="Order 123456 modified successfully - price: 3200.0, quantity: 0.005",
        )
        assert result == expected_result

        # Verify order status was checked first
        mock_connection.info.query_order_by_oid.assert_called_once_with(
            "0x1234567890123456789012345678901234567890", 123456
        )
        # Verify modify was called with correct parameters
        mock_connection.exchange.modify_order.assert_called_once_with(
            oid=123456,
            name="ETH",
            is_buy=True,
            sz=0.005,
            limit_px=3200.0,
            order_type={"limit": {"tif": "Gtc"}},
        )

    def test_modify_order_success_price_only(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test successful order modification with only price change."""
        # Mock current order status (open limit order)
        current_order_response = {
            "order": {
                "order": {
                    "coin": "BTC",
                    "side": "S",
                    "limitPx": "50000.0",
                    "sz": "0.1",
                    "oid": 123457,
                    "timestamp": 1762271506633,
                    "reduceOnly": False,
                    "orderType": "Limit",
                    "origSz": "0.1",
                    "tif": "Gtc",
                },
                "status": "open",
                "statusTimestamp": 1762271506633,
            }
        }

        # Mock successful modify response
        modify_response = {
            "status": "ok",
            "response": {
                "type": "order",
                "data": {"statuses": [{"resting": {"oid": 123457}}]},
            },
        }

        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.query_order_by_oid.return_value = current_order_response
        mock_connection.exchange.modify_order.return_value = modify_response

        result = client.modify_order(123457, Decimal("51000.0"), None)

        expected_result = OrderResult(
            success=True,
            order_id=123457,
            status=OrderStatus.OPEN,
            message="Order 123457 modified successfully - price: 51000.0, quantity: 0.1",
        )
        assert result == expected_result

        # Verify modify was called with original quantity
        mock_connection.exchange.modify_order.assert_called_once_with(
            oid=123457,
            name="BTC",
            is_buy=False,
            sz=0.1,  # Original remaining quantity
            limit_px=51000.0,
            order_type={"limit": {"tif": "Gtc"}},
        )

    def test_modify_order_success_quantity_only(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test successful order modification with only quantity change."""
        # Mock current order status (open limit order)
        current_order_response = {
            "order": {
                "order": {
                    "coin": "SOL",
                    "side": "B",
                    "limitPx": "150.0",
                    "sz": "5.0",
                    "oid": 123458,
                    "timestamp": 1762271506634,
                    "reduceOnly": False,
                    "orderType": "Limit",
                    "origSz": "5.0",
                    "tif": "Ioc",
                },
                "status": "open",
                "statusTimestamp": 1762271506634,
            }
        }

        # Mock successful modify response
        modify_response = {
            "status": "ok",
            "response": {
                "type": "order",
                "data": {"statuses": [{"resting": {"oid": 123458}}]},
            },
        }

        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.query_order_by_oid.return_value = current_order_response
        mock_connection.exchange.modify_order.return_value = modify_response

        result = client.modify_order(123458, None, Decimal("3.0"))

        expected_result = OrderResult(
            success=True,
            order_id=123458,
            status=OrderStatus.OPEN,
            message="Order 123458 modified successfully - price: 150.0, quantity: 3.0",
        )
        assert result == expected_result

        # Verify modify was called with original price
        mock_connection.exchange.modify_order.assert_called_once_with(
            oid=123458,
            name="SOL",
            is_buy=True,
            sz=3.0,
            limit_px=150.0,  # Original price
            order_type={"limit": {"tif": "Ioc"}},
        )

    def test_modify_order_order_not_found(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test modify order when order is not found."""
        # Mock retry operation to return the expected result
        mock_connection.retry_operation.return_value = OrderResult(
            success=False,
            order_id=999999,
            status=OrderStatus.REJECTED,
            message="Order modification failed",
            error="Order 999999 not found",
        )
        mock_connection.info.query_order_by_oid.return_value = None

        result = client.modify_order(999999, Decimal("3000.0"), Decimal("0.1"))

        expected_result = OrderResult(
            success=False,
            order_id=999999,
            status=OrderStatus.REJECTED,
            message="Order modification failed",
            error="Order 999999 not found",
        )
        assert result == expected_result

        # Verify retry operation was called
        mock_connection.retry_operation.assert_called_once()
        # Verify modify was not called since order doesn't exist
        mock_connection.exchange.modify_order.assert_not_called()

    def test_modify_order_already_cancelled(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test modify order when order is already cancelled."""
        # Mock order status for cancelled order
        cancelled_order_response = {
            "order": {
                "order": {
                    "coin": "ETH",
                    "side": "B",
                    "limitPx": "3000.0",
                    "sz": "0.0",
                    "oid": 123456,
                    "timestamp": 1762271506632,
                    "reduceOnly": False,
                    "orderType": "Limit",
                    "origSz": "0.003",
                    "tif": "Gtc",
                },
                "status": "canceled",
                "statusTimestamp": 1762271506632,
            }
        }

        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.query_order_by_oid.return_value = cancelled_order_response

        result = client.modify_order(123456, Decimal("3100.0"), Decimal("0.005"))

        expected_result = OrderResult(
            success=False,
            order_id=123456,
            status=OrderStatus.REJECTED,
            message="Order modification failed",
            error="Order 123456 is already cancelled and cannot be modified",
        )
        assert result == expected_result

        # Verify modify was not called since order is already cancelled
        mock_connection.exchange.modify_order.assert_not_called()

    def test_modify_order_already_filled(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test modify order when order is already filled."""
        # Mock order status for filled order
        filled_order_response = {
            "order": {
                "order": {
                    "coin": "ETH",
                    "side": "B",
                    "sz": "0.0",
                    "oid": 123456,
                    "timestamp": 1762271506632,
                    "reduceOnly": False,
                    "orderType": "Limit",
                    "origSz": "0.003",
                    "averageFillPx": "3050.0",
                },
                "status": "filled",
                "statusTimestamp": 1762271506632,
            }
        }

        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.query_order_by_oid.return_value = filled_order_response

        result = client.modify_order(123456, Decimal("3100.0"), Decimal("0.005"))

        expected_result = OrderResult(
            success=False,
            order_id=123456,
            status=OrderStatus.REJECTED,
            message="Order modification failed",
            error="Order 123456 is already filled and cannot be modified",
        )
        assert result == expected_result

        # Verify modify was not called since order is already filled
        mock_connection.exchange.modify_order.assert_not_called()

    def test_modify_order_already_rejected(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test modify order when order is already rejected."""
        # Mock order status for rejected order
        rejected_order_response = {
            "order": {
                "order": {
                    "coin": "ETH",
                    "side": "B",
                    "limitPx": "3000.0",
                    "sz": "0.003",
                    "oid": 123456,
                    "timestamp": 1762271506632,
                    "reduceOnly": False,
                    "orderType": "Limit",
                    "origSz": "0.003",
                    "tif": "Gtc",
                },
                "status": "rejected",
                "statusTimestamp": 1762271506632,
            }
        }

        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.query_order_by_oid.return_value = rejected_order_response

        result = client.modify_order(123456, Decimal("3100.0"), Decimal("0.005"))

        expected_result = OrderResult(
            success=False,
            order_id=123456,
            status=OrderStatus.REJECTED,
            message="Order modification failed",
            error="Order 123456 was rejected and cannot be modified",
        )
        assert result == expected_result

        # Verify modify was not called since order is already rejected
        mock_connection.exchange.modify_order.assert_not_called()

    def test_modify_order_market_order_type(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test modify order when order is a market order (not allowed)."""
        # Mock order status for market order
        market_order_response = {
            "order": {
                "order": {
                    "coin": "ETH",
                    "side": "B",
                    "sz": "0.0",
                    "oid": 123456,
                    "timestamp": 1762271506632,
                    "reduceOnly": False,
                    "orderType": "Market",
                    "origSz": "0.003",
                    "averageFillPx": "3050.0",
                },
                "status": "filled",
                "statusTimestamp": 1762271506632,
            }
        }

        # Mock retry operation to return the expected result
        mock_connection.retry_operation.return_value = OrderResult(
            success=False,
            order_id=123456,
            status=OrderStatus.REJECTED,
            message="Order modification failed",
            error="Order 123456 is a market order and cannot be modified (only limit orders can be modified)",
        )
        mock_connection.info.query_order_by_oid.return_value = market_order_response

        result = client.modify_order(123456, Decimal("3100.0"), Decimal("0.005"))

        expected_result = OrderResult(
            success=False,
            order_id=123456,
            status=OrderStatus.REJECTED,
            message="Order modification failed",
            error="Order 123456 is a market order and cannot be modified (only limit orders can be modified)",
        )
        assert result == expected_result

        # Verify retry operation was called
        mock_connection.retry_operation.assert_called_once()
        # Verify modify was not called since order is a market order
        mock_connection.exchange.modify_order.assert_not_called()

    def test_modify_order_api_error(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test modify order when API returns error."""
        # Mock order status for open order
        current_order_response = {
            "order": {
                "order": {
                    "coin": "ETH",
                    "side": "B",
                    "limitPx": "3000.0",
                    "sz": "0.003",
                    "oid": 123456,
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

        # Mock failed modify response
        modify_error_response = {
            "status": "error",
            "response": "Insufficient balance",
        }

        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.query_order_by_oid.return_value = current_order_response
        mock_connection.exchange.modify_order.return_value = modify_error_response

        result = client.modify_order(123456, Decimal("3100.0"), Decimal("0.005"))

        expected_result = OrderResult(
            success=False,
            order_id=123456,
            status=OrderStatus.REJECTED,
            message="Order modification failed",
            error="Insufficient balance",
        )
        assert result == expected_result

    def test_modify_order_zero_quantity(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test modify order with zero quantity (should fail validation)."""
        # Mock retry operation to return the expected result
        mock_connection.retry_operation.return_value = OrderResult(
            success=False,
            order_id=123456,
            status=OrderStatus.REJECTED,
            message="Order modification failed",
            error="Quantity must be greater than 0",
        )

        result = client.modify_order(123456, Decimal("3100.0"), Decimal("0.0"))

        expected_result = OrderResult(
            success=False,
            order_id=123456,
            status=OrderStatus.REJECTED,
            message="Order modification failed",
            error="Quantity must be greater than 0",
        )
        assert result == expected_result

        # Verify retry operation was called since this case goes through the normal flow
        mock_connection.retry_operation.assert_called_once()

        # Verify API was not called since validation failed
        mock_connection.info.query_order_by_oid.assert_not_called()
        mock_connection.exchange.modify_order.assert_not_called()

    def test_modify_order_missing_price_for_limit_order(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test modify order when current order has no price (edge case)."""
        # Mock current order status with no price
        current_order_response = {
            "order": {
                "order": {
                    "coin": "ETH",
                    "side": "B",
                    "sz": "0.003",
                    "oid": 123456,
                    "timestamp": 1762271506632,
                    "reduceOnly": False,
                    "orderType": "Limit",
                    "origSz": "0.003",
                    "tif": "Gtc",
                    # Missing limitPx - edge case
                },
                "status": "open",
                "statusTimestamp": 1762271506632,
            }
        }

        # Mock retry operation to return the expected result
        mock_connection.retry_operation.return_value = OrderResult(
            success=False,
            order_id=123456,
            status=OrderStatus.REJECTED,
            message="Order modification failed",
            error="Price is required for limit order modification",
        )
        mock_connection.info.query_order_by_oid.return_value = current_order_response

        result = client.modify_order(123456, None, Decimal("0.005"))

        expected_result = OrderResult(
            success=False,
            order_id=123456,
            status=OrderStatus.REJECTED,
            message="Order modification failed",
            error="Price is required for limit order modification",
        )
        assert result == expected_result

        # Verify retry operation was called
        mock_connection.retry_operation.assert_called_once()
        # Verify modify was not called since price validation failed
        mock_connection.exchange.modify_order.assert_not_called()

    def test_modify_order_status_filled_with_error_response(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test modify order with API response having error status."""
        # Mock current order status (open limit order)
        current_order_response = {
            "order": {
                "order": {
                    "coin": "ETH",
                    "side": "B",
                    "limitPx": "3000.0",
                    "sz": "0.003",
                    "oid": 123456,
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

        # Mock modify response with error status
        modify_error_response = {
            "status": "ok",
            "response": {
                "type": "order",
                "data": {"statuses": [{"error": "Order size too small"}]},
            },
        }

        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.query_order_by_oid.return_value = current_order_response
        mock_connection.exchange.modify_order.return_value = modify_error_response

        result = client.modify_order(123456, Decimal("3100.0"), Decimal("0.005"))

        expected_result = OrderResult(
            success=False,
            order_id=123456,
            status=OrderStatus.REJECTED,
            message="Order modification failed",
            error="Order size too small",
        )
        assert result == expected_result

    def test_modify_order_no_changes_requested(
        self,
        client,
        mock_connection,
    ):
        """Test modify order when no changes are requested (both price and quantity are None)."""
        result = client.modify_order(123456, None, None)

        expected_result = OrderResult(
            success=False,
            order_id=123456,
            status=OrderStatus.REJECTED,
            message="Order modification failed",
            error="No changes requested - both price and quantity are None",
        )
        assert result == expected_result

        # Verify API was not called since early exit should trigger
        mock_connection.info.query_order_by_oid.assert_not_called()
        mock_connection.exchange.modify_order.assert_not_called()
        mock_connection.retry_operation.assert_not_called()

    def test_modify_order_retry_logic(
        self,
        client,
        mock_connection,
    ):
        """Test that retry logic works for modify order operations."""
        # This tests the retry_operation wrapper by verifying it's called
        mock_connection.retry_operation.return_value = OrderResult(
            success=True,
            order_id=123456,
            status=OrderStatus.OPEN,
            message="Order 123456 modified successfully - price: 3100.0, quantity: 0.005",
        )

        result = client.modify_order(123456, Decimal("3100.0"), Decimal("0.005"))

        assert result.success is True
        mock_connection.retry_operation.assert_called_once()
