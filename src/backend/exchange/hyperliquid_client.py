"""
Hyperliquid client for interacting with the exchange API.

This module provides a high-level client interface for the Hyperliquid exchange,
handling data retrieval and portfolio management operations.
"""

from decimal import Decimal
from typing import List

from .hyperliquid_connection import HyperliquidConnection
from models.backend import (
    Ticker,
    CoinMetadata,
    PositionInfo,
    ExchangeError,
    LeverageType,
)
from models.config import Config


class HyperliquidClient:
    """
    High-level client for interacting with the Hyperliquid exchange.

    This class provides a simplified interface for common exchange operations
    like retrieving market data, positions, and account information.
    """

    def __init__(self, config: Config):
        """
        Initialize the Hyperliquid client.

        Args:
            config: Configuration object with exchange settings
        """
        self.config = config
        self.connection = HyperliquidConnection(config)

    def test_connection(self) -> bool:
        """
        Test the connection to the exchange.

        Returns:
            bool: True if connection is successful
        """
        return self.connection.test_connection()

    def get_available_coins(self) -> List[str]:
        """
        Get list of available trading coins.

        Returns:
            List[str]: List of available coin symbols
        """

        def _get_available_coins():
            meta = self.connection.info.meta()
            return [asset["name"] for asset in meta["universe"]]

        return self.connection.retry_operation(_get_available_coins)

    def get_ticker(self, coin: str) -> Ticker:
        """
        Get ticker information for a specific coin.

        Args:
            coin: Symbol of the cryptocurrency

        Returns:
            Ticker: Ticker data
        """

        def _get_ticker():
            meta, asset_ctxs = self.connection.info.meta_and_asset_ctxs()
            if not meta or "universe" not in meta:
                raise ExchangeError("Failed to retrieve market metadata from exchange")

            available_coins = [asset["name"] for asset in meta["universe"]]
            if coin not in available_coins:
                raise ExchangeError(
                    f"Coin '{coin}' not found in available trading pairs"
                )

            asset = asset_ctxs[available_coins.index(coin)]

            return Ticker(
                coin=coin,
                mark_price=Decimal(str(asset["markPx"])),
                funding_rate=Decimal(str(asset["funding"])),
                open_interest=Decimal(str(asset["openInterest"])),
            )

        return self.connection.retry_operation(_get_ticker)

    def get_metadata(self, coin: str) -> CoinMetadata:
        """
        Get metadata for a specific coin.

        Args:
            coin: Symbol of the cryptocurrency

        Returns:
            CoinMetadata: Coin metadata
        """

        def _get_metadata():
            meta = self.connection.info.meta()
            if not meta or "universe" not in meta:
                raise ExchangeError("Failed to retrieve market metadata from exchange")

            for asset in meta["universe"]:
                if asset["name"] == coin:
                    return CoinMetadata(
                        coin=asset["name"],
                        size_decimals=asset["szDecimals"],
                        max_leverage=asset["maxLeverage"],  # type: ignore
                    )

            raise ExchangeError(f"Coin '{coin}' not found in available trading pairs")

        return self.connection.retry_operation(_get_metadata)

    def get_positions(self) -> List[PositionInfo]:
        """
        Get current open positions.

        Returns:
            List[PositionInfo]: List of open positions
        """

        def _get_positions():
            user_state = self.connection.info.user_state(
                self.config.hyperliquid.account_address
            )
            positions = []

            for position in user_state.get("assetPositions", []):

                # position_sample_data = {
                #     "type": "oneWay",
                #     "position": {
                #         "coin": "ETH",
                #         "szi": "0.003",
                #         "leverage": {
                #             "type": "isolated",
                #             "value": 25,
                #             "rawUsd": "-11.080576",
                #         },
                #         "entryPx": "3845.9",
                #         "positionValue": "11.4921",
                #         "unrealizedPnl": "-0.0456",
                #         "returnOnEquity": "-0.0988065212",
                #         "liquidationPx": "3768.9034013605",
                #         "marginUsed": "0.411524",
                #         "maxLeverage": 25,
                #         "cumFunding": {
                #             "allTime": "87.082076",
                #             "sinceOpen": "0.0",
                #             "sinceChange": "0.0",
                #         },
                #     },
                # }

                if float(position["position"]["szi"]) != 0:  # Non-zero position
                    coin = position["position"]["coin"]
                    size = Decimal(str(position["position"]["szi"]))
                    entry_price = Decimal(str(position["position"]["entryPx"]))
                    mark_price = self.get_ticker(coin).mark_price
                    unrealized_pnl = Decimal(str(position["position"]["unrealizedPnl"]))
                    leverage = position["position"]["leverage"]["value"]
                    leverage_type = LeverageType(
                        position["position"]["leverage"]["type"]
                    )
                    margin_used = Decimal(str(position["position"]["marginUsed"]))
                    cum_funding = Decimal(
                        str(position["position"]["cumFunding"]["allTime"])
                    )

                    positions.append(
                        PositionInfo(
                            coin=coin,
                            size=size,
                            entry_price=entry_price,
                            mark_price=mark_price,
                            unrealized_pnl=unrealized_pnl,
                            leverage=leverage,
                            leverage_type=leverage_type,
                            margin_used=margin_used,
                            cum_funding=cum_funding,
                        )
                    )

            return positions

        return self.connection.retry_operation(_get_positions)


__all__ = [
    "HyperliquidClient",
]
