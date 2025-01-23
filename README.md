# PrusaSlicer-Py

**PrusaSlicer-Py** is a Python toolkit for automating and extending PrusaSlicer functionality through its command-line interface (CLI). This project aims to simplify slicing workflows, customize G-code generation, and provide a flexible framework for integrating PrusaSlicer into Python-based workflows.

## Features

- Automate slicing operations using the PrusaSlicer CLI.
- Customize slicing parameters dynamically.
- Load and manage profiles from `.3MF` or `.AMF` files.
- Support for generating G-code with fine-tuned settings for FFF and SLA printers.

---

## Getting Started

### Prerequisites

1. **PrusaSlicer Installation**:

   - Download and install [PrusaSlicer](https://www.prusa3d.com/prusaslicer/).
   - Ensure `prusa-slicer-console.exe` (Windows) or the equivalent CLI executable is installed.
   - Add the directory containing the executable to your system PATH.

2. **Python Setup**:
   - Python 3.8 or newer is recommended.
   - Install `virtualenv` (optional but recommended):
     ```bash
     pip install virtualenv
     ```

---

### Installation

1. Clone the repository:
2.

```bash
git clone https://github.com/yourusername/prusaslicer-py.git
cd prusaslicer-py
```

1. Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies (if any):

```bash
pip install -r requirements.txt
```

### Usage

Start by running a basic slicing operation:

```python

from prusaslicer_py import PrusaSlicer

slicer = PrusaSlicer(slicer_path="prusa-slicer-console.exe")
slicer.slice_model(
    stl_path="example.stl",
    gcode_output="output.gcode",
    layer_height=0.2,
    fill_density=20
)


```

1. Replace slicer_path with the path to your PrusaSlicer CLI executable, if not in PATH.
2. Provide the .stl file, desired output path for the .gcode, and any additional parameters as keyword arguments.

### Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository.
2. Create a feature branch:

```bash
git checkout -b feature/your-feature-name
```

3. Commit your changes and open a pull request.

### License

This project is licensed under the [MIT License](./LICENSE).

