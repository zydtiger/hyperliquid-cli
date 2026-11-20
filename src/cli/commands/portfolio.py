"""Portfolio snapshot command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer

from exchange import HyperliquidClient
from models.config import Config, NetworkType

from ..formatters import TableFormatter
from ..runtime import resolve_options, run_command
from .parsers import ADDRESS_OPTION, CONFIG_OPTION, JSON_OPTION, NETWORK_OPTION


def _fmt_usd(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, (int, float)):
        return f"${value:,.2f}"
    return str(value)


def _fmt_signed_usd(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, (int, float)):
        return f"${value:+,.2f}"
    return str(value)


def _fmt_pct(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, (int, float)):
        return f"{value:.2f}%"
    return str(value)


def _fmt_num(value: Any, decimals: int = 4) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, (int, float)):
        return f"{value:,.{decimals}f}".rstrip("0").rstrip(".") or "0"
    return str(value)


def _render_account_summary(formatter: TableFormatter, data: dict[str, Any]) -> str:
    source = data.get("source") or {}
    account = data.get("account") or {}
    perps = account.get("perps")
    perps_equity = perps.get("account_value") if isinstance(perps, dict) else perps
    rows = [
        ["Network", source.get("network", "N/A")],
        ["Account", source.get("account_address", "N/A")],
        ["Mode", source.get("abstraction_mode") or "default"],
        ["Total Assets", _fmt_usd(account.get("total_assets"))],
        ["Perps Equity", _fmt_usd(perps_equity)],
        ["Spot Total", _fmt_usd(account.get("spot_total_usd"))],
        ["Spot USDC", _fmt_usd(account.get("spot_usdc"))],
        ["Staking Total", _fmt_usd(account.get("staking_total_usd"))],
        ["Vaults Total", _fmt_usd(account.get("vaults_total_usd"))],
    ]
    return formatter.format((["Metric", "Value"], rows), title="Portfolio Summary")


def _render_perp_positions(formatter: TableFormatter, positions: list[dict[str, Any]]) -> str:
    rows = [
        [
            pos.get("coin", ""),
            pos.get("side", ""),
            _fmt_num(pos.get("size"), 6),
            _fmt_usd(pos.get("entry_price")),
            _fmt_usd(pos.get("mark_price")),
            _fmt_usd(pos.get("position_value")),
            _fmt_usd(pos.get("margin_used")),
            _fmt_signed_usd(pos.get("unrealized_pnl")),
            f"{pos.get('leverage')}x" if pos.get("leverage") is not None else "N/A",
        ]
        for pos in positions
    ]
    return formatter.format(
        (["Coin", "Side", "Size", "Entry", "Mark", "Notional", "Margin", "uPnL", "Lev"], rows),
        title=f"Perp Positions ({len(positions)})",
    )


def _render_spot_balances(formatter: TableFormatter, balances: list[dict[str, Any]]) -> str:
    rows = [
        [
            bal.get("coin", ""),
            _fmt_num(bal.get("total"), 6),
            _fmt_usd(bal.get("mark_price")),
            _fmt_usd(bal.get("market_value")),
            _fmt_pct(bal.get("share_pct")),
        ]
        for bal in balances
    ]
    return formatter.format(
        (["Coin", "Total", "Mark", "USD Value", "Share"], rows),
        title=f"Spot Balances ({len(balances)})",
    )


def _render_staking(formatter: TableFormatter, staking: dict[str, Any]) -> str | None:
    if not staking:
        return None
    rows = [
        ["Total HYPE", _fmt_num(staking.get("total_hype"), 6)],
        ["Delegated", _fmt_num(staking.get("delegated"), 6)],
        ["Total Reward", _fmt_num(staking.get("total_reward"), 6)],
        ["USD Value", _fmt_usd(staking.get("market_value"))],
        ["Share", _fmt_pct(staking.get("share_pct"))],
    ]
    return formatter.format((["Metric", "Value"], rows), title="Staking")


def _render_vaults(formatter: TableFormatter, vaults: list[dict[str, Any]]) -> str:
    rows = [
        [
            vault.get("vault_address", ""),
            _fmt_usd(vault.get("equity")),
            _fmt_pct(vault.get("share_pct")),
        ]
        for vault in vaults
    ]
    return formatter.format(
        (["Vault Address", "Equity", "Share"], rows),
        title=f"Vaults ({len(vaults)})",
    )


def _render_errors(formatter: TableFormatter, errors: Any) -> str | None:
    if isinstance(errors, dict):
        active = [[section, str(msg)] for section, msg in errors.items() if msg]
        if not active:
            return None
        return formatter.format((["Section", "Error"], active), title=f"Errors ({len(active)})")
    if isinstance(errors, list) and errors:
        rows = [[str(err)] for err in errors]
        return formatter.format((["Error"], rows), title=f"Errors ({len(errors)})")
    return None


def _render_portfolio_human(data: dict[str, Any], _config: Config) -> None:
    """Render portfolio snapshot tables for human consumption."""
    formatter = TableFormatter()
    sections = [_render_account_summary(formatter, data)]

    perp_positions = data.get("perp_positions") or []
    if perp_positions:
        sections.append(_render_perp_positions(formatter, perp_positions))

    spot_balances = data.get("spot_balances") or []
    if spot_balances:
        sections.append(_render_spot_balances(formatter, spot_balances))

    staking = data.get("staking")
    if isinstance(staking, dict) and staking:
        staking_table = _render_staking(formatter, staking)
        if staking_table:
            sections.append(staking_table)

    vaults = data.get("vaults") or []
    if vaults:
        sections.append(_render_vaults(formatter, vaults))

    open_orders = data.get("open_orders")
    if isinstance(open_orders, list) and open_orders:
        order_rows = [
            [
                order.get("order_id", ""),
                order.get("coin", ""),
                str(order.get("side", "")).upper(),
                _fmt_num(order.get("quantity"), 6),
                _fmt_usd(order.get("price")),
            ]
            for order in open_orders
        ]
        sections.append(
            formatter.format(
                (["Order ID", "Coin", "Side", "Qty", "Price"], order_rows),
                title=f"Open Orders ({len(open_orders)})",
            )
        )

    errors_table = _render_errors(formatter, data.get("errors"))
    if errors_table:
        sections.append(errors_table)

    print("\n".join(sections))


def register_portfolio_commands(app: typer.Typer) -> None:
    """Register the portfolio snapshot command on the Typer app."""

    @app.command("portfolio")
    def portfolio_command(
        ctx: typer.Context,
        open_orders: Annotated[
            bool,
            typer.Option(
                "--open-orders/--no-open-orders",
                help="Include open orders in the portfolio snapshot",
            ),
        ] = True,
        today: Annotated[
            bool,
            typer.Option(
                "--today/--no-today",
                help="Include closed-today fills in the portfolio snapshot",
            ),
        ] = True,
        config_path: Annotated[Path | None, CONFIG_OPTION] = None,
        address: Annotated[str | None, ADDRESS_OPTION] = None,
        network: Annotated[NetworkType | None, NETWORK_OPTION] = None,
        json_output: Annotated[bool, JSON_OPTION] = False,
    ) -> None:
        """Fetch a unified portfolio snapshot (perps, spot, staking, vaults)."""
        opts = resolve_options(
            ctx,
            config_path=config_path,
            address=address,
            network=network,
            json_output=json_output,
        )

        def _execute(_config: Config, client: HyperliquidClient) -> dict[str, Any]:
            snapshot = client.get_portfolio(
                include_open_orders=open_orders,
                include_today=today,
            )
            payload: dict[str, Any] = snapshot.to_json_dict()
            return payload

        run_command(
            "portfolio",
            opts,
            require_address=True,
            execute=_execute,
            render_human=_render_portfolio_human,
            raw_json=True,
        )
