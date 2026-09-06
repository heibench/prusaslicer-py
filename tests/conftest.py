"""Shared fixtures.

The distinction this file exists to enforce: *PrusaSlicer is not installed on
this machine* is an environment fault, not a verdict on this code.  A test that
needs the engine and cannot find it must not report as a failure.
"""

import os

import pytest

from prusaslicer_py.slicer import PrusaSlicer

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


@pytest.fixture
def engine() -> PrusaSlicer:
    """A PrusaSlicer bound to the real engine, or a skipped test.

    Requesting this fixture is how a test declares "I need the engine".  When
    the engine is absent the test is skipped -- unless the caller has asserted
    it should be there via the environment variable above, in which case the
    absence is a hard failure rather than a silent skip.

    Resolution goes through PrusaSlicer itself rather than repeating the
    executable-name choice here.  A second copy of that logic in the test suite
    would drift from the one in the driver, and the tests would then be
    checking for an engine the driver would not have used.
    """
    try:
        return PrusaSlicer()
    except FileNotFoundError as e:
        message = f"{e} This is an environment fault, not a verdict on the code under test."
        if engine_required():
            pytest.fail(f"{REQUIRE_ENGINE_ENV} is set but: {message}")
        pytest.skip(message)
