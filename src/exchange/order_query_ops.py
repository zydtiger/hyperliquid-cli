"""
Order status, open orders, and order history query operations for HyperliquidClient.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from models.api import ExchangeError
from models.order import OrderHistoryEntry, OrderInfo, OrderStatus

from .helpers import (
    aggregate_fills_by_order,
    build_order_history_entries,
    build_order_history_from_fills,
)
from .order_parsing import parse_order_info, parse_order_status

if TYPE_CHECKING:
    from .hyperliquid_client import HyperliquidClient


def get_order_status(client: HyperliquidClient, order_id: int) -> OrderInfo:
    """Get the status and details of an order by its ID."""
    address = client.require_account_address()

    def _get_order_status() -> OrderInfo:
        try:
            result = client.connection.info.query_order_by_oid(address, order_id)
            if not result or not result.get("order"):
                raise ExchangeError(f"Order {order_id} not found")

            order_wrapper = result["order"]
            order_data = order_wrapper["order"]
            status = parse_order_status(str(order_wrapper.get("status", "unknown")))
            return parse_order_info(
                order_data,
                status=status,
                resolve_coin=client._resolve_coin_symbol,
                order_id=order_id,
            )
        except Exception as e:
            raise ExchangeError(f"Failed to get order status: {e}") from e

    return client.connection.retry_operation(_get_order_status)


def get_open_orders(client: HyperliquidClient) -> list[OrderInfo]:
    """Get all open orders using a single frontend_open_orders call."""
    address = client.require_account_address()

    def _get_open_orders() -> list[OrderInfo]:
        try:
            orders_data = client.connection.info.frontend_open_orders(address)
            return [
                parse_order_info(
                    order_data,
                    status=OrderStatus.OPEN,
                    resolve_coin=client._resolve_coin_symbol,
                )
                for order_data in orders_data
            ]
        except Exception as e:
            raise ExchangeError(f"Failed to get open orders: {e}") from e

    return client.connection.retry_operation(_get_open_orders)


def get_order_history(
    client: HyperliquidClient,
    limit: int,
    since_ms: int | None = None,
) -> list[OrderHistoryEntry]:
    """Get recent filled-order history, optionally bounded by ``since_ms``."""
    address = client.require_account_address()

    def _get_order_history() -> list[OrderHistoryEntry]:
        try:
            if since_ms is not None:
                fills = client.connection.info.user_fills_by_time(address, since_ms)
                resolved_fills = [
                    {
                        **fill,
                        "coin": client._resolve_coin_symbol(str(fill.get("coin", ""))),
                    }
                    for fill in fills
                    if int(fill.get("time", 0)) >= since_ms
                ]
                fills_by_order = aggregate_fills_by_order(resolved_fills)
                return build_order_history_from_fills(fills_by_order, limit)

            historical_orders = sorted(
                client.connection.info.historical_orders(address),
                key=lambda entry: int(entry.get("statusTimestamp") or 0),
                reverse=True,
            )
            filled_entries = [
                entry
                for entry in historical_orders
                if str(entry.get("status", "")).lower() == OrderStatus.FILLED.value
            ]
            if not filled_entries:
                return []

            candidate_count = min(limit, len(filled_entries))
            while candidate_count > 0:
                start_time = int(filled_entries[candidate_count - 1].get("statusTimestamp") or 0)
                fills = client.connection.info.user_fills_by_time(address, start_time)
                fills_by_order = aggregate_fills_by_order(
                    [
                        {
                            **fill,
                            "coin": client._resolve_coin_symbol(str(fill.get("coin", ""))),
                        }
                        for fill in fills
                    ]
                )
                rows = build_order_history_entries(
                    filled_entries[:candidate_count],
                    fills_by_order,
                    limit,
                    resolve_coin=client._resolve_coin_symbol,
                )
                if len(rows) >= limit or candidate_count == len(filled_entries):
                    return rows

                candidate_count = min(
                    len(filled_entries),
                    candidate_count + (limit - len(rows)),
                )

            return []
        except Exception as e:
            raise ExchangeError(f"Failed to get order history: {e}") from e

    return client.connection.retry_operation(_get_order_history)
