"""
Leverage modification models for the Hyperliquid CLI.

This module provides Pydantic models for leverage modification requests
and responses used throughout the application.
"""

from pydantic import BaseModel, Field

from .api import PositionInfo


class LeverageUpdateRequest(BaseModel):
    """Request model for updating position leverage."""

    leverage: int = Field(..., ge=1, le=250, description="Target leverage multiplier (1-250)")
    coin: str = Field(..., description="Symbol of the cryptocurrency")
    is_cross: bool = Field(
        True,
        description="Whether to use cross margin (True) or isolated margin (False)",
    )


class LeverageResult(BaseModel):
    """Result model for leverage modification operations."""

    success: bool = Field(..., description="Whether the leverage update was successful")
    message: str = Field(..., description="Result message describing the operation outcome")
    updated_position: PositionInfo | None = Field(
        None, description="Updated position information if successful"
    )
