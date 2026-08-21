# Backend Feature Implementation Template

Use this checklist when implementing backend exchange and API functionality for the Hyperliquid trading system.

## Task Definition

Set:
- `Feature Name`
- `Feature Description`

## Pre-Implementation Research

- Search existing codebase for similar functionality.
- Review `src/models/` for reusable data models.
- Identify relevant backend client tests in `tests/backend/hyperliquid_client/`.
- Check whether existing request handlers or CLI API functions already cover part of the flow.

## Phase 1: Backend Foundation

Objective:
- Establish data models and core exchange functionality.
- Set up comprehensive unit testing.

Tasks:

### 1.1 Model Research and Definition

- Search `src/models/` for existing relevant models.
- Reuse existing models when possible.
- Define new models only if existing ones are insufficient.
- Place new models in the appropriate `src/models/` subdirectory.

### 1.2 Exchange Integration

- Update `src/backend/exchange/hyperliquid_client.py` with the new feature.
- Implement core exchange functionality.
- Handle errors and edge cases.

### 1.3 Unit Testing

- Write comprehensive unit tests in `tests/backend/hyperliquid_client/`.
- Use existing test file patterns or create a new one if needed.
- Test all success and failure scenarios.
- Ensure test coverage meets project standards.

Files typically modified:
- `src/backend/exchange/hyperliquid_client.py`
- `tests/backend/hyperliquid_client/*`

## Phase 2: API Layer

Objective:
- Expose functionality through the backend service and CLI API client.
- Provide stable integration points for CLI commands.
- Document API endpoints.

Tasks:

### 2.1 API Endpoint Implementation

- Add the new endpoint in `src/backend/request_handlers.py`.
- Implement request validation and error handling.
- Add endpoint tests to `tests/backend/test_service.py`.

### 2.2 CLI API Integration

- Add the API-calling function to `src/cli/api.py`.
- Follow existing API client patterns.
- Handle API response parsing and error propagation.

### 2.3 Documentation

- Update `docs/api.md` with the new or changed endpoint.
- Include:
  - Endpoint path and HTTP method
  - Request parameters and body structure
  - Response format and examples
  - Error codes and handling

Files typically modified:
- `src/backend/request_handlers.py`
- `tests/backend/test_service.py`
- `src/cli/api.py`
- `docs/api.md`

## Post-Implementation Checklist

### Code Quality

- Run `uv run ruff format <modified_files>` for formatting.
- Clean up unused imports.
- Verify type hints are complete and accurate.
- Keep files under 300 lines when practical; refactor if needed.

### Testing

- Run unit tests for the touched backend client area.
- Run `uv run pytest tests/backend/test_service.py` when the API layer changes.
- Run any focused tests for shared models or helper modules touched by the feature.

### Handoff

- If this backend feature exists to support a new interactive command, hand off command wiring and formatter work to `create-interactive-cli-command`.

## Quick Commands

Before coding:

```bash
rg -n "<similar_feature>" src tests
rg --files src/models
rg --files tests/backend/hyperliquid_client
```

After each phase:

```bash
uv run ruff format <modified_files>
uv run pytest tests/backend/hyperliquid_client/
uv run pytest tests/backend/test_service.py
```
