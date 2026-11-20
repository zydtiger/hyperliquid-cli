"""Shared CLI runtime options, config loading, and command execution wrapper."""

from __future__ import annotations

import logging
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import typer

from exchange import HyperliquidClient
from models.config import Config, ConfigurationError, NetworkType

from .json_output import (
    EXIT_RUNTIME_ERROR,
    EXIT_SUCCESS,
    EXIT_VALIDATION_ERROR,
    JsonAwareTyperGroup,
    emit_json_error,
    emit_json_raw,
    emit_json_success,
)

try:
    CLI_VERSION = version("hyperliquid-cli")
except PackageNotFoundError:
    CLI_VERSION = "0.2.0"

default_config_path = Path.home() / ".hyperliquid-cli" / "config.yaml"


class CliValidationError(ValueError):
    """Raised when CLI arguments or options fail semantic validation (exit code 2)."""


class CliRuntimeOptions:
    """Resolved global runtime options shared between root callback and subcommands."""

    def __init__(
        self,
        *,
        config_path: Path | None = None,
        address: str | None = None,
        network: NetworkType | None = None,
        json_output: bool = False,
    ) -> None:
        self.config_path = config_path
        self.address = address
        self.network = network
        self.json_output = json_output


def resolve_options(
    ctx: typer.Context,
    *,
    config_path: Path | None = None,
    address: str | None = None,
    network: NetworkType | None = None,
    json_output: bool = False,
) -> CliRuntimeOptions:
    """Merge root callback options with subcommand-level overrides."""
    root = ctx.obj if isinstance(ctx.obj, CliRuntimeOptions) else CliRuntimeOptions()
    return CliRuntimeOptions(
        config_path=config_path if config_path is not None else root.config_path,
        address=address if address is not None else root.address,
        network=network if network is not None else root.network,
        json_output=root.json_output or json_output,
    )


def load_cli_config(options: CliRuntimeOptions, *, require_address: bool) -> Config:
    """Load CLI configuration respecting explicit ``--config`` and default fallback."""
    explicit_config = options.config_path is not None
    target_path = options.config_path if explicit_config else default_config_path
    return Config.load_for_cli(
        target_path,
        address=options.address,
        network=options.network,
        require_address=require_address,
        must_exist=explicit_config,
    )


def emit_options_success(
    command: str,
    data: Any,
    config: Config | None,
    options: CliRuntimeOptions,
) -> None:
    """Emit a standard JSON success envelope using resolved runtime options."""
    emit_json_success(
        command,
        data,
        config,
        network=options.network,
        address=options.address,
    )


def emit_options_error(
    command: str,
    exc: BaseException,
    config: Config | None,
    options: CliRuntimeOptions,
) -> None:
    """Emit a standard JSON error envelope using resolved runtime options."""
    emit_json_error(
        command,
        exc,
        config,
        network=options.network,
        address=options.address,
    )


def _handle_command_error(
    command: str,
    exc: Exception,
    config: Config | None,
    options: CliRuntimeOptions,
    *,
    exit_code: int,
    prefix: str,
) -> None:
    """Render an error in JSON or human mode and exit with the appropriate status code."""
    if options.json_output:
        emit_options_error(command, exc, config, options)
    else:
        typer.echo(f"❌ {prefix}: {exc}", err=True)
    raise typer.Exit(exit_code) from exc


def run_command(
    command: str,
    options: CliRuntimeOptions,
    *,
    require_address: bool,
    execute: Callable[[Config, HyperliquidClient], Any],
    render_human: Callable[[Any, Config], None],
    validate: Callable[[], None] | None = None,
    raw_json: bool = False,
) -> None:
    """Execute a stateless CLI subcommand with unified error and JSON handling."""
    previous_disable = logging.root.manager.disable
    if options.json_output:
        logging.disable(logging.CRITICAL)

    config: Config | None = None
    try:
        if validate is not None:
            validate()
        config = load_cli_config(options, require_address=require_address)
        with HyperliquidClient(config) as client:
            result = execute(config, client)

        if not options.json_output:
            render_human(result, config)
            return

        if raw_json:
            emit_json_raw(result)
        else:
            emit_options_success(command, result, config, options)
    except typer.Exit:
        raise
    except CliValidationError as exc:
        _handle_command_error(
            command,
            exc,
            config,
            options,
            exit_code=EXIT_VALIDATION_ERROR,
            prefix="Validation error",
        )
    except ConfigurationError as exc:
        _handle_command_error(
            command,
            exc,
            config,
            options,
            exit_code=EXIT_RUNTIME_ERROR,
            prefix="Configuration error",
        )
    except Exception as exc:
        _handle_command_error(
            command,
            exc,
            config,
            options,
            exit_code=EXIT_RUNTIME_ERROR,
            prefix="Error",
        )
    finally:
        if options.json_output:
            logging.disable(previous_disable)


_ = (EXIT_SUCCESS, JsonAwareTyperGroup)
