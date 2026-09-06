"""Gates on the repository's own machinery, not on the package.

A convention nothing checks is a convention that drifts. `CONTRIBUTING.md` puts it
as "a check that cannot fail is not a check", and these are the checks for claims
this repo makes about itself.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JUSTFILE = ROOT / "justfile"


def test_every_uv_run_in_the_justfile_is_locked() -> None:
    """#23's guard is per-invocation, which is fail-OPEN without this.

    An exported `UV_LOCKED` would protect a recipe added next year by default. Ten
    explicit `--locked` flags do not: a new `uv run` is unprotected, and the failure
    is silent -- a stale lock gets rewritten at exit 0, which is the exact defect
    #23 was about. That is a check that cannot fail, so this is the check.

    `uv lock` is the one deliberate exception: it is the only recipe allowed to
    write the lockfile, and passing `--locked` to it would refuse the repair.
    """
    offenders = [
        (n, line.strip())
        for n, line in enumerate(JUSTFILE.read_text(encoding="utf-8").splitlines(), 1)
        if re.search(r"\buv run\b", line)
        and not line.lstrip().startswith("#")
        and "--locked" not in line
    ]
    assert not offenders, (
        "every `uv run` in the justfile must pass --locked, or a stale uv.lock is "
        "silently rewritten at exit 0 (#23, D2.1):\n  "
        + "\n  ".join(f"line {n}: {text}" for n, text in offenders)
    )


def test_the_lock_recipe_is_the_only_one_that_may_write_the_lockfile() -> None:
    """The other half. `uv lock` anywhere else would be a second writer, and the
    point of D2.1 is that exactly one recipe repairs what the rest only verify."""
    writers = [
        (n, line.strip())
        for n, line in enumerate(JUSTFILE.read_text(encoding="utf-8").splitlines(), 1)
        if re.search(r"\buv lock\b", line) and not line.lstrip().startswith("#")
    ]
    assert len(writers) == 1, f"expected exactly one `uv lock`, found: {writers}"


def _recipes_with_their_doc_block() -> list[tuple[str, list[str]]]:
    """Each recipe name, with the contiguous comment block directly above it.

    "Directly above" is what matters: a blank line ends the block, and `just` reads
    only what remains adjacent.
    """
    out: list[tuple[str, list[str]]] = []
    block: list[str] = []
    for raw in JUSTFILE.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if raw.startswith("#"):
            block.append(stripped)
        elif not stripped:
            block = []
        elif raw[0].isspace():
            continue  # a recipe body line
        elif (
            ":" in raw and not raw.startswith(("set ", "export ")) and "=" not in raw.split(":")[0]
        ):
            out.append((raw.split(":")[0].strip(), list(block)))
            block = []
        else:
            block = []
    return out


def test_every_recipe_has_exactly_one_doc_comment_line() -> None:
    """`just` publishes the LAST comment line before a recipe, so a multi-line block
    silently publishes its final line and starves the recipe below it of one (#27).

    Both failure modes are real and were live here: `capture-cli` carried three lines
    and `just --list` showed the third -- a note about D8, not a description -- while
    `extract-cli` had none, its own line having been absorbed into the block above.

    Rationale is not banned, it is separated: put it above a blank line, where `just`
    cannot reach it. Exactly one line rather than at-least-one, because a second line
    is how the drift starts.
    """
    wrong = [
        (name, len(block), block[-1] if block else "")
        for name, block in _recipes_with_their_doc_block()
        if len(block) != 1
    ]
    assert not wrong, (
        "every recipe needs exactly one comment line directly above it; put any "
        "rationale above a blank line so `just` cannot publish it:\n  "
        + "\n  ".join(f"{name}: {n} line(s), would show {last!r}" for name, n, last in wrong)
    )


def test_no_doc_attribute_is_used() -> None:
    """`[doc(...)]` states the description explicitly and would make the rule above
    unnecessary -- and unknown attributes are a PARSE error in every `just`, while
    `[doc]` exists only from 1.27.0. One of them breaks the entire file for anyone on
    an older `just`, Ubuntu 24.04 LTS included (D2.1)."""
    text = JUSTFILE.read_text(encoding="utf-8")
    offenders = [
        n
        for n, line in enumerate(text.splitlines(), 1)
        if line.lstrip().startswith("[") and "doc" in line
    ]
    assert not offenders, f"[doc(...)] on line(s) {offenders}; see D2.1"
