# Command Implementation Template

Use this checklist when implementing a new CLI command for the Hyperliquid trading system.

## Task Definition

Set:
- `Command Name`
- `Feature Description`

## Pre-Implementation Research

- Search existing codebase for similar functionality.
- Check whether the required exchange support already exists in `src/exchange/hyperliquid_client.py` and `src/exchange/*_ops.py`.
- Check existing formatters in `src/cli/formatters/`.
- Check shared CLI runtime helpers in `src/cli/runtime.py` and argument parsers in `src/cli/commands/parsers.py`.
- Identify relevant command and CLI-facing test files under `tests/cli/`.

## Phase 1: Exchange Prerequisite

Objective:
- Confirm the command can rely on an existing `HyperliquidClient` method.

Tasks:

### 1.1 Capability Check

- Search `src/exchange/` and `src/models/` for an existing method and response model.
- Reuse an existing `HyperliquidClient` method if one already exposes the needed behavior.
- If exchange support is missing, add models under `src/models/`, implement the operation under `src/exchange/`, expose it on `HyperliquidClient`, and add unit tests under `tests/exchange/`.

Files typically reviewed:
- `src/exchange/hyperliquid_client.py`
- `src/exchange/*_ops.py`
- `src/models/`

## Phase 2: CLI Integration

Objective:
- Implement the stateless subcommand and/or interactive REPL command.
- Support global options (`-c/--config`, `--address`, `--network`, `--json`) and `--dry-run` for write operations.
- Provide consistent output formatting.

Tasks:

### 2.1 Command Implementation

- For stateless subcommands: add the command in the matching module under `src/cli/commands/`, register it in `src/cli/commands/__init__.py`, and route execution through `run_command`.
- For interactive REPL commands: add `do_<command>` to the matching mixin in `src/cli/interactive/` and `help_<command>` in `src/cli/interactive/repl_help.py`.
- Handle user input validation cleanly (raise `CliValidationError` for exit code 2 in stateless commands).

### 2.2 Output Formatting

- Review existing formatters in `src/cli/formatters/`.
- Reuse an appropriate existing formatter.
- If needed, create a new formatter following `src/cli/formatters/base.py`.
- Always use type routing in `formatter.format()` to route to internal private functions.

Files typically modified:
- `src/cli/commands/*`
- `src/cli/interactive/*` and `src/cli/interactive_cli.py`
- `src/cli/formatters/*` if a new formatter is needed

## Post-Implementation Checklist

### Code Quality

- Run `uv run ruff format <modified_files>` for formatting.
- Run `uv run ruff check <modified_files>` and `uv run mypy src tests`.
- Clean up unused imports.
- Keep source files <= 300 lines; refactor if needed.

### Testing

- Run command-related tests in `tests/cli/` covering both human and `--json` modes (and `--dry-run` for write commands).

### Documentation

- Verify command help text is clear.
- Ensure interactive commands have matching `help_*` methods discovered by `src/cli/cli_manual.py`.
- Update `README.md` if adding a top-level subcommand.

## Quick Commands

Before coding:

```bash
rg -n "<similar_feature>" src tests
rg -n "<similar_feature>" src/cli
rg -n "<similar_feature>" src/exchange src/models
rg --files src/cli/formatters
rg --files tests
```

After each phase:

```bash
uv run ruff format <modified_files>
uv run pytest <relevant_cli_tests>
```
