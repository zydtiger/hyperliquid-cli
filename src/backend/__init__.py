"""
Backend module for the Hyperliquid CLI.

This module provides the backend service components for the Hyperliquid CLI,
including FastAPI server, request handlers, and exchange client integration.

Components:
- service: FastAPI backend service setup and configuration
- request_handlers: HTTP endpoint handlers for trading operations
- exchange: Hyperliquid exchange client and connection management

The backend exposes a REST API that wraps Hyperliquid exchange functionality
through HTTP endpoints with proper error handling and type safety.
"""

from .service import main

__all__ = ["main"]