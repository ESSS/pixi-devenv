# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

pixi-devenv is a code generation tool that aggregates multiple pixi projects in development mode. It reads `pixi.devenv.toml` files and generates standard `pixi.toml` configuration files by consolidating dependencies, features, and environment variables from upstream projects.

## Development Commands

This project uses `uv` for development (pure Python package, not using pixi for self-development).

### Testing

```bash
# Run all tests
uv run pytest

# Run specific test
uv run pytest tests/test_consolidate.py

# Run tests with verbose output
uv run pytest -v
```

### Type Checking

```bash
uv run mypy
```

### Linting and Formatting
```bash
# Format code
uv run ruff format

# Check and auto-fix issues
uv run ruff check --fix
```

### Pre-commit Hooks

Commit hooks handle linting, formatting and type-checking. 

```bash
# Install hooks
uv run pre-commit install

# Run manually
uv run pre-commit run --all-files
```

### Running the Tool
```bash
# Update pixi.toml from pixi.devenv.toml in current directory
uv run pixi-devenv update

# Initialize a new pixi.devenv.toml
uv run pixi-devenv init
```

## Code Architecture

### Core Data Flow

1. **Workspace Construction** (`workspace.py`):
   - Starts from a `pixi.devenv.toml` file (the "starting project")
   - Recursively loads upstream projects via `[devenv.upstream]` references
   - Builds a dependency graph and topologically sorts it
   - Detects cycles in the dependency chain

2. **Consolidation** (`consolidate.py`):
   - Iterates projects from upstream to downstream
   - Merges dependencies, constraints, and environment variables based on inheritance rules
   - Handles platform-specific targets using `target_matches_platforms()`
   - **Critical**: Platform filtering must happen BEFORE consolidating targets/features

3. **Update/Generation** (`update.py`):
   - Reads existing `pixi.toml` file
   - Calls consolidation logic
   - Generates TOML structure with proper comments ("Managed by devenv")
   - Writes updated `pixi.toml` preserving structure

### Key Modules

- **`project.py`**: Data models for pixi.devenv.toml schema (`Project`, `Spec`, `Aspect`, `Feature`)
- **`workspace.py`**: Multi-project graph construction and topological sorting
- **`consolidate.py`**: Core merging logic that combines upstream projects
- **`update.py`**: TOML generation and file writing
- **`cli.py`**: Command-line interface (update, init commands)
- **`init.py`**: Scaffold new pixi.devenv.toml files

### Important Concepts

**Inheritance Rules**:
- Dependencies/constraints: inherited by default (controlled by `[devenv.inherit]`)
- Features: NOT inherited by default (must be explicitly requested via `[devenv.inherit.features]`)
- Environments: NEVER inherited, defined directly in `pixi.toml`
- Environment variables: inherited by default, support both string values and tuple values (for path-like vars)

**Platform Filtering**:
- Platforms resolved at the starting project level
- Targets filtered using aggregate selectors: "win"/"windows", "linux", "osx"/"macos", "unix"
- Platform-specific environment variables only rendered if target matches resolved platforms
- See `target_matches_platforms()` helper in `consolidate.py`

**Spec Merging**:
- Version specs combined using intersection logic
- Constraint specs applied when downstream explicitly declares the same dependency
- Source tracking maintains which projects contributed each dependency

### Testing Patterns

**Regression Tests**: Use `file_regression.check()` from pytest-regressions for complex output verification:
```python
def test_example(file_regression):
    result = generate_complex_output()
    file_regression.check(result, extension=".toml")
```
- First run creates baseline files in `tests/test_<module>/test_<name>.toml`
- Subsequent runs compare against baseline
- Used extensively in `test_consolidate.py` and `test_update.py`

## Release Process

Releases are published to conda-forge, NOT PyPI.

1. Create branch `release-X.Y.Z`
2. Update version in `pyproject.toml`
3. Update `CHANGELOG.md`
4. Run `uv lock` to update lock file
5. Open PR, get approval
6. Create GitHub release using `release-X.Y.Z` branch
7. Merge PR (**do not squash**)
8. conda-forge bot will auto-create feedstock PR

## Code Style

- Line length: 110 characters (ruff.toml)
- Type checking: strict mode enabled (mypy.ini)
- All code must pass mypy, ruff format, and ruff check
