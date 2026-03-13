# Command Implementation Template

Use this checklist when implementing a new CLI command for the Hyperliquid trading system.

## Task Definition

Set:
- `Command Name`
- `Feature Description`

## Pre-Implementation Research

- Search existing codebase for similar functionality.
- Review `src/models/` for reusable data models.
- Check existing formatters in `src/cli/formatters/`.
- Identify relevant test files in `tests/backend/hyperliquid_client/`.

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
- Expose functionality through REST API.
- Provide frontend integration points.
- Document API endpoints.

Tasks:

### 2.1 API Endpoint Implementation

- Add the new endpoint in `src/backend/request_handlers.py`.
- Implement request validation and error handling.
- Add endpoint tests to `tests/backend/test_service.py`.

### 2.2 Frontend API Integration

- Add the API-calling function to `src/cli/api.py`.
- Follow existing API client patterns.
- Handle API response formatting.

### 2.3 Documentation

- Update `docs/api.md` with the new endpoint.
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

## Phase 3: CLI Integration

Objective:
- Implement the interactive CLI command.
- Provide consistent output formatting.
- Ensure a smooth user experience.

Tasks:

### 3.1 Command Implementation

- Add command logic to `src/cli/interactive_cli.py`.
- Follow existing command patterns.
- Handle user input validation.
- Implement help text and usage instructions.

### 3.2 Output Formatting

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

- Run unit tests for the touched backend client area.
- Run `uv run pytest tests/backend/test_service.py` when the API layer changes.
- Run command-related tests and any integration coverage needed for the new flow.

### Documentation

- Verify API documentation is complete and accurate.
- Verify command help text is clear.
- Verify examples are present and tested where useful.

## Quick Commands

Before coding:

```bash
rg -n "<similar_feature>" src tests
rg --files src/models
rg --files src/cli/formatters
rg --files tests/backend/hyperliquid_client
```

After each phase:

```bash
uv run ruff format <modified_files>
uv run pytest tests/backend/hyperliquid_client/
uv run pytest tests/backend/test_service.py
```
