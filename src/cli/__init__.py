"""
CLI module for the Hyperliquid trading system.

This module provides the stateless and interactive command-line interface
components for the Hyperliquid CLI, connecting directly to Hyperliquid via
the in-process ``exchange.HyperliquidClient``.

Components:
- app: Main CLI application entry point and root callback
- runtime: Global option resolution, error handling, and JSON envelope contract
- commands: Stateless subcommands for account, market, portfolio, and trading ops
- interactive_cli: Interactive REPL command prompt interface
- formatters: Output formatting utilities for orders, accounts, and tables
- interactive: Interactive wizards, prompts, and fullscreen TUIs
"""

from .app import main

__all__ = ["main"]
