"""
Hyperliquid CLI Models.

This package provides centralized data models and types for the Hyperliquid CLI.
"""

from .config import (
    ConfigurationError,
    NetworkType,
    HyperliquidConfig,
    TradingConfig,
    LoggingConfig,
    BackendConfig,
    Config,
)

from .api import (
    APIError,
    ExchangeError,
    HealthStatus,
    LeverageType,
    HealthResponse,
    RootResponse,
    Ticker,
    CoinMetadata,
    PositionInfo,
    SpotBalance,
    StakingInfo,
    BalanceInfo,
)

from .order import (
    OrderSide,
    OrderTif,
    OrderStatus,
    OrderType,
    MarketOrder,
    LimitOrder,
    OrderResult,
    OrderInfo,
    CancelOrderRequest,
    ModifyOrderRequest,
)

__all__ = [
    # Config models
    "ConfigurationError",
    "NetworkType",
    "HyperliquidConfig",
    "TradingConfig",
    "LoggingConfig",
    "BackendConfig",
    "Config",
    # API models
    "APIError",
    "ExchangeError",
    "HealthStatus",
    "LeverageType",
    "HealthResponse",
    "RootResponse",
    "Ticker",
    "CoinMetadata",
    "PositionInfo",
    "SpotBalance",
    "StakingInfo",
    "BalanceInfo",
    # Order models
    "OrderSide",
    "OrderTif",
    "OrderStatus",
    "OrderType",
    "MarketOrder",
    "LimitOrder",
    "OrderResult",
    "OrderInfo",
    "CancelOrderRequest",
    "ModifyOrderRequest",
]
