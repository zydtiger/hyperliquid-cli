"""
Hyperliquid client for interacting with the exchange API.

This module provides a high-level client interface for the Hyperliquid exchange,
handling data retrieval and portfolio management operations.
"""

from decimal import Decimal
from typing import List
from hyperliquid.utils.signing import Tif

from .hyperliquid_connection import HyperliquidConnection
from models.api import (
    Ticker,
    CoinMetadata,
    PositionInfo,
    ExchangeError,
    LeverageType,
)
from models.order import (
    MarketOrder,
    LimitOrder,
    OrderResult,
    OrderSide,
    OrderStatus,
    OrderTif,
    OrderType,
    OrderInfo,
)
from models.config import Config


class HyperliquidClient:
    """
    High-level client for interacting with the Hyperliquid exchange.

    This class provides a simplified interface for common exchange operations
    like retrieving market data, positions, and account information.
    """

    def __init__(self, config: Config):
        """
        Initialize the Hyperliquid client.

        Args:
            config: Configuration object with exchange settings
        """
        self.config = config
        self.connection = HyperliquidConnection(config)

    def test_connection(self) -> bool:
        """
        Test the connection to the exchange.

        Returns:
            bool: True if connection is successful
        """
        return self.connection.test_connection()

    def get_available_coins(self) -> List[str]:
        """
        Get list of available trading coins.

        Returns:
            List[str]: List of available coin symbols
        """

        def _get_available_coins():
            meta = self.connection.info.meta()
            return [asset["name"] for asset in meta["universe"]]

        return self.connection.retry_operation(_get_available_coins)

    def get_ticker(self, coin: str) -> Ticker:
        """
        Get ticker information for a specific coin.

        Args:
            coin: Symbol of the cryptocurrency

        Returns:
            Ticker: Ticker data
        """

        def _get_ticker():
            meta, asset_ctxs = self.connection.info.meta_and_asset_ctxs()
            if not meta or "universe" not in meta:
                raise ExchangeError("Failed to retrieve market metadata from exchange")

            available_coins = [asset["name"] for asset in meta["universe"]]
            if coin not in available_coins:
                raise ExchangeError(
                    f"Coin '{coin}' not found in available trading pairs"
                )

            asset = asset_ctxs[available_coins.index(coin)]

            return Ticker(
                coin=coin,
                mark_price=Decimal(str(asset["markPx"])),
                funding_rate=Decimal(str(asset["funding"])),
                open_interest=Decimal(str(asset["openInterest"])),
            )

        return self.connection.retry_operation(_get_ticker)

    def get_metadata(self, coin: str) -> CoinMetadata:
        """
        Get metadata for a specific coin.

        Args:
            coin: Symbol of the cryptocurrency

        Returns:
            CoinMetadata: Coin metadata
        """

        def _get_metadata():
            meta = self.connection.info.meta()
            if not meta or "universe" not in meta:
                raise ExchangeError("Failed to retrieve market metadata from exchange")

            for asset in meta["universe"]:
                if asset["name"] == coin:
                    return CoinMetadata(
                        coin=asset["name"],
                        size_decimals=asset["szDecimals"],
                        max_leverage=asset["maxLeverage"],  # type: ignore
                    )

            raise ExchangeError(f"Coin '{coin}' not found in available trading pairs")

        return self.connection.retry_operation(_get_metadata)

    def get_positions(self) -> List[PositionInfo]:
        """
        Get current open positions.

        Returns:
            List[PositionInfo]: List of open positions
        """

        def _get_positions():
            user_state = self.connection.info.user_state(
                self.config.hyperliquid.account_address
            )
            positions = []

            for position in user_state.get("assetPositions", []):

                # position_sample_data = {
                #     "type": "oneWay",
                #     "position": {
                #         "coin": "ETH",
                #         "szi": "0.003",
                #         "leverage": {
                #             "type": "isolated",
                #             "value": 25,
                #             "rawUsd": "-11.080576",
                #         },
                #         "entryPx": "3845.9",
                #         "positionValue": "11.4921",
                #         "unrealizedPnl": "-0.0456",
                #         "returnOnEquity": "-0.0988065212",
                #         "liquidationPx": "3768.9034013605",
                #         "marginUsed": "0.411524",
                #         "maxLeverage": 25,
                #         "cumFunding": {
                #             "allTime": "87.082076",
                #             "sinceOpen": "0.0",
                #             "sinceChange": "0.0",
                #         },
                #     },
                # }

                if float(position["position"]["szi"]) != 0:  # Non-zero position
                    coin = position["position"]["coin"]
                    size = Decimal(str(position["position"]["szi"]))
                    entry_price = Decimal(str(position["position"]["entryPx"]))
                    mark_price = self.get_ticker(coin).mark_price
                    unrealized_pnl = Decimal(str(position["position"]["unrealizedPnl"]))
                    leverage = position["position"]["leverage"]["value"]
                    leverage_type = LeverageType(
                        position["position"]["leverage"]["type"]
                    )
                    margin_used = Decimal(str(position["position"]["marginUsed"]))
                    cum_funding = Decimal(
                        str(position["position"]["cumFunding"]["allTime"])
                    )

                    positions.append(
                        PositionInfo(
                            coin=coin,
                            size=size,
                            entry_price=entry_price,
                            mark_price=mark_price,
                            unrealized_pnl=unrealized_pnl,
                            leverage=leverage,
                            leverage_type=leverage_type,
                            margin_used=margin_used,
                            cum_funding=cum_funding,
                        )
                    )

            return positions

        return self.connection.retry_operation(_get_positions)

    def get_order_status(self, order_id: int) -> OrderInfo:
        """
        Get the status and details of an order by its ID.

        Args:
            order_id: Order identifier (integer OID)

        Returns:
            OrderInfo: Detailed order information

        Raises:
            ExchangeError: If order status query fails
        """

        def _get_order_status():
            try:
                user_address = self.config.hyperliquid.account_address
                result = self.connection.info.query_order_by_oid(user_address, order_id)

                print(result)

                if not result or not result.get("order"):
                    raise ExchangeError(f"Order {order_id} not found")

                # order_status_sample = {
                #     "status": "order",
                #     "order": {
                #         "order": {
                #             "coin": "ETH",
                #             "side": "B",
                #             "limitPx": "3700.0",
                #             "sz": "0.003",
                #             "oid": 220717680685,
                #             "timestamp": 1762141573004,
                #             "triggerCondition": "N/A",
                #             "isTrigger": False,
                #             "triggerPx": "0.0",
                #             "children": [],
                #             "isPositionTpsl": False,
                #             "reduceOnly": False,
                #             "orderType": "Limit",
                #             "origSz": "0.003",
                #             "tif": "Gtc",
                #             "cloid": None,
                #         },
                #         "status": "open",
                #         "statusTimestamp": 1762141573004,
                #     },
                # }

                # order_status_sample_cancel = {
                #     "status": "order",
                #     "order": {
                #         "order": {
                #             "coin": "ETH",
                #             "side": "B",
                #             "limitPx": "3842.3",
                #             "sz": "0.003",
                #             "oid": 217754135125,
                #             "timestamp": 1761876222838,
                #             "triggerCondition": "N/A",
                #             "isTrigger": False,
                #             "triggerPx": "0.0",
                #             "children": [],
                #             "isPositionTpsl": False,
                #             "reduceOnly": False,
                #             "orderType": "Limit",
                #             "origSz": "0.003",
                #             "tif": "Gtc",
                #             "cloid": None,
                #         },
                #         "status": "canceled",
                #         "statusTimestamp": 1761876248833,
                #     },
                # }

                # Extract order wrapper and actual order data from nested structure
                order_wrapper = result["order"]
                order_data = order_wrapper["order"]
                status_str = order_wrapper.get("status", "unknown").lower()

                # Map status strings to our enum
                if status_str == "open":
                    status = OrderStatus.OPEN
                elif status_str == "filled":
                    status = OrderStatus.FILLED
                elif status_str == "canceled":
                    status = OrderStatus.CANCELLED
                elif status_str in ("rejected", "failed"):
                    status = OrderStatus.REJECTED
                else:
                    status = OrderStatus.PARTIALLY_FILLED

                # Convert quantities and prices from API field names
                # Use origSz for original quantity, sz for current remaining quantity
                original_quantity = Decimal(str(order_data.get("origSz", "0")))
                current_quantity = Decimal(str(order_data.get("sz", "0")))
                filled_quantity = original_quantity - current_quantity
                remaining_quantity = current_quantity

                # Get limit price if available (limitPx is the API field name)
                limit_px = order_data.get("limitPx")
                price = Decimal(str(limit_px)) if limit_px and limit_px != "0" else None

                # Get average fill price if available
                avg_fill_px = order_data.get("averageFillPx")
                average_fill_price = Decimal(str(avg_fill_px)) if avg_fill_px else None

                # Convert TIF if available (tif field exists in API)
                tif_value = order_data.get("tif")
                time_in_force = OrderTif(tif_value.upper()) if tif_value else None

                # Determine order type from API orderType field
                order_type_str = order_data.get("orderType", "Limit").upper()
                order_type = (
                    OrderType.LIMIT if order_type_str == "LIMIT" else OrderType.MARKET
                )

                return OrderInfo(
                    order_id=order_id,
                    coin=order_data.get("coin", ""),
                    side=(
                        OrderSide.BUY
                        if order_data.get("side") == "B"
                        else OrderSide.SELL
                    ),
                    order_type=order_type,
                    quantity=original_quantity,
                    price=price,
                    filled_quantity=filled_quantity,
                    remaining_quantity=remaining_quantity,
                    average_fill_price=average_fill_price,
                    status=status,
                    timestamp=int(order_data.get("timestamp", 0)),
                    reduce_only=bool(order_data.get("reduceOnly", False)),
                    time_in_force=time_in_force,
                )

            except Exception as e:
                raise ExchangeError(f"Failed to get order status: {e}")

        return self.connection.retry_operation(_get_order_status)

    def submit_market_order(self, order: MarketOrder) -> OrderResult:
        """
        Submit a market order to the exchange.

        Args:
            order: MarketOrder object containing order parameters

        Returns:
            OrderResult: Result of the order submission

        Raises:
            ExchangeError: If order submission fails
        """

        def _submit_market_order():
            try:
                # Use market_open for buying, market_close for selling
                slippage = float(self.config.trading.default_slippage)
                if order.side.value == "buy":
                    result = self.connection.exchange.market_open(
                        name=order.coin,
                        is_buy=True,
                        sz=float(order.quantity),
                        px=None,  # Market price
                        slippage=slippage,
                    )
                else:  # sell
                    result = self.connection.exchange.market_close(
                        coin=order.coin,
                        sz=float(order.quantity),
                        px=None,  # Market price
                        slippage=slippage,
                    )

                # success_response = {
                #     "status": "ok",
                #     "response": {
                #         "type": "order",
                #         "data": {
                #             "statuses": [
                #                 {
                #                     "filled": {
                #                         "totalSz": "0.003",
                #                         "avgPx": "3593.5",
                #                         "oid": 221679167225,
                #                     }
                #                 }
                #             ]
                #         },
                #     },
                # }

                # Parse response
                if result.get("status") == "ok":
                    # Check individual order statuses from response.data
                    statuses = result.get("response", {}).get("data", {}).get("statuses", [])

                    for status in statuses:
                        if "resting" in status:
                            oid = status["resting"]["oid"]
                            return OrderResult(
                                success=True,
                                order_id=oid,
                                status=OrderStatus.OPEN,
                                message="Market order is resting on the book",
                            )
                        elif "error" in status:
                            error = status["error"]
                            return OrderResult(
                                success=False,
                                order_id=None,
                                status=OrderStatus.REJECTED,
                                message="Market order failed",
                                error=error,
                            )
                        elif "filled" in status:
                            fill = status["filled"]
                            return OrderResult(
                                success=True,
                                order_id=fill["oid"],
                                status=OrderStatus.FILLED,
                                message=f"Market order filled {fill['totalSz']} at {fill['avgPx']}",
                            )

                    # Fallback if no statuses found
                    return OrderResult(
                        success=False,
                        order_id=None,
                        status=OrderStatus.REJECTED,
                        message="Market order submission failed - no status returned",
                        error="Unknown response structure",
                    )
                else:
                    return OrderResult(
                        success=False,
                        status=OrderStatus.REJECTED,
                        message="Market order submission failed",
                        error=result.get("response", "Unknown error"),
                    )

            except Exception as e:
                return OrderResult(
                    success=False,
                    status=OrderStatus.REJECTED,
                    message="Market order submission failed",
                    error=str(e),
                )

        return self.connection.retry_operation(_submit_market_order)

    def submit_limit_order(self, order: LimitOrder) -> OrderResult:
        """
        Submit a limit order to the exchange.

        Args:
            order: LimitOrder object containing order parameters

        Returns:
            OrderResult: Result of the order submission

        Raises:
            ExchangeError: If order submission fails
        """

        def _submit_limit_order():
            try:
                result = self.connection.exchange.order(
                    name=order.coin,
                    is_buy=(order.side.value == "buy"),
                    sz=float(order.quantity),
                    limit_px=float(order.price),
                    order_type={
                        "limit": {
                            "tif": self._convert_tif_value(order.time_in_force),
                        }
                    },
                    reduce_only=order.reduce_only,
                )

                # success_response = {
                #     "status": "ok",
                #     "response": {
                #         "type": "order",
                #         "data": {"statuses": [{"resting": {"oid": 221678311701}}]},
                #     },
                # }

                # Parse response
                if result.get("status") == "ok":
                    # Check individual order statuses from response.data
                    statuses = result.get("response", {}).get("data", {}).get("statuses", [])

                    for status in statuses:
                        if "resting" in status:
                            oid = status["resting"]["oid"]
                            return OrderResult(
                                success=True,
                                order_id=oid,
                                status=OrderStatus.OPEN,
                                message="Limit order is resting on the book",
                            )
                        elif "error" in status:
                            error = status["error"]
                            return OrderResult(
                                success=False,
                                order_id=None,
                                status=OrderStatus.REJECTED,
                                message="Limit order failed",
                                error=error,
                            )
                        elif "filled" in status:
                            fill = status["filled"]
                            return OrderResult(
                                success=True,
                                order_id=fill["oid"],
                                status=OrderStatus.FILLED,
                                message=f"Limit order filled {fill['totalSz']} at {fill['avgPx']}",
                            )

                    # Fallback if no statuses found
                    return OrderResult(
                        success=False,
                        order_id=None,
                        status=OrderStatus.REJECTED,
                        message="Limit order submission failed - no status returned",
                        error="Unknown response structure",
                    )
                else:
                    return OrderResult(
                        success=False,
                        status=OrderStatus.REJECTED,
                        message="Limit order submission failed",
                        error=result.get("response", "Unknown error"),
                    )

            except Exception as e:
                return OrderResult(
                    success=False,
                    status=OrderStatus.REJECTED,
                    message="Limit order submission failed",
                    error=str(e),
                )

        return self.connection.retry_operation(_submit_limit_order)

    def _convert_tif_value(self, tif: OrderTif) -> Tif:
        if tif == OrderTif.GTC:
            return "Gtc"
        elif tif == OrderTif.IOC:
            return "Ioc"
        else:
            return "Alo"


__all__ = [
    "HyperliquidClient",
]
