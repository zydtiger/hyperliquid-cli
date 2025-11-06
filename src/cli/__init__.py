"""
CLI module for the Hyperliquid trading system.

This module provides the command-line interface components for the Hyperliquid CLI,
including interactive commands, formatters, and API client integration.

Components:
- app: Main CLI application entry point and command definitions
- interactive_cli: Interactive command prompt interface
- formatters: Output formatting utilities for orders, accounts, and tables
- interactive: Interactive wizards and prompts for order creation and modification
- api: Backend API client for communicating with the Hyperliquid service

The CLI provides both interactive and programmatic interfaces for managing
trading operations, viewing positions, and monitoring account status.
"""

from .app import main

__all__ = ["main"]