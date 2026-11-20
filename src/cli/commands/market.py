"""Public market data commands: coins, info, watch."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer

from exchange import HyperliquidClient
from models.api import (
    DEFAULT_WATCH_INTERVAL,
    DEFAULT_WATCH_ORDER_BOOK_DEPTH,
    MarketType,
    WatchInterval,
    WatchSnapshot,
)
from models.config import Config, NetworkType

from ..formatters import TableFormatter
from ..interactive import WatchTUI
from ..runtime import resolve_options, run_command
from .parsers import (
    ADDRESS_OPTION,
    CONFIG_OPTION,
    JSON_OPTION,
    NETWORK_OPTION,
    parse_coin,
    parse_market_type,
    parse_watch_depth,
    parse_watch_interval,
)


def _render_info_human(data: dict[str, Any], _config: Config) -> None:
    """Render ticker and metadata tables for a coin."""
    ticker = data["ticker"]
    metadata = data["metadata"]
    coin = data["coin"]

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
    print(formatter.format((metadata_rows[0], metadata_rows[1:]), title=f"🔵 {coin} Metadata"))


def register_market_commands(app: typer.Typer) -> None:
    """Register coins, info, and watch commands."""

    @app.command("coins")
    def coins_command(
        ctx: typer.Context,
        market_type: Annotated[
            str,
            typer.Option("--type", help="Filter market type (all|perp|spot)"),
        ] = "all",
        config_path: Annotated[Path | None, CONFIG_OPTION] = None,
        address: Annotated[str | None, ADDRESS_OPTION] = None,
        network: Annotated[NetworkType | None, NETWORK_OPTION] = None,
        json_output: Annotated[bool, JSON_OPTION] = False,
    ) -> None:
        """List available tradable coins (public read-only)."""
        opts = resolve_options(
            ctx,
            config_path=config_path,
            address=address,
            network=network,
            json_output=json_output,
        )
        parsed_type: list[MarketType] = ["all"]

        def _validate() -> None:
            parsed_type[0] = parse_market_type(market_type)

        def _execute(_config: Config, client: HyperliquidClient) -> list[str]:
            return client.get_available_coins(market_type=parsed_type[0])

        def _render(result: list[str], _config: Config) -> None:
            if not result:
                print(f"No coins found for type '{parsed_type[0]}'.")
                return
            rows = [[symbol] for symbol in result]
            print(
                TableFormatter().format(
                    (["Coin"], rows),
                    title=f"Available Coins ({parsed_type[0]}: {len(result)})",
                )
            )

        run_command(
            "coins",
            opts,
            require_address=False,
            validate=_validate,
            execute=_execute,
            render_human=_render,
        )

    @app.command("info")
    def info_command(
        ctx: typer.Context,
        coin: Annotated[str, typer.Argument(help="Coin symbol (e.g., BTC, ETH, UBTC/USDC)")],
        config_path: Annotated[Path | None, CONFIG_OPTION] = None,
        address: Annotated[str | None, ADDRESS_OPTION] = None,
        network: Annotated[NetworkType | None, NETWORK_OPTION] = None,
        json_output: Annotated[bool, JSON_OPTION] = False,
    ) -> None:
        """Show ticker and metadata for a coin (public read-only)."""
        opts = resolve_options(
            ctx,
            config_path=config_path,
            address=address,
            network=network,
            json_output=json_output,
        )
        parsed_coin: list[str] = [""]

        def _validate() -> None:
            parsed_coin[0] = parse_coin(coin)

        def _execute(_config: Config, client: HyperliquidClient) -> dict[str, Any]:
            symbol = parsed_coin[0]
            ticker = client.get_ticker(symbol)
            metadata = client.get_metadata(symbol)
            return {
                "coin": ticker.coin,
                "ticker": ticker,
                "metadata": metadata,
            }

        run_command(
            "info",
            opts,
            require_address=False,
            validate=_validate,
            execute=_execute,
            render_human=_render_info_human,
        )

    @app.command("watch")
    def watch_command(
        ctx: typer.Context,
        coin: Annotated[str, typer.Argument(help="Market symbol (e.g., BTC, ETH, UBTC/USDC)")],
        interval: Annotated[
            str,
            typer.Option("--interval", help="Candle interval (1m|5m|15m|1h|4h|1d)"),
        ] = DEFAULT_WATCH_INTERVAL,
        depth: Annotated[
            int,
            typer.Option("--depth", help="Order book depth per side (1-50)"),
        ] = DEFAULT_WATCH_ORDER_BOOK_DEPTH,
        config_path: Annotated[Path | None, CONFIG_OPTION] = None,
        address: Annotated[str | None, ADDRESS_OPTION] = None,
        network: Annotated[NetworkType | None, NETWORK_OPTION] = None,
        json_output: Annotated[bool, JSON_OPTION] = False,
    ) -> None:
        """Show one-shot REST snapshot (--json) or live WebSocket WatchTUI."""
        opts = resolve_options(
            ctx,
            config_path=config_path,
            address=address,
            network=network,
            json_output=json_output,
        )
        parsed_coin: list[str] = [""]
        parsed_interval: list[WatchInterval] = [DEFAULT_WATCH_INTERVAL]
        parsed_depth: list[int] = [DEFAULT_WATCH_ORDER_BOOK_DEPTH]

        def _validate() -> None:
            parsed_coin[0] = parse_coin(coin)
            parsed_interval[0] = parse_watch_interval(interval)
            parsed_depth[0] = parse_watch_depth(depth)

        def _execute(_config: Config, client: HyperliquidClient) -> WatchSnapshot | None:
            symbol = parsed_coin[0]
            iv = parsed_interval[0]
            dp = parsed_depth[0]
            if opts.json_output:
                return client.get_watch_snapshot_once(symbol, interval=iv, depth=dp)
            client.get_watch_snapshot(symbol, interval=iv, depth=dp)
            WatchTUI(
                symbol,
                client.get_watch_snapshot,
                initial_interval=iv,
                initial_depth=dp,
            ).run()
            return None

        def _render(_result: WatchSnapshot | None, _config: Config) -> None:
            return None

        run_command(
            "watch",
            opts,
            require_address=False,
            validate=_validate,
            execute=_execute,
            render_human=_render,
        )
