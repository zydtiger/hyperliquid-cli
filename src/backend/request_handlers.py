"""
FastAPI request handlers for Hyperliquid exchange operations.

This module defines REST API endpoints that expose Hyperliquid client functionality
through HTTP requests with proper error handling and response formatting.
"""

import logging
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path, Query, status

from models.api import (
    BalanceInfo,
    CoinMetadata,
    ExchangeError,
    PnlHistoryCatalog,
    PositionInfo,
    Ticker,
)
from models.leverage import LeverageResult, LeverageUpdateRequest
from models.margin import IsolatedMarginUpdateRequest, IsolatedMarginUpdateResult
from models.order import (
    CancelOrderRequest,
    LimitOrder,
    MarketOrder,
    ModifyOrderRequest,
    OrderHistoryEntry,
    OrderInfo,
    OrderResult,
)

from .exchange.hyperliquid_client import HyperliquidClient

logger = logging.getLogger(__name__)


def setup_request_handlers(app: FastAPI, client: HyperliquidClient) -> None:  # noqa: PLR0915
    """
    Setup FastAPI request handlers with the provided Hyperliquid client.

    Args:
        app: FastAPI application instance
        client: Shared Hyperliquid client instance
    """

    @app.get("/available_coins")
    async def get_available_coins() -> list[str]:
        """
        Get list of available trading coins.

        Returns:
            List[str]: List of available coin symbols
        """
        try:
            return client.get_available_coins()
        except ExchangeError as e:
            logger.error(f"Exchange error getting available coins: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        except Exception as e:
            logger.error(f"Unexpected error getting available coins: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            ) from e

    @app.get("/ticker/{coin}")
    async def get_ticker(
        coin: str = Path(..., description="Symbol of the cryptocurrency"),
    ) -> Ticker:
        """
        Get ticker information for a specific coin.

        Args:
            coin: Symbol of the cryptocurrency

        Returns:
            Ticker: Ticker data
        """
        try:
            return client.get_ticker(coin)
        except ExchangeError as e:
            logger.error(f"Exchange error getting ticker for {coin}: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        except Exception as e:
            logger.error(f"Unexpected error getting ticker for {coin}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            ) from e

    @app.get("/metadata/{coin}")
    async def get_metadata(
        coin: str = Path(..., description="Symbol of the cryptocurrency"),
    ) -> CoinMetadata:
        """
        Get metadata for a specific coin.

        Args:
            coin: Symbol of the cryptocurrency

        Returns:
            CoinMetadata: Coin metadata
        """
        try:
            return client.get_metadata(coin)
        except ExchangeError as e:
            logger.error(f"Exchange error getting metadata for {coin}: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        except Exception as e:
            logger.error(f"Unexpected error getting metadata for {coin}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            ) from e

    @app.get("/positions")
    async def get_positions() -> list[PositionInfo]:
        """
        Get current open positions.

        Returns:
            List[PositionInfo]: List of open positions
        """
        try:
            return client.get_positions()
        except ExchangeError as e:
            logger.error(f"Exchange error getting positions: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        except Exception as e:
            logger.error(f"Unexpected error getting positions: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            ) from e

    @app.get("/positions/{coin}")
    async def get_position(
        coin: str = Path(..., description="Symbol of the cryptocurrency"),
    ) -> PositionInfo:
        """
        Get position information for a specific coin.

        Args:
            coin: Symbol of the cryptocurrency

        Returns:
            PositionInfo: Position information
        """
        try:
            positions = client.get_positions()

            # Find position for the specified coin
            for position in positions:
                if position.coin == coin:
                    return position

            # If no position found, return empty position
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No position found for {coin}",
            )

        except ExchangeError as e:
            logger.error(f"Exchange error getting position for {coin}: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        except HTTPException:
            # Re-raise HTTP exceptions (like 404)
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting position for {coin}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            ) from e

    @app.get("/balances")
    async def get_balances() -> BalanceInfo:
        """
        Get comprehensive balance information for the account.

        Returns:
            BalanceInfo: Comprehensive balance information including perpetuals, spot, and staking
        """
        try:
            return client.get_balances()
        except ExchangeError as e:
            logger.error(f"Exchange error getting balances: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        except Exception as e:
            logger.error(f"Unexpected error getting balances: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            ) from e

    @app.get("/order_status/{order_id}")
    async def get_order_status(
        order_id: int = Path(..., description="Order ID (integer OID)", ge=1),
    ) -> OrderInfo:
        """
        Get status and details of a specific order by its ID.

        Args:
            order_id: Order identifier (integer OID)

        Returns:
            OrderInfo: Detailed order information
        """
        try:
            return client.get_order_status(order_id)
        except ExchangeError as e:
            logger.error(f"Exchange error getting order status for {order_id}: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        except Exception as e:
            logger.error(f"Unexpected error getting order status for {order_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            ) from e

    @app.get("/open_orders")
    async def get_open_orders() -> list[OrderInfo]:
        """
        Get all open orders for the account.

        Returns:
            List[OrderInfo]: List of open orders with full details
        """
        try:
            return client.get_open_orders()
        except ExchangeError as e:
            logger.error(f"Exchange error getting open orders: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        except Exception as e:
            logger.error(f"Unexpected error getting open orders: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            ) from e

    @app.get("/order_history")
    async def get_order_history(
        limit: Annotated[int, Query(ge=1, description="Maximum entries to return")] = 10,
    ) -> list[OrderHistoryEntry]:
        """
        Get recent filled-order history for the configured account.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List[OrderHistoryEntry]: Filled-order history entries
        """
        try:
            return client.get_order_history(limit)
        except ExchangeError as e:
            logger.error(f"Exchange error getting order history: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        except Exception as e:
            logger.error(f"Unexpected error getting order history: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            ) from e

    @app.get("/pnl")
    async def get_pnl_history() -> PnlHistoryCatalog:
        """
        Get all supported total/perpetual/spot PnL history windows.

        Returns:
            PnlHistoryCatalog: Ordered PnL history windows for the frontend
        """
        try:
            return client.get_pnl_history()
        except ExchangeError as e:
            logger.error(f"Exchange error getting PnL history: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        except Exception as e:
            logger.error(f"Unexpected error getting PnL history: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            ) from e

    @app.post("/market_order")
    async def submit_market_order(order: MarketOrder) -> OrderResult:
        """
        Submit a market order for immediate execution.

        Args:
            order: Market order details including coin, side, quantity, and reduce_only flag

        Returns:
            OrderResult: Result of the order submission with order ID and status
        """
        try:
            return client.submit_market_order(order)
        except ExchangeError as e:
            logger.error(f"Exchange error submitting market order: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        except Exception as e:
            logger.error(f"Unexpected error submitting market order: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            ) from e

    @app.post("/limit_order")
    async def submit_limit_order(order: LimitOrder) -> OrderResult:
        """
        Submit a limit order with specified price and time-in-force.

        Args:
            order: Limit order details including coin, side, quantity, price,
                reduce_only flag, and time-in-force

        Returns:
            OrderResult: Result of the order submission with order ID and status
        """
        try:
            return client.submit_limit_order(order)
        except ExchangeError as e:
            logger.error(f"Exchange error submitting limit order: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        except Exception as e:
            logger.error(f"Unexpected error submitting limit order: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            ) from e

    @app.post("/cancel_order")
    async def cancel_order(request: CancelOrderRequest) -> OrderResult:
        """
        Cancel a specific order or all open orders.

        Request body:
        {
            "order_id": int | str  # int for specific order, "all" for all orders
        }

        Returns:
            OrderResult: Result of the cancellation operation with success status and details
        """
        try:
            return client.cancel_order(request.order_id)
        except ExchangeError as e:
            logger.error(f"Exchange error cancelling order {request.order_id}: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        except Exception as e:
            logger.error(f"Unexpected error cancelling order {request.order_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            ) from e

    @app.post("/modify_order")
    async def modify_order(request: ModifyOrderRequest) -> OrderResult:
        """
        Modify price and/or quantity of an existing open limit order.

        Request body:
        {
            "order_id": int,
            "price": Decimal | null,  # New price (null to keep current price)
            "quantity": Decimal | null  # New quantity (null to keep current quantity)
        }

        Returns:
            OrderResult: Result of the modification operation with success status and details
        """
        try:
            return client.modify_order(request.order_id, request.price, request.quantity)
        except ExchangeError as e:
            logger.error(f"Exchange error modifying order {request.order_id}: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        except Exception as e:
            logger.error(f"Unexpected error modifying order {request.order_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            ) from e

    @app.post("/change_leverage", response_model=LeverageResult)
    async def change_leverage(request: LeverageUpdateRequest) -> LeverageResult:
        """
        Update leverage for a specific position.

        Request body:
        {
            "leverage": int,        # Target leverage multiplier (1-250)
            "coin": str,            # Symbol of the cryptocurrency
            "is_cross": bool        # Whether to use cross margin (True) or isolated margin (False)
        }

        Returns:
            LeverageResult: Result of the leverage modification operation with success status,
                          message, and updated position information if successful
        """
        try:
            return client.change_leverage(
                leverage=request.leverage,
                coin=request.coin,
                is_cross=request.is_cross,
            )
        except ExchangeError as e:
            logger.error(f"Exchange error changing leverage for {request.coin}: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        except Exception as e:
            logger.error(f"Unexpected error changing leverage for {request.coin}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            ) from e

    @app.post("/update_isolated_margin", response_model=IsolatedMarginUpdateResult)
    async def update_isolated_margin(
        request: IsolatedMarginUpdateRequest,
    ) -> IsolatedMarginUpdateResult:
        """
        Update isolated margin for a specific position.

        Request body:
        {
            "coin": str,      # Symbol of the cryptocurrency
            "amount": decimal # Signed isolated margin delta in USD
        }

        Returns:
            IsolatedMarginUpdateResult: Result of the isolated margin update operation
        """
        try:
            return client.update_isolated_margin(
                amount=request.amount,
                coin=request.coin,
            )
        except ExchangeError as e:
            logger.error(f"Exchange error updating isolated margin for {request.coin}: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        except Exception as e:
            logger.error(f"Unexpected error updating isolated margin for {request.coin}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            ) from e
