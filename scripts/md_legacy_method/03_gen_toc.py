import os
from pathlib import Path


def generate_markdown(parsed_output):
    toc = ["# Table of Contents"]
    markdown_content = []

    for header, content in parsed_output.items():
        # Format the TOC link
        toc.append(f"- [{header}](#{header.lower().replace(' ', '-')})")

        # Format the section with the header and content
        markdown_content.append(f"\n## {header}\n")
        markdown_content.append("```\n" + content + "\n```")

    return "\n".join(toc + markdown_content)


# Define the directories for parsed and output markdown files
script_dir = Path(__file__).parent
parsed_helps_dir = script_dir / "02_parsed_helps"  # Folder with parsed markdown files
toc_helps_dir = script_dir / "03_toc_helps"  # Folder to store generated TOC files

# Create the output directory if it doesn't exist
toc_helps_dir.mkdir(parents=True, exist_ok=True)

# Generate TOC and markdown for each parsed markdown file
for parsed_file in os.listdir(parsed_helps_dir):
    if parsed_file.endswith("_parsed.md"):
        parsed_file_path = parsed_helps_dir / parsed_file

        # Read the parsed markdown file
        with open(parsed_file_path, "r") as file:
            parsed_content = file.read()

        # Parse the file into sections (header + content)
        parsed_output = {}
        sections = parsed_content.split("\n## ")
        for section in sections[1:]:
            header, content = section.split("\n", 1)
            parsed_output[header.strip()] = content.strip()

        # Generate the markdown with TOC and content
        markdown = generate_markdown(parsed_output)

        # Save the generated TOC markdown to the 03_toc_helps directory
        toc_file_name = parsed_file.replace("_parsed.md", "_toc.md")
        toc_file_path = toc_helps_dir / toc_file_name
        with open(toc_file_path, "w") as file:
            file.write(markdown)

        print(f"Generated TOC markdown saved to {toc_file_path}")

print(f"Table of Contents generation complete. Files saved in {toc_helps_dir}")
