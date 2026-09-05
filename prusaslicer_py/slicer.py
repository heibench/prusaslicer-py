import os
import shutil
import subprocess
from pathlib import Path


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
    ) -> None:
        """
        Slices a 3D model using PrusaSlicer.

        :param stl_path: Path to the input STL file.
        :param gcode_output: Path to the output G-code file.
        :param loglevel: Log severity level (e.g., "info", "warn", "error").
        :param additional_args: Additional CLI arguments as a dictionary.
        :raises RuntimeError: If the slicing process fails.
        """
        if not Path(stl_path).is_file():
            raise FileNotFoundError(f"STL file not found: {stl_path}")

        command = [self.slicer_path, "--export-gcode", stl_path, "-o", gcode_output]

        if loglevel:
            command.extend(["--loglevel", loglevel])

        if additional_args:
            for key, value in additional_args.items():
                command.append(f"--{key}")
                if value:
                    command.append(str(value))

        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Slicing failed: {e}") from e

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
