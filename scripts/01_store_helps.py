import subprocess
from pathlib import Path

# Define the commands to run
commands = [
    ["prusa-slicer-console.exe", "--help"],
    ["prusa-slicer-console.exe", "--help-fff"],
    ["prusa-slicer-console.exe", "--help-sla"],
]

# Define the output directory
script_dir = Path(__file__).parent  # Get the directory of the current script
output_dir = script_dir / "01_helps"  # Folder inside 'scripts' to store the output files

# Create the output directory if it doesn't exist
output_dir.mkdir(parents=True, exist_ok=True)

# Run each command and store the output
output = {}

for cmd in commands:
    # errors="replace": a byte the locale codec cannot read must not abort the
    # capture. The codec itself stays the platform default -- it is the OS's
    # best guess at what its own console produced.
    result = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    output[cmd[-1]] = result.stdout

# Save the outputs to text files inside the 'helps' folder
for key, content in output.items():
    output_file = output_dir / f"{key}_output.txt"
    # Always UTF-8 with LF, whatever platform captured it. Step 02 reads these
    # as UTF-8; a locale-encoded capture (cp1252 on Windows) would either make
    # it fail outright or reintroduce the mojibake this pipeline just lost.
    with open(output_file, "w", encoding="utf-8", newline="\n") as file:
        file.write(content)

print(f"Help outputs saved to {output_dir}")
