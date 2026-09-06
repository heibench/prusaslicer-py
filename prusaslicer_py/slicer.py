import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

# Every subprocess.run below passes `errors="replace"`. That is not tidiness.
# The engine's output encoding is not ours to choose -- PrusaSlicer's own
# --help demonstrably contains a degree sign and a mu -- and a strict decode
# raises UnicodeDecodeError *before* the result can be verified, reporting
# failure for a slice that succeeded. The codec itself is left as Python's
# locale default, because no single choice is right on every platform; what
# matters is that a byte we cannot decode never becomes a verdict.


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


class SliceError(RuntimeError):
    """A slice that did not produce usable G-code.

    Carries the same four facts the success path returns on a
    :class:`SliceResult`, so a caller reads a failed slice the same way it
    reads a successful one instead of parsing prose out of a message. The
    engine's own output is usually the only explanation available.

    Subclasses ``RuntimeError``, which ``slice_model`` raised before this
    existed, so callers that already catch ``RuntimeError`` keep working.
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


class SliceEngineError(SliceError):
    """The engine exited non-zero. It said the slice failed, and why."""


class SliceOutputError(SliceError):
    """The engine reported success but did not produce the G-code.

    PrusaSlicer can exit 0 and write nothing: a destination it cannot write to,
    an option that silently no-ops, an empty plate. Without this, every one of
    those reads to the caller exactly like a successful slice.
    """


class PrusaSlicer:
    def __init__(self, slicer_path: str | None = None):
        """
        Initializes the PrusaSlicer wrapper.

        :param slicer_path: Path to the PrusaSlicer CLI executable.
                            If None, the method will attempt to locate it in the system PATH.
        """
        if slicer_path:
            self.slicer_path = str(slicer_path)
            self._argv: list[str] = [self.slicer_path]
            self.engine_kind = "path"
        else:
            try:
                self.slicer_path = self._find_executable()
                self._argv = [self.slicer_path]
                self.engine_kind = "path"
            except FileNotFoundError:
                flatpak = self._find_flatpak()
                if flatpak is None:
                    raise
                self._argv = flatpak
                self.slicer_path = f"flatpak:{self.FLATPAK_APP_ID}"
                self.engine_kind = "flatpak"

    #: The Flatpak application id PrusaSlicer publishes on Flathub.
    FLATPAK_APP_ID = "com.prusa3d.PrusaSlicer"

    @staticmethod
    def _exec_name() -> str:
        return "prusa-slicer-console.exe" if os.name == "nt" else "prusa-slicer"

    @classmethod
    def _find_flatpak(cls) -> list[str] | None:
        """The argv prefix for a Flathub PrusaSlicer, or None if absent.

        Flathub is how PrusaSlicer is normally installed on Linux, and a
        Flatpak is invisible to ``shutil.which`` -- the app is not on PATH and
        there is no binary to find. Discovery that only asks PATH reports "not
        installed" on a machine where the engine is sitting right there.

        ``--command=prusa-slicer`` bypasses the wrapper the Flatpak runs by
        default, which swallows CLI arguments and answers ``Unknown option``.
        """
        flatpak = shutil.which("flatpak")
        if not flatpak:
            return None
        probe = subprocess.run(
            [flatpak, "info", cls.FLATPAK_APP_ID],
            capture_output=True,
            text=True,
            errors="replace",
        )
        if probe.returncode != 0:
            return None
        return [flatpak, "run", f"--command={cls._exec_name()}", cls.FLATPAK_APP_ID]

    def _flatpak_roots(self) -> list[Path]:
        """Host locations where this Flatpak's own files are mounted."""
        return [
            Path("/var/lib/flatpak/app") / self.FLATPAK_APP_ID / "current/active/files",
            Path.home() / ".local/share/flatpak/app" / self.FLATPAK_APP_ID / "current/active/files",
        ]

    def _to_engine_path(self, path: str) -> str:
        """A path as the engine will see it.

        Inside the sandbox a Flatpak's own files are mounted at ``/app``, not at
        the host path they occupy on disk. A bundled example shape found at
        ``/var/lib/flatpak/.../files/share/...`` is therefore real to us and
        absent to the engine, which answers "No such file" for a model that
        plainly exists. Paths outside the app's own tree are the caller's files
        and pass through unchanged -- those are reachable via ``--filesystem``.
        """
        if self.engine_kind != "flatpak":
            return path
        resolved = Path(path).expanduser().resolve()
        for root in self._flatpak_roots():
            # resolve() follows `current/active`, which is a symlink into a
            # hashed deployment directory -- comparing against the unresolved
            # root never matches.
            try:
                real_root = root.resolve()
            except OSError:
                continue
            try:
                relative = resolved.relative_to(real_root)
            except ValueError:
                continue
            return str(Path("/app") / relative)
        return path

    def _sandbox_grants(self, *paths: str) -> list[str]:
        """The argv prefix, plus filesystem access for the paths involved.

        A Flatpak sees only its own sandbox. Slicing reads an STL and writes a
        G-code file, and both normally live outside it, so their directories
        have to be granted or the engine reports a file it cannot open --
        which would surface here as a slice that "failed" for a model that is
        perfectly fine.

        Only the directories actually involved are granted, not
        ``--filesystem=host``: this runs somebody else's build pipeline, and a
        driver should not hand the engine the whole filesystem to slice one
        part.
        """
        if self.engine_kind != "flatpak":
            return list(self._argv)
        directories = {str(Path(p).expanduser().resolve().parent) for p in paths}
        grants = [f"--filesystem={d}" for d in sorted(directories)]
        *head, app_id = self._argv
        return [*head, *grants, app_id]

    @classmethod
    def _find_executable(cls) -> str:
        """
        Finds the PrusaSlicer executable in the system PATH.

        :return: Path to the executable.
        :raises FileNotFoundError: If the executable is not found.
        """
        slicer_path = shutil.which(cls._exec_name())
        if not slicer_path:
            raise FileNotFoundError(
                f"Could not find {cls._exec_name()}. "
                "Ensure PrusaSlicer is installed and added to PATH."
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
                # PrusaSlicer's CLI has NO --version flag -- 2.9.6 answers
                # "Unknown option --version" and exits 1. The version is only
                # ever printed as the first line of --help:
                #   PrusaSlicer-2.9.6+flathub.org based on Slic3r (with GUI support)
                # This went unnoticed because the stub engines used in tests
                # answered --version; the real engine never has.
                [*self._argv, "--help"],
                check=True,
                stdout=subprocess.PIPE,
                text=True,
                errors="replace",
            )
            first_line = result.stdout.strip().splitlines()
            return first_line[0] if first_line else ""
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
        :raises SliceEngineError: If the engine exits non-zero.
        :raises SliceOutputError: If the engine exits zero without producing
                                  the G-code.

        Both failures are :class:`SliceError`, which is a ``RuntimeError``, and
        both carry ``output_path``, ``returncode``, ``stdout`` and ``stderr``
        as attributes -- the same four facts the success path returns.
        """
        if not Path(stl_path).is_file():
            raise FileNotFoundError(f"STL file not found: {stl_path}")

        output = Path(gcode_output)
        command = [
            *self._sandbox_grants(stl_path, gcode_output),
            "--export-gcode",
            self._to_engine_path(stl_path),
            "-o",
            gcode_output,
        ]

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
                errors="replace",
            )
        except subprocess.CalledProcessError as e:
            raise SliceEngineError(
                f"PrusaSlicer exited {e.returncode} slicing {stl_path}",
                output_path=output,
                returncode=e.returncode,
                stdout=e.stdout or "",
                stderr=e.stderr or "",
            ) from e

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

        :param mode: Help mode -- 'fff', 'sla', or 'all' for the top-level --help.
        :return: The help text.
        :raises RuntimeError: If the CLI command fails.
        """
        if mode not in ("fff", "sla", "all"):
            raise ValueError("Invalid mode. Choose 'fff', 'sla' or 'all'.")
        flag = "--help" if mode == "all" else f"--help-{mode}"
        try:
            result = subprocess.run(
                [*self._argv, flag],
                check=True,
                stdout=subprocess.PIPE,
                text=True,
                errors="replace",
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to generate help: {e}") from e

    def get_example_shapes(self) -> list[str]:
        """
        Retrieves a list of example STL shapes available in the default shapes directory.

        :return: List of paths to example STL files.
        """
        candidates = self._shape_dir_candidates()
        for shapes_dir in candidates:
            if shapes_dir.is_dir():
                return [str(f) for f in sorted(shapes_dir.glob("*.stl"))]
        listed = ", ".join(str(c) for c in candidates)
        raise FileNotFoundError(f"Shapes directory not found. Looked in: {listed}")

    def _shape_dir_candidates(self) -> list[Path]:
        """Where this engine's bundled example shapes might live.

        Derived from the engine that was actually resolved, not from a fresh
        discovery: re-running lookup here ignored an explicitly supplied
        ``slicer_path`` and raised FileNotFoundError even when the caller had
        handed us a perfectly good binary.

        A Flatpak keeps its resources under the app's ``files/share`` rather
        than beside the executable, and the executable is inside the sandbox
        where this process cannot reach it at all.
        """
        if self.engine_kind == "flatpak":
            return [r / "share/PrusaSlicer/shapes" for r in self._flatpak_roots()]
        binary_dir = Path(self.slicer_path).resolve().parent
        candidates = [
            # Windows installer, and a Linux tree that keeps resources beside
            # the binary.
            binary_dir / "resources" / "shapes",
            # Unix prefix layout: <prefix>/bin/prusa-slicer, resources under
            # <prefix>/share.
            binary_dir.parent / "share/PrusaSlicer/shapes",
        ]
        # macOS .app bundle: the binary sits in Contents/MacOS and the
        # resources in Contents/Resources -- capitalised, and NOT beside the
        # binary. Looking only beside it made `brew install --cask prusaslicer`
        # fail with "Shapes directory not found" on a perfectly good install.
        for parent in binary_dir.parents:
            if parent.suffix == ".app":
                candidates.append(parent / "Contents/Resources/shapes")
                candidates.append(parent / "Contents/Resources/PrusaSlicer/shapes")
                break
        return candidates
