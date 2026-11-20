"""
Leverage and isolated margin mutation operations for HyperliquidClient.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from models.api import LeverageType
from models.leverage import LeverageResult
from models.margin import IsolatedMarginUpdateResult, get_decimal_places

if TYPE_CHECKING:
    from .hyperliquid_client import HyperliquidClient

MIN_LEVERAGE = 1
MAX_LEVERAGE = 250
MAX_DECIMALS = 6


def change_leverage(
    client: HyperliquidClient,
    leverage: int,
    coin: str,
    is_cross: bool = True,
) -> LeverageResult:
    """Change leverage for a specific position."""
    if not isinstance(leverage, int) or leverage < MIN_LEVERAGE or leverage > MAX_LEVERAGE:
        return LeverageResult(
            success=False,
            message=(
                f"Invalid leverage value: {leverage}. "
                f"Must be an integer between {MIN_LEVERAGE} and {MAX_LEVERAGE}"
            ),
            updated_position=None,
        )

    if not coin or not isinstance(coin, str):
        return LeverageResult(
            success=False,
            message="Invalid coin symbol: must be a non-empty string",
            updated_position=None,
        )

    exchange = client.connection.exchange

    def _change_leverage() -> LeverageResult:
        try:
            result = exchange.update_leverage(leverage, coin, is_cross)

            if result.get("status") == "ok":
                try:
                    updated_positions = client.get_positions()
                    updated_position = next(
                        (pos for pos in updated_positions if pos.coin == coin),
                        None,
                    )
                except Exception:
                    updated_position = None

                leverage_type = "cross" if is_cross else "isolated"
                return LeverageResult(
                    success=True,
                    message=(
                        f"Successfully updated {coin} leverage to "
                        f"{leverage}x ({leverage_type} margin)"
                    ),
                    updated_position=updated_position,
                )

            error_response = result.get("response", "Unknown error")
            if "Cannot switch leverage type with open position" in str(error_response):
                error_msg = (
                    f"Cannot switch leverage type for {coin} with open position. "
                    "Close the position first or use the same margin type."
                )
            elif "isolated position does not have sufficient margin" in str(error_response).lower():
                error_msg = (
                    f"Insufficient margin to decrease leverage for {coin} "
                    "isolated position. Add margin to the position or use "
                    "a higher leverage."
                )
            else:
                error_msg = f"Failed to update {coin} leverage: {error_response}"

            return LeverageResult(
                success=False,
                message=error_msg,
                updated_position=None,
            )
        except Exception as e:
            return LeverageResult(
                success=False,
                message=f"Leverage update failed for {coin}: {e!s}",
                updated_position=None,
            )

    return client.connection.retry_operation(_change_leverage)


def update_isolated_margin(
    client: HyperliquidClient,
    amount: Decimal,
    coin: str,
) -> IsolatedMarginUpdateResult:
    """Update isolated margin for a specific position."""
    if not coin or not isinstance(coin, str):
        return IsolatedMarginUpdateResult(
            success=False,
            message="Invalid coin symbol: must be a non-empty string",
            updated_position=None,
        )

    if amount == 0:
        return IsolatedMarginUpdateResult(
            success=False,
            message="Invalid amount: isolated margin update amount must be non-zero",
            updated_position=None,
        )

    if get_decimal_places(amount) > MAX_DECIMALS:
        return IsolatedMarginUpdateResult(
            success=False,
            message=(
                "Invalid amount: isolated margin update amount must have at most 6 decimal places"
            ),
            updated_position=None,
        )

    exchange = client.connection.exchange

    def _update_isolated_margin() -> IsolatedMarginUpdateResult:
        try:
            current_position = next(
                (position for position in client.get_positions() if position.coin == coin),
                None,
            )
            if current_position is None:
                return IsolatedMarginUpdateResult(
                    success=False,
                    message=f"No open position found for {coin}",
                    updated_position=None,
                )

            if current_position.leverage_type != LeverageType.ISOLATED:
                return IsolatedMarginUpdateResult(
                    success=False,
                    message=(
                        f"Cannot update isolated margin for {coin}: position is using cross margin"
                    ),
                    updated_position=None,
                )

            result = exchange.update_isolated_margin(float(amount), coin)
            result_status = result.get("status")
            response_payload = result.get("response")

            if result_status == "ok":
                if isinstance(response_payload, dict) and response_payload.get("type") not in (
                    None,
                    "default",
                ):
                    return IsolatedMarginUpdateResult(
                        success=False,
                        message=(
                            f"Unexpected isolated margin response for {coin}: {response_payload}"
                        ),
                        updated_position=None,
                    )

                try:
                    updated_positions = client.get_positions()
                    updated_position = next(
                        (position for position in updated_positions if position.coin == coin),
                        None,
                    )
                except Exception:
                    updated_position = None

                action = "added" if amount > 0 else "removed"
                direction = "to" if amount > 0 else "from"
                return IsolatedMarginUpdateResult(
                    success=True,
                    message=(
                        f"Successfully {action} ${abs(amount):.2f} "
                        f"isolated margin {direction} {coin}"
                    ),
                    updated_position=updated_position,
                )

            if isinstance(response_payload, dict):
                error_response = response_payload.get("error") or response_payload.get("message")
                if error_response is None:
                    error_response = str(response_payload)
            else:
                error_response = response_payload or "Unknown error"

            return IsolatedMarginUpdateResult(
                success=False,
                message=f"Failed to update isolated margin for {coin}: {error_response}",
                updated_position=None,
            )
        except Exception as e:
            return IsolatedMarginUpdateResult(
                success=False,
                message=f"Isolated margin update failed for {coin}: {e!s}",
                updated_position=None,
            )

    return client.connection.retry_operation(_update_isolated_margin)
