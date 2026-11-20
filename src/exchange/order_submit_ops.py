"""
Order submission operations for HyperliquidClient.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from hyperliquid.utils.signing import OrderType as ExchangeOrderType

from models.order import LimitOrder, MarketOrder, OrderResult, OrderSide, OrderStatus

from .order_parsing import (
    build_trigger_order_type,
    convert_tif_value,
    parse_order_submission_result,
)

if TYPE_CHECKING:
    from .hyperliquid_client import HyperliquidClient


def _get_trigger_market_limit_px(client: HyperliquidClient, order: MarketOrder) -> float:
    slippage = float(client.config.trading.default_slippage)
    return float(
        client.connection.exchange._slippage_price(
            order.coin,
            order.side == OrderSide.BUY,
            slippage,
            None,
        )
    )


def submit_market_order(client: HyperliquidClient, order: MarketOrder) -> OrderResult:
    """Submit a market order to the exchange."""
    exchange = client.connection.exchange

    def _submit_market_order() -> OrderResult:
        try:
            coin = client._normalize_order_coin(order.coin)

            if order.trigger is not None:
                result = exchange.order(
                    name=coin,
                    is_buy=(order.side.value == "buy"),
                    sz=float(order.quantity),
                    limit_px=_get_trigger_market_limit_px(client, order),
                    order_type=build_trigger_order_type(order.trigger, is_market=True),
                    reduce_only=order.reduce_only,
                )
                return parse_order_submission_result(result, "Market order")

            slippage = float(client.config.trading.default_slippage)
            if order.reduce_only:
                result = exchange.market_close(
                    coin=coin,
                    sz=float(order.quantity),
                    px=None,
                    slippage=slippage,
                )
            else:
                result = exchange.market_open(
                    name=coin,
                    is_buy=(order.side.value == "buy"),
                    sz=float(order.quantity),
                    px=None,
                    slippage=slippage,
                )

            return parse_order_submission_result(result, "Market order")
        except Exception as e:
            return OrderResult(
                success=False,
                status=OrderStatus.REJECTED,
                message="Market order submission failed",
                error=str(e),
            )

    return client.connection.retry_operation(_submit_market_order)


def submit_limit_order(client: HyperliquidClient, order: LimitOrder) -> OrderResult:
    """Submit a limit order to the exchange."""
    exchange = client.connection.exchange

    def _submit_limit_order() -> OrderResult:
        try:
            coin = client._normalize_order_coin(order.coin)

            order_type: ExchangeOrderType
            if order.trigger is not None:
                order_type = build_trigger_order_type(order.trigger, is_market=False)
            else:
                order_type = cast(
                    ExchangeOrderType,
                    {"limit": {"tif": convert_tif_value(order.time_in_force)}},
                )

            result = exchange.order(
                name=coin,
                is_buy=(order.side.value == "buy"),
                sz=float(order.quantity),
                limit_px=float(order.price),
                order_type=order_type,
                reduce_only=order.reduce_only,
            )
            return parse_order_submission_result(result, "Limit order")
        except Exception as e:
            return OrderResult(
                success=False,
                status=OrderStatus.REJECTED,
                message="Limit order submission failed",
                error=str(e),
            )

    return client.connection.retry_operation(_submit_limit_order)
