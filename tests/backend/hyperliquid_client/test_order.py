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
        market_success_response,
        mock_retry_operation,
    ):
        """Test successful market buy order submission."""
        # Re-create client with config that has slippage
        with patch(
            "backend.exchange.hyperliquid_client.HyperliquidConnection",
            return_value=client.connection,
        ):
            client = HyperliquidClient(mock_config_with_slippage)

        # Mock the market_open method
        client.connection.exchange.market_open.return_value = market_success_response  # type: ignore[attr-defined]

        client.connection.retry_operation.side_effect = mock_retry_operation  # type: ignore[attr-defined]

        result = client.submit_market_order(sample_market_buy_order)

        # Verify result
        expected_result = OrderResult(
            success=True,
            order_id=123456789,
            status=OrderStatus.OPEN,
            message="Market order submitted successfully",
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

    def test_submit_market_order_sell_success(
        self,
        client,
        mock_config_with_slippage,
        sample_market_sell_order,
        market_success_response,
        mock_retry_operation,
    ):
        """Test successful market sell order submission."""
        # Re-create client with config that has slippage
        with patch(
            "backend.exchange.hyperliquid_client.HyperliquidConnection",
            return_value=client.connection,
        ):
            client = HyperliquidClient(mock_config_with_slippage)

        # Mock the market_close method
        client.connection.exchange.market_close.return_value = market_success_response  # type: ignore[attr-defined]

        client.connection.retry_operation.side_effect = mock_retry_operation  # type: ignore[attr-defined]

        result = client.submit_market_order(sample_market_sell_order)

        # Verify result
        expected_result = OrderResult(
            success=True,
            order_id=123456789,
            status=OrderStatus.OPEN,
            message="Market order submitted successfully",
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
        market_error_response,
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
        client.connection.exchange.market_open.return_value = market_error_response  # type: ignore[attr-defined]

        client.connection.retry_operation.side_effect = mock_retry_operation  # type: ignore[attr-defined]aaaaz

        result = client.submit_market_order(sample_market_buy_order)

        # Verify result
        expected_result = OrderResult(
            success=False,
            order_id=None,
            status=OrderStatus.REJECTED,
            message="Market order submission failed",
            error="Insufficient balance",
        )
        assert result == expected_result


class TestHyperliquidClientSubmitLimitOrder:
    """Test cases for the submit_limit_order method."""

    def test_submit_limit_order_buy_success(
        self,
        client,
        sample_limit_buy_order,
        limit_success_response,
        mock_retry_operation,
    ):
        """Test successful limit buy order submission."""
        # Mock the order method
        client.connection.exchange.order.return_value = limit_success_response

        client.connection.retry_operation.side_effect = mock_retry_operation

        result = client.submit_limit_order(sample_limit_buy_order)

        # Verify result
        expected_result = OrderResult(
            success=True,
            order_id=987654321,
            status=OrderStatus.OPEN,
            message="Limit order submitted successfully",
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

    def test_submit_limit_order_sell_success(
        self,
        client,
        sample_limit_sell_order,
        limit_success_response,
        mock_retry_operation,
    ):
        """Test successful limit sell order submission."""
        # Mock the order method
        client.connection.exchange.order.return_value = limit_success_response

        client.connection.retry_operation.side_effect = mock_retry_operation

        result = client.submit_limit_order(sample_limit_sell_order)

        # Verify result
        expected_result = OrderResult(
            success=True,
            order_id=987654321,
            status=OrderStatus.OPEN,
            message="Limit order submitted successfully",
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
        limit_success_response,
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

        client.connection.exchange.order.return_value = limit_success_response
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
        limit_error_response,
        mock_retry_operation,
    ):
        """Test limit order submission when API returns error status."""
        # Mock the order method to return error
        client.connection.exchange.order.return_value = limit_error_response

        client.connection.retry_operation.side_effect = mock_retry_operation

        result = client.submit_limit_order(sample_limit_buy_order)

        # Verify result
        expected_result = OrderResult(
            success=False,
            order_id=None,
            status=OrderStatus.REJECTED,
            message="Limit order submission failed",
            error="Insufficient margin",
        )
        assert result == expected_result

    def test_submit_limit_order_side_parameter_mapping(
        self,
        client,
        sample_limit_buy_order,
        sample_limit_sell_order,
        limit_success_response,
        mock_retry_operation,
    ):
        """Test that order side is correctly mapped to is_buy parameter."""
        # Test BUY side
        buy_order = sample_limit_buy_order

        client.connection.exchange.order.return_value = limit_success_response
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
