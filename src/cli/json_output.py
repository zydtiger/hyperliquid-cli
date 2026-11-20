"""Compact JSON output envelopes and JSON-aware Typer error handling."""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

import typer
import typer.core
from pydantic import BaseModel

from models.config import Config, NetworkType

EXIT_SUCCESS = 0
EXIT_RUNTIME_ERROR = 1
EXIT_VALIDATION_ERROR = 2

_ROOT_VALUE_OPTIONS = frozenset({"-c", "--config", "--address", "--network"})


def local_iso_now() -> str:
    """Return the current local timestamp formatted as ISO-8601."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def to_json_value(value: Any) -> Any:
    """Convert Pydantic models, Decimals, Enums, and Paths to JSON-safe values."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, (Decimal, Path)):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): to_json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json_value(item) for item in value]
    return value


def build_source(
    config: Config | None,
    *,
    network: NetworkType | None = None,
    address: str | None = None,
) -> dict[str, str | None]:
    """Build the standard JSON ``source`` metadata block."""
    if config is not None:
        return {
            "network": config.hyperliquid.network.value,
            "account_address": config.hyperliquid.account_address,
        }
    return {
        "network": network.value if network is not None else NetworkType.MAINNET.value,
        "account_address": address,
    }


def emit_json_raw(payload: dict[str, Any]) -> None:
    """Print exactly one compact JSON object to stdout."""
    sys.stdout.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def emit_json_success(
    command: str,
    data: Any,
    config: Config | None,
    *,
    network: NetworkType | None = None,
    address: str | None = None,
) -> None:
    """Print the standard success JSON envelope to stdout."""
    emit_json_raw(
        {
            "ok": True,
            "as_of": local_iso_now(),
            "command": command,
            "source": build_source(config, network=network, address=address),
            "data": to_json_value(data),
        }
    )


def emit_json_error(
    command: str,
    exc: BaseException,
    config: Config | None = None,
    *,
    network: NetworkType | None = None,
    address: str | None = None,
) -> None:
    """Print the standard error JSON envelope to stdout."""
    message = exc.format_message() if hasattr(exc, "format_message") else str(exc)
    emit_json_raw(
        {
            "ok": False,
            "as_of": local_iso_now(),
            "command": command,
            "source": build_source(config, network=network, address=address),
            "error": {
                "type": type(exc).__name__,
                "message": message,
            },
        }
    )


def _extract_cli_context(
    args: Sequence[str],
) -> tuple[str, NetworkType | None, str | None]:
    """Best-effort parse of command name, network, and address from raw argv."""
    command = "hyperliquid-cli"
    address: str | None = None
    network: NetworkType | None = None
    found_command = False
    index = 0

    while index < len(args):
        arg = args[index]
        if arg == "--":
            break
        if arg in _ROOT_VALUE_OPTIONS:
            value = args[index + 1] if index + 1 < len(args) else None
            if arg == "--address":
                address = value
            elif arg == "--network" and value in (NetworkType.MAINNET, NetworkType.TESTNET):
                network = NetworkType(value)
            index += 2
            continue
        if arg.startswith("--address="):
            address = arg.split("=", maxsplit=1)[1] or None
            index += 1
            continue
        if arg.startswith("--network="):
            net_val = arg.split("=", maxsplit=1)[1]
            if net_val in (NetworkType.MAINNET, NetworkType.TESTNET):
                network = NetworkType(net_val)
            index += 1
            continue
        if arg.startswith("-"):
            index += 1
            continue
        if not found_command:
            command = arg
            found_command = True
        index += 1

    return command, network, address


class JsonAwareTyperGroup(typer.core.TyperGroup):
    """Typer group that formats CLI parse/validation errors as JSON when ``--json`` is set."""

    def main(
        self,
        args: Sequence[str] | None = None,
        prog_name: str | None = None,
        complete_var: str | None = None,
        standalone_mode: bool = True,
        windows_expand_args: bool = True,
        **extra: Any,
    ) -> Any:
        raw_args = list(sys.argv[1:]) if args is None else list(args)
        wants_help = any(flag in raw_args for flag in ("--help", "-h"))
        json_active = "--json" in raw_args and not wants_help

        if not standalone_mode or not json_active:
            return super().main(
                args=args,
                prog_name=prog_name,
                complete_var=complete_var,
                standalone_mode=standalone_mode,
                windows_expand_args=windows_expand_args,
                **extra,
            )

        previous_disable = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        command, network, address = _extract_cli_context(raw_args)
        try:
            rv = super().main(
                args=raw_args,
                prog_name=prog_name,
                complete_var=complete_var,
                standalone_mode=False,
                windows_expand_args=windows_expand_args,
                **extra,
            )
            exit_code = rv if isinstance(rv, int) else EXIT_SUCCESS
            sys.exit(exit_code)
        except typer.Exit as exc:
            sys.exit(exc.exit_code)
        except typer.exceptions.TyperException as exc:
            emit_json_error(command, exc, None, network=network, address=address)
            code = getattr(exc, "exit_code", EXIT_VALIDATION_ERROR)
            sys.exit(code if isinstance(code, int) else EXIT_VALIDATION_ERROR)
        except typer.Abort as exc:
            emit_json_error(command, exc, None, network=network, address=address)
            sys.exit(EXIT_RUNTIME_ERROR)
        except Exception as exc:
            emit_json_error(command, exc, None, network=network, address=address)
            sys.exit(EXIT_RUNTIME_ERROR)
        finally:
            logging.disable(previous_disable)
