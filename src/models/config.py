"""
Configuration models for the Hyperliquid CLI.

This module provides centralized configuration data models and base types
with their respective validation logic.
"""

from decimal import Decimal
from enum import Enum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .order import OrderTif

PRIVATE_KEY_LENGTH = 66
STRICT_MODEL_CONFIG = ConfigDict(extra="forbid", validate_assignment=True)


class ConfigurationError(Exception):
    """Exception raised for configuration-related errors."""

    pass


class NetworkType(str, Enum):
    """Constants for network types."""

    MAINNET = "mainnet"
    TESTNET = "testnet"


class HyperliquidConfig(BaseModel):
    """Configuration for Hyperliquid API connection."""

    model_config = STRICT_MODEL_CONFIG

    account_address: str
    private_key: str
    network: NetworkType = NetworkType.MAINNET

    @field_validator("account_address")
    @classmethod
    def validate_account_address(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("account_address is required and must be a string")
        if not v.startswith("0x"):
            raise ValueError("account_address must be a valid Ethereum address")
        return v

    @field_validator("private_key")
    @classmethod
    def validate_private_key(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("private_key is required and must be a string")
        if not (v.startswith("0x") and len(v) == PRIVATE_KEY_LENGTH):
            raise ValueError("private_key must be a valid 32-byte hex string")
        return v


class TradingConfig(BaseModel):
    """Configuration for trading parameters."""

    model_config = STRICT_MODEL_CONFIG

    default_slippage: Decimal = Field(default_factory=lambda: Decimal("0.01"), gt=0, lt=1)
    default_time_in_force: OrderTif = OrderTif.GTC


class LoggingConfig(BaseModel):
    """Configuration for logging."""

    model_config = STRICT_MODEL_CONFIG

    level: str = Field(default="INFO")

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v not in valid_levels:
            raise ValueError(f"logging.level must be one of {valid_levels}")
        return v


class BackendConfig(BaseModel):
    """Configuration for backend WebSocket monitoring service."""

    model_config = STRICT_MODEL_CONFIG

    host: str = Field(default="localhost")
    port: int = Field(default=8080, ge=1, le=65535)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


class AgentConfig(BaseModel):
    """Configuration for the frontend AI assistant."""

    model_config = STRICT_MODEL_CONFIG

    api_key: str = Field(default="your_openai_api_key_here")
    openai_base_url: str = Field(default="your_openai_compatible_base_url_here")
    model_id: str = Field(default="your_model_id_here")

    @field_validator("api_key", "openai_base_url", "model_id")
    @classmethod
    def validate_non_empty_string(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("agent settings must be non-empty strings")
        return v


class Config(BaseModel):
    """Main configuration class encompassing all sub-configurations."""

    model_config = STRICT_MODEL_CONFIG

    hyperliquid: HyperliquidConfig
    trading: TradingConfig = Field(default_factory=TradingConfig)
    backend: BackendConfig = Field(default_factory=BackendConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)

    @classmethod
    def from_file(cls, config_path: Path) -> "Config":
        """
        Load configuration from a YAML file.

        Args:
            config_path: Path to the configuration file

        Returns:
            Config instance

        Raises:
            ConfigurationError: If file cannot be loaded or validation fails
        """
        if not config_path.exists():
            raise ConfigurationError(f"Configuration file not found: {config_path}")

        try:
            with open(config_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in configuration file: {e}") from e
        except Exception as e:
            raise ConfigurationError(f"Error reading configuration file: {e}") from e

        if data is None:
            raise ConfigurationError("Configuration file is empty")

        return cls(**data)
