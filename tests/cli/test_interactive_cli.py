"""
Tests for interactive CLI position hints and isolated margin commands.
"""

import sys
from decimal import Decimal
from io import StringIO
from typing import TextIO

import pytest

from cli.interactive_cli import InteractiveCLI
from models.api import (
    DEFAULT_PNL_WINDOW,
    CoinMetadata,
    LeverageType,
    OrderBookLevel,
    PnlHistory,
    PnlHistoryCatalog,
    PnlPoint,
    PositionInfo,
    StakingDelegation,
    StakingStatus,
    Ticker,
    WatchCandle,
    WatchSnapshot,
)
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
            self.calls: list[tuple[Decimal, str]] = []
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
            self.calls: list[tuple[Decimal, str]] = []
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
            self.calls: list[int] = []
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
            self.calls: list[int] = []
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
def pnl_history() -> PnlHistoryCatalog:
    """Sample multi-window PnL history for CLI tests."""
    return PnlHistoryCatalog(
        default_window=DEFAULT_PNL_WINDOW,
        histories=[
            PnlHistory(window="1d", points=[]),
            PnlHistory(
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
            ),
        ],
    )


@pytest.fixture
def watch_snapshot() -> WatchSnapshot:
    """Sample watch snapshot for CLI tests."""
    return WatchSnapshot(
        coin="BTC",
        interval="5m",
        mark_price=Decimal("43250.50"),
        open_interest=Decimal("1250.75"),
        updated_at=1741973030493,
        candles=[
            WatchCandle(
                open_time=1741972800000,
                close_time=1741973100000,
                open=Decimal("43210.25"),
                high=Decimal("43250.50"),
                low=Decimal("43200.00"),
                close=Decimal("43250.50"),
                is_closed=False,
            ),
        ],
        bids=[OrderBookLevel(price=Decimal("43249.50"), size=Decimal("1.25"))],
        asks=[OrderBookLevel(price=Decimal("43250.75"), size=Decimal("0.50"))],
        size_decimals=5,
    )


def test_pnl_command_renders_graph(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    config: Config,
    pnl_history: PnlHistoryCatalog,
):
    """Test pnl launches the fullscreen TUI renderer."""
    created_apis = []
    launched_histories: list[object] = []

    class FakeBackendAPI:
        def __init__(self, _config: Config):
            self.calls = 0
            created_apis.append(self)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return None

        def get_pnl_history(self) -> PnlHistoryCatalog:
            self.calls += 1
            return pnl_history

    class FakePnlTUI:
        def __init__(self, history: PnlHistoryCatalog):
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

        def get_pnl_history(self) -> PnlHistoryCatalog:
            return PnlHistoryCatalog(
                default_window=DEFAULT_PNL_WINDOW,
                histories=[PnlHistory(window="7d", points=[])],
            )

    monkeypatch.setattr("cli.interactive_cli.BackendAPI", FakeBackendAPI)

    cli = InteractiveCLI(config)
    cli.do_pnl("")
    output = capsys.readouterr().out

    assert "No PnL history found." in output


def test_watch_command_renders_graph(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    config: Config,
    watch_snapshot: WatchSnapshot,
):
    """Test watch launches the live watch TUI renderer."""
    created_apis = []
    launched = []

    class FakeBackendAPI:
        def __init__(self, _config: Config):
            self.calls: list[str] = []
            created_apis.append(self)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return None

        def get_watch_snapshot(
            self, coin: str, interval: str = "5m", depth: int = 10
        ) -> WatchSnapshot:
            self.calls.append(f"{coin}:{interval}:{depth}")
            return watch_snapshot

    class FakeWatchTUI:
        def __init__(self, coin: str, fetcher):
            launched.append(coin)
            launched.append(fetcher("BTC", "5m", 10))

        def run(self) -> None:
            launched.append("ran")

    monkeypatch.setattr("cli.interactive_cli.BackendAPI", FakeBackendAPI)
    monkeypatch.setattr("cli.interactive_cli.WatchTUI", FakeWatchTUI)

    cli = InteractiveCLI(config)
    cli.do_watch("btc")
    output = capsys.readouterr().out

    assert created_apis[0].calls == ["BTC:5m:10", "BTC:5m:10"]
    assert launched == ["BTC", watch_snapshot, "ran"]
    assert output == "\n"


@pytest.mark.parametrize("args", ["", "BTC ETH"])
def test_watch_command_rejects_invalid_args(
    args: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    config: Config,
):
    """Test watch validates its required single-argument interface."""

    class FakeBackendAPI:
        def __init__(self, _config: Config):
            raise AssertionError("BackendAPI should not be created for invalid args")

    monkeypatch.setattr("cli.interactive_cli.BackendAPI", FakeBackendAPI)

    cli = InteractiveCLI(config)
    cli.do_watch(args)
    output = capsys.readouterr().out

    assert "Usage: watch <coin>" in output


def test_watch_command_handles_backend_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    config: Config,
):
    """Test watch prints backend errors cleanly."""

    class FakeBackendAPI:
        def __init__(self, _config: Config):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return None

        def get_watch_snapshot(
            self, coin: str, interval: str = "5m", depth: int = 10
        ) -> WatchSnapshot:
            raise RuntimeError(f"{coin} unavailable")

    monkeypatch.setattr("cli.interactive_cli.BackendAPI", FakeBackendAPI)

    cli = InteractiveCLI(config)
    cli.do_watch("BTC")
    output = capsys.readouterr().out

    assert "Error fetching watch snapshot for BTC" in output
    assert "BTC unavailable" in output


def test_info_command_renders_open_interest_as_usd(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    config: Config,
):
    """Test info renders open interest with a leading dollar sign."""

    class FakeBackendAPI:
        def __init__(self, _config: Config):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return None

        def get_ticker(self, coin: str) -> Ticker:
            return Ticker(
                coin=coin,
                mark_price=Decimal("43250.50"),
                funding_rate=Decimal("0.0001"),
                open_interest=Decimal("54109437.50"),
            )

        def get_metadata(self, coin: str) -> CoinMetadata:
            return CoinMetadata(coin=coin, size_decimals=5, max_leverage=50)

    monkeypatch.setattr("cli.interactive_cli.BackendAPI", FakeBackendAPI)

    cli = InteractiveCLI(config)
    cli.do_info("BTC")
    output = capsys.readouterr().out

    assert "$54,109,437.50" in output


def test_staking_command_renders_summary_and_table(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    config: Config,
):
    """Test staking prints summary and validator rows."""

    class FakeBackendAPI:
        def __init__(self, _config: Config):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return None

        def get_staking_status(self) -> StakingStatus:
            return StakingStatus(
                total_staked=Decimal("100.61607572"),
                total_reward=Decimal("2.00000000"),
                delegations=[
                    StakingDelegation(
                        validator="validator-1",
                        name="CMI",
                        commission=Decimal("0.05"),
                        amount=Decimal("70.50000000"),
                    ),
                    StakingDelegation(
                        validator="validator-2",
                        name="HyperStake",
                        commission=Decimal("0.10"),
                        amount=Decimal("30.11607572"),
                    ),
                ],
            )

    monkeypatch.setattr("cli.interactive_cli.BackendAPI", FakeBackendAPI)

    cli = InteractiveCLI(config)
    cli.do_staking("")
    output = capsys.readouterr().out

    assert "Staking Summary" in output
    assert "100.61607572 HYPE" in output
    assert "2.00000000 HYPE" in output
    assert "Active Staking Endpoints" in output
    assert "validator-1" in output
    assert "CMI" in output
    assert "5.00%" in output
    assert "70.50000000" in output


def test_staking_command_empty_state(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    config: Config,
):
    """Test staking prints the empty-state message when no delegations exist."""

    class FakeBackendAPI:
        def __init__(self, _config: Config):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return None

        def get_staking_status(self) -> StakingStatus:
            return StakingStatus(
                total_staked=Decimal("0"), total_reward=Decimal("0"), delegations=[]
            )

    monkeypatch.setattr("cli.interactive_cli.BackendAPI", FakeBackendAPI)

    cli = InteractiveCLI(config)
    cli.do_staking("")
    output = capsys.readouterr().out

    assert "Staking Summary" in output
    assert "0.00000000 HYPE" in output
    assert "No active HYPE staking delegations found." in output


def test_staking_command_rejects_extra_args(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    config: Config,
):
    """Test staking validates its no-argument interface."""

    class FakeBackendAPI:
        def __init__(self, _config: Config):
            raise AssertionError("BackendAPI should not be created for invalid args")

    monkeypatch.setattr("cli.interactive_cli.BackendAPI", FakeBackendAPI)

    cli = InteractiveCLI(config)
    cli.do_staking("extra")
    output = capsys.readouterr().out

    assert "Usage: staking" in output


def test_staking_command_handles_backend_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    config: Config,
):
    """Test staking prints backend errors cleanly."""

    class FakeBackendAPI:
        def __init__(self, _config: Config):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return None

        def get_staking_status(self) -> StakingStatus:
            raise RuntimeError("staking unavailable")

    monkeypatch.setattr("cli.interactive_cli.BackendAPI", FakeBackendAPI)

    cli = InteractiveCLI(config)
    cli.do_staking("")
    output = capsys.readouterr().out

    assert "Error fetching staking status" in output
    assert "staking unavailable" in output


def test_clear_command_clears_screen(
    capsys: pytest.CaptureFixture[str],
    config: Config,
):
    """Test clear emits the terminal clear sequence."""
    cli = InteractiveCLI(config)

    cli.do_clear("")
    output = capsys.readouterr().out

    assert output == "\033[2J\033[H"


def test_cls_command_is_alias_for_clear(
    capsys: pytest.CaptureFixture[str],
    config: Config,
):
    """Test cls emits the same terminal clear sequence as clear."""
    cli = InteractiveCLI(config)

    cli.do_cls("")
    output = capsys.readouterr().out

    assert output == "\033[2J\033[H"


@pytest.mark.parametrize(
    ("command", "expected_usage"),
    [("clear", "Usage: clear"), ("cls", "Usage: clear")],
)
def test_clear_commands_reject_extra_args(
    command: str,
    expected_usage: str,
    capsys: pytest.CaptureFixture[str],
    config: Config,
):
    """Test clear aliases reject unexpected arguments."""
    cli = InteractiveCLI(config)

    getattr(cli, f"do_{command}")("extra")
    output = capsys.readouterr().out

    assert expected_usage in output


def test_clear_commands_are_in_command_completion(config: Config):
    """Test clear aliases are available for command completion."""
    cli = InteractiveCLI(config)

    assert "clear" in cli.completenames("cl")
    assert "cls" in cli.completenames("cl")
    assert "watch" in cli.completenames("wa")


@pytest.mark.parametrize(
    ("command", "expected_text"),
    [
        ("help clear", "clear - Clear the terminal screen"),
        ("clear extra", "Usage: clear"),
        ("conditionals", "Conditionals functionality not implemented yet"),
        ("wat", "Unknown command: wat"),
    ],
)
def test_onecmd_always_ends_with_single_blank_line(
    command: str,
    expected_text: str,
    capsys: pytest.CaptureFixture[str],
    config: Config,
):
    """Test command output is normalized to one trailing blank line in interactive mode."""
    cli = InteractiveCLI(config)

    cli.onecmd(command)
    output = capsys.readouterr().out

    assert expected_text in output
    assert output.endswith("\n\n")
    assert not output.endswith("\n\n\n")


@pytest.mark.parametrize(
    ("command", "expected_calls"),
    [("pnl", ["pnl"]), ("watch BTC", ["BTC:5m:10", "BTC:5m:10"])],
)
def test_onecmd_bypasses_normalizing_writer_for_tui_commands(
    command: str,
    expected_calls: list[str],
    monkeypatch: pytest.MonkeyPatch,
    config: Config,
    pnl_history: PnlHistoryCatalog,
    watch_snapshot: WatchSnapshot,
):
    """Test fullscreen TUI commands write to and flush the original stdout."""

    class TrackingStdout(StringIO):
        def __init__(self) -> None:
            super().__init__()
            self.flush_count = 0

        def flush(self) -> None:
            self.flush_count += 1
            super().flush()

    tracked_stdout = TrackingStdout()
    observed_stdouts: list[TextIO] = []
    created_apis = []

    class FakeBackendAPI:
        def __init__(self, _config: Config):
            self.calls: list[str] = []
            created_apis.append(self)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return None

        def get_pnl_history(self) -> PnlHistoryCatalog:
            self.calls.append("pnl")
            return pnl_history

        def get_watch_snapshot(
            self, coin: str, interval: str = "5m", depth: int = 10
        ) -> WatchSnapshot:
            self.calls.append(f"{coin}:{interval}:{depth}")
            return watch_snapshot

    class FakePnlTUI:
        def __init__(self, history: PnlHistoryCatalog):
            assert history == pnl_history

        def run(self) -> None:
            observed_stdouts.append(sys.stdout)

    class FakeWatchTUI:
        def __init__(self, coin: str, fetcher):
            assert coin == "BTC"
            assert fetcher("BTC", "5m", 10) == watch_snapshot

        def run(self) -> None:
            observed_stdouts.append(sys.stdout)

    def fail_if_writer_used(*_args, **_kwargs):
        raise AssertionError("TrailingNewlineNormalizingWriter should not wrap TUI commands")

    monkeypatch.setattr("cli.interactive_cli.BackendAPI", FakeBackendAPI)
    monkeypatch.setattr("cli.interactive_cli.PnlTUI", FakePnlTUI)
    monkeypatch.setattr("cli.interactive_cli.WatchTUI", FakeWatchTUI)
    monkeypatch.setattr("cli.interactive_cli.TrailingNewlineNormalizingWriter", fail_if_writer_used)
    monkeypatch.setattr(sys, "stdout", tracked_stdout)

    cli = InteractiveCLI(config)
    cli.stdout = tracked_stdout

    cli.onecmd(command)

    assert observed_stdouts == [tracked_stdout]
    assert created_apis[0].calls == expected_calls
    assert tracked_stdout.getvalue() == "\n"
    assert tracked_stdout.flush_count >= 1
