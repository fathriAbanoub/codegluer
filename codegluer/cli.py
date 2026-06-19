import sys
import argparse
import logging
from . import __version__
from .core import glue_files, GlueConfig, CodeGluerError


def non_negative_int(value):
    """Argparse type for non-negative integers (>= 0)."""
    try:
        ivalue = int(value)
    except ValueError as err:
        raise argparse.ArgumentTypeError(f"{value} is not a valid integer") from err
    if ivalue < 0:
        raise argparse.ArgumentTypeError(f"{value} is not a non-negative integer")
    return ivalue


def positive_int(value):
    """Argparse type for positive integers (> 0)."""
    try:
        ivalue = int(value)
    except ValueError as err:
        raise argparse.ArgumentTypeError(f"{value} is not a valid integer") from err
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(f"{value} is not a positive integer")
    return ivalue


def main():
    logging.basicConfig(level=logging.WARNING, format="%(message)s", stream=sys.stderr)

    parser = argparse.ArgumentParser(
        description="Glue multiple code files (and directories) into a single .txt or .md file."
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"CodeGluer {__version__}"
    )
    parser.add_argument("paths", nargs="+", help="Paths to files or directories.")
    parser.add_argument("-o", "--output", default=None,
        help="Output file path. Use '-' to write to stdout.")
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

    # ── New AI context arguments ──────────────────────────────────────────

    # Tree
    parser.add_argument("--tree", action="store_true",
        help="Prepend an ASCII project structure tree to the output.")
    parser.add_argument("--tree-depth", type=non_negative_int, default=None,
        help="Limit the depth of the ASCII tree (non-negative integer).")
    parser.add_argument("--tree-max-files", type=positive_int, default=10,
        help="Collapse directories with more than N items in the tree (positive integer; default: 10).")

    # Stats
    parser.add_argument("--stats", action="store_true",
        help="Prepend a project statistics summary (files, lines, languages).")

    # Tokens
    parser.add_argument("--estimate-tokens", action="store_true",
        help="Append a token count estimate and context-size tier.")

    # TOC
    parser.add_argument("--toc", action="store_true",
        help="Prepend a Table of Contents. Markdown format only.")

    # AI prompt
    parser.add_argument("--ai-prompt", type=str, default=None,
        help="Prepend a custom system prompt wrapped in <system_context> tags.")
    parser.add_argument("--ai-prompt-file", type=str, default=None,
        help="Read the system prompt from this file path.")

    # Priority
    parser.add_argument("--priority", action="append", metavar="GLOB", default=None,
        help="Glob pattern for files to place at the top (repeatable).")

    args = parser.parse_args()

    try:
        config = GlueConfig(
            output_path=args.output,
            output_format=args.format,
            recursive=args.recursive,
            respect_gitignore=args.respect_gitignore,
            exclude_patterns=args.exclude or [],
            include_patterns=args.include or [],
            show_tree=args.tree,
            tree_depth=args.tree_depth,
            tree_max_files=args.tree_max_files,
            show_stats=args.stats,
            estimate_tokens=args.estimate_tokens,
            toc=args.toc,
            ai_prompt=args.ai_prompt,
            ai_prompt_file=args.ai_prompt_file,
            priority_patterns=args.priority or [],
        )

        output_path, count = glue_files(paths=args.paths, config=config)
        if output_path != "-":
            print(f"✅ Glued {count} file(s) into: {output_path}")
    except CodeGluerError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
