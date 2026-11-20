"""
Comprehensive unit tests for HyperliquidClient.get_portfolio and portfolio helpers.

Uses purely synthetic fixtures; never reads real user configuration or keys.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any
from unittest.mock import Mock, patch

import pytest

from exchange.hyperliquid_client import HyperliquidClient
from exchange.hyperliquid_connection import HyperliquidConnection
from exchange.portfolio_pricing import (
    extract_spot_prices_and_symbols,
    parse_abstraction_mode,
)
from models.api import ExchangeError
from models.config import Config, HyperliquidConfig, NetworkType


def _sample_spot_meta_and_ctxs() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Synthetic spotMetaAndAssetCtxs payload covering USDC, HYPE, UETH, and PURR."""
    spot_meta = {
        "tokens": [
            {"name": "USDC", "index": 0, "szDecimals": 8, "weiDecimals": 8},
            {"name": "PURR", "index": 1, "szDecimals": 0, "weiDecimals": 5},
            {"name": "HYPE", "index": 150, "szDecimals": 2, "weiDecimals": 8},
            {"name": "UETH", "index": 221, "szDecimals": 4, "weiDecimals": 8},
        ],
        "universe": [
            {"name": "PURR/USDC", "tokens": [1, 0], "index": 0, "isCanonical": True},
            {"name": "@107", "tokens": [150, 0], "index": 107, "isCanonical": True},
            {"name": "@151", "tokens": [221, 0], "index": 151, "isCanonical": True},
        ],
    }
    spot_ctxs = [
        {"coin": "PURR/USDC", "markPx": "0.25", "midPx": "0.24"},
        {"coin": "@107", "markPx": "25.0", "midPx": "24.9"},
        {"coin": "@151", "markPx": "3000.0", "midPx": "2999.5"},
    ]
    return spot_meta, spot_ctxs


def _sample_perp_meta_and_ctxs() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Synthetic perp meta_and_asset_ctxs payload."""
    meta = {
        "universe": [
            {"name": "BTC", "szDecimals": 5, "maxLeverage": 50},
            {"name": "ETH", "szDecimals": 4, "maxLeverage": 25},
            {"name": "SOL", "szDecimals": 2, "maxLeverage": 20},
            {"name": "HYPE", "szDecimals": 2, "maxLeverage": 10},
        ]
    }
    ctxs = [
        {"markPx": "50000.0", "funding": "0.0001", "openInterest": "1000"},
        {"markPx": "3000.0", "funding": "0.0001", "openInterest": "2000"},
        {"markPx": "150.0", "funding": "0.0001", "openInterest": "5000"},
        {"markPx": "24.5", "funding": "0.0001", "openInterest": "3000"},
    ]
    return meta, ctxs


def _sample_standard_user_state() -> dict[str, Any]:
    """Synthetic clearinghouseState with one cross LONG (BTC) and one isolated SHORT (ETH)."""
    return {
        "marginSummary": {
            "accountValue": "4000.0",
            "totalNtlPos": "8000.0",
            "totalRawUsd": "-4000.0",
            "totalMarginUsed": "1200.0",
        },
        "crossMarginSummary": {
            "accountValue": "3500.0",
            "totalNtlPos": "5000.0",
            "totalRawUsd": "-1500.0",
            "totalMarginUsed": "500.0",
        },
        "crossMaintenanceMarginUsed": "125.5",
        "withdrawable": "2800.0",
        "assetPositions": [
            {
                "type": "oneWay",
                "position": {
                    "coin": "BTC",
                    "szi": "0.1",
                    "leverage": {"type": "cross", "value": 10},
                    "entryPx": "48000.0",
                    "positionValue": "5000.0",
                    "unrealizedPnl": "200.0",
                    "returnOnEquity": "0.4",
                    "liquidationPx": "15000.0",
                    "marginUsed": "500.0",
                    "maxLeverage": 50,
                    "cumFunding": {"allTime": "12.5", "sinceOpen": "1.5"},
                },
            },
            {
                "type": "oneWay",
                "position": {
                    "coin": "ETH",
                    "szi": "-1.0",
                    "leverage": {"type": "isolated", "value": 6, "rawUsd": "3500.0"},
                    "entryPx": "3100.0",
                    "positionValue": "3000.0",
                    "unrealizedPnl": "100.0",
                    "returnOnEquity": "0.2",
                    "liquidationPx": "3450.0",
                    "marginUsed": "500.0",
                    "maxLeverage": 25,
                    "cumFunding": {"allTime": "-3.0", "sinceOpen": "-0.5"},
                },
            },
            {
                "type": "oneWay",
                "position": {
                    "coin": "SOL",
                    "szi": "0.0",
                    "leverage": {"type": "cross", "value": 10},
                    "entryPx": "100.0",
                    "positionValue": "0.0",
                    "unrealizedPnl": "0.0",
                    "marginUsed": "0.0",
                    "cumFunding": {"allTime": "0.0"},
                },
            },
        ],
    }


def _configure_full_mock(
    mock_connection: Mock,
    mock_retry_operation: Callable[..., Any],
    *,
    abstraction_mode: str | None = "disabled",
    user_state: dict[str, Any] | None = None,
    spot_balances: list[dict[str, Any]] | None = None,
    staking_summary: dict[str, Any] | None = None,
    vault_equities: list[dict[str, Any]] | None = None,
    open_orders: list[dict[str, Any]] | None = None,
    fills: list[dict[str, Any]] | None = None,
) -> Mock:
    """Populate mock_connection.info with synthetic portfolio responses."""
    mock_info: Mock = mock_connection.info
    mock_connection.retry_operation.side_effect = mock_retry_operation

    mock_info.user_state.return_value = (
        user_state if user_state is not None else _sample_standard_user_state()
    )
    mock_info.meta_and_asset_ctxs.return_value = _sample_perp_meta_and_ctxs()
    mock_info.query_user_abstraction_state.return_value = abstraction_mode
    mock_info.spot_meta_and_asset_ctxs.return_value = _sample_spot_meta_and_ctxs()
    mock_info.spot_user_state.return_value = {
        "balances": spot_balances
        if spot_balances is not None
        else [
            {"coin": "USDC", "token": 0, "total": "2000.0", "hold": "100.0", "entryNtl": "0.0"},
            {"coin": "HYPE", "token": 150, "total": "100.0", "hold": "10.0", "entryNtl": "1800.0"},
            {"coin": "UETH", "token": 221, "total": "0.5", "hold": "0.0", "entryNtl": "1400.0"},
            {"coin": "ZERO", "token": 99, "total": "0.0", "hold": "0.0", "entryNtl": "0.0"},
        ]
    }
    mock_info.user_staking_summary.return_value = (
        staking_summary
        if staking_summary is not None
        else {
            "delegated": "80.0",
            "undelegated": "15.0",
            "totalPendingWithdrawal": "5.0",
            "nPendingWithdrawals": 1,
        }
    )
    mock_info.user_staking_delegations.return_value = [
        {"validator": "0xval1", "amount": "80.0"},
        {"validator": "0xval0", "amount": "0.0"},
    ]
    mock_info.user_staking_rewards.return_value = [
        {"time": 1762271507000, "source": "delegation", "totalAmount": "1.5"},
        {"time": 1762271508000, "source": "delegation", "totalAmount": "0.75"},
    ]
    mock_info.post.return_value = [
        {"validator": "0xval1", "name": "Validator One", "commission": "0.05"},
    ]
    mock_info.user_vault_equities.return_value = (
        vault_equities
        if vault_equities is not None
        else [
            {"vaultAddress": "0xhlpvault", "equity": "1000.0"},
            {"vaultAddress": "0xemptyvault", "equity": "0.0"},
        ]
    )
    mock_info.frontend_open_orders.return_value = (
        open_orders
        if open_orders is not None
        else [
            {
                "coin": "@107",
                "side": "B",
                "limitPx": "24.0",
                "sz": "5.0",
                "oid": 9001,
                "timestamp": 1762271506000,
                "origSz": "5.0",
                "reduceOnly": False,
                "orderType": "Limit",
                "tif": "Gtc",
                "isTrigger": False,
            }
        ]
    )

    now_ms = int(datetime.now().astimezone().timestamp() * 1000)
    mock_info.user_fills_by_time.return_value = (
        fills
        if fills is not None
        else [
            {
                "oid": 1001,
                "coin": "BTC",
                "side": "B",
                "dir": "Open Long",
                "px": "48000.0",
                "sz": "0.1",
                "fee": "1.68",
                "feeToken": "USDC",
                "closedPnl": "0.0",
                "time": now_ms,
            },
            {
                "oid": 1002,
                "coin": "@107",
                "side": "B",
                "dir": "Buy",
                "px": "25.0",
                "sz": "20.0",
                "fee": "0.02",
                "feeToken": "HYPE",
                "closedPnl": "0.0",
                "time": now_ms,
            },
            {
                "oid": 1003,
                "coin": "SOL",
                "side": "A",
                "dir": "Close Long",
                "px": "155.0",
                "sz": "10.0",
                "fee": "0.50",
                "feeToken": "USDC",
                "closedPnl": "42.5",
                "time": now_ms,
            },
            {
                "oid": 1004,
                "coin": "PURR/USDC",
                "side": "A",
                "dir": "Sell",
                "px": "0.25",
                "sz": "100.0",
                "fee": "0.01",
                "feeToken": "USDC",
                "closedPnl": "5.0",
                "time": now_ms,
            },
            {
                # Prior-day fill should be excluded by start_ms filter
                "oid": 999,
                "coin": "DOGE",
                "side": "B",
                "dir": "Open Long",
                "px": "0.10",
                "sz": "1000.0",
                "fee": "0.10",
                "feeToken": "USDC",
                "closedPnl": "0.0",
                "time": 1000,
            },
        ]
    )
    return mock_info


class TestPortfolioStandardMode:
    """Tests for standard (disabled/default) mode portfolio aggregation and JSON contract."""

    def test_standard_mode_account_allocation_and_json_contract(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable[..., Any],
    ) -> None:
        """Standard-mode snapshot validates JSON contract, totals, floats, and allocation."""
        mock_info = _configure_full_mock(mock_connection, mock_retry_operation)

        round_tripped = json.loads(json.dumps(client.get_portfolio().to_json_dict()))

        assert set(round_tripped.keys()) == {
            "ok",
            "as_of",
            "source",
            "account",
            "allocation",
            "portfolio",
            "perp_positions",
            "spot_balances",
            "staking",
            "vaults",
            "open_orders",
            "closed_today",
            "errors",
        }
        assert round_tripped["ok"] is True
        assert datetime.fromisoformat(round_tripped["as_of"]).tzinfo is not None
        assert round_tripped["source"] == {
            "provider": "hyperliquid-cli",
            "network": "mainnet",
            "account_address": "0x1234567890123456789012345678901234567890",
            "abstraction_mode": "disabled",
        }

        # perps (4000) + spot (USDC 2000 + HYPE 2500 + UETH 1500 = 6000)
        # + staking (100 * 25 = 2500) + vaults (1000) = 13500
        account = round_tripped["account"]
        assert account["currency"] == "USD"
        assert account["total_assets"] == pytest.approx(13500.0)
        assert isinstance(account["total_assets"], float)
        assert account["spot_total_usd"] == pytest.approx(6000.0)
        assert account["spot_usdc"] == pytest.approx(2000.0)
        assert account["staking_total_usd"] == pytest.approx(2500.0)
        assert account["vaults_total_usd"] == pytest.approx(1000.0)
        assert account["perps"] == {
            "account_value": pytest.approx(4000.0),
            "total_position_value": pytest.approx(8000.0),
            "total_raw_usd": pytest.approx(-4000.0),
            "margin_used": pytest.approx(1200.0),
            "cross_maintenance_margin_used": pytest.approx(125.5),
            "withdrawable": pytest.approx(2800.0),
        }

        allocation = round_tripped["allocation"]
        assert allocation["total_assets"] == pytest.approx(13500.0)
        buckets_by_name = {b["name"]: b["value"] for b in allocation["buckets"]}
        assert buckets_by_name == {
            "usdc_cash": pytest.approx(2000.0),
            "spot_crypto": pytest.approx(4000.0),
            "perps_equity": pytest.approx(4000.0),
            "staking": pytest.approx(2500.0),
            "vaults": pytest.approx(1000.0),
        }
        assert sum(b["share_pct"] for b in allocation["buckets"]) == pytest.approx(100.0)
        assert round_tripped["errors"] == {
            "spot": None,
            "staking": None,
            "vaults": None,
            "open_orders": None,
            "today": None,
            "abstraction": None,
        }
        mock_info.meta_and_asset_ctxs.assert_called_once_with()
        mock_info.spot_meta_and_asset_ctxs.assert_called_once_with()

    def test_standard_mode_rows_positions_spot_staking_orders_and_today(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable[..., Any],
    ) -> None:
        """Standard-mode rows sort by descending share_pct and map fills, orders, and staking."""
        _configure_full_mock(mock_connection, mock_retry_operation)
        payload = json.loads(json.dumps(client.get_portfolio().to_json_dict()))

        rows = payload["portfolio"]
        assert all(row["symbol"] != "USDC" for row in rows)
        share_pcts = [row["share_pct"] for row in rows]
        assert share_pcts == sorted(share_pcts, reverse=True)
        assert [(row["bucket"], row["symbol"], row["side"]) for row in rows] == [
            ("perp", "BTC", "LONG"),
            ("perp", "ETH", "SHORT"),
            ("spot", "HYPE", "LONG"),
            ("staking", "HYPE", "LONG"),
            ("spot", "UETH", "LONG"),
            ("vault", "0xhlpvault", "LONG"),
        ]

        btc_row, eth_row = rows[0], rows[1]
        assert btc_row["quantity"] == pytest.approx(0.1)
        assert btc_row["market_value"] == pytest.approx(5000.0)
        assert btc_row["equity_value"] == pytest.approx(700.0)
        assert btc_row["today"]["buy_value"] == pytest.approx(4800.0)
        assert eth_row["market_value"] == pytest.approx(3000.0)
        assert eth_row["equity_value"] == pytest.approx(600.0)

        hype_spot_row = next(r for r in rows if r["bucket"] == "spot" and r["symbol"] == "HYPE")
        assert hype_spot_row["today"] == {
            "symbol": "HYPE/USDC",
            "buy_quantity": pytest.approx(20.0),
            "buy_value": pytest.approx(500.0),
            "sell_quantity": pytest.approx(0.0),
            "sell_value": pytest.approx(0.0),
            "fee_usdc": pytest.approx(0.5),
            "realized_pnl": pytest.approx(0.0),
        }

        eth_perp = next(p for p in payload["perp_positions"] if p["coin"] == "ETH")
        assert eth_perp["size"] == pytest.approx(-1.0)
        assert eth_perp["leverage"] == 6
        assert isinstance(eth_perp["leverage"], int)
        assert eth_perp["leverage_type"] == "isolated"
        assert eth_perp["funding_since_open"] == pytest.approx(-0.5)

        spots = {s["coin"]: s for s in payload["spot_balances"]}
        assert spots["USDC"]["available"] == pytest.approx(1900.0)
        assert spots["HYPE"]["entry_ntl"] == pytest.approx(1800.0)
        assert spots["HYPE"]["available"] == pytest.approx(90.0)

        staking = payload["staking"]
        assert staking["total_hype"] == pytest.approx(100.0)
        assert staking["total_reward"] == pytest.approx(2.25)
        assert staking["market_value"] == pytest.approx(2500.0)
        assert isinstance(staking["pending_withdrawal_count"], int)
        assert staking["delegations"][0]["name"] == "Validator One"

        assert payload["open_orders"][0]["coin"] == "HYPE/USDC"
        assert payload["open_orders"][0]["time_in_force"] == "GTC"

        closed = {c["symbol"]: c for c in payload["closed_today"]}
        assert set(closed.keys()) == {"SOL", "PURR/USDC"}
        assert closed["SOL"]["realized_pnl"] == pytest.approx(42.5)
        assert closed["PURR/USDC"]["realized_pnl"] == pytest.approx(5.0)


class TestPortfolioUnifiedAndPortfolioMargin:
    """Tests for anti-double-counting in unifiedAccount and portfolioMargin modes."""

    @pytest.mark.parametrize("reported_perps_account_value", ["5250.0", "250.0"])
    def test_unified_account_cross_only_does_not_double_count_usdc(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable[..., Any],
        reported_perps_account_value: str,
    ) -> None:
        """Unified account with cross perp counts spot USDC once plus cross unrealized PnL."""
        user_state = {
            "marginSummary": {
                "accountValue": reported_perps_account_value,
                "totalNtlPos": "5000.0",
                "totalRawUsd": "250.0",
                "totalMarginUsed": "500.0",
            },
            "crossMarginSummary": {
                "accountValue": reported_perps_account_value,
                "totalNtlPos": "5000.0",
                "totalRawUsd": "250.0",
                "totalMarginUsed": "500.0",
            },
            "crossMaintenanceMarginUsed": "50.0",
            "withdrawable": "4500.0",
            "assetPositions": [
                {
                    "type": "oneWay",
                    "position": {
                        "coin": "BTC",
                        "szi": "0.1",
                        "leverage": {"type": "cross", "value": 10},
                        "entryPx": "47500.0",
                        "positionValue": "5000.0",
                        "unrealizedPnl": "250.0",
                        "marginUsed": "500.0",
                        "cumFunding": {"allTime": "0.0"},
                    },
                }
            ],
        }
        _configure_full_mock(
            mock_connection,
            mock_retry_operation,
            abstraction_mode="unifiedAccount",
            user_state=user_state,
            spot_balances=[
                {"coin": "USDC", "token": 0, "total": "5000.0", "hold": "500.0"},
                {"coin": "HYPE", "token": 150, "total": "40.0", "hold": "0.0"},
            ],
            staking_summary={
                "delegated": "20.0",
                "undelegated": "0.0",
                "totalPendingWithdrawal": "0.0",
                "nPendingWithdrawals": 0,
            },
            vault_equities=[{"vaultAddress": "0xvault", "equity": "500.0"}],
            open_orders=[],
            fills=[],
        )

        payload = client.get_portfolio().to_json_dict()

        # spot_usdc (5000) + spot_crypto (40 * 25 = 1000) + cross_upnl (250)
        # + staking (20 * 25 = 500) + vault (500) = 7250 (NOT 12250!)
        assert payload["source"]["abstraction_mode"] == "unifiedAccount"
        assert payload["account"]["total_assets"] == pytest.approx(7250.0)
        buckets = {b["name"]: b["value"] for b in payload["allocation"]["buckets"]}
        assert buckets == {
            "usdc_cash": pytest.approx(5000.0),
            "spot_crypto": pytest.approx(1000.0),
            "perps_unrealized_pnl": pytest.approx(250.0),
            "staking": pytest.approx(500.0),
            "vaults": pytest.approx(500.0),
        }
        assert sum(buckets.values()) == pytest.approx(payload["account"]["total_assets"])

    def test_unified_account_with_isolated_and_cross_positions(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable[..., Any],
    ) -> None:
        """Unified account includes ring-fenced isolated equity alongside cross unrealized PnL."""
        user_state = {
            "marginSummary": {
                "accountValue": "5750.0",  # cross (5250) + isolated (500)
                "totalNtlPos": "8000.0",
                "totalRawUsd": "-2250.0",
                "totalMarginUsed": "1000.0",
            },
            "crossMarginSummary": {
                "accountValue": "5250.0",
                "totalNtlPos": "5000.0",
                "totalRawUsd": "250.0",
                "totalMarginUsed": "500.0",
            },
            "withdrawable": "4500.0",
            "assetPositions": [
                {
                    "type": "oneWay",
                    "position": {
                        "coin": "BTC",
                        "szi": "0.1",
                        "leverage": {"type": "cross", "value": 10},
                        "entryPx": "47500.0",
                        "positionValue": "5000.0",
                        "unrealizedPnl": "250.0",
                        "marginUsed": "500.0",
                        "cumFunding": {"allTime": "0.0"},
                    },
                },
                {
                    "type": "oneWay",
                    "position": {
                        "coin": "ETH",
                        "szi": "1.0",
                        "leverage": {"type": "isolated", "value": 6, "rawUsd": "-2500.0"},
                        "entryPx": "2950.0",
                        "positionValue": "3000.0",
                        "unrealizedPnl": "50.0",
                        "marginUsed": "500.0",
                        "cumFunding": {"allTime": "0.0"},
                    },
                },
            ],
        }
        _configure_full_mock(
            mock_connection,
            mock_retry_operation,
            abstraction_mode="unifiedAccount",
            user_state=user_state,
            spot_balances=[{"coin": "USDC", "token": 0, "total": "5000.0", "hold": "0.0"}],
            staking_summary={
                "delegated": "0",
                "undelegated": "0",
                "totalPendingWithdrawal": "0",
                "nPendingWithdrawals": 0,
            },
            vault_equities=[],
            open_orders=[],
            fills=[],
        )

        payload = client.get_portfolio().to_json_dict()

        # spot_usdc (5000) + isolated_equity (500) + cross_upnl (250) = 5750
        assert payload["account"]["total_assets"] == pytest.approx(5750.0)
        buckets = {b["name"]: b["value"] for b in payload["allocation"]["buckets"]}
        assert buckets["perps_isolated_equity"] == pytest.approx(500.0)
        assert buckets["perps_unrealized_pnl"] == pytest.approx(250.0)
        assert sum(buckets.values()) == pytest.approx(5750.0)

    def test_portfolio_margin_negative_upnl(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable[..., Any],
    ) -> None:
        """Portfolio margin reflects negative cross unrealized PnL without double-counting spot."""
        user_state = {
            "marginSummary": {
                "accountValue": "4850.0",
                "totalNtlPos": "5000.0",
                "totalRawUsd": "-150.0",
                "totalMarginUsed": "500.0",
            },
            "crossMarginSummary": {
                "accountValue": "4850.0",
                "totalNtlPos": "5000.0",
                "totalRawUsd": "-150.0",
                "totalMarginUsed": "500.0",
            },
            "withdrawable": "4350.0",
            "assetPositions": [
                {
                    "type": "oneWay",
                    "position": {
                        "coin": "BTC",
                        "szi": "0.1",
                        "leverage": {"type": "cross", "value": 10},
                        "entryPx": "51500.0",
                        "positionValue": "5000.0",
                        "unrealizedPnl": "-150.0",
                        "marginUsed": "500.0",
                        "cumFunding": {"allTime": "0.0"},
                    },
                }
            ],
        }
        _configure_full_mock(
            mock_connection,
            mock_retry_operation,
            abstraction_mode="portfolioMargin",
            user_state=user_state,
            spot_balances=[
                {"coin": "USDC", "token": 0, "total": "2000.0", "hold": "0.0"},
                {"coin": "UETH", "token": 221, "total": "1.0", "hold": "0.0"},
            ],
            staking_summary={
                "delegated": "0",
                "undelegated": "0",
                "totalPendingWithdrawal": "0",
                "nPendingWithdrawals": 0,
            },
            vault_equities=[],
            open_orders=[],
            fills=[],
        )

        payload = client.get_portfolio().to_json_dict()

        # spot_usdc (2000) + spot_crypto (3000) + cross_upnl (-150) = 4850
        assert payload["source"]["abstraction_mode"] == "portfolioMargin"
        assert payload["account"]["total_assets"] == pytest.approx(4850.0)
        buckets = {b["name"]: b["value"] for b in payload["allocation"]["buckets"]}
        assert buckets["perps_unrealized_pnl"] == pytest.approx(-150.0)
        assert sum(buckets.values()) == pytest.approx(4850.0)

    def test_unified_account_no_perp_positions(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable[..., Any],
    ) -> None:
        """Unified account with zero perp positions does not double-count shared USDC."""
        user_state = {
            "marginSummary": {
                "accountValue": "3000.0",
                "totalNtlPos": "0.0",
                "totalRawUsd": "3000.0",
                "totalMarginUsed": "0.0",
            },
            "withdrawable": "3000.0",
            "assetPositions": [],
        }
        _configure_full_mock(
            mock_connection,
            mock_retry_operation,
            abstraction_mode="unifiedAccount",
            user_state=user_state,
            spot_balances=[{"coin": "USDC", "token": 0, "total": "3000.0", "hold": "0.0"}],
            staking_summary={
                "delegated": "0",
                "undelegated": "0",
                "totalPendingWithdrawal": "0",
                "nPendingWithdrawals": 0,
            },
            vault_equities=[],
            open_orders=[],
            fills=[],
        )

        payload = client.get_portfolio().to_json_dict()
        assert payload["account"]["total_assets"] == pytest.approx(3000.0)


class TestPortfolioPricingFallbacksAndFlags:
    """Tests for spot/staking pricing fallbacks, optional flags, and edge cases."""

    def test_staking_falls_back_to_perp_hype_and_spot_falls_back_to_all_mids(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable[..., Any],
    ) -> None:
        """HYPE staking falls back to perp HYPE price, obscure spot token falls back to allMids."""
        mock_info = _configure_full_mock(
            mock_connection,
            mock_retry_operation,
            user_state={
                "marginSummary": {
                    "accountValue": "0.0",
                    "totalNtlPos": "0.0",
                    "totalRawUsd": "0.0",
                    "totalMarginUsed": "0.0",
                },
                "withdrawable": "0.0",
                "assetPositions": [],
            },
            spot_balances=[
                {"coin": "MYTOK", "token": 500, "total": "10.0", "hold": "0.0"},
                {"coin": "NOPRICE", "token": 501, "total": "5.0", "hold": "0.0"},
            ],
            staking_summary={
                "delegated": "10.0",
                "undelegated": "0.0",
                "totalPendingWithdrawal": "0.0",
                "nPendingWithdrawals": 0,
            },
            vault_equities=[],
            open_orders=[],
            fills=[],
        )
        # Spot meta lacks HYPE, MYTOK, and NOPRICE
        mock_info.spot_meta_and_asset_ctxs.return_value = (
            {"tokens": [{"name": "USDC", "index": 0}], "universe": []},
            [],
        )
        mock_info.all_mids.return_value = {"MYTOK": "12.5"}

        payload = client.get_portfolio().to_json_dict()

        # Staking 10 HYPE priced from perp HYPE mark (24.5) = 245.0
        assert payload["staking"]["mark_price"] == pytest.approx(24.5)
        assert payload["staking"]["market_value"] == pytest.approx(245.0)
        # MYTOK priced via all_mids (12.5 * 10 = 125.0); NOPRICE remains unpriced (None)
        spots = {s["coin"]: s for s in payload["spot_balances"]}
        assert spots["MYTOK"]["mark_price"] == pytest.approx(12.5)
        assert spots["MYTOK"]["market_value"] == pytest.approx(125.0)
        assert spots["NOPRICE"]["mark_price"] is None
        assert spots["NOPRICE"]["market_value"] is None
        assert payload["account"]["total_assets"] == pytest.approx(370.0)

    def test_include_flags_skip_open_orders_and_today_queries(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable[..., Any],
    ) -> None:
        """include_open_orders=False and include_today=False skip their info calls."""
        mock_info = _configure_full_mock(mock_connection, mock_retry_operation)

        payload = client.get_portfolio(
            include_open_orders=False,
            include_today=False,
        ).to_json_dict()

        mock_info.frontend_open_orders.assert_not_called()
        mock_info.user_fills_by_time.assert_not_called()
        assert payload["open_orders"] == []
        assert payload["closed_today"] == []
        assert all(row["today"] is None for row in payload["portfolio"])
        assert payload["errors"]["open_orders"] is None
        assert payload["errors"]["today"] is None

    def test_empty_account_zero_assets_avoids_division_by_zero(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable[..., Any],
    ) -> None:
        """Empty zero-equity account produces 0% shares and skips unused market metadata calls."""
        mock_info = _configure_full_mock(
            mock_connection,
            mock_retry_operation,
            user_state={
                "marginSummary": {
                    "accountValue": "0",
                    "totalNtlPos": "0",
                    "totalRawUsd": "0",
                    "totalMarginUsed": "0",
                },
                "withdrawable": "0",
                "assetPositions": [],
            },
            spot_balances=[],
            staking_summary={
                "delegated": "0",
                "undelegated": "0",
                "totalPendingWithdrawal": "0",
                "nPendingWithdrawals": 0,
            },
            vault_equities=[],
            open_orders=[],
            fills=[],
        )
        mock_info.user_staking_delegations.return_value = []
        mock_info.user_staking_rewards.return_value = []

        payload = client.get_portfolio().to_json_dict()

        assert payload["account"]["total_assets"] == pytest.approx(0.0)
        assert payload["portfolio"] == []
        assert all(b["share_pct"] == pytest.approx(0.0) for b in payload["allocation"]["buckets"])
        mock_info.meta_and_asset_ctxs.assert_not_called()
        mock_info.post.assert_not_called()

    def test_spot_price_helper_prefers_canonical_and_mid_px_fallback(self) -> None:
        """Canonical pairs win over non-canonical duplicates, and midPx works if markPx missing."""
        spot_meta = {
            "tokens": [
                {"name": "USDC", "index": 0},
                {"name": "FOO", "index": 10},
                {"name": "BAR", "index": 11},
            ],
            "universe": [
                {"name": "@1", "tokens": [10, 0], "isCanonical": False},
                {"name": "@2", "tokens": [10, 0], "isCanonical": True},
                {"name": "@3", "tokens": [11, 0], "isCanonical": True},
            ],
        }
        spot_ctxs: list[dict[str, Any]] = [
            {"coin": "@1", "markPx": "1.0"},
            {"coin": "@2", "markPx": "2.5"},
            {"coin": "@3", "markPx": None, "midPx": "7.25"},
        ]
        prices, symbols = extract_spot_prices_and_symbols(spot_meta, spot_ctxs)

        assert prices["USDC"] == Decimal("1")
        assert prices["FOO"] == Decimal("2.5")
        assert prices["BAR"] == Decimal("7.25")
        assert symbols["@2"] == "FOO/USDC"
        assert parse_abstraction_mode("  unifiedAccount ") == "unifiedAccount"
        assert parse_abstraction_mode({"mode": "portfolioMargin"}) == "portfolioMargin"
        assert parse_abstraction_mode(None) is None


class TestPortfolioErrorsAndReadOnlyGuarantee:
    """Tests for partial section errors, fatal core errors, and read-only guarantees."""

    def test_partial_section_failures_recorded_without_crashing(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable[..., Any],
    ) -> None:
        """Failures in optional sections are recorded cleanly in errors while perps survive."""
        mock_info = _configure_full_mock(mock_connection, mock_retry_operation)
        mock_info.query_user_abstraction_state.side_effect = RuntimeError("abstraction down")
        mock_info.spot_user_state.side_effect = RuntimeError("spot down")
        mock_info.user_staking_summary.side_effect = RuntimeError("staking down")
        mock_info.user_vault_equities.side_effect = RuntimeError("vaults down")
        mock_info.frontend_open_orders.side_effect = RuntimeError("orders down")
        mock_info.user_fills_by_time.side_effect = RuntimeError("fills down")

        payload = client.get_portfolio().to_json_dict()

        assert payload["ok"] is True
        assert payload["source"]["abstraction_mode"] is None
        assert payload["staking"] is None
        assert payload["spot_balances"] == []
        assert payload["vaults"] == []
        assert payload["open_orders"] == []
        assert payload["closed_today"] == []
        assert payload["account"]["total_assets"] == pytest.approx(4000.0)
        assert payload["errors"] == {
            "spot": "spot down",
            "staking": "staking down",
            "vaults": "vaults down",
            "open_orders": "orders down",
            "today": "fills down",
            "abstraction": "abstraction down",
        }

    def test_partial_staking_metadata_error_preserves_valuation(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable[..., Any],
    ) -> None:
        """Delegation/reward sub-failures keep staking USD valuation and surface errors.staking."""
        mock_info = _configure_full_mock(mock_connection, mock_retry_operation)
        mock_info.user_staking_delegations.side_effect = RuntimeError("delegations timeout")
        mock_info.user_staking_rewards.side_effect = RuntimeError("rewards timeout")

        payload = client.get_portfolio().to_json_dict()

        assert payload["staking"]["total_hype"] == pytest.approx(100.0)
        assert payload["staking"]["market_value"] == pytest.approx(2500.0)
        assert payload["staking"]["delegations"] == []
        assert "delegations timeout" in payload["errors"]["staking"]
        assert "rewards timeout" in payload["errors"]["staking"]

    def test_core_user_state_failure_raises_exchange_error(
        self,
        client: HyperliquidClient,
        mock_connection: Mock,
        mock_retry_operation: Callable[..., Any],
    ) -> None:
        """Failure of core user_state raises ExchangeError rather than returning empty totals."""
        mock_info = _configure_full_mock(mock_connection, mock_retry_operation)
        mock_info.user_state.side_effect = RuntimeError("clearinghouse offline")

        with pytest.raises(ExchangeError, match="clearinghouse offline"):
            client.get_portfolio()

    def test_requires_account_address(self, mock_connection: Mock) -> None:
        """get_portfolio fails immediately if account_address is unset."""
        with patch(
            "exchange.hyperliquid_client.HyperliquidConnection",
            return_value=mock_connection,
        ):
            client = HyperliquidClient(Config())

        with pytest.raises(ExchangeError, match="Account address is required"):
            client.get_portfolio()
        mock_connection.retry_operation.assert_not_called()

    def test_read_only_never_touches_exchange_ws_info_or_private_key(
        self,
        mock_retry_operation: Callable[..., Any],
    ) -> None:
        """get_portfolio works with private_key=None and never accesses exchange or ws_info."""
        config = Config(
            hyperliquid=HyperliquidConfig(
                account_address="0x1234567890123456789012345678901234567890",
                private_key=None,
                network=NetworkType.TESTNET,
            )
        )

        class _StrictReadOnlyConnection:
            def __init__(self) -> None:
                self.info = Mock()
                self.retry_operation = Mock(side_effect=mock_retry_operation)

            @property
            def exchange(self) -> Any:
                raise AssertionError("get_portfolio must never access connection.exchange")

            @property
            def ws_info(self) -> Any:
                raise AssertionError("get_portfolio must never access connection.ws_info")

            def close(self) -> None:
                pass

        strict_conn = _StrictReadOnlyConnection()
        _configure_full_mock(
            strict_conn,  # type: ignore[arg-type]
            mock_retry_operation,
        )

        with patch(
            "exchange.hyperliquid_client.HyperliquidConnection",
            return_value=strict_conn,
        ):
            with HyperliquidClient(config) as ro_client:
                payload = ro_client.get_portfolio().to_json_dict()

        assert payload["ok"] is True
        assert payload["source"]["network"] == "testnet"
        assert isinstance(HyperliquidConnection, type)
