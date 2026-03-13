"""
Test cases for HyperliquidClient leverage functionality.

This module provides comprehensive tests for leverage modification
operations including success and failure scenarios.
"""

from decimal import Decimal
from unittest.mock import patch

import pytest

from models.api import LeverageType, PositionInfo


class TestHyperliquidClientLeverage:
    """Test cases for change_leverage method."""

    @pytest.fixture(autouse=True)
    def _setup_retry_operation(self, mock_connection, mock_retry_operation):
        """Execute retry-wrapped leverage calls during tests."""
        mock_connection.retry_operation.side_effect = mock_retry_operation

    def test_change_leverage_success_cross_margin(
        self,
        client,
        mock_connection,
        sample_user_state_response,
    ):
        """Test successful leverage update with cross margin."""
        # Setup mock responses
        mock_connection.info.user_state.return_value = sample_user_state_response
        mock_connection.exchange.update_leverage.return_value = {"status": "ok"}

        # Mock get_positions to return updated position
        updated_position = PositionInfo(
            coin="ETH",
            size=Decimal("0.1"),
            entry_price=Decimal("3000"),
            mark_price=Decimal("3100"),
            unrealized_pnl=Decimal("10"),
            leverage=21,  # Updated leverage
            leverage_type=LeverageType.CROSS,
            margin_used=Decimal("14.29"),
            cum_funding=Decimal("0.5"),
        )

        with patch.object(client, "get_positions") as mock_get_positions:
            mock_get_positions.return_value = [updated_position]

            result = client.change_leverage(21, "ETH", is_cross=True)

        assert result.success is True
        assert (
            "Successfully updated ETH leverage to 21x (cross margin)" in result.message
        )
        assert result.updated_position == updated_position
        mock_connection.exchange.update_leverage.assert_called_once_with(
            21, "ETH", True
        )

    def test_change_leverage_success_isolated_margin(
        self,
        client,
        mock_connection,
        sample_user_state_response,
    ):
        """Test successful leverage update with isolated margin."""
        # Setup mock responses
        mock_connection.info.user_state.return_value = sample_user_state_response
        mock_connection.exchange.update_leverage.return_value = {"status": "ok"}

        # Mock get_positions to return updated position
        updated_position = PositionInfo(
            coin="BTC",
            size=Decimal("0.05"),
            entry_price=Decimal("50000"),
            mark_price=Decimal("51000"),
            unrealized_pnl=Decimal("50"),
            leverage=15,  # Updated leverage
            leverage_type=LeverageType.ISOLATED,
            margin_used=Decimal("166.67"),
            cum_funding=Decimal("1.2"),
        )

        with patch.object(client, "get_positions") as mock_get_positions:
            mock_get_positions.return_value = [updated_position]

            result = client.change_leverage(15, "BTC", is_cross=False)

        assert result.success is True
        assert (
            "Successfully updated BTC leverage to 15x (isolated margin)"
            in result.message
        )
        assert result.updated_position == updated_position
        mock_connection.exchange.update_leverage.assert_called_once_with(
            15, "BTC", False
        )

    def test_change_leverage_exchange_error(
        self,
        client,
        mock_connection,
        sample_user_state_response,
    ):
        """Test leverage update when exchange returns an error."""
        # Setup mock responses
        mock_connection.info.user_state.return_value = sample_user_state_response
        mock_connection.exchange.update_leverage.return_value = {
            "status": "error",
            "response": "Invalid leverage value",
        }

        # Mock get_positions to return existing position
        with patch.object(client, "get_positions") as mock_get_positions:
            mock_get_positions.return_value = [
                PositionInfo(
                    coin="ETH",
                    size=Decimal("0.1"),
                    entry_price=Decimal("3000"),
                    mark_price=Decimal("3100"),
                    unrealized_pnl=Decimal("10"),
                    leverage=10,
                    leverage_type=LeverageType.CROSS,
                    margin_used=Decimal("30"),
                    cum_funding=Decimal("0.5"),
                )
            ]

            result = client.change_leverage(
                21, "ETH", is_cross=True
            )

        assert result.success is False
        assert "Failed to update ETH leverage: Invalid leverage value" in result.message
        assert result.updated_position is None

    def test_change_leverage_exception_handling(
        self,
        client,
        mock_connection,
        sample_user_state_response,
    ):
        """Test leverage update when an exception occurs."""
        # Setup mock responses
        mock_connection.info.user_state.return_value = sample_user_state_response
        mock_connection.exchange.update_leverage.side_effect = Exception(
            "Connection error"
        )

        # Mock get_positions to return existing position
        with patch.object(client, "get_positions") as mock_get_positions:
            mock_get_positions.return_value = [
                PositionInfo(
                    coin="ETH",
                    size=Decimal("0.1"),
                    entry_price=Decimal("3000"),
                    mark_price=Decimal("3100"),
                    unrealized_pnl=Decimal("10"),
                    leverage=10,
                    leverage_type=LeverageType.CROSS,
                    margin_used=Decimal("30"),
                    cum_funding=Decimal("0.5"),
                )
            ]

            result = client.change_leverage(21, "ETH", is_cross=True)

        assert result.success is False
        assert "Leverage update failed for ETH: Connection error" in result.message
        assert result.updated_position is None

    @pytest.mark.parametrize(
        "leverage,coin,is_cross",
        [
            (1, "ETH", True),  # Minimum leverage
            (250, "BTC", False),  # Maximum leverage, isolated
            (50, "SOL", True),  # Mid-range leverage, cross
        ],
    )
    def test_change_leverage_parameter_validation(
        self,
        client,
        mock_connection,
        sample_user_state_response,
        leverage,
        coin,
        is_cross,
    ):
        """Test leverage update with various valid parameters."""
        # Setup mock responses
        mock_connection.info.user_state.return_value = sample_user_state_response
        mock_connection.exchange.update_leverage.return_value = {"status": "ok"}

        # Mock get_positions to return existing position
        with patch.object(client, "get_positions") as mock_get_positions:
            mock_get_positions.return_value = [
                PositionInfo(
                    coin=coin,
                    size=Decimal("0.1"),
                    entry_price=Decimal("100"),
                    mark_price=Decimal("110"),
                    unrealized_pnl=Decimal("1"),
                    leverage=10,
                    leverage_type=(
                        LeverageType.CROSS if is_cross else LeverageType.ISOLATED
                    ),
                    margin_used=Decimal("10"),
                    cum_funding=Decimal("0.1"),
                )
            ]

            result = client.change_leverage(leverage, coin, is_cross)

        assert result.success is True
        assert f"Successfully updated {coin} leverage to {leverage}x" in result.message
        mock_connection.exchange.update_leverage.assert_called_once_with(
            leverage, coin, is_cross
        )

    @pytest.mark.parametrize(
        "leverage,coin,is_cross,expected_error",
        [
            (0, "ETH", True, "Invalid leverage value: 0"),
            (-5, "BTC", False, "Invalid leverage value: -5"),
            (251, "SOL", True, "Invalid leverage value: 251"),
            (1000, "DOGE", False, "Invalid leverage value: 1000"),
            (1.5, "ETH", True, "Invalid leverage value: 1.5"),  # Non-integer
        ],
    )
    def test_change_leverage_bounds_validation(
        self,
        client,
        mock_connection,
        leverage,
        coin,
        is_cross,
        expected_error,
    ):
        """Test leverage update with invalid leverage values."""
        result = client.change_leverage(leverage, coin, is_cross)

        assert result.success is False
        assert expected_error in result.message
        assert "Must be an integer between 1 and 250" in result.message
        assert result.updated_position is None
        mock_connection.exchange.update_leverage.assert_not_called()

    @pytest.mark.parametrize(
        "coin,is_cross,expected_error",
        [
            ("", True, "Invalid coin symbol"),
            (None, False, "Invalid coin symbol"),
        ],
    )
    def test_change_leverage_coin_validation(
        self,
        client,
        mock_connection,
        coin,
        is_cross,
        expected_error,
    ):
        """Test leverage update with invalid coin symbols."""
        result = client.change_leverage(10, coin, is_cross)

        assert result.success is False
        assert expected_error in result.message
        assert "must be a non-empty string" in result.message
        assert result.updated_position is None
        mock_connection.exchange.update_leverage.assert_not_called()

    def test_change_leverage_specific_error_messages(
        self,
        client,
        mock_connection,
    ):
        """Test leverage update with specific API error messages."""
        # Test leverage type switch error
        mock_connection.exchange.update_leverage.return_value = {
            "status": "err",
            "response": "Cannot switch leverage type with open position.",
        }

        result = client.change_leverage(20, "ETH", True)

        assert result.success is False
        assert (
            "Cannot switch leverage type for ETH with open position" in result.message
        )
        assert "Close the position first or use the same margin type" in result.message
        mock_connection.exchange.update_leverage.assert_called_once_with(
            20, "ETH", True
        )

        # Reset mock for next test
        mock_connection.reset_mock()

        # Test isolated margin insufficient error
        mock_connection.exchange.update_leverage.return_value = {
            "status": "err",
            "response": "Isolated position does not have sufficient margin available to decrease leverage. To decrease leverage, add margin to the position.",
        }

        result = client.change_leverage(5, "BTC", False)

        assert result.success is False
        assert (
            "Insufficient margin to decrease leverage for BTC isolated position"
            in result.message
        )
        assert "Add margin to the position or use a higher leverage" in result.message
        mock_connection.exchange.update_leverage.assert_called_once_with(
            5, "BTC", False
        )
