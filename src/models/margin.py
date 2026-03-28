"""
Isolated margin update models for the Hyperliquid CLI.

This module provides Pydantic models for isolated margin update requests
and responses used throughout the application.
"""

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from .api import PositionInfo

MAX_MARGIN_DECIMALS = 6


def get_decimal_places(value: Decimal) -> int:
    """Return the number of decimal places for a Decimal value."""
    normalized_value = value.normalize() if value != value.to_integral() else value
    exponent = normalized_value.as_tuple().exponent
    if not isinstance(exponent, int):
        raise ValueError("Amount exponent must be a finite integer")
    return max(0, -exponent)


class IsolatedMarginUpdateRequest(BaseModel):
    """Request model for updating isolated position margin."""

    coin: str = Field(..., description="Symbol of the cryptocurrency")
    amount: Decimal = Field(
        ...,
        description=(
            "Signed USD delta for isolated margin; positive adds margin and negative removes"
        ),
    )

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: Decimal) -> Decimal:
        """Validate isolated margin amount before it reaches the SDK layer."""
        if value == 0:
            raise ValueError("Amount must be non-zero")

        decimal_places = get_decimal_places(value)
        if decimal_places > MAX_MARGIN_DECIMALS:
            raise ValueError(f"Amount must have at most {MAX_MARGIN_DECIMALS} decimal places")

        return value


class IsolatedMarginUpdateResult(BaseModel):
    """Result model for isolated margin update operations."""

    success: bool = Field(..., description="Whether the isolated margin update was successful")
    message: str = Field(..., description="Result message describing the operation outcome")
    updated_position: PositionInfo | None = Field(
        None, description="Updated position information if successful"
    )
