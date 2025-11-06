"""
Hyperliquid CLI

A command-line interface for the modular order system with support for
market orders, limit orders, stop orders, and intelligent TP/SL management.
"""

import os
import shutil
import typer
from pathlib import Path

from .interactive_cli import InteractiveCLI
from .api import BackendAPI
from models.config import Config
from models.api import HealthStatus


app = typer.Typer(
    name="hyperliquid-cli",
    help="Hyperliquid CLI - Simple order management system",
)

default_config_path = Path.home() / ".hyperliquid-cli" / "config.yaml"


@app.command()
def run(
    config_path: Path = typer.Option(
        default_config_path,
        "--config",
        "-c",
        help=f"Path to configuration file (default: {default_config_path})",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
) -> None:
    # Load configuration
    config = Config.from_file(config_path)

    # Test connections before starting CLI
    typer.echo("🔌 Checking connections...")

    # Test 1: Check backend API connection
    try:
        with BackendAPI(config) as api:
            root_data = api.get_root()
        typer.echo("✅ Successfully connected to backend API")
    except Exception as e:
        typer.echo("❌ Failed to connect to backend API")
        raise typer.Exit(1)

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
        raise typer.Exit(1)


@app.command()
def create_config() -> None:
    """Create a default configuration file."""
    try:
        example_config = Path(__file__).parent.parent.parent / "config.example.yaml"

        os.makedirs(default_config_path.parent, exist_ok=True)

        if os.path.exists(default_config_path):
            if not typer.confirm("⚠️  Configuration file already exists. Overwrite?"):
                typer.echo("❌ Configuration file creation cancelled.")
                return

        shutil.copyfile(example_config, default_config_path)
        typer.echo("✅ Default configuration file created successfully!")
    except Exception as e:
        typer.echo(f"❌ Failed to create configuration file: {e}", err=True)
        raise typer.Exit(1)


def main() -> None:
    app()
