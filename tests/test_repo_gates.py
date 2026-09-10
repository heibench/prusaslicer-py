"""Gates on the repository's own machinery, not on the package.

A convention nothing checks is a convention that drifts. `CONTRIBUTING.md` puts it
as "a check that cannot fail is not a check", and these are the checks for claims
this repo makes about itself.
"""

from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JUSTFILE = ROOT / "justfile"
PYPROJECT = ROOT / "pyproject.toml"


def _resolved_recipe(name: str) -> str:
    """What `just` would actually RUN for a recipe, with interpolation resolved.

    Reading the justfile's raw text is not enough, and the gap is an ordinary
    refactor rather than an evasion. `mypy . {{mypy_extra}}` with
    `mypy_extra := "--exclude scripts/"` at the top of the file, or a defaulted
    parameter invoked as `(typecheck "--exclude scripts/")`, both leave the recipe
    text saying `mypy .` while `just` runs a narrowed command. Both defeated the
    `mypy .` assertion and the `--exclude` ban at once.

    `--dry-run` prints the resolved command to stderr and executes nothing.
    """
    out = subprocess.run(
        ["just", "--dry-run", name], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert out.returncode == 0, f"`just --dry-run {name}` failed:\n{out.stderr}"
    resolved = out.stderr.strip()
    assert resolved, f"`just --dry-run {name}` printed nothing to resolve"
    return resolved


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
        check=False,
    )
    # Not `check=True`: it raises a CalledProcessError whose text names the command and
    # the exit status and drops the stderr this call just captured -- so an unparseable
    # justfile surfaced as a traceback instead of `just`'s own "Mismatched closing
    # delimiter" line, twice, once per gate.
    #
    # `--dump-format json` has shipped since just 0.10.4 (2021-11-21), which is far
    # older than the 1.27.0 that D2.1 refuses to depend on for `[doc]`, so this gate
    # does not undercut that stance -- Ubuntu 24.04 LTS's 1.21.0 has this and not that.
    # If some `just` ever lacks it, the assertion below says which tool failed and why.
    assert out.returncode == 0, (
        f"`just --dump --dump-format json` failed ({out.returncode}); this gate reads "
        f"the recipe list from it:\n{out.stderr.strip()}"
    )
    dump = json.loads(out.stdout)
    # Fail closed on a scope this gate does not cover. Submodule recipes live under
    # `modules`, not `recipes`, so #27 could live in one unseen -- and splitting a
    # growing justfile into modules is the normal path, where nobody would think to
    # re-check this test. An assertion is cheaper than the silence.
    assert not dump.get("modules"), (
        f"this gate does not descend into submodules {sorted(dump['modules'])}; extend "
        "it before adding one, or a recipe there can carry #27 unseen"
    )
    return dump["recipes"]


def _comment_blocks_above(name: str, lines: list[str]) -> list[list[str]] | None:
    """One comment block per definition of `name`, in file order.

    None when no definition can be located, which is a defect in this helper and is
    asserted as such rather than skipped -- silently finding nothing is how the first
    version of this gate passed over the recipes it could not parse.

    EVERY definition, not just the last. `clean` has an `[unix]` and a `[windows]`
    body, and `just --dump` reports only the one for the running platform, so taking
    a single block left the other unchecked on every platform: the #27 defect could
    be planted on the `[unix]` half with both doc gates green and `just --list`
    publishing rationale as the description. Two OS-attributed bodies are both live
    code, unlike `allow-duplicate-recipes` where the last simply wins.
    """
    blocks: list[list[str]] = []
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i]
        # `@name:` is a quiet recipe and is still a definition.
        if not re.match(rf"^@?{re.escape(name)}(\s|:)", line):
            continue
        if re.match(rf"^@?{re.escape(name)}\s*:=", line):
            # `just` allows a variable and a recipe to share a name, and `lint := "ruff"`
            # matches the pattern above because of the space before `:=`. Matching the
            # assignment instead of the recipe counted the wrong comment block and let
            # #27 through with every gate green -- the `unlocatable` net does not fire,
            # because something WAS found.
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
        blocks.insert(0, block)
    return blocks or None


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
        found = _comment_blocks_above(name, lines)
        if found is None:
            unlocatable.append(name)
            continue
        for n, block in enumerate(found, 1):
            if len(block) != 1:
                where = f"{name} (definition {n} of {len(found)})" if len(found) > 1 else name
                wrong.append(f"{where}: {len(block)} comment line(s) directly above it")

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


@pytest.mark.parametrize("assignment", ['lint := "ruff"', 'lint:="ruff"', 'lint  :=  "ruff"'])
def test_the_doc_gate_is_not_fooled_by_an_assignment_sharing_a_recipe_name(
    assignment: str,
) -> None:
    """The F9 false pass, pinned. `just` allows `lint := "ruff"` beside a `lint:` recipe,
    and the assignment matches a naive name-anchored search first -- so the gate counted
    the assignment's comment block, found one line, and passed while #27 was live and
    published. The `unlocatable` net does not catch it either: something WAS found.
    """
    lines = [
        "# the linter this project uses",
        assignment,
        "",
        "# Run the linter over the whole tree",
        "# Ruff is pinned in pyproject -- see D2.",
        "lint:",
        "    echo hi",
    ]
    found = _comment_blocks_above("lint", lines)
    assert found is not None and len(found) == 1, "expected one `lint` definition"
    block = found[0]
    assert block is not None, "the recipe must be found, not the assignment"
    assert len(block) == 2, (
        f"expected the RECIPE's two-line block, got {block!r} -- if this is one line the "
        "helper matched the assignment and the gate has gone fail-open again"
    )


@pytest.mark.skipif(shutil.which("just") is None, reason="needs the just binary")
def test_the_typecheck_recipe_checks_the_whole_repository() -> None:
    """#24 narrowed the typecheck scope by hand, which is fail-OPEN.

    The recipe used to name `prusaslicer_py/ tests/`, so `scripts/` -- the code
    that builds the extracted CLI surface D6 froze -- was never checked at all,
    and nothing said so. Adding `scripts/` by hand would have left `examples/`
    outside on the same terms, and the next directory after that. A bare `mypy .`
    is the only spelling that cannot silently omit something: what it covers is
    decided by the repository's contents, not by a list someone has to remember
    to extend.

    Exclusions belong in `pyproject.toml`, where they are visible and reviewable,
    not in an argument list read only when a recipe is edited.
    """
    recipes = _just_recipes()
    assert "typecheck" in recipes, f"no `typecheck` recipe; found {sorted(recipes)}"

    # Resolve `check`, not `typecheck`. A defaulted parameter -- `typecheck extra="":`
    # invoked as `check: ... (typecheck "--exclude scripts/")` -- resolves to a bare
    # `mypy .` when the recipe is asked about on its own, while what CI runs is
    # narrowed. Asking the recipe the same question CI asks is the only version that
    # cannot differ from it.
    resolved = _resolved_recipe("check")
    mypy_lines = [line for line in resolved.splitlines() if re.search(r"\bmypy\b", line)]
    assert len(mypy_lines) == 1, (
        f"expected exactly one mypy invocation in `just check`, found {len(mypy_lines)}:"
        f"\n  {resolved}"
    )
    command = mypy_lines[0]
    assert re.search(r"\bmypy\s+\.(?:\s|$)", command), (
        "`just check` must run `mypy .` so no directory can be omitted by forgetting "
        f"to list it; it runs:\n  {command}"
    )
    assert "--exclude" not in command, (
        "narrowing on the command line puts the excluded set where only a reader of "
        "the recipe finds it; D10 says exclusions belong in `pyproject.toml`. It "
        f"runs:\n  {command}"
    )


#: Every way this repository spells "the engine". Four, and the comment is the
#: kind of thing that goes stale, so `test_the_engine_name_gate_knows_every_
#: spelling_slicer_py_uses` checks the tuple against `slicer.py` rather than
#: trusting this list to be kept current. `PrusaSlicer.app` is here because a
#: macOS bundle path is what a contributor would paste into an example; it does
#: not appear in `slicer.py` itself, which is fine -- the meta-gate requires
#: slicer.py's names to be covered, not the reverse.
#:
#: The longer spellings look redundant beside the shorter ones -- "prusa-slicer"
#: already matches "prusa-slicer-console.exe" as a substring -- and they are not.
#: This tuple has two consumers with different needs: the D1 scan matches
#: substrings, where the shorter entry does subsume the longer; the meta-gate below
#: compares *exact* literals against what the package contains, where it does not.
#: Removing the longer entries made the meta-gate report slicer.py's own name as
#: unclassified.
#:
#: Note the asymmetry with `_NOT_A_NAME`, which is deliberate rather than an
#: oversight: a stale entry here can only over-refuse a string, which is
#: fail-closed, while a stale entry in `_NOT_A_NAME` would go on vouching for a
#: literal nobody has rechecked -- so only that list is gated for staleness.
#:
#: The bare capitalised binary `PrusaSlicer` is deliberately NOT here. It is a
#: real spelling -- `engine.yml` symlinks it -- but as a substring it matches
#: every sentence of prose that mentions the product, which would make the gate
#: fire on documentation and train people to ignore it.
_EXEC_LITERALS = (
    "prusa-slicer-console.exe",
    "prusa-slicer",
    "com.prusa3d.PrusaSlicer",
    "PrusaSlicer.app",
    "slic3r-console.exe",
    "slic3r",
)

#: Strings in the package that match the engine pattern and are not engine names:
#: prose in messages, and resource paths inside an installation.
_NOT_A_NAME = {
    ". Ensure PrusaSlicer is installed and added to PATH.",
    # Python identifiers in `__init__.py`'s `__all__`, not engine names.
    "PrusaSlicer",
    "SliceResult",
    "Contents/Resources/PrusaSlicer/shapes",
    "PrusaSlicer exited ",
    "PrusaSlicer exited 0 but ",
    "PrusaSlicer exited 0 but stated no version in its --help output",
    "share/PrusaSlicer/shapes",
    # The version banner pattern (#34). It matches what the engine PRINTS about
    # itself, which is not a name anything is invoked by -- pasting it into
    # another module would start nothing.
    "^PrusaSlicer-(?P<version>\\d\\S*)",
}

#: The file allowed to contain one, and the directory allowed to. `slicer.py` is
#: the seam D1 defines; `tests/` names paths to drive a `subprocess` stand-in,
#: which is that seam being exercised rather than a second home for the choice.
_THE_DRIVER = "prusaslicer_py/slicer.py"
_MAY_NAME_THE_ENGINE = ("tests/",)


def _tracked_python_files() -> list[str]:
    """Every `.py` git tracks, as repo-relative posix paths.

    `rglob` needed a hand-written exclusion list -- `.venv/`, `build/` -- which is
    the omit-by-default shape D10 argues against, one directory at a time. It also
    went red on a virtualenv at `venv/` or an unpacked sdist under `dist/`, neither
    of which is a defect in this repository.

    The narrow fail-open is a brand-new untracked file, which this cannot see. That
    is acceptable: pre-commit runs on staged content and CI runs on a checkout, so
    the window closes at `git add`.
    """
    if shutil.which("git") is None:
        pytest.skip("needs the git binary")
    out = subprocess.run(
        ["git", "ls-files", "*.py"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert out.returncode == 0, f"`git ls-files` failed:\n{out.stderr}"
    files = [line for line in out.stdout.splitlines() if line]
    assert files, "`git ls-files '*.py'` returned nothing; the scan would assert nothing"
    return files


def _engine_ish_literals(source: str) -> set[str]:
    """Non-docstring string literals that could be naming the engine.

    `slic3r` is in the pattern because it is a real spelling: PrusaSlicer forked
    from Slic3r and upstream still ships `slic3r-console.exe`, which contains
    neither "prusa" nor "slicer". `bytes` literals are decoded rather than skipped
    -- a `b"prusa-slicer"` is the same name.
    """
    tree = ast.parse(source)
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    }
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or id(node) in docstrings:
            continue
        value = node.value
        if isinstance(value, bytes):
            value = value.decode("utf-8", "replace")
        if isinstance(value, str) and re.search(r"prusa|slicer|slic3r", value, re.IGNORECASE):
            found.add(value)
    return found


def test_only_the_driver_names_the_engine_executable() -> None:
    """D1's claim has now been wrong three times, so it stops being a claim.

    D1 says one module may name an executable. The sentence has drifted every time
    it was rewritten: it described a `scripts/01_store_helps.py` carve-out that the
    script had already removed; the correction overlooked that `tests/` name one
    deliberately; and the re-correction overlooked `examples/`, which named the real
    Windows executable and was Windows-only for exactly the reason D1 gives for
    removing the original carve-out.

    Each rewrite was checkable by grep and none of them was checked. That is the
    definition CONTRIBUTING.md gives -- a check that cannot fail is not a check --
    applied to the sentence rather than to the code, so the sentence is now gated.
    """
    offenders = []
    for rel in _tracked_python_files():
        if rel == _THE_DRIVER or rel.startswith(_MAY_NAME_THE_ENGINE):
            continue
        for n, line in enumerate((ROOT / rel).read_text(encoding="utf-8").splitlines(), 1):
            if any(lit in line for lit in _EXEC_LITERALS):
                offenders.append(f"{rel}:{n}: {line.strip()}")

    assert not offenders, (
        "only `prusaslicer_py/slicer.py` may name the engine executable (D1); "
        "construct `PrusaSlicer()` and let the driver find it. Found:\n  " + "\n  ".join(offenders)
    )


def test_the_engine_name_gate_knows_every_spelling_slicer_py_uses() -> None:
    """`_EXEC_LITERALS` is a hand-written list, so something has to gate it.

    An earlier version of this read only `_exec_name`, which meant it gated almost
    nothing: `FLATPAK_APP_ID` already lived outside that function, and adding a
    `MACOS_BINARY = "PrusaSlicer-macos"` constant beside it -- then pasting that
    name into an example -- passed every gate in this file. That is the defect this
    PR fixed, reintroduced inside the test written to prevent it.

    So it reads *every* non-docstring string literal in `slicer.py` that looks like
    it could name the engine, and requires each to be either a known spelling or
    explicitly listed as prose. A new name is then a red gate rather than a silent
    hole, and the failure mode of forgetting to classify one is fail-closed.

    Deriving the names from `_exec_name()` at runtime would be worse: it returns one
    spelling per platform, so a gate calling it on Linux would stop catching the
    Windows name.
    """
    candidates: set[str] = set()
    scanned = [f for f in _tracked_python_files() if f.startswith("prusaslicer_py/")]
    assert scanned, "no package files found to scan"
    for rel in scanned:
        candidates |= _engine_ish_literals((ROOT / rel).read_text(encoding="utf-8"))

    assert candidates, "no engine-ish literals found in the package; did it move?"

    stale = sorted(_NOT_A_NAME - candidates)
    assert not stale, (
        "`_NOT_A_NAME` lists literals that are no longer in the package, so the list "
        "has drifted from what it describes and would go on vouching for strings "
        "nobody has looked at since:\n  " + "\n  ".join(repr(x) for x in stale)
    )

    unclassified = sorted(candidates - _NOT_A_NAME - set(_EXEC_LITERALS))
    assert not unclassified, (
        "`prusaslicer_py/` contains string literals the D1 gate has not been told "
        "about, so "
        "the gate would miss them everywhere else in the repository:\n  "
        + "\n  ".join(repr(u) for u in unclassified)
        + "\nAdd each to `_EXEC_LITERALS` if it names the engine, or to `_NOT_A_NAME` "
        "if it is prose or a resource path."
    )


@pytest.mark.skipif(shutil.which("just") is None, reason="needs the just binary")
def test_the_check_recipe_actually_runs_the_typechecker() -> None:
    """Gating a recipe's body says nothing about whether anything calls it.

    Every other gate here verifies what `typecheck` *contains*. None verified that
    `check` still depends on it -- so `check: fmt-check lint` passed all of them
    while `.github/workflows/ci.yml` ran `just check` and typechecked nothing. The
    sharper version keeps the gates green and reintroduces #24 exactly:

        check: fmt-check lint
            uv run --locked mypy prusaslicer_py/ tests/

    `check: fmt-check lint typecheck` is a hand-written list, which is the shape
    D10 spends its opening paragraph on.
    """
    recipes = _just_recipes()
    assert "check" in recipes, f"no `check` recipe; found {sorted(recipes)}"
    deps = [d["recipe"] for d in recipes["check"]["dependencies"]]
    assert "typecheck" in deps, (
        "`just check` is what CI runs, so it must depend on `typecheck`; "
        f"it depends on {deps}. A `mypy` line in `check`'s own body does not count "
        "-- that is where #24's narrowed scope came back."
    )


def test_pyproject_is_the_mypy_config_mypy_actually_reads() -> None:
    """mypy prefers `mypy.ini` over `pyproject.toml`, silently.

    Its precedence is `mypy.ini`, then `.mypy.ini`, then `pyproject.toml`. A
    two-line `mypy.ini` naming only `python_version` therefore drops
    `check_untyped_defs` and `disallow_untyped_defs` together, and a fully
    unannotated new script passes clean at exit 0. mypy emits an
    `[annotation-unchecked]` *note* pointing straight at the disabled feature and
    still exits 0 -- the same note-versus-error trap D10 records for
    `warn_unused_configs`.

    Nothing else in this repository would notice, because every gate here reads
    `pyproject.toml` and assumes mypy did too.
    """
    for name in ("mypy.ini", ".mypy.ini"):
        assert not (ROOT / name).exists(), (
            f"`{name}` silently supersedes `[tool.mypy]` in pyproject.toml, taking "
            "`check_untyped_defs` and `disallow_untyped_defs` with it. Put mypy "
            "configuration in pyproject.toml, where D10 and these gates can see it."
        )
    setup_cfg = ROOT / "setup.cfg"
    if setup_cfg.exists():
        assert "[mypy]" not in setup_cfg.read_text(encoding="utf-8"), (
            "a `[mypy]` section in setup.cfg supersedes pyproject.toml's `[tool.mypy]`"
        )


def test_ci_runs_the_gates_that_guard_all_of_this() -> None:
    """The chain above is only worth anything if CI still invokes it.

    `test_the_check_recipe_actually_runs_the_typechecker` asserts `check` calls
    `typecheck`. Nothing asserted that CI calls `check` -- changing `ci.yml`'s step
    to `just lint` left every gate in this file green while the typechecker stopped
    running on pull requests.

    **This is where the recursion stops, and that is worth saying.** `just` can be
    made to run nothing at all -- `set shell := ["true", "-c"]` makes both `just
    check` and `just test` print their commands and exit 0 -- and no test inside
    pytest can catch that, because pytest never runs. A gate cannot verify the
    machinery that decides whether the gate runs. This one closes the realistic
    half: a workflow edited to call something narrower.
    """
    ci = ROOT / ".github/workflows/ci.yml"
    assert ci.exists(), "ci.yml is gone; the gates in this file guard nothing"
    text = ci.read_text(encoding="utf-8")
    pre_commit_job = re.search(r"^  pre-commit:\n(?:(?:    .*)?\n)*", text, re.M)
    assert pre_commit_job, "no `pre-commit` job in ci.yml"
    # Matched as a key, not as a substring. `fetch-depth: 50` under a comment reading
    # "was fetch-depth: 0; full history is slow on this runner" satisfied the
    # substring form -- an ordinary CI optimisation, and per the depth table below
    # it silently loses the added-then-removed case this hook exists for.
    assert re.search(r"^\s*(-\s*)?fetch-depth:\s*0\s*$", pre_commit_job.group(), re.M), (
        "the `pre-commit` job must check out full history. `gitleaks-history` scans "
        "what the clone contains and says nothing about what it cannot see: on a "
        "shallow clone a secret added and later removed reports `no leaks found` at "
        "exit 0, with no warning. Deleting this line reads as a cleanup and silently "
        "removes the control."
    )
    assert "pre-commit/action" in text, (
        "`ci.yml` no longer runs pre-commit, so `.pre-commit-config.yaml`'s eight "
        "hooks -- gitleaks included -- are enforced only on machines that installed "
        "the local hook, which `--no-verify` skips"
    )
    for recipe in ("just check", "just test"):
        assert re.search(rf"^\s*(-\s*)?run:\s*{re.escape(recipe)}\s*$", text, re.M), (
            f"`ci.yml` no longer runs `{recipe}`, so the gates in this file do not "
            "run on pull requests. Every other gate here assumes it does."
        )

    # A step or job that is present but never runs satisfies the check above while
    # running nothing. `if: false` on the `check` job was a fully green PR, because
    # the `ok` job tested for 'failure' and a skipped job reports 'skipped'.
    for job in ("check", "test", "pre-commit", "recipes"):
        block = re.search(rf"^  {job}:\n(?:(?:    .*)?\n)*", text, re.M)
        assert block, f"no `{job}` job in ci.yml"
        body = block.group()
        # Banning `if:` alone was enumerating one bad state out of several.
        # `continue-on-error: true` on the job or the step makes it report success
        # when `just check` fails, so `needs.check.result == 'success'` holds and the
        # `ok` job passes -- a green pull request over a red gate, with no `if:`
        # anywhere. State the positive property instead: these two jobs run
        # unconditionally and their result is the truth.
        # `env:` is here because `SKIP=gitleaks,check-yaml` on the pre-commit
        # action turns those hooks off and reports success -- the same defeat as
        # `if: false`, one level above where the ban was looking.
        for forbidden in ("if:", "continue-on-error:", "env:"):
            # `(-\s*)?` because a step's first key is written `- if: false`, and
            # `\s*` does not match `-`. Reordering the keys walked the original
            # `if: false` defeat straight back in. The `run:` assertion above has
            # used this idiom since it was written; this one had not.
            assert not re.search(rf"^\s*(-\s*)?{re.escape(forbidden)}", body, re.M), (
                f"the `{job}` job (or a step in it) carries `{forbidden}`, which per "
                "GitHub's documented behaviour lets it not run, or report success "
                "when it failed, while every gate in this file stays green. "
                "(Documented Actions behaviour, not measured here -- this suite "
                "cannot run Actions.)"
            )

    # A trigger that never fires is the same defect one level out: the workflow is
    # present, correct, and never runs on the pull request it is supposed to gate.
    trigger = re.search(r"^on:\n(?:(?:  .*)?\n)*", text, re.M)
    assert trigger, "no `on:` block in ci.yml"
    assert "pull_request" in trigger.group(), "ci.yml no longer triggers on pull_request"
    for narrowing in ("paths:", "paths-ignore:", "types:"):
        assert narrowing not in trigger.group(), (
            f"the `on:` block carries `{narrowing}`, which per GitHub's documented "
            "behaviour can stop this workflow running on a pull request entirely, "
            "with nothing else here noticing. (Documented Actions behaviour, not "
            "measured here.)"
        )

    assert "needs.recipes.result != 'success'" in text, (
        "the `recipes` job must gate `ok`; it is the only place the Windows half of "
        "`just clean` is executed rather than read"
    )

    # Asserting the job EXISTS says nothing about what it does. Three edits left it
    # named, gating, and useless: moving it to `ubuntu-latest` (a plausible "cheaper
    # runner" cleanup, which silently dispatches `clean` to the POSIX body), deleting
    # the assertion step, and replacing `just clean` with anything else. The message
    # above claims this job executes the Windows half -- so something has to make
    # that true.
    recipes = re.search(r"^  recipes:\n(?:(?:    .*)?\n)*", text, re.M)
    assert recipes, "no `recipes` job in ci.yml"
    body = recipes.group()
    assert re.search(r"^\s*runs-on:\s*windows-latest\s*$", body, re.M), (
        "the `recipes` job must run on windows-latest; on Linux `just clean` "
        "dispatches to the `[unix]` body and the Windows half is never executed"
    )
    assert re.search(r"^\s*(-\s*)?run:\s*just clean\s*$", body, re.M), (
        "the `recipes` job must actually run `just clean`"
    )
    # Matched as a line, not a substring -- the same lesson twelve lines above, and
    # I made the same mistake again here. A comment left behind while removing the
    # step ("the old step threw \"just clean left: $stale\"; removed as flaky")
    # satisfies a substring test.
    assert re.search(r'^\s*if \(\$stale\) \{ throw "just clean left:', body, re.M), (
        "the assertion after `just clean` is gone, so a `clean` that silently "
        "removes nothing passes -- which is the bug this job caught on its first run"
    )
    assert "no __pycache__ was produced" in body, (
        "the step that creates the artifacts before `just clean` is gone. Without it "
        "only `.venv` exists after `just setup`, so the assertion is vacuous for five "
        "of the six and the `__pycache__` sweep is exercised against no input at all"
    )
    assert "RemoveFileSystemItemIOError" in body, (
        "the loud-failure probe is gone. Deleting it and then dropping "
        "`-ErrorAction Stop` in a later tidy-up restores a `clean` that exits 0 "
        "having removed nothing, with nothing red anywhere"
    )
    assert "PRUSASLICER_PY_REQUIRE_ENGINE is set but" in body, (
        "the #30 step is gone. D12 says #30 is settled by measurement in this job, "
        "and `engine.yml` cites it twice -- delete the step and three prose sites "
        "assert a measurement nothing performs, which is #30's own complaint"
    )
    assert "needs.check.result != 'success'" in text, (
        "the `ok` job must require upstream success; testing only for 'failure' "
        "passes a job that was skipped"
    )


@pytest.mark.skipif(shutil.which("just") is None, reason="needs the just binary")
def test_the_typechecker_still_objects_to_a_defect_planted_in_scripts() -> None:
    """Ask mypy to prove it is still checking, rather than asking how it was called.

    Counting files was the previous version of this and it was not enough. A count
    says how many files were *counted*, not which ones, nor whether anything was
    examined in them. Three configurations keep the number at 14 and remove the
    checking:

    * ``ignore_errors = true`` for the script modules -- 14 files, defect missed;
    * ``disable_error_code = ["arg-type", ...]`` -- 14 files, defect missed;
    * ``exclude`` the three scripts and drop three untracked ``.py`` elsewhere --
      14 files again, and `scripts/` is the whole reason this issue exists.

    That last one works precisely because the comparison was ``>=`` on cardinality.
    Cardinality can be padded; a defect cannot. So this plants a real defect in the
    directory #24 is about -- a call with its arguments reversed, the exact shape
    D10 is written around -- and requires `just check` to reject it.

    One probe, and it does not need to know which trick was used: under all three
    configurations above the canary passes and this gate goes red. It is also the
    only version of this that cannot be satisfied by a count, because it reads
    whether mypy *objected*, and no arrangement of files produces an objection to
    a defect that was not examined.
    """
    canary = ROOT / "scripts" / "zz_typecheck_canary.py"
    assert not canary.exists(), f"{canary} already exists; refusing to overwrite it"
    # One defect per mechanism D10 relies on, not one per gate. A single shape is
    # not enough: `disable_error_code` can spare `arg-type` while switching off
    # `no-untyped-def` (which IS `disallow_untyped_defs`) and `typeddict-item`
    # (which IS the D6 schema protection the TypedDict was added for). Both would
    # die silently behind a canary that only tests for a reversed call.
    #
    # `[assignment]` covers the fourth mechanism, and it is deliberately planted
    # INSIDE the unannotated function. `check_untyped_defs` is what reads bodies
    # like that one, and `pyproject.toml` exempts `tests/` from annotation
    # explicitly *because* of it -- so flipping that flag leaves the whole test
    # suite with neither protection, and mypy says so with a NOTE at exit 0. No
    # other gate can see it: the count is unchanged, linecount excludes `tests/`
    # by design, and the canary's other three defects live in annotated code.
    #
    # Deliberately ruff-clean: formatted as ruff formats, and lint-clean. An earlier
    # version used single quotes, so `fmt-check` rejected it before mypy ran and the
    # gate passed on ruff's output with the typechecker never consulted -- the gate
    # passing for the wrong reason, which is the thing it exists to catch.
    canary.write_text(
        "from pathlib import Path\n"
        "from typing import TypedDict\n\n\n"
        "class _Record(TypedDict):\n"
        "    option: str\n\n\n"
        "def _writes(data: dict[str, int], path: Path) -> None:\n"
        '    path.write_text(str(data), encoding="utf-8")\n\n\n'
        "def _unannotated(value):\n"
        '    inner: int = "not an int"\n'
        "    return value, inner\n\n\n"
        '_writes(Path("x"), {"a": 1})\n'
        '_record: _Record = {"optionn": "x"}\n',
        encoding="utf-8",
    )
    try:
        out = subprocess.run(
            ["just", "check"], cwd=ROOT, capture_output=True, text=True, check=False
        )
        report = out.stdout + out.stderr
    finally:
        canary.unlink()

    # These are mypy's codes, so this cannot be satisfied by ruff objecting to the
    # file for its own reasons -- which is how the first version of this passed.
    missing = [
        code
        for code in ("[arg-type]", "[no-untyped-def]", "[typeddict-item]", "[assignment]")
        if code not in report
    ]
    assert not missing and "zz_typecheck_canary" in report, (
        f"`just check` did not report {missing or 'the planted defects'} for a "
        "canary in `scripts/`, so at least one of the properties D10 rests on is no "
        "longer being enforced. `no-untyped-def` is `disallow_untyped_defs`; "
        "`typeddict-item` is D6's schema protection; `assignment` is planted in an "
        "unannotated body, so losing it means `check_untyped_defs` is off and "
        "`tests/` has no checking at all. An `exclude` entry, "
        "`ignore_errors`, or a `disable_error_code` entry will each switch one off "
        f"while leaving the file count untouched.\n{report}"
    )
    assert out.returncode != 0, (
        "`just check` reported the planted defect and still exited 0, so its exit "
        f"code does not depend on what mypy found.\n{report}"
    )


@pytest.mark.skipif(shutil.which("just") is None, reason="needs the just binary")
def test_the_typechecker_actually_covered_every_tracked_file() -> None:
    """Gate what mypy COVERED, not how it was invoked. This is the one that holds.

    Every earlier version of this gate read an instruction and asked whether it
    looked right: the recipe's text, then the recipe's text after `just`
    interpolation. Both were defeated one layer further down, because `just` hands
    the line to a shell and everything the shell does is invisible to `--dry-run`::

        uv run --locked mypy . $(cat .mypyargs 2>/dev/null)   # 11 files, gate green
        uv run --locked mypy . $MYPY_EXTRA                    # 9 files, gate green
        uv run --locked mypy . "$@"                           # 11 files, gate green

    There is always another layer of instruction to spoof. There is no other
    outcome: mypy names its own scope in both the passing and the failing case, and
    that number cannot be argued with.

    So this runs the real recipe and reads the count back. A narrowing anywhere --
    command substitution, a dotenv variable, positional arguments, a
    `[tool.mypy] exclude` entry, a hand-edited recipe -- lowers it, and the gate
    goes red without needing to know which trick was used.

    The comparison is against every *tracked* `.py`, deliberately not against
    tracked-minus-excluded: subtracting the declared excludes would let the
    exclusion list grow while the gate stayed green, which is the omit-by-default
    shape D10 exists to argue against. `>=` rather than `==` because an untracked
    scratch file legitimately raises mypy's count and is nobody's defect.
    """
    expected = len(_tracked_python_files())
    # `check`, not `typecheck`: with `set positional-arguments` and a `*args`
    # recipe, asking `typecheck` on its own resolves to the full scope while the
    # narrowing rides in on `check`'s invocation of it. Run what CI runs.
    out = subprocess.run(["just", "check"], cwd=ROOT, capture_output=True, text=True, check=False)
    report = out.stdout + out.stderr
    match = re.search(r"(?:in|checked)\s+(\d+)\s+source files?", report)
    if not match:
        # `check` runs fmt-check and lint first, so either of those failing means
        # mypy never spoke. Skipping is not fail-open here: `just check` has already
        # exited non-zero, so CI is red either way and nothing is being hidden.
        assert out.returncode != 0, (
            f"`just check` succeeded without mypy reporting a file count:\n{report}"
        )
        pytest.skip(
            "`just check` failed before mypy ran, so there is no count to read. "
            "If this is a lint or format failure, `just check` is red in CI too and "
            "nothing is hidden. If it is not -- this runs `just check` nested inside "
            "`uv run pytest`, while CI runs it directly -- then the two disagree and "
            f"that is worth knowing:\n{report}"
        )

    checked = int(match.group(1))
    assert checked >= expected, (
        f"mypy checked {checked} files but git tracks {expected} `.py` files, so "
        "something narrowed its scope. That may be the recipe, a shell expansion "
        "inside it, or an `exclude` entry in `pyproject.toml` -- this gate reads the "
        f"outcome rather than the instruction, so it does not say which.\n{report}"
    )


@pytest.mark.skipif(shutil.which("just") is None, reason="needs the just binary")
def test_mypy_actually_examined_every_tracked_module() -> None:
    """A planted defect proves its own file, not the files beside it.

    `ignore_errors = true` scoped to the script modules leaves the canary in the
    same directory checked, so the canary gate passes while the three files #24 is
    about are examined for nothing. The count gate passes too -- mypy still reports
    them as source files. Both are satisfied, and nothing is being checked.

    mypy will say so if asked directly. `--linecount-report` prints, per module, the
    lines it *analysed* against the lines the module *has*, and under `ignore_errors`
    the first column collapses while the second does not::

        baseline        197 197  5  5   02_json_cli
        ignore_errors     0 197  0  5   02_json_cli

    So this asserts every tracked module appears with a non-zero analysed count. It
    is the same "read the outcome" move as the other two gates, aimed at the one
    property neither of them can see: not how mypy was invoked, not how many files
    it counted, but whether it looked inside them.

    Read what the signal is, and is not: "mypy analysed zero lines of *typed* code
    in this module", not "this module was skipped". The two coincide for a file that
    should be fully annotated, which is why the scope is the modules
    `disallow_untyped_defs` covers. It also means an `ignore_errors` override on a
    module with nothing typed in it stays invisible -- and inert, since there is
    nothing there for it to suppress. The gate fires the moment there is.

    Deliberately NOT routed through `just check`. Adding `--linecount-report` to the
    recipe would make every developer's `just check` write a test-only artifact, to
    answer a question the recipe does not ask. This gate's only claim is "did mypy
    look inside these modules"; whether CI's invocation was narrowed is the count
    gate's job, and it asks that through the recipe.
    """
    # Only the modules `disallow_untyped_defs` covers. The first column counts lines
    # of *typed* code, so `tests/` legitimately reads zero -- it is exempt from
    # annotation by design, and flagging it would be reading the exemption as a
    # defect. Everywhere else, zero typed lines in a file that is fully annotated
    # means mypy stopped looking.
    # `__init__.py` is mapped to its package rather than dropped. Skipping it by
    # name was a hand-written exclusion inside the gate set built to argue against
    # hand-written exclusions, and it was fail-open: `ignore_errors` on the
    # `prusaslicer_py` module left the package's public entry point -- the one that
    # defines `__all__` and every re-export consumers import -- checked for nothing,
    # invisible to all four gates. mypy already reports it as `prusaslicer_py`.
    tracked = {
        Path(f).parent.name if Path(f).name == "__init__.py" else Path(f).stem
        for f in _tracked_python_files()
        if not f.startswith("tests/")
    }
    with tempfile.TemporaryDirectory() as tmp:
        out = subprocess.run(
            ["uv", "run", "--locked", "mypy", ".", "--linecount-report", tmp],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        report_file = Path(tmp) / "linecount.txt"
        assert report_file.exists(), (
            f"mypy produced no linecount report:\n{out.stdout}\n{out.stderr}"
        )
        rows = report_file.read_text(encoding="utf-8").splitlines()

    analysed: dict[str, int] = {}
    for row in rows:
        parts = row.split()
        if len(parts) != 5 or parts[4] == "total":
            continue
        if not parts[0].isdigit():
            # A future report shape should be a diagnosis, not a ValueError from
            # inside a gate everything else now leans on.
            continue
        analysed[parts[4].rsplit(".", 1)[-1]] = int(parts[0])

    unexamined = sorted(name for name in tracked if analysed.get(name, 0) == 0 and name in analysed)
    missing = sorted(name for name in tracked if name not in analysed)
    assert not unexamined, (
        "mypy counted these modules as source files but analysed zero lines in them, "
        "which is what `ignore_errors` does -- they are checked for nothing while "
        f"every count-based gate stays green: {unexamined}"
    )
    assert not missing, f"mypy never saw these tracked modules at all: {missing}"


def test_both_ruff_pins_name_one_version() -> None:
    """Two ruffs formatting one repository is a `commit` / `check` split.

    `.pre-commit-config.yaml` pinned ruff `v0.11.12` while the dev group asked for
    `ruff>=0.11`, which resolved to `0.16.6`. That is not a hypothetical drift: the
    older ruff raised `UP038` on `isinstance(node, (ast.Module, ast.ClassDef, ...))`
    in this repository's own test file, and the newer one does not have the rule.
    A contributor with hooks installed could not commit code that CI accepts.

    So both pins are exact and this holds them equal, which means bumping one alone
    fails here instead of drifting quietly. Ported from partspec's
    `tests/test_lint_config.py`, which exists for the same defect.

    Parsed with a regex rather than YAML: pyyaml is not a dependency of this
    project, and adding one to read four lines would be the heavier fix.
    """
    dev = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["dependency-groups"]["dev"]
    pinned = [d for d in dev if d.startswith("ruff")]
    assert len(pinned) == 1, f"expected one ruff pin in the dev group, got {pinned}"
    assert pinned[0].startswith("ruff=="), f"the pin must be exact `==`, not {pinned[0]!r}"
    assert "*" not in pinned[0], f"the pin must be exact, not {pinned[0]!r}"

    # The RESOLVED version, not the declared one. A declared `ruff==0.16.6` can still
    # run a different ruff: `[tool.uv] override-dependencies = ["ruff==0.14.0"]`
    # resolves to 0.14.0 with every gate green, measured. `uv.lock` is what `uv run`
    # actually installs, so it is the only version worth comparing against.
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    resolved = [pkg["version"] for pkg in lock["package"] if pkg["name"] == "ruff"]
    assert len(resolved) == 1, f"expected one ruff in uv.lock, got {resolved}"
    running = resolved[0]
    assert pinned[0] == f"ruff=={running}", (
        f"the dev group declares {pinned[0]!r} but `uv.lock` resolves ruff {running}"
    )

    # Read line-wise at the repo item's key indent, rather than flattening the file
    # and pattern-matching across it. Flattening was defeated twice: once by a
    # comment reading `ruff-pre-commit rev: v0.16.6`, and once by a folded-scalar
    # hook `name:` containing the same words while the real `rev:` named another
    # version. Both worked because a flattened document has no structure left to
    # anchor on.
    #
    # A block scalar's continuation must be indented deeper than its own key, so it
    # cannot masquerade as a four-space `rev:` at repo-item level. That closes the
    # class rather than the two instances, and fixes a false positive too: a second
    # legitimate ruff-pre-commit block at the same rev used to read as a mismatch.
    # pyyaml would also close it; it is not a dependency here and this is a dozen
    # lines, so it stays out -- but the reason is the size of the fix, not that a
    # regex is adequate for YAML.
    revs = []
    in_ruff_repo = False
    for line in (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8").splitlines():
        bare = line.split("#", 1)[0].rstrip()
        if re.match(r"^  - repo:", bare):
            in_ruff_repo = "ruff-pre-commit" in bare
            continue
        if in_ruff_repo:
            found = re.match(r"^    rev:\s*v?(\S+)$", bare)
            if found:
                revs.append(found.group(1))
    assert revs, "could not find the ruff-pre-commit rev"
    # `set(...)`, because two legitimate ruff-pre-commit blocks at the same rev are
    # not a mismatch. The line-wise rewrite changed how revs are collected and left
    # this comparison alone, so the false positive it was credited with fixing
    # survived it -- and the failure message read "pins ['0.16.6', '0.16.6'] but
    # installs 0.16.6", stating the versions match while failing on them.
    assert set(revs) == {running}, (
        f"pre-commit pins {sorted(set(revs))} but `uv run` installs ruff {running}"
    )


def _windows_clean_body() -> str:
    """The body of the `[windows]`-attributed `clean` recipe, as written."""
    lines = JUSTFILE.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if line.strip() != "[windows]":
            continue
        if i + 1 >= len(lines) or not re.match(r"^@?clean(\s|:)", lines[i + 1]):
            continue
        body = []
        for below in lines[i + 2 :]:
            if below.strip() and not below.startswith((" ", "\t")):
                break
            body.append(below)
        return "\n".join(body).strip()
    raise AssertionError("no `[windows]` clean recipe found in the justfile")


def test_the_windows_clean_body_contains_no_dollar_sign() -> None:
    """`just` runs recipe bodies through `sh -u`, including on Windows.

    So a `$` in a PowerShell body is expanded by `sh` before PowerShell sees it.
    That happened three times in this one recipe: `$_` in a `ForEach-Object` block,
    which made `clean` delete nothing while exiting `0`, and `$ErrorActionPreference`
    twice, which made it die at `unbound variable`, exit 127.

    Each was found by a Windows CI round-trip. The rule is written above the recipe;
    this makes it local and instant, because a fourth would otherwise cost the same
    round-trip. `-ErrorAction Stop` on the cmdlet does the preference variable's job
    with no sigil, so the rule costs nothing to keep.
    """
    body = _windows_clean_body()
    assert "$" not in body, (
        "the `[windows]` clean body contains a `$`, which `sh` will expand before "
        f"PowerShell sees it -- use a cmdlet parameter instead:\n  {body}"
    )
    assert "-ErrorAction Stop" in body, (
        "the `[windows]` clean body must fail loudly on a real error. Without "
        "`-ErrorAction Stop`, `Remove-Item` raises a NON-terminating error, the "
        "`__pycache__` sweep runs after it and succeeds, and `just clean` exits 0 "
        "having removed nothing -- measured, with `.venv` held open"
    )
