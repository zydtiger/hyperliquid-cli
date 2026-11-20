"""
Tests for lazy 3-tier HyperliquidConnection behavior.
"""

from unittest.mock import Mock, patch

import pytest

from exchange.hyperliquid_connection import HyperliquidConnection
from models.api import ExchangeError
from models.config import Config, HyperliquidConfig, NetworkType

VALID_ADDRESS = "0x1234567890123456789012345678901234567890"
VALID_PRIVATE_KEY = "0x1234567890123456789012345678901234567890123456789012345678901234"


class TestHyperliquidConnectionLazyTiers:
    """Verify 3-tier lazy connection lifecycle."""

    def test_init_creates_rest_info_only_without_private_key_or_ws(self) -> None:
        """Startup uses Info(..., skip_ws=True) and never touches private_key or WS."""
        config = Config()
        mock_info = Mock(ws_manager=None)

        with (
            patch("exchange.hyperliquid_connection.Info", return_value=mock_info) as mock_info_cls,
            patch("exchange.hyperliquid_connection.Exchange") as mock_exchange_cls,
            patch("exchange.hyperliquid_connection.eth_account.Account.from_key") as mock_from_key,
        ):
            conn = HyperliquidConnection(config)

        assert conn.info is mock_info
        mock_info_cls.assert_called_once_with("https://api.hyperliquid.xyz", skip_ws=True)
        mock_exchange_cls.assert_not_called()
        mock_from_key.assert_not_called()

    def test_testnet_base_url_selected(self) -> None:
        """Testnet config connects to Hyperliquid testnet API URL."""
        config = Config(hyperliquid=HyperliquidConfig(network=NetworkType.TESTNET))
        with patch("exchange.hyperliquid_connection.Info", return_value=Mock()) as mock_info_cls:
            HyperliquidConnection(config)

        mock_info_cls.assert_called_once_with("https://api.hyperliquid-testnet.xyz", skip_ws=True)

    def test_exchange_property_raises_when_private_key_missing(self) -> None:
        """Accessing exchange without a private_key raises ExchangeError."""
        config = Config(hyperliquid=HyperliquidConfig(account_address=VALID_ADDRESS))
        with patch("exchange.hyperliquid_connection.Info", return_value=Mock()):
            conn = HyperliquidConnection(config)

        with pytest.raises(ExchangeError, match="Private key is required"):
            _ = conn.exchange

    def test_exchange_property_lazily_initializes_and_caches(self) -> None:
        """Accessing exchange lazily creates Exchange once using Account.from_key."""
        config = Config(
            hyperliquid=HyperliquidConfig(
                account_address=VALID_ADDRESS,
                private_key=VALID_PRIVATE_KEY,
            )
        )
        mock_account = Mock()
        mock_exchange = Mock()

        with (
            patch("exchange.hyperliquid_connection.Info", return_value=Mock()),
            patch(
                "exchange.hyperliquid_connection.eth_account.Account.from_key",
                return_value=mock_account,
            ) as mock_from_key,
            patch(
                "exchange.hyperliquid_connection.Exchange",
                return_value=mock_exchange,
            ) as mock_exchange_cls,
        ):
            conn = HyperliquidConnection(config)
            mock_from_key.assert_not_called()
            mock_exchange_cls.assert_not_called()

            first = conn.exchange
            second = conn.exchange

        assert first is mock_exchange
        assert second is mock_exchange
        mock_from_key.assert_called_once_with(VALID_PRIVATE_KEY)
        mock_exchange_cls.assert_called_once_with(mock_account, "https://api.hyperliquid.xyz")

    def test_ws_info_lazily_initializes_and_closes_cleanly(self) -> None:
        """ws_info initializes Info(skip_ws=False) only on demand and stops on close()."""
        config = Config()
        rest_info = Mock(ws_manager=None)
        ws_manager = Mock()
        ws_info_instance = Mock(ws_manager=ws_manager)

        with patch(
            "exchange.hyperliquid_connection.Info",
            side_effect=[rest_info, ws_info_instance],
        ) as mock_info_cls:
            conn = HyperliquidConnection(config)
            assert mock_info_cls.call_count == 1

            first = conn.ws_info
            second = conn.ws_info

            assert first is ws_info_instance
            assert second is ws_info_instance
            assert mock_info_cls.call_count == 2
            assert mock_info_cls.call_args_list[1].kwargs == {"skip_ws": False}

            conn.close()

        ws_manager.stop.assert_called_once_with()

    def test_close_without_ws_info_does_not_open_ws(self) -> None:
        """Calling close() without ever touching ws_info creates no WebSocket."""
        config = Config()
        rest_info = Mock(ws_manager=None)

        with patch("exchange.hyperliquid_connection.Info", return_value=rest_info) as mock_info_cls:
            conn = HyperliquidConnection(config)
            conn.close()

        mock_info_cls.assert_called_once_with("https://api.hyperliquid.xyz", skip_ws=True)

    def test_test_connection_and_retry_operation(self) -> None:
        """test_connection and retry_operation behave as expected."""
        config = Config()
        rest_info = Mock(ws_manager=None)
        rest_info.meta.return_value = {"universe": [{"name": "BTC"}]}

        with patch("exchange.hyperliquid_connection.Info", return_value=rest_info):
            conn = HyperliquidConnection(config, max_retries=1, retry_delay=0.0)

        assert conn.test_connection() is True

        attempts = {"count": 0}

        def flaky() -> str:
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise RuntimeError("transient")
            return "ok"

        assert conn.retry_operation(flaky) == "ok"
        assert attempts["count"] == 2

        with pytest.raises(ExchangeError, match="Operation failed after 2 attempts: boom"):
            conn.retry_operation(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
