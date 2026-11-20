"""
Order parsing and formatting helpers for Hyperliquid exchange responses.
"""

from collections.abc import Callable, Mapping
from decimal import Decimal
from typing import Any, cast

from hyperliquid.utils.signing import OrderType as ExchangeOrderType
from hyperliquid.utils.signing import Tif

from models.order import (
    OrderInfo,
    OrderResult,
    OrderSide,
    OrderStatus,
    OrderTif,
    OrderTrigger,
    OrderType,
    TriggerType,
)


def convert_tif_value(tif: OrderTif) -> Tif:
    """Convert internal OrderTif enum to Hyperliquid SDK TIF string."""
    if tif == OrderTif.GTC:
        return "Gtc"
    if tif == OrderTif.IOC:
        return "Ioc"
    return "Alo"


def convert_trigger_type(trigger_type: TriggerType) -> str:
    """Convert TriggerType enum to Hyperliquid SDK tpsl string."""
    if trigger_type == TriggerType.STOP:
        return "sl"
    return "tp"


def build_trigger_order_type(
    trigger: OrderTrigger,
    *,
    is_market: bool,
) -> ExchangeOrderType:
    """Build a Hyperliquid SDK trigger order type payload."""
    return cast(
        ExchangeOrderType,
        {
            "trigger": {
                "triggerPx": float(trigger.trigger_price),
                "isMarket": is_market,
                "tpsl": convert_trigger_type(trigger.trigger_type),
            }
        },
    )


def parse_order_status(status_str: str) -> OrderStatus:
    """Map an exchange order status string to OrderStatus."""
    normalized = status_str.lower()
    if normalized in ("open", "order"):
        return OrderStatus.OPEN
    if normalized == "filled":
        return OrderStatus.FILLED
    if normalized in ("canceled", "cancelled"):
        return OrderStatus.CANCELLED
    if normalized in ("rejected", "failed"):
        return OrderStatus.REJECTED
    return OrderStatus.PARTIALLY_FILLED


def parse_order_tif(tif_value: Any) -> OrderTif | None:
    """Parse an optional exchange TIF string into OrderTif."""
    if not tif_value or not isinstance(tif_value, str):
        return None
    try:
        return OrderTif(tif_value.upper())
    except ValueError:
        return None


def parse_trigger_type(  # noqa: PLR0911
    trigger_condition: str | None,
    side: OrderSide,
) -> TriggerType | None:
    """Infer TriggerType from a Hyperliquid triggerCondition string and order side."""
    if not trigger_condition:
        return None

    normalized = trigger_condition.strip().lower()
    if normalized in {"n/a", "na"}:
        return None
    if "tp" in normalized or "take" in normalized:
        return TriggerType.TAKE
    if "sl" in normalized or "stop" in normalized:
        return TriggerType.STOP
    if "above" in normalized:
        return TriggerType.STOP if side == OrderSide.BUY else TriggerType.TAKE
    if "below" in normalized:
        return TriggerType.TAKE if side == OrderSide.BUY else TriggerType.STOP
    return None


def extract_order_trigger(order_data: Mapping[str, Any]) -> OrderTrigger | None:
    """Extract optional OrderTrigger metadata from an exchange order payload."""
    if not order_data.get("isTrigger"):
        return None

    trigger_px = order_data.get("triggerPx")
    if trigger_px in (None, "0", "0.0"):
        return None

    trigger_type = parse_trigger_type(
        order_data.get("triggerCondition"),
        OrderSide.BUY if order_data.get("side") == "B" else OrderSide.SELL,
    )
    if trigger_type is None:
        return None

    return OrderTrigger(
        trigger_price=Decimal(str(trigger_px)),
        trigger_type=trigger_type,
    )


def parse_order_info(
    order_data: Mapping[str, Any],
    *,
    status: OrderStatus,
    resolve_coin: Callable[[str], str],
    order_id: int | None = None,
) -> OrderInfo:
    """Build an OrderInfo model from a query_order_by_oid or frontendOpenOrders item."""
    resolved_order_id = int(order_id if order_id is not None else order_data["oid"])
    original_quantity = Decimal(str(order_data.get("origSz", order_data.get("sz", "0"))))
    current_quantity = Decimal(str(order_data.get("sz", "0")))
    filled_quantity = original_quantity - current_quantity

    order_type_str = str(order_data.get("orderType", "Limit")).upper()
    order_type = OrderType.LIMIT if "LIMIT" in order_type_str else OrderType.MARKET

    limit_px = order_data.get("limitPx")
    price = (
        Decimal(str(limit_px))
        if order_type == OrderType.LIMIT and limit_px and str(limit_px) != "0"
        else None
    )

    avg_fill_px = order_data.get("averageFillPx")
    average_fill_price = Decimal(str(avg_fill_px)) if avg_fill_px else None

    return OrderInfo(
        order_id=resolved_order_id,
        coin=resolve_coin(str(order_data.get("coin", ""))),
        side=OrderSide.BUY if order_data.get("side") == "B" else OrderSide.SELL,
        order_type=order_type,
        quantity=original_quantity,
        price=price,
        filled_quantity=filled_quantity,
        remaining_quantity=current_quantity,
        average_fill_price=average_fill_price,
        status=status,
        timestamp=int(order_data.get("timestamp", 0)),
        reduce_only=bool(order_data.get("reduceOnly", False)),
        time_in_force=parse_order_tif(order_data.get("tif")),
        trigger=extract_order_trigger(order_data),
    )


def parse_order_submission_result(result: Mapping[str, Any], order_label: str) -> OrderResult:
    """Parse Hyperliquid order submission response into OrderResult."""
    if result.get("status") == "ok":
        statuses = result.get("response", {}).get("data", {}).get("statuses", [])

        for status in statuses:
            if "resting" in status:
                oid = status["resting"]["oid"]
                return OrderResult(
                    success=True,
                    order_id=oid,
                    status=OrderStatus.OPEN,
                    message=f"{order_label} is resting on the book",
                )
            if "error" in status:
                error = status["error"]
                return OrderResult(
                    success=False,
                    order_id=None,
                    status=OrderStatus.REJECTED,
                    message=f"{order_label} failed",
                    error=error,
                )
            if "filled" in status:
                fill = status["filled"]
                return OrderResult(
                    success=True,
                    order_id=fill["oid"],
                    status=OrderStatus.FILLED,
                    message=f"{order_label} filled {fill['totalSz']} at {fill['avgPx']}",
                )

        return OrderResult(
            success=False,
            order_id=None,
            status=OrderStatus.REJECTED,
            message=f"{order_label} submission failed - no status returned",
            error="Unknown response structure",
        )

    return OrderResult(
        success=False,
        status=OrderStatus.REJECTED,
        message=f"{order_label} submission failed",
        error=result.get("response", "Unknown error"),
    )
