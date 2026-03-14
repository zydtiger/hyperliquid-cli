# Command Implementation Template

Use this checklist when implementing a new interactive CLI command for the Hyperliquid trading system.

## Task Definition

Set:
- `Command Name`
- `Feature Description`

## Pre-Implementation Research

- Search existing codebase for similar functionality.
- Check whether the required backend support already exists in `src/backend/exchange/hyperliquid_client.py`, `src/backend/request_handlers.py`, and `src/cli/api.py`.
- Check existing formatters in `src/cli/formatters/`.
- Identify relevant command and CLI-facing test files.

## Phase 1: Backend Prerequisite

Objective:
- Confirm the command can rely on an existing backend/API surface.

Tasks:

### 1.1 Capability Check

- Search the backend exchange client, request handlers, and CLI API client for an existing feature path.
- Reuse an existing CLI API function if one already exposes the needed behavior.
- If backend support is missing or incomplete, use `create-backend-feature` and follow `references/backend-feature-template.md` in that skill before continuing here.

Files typically reviewed:
- `src/backend/exchange/hyperliquid_client.py`
- `src/backend/request_handlers.py`
- `src/cli/api.py`

## Phase 2: CLI Integration

Objective:
- Implement the interactive CLI command.
- Provide consistent output formatting.
- Ensure a smooth user experience.

Tasks:

### 2.1 Command Implementation

- Add command logic to `src/cli/interactive_cli.py`.
- Follow existing command patterns.
- Handle user input validation.
- Implement help text and usage instructions.

### 2.2 Output Formatting

- Review existing formatters in `src/cli/formatters/`.
- Reuse an appropriate existing formatter.
- If needed, create a new formatter following `src/cli/formatters/base.py`.
- Always use type routing in `formatter.format()` to route to internal private functions.
- Ensure consistent output format with other commands.

Files typically modified:
- `src/cli/interactive_cli.py`
- `src/cli/formatters/*` if a new formatter is needed

## Post-Implementation Checklist

### Code Quality

- Run `uv run ruff format <modified_files>` for formatting.
- Clean up unused imports.
- Verify type hints are complete and accurate.
- Keep files under 300 lines when practical; refactor if needed.

### Testing

- Run command-related tests and any integration coverage needed for the new flow.

### Documentation

- Verify command help text is clear.
- Verify examples are present and tested where useful.

## Quick Commands

Before coding:

```bash
rg -n "<similar_feature>" src tests
rg -n "<similar_feature>" src/cli
rg -n "<similar_feature>" src/backend src/cli/api.py
rg --files src/cli/formatters
rg --files tests
```

After each phase:

```bash
uv run ruff format <modified_files>
uv run pytest <relevant_cli_tests>
```
