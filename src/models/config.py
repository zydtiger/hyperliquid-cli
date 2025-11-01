"""
Configuration models for the Hyperliquid CLI.

This module provides centralized configuration data models and base types
with their respective validation logic.
"""

from decimal import Decimal
from enum import Enum
from pathlib import Path
from jsoncomment import JsonComment
from pydantic import BaseModel, Field, field_validator

from .order import OrderTif


class ConfigurationError(Exception):
    """Exception raised for configuration-related errors."""

    pass


class NetworkType(Enum):
    """Constants for network types."""

    MAINNET = "mainnet"
    TESTNET = "testnet"


class HyperliquidConfig(BaseModel, extra="forbid", validate_assignment=True):
    """Configuration for Hyperliquid API connection."""

    account_address: str
    private_key: str
    network: NetworkType = NetworkType.MAINNET

    @field_validator("account_address")
    def validate_account_address(cls, v):
        if not v or not isinstance(v, str):
            raise ValueError("account_address is required and must be a string")
        if not v.startswith("0x"):
            raise ValueError("account_address must be a valid Ethereum address")
        return v

    @field_validator("private_key")
    def validate_private_key(cls, v):
        if not v or not isinstance(v, str):
            raise ValueError("private_key is required and must be a string")
        if not (v.startswith("0x") and len(v) == 66):
            raise ValueError("private_key must be a valid 32-byte hex string")
        return v


class TradingConfig(BaseModel, extra="forbid", validate_assignment=True):
    """Configuration for trading parameters."""

    default_slippage: Decimal = Field(
        default_factory=lambda: Decimal("0.01"), gt=0, lt=1
    )
    default_time_in_force: OrderTif = OrderTif.GTC


class LoggingConfig(BaseModel, extra="forbid", validate_assignment=True):
    """Configuration for logging."""

    level: str = Field(default="INFO")

    @field_validator("level")
    def validate_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v not in valid_levels:
            raise ValueError(f"logging.level must be one of {valid_levels}")
        return v


class BackendConfig(BaseModel, extra="forbid", validate_assignment=True):
    """Configuration for backend WebSocket monitoring service."""

    host: str = Field(default="localhost")
    port: int = Field(default=8080, ge=1, le=65535)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


class Config(BaseModel, extra="forbid", validate_assignment=True):
    """Main configuration class encompassing all sub-configurations."""

    hyperliquid: HyperliquidConfig
    trading: TradingConfig = Field(default_factory=TradingConfig)
    backend: BackendConfig = Field(default_factory=BackendConfig)

    @classmethod
    def from_file(cls, config_path: Path) -> "Config":
        """
        Load configuration from a JSONC file.

        Args:
            config_path: Path to the configuration file

        Returns:
            Config instance

        Raises:
            ConfigurationError: If file cannot be loaded or validation fails
        """
        if not config_path.exists():
            raise ConfigurationError(f"Configuration file not found: {config_path}")

        with open(config_path, "r") as f:
            parser = JsonComment()
            data = parser.load(f)

        return cls(**data)


__all__ = [
    "ConfigurationError",
    "NetworkType",
    "Config",
    "HyperliquidConfig",
    "TradingConfig",
    "LoggingConfig",
    "BackendConfig",
]
