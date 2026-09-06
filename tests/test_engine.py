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


def test_engine_resolves_to_something_runnable(engine):
    """Whatever the wrapper resolved, it is a real, invocable engine.

    Not "is on PATH": a Flatpak has no binary on PATH at all, and asserting
    PATH here made the test fail on the most common Linux install of
    PrusaSlicer while the engine sat one `flatpak run` away.
    """
    assert engine.slicer_path
    assert engine.engine_kind in {"path", "flatpak"}
    if engine.engine_kind == "path":
        assert shutil.which(engine.slicer_path) is not None
    else:
        assert engine._argv[0].endswith("flatpak")
        assert engine.FLATPAK_APP_ID in engine._argv


def test_check_version_against_real_engine(engine):
    assert engine.check_version().strip(), "engine returned an empty version string"


def test_generate_help_against_real_engine(engine):
    assert engine.generate_help("fff").strip()


def test_slice_produces_gcode_with_the_real_engine(engine, tmp_path):
    """The end-to-end path: a real slice, verified by the driver's own result."""
    shapes = [s for s in engine.get_example_shapes() if s.endswith(".stl")]
    if not shapes:
        raise AssertionError("engine is installed but shipped no example shapes to slice")

    out = tmp_path / "out.gcode"
    result = engine.slice_model(shapes[0], str(out))

    assert result.output_path == out
    assert result.size_bytes > 0
    assert out.read_text().strip(), "slice_model returned but the G-code is blank"
