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

if torus_path:
    print(f"Found torus.stl at: {torus_path}")

    # Specify the output directory, one level above the script (beside 'examples')
    script_dir = Path(__file__).parent  # Get the directory of the current script
    output_dir = script_dir.parent / "output"  # Path to the 'output' directory, one level above
    output_dir.mkdir(parents=True, exist_ok=True)  # Create the output directory if it doesn't exist

    # Specify the output G-code file path
    gcode_output = output_dir / "torus.gcode"

    # Slice the torus.stl into G-code without any extra arguments
    try:
        result = slicer.slice_model(torus_path, str(gcode_output))
    except SliceError as e:
        # Either the engine failed, or it exited 0 without producing the file.
        # Both carry the engine's own output -- usually the only explanation.
        print(f"No G-code produced: {e}")
        print(e.stderr)
    else:
        print(f"Sliced {torus_path} -> {result.output_path} ({result.size_bytes} bytes)")

else:
    print("torus.stl not found in example shapes.")
