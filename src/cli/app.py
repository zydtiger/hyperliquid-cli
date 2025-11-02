"""
Hyperliquid CLI

A command-line interface for the modular order system with support for
market orders, limit orders, stop orders, and intelligent TP/SL management.
"""

import shutil
import typer
from pathlib import Path

from .interactive import InteractiveCLI


app = typer.Typer(
    name="hyperliquid-cli",
    help="Hyperliquid CLI - Simple order management system",
)


@app.command()
def run(
    config: Path = typer.Option(
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
    # Run the CLI
    try:
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
