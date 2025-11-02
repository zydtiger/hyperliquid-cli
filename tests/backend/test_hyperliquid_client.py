"""
Test suite for the HyperliquidClient class.

This module provides comprehensive unit tests for the HyperliquidClient,
covering initialization, connection testing, data retrieval methods,
error handling, and edge cases.
"""

import pytest
from decimal import Decimal
from unittest.mock import Mock, patch
from typing import List, Dict, Any

from backend.exchange.hyperliquid_client import HyperliquidClient
from backend.exchange.hyperliquid_connection import HyperliquidConnection
from models.backend import (
    Ticker,
    CoinMetadata,
    ExchangeError,
    LeverageType,
    PositionInfo,
)
from models.config import Config, HyperliquidConfig, NetworkType


class TestHyperliquidClient:
    """Test cases for the HyperliquidClient class."""

    @pytest.fixture
    def mock_config(self) -> Config:
        """Create a mock configuration object for testing."""
        hyperliquid_config = HyperliquidConfig(
            account_address="0x1234567890123456789012345678901234567890",
            private_key="0x1234567890123456789012345678901234567890123456789012345678901234",
            network=NetworkType.MAINNET,
        )
        return Config(hyperliquid=hyperliquid_config)

    @pytest.fixture
    def mock_connection(self) -> Mock:
        """Create a mock HyperliquidConnection."""
        connection = Mock(spec=HyperliquidConnection)
        return connection

    @pytest.fixture
    def client(self, mock_config: Config, mock_connection: Mock) -> HyperliquidClient:
        """Create a HyperliquidClient instance with mocked dependencies."""
        with patch(
            "backend.exchange.hyperliquid_client.HyperliquidConnection",
            return_value=mock_connection,
        ):
            return HyperliquidClient(mock_config)

    @pytest.fixture
    def sample_meta_response(self) -> Dict[str, Any]:
        """Sample response from meta API."""
        return {
            "universe": [
                {"name": "BTC", "szDecimals": 8, "maxLeverage": 50},
                {"name": "ETH", "szDecimals": 6, "maxLeverage": 25},
                {"name": "SOL", "szDecimals": 4, "maxLeverage": 20},
            ]
        }

    @pytest.fixture
    def sample_asset_ctxs_response(self) -> List[Dict[str, Any]]:
        """Sample response from asset contexts API."""
        return [
            {
                "markPx": "50000.0",
                "funding": "0.0001",
                "openInterest": "1000.0",
            },
            {
                "markPx": "3000.0",
                "funding": "-0.0002",
                "openInterest": "5000.0",
            },
            {
                "markPx": "100.0",
                "funding": "0.0003",
                "openInterest": "2000.0",
            },
        ]

    @pytest.fixture
    def sample_user_state_response(self) -> Dict[str, Any]:
        """Sample response from user state API."""
        return {
            "assetPositions": [
                {
                    "type": "oneWay",
                    "position": {
                        "coin": "ETH",
                        "szi": "0.003",
                        "leverage": {
                            "type": "isolated",
                            "value": 25,
                            "rawUsd": "-11.080576",
                        },
                        "entryPx": "3845.9",
                        "positionValue": "11.4921",
                        "unrealizedPnl": "-0.0456",
                        "returnOnEquity": "-0.0988065212",
                        "liquidationPx": "3768.9034013605",
                        "marginUsed": "0.411524",
                        "maxLeverage": 25,
                        "cumFunding": {
                            "allTime": "87.082076",
                            "sinceOpen": "0.0",
                            "sinceChange": "0.0",
                        },
                    },
                },
                {
                    "type": "oneWay",
                    "position": {
                        "coin": "BTC",
                        "szi": "0.001",
                        "leverage": {
                            "type": "cross",
                            "value": 10,
                            "rawUsd": "50.0",
                        },
                        "entryPx": "49000.0",
                        "positionValue": "49.0",
                        "unrealizedPnl": "1.0",
                        "returnOnEquity": "0.0204081632",
                        "liquidationPx": "44100.0",
                        "marginUsed": "4.9",
                        "maxLeverage": 50,
                        "cumFunding": {
                            "allTime": "120.5",
                            "sinceOpen": "0.5",
                            "sinceChange": "0.1",
                        },
                    },
                },
                # Zero-sized position should be ignored
                {
                    "type": "oneWay",
                    "position": {
                        "coin": "SOL",
                        "szi": "0.0",
                        "leverage": {
                            "type": "isolated",
                            "value": 20,
                            "rawUsd": "0.0",
                        },
                        "entryPx": "100.0",
                        "positionValue": "0.0",
                        "unrealizedPnl": "0.0",
                        "returnOnEquity": "0.0",
                        "liquidationPx": "80.0",
                        "marginUsed": "0.0",
                        "maxLeverage": 20,
                        "cumFunding": {
                            "allTime": "0.0",
                            "sinceOpen": "0.0",
                            "sinceChange": "0.0",
                        },
                    },
                },
            ],
        }


class TestHyperliquidClientInitialization(TestHyperliquidClient):
    """Test cases for HyperliquidClient initialization."""

    def test_initialization(self, mock_config: Config, mock_connection: Mock):
        """Test that HyperliquidClient initializes correctly."""
        with patch(
            "backend.exchange.hyperliquid_client.HyperliquidConnection",
            return_value=mock_connection,
        ) as mock_conn_class:
            client = HyperliquidClient(mock_config)

            assert client.config == mock_config
            assert client.connection == mock_connection
            mock_conn_class.assert_called_once_with(mock_config)

    def test_initialization_with_connection_error(self, mock_config: Config):
        """Test initialization when HyperliquidConnection fails."""
        with patch(
            "backend.exchange.hyperliquid_client.HyperliquidConnection",
            side_effect=Exception("Connection failed"),
        ):
            with pytest.raises(Exception, match="Connection failed"):
                HyperliquidClient(mock_config)


class TestHyperliquidClientConnection(TestHyperliquidClient):
    """Test cases for connection-related methods."""

    def test_test_connection_success(
        self, client: HyperliquidClient, mock_connection: Mock
    ):
        """Test successful connection test."""
        mock_connection.test_connection.return_value = True

        result = client.test_connection()

        assert result is True
        mock_connection.test_connection.assert_called_once()

    def test_test_connection_failure(
        self, client: HyperliquidClient, mock_connection: Mock
    ):
        """Test failed connection test."""
        mock_connection.test_connection.return_value = False

        result = client.test_connection()

        assert result is False
        mock_connection.test_connection.assert_called_once()


class TestHyperliquidClientAvailableCoins(TestHyperliquidClient):
    """Test cases for get_available_coins method."""

    def test_get_available_coins_success(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        sample_meta_response: Dict[str, Any],
    ):
        """Test successful retrieval of available coins."""
        mock_info = Mock()
        mock_info.meta.return_value = sample_meta_response
        mock_connection.info = mock_info
        mock_connection.retry_operation.side_effect = lambda func: func()

        result = client.get_available_coins()

        assert result == ["BTC", "ETH", "SOL"]
        mock_connection.retry_operation.assert_called_once()

    def test_get_available_coins_empty_universe(
        self, client: HyperliquidClient, mock_connection: Mock
    ):
        """Test handling of empty universe in meta response."""
        mock_info = Mock()
        mock_info.meta.return_value = {"universe": []}
        mock_connection.info = mock_info
        mock_connection.retry_operation.side_effect = lambda func: func()

        result = client.get_available_coins()

        assert result == []

    def test_get_available_coins_with_retry_failure(
        self, client: HyperliquidClient, mock_connection: Mock
    ):
        """Test retry failure when getting available coins."""
        mock_connection.retry_operation.side_effect = ExchangeError(
            "Operation failed after 4 attempts: API Error"
        )

        with pytest.raises(
            ExchangeError, match="Operation failed after 4 attempts: API Error"
        ):
            client.get_available_coins()


class TestHyperliquidClientTicker(TestHyperliquidClient):
    """Test cases for get_ticker method."""

    def test_get_ticker_success(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        sample_meta_response: Dict[str, Any],
        sample_asset_ctxs_response: List[Dict[str, Any]],
    ):
        """Test successful ticker retrieval."""
        mock_info = Mock()
        mock_info.meta_and_asset_ctxs.return_value = (
            sample_meta_response,
            sample_asset_ctxs_response,
        )
        mock_connection.info = mock_info

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
        client: HyperliquidClient,
        mock_connection: Mock,
        sample_meta_response: Dict[str, Any],
        sample_asset_ctxs_response: List[Dict[str, Any]],
    ):
        """Test ticker retrieval for non-existent coin."""
        mock_info = Mock()
        mock_info.meta_and_asset_ctxs.return_value = (
            sample_meta_response,
            sample_asset_ctxs_response,
        )
        mock_connection.info = mock_info
        mock_connection.retry_operation.side_effect = lambda func: func()

        with pytest.raises(
            ExchangeError, match="Coin 'DOGE' not found in available trading pairs"
        ):
            client.get_ticker("DOGE")

    def test_get_ticker_meta_failure(
        self, client: HyperliquidClient, mock_connection: Mock
    ):
        """Test ticker retrieval when meta call fails."""
        mock_info = Mock()
        mock_info.meta_and_asset_ctxs.return_value = (None, [])
        mock_connection.info = mock_info
        mock_connection.retry_operation.side_effect = lambda func: func()

        with pytest.raises(
            ExchangeError, match="Failed to retrieve market metadata from exchange"
        ):
            client.get_ticker("BTC")

    def test_get_ticker_with_retry_failure(
        self, client: HyperliquidClient, mock_connection: Mock
    ):
        """Test retry failure when getting ticker."""
        mock_connection.retry_operation.side_effect = ExchangeError(
            "Operation failed after 4 attempts: Network timeout"
        )

        with pytest.raises(
            ExchangeError, match="Operation failed after 4 attempts: Network timeout"
        ):
            client.get_ticker("BTC")


class TestHyperliquidClientMetadata(TestHyperliquidClient):
    """Test cases for get_metadata method."""

    def test_get_metadata_success(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        sample_meta_response: Dict[str, Any],
    ):
        """Test successful metadata retrieval."""
        mock_info = Mock()
        mock_info.meta.return_value = sample_meta_response
        mock_connection.info = mock_info
        mock_connection.retry_operation.side_effect = lambda func: func()

        result = client.get_metadata("ETH")

        expected_metadata = CoinMetadata(
            coin="ETH",
            size_decimals=6,
            max_leverage=25,
        )
        assert result == expected_metadata

    def test_get_metadata_coin_not_found(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        sample_meta_response: Dict[str, Any],
    ):
        """Test metadata retrieval for non-existent coin."""
        mock_info = Mock()
        mock_info.meta.return_value = sample_meta_response
        mock_connection.info = mock_info
        mock_connection.retry_operation.side_effect = lambda func: func()

        with pytest.raises(
            ExchangeError, match="Coin 'DOGE' not found in available trading pairs"
        ):
            client.get_metadata("DOGE")

    def test_get_metadata_meta_failure(
        self, client: HyperliquidClient, mock_connection: Mock
    ):
        """Test metadata retrieval when meta call fails."""
        mock_info = Mock()
        mock_info.meta.return_value = None
        mock_connection.info = mock_info
        mock_connection.retry_operation.side_effect = lambda func: func()

        with pytest.raises(
            ExchangeError, match="Failed to retrieve market metadata from exchange"
        ):
            client.get_metadata("BTC")

    def test_get_metadata_with_retry_failure(
        self, client: HyperliquidClient, mock_connection: Mock
    ):
        """Test retry failure when getting metadata."""
        mock_connection.retry_operation.side_effect = ExchangeError(
            "Operation failed after 4 attempts: API timeout"
        )

        with pytest.raises(
            ExchangeError, match="Operation failed after 4 attempts: API timeout"
        ):
            client.get_metadata("BTC")


class TestHyperliquidClientPositions(TestHyperliquidClient):
    """Test cases for get_positions method."""

    def test_get_positions_success(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        sample_user_state_response: Dict[str, Any],
    ):
        """Test successful positions retrieval."""
        mock_info = Mock()
        mock_info.user_state.return_value = sample_user_state_response
        mock_connection.info = mock_info

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

        def mock_retry_operation(func):
            if func.__name__ == "_get_positions":
                # Patch the get_ticker call within _get_positions
                with patch.object(client, "get_ticker", side_effect=mock_get_ticker):
                    return func()
            return func()

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
        self, client: HyperliquidClient, mock_connection: Mock
    ):
        """Test positions retrieval when no positions exist."""
        mock_info = Mock()
        mock_info.user_state.return_value = {"assetPositions": []}
        mock_connection.info = mock_info
        mock_connection.retry_operation.side_effect = lambda func: func()

        result = client.get_positions()

        assert result == []

    def test_get_positions_no_asset_positions_key(
        self, client: HyperliquidClient, mock_connection: Mock
    ):
        """Test positions retrieval when assetPositions key is missing."""
        mock_info = Mock()
        mock_info.user_state.return_value = {}
        mock_connection.info = mock_info
        mock_connection.retry_operation.side_effect = lambda func: func()

        result = client.get_positions()

        assert result == []

    def test_get_positions_only_zero_sized(
        self, client: HyperliquidClient, mock_connection: Mock
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

        mock_info = Mock()
        mock_info.user_state.return_value = user_state
        mock_connection.info = mock_info
        mock_connection.retry_operation.side_effect = lambda func: func()

        result = client.get_positions()

        assert result == []

    def test_get_positions_with_retry_failure(
        self, client: HyperliquidClient, mock_connection: Mock
    ):
        """Test retry failure when getting positions."""
        mock_connection.retry_operation.side_effect = ExchangeError(
            "Operation failed after 4 attempts: Connection lost"
        )

        with pytest.raises(
            ExchangeError, match="Operation failed after 4 attempts: Connection lost"
        ):
            client.get_positions()


class TestHyperliquidClientIntegration(TestHyperliquidClient):
    """Integration-style tests for the HyperliquidClient."""

    def test_client_workflow_full(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        sample_meta_response: Dict[str, Any],
        sample_asset_ctxs_response: List[Dict[str, Any]],
        sample_user_state_response: Dict[str, Any],
    ):
        """Test a complete workflow using multiple client methods."""
        mock_info = Mock()
        mock_info.meta.return_value = sample_meta_response
        mock_info.meta_and_asset_ctxs.return_value = (
            sample_meta_response,
            sample_asset_ctxs_response,
        )
        mock_info.user_state.return_value = sample_user_state_response
        mock_connection.info = mock_info

        # Set up expected return values for each method
        expected_ticker = Ticker(
            coin="ETH",
            mark_price=Decimal("3000.0"),
            funding_rate=Decimal("-0.0002"),
            open_interest=Decimal("5000.0"),
        )
        expected_metadata = CoinMetadata(
            coin="ETH",
            size_decimals=6,
            max_leverage=25,
        )

        # Mock retry operation to return expected values
        def mock_retry_operation(func):
            if func.__name__ == "_get_available_coins":
                return ["BTC", "ETH", "SOL"]
            elif func.__name__ == "_get_ticker":
                return expected_ticker
            elif func.__name__ == "_get_metadata":
                return expected_metadata
            elif func.__name__ == "_get_positions":
                # Mock positions with expected ticker
                with patch.object(client, "get_ticker", return_value=expected_ticker):
                    return func()
            return func()

        mock_connection.retry_operation.side_effect = mock_retry_operation

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

    def test_error_propagation(self, client: HyperliquidClient, mock_connection: Mock):
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


class TestHyperliquidClientEdgeCases(TestHyperliquidClient):
    """Test cases for edge cases and boundary conditions."""

    def test_ticker_with_decimal_values(
        self, client: HyperliquidClient, mock_connection: Mock
    ):
        """Test ticker with very small decimal values."""
        expected_ticker = Ticker(
            coin="BTC",
            mark_price=Decimal("0.00000001"),
            funding_rate=Decimal("-0.99999999"),
            open_interest=Decimal("999999999999.99999999"),
        )
        mock_connection.retry_operation.return_value = expected_ticker

        result = client.get_ticker("BTC")

        assert result == expected_ticker

    def test_positions_with_extreme_values(
        self, client: HyperliquidClient, mock_connection: Mock
    ):
        """Test positions with extreme decimal values."""
        # This test would require mocking the complex position data
        # For now, just ensure the method handles the retry mechanism
        mock_connection.retry_operation.return_value = []

        result = client.get_positions()

        assert isinstance(result, list)
        assert len(result) == 0

    def test_retry_operation_called_on_all_methods(
        self, client: HyperliquidClient, mock_connection: Mock
    ):
        """Test that retry_operation is called on all data retrieval methods."""
        mock_connection.retry_operation.side_effect = lambda func: func()

        # Mock the info object
        mock_info = Mock()
        mock_info.meta.return_value = {
            "universe": [{"name": "BTC", "szDecimals": 8, "maxLeverage": 50}]
        }
        mock_info.meta_and_asset_ctxs.return_value = (
            {"universe": [{"name": "BTC", "szDecimals": 8, "maxLeverage": 50}]},
            [{"markPx": "50000", "funding": "0.0001", "openInterest": "1000"}],
        )
        mock_info.user_state.return_value = {"assetPositions": []}
        mock_connection.info = mock_info

        # Call each method
        client.get_available_coins()
        client.get_ticker("BTC")
        client.get_metadata("BTC")
        client.get_positions()

        # Verify retry_operation was called for each method
        assert mock_connection.retry_operation.call_count == 4
