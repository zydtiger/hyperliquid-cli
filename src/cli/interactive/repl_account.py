"""Account, market, and TUI command mixin for the interactive CLI."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager

from exchange import HyperliquidClient
from models.api import PnlHistoryCatalog, WatchInterval, WatchSnapshot
from models.config import Config

from ..formatters import AccountFormatter, TableFormatter
from ..runtime import CLI_VERSION


class ReplAccountMixin:
    """Provides account, market, and TUI commands for InteractiveCLI."""

    config: Config

    def _client_scope(self) -> AbstractContextManager[HyperliquidClient]:
        raise NotImplementedError

    def _create_client(self) -> HyperliquidClient:
        raise NotImplementedError

    def _run_pnl_tui(self, history_catalog: PnlHistoryCatalog) -> None:
        raise NotImplementedError

    def _run_watch_tui(
        self,
        coin: str,
        fetcher: Callable[[str, WatchInterval, int], WatchSnapshot],
    ) -> None:
        raise NotImplementedError

    def do_status(self, args: str) -> None:
        """Show account status."""
        try:
            with self._client_scope() as client:
                connected = client.test_connection()
                headers = ["Property", "Value"]
                rows = [
                    ["Account", self.config.hyperliquid.account_address or "Not configured"],
                    ["Network", self.config.hyperliquid.network.value],
                    ["Exchange", "connected" if connected else "disconnected"],
                    [
                        "Signing Key",
                        "configured" if self.config.hyperliquid.private_key else "not configured",
                    ],
                    ["Version", CLI_VERSION],
                ]
                formatter = TableFormatter()
                print(formatter.format((headers, rows), title="Account Status"))
                print()
        except Exception as e:
            print(f"❌ Error fetching status: {e}")
            print(f"Configured account: {self.config.hyperliquid.account_address}")
            print(f"Network: {self.config.hyperliquid.network}")

    def do_positions(self, args: str) -> None:
        """Show current positions."""
        try:
            with self._client_scope() as client:
                positions = client.get_positions()
                formatter = AccountFormatter()
                try:
                    print(formatter.format(positions))
                except ValueError as format_err:
                    print(format_err)
                print()
        except Exception as e:
            print(f"❌ Error fetching positions: {e}")

    def do_balances(self, args: str) -> None:
        """Show comprehensive balance information."""
        try:
            with self._client_scope() as client:
                balances = client.get_balances()
                formatter = AccountFormatter()
                try:
                    print(formatter.format(balances))
                except ValueError as format_err:
                    print(format_err)
                print()
        except Exception as e:
            print(f"❌ Error fetching balances: {e}")

    def do_staking(self, args: str) -> None:
        """Show staking status for the configured account."""
        if args.strip():
            print("❌ Error: staking does not take any arguments")
            print("Usage: staking")
            return

        try:
            with self._client_scope() as client:
                staking_status = client.get_staking_status()
                formatter = AccountFormatter()
                try:
                    print(formatter.format(staking_status))
                except ValueError as format_err:
                    print(format_err)
                print()
        except Exception as e:
            print(f"❌ Error fetching staking status: {e}")

    def do_info(self, args: str) -> None:
        """Get comprehensive information about a specific coin."""
        if not args.strip():
            print("❌ Error: Coin symbol is required")
            print("Usage: info <coin>")
            print("Example: info BTC")
            return

        coin = args.strip().upper()
        try:
            with self._client_scope() as client:
                print(f"\n⏳ Fetching information for {coin}...")
                ticker = client.get_ticker(coin)
                metadata = client.get_metadata(coin)

                ticker_rows = [
                    ["Coin", ticker.coin],
                    ["Mark Price", f"${ticker.mark_price:,.4f}"],
                    ["Funding Rate", f"{ticker.funding_rate * 100:.4f}%"],
                    [
                        "Open Interest",
                        "n/a" if ticker.open_interest is None else f"${ticker.open_interest:,.2f}",
                    ],
                ]
                metadata_rows = [
                    ["Coin", metadata.coin],
                    ["Size Decimals", str(metadata.size_decimals)],
                    ["Max Leverage", f"{metadata.max_leverage}x"],
                ]

                formatter = TableFormatter()
                print(
                    formatter.format(
                        (ticker_rows[0], ticker_rows[1:]),
                        title=f"📊 {coin} Ticker Information",
                    )
                )
                print(
                    formatter.format(
                        (metadata_rows[0], metadata_rows[1:]),
                        title=f"🔵 {coin} Metadata",
                    )
                )
                print()
        except Exception as e:
            print(f"❌ Error fetching information for {coin}: {e}")

    def do_pnl(self, args: str) -> None:
        """Show the fullscreen multi-window PnL dashboard."""
        if args.strip():
            print("❌ Error: pnl does not take any arguments")
            print("Usage: pnl")
            return

        try:
            with self._client_scope() as client:
                history_catalog = client.get_pnl_history()
                if not any(history.points for history in history_catalog.histories):
                    print("No PnL history found.")
                else:
                    self._run_pnl_tui(history_catalog)
                print(flush=True)
        except Exception as e:
            print(f"❌ Error fetching PnL history: {e}")

    def do_watch(self, args: str) -> None:
        """Launch the live watch TUI for a supported market using a per-watch client."""
        parts = args.strip().split()
        if len(parts) != 1:
            print("❌ Error: watch requires exactly one coin symbol")
            print("Usage: watch <coin>")
            return

        coin = parts[0].upper()
        try:
            # Dedicated client ensures the live watch WebSocket closes on TUI exit.
            with self._create_client() as watch_client:
                watch_client.get_watch_snapshot(coin)
                self._run_watch_tui(coin, watch_client.get_watch_snapshot)
                print(flush=True)
        except Exception as e:
            print(f"❌ Error fetching watch snapshot for {coin}: {e}")
