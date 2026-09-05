"""Tests that need the real PrusaSlicer engine.

These are the counterpart to the mocked tests in ``test_slicer.py``: they are
the only place the engine is actually invoked.  Each requests the ``engine``
fixture, which skips -- or, under PRUSASLICER_PY_REQUIRE_ENGINE, fails loudly
-- when PrusaSlicer is not installed, so a machine without the engine reports
an environment fault rather than a verdict on this code.

These are per-test guards, not a module-level skip: a module gated at import
reports as a single skipped line and takes every test in the file with it.
"""

import shutil


def test_engine_resolves_from_path(engine):
    """The executable the wrapper found is real and on PATH."""
    assert engine.slicer_path
    assert shutil.which(engine.slicer_path) is not None


def test_check_version_against_real_engine(engine):
    assert engine.check_version().strip(), "engine returned an empty version string"


def test_generate_help_against_real_engine(engine):
    assert engine.generate_help("fff").strip()
