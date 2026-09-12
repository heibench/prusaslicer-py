"""The examples are run, not read.

An example is a status claim: it says "this is how the library works". Reading one
establishes that it parses. Running it establishes that the engine accepted every
option it passes -- which is the half that rotted, because `additional_args` spells
keys verbatim and three of this repo's four demo keys were not options at all.

Both examples are run as real subprocesses, because the exit code is the thing that
was wrong. `torus_example_attempt.py` printed "No G-code produced" and exited 0: a
person reading the output saw the failure and a smoke test reading `$?` did not
(prusaslicer-py#36). Asserting the exit status inside the process would not have
caught that.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import environment_fault, resolve_engine

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = sorted((ROOT / "examples").glob("*.py"))


def test_there_are_examples_to_run() -> None:
    """The control. Without it, an empty glob makes every test below vacuously green."""
    assert EXAMPLES, "no examples found, so parametrising over them proves nothing"


def _require_the_shape_the_examples_name() -> None:
    """Both examples look for `torus.stl` by name, and a build need not ship it.

    An engine whose example shapes differ is an environment fact, not a defect in
    these files (org 2.2), and it is named as one rather than surfacing as an
    assertion about the example's own correctness.

    It does NOT make the engine matrix green: `engine.yml` sets
    `PRUSASLICER_PY_REQUIRE_ENGINE` for every job, so `environment_fault` fails there
    rather than skipping -- deliberately, because that matrix asserts a usable engine
    is present and one without the shapes these examples need is not the engine it
    is asserting. What this changes is the REASON reported: "this engine ships no
    torus.stl", not "the example is broken".
    """
    slicer = resolve_engine()
    shapes = slicer.get_example_shapes()
    if not any("torus.stl" in shape for shape in shapes):
        environment_fault(
            f"this engine ships no torus.stl; the examples name it. Shapes found: {len(shapes)}."
        )


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.name)
def test_each_example_succeeds_against_a_real_engine(example: Path, tmp_path: Path) -> None:
    """Exit 0, and the engine accepted every option the example passes.

    `--help-fff` is where these names come from; this is what notices when one of
    them stops being a real option, or was never one.
    """
    _require_the_shape_the_examples_name()
    # A copy, not the file in place: running the real one writes into the developer's
    # own `<repo>/output/`, which is gitignored but still theirs.
    workspace = tmp_path / "examples"
    workspace.mkdir()
    copy = workspace / example.name
    copy.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
    done = subprocess.run([sys.executable, str(copy)], capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, (
        f"{example.name} exited {done.returncode}\n{done.stdout}\n{done.stderr}"
    )
    assert "Unknown option" not in done.stdout + done.stderr, (
        f"{example.name} passed an option this engine does not have:\n{done.stderr}"
    )


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.name)
def test_an_example_that_cannot_produce_its_output_exits_non_zero(
    example: Path, tmp_path: Path
) -> None:
    """The property the record is about, for EVERY example rather than one of them.

    An earlier version broke one option name, which only `torus_example_attempt.py`
    passes -- so `basic_slicing.py` had no way to fail this, and it kept the exit-0
    swallow for a whole review round with the suite green.

    What both examples share is a destination they must write. A **directory** in its
    place blocks it on every platform: `chmod(0o500)` was the first attempt and is
    POSIX-only -- Windows ignores the mode bits, and ignores the read-only attribute on
    directories entirely -- so on the Windows engine job the write would have succeeded,
    the example exited 0, and this test would have reported the #36 defect on a platform
    where the example is fine. A platform fact asserted as a verdict about the code is
    org contract 2.2, which is the thing this file is about.

    What the engine actually does is write `torus.gcode` *inside* that directory, so
    nothing lands at the path it was given. `slice_model`'s `if not output.is_file()`
    is what catches it, and that is false for a directory everywhere -- a stronger
    invariant than "the write fails", which is what an earlier version of this
    docstring claimed. Where a platform's engine errors instead, the same
    `No G-code produced` assertion below still matches.
    """
    _require_the_shape_the_examples_name()
    # The examples derive their output directory as `<script>/../output`, so a copy one
    # level down gets its own. Both filenames are blocked because the test does not
    # know which one this example writes, and asserting that would duplicate the
    # example's own choice here.
    workspace = tmp_path / "examples"
    workspace.mkdir()
    copy = workspace / example.name
    copy.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
    blocked = tmp_path / "output"
    blocked.mkdir()
    for name in ("torus.gcode", "torus_defaults.gcode"):
        (blocked / name).mkdir()

    done = subprocess.run([sys.executable, str(copy)], capture_output=True, text=True, timeout=600)

    assert done.returncode != 0, (
        f"{example.name} produced no G-code and exited 0; a smoke test cannot tell "
        f"that from success\n{done.stdout}\n{done.stderr}"
    )
    assert "No G-code produced" in done.stdout + done.stderr, (
        "the run failed for some reason other than the blocked destination, so this "
        f"test is measuring the wrong thing:\n{done.stdout}\n{done.stderr}"
    )


def test_a_misspelled_option_is_rejected_rather_than_translated(tmp_path: Path) -> None:
    """`additional_args` spells keys verbatim, and the engine is the only authority.

    A copy with `layer-height` written the way PrusaSlicer's own config spells it --
    `layer_height` -- must fail. If this ever passes, something started translating,
    and a name the engine does not have has become indistinguishable from one it does.
    """
    _require_the_shape_the_examples_name()
    source = ROOT / "examples" / "torus_example_attempt.py"
    text = source.read_text(encoding="utf-8")
    needle = '"layer-height"'
    assert needle in text, (
        f"{source.name} no longer passes {needle}. That is a change to this repo, not "
        "an environment fault -- retarget this test rather than skipping it."
    )
    workspace = tmp_path / "examples"
    workspace.mkdir()
    broken = workspace / "broken_example.py"
    broken.write_text(text.replace(needle, '"layer_height"'), encoding="utf-8")

    done = subprocess.run(
        [sys.executable, str(broken)], capture_output=True, text=True, timeout=600
    )
    assert done.returncode != 0, f"{done.stdout}\n{done.stderr}"
    assert "Unknown option" in done.stdout + done.stderr, (
        "the engine did not reject the underscore spelling; either it grew that "
        f"option or something translated it:\n{done.stdout}\n{done.stderr}"
    )


def test_every_demo_option_actually_changes_the_output(tmp_path: Path) -> None:
    """The options example must differ from the defaults example, key by key.

    Two of the four demo values were once `20%` and `60` -- exactly the engine's
    defaults for `fill-density` and `perimeter-speed` -- so the example demonstrated
    nothing for them, and a check that the value "came back" could not tell that from
    the option never being passed at all. Setting one back to its default is a silent
    regression that no other test here notices.

    The two examples are run into a scratch tree and their footers compared. The
    `-` to `_` mapping below reads the engine's own footer spelling; it is not the
    transform D15 refuses, which is about SENDING an option name this driver invented.
    """
    _require_the_shape_the_examples_name()
    workspace = tmp_path / "examples"
    workspace.mkdir()
    for example in EXAMPLES:
        copy = workspace / example.name
        copy.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        done = subprocess.run(
            [sys.executable, str(copy)], capture_output=True, text=True, timeout=600
        )
        assert done.returncode == 0, f"{example.name}: {done.stdout}{done.stderr}"

    produced = sorted((tmp_path / "output").glob("*.gcode"))
    assert len(produced) == 2, f"expected one G-code per example, got {produced}"

    def footer(path: Path) -> dict[str, str]:
        return {
            key.strip("; ").strip(): value.strip()
            for key, _, value in (
                line.partition(" = ")
                for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
                if line.startswith("; ") and " = " in line
            )
        }

    source = (ROOT / "examples" / "torus_example_attempt.py").read_text(encoding="utf-8")
    authored = re.findall(r'^\s*"([a-z-]+)":\s*"([^"]+)"', source, re.MULTILINE)
    assert len(authored) == 4, f"expected four demo options, parsed {authored}"

    with_options = footer(tmp_path / "output" / "torus.gcode")
    defaults = footer(tmp_path / "output" / "torus_defaults.gcode")
    assert with_options and defaults, "no footer parsed from one of the two runs"

    same_as_default = [
        option
        for option, _ in authored
        if with_options.get(option.replace("-", "_")) == defaults.get(option.replace("-", "_"))
    ]
    assert same_as_default == [], (
        f"{same_as_default} are set to the engine's own default, so the example "
        "demonstrates nothing for them and 'the value came back' cannot be told "
        "from the option never being passed"
    )


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.name)
def test_an_example_that_cannot_find_its_shape_exits_non_zero(
    example: Path, tmp_path: Path
) -> None:
    """The second `SystemExit(1)` in each example, which nothing else covers.

    Each example has two: one for "the engine produced no G-code" and one for "the
    shape I need is not in this engine's examples". Only the first had a test, and
    turning the second into `SystemExit(0)` left the whole suite green -- while the
    pull request and a commit message both said "either example's `raise SystemExit(1)`"
    was verified, which was true of two of the four sites.

    Reaching it needs an engine that ships no `torus.stl`, which no engine here does,
    so the copy is prefixed with a patch making `get_example_shapes` return nothing.
    That is a stand-in for a build with a different shape set, not a claim that one
    exists.
    """
    _require_the_shape_the_examples_name()
    workspace = tmp_path / "examples"
    workspace.mkdir()
    patched = (
        "from prusaslicer_py import PrusaSlicer as _P\n_P.get_example_shapes = lambda self: []\n"
    ) + example.read_text(encoding="utf-8")
    copy = workspace / example.name
    copy.write_text(patched, encoding="utf-8")

    done = subprocess.run([sys.executable, str(copy)], capture_output=True, text=True, timeout=600)

    assert done.returncode != 0, (
        f"{example.name} could not find the shape it needs and exited 0\n"
        f"{done.stdout}\n{done.stderr}"
    )
    assert "not found in example shapes" in done.stdout + done.stderr, (
        "the run failed for some reason other than the missing shape, so this test is "
        f"measuring the wrong thing:\n{done.stdout}\n{done.stderr}"
    )
