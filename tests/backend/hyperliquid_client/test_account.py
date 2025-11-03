"""
Test cases for HyperliquidClient account functionality.

This module provides comprehensive tests for position management
and account-related queries.
"""

import pytest
from decimal import Decimal
from unittest.mock import patch

from models.api import Ticker, ExchangeError, LeverageType, PositionInfo


class TestHyperliquidClientPositions:
    """Test cases for get_positions method."""

    def test_get_positions_success(
        self,
        client,
        mock_connection,
        sample_user_state_response,
        sample_meta_response,
        sample_asset_ctxs_response,
        mock_retry_operation,
    ):
        """Test successful positions retrieval."""
        mock_info = mock_connection.info
        mock_info.user_state.return_value = sample_user_state_response
        mock_info.meta_and_asset_ctxs.return_value = (
            sample_meta_response,
            sample_asset_ctxs_response,
        )

        # Mock get_ticker to return different data for different coins
        eth_ticker = Ticker(
            coin="ETH",
            mark_price=Decimal("3000.0"),
            funding_rate=Decimal("-0.0002"),
            open_interest=Decimal("5000.0"),
        )
        btc_ticker = Ticker(
            coin="BTC",
            mark_price=Decimal("50000.0"),
            funding_rate=Decimal("0.0001"),
            open_interest=Decimal("1000.0"),
        )

        def mock_get_ticker(coin: str) -> Ticker:
            if coin == "ETH":
                return eth_ticker
            elif coin == "BTC":
                return btc_ticker
            else:
                raise ExchangeError(f"Coin '{coin}' not found")

        # Use the fixture for retry operation and patch get_ticker for positions call
        with patch.object(client, "get_ticker", side_effect=mock_get_ticker):
            mock_connection.retry_operation.side_effect = mock_retry_operation

        result = client.get_positions()

        assert len(result) == 2  # Should ignore zero-sized position

        # Expected ETH position
        expected_eth_position = PositionInfo(
            coin="ETH",
            size=Decimal("0.003"),
            entry_price=Decimal("3845.9"),
            mark_price=Decimal("3000.0"),
            unrealized_pnl=Decimal("-0.0456"),
            leverage=25,
            leverage_type=LeverageType.ISOLATED,
            margin_used=Decimal("0.411524"),
            cum_funding=Decimal("87.082076"),
        )

        # Expected BTC position
        expected_btc_position = PositionInfo(
            coin="BTC",
            size=Decimal("0.001"),
            entry_price=Decimal("49000.0"),
            mark_price=Decimal("50000.0"),  # From sample_asset_ctxs_response
            unrealized_pnl=Decimal("1.0"),
            leverage=10,
            leverage_type=LeverageType.CROSS,
            margin_used=Decimal("4.9"),
            cum_funding=Decimal("120.5"),
        )

        # Assert positions match expected values (order may vary)
        positions_by_coin = {p.coin: p for p in result}
        assert positions_by_coin["ETH"] == expected_eth_position
        assert positions_by_coin["BTC"] == expected_btc_position

    def test_get_positions_empty_positions(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test positions retrieval when no positions exist."""
        mock_info = mock_connection.info
        mock_info.user_state.return_value = {"assetPositions": []}
        mock_connection.retry_operation.side_effect = mock_retry_operation

        result = client.get_positions()

        assert result == []

    def test_get_positions_no_asset_positions_key(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test positions retrieval when assetPositions key is missing."""
        mock_info = mock_connection.info
        mock_info.user_state.return_value = {}
        mock_connection.retry_operation.side_effect = mock_retry_operation

        result = client.get_positions()

        assert result == []

    def test_get_positions_only_zero_sized(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test positions retrieval when all positions are zero-sized."""
        user_state = {
            "assetPositions": [
                {
                    "type": "oneWay",
                    "position": {
                        "coin": "ETH",
                        "szi": "0.0",
                        "leverage": {"type": "isolated", "value": 25, "rawUsd": "0.0"},
                        "entryPx": "3845.9",
                        "positionValue": "0.0",
                        "unrealizedPnl": "0.0",
                        "returnOnEquity": "0.0",
                        "liquidationPx": "3768.9034013605",
                        "marginUsed": "0.0",
                        "maxLeverage": 25,
                        "cumFunding": {
                            "allTime": "0.0",
                            "sinceOpen": "0.0",
                            "sinceChange": "0.0",
                        },
                    },
                },
            ],
        }

        mock_info = mock_connection.info
        mock_info.user_state.return_value = user_state
        mock_connection.retry_operation.side_effect = mock_retry_operation

        result = client.get_positions()

        assert result == []

    def test_get_positions_with_retry_failure(self, client, mock_connection):
        """Test retry failure when getting positions."""
        mock_connection.retry_operation.side_effect = ExchangeError(
            "Operation failed after 4 attempts: Connection lost"
        )

        with pytest.raises(
            ExchangeError, match="Operation failed after 4 attempts: Connection lost"
        ):
            client.get_positions()
