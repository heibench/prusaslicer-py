import json
from pathlib import Path

# The extracted CLI surface as this script handles it: section name to the
# option records under it. Nothing here looks inside a record -- the four
# fields D6 froze are read by consumers, not by the restructuring step -- so
# the element type stays opaque rather than restating that schema a second
# time where it could drift from the parser that writes it.
Sections = dict[str, list[object]]


def load_json(file_path: Path) -> Sections:
    """Load JSON data from a file."""
    with open(file_path, encoding="utf-8") as file:
        data: Sections = json.load(file)
    return data


def save_json(data: Sections, file_path: Path) -> None:
    """Save data to a JSON file."""
    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


def find_common_sections(data1: Sections, data2: Sections, data3: Sections) -> set[str]:
    """Find sections that are common across all three JSONs."""
    common_sections = set(data1.keys()) & set(data2.keys()) & set(data3.keys())
    return common_sections


def filter_common_sections(data: Sections, common_sections: set[str]) -> Sections:
    """Remove common sections from the given data."""
    return {section: options for section, options in data.items() if section not in common_sections}


def create_output_jsons(structured_data_dir: Path) -> None:
    """Create the five JSON files: actions, transform, options_common,
    options_fff, and options_sla."""
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
    fff_filtered = filter_common_sections(fff_data, common_sections)
    sla_filtered = filter_common_sections(sla_data, common_sections)

    # Prepare the output files
    actions_data = {
        section: common_data[section] for section in common_sections if "actions" in section.lower()
    }
    transform_data = {
        section: common_data[section]
        for section in common_sections
        if "transform" in section.lower()
    }
    # Every common section that is not actions or transform belongs here.
    #
    # This used to match only "other options", which meant any common section
    # whose name matched none of the three buckets was dropped with no
    # diagnostic -- PrusaSlicer 2.9.6's "input:" section lost --load,
    # --print-profile, --printer-profile and --material-profile exactly that
    # way. Partition by exclusion rather than by an allow-list, so a section
    # this script has never seen before is carried rather than discarded.
    options_common_data = {
        section: common_data[section]
        for section in common_sections
        if section not in actions_data and section not in transform_data
    }

    routed = set(actions_data) | set(transform_data) | set(options_common_data)
    unrouted = set(common_sections) - routed
    if unrouted:  # pragma: no cover - defensive; the partition above is total
        raise RuntimeError(f"common sections routed nowhere: {sorted(unrouted)}")

    # Define new output directory
    output_dir = structured_data_dir.parent / "03_restructured_data"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save the filtered data as JSON files
    save_json(actions_data, output_dir / "actions.json")
    save_json(transform_data, output_dir / "transform.json")
    save_json(options_common_data, output_dir / "options_common.json")
    save_json(fff_filtered, output_dir / "options_fff.json")
    save_json(sla_filtered, output_dir / "options_sla.json")


def main() -> None:
    # Define directory where structured data is located
    script_dir = Path(__file__).parent
    structured_data_dir = script_dir / "02_structured_data"  # Folder with the structured JSON files

    # Create the output JSONs
    create_output_jsons(structured_data_dir)

    print("Processing complete. Output files saved in 03_restructured_data")


if __name__ == "__main__":
    main()
