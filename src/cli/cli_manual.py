"""Utilities for generating the interactive CLI manual."""

from cmd import Cmd
from collections.abc import Iterable
from contextlib import redirect_stdout
from io import StringIO


def _capture_help_output(cli: Cmd, command: str) -> str:
    """Capture the rendered help output for a single command."""
    buffer = StringIO()
    with redirect_stdout(buffer):
        cli.do_help(command)

    output = buffer.getvalue().strip()
    if output:
        return output
    return f"{command} - No help available"


def _discover_cli_commands(cli: Cmd) -> tuple[str, ...]:
    """Return user-facing command names from project-defined do_* methods."""
    commands: list[str] = []
    seen: set[str] = set()

    for cls in reversed(type(cli).mro()):
        if cls in {Cmd, object}:
            continue
        for attribute_name in cls.__dict__:
            if not attribute_name.startswith("do_"):
                continue
            command_name = attribute_name.removeprefix("do_")
            if command_name in seen:
                continue
            seen.add(command_name)
            commands.append(command_name)

    return tuple(commands)


def build_cli_manual(cli: Cmd, commands: Iterable[str] | None = None) -> str:
    """Build the aggregate CLI manual from live help output."""
    manual_commands = tuple(commands) if commands is not None else _discover_cli_commands(cli)
    sections = [
        "# Hyperliquid CLI Manual",
        "",
        "This document aggregates the interactive CLI help output for user-facing commands.",
        "",
    ]

    for command in manual_commands:
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


__all__ = ["build_cli_manual"]
