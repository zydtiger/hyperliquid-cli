"""
Market data and watch snapshot operations for HyperliquidClient.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING

from models.api import (
    DEFAULT_WATCH_INTERVAL,
    DEFAULT_WATCH_ORDER_BOOK_DEPTH,
    CoinMetadata,
    ExchangeError,
    MarketType,
    Ticker,
    WatchInterval,
    WatchSnapshot,
)

from .helpers import normalize_spot_order_symbol, perp_open_interest_value
from .watch_snapshot import build_watch_snapshot_once

if TYPE_CHECKING:
    from .hyperliquid_client import HyperliquidClient

logger = logging.getLogger(__name__)
VALID_MARKET_TYPES: frozenset[str] = frozenset({"all", "perp", "spot"})


def get_available_coins(
    client: HyperliquidClient,
    market_type: MarketType = "all",
) -> list[str]:
    """Get list of available trading coins filtered by market type."""
    if market_type not in VALID_MARKET_TYPES:
        raise ValueError(f"Invalid market_type: {market_type!r}. Must be 'all', 'perp', or 'spot'.")

    def _get_available_coins() -> list[str]:
        if market_type == "spot":
            return list(dict.fromkeys(client._get_spot_symbol_map().values()))

        meta = client.connection.info.meta()
        coins = [asset["name"] for asset in meta["universe"]]

        if market_type == "perp":
            return coins

        try:
            for spot_symbol in client._get_spot_symbol_map().values():
                if spot_symbol not in coins:
                    coins.append(spot_symbol)
        except Exception:
            logger.exception("Failed to load spot symbols while listing available coins")

        return coins

    return client.connection.retry_operation(_get_available_coins)


def get_ticker(client: HyperliquidClient, coin: str) -> Ticker:
    """Get ticker information for a specific perp or spot coin."""

    def _get_ticker() -> Ticker:
        meta, asset_ctxs = client.connection.info.meta_and_asset_ctxs()
        if not meta or "universe" not in meta:
            raise ExchangeError("Failed to retrieve market metadata from exchange")

        available_coins = [asset["name"] for asset in meta["universe"]]
        if coin in available_coins:
            asset = asset_ctxs[available_coins.index(coin)]
            mark_price = Decimal(str(asset["markPx"]))
            return Ticker(
                coin=coin,
                mark_price=mark_price,
                funding_rate=Decimal(str(asset["funding"])),
                open_interest=perp_open_interest_value(mark_price, asset.get("openInterest")),
            )

        spot_symbol_map = client._get_spot_symbol_map()
        raw_symbol = normalize_spot_order_symbol(coin, spot_symbol_map)
        spot_meta, spot_ctxs = client.connection.info.spot_meta_and_asset_ctxs()
        spot_coins = [entry["name"] for entry in spot_meta.get("universe", [])]
        if raw_symbol in spot_coins:
            spot_asset = spot_ctxs[spot_coins.index(raw_symbol)]
            return Ticker(
                coin=coin,
                mark_price=Decimal(str(spot_asset["markPx"])),
                funding_rate=Decimal("0"),
                open_interest=None,
            )

        raise ExchangeError(f"Coin '{coin}' not found in available trading pairs")

    return client.connection.retry_operation(_get_ticker)


def get_metadata(client: HyperliquidClient, coin: str) -> CoinMetadata:
    """Get metadata for a specific perp or spot coin."""

    def _get_metadata() -> CoinMetadata:
        meta = client.connection.info.meta()
        if not meta or "universe" not in meta:
            raise ExchangeError("Failed to retrieve market metadata from exchange")

        for asset in meta["universe"]:
            if asset["name"] == coin:
                max_leverage = asset.get("maxLeverage")
                if max_leverage is None:
                    raise ExchangeError(f"Missing max leverage metadata for coin '{coin}'")
                return CoinMetadata(
                    coin=asset["name"],
                    size_decimals=asset["szDecimals"],
                    max_leverage=max_leverage,
                )

        spot_symbol_map = client._get_spot_symbol_map()
        raw_symbol = normalize_spot_order_symbol(coin, spot_symbol_map)
        spot_meta = client.connection.info.spot_meta()
        tokens = spot_meta.get("tokens", [])
        for spot_info in spot_meta.get("universe", []):
            if spot_info.get("name") == raw_symbol:
                token_indexes = spot_info.get("tokens", [])
                if len(token_indexes) >= 1:
                    base_info = tokens[token_indexes[0]]
                    return CoinMetadata(
                        coin=coin,
                        size_decimals=base_info.get("szDecimals", 0),
                        max_leverage=1,
                    )

        raise ExchangeError(f"Coin '{coin}' not found in available trading pairs")

    return client.connection.retry_operation(_get_metadata)


def get_watch_snapshot(
    client: HyperliquidClient,
    coin: str,
    interval: WatchInterval = DEFAULT_WATCH_INTERVAL,
    depth: int = DEFAULT_WATCH_ORDER_BOOK_DEPTH,
) -> WatchSnapshot:
    """Get the live WebSocket-backed watch snapshot for a supported market."""

    def _get_watch_snapshot() -> WatchSnapshot:
        market_coin = client._resolve_coin_symbol(coin.upper())
        snapshot = client._get_watch_registry().get_snapshot(market_coin, interval, depth)
        metadata = client.get_metadata(market_coin)
        return snapshot.model_copy(update={"size_decimals": metadata.size_decimals})

    return client.connection.retry_operation(_get_watch_snapshot)


def get_watch_snapshot_once(
    client: HyperliquidClient,
    coin: str,
    interval: WatchInterval = DEFAULT_WATCH_INTERVAL,
    depth: int = DEFAULT_WATCH_ORDER_BOOK_DEPTH,
) -> WatchSnapshot:
    """Get a one-shot REST watch snapshot without opening any WebSocket."""

    def _get_watch_snapshot_once() -> WatchSnapshot:
        market_coin = client._resolve_coin_symbol(coin.upper())
        metadata = client.get_metadata(market_coin)
        return build_watch_snapshot_once(
            client.connection.info,
            client.get_ticker,
            market_coin,
            interval=interval,
            depth=depth,
            size_decimals=metadata.size_decimals,
        )

    return client.connection.retry_operation(_get_watch_snapshot_once)
