# prusaslicer-py task runner

set dotenv-load := false

# Show available recipes
default:
    @just --list

# Install dependencies from the committed lockfile, and fail if it is stale
setup:
    uv sync --locked

# Separate from `setup` on purpose. `uv sync` alone updates the lockfile when it is out
# of date and says nothing, so a setup that quietly fixes the thing it is meant to verify
# is the same defect with a friendlier face -- and CI runs `setup`, so its green could not
# have failed on a stale lock (#23).
#
# `[doc]` rather than a trailing comment: `just` takes the LAST comment line as the doc
# string, so a multi-line rationale silently publishes its final line to `just --list`.
[doc("Re-resolve and rewrite uv.lock; run when a dependency changes, then commit it")]
lock:
    uv lock

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
