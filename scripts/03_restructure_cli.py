import json
import os
from pathlib import Path


def load_json(file_path):
    """Load JSON data from a file."""
    with open(file_path, "r") as file:
        return json.load(file)


def save_json(data, file_path):
    """Save data to a JSON file."""
    with open(file_path, "w") as file:
        json.dump(data, file, indent=4)


def find_common_sections(data1, data2, data3):
    """Find sections that are common across all three JSONs."""
    common_sections = set(data1.keys()) & set(data2.keys()) & set(data3.keys())
    return common_sections


def filter_common_sections(data, common_sections):
    """Remove common sections from the given data."""
    return {
        section: options
        for section, options in data.items()
        if section not in common_sections
    }


def create_output_jsons(structured_data_dir, common_sections=None):
    """Create the five JSON files: actions, transform, options_common, options_fff, and options_sla."""
    # Load the three JSON files
    help_file = structured_data_dir / "--help_structured.json"
    fff_file = structured_data_dir / "--help-fff_structured.json"
    sla_file = structured_data_dir / "--help-sla_structured.json"

    help_data = load_json(help_file)
    fff_data = load_json(fff_file)
    sla_data = load_json(sla_file)

    # Identify common sections
    common_sections = find_common_sections(help_data, fff_data, sla_data)

    # Extract the common sections data (actions, transform options, other options)
    common_data = {section: help_data[section] for section in common_sections}

    # Filter out common sections from the original data
    help_filtered = filter_common_sections(help_data, common_sections)
    fff_filtered = filter_common_sections(fff_data, common_sections)
    sla_filtered = filter_common_sections(sla_data, common_sections)

    # Prepare the output files
    actions_data = {
        section: common_data[section]
        for section in common_sections
        if "actions" in section.lower()
    }
    transform_data = {
        section: common_data[section]
        for section in common_sections
        if "transform" in section.lower()
    }
    options_common_data = {
        section: common_data[section]
        for section in common_sections
        if "other options" in section.lower()
    }

    # Define new output directory
    output_dir = structured_data_dir.parent / "03_restructured_data"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save the filtered data as JSON files
    save_json(actions_data, output_dir / "actions.json")
    save_json(transform_data, output_dir / "transform.json")
    save_json(options_common_data, output_dir / "options_common.json")
    save_json(fff_filtered, output_dir / "options_fff.json")
    save_json(sla_filtered, output_dir / "options_sla.json")


def main():
    # Define directory where structured data is located
    script_dir = Path(__file__).parent
    structured_data_dir = (
        script_dir / "02_structured_data"
    )  # Folder with the structured JSON files

    # Create the output JSONs
    create_output_jsons(structured_data_dir)

    print(f"Processing complete. Output files saved in 03_restructured_data")


if __name__ == "__main__":
    main()
