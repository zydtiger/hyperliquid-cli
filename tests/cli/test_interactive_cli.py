"""
Tests for interactive CLI position hints and isolated margin commands.
"""

from decimal import Decimal

import pytest

from cli.interactive_cli import InteractiveCLI
from models.api import LeverageType, PnlHistory, PnlPoint, PositionInfo
from models.config import Config, HyperliquidConfig, NetworkType
from models.margin import IsolatedMarginUpdateResult
from models.order import OrderHistoryEntry, OrderStatus


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
    assert "Updated hint: estimated removable isolated margin is up to $13.34" in output


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


@pytest.fixture
def order_history_entries() -> list[OrderHistoryEntry]:
    """Sample filled-order history entries for CLI tests."""
    return [
        OrderHistoryEntry(
            time=1762271507000,
            coin="ETH",
            direction="Open Long",
            price=Decimal("2020.6"),
            size=Decimal("0.005"),
            notional=Decimal("10.1030"),
            fee=Decimal("0.004000"),
            fee_usdc=Decimal("0.004000"),
            fee_token="USDC",  # noqa: S106 - fee token symbol, not a credential
            gross_closed_pnl=Decimal("0.300000"),
            closed_pnl=Decimal("0.296000"),
            order_id=333001,
            status=OrderStatus.FILLED,
        )
    ]


def test_order_history_defaults_to_ten(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    config: Config,
    order_history_entries: list[OrderHistoryEntry],
):
    """Test order_history defaults to 10 entries."""
    created_apis = []

    class FakeBackendAPI:
        def __init__(self, _config: Config):
            self.calls = []
            created_apis.append(self)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return None

        def get_order_history(self, limit: int) -> list[OrderHistoryEntry]:
            self.calls.append(limit)
            return order_history_entries

    monkeypatch.setattr("cli.interactive_cli.BackendAPI", FakeBackendAPI)

    cli = InteractiveCLI(config)
    cli.do_order_history("")
    output = capsys.readouterr().out

    assert created_apis[0].calls == [10]
    assert "Order History (1)" in output
    assert "Time" in output
    assert "Closed PnL" in output


def test_order_history_uses_explicit_limit(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    config: Config,
    order_history_entries: list[OrderHistoryEntry],
):
    """Test order_history forwards the explicit limit."""
    created_apis = []

    class FakeBackendAPI:
        def __init__(self, _config: Config):
            self.calls = []
            created_apis.append(self)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return None

        def get_order_history(self, limit: int) -> list[OrderHistoryEntry]:
            self.calls.append(limit)
            return order_history_entries

    monkeypatch.setattr("cli.interactive_cli.BackendAPI", FakeBackendAPI)

    cli = InteractiveCLI(config)
    cli.do_order_history("5")
    capsys.readouterr()

    assert created_apis[0].calls == [5]


@pytest.mark.parametrize("args", ["abc", "0", "-1", "1 2"])
def test_order_history_rejects_invalid_args(
    args: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    config: Config,
):
    """Test order_history validates CLI arguments."""

    class FakeBackendAPI:
        def __init__(self, _config: Config):
            raise AssertionError("BackendAPI should not be created for invalid args")

    monkeypatch.setattr("cli.interactive_cli.BackendAPI", FakeBackendAPI)

    cli = InteractiveCLI(config)
    cli.do_order_history(args)
    output = capsys.readouterr().out

    assert "Usage: order_history [N]" in output


@pytest.fixture
def pnl_history() -> PnlHistory:
    """Sample PnL history for CLI tests."""
    return PnlHistory(
        window="7d",
        points=[
            PnlPoint(
                time=1741886630493,
                total_pnl=Decimal("0.0"),
                perp_pnl=Decimal("0.0"),
                spot_pnl=Decimal("0.0"),
            ),
            PnlPoint(
                time=1741973030493,
                total_pnl=Decimal("10.5"),
                perp_pnl=Decimal("7.0"),
                spot_pnl=Decimal("3.5"),
            ),
            PnlPoint(
                time=1742059430493,
                total_pnl=Decimal("6.0"),
                perp_pnl=Decimal("8.5"),
                spot_pnl=Decimal("-2.5"),
            ),
        ],
    )


def test_pnl_command_renders_graph(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    config: Config,
    pnl_history: PnlHistory,
):
    """Test pnl launches the fullscreen TUI renderer."""
    created_apis = []
    launched_histories = []

    class FakeBackendAPI:
        def __init__(self, _config: Config):
            self.calls = 0
            created_apis.append(self)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return None

        def get_pnl_history(self) -> PnlHistory:
            self.calls += 1
            return pnl_history

    class FakePnlTUI:
        def __init__(self, history: PnlHistory):
            launched_histories.append(history)

        def run(self) -> None:
            launched_histories.append("ran")

    monkeypatch.setattr("cli.interactive_cli.BackendAPI", FakeBackendAPI)
    monkeypatch.setattr("cli.interactive_cli.PnlTUI", FakePnlTUI)

    cli = InteractiveCLI(config)
    cli.do_pnl("")
    output = capsys.readouterr().out

    assert created_apis[0].calls == 1
    assert launched_histories == [pnl_history, "ran"]
    assert output == "\n"


def test_pnl_command_rejects_extra_args(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    config: Config,
):
    """Test pnl validates its no-argument interface."""

    class FakeBackendAPI:
        def __init__(self, _config: Config):
            raise AssertionError("BackendAPI should not be created for invalid args")

    monkeypatch.setattr("cli.interactive_cli.BackendAPI", FakeBackendAPI)

    cli = InteractiveCLI(config)
    cli.do_pnl("7d")
    output = capsys.readouterr().out

    assert "Usage: pnl" in output


def test_pnl_command_handles_empty_history(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    config: Config,
):
    """Test pnl prints the empty-state message when no points are available."""

    class FakeBackendAPI:
        def __init__(self, _config: Config):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return None

        def get_pnl_history(self) -> PnlHistory:
            return PnlHistory(window="7d", points=[])

    monkeypatch.setattr("cli.interactive_cli.BackendAPI", FakeBackendAPI)

    cli = InteractiveCLI(config)
    cli.do_pnl("")
    output = capsys.readouterr().out

    assert "No 7-day PnL history found." in output
