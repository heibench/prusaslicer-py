import re
import os
from pathlib import Path

# Define the output directory for parsed help files
script_dir = Path(__file__).parent  # Get the directory of the current script
parsed_output_dir = (
    script_dir / "02_parsed_helps"
)  # Folder inside 'scripts' to store parsed output files

# Create the output directory if it doesn't exist
parsed_output_dir.mkdir(parents=True, exist_ok=True)


def parse_help_output(file_path):
    with open(file_path, "r") as file:
        content = file.read()

    # Define regex pattern for sections (e.g., "Actions:", "Transform options:", etc.)
    sections = re.split(r"\n([A-Za-z\s]+:)\n", content)

    # Pair headers with content
    parsed_output = {}
    for i in range(1, len(sections), 2):
        section_name = sections[i].strip()
        section_content = sections[i + 1].strip()
        parsed_output[section_name] = section_content

    return parsed_output


# Parse each output file from the "01_helps" directory
help_dir = script_dir / "01_helps"
for help_file in os.listdir(help_dir):
    if help_file.endswith("_output.txt"):
        file_path = help_dir / help_file
        parsed = parse_help_output(file_path)

        # Process the parsed output and generate a markdown or other formats
        parsed_file_name = help_file.replace("_output.txt", "_parsed.md")
        parsed_file_path = parsed_output_dir / parsed_file_name

        with open(parsed_file_path, "w") as md_file:
            # Convert parsed data into a markdown format
            for section, content in parsed.items():
                md_file.write(f"## {section}\n\n")
                md_file.write(f"{content}\n\n")

        print(f"Parsed output saved to {parsed_file_path}")

print(f"Parsing complete. Files saved in {parsed_output_dir}")
