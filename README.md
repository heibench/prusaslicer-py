# PrusaSlicer-Py

**PrusaSlicer-Py** is a Python toolkit for automating and extending PrusaSlicer functionality through its command-line interface (CLI). This project aims to simplify slicing workflows, customize G-code generation, and provide a flexible framework for integrating PrusaSlicer into Python-based workflows.

## Features

- Automate slicing operations using the PrusaSlicer CLI.
- Customize slicing parameters dynamically.
- Load and manage shapes from `.stl` files or existing profiles from `.3MF` or `.AMF` files.
- Support for generating G-code with fine-tuned settings for FFF and SLA printers.

## Status

Pre-1.0. The API may change; what it establishes will not be overstated.

- **Linux / Flatpak (Flathub)** -- the full path is exercised, including a real
  end-to-end slice: `slice_model` produced 133 KB of G-code from PrusaSlicer's
  own 3DBenchy against PrusaSlicer 2.9.6.
- **Windows** -- `generate_help` and `get_example_shapes` have been used
  against a real `prusa-slicer-console.exe`, though not since the rewrite.
  `check_version` cannot have been: it called `--version`, which PrusaSlicer
  does not support on any platform (it answers `Unknown option` and exits 1),
  so the previous claim that it was in regular use was false and is withdrawn.
- **Linux on PATH, macOS** -- covered by the mocked suite and by stub engines;
  not yet run against a real install. The `Engine` workflow installs PrusaSlicer
  four different ways and runs the real tests on each; reports from real
  machines are still welcome.
- **CI** -- `CI` runs the gate on Linux (3.11/3.12/3.13) and Windows with no
  engine present, so the engine tests skip and the log says how many were
  withheld. `Engine` installs the real thing and runs them, with a missing
  engine as a hard failure rather than a skip. See
  [`docs/DECISIONS.md`](./docs/DECISIONS.md) D3.

## Finding the engine

PrusaSlicer is located in this order:

1. an explicit `slicer_path` you pass in,
2. `prusa-slicer` (or `prusa-slicer-console.exe`) on `PATH`,
3. a Flathub Flatpak (`com.prusa3d.PrusaSlicer`).

`PrusaSlicer().engine_kind` tells you which was found. Flatpak support is not
cosmetic: a Flatpak has no binary on `PATH`, so discovery that only asks `PATH`
reports "not installed" on the most common Linux install (D9).

---

- [PrusaSlicer-Py](#prusaslicer-py)
  - [Features](#features)
  - [Status](#status)
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

   - Python 3.11 or newer.
   - [`uv`](https://docs.astral.sh/uv/) and [`just`](https://just.systems/) for
     development (not needed to use the package).

---

### Installation

1. Clone the repository:

   ```sh
   git clone https://github.com/heibench/prusaslicer-py.git
   cd prusaslicer-py
   ```

2. Install it:

   ```sh
   pip install -e .
   ```

   Or, for development:

   ```sh
   just setup     # uv sync
   just check     # fmt-check + lint + typecheck
   just test      # run the suite
   ```

   The package itself has no runtime dependencies.

### Usage

Below is an example of running a basic slicing operation with the built-in example shapes provided as stl files with all prusaslicer installations:

```python
import os
from pathlib import Path
from prusaslicer_py import PrusaSlicer, SliceError

# Initialize the PrusaSlicer object
slicer = PrusaSlicer(slicer_path="prusa-slicer-console.exe")  # slicer_path="prusa-slicer" on Linux

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
        # Either the engine failed, or it exited 0 without producing the file
        # -- a mistyped destination, an option that no-ops, an empty plate.
        # Both carry returncode, stdout and stderr as attributes.
        print(f"No G-code produced: {e}\n{e.stderr}")
    else:
        print(f"Sliced {torus_path} -> {result.output_path} ({result.size_bytes} bytes)")
else:
    print("torus.stl not found in example shapes.")
```

**NOTE:**

1. Replace slicer_path with the path to your PrusaSlicer CLI executable, if not in PATH.
2. Provide the .stl file, desired output path for the .gcode, and any additional parameters as keyword arguments.
3. `slice_model` returns a `SliceResult` (`output_path`, `size_bytes`, `returncode`, `stdout`, `stderr`). It returns only once it has confirmed the G-code exists and is non-empty. "It did not raise" is a checked guarantee, not an assumption.
4. Both failures raise a `SliceError` (a `RuntimeError`) carrying those same fields: `SliceEngineError` when PrusaSlicer exits non-zero, `SliceOutputError` when it exits 0 without producing the file.

## Contributing

See [`AGENTS.md`](./AGENTS.md) for repository conventions, and
[`docs/DECISIONS.md`](./docs/DECISIONS.md) for the reasoning behind the ones
that were not obvious.

Contributions are welcome! Please follow these steps:

1. Fork the repository.
2. Create a feature branch:

   ```sh
   git checkout -b feature/your-feature-name
   ```

3. Run `just check && just test`, then commit your changes and open a pull
   request.

## License

This project is licensed under the [MIT License](./LICENSE).
