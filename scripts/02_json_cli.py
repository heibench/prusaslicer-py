import os
import json
import re
from pathlib import Path


def replace_large_gaps(description, separator=";"):
    """
    Replace large gaps in the description with the specified separator.
    Large gaps are defined as multiple spaces between text.
    """
    cleaned_description = re.sub(r"\s{2,}", f" {separator} ", description)
    return cleaned_description.strip()


def parse_cli_output_with_sections(file_path, separator=";"):
    """
    Parse the raw CLI output, extract sections, and structure the data into a dictionary.
    Each section will contain a list of options with their descriptions.
    """
    structured_data = {}
    current_section = ""
    current_option = ""
    current_description = ""

    with open(file_path, "r") as file:
        content = file.read()

    # Split the content into sections based on section headers (e.g., "Actions:", "Transform options:", etc.)
    sections = re.split(r"\n([A-Za-z\s]+:)\n", content)

    # Process each section separately
    for i in range(1, len(sections), 2):
        section_name = (
            sections[i].strip().lower()
        )  # Normalize section names to lowercase
        section_content = sections[i + 1].strip()

        # Initialize the section if it doesn't exist in the structured data
        if section_name not in structured_data:
            structured_data[section_name] = []

        # Process each line in the section's content
        lines = section_content.split("\n")
        for line in lines:
            line = line.strip()

            # Look for lines that start with "--" (CLI option)
            if line.startswith("--"):
                # If there's an existing option, store it before processing the next one
                if current_option and current_description:
                    current_description = replace_large_gaps(
                        current_description, separator
                    )
                    option_data = {
                        "option": current_option.strip(),
                        "description": current_description,
                    }
                    structured_data[section_name].append(option_data)

                # New option found, reset the description and store the option
                parts = line.split(" ", 1)
                if len(parts) == 2:
                    current_option, current_description = parts
                    current_description = current_description.strip()
                else:
                    current_option = parts[0].strip()
                    current_description = ""
            else:
                # If the line doesn't start with an option, it's part of a description
                if current_description:
                    current_description += " " + line.strip()

        # After finishing the section, make sure to save the last option if any
        if current_option and current_description:
            current_description = replace_large_gaps(current_description, separator)
            option_data = {
                "option": current_option.strip(),
                "description": current_description,
            }
            structured_data[section_name].append(option_data)

        # Reset for the next section
        current_option = ""
        current_description = ""

    # Remove empty sections
    structured_data = {
        section: options for section, options in structured_data.items() if options
    }

    return structured_data


def process_cli_files(input_dir, output_dir, separator=";"):
    """
    Process all CLI output files in the input directory and output structured JSON data,
    with sections properly organized.
    """
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    for cli_file in os.listdir(input_dir):
        if cli_file.endswith("_output.txt"):
            cli_file_path = input_dir / cli_file

            # Parse the CLI file and extract structured data with sections
            structured_data = parse_cli_output_with_sections(cli_file_path, separator)

            # Output JSON file name
            json_file_name = cli_file.replace("_output.txt", "_structured.json")
            json_file_path = output_dir / json_file_name

            # Save the structured data as JSON
            with open(json_file_path, "w") as json_file:
                json.dump(structured_data, json_file, indent=4)

            print(f"Processed {cli_file} into {json_file_name}")


# Define directories
script_dir = Path(__file__).parent
cli_dir = script_dir / "01_helps"  # Folder containing the .txt CLI output files
structured_data_dir = (
    script_dir / "02_structured_data"
)  # Folder to store structured JSON files

# Process all CLI output files in the input directory
process_cli_files(cli_dir, structured_data_dir, separator=";")

print(f"Processing complete. Structured data saved in {structured_data_dir}")
