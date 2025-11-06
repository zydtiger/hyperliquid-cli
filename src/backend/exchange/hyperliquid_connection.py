"""
Exchange connection management for the Hyperliquid CLI.

This module handles the connection to the Hyperliquid exchange including
authentication, retry logic, and connection testing.
"""

import time
from typing import Callable, TypeVar

from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants
import eth_account

from models.api import ExchangeError
from models.config import Config, NetworkType

T = TypeVar("T")


class HyperliquidConnection:
    """
    Manages the connection to the Hyperliquid exchange.

    This class handles authentication, retry logic, and provides
    a stable connection interface for other exchange components.
    """

    def __init__(self, config: Config, max_retries: int = 3, retry_delay: float = 1.0):
        """
        Initialize the exchange connection.

        Args:
            config: Configuration object with exchange settings
            max_retries: Maximum number of retry attempts for failed operations
            retry_delay: Delay between retry attempts in seconds
        """
        self.config = config
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # Initialize exchange connection
        self._init_exchange()

    def _init_exchange(self) -> None:
        """Initialize the exchange connection."""
        try:
            # Create account from private key
            account = eth_account.Account.from_key(self.config.hyperliquid.private_key)

            # Initialize exchange and info clients
            base_url = self._get_base_url()
            self.exchange = Exchange(account, base_url)
            self.info = Info(base_url)

        except Exception as e:
            raise ExchangeError(f"Failed to initialize exchange connection: {e}")

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
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                return operation()
            except Exception as e:
                last_exception = e

                if attempt < self.max_retries:
                    # Exponential backoff
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
            # Try to get available symbols as a connection test
            meta = self.info.meta()
            return len(meta.get("universe", [])) > 0
        except Exception:
            return False


__all__ = [
    "HyperliquidConnection",
]
