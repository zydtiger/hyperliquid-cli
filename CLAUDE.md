# Hyperliquid CLI - Project Instructions

Hyperliquid smart order trading system with structured architecture.

## Environment

- **Before any bash command**: `source ~/.zshrc`
- **Python execution**: `conda activate finance`
- **After file changes**: `black <file>`
- **File length**: Source files max 300 lines (refactor if needed)
- **Test files**: No length limit

## Code Rules

### Models & Types
- All models in `src/models/`
- No local type definitions
- Use appropriate subdirectories

### Development
- Reuse existing code, models, functions
- Search codebase before creating new
- Clean up imports when removing files
- Maintain test coverage
- Use `pytest-suite-generator` agent for unit tests

### Config Files
- Reference: `config.example.yaml`
- Only modify `config.example.yaml`

## Workflow

### Adding Features
1. Search existing codebase
2. Check `src/models/` for reusable types
3. Add new models to `src/models/`
4. Update imports, remove obsolete files
5. Format with `black`
6. Update tests, remove obsolete unit tests
7. Update docs

### Modifying Code
1. Read current implementation
2. Check dependencies
3. Make changes
4. Format with `black`
5. Update tests, remove obsolete unit tests if needed
6. Update docs

## Project Notes
- Hyperliquid exchange trading system
- Uses type hints extensively
- Follows Python best practices

## API Documentation
- Update `docs/api.md` for any API changes
- Include endpoints, parameters, responses, examples
