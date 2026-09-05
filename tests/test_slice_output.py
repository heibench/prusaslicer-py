"""slice_model must establish that the artifact exists before reporting it.

PrusaSlicer can exit 0 without writing the file it was asked for. These tests
stand in a fake engine -- one that controls exactly what lands on disk -- and
assert that each way of producing nothing is distinguishable from a real slice.

The engine is faked rather than run, because what is under test is the
driver's verification of the result -- with one exception at the bottom, where
the defect is in the decode subprocess itself performs. The end-to-end path
against a real PrusaSlicer lives in test_engine.py.
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from prusaslicer_py.slicer import (
    PrusaSlicer,
    SliceEngineError,
    SliceError,
    SliceOutputError,
    SliceResult,
)

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


def test_non_zero_exit_carries_the_same_fields_as_a_success(model, tmp_path):
    """The failure path is read the same way as the success path.

    Interpolating stderr into the message and dropping returncode and stdout
    would leave the caller parsing prose for facts the success path hands over
    as fields.
    """
    out = tmp_path / "out.gcode"
    slicer = PrusaSlicer(slicer_path=FAKE_SLICER_PATH)

    error = subprocess.CalledProcessError(
        2, "prusa-slicer", output="engine stdout", stderr="invalid option"
    )
    with (
        patch("subprocess.run", side_effect=error),
        pytest.raises(SliceEngineError) as excinfo,
    ):
        slicer.slice_model(str(model), str(out))

    assert excinfo.value.returncode == 2
    assert excinfo.value.stdout == "engine stdout"
    assert excinfo.value.stderr == "invalid option"
    assert excinfo.value.output_path == out


@pytest.mark.parametrize("failure", [SliceEngineError, SliceOutputError])
def test_both_failures_are_slice_errors_and_runtime_errors(failure):
    assert issubclass(failure, SliceError)
    assert issubclass(failure, RuntimeError)


def test_slice_output_error_is_a_runtime_error(model, tmp_path):
    """Existing callers catching RuntimeError keep working."""
    slicer = PrusaSlicer(slicer_path=FAKE_SLICER_PATH)
    with patch("subprocess.run", side_effect=fake_engine(None)), pytest.raises(RuntimeError):
        slicer.slice_model(str(model), str(tmp_path / "out.gcode"))


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="the stub engine is a shell script; the decode path itself is not OS-specific",
)
def test_undecodable_engine_output_does_not_fail_a_good_slice(model, tmp_path):
    """A byte the locale codec cannot decode must never become a verdict.

    Regression: capturing the engine's output with a strict decode raised
    UnicodeDecodeError *before* verification ran, so a slice that wrote perfect
    G-code and exited 0 was reported as a failure. Uses a real subprocess,
    because the defect is in the decode subprocess performs.
    """
    stub = tmp_path / "engine.sh"
    stub.write_bytes(
        b"#!/bin/sh\n"
        b'out=""; prev=""\n'
        b'for a in "$@"; do [ "$prev" = "-o" ] && out="$a"; prev="$a"; done\n'
        b'[ -n "$out" ] && printf \'G1 X0 Y0\\n\' > "$out"\n'
        # 0xb0 is a degree sign in latin-1 and an invalid start byte in UTF-8.
        b"printf 'nozzle 210\\260C\\n' >&2\n"
        b"exit 0\n"
    )
    stub.chmod(0o755)

    out = tmp_path / "out.gcode"
    result = PrusaSlicer(slicer_path=str(stub)).slice_model(str(model), str(out))

    assert result.size_bytes > 0
    assert out.read_text() == "G1 X0 Y0\n"
    # The undecodable byte survives as a replacement character, not an exception.
    assert "nozzle 210" in result.stderr
