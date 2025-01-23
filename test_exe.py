import os
import sys
from prusaslicer_py.slicer import PrusaSlicer


def test_executable():
    slicer = PrusaSlicer()

    try:
        # Try to find the executable in the PATH
        executable_path = slicer._find_executable()
        print(f"Executable found: {executable_path}")
    except FileNotFoundError:
        print(
            "Executable not found. Please check your PATH and ensure PrusaSlicer is installed."
        )


if __name__ == "__main__":
    test_executable()
