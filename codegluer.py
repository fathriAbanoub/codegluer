#!/usr/bin/env python3
"""
CodeGluer - Glue multiple code files into a single .txt or .md file.
Each file's content is wrapped with clear markers (plain) or markdown code blocks.
Usage:
codegluer <file1> <file2> ... [--output <output_path>] [--format {plain,markdown}]

If --output is not specified, the output file is saved next to the first input
file with the name "glued_code.txt" (plain) or "glued_code.md" (markdown).
If that name already exists, a timestamp is appended.
"""
import sys
import os
import argparse
import datetime
import logging

# Module-level logger – lets host applications control output
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

SEPARATOR_CHAR = "="
SEPARATOR_LENGTH = 70

# Mapping from file extensions to markdown code fence languages
EXT_TO_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "jsx",
    ".tsx": "tsx",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".md": "markdown",
    ".sh": "bash",
    ".bash": "bash",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".sql": "sql",
    ".r": "r",
    ".lua": "lua",
    ".pl": "perl",
    ".pm": "perl",
    ".tcl": "tcl",
    ".xml": "xml",
    ".svg": "svg",
    ".txt": "text",
    # fallback to empty (no language specified)
}


def detect_language(filename):
    """Return the markdown language identifier based on file extension."""
    ext = os.path.splitext(filename)[1].lower()
    return EXT_TO_LANG.get(ext, "")


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


def build_markdown_section(filename, content):
    """Build a markdown section for a file, safely handling inner backticks."""
    lang = detect_language(filename)
    heading = f"### `{filename}`"

    # Find the longest run of backticks in the content
    max_backticks = 0
    current = 0
    for ch in content:
        if ch == '`':
            current += 1
            max_backticks = max(max_backticks, current)
        else:
            current = 0

    # Fence must be at least 3, and longer than any run
    fence = '`' * max(3, max_backticks + 1)
    lang_str = f"{lang}" if lang else ""

    # Strip trailing newlines to avoid an extra blank line before the closing fence
    content = content.rstrip('\n')

    return f"{heading}\n\n{fence}{lang_str}\n{content}\n{fence}\n"


def glue_files(file_paths, output_path=None, output_format="plain"):
    """
    Glue the given files into a single text file.
    Args:
        file_paths: List of paths to the files to glue.
        output_path: Optional path for the output file. If None, a default
        is generated in the same directory as the first input file.
        output_format: "plain" (separator markers) or "markdown".
    Returns:
        A tuple of (path to the created output file, count of successfully glued files).
    Raises:
        NoFilesError: if file_paths is empty.
        NoReadableFilesError: if none of the files could be read.
        OutputWriteError: if the output file could not be written.
    """
    if not file_paths:
        raise NoFilesError("No files provided.")

    # Determine output path (smart extension)
    if output_path is None:
        base_dir = os.path.dirname(os.path.abspath(file_paths[0]))
        ext = ".md" if output_format == "markdown" else ".txt"
        output_path = os.path.join(base_dir, f"glued_code{ext}")
        if os.path.exists(output_path):
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(base_dir, f"glued_code_{ts}{ext}")

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

        if output_format == "markdown":
            section = build_markdown_section(filename, content)
        else:  # plain
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

    # Join sections: markdown needs blank lines between blocks, plain does not
    if output_format == "markdown":
        glued_content = "\n\n".join(sections)
    else:
        glued_content = "\n".join(sections)

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(glued_content)
    except Exception as e:
        raise OutputWriteError(f"Could not write output file: {e}") from e

    return output_path, success_count


def main():
    # Configure logging for the CLI – warnings go to stderr
    logging.basicConfig(
        level=logging.WARNING,
        format="%(message)s",
        stream=sys.stderr
    )

    parser = argparse.ArgumentParser(
        description="Glue multiple code files into a single .txt or .md file."
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="Paths to the code files to glue."
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Path for the output file. "
        "Defaults to 'glued_code.txt' (plain) or 'glued_code.md' (markdown) "
        "in the same directory as the first input file."
    )
    parser.add_argument(
        "--format",
        choices=["plain", "markdown"],
        default="plain",
        help="Output format: 'plain' (separator markers) or 'markdown' "
             "(code blocks with file headings)."
    )
    args = parser.parse_args()

    try:
        output_path, count = glue_files(
            args.files,
            output_path=args.output,
            output_format=args.format
        )
        print(f"✅ Glued {count} file(s) into: {output_path}")
    except CodeGluerError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
