"""
Comprehensive unit tests for configuration models.

Tests all configuration classes, validators, constraints, and Pydantic V2 features.
"""

import tempfile
from decimal import Decimal
from pathlib import Path
import yaml

import pytest

from models.config import (
    BackendConfig,
    Config,
    ConfigurationError,
    HyperliquidConfig,
    LoggingConfig,
    NetworkType,
    TradingConfig,
)
from models.order import OrderTif


class TestNetworkType:
    """Test NetworkType enum."""

    def test_network_type_values(self):
        """Test NetworkType enum has correct values."""
        assert NetworkType.MAINNET.value == "mainnet"
        assert NetworkType.TESTNET.value == "testnet"
        assert len(NetworkType) == 2

    def test_network_type_inheritance(self):
        """Test NetworkType inherits from str enum."""
        assert issubclass(NetworkType, str)
        assert NetworkType.MAINNET.value == "mainnet"


class TestHyperliquidConfig:
    """Test HyperliquidConfig model."""

    def test_valid_config_creation(self):
        """Test creating valid HyperliquidConfig."""
        config = HyperliquidConfig(
            account_address="0x1234567890123456789012345678901234567890",
            private_key="0x1234567890123456789012345678901234567890123456789012345678901234",
            network="mainnet",
        )
        assert config.account_address == "0x1234567890123456789012345678901234567890"
        assert (
            config.private_key
            == "0x1234567890123456789012345678901234567890123456789012345678901234"
        )
        assert config.network == NetworkType.MAINNET

    def test_valid_config_with_enum(self):
        """Test creating config with enum directly."""
        config = HyperliquidConfig(
            account_address="0x1234567890123456789012345678901234567890",
            private_key="0x1234567890123456789012345678901234567890123456789012345678901234",
            network=NetworkType.TESTNET,
        )
        assert config.network == NetworkType.TESTNET

    def test_default_network(self):
        """Test default network is mainnet."""
        config = HyperliquidConfig(
            account_address="0x1234567890123456789012345678901234567890",
            private_key="0x1234567890123456789012345678901234567890123456789012345678901234",
        )
        assert config.network == NetworkType.MAINNET

    def test_invalid_account_address(self):
        """Test validation fails for invalid account address."""
        # Empty address
        with pytest.raises(ValueError, match="account_address is required"):
            HyperliquidConfig(
                account_address="",
                private_key="0x1234567890123456789012345678901234567890123456789012345678901234",
            )

        # Not starting with 0x
        with pytest.raises(ValueError, match="must be a valid Ethereum address"):
            HyperliquidConfig(
                account_address="1234567890123456789012345678901234567890",
                private_key="0x1234567890123456789012345678901234567890123456789012345678901234",
            )

    def test_invalid_private_key(self):
        """Test validation fails for invalid private key."""
        # Empty private key
        with pytest.raises(ValueError, match="private_key is required"):
            HyperliquidConfig(
                account_address="0x1234567890123456789012345678901234567890",
                private_key="",
            )

        # Wrong length
        with pytest.raises(ValueError, match="must be a valid 32-byte hex string"):
            HyperliquidConfig(
                account_address="0x1234567890123456789012345678901234567890",
                private_key="0x123456789012345678901234567890123456789012345678901234567890",
            )

        # Not starting with 0x
        with pytest.raises(ValueError, match="must be a valid 32-byte hex string"):
            HyperliquidConfig(
                account_address="0x1234567890123456789012345678901234567890",
                private_key="1234567890123456789012345678901234567890123456789012345678901234",
            )

    def test_extra_fields_forbidden(self):
        """Test extra fields are rejected."""
        with pytest.raises(Exception) as exc_info:
            HyperliquidConfig(
                account_address="0x1234567890123456789012345678901234567890",
                private_key="0x1234567890123456789012345678901234567890123456789012345678901234",
                unknown_field="value",
            )
        assert "Extra inputs are not permitted" in str(exc_info.value)

    def test_validate_assignment(self):
        """Test assignment validation works."""
        config = HyperliquidConfig(
            account_address="0x1234567890123456789012345678901234567890",
            private_key="0x1234567890123456789012345678901234567890123456789012345678901234",
        )

        # Valid assignment should work
        config.account_address = "0xabcdef123456789012345678901234567890abcdef"
        assert config.account_address == "0xabcdef123456789012345678901234567890abcdef"

        # Invalid assignment should fail
        with pytest.raises(ValueError, match="must be a valid Ethereum address"):
            config.account_address = "invalid_address"


class TestTradingConfig:
    """Test TradingConfig model."""

    def test_valid_config_creation(self):
        """Test creating valid TradingConfig."""
        config = TradingConfig(
            default_slippage=Decimal("0.05"),
            default_time_in_force="GTC",
        )
        assert config.default_slippage == Decimal("0.05")
        assert config.default_time_in_force == OrderTif.GTC

    def test_default_values(self):
        """Test default values are applied correctly."""
        config = TradingConfig()
        assert config.default_slippage == Decimal("0.01")
        assert config.default_time_in_force == OrderTif.GTC

    def test_slippage_constraints(self):
        """Test slippage field constraints."""
        # Valid values
        valid_values = [
            Decimal("0.001"),
            Decimal("0.1"),
            Decimal("0.5"),
            Decimal("0.99"),
        ]
        for value in valid_values:
            config = TradingConfig(default_slippage=value)
            assert config.default_slippage == value

        # Invalid values (too low)
        invalid_low = [Decimal("0"), Decimal("-0.1"), Decimal("-1")]
        for value in invalid_low:
            with pytest.raises(Exception) as exc_info:
                TradingConfig(default_slippage=value)
            assert "Input should be greater than 0" in str(exc_info.value)

        # Invalid values (too high)
        invalid_high = [Decimal("1"), Decimal("1.1"), Decimal("2")]
        for value in invalid_high:
            with pytest.raises(Exception) as exc_info:
                TradingConfig(default_slippage=value)
            assert "Input should be less than 1" in str(exc_info.value)

    def test_time_in_force_enum_conversion(self):
        """Test string to enum conversion for time_in_force."""
        valid_values = ["ALO", "IOC", "GTC"]
        for value in valid_values:
            config = TradingConfig(default_time_in_force=value)
            assert isinstance(config.default_time_in_force, OrderTif)

        # Invalid case sensitivity
        invalid_values = ["Alo", "Ioc", "Gtc", "alo", "ioc", "gtc", "INVALID"]
        for value in invalid_values:
            with pytest.raises(Exception):
                TradingConfig(default_time_in_force=value)

    def test_extra_fields_forbidden(self):
        """Test extra fields are rejected."""
        with pytest.raises(Exception) as exc_info:
            TradingConfig(unknown_field="value")
        assert "Extra inputs are not permitted" in str(exc_info.value)

    def test_validate_assignment(self):
        """Test assignment validation works."""
        config = TradingConfig()

        # Valid assignment should work
        config.default_slippage = Decimal("0.05")
        assert config.default_slippage == Decimal("0.05")

        # Invalid assignment should fail (constraint violation)
        with pytest.raises(Exception) as exc_info:
            config.default_slippage = Decimal("2.0")
        assert "Input should be less than 1" in str(exc_info.value)

        # Valid enum assignment should work
        config.default_time_in_force = "IOC"
        assert config.default_time_in_force == OrderTif.IOC

        # Invalid enum assignment should fail
        with pytest.raises(Exception):
            config.default_time_in_force = "INVALID"


class TestLoggingConfig:
    """Test LoggingConfig model."""

    def test_valid_config_creation(self):
        """Test creating valid LoggingConfig."""
        config = LoggingConfig(level="DEBUG")
        assert config.level == "DEBUG"

    def test_default_value(self):
        """Test default level is INFO."""
        config = LoggingConfig()
        assert config.level == "INFO"

    def test_valid_levels(self):
        """Test all valid log levels."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        for level in valid_levels:
            config = LoggingConfig(level=level)
            assert config.level == level

    def test_invalid_level(self):
        """Test invalid log levels are rejected."""
        invalid_levels = ["TRACE", "VERBOSE", "INFO ", " debug", "invalid"]
        for level in invalid_levels:
            with pytest.raises(ValueError, match="logging.level must be one of"):
                LoggingConfig(level=level)

    def test_extra_fields_forbidden(self):
        """Test extra fields are rejected."""
        with pytest.raises(Exception) as exc_info:
            LoggingConfig(unknown_field="value")
        assert "Extra inputs are not permitted" in str(exc_info.value)

    def test_validate_assignment(self):
        """Test assignment validation works."""
        config = LoggingConfig()

        # Valid assignment should work
        config.level = "ERROR"
        assert config.level == "ERROR"

        # Invalid assignment should fail
        with pytest.raises(ValueError, match="logging.level must be one of"):
            config.level = "INVALID"


class TestBackendConfig:
    """Test BackendConfig model."""

    def test_valid_config_creation(self):
        """Test creating valid BackendConfig."""
        logging_config = LoggingConfig(level="DEBUG")
        config = BackendConfig(
            host="0.0.0.0",
            port=9000,
            logging=logging_config,
        )
        assert config.host == "0.0.0.0"
        assert config.port == 9000
        assert config.logging.level == "DEBUG"

    def test_default_values(self):
        """Test default values are applied correctly."""
        config = BackendConfig()
        assert config.host == "localhost"
        assert config.port == 8080
        assert config.logging.level == "INFO"  # Default logging config

    def test_port_constraints(self):
        """Test port field constraints."""
        # Valid ports
        valid_ports = [1, 80, 443, 8080, 65535]
        for port in valid_ports:
            config = BackendConfig(port=port)
            assert config.port == port

        # Invalid ports (too low)
        invalid_low = [0, -1, -100]
        for port in invalid_low:
            with pytest.raises(Exception) as exc_info:
                BackendConfig(port=port)
            assert "Input should be greater than or equal to 1" in str(exc_info.value)

        # Invalid ports (too high)
        invalid_high = [65536, 70000, 100000]
        for port in invalid_high:
            with pytest.raises(Exception) as exc_info:
                BackendConfig(port=port)
            assert "Input should be less than or equal to 65535" in str(exc_info.value)

    def test_nested_logging_config(self):
        """Test nested logging config validation."""
        # Valid nested config
        config = BackendConfig(
            host="localhost",
            port=8080,
            logging={"level": "DEBUG"},
        )
        assert config.logging.level == "DEBUG"

        # Invalid nested config
        with pytest.raises(ValueError, match="logging.level must be one of"):
            BackendConfig(
                host="localhost",
                port=8080,
                logging={"level": "INVALID"},
            )

    def test_extra_fields_forbidden(self):
        """Test extra fields are rejected."""
        with pytest.raises(Exception) as exc_info:
            BackendConfig(unknown_field="value")
        assert "Extra inputs are not permitted" in str(exc_info.value)

    def test_validate_assignment(self):
        """Test assignment validation works."""
        config = BackendConfig()

        # Valid assignments should work
        config.host = "0.0.0.0"
        assert config.host == "0.0.0.0"

        config.port = 9000
        assert config.port == 9000

        config.logging.level = "ERROR"
        assert config.logging.level == "ERROR"

        # Invalid assignments should fail
        with pytest.raises(Exception) as exc_info:
            config.port = 70000
        assert "Input should be less than or equal to 65535" in str(exc_info.value)

        with pytest.raises(ValueError, match="logging.level must be one of"):
            config.logging.level = "INVALID"


class TestConfig:
    """Test main Config class."""

    def test_valid_config_creation(self):
        """Test creating valid Config."""
        config_data = {
            "hyperliquid": {
                "account_address": "0x1234567890123456789012345678901234567890",
                "private_key": "0x1234567890123456789012345678901234567890123456789012345678901234",
                "network": "mainnet",
            },
            "trading": {
                "default_slippage": "0.02",
                "default_time_in_force": "IOC",
            },
            "backend": {
                "host": "0.0.0.0",
                "port": 9000,
                "logging": {"level": "DEBUG"},
            },
        }
        config = Config(**config_data)

        assert (
            config.hyperliquid.account_address
            == "0x1234567890123456789012345678901234567890"
        )
        assert config.hyperliquid.network == NetworkType.MAINNET
        assert config.trading.default_slippage == Decimal("0.02")
        assert config.trading.default_time_in_force == OrderTif.IOC
        assert config.backend.host == "0.0.0.0"
        assert config.backend.port == 9000
        assert config.backend.logging.level == "DEBUG"

    def test_minimal_config_creation(self):
        """Test creating config with only required hyperliquid section."""
        config_data = {
            "hyperliquid": {
                "account_address": "0x1234567890123456789012345678901234567890",
                "private_key": "0x1234567890123456789012345678901234567890123456789012345678901234",
            }
        }
        config = Config(**config_data)

        assert config.hyperliquid.network == NetworkType.MAINNET  # Default
        assert config.trading.default_slippage == Decimal("0.01")  # Default
        assert config.trading.default_time_in_force == OrderTif.GTC  # Default
        assert config.backend.host == "localhost"  # Default
        assert config.backend.port == 8080  # Default
        assert config.backend.logging.level == "INFO"  # Default

    def test_missing_hyperliquid_section(self):
        """Test validation fails when hyperliquid section is missing."""
        config_data = {
            "trading": {"default_slippage": "0.02"},
        }
        with pytest.raises(Exception) as exc_info:
            Config(**config_data)
        assert "hyperliquid" in str(exc_info.value)

    def test_extra_fields_forbidden(self):
        """Test extra fields are rejected at top level."""
        config_data = {
            "hyperliquid": {
                "account_address": "0x1234567890123456789012345678901234567890",
                "private_key": "0x1234567890123456789012345678901234567890123456789012345678901234",
            },
            "unknown_section": "value",
        }
        with pytest.raises(Exception) as exc_info:
            Config(**config_data)
        assert "Extra inputs are not permitted" in str(exc_info.value)

    def test_nested_extra_fields_forbidden(self):
        """Test extra fields are rejected in nested sections."""
        config_data = {
            "hyperliquid": {
                "account_address": "0x1234567890123456789012345678901234567890",
                "private_key": "0x1234567890123456789012345678901234567890123456789012345678901234",
                "unknown_field": "value",
            }
        }
        with pytest.raises(Exception) as exc_info:
            Config(**config_data)
        assert "Extra inputs are not permitted" in str(exc_info.value)

    def test_from_dict_method(self):
        """Test direct creation from dict (equivalent to from_dict)."""
        config_data = {
            "hyperliquid": {
                "account_address": "0x1234567890123456789012345678901234567890",
                "private_key": "0x1234567890123456789012345678901234567890123456789012345678901234",
            }
        }
        config = Config(**config_data)
        assert isinstance(config, Config)
        assert (
            config.hyperliquid.account_address
            == "0x1234567890123456789012345678901234567890"
        )

    def test_from_file_method(self):
        """Test from_file class method."""
        config_data = {
            "hyperliquid": {
                "account_address": "0x1234567890123456789012345678901234567890",
                "private_key": "0x1234567890123456789012345678901234567890123456789012345678901234",
                "network": "testnet",
            },
            "trading": {
                "default_slippage": "0.05",
            },
        }

        # Create temporary config file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = Path(f.name)

        try:
            config = Config.from_file(temp_path)
            assert isinstance(config, Config)
            assert config.hyperliquid.network == NetworkType.TESTNET
            assert config.trading.default_slippage == Decimal("0.05")
        finally:
            temp_path.unlink()

    def test_from_file_not_found(self):
        """Test from_file raises error for non-existent file."""
        non_existent_path = Path("/tmp/does_not_exist_config.yaml")
        with pytest.raises(ConfigurationError, match="Configuration file not found"):
            Config.from_file(non_existent_path)

    def test_from_file_invalid_yaml(self):
        """Test from_file raises error for invalid YAML."""
        # Create temporary file with invalid YAML
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [")  # Invalid YAML
            temp_path = Path(f.name)

        try:
            with pytest.raises(
                ConfigurationError, match="Invalid YAML in configuration file"
            ):
                Config.from_file(temp_path)
        finally:
            temp_path.unlink()

    def test_from_file_empty_file(self):
        """Test from_file raises error for empty file."""
        # Create temporary empty file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")  # Empty file
            temp_path = Path(f.name)

        try:
            with pytest.raises(ConfigurationError, match="Configuration file is empty"):
                Config.from_file(temp_path)
        finally:
            temp_path.unlink()

    def test_from_file_invalid_config(self):
        """Test from_file raises error for invalid configuration."""
        config_data = {
            "hyperliquid": {
                "account_address": "invalid_address",  # Invalid
                "private_key": "0x1234567890123456789012345678901234567890123456789012345678901234",
            }
        }

        # Create temporary config file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = Path(f.name)

        try:
            with pytest.raises(Exception) as exc_info:
                Config.from_file(temp_path)
            assert "must be a valid Ethereum address" in str(exc_info.value)
        finally:
            temp_path.unlink()

    def test_validate_assignment(self):
        """Test assignment validation works on nested configs."""
        config = Config(
            **{
                "hyperliquid": {
                    "account_address": "0x1234567890123456789012345678901234567890",
                    "private_key": "0x1234567890123456789012345678901234567890123456789012345678901234",
                }
            }
        )

        # Valid assignments should work
        config.trading.default_slippage = Decimal("0.05")
        assert config.trading.default_slippage == Decimal("0.05")

        config.backend.port = 9000
        assert config.backend.port == 9000

        # Invalid assignments should fail
        with pytest.raises(Exception) as exc_info:
            config.hyperliquid.account_address = "invalid"
        assert "must be a valid Ethereum address" in str(exc_info.value)

        with pytest.raises(Exception) as exc_info:
            config.trading.default_slippage = Decimal("2.0")
        assert "Input should be less than 1" in str(exc_info.value)


class TestConfigIntegration:
    """Integration tests for the complete configuration system."""

    def test_complete_real_world_config(self):
        """Test with a complete realistic configuration."""
        config_data = {
            "hyperliquid": {
                "account_address": "0xabcdef123456789012345678901234567890abcdef",
                "private_key": "0x1234567890123456789012345678901234567890123456789012345678901234",
                "network": "testnet",
            },
            "trading": {
                "default_slippage": "0.025",
                "default_time_in_force": "ALO",
            },
            "backend": {
                "host": "127.0.0.1",
                "port": 3000,
                "logging": {"level": "WARNING"},
            },
        }

        config = Config(**config_data)

        # Verify all values are correctly parsed and converted
        assert (
            config.hyperliquid.account_address
            == "0xabcdef123456789012345678901234567890abcdef"
        )
        assert config.hyperliquid.network == NetworkType.TESTNET
        assert config.trading.default_slippage == Decimal("0.025")
        assert config.trading.default_time_in_force == OrderTif.ALO
        assert config.backend.host == "127.0.0.1"
        assert config.backend.port == 3000
        assert config.backend.logging.level == "WARNING"

    def test_config_serialization(self):
        """Test that config can be serialized for debugging/logging."""
        config_data = {
            "hyperliquid": {
                "account_address": "0x1234567890123456789012345678901234567890",
                "private_key": "0x1234567890123456789012345678901234567890123456789012345678901234",
            }
        }
        config = Config(**config_data)

        # Test model_dump works
        data = config.model_dump()
        assert "hyperliquid" in data
        assert "trading" in data
        assert "backend" in data
        assert data["hyperliquid"]["network"] == "mainnet"

        # Test JSON serialization works
        json_str = config.model_dump_json()
        assert isinstance(json_str, str)
        assert "hyperliquid" in json_str

    def test_config_copy_and_update(self):
        """Test config copying and updating functionality."""

        config_dict = {
            "hyperliquid": {
                "account_address": "0x1234567890123456789012345678901234567890",
                "private_key": "0x1234567890123456789012345678901234567890123456789012345678901234",
            }
        }

        original_config = Config(**config_dict)

        # Test copy
        copied_config = original_config.model_copy()
        assert (
            copied_config.hyperliquid.account_address
            == original_config.hyperliquid.account_address
        )

        # Test copy with update
        updated_config = original_config.model_copy(
            update={"trading": TradingConfig(default_slippage=Decimal("0.05"))}
        )
        assert updated_config.trading.default_slippage == Decimal("0.05")
        assert original_config.trading.default_slippage == Decimal(
            "0.01"
        )  # Original unchanged

        # Validation should still work on update
        with pytest.raises(Exception) as exc_info:
            original_config.model_copy(
                update={
                    "trading": TradingConfig(default_slippage=Decimal("2.0"))  # Invalid
                }
            )
        assert "Input should be less than 1" in str(exc_info.value)
