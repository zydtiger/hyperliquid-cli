"""
Tests for HyperliquidClient PnL history retrieval.
"""

from decimal import Decimal

import pytest

from models.api import ExchangeError


@pytest.fixture
def sample_portfolio_response() -> list[list[object]]:
    """Sample portfolio payload containing total and perpetual history buckets."""
    return [
        [
            "week",
            {
                "pnlHistory": [
                    [1741886630493, "0.0"],
                    [1741973030493, "10.5"],
                    [1742059430493, "6.0"],
                ]
            },
        ],
        [
            "perpWeek",
            {
                "pnlHistory": [
                    [1741886630493, "0.0"],
                    [1741930000000, "7.0"],
                    [1742059430493, "8.5"],
                ]
            },
        ],
    ]


class TestHyperliquidClientGetPnlHistory:
    """Test cases for the get_pnl_history method."""

    def test_get_pnl_history_success(
        self,
        client,
        mock_connection,
        mock_retry_operation,
        sample_portfolio_response: list[list[object]],
    ):
        """Test portfolio data is parsed into total/perp/spot PnL points."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.portfolio.return_value = sample_portfolio_response

        result = client.get_pnl_history()

        assert result.window == "7d"
        assert [point.time for point in result.points] == [
            1741886630493,
            1741973030493,
            1742059430493,
        ]
        assert [point.total_pnl for point in result.points] == [
            Decimal("0.0"),
            Decimal("10.5"),
            Decimal("6.0"),
        ]
        assert [point.perp_pnl for point in result.points] == [
            Decimal("0.0"),
            Decimal("7.0"),
            Decimal("8.5"),
        ]
        assert [point.spot_pnl for point in result.points] == [
            Decimal("0.0"),
            Decimal("3.5"),
            Decimal("-2.5"),
        ]
        mock_connection.info.portfolio.assert_called_once_with(
            "0x1234567890123456789012345678901234567890"
        )

    def test_get_pnl_history_zero_fills_missing_perp_bucket(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test missing perp history treats the full total series as spot PnL."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.portfolio.return_value = [
            ["week", {"pnlHistory": [[1741886630493, "1.5"], [1741973030493, "2.5"]]}]
        ]

        result = client.get_pnl_history()

        assert [point.perp_pnl for point in result.points] == [Decimal("0"), Decimal("0")]
        assert [point.spot_pnl for point in result.points] == [Decimal("1.5"), Decimal("2.5")]

    def test_get_pnl_history_returns_empty_when_week_history_missing(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test an empty week history returns an empty response model."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.portfolio.return_value = [["week", {"pnlHistory": []}]]

        result = client.get_pnl_history()

        assert result.window == "7d"
        assert result.points == []

    def test_get_pnl_history_wraps_portfolio_errors(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test exchange errors are surfaced with the new command context."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.portfolio.side_effect = Exception("portfolio failed")

        with pytest.raises(ExchangeError) as exc_info:
            client.get_pnl_history()

        assert "Failed to get PnL history: portfolio failed" in str(exc_info.value)
