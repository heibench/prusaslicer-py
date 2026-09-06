# prusaslicer-py task runner

set dotenv-load := false

# Every recipe below reaches uv, and `uv run` locks-and-syncs by default -- so
# `just test` on a stale lock rewrote uv.lock, exit 0, no diagnostic, exactly as
# `uv sync` did. Verifying only in `setup` fixed CI (which runs setup first and
# stops on failure) and left the local half of #23 open: after the first day
# nobody runs setup again.
#
# `lock` is the one place allowed to write it, and unsets this for that one call.
export UV_LOCKED := "1"

# Show available recipes
default:
    @just --list

# Install dependencies from the committed lockfile, and fail if it is stale
setup:
    uv sync --locked

# Separate from `setup` on purpose. A setup that quietly fixes the thing it is meant to
# verify is the same defect with a friendlier face (#23).
#
# The blank line below is load-bearing: `just` takes the LAST comment line before a
# recipe as its doc string, so without it this rationale would be what `just --list`
# shows. `[doc(...)]` says the same thing more clearly and needs just >= 1.27.0, where an
# unknown attribute is a PARSE error -- it would break every recipe in this file for
# anyone on an older just, including Ubuntu 24.04 LTS.

# Re-resolve and rewrite uv.lock; run when a dependency changes, then commit it
lock:
    UV_LOCKED=0 uv lock

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
