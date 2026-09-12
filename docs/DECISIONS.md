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

This once had an exception, and it no longer does. `scripts/01_store_helps.py`
named `prusa-slicer-console.exe` directly, on the argument that capturing
`--help` is the one job that has to happen before the driver exists. That
argument was wrong twice: the driver does exist by then, and hardcoding the
Windows executable made the capture Windows-only. The script now constructs
`PrusaSlicer()` like everything else, so `prusaslicer_py/slicer.py` is the only
place outside the tests that names an executable, with no carve-out. The tests
name executable paths -- some fake, some plausible-looking -- as return values
for a `subprocess` stand-in, which is the seam being exercised rather than a
second home for the real choice.

`examples/` named `prusa-slicer-console.exe` too, and was Windows-only for
exactly the reason given above for removing the script's carve-out. Both examples
now construct `PrusaSlicer()`.

This is now enforced rather than asserted:
`tests/test_repo_gates.py::test_only_the_driver_names_the_engine_executable`
fails on an executable-name literal in any `.py` outside `slicer.py` and
`tests/`. The gate exists because this paragraph was rewritten three times and
was wrong all three -- describing a carve-out the code had removed, then
overlooking the tests, then overlooking `examples/` -- each time from memory when
a grep would have settled it.

`tests/conftest.py` resolves the engine the same way -- constructing
`PrusaSlicer()` and catching `FileNotFoundError` -- rather than repeating the
executable-name choice where it would drift.

**Amended 2026-09-06 (#24).** The exception was removed when the script was
changed, but this entry and `AGENTS.md` went on describing it, so both asserted
a carve-out the code had already closed and pointed readers at a name
`01_store_helps.py` no longer contains. Section 2.5 counts a stale status claim
as a defect in the gate, and a decision record is the strongest status claim
there is.

---

## D2 -- Packaging is `pyproject` + `uv` with a committed lock

**Decided:** 2026-09-05

Replaces the previous `setup.py` + `requirements.txt`. This matches the other
heibench members and makes `just setup` reproducible. The package itself has
**zero runtime dependencies** and that is deliberate: the driver's job is to
start a process and read what comes back.

`mypy` rather than `pyright` for type checking, matching gerberdiff, so a
contributor moving between members does not meet two type checkers.

### D2.1 -- the lock is verified, never silently repaired (amendment, #23)

"Committed lock" was half a claim: nothing checked it. `just setup` ran `uv sync`,
which **updates** a stale lockfile rather than failing, and every other recipe
reaches `uv run`, which locks-and-syncs by default. Measured, with a dependency
added to `pyproject.toml` and the lock left alone: `uv sync` and `just lint` both
exited `0` and rewrote `uv.lock`, with no diagnostic on either.

CI runs `just setup`, so the gate could not fail on a stale lock and its green
said nothing about the dependency set that shipped.

`setup` is `uv sync --locked`, and **every other recipe passes `--locked` to
`uv run`** -- which matters more locally, because after the first day nobody runs
`setup` again, so verifying only there fixes CI and leaves the contributor exactly
where they were.

Per-invocation rather than an exported `UV_LOCKED`, and the trade is real in both
directions. The exported form needs `lock` to override it with a `VAR=x cmd`
prefix, and `engine.yml` records that construct as POSIX-only and not runnable on
its Windows job; whether that record is right is a separate question (#30). `lock`
is the only way out of a stale lock, so it is the one recipe that must work
everywhere and must not depend on the answer. `--locked` is also the more portable
flag by version: uv has accepted it since at least 0.5.5, where `uv lock
--no-locked` -- the purpose-built escape for the exported form -- landed only in
0.12.9.

**What it costs is that the guard is fail-open.** An exported variable protects a
recipe added next year by default; ten explicit flags do not, and a new `uv run`
without one would silently rewrite the lock at exit 0 -- the exact defect. So the
convention is gated rather than remembered:
`tests/test_repo_gates.py::test_every_uv_run_in_the_justfile_is_locked` fails on any
unflagged `uv run`, and a sibling asserts `uv lock` appears exactly once. A check
that cannot fail is not a check (`CONTRIBUTING.md`).

**`lock` is the only recipe that writes the lock.** Separate from `setup` on
purpose: a setup that quietly fixes the thing it is meant to verify is the same
defect with a friendlier face, which is the whole of #23.

**No `[doc(...)]` attributes anywhere in the justfile.** Unknown attributes are a
**parse** error in every `just` -- not a warning -- and `[doc]` was only added in
1.27.0, so one of them breaks *every recipe in the file* for anyone on an older
one, including Ubuntu 24.04 LTS. The blank line above a recipe's doc comment does
the same job on any version: `just` takes the last comment line before a recipe as
its doc string.

That rule has a cost, and #27 is what it looks like: a recipe with a two-line
comment publishes the **wrong** line, and the recipe below it can be left with
none. So the convention is **exactly one comment line directly above each recipe,
rationale above a blank line**, gated by
`tests/test_repo_gates.py::test_every_recipe_has_exactly_one_doc_comment_line`.

Two gates, and the second is the one that asserts the property:
`test_every_listed_recipe_has_a_description` reads `doc` straight off `just`'s own
output, so nothing a reader sees in `just --list` can be blank. The comment count is
a proxy for how that happens; the doc check is the thing itself, and it caught a hole
the proxy missed during review.

Both read `just --dump --dump-format json` for the authoritative recipe list rather
than parsing the file. The first version did parse it and skipped any line with an
`=` before the colon -- silently excluding every recipe with a **defaulted
parameter**, so #27 could be reintroduced verbatim on one and the test stayed green.
A second round found the same shape again: a `lint := "ruff"` assignment sharing a
recipe's name matched before the recipe did. Both found in review, both fail-open on
the defect being gated. Where the tool will answer a question about itself, ask it.

**This does not undercut the `[doc]` ban.** `--dump-format json` has shipped since
just **0.10.4** (2021-11-21) and the format was stabilised in **1.15.0**
(2023-10-09); `[doc]` only arrived in **1.27.0** (2024-05-25). Ubuntu 24.04 LTS's
1.21.0 is above the stabilisation and below the attribute, so the contributor that
ban protects can still run these gates. If some `just` ever cannot, the gate names
the tool and prints its stderr rather than raising a bare `CalledProcessError`.

**What the comment-count gate does and does not guarantee.** It is a best-effort
read of the *file*, and its blind spot is text that is not code: `just` parses a
string literal or a recipe body, this reads lines. Three shapes are known to slip
it, all found in review, none present here:

- a triple-quoted string whose interior contains a line shaped like a recipe head
- under `allow-duplicate-recipes`, a superseded definition (mitigated: the scan runs
  bottom-up, matching `just`'s own last-wins precedence)
- recipes inside a `mod` submodule, which live under the dump's `modules` key rather
  than `recipes` (mitigated: the gate refuses to run at all once a module exists,
  rather than passing over it silently)

`test_every_listed_recipe_has_a_description` has no such blind spot -- it reads
`just`'s own answer -- which is why it is the gate to trust and the count is the one
that explains *how* a description goes wrong. Stating the limit is the point: an
implied completeness this cannot deliver would be the same defect one level up.

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

**Decided:** 2026-09-05 · **SUPERSEDED by D7, 2026-09-05**

The org contract picks Apache-2.0 where the binding leaves the choice open, and
takes what the engine compels where it does not. PrusaSlicer is AGPL-3.0, but
this repository does not link it -- it starts it as a separate process and reads
its stdout, so the AGPL does not reach across that boundary and **the choice is
open**.

By the org's default that argues for Apache-2.0. The repository shipped under
MIT and is left under MIT here, because relicensing is a decision for the
copyright holder to make deliberately rather than a side effect of a scaffolding
change. Flagged for the maintainer; supersede this entry either way.

The maintainer took the flag. See D7.

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

### Failure carries the same fields as success

`SliceEngineError` (the engine exited non-zero) and `SliceOutputError` (it
exited 0 and produced nothing) are both `SliceError`, which is a
`RuntimeError`, and both carry `output_path`, `returncode`, `stdout` and
`stderr`. The first draft interpolated stderr into the message on the non-zero
path and dropped returncode and stdout entirely, which left a caller parsing
prose for facts the success path hands over as fields -- the thing section 2.2
says not to do, reintroduced on the path most likely to be hit.

### The engine's output is decoded with `errors="replace"`

Capturing the output introduced a way to fail a slice that had succeeded.
`capture_output=True, text=True` decodes strictly under the locale codec, and
that decode happens *inside* `subprocess.run` -- before any verification. An
engine that wrote perfect G-code, exited 0 and printed one byte the codec could
not read raised `UnicodeDecodeError`:

```
RAISED: UnicodeDecodeError 'utf-8' codec can't decode byte 0xb0 in position 15
but the gcode WAS written: True 'G1 X0 Y0'
```

This was not hypothetical. D6 establishes that PrusaSlicer's own help output
contains a degree sign and a mu, and that its encoding follows whatever machine
it ran on. On `main` the risk did not exist because nothing was captured, so
capturing is what created it.

All three `subprocess.run` calls now pass `errors="replace"`. The *codec* is
left as Python's locale default: there is no single right answer across
platforms, and forcing UTF-8 would be wrong more often on Windows. What matters
is that a byte we cannot decode never becomes a verdict.

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

---

## D6 -- The extracted CLI surface is structured, and it is complete

**Decided:** 2026-09-05 (issue #5)

`scripts/03_restructured_data/*.json` is the machine-readable description of
PrusaSlicer's CLI. It exists to be read by a program, so it has to survive being
read by one.

Issue #5 reported 7 of 450 entries where an aliased option had been mis-split --
`{"option": "--export-gcode,", "description": "--gcode, -g Slice the model..."}`.
Reproduced: 7 of 450, exactly. Fixing the parser turned up two larger defects
behind it.

**The extraction was incomplete.** The parser emitted an entry only when it had
both an option and a description, and it read a description only from the same
line. PrusaSlicer prints the description on the *next* line whenever the flag
list is too long for the column -- so those options were dropped entirely, with
no diagnostic. Measured against the captured help output, counting an option as
present if it appeared anywhere in the old data including inside a description:
**5 of 47 options missing from `--help`, 54 of 383 from `--help-fff`, 20 of 183
from `--help-sla`** -- **68 distinct options** absent from a file whose purpose
is to enumerate them. A consumer had no way to tell an option PrusaSlicer does
not have from one this parser could not see.

**The extraction was mojibake on Linux, or on Windows, depending on where it
ran.** No `open()` in the pipeline named an encoding, so all of them followed
the locale. The help output is UTF-8 and contains a degree sign and a mu; the
committed data was generated on Windows under cp1252 and said `Â°C`. Every
`open()` in `scripts/02_json_cli.py` and `scripts/03_restructure_cli.py` now
names `utf-8` explicitly, and the JSON is written with `ensure_ascii=False`.

### The schema

Each entry now carries four fields rather than two:

```json
{
  "option": "--export-gcode",
  "aliases": ["--gcode", "-g"],
  "value": null,
  "description": "Slice the model and export toolpaths as G-code."
}
```

`value` is the placeholder PrusaSlicer prints for options that take one
(`ABCD`, `N`, `X,Y`), which previously landed at the front of the description on
**377 of the 450 entries** in `scripts/03_restructured_data` (419 in
`scripts/02_structured_data`, which is the same data before the three help files
are deduplicated). `description` may be an empty string: a handful of options are
printed with no description at all, and dropping them would be the incomplete
extraction all over again.

This is a breaking change to the shape of the data. It is taken now because the
repository is not yet public and the file has no consumers; after that it would
need a deprecation. **After this, treat the schema as stable.**

Both figures above were wrong in the first draft of this entry -- 67 and 256 --
and are corrected here rather than quietly edited. 67 was measured against an
intermediate state of the parser, before it stopped dropping options that have
no description, and never re-measured after that change. 256 was not a count of
this defect at all; it was the number of option *lines* carrying a placeholder
in one of the three help files. Section 7 says never state a number you did not
produce; the failure mode it does not name is producing a number honestly and
then changing the code underneath it.

The count went from 450 entries to 519, and `just extract-cli` now reproduces
the committed files byte for byte -- pinned by
`tests/test_cli_extraction.py::test_committed_data_matches_the_committed_parser`,
so hand-editing the generated data, or changing the generator without
regenerating, both go red.

---

## D7 -- Apache-2.0, chosen deliberately, superseding D4

**Decided:** 2026-09-05 (supersedes D4)

The copyright holder made the call D4 asked for: **Apache-2.0**.

It aligns with `partspec`, `netspec` and `gerberdiff`. **Not with an org-wide
default, because there is not one** -- `.github/AGENTS.md` 9 says so in as many
words, having removed a draft that claimed Apache-2.0 across the org and was
already false when it said it. What 9 actually says is narrower and is what
applies here: pick Apache-2.0 *where the binding leaves the choice open*, take
what the engine compels where it does not, and record which case you are in.

This is the first case. Nothing compels anything, because the engine is reached
through `subprocess` (D1) and a process boundary does not propagate a licence.
`orlab` is the second: OpenRocket is reached in-process through JPype, so
GPL-2.0 follows and no preference of ours enters into it.

Apache-2.0 over MIT for the express patent grant, which matters more for a
driver that will be embedded in other people's build pipelines than the extra
paragraphs cost.

The licence changed before the first public release rather than after, so no
downstream consumer relied on the previous terms. `pyproject.toml` carries the
SPDX expression `Apache-2.0`; the redundant `License ::` classifier is removed,
since a licence expression and a classifier are two statements of one fact and
the classifier is the one that goes stale.

---

## D8 -- PrusaSlicer's captured help is not committed

**Decided:** 2026-09-05

`scripts/01_helps/*.txt` is PrusaSlicer's own `--help` output, verbatim.
PrusaSlicer is AGPL-3.0; this repository is Apache-2.0 (D7). Committing that
output was fine while the repository was private and becomes redistribution the
moment it is public, so the captures and everything derived from them are
generated locally and ignored: `just capture-cli` then `just extract-cli`.

Nothing is lost downstream. The wheel never shipped any of it -- it contains
`prusaslicer_py/` and nothing else -- so no consumer relied on it.

**The tests that read the corpus SKIP when it is absent; they do not pass.**
Every one of them walks a `glob`, and a glob over an empty directory makes an
assertion loop vacuous: the test reports success having examined nothing. That
is the failure this project exists to prevent, so the skip states the reason.

The coverage those tests provided is carried by
`tests/fixtures/synthetic_help_output.txt`, written by hand in PrusaSlicer's
format and therefore ours to redistribute. It is not decorative: running the
pre-fix parser against it reproduces every historical defect -- the dropped
bare flags, the mis-split `--export-gcode, --gcode, -g`, and the flag whose
description begins on the following line, which is the shape that lost 68
options. A first attempt used a placeholder-carrying flag for that last case
and the old parser *kept* it, so the fixture was checked against the real
defect rather than assumed to reproduce it.

---

## D9 -- The engine is found on PATH or as a Flatpak, and paths are translated

**Decided:** 2026-09-05

`shutil.which` cannot see a Flatpak: the app is not on PATH and there is no
binary to find. Flathub is how PrusaSlicer is normally installed on Linux, so
discovery that only asked PATH reported "not installed" on machines where the
engine was sitting right there -- including the one this was developed on.

Discovery therefore tries PATH first, then probes `flatpak info`, and invokes
via `--command=prusa-slicer` to bypass the wrapper the Flatpak runs by default,
which swallows CLI arguments and answers `Unknown option`. `engine_kind` says
which was found, so a caller can branch rather than infer.

Two consequences a sandbox forces, both found by running the real engine rather
than a stub:

- **Filesystem grants.** A Flatpak sees only its own sandbox, so the input and
  output directories are granted with `--filesystem=<dir>`. Only the
  directories involved, never `--filesystem=host`: this runs inside other
  people's build pipelines and a driver should not hand the engine the whole
  disk to slice one part.
- **Path translation.** The app's own files are mounted at `/app` inside the
  sandbox, not at their host path, so a bundled example shape is real to us and
  absent to the engine. `_to_engine_path` rewrites those, and it must resolve
  the Flatpak root before comparing -- `current/active` is a symlink into a
  hashed deployment directory, and comparing against the unresolved root
  silently never matches.

Related, and only visible against a real engine: `check_version` called
`--version`, which PrusaSlicer has never supported -- 2.9.6 answers `Unknown
option --version` and exits 1. The version appears only as the first line of
`--help`. Every stub in the suite answered `--version`, so the tests agreed
with the code and both were wrong.


---

## D10 -- The typechecker covers the repository, and `scripts/` carries annotations

**Decided:** 2026-09-06 (issue #24)

`just typecheck` named `prusaslicer_py/ tests/`. Two directories were outside it:
`scripts/`, which holds the CLI-surface extraction that produces the data D6
froze, and `examples/`, which nothing had thought about either way. A hand-written
path list omits by default -- the omission is invisible until someone re-reads the
recipe, and the next directory added to the repository joins the omitted set
automatically.

The recipe is now `mypy .`. What it covers is decided by the repository's
contents rather than by a list someone has to remember to extend, and
`tests/test_repo_gates.py::test_the_typecheck_recipe_checks_the_whole_repository`
asserts that spelling -- it goes red against the exact recipe this issue started
from. Exclusions, if any are ever needed, belong in `pyproject.toml` where they
are visible and reviewable.

### Scope alone would have been close to nothing

mypy skips the body of any function with no annotations. 12 of the 13 functions
in `scripts/` were unannotated, so `scripts/` in the recipe would have bought one
checked function. `check_untyped_defs` reads those bodies and is set for the whole
project.

That is still not enough, and the measurement is the point. With bodies checked
but signatures absent, mypy accepts

```python
save_json(output_dir / "actions.json", actions_data)  # arguments reversed
```

with no error, because there is no signature to check the call against. That is
the defect shape `scripts/` is most exposed to: it generates data, nothing
downstream re-checks that data, and a wrong-order call writes a plausible file.
So all 12 signatures are annotated and `disallow_untyped_defs` holds them there,
and the reversed call is now an error at the call site.

**It is required repo-wide, with one exemption, and that direction is the
decision.** The first attempt listed the three script modules in a
`[[tool.mypy.overrides]]` allowlist -- which is the same defect this entry opens
by describing, moved from the justfile into `pyproject.toml` and out from under
the gate that had just been written for it. Two ways it failed, both measured: a
new `scripts/04_*.py` was unchecked the day it was added, so a reversed call in
it passed clean; and renaming a listed module silently dropped its protection,
because `warn_unused_configs` reports the stale entry as a *note* and the run
still exits 0. A stale allowlist entry is precisely the shape of thing that
cannot fail.

`disallow_untyped_defs = true` therefore applies to everything, and `tests/`
is exempted by name. It has 33 unannotated signatures and a `-> None` on a pytest
function buys nothing; `check_untyped_defs` already reads their bodies, which is
where test defects live. `prusaslicer_py/` needs no mention -- it had zero unannotated
signatures already, and now cannot acquire one. `examples/` has no functions at
all, so it contributed nothing either way; it is in scope now so that it cannot
start contributing silently.

The exemption is the part someone has to write down, which is the whole point:
adding a directory to this repository now inherits the check instead of escaping
it.

### And something has to call it

Gating a recipe's body says nothing about whether anything runs it. Every gate
above verifies what `typecheck` contains; none verified that `check` still
depends on it, so `check: fmt-check lint` passed all of them while
`.github/workflows/ci.yml` ran `just check` and typechecked nothing. The sharper
form keeps every gate green and reintroduces this issue verbatim:

```
check: fmt-check lint
    uv run --locked mypy prusaslicer_py/ tests/
```

`check: fmt-check lint typecheck` is a hand-written list -- the shape this entry
opens by arguing against -- and it was the last unguarded one.
`test_the_check_recipe_actually_runs_the_typechecker` reads the dependency list
out of `just --dump` and asserts `typecheck` is in it.

### D6's schema is now a type, not a comment

The records the extraction emits were `dict[str, object]`. `object` accepts
anything, so the schema D6 explicitly froze -- and told consumers to rely on --
was the one part of the pipeline the typechecker could not check. It is now a
`TypedDict`, and a renamed key, a wrong field type, or an `option` that could be
`None` are errors.

The flag pairs feeding it are `tuple[str, str | None]`. They were
`list[list[str | None]]`, which was wrong twice over: the shape is a pair rather
than a variable-length list, and it declared the spelling nullable when only the
value ever is. That second error contradicted D6 in writing -- D6 says
`option: str` -- and it was the annotation itself that carried the contradiction,
which is why restating a frozen schema loosely is worse than not restating it.
`scripts/03_restructure_cli.py` therefore keeps its element type opaque
(`dict[str, list[object]]`): it never looks inside a record, so it has no reason
to repeat those four fields where they could drift from the parser that writes
them.

### What was considered and not done

A `NewType` for the flag spelling would catch `flags[-1] = (value, spelling)` --
a swap between two `str`s that types clean. It is not taken.
`OptionRecord.option` must stay `str` because D6 froze it, so a `Spelling` alias
would put a second vocabulary in front of a frozen schema, which is the failure
this entry argues against above. Against that: two construction sites and one
swap shape, in a generator pinned by nine parametrised `split_option_line` cases.
A test is the right instrument for a same-type swap, and it already exists.

Note which test does the work.
`test_committed_data_matches_the_committed_parser` is gated on a captured corpus
and so skips on every pull request, running only in `engine.yml`. The instrument
that actually catches a swapped pair is those nine parametrised cases, which are
always on -- verified by swapping the pair and watching six of them fail.
Recorded so the next reviewer does not re-raise it, and so the citation does not
rest on a test that is usually skipped.

### What this actually found on the way in

Three `var-annotated` errors on empty literals in `scripts/`, where mypy could not
infer an element type, and six in `tests/` from calling `module_from_spec` on a
possibly-`None` spec. Nothing had behaved wrongly. Recorded plainly because
section 7's rule cuts both ways: a change is not more valuable for being described
as a defect fix, and the value here is the checking that now exists rather than
the errors it cleared.

### Gate the outcome, not the instruction

Each version of this gate read an *instruction* and asked whether it looked right,
and each was defeated one layer further down. The recipe's text came first. Then
the text after `just` interpolation, via `just --dry-run` -- which still missed a
defaulted parameter, because the default is empty and only `check` supplies the
narrowing. Then, once `check` was resolved, the shell turned out to be below
`just` entirely:

```
uv run --locked mypy . $(cat .mypyargs 2>/dev/null)   # 11 files, gate green
uv run --locked mypy . $MYPY_EXTRA                    # 9 files, gate green
uv run --locked mypy . "$@"                           # 11 files, gate green
```

None of those is sabotage; each is an ordinary refactor. The lesson is that
**there is always another layer of instruction, and there is only one outcome.**
mypy names its own scope in both the passing and the failing case -- `Success: no
issues found in 14 source files`, `Found 2 errors in 1 file (checked 14 source
files)` -- and that number cannot be argued with.

So `test_the_typechecker_actually_covered_every_tracked_file` runs `just check`
and compares mypy's own count against every `.py` git tracks. A narrowing lowers
it, whatever produced the narrowing, and the gate does not need to know which
trick was used. It closed the three shell cases above and a
`[tool.mypy] exclude` entry at the same time -- the last of which nothing else
checked, because D10 routes exclusions into `pyproject.toml` and then nothing read
them.

The comparison is deliberately against *all* tracked files rather than
tracked-minus-excluded: subtracting the declared excludes would let the exclusion
list grow while the gate stayed green, which is the omit-by-default shape this
entry exists to argue against. It is `>=` rather than `==` because an untracked
scratch file legitimately raises the count and is nobody's defect.

### Four gates, and why none is redundant

Three of these read outcomes and one reads shape, and the temptation is to delete
the overlap. There is none: each has a red state no other produces, verified by
attack.

| attack | dry-run | count | canary | linecount |
| --- | --- | --- | --- | --- |
| a *complete* hand-written path list | **red** | green | green | green |
| `exclude tests/` -- the one directory no other gate covers | green | **red** | green | green |
| `disable_error_code` sparing the canary's shape | green | green | **red** | green |
| `ignore_errors` on some modules | green | green | green | **red** |
| `check_untyped_defs = false` | green | green | **red** | green |

The second row was first written as "`exclude` a directory", generalised from one
measurement. Measured across all three, the coverage is uneven and the label
mattered: excluding `scripts/` reddens three gates, `examples/` two, and `tests/`
only one. The row is making a true point -- the count gate is the only one
covering `tests/` -- but as written it understated how much the canary and
linecount catch, in the table a future reader would use to decide whether a gate
is redundant.

The first row is the one worth naming. A hand list naming every directory checks
all 14 files today, so every outcome gate is satisfied -- it is red only because
the *shape* omits by default, which is what this entry opens by arguing against.
That is a gate on shape, and no outcome gate can express it.

Two holes in this set were found by planting defects rather than by reasoning
about it, and both are the same mistake in different clothes:

* **The canary planted one error shape.** `disable_error_code` sparing `arg-type`
  left it objecting while switching off `no-untyped-def` -- which *is*
  `disallow_untyped_defs` -- and `typeddict-item`, which *is* D6's schema
  protection. Both properties this entry rests on, dead, with every gate green.
  The canary now plants one defect per mechanism rather than one per gate.
* **The canary lived only in annotated code.** `check_untyped_defs` is the fourth
  mechanism this entry rests on -- it is the stated reason `tests/` may be exempt
  from `disallow_untyped_defs`, since bodies are read either way. Turning it off
  leaves the whole test suite with neither, and mypy reports that as a *note* at
  exit `0`. No gate could see it: the count is unchanged, linecount excludes
  `tests/` by design, and the canary's defects all sat in annotated functions. The
  canary now plants one inside its unannotated function too.
* **The linecount gate skipped `__init__.py` by name.** That was a hand-written
  exclusion inside the gate set built to argue against hand-written exclusions,
  and it was fail-open: `ignore_errors` on the `prusaslicer_py` module left the
  package's public entry point checked for nothing, invisible to all four. The
  filename is now mapped to its package instead of dropped.

### Accepted, and why

Three gaps are known, measured, and deliberately left. Recorded because the
difference between *measured and accepted* and *never noticed* is the whole point
of writing any of this down, and without a line here they read as the latter.

* **`warn_unused_configs`, `warn_redundant_casts` and `warn_unused_ignores` are
  ungated.** None carries a claim this entry rests on, so switching one off is a
  loss of hygiene rather than a directory going unchecked. Gating them would mean
  asserting the contents of `[tool.mypy]`, which is the config-allowlist shape this
  entry rejects everywhere else.
* **An in-band `# mypy: ignore-errors` silences a file, and passes.** Measured.
  Not closed, because it is visible in the diff of the very file it silences, and
  closing it would mean rejecting a legitimate escape hatch. `warn_unused_ignores`
  already catches a stale one.
* **`set shell := ["true", "-c"]` makes `just` run nothing**, as described under
  *Where it actually stops*. Listed here too so the three sit together.

### Is this too much machinery?

`tests/test_repo_gates.py` is larger than the `scripts/` it protects, and
`just test` spawns three extra typechecks. That ratio is worth naming rather than
discovering later.

It is not disproportionate, and the reason is not that typechecking is
high-stakes. It is that this repository's own standard was violated five
consecutive times while being fixed, each violation reproducing the previous one
exactly one level up, and **not one of them required an adversary** -- every
attack that worked was an ordinary refactor. That is evidence the failure mode is
live here rather than theoretical.

The durable asset is the sentence, not the gates: *an instruction gate always has
a next layer, and an outcome gate does not.* The gates are its local application.

**A falsifiable test for when this has outrun the risk:** if a review of this kind
comes back clean on its first attempt, the machinery is doing more work than the
risk warrants and something should go. Five rounds and roughly thirty attacks
found a live hole every round -- including two in the gates themselves, and one
in the reviewer's own harness, which had disabled the thing it was measuring.

### Where it actually stops

Not at the recipe, and not at `set shell := ["true", "-c"]` -- an earlier draft of
this entry said the latter and was wrong, because every shell expansion above sat
below that claim and needed no sabotage.

It stops at whether the suite runs at all. `ci.yml` is gated: it must invoke
`just check` and `just test`, the `check` and `test` jobs may carry no `if:`, and
the `ok` job now requires upstream *success* rather than the absence of failure --
`contains(needs.*.result, 'failure')` does not match `'skipped'`, so an `if: false`
on `check` produced a fully green pull request with nothing checked. Past that, a
runner told to execute nothing executes nothing, and no test can observe that from
inside a process that was never started. That is a different threat model from
drift, and it is visible in a diff.

---

## D11 -- pre-commit is enforced, and one ruff formats this repository

**Decided:** 2026-09-06 (issue #25)

`.pre-commit-config.yaml` makes a claim: eight hooks check this repository. It was
true only on machines where somebody had run `pre-commit install`, and `--no-verify`
skipped it there. `ruff` and `ruff-format` were covered independently by
`just check`; the other six were not covered at all.

**`gitleaks` is why this is a job and not a note.** Secret detection that runs only
where it was opted into is not a control. A commit pushed from a fresh clone
reaches `main` unscanned, and this repository is public.

### Running a hook is not the same as the hook checking anything

The first version of this entry said the job made eight hooks real, and that
`fetch-depth: 0` mattered because gitleaks scans history. **Both were wrong**, and
they were wrong in the way this repository is supposed to catch: stated from
reading a config rather than from watching a check fail.

Three of the eight were no-ops even once CI ran them, measured on a repository
with a secret, a 2 MB binary and a file full of conflict markers all **committed**
and the tree clean:

```
Detect hardcoded secrets.................................................Passed
check for merge conflicts................................................Passed
check for added large files..............................................Passed
```

* The stock gitleaks hook is `gitleaks git --pre-commit --redact --staged`. On a
  CI checkout the index equals `HEAD`, so `git diff --staged` is empty and it
  scans **zero bytes**. The positive control -- the same secret merely *staged* --
  reports `leaks found: 1`, so the hook works and the invocation never asks it to
  look.
* `check-added-large-files` intersects its filenames with
  `git diff --staged --diff-filter=A`, empty for the same reason.
* `check-merge-conflict` returns 0 immediately unless the repository is mid-merge.

So `fetch-depth: 0` was pure cost, and issue #25's actual complaint -- a commit
reaching `main` unscanned -- was not fixed by running the hooks.

A second gitleaks hook, aliased `gitleaks-history`, overrides the entry to
`gitleaks git --redact --verbose` and scans history; the other two now carry
`--enforce-all` and `--assume-in-merge`. On that same committed-secret tree all
three go red, and `fetch-depth: 0` is now load-bearing rather than decorative.

`CONTRIBUTING.md` says it exactly: *a check that cannot fail is not a check; break
the thing it checks and watch it go red before you trust it.* That was not done
for these three, and the cost was a security control that existed only on paper --
in a decision record, which by this repo's own rule is not to be relitigated.

**All nine hooks are now measured red-capable**, one planted defect each, not
inferred from configuration: trailing whitespace, a missing final newline, invalid
YAML, an unfixable `F821`, an autofixable `F401`, a 146-character line, unformatted
code, and the three above. The `E501` probe is the useful one -- it fails at 100
characters rather than ruff's default 88, which shows the hook reads this repo's
`[tool.ruff]` rather than merely running the same binary as `just check`.

### Two gitleaks hooks, and neither is redundant

They cover different things and a future reader will otherwise delete one.
Verified on the real `git commit` path: committing a new secret fails the
`--staged` hook while the history hook passes, because the commit in flight is not
yet in history. The history hook covers what is already there. Neither alone is
sufficient.

**What the history hook cannot do is see past the clone.** On a shallow clone a
secret added and later removed reports `no leaks found` at exit `0` -- no warning,
no diagnostic. Measured: full clone and `--depth 7` catch it, `--depth 5` and
below do not. So `fetch-depth: 0` is the whole control, and
`test_ci_runs_the_gates_that_guard_all_of_this` asserts it: deleting that line
reads as a cleanup and would silently remove the protection. A secret still present
in `HEAD` is caught at any depth; it is the added-then-removed case that needs the
history, and that is the case the hook exists for.

Pinning `rev:` to a commit SHA rather than a tag currently fails the pin gate,
which compares against a version string. `pre-commit autoupdate` writes tags so it
will not bite soon, but if this repository ever adopts supply-chain SHA pinning for
hook repos, that test has to be taught first.

If a real secret ever does land, `.gitleaksignore` with the reported fingerprint is
the escape hatch. Recorded because without knowing it, the first true positive
makes the hook permanently red for everyone and it gets deleted under pressure --
which is how a control dies.

### The job was watched failing, not reasoned about

Every red proof in this issue was local, across three review rounds, and the one
thing left asserted rather than observed was the part this repository has been
burned by before: that the job *gates* rather than merely *runs*. `ci.yml` records
that `contains(needs.*.result, 'failure')` once missed `'skipped'` and produced a
fully green pull request with nothing checked. Reasoning about that wiring is what
produced every other defect in this entry.

So it was measured. A throwaway branch planted trailing whitespace **in a markdown
file** -- ruff, mypy and pytest do not read `.md`, so the failure is isolated to
one hook -- and
[run 34062300790](https://github.com/heibench/prusaslicer-py/actions/runs/34062300790)
gives:

```
pre-commit: failure
Check: success
Test (Python 3.11, 3.12, 3.13, windows-latest): success
ok: failure
```

`ok` going red with every other job green can only be
`needs.pre-commit.result != 'success'` evaluating correctly, which also settles
that a hyphenated job id dereferences as expected. The branch was deleted; the run
id is the record.

One thing stays unmeasured and is labelled as such in the gate itself:
`continue-on-error` and `paths-ignore` are rejected on GitHub's documented
behaviour, not on a run anyone has watched. That is deliberate, and the reason is
the general rule this entry was actually teaching.

**The distinction that matters is not measured versus inferred. It is which way
the inference fails if it is wrong.** Every inference that cost something here
failed *open* -- it made a control weaker than the record claimed. "gitleaks scans
history" meant it scanned zero bytes; "a substring guards `fetch-depth`" meant a
shallow clone passed. Those two bans fail *closed*: rejecting `continue-on-error:`
or `paths-ignore:` can only refuse a configuration, never accept one. If the
documented behaviour is wrong, the whole consequence is that somebody writing a
legitimate `paths-ignore:` gets a red test with an explanation and loses five
minutes. It cannot produce a green pull request over a red gate.

So the rule is not "measure everything", which would be unaffordable and would
dilute the ones that matter. It is: **an unmeasured claim that can only tighten a
gate is a different risk class from one that can loosen it, and only the second
kind earns a probe.** F1 was expensive precisely because it was the second kind,
written as though it were the first.

### The recurring failure here is a line-oriented pattern over YAML

Three separate defeats in this issue came from the same place, and it is worth
naming as a class rather than three incidents: a comment supplying a decoy `rev:`;
a folded-scalar hook `name:` doing the same; and a forbidden key written as a
step's first key, `- if: false`, where the guard's `^\s*` could not match the `-`.
None needed an adversary and none needed unusual YAML -- mapping keys are
unordered, so the reordering that defeated two of them is just as valid a document.

Both rev gates now anchor on structure -- indentation and key position -- rather
than matching text in a flattened document. Note that the `fetch-depth` guard
added alongside them did **not**: it was a substring over a block containing
comments, so `fetch-depth: 50` under a comment reading "was fetch-depth: 0; full
history is slow on this runner" satisfied it, and per the depth table above that
silently loses the added-then-removed case. The class named in this section was
reintroduced in the commit that named it, which is the strongest evidence that
naming it was right. It is matched as a key now.

A related correction: this entry credited the line-wise rewrite with fixing a false
positive on a second legitimate `ruff-pre-commit` block at the same rev. It did
not -- the rewrite changed how revs are collected and left the `== [running]`
comparison alone, so two identical revs still failed, with a message reading "pins
['0.16.6', '0.16.6'] but installs 0.16.6". That claim was written from reading the
new code rather than from watching the old complaint go green, which is the exact
habit this whole entry is about. It is a set comparison now, verified both ways.

`pyyaml` would close the class outright and
is deliberately not added: it would be a dependency to read four lines, and the
line-wise reads are a dozen. That is a size judgement, not a claim that a regex is
adequate for YAML.

### One ruff, exactly

The pins had already drifted. pre-commit named `v0.11.12`; the dev group asked for
`ruff>=0.11`, which resolved to `0.16.6`. Measured rather than assumed: the older
ruff raises `UP038` on

```python
isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
```

in `tests/test_repo_gates.py`, and the newer one does not carry that rule at all.
So a contributor with hooks installed could not commit code that CI accepts, and
the failure would have read as their mistake.

Both pins are now exact and equal, held by
`tests/test_repo_gates.py::test_both_ruff_pins_name_one_version`, ported from
partspec's `tests/test_lint_config.py` -- the same defect, found there first. An
inexact pin on either side fails it, so bumping one alone is a red gate rather than
a quiet split between what `git commit` writes and what `just check` rejects.

The gate compares the **resolved** version from `uv.lock`, not the declared one.
Declaring `ruff==0.16.6` does not mean `uv run` installs it:
`[tool.uv] override-dependencies = ["ruff==0.14.0"]` resolves to 0.14.0 with every
gate green, measured. `uv.lock` is what actually gets installed, so it is the only
version worth comparing. Comments are stripped before the `rev:` is read, because
a comment reading `ruff-pre-commit rev: v0.16.6` satisfied the earlier regex while
the real `rev:` sat lower in the block naming a different version.

Note what this does *not* claim. The gate holds the two version strings equal; it
does not verify that two builds of the same version format identically, which
nothing here can. Equal versions is the strongest available guarantee, not a proof.

### It found something before it was merged

Adding the job to `ci.yml` introduced a YAML syntax error -- a plain-scalar `if:`
continued on an under-indented line, which is not the value it looks like.
`just check` cannot see that: `ruff` and `mypy` read Python, and nothing else in
the gate reads YAML. `check-yaml` caught it on the first run, in the very file
that adds the job.

That is the argument for this entry in one line. The six unenforced hooks were not
covering a hypothetical gap, and the first thing enforcing them found was a real
defect in the change that enforced them.

---

## D12 -- Recipes work on Windows, and the Windows half is executed rather than read

**Decided:** 2026-09-06 (issue #26)

`just clean` used `rm -rf` and GNU `find`; `just test-engine` used `VAR=1 cmd`.
Neither runs on Windows without a POSIX layer, on a project that deliberately
supports Windows: `engine.yml` runs the real engine on `windows-latest`, and
`_exec_name()`'s `prusa-slicer-console.exe` branch exists precisely so that a
Windows contributor is a real contributor. A contributor who can run the tests but
not the project's own recipes gets the second-class experience the rest of this
repository argues against.

### `test-engine` was not the problem, and the attempted fix was worse

The issue named `test-engine` alongside `clean`, and the first version of this
entry changed it to an exported recipe parameter:

```
test-engine $PRUSASLICER_PY_REQUIRE_ENGINE="1":
```

**That was wrong twice, and it is recorded rather than quietly reverted.**

It fixed nothing. `just` runs recipe bodies through `sh` on *every* platform --
its own documentation says so, and this issue produced independent evidence when
`sh` ate a `$_` out of a PowerShell body. So `VAR=1 cmd` is ordinary `sh` syntax
that works wherever `just` works at all. `clean` was a real portability problem
because `rm -rf` and GNU `find` are external programs that need not exist; an
environment-variable prefix is not in that class.

It also **introduced a fail-open**, in the one recipe whose entire purpose is that
a missing engine must not read as success. A parameter is settable, and `just`
advertised it in `--list`:

```
just test-engine       -> 4 errors, exit 1
just test-engine ""    -> 48 passed, 7 skipped, exit 0   <- green, no engine
```

An empty string exports as empty, `os.environ.get()` returns `''`, and
`conftest.py` skipped. A wrapper written as `just test-engine "$REQUIRE"` with
`REQUIRE` unset is a fully green "engine required" run. On `main` the recipe took
no arguments and could not be weakened at all. The recipe is back to its original
form.

`conftest.py` is hardened independently, because the underlying defect was its
own: it tested truthiness, so `PRUSASLICER_PY_REQUIRE_ENGINE=` in the environment
disabled the switch by setting it to nothing. It tests membership now.

### #30 is settled by measurement, in the same job

`engine.yml` carried a comment calling `VAR=x cmd` POSIX-only, and #30 records that
nothing in the repository settled whether that mattered -- `just` documents `sh` on
Windows, but the repo had no Windows job that could tell.

The `recipes` job now runs `just test-engine` on `windows-latest`, where no engine
is installed, and requires it to fail **with the require-engine message**. If the
prefix did not reach the child process the variable would be unset, `conftest`
would skip, and the run would exit `0`; the only way to get that specific failure
is for `sh` to have handled the prefix and `conftest` to have seen the variable.
The comments in `engine.yml` are corrected to say so.

That is a claim the repository can now break, rather than one it can only read.

### What the `[windows]` body is actually for

Not "makes it work where there is no POSIX layer". `just` launches
`powershell -NoLogo -Command "..."` *through* `sh` -- which is how `sh` came to eat
a `$_` -- so on a Windows box with no POSIX layer `just` runs nothing at all,
`[windows]` body included. Neither body delivers that, and this entry should not
imply otherwise.

The benefit is narrower and real: independence from `rm` and `find` as external
programs. That is also why reverting `test-engine` and keeping this is coherent
rather than arbitrary -- `VAR=1 cmd` is `sh` syntax, while `rm` and `find` are
separate executables that have to be found. Windows ships
`C:\Windows\System32\find.exe`, a completely different program, so which one a
recipe gets is PATH-order dependent -- and the POSIX body would swallow the
failure, since its `find` line ends `2>/dev/null || true`. A `clean` that exits `0`
having removed no `__pycache__` on some machines and not others.

**Measured, and the measurement cuts both ways.** The `recipes` job prints what
`sh` actually resolves on `windows-latest`:

```
/usr/bin/rm
/usr/bin/find
find (GNU findutils) 4.11.0
```

So on this runner `rm` and `find` are the GNU programs the POSIX body expects, and
the PATH hazard the `[windows]` body guards against does not arise here. Whether
the body would then have *cleaned correctly* is not something this step
establishes -- and its `find` line ends `2>/dev/null || true`, so a green run of it
would not establish that either. The `[windows]` body is kept for machines where
PATH order differs, which is a class the runner cannot speak to.

An earlier draft of this paragraph said "the POSIX body would have worked" --
resolution inferred into behaviour. It slipped precisely *because* it concedes
against the change: a sentence that weakens your own work feels self-evidently safe
to write, and this one would have been the strongest available argument for
deleting the `[windows]` body, sitting unmeasured in the project's own decision
record. The direction a claim points does not change what it owes.

### `clean` dispatches per OS, and `[unix]`/`[windows]` are safe where `[doc]` was not

D2.1 bans `[doc]` because an unknown attribute is a *parse* error, so one of them
breaks every recipe in the file for anyone on an older `just` -- Ubuntu 24.04 LTS
ships **1.21.0**, below `[doc]`'s **1.27.0**. That ban does not extend here:
`[unix]` and `[windows]` arrived in **1.8.0**, which is below the same floor.
Checked in `just`'s own attribute table rather than assumed, because the version
number is the whole argument.

### The Windows body is executed, not read

`clean`'s Windows half is PowerShell, and no amount of care on a Linux machine
establishes that it works. That is exactly the habit D11 was written about, so a
`recipes` job runs `just clean` on `windows-latest` and then asserts the
directories are gone -- the assertion matters, because a recipe that silently does
nothing would otherwise pass. It gates `ok` like every other job, and the repo
gate requires it to.

The POSIX half needs no such job: every other CI leg has a working tree and would
break loudly.

The job also **creates** every artifact `clean` claims to remove before running it.
Without that, only `.venv` exists after `just setup` -- so the assertion was
vacuous for five of the six, including the `__pycache__` sweep, which is the half
of the Windows body most likely to break next and had never been exercised against
a single input.

And the gate asserts what the job *does*, not merely that it exists. Three edits
left it named, gating `ok`, and useless: moving it to `ubuntu-latest`, which is a
plausible cheaper-runner cleanup and silently dispatches `clean` to the POSIX body;
deleting the assertion step; and replacing `just clean` with anything else. The
gate's own message claims this job executes the Windows half, so something has to
make that true -- an unmeasured claim that *loosens* a gate is the expensive kind.

**It caught the first version on its first run**, which is the argument for it.
`just` executes a recipe body through `sh` on Windows too, not through the
platform shell -- so a body written as

```
powershell -NoLogo -Command "... | ForEach-Object { if (Test-Path $_) { ... } }"
```

had its `$_` expanded by `sh` before PowerShell ever saw it. The recipe ran, exited
`0`, and deleted nothing; the assertion is what turned that into
`just clean left: .venv` rather than a green run. A `clean` that silently cleans
nothing is the failure this repository is named around, and reading the recipe
would not have found it -- the `$_` is correct PowerShell and correct `just`, and
wrong only in the seam between them.

The body avoids `$_` entirely now, so there is nothing for `sh` to substitute.

**And it caught a second one, which I had asserted was already handled.** Asked
whether `clean` fails loudly when a real error stops it, I said the Windows body
did. It did not. `Remove-Item` raises a *non-terminating* error, and the
`__pycache__` sweep runs after it and always succeeds, so with `.venv` held open by
another process the job measured:

```
Remove-Item : Cannot remove item ...\.venv: The directory is not empty
just clean -> exit 0
```

An error on stderr and success to the caller -- while `rm -rf` exits non-zero and
`just` aborts the recipe. The two halves were not equivalent in the way that
matters most, and the difference was invisible to every green run because nothing
had ever made `clean` fail. `$ErrorActionPreference = 'Stop'` inside the command
makes the non-terminating error terminating; the `__pycache__` sweep keeps its own
`-ErrorAction SilentlyContinue`, matching the POSIX body's `|| true` on the same
sweep.

The probe was added deliberately without a pre-emptive fix, so that the run would
answer the question rather than confirm a guess. It answered it against me.

The first fix for that was `$ErrorActionPreference = 'Stop'` -- and `sh`, running
with `-u`, ate that too: `ErrorActionPreference: unbound variable`, exit 127. Three
instances of one class in a single recipe. The rule the recipe carries now is
therefore not "escape the `$`" but **the body must contain no `$` at all**;
`-ErrorAction Stop` on the cmdlet does the same job with no sigil for `sh` to
find.

---

## D13 -- `check_version` matches the banner, and says when there is none

**Decided:** 2026-09-09 (issue #34)

`check_version` took the first non-empty line of `--help` and returned it as
the version. On any build that prints something before its banner it returned
that something -- at exit `0`, with no error, and no channel for the caller to
learn otherwise. The native Windows console build opens `--help` with `System
OpenGL library successfully released` and states its version on the line below,
so that is what it returned there.

The Linux Flathub build prints no preamble. That is why the defect survived
every local run: the shape it was measured against was one build's, and the
comment above the code recorded that shape as though it were the format.

### The line is matched, not counted to

The banner identifies itself -- `PrusaSlicer-<version> based on Slic3r ...` --
so the version is read from the first line matching
`^PrusaSlicer-(\d\S*)`, wherever in the output it appears. Three choices
inside that pattern, each of which had to be argued rather than assumed:

- **`based on Slic3r` is not required.** It is on every build seen so far, but
  requiring it would answer *could not tell* for a version that is plainly
  there, and the org contract warns against refusing more than the question
  requires (§2.3) as squarely as it warns against guessing.
- **The digit is.** Without it the pattern matches `PrusaSlicer-Py`, which is
  this package's own name, and a build that greeted with it would have that
  greeting returned as its version -- the defect, one product name over.
  `test_the_banner_needs_a_digit_not_just_the_product_name` exercises exactly
  that, because a discriminator with no case that needs it is a comment.
- **The match is at column 0 of the raw line.** The banner is the first thing
  the engine prints and is not indented. Stripping first only widens what can
  be mistaken for a banner, and an indented `PrusaSlicer-2.9.6` is help text.

**Both streams are searched, stdout first.** `--help` goes to stdout on every
build seen here, but a startup banner is exactly the kind of thing a build
sends to stderr, and which stream it lands on is not something one host can
establish. Both are already captured, so answering *could not tell* while
holding the answer in a field would be a self-inflicted third outcome.

### The third outcome is the exception, not the return type

`-> str` was not the defect. Returning a `str` **for output that states no
version** was. Those are separable, and separating them is what this entry
settles:

```python
def check_version(self) -> str:  # unchanged, and 0.2.0-compatible
    ...
    if found is None:
        raise VersionUnreadableError(...)  # the third outcome lives here
    return banner
```

§2.1 is satisfied in full -- *satisfied*, *violated*, *could not tell*, and the
third never returns a value -- with nothing broken. `VersionError` subclasses
`RuntimeError`, which is what this method raised before any of these types
existed, so a caller that already handled failure keeps working unchanged.

**An earlier draft of this entry broke the return type and argued from
necessity: that no `str` could be handed back, so every scheme keeping one
reintroduced the silence. That argument was wrong**, and it was wrong in a way
worth recording. It conflated *keeping a `str` return type* with *returning a
`str` in the no-version case*. Raising does neither.

The draft also cited §2.1 and never engaged §5 or §10, which is where the cost
of being wrong sat. §5's second paragraph closes the pre-1.0 escape for drivers
specifically: "For a driver the equivalent surface is **what the call returns**
and what it guarantees about the engine's output." This is a driver, so
`check_version`'s return value is the report-schema analogue, §10's "changing a
report schema in a released tool" applies, and 0.1.0 and 0.2.0 are both
published with a README documenting `print(slicer.check_version())`. The
non-breaking shape removes that escalation rather than resolving it, which is
strictly better than winning the argument.

### `version_info()` is additive, and that is all it is

The parts are genuinely useful -- the version alone (`2.9.6+flathub.org`), and
the engine's own output beside it -- so `version_info()` returns a
`VersionResult` carrying `version`, `banner`, `returncode`, `stdout` and
`stderr`, matching what D5 settled for `slice_model`: failure carries the same
fields as success, and the evidence travels with the claim. `check_version()`
is exactly its `.banner`.

A benefit is not a necessity. This ships because it is worth having, not
because the fix required it, and nothing has to move to keep working.

### Four outcomes were possible under a docstring promising three

`version_info` caught only `subprocess.CalledProcessError`. A `slicer_path`
pointing at a file that is not there raises `FileNotFoundError`; one pointing at
a file that is not executable raises `PermissionError`. Reproduced:

```
/definitely/not/here/prusa-slicer: NOT a VersionError -> FileNotFoundError: [Errno 2] ...
/etc/hostname:                     NOT a VersionError -> PermissionError:  [Errno 13] ...
```

Neither is a `VersionError`, and the README recommends `except VersionError`.
`OSError` is caught and re-raised as `VersionEngineError` with `returncode=None`
-- there was never an exit status, and a stand-in integer would be a number
nothing measured. D14 reaches the same conclusion for `probe()` independently,
which is the tell that it is the right one.

### What is not changed

`--help` is still the source. PrusaSlicer has no `--version` flag -- 2.9.6
answers `Unknown option --version` and exits 1 -- so D9 stands. The defect was
in which line was taken, not in the flag.

---

## D14 -- Discovery establishes installed; `probe()` establishes usable

**Decided:** 2026-09-09 (issue #33)

`tests/conftest.py` decided whether to skip an engine-dependent test by
constructing `PrusaSlicer()` and catching `FileNotFoundError`. That sees an
engine that is **absent**. It does not see one that is **present and will not
run**, and there is no reason it would: `_find_flatpak` accepts a Flatpak on
`flatpak info` exiting 0, which establishes that the app is installed and
nothing about whether it can start.

Reproduced on this machine, with an unwritable `HOME`:

```
$ HOME=$RO flatpak info com.prusa3d.PrusaSlicer          # exit 0
$ HOME=$RO flatpak run --command=prusa-slicer com.prusa3d.PrusaSlicer --help
error: mkdirat(.var): Permission denied
exit 1

$ HOME=$RO ./.venv/bin/python -m pytest -q
FAILED tests/test_engine.py::test_check_version_against_real_engine
FAILED tests/test_engine.py::test_generate_help_against_real_engine
FAILED tests/test_engine.py::test_slice_produces_gcode_with_the_real_engine
3 failed, 56 passed, 3 skipped
```

Same tree, working `HOME`: green. Nothing about the code had changed, and the
suite said the code was wrong.

**This is a verdict misattribution, not a silence defect, and the distinction
is worth keeping.** The suite goes red, and D5 is why -- nothing reported a
success it had not verified. What is wrong is the attribution: the org contract
draws exactly this line between a finding about the code and a fault in the
environment (§2.2), and D3 already draws it correctly for an absent engine.
`PRUSASLICER_PY_REQUIRE_ENGINE=1` is where it costs the most, because the mode
whose whole job is to assert an engine really was exercised could not tell
"the engine ran and the code is wrong" from "the engine never started".

**Ask the engine, not its packaging.** `PrusaSlicer.probe()` runs
`[*argv, "--help"]` and raises `EngineUnusableError` unless the engine started
and answered. `--help` is the probe because it is the only thing PrusaSlicer
answers -- there is no `--version` flag (D9). Three states, and each has
somewhere to go:

| state | how it is established | what conftest does |
| --- | --- | --- |
| absent | `PrusaSlicer()` raises `FileNotFoundError` | skip, or fail if required |
| found, unusable | `probe()` raises `EngineUnusableError` | skip, or fail if required |
| found, usable | `probe()` returns an `EngineProbe` | run the test |

`EngineUnusableError` carries `argv`, `engine_kind`, `returncode` and the
engine's `stdout`/`stderr`, so the launcher's own complaint -- usually the whole
explanation -- reaches the caller as fields rather than as prose in a message.
`returncode` is `None`, not a stand-in, when the launcher could not be started
at all and there never was an exit status.

**Exit 0 with nothing said is unusable too.** An engine that answers `--help`
with an empty stream did not identify itself, and accepting that as a working
engine is the same error one exit code further along.

**`probe()` establishes usable at a point in time, and that is all it can
establish.** The state it rules out can come back between the probe and the
call: a Flatpak that answered `--help` a second ago can fail to start for the
next process. That is not hypothetical here -- 135 sequential runs of
`tests/test_engine.py` on `main` on this host produced **1** red, with the
launcher answering `error: Extension org.freedesktop.Platform.GL.default has
invalid merge-dirs`, which is the same class of pre-start launcher failure this
entry is about and not something the code under test did. The rate is not
stable between sittings, so treat the figure as one measurement rather than a
frequency.

No probe can close that window, and this entry does not claim to. What it
removes is the *systematic* case, where the engine was never going to start and
the suite reported that as a verdict. The residue is a flake and is filed
separately (#43). Note that `PRUSASLICER_PY_REQUIRE_ENGINE=1` turns it into a
hard error rather than a skip, which is the correct trade for a mode whose job
is to assert an engine really ran -- and the reason the flake is worth a report
of its own rather than a retry loop.

**What this deliberately does not do:**

- **Discovery is unchanged.** Probing inside `__init__` would make every
  construction start a process -- roughly a second for a Flatpak -- and would
  fold "found and unusable" back into `FileNotFoundError`, which is the
  conflation this entry exists to remove. The probe is explicit and its result
  is a value.
- **The probe lives in the driver, not in `conftest.py`.** D1 puts the engine
  behind one module, and a `subprocess.run` written in the test suite would be
  checking an engine the driver would not have used.
- **`slice_model` and `generate_help` do not call it.** They already report a
  failed engine with its output attached; adding a probe ahead of each would be
  a second process launch per call to establish what the call is about to
  establish anyway.

## D15 — `additional_args` keys are passed through verbatim; the engine names its own options

`slice_model(additional_args={...})` builds `--{key}` from each key with no
transformation. A dictionary written with Python-shaped keys — `layer_height`,
because that is how PrusaSlicer's own config files and G-code footers spell it —
therefore reaches the engine as `--layer_height` and is rejected.

That is not hypothetical: every example in this repository was written that way, and
`examples/torus_example_attempt.py` failed to slice for it (#36).

**The obvious reading of "why not translate" is wrong, and worth recording so it is
not re-argued.** The argument that a `_` to `-` rewrite would make a misspelled
option indistinguishable from a correct one does not hold: no option name in
`--help-fff` contains an underscore, so a rewrite can collide with nothing, and a
name that is still not an option after rewriting is still rejected.

The reason that survives is ownership. **The engine is the sole authority on what its
options are called**, and a translation table here is a second place that has to
track the engine's naming. It would be wrong the first time the engine disagreed with
it, and wrong quietly — a rewritten name that is not an option produces the same
`Unknown option` as the name the author typed, so the driver's guess and the author's
mistake are reported identically. A driver that does not guess cannot guess wrong.

The cost is real and is accepted: the caller must read `--help-fff`, and the spelling
in the engine's config files is not the spelling on its command line. That cost is
visible — the engine says `Unknown option` and names it — which is the trade this
repository makes everywhere else.

*Supersedes:* if the engine ever ships a machine-readable option list, validating a
key against it before launching would be a refusal with a cause, which is strictly
better than passing an unknown name through. That is validation, not translation, and
it does not reopen this.
