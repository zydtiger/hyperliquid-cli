"""
Hyperliquid CLI

Stateless and interactive command-line interface for Hyperliquid market data,
portfolio inspection, and smart order management.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from models.config import NetworkType

from . import runtime
from .commands import launch_cli, register_commands
from .commands.parsers import ADDRESS_OPTION, CONFIG_OPTION, JSON_OPTION, NETWORK_OPTION
from .runtime import (
    EXIT_VALIDATION_ERROR,
    CliRuntimeOptions,
    CliValidationError,
    JsonAwareTyperGroup,
    default_config_path,
    emit_options_error,
)

app = typer.Typer(
    name="hyperliquid-cli",
    help="Hyperliquid CLI - Stateless trading & portfolio CLI with interactive REPL",
    cls=JsonAwareTyperGroup,
)


@app.callback(invoke_without_command=True)
def default_run(
    ctx: typer.Context,
    config_path: Annotated[Path | None, CONFIG_OPTION] = None,
    address: Annotated[str | None, ADDRESS_OPTION] = None,
    network: Annotated[NetworkType | None, NETWORK_OPTION] = None,
    json_output: Annotated[bool, JSON_OPTION] = False,
) -> None:
    """Run the interactive REPL when no subcommand is provided."""
    options = CliRuntimeOptions(
        config_path=config_path,
        address=address,
        network=network,
        json_output=json_output,
    )
    ctx.obj = options

    if ctx.invoked_subcommand is None and not ctx.resilient_parsing:
        if json_output:
            exc = CliValidationError(
                "No subcommand provided; interactive REPL does not support --json"
            )
            emit_options_error("hyperliquid-cli", exc, None, options)
            raise typer.Exit(EXIT_VALIDATION_ERROR)

        explicit_config = config_path is not None
        target_path = config_path if config_path is not None else runtime.default_config_path
        launch_cli(
            target_path,
            address=address,
            network=network,
            must_exist=explicit_config,
        )


register_commands(app)


def main() -> None:
    """Entry point for the hyperliquid-cli console script."""
    app()


# Keep default_config_path accessible on cli.app for callers and tests.
_ = default_config_path
