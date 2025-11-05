"""
Backend API client for the Hyperliquid CLI.

This module provides a convenient interface for making HTTP requests to the
Hyperliquid backend FastAPI service, with proper error handling and type safety.
"""

import logging
from decimal import Decimal
from typing import List, Optional

import httpx

from models.api import (
    APIError,
    HealthResponse,
    RootResponse,
    Ticker,
    CoinMetadata,
    PositionInfo,
    BalanceInfo,
)
from models.order import (
    OrderInfo,
    OrderResult,
    MarketOrder,
    LimitOrder,
    CancelOrderRequest,
    ModifyOrderRequest,
)
from models.config import Config


logger = logging.getLogger(__name__)


class BackendAPI:
    """
    Client for interacting with the Hyperliquid backend API.

    This class provides convenient methods for calling all backend endpoints
    with proper error handling and response parsing.
    """

    def __init__(self, config: Config):
        """
        Initialize the BackendAPI client.

        Args:
            config: Configuration object containing backend connection settings
        """
        self.base_url = f"http://{config.backend.host}:{config.backend.port}"
        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(30.0, connect=5.0),
            headers={"Content-Type": "application/json"},
        )
        logger.debug(f"Initialized BackendAPI with base URL: {self.base_url}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.client.close()

    def _handle_response_error(self, response: httpx.Response) -> None:
        """
        Handle API error responses.

        Args:
            response: HTTP response object

        Raises:
            APIError: If the response indicates an error
        """
        if response.status_code >= 400:
            try:
                error_data = response.json()
                error_message = error_data.get("detail", response.text)
            except Exception:
                error_message = response.text

            raise APIError(message=error_message, status_code=response.status_code)

    def get_root(self) -> RootResponse:
        """
        Get API root information.

        Returns:
            RootResponse: API information

        Raises:
            APIError: If the request fails
        """
        try:
            response = self.client.get("/")
            self._handle_response_error(response)
            return RootResponse(**response.json())
        except httpx.RequestError as e:
            logger.error(f"Failed to get root info: {e}")
            raise APIError(f"Connection error: {str(e)}")

    def health_check(self) -> HealthResponse:
        """
        Check if the backend service is healthy.

        Returns:
            HealthResponse: Health status

        Raises:
            APIError: If the request fails
        """
        try:
            response = self.client.get("/health")
            self._handle_response_error(response)
            return HealthResponse(**response.json())
        except httpx.RequestError as e:
            logger.error(f"Health check failed: {e}")
            raise APIError(f"Connection error: {str(e)}")

    def get_available_coins(self) -> List[str]:
        """
        Get list of all available trading coins.

        Returns:
            List[str]: List of available coin symbols

        Raises:
            APIError: If the request fails
        """
        try:
            response = self.client.get("/available_coins")
            self._handle_response_error(response)
            return response.json()
        except httpx.RequestError as e:
            logger.error(f"Failed to get available coins: {e}")
            raise APIError(f"Connection error: {str(e)}")

    def get_ticker(self, coin: str) -> Ticker:
        """
        Get ticker information for a specific coin.

        Args:
            coin: Symbol of the cryptocurrency

        Returns:
            Ticker: Ticker data

        Raises:
            APIError: If the request fails
        """
        try:
            response = self.client.get(f"/ticker/{coin}")
            self._handle_response_error(response)
            return Ticker(**response.json())
        except httpx.RequestError as e:
            logger.error(f"Failed to get ticker for {coin}: {e}")
            raise APIError(f"Connection error: {str(e)}")

    def get_metadata(self, coin: str) -> CoinMetadata:
        """
        Get metadata for a specific coin.

        Args:
            coin: Symbol of the cryptocurrency

        Returns:
            CoinMetadata: Coin metadata

        Raises:
            APIError: If the request fails
        """
        try:
            response = self.client.get(f"/metadata/{coin}")
            self._handle_response_error(response)
            return CoinMetadata(**response.json())
        except httpx.RequestError as e:
            logger.error(f"Failed to get metadata for {coin}: {e}")
            raise APIError(f"Connection error: {str(e)}")

    def get_positions(self) -> List[PositionInfo]:
        """
        Get all current open positions.

        Returns:
            List[PositionInfo]: List of open positions

        Raises:
            APIError: If the request fails
        """
        try:
            response = self.client.get("/positions")
            self._handle_response_error(response)
            return [PositionInfo(**position) for position in response.json()]
        except httpx.RequestError as e:
            logger.error(f"Failed to get positions: {e}")
            raise APIError(f"Connection error: {str(e)}")

    def get_balances(self) -> BalanceInfo:
        """
        Get comprehensive balance information for the account.

        Returns:
            BalanceInfo: Comprehensive balance information including perpetuals, spot, and staking

        Raises:
            APIError: If the request fails
        """
        try:
            response = self.client.get("/balances")
            self._handle_response_error(response)
            return BalanceInfo(**response.json())
        except httpx.RequestError as e:
            logger.error(f"Failed to get balances: {e}")
            raise APIError(f"Connection error: {str(e)}")

    def get_position(self, coin: str) -> PositionInfo:
        """
        Get position information for a specific coin.

        Args:
            coin: Symbol of the cryptocurrency

        Returns:
            PositionInfo: Position information

        Raises:
            APIError: If the request fails or no position is found
        """
        try:
            response = self.client.get(f"/positions/{coin}")
            self._handle_response_error(response)
            return PositionInfo(**response.json())
        except httpx.RequestError as e:
            logger.error(f"Failed to get position for {coin}: {e}")
            raise APIError(f"Connection error: {str(e)}")

    def get_order_status(self, order_id: int) -> OrderInfo:
        """
        Get status and details of a specific order by its ID.

        Args:
            order_id: Order identifier (integer OID)

        Returns:
            OrderInfo: Detailed order information

        Raises:
            APIError: If the request fails
        """
        try:
            response = self.client.get(f"/order_status/{order_id}")
            self._handle_response_error(response)
            return OrderInfo(**response.json())
        except httpx.RequestError as e:
            logger.error(f"Failed to get order status for {order_id}: {e}")
            raise APIError(f"Connection error: {str(e)}")

    def get_open_orders(self) -> List[OrderInfo]:
        """
        Get all open orders for the account.

        Returns:
            List[OrderInfo]: List of open orders with full details

        Raises:
            APIError: If the request fails
        """
        try:
            response = self.client.get("/open_orders")
            self._handle_response_error(response)
            return [OrderInfo(**order) for order in response.json()]
        except httpx.RequestError as e:
            logger.error(f"Failed to get open orders: {e}")
            raise APIError(f"Connection error: {str(e)}")

    def submit_market_order(self, order: MarketOrder) -> OrderResult:
        """
        Submit a market order for immediate execution.

        Args:
            order: Market order details including coin, side, quantity, and reduce_only flag

        Returns:
            OrderResult: Result of the order submission with order ID and status

        Raises:
            APIError: If the request fails
        """
        try:
            response = self.client.post(
                "/market_order",
                content=order.model_dump_json(),
                headers={"Content-Type": "application/json"},
            )
            self._handle_response_error(response)
            return OrderResult(**response.json())
        except httpx.RequestError as e:
            logger.error(f"Failed to submit market order: {e}")
            raise APIError(f"Connection error: {str(e)}")

    def submit_limit_order(self, order: LimitOrder) -> OrderResult:
        """
        Submit a limit order with specified price and time-in-force.

        Args:
            order: Limit order details including coin, side, quantity, price, reduce_only flag, and time-in-force

        Returns:
            OrderResult: Result of the order submission with order ID and status

        Raises:
            APIError: If the request fails
        """
        try:
            response = self.client.post(
                "/limit_order",
                content=order.model_dump_json(),
                headers={"Content-Type": "application/json"},
            )
            self._handle_response_error(response)
            return OrderResult(**response.json())
        except httpx.RequestError as e:
            logger.error(f"Failed to submit limit order: {e}")
            raise APIError(f"Connection error: {str(e)}")

    def cancel_order(self, order_id: int | str) -> OrderResult:
        """
        Cancel a specific order or all open orders.

        Args:
            order_id: Order ID (int) to cancel, or "all" to cancel all open orders

        Returns:
            OrderResult: Result of the cancellation operation

        Raises:
            APIError: If the request fails
        """
        try:
            # Create CancelOrderRequest model
            request = CancelOrderRequest(order_id=order_id)

            # Send the request as JSON
            response = self.client.post(
                "/cancel_order",
                content=request.model_dump_json(),
                headers={"Content-Type": "application/json"},
            )
            self._handle_response_error(response)
            return OrderResult(**response.json())
        except httpx.RequestError as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            raise APIError(f"Connection error: {str(e)}")

    def modify_order(self, request: ModifyOrderRequest) -> OrderResult:
        """
        Modify price and/or quantity of an existing open limit order.

        Args:
            request: ModifyOrderRequest model containing order_id, price, and quantity

        Returns:
            OrderResult: Result of the modification operation

        Raises:
            APIError: If the request fails
        """
        try:
            # Send the request as JSON
            response = self.client.post(
                "/modify_order",
                content=request.model_dump_json(),
                headers={"Content-Type": "application/json"},
            )
            self._handle_response_error(response)
            return OrderResult(**response.json())
        except httpx.RequestError as e:
            logger.error(f"Failed to modify order {request.order_id}: {e}")
            raise APIError(f"Connection error: {str(e)}")

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()
        logger.debug("BackendAPI client closed")
