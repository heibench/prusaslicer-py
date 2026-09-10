import subprocess
from unittest.mock import patch

import pytest

from prusaslicer_py.slicer import (
    EngineUnusableError,
    PrusaSlicer,
    VersionEngineError,
    VersionUnreadableError,
)

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


#: What the native Windows console build prints. The version is on the SECOND
#: line, under a startup message from the graphics stack -- so the first line is
#: not the version, and taking it returned that preamble as one (#34).
WINDOWS_HELP = (
    "System OpenGL library successfully released\n"
    "PrusaSlicer-2.9.6 based on Slic3r (with GUI support)\n"
    "https://github.com/prusa3d/PrusaSlicer\n"
    "\n"
    "Usage: prusa-slicer [ INPUT ] [ OPTIONS ]\n"
)

#: The Linux Flatpak, which prints no preamble at all. This is the shape the old
#: code was measured against, and the reason neither project found the defect on
#: the host it was written on.
FLATPAK_HELP = (
    "PrusaSlicer-2.9.6+flathub.org based on Slic3r (with GUI support)\n"
    "https://github.com/prusa3d/PrusaSlicer\n"
)


def fake_help(stdout: str, *, returncode: int = 0, stderr: str = ""):
    """A subprocess.run stand-in that answers --help with exactly `stdout`."""

    def run(command, **kwargs):
        return subprocess.CompletedProcess(command, returncode, stdout=stdout, stderr=stderr)

    return run


def test_check_version_reads_the_banner_not_the_first_line():
    """The defect, directly: a preamble above the banner must not be the answer."""
    slicer = PrusaSlicer(slicer_path=FAKE_SLICER_PATH)

    with patch("subprocess.run", side_effect=fake_help(WINDOWS_HELP)):
        banner = slicer.check_version()

    assert banner == "PrusaSlicer-2.9.6 based on Slic3r (with GUI support)"
    assert "OpenGL" not in banner


def test_check_version_still_returns_the_line_it_always_returned():
    """The no-preamble build is what 0.2.0 was measured against; it is unchanged.

    This is the whole reason the signature did not need to move. On every build
    that prints no preamble, the first line IS the banner, so what callers get
    back is byte-for-byte what they got from 0.2.0 -- including the README's
    `print(slicer.check_version())`.
    """
    slicer = PrusaSlicer(slicer_path=FAKE_SLICER_PATH)

    with patch("subprocess.run", side_effect=fake_help(FLATPAK_HELP)):
        banner = slicer.check_version()

    assert banner == "PrusaSlicer-2.9.6+flathub.org based on Slic3r (with GUI support)"
    assert isinstance(banner, str)


def test_version_info_takes_the_banner_apart():
    """The additive long form. `check_version` is exactly its `banner`."""
    slicer = PrusaSlicer(slicer_path=FAKE_SLICER_PATH)

    with patch("subprocess.run", side_effect=fake_help(WINDOWS_HELP)):
        result = slicer.version_info()
    with patch("subprocess.run", side_effect=fake_help(WINDOWS_HELP)):
        assert slicer.check_version() == result.banner

    assert result.version == "2.9.6"
    assert result.banner == "PrusaSlicer-2.9.6 based on Slic3r (with GUI support)"
    assert result.returncode == 0
    assert result.stdout == WINDOWS_HELP


def test_the_banner_needs_a_digit_not_just_the_product_name():
    """`PrusaSlicer-Py` is a name; `PrusaSlicer-2.9.6` is a version.

    The digit in the pattern is the only thing separating them, and without a
    build that greets with the former there is nothing to notice if it goes.
    Dropping `\\d` makes this return `PrusaSlicer-Py 0.2.0 starting` -- a line
    that is not a version, from the function whose defect was returning a line
    that is not a version.
    """
    slicer = PrusaSlicer(slicer_path=FAKE_SLICER_PATH)
    greeting = (
        "PrusaSlicer-Py 0.2.0 starting\nPrusaSlicer-2.9.6 based on Slic3r (with GUI support)\n"
    )

    with patch("subprocess.run", side_effect=fake_help(greeting)):
        result = slicer.version_info()

    assert result.version == "2.9.6"
    assert result.banner == "PrusaSlicer-2.9.6 based on Slic3r (with GUI support)"


def test_the_banner_is_found_on_stderr_too():
    """A startup banner is exactly the kind of thing a build sends to stderr.

    Both streams are already captured, so answering "could not tell" while
    holding the answer in a field would be a self-inflicted third outcome.
    """
    slicer = PrusaSlicer(slicer_path=FAKE_SLICER_PATH)

    with patch(
        "subprocess.run",
        side_effect=fake_help("Usage: prusa-slicer\n", stderr=FLATPAK_HELP),
    ):
        result = slicer.version_info()

    assert result.version == "2.9.6+flathub.org"


def test_an_indented_line_is_not_a_banner():
    """The banner is printed at column 0. Anything indented is help text."""
    slicer = PrusaSlicer(slicer_path=FAKE_SLICER_PATH)

    with (
        patch(
            "subprocess.run",
            side_effect=fake_help("Options:\n    PrusaSlicer-2.9.6 is the build\n"),
        ),
        pytest.raises(VersionUnreadableError),
    ):
        slicer.check_version()


def test_check_version_refuses_output_that_states_no_version():
    """The third outcome. There is no line here to hand back, so nothing is.

    `-> str` had no way to say this, which is why the preamble came back as a
    version instead: the only thing the signature allowed was a string.
    """
    slicer = PrusaSlicer(slicer_path=FAKE_SLICER_PATH)
    noise = "System OpenGL library successfully released\nUsage: prusa-slicer\n"

    with (
        patch("subprocess.run", side_effect=fake_help(noise)),
        pytest.raises(VersionUnreadableError) as caught,
    ):
        slicer.check_version()

    # The engine's own output reaches the caller, because it is the only
    # explanation of why this could not be read.
    assert caught.value.stdout == noise
    assert caught.value.returncode == 0
    assert isinstance(caught.value, RuntimeError)


def test_check_version_refuses_empty_output():
    slicer = PrusaSlicer(slicer_path=FAKE_SLICER_PATH)

    with (
        patch("subprocess.run", side_effect=fake_help("")),
        pytest.raises(VersionUnreadableError),
    ):
        slicer.check_version()


def test_check_version_reports_an_engine_that_exited_non_zero():
    """Distinct from "could not tell": the engine answered, and answered badly."""
    slicer = PrusaSlicer(slicer_path=FAKE_SLICER_PATH)

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "command", output="Unknown option", stderr="boom"
        )
        with pytest.raises(VersionEngineError) as caught:
            slicer.check_version()

    assert caught.value.returncode == 1
    assert caught.value.stderr == "boom"
    assert isinstance(caught.value, RuntimeError)


def test_an_engine_that_is_not_there_is_a_version_error_not_an_os_error(tmp_path):
    """The fourth outcome that used to walk past `except VersionError`.

    No mock: a real path that does not exist, and a real one that is not
    executable. `subprocess.run` raises FileNotFoundError and PermissionError
    respectively, and catching only CalledProcessError let both escape -- under
    a docstring promising three outcomes and a README recommending
    `except VersionError`.
    """
    not_there = tmp_path / "not-here" / "prusa-slicer"
    not_executable = tmp_path / "prusa-slicer"
    not_executable.write_text("not a program\n")

    for path in (not_there, not_executable):
        with pytest.raises(VersionEngineError) as caught:
            PrusaSlicer(slicer_path=str(path)).check_version()
        assert caught.value.returncode is None, "there was never an exit status to report"
        assert isinstance(caught.value, RuntimeError)


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
