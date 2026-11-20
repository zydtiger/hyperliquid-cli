"""Position write commands: change-leverage, update-margin."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any

import typer
from pydantic import ValidationError

from exchange import HyperliquidClient
from models.api import ExchangeError, LeverageType
from models.config import Config, NetworkType
from models.leverage import LeverageResult
from models.margin import IsolatedMarginUpdateRequest, IsolatedMarginUpdateResult

from ..formatters import AccountFormatter, TableFormatter
from ..runtime import CliValidationError, resolve_options, run_command
from .parsers import (
    ADDRESS_OPTION,
    CONFIG_OPTION,
    JSON_OPTION,
    NETWORK_OPTION,
    find_position_for_coin,
    parse_coin,
    parse_decimal,
    parse_leverage,
)


def _render_leverage_human(result: Any, _config: Config) -> None:
    if isinstance(result, LeverageResult):
        print(f"✅ {result.message}")
        if result.updated_position is not None:
            print(AccountFormatter().format([result.updated_position]))
        return
    if isinstance(result, dict) and result.get("dry_run"):
        rows = [
            ["Coin", result["coin"]],
            ["Leverage", f"{result['leverage']}x"],
            ["Margin Mode", result["leverage_type"]],
            ["Max Leverage", f"{result['max_leverage']}x"],
        ]
        print(
            TableFormatter().format(
                (["Field", "Value"], rows),
                title="[DRY RUN] Leverage Update",
            )
        )


def _render_margin_human(result: Any, _config: Config) -> None:
    if isinstance(result, IsolatedMarginUpdateResult):
        print(f"✅ {result.message}")
        if result.updated_position is not None:
            print(AccountFormatter().format([result.updated_position]))
        return
    if isinstance(result, dict) and result.get("dry_run"):
        rows = [
            ["Coin", result["coin"]],
            ["Action", result["action"]],
            ["Amount", f"${result['amount']}"],
        ]
        print(
            TableFormatter().format(
                (["Field", "Value"], rows),
                title="[DRY RUN] Isolated Margin Update",
            )
        )
        print(AccountFormatter().format([result["current_position"]]))


def register_position_write_commands(app: typer.Typer) -> None:
    """Register change-leverage and update-margin commands."""

    @app.command("change-leverage")
    def change_leverage_command(
        ctx: typer.Context,
        coin: Annotated[str, typer.Argument(help="Coin symbol (e.g., BTC, ETH)")],
        leverage: Annotated[int, typer.Argument(help="Target leverage multiplier (1-250)")],
        is_cross: Annotated[
            bool,
            typer.Option(
                "--cross/--isolated",
                help="Use cross margin (default) or isolated margin",
            ),
        ] = True,
        dry_run: Annotated[
            bool,
            typer.Option(
                "--dry-run",
                help="Validate leverage against coin metadata without signing",
            ),
        ] = False,
        config_path: Annotated[Path | None, CONFIG_OPTION] = None,
        address: Annotated[str | None, ADDRESS_OPTION] = None,
        network: Annotated[NetworkType | None, NETWORK_OPTION] = None,
        json_output: Annotated[bool, JSON_OPTION] = False,
    ) -> None:
        """Change leverage and margin mode for a coin."""
        opts = resolve_options(
            ctx,
            config_path=config_path,
            address=address,
            network=network,
            json_output=json_output,
        )
        parsed_coin: list[str] = [""]
        parsed_leverage: list[int] = [1]

        def _validate() -> None:
            parsed_coin[0] = parse_coin(coin)
            parsed_leverage[0] = parse_leverage(leverage)

        def _execute(_config: Config, client: HyperliquidClient) -> Any:
            symbol = parsed_coin[0]
            target_leverage = parsed_leverage[0]
            if dry_run:
                metadata = client.get_metadata(symbol)
                if target_leverage > metadata.max_leverage:
                    raise CliValidationError(
                        f"Leverage {target_leverage}x exceeds maximum allowed leverage "
                        f"{metadata.max_leverage}x for {metadata.coin}"
                    )
                return {
                    "dry_run": True,
                    "coin": metadata.coin,
                    "leverage": target_leverage,
                    "leverage_type": "cross" if is_cross else "isolated",
                    "max_leverage": metadata.max_leverage,
                    "metadata": metadata,
                }

            result = client.change_leverage(target_leverage, symbol, is_cross=is_cross)
            if not result.success:
                raise ExchangeError(result.message)
            return result

        run_command(
            "change-leverage",
            opts,
            require_address=not dry_run,
            validate=_validate,
            execute=_execute,
            render_human=_render_leverage_human,
        )

    @app.command("update-margin")
    def update_margin_command(
        ctx: typer.Context,
        coin: Annotated[str, typer.Argument(help="Coin symbol (e.g., ETH, BTC)")],
        amount: Annotated[
            str,
            typer.Option(
                "--amount",
                help="Signed USD delta (positive adds margin, negative removes margin)",
            ),
        ],
        dry_run: Annotated[
            bool,
            typer.Option(
                "--dry-run",
                help="Validate isolated position and amount without signing",
            ),
        ] = False,
        config_path: Annotated[Path | None, CONFIG_OPTION] = None,
        address: Annotated[str | None, ADDRESS_OPTION] = None,
        network: Annotated[NetworkType | None, NETWORK_OPTION] = None,
        json_output: Annotated[bool, JSON_OPTION] = False,
    ) -> None:
        """Add or remove isolated margin for an open isolated position."""
        opts = resolve_options(
            ctx,
            config_path=config_path,
            address=address,
            network=network,
            json_output=json_output,
        )
        parsed_coin: list[str] = [""]
        parsed_amount: list[Decimal] = [Decimal("0")]

        def _validate() -> None:
            symbol = parse_coin(coin)
            dec_amount = parse_decimal(amount, "--amount")
            try:
                validated = IsolatedMarginUpdateRequest(coin=symbol, amount=dec_amount)
            except ValidationError as exc:
                first_error = exc.errors()[0]["msg"] if exc.errors() else str(exc)
                raise CliValidationError(first_error) from exc
            parsed_coin[0] = validated.coin
            parsed_amount[0] = validated.amount

        def _execute(_config: Config, client: HyperliquidClient) -> Any:
            symbol = parsed_coin[0]
            delta = parsed_amount[0]
            if dry_run:
                pos = find_position_for_coin(client.get_positions(), symbol)
                if pos is None:
                    raise ExchangeError(f"No open position found for {symbol}")
                if pos.leverage_type != LeverageType.ISOLATED:
                    raise ExchangeError(
                        f"Cannot update isolated margin for {symbol}: "
                        "position is using cross margin"
                    )
                return {
                    "dry_run": True,
                    "coin": pos.coin,
                    "amount": delta,
                    "action": "add" if delta > 0 else "remove",
                    "current_position": pos,
                }

            result = client.update_isolated_margin(delta, symbol)
            if not result.success:
                raise ExchangeError(result.message)
            return result

        run_command(
            "update-margin",
            opts,
            require_address=True,
            validate=_validate,
            execute=_execute,
            render_human=_render_margin_human,
        )
