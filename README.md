# PrusaSlicer-Py

**PrusaSlicer-Py** is a Python toolkit for automating and extending PrusaSlicer functionality through its command-line interface (CLI). This project aims to simplify slicing workflows, customize G-code generation, and provide a flexible framework for integrating PrusaSlicer into Python-based workflows.

## Features

- Automate slicing operations using the PrusaSlicer CLI.
- Customize slicing parameters dynamically.
- Load and manage shapes from `.stl` files or existing profiles from `.3MF` or `.AMF` files.
- Support for generating G-code with fine-tuned settings for FFF and SLA printers.

## Status

Pre-1.0. The API may change; what it establishes will not be overstated.

The full path -- discovery, `check_version`, `generate_help`,
`get_example_shapes`, and a real end-to-end `slice_model` -- is exercised
against a real PrusaSlicer on every supported install mode, in CI:

| platform | install mode | engine |
| --- | --- | --- |
| Linux | Flathub Flatpak | 2.9.6 |
| Linux | distro package on `PATH` | packaged build |
| macOS | Homebrew cask (`.app` bundle) | latest cask |
| Windows | official portable `.zip` on `PATH` | 2.9.6 |

Those jobs set `PRUSASLICER_PY_REQUIRE_ENGINE=1`, so a runner that fails to
install the engine fails the job rather than quietly skipping. The `CI`
workflow separately runs the mocked suite on Linux 3.11/3.12/3.13 and Windows
with no engine present, where the engine tests skip and the log says how many
were withheld (`docs/DECISIONS.md` D3).

Not covered: SLA workflows beyond `--help-sla` parsing, and any printer profile
handling beyond passing arguments through.

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
   just setup     # uv sync --locked
   just check     # fmt-check + lint + typecheck
   just test      # run the suite
   ```

   The package itself has no runtime dependencies.

### Usage

```python
from prusaslicer_py import PrusaSlicer, SliceError

slicer = PrusaSlicer()  # found on PATH, or as a Flathub Flatpak
print(slicer.engine_kind)  # "path" or "flatpak"
print(slicer.check_version())  # PrusaSlicer-2.9.6+flathub.org based on Slic3r ...

# PrusaSlicer ships example models; pick one to slice.
torus = next(s for s in slicer.get_example_shapes() if s.endswith("torus.stl"))

try:
    result = slicer.slice_model(torus, "torus.gcode")
except SliceError as e:
    # Either the engine failed, or it exited 0 without producing the file --
    # a mistyped destination, an option that no-ops, an empty plate. Both
    # carry output_path, returncode, stdout and stderr as attributes.
    print(f"no G-code produced: {e}\n{e.stderr}")
else:
    print(f"{result.output_path} ({result.size_bytes} bytes, exit {result.returncode})")
```

`slice_model` returns only once it has checked that the file exists and is not
empty. "The call did not raise" and "the artifact was produced" are not the
same claim, and this package will not conflate them.

Pass `slicer_path=` to point at a specific executable instead of searching:

```python
slicer = PrusaSlicer(slicer_path="/opt/PrusaSlicer/bin/prusa-slicer")
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
