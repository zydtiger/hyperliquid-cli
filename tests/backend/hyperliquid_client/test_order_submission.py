"""
Test cases for HyperliquidClient order submission functionality.

This module provides comprehensive tests for market order submission,
limit order submission, and other order creation operations.
"""

import pytest
from decimal import Decimal
from unittest.mock import patch

from backend.exchange.hyperliquid_client import HyperliquidClient
from models.order import (
    LimitOrder,
    OrderResult,
    OrderSide,
    OrderStatus,
    OrderTif,
)


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
