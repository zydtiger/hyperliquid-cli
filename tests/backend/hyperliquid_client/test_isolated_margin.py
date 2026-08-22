"""
Test cases for HyperliquidClient isolated margin functionality.
"""

from collections.abc import Callable
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from backend.exchange.hyperliquid_client import HyperliquidClient
from models.api import LeverageType, PositionInfo


class TestHyperliquidClientIsolatedMargin:
    """Test cases for update_isolated_margin method."""

    @pytest.fixture(autouse=True)
    def _setup_retry_operation(self, mock_connection: Mock, mock_retry_operation: Callable) -> None:
        """Execute retry-wrapped isolated margin calls during tests."""
        mock_connection.retry_operation.side_effect = mock_retry_operation

    def test_update_isolated_margin_success_add(
        self, client: HyperliquidClient, mock_connection: Mock
    ) -> None:
        """Test successful isolated margin addition."""
        current_position = PositionInfo(
            coin="ETH",
            size=Decimal("0.1"),
            entry_price=Decimal("3000"),
            mark_price=Decimal("3100"),
            unrealized_pnl=Decimal("10"),
            leverage=15,
            leverage_type=LeverageType.ISOLATED,
            margin_used=Decimal("100"),
            removable_margin=Decimal("80"),
            cum_funding=Decimal("0.5"),
        )
        updated_position = current_position.model_copy(
            update={"margin_used": Decimal("101"), "removable_margin": Decimal("81")}
        )
        mock_connection.exchange.update_isolated_margin.return_value = {
            "status": "ok",
            "response": {"type": "default"},
        }

        with patch.object(client, "get_positions") as mock_get_positions:
            mock_get_positions.side_effect = [[current_position], [updated_position]]
            result = client.update_isolated_margin(Decimal("1"), "ETH")

        assert result.success is True
        assert result.message == "Successfully added $1.00 isolated margin to ETH"
        assert result.updated_position == updated_position
        mock_connection.exchange.update_isolated_margin.assert_called_once_with(1.0, "ETH")

    def test_update_isolated_margin_success_remove(
        self, client: HyperliquidClient, mock_connection: Mock
    ) -> None:
        """Test successful isolated margin removal."""
        current_position = PositionInfo(
            coin="ETH",
            size=Decimal("0.1"),
            entry_price=Decimal("3000"),
            mark_price=Decimal("3100"),
            unrealized_pnl=Decimal("10"),
            leverage=15,
            leverage_type=LeverageType.ISOLATED,
            margin_used=Decimal("101"),
            removable_margin=Decimal("81"),
            cum_funding=Decimal("0.5"),
        )
        updated_position = current_position.model_copy(
            update={"margin_used": Decimal("100.5"), "removable_margin": Decimal("80.5")}
        )
        mock_connection.exchange.update_isolated_margin.return_value = {
            "status": "ok",
            "response": {"type": "default"},
        }

        with patch.object(client, "get_positions") as mock_get_positions:
            mock_get_positions.side_effect = [[current_position], [updated_position]]
            result = client.update_isolated_margin(Decimal("-0.5"), "ETH")

        assert result.success is True
        assert result.message == "Successfully removed $0.50 isolated margin from ETH"
        assert result.updated_position == updated_position
        mock_connection.exchange.update_isolated_margin.assert_called_once_with(-0.5, "ETH")

    def test_update_isolated_margin_no_open_position(
        self, client: HyperliquidClient, mock_connection: Mock
    ) -> None:
        """Test isolated margin update when no open position exists."""
        with patch.object(client, "get_positions", return_value=[]):
            result = client.update_isolated_margin(Decimal("1"), "ETH")

        assert result.success is False
        assert result.message == "No open position found for ETH"
        assert result.updated_position is None
        mock_connection.exchange.update_isolated_margin.assert_not_called()

    def test_update_isolated_margin_cross_margin_position(
        self, client: HyperliquidClient, mock_connection: Mock
    ) -> None:
        """Test isolated margin update rejection for cross margin positions."""
        current_position = PositionInfo(
            coin="BTC",
            size=Decimal("0.1"),
            entry_price=Decimal("50000"),
            mark_price=Decimal("51000"),
            unrealized_pnl=Decimal("100"),
            leverage=10,
            leverage_type=LeverageType.CROSS,
            margin_used=Decimal("500"),
            removable_margin=None,
            cum_funding=Decimal("1.0"),
        )

        with patch.object(client, "get_positions", return_value=[current_position]):
            result = client.update_isolated_margin(Decimal("1"), "BTC")

        assert result.success is False
        assert (
            result.message
            == "Cannot update isolated margin for BTC: position is using cross margin"
        )
        assert result.updated_position is None
        mock_connection.exchange.update_isolated_margin.assert_not_called()

    def test_update_isolated_margin_zero_amount_validation(
        self, client: HyperliquidClient, mock_connection: Mock
    ) -> None:
        """Test isolated margin update with zero amount."""
        result = client.update_isolated_margin(Decimal("0"), "ETH")

        assert result.success is False
        assert result.message == "Invalid amount: isolated margin update amount must be non-zero"
        assert result.updated_position is None
        mock_connection.exchange.update_isolated_margin.assert_not_called()

    def test_update_isolated_margin_precision_validation(
        self, client: HyperliquidClient, mock_connection: Mock
    ) -> None:
        """Test isolated margin update with too many decimal places."""
        result = client.update_isolated_margin(Decimal("0.1234567"), "ETH")

        assert result.success is False
        assert (
            result.message
            == "Invalid amount: isolated margin update amount must have at most 6 decimal places"
        )
        assert result.updated_position is None
        mock_connection.exchange.update_isolated_margin.assert_not_called()

    @pytest.mark.parametrize("coin", ["", None])
    def test_update_isolated_margin_invalid_coin(
        self, client: HyperliquidClient, mock_connection: Mock, coin: str | None
    ) -> None:
        """Test isolated margin update with invalid coin symbols."""
        result = client.update_isolated_margin(Decimal("1"), coin)  # type: ignore[arg-type]

        assert result.success is False
        assert result.message == "Invalid coin symbol: must be a non-empty string"
        assert result.updated_position is None
        mock_connection.exchange.update_isolated_margin.assert_not_called()

    def test_update_isolated_margin_exchange_error(
        self, client: HyperliquidClient, mock_connection: Mock
    ) -> None:
        """Test isolated margin update when exchange returns an error."""
        current_position = PositionInfo(
            coin="ETH",
            size=Decimal("0.1"),
            entry_price=Decimal("3000"),
            mark_price=Decimal("3100"),
            unrealized_pnl=Decimal("10"),
            leverage=15,
            leverage_type=LeverageType.ISOLATED,
            margin_used=Decimal("100"),
            removable_margin=Decimal("80"),
            cum_funding=Decimal("0.5"),
        )
        mock_connection.exchange.update_isolated_margin.return_value = {
            "status": "err",
            "response": "Insufficient margin available",
        }

        with patch.object(client, "get_positions", return_value=[current_position]):
            result = client.update_isolated_margin(Decimal("-1"), "ETH")

        assert result.success is False
        assert (
            result.message
            == "Failed to update isolated margin for ETH: Insufficient margin available"
        )
        assert result.updated_position is None

    def test_update_isolated_margin_success_without_position_refresh(
        self, client: HyperliquidClient, mock_connection: Mock
    ) -> None:
        """Test successful isolated margin update when position refresh fails."""
        current_position = PositionInfo(
            coin="ETH",
            size=Decimal("0.1"),
            entry_price=Decimal("3000"),
            mark_price=Decimal("3100"),
            unrealized_pnl=Decimal("10"),
            leverage=15,
            leverage_type=LeverageType.ISOLATED,
            margin_used=Decimal("100"),
            removable_margin=Decimal("80"),
            cum_funding=Decimal("0.5"),
        )
        mock_connection.exchange.update_isolated_margin.return_value = {
            "status": "ok",
            "response": {"type": "default"},
        }

        with patch.object(client, "get_positions") as mock_get_positions:
            mock_get_positions.side_effect = [[current_position], Exception("refresh failed")]
            result = client.update_isolated_margin(Decimal("1"), "ETH")

        assert result.success is True
        assert result.message == "Successfully added $1.00 isolated margin to ETH"
        assert result.updated_position is None

    def test_update_isolated_margin_unexpected_success_response(
        self, client: HyperliquidClient, mock_connection: Mock
    ) -> None:
        """Test isolated margin update when the exchange returns an unexpected success payload."""
        current_position = PositionInfo(
            coin="ETH",
            size=Decimal("0.1"),
            entry_price=Decimal("3000"),
            mark_price=Decimal("3100"),
            unrealized_pnl=Decimal("10"),
            leverage=15,
            leverage_type=LeverageType.ISOLATED,
            margin_used=Decimal("100"),
            removable_margin=Decimal("80"),
            cum_funding=Decimal("0.5"),
        )
        mock_connection.exchange.update_isolated_margin.return_value = {
            "status": "ok",
            "response": {"type": "unexpected"},
        }

        with patch.object(client, "get_positions", return_value=[current_position]):
            result = client.update_isolated_margin(Decimal("1"), "ETH")

        assert result.success is False
        assert "Unexpected isolated margin response for ETH" in result.message
        assert result.updated_position is None
