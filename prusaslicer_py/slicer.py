import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SliceResult:
    """What a completed slice established.

    Returned by :meth:`PrusaSlicer.slice_model`. Every field describes
    something that was observed after the engine exited, not something that was
    assumed because it did not complain.

    :param output_path: Where the G-code was written.
    :param size_bytes: Size of that file on disk. Always greater than zero --
                       an empty output is raised, not returned.
    :param returncode: The engine's exit status.
    :param stdout: The engine's standard output.
    :param stderr: The engine's standard error, including any warnings it
                   emitted while still exiting successfully.
    """

    output_path: Path
    size_bytes: int
    returncode: int
    stdout: str
    stderr: str


class SliceOutputError(RuntimeError):
    """The engine reported success but did not produce the G-code.

    PrusaSlicer can exit 0 and write nothing: a destination it cannot write to,
    an option that silently no-ops, an empty plate. Without this, every one of
    those reads to the caller exactly like a successful slice.

    Carries the engine's own output, which is usually the only explanation
    available for why nothing was produced.
    """

    def __init__(
        self,
        message: str,
        *,
        output_path: Path,
        returncode: int,
        stdout: str,
        stderr: str,
    ) -> None:
        super().__init__(message)
        self.output_path = output_path
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class PrusaSlicer:
    def __init__(self, slicer_path: str | None = None):
        """
        Initializes the PrusaSlicer wrapper.

        :param slicer_path: Path to the PrusaSlicer CLI executable.
                            If None, the method will attempt to locate it in the system PATH.
        """
        self.slicer_path = slicer_path or self._find_executable()

    @staticmethod
    def _find_executable() -> str:
        """
        Finds the PrusaSlicer executable in the system PATH.

        :return: Path to the executable.
        :raises FileNotFoundError: If the executable is not found.
        """
        exec_name = "prusa-slicer-console.exe" if os.name == "nt" else "prusa-slicer"
        slicer_path = shutil.which(exec_name)
        if not slicer_path:
            raise FileNotFoundError(
                f"Could not find {exec_name}. Ensure PrusaSlicer is installed and added to PATH."
            )
        return slicer_path

    def check_version(self) -> str:
        """
        Checks the version of PrusaSlicer.

        :return: The version string.
        :raises RuntimeError: If the CLI command fails.
        """
        try:
            result = subprocess.run(
                [self.slicer_path, "--version"],
                check=True,
                stdout=subprocess.PIPE,
                text=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to get version: {e}") from e

    def slice_model(
        self,
        stl_path: str,
        gcode_output: str,
        loglevel: str | None = None,
        additional_args: dict[str, str] | None = None,
    ) -> SliceResult:
        """
        Slices a 3D model using PrusaSlicer.

        Returning normally is a guarantee, not an absence of complaint: the
        G-code file exists and is non-empty. The engine exiting 0 is not
        evidence of either, so both are checked before this returns.

        Note the guarantee stops short of "this run wrote it": a stale file
        left by an earlier run at the same destination cannot be told apart
        from a fresh one without deleting the destination first. See
        docs/DECISIONS.md D5.

        :param stl_path: Path to the input STL file.
        :param gcode_output: Path to the output G-code file.
        :param loglevel: Log severity level (e.g., "info", "warn", "error").
        :param additional_args: Additional CLI arguments as a dictionary.
        :return: A :class:`SliceResult` describing the file that was produced
                 and carrying the engine's stdout and stderr.
        :raises FileNotFoundError: If the input STL does not exist.
        :raises RuntimeError: If the engine exits non-zero.
        :raises SliceOutputError: If the engine exits zero without producing
                                  the G-code. This is a subclass of
                                  RuntimeError, so callers that already treat
                                  a failed slice as RuntimeError keep working.
        """
        if not Path(stl_path).is_file():
            raise FileNotFoundError(f"STL file not found: {stl_path}")

        output = Path(gcode_output)
        command = [self.slicer_path, "--export-gcode", stl_path, "-o", gcode_output]

        if loglevel:
            command.extend(["--loglevel", loglevel])

        if additional_args:
            for key, value in additional_args.items():
                command.append(f"--{key}")
                if value:
                    command.append(str(value))

        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Slicing failed: {e}\n{e.stderr or ''}".rstrip()) from e

        stdout = completed.stdout or ""
        stderr = completed.stderr or ""

        def _no_output(reason: str) -> SliceOutputError:
            return SliceOutputError(
                f"PrusaSlicer exited 0 but {reason}: {output}",
                output_path=output,
                returncode=completed.returncode,
                stdout=stdout,
                stderr=stderr,
            )

        if not output.is_file():
            raise _no_output("wrote no G-code to")
        stat = output.stat()
        if stat.st_size == 0:
            raise _no_output("wrote an empty G-code file to")

        return SliceResult(
            output_path=output,
            size_bytes=stat.st_size,
            returncode=completed.returncode,
            stdout=stdout,
            stderr=stderr,
        )

    def generate_help(self, mode: str = "fff") -> str:
        """
        Generates help text for the PrusaSlicer CLI.

        :param mode: Help mode ('fff' or 'sla').
        :return: The help text.
        :raises RuntimeError: If the CLI command fails.
        """
        if mode not in ("fff", "sla"):
            raise ValueError("Invalid mode. Choose 'fff' or 'sla'.")
        try:
            result = subprocess.run(
                [self.slicer_path, f"--help-{mode}"],
                check=True,
                stdout=subprocess.PIPE,
                text=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to generate help: {e}") from e

    def get_example_shapes(self) -> list[str]:
        """
        Retrieves a list of example STL shapes available in the default shapes directory.

        :return: List of paths to example STL files.
        """
        shapes_dir = Path(self._find_executable()).parent / "resources" / "shapes"
        if not shapes_dir.exists():
            raise FileNotFoundError(f"Shapes directory not found at {shapes_dir}")

        # Get all STL files in the shapes directory
        stl_files = [file for file in shapes_dir.glob("*.stl")]
        return [str(file) for file in stl_files]
