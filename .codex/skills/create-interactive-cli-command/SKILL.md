---
name: create-interactive-cli-command
description: Implement a new command for the Hyperliquid interactive CLI. Use when the user asks to create, add, implement, scaffold, or wire up a new command in `src/cli/interactive_cli.py`, especially when the work also needs backend exchange logic, API handlers, CLI API client updates, formatter changes, tests, and API docs.
---

# Create Interactive Cli Command

## Overview

Follow the repo-specific workflow for adding a new interactive CLI command end to end.
Use the command implementation checklist in `references/new-command-template.md` as the primary procedure.

## Workflow

1. Read `references/new-command-template.md` before editing code.
2. Treat the template as the required implementation order unless the existing codebase clearly makes one step unnecessary.
3. Start by searching for similar commands, reusable models, existing formatters, and matching tests.
4. Implement backend exchange logic and tests first, then the API layer, then the interactive CLI command and formatter work.
5. Reuse existing models, formatters, and test helpers before creating new ones.
6. Keep fixture sharing in `conftest.py` when fixtures are reused across test files. Keep fixtures inside a single test class only when they are truly local to that class.
7. Update `docs/api.md` when the command adds or changes a backend endpoint.
8. Run formatting and the relevant pytest scopes listed in the template before concluding.

## Implementation Notes

Prefer the established command pattern already present in `src/cli/interactive_cli.py`.
Prefer minimal, repo-consistent additions over introducing new abstractions.
If a new formatter is required, route through `formatter.format()` type dispatch and private helper methods, matching the existing formatter style.
