import os
import re
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


#: The version banner PrusaSlicer prints somewhere in `--help`:
#:
#:     PrusaSlicer-2.9.6+flathub.org based on Slic3r (with GUI support)
#:
#: Matched rather than counted to. Taking the first non-empty line instead
#: returned a startup preamble as the version on any build that prints one --
#: the native Windows console build opens with "System OpenGL library
#: successfully released" and states its version below it (#34).
#:
#: The trailing "based on Slic3r" is deliberately NOT required. It is present on
#: every build seen so far, but requiring it would turn a build that drops it
#: into "could not tell" for a version that is right there; a line beginning
#: `PrusaSlicer-` followed by a digit is already something no driver preamble
#: produces.
#:
#: The digit is the discriminator and it is load-bearing: without it this
#: matches `PrusaSlicer-Py`, which is this package's own name and not a version,
#: and any build that greets with it would answer that as its version.
#: `test_the_banner_needs_a_digit_not_just_the_product_name` is why that is a
#: claim rather than an assertion.
#:
#: Matched at column 0 against the raw line, not a stripped one. The banner is
#: the first thing the engine prints and is not indented; accepting a leading
#: run of whitespace only widens what can be mistaken for it.
_VERSION_BANNER = re.compile(r"^PrusaSlicer-(?P<version>\d\S*)")


def _find_version_banner(*streams: str) -> tuple[str, str] | None:
    """The (version, banner line) stated in the engine's output, or None.

    Both streams are searched, in the order given. `--help` goes to stdout on
    every build seen here, but the banner is a startup message and startup
    messages are exactly the kind of thing a build sends to stderr -- and the
    stream it lands on is not something this can establish from one host. A
    build that put it there would otherwise get "could not tell" while the
    answer sat in a field this call had already captured.

    None is the answer that has to exist. There is no line that can be handed
    back as a version when the output does not carry one, and inventing one is
    the defect this function was written to remove.
    """
    for stream in streams:
        for line in stream.splitlines():
            match = _VERSION_BANNER.match(line)
            if match:
                return match.group("version"), line.rstrip()
    return None


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


# One convention, two places it shows up. `EngineUnusableError.returncode` and
# `VersionError.returncode` are `int | None`, and the `None` is not a tidiness
# choice: when the engine could not be STARTED there is no exit status to
# report, and a stand-in integer there would be a number nothing measured. Both
# arrived at it independently -- `probe()` for a launcher that will not run
# (D14) and `version_info()` for a `slicer_path` that is not there or not
# executable (D13) -- which is the tell that it is the right answer rather than
# a local habit. A caller distinguishes "the engine ran and said no" from "the
# engine never ran" by testing `returncode is None`, in either family.


@dataclass(frozen=True)
class EngineProbe:
    """What asking the resolved engine to identify itself established.

    Returned by :meth:`PrusaSlicer.probe`. Constructing one is a claim that the
    engine started and answered ``--help``, which is a stronger claim than the
    one discovery makes: discovery establishes that an engine is *installed*.

    :param argv: Exactly what was run, including the ``flatpak run`` prefix
                 where there is one.
    :param engine_kind: ``"path"`` or ``"flatpak"``, as resolved.
    :param returncode: The engine's exit status. Always 0 -- anything else is
                       raised, not returned.
    :param stdout: What the engine answered.
    :param stderr: Anything it wrote alongside, including warnings from a
                   launcher that still worked.
    """

    argv: tuple[str, ...]
    engine_kind: str
    returncode: int
    stdout: str
    stderr: str


class EngineUnusableError(RuntimeError):
    """An engine was found on this machine and it did not run.

    The third state between "an engine is installed" and "the engine works",
    and it exists because discovery cannot see it. ``flatpak info`` exits 0 for
    an app whose launcher fails before the engine starts, so the driver
    constructs, and every consumer downstream believes it is talking to an
    engine (#33).

    **This is an environment fault, not a verdict**: it says the engine on this
    machine did not start, and nothing about whether any code is correct. It is
    a distinct type precisely so a consumer can tell the two apart -- a test
    suite skips on this where it would go red on a real defect.

    :param argv: What was run.
    :param engine_kind: ``"path"`` or ``"flatpak"``.
    :param returncode: The exit status, or ``None`` when the engine could not
                       be started at all and there never was one.
    :param stdout: What the engine managed to say.
    :param stderr: The launcher's own complaint, usually the whole explanation.
    """

    def __init__(
        self,
        message: str,
        *,
        argv: tuple[str, ...],
        engine_kind: str,
        returncode: int | None,
        stdout: str,
        stderr: str,
    ) -> None:
        super().__init__(message)
        self.argv = argv
        self.engine_kind = engine_kind
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@dataclass(frozen=True)
class VersionResult:
    """A version this engine actually stated about itself.

    Returned by :meth:`PrusaSlicer.version_info`. Constructing one is a claim
    that the engine's ``--help`` carried an identifiable version banner and
    that ``version`` was read out of it -- never that some line was there and
    looked plausible.

    :meth:`PrusaSlicer.check_version` returns this result's ``banner`` and
    nothing else, which is what it has always returned; this is the additive
    long form for a caller that wants the parts.

    :param version: The version as the engine spells it, with no leading
                    ``PrusaSlicer-``: ``2.9.6``, or ``2.9.6+flathub.org``.
    :param banner: The whole line ``version`` was read from, so a caller can
                   see the evidence rather than trust the extraction.
    :param returncode: The engine's exit status.
    :param stdout: The engine's standard output -- the full ``--help``.
    :param stderr: The engine's standard error.
    """

    version: str
    banner: str
    returncode: int
    stdout: str
    stderr: str


class VersionError(RuntimeError):
    """The engine did not state a version this call could read.

    Carries the same ``returncode``, ``stdout`` and ``stderr`` that
    :class:`VersionResult` carries on the success path, so a caller reads the
    failure the same way it reads the success instead of parsing prose out of
    a message.

    Subclasses ``RuntimeError``, which ``check_version`` raised before this
    existed, so callers that already catch ``RuntimeError`` keep working.

    ``returncode`` follows the same convention as
    :class:`EngineUnusableError`: ``None`` when the engine could not be started
    at all and there never was an exit status.
    """

    def __init__(
        self,
        message: str,
        *,
        returncode: int | None,
        stdout: str,
        stderr: str,
    ) -> None:
        super().__init__(message)
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class VersionEngineError(VersionError):
    """The engine did not answer when asked to identify itself.

    Either it could not be started -- a path that is not there, not executable,
    a launcher that fails -- or it started and exited non-zero. ``returncode``
    tells those apart: ``None`` means there was never an exit status.

    The starting case is here rather than left to escape as a bare ``OSError``
    because the docstring on ``check_version`` promises three outcomes, and a
    fourth one that walks past the caller's ``except VersionError`` makes that
    promise false. Reproduced: a ``slicer_path`` pointing at a file that does
    not exist raised ``FileNotFoundError``, and one pointing at a file that is
    not executable raised ``PermissionError``.
    """


class VersionUnreadableError(VersionError):
    """The engine ran, exited 0, and stated no version we could recognise.

    This is the *could not tell* outcome, and it exists because there was no
    channel for it: ``check_version`` returned a line of ``--help`` whatever
    that line was, so the only thing it could do with output it did not
    understand was hand back a line and call it a version. The channel is the
    exception rather than the return type -- ``check_version`` still returns
    ``str``, and a caller that never sees a version never sees a ``str``
    either. On a build that prints a startup preamble --
    ``System OpenGL library successfully released`` on the native Windows
    console build -- that line was the preamble, returned at exit 0 with no
    way for the caller to know (#34).
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

    def probe(self) -> EngineProbe:
        """Establish that the engine we resolved can actually start.

        Discovery answers "is an engine installed". This answers "did one
        answer us", and they are not the same question. ``flatpak info`` exits
        0 for an app whose launcher then fails before the engine runs -- an
        unwritable ``HOME`` is enough, and produces ``error: mkdirat(.var):
        Permission denied`` at exit 1 from a ``flatpak run`` whose ``flatpak
        info`` was perfectly happy (#33). Nothing in discovery sees that,
        because discovery never started the engine.

        ``--help`` is the probe because it is the only thing PrusaSlicer will
        answer: there is no ``--version`` flag, and 2.9.6 answers ``Unknown
        option --version`` and exits 1 (D9).

        A failure here is an **environment fault, not a verdict**: it says the
        engine on this machine did not run, and nothing about whether this code
        is correct. It is raised as its own type so a caller can branch on that
        distinction rather than read it out of a message.

        :return: An :class:`EngineProbe` carrying what the engine answered.
        :raises EngineUnusableError: The engine was found and did not run.
        """
        argv = [*self._argv, "--help"]
        try:
            result = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                errors="replace",
            )
        except OSError as e:
            # The launcher itself is unrunnable -- not on PATH after all, not
            # executable, a broken interpreter line. `flatpak` being absent is
            # already handled in discovery; a `slicer_path` handed to us is not.
            raise EngineUnusableError(
                f"could not start the engine at {self.slicer_path}: {e}.",
                argv=tuple(argv),
                engine_kind=self.engine_kind,
                returncode=None,
                stdout="",
                stderr="",
            ) from e

        stdout = result.stdout or ""
        stderr = result.stderr or ""
        if result.returncode != 0:
            raise EngineUnusableError(
                f"the engine at {self.slicer_path} exited {result.returncode} "
                "when asked for --help, so it did not start.",
                argv=tuple(argv),
                engine_kind=self.engine_kind,
                returncode=result.returncode,
                stdout=stdout,
                stderr=stderr,
            )
        if not stdout.strip():
            # Exit 0 and nothing said. The engine did not identify itself, and
            # treating that as a working engine is the same error one exit code
            # further along.
            raise EngineUnusableError(
                f"the engine at {self.slicer_path} exited 0 but answered "
                "--help with nothing, so it did not identify itself.",
                argv=tuple(argv),
                engine_kind=self.engine_kind,
                returncode=result.returncode,
                stdout=stdout,
                stderr=stderr,
            )
        return EngineProbe(
            argv=tuple(argv),
            engine_kind=self.engine_kind,
            returncode=result.returncode,
            stdout=stdout,
            stderr=stderr,
        )

    def check_version(self) -> str:
        """
        Asks the engine to identify itself, and returns the banner it stated.

        Returning normally is a guarantee: some line of the engine's output
        identified itself as a PrusaSlicer version banner, and this is that
        line -- ``PrusaSlicer-2.9.6+flathub.org based on Slic3r (with GUI
        support)``. It is what this returned before, on every build that does
        not print a preamble above its banner, so nothing that was reading it
        has to change.

        Three outcomes, and the third is not silent. The channel for it is the
        exception, not the return type: there is no line to return when the
        engine stated no version, so nothing is returned.

        :return: The version banner line.
        :raises VersionEngineError: If the engine could not be started, or
                                    started and exited non-zero.
        :raises VersionUnreadableError: If the engine exits 0 and its output
                                        carries no version banner.

        Both are :class:`VersionError`, which is a ``RuntimeError`` -- what
        this method raised before any of them existed.

        Use :meth:`version_info` for the version alone, or for the engine's
        output alongside it.
        """
        return self.version_info().banner

    def version_info(self) -> VersionResult:
        """
        The long form of :meth:`check_version`: the parts, not just the line.

        Additive. ``check_version`` is this method's ``banner``, and the
        failures are the same ones -- this exists because the version alone
        (``2.9.6+flathub.org``) and the engine's own output are both useful and
        neither is recoverable from the banner string by anyone who should have
        to parse it twice.

        :return: A :class:`VersionResult` carrying the version, the banner it
                 came from, and the engine's own output.
        :raises VersionEngineError: If the engine could not be started, or
                                    started and exited non-zero.
        :raises VersionUnreadableError: If the engine exits 0 and its output
                                        carries no version banner.
        """
        argv = [
            # PrusaSlicer's CLI has NO --version flag -- 2.9.6 answers
            # "Unknown option --version" and exits 1, so --help is the only
            # source (D9). This went unnoticed because the stub engines used
            # in tests answered --version; the real engine never has.
            *self._argv,
            "--help",
        ]
        try:
            result = subprocess.run(
                argv,
                check=True,
                capture_output=True,
                text=True,
                errors="replace",
            )
        except subprocess.CalledProcessError as e:
            raise VersionEngineError(
                f"PrusaSlicer exited {e.returncode} when asked for --help",
                returncode=e.returncode,
                stdout=e.stdout or "",
                stderr=e.stderr or "",
            ) from e
        except OSError as e:
            # The engine could not be started at all: a `slicer_path` that is
            # not there, or is not executable. Catching only
            # CalledProcessError left this escaping as a bare FileNotFoundError
            # or PermissionError, past every caller doing `except VersionError`
            # -- a fourth outcome under a docstring promising three.
            raise VersionEngineError(
                f"could not start the engine at {self.slicer_path}: {e}",
                returncode=None,
                stdout="",
                stderr="",
            ) from e

        stdout = result.stdout or ""
        stderr = result.stderr or ""
        found = _find_version_banner(stdout, stderr)
        if found is None:
            raise VersionUnreadableError(
                "PrusaSlicer exited 0 but stated no version in its --help output",
                returncode=result.returncode,
                stdout=stdout,
                stderr=stderr,
            )
        version, banner = found
        return VersionResult(
            version=version,
            banner=banner,
            returncode=result.returncode,
            stdout=stdout,
            stderr=stderr,
        )

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
