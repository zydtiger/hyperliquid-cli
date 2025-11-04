"""
FastAPI request handlers for Hyperliquid exchange operations.

This module defines REST API endpoints that expose Hyperliquid client functionality
through HTTP requests with proper error handling and response formatting.
"""

import logging
from typing import List

from fastapi import FastAPI, HTTPException, Path, status

from .exchange.hyperliquid_client import HyperliquidClient
from models.api import Ticker, CoinMetadata, PositionInfo, BalanceInfo, ExchangeError
from models.order import OrderInfo, MarketOrder, LimitOrder, OrderResult


logger = logging.getLogger(__name__)


def setup_request_handlers(app: FastAPI, client: HyperliquidClient) -> None:
    """
    Setup FastAPI request handlers with the provided Hyperliquid client.

    Args:
        app: FastAPI application instance
        client: Shared Hyperliquid client instance
    """

    @app.get("/available_coins", response_model=List[str])
    async def get_available_coins():
        """
        Get list of available trading coins.

        Returns:
            List[str]: List of available coin symbols
        """
        try:
            coins = client.get_available_coins()
            return coins
        except ExchangeError as e:
            logger.error(f"Exchange error getting available coins: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except Exception as e:
            logger.error(f"Unexpected error getting available coins: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            )

    @app.get("/ticker/{coin}", response_model=Ticker)
    async def get_ticker(
        coin: str = Path(..., description="Symbol of the cryptocurrency")
    ):
        """
        Get ticker information for a specific coin.

        Args:
            coin: Symbol of the cryptocurrency

        Returns:
            Ticker: Ticker data
        """
        try:
            ticker = client.get_ticker(coin)
            return ticker
        except ExchangeError as e:
            logger.error(f"Exchange error getting ticker for {coin}: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except Exception as e:
            logger.error(f"Unexpected error getting ticker for {coin}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            )

    @app.get("/metadata/{coin}", response_model=CoinMetadata)
    async def get_metadata(
        coin: str = Path(..., description="Symbol of the cryptocurrency")
    ):
        """
        Get metadata for a specific coin.

        Args:
            coin: Symbol of the cryptocurrency

        Returns:
            CoinMetadata: Coin metadata
        """
        try:
            metadata = client.get_metadata(coin)
            return metadata
        except ExchangeError as e:
            logger.error(f"Exchange error getting metadata for {coin}: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except Exception as e:
            logger.error(f"Unexpected error getting metadata for {coin}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            )

    @app.get("/positions", response_model=List[PositionInfo])
    async def get_positions():
        """
        Get current open positions.

        Returns:
            List[PositionInfo]: List of open positions
        """
        try:
            positions = client.get_positions()
            return positions
        except ExchangeError as e:
            logger.error(f"Exchange error getting positions: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except Exception as e:
            logger.error(f"Unexpected error getting positions: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            )

    @app.get("/positions/{coin}", response_model=PositionInfo)
    async def get_position(
        coin: str = Path(..., description="Symbol of the cryptocurrency")
    ):
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
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except HTTPException:
            # Re-raise HTTP exceptions (like 404)
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting position for {coin}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            )

    @app.get("/balances", response_model=BalanceInfo)
    async def get_balances():
        """
        Get comprehensive balance information for the account.

        Returns:
            BalanceInfo: Comprehensive balance information including perpetuals, spot, and staking
        """
        try:
            balances = client.get_balances()
            return balances
        except ExchangeError as e:
            logger.error(f"Exchange error getting balances: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except Exception as e:
            logger.error(f"Unexpected error getting balances: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            )

    @app.get("/order_status/{order_id}", response_model=OrderInfo)
    async def get_order_status(
        order_id: int = Path(..., description="Order ID (integer OID)", ge=1)
    ):
        """
        Get status and details of a specific order by its ID.

        Args:
            order_id: Order identifier (integer OID)

        Returns:
            OrderInfo: Detailed order information
        """
        try:
            order_info = client.get_order_status(order_id)
            return order_info
        except ExchangeError as e:
            logger.error(f"Exchange error getting order status for {order_id}: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except Exception as e:
            logger.error(f"Unexpected error getting order status for {order_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            )

    @app.get("/open_orders", response_model=List[OrderInfo])
    async def get_open_orders():
        """
        Get all open orders for the account.

        Returns:
            List[OrderInfo]: List of open orders with full details
        """
        try:
            orders = client.get_open_orders()
            return orders
        except ExchangeError as e:
            logger.error(f"Exchange error getting open orders: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except Exception as e:
            logger.error(f"Unexpected error getting open orders: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            )

    @app.post("/market_order", response_model=OrderResult)
    async def submit_market_order(order: MarketOrder):
        """
        Submit a market order for immediate execution.

        Args:
            order: Market order details including coin, side, quantity, and reduce_only flag

        Returns:
            OrderResult: Result of the order submission with order ID and status
        """
        try:
            result = client.submit_market_order(order)
            return result
        except ExchangeError as e:
            logger.error(f"Exchange error submitting market order: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except Exception as e:
            logger.error(f"Unexpected error submitting market order: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            )

    @app.post("/limit_order", response_model=OrderResult)
    async def submit_limit_order(order: LimitOrder):
        """
        Submit a limit order with specified price and time-in-force.

        Args:
            order: Limit order details including coin, side, quantity, price, reduce_only flag, and time-in-force

        Returns:
            OrderResult: Result of the order submission with order ID and status
        """
        try:
            result = client.submit_limit_order(order)
            return result
        except ExchangeError as e:
            logger.error(f"Exchange error submitting limit order: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except Exception as e:
            logger.error(f"Unexpected error submitting limit order: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",
            )
