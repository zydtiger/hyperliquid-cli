"""System and session commands: repl, create-config, status."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from exchange import HyperliquidClient
from models.config import Config, ConfigurationError, NetworkType

from .. import runtime
from ..formatters import TableFormatter
from ..interactive_cli import InteractiveCLI
from ..runtime import (
    CLI_VERSION,
    EXIT_RUNTIME_ERROR,
    EXIT_VALIDATION_ERROR,
    CliValidationError,
    emit_options_error,
    emit_options_success,
    resolve_options,
    run_command,
)
from .parsers import ADDRESS_OPTION, CONFIG_OPTION, JSON_OPTION, NETWORK_OPTION

FALLBACK_CONFIG_TEMPLATE = """hyperliquid:
  account_address: "your_ethereum_address_here"
  private_key: "your_hyperliquid_private_key_here"
  network: "mainnet" # 'mainnet' or 'testnet'

trading:
  default_slippage: 0.005 # 0.5%
  default_time_in_force: "GTC"

agent:
  api_key: "your_openai_api_key_here"
  openai_base_url: "your_openai_compatible_base_url_here"
  model_id: "your_model_id_here"
"""


def _example_config_path() -> Path:
    """Resolve the repository's config.example.yaml template path."""
    return Path(__file__).resolve().parents[3] / "config.example.yaml"


def launch_cli(
    config_path: Path,
    *,
    address: str | None = None,
    network: NetworkType | None = None,
    must_exist: bool = False,
) -> None:
    """Load config, verify Hyperliquid /info connectivity, and start InteractiveCLI."""
    try:
        config = Config.load_for_cli(
            config_path,
            address=address,
            network=network,
            require_address=True,
            must_exist=must_exist,
        )
    except ConfigurationError as e:
        typer.echo(f"❌ Failed to load configuration: {e}", err=True)
        raise typer.Exit(EXIT_RUNTIME_ERROR) from e

    typer.echo("🔌 Checking connection to Hyperliquid...")
    try:
        with HyperliquidClient(config) as client:
            if not client.test_connection():
                typer.echo("❌ Failed to connect to Hyperliquid exchange", err=True)
                raise typer.Exit(EXIT_RUNTIME_ERROR)

            typer.echo(f"✅ Connected to Hyperliquid exchange ({config.hyperliquid.network.value})")
            print()
            InteractiveCLI(config, client=client).run()
    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"❌ Fatal error: {e}", err=True)
        raise typer.Exit(EXIT_RUNTIME_ERROR) from e


def _render_status(data: dict[str, Any], _config: Config) -> None:
    """Render status information as a human-readable table."""
    rows = [
        ["Account", data["account_address"] or "Not configured"],
        ["Network", data["network"]],
        ["Connected", "yes" if data["connected"] else "no"],
        ["Signing Key", "configured" if data["has_private_key"] else "not configured"],
        ["Version", data["version"]],
    ]
    print(TableFormatter().format((["Property", "Value"], rows), title="Hyperliquid Status"))


def register_system_commands(app: typer.Typer) -> None:
    """Register repl, create-config, and status commands on the Typer app."""

    @app.command("repl")
    def repl_command(
        ctx: typer.Context,
        config_path: Annotated[Path | None, CONFIG_OPTION] = None,
        address: Annotated[str | None, ADDRESS_OPTION] = None,
        network: Annotated[NetworkType | None, NETWORK_OPTION] = None,
        json_output: Annotated[bool, JSON_OPTION] = False,
    ) -> None:
        """Launch the interactive REPL session."""
        opts = resolve_options(
            ctx,
            config_path=config_path,
            address=address,
            network=network,
            json_output=json_output,
        )
        if opts.json_output:
            exc = CliValidationError("repl is interactive and does not support --json")
            emit_options_error("repl", exc, None, opts)
            raise typer.Exit(EXIT_VALIDATION_ERROR)

        explicit_config = opts.config_path is not None
        target_path = (
            opts.config_path if opts.config_path is not None else runtime.default_config_path
        )
        launch_cli(
            target_path,
            address=opts.address,
            network=opts.network,
            must_exist=explicit_config,
        )

    @app.command("create-config")
    def create_config_command(
        ctx: typer.Context,
        force: Annotated[
            bool,
            typer.Option("--force", help="Overwrite an existing configuration file"),
        ] = False,
        config_path: Annotated[Path | None, CONFIG_OPTION] = None,
        address: Annotated[str | None, ADDRESS_OPTION] = None,
        network: Annotated[NetworkType | None, NETWORK_OPTION] = None,
        json_output: Annotated[bool, JSON_OPTION] = False,
    ) -> None:
        """Create a default configuration file from config.example.yaml."""
        opts = resolve_options(
            ctx,
            config_path=config_path,
            address=address,
            network=network,
            json_output=json_output,
        )
        target_path = (
            opts.config_path if opts.config_path is not None else runtime.default_config_path
        )

        try:
            existed = target_path.exists()
            if existed and not force:
                if opts.json_output or not sys.stdin.isatty():
                    raise FileExistsError(
                        f"Configuration file already exists: {target_path}. "
                        "Pass --force to overwrite."
                    )
                if not typer.confirm("⚠️  Configuration file already exists. Overwrite?"):
                    typer.echo("❌ Configuration file creation cancelled.")
                    return

            target_path.parent.mkdir(parents=True, exist_ok=True)
            example_path = _example_config_path()
            if example_path.exists():
                shutil.copyfile(example_path, target_path)
            else:
                target_path.write_text(FALLBACK_CONFIG_TEMPLATE, encoding="utf-8")

            payload = {
                "path": str(target_path),
                "created": True,
                "overwritten": existed,
            }
            if opts.json_output:
                emit_options_success("create-config", payload, None, opts)
            else:
                typer.echo(f"✅ Default configuration file created at {target_path}")
        except typer.Exit:
            raise
        except Exception as exc:
            if opts.json_output:
                emit_options_error("create-config", exc, None, opts)
            else:
                typer.echo(f"❌ Failed to create configuration file: {exc}", err=True)
            raise typer.Exit(EXIT_RUNTIME_ERROR) from exc

    @app.command("status")
    def status_command(
        ctx: typer.Context,
        config_path: Annotated[Path | None, CONFIG_OPTION] = None,
        address: Annotated[str | None, ADDRESS_OPTION] = None,
        network: Annotated[NetworkType | None, NETWORK_OPTION] = None,
        json_output: Annotated[bool, JSON_OPTION] = False,
    ) -> None:
        """Check connectivity to Hyperliquid /info and show configuration status."""
        opts = resolve_options(
            ctx,
            config_path=config_path,
            address=address,
            network=network,
            json_output=json_output,
        )

        def _execute(config: Config, client: HyperliquidClient) -> dict[str, Any]:
            connected = client.test_connection()
            return {
                "network": config.hyperliquid.network.value,
                "account_address": config.hyperliquid.account_address,
                "has_private_key": bool(config.hyperliquid.private_key),
                "connected": connected,
                "version": CLI_VERSION,
            }

        run_command(
            "status",
            opts,
            require_address=False,
            execute=_execute,
            render_human=_render_status,
        )
