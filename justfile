# prusaslicer-py task runner

set dotenv-load := false

# `--locked` on every uv invocation below, not an exported UV_LOCKED. Same effect,
# and it keeps `lock` free of a `VAR=x cmd` prefix -- `engine.yml` records that
# construct as POSIX-only and not runnable on its Windows job, and `lock` is the
# only way out of a stale lock, so it is the one recipe that must work everywhere.
#
# `uv run` locks-and-syncs by DEFAULT, which is the whole of #23's local half:
# `just test` on a stale lock rewrote uv.lock at exit 0 with no diagnostic, exactly
# as `uv sync` did. Verifying only in `setup` fixed CI -- which runs setup first and
# stops -- and left a contributor where they started, since nobody runs setup twice.

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
# shows. `[doc(...)]` says the same thing more clearly, and is not used: an unknown
# attribute is a PARSE error in every just, and `[doc]` only exists from 1.27.0 -- so one
# of them breaks EVERY recipe in this file for anyone on an older just, Ubuntu 24.04 LTS
# included.

# Re-resolve and rewrite uv.lock; run when a dependency changes, then commit it
lock:
    uv lock

# Format code and apply lint fixes (mutates the working tree)
fmt:
    uv run --locked ruff format .
    uv run --locked ruff check --fix .

# Verify formatting without mutating (CI)
fmt-check:
    uv run --locked ruff format --check .

# Lint
lint:
    uv run --locked ruff check .

# Type-check
typecheck:
    uv run --locked mypy .

# Format-check + lint + typecheck -- the CI-equivalent gate
check: fmt-check lint typecheck

# Run tests. PrusaSlicer-dependent tests skip when the engine is absent.
test:
    uv run --locked pytest

# Run tests and fail (rather than skip) if PrusaSlicer is not installed
test-engine:
    PRUSASLICER_PY_REQUIRE_ENGINE=1 uv run --locked pytest

# Regenerating the CLI surface is two steps and only the first needs the engine, so
# they are separate recipes. The captures are PrusaSlicer's output rather than ours
# and are not committed -- see D8.
#
# One comment line each below the blank, per the rule above `lock`: these three lines
# used to sit directly against `capture-cli`, so `just --list` published the D8
# sentence as its description and `extract-cli`'s own line was absorbed upward,
# leaving it with none (#27).

# Capture PrusaSlicer's --help into scripts/01_helps (needs the engine installed)
capture-cli:
    uv run --locked python scripts/01_store_helps.py

# Regenerate the machine-readable CLI surface from the captured help output
extract-cli:
    uv run --locked python scripts/02_json_cli.py
    uv run --locked python scripts/03_restructure_cli.py

# Remove build and tool caches
[unix]
clean:
    rm -rf .venv dist .pytest_cache .ruff_cache .mypy_cache
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Remove build and tool caches
[windows]
clean:
    powershell -NoLogo -Command "Get-Item -ErrorAction SilentlyContinue .venv, dist, .pytest_cache, .ruff_cache, .mypy_cache | Remove-Item -Recurse -Force; Get-ChildItem -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue"
