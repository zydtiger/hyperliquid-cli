# Hyperliquid CLI - Project Instructions

Hyperliquid smart order trading system with structured architecture.

## Environment

- **Python execution**: `uv run <python command>`
- **After file changes**: `uv run ruff format <file>`
- **File length**: Source files max 300 lines (refactor if needed)
- **Test files**: No length limit

## Validation

- **Hook runner**: `uv tool install prek` once per machine, then `prek install`
- **Full**: `prek run --all-files && prek run --all-files --hook-stage pre-push`
- **Targeted**: `uv run pytest tests/<file>` or a `::<test>` selector
- Mechanical scope — lint, format, types, file hygiene — is defined solely by
  `.pre-commit-config.yaml`; tests run from the same file as a `pre-push` stage
  hook. Do not restate those commands or their scopes elsewhere.
- **CI** (`.github/workflows/ci.yml`) invokes the same hook runner rather than
  restating hook commands: a `lint` job runs the commit-stage hooks once, and a
  matrixed `test` job runs the pre-push stage on every supported Python
  version, then builds and smoke-tests the wheel on the lowest one.

## Code Rules

### Models & Types

- All models in `src/models/`
- No local type definitions
- Use appropriate subdirectories

### Development

- Reuse existing code, models, functions
- Search codebase before creating new
- Clean up imports when removing files
- Define `__all__` only in `__init__.py` files; do not add `__all__` to other modules
- Maintain test coverage
- Use `pytest-suite-generator` agent for unit tests

### Config Files

- Reference: `config.example.yaml`
- Only modify `config.example.yaml`

## Workflow

### Project Skills

Task workflows for this repository live in `.agents/skills/`, one directory per
skill with a `SKILL.md`. Read the matching `SKILL.md` and follow it before
falling back to a general approach:

| Skill | Use for |
| --- | --- |
| `create-backend-feature` | Adding or modifying backend functionality |
| `create-interactive-cli-command` | Adding a command to the interactive CLI |

### Adding Features

1. Search existing codebase
2. Check `src/models/` for reusable types
3. Add new models to `src/models/`
4. Update imports, remove obsolete files
5. Format with `ruff format`
6. Update tests, remove obsolete unit tests
7. Update docs

### Modifying Code

1. Read current implementation
2. Check dependencies
3. Make changes
4. Format with `ruff format`
5. Update tests, remove obsolete unit tests if needed
6. Update docs

## Project Notes

- Hyperliquid exchange trading system
- Uses type hints extensively
- Follows Python best practices

## API Documentation

- Update `docs/api.md` for any API changes
- Include endpoints, parameters, responses, examples
