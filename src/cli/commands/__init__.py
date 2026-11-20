"""Stateless CLI subcommand registration."""

from __future__ import annotations

import typer

from .account import register_account_commands
from .market import register_market_commands
from .order_create import register_order_create_command
from .order_manage import register_order_manage_commands
from .orders_read import register_order_read_commands
from .portfolio import register_portfolio_commands
from .positions_write import register_position_write_commands
from .system import launch_cli, register_system_commands


def register_commands(app: typer.Typer) -> None:
    """Register all stateless and interactive subcommands on the root Typer app."""
    register_system_commands(app)
    register_portfolio_commands(app)
    register_account_commands(app)
    register_market_commands(app)
    register_order_read_commands(app)
    register_order_create_command(app)
    register_order_manage_commands(app)
    register_position_write_commands(app)


__all__ = ["launch_cli", "register_commands"]
