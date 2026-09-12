"""Slice a shipped example shape, passing engine options through `additional_args`.

**The keys are the engine's own option names**, spelled exactly as the engine's
own `--help-fff` spells them. `additional_args` builds `--{key}` verbatim
and does not translate, which is deliberate: a silent `_` to `-` rewrite would make
a genuinely misspelled option indistinguishable from a correctly spelled one, and
the engine's "Unknown option" is the only signal that anything was wrong.

That is not a hypothetical. This example used to pass `layer_height`,
`infill_density`, `print_speed` and `extruder_temperature`, and only the first of
those becomes a real option by swapping the underscore: there is no
`--infill-density` (it is `--fill-density`), no `--print-speed` (speeds are
per-feature), and no `--extruder-temperature` (it is `--temperature`). Checking the
spelling against the engine's `--help-fff` is the habit this file demonstrates.
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

# Specify the output G-code file path
gcode_output = output_dir / "torus.gcode"

# Engine option names, verified against the engine's own `--help-fff`.
additional_args = {
    "layer-height": "0.2",  # mm
    "fill-density": "20%",  # the engine states this one as a percentage
    "perimeter-speed": "60",  # mm/s. PrusaSlicer has no single "print speed"
    "temperature": "210",  # Celsius, for layers after the first
}

# Slice the torus.stl into G-code with the specified arguments
try:
    result = slicer.slice_model(torus_path, str(gcode_output), additional_args=additional_args)
except SliceError as e:
    # Either the engine failed, or it exited 0 without producing the file.
    # Both carry the engine's own output -- usually the only explanation.
    #
    # Exit NON-ZERO. Printing the failure and returning 0 is what this file used to
    # do, and it is the defect the whole org is named after, in a file whose job is
    # to demonstrate the library working: a person reads the message, a smoke test
    # reads `$?`, and the two disagreed.
    print(f"No G-code produced: {e}", file=sys.stderr)
    print(e.stderr, file=sys.stderr)
    raise SystemExit(1) from e

print(f"Sliced {torus_path} -> {result.output_path} ({result.size_bytes} bytes)")
