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
this repository is for.

## Stack

- **Python >= 3.11**, packaged with `hatchling`, dependencies managed by `uv`
  against a committed `uv.lock`.
- **No runtime dependencies.** The engine boundary is `subprocess`; keep it
  that way. Adding a runtime dependency needs a decision entry.
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
just setup          # uv sync
just fmt            # format + autofix
just check          # fmt-check + lint + typecheck (CI-equivalent)
just test           # run tests; engine tests skip if PrusaSlicer is absent
just test-engine    # run tests; engine tests FAIL if PrusaSlicer is absent
just extract-cli    # regenerate scripts/02_ and 03_ data from captured help
```

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
- Do not add an "assume it worked" escape hatch.

## Status -- what has actually been established

Treat these lines as code: if a change makes one false, the change is not
finished.

- **Windows**: the driver is used regularly against a real
  `prusa-slicer-console.exe`.
- **Linux**: the mocked suite passes and the engine fixture has been exercised
  against a stub, but the driver has **not** been run against a real
  PrusaSlicer install on Linux. Reports welcome.
- **macOS**: untested.
- **CI**: runs `just check` and `just test` on Linux (3.11/3.12/3.13) and
  Windows (3.11). No runner has PrusaSlicer installed, so the engine tests skip
  there and the end-to-end path is **not** covered by CI.

## Constraints

- Do not hand-edit `scripts/02_structured_data/` or
  `scripts/03_restructured_data/`. They are generated; fix the generator and run
  `just extract-cli`.
- Do not reimplement PrusaSlicer's arithmetic. The premise is that the engine
  knows what the slice is and we do not.
- Do not add AI attribution to commits or PR descriptions -- no co-author
  trailers, session links, or "generated with" footers.
- Do not name, link, or describe any private repository in public output.
