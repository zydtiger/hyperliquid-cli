"""Tests for all stateless read-only CLI subcommands in human and --json modes."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Self

import pytest
from typer.testing import CliRunner

import cli.app as app_module
import cli.commands.account as account_module
import cli.commands.market as market_module
import cli.runtime as runtime_module
from models.api import (
    DEFAULT_PNL_WINDOW,
    BalanceInfo,
    CoinMetadata,
    LeverageType,
    OrderBookLevel,
    PnlHistory,
    PnlHistoryCatalog,
    PnlPoint,
    PositionInfo,
    SpotBalance,
    StakingDelegation,
    StakingInfo,
    StakingStatus,
    Ticker,
    WatchCandle,
    WatchInterval,
    WatchSnapshot,
)
from models.config import Config
from models.order import (
    OrderHistoryEntry,
    OrderInfo,
    OrderSide,
    OrderStatus,
    OrderTif,
    OrderType,
)

runner = CliRunner()
TEST_ADDRESS = "0x1234567890123456789012345678901234567890"


def _sample_position(coin: str = "ETH") -> PositionInfo:
    return PositionInfo(
        coin=coin,
        size=Decimal("0.5"),
        entry_price=Decimal("3000.25"),
        mark_price=Decimal("3100.50"),
        unrealized_pnl=Decimal("50.125"),
        leverage=10,
        leverage_type=LeverageType.CROSS,
        margin_used=Decimal("155.025"),
        removable_margin=None,
        cum_funding=Decimal("-1.25"),
    )


def _sample_balance() -> BalanceInfo:
    return BalanceInfo(
        perps_account_value=Decimal("1000.50"),
        perps_total_position_value=Decimal("1550.25"),
        perps_total_raw_usd=Decimal("845.475"),
        perps_margin_used=Decimal("155.025"),
        perps_withdrawable=Decimal("845.475"),
        spot_balances=[SpotBalance(coin="USDC", total=Decimal("250.123456"))],
        staking_info=StakingInfo(
            delegated_amount=Decimal("10.5"),
            undelegated_amount=Decimal("0"),
            pending_withdrawals=Decimal("0"),
            pending_withdrawal_count=0,
        ),
    )


def _sample_order(order_id: int = 1001, coin: str = "BTC") -> OrderInfo:
    return OrderInfo(
        order_id=order_id,
        coin=coin,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.1"),
        price=Decimal("90000.5"),
        filled_quantity=Decimal("0"),
        remaining_quantity=Decimal("0.1"),
        average_fill_price=None,
        status=OrderStatus.OPEN,
        timestamp=1762271507000,
        reduce_only=False,
        time_in_force=OrderTif.GTC,
        trigger=None,
    )


def _sample_history() -> list[OrderHistoryEntry]:
    return [
        OrderHistoryEntry(
            time=1762271507000,
            coin="ETH",
            direction="Open Long",
            price=Decimal("3000.5"),
            size=Decimal("0.25"),
            notional=Decimal("750.125"),
            fee=Decimal("0.25"),
            fee_usdc=Decimal("0.25"),
            fee_token="USDC",  # noqa: S106
            gross_closed_pnl=Decimal("12.50"),
            closed_pnl=Decimal("12.25"),
            order_id=2001,
            status=OrderStatus.FILLED,
        )
    ]


def _sample_pnl_catalog() -> PnlHistoryCatalog:
    return PnlHistoryCatalog(
        default_window=DEFAULT_PNL_WINDOW,
        histories=[
            PnlHistory(
                window="1d",
                points=[
                    PnlPoint(
                        time=1741973030493,
                        total_pnl=Decimal("15.25"),
                        perp_pnl=Decimal("10.00"),
                        spot_pnl=Decimal("5.25"),
                    )
                ],
            ),
            PnlHistory(
                window="7d",
                points=[
                    PnlPoint(
                        time=1741973030493,
                        total_pnl=Decimal("42.50"),
                        perp_pnl=Decimal("30.00"),
                        spot_pnl=Decimal("12.50"),
                    )
                ],
            ),
        ],
    )


def _sample_watch_snapshot(
    coin: str = "BTC", interval: WatchInterval = "5m", depth: int = 10
) -> WatchSnapshot:
    return WatchSnapshot(
        coin=coin,
        interval=interval,
        mark_price=Decimal("95000.25"),
        open_interest=Decimal("1234567.89"),
        updated_at=1741973030493,
        candles=[
            WatchCandle(
                open_time=1741972800000,
                close_time=1741973100000,
                open=Decimal("94900"),
                high=Decimal("95100"),
                low=Decimal("94850"),
                close=Decimal("95000.25"),
                is_closed=False,
            )
        ],
        bids=[OrderBookLevel(price=Decimal("95000"), size=Decimal("1.5"))],
        asks=[OrderBookLevel(price=Decimal("95001"), size=Decimal("2.0"))],
        size_decimals=5,
        order_book_depth=depth,
    )


def _sample_portfolio_dict() -> dict[str, Any]:
    return {
        "ok": True,
        "as_of": "2026-11-20T14:00:00-05:00",
        "source": {
            "provider": "hyperliquid-cli",
            "network": "mainnet",
            "account_address": TEST_ADDRESS,
            "abstraction_mode": "default",
        },
        "account": {
            "currency": "USD",
            "total_assets": 2500.5,
            "perps": {
                "account_value": 1500.0,
                "total_position_value": 1550.0,
                "total_raw_usd": 1345.0,
                "margin_used": 155.0,
                "cross_maintenance_margin_used": 25.0,
                "withdrawable": 1345.0,
            },
            "spot_total_usd": 500.5,
            "spot_usdc": 250.0,
            "staking_total_usd": 300.0,
            "vaults_total_usd": 200.0,
        },
        "allocation": {"total_assets": 2500.5, "buckets": []},
        "portfolio": [],
        "perp_positions": [
            {
                "coin": "ETH",
                "side": "LONG",
                "size": 0.5,
                "entry_price": 3000.0,
                "mark_price": 3100.0,
                "position_value": 1550.0,
                "margin_used": 155.0,
                "unrealized_pnl": 50.0,
                "leverage": 10,
                "leverage_type": "cross",
                "share_pct": 61.99,
            }
        ],
        "spot_balances": [
            {
                "coin": "USDC",
                "total": 250.0,
                "hold": 0.0,
                "available": 250.0,
                "mark_price": 1.0,
                "market_value": 250.0,
                "share_pct": 10.0,
            }
        ],
        "staking": {
            "delegated": 10.5,
            "undelegated": 0.0,
            "pending_withdrawals": 0.0,
            "pending_withdrawal_count": 0,
            "total_hype": 10.5,
            "total_reward": 0.25,
            "mark_price": 28.57,
            "market_value": 300.0,
            "share_pct": 12.0,
            "delegations": [],
        },
        "vaults": [{"vault_address": "0xvault1", "equity": 200.0, "share_pct": 8.0}],
        "open_orders": [
            {"order_id": 1001, "coin": "BTC", "side": "buy", "quantity": 0.1, "price": 90000.0}
        ],
        "closed_today": [],
        "errors": {
            "spot": None,
            "staking": None,
            "vaults": "vault timeout",
            "open_orders": None,
            "today": None,
            "abstraction": None,
        },
    }


class FakeReadClient:
    """In-memory mock of HyperliquidClient for stateless read commands."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.closed = False
        self.calls: list[tuple[str, Any]] = []

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.closed = True

    def get_portfolio(
        self, *, include_open_orders: bool = True, include_today: bool = True
    ) -> object:
        self.calls.append(("get_portfolio", (include_open_orders, include_today)))

        class _Snapshot:
            def to_json_dict(self) -> dict[str, Any]:
                return _sample_portfolio_dict()

        return _Snapshot()

    def get_balances(self) -> BalanceInfo:
        self.calls.append(("get_balances", None))
        return _sample_balance()

    def get_positions(self) -> list[PositionInfo]:
        self.calls.append(("get_positions", None))
        return [_sample_position("ETH"), _sample_position("BTC")]

    def get_staking_status(self) -> StakingStatus:
        self.calls.append(("get_staking_status", None))
        return StakingStatus(
            total_staked=Decimal("100.5"),
            total_reward=Decimal("2.25"),
            delegations=[
                StakingDelegation(
                    validator="val-1",
                    name="Validator One",
                    commission=Decimal("0.05"),
                    amount=Decimal("100.5"),
                )
            ],
        )

    def get_open_orders(self) -> list[OrderInfo]:
        self.calls.append(("get_open_orders", None))
        return [_sample_order(1001, "BTC"), _sample_order(1002, "ETH")]

    def get_order_status(self, order_id: int) -> OrderInfo:
        self.calls.append(("get_order_status", order_id))
        return _sample_order(order_id, "BTC")

    def get_order_history(self, limit: int, since_ms: int | None = None) -> list[OrderHistoryEntry]:
        self.calls.append(("get_order_history", (limit, since_ms)))
        return _sample_history()

    def get_pnl_history(self) -> PnlHistoryCatalog:
        self.calls.append(("get_pnl_history", None))
        return _sample_pnl_catalog()

    def get_available_coins(self, market_type: str = "all") -> list[str]:
        self.calls.append(("get_available_coins", market_type))
        if market_type == "spot":
            return ["UBTC/USDC", "HYPE/USDC"]
        if market_type == "perp":
            return ["BTC", "ETH"]
        return ["BTC", "ETH", "UBTC/USDC"]

    def get_ticker(self, coin: str) -> Ticker:
        self.calls.append(("get_ticker", coin))
        return Ticker(
            coin=coin,
            mark_price=Decimal("95000.25"),
            funding_rate=Decimal("0.0001"),
            open_interest=Decimal("1234567.89"),
        )

    def get_metadata(self, coin: str) -> CoinMetadata:
        self.calls.append(("get_metadata", coin))
        return CoinMetadata(coin=coin, size_decimals=4, max_leverage=50)

    def get_watch_snapshot_once(
        self, coin: str, interval: WatchInterval = "5m", depth: int = 10
    ) -> WatchSnapshot:
        self.calls.append(("get_watch_snapshot_once", (coin, interval, depth)))
        return _sample_watch_snapshot(coin, interval, depth)

    def get_watch_snapshot(
        self, coin: str, interval: WatchInterval = "5m", depth: int = 10
    ) -> WatchSnapshot:
        self.calls.append(("get_watch_snapshot", (coin, interval, depth)))
        return _sample_watch_snapshot(coin, interval, depth)


@pytest.fixture
def fake_clients(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> list[FakeReadClient]:
    monkeypatch.setattr(runtime_module, "default_config_path", tmp_path / "absent.yaml")
    created: list[FakeReadClient] = []

    def _factory(config: Config) -> FakeReadClient:
        client = FakeReadClient(config)
        created.append(client)
        return client

    monkeypatch.setattr(runtime_module, "HyperliquidClient", _factory)
    return created


def test_portfolio_json_emits_snapshot_dict_directly_and_forwards_flags(
    fake_clients: list[FakeReadClient],
) -> None:
    result = runner.invoke(
        app_module.app,
        [
            "portfolio",
            "--address",
            TEST_ADDRESS,
            "--no-open-orders",
            "--no-today",
            "--json",
        ],
    )

    assert result.exit_code == 0
    lines = result.stdout.strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["ok"] is True
    assert payload["account"]["total_assets"] == 2500.5
    assert "data" not in payload
    assert fake_clients[0].calls == [("get_portfolio", (False, False))]
    assert fake_clients[0].closed is True


def test_portfolio_human_renders_tables(fake_clients: list[FakeReadClient]) -> None:
    result = runner.invoke(app_module.app, ["portfolio", "--address", TEST_ADDRESS])

    assert result.exit_code == 0
    assert "Portfolio Summary" in result.stdout
    assert "$2,500.50" in result.stdout
    assert "Perp Positions (1)" in result.stdout
    assert "Spot Balances (1)" in result.stdout
    assert "Staking" in result.stdout
    assert "$300.00" in result.stdout
    assert "Vaults (1)" in result.stdout
    assert "0xvault1" in result.stdout
    assert "Errors (1)" in result.stdout
    assert "vault timeout" in result.stdout


def test_portfolio_requires_address_and_emits_json_error(
    fake_clients: list[FakeReadClient],
) -> None:
    result = runner.invoke(app_module.app, ["--json", "portfolio"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["command"] == "portfolio"
    assert payload["error"]["type"] == "ConfigurationError"
    assert fake_clients == []


def test_balances_json_before_and_after_subcommand(fake_clients: list[FakeReadClient]) -> None:
    res_after = runner.invoke(app_module.app, ["balances", "--address", TEST_ADDRESS, "--json"])
    res_before = runner.invoke(app_module.app, ["--json", "--address", TEST_ADDRESS, "balances"])

    for result in (res_after, res_before):
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["command"] == "balances"
        assert payload["data"]["perps_account_value"] == "1000.50"
        assert payload["data"]["spot_balances"][0]["total"] == "250.123456"


def test_positions_all_filtered_and_not_found(fake_clients: list[FakeReadClient]) -> None:
    all_res = runner.invoke(app_module.app, ["positions", "--address", TEST_ADDRESS, "--json"])
    assert all_res.exit_code == 0
    assert len(json.loads(all_res.stdout)["data"]) == 2

    one_res = runner.invoke(
        app_module.app, ["positions", "eth", "--address", TEST_ADDRESS, "--json"]
    )
    assert one_res.exit_code == 0
    one_data = json.loads(one_res.stdout)["data"]
    assert len(one_data) == 1
    assert one_data[0]["coin"] == "ETH"
    assert one_data[0]["unrealized_pnl"] == "50.125"

    missing_res = runner.invoke(
        app_module.app, ["positions", "DOGE", "--address", TEST_ADDRESS, "--json"]
    )
    assert missing_res.exit_code == 1
    err = json.loads(missing_res.stdout)
    assert err["ok"] is False
    assert err["error"]["type"] == "ExchangeError"
    assert "DOGE" in err["error"]["message"]


def test_staking_human_and_json(fake_clients: list[FakeReadClient]) -> None:
    human = runner.invoke(app_module.app, ["staking", "--address", TEST_ADDRESS])
    assert human.exit_code == 0
    assert "Staking Summary" in human.stdout

    as_json = runner.invoke(app_module.app, ["--json", "staking", "--address", TEST_ADDRESS])
    assert as_json.exit_code == 0
    payload = json.loads(as_json.stdout)
    assert payload["data"]["total_staked"] == "100.5"
    assert payload["data"]["delegations"][0]["name"] == "Validator One"


def test_open_orders_filters_case_insensitively(fake_clients: list[FakeReadClient]) -> None:
    result = runner.invoke(
        app_module.app,
        ["open-orders", "--coin", "eth", "--address", TEST_ADDRESS, "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert [o["order_id"] for o in payload["data"]] == [1002]


def test_order_status_valid_and_invalid_id(fake_clients: list[FakeReadClient]) -> None:
    ok_res = runner.invoke(
        app_module.app, ["order-status", "1001", "--address", TEST_ADDRESS, "--json"]
    )
    assert ok_res.exit_code == 0
    assert json.loads(ok_res.stdout)["data"]["order_id"] == 1001

    bad_res = runner.invoke(
        app_module.app, ["order-status", "0", "--address", TEST_ADDRESS, "--json"]
    )
    assert bad_res.exit_code == 2
    err = json.loads(bad_res.stdout)
    assert err["ok"] is False
    assert err["error"]["type"] == "CliValidationError"


def test_order_history_parses_since_ms_and_iso_and_rejects_bad_since(
    fake_clients: list[FakeReadClient],
) -> None:
    ms_res = runner.invoke(
        app_module.app,
        [
            "order-history",
            "--limit",
            "5",
            "--since",
            "1762271500000",
            "--address",
            TEST_ADDRESS,
            "--json",
        ],
    )
    assert ms_res.exit_code == 0
    assert fake_clients[0].calls == [("get_order_history", (5, 1762271500000))]

    iso_str = "2026-11-20T12:00:00Z"
    expected_ms = int(datetime(2026, 11, 20, 12, 0, 0, tzinfo=UTC).timestamp() * 1000)
    iso_res = runner.invoke(
        app_module.app,
        [
            "order-history",
            "--since",
            iso_str,
            "--address",
            TEST_ADDRESS,
            "--json",
        ],
    )
    assert iso_res.exit_code == 0
    assert fake_clients[1].calls == [("get_order_history", (10, expected_ms))]

    bad_res = runner.invoke(
        app_module.app,
        ["order-history", "--since", "not-a-timestamp", "--json"],
    )
    assert bad_res.exit_code == 2
    assert json.loads(bad_res.stdout)["error"]["type"] == "CliValidationError"


def test_pnl_json_summary_and_tty_tui(
    fake_clients: list[FakeReadClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    full_json = runner.invoke(app_module.app, ["pnl", "--address", TEST_ADDRESS, "--json"])
    assert full_json.exit_code == 0
    assert json.loads(full_json.stdout)["data"]["default_window"] == "7d"

    win_json = runner.invoke(
        app_module.app, ["pnl", "--window", "7d", "--address", TEST_ADDRESS, "--json"]
    )
    assert win_json.exit_code == 0
    win_data = json.loads(win_json.stdout)["data"]
    assert win_data["window"] == "7d"
    assert win_data["points"][0]["total_pnl"] == "42.50"

    table_res = runner.invoke(app_module.app, ["pnl", "--window", "7d", "--address", TEST_ADDRESS])
    assert table_res.exit_code == 0
    assert "PnL Summary (7D)" in table_res.stdout
    assert "$+42.50" in table_res.stdout

    launched: list[object] = []

    class FakePnlTUI:
        def __init__(self, catalog: PnlHistoryCatalog) -> None:
            launched.append(catalog)

        def run(self) -> None:
            launched.append("ran")

    monkeypatch.setattr(account_module, "PnlTUI", FakePnlTUI)
    monkeypatch.setattr(account_module, "_is_interactive_tty", lambda: False)

    non_tty_res = runner.invoke(app_module.app, ["pnl", "--address", TEST_ADDRESS])
    assert non_tty_res.exit_code == 0
    assert "PnL Summary" in non_tty_res.stdout
    assert launched == []

    monkeypatch.setattr(account_module, "_is_interactive_tty", lambda: True)

    tui_res = runner.invoke(app_module.app, ["pnl", "--address", TEST_ADDRESS])
    assert tui_res.exit_code == 0
    assert launched[1] == "ran"

    bad_res = runner.invoke(app_module.app, ["pnl", "--window", "99y", "--json"])
    assert bad_res.exit_code == 2


def test_coins_and_info_are_public_read_only(fake_clients: list[FakeReadClient]) -> None:
    coins_res = runner.invoke(app_module.app, ["coins", "--type", "spot", "--json"])
    assert coins_res.exit_code == 0
    assert json.loads(coins_res.stdout)["data"] == ["UBTC/USDC", "HYPE/USDC"]
    assert fake_clients[0].calls == [("get_available_coins", "spot")]

    bad_type = runner.invoke(app_module.app, ["coins", "--type", "futures", "--json"])
    assert bad_type.exit_code == 2

    info_res = runner.invoke(app_module.app, ["info", "btc", "--json"])
    assert info_res.exit_code == 0
    info_data = json.loads(info_res.stdout)["data"]
    assert info_data["coin"] == "BTC"
    assert info_data["ticker"]["mark_price"] == "95000.25"
    assert info_data["metadata"]["max_leverage"] == 50

    info_human = runner.invoke(app_module.app, ["info", "BTC"])
    assert info_human.exit_code == 0
    assert "BTC Ticker Information" in info_human.stdout
    assert "BTC Metadata" in info_human.stdout


def test_watch_json_oneshot_and_human_tui(
    fake_clients: list[FakeReadClient],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    json_res = runner.invoke(
        app_module.app,
        ["watch", "btc", "--interval", "1h", "--depth", "20", "--json"],
    )
    assert json_res.exit_code == 0
    payload = json.loads(json_res.stdout)
    assert payload["data"]["coin"] == "BTC"
    assert payload["data"]["interval"] == "1h"
    assert payload["data"]["order_book_depth"] == 20
    assert fake_clients[0].calls == [("get_watch_snapshot_once", ("BTC", "1h", 20))]

    launched: list[tuple[str, str, int]] = []

    class FakeWatchTUI:
        def __init__(
            self,
            coin: str,
            _fetcher: Any,
            *,
            initial_interval: str = "5m",
            initial_depth: int = 10,
        ) -> None:
            launched.append((coin, initial_interval, initial_depth))

        def run(self) -> None:
            return None

    monkeypatch.setattr(market_module, "WatchTUI", FakeWatchTUI)

    tui_res = runner.invoke(app_module.app, ["watch", "eth", "--interval", "15m", "--depth", "12"])
    assert tui_res.exit_code == 0
    assert launched == [("ETH", "15m", 12)]
    assert fake_clients[1].calls == [("get_watch_snapshot", ("ETH", "15m", 12))]
    assert fake_clients[1].closed is True

    bad_depth = runner.invoke(app_module.app, ["watch", "BTC", "--depth", "99", "--json"])
    assert bad_depth.exit_code == 2
