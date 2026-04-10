"""
Hyperliquid CLI

A command-line interface for the modular order system with support for
market orders, limit orders, stop orders, and intelligent TP/SL management.
"""

import shutil
from pathlib import Path
from typing import Annotated

import typer

from models.api import HealthStatus
from models.config import Config, ConfigurationError

from .api import BackendAPI
from .interactive_cli import InteractiveCLI

app = typer.Typer(
    name="hyperliquid-cli",
    help="Hyperliquid CLI - Simple order management system",
)

default_config_path = Path.home() / ".hyperliquid-cli" / "config.yaml"
config_option = typer.Option(
    "--config",
    "-c",
    help="Path to configuration file",
    file_okay=True,
    dir_okay=False,
)


@app.callback(invoke_without_command=True)
def default_run(
    ctx: typer.Context,
    config_path: Annotated[Path, config_option] = default_config_path,
) -> None:
    """Run the interactive CLI when no subcommand is provided."""
    if ctx.invoked_subcommand is None and not ctx.resilient_parsing:
        launch_cli(config_path)


def launch_cli(config_path: Path) -> None:
    try:
        config = Config.from_file(config_path)
    except ConfigurationError as e:
        typer.echo(f"❌ Failed to load configuration: {e}", err=True)
        raise typer.Exit(1) from e

    # Test connections before starting CLI
    typer.echo("🔌 Checking connections...")

    # Test 1: Check backend API connection
    try:
        with BackendAPI(config) as api:
            root_data = api.get_root()
        typer.echo("✅ Successfully connected to backend API")
    except Exception as e:
        typer.echo("❌ Failed to connect to backend API")
        raise typer.Exit(1) from e

    # Test 2: Check if backend is connected to Hyperliquid
    if root_data.status == HealthStatus.HEALTHY:
        typer.echo("✅ Backend API is connected to Hyperliquid exchange")
    else:
        typer.echo(f"❌ Backend API status: {root_data.status}")
        raise typer.Exit(1)

    # Run the CLI
    try:
        print()
        cli = InteractiveCLI(config)
        cli.run()
    except Exception as e:
        typer.echo(f"❌ Fatal error: {e}", err=True)
        raise typer.Exit(1) from e


@app.command()
def create_config() -> None:
    """Create a default configuration file."""
    try:
        example_config = Path(__file__).parent.parent.parent / "config.example.yaml"
        default_config_path.parent.mkdir(parents=True, exist_ok=True)

        if default_config_path.exists():
            if not typer.confirm("⚠️  Configuration file already exists. Overwrite?"):
                typer.echo("❌ Configuration file creation cancelled.")
                return

        shutil.copyfile(example_config, default_config_path)
        typer.echo("✅ Default configuration file created successfully!")
    except Exception as e:
        typer.echo(f"❌ Failed to create configuration file: {e}", err=True)
        raise typer.Exit(1) from e


def main() -> None:
    app()
