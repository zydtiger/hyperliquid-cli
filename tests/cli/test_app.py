import re
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

import cli.app as app_module

runner = CliRunner()
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(value: str) -> str:
    return ANSI_ESCAPE_RE.sub("", value)


def test_cli_defaults_to_run_without_subcommand(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("test: true\n", encoding="utf-8")
    called_with: list[Path] = []

    def fake_launch_cli(run_config_path: Path = app_module.default_config_path) -> None:
        called_with.append(run_config_path)

    monkeypatch.setattr(app_module, "launch_cli", fake_launch_cli)

    result = runner.invoke(app_module.app, ["--config", str(config_path)])

    assert result.exit_code == 0
    assert called_with == [config_path]


def test_cli_subcommands_do_not_trigger_default_run(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    def fake_launch_cli(run_config_path: Path = app_module.default_config_path) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(app_module, "launch_cli", fake_launch_cli)

    result = runner.invoke(app_module.app, ["create-config", "--help"])

    assert result.exit_code == 0
    assert called is False


def test_run_is_not_available_as_subcommand() -> None:
    result = runner.invoke(app_module.app, ["run"], color=True)

    assert result.exit_code != 0
    assert "No such command 'run'" in strip_ansi(result.output)


def test_cli_missing_default_config_exits_cleanly(tmp_path: Path) -> None:
    missing_config = tmp_path / "missing.yaml"
    test_app = typer.Typer()

    @test_app.command()
    def run() -> None:
        app_module.launch_cli(missing_config)

    result = runner.invoke(test_app, [])

    assert result.exit_code == 1
    assert "Failed to load configuration" in strip_ansi(result.output)
