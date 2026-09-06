# AGENTS.md

Instructions for humans and AI coding agents working in this repository.

The org-wide contract at <https://github.com/heibench/.github/blob/main/AGENTS.md>
is the floor. This file carries what is specific to this repository; where the
two conflict, this file wins.

## Project

`prusaslicer-py` is a **driver**, not a checker. It puts the PrusaSlicer
command-line interface under program control: locating the executable, invoking
it, and returning what it established about the engine's output. It does not
adjudicate a design, and it does not post-process G-code.

`scripts/` holds a small extraction pipeline that turns PrusaSlicer's own
`--help` output into a machine-readable description of its CLI surface
(`scripts/03_restructured_data/*.json`). That artifact is a large part of what
this repository is for. Each entry is
`{option, aliases, value, description}`; see `docs/DECISIONS.md` D6, and treat
the schema as stable.

## Stack

- **Python >= 3.11**, packaged with `hatchling`, dependencies managed by `uv`
  against a committed `uv.lock`.
- **No runtime dependencies.** The engine boundary is `subprocess`; keep it
  that way. Adding a runtime dependency needs a decision entry.
- **`prusaslicer_py/slicer.py` is the only module in the package that may
  import `subprocess` or name an executable.** `scripts/01_store_helps.py` is
  the one recorded exception; see `docs/DECISIONS.md` D1.
- **Tooling** -- `ruff` (format + lint), `mypy` (types), `pytest` (tests),
  `just` (task runner), `pre-commit`.

## Layout

```
prusaslicer_py/     the driver; the only module that touches the engine
tests/              pytest suite
examples/           runnable usage examples
scripts/            CLI-surface extraction pipeline (01 -> 02 -> 03)
docs/DECISIONS.md   numbered decisions and their reasoning
```

## Commands

```sh
just setup          # uv sync --locked; fails if uv.lock is stale
just lock           # re-resolve uv.lock after a dependency change, then commit it
just fmt            # format + autofix
just check          # fmt-check + lint + typecheck (CI-equivalent)
just test           # run tests; engine tests skip if PrusaSlicer is absent
just test-engine    # run tests; engine tests FAIL if PrusaSlicer is absent
just extract-cli    # regenerate scripts/02_ and 03_ data from captured help
```

**Every recipe passes `--locked`, so the whole gate fails after a dependency change
until you re-lock.** Edit `pyproject.toml` and `just check` / `just test` exit `2`
with *"The lockfile at `uv.lock` needs to be updated"* -- that is not a test failure
and not a broken environment. Run `just lock`, commit the result, and re-run. The
lockfile is committed and CI runs the same recipes, so a lock nothing verified was a
claim this repo did not keep (D2.1, #23).

Run `just check && just test` before every commit. Never `--no-verify`.

## The engine is optional at test time, and that is load-bearing

PrusaSlicer is not installed on most machines that will run this suite,
including CI. A missing engine is an **environment fault, not a verdict**: it
says nothing about whether this code is correct.

- Tests that need the engine request the `engine` fixture in
  `tests/conftest.py`. It skips when PrusaSlicer is not on `PATH`.
- Setting `PRUSASLICER_PY_REQUIRE_ENGINE` turns that skip into a hard failure.
  Use it on any machine where the engine is supposed to be present.
- **A skipped test is not a passing test.** Guard per-test, never at module
  import: a module-level gate reports one skipped line and silently takes every
  test in the file with it.

## Never let silence read as success

The engine can exit `0` without producing the file it was asked for. A driver
call that did not do the thing must not return as though it did:

- Verify the artifact before reporting it. `slice_model` checks that the G-code
  file exists and is non-empty, and returns a result describing it.
- Capture the engine's `stdout`/`stderr` and hand them to the caller. A
  diagnostic that only reaches the parent process's terminal is unavailable to
  the program that needs it.
- **Decode the engine's output with `errors="replace"`, always.** A strict
  decode raises before the result can be checked, so a byte we cannot read
  becomes a verdict on a slice that succeeded. See `docs/DECISIONS.md` D5.
- Failure carries the same fields as success. Both `SliceEngineError` and
  `SliceOutputError` expose `output_path`, `returncode`, `stdout` and `stderr`;
  do not put a fact in a message string that the success path returns.
- Do not add an "assume it worked" escape hatch.

## Status -- what has actually been established

Treat these lines as code: if a change makes one false, the change is not
finished.

- **The end-to-end path runs against a real engine on four install modes**,
  in the `Engine` workflow: Flathub Flatpak, a Linux distro package on PATH,
  a macOS Homebrew cask `.app` bundle, and the official Windows portable zip.
  Each runs the whole suite with `PRUSASLICER_PY_REQUIRE_ENGINE=1`, including
  `test_slice_produces_gcode_with_the_real_engine`.
- **`CI` runs the mocked suite** on Linux (3.11/3.12/3.13) and Windows with no
  engine, so the engine tests skip and the count says how many were withheld.
- Earlier revisions of this file claimed `check_version` was in regular use on
  Windows. That was false -- it called `--version`, which PrusaSlicer supports
  on no platform. Kept here as a reminder that a Status line is a claim.

## Constraints

- Do not hand-edit `scripts/02_structured_data/` or
  `scripts/03_restructured_data/`. They are generated; fix the generator and run
  `just extract-cli`. A test regenerates them and fails if the committed files
  have drifted from the committed parser.
- Always name an encoding when reading or writing the help output and the JSON
  -- in every stage, `01_store_helps.py` included. The help contains non-ASCII
  characters, and a locale-dependent `open()` is how the data came to say
  `Â°C`. Decode the engine itself with `errors="replace"`.
- Do not reimplement PrusaSlicer's arithmetic. The premise is that the engine
  knows what the slice is and we do not.
- Do not add AI attribution to commits or PR descriptions -- no co-author
  trailers, session links, or "generated with" footers.
- Do not name, link, or describe any private repository in public output.
