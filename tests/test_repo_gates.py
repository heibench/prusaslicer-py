"""Gates on the repository's own machinery, not on the package.

A convention nothing checks is a convention that drifts. `CONTRIBUTING.md` puts it
as "a check that cannot fail is not a check", and these are the checks for claims
this repo makes about itself.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

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


def _just_recipes() -> dict[str, dict]:
    """Every recipe as `just` itself sees it.

    The names come from the tool rather than from a regex over the file, because a
    hand-rolled parser is exactly what failed here: the first version of this gate
    skipped any line with an `=` before the colon, which silently excluded every
    recipe with a defaulted parameter -- `capture-cli mode="all":` -- so #27 could be
    reintroduced verbatim on such a recipe and this test stayed green. A check that
    cannot fail is not a check.
    """
    out = subprocess.run(
        ["just", "--dump", "--dump-format", "json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)["recipes"]


def _comment_block_above(name: str, lines: list[str]) -> list[str] | None:
    """The contiguous comment block directly above `name`'s definition.

    None when the definition cannot be located, which is a defect in this helper and
    is asserted as such rather than skipped -- silently finding nothing is how the
    first version of this gate passed over the recipes it could not parse.
    """
    for i, line in enumerate(lines):
        if not re.match(rf"^{re.escape(name)}(\s|:)", line):
            continue
        block: list[str] = []
        j = i - 1
        while j >= 0:
            above = lines[j].strip()
            if above.startswith("[") and above.endswith("]"):
                j -= 1  # an attribute sits between the comment and the recipe
                continue
            if above.startswith("#"):
                block.insert(0, above)
                j -= 1
                continue
            break
        return block
    return None


@pytest.mark.skipif(shutil.which("just") is None, reason="needs the just binary")
def test_every_recipe_has_exactly_one_doc_comment_line() -> None:
    """`just` publishes the LAST comment line before a recipe, so a multi-line block
    silently publishes its final line and starves the recipe below it of one (#27).

    Both failure modes were live here: `capture-cli` carried three lines and
    `just --list` showed the third -- a note about D8, not a description -- while
    `extract-cli` had none, its own line having been absorbed into the block above.

    Rationale is not banned, it is separated: put it above a blank line, where `just`
    cannot reach it. Exactly one line rather than at-least-one, because a second line
    is how the drift starts. Private recipes are exempt -- `just --list` hides them,
    so a description would be for nobody.
    """
    lines = JUSTFILE.read_text(encoding="utf-8").splitlines()
    unlocatable, wrong = [], []
    for name, recipe in sorted(_just_recipes().items()):
        if recipe.get("private"):
            continue
        block = _comment_block_above(name, lines)
        if block is None:
            unlocatable.append(name)
        elif len(block) != 1:
            wrong.append(f"{name}: {len(block)} comment line(s) directly above it")

    assert not unlocatable, (
        f"this test could not find the definition of {unlocatable} in the justfile, so "
        "it was not checked -- fix the helper rather than the justfile"
    )
    assert not wrong, (
        "every recipe needs exactly one comment line directly above it; put any "
        "rationale above a blank line so `just` cannot publish it:\n  " + "\n  ".join(wrong)
    )


@pytest.mark.skipif(shutil.which("just") is None, reason="needs the just binary")
def test_every_listed_recipe_has_a_description() -> None:
    """The other half, read straight off `just`'s own output rather than inferred.

    The rule above is a proxy -- it counts comment lines. This asserts the property
    those lines exist for: nothing a reader sees in `just --list` is blank.
    """
    missing = [
        name
        for name, recipe in sorted(_just_recipes().items())
        if not recipe.get("private") and not (recipe.get("doc") or "").strip()
    ]
    assert not missing, f"these recipes appear in `just --list` with no description: {missing}"


def test_no_doc_attribute_is_used() -> None:
    """`[doc(...)]` states the description explicitly and would make the rule above
    unnecessary -- and unknown attributes are a PARSE error in every `just`, while
    `[doc]` exists only from 1.27.0. One of them breaks the entire file for anyone on
    an older `just`, Ubuntu 24.04 LTS included (D2.1).

    Matched precisely: a substring test for "doc" also rejects `[group('docs')]` and
    every other attribute, none of which have the version problem.
    """
    offenders = [
        n
        for n, line in enumerate(JUSTFILE.read_text(encoding="utf-8").splitlines(), 1)
        if re.match(r"\[\s*doc\s*[(\]]", line.lstrip())
    ]
    assert not offenders, f"[doc(...)] on line(s) {offenders}; see D2.1"
