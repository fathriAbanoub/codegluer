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
import logging

# Module-level logger – lets host applications control output
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())   # <-- NEW: suppress logging by default

SEPARATOR_CHAR = "="
SEPARATOR_LENGTH = 70


class CodeGluerError(Exception):
    """Base exception for CodeGluer."""
    pass


class NoFilesError(CodeGluerError):
    """Raised when no input files are provided."""
    pass


class NoReadableFilesError(CodeGluerError):
    """Raised when none of the provided files could be read."""
    pass


class OutputWriteError(CodeGluerError):
    """Raised when the output file could not be written."""
    pass


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
        file_paths: List of paths to the files to glue.
        output_path: Optional path for the output file. If None, a default
        is generated in the same directory as the first input file.
    Returns:
        A tuple of (path to the created output file, count of successfully glued files).
    Raises:
        NoFilesError: if file_paths is empty.
        NoReadableFilesError: if none of the files could be read.
        OutputWriteError: if the output file could not be written.
    """
    if not file_paths:
        raise NoFilesError("No files provided.")

    # Determine output path
    if output_path is None:
        base_dir = os.path.dirname(os.path.abspath(file_paths[0]))
        output_path = os.path.join(base_dir, "glued_code.txt")
        if os.path.exists(output_path):
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(base_dir, f"glued_code_{ts}.txt")

    sections = []
    success_count = 0

    for filepath in file_paths:
        filepath = os.path.abspath(filepath)
        if not os.path.isfile(filepath):
            logger.warning(f"Skipping '{filepath}' (not a regular file).")
            continue

        filename = os.path.basename(filepath)
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            logger.warning(f"Could not read '{filepath}': {e}")
            continue

        header = build_header(filename)
        footer = build_footer(filename)
        section = f"{header}\n{content}"
        if not section.endswith("\n"):
            section += "\n"
        section += f"{footer}\n"
        sections.append(section)
        success_count += 1

    if not sections:
        raise NoReadableFilesError("No files could be read.")

    glued_content = "\n".join(sections)
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(glued_content)
    except Exception as e:
        raise OutputWriteError(f"Could not write output file: {e}") from e

    return output_path, success_count


def main():
    # Configure logging for the CLI – warnings go to stderr (same as before)
    logging.basicConfig(
        level=logging.WARNING,
        format="%(message)s",
        stream=sys.stderr
    )

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

    try:
        output_path, count = glue_files(args.files, args.output)
        print(f"✅ Glued {count} file(s) into: {output_path}")
    except CodeGluerError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
