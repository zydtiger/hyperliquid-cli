"""Account read commands: balances, positions, staking, pnl."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

from exchange import HyperliquidClient
from models.api import (
    BalanceInfo,
    ExchangeError,
    PnlHistory,
    PnlHistoryCatalog,
    PnlWindow,
    PositionInfo,
    StakingStatus,
)
from models.config import Config, NetworkType

from ..formatters import AccountFormatter, TableFormatter
from ..interactive import PnlTUI
from ..interactive.pnl_tui.pnl_helpers import format_money, window_label
from ..runtime import resolve_options, run_command
from .parsers import (
    ADDRESS_OPTION,
    CONFIG_OPTION,
    JSON_OPTION,
    NETWORK_OPTION,
    parse_coin,
    parse_pnl_window,
)


def _is_interactive_tty() -> bool:
    """Return True when both stdin and stdout are attached to a TTY."""
    return sys.stdout.isatty() and sys.stdin.isatty()


def _render_pnl_summary_table(
    data: PnlHistoryCatalog | PnlHistory,
    requested_window: PnlWindow | None,
) -> None:
    """Render a compact text summary table for PnL history."""
    formatter = TableFormatter()
    histories = [data] if isinstance(data, PnlHistory) else data.histories

    rows: list[list[str]] = []
    for history in histories:
        if not history.points:
            rows.append([window_label(history.window), "0", "N/A", "N/A", "N/A"])
            continue
        latest = history.points[-1]
        rows.append(
            [
                window_label(history.window),
                str(len(history.points)),
                format_money(latest.total_pnl),
                format_money(latest.perp_pnl),
                format_money(latest.spot_pnl),
            ]
        )

    if not rows:
        print("No PnL history found.")
        return

    title = (
        f"PnL Summary ({window_label(requested_window)})"
        if requested_window is not None
        else "PnL Summary"
    )
    headers = ["Window", "Points", "Total PnL", "Perp PnL", "Spot PnL"]
    print(formatter.format((headers, rows), title=title))


def balances_command(
    ctx: typer.Context,
    config_path: Annotated[Path | None, CONFIG_OPTION] = None,
    address: Annotated[str | None, ADDRESS_OPTION] = None,
    network: Annotated[NetworkType | None, NETWORK_OPTION] = None,
    json_output: Annotated[bool, JSON_OPTION] = False,
) -> None:
    """Show perpetuals, spot, and staking balances."""
    opts = resolve_options(
        ctx,
        config_path=config_path,
        address=address,
        network=network,
        json_output=json_output,
    )

    def _execute(_config: Config, client: HyperliquidClient) -> BalanceInfo:
        return client.get_balances()

    def _render(result: BalanceInfo, _config: Config) -> None:
        print(AccountFormatter().format(result))

    run_command(
        "balances",
        opts,
        require_address=True,
        execute=_execute,
        render_human=_render,
    )


def positions_command(
    ctx: typer.Context,
    coin: Annotated[
        str | None,
        typer.Argument(help="Optional coin symbol filter (e.g., BTC)"),
    ] = None,
    config_path: Annotated[Path | None, CONFIG_OPTION] = None,
    address: Annotated[str | None, ADDRESS_OPTION] = None,
    network: Annotated[NetworkType | None, NETWORK_OPTION] = None,
    json_output: Annotated[bool, JSON_OPTION] = False,
) -> None:
    """Show current open positions, optionally filtered to one coin."""
    opts = resolve_options(
        ctx,
        config_path=config_path,
        address=address,
        network=network,
        json_output=json_output,
    )
    normalized_coin: list[str | None] = [None]

    def _validate() -> None:
        if coin is not None:
            normalized_coin[0] = parse_coin(coin)

    def _execute(_config: Config, client: HyperliquidClient) -> list[PositionInfo]:
        positions = client.get_positions()
        target = normalized_coin[0]
        if target is None:
            return positions
        matched = [pos for pos in positions if pos.coin.upper() == target]
        if not matched:
            raise ExchangeError(f"No open position found for {target}")
        return matched

    def _render(result: list[PositionInfo], _config: Config) -> None:
        print(AccountFormatter().format(result))

    run_command(
        "positions",
        opts,
        require_address=True,
        validate=_validate,
        execute=_execute,
        render_human=_render,
    )


def staking_command(
    ctx: typer.Context,
    config_path: Annotated[Path | None, CONFIG_OPTION] = None,
    address: Annotated[str | None, ADDRESS_OPTION] = None,
    network: Annotated[NetworkType | None, NETWORK_OPTION] = None,
    json_output: Annotated[bool, JSON_OPTION] = False,
) -> None:
    """Show HYPE staking summary and active validator delegations."""
    opts = resolve_options(
        ctx,
        config_path=config_path,
        address=address,
        network=network,
        json_output=json_output,
    )

    def _execute(_config: Config, client: HyperliquidClient) -> StakingStatus:
        return client.get_staking_status()

    def _render(result: StakingStatus, _config: Config) -> None:
        print(AccountFormatter().format(result))

    run_command(
        "staking",
        opts,
        require_address=True,
        execute=_execute,
        render_human=_render,
    )


def pnl_command(
    ctx: typer.Context,
    window: Annotated[
        str | None,
        typer.Option(
            "--window",
            help="PnL window (1d|3d|7d|1m|3m|6m|1y|all)",
        ),
    ] = None,
    config_path: Annotated[Path | None, CONFIG_OPTION] = None,
    address: Annotated[str | None, ADDRESS_OPTION] = None,
    network: Annotated[NetworkType | None, NETWORK_OPTION] = None,
    json_output: Annotated[bool, JSON_OPTION] = False,
) -> None:
    """Show PnL history as TUI (TTY), summary table, or JSON."""
    opts = resolve_options(
        ctx,
        config_path=config_path,
        address=address,
        network=network,
        json_output=json_output,
    )
    parsed_window: list[PnlWindow | None] = [None]

    def _validate() -> None:
        if window is not None:
            parsed_window[0] = parse_pnl_window(window)

    def _execute(_config: Config, client: HyperliquidClient) -> PnlHistoryCatalog | PnlHistory:
        catalog = client.get_pnl_history()
        target_window = parsed_window[0]
        if target_window is None:
            return catalog
        for history in catalog.histories:
            if history.window == target_window:
                return history
        return PnlHistory(window=target_window, points=[])

    def _render(result: PnlHistoryCatalog | PnlHistory, _config: Config) -> None:
        target_window = parsed_window[0]
        if (
            target_window is None
            and isinstance(result, PnlHistoryCatalog)
            and _is_interactive_tty()
        ):
            if not any(history.points for history in result.histories):
                print("No PnL history found.")
            else:
                PnlTUI(result).run()
            return
        _render_pnl_summary_table(result, target_window)

    run_command(
        "pnl",
        opts,
        require_address=True,
        validate=_validate,
        execute=_execute,
        render_human=_render,
    )


def register_account_commands(app: typer.Typer) -> None:
    """Register balances, positions, staking, and pnl commands."""
    app.command("balances")(balances_command)
    app.command("positions")(positions_command)
    app.command("staking")(staking_command)
    app.command("pnl")(pnl_command)
