"""
Backend models for the Hyperliquid CLI.

This module provides error handling and type definitions for backend operations
including exchange connectivity and data management.
"""

from .types import ExchangeError, LeverageType, Ticker, CoinMetadata, PositionInfo

__all__ = [
    "ExchangeError",
    "LeverageType",
    "Ticker",
    "CoinMetadata",
    "PositionInfo",
]
