"""
Configuration models for the Hyperliquid CLI.

This module provides centralized configuration data models and base types
with their respective validation logic.
"""

from decimal import Decimal
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .order import OrderTif

PRIVATE_KEY_LENGTH = 66
HEX_CHARS = frozenset("0123456789abcdefABCDEF")
STRICT_MODEL_CONFIG = ConfigDict(extra="forbid", validate_assignment=True)


class ConfigurationError(Exception):
    """Exception raised for configuration-related errors."""


class NetworkType(StrEnum):
    """Constants for network types."""

    MAINNET = "mainnet"
    TESTNET = "testnet"


class HyperliquidConfig(BaseModel):
    """Configuration for Hyperliquid API connection."""

    model_config = STRICT_MODEL_CONFIG

    account_address: str | None = None
    private_key: str | None = None
    network: NetworkType = NetworkType.MAINNET

    @field_validator("account_address")
    @classmethod
    def validate_account_address(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not isinstance(v, str) or not v:
            raise ValueError("account_address must be a non-empty string")
        if not v.startswith("0x"):
            raise ValueError("account_address must be a valid Ethereum address")
        return v

    @field_validator("private_key")
    @classmethod
    def validate_private_key(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not isinstance(v, str) or not v:
            raise ValueError("private_key must be a non-empty string")
        if not (
            v.startswith("0x")
            and len(v) == PRIVATE_KEY_LENGTH
            and all(ch in HEX_CHARS for ch in v[2:])
        ):
            raise ValueError("private_key must be a valid 32-byte hex string")
        return v


class TradingConfig(BaseModel):
    """Configuration for trading parameters."""

    model_config = STRICT_MODEL_CONFIG

    default_slippage: Decimal = Field(default_factory=lambda: Decimal("0.01"), gt=0, lt=1)
    default_time_in_force: OrderTif = OrderTif.GTC


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

    hyperliquid: HyperliquidConfig = Field(default_factory=HyperliquidConfig)
    trading: TradingConfig = Field(default_factory=TradingConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)

    @classmethod
    def from_file(cls, config_path: Path) -> "Config":
        """
        Load configuration from a YAML file.

        Legacy ``backend`` sections are stripped before strict validation so
        existing user configs continue loading seamlessly.

        Args:
            config_path: Path to the configuration file

        Returns:
            Config instance

        Raises:
            ConfigurationError: If file cannot be loaded or is empty/malformed
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
        if not isinstance(data, dict):
            raise ConfigurationError("Configuration file must contain a YAML mapping")

        data.pop("backend", None)
        return cls(**data)

    @classmethod
    def load_for_cli(
        cls,
        config_path: Path | None = None,
        *,
        address: str | None = None,
        network: NetworkType | None = None,
        require_address: bool = False,
        must_exist: bool = False,
    ) -> "Config":
        """
        Load configuration for stateless CLI commands with optional overrides.

        Loads ``config_path`` when provided and present, applies explicit
        ``address`` and ``network`` overrides, and works without a config file
        when ``require_address`` is False or ``address`` is explicitly supplied.

        Args:
            config_path: Optional path to a YAML configuration file
            address: Optional Ethereum account address override (``--address``)
            network: Optional network override (``--network``)
            require_address: Whether a non-empty ``account_address`` is required
            must_exist: Whether a missing ``config_path`` must fail immediately

        Returns:
            Config instance

        Raises:
            ConfigurationError: If a required config file or account address is missing
        """
        if config_path is not None and config_path.exists():
            config = cls.from_file(config_path)
        elif config_path is not None and must_exist:
            raise ConfigurationError(f"Configuration file not found: {config_path}")
        else:
            config = cls()

        if address is not None:
            config.hyperliquid.account_address = address
        if network is not None:
            config.hyperliquid.network = network

        if require_address and not config.hyperliquid.account_address:
            if config_path is not None and not config_path.exists():
                raise ConfigurationError(
                    f"Configuration file not found: {config_path}. "
                    "Provide --address or create a configuration file."
                )
            raise ConfigurationError(
                "Account address is required; configure hyperliquid.account_address "
                "or pass --address."
            )

        return config
