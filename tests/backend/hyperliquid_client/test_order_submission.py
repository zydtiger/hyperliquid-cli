"""
Test cases for HyperliquidClient order submission functionality.

This module provides comprehensive tests for market order submission,
limit order submission, and other order creation operations.
"""

from decimal import Decimal
from unittest.mock import patch

from backend.exchange.hyperliquid_client import HyperliquidClient
from models.order import (
    LimitOrder,
    MarketOrder,
    OrderResult,
    OrderSide,
    OrderStatus,
    OrderTif,
    OrderTrigger,
    TriggerType,
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

        # Mock the market_open method
        client.connection.exchange.market_open.return_value = market_success_response_resting  # type: ignore[attr-defined]

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
        client.connection.exchange.market_open.assert_called_once_with(  # type: ignore[attr-defined]
            name="BTC",
            is_buy=False,
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

    def test_submit_market_order_with_stop_trigger_uses_trigger_order(
        self,
        client,
        mock_config_with_slippage,
        market_success_response_resting,
        mock_retry_operation,
    ):
        """Test trigger market stop order submission uses exchange.order."""
        with patch(
            "backend.exchange.hyperliquid_client.HyperliquidConnection",
            return_value=client.connection,
        ):
            client = HyperliquidClient(mock_config_with_slippage)

        order = MarketOrder(
            coin="ETH",
            side=OrderSide.SELL,
            quantity=Decimal("0.02"),
            reduce_only=True,
            trigger=OrderTrigger(
                trigger_type=TriggerType.STOP,
                trigger_price=Decimal("1000"),
            ),
        )

        client.connection.exchange._slippage_price.return_value = 995.5  # type: ignore[attr-defined]
        client.connection.exchange.order.return_value = market_success_response_resting  # type: ignore[attr-defined]
        client.connection.retry_operation.side_effect = mock_retry_operation  # type: ignore[attr-defined]

        result = client.submit_market_order(order)

        assert result == OrderResult(
            success=True,
            order_id=123456789,
            status=OrderStatus.OPEN,
            message="Market order is resting on the book",
        )
        client.connection.exchange.market_open.assert_not_called()  # type: ignore[attr-defined]
        client.connection.exchange.market_close.assert_not_called()  # type: ignore[attr-defined]
        client.connection.exchange._slippage_price.assert_called_once_with(  # type: ignore[attr-defined]
            "ETH",
            False,
            0.01,
            None,
        )
        client.connection.exchange.order.assert_called_once_with(  # type: ignore[attr-defined]
            name="ETH",
            is_buy=False,
            sz=0.02,
            limit_px=995.5,
            order_type={
                "trigger": {
                    "triggerPx": 1000.0,
                    "isMarket": True,
                    "tpsl": "sl",
                }
            },
            reduce_only=True,
        )

    def test_submit_market_order_with_take_trigger_error_response(
        self,
        client,
        mock_config_with_slippage,
        order_error_response,
        mock_retry_operation,
    ):
        """Test trigger market take order error handling."""
        with patch(
            "backend.exchange.hyperliquid_client.HyperliquidConnection",
            return_value=client.connection,
        ):
            client = HyperliquidClient(mock_config_with_slippage)

        order = MarketOrder(
            coin="BTC",
            side=OrderSide.BUY,
            quantity=Decimal("0.05"),
            reduce_only=False,
            trigger=OrderTrigger(
                trigger_type=TriggerType.TAKE,
                trigger_price=Decimal("101000"),
            ),
        )

        client.connection.exchange._slippage_price.return_value = 101500.0  # type: ignore[attr-defined]
        client.connection.exchange.order.return_value = order_error_response  # type: ignore[attr-defined]
        client.connection.retry_operation.side_effect = mock_retry_operation  # type: ignore[attr-defined]

        result = client.submit_market_order(order)

        assert result == OrderResult(
            success=False,
            order_id=None,
            status=OrderStatus.REJECTED,
            message="Market order failed",
            error="Insufficient balance",
        )
        client.connection.exchange.order.assert_called_once()  # type: ignore[attr-defined]

    def test_submit_market_order_trigger_without_statuses_returns_fallback(
        self,
        client,
        mock_config_with_slippage,
        mock_retry_operation,
    ):
        """Test trigger market order malformed response fallback."""
        with patch(
            "backend.exchange.hyperliquid_client.HyperliquidConnection",
            return_value=client.connection,
        ):
            client = HyperliquidClient(mock_config_with_slippage)

        order = MarketOrder(
            coin="ETH",
            side=OrderSide.BUY,
            quantity=Decimal("0.01"),
            reduce_only=False,
            trigger=OrderTrigger(
                trigger_type=TriggerType.STOP,
                trigger_price=Decimal("2500"),
            ),
        )

        client.connection.exchange._slippage_price.return_value = 2525.0  # type: ignore[attr-defined]
        client.connection.exchange.order.return_value = {"status": "ok", "response": {"data": {}}}  # type: ignore[attr-defined]
        client.connection.retry_operation.side_effect = mock_retry_operation  # type: ignore[attr-defined]

        result = client.submit_market_order(order)

        assert result == OrderResult(
            success=False,
            order_id=None,
            status=OrderStatus.REJECTED,
            message="Market order submission failed - no status returned",
            error="Unknown response structure",
        )


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
        _args, kwargs = client.connection.exchange.order.call_args
        assert kwargs["is_buy"] is True

        # Reset mock
        client.connection.exchange.order.reset_mock()

        # Test SELL side
        sell_order = sample_limit_sell_order

        client.submit_limit_order(sell_order)

        # Verify SELL side maps to is_buy=False
        _args, kwargs = client.connection.exchange.order.call_args
        assert kwargs["is_buy"] is False

    def test_submit_limit_order_with_stop_trigger_uses_trigger_payload(
        self,
        client,
        limit_success_response_resting,
        mock_retry_operation,
    ):
        """Test trigger limit stop order uses trigger order_type and ignores TIF."""
        order = LimitOrder(
            coin="ETH",
            side=OrderSide.SELL,
            quantity=Decimal("0.02"),
            price=Decimal("800"),
            reduce_only=True,
            time_in_force=OrderTif.ALO,
            trigger=OrderTrigger(
                trigger_type=TriggerType.STOP,
                trigger_price=Decimal("1000"),
            ),
        )

        client.connection.exchange.order.return_value = limit_success_response_resting
        client.connection.retry_operation.side_effect = mock_retry_operation

        result = client.submit_limit_order(order)

        assert result == OrderResult(
            success=True,
            order_id=987654321,
            status=OrderStatus.OPEN,
            message="Limit order is resting on the book",
        )
        client.connection.exchange.order.assert_called_once_with(
            name="ETH",
            is_buy=False,
            sz=0.02,
            limit_px=800.0,
            order_type={
                "trigger": {
                    "triggerPx": 1000.0,
                    "isMarket": False,
                    "tpsl": "sl",
                }
            },
            reduce_only=True,
        )

    def test_submit_limit_order_with_take_trigger_filled_success(
        self,
        client,
        limit_success_response_filled,
        mock_retry_operation,
    ):
        """Test trigger limit take order filled response."""
        order = LimitOrder(
            coin="ETH",
            side=OrderSide.BUY,
            quantity=Decimal("0.1"),
            price=Decimal("3000"),
            reduce_only=False,
            time_in_force=OrderTif.IOC,
            trigger=OrderTrigger(
                trigger_type=TriggerType.TAKE,
                trigger_price=Decimal("3500"),
            ),
        )

        client.connection.exchange.order.return_value = limit_success_response_filled
        client.connection.retry_operation.side_effect = mock_retry_operation

        result = client.submit_limit_order(order)

        assert result == OrderResult(
            success=True,
            order_id=987654322,
            status=OrderStatus.FILLED,
            message="Limit order filled 0.05 at 51000.0",
        )
        _args, kwargs = client.connection.exchange.order.call_args
        assert kwargs["order_type"] == {
            "trigger": {
                "triggerPx": 3500.0,
                "isMarket": False,
                "tpsl": "tp",
            }
        }

    def test_submit_limit_order_trigger_without_statuses_returns_fallback(
        self,
        client,
        mock_retry_operation,
    ):
        """Test trigger limit order malformed response fallback."""
        order = LimitOrder(
            coin="ETH",
            side=OrderSide.BUY,
            quantity=Decimal("0.1"),
            price=Decimal("3000"),
            reduce_only=False,
            time_in_force=OrderTif.GTC,
            trigger=OrderTrigger(
                trigger_type=TriggerType.STOP,
                trigger_price=Decimal("2500"),
            ),
        )

        client.connection.exchange.order.return_value = {"status": "ok", "response": {"data": {}}}
        client.connection.retry_operation.side_effect = mock_retry_operation

        result = client.submit_limit_order(order)

        assert result == OrderResult(
            success=False,
            order_id=None,
            status=OrderStatus.REJECTED,
            message="Limit order submission failed - no status returned",
            error="Unknown response structure",
        )
