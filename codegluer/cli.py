import sys
import argparse
import logging
from . import __version__
from .core import glue_files, CodeGluerError

def main():
    logging.basicConfig(level=logging.WARNING, format="%(message)s", stream=sys.stderr)

    parser = argparse.ArgumentParser(
        description="Glue multiple code files (and directories) into a single .txt or .md file."
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"CodeGluer {__version__}"
    )
    parser.add_argument("paths", nargs="+", help="Paths to files or directories.")
    parser.add_argument("-o", "--output", default=None, help="Output file path.")
    parser.add_argument(
        "--format", choices=["plain", "markdown"], default="plain",
        help="Output format: 'plain' (separator markers) or 'markdown' (code blocks)."
    )
    parser.add_argument(
        "-r", "--recursive", action="store_true",
        help="Recursively traverse directories."
    )
    parser.add_argument(
        "--respect-gitignore", action="store_true",
        help="Respect .gitignore files."
    )
    parser.add_argument(
        "--exclude", action="append", metavar="PATTERN",
        help="Glob pattern to exclude (can be specified multiple times)."
    )
    parser.add_argument(
        "--include", action="append", metavar="PATTERN",
        help="Glob pattern to include (can be specified multiple times)."
    )

    args = parser.parse_args()

    try:
        output_path, count = glue_files(
            paths=args.paths,
            output_path=args.output,
            output_format=args.format,
            recursive=args.recursive,
            respect_gitignore=args.respect_gitignore,
            exclude_patterns=args.exclude or [],
            include_patterns=args.include or [],
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
