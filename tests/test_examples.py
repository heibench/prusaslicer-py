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
    these files (org 2.2). Without this the four-platform engine matrix would report
    a red test for a build that simply ships a different set.
    """
    slicer = resolve_engine()
    shapes = slicer.get_example_shapes()
    if not any("torus.stl" in shape for shape in shapes):
        environment_fault(
            f"this engine ships no torus.stl; the examples name it. Shapes found: {len(shapes)}."
        )


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.name)
def test_each_example_succeeds_against_a_real_engine(example: Path) -> None:
    """Exit 0, and the engine accepted every option the example passes.

    `--help-fff` is where these names come from; this is what notices when one of
    them stops being a real option, or was never one.
    """
    _require_the_shape_the_examples_name()
    done = subprocess.run(
        [sys.executable, str(example)],
        capture_output=True,
        text=True,
        timeout=600,
        cwd=ROOT,
    )
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

    What both examples share is a destination they must write. Copied into a tree
    whose `output/` is read-only, `slice_model` raises and the example has to say so
    in its exit status. Printing the engine's complaint and exiting 0 is
    indistinguishable from success to everything except a person reading the
    terminal.
    """
    _require_the_shape_the_examples_name()
    # The examples derive their output directory as `<script>/../output`, so a copy
    # one level down gets its own, and making it read-only makes the write fail.
    workspace = tmp_path / "examples"
    workspace.mkdir()
    copy = workspace / example.name
    copy.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
    blocked = tmp_path / "output"
    blocked.mkdir()
    blocked.chmod(0o500)
    try:
        done = subprocess.run(
            [sys.executable, str(copy)], capture_output=True, text=True, timeout=600
        )
    finally:
        blocked.chmod(0o700)

    assert done.returncode != 0, (
        f"{example.name} produced no G-code and exited 0; a smoke test cannot tell "
        f"that from success\n{done.stdout}\n{done.stderr}"
    )
    assert "No G-code produced" in done.stdout + done.stderr, (
        "the run failed for some reason other than the blocked write, so this test "
        f"is measuring the wrong thing:\n{done.stdout}\n{done.stderr}"
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
    broken = tmp_path / "broken_example.py"
    broken.write_text(text.replace(needle, '"layer_height"'), encoding="utf-8")

    done = subprocess.run(
        [sys.executable, str(broken)], capture_output=True, text=True, timeout=600, cwd=ROOT
    )
    assert done.returncode != 0, f"{done.stdout}\n{done.stderr}"
    assert "Unknown option" in done.stdout + done.stderr, (
        "the engine did not reject the underscore spelling; either it grew that "
        f"option or something translated it:\n{done.stdout}\n{done.stderr}"
    )
