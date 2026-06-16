#!/usr/bin/env python3
"""
CodeGluer - Glue multiple code files into a single .txt file.
Each file's content is wrapped with clear start/end markers and the filename,
making it easy to identify file boundaries in the glued output.
Usage:
codegluer <file1> <file2> ... [--output <output_path>]
If --output is not specified, the glued file is saved next to the first
input file with the name "glued_code.txt". If that name already exists,
a timestamp is appended.
"""
import sys
import os
import argparse
import datetime

SEPARATOR_CHAR = "="
SEPARATOR_LENGTH = 70

def build_header(filename):
    """Build the start marker for a file."""
    label = f" BEGIN FILE: {filename} "
    pad_total = SEPARATOR_LENGTH - len(label)
    pad_left = pad_total // 2
    pad_right = pad_total - pad_left
    return f"{SEPARATOR_CHAR * pad_left}{label}{SEPARATOR_CHAR * pad_right}"

def build_footer(filename):
    """Build the end marker for a file."""
    label = f" END FILE: {filename} "
    pad_total = SEPARATOR_LENGTH - len(label)
    pad_left = pad_total // 2
    pad_right = pad_total - pad_left
    return f"{SEPARATOR_CHAR * pad_left}{label}{SEPARATOR_CHAR * pad_right}"

def glue_files(file_paths, output_path=None):
    """
    Glue the given files into a single text file.
    Args:
        file_paths: List of absolute paths to the files to glue.
        output_path: Optional path for the output file. If None, a default
        is generated in the same directory as the first input file.
    Returns:
        A tuple of (path to the created output file, count of successfully glued files).
    """
    if not file_paths:
        print("Error: No files provided.", file=sys.stderr)
        sys.exit(1)

    # Determine output path
    if output_path is None:
        base_dir = os.path.dirname(os.path.abspath(file_paths[0]))
        output_path = os.path.join(base_dir, "glued_code.txt")
        # Avoid overwriting an existing file – append a timestamp
        if os.path.exists(output_path):
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(base_dir, f"glued_code_{ts}.txt")

    sections = []
    success_count = 0

    for filepath in file_paths:
        filepath = os.path.abspath(filepath)
        if not os.path.isfile(filepath):
            print(f"Warning: Skipping '{filepath}' (not a regular file).", file=sys.stderr)
            continue

        filename = os.path.basename(filepath)
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            print(f"Warning: Could not read '{filepath}': {e}", file=sys.stderr)
            continue

        header = build_header(filename)
        footer = build_footer(filename)
        section = f"{header}\n{content}"

        # Ensure content ends with a newline before the footer
        if not section.endswith("\n"):
            section += "\n"
        section += f"{footer}\n"

        sections.append(section)
        success_count += 1

    if not sections:
        print("Error: No files could be read.", file=sys.stderr)
        sys.exit(1)

    glued_content = "\n".join(sections)
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(glued_content)
    except Exception as e:
        print(f"Error: Could not write output file: {e}", file=sys.stderr)
        sys.exit(1)

    return output_path, success_count

def main():
    parser = argparse.ArgumentParser(
        description="Glue multiple code files into a single .txt file "
        "with start/end markers for each file."
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="Paths to the code files to glue."
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Path for the output .txt file. "
        "Defaults to 'glued_code.txt' in the same directory as "
        "the first input file."
    )
    args = parser.parse_args()

    output, count = glue_files(args.files, args.output)
    print(f"✅ Glued {count} file(s) into: {output}")

if __name__ == "__main__":
    main()
