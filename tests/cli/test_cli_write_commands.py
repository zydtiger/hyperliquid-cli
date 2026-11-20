"""Tests for all 5 stateless write CLI subcommands: live, --dry-run, and validation."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Self

import pytest
from typer.testing import CliRunner

import cli.app as app_module
import cli.runtime as runtime_module
from models.api import CoinMetadata, LeverageType, PositionInfo
from models.config import Config
from models.leverage import LeverageResult
from models.margin import IsolatedMarginUpdateResult
from models.order import (
    LimitOrder,
    MarketOrder,
    OrderInfo,
    OrderResult,
    OrderSide,
    OrderStatus,
    OrderTif,
    OrderTrigger,
    OrderType,
    TriggerType,
)

runner = CliRunner()
TEST_ADDRESS = "0x1234567890123456789012345678901234567890"


def _make_order_info(
    order_id: int,
    coin: str = "ETH",
    *,
    status: OrderStatus = OrderStatus.OPEN,
    order_type: OrderType = OrderType.LIMIT,
) -> OrderInfo:
    return OrderInfo(
        order_id=order_id,
        coin=coin,
        side=OrderSide.BUY,
        order_type=order_type,
        quantity=Decimal("1.5"),
        price=Decimal("3000") if order_type == OrderType.LIMIT else None,
        filled_quantity=Decimal("0"),
        remaining_quantity=Decimal("1.5"),
        average_fill_price=None,
        status=status,
        timestamp=1762271507000,
        reduce_only=False,
        time_in_force=OrderTif.GTC if order_type == OrderType.LIMIT else None,
        trigger=None,
    )


def _make_position(
    coin: str = "ETH",
    *,
    leverage_type: LeverageType = LeverageType.ISOLATED,
    leverage: int = 10,
) -> PositionInfo:
    return PositionInfo(
        coin=coin,
        size=Decimal("1.0"),
        entry_price=Decimal("3000"),
        mark_price=Decimal("3100"),
        unrealized_pnl=Decimal("100"),
        leverage=leverage,
        leverage_type=leverage_type,
        margin_used=Decimal("300"),
        removable_margin=Decimal("50") if leverage_type == LeverageType.ISOLATED else None,
        cum_funding=Decimal("0"),
    )


class FakeWriteClient:
    """In-memory HyperliquidClient double that forbids signing in dry-run tests."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.calls: list[tuple[str, Any]] = []
        self.metadata_map: dict[str, CoinMetadata] = {
            "BTC": CoinMetadata(coin="BTC", size_decimals=3, max_leverage=50),
            "ETH": CoinMetadata(coin="ETH", size_decimals=2, max_leverage=25),
        }
        self.orders_by_id: dict[int, OrderInfo] = {
            101: _make_order_info(101, "ETH"),
            102: _make_order_info(102, "BTC"),
            103: _make_order_info(103, "ETH", status=OrderStatus.FILLED),
            104: _make_order_info(104, "ETH", order_type=OrderType.MARKET),
        }
        self.positions: list[PositionInfo] = [
            _make_position("ETH", leverage_type=LeverageType.ISOLATED),
            _make_position("BTC", leverage_type=LeverageType.CROSS),
        ]
        self.fail_next_submit = False

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        return None

    def get_metadata(self, coin: str) -> CoinMetadata:
        self.calls.append(("get_metadata", coin))
        return self.metadata_map[coin]

    def get_order_status(self, order_id: int) -> OrderInfo:
        self.calls.append(("get_order_status", order_id))
        return self.orders_by_id[order_id]

    def get_open_orders(self) -> list[OrderInfo]:
        self.calls.append(("get_open_orders", None))
        return [o for o in self.orders_by_id.values() if o.status == OrderStatus.OPEN]

    def get_positions(self) -> list[PositionInfo]:
        self.calls.append(("get_positions", None))
        return list(self.positions)

    def submit_market_order(self, order: MarketOrder) -> OrderResult:
        self.calls.append(("submit_market_order", order))
        if self.fail_next_submit:
            return OrderResult(
                success=False,
                order_id=None,
                status=OrderStatus.REJECTED,
                message="Rejected",
                error="insufficient margin",
            )
        return OrderResult(
            success=True,
            order_id=5001,
            status=OrderStatus.FILLED,
            message="Market order filled",
        )

    def submit_limit_order(self, order: LimitOrder) -> OrderResult:
        self.calls.append(("submit_limit_order", order))
        return OrderResult(
            success=True,
            order_id=5002,
            status=OrderStatus.OPEN,
            message="Limit order resting",
        )

    def cancel_order(self, order_id: int | str) -> OrderResult:
        self.calls.append(("cancel_order", order_id))
        return OrderResult(
            success=True,
            order_id=order_id if isinstance(order_id, int) else None,
            status=OrderStatus.CANCELLED,
            message=f"Cancelled {order_id}",
        )

    def modify_order(
        self,
        order_id: int,
        price: Decimal | None = None,
        quantity: Decimal | None = None,
    ) -> OrderResult:
        self.calls.append(("modify_order", (order_id, price, quantity)))
        return OrderResult(
            success=True,
            order_id=order_id,
            status=OrderStatus.OPEN,
            message=f"Modified {order_id}",
        )

    def change_leverage(self, leverage: int, coin: str, is_cross: bool = True) -> LeverageResult:
        self.calls.append(("change_leverage", (leverage, coin, is_cross)))
        return LeverageResult(
            success=True,
            message=f"Updated {coin} leverage to {leverage}x",
            updated_position=_make_position(
                coin,
                leverage_type=LeverageType.CROSS if is_cross else LeverageType.ISOLATED,
                leverage=leverage,
            ),
        )

    def update_isolated_margin(self, amount: Decimal, coin: str) -> IsolatedMarginUpdateResult:
        self.calls.append(("update_isolated_margin", (amount, coin)))
        return IsolatedMarginUpdateResult(
            success=True,
            message=f"Updated {coin} margin by {amount}",
            updated_position=_make_position(coin, leverage_type=LeverageType.ISOLATED),
        )


@pytest.fixture
def write_clients(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> list[FakeWriteClient]:
    monkeypatch.setattr(runtime_module, "default_config_path", tmp_path / "absent.yaml")
    created: list[FakeWriteClient] = []

    def _factory(config: Config) -> FakeWriteClient:
        client = FakeWriteClient(config)
        created.append(client)
        return client

    monkeypatch.setattr(runtime_module, "HyperliquidClient", _factory)
    return created


def test_order_dry_run_validates_without_private_key_or_address(
    write_clients: list[FakeWriteClient],
) -> None:
    result = runner.invoke(
        app_module.app,
        [
            "order",
            "buy",
            "btc",
            "0.125",
            "--price",
            "90000",
            "--tif",
            "ALO",
            "--tp",
            "95000",
            "--sl",
            "85000",
            "--dry-run",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["data"]["dry_run"] is True
    assert payload["data"]["order_type"] == "limit"
    assert payload["data"]["order"]["time_in_force"] == "ALO"
    assert len(payload["data"]["trigger_orders"]) == 2
    assert payload["data"]["trigger_orders"][0]["side"] == "sell"
    assert write_clients[0].config.hyperliquid.private_key is None
    assert write_clients[0].calls == [("get_metadata", "BTC")]


def test_order_dry_run_rejects_bad_size_precision(write_clients: list[FakeWriteClient]) -> None:
    result = runner.invoke(
        app_module.app,
        ["order", "buy", "ETH", "0.125", "--dry-run", "--json"],
    )

    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["type"] == "CliValidationError"
    assert "size_decimals=2" in payload["error"]["message"]


def test_order_live_submits_limit_trigger_and_tp_sl(
    write_clients: list[FakeWriteClient],
) -> None:
    result = runner.invoke(
        app_module.app,
        [
            "order",
            "sell",
            "ETH",
            "1.50",
            "--price",
            "3200",
            "--tif",
            "IOC",
            "--reduce-only",
            "--trigger-type",
            "stop",
            "--trigger-price",
            "3150",
            "--tp",
            "2800",
            "--address",
            TEST_ADDRESS,
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["data"]["primary"]["order_id"] == 5002
    assert len(payload["data"]["trigger_results"]) == 1
    assert write_clients[0].calls[0] == (
        "submit_limit_order",
        LimitOrder(
            coin="ETH",
            side=OrderSide.SELL,
            quantity=Decimal("1.50"),
            price=Decimal("3200"),
            reduce_only=True,
            time_in_force=OrderTif.IOC,
            trigger=OrderTrigger(trigger_type=TriggerType.STOP, trigger_price=Decimal("3150")),
        ),
    )
    assert write_clients[0].calls[1][0] == "submit_market_order"
    assert write_clients[0].calls[1][1].side == OrderSide.BUY


@pytest.mark.parametrize(
    "args",
    [
        ["order", "hold", "BTC", "1", "--json"],
        ["order", "buy", "BTC", "0", "--json"],
        ["order", "buy", "BTC", "1", "--tif", "GTC", "--json"],
        ["order", "buy", "BTC", "1", "--trigger-type", "stop", "--json"],
        ["order", "buy", "BTC", "1", "--trigger-price", "100", "--json"],
        ["order", "--json"],
    ],
)
def test_order_validation_errors_exit_two_with_json(args: list[str]) -> None:
    result = runner.invoke(app_module.app, args)

    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["command"] == "order"


def test_cancel_order_dry_run_and_live_all_coin(write_clients: list[FakeWriteClient]) -> None:
    dry_single = runner.invoke(
        app_module.app,
        ["cancel-order", "101", "--dry-run", "--address", TEST_ADDRESS, "--json"],
    )
    assert dry_single.exit_code == 0
    assert json.loads(dry_single.stdout)["data"]["count"] == 1
    assert write_clients[0].calls == [("get_order_status", 101)]

    dry_coin = runner.invoke(
        app_module.app,
        [
            "cancel-order",
            "--all",
            "--coin",
            "btc",
            "--dry-run",
            "--address",
            TEST_ADDRESS,
            "--json",
        ],
    )
    assert dry_coin.exit_code == 0
    dry_coin_data = json.loads(dry_coin.stdout)["data"]
    assert dry_coin_data["count"] == 1
    assert dry_coin_data["would_cancel"][0]["order_id"] == 102

    live_coin = runner.invoke(
        app_module.app,
        ["cancel-order", "--all", "--coin", "btc", "--address", TEST_ADDRESS, "--json"],
    )
    assert live_coin.exit_code == 0
    assert ("cancel_order", 102) in write_clients[2].calls
    assert ("cancel_order", 101) not in write_clients[2].calls

    dry_filled = runner.invoke(
        app_module.app,
        ["cancel-order", "103", "--dry-run", "--address", TEST_ADDRESS, "--json"],
    )
    assert dry_filled.exit_code == 1


@pytest.mark.parametrize(
    "args",
    [
        ["cancel-order", "--json"],
        ["cancel-order", "101", "--all", "--json"],
        ["cancel-order", "101", "--coin", "ETH", "--json"],
        ["cancel-order", "0", "--json"],
    ],
)
def test_cancel_order_validation_errors_exit_two(args: list[str]) -> None:
    result = runner.invoke(app_module.app, args)
    assert result.exit_code == 2
    assert json.loads(result.stdout)["ok"] is False


def test_modify_order_dry_run_and_live(write_clients: list[FakeWriteClient]) -> None:
    dry_res = runner.invoke(
        app_module.app,
        [
            "modify-order",
            "101",
            "--price",
            "3050",
            "--quantity",
            "2.00",
            "--dry-run",
            "--address",
            TEST_ADDRESS,
            "--json",
        ],
    )
    assert dry_res.exit_code == 0
    dry_data = json.loads(dry_res.stdout)["data"]
    assert dry_data["dry_run"] is True
    assert dry_data["new_price"] == "3050"
    assert dry_data["new_quantity"] == "2.00"
    assert write_clients[0].calls == [("get_order_status", 101), ("get_metadata", "ETH")]

    bad_qty = runner.invoke(
        app_module.app,
        [
            "modify-order",
            "101",
            "--quantity",
            "1.123",
            "--dry-run",
            "--address",
            TEST_ADDRESS,
            "--json",
        ],
    )
    assert bad_qty.exit_code == 2

    market_order_res = runner.invoke(
        app_module.app,
        [
            "modify-order",
            "104",
            "--price",
            "3050",
            "--dry-run",
            "--address",
            TEST_ADDRESS,
            "--json",
        ],
    )
    assert market_order_res.exit_code == 1

    live_res = runner.invoke(
        app_module.app,
        ["modify-order", "101", "--price", "3050", "--address", TEST_ADDRESS, "--json"],
    )
    assert live_res.exit_code == 0
    assert write_clients[3].calls == [("modify_order", (101, Decimal("3050"), None))]

    no_changes = runner.invoke(app_module.app, ["modify-order", "101", "--json"])
    assert no_changes.exit_code == 2


def test_change_leverage_dry_run_and_live(write_clients: list[FakeWriteClient]) -> None:
    dry_ok = runner.invoke(
        app_module.app,
        ["change-leverage", "eth", "20", "--isolated", "--dry-run", "--json"],
    )
    assert dry_ok.exit_code == 0
    dry_data = json.loads(dry_ok.stdout)["data"]
    assert dry_data["dry_run"] is True
    assert dry_data["leverage_type"] == "isolated"
    assert dry_data["max_leverage"] == 25
    assert write_clients[0].calls == [("get_metadata", "ETH")]

    dry_too_high = runner.invoke(
        app_module.app,
        ["change-leverage", "ETH", "30", "--dry-run", "--json"],
    )
    assert dry_too_high.exit_code == 2

    live_res = runner.invoke(
        app_module.app,
        ["change-leverage", "ETH", "15", "--address", TEST_ADDRESS, "--json"],
    )
    assert live_res.exit_code == 0
    assert write_clients[2].calls == [("change_leverage", (15, "ETH", True))]


def test_update_margin_negative_amount_dry_run_and_live(
    write_clients: list[FakeWriteClient],
) -> None:
    dry_neg = runner.invoke(
        app_module.app,
        [
            "update-margin",
            "eth",
            "--amount",
            "-0.5",
            "--dry-run",
            "--address",
            TEST_ADDRESS,
            "--json",
        ],
    )
    assert dry_neg.exit_code == 0
    dry_data = json.loads(dry_neg.stdout)["data"]
    assert dry_data["dry_run"] is True
    assert dry_data["amount"] == "-0.5"
    assert dry_data["action"] == "remove"
    assert write_clients[0].calls == [("get_positions", None)]

    live_eq = runner.invoke(
        app_module.app,
        ["update-margin", "ETH", "--amount=-0.5", "--address", TEST_ADDRESS, "--json"],
    )
    assert live_eq.exit_code == 0
    assert write_clients[1].calls == [("update_isolated_margin", (Decimal("-0.5"), "ETH"))]

    dry_cross = runner.invoke(
        app_module.app,
        [
            "update-margin",
            "BTC",
            "--amount",
            "1",
            "--dry-run",
            "--address",
            TEST_ADDRESS,
            "--json",
        ],
    )
    assert dry_cross.exit_code == 1

    bad_zero = runner.invoke(
        app_module.app,
        ["update-margin", "ETH", "--amount", "0", "--json"],
    )
    assert bad_zero.exit_code == 2

    bad_precision = runner.invoke(
        app_module.app,
        ["update-margin", "ETH", "--amount", "0.1234567", "--json"],
    )
    assert bad_precision.exit_code == 2


def test_all_write_commands_human_dry_run_output(write_clients: list[FakeWriteClient]) -> None:
    r1 = runner.invoke(app_module.app, ["order", "buy", "BTC", "0.1", "--dry-run"])
    assert r1.exit_code == 0
    assert "[DRY RUN] Order validated" in r1.stdout

    r2 = runner.invoke(
        app_module.app, ["cancel-order", "--all", "--dry-run", "--address", TEST_ADDRESS]
    )
    assert r2.exit_code == 0
    assert "[DRY RUN] Would cancel" in r2.stdout

    r3 = runner.invoke(
        app_module.app,
        ["modify-order", "101", "--price", "3050", "--dry-run", "--address", TEST_ADDRESS],
    )
    assert r3.exit_code == 0
    assert "[DRY RUN] Order Modification" in r3.stdout

    r4 = runner.invoke(app_module.app, ["change-leverage", "ETH", "10", "--dry-run"])
    assert r4.exit_code == 0
    assert "[DRY RUN] Leverage Update" in r4.stdout

    r5 = runner.invoke(
        app_module.app,
        ["update-margin", "ETH", "--amount", "-0.5", "--dry-run", "--address", TEST_ADDRESS],
    )
    assert r5.exit_code == 0
    assert "[DRY RUN] Isolated Margin Update" in r5.stdout
