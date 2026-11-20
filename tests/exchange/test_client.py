"""
Test cases for HyperliquidClient core functionality.

Tests client initialization, context manager cleanup, account address
enforcement, and connection testing functionality.
"""

from unittest.mock import Mock, patch

import pytest

from exchange.hyperliquid_client import HyperliquidClient
from models.api import ExchangeError
from models.config import Config


class TestHyperliquidClientInitialization:
    """Test cases for HyperliquidClient initialization."""

    def test_initialization(self, mock_config: Config, mock_connection: Mock) -> None:
        """Test that HyperliquidClient initializes correctly without opening WS."""
        with patch(
            "exchange.hyperliquid_client.HyperliquidConnection",
            return_value=mock_connection,
        ) as mock_conn_class:
            client = HyperliquidClient(mock_config)

            assert client.config == mock_config
            assert client.connection == mock_connection
            assert client._watch_registry is None
            mock_conn_class.assert_called_once_with(mock_config)

    def test_initialization_with_connection_error(self, mock_config: Config) -> None:
        """Test initialization when HyperliquidConnection fails."""
        with patch(
            "exchange.hyperliquid_client.HyperliquidConnection",
            side_effect=Exception("Connection failed"),
        ):
            with pytest.raises(Exception, match="Connection failed"):
                HyperliquidClient(mock_config)

    def test_context_manager_calls_close(self, mock_config: Config, mock_connection: Mock) -> None:
        """Test HyperliquidClient closes connection on context manager exit."""
        with (
            patch(
                "exchange.hyperliquid_client.HyperliquidConnection",
                return_value=mock_connection,
            ),
            HyperliquidClient(mock_config) as client,
        ):
            assert client.connection is mock_connection

        mock_connection.close.assert_called_once_with()

    def test_require_account_address_returns_configured_address(
        self, client: HyperliquidClient
    ) -> None:
        """Test require_account_address returns configured Ethereum address."""
        assert client.require_account_address() == "0x1234567890123456789012345678901234567890"

    def test_require_account_address_raises_when_missing(self, mock_connection: Mock) -> None:
        """Test require_account_address raises ExchangeError when address is unset."""
        with patch(
            "exchange.hyperliquid_client.HyperliquidConnection",
            return_value=mock_connection,
        ):
            client = HyperliquidClient(Config())

        with pytest.raises(ExchangeError, match="Account address is required"):
            client.require_account_address()


class TestHyperliquidClientConnection:
    """Test cases for connection-related methods."""

    def test_test_connection_success(
        self, client: HyperliquidClient, mock_connection: Mock
    ) -> None:
        """Test successful connection test."""
        mock_connection.test_connection.return_value = True

        result = client.test_connection()

        assert result is True
        mock_connection.test_connection.assert_called_once()

    def test_test_connection_failure(
        self, client: HyperliquidClient, mock_connection: Mock
    ) -> None:
        """Test failed connection test."""
        mock_connection.test_connection.return_value = False

        result = client.test_connection()

        assert result is False
        mock_connection.test_connection.assert_called_once()
