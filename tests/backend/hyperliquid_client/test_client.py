"""
Test cases for HyperliquidClient core functionality.

This module provides comprehensive tests for client initialization
and connection testing functionality.
"""

from unittest.mock import Mock, patch

import pytest

from backend.exchange.hyperliquid_client import HyperliquidClient
from models.config import Config


class TestHyperliquidClientInitialization:
    """Test cases for HyperliquidClient initialization."""

    def test_initialization(self, mock_config: Config, mock_connection: Mock) -> None:
        """Test that HyperliquidClient initializes correctly."""
        with patch(
            "backend.exchange.hyperliquid_client.HyperliquidConnection",
            return_value=mock_connection,
        ) as mock_conn_class:
            client = HyperliquidClient(mock_config)

            assert client.config == mock_config
            assert client.connection == mock_connection
            mock_conn_class.assert_called_once_with(mock_config)

    def test_initialization_with_connection_error(self, mock_config: Config) -> None:
        """Test initialization when HyperliquidConnection fails."""
        with patch(
            "backend.exchange.hyperliquid_client.HyperliquidConnection",
            side_effect=Exception("Connection failed"),
        ):
            with pytest.raises(Exception, match="Connection failed"):
                HyperliquidClient(mock_config)


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
