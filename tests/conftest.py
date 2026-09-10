"""Shared fixtures.

The distinction this file exists to enforce: *the engine on this machine is not
usable* is an environment fault, not a verdict on this code.  A test that needs
the engine and cannot get one must not report as a failure.

Two ways to not get one, and this file used to see only the first.  *Absent* is
a `PrusaSlicer()` that raises `FileNotFoundError`.  *Present and unusable* is a
`PrusaSlicer()` that constructs perfectly and then will not start: `flatpak
info` exits 0 for an app whose launcher fails before the engine runs, so
discovery is satisfied and the engine never answers.  That went through as a
working engine, and the environment fault was reported as three failing tests
(#33).
"""

import os
from typing import NoReturn

import pytest

from prusaslicer_py.slicer import EngineUnusableError, PrusaSlicer

#: Set to ANY value, the empty string included, to turn a missing engine into a
#: hard failure. Presence is the switch; see `engine_required`.
#: CI sets this on runners where the engine is expected to be installed, so
#: that "the engine is missing" cannot quietly masquerade as a green run.
REQUIRE_ENGINE_ENV = "PRUSASLICER_PY_REQUIRE_ENGINE"


def engine_required() -> bool:
    """Whether a missing engine must fail rather than skip.

    Membership, not truthiness. `.get()` made `PRUSASLICER_PY_REQUIRE_ENGINE=` --
    set to the empty string -- falsy, so the one switch whose job is "a missing
    engine must not read as green" could be turned off by setting it to nothing,
    and the run reported green with no engine.

    Extracted from the fixture so it can be tested without an engine-free machine;
    `test_engine.py` asserts the empty string still requires.
    """
    return REQUIRE_ENGINE_ENV in os.environ


def environment_fault(reason: str) -> NoReturn:
    """Skip -- or fail, if the caller said the engine should be here.

    One place, because there are now two ways to be without an engine and both
    have to be treated the same way.  Duplicating the skip-or-fail decision at
    each of them is how one of them ends up with only half of it: the *skip*
    half is the visible one, and dropping the *require* half leaves an
    engine-less runner with PRUSASLICER_PY_REQUIRE_ENGINE=1 green.
    """
    message = f"{reason} This is an environment fault, not a verdict on the code under test."
    if engine_required():
        pytest.fail(f"{REQUIRE_ENGINE_ENV} is set but: {message}")
    pytest.skip(message)


def resolve_engine() -> PrusaSlicer:
    """A PrusaSlicer bound to a *usable* real engine, or a skipped test.

    Requesting this fixture is how a test declares "I need the engine".  When
    there is no usable engine the test is skipped -- unless the caller has
    asserted one should be there via the environment variable above, in which
    case it is a hard failure rather than a silent skip.

    Both checks are here because both are environment faults and only one of
    them was being made.  Constructing the driver establishes that an engine is
    *installed*; `probe()` establishes that it *ran*.  `flatpak info` answers
    the first and says nothing about the second, so an engine whose launcher
    fails -- an unwritable HOME does it -- reached the tests as a working one
    and turned that fault into three red tests (#33).

    Resolution goes through PrusaSlicer itself rather than repeating the
    executable-name choice here.  A second copy of that logic in the test suite
    would drift from the one in the driver, and the tests would then be
    checking for an engine the driver would not have used.  The same reasoning
    is why the probe is the driver's and not a `subprocess.run` written here.
    """
    try:
        slicer = PrusaSlicer()
    except FileNotFoundError as e:
        environment_fault(str(e))
    try:
        slicer.probe()
    except EngineUnusableError as e:
        # The launcher's own complaint, not just that there was one. It is
        # usually the entire explanation -- `error: Extension
        # org.freedesktop.Platform.GL.default has invalid merge-dirs` names
        # what to fix, where "it did not start" names only that something is
        # wrong. `EngineUnusableError` carries the streams as fields precisely
        # so this does not have to be recovered from prose, and the one
        # consumer in this repository dropping them would make that pointless.
        complaint = (e.stderr.strip() or e.stdout.strip()).rstrip(".")
        environment_fault(f"{e} The engine said: {complaint}." if complaint else str(e))
    return slicer


@pytest.fixture
def engine() -> PrusaSlicer:
    """The fixture is this one call, deliberately.

    Reaching into a fixture to test it needs `__wrapped__`, which is untyped
    and which mypy rejects. Keeping the fixture a single call to a plain
    function means the test exercises the real code path instead of a private
    attribute.

    Nothing gates that this line stays `resolve_engine()`, deliberately -- but
    not because every divergence fails closed. It does not, and that premise was
    wrong when first written here. Replacing this with a bare `PrusaSlicer()`
    errors loudly, which is what the earlier note reasoned about; inlining the
    fixture and faithfully reproducing only the *skip* -- dropping the require
    branch, which is the invisible half -- leaves an engine-less runner with
    `PRUSASLICER_PY_REQUIRE_ENGINE=1` at `6 passed, 4 skipped, exit 0`. Measured.
    That is `engine.yml`'s exact condition going green, which is the one thing it
    promises cannot happen.

    What catches it is `ci.yml`'s #30 step: it runs `just test-engine` on
    `windows-latest` where no engine exists and requires the require-engine
    message, which that mutation does not produce. And the step itself is gated,
    by `test_ci_runs_the_gates_that_guard_all_of_this`.

    So the protection is real and checkable, and it is a Windows round-trip away
    rather than local. Left as a comment rather than a local gate because the
    alternatives are worse: a source-shape assertion reads rather than runs, and
    `pytester` is a great deal of machinery for one line.
    """
    return resolve_engine()
