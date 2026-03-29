"""
Tests for interactive CLI position hints and isolated margin commands.
"""

from decimal import Decimal

import pytest

from cli.interactive_cli import InteractiveCLI
from models.api import LeverageType, PositionInfo
from models.config import Config, HyperliquidConfig, NetworkType
from models.margin import IsolatedMarginUpdateResult


@pytest.fixture
def config() -> Config:
    """Create a mock configuration for CLI tests."""
    return Config(
        hyperliquid=HyperliquidConfig(
            account_address="0x1234567890123456789012345678901234567890",
            private_key="0x1234567890123456789012345678901234567890123456789012345678901234",
            network=NetworkType.MAINNET,
        )
    )


@pytest.fixture
def isolated_position() -> PositionInfo:
    """Create a sample isolated position for CLI tests."""
    return PositionInfo(
        coin="ETH",
        size=Decimal("0.1"),
        entry_price=Decimal("3000"),
        mark_price=Decimal("3100"),
        unrealized_pnl=Decimal("10"),
        leverage=15,
        leverage_type=LeverageType.ISOLATED,
        margin_used=Decimal("100"),
        removable_margin=Decimal("12.34"),
        cum_funding=Decimal("0.5"),
    )


def test_positions_command_shows_removable_margin(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    config: Config,
    isolated_position: PositionInfo,
):
    """Test positions output includes the removable margin column."""

    class FakeBackendAPI:
        def __init__(self, _config: Config):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return None

        def get_positions(self) -> list[PositionInfo]:
            return [isolated_position]

    monkeypatch.setattr("cli.interactive_cli.BackendAPI", FakeBackendAPI)

    cli = InteractiveCLI(config)
    cli.do_positions("")
    output = capsys.readouterr().out

    assert "Removable" in output
    assert "$12.34" in output


def test_update_margin_shows_hint_and_calls_backend(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    config: Config,
    isolated_position: PositionInfo,
):
    """Test update_margin shows the removable hint before submitting."""
    created_apis = []

    class FakeBackendAPI:
        def __init__(self, _config: Config):
            self.calls = []
            created_apis.append(self)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return None

        def get_position(self, coin: str) -> PositionInfo:
            assert coin == "ETH"
            return isolated_position

        def update_isolated_margin(
            self,
            amount: Decimal,
            coin: str,
        ) -> IsolatedMarginUpdateResult:
            self.calls.append((amount, coin))
            return IsolatedMarginUpdateResult(
                success=True,
                message="Successfully added $1.00 isolated margin to ETH",
                updated_position=isolated_position.model_copy(
                    update={"margin_used": Decimal("101"), "removable_margin": Decimal("13.34")}
                ),
            )

    monkeypatch.setattr("cli.interactive_cli.BackendAPI", FakeBackendAPI)

    cli = InteractiveCLI(config)
    cli.do_update_margin("ETH 1")
    output = capsys.readouterr().out

    assert created_apis[0].calls == [(Decimal("1"), "ETH")]
    assert "estimated removable isolated margin is up to $12.34" in output
    assert "Updated hint: estimated removable isolated margin is $13.34" in output


def test_update_margin_requires_existing_position(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    config: Config,
):
    """Test update_margin exits early when no current position exists."""
    created_apis = []

    class FakeBackendAPI:
        def __init__(self, _config: Config):
            self.calls = []
            created_apis.append(self)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return None

        def get_position(self, coin: str) -> PositionInfo:
            raise RuntimeError("not found")

        def update_isolated_margin(
            self,
            amount: Decimal,
            coin: str,
        ) -> IsolatedMarginUpdateResult:
            self.calls.append((amount, coin))
            raise AssertionError("update_isolated_margin should not be called")

    monkeypatch.setattr("cli.interactive_cli.BackendAPI", FakeBackendAPI)

    cli = InteractiveCLI(config)
    cli.do_update_margin("ETH 1")
    output = capsys.readouterr().out

    assert created_apis[0].calls == []
    assert "No current ETH position found" in output
