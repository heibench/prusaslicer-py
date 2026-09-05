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
    result = subprocess.run(cmd, capture_output=True, text=True)
    output[cmd[-1]] = result.stdout

# Save the outputs to text files inside the 'helps' folder
for key, content in output.items():
    output_file = output_dir / f"{key}_output.txt"
    with open(output_file, "w") as file:
        file.write(content)

print(f"Help outputs saved to {output_dir}")
