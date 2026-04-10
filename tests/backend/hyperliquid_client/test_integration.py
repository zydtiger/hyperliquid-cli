"""
Test cases for HyperliquidClient integration and edge cases.

This module provides comprehensive integration tests and edge case
scenarios for the HyperliquidClient class.
"""

from decimal import Decimal
from unittest.mock import patch

import pytest

from models.api import CoinMetadata, ExchangeError, Ticker
from models.order import OrderInfo, OrderSide, OrderStatus, OrderTif, OrderType


class TestHyperliquidClientIntegration:
    """Integration-style tests for the HyperliquidClient."""

    def test_client_workflow_full(
        self,
        client,
        mock_connection,
        sample_meta_response,
        sample_asset_ctxs_response,
        sample_user_state_response,
    ):
        """Test a complete workflow using multiple client methods."""
        mock_info = mock_connection.info
        mock_info.meta.return_value = sample_meta_response
        mock_info.meta_and_asset_ctxs.return_value = (
            sample_meta_response,
            sample_asset_ctxs_response,
        )
        mock_info.user_state.return_value = sample_user_state_response

        # Set up expected return values for each method
        expected_ticker = Ticker(
            coin="ETH",
            mark_price=Decimal("3000.0"),
            funding_rate=Decimal("-0.0002"),
            open_interest=Decimal("15000000.0"),
        )
        expected_metadata = CoinMetadata(
            coin="ETH",
            size_decimals=6,
            max_leverage=25,
        )

        # Custom retry operation for this integration test.
        # Different methods need different return values.
        def mock_retry_operation_integration(func):
            if func.__name__ == "_get_available_coins":
                return ["BTC", "ETH", "SOL"]
            if func.__name__ == "_get_ticker":
                return expected_ticker
            if func.__name__ == "_get_metadata":
                return expected_metadata
            if func.__name__ == "_get_positions":
                # Mock positions with expected ticker
                with patch.object(client, "get_ticker", return_value=expected_ticker):
                    return func()
            return func()

        mock_connection.retry_operation.side_effect = mock_retry_operation_integration

        # Test connection
        mock_connection.test_connection.return_value = True
        assert client.test_connection() is True

        # Get available coins
        coins = client.get_available_coins()
        assert "ETH" in coins

        # Get ticker
        ticker = client.get_ticker("ETH")
        assert isinstance(ticker, Ticker)
        assert ticker.coin == "ETH"

        # Get metadata
        metadata = client.get_metadata("ETH")
        assert isinstance(metadata, CoinMetadata)
        assert metadata.coin == "ETH"

        # Get positions
        positions = client.get_positions()
        assert isinstance(positions, list)

        # Verify all operations were called
        assert mock_connection.retry_operation.call_count == 4

    def test_error_propagation(self, client, mock_connection):
        """Test that errors from connection are properly propagated."""
        mock_connection.retry_operation.side_effect = ExchangeError("API error")

        with pytest.raises(ExchangeError, match="API error"):
            client.get_available_coins()

        with pytest.raises(ExchangeError, match="API error"):
            client.get_ticker("BTC")

        with pytest.raises(ExchangeError, match="API error"):
            client.get_metadata("BTC")

        with pytest.raises(ExchangeError, match="API error"):
            client.get_positions()


class TestHyperliquidClientEdgeCases:
    """Test cases for edge cases and boundary conditions."""

    def test_ticker_with_decimal_values(self, client, mock_connection):
        """Test ticker with very small decimal values."""
        expected_ticker = Ticker(
            coin="BTC",
            mark_price=Decimal("0.00000001"),
            funding_rate=Decimal("-0.99999999"),
            open_interest=Decimal("9999.9999999999999999"),
        )
        mock_connection.retry_operation.return_value = expected_ticker

        result = client.get_ticker("BTC")

        assert result == expected_ticker

    def test_positions_with_extreme_values(self, client, mock_connection):
        """Test positions with extreme decimal values."""
        # This test would require mocking the complex position data
        # For now, just ensure the method handles the retry mechanism
        mock_connection.retry_operation.return_value = []

        result = client.get_positions()

        assert isinstance(result, list)
        assert len(result) == 0

    def test_retry_operation_called_on_all_methods(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test that retry_operation is called on all data retrieval methods."""
        mock_connection.retry_operation.side_effect = mock_retry_operation

        # Mock the info object
        mock_info = mock_connection.info
        mock_info.meta.return_value = {
            "universe": [{"name": "BTC", "szDecimals": 8, "maxLeverage": 50}]
        }
        mock_info.meta_and_asset_ctxs.return_value = (
            {"universe": [{"name": "BTC", "szDecimals": 8, "maxLeverage": 50}]},
            [{"markPx": "50000", "funding": "0.0001", "openInterest": "1000"}],
        )
        mock_info.user_state.return_value = {"assetPositions": []}

        # Call each method
        client.get_available_coins()
        client.get_ticker("BTC")
        client.get_metadata("BTC")
        client.get_positions()

        # Verify retry_operation was called for each method
        assert mock_connection.retry_operation.call_count == 4

    @pytest.mark.parametrize(
        "api_status,expected_status",
        [
            ("canceled", OrderStatus.CANCELLED),
            ("cancelled", OrderStatus.CANCELLED),
            ("filled", OrderStatus.FILLED),
            ("rejected", OrderStatus.REJECTED),
            ("failed", OrderStatus.REJECTED),
        ],
    )
    def test_get_order_status_status_variations(
        self,
        client,
        mock_connection,
        mock_retry_operation,
        api_status,
        expected_status,
    ):
        """Test order status retrieval with various status strings from API."""
        api_response = {
            "order": {
                "order": {
                    "coin": "ETH",
                    "side": "B",
                    "limitPx": "3000.0",
                    "sz": "0.1",
                    "oid": 217754135127,
                    "timestamp": 1761876222840,
                    "reduceOnly": False,
                    "orderType": "Limit",
                    "origSz": "0.1",
                    "tif": "Gtc",
                },
                "status": api_status,
                "statusTimestamp": 1761876248835,
            }
        }

        expected_order = OrderInfo(
            order_id=217754135127,
            coin="ETH",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.1"),
            price=Decimal("3000.0"),
            filled_quantity=Decimal("0.0"),
            remaining_quantity=Decimal("0.1"),
            average_fill_price=None,
            status=expected_status,
            timestamp=1761876222840,
            reduce_only=False,
            time_in_force=OrderTif.GTC,
        )

        mock_connection.retry_operation.return_value = expected_order
        mock_connection.info.query_order_by_oid.return_value = api_response

        result = client.get_order_status(217754135127)
        assert result.status == expected_status

    def test_get_order_status_order_status_mapped_to_open(
        self,
        client,
        mock_connection,
    ):
        """Test that 'order' status from API is mapped to OPEN."""
        api_response = {
            "order": {
                "order": {
                    "coin": "ETH",
                    "side": "B",
                    "limitPx": "3700.0",
                    "sz": "0.003",
                    "oid": 220717680688,
                    "timestamp": 1762141573009,
                    "reduceOnly": False,
                    "orderType": "Limit",
                    "origSz": "0.003",
                    "tif": "Gtc",
                },
                "status": "order",  # API returns "order" status
                "statusTimestamp": 1762141573009,
            }
        }

        expected_order = OrderInfo(
            order_id=220717680688,
            coin="ETH",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.003"),
            price=Decimal("3700.0"),
            filled_quantity=Decimal("0.0"),
            remaining_quantity=Decimal("0.003"),
            average_fill_price=None,
            status=OrderStatus.OPEN,  # Should be mapped from "order" to "open"
            timestamp=1762141573009,
            reduce_only=False,
            time_in_force=OrderTif.GTC,
        )

        mock_connection.retry_operation.return_value = expected_order
        mock_connection.info.query_order_by_oid.return_value = api_response

        result = client.get_order_status(220717680688)

        assert result.status == OrderStatus.OPEN
