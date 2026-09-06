"""Capture PrusaSlicer's own --help output into scripts/01_helps/.

The captures are PrusaSlicer's output, not ours, so they are not committed
(D8). Run this with PrusaSlicer installed to regenerate them, then
`just extract-cli` to rebuild the structured data.

The engine is located by the driver rather than by a hardcoded name: D1 says
`prusaslicer_py/slicer.py` is the only module that may name an executable, and
this script hardcoding `prusa-slicer-console.exe` was the one exception --
which also made the capture Windows-only.
"""

from pathlib import Path

from prusaslicer_py.slicer import PrusaSlicer

MODES = {"--help": "all", "--help-fff": "fff", "--help-sla": "sla"}


def main() -> None:
    output_dir = Path(__file__).parent / "01_helps"
    output_dir.mkdir(parents=True, exist_ok=True)

    slicer = PrusaSlicer()
    for filename_stem, mode in MODES.items():
        content = slicer.generate_help(mode)
        # Always UTF-8 with LF, whatever platform captured it. Step 02 reads
        # these as UTF-8; a locale-encoded capture (cp1252 on Windows) would
        # either fail outright or reintroduce the mojibake this pipeline lost.
        (output_dir / f"{filename_stem}_output.txt").write_text(
            content + "\n", encoding="utf-8", newline="\n"
        )

    print(f"Help outputs saved to {output_dir}")


if __name__ == "__main__":
    main()
