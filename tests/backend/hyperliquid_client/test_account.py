"""
Test cases for HyperliquidClient account functionality.

This module provides comprehensive tests for position management
and account-related queries.
"""

from collections.abc import Callable
from decimal import Decimal
from typing import Any
from unittest.mock import Mock, patch

import pytest

from backend.exchange.hyperliquid_client import HyperliquidClient
from models.api import (
    BalanceInfo,
    ExchangeError,
    LeverageType,
    PositionInfo,
    StakingDelegation,
    StakingStatus,
    Ticker,
)


class TestHyperliquidClientPositions:
    """Test cases for get_positions method."""

    def test_get_positions_success(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        sample_user_state_response: dict[str, Any],
        sample_meta_response: dict[str, Any],
        sample_asset_ctxs_response: list[dict[str, Any]],
        mock_retry_operation: Callable,
    ) -> None:
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
            if coin == "BTC":
                return btc_ticker
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
            removable_margin=Decimal("0"),
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
            removable_margin=None,
            cum_funding=Decimal("120.5"),
        )

        # Assert positions match expected values (order may vary)
        positions_by_coin = {p.coin: p for p in result}
        assert positions_by_coin["ETH"] == expected_eth_position
        assert positions_by_coin["BTC"] == expected_btc_position

    def test_get_positions_empty_positions(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
        """Test positions retrieval when no positions exist."""
        mock_info = mock_connection.info
        mock_info.user_state.return_value = {"assetPositions": []}
        mock_connection.retry_operation.side_effect = mock_retry_operation

        result = client.get_positions()

        assert result == []

    def test_get_positions_no_asset_positions_key(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
        """Test positions retrieval when assetPositions key is missing."""
        mock_info = mock_connection.info
        mock_info.user_state.return_value = {}
        mock_connection.retry_operation.side_effect = mock_retry_operation

        result = client.get_positions()

        assert result == []

    def test_get_positions_only_zero_sized(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
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

    def test_get_positions_computes_positive_removable_margin(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        sample_meta_response: dict[str, Any],
        sample_asset_ctxs_response: list[dict[str, Any]],
        mock_retry_operation: Callable,
    ) -> None:
        """Test removable margin calculation for isolated positions with excess margin."""
        user_state = {
            "assetPositions": [
                {
                    "type": "oneWay",
                    "position": {
                        "coin": "ETH",
                        "szi": "0.02",
                        "leverage": {"type": "isolated", "value": 5, "rawUsd": "-76.0"},
                        "entryPx": "4000.0",
                        "positionValue": "100.0",
                        "unrealizedPnl": "2.0",
                        "returnOnEquity": "0.1",
                        "liquidationPx": "3200.0",
                        "marginUsed": "30.0",
                        "maxLeverage": 25,
                        "cumFunding": {
                            "allTime": "1.0",
                            "sinceOpen": "0.0",
                            "sinceChange": "0.0",
                        },
                    },
                }
            ]
        }

        mock_info = mock_connection.info
        mock_info.user_state.return_value = user_state
        mock_info.meta_and_asset_ctxs.return_value = (
            sample_meta_response,
            sample_asset_ctxs_response,
        )
        mock_connection.retry_operation.side_effect = mock_retry_operation

        with patch.object(
            client,
            "get_ticker",
            return_value=Ticker(
                coin="ETH",
                mark_price=Decimal("3000.0"),
                funding_rate=Decimal("-0.0002"),
                open_interest=Decimal("5000.0"),
            ),
        ):
            result = client.get_positions()

        assert len(result) == 1
        assert result[0].removable_margin == Decimal("10.0")

    def test_get_positions_with_retry_failure(
        self, client: HyperliquidClient, mock_connection: Mock
    ) -> None:
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
        client: HyperliquidClient,
        mock_connection: Mock,
        sample_user_state_response: dict[str, Any],
        sample_spot_state: dict[str, Any],
        sample_staking_summary: dict[str, Any],
        expected_balance_info: BalanceInfo,
        mock_retry_operation: Callable,
    ) -> None:
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
        client: HyperliquidClient,
        mock_connection: Mock,
        sample_user_state_response: dict[str, Any],
        sample_staking_summary: dict[str, Any],
        mock_retry_operation: Callable,
    ) -> None:
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
        client: HyperliquidClient,
        mock_connection: Mock,
        sample_user_state_response: dict[str, Any],
        sample_spot_state: dict[str, Any],
        mock_retry_operation: Callable,
    ) -> None:
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
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
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
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
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
        client: HyperliquidClient,
        mock_connection: Mock,
        sample_user_state_response: dict[str, Any],
        sample_staking_summary: dict[str, Any],
        mock_retry_operation: Callable,
    ) -> None:
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

    def test_get_balances_retry_failure(
        self, client: HyperliquidClient, mock_connection: Mock
    ) -> None:
        """Test retry failure when getting balances."""
        mock_connection.retry_operation.side_effect = ExchangeError(
            "Operation failed after 4 attempts: Connection lost"
        )

        with pytest.raises(
            ExchangeError, match="Operation failed after 4 attempts: Connection lost"
        ):
            client.get_balances()


class TestHyperliquidClientStaking:
    """Test cases for get_staking_status method."""

    def test_get_staking_status_success(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        sample_staking_summary: dict[str, Any],
        sample_staking_delegations: list[dict[str, Any]],
        sample_staking_rewards: list[dict[str, Any]],
        sample_validator_summaries: list[dict[str, Any]],
        expected_staking_status: StakingStatus,
        mock_retry_operation: Callable,
    ) -> None:
        """Test successful staking status retrieval."""
        mock_info = mock_connection.info
        mock_info.user_staking_summary.return_value = sample_staking_summary
        mock_info.user_staking_delegations.return_value = sample_staking_delegations
        mock_info.user_staking_rewards.return_value = sample_staking_rewards
        mock_info.post.return_value = sample_validator_summaries
        mock_connection.retry_operation.side_effect = mock_retry_operation

        result = client.get_staking_status()

        assert result == expected_staking_status

    def test_get_staking_status_filters_zero_amount_delegations(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        sample_staking_summary: dict[str, Any],
        sample_staking_rewards: list[dict[str, Any]],
        mock_retry_operation: Callable,
    ) -> None:
        """Test zero-amount staking delegations are excluded."""
        mock_info = mock_connection.info
        mock_info.user_staking_summary.return_value = sample_staking_summary
        mock_info.user_staking_delegations.return_value = [
            {"validator": "validator-1", "amount": "0"},
            {"validator": "validator-2", "amount": "1.25000000"},
        ]
        mock_info.user_staking_rewards.return_value = sample_staking_rewards
        mock_info.post.return_value = [
            {
                "validator": "validator-2",
                "signer": "signer-2",
                "name": "HyperStake",
                "description": "Validator 2",
                "nRecentBlocks": 100,
                "stake": "100000000",
                "isJailed": False,
                "isActive": True,
                "stats": {},
                "commission": "0.1",
            }
        ]
        mock_connection.retry_operation.side_effect = mock_retry_operation

        result = client.get_staking_status()

        assert result.total_staked == Decimal("100.61607572")
        assert result.total_reward == Decimal("2.00000000")
        assert result.delegations == [
            StakingDelegation(
                validator="validator-2",
                name="HyperStake",
                commission=Decimal("0.1"),
                amount=Decimal("1.25000000"),
            )
        ]

    def test_get_staking_status_empty(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
        """Test staking status retrieval with no active delegations."""
        mock_info = mock_connection.info
        mock_info.user_staking_summary.return_value = {"delegated": "0"}
        mock_info.user_staking_delegations.return_value = []
        mock_info.user_staking_rewards.return_value = []
        mock_info.post.return_value = []
        mock_connection.retry_operation.side_effect = mock_retry_operation

        result = client.get_staking_status()

        assert result.total_staked == Decimal("0")
        assert result.total_reward == Decimal("0")
        assert result.delegations == []

    def test_get_staking_status_summary_failure(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable,
    ) -> None:
        """Test staking summary retrieval failures are wrapped."""
        mock_info = mock_connection.info
        mock_info.user_staking_summary.side_effect = Exception("summary failed")
        mock_connection.retry_operation.side_effect = mock_retry_operation

        with pytest.raises(ExchangeError, match="Failed to get staking status: summary failed"):
            client.get_staking_status()

    def test_get_staking_status_delegations_failure(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        sample_staking_summary: dict[str, Any],
        mock_retry_operation: Callable,
    ) -> None:
        """Test staking delegation retrieval failures are wrapped."""
        mock_info = mock_connection.info
        mock_info.user_staking_summary.return_value = sample_staking_summary
        mock_info.user_staking_delegations.side_effect = Exception("delegations failed")
        mock_connection.retry_operation.side_effect = mock_retry_operation

        with pytest.raises(ExchangeError, match="Failed to get staking status: delegations failed"):
            client.get_staking_status()

    def test_get_staking_status_validator_metadata_failure(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        sample_staking_summary: dict[str, Any],
        sample_staking_delegations: list[dict[str, Any]],
        mock_retry_operation: Callable,
    ) -> None:
        """Test validator metadata retrieval failures are wrapped."""
        mock_info = mock_connection.info
        mock_info.user_staking_summary.return_value = sample_staking_summary
        mock_info.user_staking_delegations.return_value = sample_staking_delegations
        mock_info.user_staking_rewards.return_value = []
        mock_info.post.side_effect = Exception("validators failed")
        mock_connection.retry_operation.side_effect = mock_retry_operation

        with pytest.raises(ExchangeError, match="Failed to get staking status: validators failed"):
            client.get_staking_status()

    def test_get_staking_status_rewards_failure(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        sample_staking_summary: dict[str, Any],
        sample_staking_delegations: list[dict[str, Any]],
        mock_retry_operation: Callable,
    ) -> None:
        """Test staking reward retrieval failures are wrapped."""
        mock_info = mock_connection.info
        mock_info.user_staking_summary.return_value = sample_staking_summary
        mock_info.user_staking_delegations.return_value = sample_staking_delegations
        mock_info.user_staking_rewards.side_effect = Exception("rewards failed")
        mock_connection.retry_operation.side_effect = mock_retry_operation

        with pytest.raises(ExchangeError, match="Failed to get staking status: rewards failed"):
            client.get_staking_status()
