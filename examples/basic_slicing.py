from pathlib import Path

from prusaslicer_py import PrusaSlicer

# Initialize the PrusaSlicer object
slicer = PrusaSlicer(slicer_path="prusa-slicer-console.exe")

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
        slicer.slice_model(torus_path, str(gcode_output))
        print(f"Successfully sliced {torus_path} to G-code: {gcode_output}")
    except Exception as e:
        print(f"Error slicing {torus_path}: {e}")
else:
    print("torus.stl not found in example shapes.")
