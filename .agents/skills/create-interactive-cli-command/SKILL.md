---
name: create-interactive-cli-command
description: Implement a new command for the Hyperliquid CLI (stateless subcommand and/or interactive REPL command). Use when the user asks to create, add, implement, scaffold, or wire up a command under `src/cli/`, especially when the work needs argument parsing, `--json` / `--dry-run` support, prompt flow, formatter changes, or command-facing tests.
---

# Create CLI Command

## Overview

Follow the repo-specific workflow for adding a new CLI command end to end.
Use the command implementation checklist in `references/new-command-template.md` as the primary procedure.

## Workflow

1. Read `references/new-command-template.md` before editing code.
2. Treat the template as the required implementation order unless the existing codebase clearly makes one step unnecessary.
3. Start by searching for similar commands, reusable formatters, existing `HyperliquidClient` methods in `src/exchange/`, and matching tests.
4. If the command needs new exchange capability, add the Pydantic models in `src/models/` and operation module under `src/exchange/` first, exposing it on `HyperliquidClient`.
5. Reuse existing formatters, command helpers (`src/cli/runtime.py`, `src/cli/commands/parsers.py`), and test helpers before creating new ones.
6. Keep fixture sharing in `conftest.py` when fixtures are reused across test files. Keep fixtures inside a single test class only when they are truly local to that class.
7. For interactive REPL commands, add `help_<command>` so `src/cli/cli_manual.py` picks it up automatically.
8. Run formatting and the relevant pytest scopes listed in the template before concluding.

## Implementation Notes

Prefer the established command patterns already present in `src/cli/commands/` (stateless Typer subcommands with `run_command`) and `src/cli/interactive/` (REPL mixins composed into `InteractiveCLI`).
Keep every source file <= 300 lines.
If a new formatter is required, route through `formatter.format()` type dispatch and private helper methods, matching the existing formatter style.
