"""
Hyperliquid CLI

A command-line interface for the modular order system with support for
market orders, limit orders, stop orders, and intelligent TP/SL management.
"""

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


@app.command()
def run(
    config_path: Path = typer.Option(
        "config.yaml",
        "--config",
        "-c",
        help="Path to configuration file (default: config.yaml)",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
):
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
    except KeyboardInterrupt:
        typer.echo("\n👋 Goodbye!")
    except Exception as e:
        typer.echo(f"❌ Fatal error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def create_config():
    """Create a default configuration file."""
    try:
        shutil.copyfile("config.example.yaml", "config.yaml")
        typer.echo("✅ Default configuration file created successfully!")
    except Exception as e:
        typer.echo(f"❌ Failed to create configuration file: {e}", err=True)
        raise typer.Exit(1)


def main():
    app()
