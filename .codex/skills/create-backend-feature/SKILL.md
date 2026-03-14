---
name: create-backend-feature
description: Implement backend functionality for the Hyperliquid CLI project. Use when the user asks to add or modify exchange client logic, backend request handlers, CLI API client methods, backend tests, or `docs/api.md`, including when a new interactive CLI command requires new backend support.
---

# Create Backend Feature

## Overview

Follow the repo-specific workflow for backend feature work that spans exchange integration, service handlers, CLI API wiring, tests, and API documentation.
Use `references/backend-feature-template.md` as the primary implementation checklist.

## Workflow

1. Read `references/backend-feature-template.md` before editing code.
2. Treat the template as the required implementation order unless the existing codebase clearly makes one step unnecessary.
3. Start by searching for similar backend features, reusable models, existing request handlers, and matching tests.
4. Implement exchange-layer changes and unit tests first, then request handlers, then CLI API client integration and API docs.
5. Reuse existing models, request and response shapes, and test helpers before creating new ones.
6. Keep fixture sharing in `conftest.py` when fixtures are reused across test files. Keep fixtures inside a single test class only when they are truly local to that class.
7. Update `docs/api.md` whenever backend endpoints are added or changed.
8. Run formatting and the relevant pytest scopes listed in the template before concluding.

## Implementation Notes

Prefer minimal, repo-consistent additions over introducing new abstractions.
Keep all models in `src/models/` and avoid local type definitions.
If this backend work exists to support a new interactive CLI command, hand off command wiring and formatter changes to `create-interactive-cli-command` after the backend and API surface are ready.
