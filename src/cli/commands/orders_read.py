"""Read-only order commands: open-orders, order-status, order-history."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from exchange import HyperliquidClient
from models.config import Config, NetworkType
from models.order import OrderHistoryEntry, OrderInfo

from ..formatters import OrderFormatter
from ..runtime import resolve_options, run_command
from .parsers import (
    ADDRESS_OPTION,
    CONFIG_OPTION,
    JSON_OPTION,
    NETWORK_OPTION,
    parse_coin,
    parse_positive_int,
    parse_since_ms,
)

DEFAULT_HISTORY_LIMIT = 10


def register_order_read_commands(app: typer.Typer) -> None:
    """Register open-orders, order-status, and order-history commands."""

    @app.command("open-orders")
    def open_orders_command(
        ctx: typer.Context,
        coin: Annotated[
            str | None,
            typer.Option("--coin", help="Filter open orders by coin symbol (case-insensitive)"),
        ] = None,
        config_path: Annotated[Path | None, CONFIG_OPTION] = None,
        address: Annotated[str | None, ADDRESS_OPTION] = None,
        network: Annotated[NetworkType | None, NETWORK_OPTION] = None,
        json_output: Annotated[bool, JSON_OPTION] = False,
    ) -> None:
        """List currently open orders, optionally filtered by coin."""
        opts = resolve_options(
            ctx,
            config_path=config_path,
            address=address,
            network=network,
            json_output=json_output,
        )
        coin_filter: list[str | None] = [None]

        def _validate() -> None:
            if coin is not None:
                coin_filter[0] = parse_coin(coin)

        def _execute(_config: Config, client: HyperliquidClient) -> list[OrderInfo]:
            orders = client.get_open_orders()
            target = coin_filter[0]
            if target is None:
                return orders
            return [order for order in orders if order.coin.upper() == target]

        def _render(result: list[OrderInfo], _config: Config) -> None:
            print(OrderFormatter().format(result))

        run_command(
            "open-orders",
            opts,
            require_address=True,
            validate=_validate,
            execute=_execute,
            render_human=_render,
        )

    @app.command("order-status")
    def order_status_command(
        ctx: typer.Context,
        order_id: Annotated[int, typer.Argument(help="Positive integer order ID (OID)")],
        config_path: Annotated[Path | None, CONFIG_OPTION] = None,
        address: Annotated[str | None, ADDRESS_OPTION] = None,
        network: Annotated[NetworkType | None, NETWORK_OPTION] = None,
        json_output: Annotated[bool, JSON_OPTION] = False,
    ) -> None:
        """Get status and details of a specific order by ID."""
        opts = resolve_options(
            ctx,
            config_path=config_path,
            address=address,
            network=network,
            json_output=json_output,
        )

        def _validate() -> None:
            parse_positive_int(order_id, "Order ID")

        def _execute(_config: Config, client: HyperliquidClient) -> OrderInfo:
            return client.get_order_status(order_id)

        def _render(result: OrderInfo, _config: Config) -> None:
            print(OrderFormatter().format(result))

        run_command(
            "order-status",
            opts,
            require_address=True,
            validate=_validate,
            execute=_execute,
            render_human=_render,
        )

    @app.command("order-history")
    def order_history_command(
        ctx: typer.Context,
        limit: Annotated[
            int,
            typer.Option("--limit", help="Maximum number of filled-order entries"),
        ] = DEFAULT_HISTORY_LIMIT,
        since: Annotated[
            str | None,
            typer.Option(
                "--since",
                help="Start time filter as ISO-8601 datetime or Unix millisecond integer",
            ),
        ] = None,
        config_path: Annotated[Path | None, CONFIG_OPTION] = None,
        address: Annotated[str | None, ADDRESS_OPTION] = None,
        network: Annotated[NetworkType | None, NETWORK_OPTION] = None,
        json_output: Annotated[bool, JSON_OPTION] = False,
    ) -> None:
        """Show recent filled-order history."""
        opts = resolve_options(
            ctx,
            config_path=config_path,
            address=address,
            network=network,
            json_output=json_output,
        )
        parsed_since_ms: list[int | None] = [None]

        def _validate() -> None:
            parse_positive_int(limit, "--limit")
            if since is not None:
                parsed_since_ms[0] = parse_since_ms(since)

        def _execute(_config: Config, client: HyperliquidClient) -> list[OrderHistoryEntry]:
            return client.get_order_history(limit, since_ms=parsed_since_ms[0])

        def _render(result: list[OrderHistoryEntry], _config: Config) -> None:
            print(OrderFormatter().format(result))

        run_command(
            "order-history",
            opts,
            require_address=True,
            validate=_validate,
            execute=_execute,
            render_human=_render,
        )
