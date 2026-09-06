# prusaslicer-py task runner

set dotenv-load := false

# Show available recipes
default:
    @just --list

# Install dependencies and set up the environment
setup:
    uv sync

# Format code and apply lint fixes (mutates the working tree)
fmt:
    uv run ruff format .
    uv run ruff check --fix .

# Verify formatting without mutating (CI)
fmt-check:
    uv run ruff format --check .

# Lint
lint:
    uv run ruff check .

# Type-check
typecheck:
    uv run mypy prusaslicer_py/ tests/

# Format-check + lint + typecheck -- the CI-equivalent gate
check: fmt-check lint typecheck

# Run tests. PrusaSlicer-dependent tests skip when the engine is absent.
test:
    uv run pytest

# Run tests and fail (rather than skip) if PrusaSlicer is not installed
test-engine:
    PRUSASLICER_PY_REQUIRE_ENGINE=1 uv run pytest

# Regenerate the machine-readable CLI surface from the captured help output
# Capture PrusaSlicer's --help into scripts/01_helps (needs the engine installed).
# The captures are PrusaSlicer's output and are not committed -- see D8.
capture-cli:
    uv run python scripts/01_store_helps.py

extract-cli:
    uv run python scripts/02_json_cli.py
    uv run python scripts/03_restructure_cli.py

# Remove build and tool caches
clean:
    rm -rf .venv dist .pytest_cache .ruff_cache .mypy_cache
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
