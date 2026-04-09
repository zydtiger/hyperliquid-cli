from pathlib import Path

from typer.testing import CliRunner

import cli.app as app_module

runner = CliRunner()


def test_cli_defaults_to_run_without_subcommand(
    monkeypatch,
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


def test_cli_subcommands_do_not_trigger_default_run(monkeypatch) -> None:
    called = False

    def fake_launch_cli(run_config_path: Path = app_module.default_config_path) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(app_module, "launch_cli", fake_launch_cli)

    result = runner.invoke(app_module.app, ["create-config", "--help"])

    assert result.exit_code == 0
    assert called is False


def test_run_is_not_available_as_subcommand() -> None:
    result = runner.invoke(app_module.app, ["run"])

    assert result.exit_code != 0
    assert "No such command 'run'" in result.output
