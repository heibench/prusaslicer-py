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


def test_extraction_carries_no_mojibake():
    """The help output is UTF-8; reading it as cp1252 used to corrupt it."""
    for path in (SCRIPTS / "03_restructured_data").glob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert "Â°" not in text, f"{path.name} contains a double-encoded degree sign"
        assert "Î¼" not in text, f"{path.name} contains a double-encoded mu"
