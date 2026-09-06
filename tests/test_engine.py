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

import pytest
from _pytest.outcomes import Failed, Skipped

from prusaslicer_py.slicer import PrusaSlicer
from tests.conftest import REQUIRE_ENGINE_ENV, engine_required, resolve_engine


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


@pytest.mark.parametrize("value", ["1", "", "0", "false"])
def test_any_value_requires_the_engine_including_the_empty_string(
    value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The switch is presence, and the empty string is the case that bit.

    `os.environ.get()` returns `''` for `PRUSASLICER_PY_REQUIRE_ENGINE=`, which is
    falsy, so the fixture skipped -- the one control that exists so a missing engine
    cannot read as green, turned off by setting it to nothing. `"0"` and `"false"`
    are here because they are falsy to a reader, not to this function; requiring on
    them is the fail-closed direction and is deliberate.
    """
    monkeypatch.setenv(REQUIRE_ENGINE_ENV, value)
    assert engine_required(), f"{value!r} did not require the engine"


def test_the_switch_is_off_when_the_variable_is_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """The other half: without it, a missing engine skips rather than failing."""
    monkeypatch.delenv(REQUIRE_ENGINE_ENV, raising=False)
    assert not engine_required()


def test_the_fixture_actually_consults_the_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    """The tests above watch `engine_required`. This watches that the fixture uses it.

    Extracting the decision so it could be tested is what opened the seam: reverting
    only the *call site* back to `os.environ.get(...)` -- leaving `engine_required`
    itself correct -- left the whole suite green while restoring the fail-open, and a
    run with the engine unreachable and the variable set to the empty string went
    `5 passed, 4 skipped, exit 0`.

    This calls `resolve_engine()`, which is the function the fixture is, rather than
    reaching through the fixture's `__wrapped__` -- that attribute is untyped and
    mypy rejects it, and CI said so after a local `grep` of mine hid it.

    A gate on the helper says nothing about whether anything calls it. That is the
    same shape as every other defeat in this issue, one level below where it lives.
    """
    monkeypatch.setenv(REQUIRE_ENGINE_ENV, "")

    def _no_engine(self: PrusaSlicer) -> None:
        raise FileNotFoundError("no engine")

    monkeypatch.setattr(PrusaSlicer, "__init__", _no_engine)

    # Not `pytest.raises(Failed)`. A fixture that skips raises `Skipped`, and letting
    # that escape a test SKIPS the test -- so the first version of this reported
    # "9 passed, 1 skipped" against the very revert it was written to catch. Each
    # outcome is named instead, and skipping is a failure here.
    try:
        resolve_engine()
    except Failed as failure:
        assert "is set but" in str(failure)
    except Skipped:
        pytest.fail(
            "the fixture skipped with the switch set to the empty string, so it is "
            "not consulting `engine_required()` -- the fail-open is back"
        )
    else:
        pytest.fail("the fixture neither failed nor skipped without an engine")
