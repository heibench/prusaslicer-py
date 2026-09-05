import subprocess
from unittest.mock import patch

import pytest

from prusaslicer_py.slicer import PrusaSlicer

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
