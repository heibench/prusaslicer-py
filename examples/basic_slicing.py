"""Slice a shipped example shape with the engine's own defaults.

The companion to `torus_example_attempt.py`, which passes options. This one passes
none, so the two together show what changes and what does not.

Both **exit non-zero when they do not produce what they demonstrate**. Printing the
engine's complaint and exiting 0 is indistinguishable from success to everything
except a person reading the terminal (prusaslicer-py#36).
"""

import sys
from pathlib import Path

from prusaslicer_py import PrusaSlicer, SliceError

# Let the driver find the engine. Naming the Windows executable here made this
# example Windows-only -- the same defect D1 removed from the capture script.
slicer = PrusaSlicer()

# Retrieve the list of example shapes
example_shapes = slicer.get_example_shapes()

# Find the path to the torus.stl example
torus_path = None
for shape in example_shapes:
    if "torus.stl" in shape:
        torus_path = shape
        break

if torus_path is None:
    print("torus.stl not found in example shapes.", file=sys.stderr)
    raise SystemExit(1)

print(f"Found torus.stl at: {torus_path}")

# Specify the output directory, one level above the script (beside 'examples')
script_dir = Path(__file__).parent  # Get the directory of the current script
output_dir = script_dir.parent / "output"  # Path to the 'output' directory, one level above
output_dir.mkdir(parents=True, exist_ok=True)  # Create the output directory if it doesn't exist

# A name of its own. Both examples used to write `torus.gcode`, so whichever ran
# second could not tell its own output from the one already sitting there -- the
# stale-artifact case `slice_model` documents, reintroduced by the file name.
gcode_output = output_dir / "torus_defaults.gcode"

# Slice the torus.stl into G-code without any extra arguments
try:
    result = slicer.slice_model(torus_path, str(gcode_output))
except SliceError as e:
    # Either the engine failed, or it exited 0 without producing the file.
    # Both carry the engine's own output -- usually the only explanation.
    print(f"No G-code produced: {e}", file=sys.stderr)
    print(e.stderr, file=sys.stderr)
    raise SystemExit(1) from e

print(f"Sliced {torus_path} -> {result.output_path} ({result.size_bytes} bytes)")
