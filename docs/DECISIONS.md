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

The consequence is that `prusaslicer_py/slicer.py` is the only module that may
import `subprocess` or name an executable. Everything the engine tells us has to
come back through that one seam.

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
