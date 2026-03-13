"""
Test cases for HyperliquidClient account functionality.

This module provides comprehensive tests for position management
and account-related queries.
"""

import pytest
from decimal import Decimal
from unittest.mock import patch

from models.api import (
    Ticker,
    ExchangeError,
    LeverageType,
    PositionInfo,
)


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


class TestHyperliquidClientBalances:
    """Test cases for get_balances method."""

    def test_get_balances_success(
        self,
        client,
        mock_connection,
        sample_user_state_response,
        sample_spot_state,
        sample_staking_summary,
        expected_balance_info,
        mock_retry_operation,
    ):
        """Test successful balance retrieval with all data sources."""
        mock_info = mock_connection.info
        mock_info.user_state.return_value = sample_user_state_response
        mock_info.spot_user_state.return_value = sample_spot_state
        mock_info.user_staking_summary.return_value = sample_staking_summary
        mock_connection.retry_operation.side_effect = mock_retry_operation

        result = client.get_balances()

        # Use expected_balance_info fixture for comprehensive validation
        assert result == expected_balance_info

    def test_get_balances_no_spot_balances(
        self,
        client,
        mock_connection,
        sample_user_state_response,
        sample_staking_summary,
        mock_retry_operation,
    ):
        """Test balance retrieval with no spot balances."""
        mock_info = mock_connection.info
        mock_info.user_state.return_value = sample_user_state_response
        mock_info.spot_user_state.return_value = {"balances": []}
        mock_info.user_staking_summary.return_value = sample_staking_summary
        mock_connection.retry_operation.side_effect = mock_retry_operation

        result = client.get_balances()

        # Check perps data is still populated
        assert result.perps_account_value == Decimal("3451.743653")
        assert result.perps_margin_used == Decimal("5.318932")

        # Check empty spot balances
        assert result.spot_balances == []

        # Check staking info is still populated
        assert result.staking_info is not None
        assert result.staking_info.delegated_amount == Decimal("100.61607572")

    def test_get_balances_no_staking_info(
        self,
        client,
        mock_connection,
        sample_user_state_response,
        sample_spot_state,
        mock_retry_operation,
    ):
        """Test balance retrieval with staking data failure."""
        mock_info = mock_connection.info
        mock_info.user_state.return_value = sample_user_state_response
        mock_info.spot_user_state.return_value = sample_spot_state
        mock_info.user_staking_summary.side_effect = Exception("Staking API error")
        mock_connection.retry_operation.side_effect = mock_retry_operation

        result = client.get_balances()

        # Check perps and spot data are populated
        assert result.perps_account_value == Decimal("3451.743653")
        assert len(result.spot_balances) == 3

        # Check staking info is None due to API failure
        assert result.staking_info is None

    def test_get_balances_zero_balances_filtered(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test that zero spot balances are filtered out."""
        mock_info = mock_connection.info

        # User state with minimal data
        user_state = {
            "marginSummary": {
                "accountValue": "1000.0",
                "totalNtlPos": "0.0",
                "totalRawUsd": "1000.0",
                "totalMarginUsed": "0.0",
            },
            "withdrawable": "1000.0",
            "assetPositions": [],
        }

        # Spot state with zero and non-zero balances
        spot_state = {
            "balances": [
                {"coin": "BTC", "total": "0.0", "hold": "0.0"},  # Should be filtered
                {"coin": "ETH", "total": "0.0", "hold": "0.0"},  # Should be filtered
                {
                    "coin": "USDC",
                    "total": "100.0",
                    "hold": "10.0",
                },  # Should be included
            ]
        }

        mock_info.user_state.return_value = user_state
        mock_info.spot_user_state.return_value = spot_state
        mock_info.user_staking_summary.side_effect = Exception("No staking")
        mock_connection.retry_operation.side_effect = mock_retry_operation

        result = client.get_balances()

        # Check that only non-zero balance is included
        assert len(result.spot_balances) == 1
        assert result.spot_balances[0].coin == "USDC"
        assert result.spot_balances[0].total == Decimal("100.0")

    def test_get_balances_missing_user_state_keys(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test balance retrieval with missing user state keys."""
        mock_info = mock_connection.info

        # Minimal user state missing some keys
        user_state = {
            "marginSummary": {
                # Missing accountValue, totalNtlPos, etc.
                "totalMarginUsed": "0.0",
            },
            # Missing withdrawable key
            "assetPositions": [],
        }

        mock_info.user_state.return_value = user_state
        mock_info.spot_user_state.return_value = {"balances": []}
        mock_info.user_staking_summary.side_effect = Exception("No staking")
        mock_connection.retry_operation.side_effect = mock_retry_operation

        result = client.get_balances()

        # Check default values are used
        assert result.perps_account_value == Decimal("0")
        assert result.perps_total_position_value == Decimal("0")
        assert result.perps_total_raw_usd == Decimal("0")
        assert result.perps_margin_used == Decimal("0.0")
        assert result.perps_withdrawable == Decimal("0")
        assert result.spot_balances == []
        assert result.staking_info is None

    def test_get_balances_spot_api_failure(
        self,
        client,
        mock_connection,
        sample_user_state_response,
        sample_staking_summary,
        mock_retry_operation,
    ):
        """Test balance retrieval when spot API fails."""
        mock_info = mock_connection.info
        mock_info.user_state.return_value = sample_user_state_response
        mock_info.spot_user_state.side_effect = Exception("Spot API error")
        mock_info.user_staking_summary.return_value = sample_staking_summary
        mock_connection.retry_operation.side_effect = mock_retry_operation

        result = client.get_balances()

        # Check perps and staking data are populated despite spot API failure
        assert result.perps_account_value == Decimal("3451.743653")
        assert result.staking_info is not None
        assert result.staking_info.delegated_amount == Decimal("100.61607572")

        # Check spot balances is empty due to API failure
        assert result.spot_balances == []

    def test_get_balances_retry_failure(self, client, mock_connection):
        """Test retry failure when getting balances."""
        mock_connection.retry_operation.side_effect = ExchangeError(
            "Operation failed after 4 attempts: Connection lost"
        )

        with pytest.raises(
            ExchangeError, match="Operation failed after 4 attempts: Connection lost"
        ):
            client.get_balances()
