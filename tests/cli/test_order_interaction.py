from decimal import Decimal
from unittest.mock import Mock, call, patch

import pytest

from cli.api import BackendAPI
from cli.formatters.order_formatter import OrderFormatter
from cli.interactive.order_wizard import OrderWizard
from cli.interactive.prompts import Prompts
from cli.interactive_cli import InteractiveCLI
from models import (
    Config,
    HyperliquidConfig,
    LimitOrder,
    MarketOrder,
    NetworkType,
    OrderInfo,
    OrderResult,
    OrderSide,
    OrderStatus,
    OrderTif,
    OrderTrigger,
    OrderType,
    TriggerType,
)


class FakeAPI(BackendAPI):
    def __init__(self) -> None:
        """Avoid real BackendAPI setup in tests."""

    def get_available_coins(self) -> list[str]:
        return ["BTC", "ETH", "SOL"]

    def get_ticker(self, coin: str) -> Mock:
        return Mock(mark_price=Decimal("100000") if coin == "BTC" else Decimal("3000"))

    def get_metadata(self, coin: str) -> Mock:
        return Mock(size_decimals=3)


def make_config() -> Config:
    return Config(
        hyperliquid=HyperliquidConfig(
            account_address="0x1234567890123456789012345678901234567890",
            private_key="0x1234567890123456789012345678901234567890123456789012345678901234",
            network=NetworkType.MAINNET,
        )
    )


def make_order_result(
    order_id: int | None,
    *,
    success: bool = True,
    status: OrderStatus = OrderStatus.OPEN,
    message: str = "submitted",
    error: str | None = None,
) -> OrderResult:
    return OrderResult(
        success=success,
        order_id=order_id,
        status=status,
        message=message,
        error=error,
    )


def make_order_info(
    order_id: int,
    *,
    coin: str,
    side: OrderSide,
    order_type: OrderType,
    quantity: Decimal,
    price: Decimal | None,
    status: OrderStatus,
    reduce_only: bool,
    trigger: OrderTrigger | None = None,
    time_in_force: OrderTif | None = None,
) -> OrderInfo:
    return OrderInfo(
        order_id=order_id,
        coin=coin,
        side=side,
        order_type=order_type,
        quantity=quantity,
        price=price,
        filled_quantity=Decimal("0"),
        remaining_quantity=quantity,
        average_fill_price=None,
        status=status,
        timestamp=1,
        reduce_only=reduce_only,
        time_in_force=time_in_force,
        trigger=trigger,
    )


def test_market_order_wizard_without_trigger(monkeypatch) -> None:
    wizard = OrderWizard(make_config(), FakeAPI())
    responses = iter(["BTC", "1", "1", "0.123", "n", "", "y"])
    monkeypatch.setattr("builtins.input", lambda _: next(responses))

    order = wizard.run()

    assert isinstance(order, MarketOrder)
    assert order.side == OrderSide.BUY
    assert order.quantity == Decimal("0.123")
    assert order.reduce_only is False
    assert order.trigger is None


def test_market_order_wizard_with_stop_trigger(monkeypatch) -> None:
    wizard = OrderWizard(make_config(), FakeAPI())
    responses = iter(["BTC", "1", "1", "0.123", "n", "y", "1", "101000", "y"])
    monkeypatch.setattr("builtins.input", lambda _: next(responses))

    order = wizard.run()

    assert isinstance(order, MarketOrder)
    assert order.trigger == OrderTrigger(
        trigger_type=TriggerType.STOP, trigger_price=Decimal("101000")
    )


def test_limit_order_wizard_with_take_trigger(monkeypatch) -> None:
    wizard = OrderWizard(make_config(), FakeAPI())
    responses = iter(["ETH", "2", "2", "3200", "", "1.500", "n", "y", "2", "3500", "y"])
    monkeypatch.setattr("builtins.input", lambda _: next(responses))

    order = wizard.run()

    assert isinstance(order, LimitOrder)
    assert order.side == OrderSide.SELL
    assert order.price == Decimal("3200")
    assert order.time_in_force == OrderTif.GTC
    assert order.trigger == OrderTrigger(
        trigger_type=TriggerType.TAKE, trigger_price=Decimal("3500")
    )


def test_trigger_type_prompt_retries_on_invalid_choice(monkeypatch, capsys) -> None:
    prompts = Prompts(make_config(), FakeAPI())
    responses = iter(["3", "2"])
    monkeypatch.setattr("builtins.input", lambda _: next(responses))

    trigger_type = prompts.get_trigger_type_selection()

    assert trigger_type == TriggerType.TAKE
    assert "Please enter 1 (Stop) or 2 (Take)" in capsys.readouterr().out


def test_trigger_price_prompt_retries_on_invalid_input(monkeypatch, capsys) -> None:
    prompts = Prompts(make_config(), FakeAPI())
    responses = iter(["abc", "0", "123.45"])
    monkeypatch.setattr("builtins.input", lambda _: next(responses))

    trigger_price = prompts.get_trigger_price_input("BTC")

    assert trigger_price == Decimal("123.45")
    output = capsys.readouterr().out
    assert "Please enter a valid number" in output
    assert "Trigger price must be greater than 0" in output


def test_order_formatter_includes_trigger_details() -> None:
    order = LimitOrder(
        coin="ETH",
        side=OrderSide.SELL,
        quantity=Decimal("1.5"),
        price=Decimal("3200"),
        time_in_force=OrderTif.GTC,
        reduce_only=True,
        trigger=OrderTrigger(trigger_type=TriggerType.TAKE, trigger_price=Decimal("3500")),
    )

    output = OrderFormatter().format(order)

    assert "Trigger     : Yes" in output
    assert "Trigger Type: TAKE" in output
    assert "Trigger Px  : $3500" in output


def test_open_orders_formatter_shows_trigger_columns_only_when_needed() -> None:
    orders = [
        OrderInfo(
            order_id=1,
            coin="ETH",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.005"),
            price=Decimal("2094.7"),
            filled_quantity=Decimal("0.0"),
            remaining_quantity=Decimal("0.005"),
            average_fill_price=None,
            status=OrderStatus.OPEN,
            timestamp=1,
            reduce_only=False,
            time_in_force=OrderTif.GTC,
            trigger=None,
        ),
        OrderInfo(
            order_id=2,
            coin="DOGE",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=Decimal("30000.0"),
            price=Decimal("0.099141"),
            filled_quantity=Decimal("0.0"),
            remaining_quantity=Decimal("30000.0"),
            average_fill_price=None,
            status=OrderStatus.OPEN,
            timestamp=2,
            reduce_only=False,
            time_in_force=OrderTif.GTC,
            trigger=OrderTrigger(
                trigger_type=TriggerType.TAKE,
                trigger_price=Decimal("0.1"),
            ),
        ),
    ]

    output = OrderFormatter().format(orders)

    assert "Trigger Type" in output
    assert "Trigger Px" in output
    assert "TAKE" in output
    assert "$0.1" in output
    assert "N/A" not in output


def test_open_orders_formatter_omits_trigger_columns_when_absent() -> None:
    orders = [
        OrderInfo(
            order_id=1,
            coin="ETH",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.005"),
            price=Decimal("2094.7"),
            filled_quantity=Decimal("0.0"),
            remaining_quantity=Decimal("0.005"),
            average_fill_price=None,
            status=OrderStatus.OPEN,
            timestamp=1,
            reduce_only=False,
            time_in_force=None,
            trigger=None,
        )
    ]

    output = OrderFormatter().format(orders)

    assert "Trigger Type" not in output
    assert "Trigger Px" not in output
    assert "Market" not in output


def test_parse_quick_market_order_without_triggers() -> None:
    cli = InteractiveCLI(make_config())

    order, trigger_orders = cli._parse_quick_order("buy eth 0.25")

    assert order == MarketOrder(
        coin="ETH",
        side=OrderSide.BUY,
        quantity=Decimal("0.25"),
        reduce_only=False,
    )
    assert trigger_orders == []


def test_parse_quick_limit_order_without_triggers() -> None:
    cli = InteractiveCLI(make_config())

    order, trigger_orders = cli._parse_quick_order("sell btc 0.01@105000")

    assert order == LimitOrder(
        coin="BTC",
        side=OrderSide.SELL,
        quantity=Decimal("0.01"),
        price=Decimal("105000"),
        reduce_only=False,
        time_in_force=OrderTif.GTC,
    )
    assert trigger_orders == []


def test_parse_quick_order_with_take_profit_only() -> None:
    cli = InteractiveCLI(make_config())

    order, trigger_orders = cli._parse_quick_order("buy btc 2@75000 --tp 80000")

    assert order == LimitOrder(
        coin="BTC",
        side=OrderSide.BUY,
        quantity=Decimal("2"),
        price=Decimal("75000"),
        reduce_only=False,
        time_in_force=OrderTif.GTC,
    )
    assert trigger_orders == [
        (
            "Take Profit Order",
            MarketOrder(
                coin="BTC",
                side=OrderSide.SELL,
                quantity=Decimal("2"),
                reduce_only=True,
                trigger=OrderTrigger(
                    trigger_type=TriggerType.TAKE,
                    trigger_price=Decimal("80000"),
                ),
            ),
        )
    ]


def test_parse_quick_order_with_stop_loss_only() -> None:
    cli = InteractiveCLI(make_config())

    order, trigger_orders = cli._parse_quick_order("sell eth 1 --sl 3200")

    assert order == MarketOrder(
        coin="ETH",
        side=OrderSide.SELL,
        quantity=Decimal("1"),
        reduce_only=False,
    )
    assert trigger_orders == [
        (
            "Stop Loss Order",
            MarketOrder(
                coin="ETH",
                side=OrderSide.BUY,
                quantity=Decimal("1"),
                reduce_only=True,
                trigger=OrderTrigger(
                    trigger_type=TriggerType.STOP,
                    trigger_price=Decimal("3200"),
                ),
            ),
        )
    ]


def test_parse_quick_order_accepts_flags_in_any_order() -> None:
    cli = InteractiveCLI(make_config())

    _, trigger_orders = cli._parse_quick_order("buy btc 2@75000 --sl 60000 --tp 80000")

    assert trigger_orders == [
        (
            "Take Profit Order",
            MarketOrder(
                coin="BTC",
                side=OrderSide.SELL,
                quantity=Decimal("2"),
                reduce_only=True,
                trigger=OrderTrigger(
                    trigger_type=TriggerType.TAKE,
                    trigger_price=Decimal("80000"),
                ),
            ),
        ),
        (
            "Stop Loss Order",
            MarketOrder(
                coin="BTC",
                side=OrderSide.SELL,
                quantity=Decimal("2"),
                reduce_only=True,
                trigger=OrderTrigger(
                    trigger_type=TriggerType.STOP,
                    trigger_price=Decimal("60000"),
                ),
            ),
        ),
    ]


@pytest.mark.parametrize(
    ("args", "error_message"),
    [
        ("buy btc 2 --tp 0", "Take-profit price must be greater than 0"),
        ("buy btc 2 --sl abc", "Stop-loss price must be a valid decimal value"),
        ("buy btc 2 --tp 1 --tp 2", "Duplicate quick-order flag: --tp"),
        ("buy btc 2 --sl 1 --sl 2", "Duplicate quick-order flag: --sl"),
        ("buy btc 2 --foo 1", "Unknown quick-order flag: --foo"),
        ("buy btc 2 --tp", "--tp requires a price value"),
        ("buy btc 2 --sl --tp 1", "--sl requires a price value"),
    ],
)
def test_parse_quick_order_rejects_invalid_trigger_flags(args: str, error_message: str) -> None:
    cli = InteractiveCLI(make_config())

    with pytest.raises(ValueError, match=error_message):
        cli._parse_quick_order(args)


def test_do_order_submits_non_trigger_limit_order(capsys) -> None:
    config = make_config()
    cli = InteractiveCLI(config)
    api = Mock()
    api.submit_limit_order.return_value = Mock()
    wizard = Mock()
    wizard.run.return_value = LimitOrder(
        coin="ETH",
        side=OrderSide.BUY,
        quantity=Decimal("1"),
        price=Decimal("3000"),
        time_in_force=OrderTif.GTC,
        reduce_only=False,
    )

    backend_api = Mock()
    backend_api.__enter__ = Mock(return_value=api)
    backend_api.__exit__ = Mock(return_value=None)

    with (
        patch("cli.interactive_cli.BackendAPI", return_value=backend_api),
        patch("cli.interactive_cli.OrderWizard", return_value=wizard),
        patch("cli.interactive_cli.OrderFormatter.format", return_value="formatted"),
    ):
        cli.do_order("")

    api.submit_limit_order.assert_called_once()
    api.submit_market_order.assert_not_called()
    assert "formatted" in capsys.readouterr().out


def test_do_order_submits_trigger_market_order(capsys) -> None:
    config = make_config()
    cli = InteractiveCLI(config)
    api = Mock()
    api.submit_market_order.return_value = Mock()
    wizard = Mock()
    wizard.run.return_value = MarketOrder(
        coin="BTC",
        side=OrderSide.BUY,
        quantity=Decimal("0.1"),
        reduce_only=False,
        trigger=OrderTrigger(trigger_type=TriggerType.STOP, trigger_price=Decimal("101000")),
    )

    backend_api = Mock()
    backend_api.__enter__ = Mock(return_value=api)
    backend_api.__exit__ = Mock(return_value=None)

    with (
        patch("cli.interactive_cli.BackendAPI", return_value=backend_api),
        patch("cli.interactive_cli.OrderWizard", return_value=wizard),
        patch("cli.interactive_cli.OrderFormatter.format", return_value="formatted"),
    ):
        cli.do_order("")

    api.submit_limit_order.assert_not_called()
    api.submit_market_order.assert_called_once()
    assert "formatted" in capsys.readouterr().out


def test_do_order_submits_quick_market_order(capsys) -> None:
    config = make_config()
    cli = InteractiveCLI(config)
    api = Mock()
    api.submit_market_order.return_value = Mock()

    backend_api = Mock()
    backend_api.__enter__ = Mock(return_value=api)
    backend_api.__exit__ = Mock(return_value=None)

    with (
        patch("cli.interactive_cli.BackendAPI", return_value=backend_api),
        patch("cli.interactive_cli.OrderFormatter.format", return_value="formatted"),
    ):
        cli.do_order("buy eth 0.25")

    api.submit_limit_order.assert_not_called()
    api.submit_market_order.assert_called_once_with(
        MarketOrder(
            coin="ETH",
            side=OrderSide.BUY,
            quantity=Decimal("0.25"),
            reduce_only=False,
        )
    )
    assert "formatted" in capsys.readouterr().out


def test_do_order_submits_quick_limit_order(capsys) -> None:
    config = make_config()
    cli = InteractiveCLI(config)
    api = Mock()
    api.submit_limit_order.return_value = Mock()

    backend_api = Mock()
    backend_api.__enter__ = Mock(return_value=api)
    backend_api.__exit__ = Mock(return_value=None)

    with (
        patch("cli.interactive_cli.BackendAPI", return_value=backend_api),
        patch("cli.interactive_cli.OrderFormatter.format", return_value="formatted"),
    ):
        cli.do_order("sell btc 0.01@105000")

    api.submit_market_order.assert_not_called()
    api.submit_limit_order.assert_called_once_with(
        LimitOrder(
            coin="BTC",
            side=OrderSide.SELL,
            quantity=Decimal("0.01"),
            price=Decimal("105000"),
            reduce_only=False,
            time_in_force=OrderTif.GTC,
        )
    )
    assert "formatted" in capsys.readouterr().out


def test_do_order_submits_quick_limit_order_with_tp_and_sl_and_displays_statuses(capsys) -> None:
    config = make_config()
    cli = InteractiveCLI(config)
    api = Mock()
    api.submit_limit_order.return_value = make_order_result(101, message="primary accepted")
    api.submit_market_order.side_effect = [
        make_order_result(102, message="tp accepted"),
        make_order_result(103, message="sl accepted"),
    ]
    api.get_order_status.side_effect = [
        make_order_info(
            101,
            coin="BTC",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("2"),
            price=Decimal("75000"),
            status=OrderStatus.OPEN,
            reduce_only=False,
            time_in_force=OrderTif.GTC,
        ),
        make_order_info(
            102,
            coin="BTC",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=Decimal("2"),
            price=None,
            status=OrderStatus.OPEN,
            reduce_only=True,
            trigger=OrderTrigger(
                trigger_type=TriggerType.TAKE,
                trigger_price=Decimal("80000"),
            ),
        ),
        make_order_info(
            103,
            coin="BTC",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=Decimal("2"),
            price=None,
            status=OrderStatus.OPEN,
            reduce_only=True,
            trigger=OrderTrigger(
                trigger_type=TriggerType.STOP,
                trigger_price=Decimal("60000"),
            ),
        ),
    ]

    backend_api = Mock()
    backend_api.__enter__ = Mock(return_value=api)
    backend_api.__exit__ = Mock(return_value=None)

    with patch("cli.interactive_cli.BackendAPI", return_value=backend_api):
        cli.do_order("buy btc 2@75000 --tp 80000 --sl 60000")

    api.submit_limit_order.assert_called_once_with(
        LimitOrder(
            coin="BTC",
            side=OrderSide.BUY,
            quantity=Decimal("2"),
            price=Decimal("75000"),
            reduce_only=False,
            time_in_force=OrderTif.GTC,
        )
    )
    assert api.submit_market_order.call_args_list == [
        call(
            MarketOrder(
                coin="BTC",
                side=OrderSide.SELL,
                quantity=Decimal("2"),
                reduce_only=True,
                trigger=OrderTrigger(
                    trigger_type=TriggerType.TAKE,
                    trigger_price=Decimal("80000"),
                ),
            )
        ),
        call(
            MarketOrder(
                coin="BTC",
                side=OrderSide.SELL,
                quantity=Decimal("2"),
                reduce_only=True,
                trigger=OrderTrigger(
                    trigger_type=TriggerType.STOP,
                    trigger_price=Decimal("60000"),
                ),
            )
        ),
    ]
    assert api.get_order_status.call_args_list == [call(101), call(102), call(103)]

    output = capsys.readouterr().out
    assert "Submitted Orders (3)" in output
    assert "TAKE" in output
    assert "STOP" in output


def test_do_order_submits_quick_sell_order_tp_sl_children_as_buy_reduce_only(capsys) -> None:
    config = make_config()
    cli = InteractiveCLI(config)
    api = Mock()
    api.submit_market_order.side_effect = [
        make_order_result(201, message="primary accepted"),
        make_order_result(202, message="tp accepted"),
        make_order_result(203, message="sl accepted"),
    ]
    api.get_order_status.side_effect = [
        make_order_info(
            201,
            coin="ETH",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=Decimal("1"),
            price=None,
            status=OrderStatus.OPEN,
            reduce_only=False,
        ),
        make_order_info(
            202,
            coin="ETH",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("1"),
            price=None,
            status=OrderStatus.OPEN,
            reduce_only=True,
            trigger=OrderTrigger(
                trigger_type=TriggerType.TAKE,
                trigger_price=Decimal("2500"),
            ),
        ),
        make_order_info(
            203,
            coin="ETH",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("1"),
            price=None,
            status=OrderStatus.OPEN,
            reduce_only=True,
            trigger=OrderTrigger(
                trigger_type=TriggerType.STOP,
                trigger_price=Decimal("3200"),
            ),
        ),
    ]

    backend_api = Mock()
    backend_api.__enter__ = Mock(return_value=api)
    backend_api.__exit__ = Mock(return_value=None)

    with patch("cli.interactive_cli.BackendAPI", return_value=backend_api):
        cli.do_order("sell eth 1 --tp 2500 --sl 3200")

    assert api.submit_market_order.call_args_list == [
        call(
            MarketOrder(
                coin="ETH",
                side=OrderSide.SELL,
                quantity=Decimal("1"),
                reduce_only=False,
            )
        ),
        call(
            MarketOrder(
                coin="ETH",
                side=OrderSide.BUY,
                quantity=Decimal("1"),
                reduce_only=True,
                trigger=OrderTrigger(
                    trigger_type=TriggerType.TAKE,
                    trigger_price=Decimal("2500"),
                ),
            )
        ),
        call(
            MarketOrder(
                coin="ETH",
                side=OrderSide.BUY,
                quantity=Decimal("1"),
                reduce_only=True,
                trigger=OrderTrigger(
                    trigger_type=TriggerType.STOP,
                    trigger_price=Decimal("3200"),
                ),
            )
        ),
    ]
    assert "Submitted Orders (3)" in capsys.readouterr().out


def test_do_order_does_not_submit_child_triggers_when_primary_quick_order_fails(capsys) -> None:
    config = make_config()
    cli = InteractiveCLI(config)
    api = Mock()
    api.submit_limit_order.return_value = make_order_result(
        None,
        success=False,
        status=OrderStatus.REJECTED,
        message="Limit order failed",
        error="insufficient margin",
    )

    backend_api = Mock()
    backend_api.__enter__ = Mock(return_value=api)
    backend_api.__exit__ = Mock(return_value=None)

    with patch("cli.interactive_cli.BackendAPI", return_value=backend_api):
        cli.do_order("buy btc 2@75000 --tp 80000 --sl 60000")

    api.submit_limit_order.assert_called_once()
    api.submit_market_order.assert_not_called()
    api.get_order_status.assert_not_called()
    output = capsys.readouterr().out
    assert "Limit order failed" in output
    assert "Submitted Orders" not in output


def test_do_order_reports_partial_trigger_failures_and_continues(capsys) -> None:
    config = make_config()
    cli = InteractiveCLI(config)
    api = Mock()
    api.submit_market_order.side_effect = [
        make_order_result(301, message="primary accepted"),
        make_order_result(
            None,
            success=False,
            status=OrderStatus.REJECTED,
            message="Market order failed",
            error="trigger rejected",
        ),
        make_order_result(303, message="sl accepted"),
    ]
    api.get_order_status.side_effect = [
        make_order_info(
            301,
            coin="ETH",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("1"),
            price=None,
            status=OrderStatus.OPEN,
            reduce_only=False,
        ),
        make_order_info(
            303,
            coin="ETH",
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=Decimal("1"),
            price=None,
            status=OrderStatus.OPEN,
            reduce_only=True,
            trigger=OrderTrigger(
                trigger_type=TriggerType.STOP,
                trigger_price=Decimal("2000"),
            ),
        ),
    ]

    backend_api = Mock()
    backend_api.__enter__ = Mock(return_value=api)
    backend_api.__exit__ = Mock(return_value=None)

    with patch("cli.interactive_cli.BackendAPI", return_value=backend_api):
        cli.do_order("buy eth 1 --tp 3000 --sl 2000")

    assert api.submit_market_order.call_count == 3
    assert api.get_order_status.call_args_list == [call(301), call(303)]
    output = capsys.readouterr().out
    assert "Submitted Orders (2)" in output
    assert "Take Profit Order:" in output
    assert "trigger rejected" in output


def test_do_order_rejects_invalid_quick_order_side(capsys) -> None:
    cli = InteractiveCLI(make_config())

    cli.do_order("long ETH 1")
    output = capsys.readouterr().out

    assert "Side must be 'buy' or 'sell'" in output
    assert (
        "order <buy|sell> <coin> <quantity|quantity@price> [--tp <price>] [--sl <price>]" in output
    )


def test_help_order_describes_quick_order_syntax(capsys) -> None:
    cli = InteractiveCLI(make_config())

    cli.help_order()
    output = capsys.readouterr().out

    assert (
        "order <buy|sell> <coin> <quantity|quantity@price> [--tp <price>] [--sl <price>]" in output
    )
    assert "order buy ETH 0.25" in output
    assert "order sell BTC 0.01@105000" in output
    assert "order buy BTC 2@75000 --tp 80000 --sl 60000" in output
    assert "--tp <price>" in output
    assert "--sl <price>" in output
