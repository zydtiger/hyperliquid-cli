"""Utilities for generating the interactive CLI manual."""

from cmd import Cmd
from collections.abc import Iterable
from contextlib import redirect_stdout
from io import StringIO

INTERACTIVE_COMMANDS = (
    "ask",
    "order",
    "status",
    "positions",
    "balances",
    "staking",
    "conditionals",
    "clear",
    "cls",
    "quit",
    "exit",
    "order_status",
    "info",
    "open_orders",
    "order_history",
    "pnl",
    "cancel_order",
    "modify_order",
    "change_leverage",
    "update_margin",
)


def _capture_help_output(cli: Cmd, command: str) -> str:
    """Capture the rendered help output for a single command."""
    buffer = StringIO()
    with redirect_stdout(buffer):
        cli.do_help(command)

    output = buffer.getvalue().strip()
    if output:
        return output
    return f"{command} - No help available"


def build_cli_manual(cli: Cmd, commands: Iterable[str] = INTERACTIVE_COMMANDS) -> str:
    """Build the aggregate CLI manual from live help output."""
    sections = [
        "# Hyperliquid CLI Manual",
        "",
        "This document aggregates the interactive CLI help output for user-facing commands.",
        "",
    ]

    for command in commands:
        sections.extend(
            [
                f"## {command}",
                "",
                "```text",
                _capture_help_output(cli, command),
                "```",
                "",
            ]
        )

    return "\n".join(sections).rstrip() + "\n"


__all__ = ["INTERACTIVE_COMMANDS", "build_cli_manual"]
