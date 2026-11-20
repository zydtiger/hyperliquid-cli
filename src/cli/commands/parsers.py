"""Shared CLI option definitions and pure argument parsers/validators."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation

import typer

from models.api import (
    MAX_WATCH_ORDER_BOOK_DEPTH,
    MIN_WATCH_ORDER_BOOK_DEPTH,
    PNL_WINDOW_ORDER,
    WATCH_INTERVAL_ORDER,
    MarketType,
    PnlWindow,
    PositionInfo,
    WatchInterval,
)
from models.order import (
    LimitOrder,
    MarketOrder,
    OrderSide,
    OrderTif,
    OrderTrigger,
    TriggerType,
)

from ..runtime import CliValidationError

MIN_LEVERAGE = 1
MAX_LEVERAGE = 250
MARKET_TYPES: tuple[MarketType, ...] = ("all", "perp", "spot")

CONFIG_OPTION = typer.Option(
    "--config",
    "-c",
    help="Path to configuration file",
    file_okay=True,
    dir_okay=False,
)
ADDRESS_OPTION = typer.Option(
    "--address",
    help="Override Hyperliquid account address (0x...)",
)
NETWORK_OPTION = typer.Option(
    "--network",
    help="Override Hyperliquid network (mainnet or testnet)",
)
JSON_OPTION = typer.Option(
    "--json",
    help="Emit a single compact JSON object to stdout",
)


def parse_coin(value: str) -> str:
    """Normalize and validate a non-empty coin symbol."""
    coin = value.strip().upper()
    if not coin:
        raise CliValidationError("Coin symbol must be non-empty")
    return coin


def parse_positive_int(value: int, label: str) -> int:
    """Validate that an integer argument is strictly positive."""
    if value <= 0:
        raise CliValidationError(f"{label} must be a positive integer")
    return value


def parse_decimal(value: str, label: str) -> Decimal:
    """Parse a finite Decimal value."""
    try:
        parsed = Decimal(value.strip())
    except InvalidOperation as exc:
        raise CliValidationError(f"{label} must be a valid decimal value") from exc
    if not parsed.is_finite():
        raise CliValidationError(f"{label} must be a finite decimal value")
    return parsed


def parse_positive_decimal(value: str, label: str) -> Decimal:
    """Parse a strictly positive Decimal value."""
    parsed = parse_decimal(value, label)
    if parsed <= 0:
        raise CliValidationError(f"{label} must be greater than 0")
    return parsed


def parse_since_ms(value: str) -> int:
    """Parse ``--since`` as either Unix milliseconds or an ISO-8601 datetime string."""
    raw = value.strip()
    if not raw:
        raise CliValidationError("--since must be a Unix millisecond integer or ISO-8601 datetime")

    if raw.lstrip("+-").isdigit():
        since_ms = int(raw)
        if since_ms < 0:
            raise CliValidationError("--since timestamp must be non-negative")
        return since_ms

    try:
        parsed_dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CliValidationError(
            f"Invalid --since value '{value}': expected ISO-8601 datetime or Unix ms integer"
        ) from exc

    if parsed_dt.tzinfo is None:
        parsed_dt = parsed_dt.astimezone()
    return int(parsed_dt.timestamp() * 1000)


def parse_market_type(value: str) -> MarketType:
    """Validate ``--type`` for ``coins``."""
    normalized = value.strip().lower()
    if normalized not in MARKET_TYPES:
        allowed = ", ".join(MARKET_TYPES)
        raise CliValidationError(f"Invalid --type '{value}': expected one of {allowed}")
    return normalized


def parse_pnl_window(value: str) -> PnlWindow:
    """Validate ``--window`` for ``pnl``."""
    normalized = value.strip().lower()
    if normalized not in PNL_WINDOW_ORDER:
        allowed = ", ".join(PNL_WINDOW_ORDER)
        raise CliValidationError(f"Invalid --window '{value}': expected one of {allowed}")
    return normalized


def parse_watch_interval(value: str) -> WatchInterval:
    """Validate ``--interval`` for ``watch``."""
    normalized = value.strip().lower()
    if normalized not in WATCH_INTERVAL_ORDER:
        allowed = ", ".join(WATCH_INTERVAL_ORDER)
        raise CliValidationError(f"Invalid --interval '{value}': expected one of {allowed}")
    return normalized


def parse_watch_depth(value: int) -> int:
    """Validate ``--depth`` for ``watch``."""
    if value < MIN_WATCH_ORDER_BOOK_DEPTH or value > MAX_WATCH_ORDER_BOOK_DEPTH:
        raise CliValidationError(
            f"--depth must be between {MIN_WATCH_ORDER_BOOK_DEPTH} and {MAX_WATCH_ORDER_BOOK_DEPTH}"
        )
    return value


def parse_order_side(value: str) -> OrderSide:
    """Validate order side (buy/sell)."""
    try:
        return OrderSide(value.strip().lower())
    except ValueError as exc:
        raise CliValidationError(f"Invalid side '{value}': expected 'buy' or 'sell'") from exc


def parse_order_tif(value: str) -> OrderTif:
    """Validate limit order time-in-force (GTC/IOC/ALO)."""
    normalized = value.strip().upper()
    try:
        return OrderTif(normalized)
    except ValueError as exc:
        raise CliValidationError(f"Invalid --tif '{value}': expected GTC, IOC, or ALO") from exc


def parse_trigger_type(value: str) -> TriggerType:
    """Validate order trigger type (stop/take)."""
    try:
        return TriggerType(value.strip().lower())
    except ValueError as exc:
        raise CliValidationError(
            f"Invalid --trigger-type '{value}': expected 'stop' or 'take'"
        ) from exc


def parse_leverage(value: int) -> int:
    """Validate leverage value within global exchange bounds."""
    if value < MIN_LEVERAGE or value > MAX_LEVERAGE:
        raise CliValidationError(f"Leverage must be between {MIN_LEVERAGE} and {MAX_LEVERAGE}")
    return value


def validate_quantity_precision(quantity: Decimal, size_decimals: int, coin: str) -> None:
    """Verify quantity respects coin size_decimals precision."""
    precision = Decimal(f"1e-{size_decimals}")
    if quantity % precision != 0:
        raise CliValidationError(
            f"Quantity {quantity} for {coin} must be a multiple of {precision} "
            f"(size_decimals={size_decimals})"
        )


def build_tp_sl_orders(
    primary_order: MarketOrder | LimitOrder,
    take_profit: Decimal | None,
    stop_loss: Decimal | None,
) -> list[tuple[str, MarketOrder]]:
    """Build reduce-only trigger-market child orders for TP/SL."""
    trigger_orders: list[tuple[str, MarketOrder]] = []
    exit_side = OrderSide.SELL if primary_order.side == OrderSide.BUY else OrderSide.BUY

    if take_profit is not None:
        trigger_orders.append(
            (
                "Take Profit Order",
                MarketOrder(
                    coin=primary_order.coin,
                    side=exit_side,
                    quantity=primary_order.quantity,
                    reduce_only=True,
                    trigger=OrderTrigger(
                        trigger_type=TriggerType.TAKE,
                        trigger_price=take_profit,
                    ),
                ),
            )
        )

    if stop_loss is not None:
        trigger_orders.append(
            (
                "Stop Loss Order",
                MarketOrder(
                    coin=primary_order.coin,
                    side=exit_side,
                    quantity=primary_order.quantity,
                    reduce_only=True,
                    trigger=OrderTrigger(
                        trigger_type=TriggerType.STOP,
                        trigger_price=stop_loss,
                    ),
                ),
            )
        )

    return trigger_orders


def find_position_for_coin(positions: list[PositionInfo], coin: str) -> PositionInfo | None:
    """Find a position matching coin case-insensitively."""
    normalized = coin.strip().upper()
    return next((pos for pos in positions if pos.coin.upper() == normalized), None)
