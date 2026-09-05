"""slice_model must establish that the artifact exists before reporting it.

PrusaSlicer can exit 0 without writing the file it was asked for. These tests
stand in a fake engine -- one that controls exactly what lands on disk -- and
assert that each way of producing nothing is distinguishable from a real slice.

The engine is faked rather than run, because what is under test is the
driver's verification of the result, not subprocess itself. The end-to-end path
against a real PrusaSlicer lives in test_engine.py.
"""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from prusaslicer_py.slicer import PrusaSlicer, SliceOutputError, SliceResult

FAKE_SLICER_PATH = "path/to/prusa-slicer-console.exe"


def fake_engine(writes: bytes | None, *, returncode: int = 0, stderr: str = ""):
    """A subprocess.run stand-in that writes `writes` to the -o destination.

    Passing None makes it write nothing at all -- the engine exiting 0 having
    silently done nothing, which is the case this module exists for.
    """

    def run(command, **kwargs):
        if writes is not None:
            Path(command[command.index("-o") + 1]).write_bytes(writes)
        return subprocess.CompletedProcess(
            command, returncode, stdout="engine stdout", stderr=stderr
        )

    return run


@pytest.fixture
def model(tmp_path) -> Path:
    stl = tmp_path / "model.stl"
    stl.write_text("solid s\nendsolid s\n")
    return stl


def test_returns_a_result_describing_the_artifact(model, tmp_path):
    out = tmp_path / "out.gcode"
    slicer = PrusaSlicer(slicer_path=FAKE_SLICER_PATH)

    with patch("subprocess.run", side_effect=fake_engine(b"G1 X0 Y0\n", stderr="a warning")):
        result = slicer.slice_model(str(model), str(out))

    assert isinstance(result, SliceResult)
    assert result.output_path == out
    assert result.size_bytes == len(b"G1 X0 Y0\n")
    assert result.returncode == 0
    # The engine's diagnostics reach the caller rather than the parent's terminal.
    assert result.stdout == "engine stdout"
    assert result.stderr == "a warning"


def test_exit_zero_with_no_file_is_not_a_success(model, tmp_path):
    """The defect this module exists for: silence reading as success."""
    out = tmp_path / "out.gcode"
    slicer = PrusaSlicer(slicer_path=FAKE_SLICER_PATH)

    with (
        patch("subprocess.run", side_effect=fake_engine(None, stderr="nothing to slice")),
        pytest.raises(SliceOutputError) as excinfo,
    ):
        slicer.slice_model(str(model), str(out))

    assert not out.exists()
    # The engine's explanation is on the exception, not lost to the terminal.
    assert excinfo.value.stderr == "nothing to slice"
    assert excinfo.value.output_path == out
    assert excinfo.value.returncode == 0


def test_exit_zero_with_an_empty_file_is_not_a_success(model, tmp_path):
    out = tmp_path / "out.gcode"
    slicer = PrusaSlicer(slicer_path=FAKE_SLICER_PATH)

    with patch("subprocess.run", side_effect=fake_engine(b"")), pytest.raises(SliceOutputError):
        slicer.slice_model(str(model), str(out))


def test_overwriting_a_previous_output_is_a_success(model, tmp_path):
    """Rewriting the destination is the normal case and must still succeed.

    Note what is NOT asserted: that this run, rather than an earlier one, wrote
    the file. See docs/DECISIONS.md D5 -- mtime cannot carry that on the
    filesystems this runs on.
    """
    out = tmp_path / "out.gcode"
    out.write_bytes(b"old\n")
    slicer = PrusaSlicer(slicer_path=FAKE_SLICER_PATH)

    with patch("subprocess.run", side_effect=fake_engine(b"G1 X1 Y1 ; fresh\n")):
        result = slicer.slice_model(str(model), str(out))

    assert result.size_bytes == len(b"G1 X1 Y1 ; fresh\n")


def test_non_zero_exit_still_raises_with_the_engine_stderr(model, tmp_path):
    out = tmp_path / "out.gcode"
    slicer = PrusaSlicer(slicer_path=FAKE_SLICER_PATH)

    error = subprocess.CalledProcessError(1, "prusa-slicer", stderr="invalid option")
    with (
        patch("subprocess.run", side_effect=error),
        pytest.raises(RuntimeError, match="invalid option"),
    ):
        slicer.slice_model(str(model), str(out))


def test_slice_output_error_is_a_runtime_error(model, tmp_path):
    """Existing callers catching RuntimeError keep working."""
    slicer = PrusaSlicer(slicer_path=FAKE_SLICER_PATH)
    with patch("subprocess.run", side_effect=fake_engine(None)), pytest.raises(RuntimeError):
        slicer.slice_model(str(model), str(tmp_path / "out.gcode"))
