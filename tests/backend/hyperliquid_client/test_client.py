"""
Test cases for HyperliquidClient core functionality.

This module provides comprehensive tests for client initialization
and connection testing functionality.
"""

import pytest
from unittest.mock import patch

from backend.exchange.hyperliquid_client import HyperliquidClient


class TestHyperliquidClientInitialization:
    """Test cases for HyperliquidClient initialization."""

    def test_initialization(self, mock_config, mock_connection):
        """Test that HyperliquidClient initializes correctly."""
        with patch(
            "backend.exchange.hyperliquid_client.HyperliquidConnection",
            return_value=mock_connection,
        ) as mock_conn_class:
            client = HyperliquidClient(mock_config)

            assert client.config == mock_config
            assert client.connection == mock_connection
            mock_conn_class.assert_called_once_with(mock_config)

    def test_initialization_with_connection_error(self, mock_config):
        """Test initialization when HyperliquidConnection fails."""
        with patch(
            "backend.exchange.hyperliquid_client.HyperliquidConnection",
            side_effect=Exception("Connection failed"),
        ):
            with pytest.raises(Exception, match="Connection failed"):
                HyperliquidClient(mock_config)


class TestHyperliquidClientConnection:
    """Test cases for connection-related methods."""

    def test_test_connection_success(self, client, mock_connection):
        """Test successful connection test."""
        mock_connection.test_connection.return_value = True

        result = client.test_connection()

        assert result is True
        mock_connection.test_connection.assert_called_once()

    def test_test_connection_failure(self, client, mock_connection):
        """Test failed connection test."""
        mock_connection.test_connection.return_value = False

        result = client.test_connection()

        assert result is False
        mock_connection.test_connection.assert_called_once()
