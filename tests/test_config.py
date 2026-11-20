"""
Comprehensive unit tests for configuration models.

Tests all configuration classes, validators, constraints, legacy backend stripping,
and CLI config loading with overrides.
"""

from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from models.config import (
    AgentConfig,
    Config,
    ConfigurationError,
    HyperliquidConfig,
    NetworkType,
    TradingConfig,
)
from models.order import OrderTif

VALID_ADDRESS = "0x1234567890123456789012345678901234567890"
ALT_ADDRESS = "0xabcdef123456789012345678901234567890abcdef"
VALID_PRIVATE_KEY = "0x1234567890123456789012345678901234567890123456789012345678901234"


class TestNetworkType:
    """Test NetworkType enum."""

    def test_network_type_values(self) -> None:
        """Test NetworkType enum has correct values."""
        assert NetworkType.MAINNET.value == "mainnet"
        assert NetworkType.TESTNET.value == "testnet"
        assert len(NetworkType) == 2

    def test_network_type_inheritance(self) -> None:
        """Test NetworkType inherits from str enum."""
        assert issubclass(NetworkType, str)
        assert NetworkType.MAINNET.value == "mainnet"


class TestHyperliquidConfig:
    """Test HyperliquidConfig model."""

    def test_valid_config_creation(self) -> None:
        """Test creating valid HyperliquidConfig."""
        config = HyperliquidConfig.model_validate(
            {
                "account_address": VALID_ADDRESS,
                "private_key": VALID_PRIVATE_KEY,
                "network": "mainnet",
            }
        )
        assert config.account_address == VALID_ADDRESS
        assert config.private_key == VALID_PRIVATE_KEY
        assert config.network == NetworkType.MAINNET

    def test_optional_credentials_defaults(self) -> None:
        """Test account_address and private_key default to None."""
        config = HyperliquidConfig()
        assert config.account_address is None
        assert config.private_key is None
        assert config.network == NetworkType.MAINNET

    def test_address_only_without_private_key(self) -> None:
        """Test read-only config with account_address and no private_key."""
        config = HyperliquidConfig(account_address=VALID_ADDRESS, network=NetworkType.TESTNET)
        assert config.account_address == VALID_ADDRESS
        assert config.private_key is None
        assert config.network == NetworkType.TESTNET

    def test_invalid_account_address(self) -> None:
        """Test validation fails for invalid non-None account address."""
        with pytest.raises(ValueError, match="account_address must be a non-empty string"):
            HyperliquidConfig(account_address="", private_key=VALID_PRIVATE_KEY)

        with pytest.raises(ValueError, match="must be a valid Ethereum address"):
            HyperliquidConfig(
                account_address="1234567890123456789012345678901234567890",
                private_key=VALID_PRIVATE_KEY,
            )

    def test_invalid_private_key(self) -> None:
        """Test validation fails for invalid non-None private key."""
        with pytest.raises(ValueError, match="private_key must be a non-empty string"):
            HyperliquidConfig(account_address=VALID_ADDRESS, private_key="")

        with pytest.raises(ValueError, match="must be a valid 32-byte hex string"):
            HyperliquidConfig(
                account_address=VALID_ADDRESS,
                private_key="0x123456789012345678901234567890123456789012345678901234567890",
            )

        with pytest.raises(ValueError, match="must be a valid 32-byte hex string"):
            HyperliquidConfig(
                account_address=VALID_ADDRESS,
                private_key="1234567890123456789012345678901234567890123456789012345678901234",
            )

        with pytest.raises(ValueError, match="must be a valid 32-byte hex string"):
            HyperliquidConfig(
                account_address=VALID_ADDRESS,
                private_key="0x" + ("z" * 64),
            )

    def test_extra_fields_forbidden(self) -> None:
        """Test extra fields are rejected."""
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            HyperliquidConfig.model_validate(
                {
                    "account_address": VALID_ADDRESS,
                    "private_key": VALID_PRIVATE_KEY,
                    "unknown_field": "value",
                }
            )

    def test_validate_assignment(self) -> None:
        """Test assignment validation works."""
        config = HyperliquidConfig(account_address=VALID_ADDRESS, private_key=VALID_PRIVATE_KEY)
        config.account_address = ALT_ADDRESS
        assert config.account_address == ALT_ADDRESS

        with pytest.raises(ValueError, match="must be a valid Ethereum address"):
            config.account_address = "invalid_address"


class TestTradingConfig:
    """Test TradingConfig model."""

    def test_valid_config_creation(self) -> None:
        """Test creating valid TradingConfig."""
        config = TradingConfig.model_validate(
            {"default_slippage": Decimal("0.05"), "default_time_in_force": "GTC"}
        )
        assert config.default_slippage == Decimal("0.05")
        assert config.default_time_in_force == OrderTif.GTC

    def test_default_values(self) -> None:
        """Test default values are applied correctly."""
        config = TradingConfig()
        assert config.default_slippage == Decimal("0.01")
        assert config.default_time_in_force == OrderTif.GTC

    def test_slippage_constraints(self) -> None:
        """Test slippage field constraints."""
        for value in [Decimal("0.001"), Decimal("0.1"), Decimal("0.5"), Decimal("0.99")]:
            assert TradingConfig(default_slippage=value).default_slippage == value

        for value in [Decimal("0"), Decimal("-0.1"), Decimal("-1")]:
            with pytest.raises(ValidationError, match="Input should be greater than 0"):
                TradingConfig(default_slippage=value)

        for value in [Decimal("1"), Decimal("1.1"), Decimal("2")]:
            with pytest.raises(ValidationError, match="Input should be less than 1"):
                TradingConfig(default_slippage=value)

    def test_time_in_force_enum_conversion(self) -> None:
        """Test string to enum conversion for time_in_force."""
        for value in ["ALO", "IOC", "GTC"]:
            config = TradingConfig.model_validate({"default_time_in_force": value})
            assert isinstance(config.default_time_in_force, OrderTif)

        for value in ["Alo", "Ioc", "Gtc", "alo", "ioc", "gtc", "INVALID"]:
            with pytest.raises(ValidationError):
                TradingConfig.model_validate({"default_time_in_force": value})

    def test_extra_fields_forbidden(self) -> None:
        """Test extra fields are rejected."""
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            TradingConfig.model_validate({"unknown_field": "value"})

    def test_validate_assignment(self) -> None:
        """Test assignment validation works."""
        config = TradingConfig()
        config.default_slippage = Decimal("0.05")
        assert config.default_slippage == Decimal("0.05")

        with pytest.raises(ValidationError, match="Input should be less than 1"):
            config.default_slippage = Decimal("2.0")

        attr_name = "default_time_in_force"
        setattr(config, attr_name, "IOC")
        assert config.default_time_in_force == OrderTif.IOC

        with pytest.raises(ValidationError):
            setattr(config, attr_name, "INVALID")


class TestAgentConfig:
    """Test AgentConfig model."""

    def test_valid_config_creation(self) -> None:
        """Test creating valid AgentConfig."""
        config = AgentConfig(
            api_key="test-key",
            openai_base_url="https://example.com/v1",
            model_id="gpt-test",
        )
        assert config.api_key == "test-key"
        assert config.openai_base_url == "https://example.com/v1"
        assert config.model_id == "gpt-test"

    def test_default_values(self) -> None:
        """Test default agent values are applied."""
        config = AgentConfig()
        assert config.api_key == "your_openai_api_key_here"
        assert config.openai_base_url == "your_openai_compatible_base_url_here"
        assert config.model_id == "your_model_id_here"

    @pytest.mark.parametrize("field_name", ["api_key", "openai_base_url", "model_id"])
    def test_empty_values_are_rejected(self, field_name: str) -> None:
        """Test agent settings must be non-empty strings."""
        with pytest.raises(ValueError, match="agent settings must be non-empty strings"):
            AgentConfig.model_validate(
                {
                    "api_key": "test-key",
                    "openai_base_url": "https://example.com/v1",
                    "model_id": "gpt-test",
                    field_name: "   ",
                }
            )

    def test_extra_fields_forbidden(self) -> None:
        """Test extra fields are rejected."""
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            AgentConfig.model_validate({"unknown_field": "value"})


class TestConfig:
    """Test main Config class."""

    def test_valid_config_creation(self) -> None:
        """Test creating valid Config without backend section."""
        config_data = {
            "hyperliquid": {
                "account_address": VALID_ADDRESS,
                "private_key": VALID_PRIVATE_KEY,
                "network": "mainnet",
            },
            "trading": {
                "default_slippage": "0.02",
                "default_time_in_force": "IOC",
            },
            "agent": {
                "api_key": "test-key",
                "openai_base_url": "https://example.com/v1",
                "model_id": "gpt-test",
            },
        }
        config = Config.model_validate(config_data)

        assert config.hyperliquid.account_address == VALID_ADDRESS
        assert config.hyperliquid.network == NetworkType.MAINNET
        assert config.trading.default_slippage == Decimal("0.02")
        assert config.trading.default_time_in_force == OrderTif.IOC
        assert config.agent.api_key == "test-key"
        assert config.agent.openai_base_url == "https://example.com/v1"
        assert config.agent.model_id == "gpt-test"

    def test_default_config_creation(self) -> None:
        """Test creating empty default Config works for stateless market commands."""
        config = Config()
        assert config.hyperliquid.account_address is None
        assert config.hyperliquid.private_key is None
        assert config.hyperliquid.network == NetworkType.MAINNET
        assert config.trading.default_slippage == Decimal("0.01")
        assert config.trading.default_time_in_force == OrderTif.GTC

    def test_extra_fields_forbidden(self) -> None:
        """Test extra fields are rejected at top level."""
        config_data = {
            "hyperliquid": {"account_address": VALID_ADDRESS},
            "unknown_section": "value",
        }
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            Config.model_validate(config_data)

    def test_backend_forbidden_on_direct_model_validate(self) -> None:
        """Test direct model_validate keeps strict extra='forbid'."""
        config_data = {
            "hyperliquid": {"account_address": VALID_ADDRESS},
            "backend": {"host": "localhost", "port": 8080},
        }
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            Config.model_validate(config_data)

    def test_from_file_strips_legacy_backend_section(self, tmp_path: Path) -> None:
        """Test from_file ignores legacy backend section in existing user configs."""
        config_path = tmp_path / "config.yaml"
        config_data = {
            "hyperliquid": {
                "account_address": VALID_ADDRESS,
                "private_key": VALID_PRIVATE_KEY,
                "network": "testnet",
            },
            "trading": {"default_slippage": "0.05"},
            "backend": {
                "host": "127.0.0.1",
                "port": 9000,
                "logging": {"level": "DEBUG"},
            },
        }
        config_path.write_text(yaml.safe_dump(config_data), encoding="utf-8")

        config = Config.from_file(config_path)

        assert config.hyperliquid.account_address == VALID_ADDRESS
        assert config.hyperliquid.network == NetworkType.TESTNET
        assert config.trading.default_slippage == Decimal("0.05")
        assert not hasattr(config, "backend")

    def test_from_file_still_rejects_unknown_keys(self, tmp_path: Path) -> None:
        """Test from_file keeps extra='forbid' for all non-backend unknown keys."""
        config_path = tmp_path / "config.yaml"
        config_data = {
            "hyperliquid": {"account_address": VALID_ADDRESS},
            "backend": {"host": "localhost", "port": 8080},
            "unexpected_key": True,
        }
        config_path.write_text(yaml.safe_dump(config_data), encoding="utf-8")

        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            Config.from_file(config_path)

    def test_from_file_not_found(self, tmp_path: Path) -> None:
        """Test from_file raises error for non-existent file."""
        non_existent_path = tmp_path / "does_not_exist_config.yaml"
        with pytest.raises(ConfigurationError, match="Configuration file not found"):
            Config.from_file(non_existent_path)

    def test_from_file_invalid_yaml(self, tmp_path: Path) -> None:
        """Test from_file raises error for invalid YAML."""
        config_path = tmp_path / "invalid.yaml"
        config_path.write_text("invalid: yaml: content: [", encoding="utf-8")

        with pytest.raises(ConfigurationError, match="Invalid YAML in configuration file"):
            Config.from_file(config_path)

    def test_from_file_empty_file(self, tmp_path: Path) -> None:
        """Test from_file raises error for empty file."""
        config_path = tmp_path / "empty.yaml"
        config_path.write_text("", encoding="utf-8")

        with pytest.raises(ConfigurationError, match="Configuration file is empty"):
            Config.from_file(config_path)

    def test_from_file_non_mapping(self, tmp_path: Path) -> None:
        """Test from_file raises error when YAML root is not a mapping."""
        config_path = tmp_path / "list.yaml"
        config_path.write_text("- item1\n- item2\n", encoding="utf-8")

        with pytest.raises(ConfigurationError, match="must contain a YAML mapping"):
            Config.from_file(config_path)

    def test_from_file_invalid_config(self, tmp_path: Path) -> None:
        """Test from_file raises error for invalid configuration values."""
        config_path = tmp_path / "bad_address.yaml"
        config_data = {
            "hyperliquid": {
                "account_address": "invalid_address",
                "private_key": VALID_PRIVATE_KEY,
            }
        }
        config_path.write_text(yaml.safe_dump(config_data), encoding="utf-8")

        with pytest.raises(ValidationError, match="must be a valid Ethereum address"):
            Config.from_file(config_path)

    def test_config_serialization(self) -> None:
        """Test config model_dump and JSON serialization."""
        config = Config.model_validate(
            {
                "hyperliquid": {
                    "account_address": VALID_ADDRESS,
                    "private_key": VALID_PRIVATE_KEY,
                }
            }
        )
        data = config.model_dump()
        assert set(data.keys()) == {"hyperliquid", "trading", "agent"}
        assert data["hyperliquid"]["network"] == "mainnet"
        assert "hyperliquid" in config.model_dump_json()


class TestConfigLoadForCli:
    """Test Config.load_for_cli helper."""

    def test_without_file_and_not_requiring_address(self, tmp_path: Path) -> None:
        """Market-data commands work with no config file."""
        missing_path = tmp_path / "missing.yaml"
        config = Config.load_for_cli(missing_path, require_address=False)

        assert config.hyperliquid.account_address is None
        assert config.hyperliquid.private_key is None
        assert config.hyperliquid.network == NetworkType.MAINNET

    def test_without_file_with_explicit_address_and_network(self, tmp_path: Path) -> None:
        """Account read commands work with --address and no config file."""
        missing_path = tmp_path / "missing.yaml"
        config = Config.load_for_cli(
            missing_path,
            address=VALID_ADDRESS,
            network=NetworkType.TESTNET,
            require_address=True,
        )

        assert config.hyperliquid.account_address == VALID_ADDRESS
        assert config.hyperliquid.private_key is None
        assert config.hyperliquid.network == NetworkType.TESTNET

    def test_none_config_path_with_overrides(self) -> None:
        """Passing config_path=None builds an in-memory config with overrides."""
        config = Config.load_for_cli(
            None,
            address=ALT_ADDRESS,
            network=NetworkType.TESTNET,
            require_address=True,
        )
        assert config.hyperliquid.account_address == ALT_ADDRESS
        assert config.hyperliquid.network == NetworkType.TESTNET

    def test_missing_file_raises_when_address_required_and_not_given(self, tmp_path: Path) -> None:
        """Missing config file fails when require_address=True and address is None."""
        missing_path = tmp_path / "missing.yaml"
        with pytest.raises(ConfigurationError, match="Configuration file not found"):
            Config.load_for_cli(missing_path, require_address=True)

    def test_none_path_raises_when_address_required_and_not_given(self) -> None:
        """None config path fails when require_address=True and address is None."""
        with pytest.raises(ConfigurationError, match="Account address is required"):
            Config.load_for_cli(None, require_address=True)

    def test_must_exist_fails_even_when_address_not_required(self, tmp_path: Path) -> None:
        """Explicitly requested missing config path fails when must_exist=True."""
        missing_path = tmp_path / "missing.yaml"
        with pytest.raises(ConfigurationError, match="Configuration file not found"):
            Config.load_for_cli(missing_path, require_address=False, must_exist=True)

    def test_loads_file_and_applies_overrides(self, tmp_path: Path) -> None:
        """CLI flags override values loaded from config file."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            yaml.safe_dump(
                {
                    "hyperliquid": {
                        "account_address": VALID_ADDRESS,
                        "network": "mainnet",
                    },
                    "trading": {"default_slippage": "0.025"},
                    "backend": {"host": "localhost", "port": 8080},
                }
            ),
            encoding="utf-8",
        )

        config = Config.load_for_cli(
            config_path,
            address=ALT_ADDRESS,
            network=NetworkType.TESTNET,
            require_address=True,
        )

        assert config.hyperliquid.account_address == ALT_ADDRESS
        assert config.hyperliquid.network == NetworkType.TESTNET
        assert config.trading.default_slippage == Decimal("0.025")

    def test_file_without_address_raises_when_address_required(self, tmp_path: Path) -> None:
        """Config file lacking account_address fails when require_address=True."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            yaml.safe_dump({"hyperliquid": {"network": "mainnet"}}),
            encoding="utf-8",
        )

        with pytest.raises(ConfigurationError, match="Account address is required"):
            Config.load_for_cli(config_path, require_address=True)

    def test_invalid_address_override_fails_validation(self) -> None:
        """Invalid --address override is validated immediately."""
        with pytest.raises(ValidationError, match="must be a valid Ethereum address"):
            Config.load_for_cli(None, address="not-an-eth-address", require_address=True)
