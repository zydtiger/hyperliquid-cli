"""
Test cases for HyperliquidClient market data functionality.

This module provides comprehensive tests for available coins retrieval,
ticker data, and metadata queries.
"""

from decimal import Decimal

import pytest

from models.api import CoinMetadata, ExchangeError, Ticker


class TestHyperliquidClientAvailableCoins:
    """Test cases for get_available_coins method."""

    def test_get_available_coins_success(
        self,
        client,
        mock_connection,
        mock_retry_operation,
        sample_meta_response,
    ):
        """Test successful retrieval of available coins."""
        mock_info = mock_connection.info
        mock_info.meta.return_value = sample_meta_response
        mock_connection.retry_operation.side_effect = mock_retry_operation

        result = client.get_available_coins()

        assert result == ["BTC", "ETH", "SOL"]
        mock_connection.retry_operation.assert_called_once()

    def test_get_available_coins_includes_spot_pairs(
        self,
        client,
        mock_connection,
        mock_retry_operation,
        sample_meta_response,
    ):
        """Test available coins includes resolved spot pair symbols."""
        mock_info = mock_connection.info
        mock_info.meta.return_value = sample_meta_response
        mock_info.spot_meta.return_value = {
            "universe": [{"tokens": [441, 360], "name": "@441", "index": 441, "isCanonical": True}],
            "tokens": [{}] * 442,
        }
        mock_info.spot_meta.return_value["tokens"][360] = {
            "name": "USDC",
            "szDecimals": 6,
            "weiDecimals": 6,
            "index": 360,
        }
        mock_info.spot_meta.return_value["tokens"][441] = {
            "name": "UBTC",
            "szDecimals": 5,
            "weiDecimals": 8,
            "index": 441,
        }
        mock_connection.retry_operation.side_effect = mock_retry_operation

        result = client.get_available_coins()

        assert result == ["BTC", "ETH", "SOL", "UBTC/USDC"]

    def test_get_available_coins_empty_universe(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test handling of empty universe in meta response."""
        mock_info = mock_connection.info
        mock_info.meta.return_value = {"universe": []}
        mock_connection.retry_operation.side_effect = mock_retry_operation

        result = client.get_available_coins()

        assert result == []

    def test_get_available_coins_with_retry_failure(self, client, mock_connection):
        """Test retry failure when getting available coins."""
        mock_connection.retry_operation.side_effect = ExchangeError(
            "Operation failed after 4 attempts: API Error"
        )

        with pytest.raises(ExchangeError, match="Operation failed after 4 attempts: API Error"):
            client.get_available_coins()


class TestHyperliquidClientTicker:
    """Test cases for get_ticker method."""

    def test_get_ticker_success(
        self,
        client,
        mock_connection,
        sample_meta_response,
        sample_asset_ctxs_response,
    ):
        """Test successful ticker retrieval."""
        mock_info = mock_connection.info
        mock_info.meta_and_asset_ctxs.return_value = (
            sample_meta_response,
            sample_asset_ctxs_response,
        )

        # Mock the get_ticker method to avoid infinite recursion
        expected_ticker = Ticker(
            coin="ETH",
            mark_price=Decimal("3000.0"),
            funding_rate=Decimal("-0.0002"),
            open_interest=Decimal("5000.0"),
        )
        mock_connection.retry_operation.return_value = expected_ticker

        result = client.get_ticker("ETH")

        assert result == expected_ticker
        mock_connection.retry_operation.assert_called_once()

    def test_get_ticker_coin_not_found(
        self,
        client,
        mock_connection,
        mock_retry_operation,
        sample_meta_response,
        sample_asset_ctxs_response,
    ):
        """Test ticker retrieval for non-existent coin."""
        mock_info = mock_connection.info
        mock_info.meta_and_asset_ctxs.return_value = (
            sample_meta_response,
            sample_asset_ctxs_response,
        )
        mock_connection.retry_operation.side_effect = mock_retry_operation

        with pytest.raises(ExchangeError, match="Coin 'DOGE' not found in available trading pairs"):
            client.get_ticker("DOGE")

    def test_get_ticker_meta_failure(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test ticker retrieval when meta call fails."""
        mock_info = mock_connection.info
        mock_info.meta_and_asset_ctxs.return_value = (None, [])
        mock_connection.retry_operation.side_effect = mock_retry_operation

        with pytest.raises(ExchangeError, match="Failed to retrieve market metadata from exchange"):
            client.get_ticker("BTC")

    def test_get_ticker_with_retry_failure(self, client, mock_connection):
        """Test retry failure when getting ticker."""
        mock_connection.retry_operation.side_effect = ExchangeError(
            "Operation failed after 4 attempts: Network timeout"
        )

        with pytest.raises(
            ExchangeError, match="Operation failed after 4 attempts: Network timeout"
        ):
            client.get_ticker("BTC")


class TestHyperliquidClientMetadata:
    """Test cases for get_metadata method."""

    def test_get_metadata_success(
        self,
        client,
        mock_connection,
        mock_retry_operation,
        sample_meta_response,
    ):
        """Test successful metadata retrieval."""
        mock_info = mock_connection.info
        mock_info.meta.return_value = sample_meta_response
        mock_connection.retry_operation.side_effect = mock_retry_operation

        result = client.get_metadata("ETH")

        expected_metadata = CoinMetadata(
            coin="ETH",
            size_decimals=6,
            max_leverage=25,
        )
        assert result == expected_metadata

    def test_get_metadata_coin_not_found(
        self,
        client,
        mock_connection,
        mock_retry_operation,
        sample_meta_response,
    ):
        """Test metadata retrieval for non-existent coin."""
        mock_info = mock_connection.info
        mock_info.meta.return_value = sample_meta_response
        mock_connection.retry_operation.side_effect = mock_retry_operation

        with pytest.raises(ExchangeError, match="Coin 'DOGE' not found in available trading pairs"):
            client.get_metadata("DOGE")

    def test_get_metadata_meta_failure(
        self,
        client,
        mock_connection,
        mock_retry_operation,
    ):
        """Test metadata retrieval when meta call fails."""
        mock_info = mock_connection.info
        mock_info.meta.return_value = None
        mock_connection.retry_operation.side_effect = mock_retry_operation

        with pytest.raises(ExchangeError, match="Failed to retrieve market metadata from exchange"):
            client.get_metadata("BTC")

    def test_get_metadata_with_retry_failure(self, client, mock_connection):
        """Test retry failure when getting metadata."""
        mock_connection.retry_operation.side_effect = ExchangeError(
            "Operation failed after 4 attempts: API timeout"
        )

        with pytest.raises(ExchangeError, match="Operation failed after 4 attempts: API timeout"):
            client.get_metadata("BTC")
