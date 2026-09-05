"""Shared fixtures.

The distinction this file exists to enforce: *PrusaSlicer is not installed on
this machine* is an environment fault, not a verdict on this code.  A test that
needs the engine and cannot find it must not report as a failure.
"""

import os

import pytest

from prusaslicer_py.slicer import PrusaSlicer

#: Set to a non-empty value to turn a missing engine into a hard failure.
#: CI sets this on runners where the engine is expected to be installed, so
#: that "the engine is missing" cannot quietly masquerade as a green run.
REQUIRE_ENGINE_ENV = "PRUSASLICER_PY_REQUIRE_ENGINE"


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
        if os.environ.get(REQUIRE_ENGINE_ENV):
            pytest.fail(f"{REQUIRE_ENGINE_ENV} is set but: {message}")
        pytest.skip(message)
