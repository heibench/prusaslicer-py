import os
import json
import re
from pathlib import Path


def replace_large_gaps(description, separator=";"):
    """
    Replace large gaps in the description with the specified separator.
    Large gaps are defined as multiple spaces between text.
    """
    # Regex to match multiple spaces or tabs
    cleaned_description = re.sub(r"\s{2,}", f" {separator} ", description)
    return cleaned_description.strip()


def parse_toc_file(toc_file_path, separator=";"):
    """
    Parse the TOC markdown file and structure the data into a dictionary,
    replacing large gaps in descriptions with a separator. Skip sections without options.
    """
    structured_data = {}
    current_section = None
    current_options = []

    with open(toc_file_path, "r") as file:
        lines = file.readlines()

    for line in lines:
        line = line.strip()
        if line.startswith("## "):  # Section header
            if current_section and current_options:
                # Only save sections that have options
                structured_data[current_section] = current_options

            current_section = line[3:].strip()  # Remove "## " to get the section name
            current_options = []  # Reset options list
        elif re.match(r"^--", line):  # Option line (match lines starting with "--")
            # Extract option and description
            parts = line.split(" ", 1)
            if len(parts) == 2:
                option, description = parts
                # Clean the description by replacing large gaps
                cleaned_description = replace_large_gaps(description, separator)
                option_data = {
                    "option": option.strip(),
                    "description": cleaned_description,
                }
                current_options.append(option_data)

    # Save the last section if it has options
    if current_section and current_options:
        structured_data[current_section] = current_options

    return structured_data


def process_all_tocs(input_dir, output_dir, separator=";"):
    """
    Process all TOC markdown files in the input directory and output structured JSON data,
    replacing large gaps with the specified separator in descriptions.
    Skip sections without any options.
    """
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    for toc_file in os.listdir(input_dir):
        if toc_file.endswith("_toc.md"):
            toc_file_path = input_dir / toc_file

            # Parse the TOC file and extract structured data
            structured_data = parse_toc_file(toc_file_path, separator)

            # Output JSON file name
            json_file_name = toc_file.replace("_toc.md", "_structured.json")
            json_file_path = output_dir / json_file_name

            # Save the structured data as JSON
            with open(json_file_path, "w") as json_file:
                json.dump(structured_data, json_file, indent=4)

            print(f"Processed {toc_file} into {json_file_name}")


# Define directories
script_dir = Path(__file__).parent
toc_helps_dir = script_dir / "03_toc_helps"
structured_data_dir = (
    script_dir / "04_structured_data"
)  # Folder to store structured JSON files

# Process all TOC files with the default separator ";"
process_all_tocs(toc_helps_dir, structured_data_dir, separator=";")

print(f"Processing complete. Structured data saved in {structured_data_dir}")
