"""Tests for interactive coin selection helpers."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from cli.interactive.coin_selector import (
    MAX_COIN_SUGGESTIONS,
    prompt_for_coin_selection,
    rank_coin_matches,
)
from cli.interactive.prompts import Prompts
from models.api import CoinMetadata, Ticker
from models.config import Config, HyperliquidConfig, NetworkType


class FakeCoinPromptSession:
    """Simple prompt session test double."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = iter(responses)

    def prompt(self, message: str) -> str:
        return next(self._responses)


class FailingAPI:
    """API test double that cannot load coins.

    The remaining `MarketDataSource` members fail loudly: these tests only
    exercise coin selection, so reaching them means the test drifted.
    """

    def get_available_coins(self) -> list[str]:
        raise RuntimeError("boom")

    def get_metadata(self, coin: str) -> CoinMetadata:
        raise AssertionError("get_metadata is not part of this test")

    def get_ticker(self, coin: str) -> Ticker:
        raise AssertionError("get_ticker is not part of this test")


class WorkingAPI:
    """API test double that returns configured coins."""

    def __init__(self, coins: list[str]) -> None:
        self._coins = coins

    def get_available_coins(self) -> list[str]:
        return self._coins

    def get_metadata(self, coin: str) -> CoinMetadata:
        raise AssertionError("get_metadata is not part of this test")

    def get_ticker(self, coin: str) -> Ticker:
        raise AssertionError("get_ticker is not part of this test")


@pytest.fixture
def config() -> Config:
    """Create a mock configuration for prompt tests."""
    return Config(
        hyperliquid=HyperliquidConfig(
            account_address="0x1234567890123456789012345678901234567890",
            private_key="0x1234567890123456789012345678901234567890123456789012345678901234",
            network=NetworkType.MAINNET,
        )
    )


def test_prompt_for_coin_selection_accepts_exact_match() -> None:
    """Exact symbol input should return immediately."""

    def session_factory(_coins: Sequence[str]) -> FakeCoinPromptSession:
        return FakeCoinPromptSession(["BTC"])

    assert prompt_for_coin_selection(["BTC", "ETH"], session_factory=session_factory) == "BTC"


def test_prompt_for_coin_selection_normalizes_case() -> None:
    """Mixed-case input should resolve to the canonical exchange symbol."""

    def session_factory(_coins: Sequence[str]) -> FakeCoinPromptSession:
        return FakeCoinPromptSession(["eTh"])

    assert prompt_for_coin_selection(["BTC", "ETH"], session_factory=session_factory) == "ETH"


def test_prompt_for_coin_selection_repompts_on_invalid_input(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Invalid input should show an error and reprompt."""

    def session_factory(_coins: Sequence[str]) -> FakeCoinPromptSession:
        return FakeCoinPromptSession(["zzz", "sol"])

    selected = prompt_for_coin_selection(["BTC", "SOL"], session_factory=session_factory)

    assert selected == "SOL"
    assert "No matching coin selected" in capsys.readouterr().out


def test_rank_coin_matches_limits_results_and_orders_by_match_strength() -> None:
    """Ranked matches should cap output to five and prioritize stronger matches."""
    coins = [
        "BTC",
        "BTCDOM",
        "UBTC",
        "ALTBTC",
        "BCT",
        "TBTCX",
        "BTT",
    ]

    matches = rank_coin_matches("btc", coins)

    assert len(matches) == MAX_COIN_SUGGESTIONS
    assert matches[:2] == ["BTC", "BTCDOM"]
    assert {"UBTC", "ALTBTC", "TBTCX"}.issubset(matches)
    assert "BCT" not in matches


def test_rank_coin_matches_prioritizes_prefix_over_fuzzy_only() -> None:
    """Prefix matches should outrank fuzzy-only alternatives."""
    coins = ["SOL", "MSOL", "SUI", "SEI", "OSOL"]

    matches = rank_coin_matches("so", coins)

    assert matches[0] == "SOL"
    assert matches.index("SOL") < matches.index("MSOL")
    assert matches.index("SOL") < matches.index("SUI")


def test_get_coin_selection_falls_back_when_coin_fetch_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    config: Config,
) -> None:
    """Coin fetch failure should use the manual input fallback."""
    prompts = Prompts(config, FailingAPI())
    inputs = iter(["", "btc"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    assert prompts.get_coin_selection() == "BTC"
    output = capsys.readouterr().out

    assert "Unable to fetch available coins" in output
    assert "Coin symbol is required" in output


def test_get_coin_selection_falls_back_when_selector_errors(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    config: Config,
) -> None:
    """Unexpected selector failures should fall back to manual exact selection."""
    prompts = Prompts(config, WorkingAPI(["BTC", "ETH", "SOL"]))
    monkeypatch.setattr("cli.interactive.prompts.prompt_for_coin_selection", lambda _coins: 1 / 0)
    inputs = iter(["bad", "eth"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    assert prompts.get_coin_selection() == "ETH"
    output = capsys.readouterr().out

    assert "Interactive coin selector unavailable" in output
    assert "'BAD' is not available" in output
