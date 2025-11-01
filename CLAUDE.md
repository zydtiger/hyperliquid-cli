# Hyperliquid Smart Order - Project Instructions

## Project Overview

This is a Hyperliquid smart order trading system. The codebase follows a structured architecture with clear separation of concerns.

## Environment Setup

### Critical Requirements

- **Before any bash command**: Load environment with `source ~/.zshrc`
- **For Python execution**: Always use the `finance` conda environment
- **Activation**: `conda activate finance` before running Python files

### Code Formatting

- **After any file modification**: Run `black <file>` to ensure proper formatting
- **Documentation**: Review and update docstrings/comments for consistency with changes
- **File length**: Source files should typically not exceed 300 lines (refactor into multiple files if needed)
- **Test files**: Unit test files are exempt from line limit restrictions and can be arbitrarily long

## File Management Guidelines

### Creating New Files

- **Check for overlaps**: Identify if new functionality overlaps with existing files
- **Cleanup**: Remove obsolete files and update all import statements
- **Organization**: Place files in appropriate directories based on function

### Adding to Config

- **Sample file**: do not read config.json, always read config.example.jsonc for reference of structure, when adding/removing config, modify config.example.jsonc only.

## Code Architecture Principles

### Model/Type Management

- **Centralized models**: All types and models MUST be placed under `src/models/`
- **No local types**: Never create models/types locally in other files
- **Proper categorization**: Use appropriate subdirectories within models/

### Development Approach

- **Reuse existing code**: ALWAYS leverage existing types, models, classes, and functions
- **Avoid duplication**: Never rewrite functionality from scratch if it exists
- **Check codebase first**: Thoroughly search for existing implementations before creating new ones

### Key Conventions

- **Import management**: Clean up imports when removing/renaming files
- **Documentation**: Keep docstrings and comments consistent with code changes
- **Testing**: Ensure all changes maintain test coverage

## Common Workflows

### Adding New Features

1. Search existing codebase for related functionality
2. Check `src/models/` for existing types that can be reused
3. Place new models in appropriate `src/models/` subdirectory
4. Update imports and remove obsolete files
5. Format code with `black`
6. Update unit tests and remove obsolete unit tests
7. Update documentation

### Modifying Existing Code

1. Read and understand the current implementation
2. Check for dependencies and imports
3. Make necessary changes
4. Format with `black`
5. Update unit tests for modified functionality
6. Remove obsolete unit tests if functionality changed significantly
7. Update related documentation

## Project-Specific Notes

- This is a trading system for Hyperliquid exchange
- Maintains compatibility with specific API structures
- Uses type hints extensively for better code reliability
- Follows Python best practices and SOLID principles
