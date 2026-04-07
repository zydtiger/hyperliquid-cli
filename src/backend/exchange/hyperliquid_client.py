"""
Hyperliquid client for interacting with the exchange API.

This module provides a high-level client interface for the Hyperliquid exchange,
handling data retrieval and portfolio management operations.
"""

from decimal import Decimal
from typing import cast

from hyperliquid.utils.signing import OrderType as ExchangeOrderType
from hyperliquid.utils.signing import Tif

from models.api import (
    BalanceInfo,
    CoinMetadata,
    ExchangeError,
    LeverageType,
    PositionInfo,
    SpotBalance,
    StakingInfo,
    Ticker,
)
from models.config import Config
from models.leverage import LeverageResult
from models.order import (
    LimitOrder,
    MarketOrder,
    OrderInfo,
    OrderResult,
    OrderSide,
    OrderStatus,
    OrderTif,
    OrderTrigger,
    OrderType,
    TriggerType,
)

from .hyperliquid_connection import HyperliquidConnection

MIN_LEVERAGE = 1
MAX_LEVERAGE = 250


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

    def get_available_coins(self) -> list[str]:
        """
        Get list of available trading coins.

        Returns:
            List[str]: List of available coin symbols
        """

        def _get_available_coins() -> list[str]:
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

        def _get_ticker() -> Ticker:
            meta, asset_ctxs = self.connection.info.meta_and_asset_ctxs()
            if not meta or "universe" not in meta:
                raise ExchangeError("Failed to retrieve market metadata from exchange")

            available_coins = [asset["name"] for asset in meta["universe"]]
            if coin not in available_coins:
                raise ExchangeError(f"Coin '{coin}' not found in available trading pairs")

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

        def _get_metadata() -> CoinMetadata:
            meta = self.connection.info.meta()
            if not meta or "universe" not in meta:
                raise ExchangeError("Failed to retrieve market metadata from exchange")

            for asset in meta["universe"]:
                if asset["name"] == coin:
                    max_leverage = asset.get("maxLeverage")
                    if max_leverage is None:
                        raise ExchangeError(f"Missing max leverage metadata for coin '{coin}'")
                    return CoinMetadata(
                        coin=asset["name"],
                        size_decimals=asset["szDecimals"],
                        max_leverage=max_leverage,
                    )

            raise ExchangeError(f"Coin '{coin}' not found in available trading pairs")

        return self.connection.retry_operation(_get_metadata)

    def get_balances(self) -> BalanceInfo:
        """
        Get comprehensive balance information for the account.

        Returns:
            BalanceInfo: Comprehensive balance information including perpetuals, spot, and staking

        Raises:
            ExchangeError: If balance retrieval fails
        """

        def _get_balances() -> BalanceInfo:
            try:
                # Get perpetuals account data from user_state
                user_state = self.connection.info.user_state(
                    self.config.hyperliquid.account_address
                )

                # sample_user_state = {
                #     "marginSummary": {
                #         "accountValue": "3451.743653",
                #         "totalNtlPos": "10.8642",
                #         "totalRawUsd": "3440.879453",
                #         "totalMarginUsed": "0.418932",
                #     },
                #     "crossMarginSummary": {
                #         "accountValue": "3451.324721",
                #         "totalNtlPos": "0.0",
                #         "totalRawUsd": "3451.324721",
                #         "totalMarginUsed": "0.0",
                #     },
                #     "crossMaintenanceMarginUsed": "0.0",
                #     "withdrawable": "3451.324721",
                #     "assetPositions": [
                #         {
                #             "type": "oneWay",
                #             "position": {
                #                 "coin": "ETH",
                #                 "szi": "0.003",
                #                 "leverage": {
                #                     "type": "isolated",
                #                     "value": 25,
                #                     "rawUsd": "-10.445268",
                #                 },
                #                 "entryPx": "3625.3",
                #                 "positionValue": "10.8642",
                #                 "unrealizedPnl": "-0.0117",
                #                 "returnOnEquity": "-0.026894326",
                #                 "liquidationPx": "3552.812244898",
                #                 "marginUsed": "0.418932",
                #                 "maxLeverage": 25,
                #                 "cumFunding": {
                #                     "allTime": "87.084461",
                #                     "sinceOpen": "0.0",
                #                     "sinceChange": "0.0",
                #                 },
                #             },
                #         }
                #     ],
                #     "time": 1762232186476,
                # }

                # Extract perpetuals data
                margin_summary = user_state.get("marginSummary", {})

                perps_data = {
                    "account_value": Decimal(margin_summary.get("accountValue", "0")),
                    "total_position_value": Decimal(margin_summary.get("totalNtlPos", "0")),
                    "total_raw_usd": Decimal(margin_summary.get("totalRawUsd", "0")),
                    "margin_used": Decimal(margin_summary.get("totalMarginUsed", "0")),
                    "withdrawable": Decimal(user_state.get("withdrawable", "0")),
                }

                # Get spot balances
                spot_balances = []
                try:
                    spot_state = self.connection.info.spot_user_state(
                        self.config.hyperliquid.account_address
                    )

                    # sample_spot_state = {
                    #     "balances": [
                    #         {
                    #             "coin": "USDC",
                    #             "token": 0,
                    #             "total": "89.12677146",
                    #             "hold": "0.0",
                    #             "entryNtl": "0.0",
                    #         },
                    #         {
                    #             "coin": "HYPE",
                    #             "token": 150,
                    #             "total": "0.0",
                    #             "hold": "0.0",
                    #             "entryNtl": "0.0",
                    #         },
                    #         {
                    #             "coin": "UETH",
                    #             "token": 221,
                    #             "total": "0.002998111",
                    #             "hold": "0.0",
                    #             "entryNtl": "10.8831",
                    #         },
                    #     ]
                    # }

                    holding_data = spot_state.get("balances", [])

                    for holding in holding_data:
                        if Decimal(holding.get("total", "0")) != 0:
                            spot_balances.append(
                                SpotBalance(
                                    coin=holding["coin"],
                                    total=Decimal(holding["total"]),
                                )
                            )
                except Exception:
                    # If spot data retrieval fails, continue with empty spot balances
                    spot_balances = []

                # Get staking information
                staking_info = None
                try:
                    staking_summary = self.connection.info.user_staking_summary(
                        self.config.hyperliquid.account_address
                    )

                    # sample_staking_summary = {
                    #     "delegated": "100.61607572",
                    #     "undelegated": "0.0",
                    #     "totalPendingWithdrawal": "0.0",
                    #     "nPendingWithdrawals": 0,
                    # }

                    staking_info = StakingInfo(
                        delegated_amount=Decimal(staking_summary.get("delegated", "0")),
                        undelegated_amount=Decimal(staking_summary.get("undelegated", "0")),
                        pending_withdrawals=Decimal(
                            staking_summary.get("totalPendingWithdrawal", "0")
                        ),
                        pending_withdrawal_count=staking_summary.get("nPendingWithdrawals", 0),
                    )
                except Exception:
                    # If staking data retrieval fails, continue with None
                    staking_info = None

                return BalanceInfo(
                    perps_account_value=perps_data["account_value"],
                    perps_total_position_value=perps_data["total_position_value"],
                    perps_total_raw_usd=perps_data["total_raw_usd"],
                    perps_margin_used=perps_data["margin_used"],
                    perps_withdrawable=perps_data["withdrawable"],
                    spot_balances=spot_balances,
                    staking_info=staking_info,
                )

            except Exception as e:
                raise ExchangeError(f"Failed to get balance information: {e}") from e

        return self.connection.retry_operation(_get_balances)

    def get_positions(self) -> list[PositionInfo]:
        """
        Get current open positions.

        Returns:
            List[PositionInfo]: List of open positions
        """

        def _get_positions() -> list[PositionInfo]:
            user_state = self.connection.info.user_state(self.config.hyperliquid.account_address)
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
                    leverage_type = LeverageType(position["position"]["leverage"]["type"])
                    margin_used = Decimal(str(position["position"]["marginUsed"]))
                    cum_funding = Decimal(str(position["position"]["cumFunding"]["allTime"]))

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

        def _get_order_status() -> OrderInfo:
            try:
                user_address = self.config.hyperliquid.account_address
                result = self.connection.info.query_order_by_oid(user_address, order_id)

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
                order_type = OrderType.LIMIT if order_type_str == "LIMIT" else OrderType.MARKET
                trigger = self._extract_order_trigger(order_data)

                return OrderInfo(
                    order_id=order_id,
                    coin=order_data.get("coin", ""),
                    side=(OrderSide.BUY if order_data.get("side") == "B" else OrderSide.SELL),
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
                    trigger=trigger,
                )

            except Exception as e:
                raise ExchangeError(f"Failed to get order status: {e}") from e

        return self.connection.retry_operation(_get_order_status)

    def get_open_orders(self) -> list[OrderInfo]:
        """
        Get all open orders for the account.

        Returns:
            List[OrderInfo]: List of open orders with full details

        Raises:
            ExchangeError: If open orders retrieval fails
        """

        def _get_open_orders() -> list[OrderInfo]:
            try:
                # Get open orders list from the API
                orders_data = self.connection.info.open_orders(
                    self.config.hyperliquid.account_address
                )

                # sample_open_orders = [
                #     {
                #         "coin": "ETH",
                #         "side": "B",
                #         "limitPx": "3000.0",
                #         "sz": "0.003",
                #         "oid": 222605232959,
                #         "timestamp": 1762271506632,
                #         "origSz": "0.003",
                #     }
                # ]

                open_orders = []
                for order_data in orders_data:
                    # Extract order ID and get full order details using existing method
                    order_id = order_data["oid"]
                    order_info = self.get_order_status(order_id)
                    open_orders.append(order_info)

                return open_orders

            except Exception as e:
                raise ExchangeError(f"Failed to get open orders: {e}") from e

        return self.connection.retry_operation(_get_open_orders)

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

        def _submit_market_order() -> OrderResult:
            try:
                if order.trigger is not None:
                    result = self.connection.exchange.order(
                        name=order.coin,
                        is_buy=(order.side.value == "buy"),
                        sz=float(order.quantity),
                        limit_px=self._get_trigger_market_limit_px(order),
                        order_type=self._build_trigger_order_type(order.trigger, is_market=True),
                        reduce_only=order.reduce_only,
                    )
                    return self._parse_order_submission_result(result, "Market order")

                # Use market_open for non-reduce-only orders, market_close for reduce-only orders
                slippage = float(self.config.trading.default_slippage)
                if order.reduce_only:
                    result = self.connection.exchange.market_close(
                        coin=order.coin,
                        sz=float(order.quantity),
                        px=None,  # Market price
                        slippage=slippage,
                    )
                else:
                    result = self.connection.exchange.market_open(
                        name=order.coin,
                        is_buy=(order.side.value == "buy"),
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

                return self._parse_order_submission_result(result, "Market order")

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

        def _submit_limit_order() -> OrderResult:
            try:
                order_type: ExchangeOrderType
                if order.trigger is not None:
                    order_type = self._build_trigger_order_type(order.trigger, is_market=False)
                else:
                    order_type = cast(
                        ExchangeOrderType,
                        {
                            "limit": {
                                "tif": self._convert_tif_value(order.time_in_force),
                            }
                        },
                    )

                result = self.connection.exchange.order(
                    name=order.coin,
                    is_buy=(order.side.value == "buy"),
                    sz=float(order.quantity),
                    limit_px=float(order.price),
                    order_type=order_type,
                    reduce_only=order.reduce_only,
                )

                # success_response = {
                #     "status": "ok",
                #     "response": {
                #         "type": "order",
                #         "data": {"statuses": [{"resting": {"oid": 221678311701}}]},
                #     },
                # }

                return self._parse_order_submission_result(result, "Limit order")

            except Exception as e:
                return OrderResult(
                    success=False,
                    status=OrderStatus.REJECTED,
                    message="Limit order submission failed",
                    error=str(e),
                )

        return self.connection.retry_operation(_submit_limit_order)

    def cancel_order(self, order_id: int | str) -> OrderResult:
        """
        Cancel a specific order or all open orders.

        Args:
            order_id: Order ID (int) to cancel, or "all" to cancel all open orders

        Returns:
            OrderResult: Result of the cancellation operation

        Raises:
            ValueError: If order_id is invalid
            ExchangeError: If cancellation fails
        """

        def _cancel_order() -> OrderResult:
            if order_id == "all":
                return self._cancel_all_orders()
            if isinstance(order_id, int) and order_id > 0:
                return self._cancel_specific_order(order_id)
            raise ValueError("order_id must be positive integer or 'all'")

        return self.connection.retry_operation(_cancel_order)

    def _cancel_specific_order(self, order_id: int) -> OrderResult:  # noqa: PLR0911
        """
        Cancel a specific order by ID.

        Args:
            order_id: Order ID to cancel

        Returns:
            OrderResult: Result of the cancellation
        """
        # First get order details to check status and find the coin
        order_info = self.get_order_status(order_id)

        # Check if order is open - only open orders can be cancelled
        if order_info.status != OrderStatus.OPEN:
            if order_info.status == OrderStatus.CANCELLED:
                return OrderResult(
                    success=False,
                    order_id=order_id,
                    status=order_info.status,
                    message=f"Order {order_id} cancellation failed",
                    error=f"Order {order_id} is already cancelled",
                )
            if order_info.status == OrderStatus.FILLED:
                return OrderResult(
                    success=False,
                    order_id=order_id,
                    status=order_info.status,
                    message=f"Order {order_id} cancellation failed",
                    error=f"Order {order_id} is already filled",
                )
            if order_info.status == OrderStatus.REJECTED:
                return OrderResult(
                    success=False,
                    order_id=order_id,
                    status=order_info.status,
                    message=f"Order {order_id} cancellation failed",
                    error=f"Order {order_id} was already rejected",
                )
            return OrderResult(
                success=False,
                order_id=order_id,
                status=order_info.status,
                message=f"Order {order_id} cancellation failed",
                error=f"Order {order_id} is {order_info.status.value} and cannot be cancelled",
            )

        # Cancel the order using the exchange API
        result = self.connection.exchange.cancel(order_info.coin, order_id)

        # sample_result = {
        #     "status": "ok",
        #     "response": {"type": "cancel", "data": {"statuses": ["success"]}},
        # }

        # Parse the response
        if result.get("status") == "ok":
            # Check individual order statuses from response.data
            statuses = result.get("response", {}).get("data", {}).get("statuses", [])

            for status in statuses:
                if status == "success":
                    # Order was successfully cancelled
                    return OrderResult(
                        success=True,
                        order_id=order_id,
                        status=OrderStatus.CANCELLED,
                        message=f"Order {order_id} cancelled successfully",
                    )
                if isinstance(status, dict) and "error" in status:
                    # Order cancellation failed
                    error = status["error"]
                    return OrderResult(
                        success=False,
                        order_id=order_id,
                        status=OrderStatus.REJECTED,
                        message="Order cancellation failed",
                        error=error,
                    )

            # Fallback if no statuses found but status was ok
            return OrderResult(
                success=True,
                order_id=order_id,
                status=OrderStatus.CANCELLED,
                message=f"Order {order_id} cancelled successfully",
            )
        return OrderResult(
            success=False,
            order_id=order_id,
            status=OrderStatus.REJECTED,
            message="Order cancellation failed",
            error=result.get("response", "Unknown error"),
        )

    def _cancel_all_orders(self) -> OrderResult:
        """
        Cancel all open orders.

        Returns:
            OrderResult: Result of the batch cancellation
        """
        # Get all open orders
        open_orders = self.get_open_orders()

        cancelled_orders = []
        failed_orders = []

        for order_info in open_orders:
            try:
                # Reuse _cancel_specific_order for each open order
                result = self._cancel_specific_order(order_info.order_id)
                if result.success:
                    cancelled_orders.append(
                        {
                            "order_id": order_info.order_id,
                            "coin": order_info.coin,
                            "status": "cancelled",
                        }
                    )
                else:
                    failed_orders.append(
                        {
                            "order_id": order_info.order_id,
                            "coin": order_info.coin,
                            "error": result.error or "Unknown error",
                        }
                    )
            except Exception as e:
                failed_orders.append(
                    {
                        "order_id": order_info.order_id,
                        "coin": order_info.coin,
                        "error": str(e),
                    }
                )

        return OrderResult(
            success=len(failed_orders) == 0,
            status=OrderStatus.CANCELLED,
            message=f"Cancelled {len(cancelled_orders)} orders, {len(failed_orders)} failed",
            error=(f"{len(failed_orders)} orders failed to cancel" if failed_orders else None),
        )

    def modify_order(
        self,
        order_id: int,
        price: Decimal | None = None,
        quantity: Decimal | None = None,
    ) -> OrderResult:
        """
        Modify price and/or quantity of an existing open limit order.

        Args:
            order_id: Order ID to modify
            price: New price (None to keep current price)
            quantity: New quantity (None to keep current quantity)

        Returns:
            OrderResult: Result of the modification operation

        Raises:
            ExchangeError: If order modification fails
            ValueError: If order is not an open limit order
        """

        # Early exit if no changes requested
        if price is None and quantity is None:
            return OrderResult(
                success=False,
                order_id=order_id,
                status=OrderStatus.REJECTED,
                message="Order modification failed",
                error="No changes requested - both price and quantity are None",
            )

        def _modify_order() -> OrderResult:
            try:
                # Get current order info to validate and extract current values
                current_order = self.get_order_status(order_id)

                # Validate order is open limit order
                if current_order.status != OrderStatus.OPEN:
                    if current_order.status == OrderStatus.CANCELLED:
                        raise ValueError(
                            f"Order {order_id} is already cancelled and cannot be modified"
                        )
                    if current_order.status == OrderStatus.FILLED:
                        raise ValueError(
                            f"Order {order_id} is already filled and cannot be modified"
                        )
                    if current_order.status == OrderStatus.REJECTED:
                        raise ValueError(f"Order {order_id} was rejected and cannot be modified")
                    raise ValueError(
                        f"Order {order_id} is {current_order.status.value} and cannot be modified"
                    )

                if current_order.order_type != OrderType.LIMIT:
                    raise ValueError(
                        f"Order {order_id} is a {current_order.order_type.value} "
                        "order and cannot be modified (only limit orders can be modified)"
                    )

                # Use current values if None provided
                new_price = price if price is not None else current_order.price
                new_quantity = (
                    quantity if quantity is not None else current_order.remaining_quantity
                )

                # Validate that we have both price and quantity for limit order
                if new_price is None:
                    raise ValueError("Price is required for limit order modification")
                if new_quantity <= 0:
                    raise ValueError("Quantity must be greater than 0")

                # Submit modification using the exchange API
                result = self.connection.exchange.modify_order(
                    oid=order_id,
                    name=current_order.coin,
                    is_buy=current_order.side == OrderSide.BUY,
                    sz=float(new_quantity),
                    limit_px=float(new_price),
                    order_type={
                        "limit": {
                            "tif": self._convert_tif_value(
                                current_order.time_in_force or OrderTif.GTC
                            )
                        }
                    },
                )

                # sample_result = {
                #     "status": "ok",
                #     "response": {
                #         "type": "order",
                #         "data": {"statuses": [{"resting": {"oid": 224350915859}}]},
                #     },
                # }

                # Parse the response
                if result.get("status") == "ok":
                    # Check individual order statuses from response.data
                    statuses = result.get("response", {}).get("data", {}).get("statuses", [])

                    for status in statuses:
                        if "resting" in status:
                            # Order was successfully modified and is resting on the book
                            # Extract the new order ID from the response.
                            # Fall back to the original if not provided.
                            new_order_id = status["resting"].get("oid", order_id)
                            return OrderResult(
                                success=True,
                                order_id=new_order_id,
                                status=OrderStatus.OPEN,
                                message=(
                                    f"Order {order_id} modified successfully - "
                                    f"price: {new_price}, quantity: {new_quantity}"
                                ),
                            )
                        if "error" in status:
                            error = status["error"]
                            return OrderResult(
                                success=False,
                                order_id=order_id,
                                status=OrderStatus.REJECTED,
                                message="Order modification failed",
                                error=error,
                            )

                    # Fallback if no statuses found but status was ok
                    return OrderResult(
                        success=True,
                        order_id=order_id,
                        status=OrderStatus.OPEN,
                        message=(
                            f"Order {order_id} modified successfully - "
                            f"price: {new_price}, quantity: {new_quantity}"
                        ),
                    )
                return OrderResult(
                    success=False,
                    order_id=order_id,
                    status=OrderStatus.REJECTED,
                    message="Order modification failed",
                    error=result.get("response", "Unknown error"),
                )

            except Exception as e:
                return OrderResult(
                    success=False,
                    order_id=order_id,
                    status=OrderStatus.REJECTED,
                    message="Order modification failed",
                    error=str(e),
                )

        return self.connection.retry_operation(_modify_order)

    def change_leverage(self, leverage: int, coin: str, is_cross: bool = True) -> LeverageResult:
        """
        Change leverage for a specific position.

        Args:
            leverage: Target leverage multiplier (1-250)
            coin: Symbol of the cryptocurrency
            is_cross: Whether to use cross margin (True) or isolated margin (False)

        Returns:
            LeverageResult: Result of the leverage modification operation

        Raises:
            ExchangeError: If leverage modification fails
        """

        def _change_leverage() -> LeverageResult:
            try:
                # Validate leverage value
                if (
                    not isinstance(leverage, int)
                    or leverage < MIN_LEVERAGE
                    or leverage > MAX_LEVERAGE
                ):
                    return LeverageResult(
                        success=False,
                        message=(
                            f"Invalid leverage value: {leverage}. "
                            f"Must be an integer between {MIN_LEVERAGE} and {MAX_LEVERAGE}"
                        ),
                        updated_position=None,
                    )

                # Validate coin symbol
                if not coin or not isinstance(coin, str):
                    return LeverageResult(
                        success=False,
                        message="Invalid coin symbol: must be a non-empty string",
                        updated_position=None,
                    )

                # Update leverage via exchange connection
                result = self.connection.exchange.update_leverage(leverage, coin, is_cross)

                # success_response = {"status": "ok", "response": {"type": "default"}}

                # error_response_1 = {
                #     "status": "err",
                #     "response": "Cannot switch leverage type with open position.",
                # }

                # error_response_2 = {
                #     "status": "err",
                #     "response": (
                #         "Isolated position does not have sufficient margin "
                #         "available to decrease leverage. To decrease leverage, "
                #         "add margin to the position."
                #     ),
                # }

                if result.get("status") == "ok":
                    # Get updated position information
                    try:
                        updated_positions = self.get_positions()
                        updated_position = None
                        for position in updated_positions:
                            if position.coin == coin:
                                updated_position = position
                                break
                    except Exception:
                        # If updated positions cannot be fetched, the leverage
                        # change still succeeded and the result remains valid.
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

                # Handle specific error messages with better user feedback
                if "Cannot switch leverage type with open position" in str(error_response):
                    error_msg = (
                        f"Cannot switch leverage type for {coin} with open position. "
                        "Close the position first or use the same margin type."
                    )
                elif (
                    "isolated position does not have sufficient margin"
                    in str(error_response).lower()
                ):
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

        return self.connection.retry_operation(_change_leverage)

    def _convert_tif_value(self, tif: OrderTif) -> Tif:
        if tif == OrderTif.GTC:
            return "Gtc"
        if tif == OrderTif.IOC:
            return "Ioc"
        return "Alo"

    def _build_trigger_order_type(
        self,
        trigger: OrderTrigger,
        *,
        is_market: bool,
    ) -> ExchangeOrderType:
        return cast(
            ExchangeOrderType,
            {
                "trigger": {
                    "triggerPx": float(trigger.trigger_price),
                    "isMarket": is_market,
                    "tpsl": self._convert_trigger_type(trigger.trigger_type),
                }
            },
        )

    def _convert_trigger_type(self, trigger_type: TriggerType) -> str:
        if trigger_type == TriggerType.STOP:
            return "sl"
        return "tp"

    def _get_trigger_market_limit_px(self, order: MarketOrder) -> float:
        slippage = float(self.config.trading.default_slippage)
        return float(
            self.connection.exchange._slippage_price(  # type: ignore[attr-defined]
                order.coin,
                order.side == OrderSide.BUY,
                slippage,
                None,
            )
        )

    def _extract_order_trigger(self, order_data: dict) -> OrderTrigger | None:
        if not order_data.get("isTrigger"):
            return None

        trigger_px = order_data.get("triggerPx")
        if trigger_px in (None, "0", "0.0"):
            return None

        trigger_type = self._parse_trigger_type(
            order_data.get("triggerCondition"),
            OrderSide.BUY if order_data.get("side") == "B" else OrderSide.SELL,
        )
        if trigger_type is None:
            return None

        return OrderTrigger(
            trigger_price=Decimal(str(trigger_px)),
            trigger_type=trigger_type,
        )

    def _parse_trigger_type(  # noqa: PLR0911
        self,
        trigger_condition: str | None,
        side: OrderSide,
    ) -> TriggerType | None:
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

    def _parse_order_submission_result(self, result: dict, order_label: str) -> OrderResult:
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


__all__ = [
    "HyperliquidClient",
]
