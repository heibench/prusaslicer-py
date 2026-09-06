"""The extraction pipeline that turns PrusaSlicer's --help into JSON.

scripts/03_restructured_data/*.json exists to be read by a program, so the
parser that produces it is worth pinning. These tests cover the option/
description split directly, and then check that the committed data is what the
committed parser actually produces -- the data is a build product, and a build
product that has drifted from its generator is worse than no build product.
"""

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

# The captured help is PrusaSlicer's own output and is NOT committed (D8), so
# the corpus tests below only run where someone has regenerated it locally with
# `just capture-cli`. They SKIP rather than pass when it is absent: every one of
# them walks a glob, and a glob over an empty directory makes an assertion loop
# vacuous -- a test that reports success having examined nothing.
_HELP_DIR = SCRIPTS / "01_helps"
_needs_corpus = pytest.mark.skipif(
    not list(_HELP_DIR.glob("*_output.txt")),
    reason=(
        "no captured help in scripts/01_helps -- run `just capture-cli` with "
        "PrusaSlicer installed. Skipped rather than passed: these tests glob, "
        "and a glob over nothing asserts nothing."
    ),
)


def _load_parser():
    spec = importlib.util.spec_from_file_location("json_cli", SCRIPTS / "02_json_cli.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


parser = _load_parser()


@pytest.mark.parametrize(
    ("line", "flags", "description"),
    [
        # A plain option.
        (
            " --export-3mf        Export the model(s) as 3MF.",
            [["--export-3mf", None]],
            "Export the model(s) as 3MF.",
        ),
        # Aliases, description on the same line. Splitting on the first space
        # used to put "--sla" in the description.
        (
            " --export-sla, --sla Slice and export SLA layers.",
            [["--export-sla", None], ["--sla", None]],
            "Slice and export SLA layers.",
        ),
        # Aliases, description on the following line: no description here.
        (
            " --export-gcode, --gcode, -g",
            [["--export-gcode", None], ["--gcode", None], ["-g", None]],
            "",
        ),
        # A short-flag alias.
        (
            " --help, -h          Show this help.",
            [["--help", None], ["-h", None]],
            "Show this help.",
        ),
        # A value placeholder is part of the option, not the description.
        (
            " --save ABCD         Save configuration to the specified file.",
            [["--save", "ABCD"]],
            "Save configuration to the specified file.",
        ),
        # A tuple-valued placeholder, whose comma is not an alias separator.
        (" --center X,Y        Center the print.", [["--center", "X,Y"]], "Center the print."),
        # A placeholder repeated across the alias list.
        (" --output ABCD, -o ABCD", [["--output", "ABCD"], ["-o", "ABCD"]], ""),
        # Three long spellings, none of which is a description.
        (
            " --top-fill-pattern, --external-fill-pattern, --solid-fill-pattern",
            [
                ["--top-fill-pattern", None],
                ["--external-fill-pattern", None],
                ["--solid-fill-pattern", None],
            ],
            "",
        ),
        # A description whose first word is capitalised like a placeholder.
        (
            " --wipe-tower-x N    X coordinate of the wipe tower.",
            [["--wipe-tower-x", "N"]],
            "X coordinate of the wipe tower.",
        ),
    ],
)
def test_split_option_line(line, flags, description):
    assert parser.split_option_line(line) == (flags, description)


@_needs_corpus
def test_committed_data_matches_the_committed_parser(tmp_path):
    """Regenerating from the captured help reproduces the committed JSON.

    If this fails, either the generated data was hand-edited or the generator
    changed without `just extract-cli` being run.
    """
    parser.process_cli_files(SCRIPTS / "01_helps", tmp_path, separator=";")

    committed_dir = SCRIPTS / "02_structured_data"
    regenerated = {
        p.name: json.loads(p.read_text(encoding="utf-8")) for p in tmp_path.glob("*.json")
    }
    committed = {
        p.name: json.loads(p.read_text(encoding="utf-8")) for p in committed_dir.glob("*.json")
    }

    assert regenerated.keys() == committed.keys()
    assert regenerated == committed


@_needs_corpus
def test_every_option_in_the_help_reaches_the_extraction():
    """Nothing is silently dropped between the help output and the JSON.

    68 options used to be missing here, because their description began on the
    line after the flags and the parser required a description to emit an entry
    at all.
    """
    restructured = SCRIPTS / "03_restructured_data"
    known: set[str] = set()
    for path in restructured.glob("*.json"):
        for entries in json.loads(path.read_text(encoding="utf-8")).values():
            for entry in entries:
                known.add(entry["option"])
                known.update(entry["aliases"])

    for help_file in (SCRIPTS / "01_helps").glob("*_output.txt"):
        printed = {
            line.split()[0].rstrip(",")
            for line in help_file.read_text(encoding="utf-8").splitlines()
            if line.startswith(" --")
        }
        assert not printed - known, f"{help_file.name} lists options absent from the extraction"


@_needs_corpus
def test_extraction_carries_no_mojibake():
    """The help output is UTF-8; reading it as cp1252 used to corrupt it."""
    for path in (SCRIPTS / "03_restructured_data").glob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert "Â°" not in text, f"{path.name} contains a double-encoded degree sign"
        assert "Î¼" not in text, f"{path.name} contains a double-encoded mu"


# --- always-on coverage, independent of the captured corpus ---------------
#
# tests/fixtures/synthetic_help_output.txt is written by hand in PrusaSlicer's
# help format. It is not PrusaSlicer output, so it is ours to redistribute, and
# it carries one instance of every shape the parser has ever got wrong.


def _parse_fixture(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    (src / "synthetic_help_output.txt").write_text(
        (FIXTURES / "synthetic_help_output.txt").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    out = tmp_path / "out"
    parser.process_cli_files(src, out, separator=";")
    data = json.loads((out / "synthetic_help_structured.json").read_text(encoding="utf-8"))
    return [entry for entries in data.values() for entry in entries]


def test_fixture_option_whose_description_starts_on_the_next_line_is_kept(tmp_path):
    """The defect that dropped 68 options: a flag whose description wraps.

    `--rotate-around X,Y,Z` has nothing after the placeholder; its description
    begins on the following line. The old parser required a same-line
    description and emitted no entry at all.
    """
    options = {e["option"] for e in _parse_fixture(tmp_path)}
    # `--rotate-around X,Y,Z` carries a placeholder; `--avoid-curled-overhangs`
    # carries nothing at all, which is the shape the old parser actually
    # dropped -- verified by running the pre-fix parser against this fixture.
    assert "--rotate-around" in options
    assert "--avoid-curled-overhangs" in options


def test_fixture_bare_flag_with_no_description_is_kept(tmp_path):
    """`--wipe-tower` and `--slice-only` have no description whatsoever."""
    options = {e["option"] for e in _parse_fixture(tmp_path)}
    assert {"--wipe-tower", "--slice-only"} <= options


def test_fixture_aliases_do_not_leak_into_the_description(tmp_path):
    """The 7 mis-split entries: `--export-gcode, --gcode, -g` on one line."""
    entry = next(e for e in _parse_fixture(tmp_path) if e["option"] == "--export-gcode")
    assert entry["aliases"] == ["--gcode", "-g"]
    assert not entry["description"].lstrip().startswith("-")
    assert "--gcode" not in entry["description"]


def test_fixture_placeholders_are_read_as_values_not_description(tmp_path):
    values = {e["option"]: e["value"] for e in _parse_fixture(tmp_path)}
    assert values["--bed-temperature"] == "N"
    assert values["--center"] == "X,Y"
    assert values["--rotate-around"] == "X,Y,Z"
    assert values["--wipe-tower"] is None


def test_fixture_non_ascii_survives_the_round_trip(tmp_path):
    """Reading the help as cp1252 used to double-encode these."""
    joined = " ".join(e["description"] for e in _parse_fixture(tmp_path))
    assert "°C" in joined and "μm" in joined
    assert "Â°" not in joined and "Î¼" not in joined


def _load_restructurer():
    spec = importlib.util.spec_from_file_location(
        "restructure_cli", SCRIPTS / "03_restructure_cli.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_a_common_section_with_an_unfamiliar_name_is_not_dropped(tmp_path):
    """Step 03 must partition by exclusion, not by an allow-list.

    It used to route common sections into three buckets by matching "actions",
    "transform" and "other options", and silently discard anything matching
    none of them. PrusaSlicer 2.9.6's `input:` section lost --load,
    --print-profile, --printer-profile and --material-profile exactly that way,
    and nothing said so.
    """
    restructure = _load_restructurer()
    section = {"option": "--load", "aliases": [], "value": "ABCD", "description": "Load config."}
    shared = {
        "actions:": [
            {"option": "--export-gcode", "aliases": [], "value": None, "description": "x"}
        ],
        "input:": [section],
        "novel section nobody has seen:": [
            {"option": "--brand-new", "aliases": [], "value": None, "description": "y"}
        ],
    }
    src = tmp_path / "02"
    src.mkdir()
    for name in (
        "--help_structured.json",
        "--help-fff_structured.json",
        "--help-sla_structured.json",
    ):
        (src / name).write_text(json.dumps(shared), encoding="utf-8")

    restructure.create_output_jsons(src)

    out = src.parent / "03_restructured_data"
    surviving = {
        entry["option"]
        for path in out.glob("*.json")
        for entries in json.loads(path.read_text(encoding="utf-8")).values()
        for entry in entries
    }
    assert "--load" in surviving, "the input: section was dropped again"
    assert "--brand-new" in surviving, "an unfamiliar common section was dropped"
