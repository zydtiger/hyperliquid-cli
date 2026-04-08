"""
Tests for HyperliquidClient PnL history retrieval.
"""

from decimal import Decimal

import pytest

from models.api import DEFAULT_PNL_WINDOW, PNL_WINDOW_ORDER, ExchangeError


@pytest.fixture
def sample_portfolio_response() -> list[list[object]]:
    """Sample portfolio payload containing native total and perpetual buckets."""
    return [
        [
            "day",
            {
                "pnlHistory": [
                    [1735603200000, "10.0"],
                    [1735689600000, "11.5"],
                ]
            },
        ],
        [
            "week",
            {
                "pnlHistory": [
                    [1735257600000, "1.0"],
                    [1735344000000, "2.0"],
                    [1735430400000, "3.0"],
                    [1735516800000, "4.0"],
                    [1735603200000, "5.0"],
                    [1735689600000, "6.0"],
                ]
            },
        ],
        [
            "month",
            {
                "pnlHistory": [
                    [1733097600000, "15.0"],
                    [1734307200000, "18.0"],
                    [1735603200000, "20.0"],
                    [1735689600000, "21.0"],
                ]
            },
        ],
        [
            "allTime",
            {
                "pnlHistory": [
                    [1704153600000, "100.0"],
                    [1711929600000, "120.0"],
                    [1725148800000, "140.0"],
                    [1730419200000, "160.0"],
                    [1733097600000, "180.0"],
                    [1735689600000, "200.0"],
                ]
            },
        ],
        [
            "perpDay",
            {
                "pnlHistory": [
                    [1735603200000, "4.0"],
                    [1735689600000, "5.5"],
                ]
            },
        ],
        [
            "perpWeek",
            {
                "pnlHistory": [
                    [1735257600000, "0.5"],
                    [1735516800000, "2.5"],
                    [1735603200000, "3.5"],
                    [1735689600000, "4.5"],
                ]
            },
        ],
        [
            "perpMonth",
            {
                "pnlHistory": [
                    [1733097600000, "8.0"],
                    [1734307200000, "10.0"],
                    [1735603200000, "11.0"],
                    [1735689600000, "12.0"],
                ]
            },
        ],
        [
            "perpAllTime",
            {
                "pnlHistory": [
                    [1704153600000, "60.0"],
                    [1711929600000, "70.0"],
                    [1725148800000, "80.0"],
                    [1730419200000, "90.0"],
                    [1733097600000, "95.0"],
                    [1735689600000, "100.0"],
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
        """Test portfolio data is parsed into the full catalog of PnL windows."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.portfolio.return_value = sample_portfolio_response

        result = client.get_pnl_history()

        assert result.default_window == DEFAULT_PNL_WINDOW
        assert [history.window for history in result.histories] == list(PNL_WINDOW_ORDER)
        by_window = {history.window: history for history in result.histories}

        assert [point.time for point in by_window["1d"].points] == [1735603200000, 1735689600000]
        assert [point.perp_pnl for point in by_window["1d"].points] == [
            Decimal("4.0"),
            Decimal("5.5"),
        ]
        assert [point.time for point in by_window["3d"].points] == [
            1735430400000,
            1735516800000,
            1735603200000,
            1735689600000,
        ]
        assert [point.time for point in by_window["7d"].points] == [
            1735257600000,
            1735344000000,
            1735430400000,
            1735516800000,
            1735603200000,
            1735689600000,
        ]
        assert [point.time for point in by_window["3m"].points] == [
            1730419200000,
            1733097600000,
            1735689600000,
        ]
        assert [point.time for point in by_window["6m"].points] == [
            1725148800000,
            1730419200000,
            1733097600000,
            1735689600000,
        ]
        assert [point.time for point in by_window["1y"].points] == [
            1704153600000,
            1711929600000,
            1725148800000,
            1730419200000,
            1733097600000,
            1735689600000,
        ]
        assert [point.time for point in by_window["all"].points] == [
            1704153600000,
            1711929600000,
            1725148800000,
            1730419200000,
            1733097600000,
            1735689600000,
        ]
        assert [point.spot_pnl for point in by_window["7d"].points] == [
            Decimal("0.5"),
            Decimal("1.5"),
            Decimal("2.5"),
            Decimal("1.5"),
            Decimal("1.5"),
            Decimal("1.5"),
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
            ["week", {"pnlHistory": [[1735603200000, "1.5"], [1735689600000, "2.5"]]}]
        ]

        result = client.get_pnl_history()
        by_window = {history.window: history for history in result.histories}

        assert [point.perp_pnl for point in by_window["7d"].points] == [Decimal("0"), Decimal("0")]
        assert [point.spot_pnl for point in by_window["7d"].points] == [
            Decimal("1.5"),
            Decimal("2.5"),
        ]

    def test_get_pnl_history_returns_empty_when_source_bucket_missing(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test missing native bucket data returns empty histories, not an exception."""
        mock_connection.retry_operation.side_effect = mock_retry_operation
        mock_connection.info.portfolio.return_value = [["allTime", {"pnlHistory": []}]]

        result = client.get_pnl_history()

        assert result.default_window == DEFAULT_PNL_WINDOW
        assert all(history.points == [] for history in result.histories)

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
