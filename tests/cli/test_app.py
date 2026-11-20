"""Tests for root CLI app, repl, create-config, status, and JSON error contract."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Self

import pytest
from typer.testing import CliRunner

import cli.app as app_module
import cli.commands.system as system_module
import cli.runtime as runtime_module
from models.config import Config, NetworkType

runner = CliRunner()
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(value: str) -> str:
    return ANSI_ESCAPE_RE.sub("", value)


def test_cli_defaults_to_repl_without_subcommand(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("hyperliquid:\n  account_address: '0x1234'\n", encoding="utf-8")
    called: list[tuple[Path, str | None, NetworkType | None, bool]] = []

    def fake_launch_cli(
        run_config_path: Path,
        *,
        address: str | None = None,
        network: NetworkType | None = None,
        must_exist: bool = False,
    ) -> None:
        called.append((run_config_path, address, network, must_exist))

    monkeypatch.setattr(app_module, "launch_cli", fake_launch_cli)

    result = runner.invoke(
        app_module.app,
        ["--config", str(config_path), "--network", "testnet"],
    )

    assert result.exit_code == 0
    assert called == [(config_path, None, NetworkType.TESTNET, True)]


def test_repl_subcommand_forwards_options_and_shares_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "hyperliquid:\n  account_address: '0x1234567890123456789012345678901234567890'\n",
        encoding="utf-8",
    )
    events: list[str] = []

    class FakeClient:
        def __init__(self, config: Config) -> None:
            self.config = config
            events.append(f"init:{config.hyperliquid.network.value}")

        def __enter__(self) -> Self:
            events.append("enter")
            return self

        def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
            events.append("exit")

        def test_connection(self) -> bool:
            events.append("test_connection")
            return True

    class FakeInteractiveCLI:
        def __init__(self, config: Config, client: object = None) -> None:
            assert isinstance(client, FakeClient)
            events.append("repl_init")

        def run(self) -> None:
            events.append("repl_run")

    monkeypatch.setattr(system_module, "HyperliquidClient", FakeClient)
    monkeypatch.setattr(system_module, "InteractiveCLI", FakeInteractiveCLI)

    result = runner.invoke(
        app_module.app,
        ["repl", "--config", str(config_path), "--network", "testnet"],
    )

    assert result.exit_code == 0
    assert events == ["init:testnet", "enter", "test_connection", "repl_init", "repl_run", "exit"]


def test_repl_rejects_json_flag() -> None:
    result = runner.invoke(app_module.app, ["repl", "--json"])

    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["command"] == "repl"
    assert payload["error"]["type"] == "CliValidationError"


def test_root_no_subcommand_rejects_json_flag() -> None:
    result = runner.invoke(app_module.app, ["--json"])

    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["command"] == "hyperliquid-cli"


def test_cli_subcommands_do_not_trigger_default_run(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    def fake_launch_cli(*_args: object, **_kwargs: object) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(app_module, "launch_cli", fake_launch_cli)

    result = runner.invoke(app_module.app, ["create-config", "--help"])

    assert result.exit_code == 0
    assert called is False


def test_run_is_not_available_as_subcommand() -> None:
    result = runner.invoke(app_module.app, ["run"], color=True)

    assert result.exit_code == 2
    assert "No such command 'run'" in strip_ansi(result.output)


def test_unknown_subcommand_with_json_emits_compact_error_envelope() -> None:
    result = runner.invoke(app_module.app, ["--json", "nonexistent"])

    assert result.exit_code == 2
    lines = result.stdout.strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["ok"] is False
    assert payload["command"] == "nonexistent"
    assert "No such command" in payload["error"]["message"]
    assert payload["source"] == {"account_address": None, "network": "mainnet"}


def test_cli_missing_default_config_exits_cleanly(tmp_path: Path) -> None:
    missing_config = tmp_path / "missing.yaml"

    result = runner.invoke(app_module.app, ["repl", "--config", str(missing_config)])

    assert result.exit_code == 1
    assert "Failed to load configuration" in strip_ansi(result.output)


def test_launch_cli_exits_when_connection_test_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "hyperliquid:\n  account_address: '0x1234567890123456789012345678901234567890'\n",
        encoding="utf-8",
    )

    class FailingClient:
        def __init__(self, _config: Config) -> None:
            pass

        def __enter__(self) -> Self:
            return self

        def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
            return None

        def test_connection(self) -> bool:
            return False

    monkeypatch.setattr(system_module, "HyperliquidClient", FailingClient)

    result = runner.invoke(app_module.app, ["repl", "--config", str(config_path)])

    assert result.exit_code == 1
    assert "Failed to connect to Hyperliquid exchange" in strip_ansi(result.output)


def test_create_config_creates_and_respects_force(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target = tmp_path / "nested" / "config.yaml"
    monkeypatch.setattr(runtime_module, "default_config_path", target)

    first = runner.invoke(app_module.app, ["create-config", "--json"])
    assert first.exit_code == 0
    first_payload = json.loads(first.stdout)
    assert first_payload["ok"] is True
    assert first_payload["command"] == "create-config"
    assert first_payload["data"] == {"created": True, "overwritten": False, "path": str(target)}
    assert target.exists()

    second = runner.invoke(app_module.app, ["create-config", "--json"])
    assert second.exit_code == 1
    second_payload = json.loads(second.stdout)
    assert second_payload["ok"] is False
    assert second_payload["error"]["type"] == "FileExistsError"
    assert "--force" in second_payload["error"]["message"]

    third = runner.invoke(app_module.app, ["--json", "create-config", "--force"])
    assert third.exit_code == 0
    third_payload = json.loads(third.stdout)
    assert third_payload["ok"] is True
    assert third_payload["data"]["overwritten"] is True


def test_status_json_never_leaks_private_key_and_silences_logging(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    secret_key = "0x" + "ab" * 32
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "hyperliquid:\n"
        "  account_address: '0x1234567890123456789012345678901234567890'\n"
        f"  private_key: '{secret_key}'\n"
        "  network: testnet\n",
        encoding="utf-8",
    )

    class FakeClient:
        def __init__(self, _config: Config) -> None:
            pass

        def __enter__(self) -> Self:
            return self

        def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
            return None

        def test_connection(self) -> bool:
            logging.warning("noisy log line that must stay silent")
            return True

    monkeypatch.setattr(runtime_module, "HyperliquidClient", FakeClient)

    result = runner.invoke(app_module.app, ["status", "-c", str(config_path), "--json"])

    assert result.exit_code == 0
    assert secret_key not in result.stdout
    assert "noisy log line" not in result.output
    lines = result.stdout.strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["ok"] is True
    assert payload["command"] == "status"
    assert payload["source"] == {
        "account_address": "0x1234567890123456789012345678901234567890",
        "network": "testnet",
    }
    assert payload["data"]["connected"] is True
    assert payload["data"]["has_private_key"] is True
    assert payload["data"]["network"] == "testnet"
    assert payload["data"]["version"]


def test_status_works_without_config_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(runtime_module, "default_config_path", tmp_path / "absent.yaml")

    class FakeClient:
        def __init__(self, _config: Config) -> None:
            pass

        def __enter__(self) -> Self:
            return self

        def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
            return None

        def test_connection(self) -> bool:
            return True

    monkeypatch.setattr(runtime_module, "HyperliquidClient", FakeClient)

    result = runner.invoke(app_module.app, ["--json", "status"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["data"]["account_address"] is None
    assert payload["data"]["has_private_key"] is False
    assert payload["data"]["connected"] is True
