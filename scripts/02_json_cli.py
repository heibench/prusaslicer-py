import json
import os
import re
from pathlib import Path
from typing import TypedDict

# A value placeholder as PrusaSlicer prints it: an all-caps token, possibly a
# comma-separated tuple (X,Y), possibly carrying the separator of an alias list
# (the "ABCD," in "--output ABCD, -o ABCD").
VALUE_PLACEHOLDER = re.compile(r"[A-Z]+(?:,[A-Z]+)*,?")

# One spelling as printed, paired with the value placeholder that follows it
# (``None`` when the option takes no value). The spelling is never absent --
# a pair exists because a spelling was matched -- so only the value is
# optional, which is what lets ``option`` below be a plain ``str``.
Flag = tuple[str, str | None]


class OptionRecord(TypedDict):
    """One entry of the extracted CLI surface: the schema D6 froze."""

    option: str
    aliases: list[str]
    value: str | None
    description: str


def replace_large_gaps(description: str, separator: str = ";") -> str:
    """
    Replace large gaps in the description with the specified separator.
    Large gaps are defined as multiple spaces between text.
    """
    cleaned_description = re.sub(r"\s{2,}", f" {separator} ", description)
    return cleaned_description.strip()


def split_option_line(line: str) -> tuple[list[Flag], str]:
    """Split one help line into its option spellings and its description.

    PrusaSlicer prints an option as a comma-separated list of spellings, each
    optionally followed by a value placeholder, then the description::

        --export-gcode, --gcode, -g
                            Slice the model and export toolpaths as G-code.
        --output ABCD, -o ABCD
                            Write output to the given file.
        --help, -h          Show this help.
        --center X,Y        Center the print around the given center.

    Splitting on the first space -- what this parser used to do -- puts
    "--gcode, -g" in the description and leaves a trailing comma on the option
    name. Two signals separate the halves reliably:

    * the spelling list continues only after a token ending in a comma;
    * a value placeholder follows its flag after exactly one space, while a
      description is set off by the help output's column gap.

    :return: ``(flags, description)``, where ``flags`` is a list of
             ``(spelling, value_or_None)`` pairs in the order printed and
             ``description`` is the rest of the line -- empty when the
             description begins on the following line.
    """
    flags: list[Flag] = []
    continues = False
    prev_end = 0

    for match in re.finditer(r"\S+", line):
        token = match.group()
        if not flags or continues:
            continues = token.endswith(",")
            flags.append((token.rstrip(","), None))
            prev_end = match.end()
            continue
        is_placeholder = match.start() == prev_end + 1 and VALUE_PLACEHOLDER.fullmatch(token)
        if is_placeholder:
            continues = token.endswith(",")
            flags[-1] = (flags[-1][0], token.rstrip(","))
            prev_end = match.end()
            continue
        return flags, line[match.start() :]

    return flags, ""


def parse_cli_output_with_sections(
    file_path: Path, separator: str = ";"
) -> dict[str, list[OptionRecord]]:
    """
    Parse the raw CLI output, extract sections, and structure the data into a dictionary.
    Each section will contain a list of options with their descriptions.
    """
    structured_data: dict[str, list[OptionRecord]] = {}
    current_flags: list[Flag] = []
    current_description = ""

    # The help output is UTF-8 (it contains a degree sign and a mu). Without an
    # explicit encoding, open() follows the locale -- on Windows, cp1252 --
    # which is how the committed data came to say "\u00c2\u00b0C".
    with open(file_path, encoding="utf-8") as file:
        content = file.read()

    # Split the content into sections based on section headers
    # (e.g., "Actions:", "Transform options:", etc.)
    sections = re.split(r"\n([A-Za-z\s]+:)\n", content)

    # Process each section separately
    for i in range(1, len(sections), 2):
        section_name = sections[i].strip().lower()  # Normalize section names to lowercase
        section_content = sections[i + 1].strip()

        # Initialize the section if it doesn't exist in the structured data
        if section_name not in structured_data:
            structured_data[section_name] = []

        def flush(flags: list[Flag], description: str, section: str = section_name) -> None:
            # An option with no description is still an option. PrusaSlicer
            # documents a handful of them with a blank line; dropping them
            # would make the extraction quietly incomplete.
            if not flags:
                return
            primary, value = flags[0]
            structured_data[section].append(
                {
                    "option": primary,
                    "aliases": [spelling for spelling, _ in flags[1:]],
                    "value": value,
                    "description": replace_large_gaps(description, separator),
                }
            )

        # Process each line in the section's content. Keep the raw line: the
        # column a description starts in is part of how it is told apart from
        # the flags.
        lines = section_content.split("\n")
        for raw_line in lines:
            if raw_line.lstrip().startswith("--"):
                flush(current_flags, current_description)
                current_flags, current_description = split_option_line(raw_line)
                current_description = current_description.strip()
            elif current_description:
                # A continuation of the description already under way.
                current_description += " " + raw_line.strip()
            elif current_flags:
                # The description began on the line after the flags.
                current_description = raw_line.strip()

        # After finishing the section, make sure to save the last option if any
        flush(current_flags, current_description)

        # Reset for the next section
        current_flags = []
        current_description = ""

    # Remove empty sections
    structured_data = {section: options for section, options in structured_data.items() if options}

    return structured_data


def process_cli_files(input_dir: Path, output_dir: Path, separator: str = ";") -> None:
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
            with open(json_file_path, "w", encoding="utf-8") as json_file:
                json.dump(structured_data, json_file, indent=4, ensure_ascii=False)

            print(f"Processed {cli_file} into {json_file_name}")


def main() -> None:
    script_dir = Path(__file__).parent
    cli_dir = script_dir / "01_helps"  # Folder containing the .txt CLI output files
    structured_data_dir = script_dir / "02_structured_data"  # Folder for the JSON files

    process_cli_files(cli_dir, structured_data_dir, separator=";")

    print(f"Processing complete. Structured data saved in {structured_data_dir}")


if __name__ == "__main__":
    main()
