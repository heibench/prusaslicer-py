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


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.name)
def test_each_example_succeeds_against_a_real_engine(example: Path) -> None:
    """Exit 0, and the engine accepted every option the example passes.

    `--help-fff` is where these names come from; this is what notices when one of
    them stops being a real option, or was never one.
    """
    resolve_engine()
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


def test_an_example_that_cannot_slice_exits_non_zero(tmp_path: Path) -> None:
    """The property the record is about, exercised rather than asserted in prose.

    A copy of the example with one option name broken must fail loudly. Printing the
    engine's complaint and exiting 0 is what it used to do, and it is indistinguishable
    from success to everything except a human reading the terminal.
    """
    resolve_engine()
    source = ROOT / "examples" / "torus_example_attempt.py"
    broken = tmp_path / "broken_example.py"
    text = source.read_text(encoding="utf-8")
    needle = '"layer-height"'
    if needle not in text:
        environment_fault(f"{source.name} no longer passes {needle}, so this cannot break it.")
    broken.write_text(text.replace(needle, '"layer_height"'), encoding="utf-8")

    done = subprocess.run(
        [sys.executable, str(broken)], capture_output=True, text=True, timeout=600, cwd=ROOT
    )
    assert done.returncode != 0, (
        "an example that produced no G-code exited 0; a smoke test cannot tell that "
        f"from success\n{done.stdout}\n{done.stderr}"
    )
    assert "Unknown option" in done.stdout + done.stderr, (
        "the run failed for some reason other than the broken option name, so this "
        f"test is measuring the wrong thing:\n{done.stdout}\n{done.stderr}"
    )
