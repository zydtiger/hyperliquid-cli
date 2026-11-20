"""
Hyperliquid client for interacting with the exchange API.

Provides a high-level, context-managed client interface for market data,
account queries, live/one-shot watch snapshots, and trading mutations.
"""

from decimal import Decimal
from types import TracebackType

from models.api import (
    DEFAULT_WATCH_INTERVAL,
    DEFAULT_WATCH_ORDER_BOOK_DEPTH,
    BalanceInfo,
    CoinMetadata,
    ExchangeError,
    MarketType,
    PnlHistoryCatalog,
    PositionInfo,
    StakingStatus,
    Ticker,
    WatchInterval,
    WatchSnapshot,
)
from models.config import Config
from models.leverage import LeverageResult
from models.margin import IsolatedMarginUpdateResult
from models.order import LimitOrder, MarketOrder, OrderHistoryEntry, OrderInfo, OrderResult
from models.portfolio import PortfolioSnapshot

from . import (
    account_ops,
    market_ops,
    order_change_ops,
    order_query_ops,
    order_submit_ops,
    portfolio,
    position_ops,
)
from .helpers import build_spot_symbol_map, normalize_spot_order_symbol, resolve_spot_symbol
from .hyperliquid_connection import HyperliquidConnection
from .watch_snapshot import LiveWatchRegistry


class HyperliquidClient:
    """
    High-level client for interacting with the Hyperliquid exchange.

    Supports use as a context manager and keeps WebSocket and signing
    connections lazy until needed.
    """

    def __init__(self, config: Config):
        """Initialize the Hyperliquid client with a REST-only default connection."""
        self.config = config
        self.connection = HyperliquidConnection(config)
        self._spot_symbol_map: dict[str, str] | None = None
        self._watch_registry: LiveWatchRegistry | None = None

    def __enter__(self) -> "HyperliquidClient":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def require_account_address(self) -> str:
        """Return the configured account address or raise ExchangeError."""
        address = self.config.hyperliquid.account_address
        if not address:
            raise ExchangeError(
                "Account address is required; configure hyperliquid.account_address "
                "or pass --address."
            )
        return address

    def _get_spot_symbol_map(self) -> dict[str, str]:
        """Load and cache raw spot-id to pair-symbol mappings."""
        if self._spot_symbol_map is None:
            self._spot_symbol_map = build_spot_symbol_map(self.connection.info.spot_meta())
        return self._spot_symbol_map

    def _resolve_coin_symbol(self, coin: str) -> str:
        """Resolve raw exchange spot ids while leaving perp symbols untouched."""
        if not coin.startswith("@"):
            return coin
        try:
            return resolve_spot_symbol(coin, self._get_spot_symbol_map())
        except Exception:
            return coin

    def _normalize_order_coin(self, coin: str) -> str:
        """Normalize user-facing spot pair symbols before submitting exchange orders."""
        try:
            return normalize_spot_order_symbol(coin, self._get_spot_symbol_map())
        except Exception:
            return coin

    def _get_watch_registry(self) -> LiveWatchRegistry:
        """Lazily create the WebSocket-backed watch registry on first live watch."""
        if self._watch_registry is None:
            self._watch_registry = LiveWatchRegistry(self.connection.ws_info, self.get_ticker)
        return self._watch_registry

    def test_connection(self) -> bool:
        """Test the connection to the exchange."""
        return self.connection.test_connection()

    def get_available_coins(self, market_type: MarketType = "all") -> list[str]:
        """Get list of available trading coins filtered by market type."""
        return market_ops.get_available_coins(self, market_type=market_type)

    def get_ticker(self, coin: str) -> Ticker:
        """Get ticker information for a specific coin."""
        return market_ops.get_ticker(self, coin)

    def get_metadata(self, coin: str) -> CoinMetadata:
        """Get metadata for a specific coin."""
        return market_ops.get_metadata(self, coin)

    def get_watch_snapshot(
        self,
        coin: str,
        interval: WatchInterval = DEFAULT_WATCH_INTERVAL,
        depth: int = DEFAULT_WATCH_ORDER_BOOK_DEPTH,
    ) -> WatchSnapshot:
        """Get the live in-memory WebSocket watch snapshot for a supported market."""
        return market_ops.get_watch_snapshot(self, coin, interval=interval, depth=depth)

    def get_watch_snapshot_once(
        self,
        coin: str,
        interval: WatchInterval = DEFAULT_WATCH_INTERVAL,
        depth: int = DEFAULT_WATCH_ORDER_BOOK_DEPTH,
    ) -> WatchSnapshot:
        """Get a one-shot REST watch snapshot without opening a WebSocket."""
        return market_ops.get_watch_snapshot_once(self, coin, interval=interval, depth=depth)

    def get_balances(self) -> BalanceInfo:
        """Get comprehensive balance information for the account."""
        return account_ops.get_balances(self)

    def get_pnl_history(self) -> PnlHistoryCatalog:
        """Get all supported total/perp/spot PnL history windows for the account."""
        return account_ops.get_pnl_history(self)

    def get_staking_status(self) -> StakingStatus:
        """Get staking status for the configured account."""
        return account_ops.get_staking_status(self)

    def get_positions(self) -> list[PositionInfo]:
        """Get current open positions."""
        return account_ops.get_positions(self)

    def get_portfolio(
        self,
        *,
        include_open_orders: bool = True,
        include_today: bool = True,
    ) -> PortfolioSnapshot:
        """Get a USD-enriched portfolio snapshot across perps, spot, staking, and vaults."""
        return portfolio.get_portfolio(
            self,
            include_open_orders=include_open_orders,
            include_today=include_today,
        )

    def get_order_status(self, order_id: int) -> OrderInfo:
        """Get the status and details of an order by its ID."""
        return order_query_ops.get_order_status(self, order_id)

    def get_open_orders(self) -> list[OrderInfo]:
        """Get all open orders for the account."""
        return order_query_ops.get_open_orders(self)

    def get_order_history(
        self,
        limit: int,
        since_ms: int | None = None,
    ) -> list[OrderHistoryEntry]:
        """Get recent filled-order history for the configured account."""
        return order_query_ops.get_order_history(self, limit, since_ms=since_ms)

    def submit_market_order(self, order: MarketOrder) -> OrderResult:
        """Submit a market order to the exchange."""
        return order_submit_ops.submit_market_order(self, order)

    def submit_limit_order(self, order: LimitOrder) -> OrderResult:
        """Submit a limit order to the exchange."""
        return order_submit_ops.submit_limit_order(self, order)

    def cancel_order(self, order_id: int | str) -> OrderResult:
        """Cancel a specific order or all open orders."""
        return order_change_ops.cancel_order(self, order_id)

    def modify_order(
        self,
        order_id: int,
        price: Decimal | None = None,
        quantity: Decimal | None = None,
    ) -> OrderResult:
        """Modify price and/or quantity of an existing open limit order."""
        return order_change_ops.modify_order(self, order_id, price=price, quantity=quantity)

    def change_leverage(self, leverage: int, coin: str, is_cross: bool = True) -> LeverageResult:
        """Change leverage for a specific position."""
        return position_ops.change_leverage(self, leverage, coin, is_cross=is_cross)

    def update_isolated_margin(self, amount: Decimal, coin: str) -> IsolatedMarginUpdateResult:
        """Update isolated margin for a specific position."""
        return position_ops.update_isolated_margin(self, amount, coin)

    def close(self) -> None:
        """Release watch subscriptions and the underlying exchange connection."""
        if self._watch_registry is not None:
            self._watch_registry.close()
        self.connection.close()
