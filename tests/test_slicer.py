import subprocess
from unittest.mock import patch

import pytest

from prusaslicer_py.slicer import EngineUnusableError, PrusaSlicer

#: A path that is never resolved -- these tests mock out the engine entirely,
#: so the constructor must not be allowed to go looking for a real one.
FAKE_SLICER_PATH = "path/to/prusa-slicer-console.exe"


@pytest.fixture
def slicer():
    # Explicit path: constructing bare PrusaSlicer() here would call
    # _find_executable() and error out on any machine without the engine
    # installed, turning an environment fault into a red test.
    return PrusaSlicer(slicer_path=FAKE_SLICER_PATH)


def test_find_executable(slicer):
    # Test if the executable can be found on Windows
    with patch(
        "shutil.which",
        return_value="C:\\Program Files\\PrusaSlicer\\prusa-slicer-console.exe",
    ):
        assert (
            slicer._find_executable() == "C:\\Program Files\\PrusaSlicer\\prusa-slicer-console.exe"
        )

    # Test if an exception is raised when executable is not found
    with patch("shutil.which", return_value=None), pytest.raises(FileNotFoundError):
        slicer._find_executable()


def test_check_version():
    slicer = PrusaSlicer(slicer_path=FAKE_SLICER_PATH)

    # Mock subprocess to simulate a successful version check
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "PrusaSlicer 2.6.1"
        version = slicer.check_version()
        assert version == "PrusaSlicer 2.6.1"

    # Simulate failure by raising subprocess.CalledProcessError instead of a generic Exception
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "command", output="Error getting version"
        )  # Simulating the subprocess error
        with pytest.raises(RuntimeError):
            slicer.check_version()


def fake_engine_run(*, returncode: int = 0, stdout: str = "help text", stderr: str = ""):
    """A subprocess.run stand-in for the --help probe."""

    def run(command, **kwargs):
        return subprocess.CompletedProcess(command, returncode, stdout=stdout, stderr=stderr)

    return run


def test_probe_returns_what_a_working_engine_answered():
    slicer = PrusaSlicer(slicer_path=FAKE_SLICER_PATH)

    with patch("subprocess.run", side_effect=fake_engine_run(stdout="Usage: ...")):
        probe = slicer.probe()

    assert probe.returncode == 0
    assert probe.stdout == "Usage: ..."
    assert probe.engine_kind == "path"
    assert probe.argv[-1] == "--help"


def test_probe_reports_an_engine_that_would_not_start():
    """The #33 case: discovery succeeded and the launcher then failed.

    `flatpak info` exits 0 for an app whose `flatpak run` cannot create its
    state directory, so the driver constructs and the engine never runs. The
    launcher's own complaint is the whole explanation, so it travels with the
    error rather than being dropped on the way past.
    """
    slicer = PrusaSlicer(slicer_path=FAKE_SLICER_PATH)
    complaint = "error: mkdirat(.var): Permission denied"

    with (
        patch("subprocess.run", side_effect=fake_engine_run(returncode=1, stderr=complaint)),
        pytest.raises(EngineUnusableError) as caught,
    ):
        slicer.probe()

    assert caught.value.returncode == 1
    assert caught.value.stderr == complaint
    assert caught.value.engine_kind == "path"


def test_probe_reports_an_engine_that_answered_nothing():
    """Exit 0 and silence is not a working engine, it is an engine that said nothing."""
    slicer = PrusaSlicer(slicer_path=FAKE_SLICER_PATH)

    with (
        patch("subprocess.run", side_effect=fake_engine_run(stdout="   \n")),
        pytest.raises(EngineUnusableError) as caught,
    ):
        slicer.probe()

    assert caught.value.returncode == 0


def test_probe_reports_a_launcher_that_cannot_be_executed():
    """No exit status exists here, so `returncode` is None rather than a stand-in."""
    slicer = PrusaSlicer(slicer_path=FAKE_SLICER_PATH)

    with (
        patch("subprocess.run", side_effect=PermissionError("Permission denied")),
        pytest.raises(EngineUnusableError) as caught,
    ):
        slicer.probe()

    assert caught.value.returncode is None
    assert isinstance(caught.value, RuntimeError)


def test_slice_model_rejects_a_missing_stl():
    """The engine is never invoked for an input that is not there.

    The rest of slice_model's contract -- that it establishes the G-code was
    actually produced -- is covered in test_slice_output.py.
    """
    slicer = PrusaSlicer(slicer_path=FAKE_SLICER_PATH)

    with patch("pathlib.Path.is_file", return_value=False), pytest.raises(FileNotFoundError):
        slicer.slice_model("model.stl", "output.gcode")


def test_generate_help():
    slicer = PrusaSlicer(slicer_path=FAKE_SLICER_PATH)

    # Mock subprocess to simulate help generation success
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "Help text for FFF"
        help_text = slicer.generate_help("fff")
        assert "Help text for FFF" in help_text

    # Test invalid mode
    with pytest.raises(ValueError):
        slicer.generate_help("invalid_mode")

    # Test help generation failure
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "command", output="Help command failed"
        )  # Simulating the subprocess error
        with pytest.raises(RuntimeError):
            slicer.generate_help("fff")


def test_shape_candidates_include_the_macos_app_bundle():
    """A macOS .app keeps resources in Contents/Resources, not beside the binary.

    Looking only beside the executable made `brew install --cask prusaslicer`
    fail with "Shapes directory not found" on a working install -- found by the
    Engine workflow, not by any local run.
    """
    slicer = PrusaSlicer.__new__(PrusaSlicer)
    slicer.engine_kind = "path"
    slicer.slicer_path = "/Applications/PrusaSlicer.app/Contents/MacOS/PrusaSlicer"
    # Compare path COMPONENTS, not strings: on Windows the same candidate is
    # spelled D:\Applications\...\Contents\Resources\shapes, and asserting the
    # POSIX spelling failed there for a list that was entirely correct.
    tails = {c.parts[-3:] for c in slicer._shape_dir_candidates()}
    assert ("Contents", "Resources", "shapes") in tails


def test_shape_candidates_cover_the_unix_prefix_layout():
    slicer = PrusaSlicer.__new__(PrusaSlicer)
    slicer.engine_kind = "path"
    slicer.slicer_path = "/usr/local/bin/prusa-slicer"
    tails = {c.parts[-3:] for c in slicer._shape_dir_candidates()}
    assert ("share", "PrusaSlicer", "shapes") in tails
