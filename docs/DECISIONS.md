# Decisions

Numbered decisions with the reasoning that produced them, per the heibench
contract. Do not relitigate an entry; if one is wrong, add a superseding entry.

---

## D1 -- The engine is reached through `subprocess`, never a binding

**Decided:** 2026-09-05 (recorded; the design predates this file)

PrusaSlicer exposes no supported Python API. The CLI is the stable surface, and
it is the one Prusa documents and tests. Driving it over a process boundary
means a PrusaSlicer upgrade cannot break us through ABI drift, only through a
CLI change we can detect.

The consequence is that within the package, `prusaslicer_py/slicer.py` is the
only module that may import `subprocess` or name an executable. Everything the
engine tells us has to come back through that one seam.

Outside the package there is exactly one exception, and it is recorded rather
than waved at: `scripts/01_store_helps.py` runs the engine and names
`prusa-slicer-console.exe` directly, because capturing `--help` is the one job
that has to happen before the driver exists. It is a capture script, not a
consumer of the driver. Nothing else may join it -- `tests/conftest.py`
deliberately resolves the engine by constructing `PrusaSlicer()` and catching
`FileNotFoundError`, rather than repeating the executable-name choice where it
would drift.

---

## D2 -- Packaging is `pyproject` + `uv` with a committed lock

**Decided:** 2026-09-05

Replaces the previous `setup.py` + `requirements.txt`. This matches the other
heibench members and makes `just setup` reproducible. The package itself has
**zero runtime dependencies** and that is deliberate: the driver's job is to
start a process and read what comes back.

`mypy` rather than `pyright` for type checking, matching gerberdiff, so a
contributor moving between members does not meet two type checkers.

---

## D3 -- A missing engine skips; asserting it is present is opt-in

**Decided:** 2026-09-05 (issue #4)

Running the suite without PrusaSlicer installed used to report
`FileNotFoundError` as a **test failure**. That makes "this machine has no
slicer" and "this code is broken" the same red, which is exactly what the org
contract's section 2.2 forbids: an environment fault is not a verdict.

Tests that need the engine take the `engine` fixture, which skips when the
executable is not on `PATH`. But a skipped test is not a passing test, so the
skip is not unconditional: `PRUSASLICER_PY_REQUIRE_ENGINE` turns it into a hard
failure, for any runner that is supposed to have the engine.

**CI does not set that variable today**, because no runner has PrusaSlicer
installed. This is recorded rather than hidden: the end-to-end slice path is not
covered by CI, and `just test` in CI says so in its skip count. Installing
PrusaSlicer on a runner, and then setting the variable, is the follow-up.

The guards are per-test rather than a module-level skip. A module gated at
import reports as one skipped line and takes every test in the file with it --
the failure mode that let partspec's entire end-to-end path disappear behind
23 skips.

---

## D4 -- Licence stays MIT, and that is a choice with an owner

**Decided:** 2026-09-05

The org contract picks Apache-2.0 where the binding leaves the choice open, and
takes what the engine compels where it does not. PrusaSlicer is AGPL-3.0, but
this repository does not link it -- it starts it as a separate process and reads
its stdout, so the AGPL does not reach across that boundary and **the choice is
open**.

By the org's default that argues for Apache-2.0. The repository shipped under
MIT and is left under MIT here, because relicensing is a decision for the
copyright holder to make deliberately rather than a side effect of a scaffolding
change. Flagged for the maintainer; supersede this entry either way.

---

## D5 -- `slice_model` verifies the artifact, and says exactly how far that goes

**Decided:** 2026-09-05 (issue #3)

`slice_model` used to return `None` and run `subprocess.run(..., check=True)`.
The caller's only signal was "it did not raise" -- which the org contract's
section 5 names directly as not a surface. PrusaSlicer can exit 0 having
written nothing, and every such case read to the caller exactly like a
successful slice.

It now returns a `SliceResult` (`output_path`, `size_bytes`, `returncode`,
`stdout`, `stderr`) and raises `SliceOutputError` when the engine exits 0
without producing the G-code. Two things about the shape:

- **The return is the guarantee, not a status to inspect.** `slice_model`
  checks that the file exists and is non-empty *before* returning, so "it did
  not raise" and "the artifact was produced" become the same fact -- a checked
  one. A `produced: bool` on the result would have been a field that is always
  `True`, which is not a state, it is decoration.
- **`SliceOutputError` subclasses `RuntimeError`**, which the method already
  raised for a non-zero exit, so existing callers keep catching it.

The engine's `stdout` and `stderr` are now captured and carried on both the
result and the exception. Previously the one verb that does real work was the
only one that let them escape to the parent's streams, where the program that
needed them could not read them.

### What this deliberately does not establish

It does **not** establish that *this run* wrote the file. A stale G-code left
by an earlier run at the same destination satisfies exists-and-non-empty.

The obvious guard -- compare `st_mtime_ns` before and after -- was implemented,
and then removed, because it does not work. Measured on this machine, 198 of
200 back-to-back writes to a file on `tmpfs` produced an **identical**
`st_mtime_ns`; the check failed in a full test run and passed in isolation,
which is a flaky test rather than a guarantee. Filesystem timestamps are not
fine-grained enough to carry this.

Making the stronger claim requires deleting the destination before invoking the
engine, so that "a file is there afterwards" can only mean this run wrote it.
That is a deliberate change in behaviour -- it destroys the previous output
when a slice fails -- and belongs to the maintainer, not to this change.
Supersede this entry if it is wanted.
