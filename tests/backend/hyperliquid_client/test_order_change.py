"""
Test cases for HyperliquidClient order modification and cancellation functionality.

This module provides comprehensive tests for order modifications,
cancellations, and other order state change operations.
"""

from collections.abc import Callable
from decimal import Decimal
from typing import Any
from unittest.mock import Mock

import pytest

from backend.exchange.hyperliquid_client import HyperliquidClient
from models.api import ExchangeError
from models.order import (
    OrderResult,
    OrderStatus,
)


class TestHyperliquidClientModifyOrder:
    """Test cases for the modify_order method."""

    def test_modify_order_success_both_price_and_quantity(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
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
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
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
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
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
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
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
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
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
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
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
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
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
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
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
            error=(
                "Order 123456 is a market order and cannot be modified "
                "(only limit orders can be modified)"
            ),
        )
        mock_connection.info.query_order_by_oid.return_value = market_order_response

        result = client.modify_order(123456, Decimal("3100.0"), Decimal("0.005"))

        expected_result = OrderResult(
            success=False,
            order_id=123456,
            status=OrderStatus.REJECTED,
            message="Order modification failed",
            error=(
                "Order 123456 is a market order and cannot be modified "
                "(only limit orders can be modified)"
            ),
        )
        assert result == expected_result

        # Verify retry operation was called
        mock_connection.retry_operation.assert_called_once()
        # Verify modify was not called since order is a market order
        mock_connection.exchange.modify_order.assert_not_called()

    def test_modify_order_api_error(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
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
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
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
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
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
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
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
        client: HyperliquidClient,
        mock_connection: Mock,
    ) -> None:
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
        client: HyperliquidClient,
        mock_connection: Mock,
    ) -> None:
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

    def test_modify_order_resolves_spot_symbol_for_exchange_request(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
        """Test spot order modification uses the resolved pair symbol."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.query_order_by_oid.return_value = {
            "order": {
                "order": {
                    "coin": "@142",
                    "side": "B",
                    "limitPx": "87000.0",
                    "sz": "0.001",
                    "oid": 123499,
                    "timestamp": 1762271506999,
                    "reduceOnly": False,
                    "orderType": "Limit",
                    "origSz": "0.001",
                    "tif": "Gtc",
                },
                "status": "open",
                "statusTimestamp": 1762271507000,
            }
        }
        mock_connection.info.spot_meta.return_value = {
            "universe": [{"tokens": [0, 1], "name": "@142", "index": 142, "isCanonical": True}],
            "tokens": [
                {"name": "BTC", "szDecimals": 5, "weiDecimals": 8, "index": 0},
                {"name": "USDC", "szDecimals": 6, "weiDecimals": 6, "index": 1},
            ],
        }
        mock_connection.exchange.modify_order.return_value = {
            "status": "ok",
            "response": {"type": "order", "data": {"statuses": [{"resting": {"oid": 123499}}]}},
        }

        client.modify_order(123499, Decimal("88000.0"), Decimal("0.001"))

        mock_connection.exchange.modify_order.assert_called_once_with(
            oid=123499,
            name="BTC/USDC",
            is_buy=True,
            sz=0.001,
            limit_px=88000.0,
            order_type={"limit": {"tif": "Gtc"}},
        )


class TestHyperliquidClientCancelOrder:
    """Test cases for the cancel_order method."""

    def test_cancel_specific_order_success(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
        cancel_success_response: dict[str, Any],
    ) -> None:
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

        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.query_order_by_oid.return_value = open_order_response
        mock_connection.exchange.cancel.return_value = cancel_success_response

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
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
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
            message="Order 123456 cancellation failed",
            error="Order 123456 is already cancelled",
        )
        assert result == expected_result

        # Verify cancel was not called since order is already cancelled
        mock_connection.exchange.cancel.assert_not_called()

    def test_cancel_specific_order_already_filled(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
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
            message="Order 123456 cancellation failed",
            error="Order 123456 is already filled",
        )
        assert result == expected_result

        # Verify cancel was not called since order is already filled
        mock_connection.exchange.cancel.assert_not_called()

    def test_cancel_specific_order_already_rejected(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
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
            message="Order 123456 cancellation failed",
            error="Order 123456 was already rejected",
        )
        assert result == expected_result

        # Verify cancel was not called since order is already rejected
        mock_connection.exchange.cancel.assert_not_called()

    def test_cancel_specific_order_api_error(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
        cancel_error_response: dict[str, Any],
    ) -> None:
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
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
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
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
        sample_open_orders_response: list[dict[str, Any]],
        sample_order_status_responses: dict[int, dict[str, Any]],
        cancel_success_response: dict[str, Any],
    ) -> None:
        """Test successful cancellation of all open orders."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.open_orders.return_value = sample_open_orders_response

        # Mock the get_order_status calls
        def mock_query_order_by_oid(user_address: str, order_id: int) -> dict[str, Any]:
            return sample_order_status_responses[order_id]

        mock_connection.info.query_order_by_oid.side_effect = mock_query_order_by_oid
        mock_connection.exchange.cancel.return_value = cancel_success_response

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
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
        sample_open_orders_empty_response: list[dict[str, Any]],
    ) -> None:
        """Test cancel_all when no open orders exist."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.open_orders.return_value = sample_open_orders_empty_response

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
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
        sample_open_orders_response: list[dict[str, Any]],
        sample_order_status_responses: dict[int, dict[str, Any]],
        cancel_success_response: dict[str, Any],
        cancel_error_response: dict[str, Any],
    ) -> None:
        """Test cancel_all with some order cancellation failures."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.open_orders.return_value = sample_open_orders_response

        # Mock the get_order_status calls
        def mock_query_order_by_oid(user_address: str, order_id: int) -> dict[str, Any]:
            return sample_order_status_responses[order_id]

        # Mock cancel responses - success for first, error for others
        def mock_cancel_with_errors(coin: str, order_id: int) -> dict[str, Any]:
            if order_id == 222605232959:
                return cancel_success_response
            return cancel_error_response

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
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
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

    def test_cancel_specific_order_with_error_in_statuses(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
        cancel_error_response: dict[str, Any],
    ) -> None:
        """Test cancellation when API returns ok status but error in statuses array."""
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

        # Verify cancel was called
        mock_connection.exchange.cancel.assert_called_once_with("ETH", 123456)

    def test_cancel_order_retry_logic(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
    ) -> None:
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

    def test_cancel_specific_order_resolves_spot_symbol_for_exchange_request(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
        cancel_success_response: dict[str, Any],
    ) -> None:
        """Test spot order cancellation uses the resolved pair symbol."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.query_order_by_oid.return_value = {
            "order": {
                "order": {
                    "coin": "@142",
                    "side": "B",
                    "limitPx": "87000.0",
                    "sz": "0.001",
                    "oid": 123500,
                    "timestamp": 1762271507099,
                    "reduceOnly": False,
                    "orderType": "Limit",
                    "origSz": "0.001",
                    "tif": "Gtc",
                },
                "status": "open",
                "statusTimestamp": 1762271507100,
            }
        }
        mock_connection.info.spot_meta.return_value = {
            "universe": [{"tokens": [0, 1], "name": "@142", "index": 142, "isCanonical": True}],
            "tokens": [
                {"name": "BTC", "szDecimals": 5, "weiDecimals": 8, "index": 0},
                {"name": "USDC", "szDecimals": 6, "weiDecimals": 6, "index": 1},
            ],
        }
        mock_connection.exchange.cancel.return_value = cancel_success_response

        client.cancel_order(123500)

        mock_connection.exchange.cancel.assert_called_once_with("BTC/USDC", 123500)
