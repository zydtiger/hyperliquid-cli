"""
Exchange connection management for the Hyperliquid CLI.

Provides a lazy 3-tier connection to the Hyperliquid exchange:
1. Default REST-only ``Info(base_url, skip_ws=True)`` with no WebSocket thread.
2. Lazy ``exchange`` signing client initialized only when a write operation runs.
3. Lazy WebSocket-enabled ``ws_info`` initialized only when live watch starts.
"""

import time
from collections.abc import Callable
from typing import TypeVar

import eth_account
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants

from models.api import ExchangeError
from models.config import Config, NetworkType

T = TypeVar("T")


class HyperliquidConnection:
    """
    Manages the connection to the Hyperliquid exchange.

    Read-only REST queries use ``self.info`` (``skip_ws=True``) without
    requiring a private key or starting any background WebSocket threads.
    """

    def __init__(self, config: Config, max_retries: int = 3, retry_delay: float = 1.0):
        """
        Initialize the REST-only exchange info connection.

        Args:
            config: Configuration object with exchange settings
            max_retries: Maximum number of retry attempts for failed operations
            retry_delay: Delay between retry attempts in seconds
        """
        self.config = config
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._base_url = self._get_base_url()
        self._exchange: Exchange | None = None
        self._ws_info: Info | None = None
        self.info: Info = self._init_info()

    def _init_info(self) -> Info:
        """Initialize the default REST-only Info client."""
        try:
            return Info(self._base_url, skip_ws=True)
        except Exception as e:
            raise ExchangeError(f"Failed to initialize exchange connection: {e}") from e

    @property
    def exchange(self) -> Exchange:
        """
        Lazily initialize and return the authenticated Exchange client.

        Raises:
            ExchangeError: If ``private_key`` is missing or initialization fails
        """
        if self._exchange is None:
            private_key = self.config.hyperliquid.private_key
            if not private_key:
                raise ExchangeError(
                    "Private key is required for write operations; "
                    "configure hyperliquid.private_key in your config file"
                )
            try:
                account = eth_account.Account.from_key(private_key)
                self._exchange = Exchange(account, self._base_url)
            except Exception as e:
                raise ExchangeError(f"Failed to initialize exchange signing client: {e}") from e
        return self._exchange

    @property
    def ws_info(self) -> Info:
        """
        Lazily initialize and return a WebSocket-enabled Info client.

        Created only when live watch streaming starts and stopped on ``close()``.
        """
        if self._ws_info is None:
            try:
                self._ws_info = Info(self._base_url, skip_ws=False)
            except Exception as e:
                raise ExchangeError(f"Failed to initialize websocket connection: {e}") from e
        return self._ws_info

    def _get_base_url(self) -> str:
        """Get the appropriate API URL based on network configuration."""
        return str(
            constants.MAINNET_API_URL
            if self.config.hyperliquid.network == NetworkType.MAINNET
            else constants.TESTNET_API_URL
        )

    def retry_operation(self, operation: Callable[[], T]) -> T:
        """
        Execute an operation with retry logic.

        Args:
            operation: The operation to execute (callable that returns T)

        Returns:
            Result of the operation (type T)

        Raises:
            ExchangeError: If all retry attempts fail
        """
        last_exception: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                return operation()
            except Exception as e:
                last_exception = e

                if attempt < self.max_retries:
                    delay = self.retry_delay * (2**attempt)
                    time.sleep(delay)
                else:
                    break

        raise ExchangeError(
            f"Operation failed after {self.max_retries + 1} attempts: {last_exception}"
        )

    def test_connection(self) -> bool:
        """
        Test the connection to the exchange.

        Returns:
            bool: True if connection is successful
        """
        try:
            meta = self.info.meta()
            return len(meta.get("universe", [])) > 0
        except Exception:
            return False

    def close(self) -> None:
        """Stop any active websocket manager when the connection is torn down."""
        ws_info = self._ws_info
        self._ws_info = None
        if ws_info is not None:
            ws_manager = getattr(ws_info, "ws_manager", None)
            if ws_manager is not None:
                ws_manager.stop()

        info_ws_manager = getattr(self.info, "ws_manager", None)
        if info_ws_manager is not None:
            info_ws_manager.stop()
