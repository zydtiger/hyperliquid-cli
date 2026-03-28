from decimal import Decimal
from unittest.mock import Mock, patch

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
    OrderSide,
    OrderTif,
    OrderTrigger,
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
    assert "Please enter 1 (STOP) or 2 (TAKE)" in capsys.readouterr().out


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


def test_do_order_blocks_trigger_submission(capsys) -> None:
    config = make_config()
    cli = InteractiveCLI(config)
    api = Mock()
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
    ):
        cli.do_order("")

    api.submit_limit_order.assert_not_called()
    api.submit_market_order.assert_not_called()
    assert "Trigger orders are not wired to backend submission yet" in capsys.readouterr().out
