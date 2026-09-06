# Changelog

All notable changes to prusaslicer-py are documented here. Follows
[Keep a Changelog](https://keepachangelog.com) and
[Semantic Versioning](https://semver.org).

## [Unreleased]

### Fixed

- **The typechecker covers the whole repository, and `scripts/` is annotated**
  (#24). `typecheck` named `prusaslicer_py/ tests/`, so `scripts/` -- which holds
  the CLI-surface extraction that produces the data the package ships -- was
  never checked, and `examples/` was outside it on the same terms. The recipe now
  runs `mypy .`, which cannot omit a directory by forgetting to list it, and a
  test asserts that spelling.

  Scope alone would have bought almost nothing. mypy skips the body of an
  unannotated function, and 12 of the 13 functions in `scripts/` were
  unannotated; `check_untyped_defs` reads those bodies, but with no signatures to
  check calls against, `save_json(path, data)` -- arguments reversed -- still
  passed. All 12 signatures are now annotated and `disallow_untyped_defs` holds
  `scripts/` there, so the call sites are checked too.

  The records the extraction emits are a `TypedDict` rather than
  `dict[str, object]`, which is what puts the schema D6 froze under the
  typechecker: a renamed key, a wrong field type, or an `option` that could be
  `None` are now errors rather than valid `object`s. The flag pairs that feed it
  are `tuple[str, str | None]`, matching D6's `option: str` -- the previous
  `list[list[str | None]]` declared the spelling nullable, which it never is.

  What the first pass of this actually turned up was smaller than a defect
  report: three `var-annotated` errors on empty literals in `scripts/`, where
  mypy could not infer an element type, and six in `tests/` from calling
  `module_from_spec` on a possibly-`None` spec. Nothing had behaved wrongly. The
  value here is the checking that now exists, not the errors it cleared on the
  way in.

- **`just --list` describes every recipe, and describes them correctly** (#27).
  `just` publishes the LAST comment line before a recipe, so `capture-cli`'s
  three-line block published a note about D8 instead of a description, and
  `extract-cli` had none at all -- its own line having been absorbed into the
  block above it. Rationale now sits above a blank line, where `just` cannot
  reach it, and a test asserts every recipe has exactly one comment line
  directly above it.

### Changed

- **Every recipe verifies the committed lockfile instead of silently rewriting
  it** (#23). `setup` runs `uv sync --locked` and the rest pass `--locked` to
  `uv run`, which locks-and-syncs by default -- so `just test` on a stale lock
  used to rewrite `uv.lock` at exit 0 with no diagnostic. CI runs these same
  recipes, so the gate could not previously fail on a stale lock. **The whole
  gate now fails after a dependency change until you re-lock**, which is the
  intended friction.

  **New recipe `just lock`** re-resolves and rewrites it -- the only place
  allowed to. Run it when a dependency changes, then commit the result.

## [0.1.0] — 2026-09-06

### Added

First release. Notable, given this began as a thin `subprocess` wrapper:

- Flatpak discovery. `shutil.which` cannot see a Flatpak — the app is not on
  PATH and there is no binary to find — so a Flathub install, which is how
  PrusaSlicer is normally installed on Linux, previously read as "not
  installed". `PrusaSlicer.engine_kind` reports `path` or `flatpak` so a caller
  can branch (D9).
- `SliceResult` returned from `slice_model`, carrying `output_path`,
  `size_bytes`, `returncode`, `stdout` and `stderr`. The artifact is verified to
  exist and be non-empty before a result is returned, so "the engine produced
  the file" and "the call did not raise" stop being the same claim (D5).
- `SliceError`, with `SliceEngineError` and `SliceOutputError` siblings. Both
  carry the same fields, so the failure path is as inspectable as the success
  path.
- `just capture-cli` regenerates PrusaSlicer's help locally, through the driver
  rather than a hardcoded Windows executable name.
- Real-engine CI across install modes — Flathub Flatpak, AppImage on PATH,
  Homebrew cask, Chocolatey — each with a missing engine as a hard failure
  rather than a skip.
- Repository floor: `pyproject` + `uv` with a committed lock, `justfile`, CI on
  Linux and Windows, pre-commit, `AGENTS.md`, `docs/DECISIONS.md`.

### Fixed

- `check_version()` called `--version`, which PrusaSlicer has never supported —
  2.9.6 answers `Unknown option --version` and exits 1. The version is read
  from the first line of `--help`, which is the only place the engine prints
  it. Every stub in the suite answered `--version`, so the tests agreed with
  the code and both were wrong.
- `get_example_shapes()` ignored an explicitly supplied `slicer_path` and
  re-ran discovery, raising `FileNotFoundError` even when handed a working
  engine.
- A Flatpak's own files are mounted at `/app` inside the sandbox, so bundled
  example shapes were real to the caller and absent to the engine. Paths under
  the app tree are translated; paths outside it are granted with
  `--filesystem=<dir>`, only for the directories involved.
- An undecodable byte in the engine's output raised `UnicodeDecodeError` before
  the result could be verified, reporting failure for a slice that succeeded.
- The CLI-surface extraction dropped 68 distinct options — every one whose
  description began on the following line — mis-split 7 aliased options, and
  carried cp1252 mojibake from a Windows capture. It also discarded any section
  whose name matched none of three hardcoded buckets, which silently lost
  PrusaSlicer 2.9.6's entire `input:` section.

### Changed

- Licensed under Apache-2.0, superseding MIT (D7).
- PrusaSlicer's captured `--help` output is no longer committed; regenerate it
  with `just capture-cli` (D8).

[Unreleased]: https://github.com/heibench/prusaslicer-py/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/heibench/prusaslicer-py/releases/tag/v0.1.0
