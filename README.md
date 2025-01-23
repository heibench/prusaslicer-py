# PrusaSlicer-Py

**PrusaSlicer-Py** is a Python toolkit for automating and extending PrusaSlicer functionality through its command-line interface (CLI). This project aims to simplify slicing workflows, customize G-code generation, and provide a flexible framework for integrating PrusaSlicer into Python-based workflows.

## Features

- Automate slicing operations using the PrusaSlicer CLI.
- Customize slicing parameters dynamically.
- Load and manage shapes from `.stl` files or existing profiles from `.3MF` or `.AMF` files.
- Support for generating G-code with fine-tuned settings for FFF and SLA printers.

_Note this is currently untested on Linux as I do all my 3D modelling and printing on my windows machine. This in particular is an area where contributors / testers are very welcome._

---

- [PrusaSlicer-Py](#prusaslicer-py)
  - [Features](#features)
  - [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Installation](#installation)
    - [Usage](#usage)
  - [Contributing](#contributing)
  - [License](#license)

---

## Getting Started

### Prerequisites

1. **PrusaSlicer Installation**:

   - Download and install [PrusaSlicer](https://www.prusa3d.com/prusaslicer/).
   - Ensure `prusa-slicer-console.exe` (Windows) or the equivalent `prusa-slicer` CLI executable is installed.
   - Add the directory containing the executable to your system's `PATH` environment variable (or the equivalent for your operating system).
     - On Windows, this is the folder containing `prusa-slicer-console.exe`.
     - On Linux, macOS, and other Unix-like systems, this is the folder containing `prusa-slicer`.

2. **Python Setup**:

   - Python 3.8 or newer is recommended.
   - Install `virtualenv` (optional but recommended):

     ```bash
     pip install virtualenv
     ```

---

### Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/CameronBrooks11/prusaslicer-py.git
   cd prusaslicer-py
   ```

2. Create and activate a virtual environment:

   ```bash
   python -m venv venv
   venv\Scripts\activate  # On Linux: source venv/bin/activate
   ```

3. Install dependencies (currently no python dependancies unless you intend to develop):

   ```bash
   pip install -r requirements.txt
   ```

### Usage

Below is an example of running a basic slicing operation with the built-in example shapes provided as stl files with all prusaslicer installations:

```python
import os
from pathlib import Path
from prusaslicer_py import PrusaSlicer

# Initialize the PrusaSlicer object
slicer = PrusaSlicer(slicer_path="prusa-slicer-console.exe") # slicer_path="prusa-slicer" on Linux

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
```

**NOTE:**

1. Replace slicer_path with the path to your PrusaSlicer CLI executable, if not in PATH.
2. Provide the .stl file, desired output path for the .gcode, and any additional parameters as keyword arguments.

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository.
2. Create a feature branch:

   ```bash
   git checkout -b feature/your-feature-name
   ```

3. Commit your changes and open a pull request.

## License

This project is licensed under the [MIT License](./LICENSE).
