from pathlib import Path

from prusaslicer_py import PrusaSlicer, SliceOutputError

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

    # PrusaSlicer command options (adjusted for proper slicing)
    additional_args = {
        "layer_height": "0.2",  # Example: Layer height
        "infill_density": "20",  # Example: Infill density in percentage
        "print_speed": "60",  # Example: Print speed in mm/s
        "extruder_temperature": "210",  # Example: Extruder temperature in Celsius
    }

    # Slice the torus.stl into G-code with the specified arguments
    try:
        result = slicer.slice_model(torus_path, str(gcode_output), additional_args=additional_args)
    except SliceOutputError as e:
        # The engine exited 0 without producing the file. Its own diagnostics
        # are on the exception -- they are usually the only explanation.
        print(f"PrusaSlicer produced no G-code: {e}")
        print(e.stderr)
    except RuntimeError as e:
        print(f"Error slicing {torus_path}: {e}")
    else:
        print(f"Sliced {torus_path} -> {result.output_path} ({result.size_bytes} bytes)")

else:
    print("torus.stl not found in example shapes.")
