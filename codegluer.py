#!/usr/bin/env python3
"""
CodeGluer - Glue multiple code files (and directories) into a single .txt or .md file.
Now with recursion, .gitignore respect, and include/exclude filters.
"""
import sys
import os
import argparse
import datetime
import logging
import fnmatch
from pathlib import Path

# Module-level logger
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

SEPARATOR_CHAR = "="
SEPARATOR_LENGTH = 70

EXT_TO_LANG = {
    ".py": "python", ".js": "javascript", ".ts": "typescript", ".jsx": "jsx", ".tsx": "tsx",
    ".html": "html", ".css": "css", ".scss": "scss", ".json": "json", ".yaml": "yaml",
    ".yml": "yaml", ".toml": "toml", ".md": "markdown", ".sh": "bash", ".bash": "bash",
    ".c": "c", ".cpp": "cpp", ".h": "c", ".hpp": "cpp", ".java": "java", ".go": "go",
    ".rs": "rust", ".rb": "ruby", ".php": "php", ".swift": "swift", ".kt": "kotlin",
    ".sql": "sql", ".r": "r", ".lua": "lua", ".pl": "perl", ".pm": "perl", ".tcl": "tcl",
    ".xml": "xml", ".svg": "svg", ".txt": "text",
}

try:
    import pathspec
    HAS_PATHSPEC = True
except ImportError:
    HAS_PATHSPEC = False
    logger.debug("pathspec not installed; advanced globbing and .gitignore support disabled.")


def detect_language(filename):
    ext = os.path.splitext(filename)[1].lower()
    return EXT_TO_LANG.get(ext, "")


def sanitize_filename_for_markdown(filename):
    sanitized = filename.replace('`', '&#96;')
    sanitized = sanitized.replace('\n', ' ').replace('\r', ' ')
    return sanitized


class CodeGluerError(Exception): pass
class NoFilesError(CodeGluerError): pass
class NoReadableFilesError(CodeGluerError): pass
class OutputWriteError(CodeGluerError): pass


def build_header(filename):
    label = f" BEGIN FILE: {filename} "
    pad_total = SEPARATOR_LENGTH - len(label)
    pad_left = pad_total // 2
    pad_right = pad_total - pad_left
    return f"{SEPARATOR_CHAR * pad_left}{label}{SEPARATOR_CHAR * pad_right}"


def build_footer(filename):
    label = f" END FILE: {filename} "
    pad_total = SEPARATOR_LENGTH - len(label)
    pad_left = pad_total // 2
    pad_right = pad_total - pad_left
    return f"{SEPARATOR_CHAR * pad_left}{label}{SEPARATOR_CHAR * pad_right}"


def build_markdown_section(filename, content):
    lang = detect_language(filename)
    safe_filename = sanitize_filename_for_markdown(filename)
    heading = f"### `{safe_filename}`"

    max_backticks = 0
    current = 0
    for ch in content:
        if ch == '`':
            current += 1
            max_backticks = max(max_backticks, current)
        else:
            current = 0

    fence = '`' * max(3, max_backticks + 1)
    lang_str = f"{lang}" if lang else ""
    content = content.rstrip('\n')
    return f"{heading}\n\n{fence}{lang_str}\n{content}\n{fence}\n"


# ---------------------------------------------------------
# Helper to determine common base directory (DRY)
# ---------------------------------------------------------
def _get_common_base(paths):
    """Determine the common base directory for a list of paths."""
    resolved = [Path(p).resolve() for p in paths]
    if not resolved:
        return Path.cwd()
    if len(resolved) == 1:
        return resolved[0] if resolved[0].is_dir() else resolved[0].parent
    try:
        base = Path(os.path.commonpath(resolved))
        return base if base.is_dir() else base.parent
    except ValueError:
        # Paths on different drives (Windows)
        return Path.cwd()


# ---------------------------------------------------------
# Filtering & .gitignore Logic
# ---------------------------------------------------------
def _build_filter_spec(patterns):
    """Build a pathspec.PathSpec if available, otherwise return the list for fnmatch."""
    if not patterns:
        return None
    if HAS_PATHSPEC:
        return pathspec.PathSpec.from_lines('gitignore', patterns)  # updated pattern name
    # Fallback for fnmatch: strip trailing slashes so "node_modules/" matches "node_modules"
    return [p.rstrip('/') for p in patterns]


def _matches_filters(rel_path_str, include_spec, exclude_spec):
    if exclude_spec:
        if HAS_PATHSPEC:
            if exclude_spec.match_file(rel_path_str):
                return False
        else:
            if any(fnmatch.fnmatch(rel_path_str, p) for p in exclude_spec):
                return False
    if include_spec:
        if HAS_PATHSPEC:
            if not include_spec.match_file(rel_path_str):
                return False
        else:
            if not any(fnmatch.fnmatch(rel_path_str, p) for p in include_spec):
                return False
    return True


def _is_ignored_by_specs(file_abs_str, gitignore_specs):
    for spec_dir_str, spec in gitignore_specs.items():
        try:
            rel_path = os.path.relpath(file_abs_str, spec_dir_str).replace("\\", "/")
            if spec.match_file(rel_path):
                return True
        except ValueError:
            continue
    return False


def collect_files(
    paths,
    recursive=False,
    respect_gitignore=False,
    exclude_patterns=None,
    include_patterns=None,
):
    exclude_patterns = exclude_patterns or []
    include_patterns = include_patterns or []
    
    exclude_spec = _build_filter_spec(exclude_patterns)
    include_spec = _build_filter_spec(include_patterns)

    collected = []
    resolved_paths = [Path(p).resolve() for p in paths]
    base_dir = _get_common_base(paths)

    for path in resolved_paths:
        if not path.exists():
            logger.warning(f"Skipping '{path}' (does not exist).")
            continue

        if path.is_file():
            try:
                rel_to_base = str(path.relative_to(base_dir)).replace("\\", "/")
            except ValueError:
                rel_to_base = path.name
            if _matches_filters(rel_to_base, include_spec, exclude_spec):
                collected.append(path)
            continue

        if path.is_dir():
            if not recursive:
                logger.warning(f"Skipping directory '{path}' (use --recursive to traverse).")
                continue

            gitignore_specs = {}

            for root, dirs, files in os.walk(path, topdown=True, followlinks=False):
                root_path = Path(root)
                
                if respect_gitignore and HAS_PATHSPEC:
                    gi_file = root_path / ".gitignore"
                    if gi_file.exists():
                        try:
                            with open(gi_file, "r", encoding="utf-8", errors="ignore") as f:
                                spec = pathspec.PathSpec.from_lines('gitignore', f)  # updated
                                gitignore_specs[str(root_path)] = spec
                        except Exception as e:
                            logger.debug(f"Could not parse {gi_file}: {e}")

                # Filter directories: only apply exclude and gitignore (NOT include)
                filtered_dirs = []
                for d in dirs:
                    dir_abs = root_path / d
                    try:
                        rel_to_base = str(dir_abs.relative_to(base_dir)).replace("\\", "/")
                    except ValueError:
                        rel_to_base = d
                    
                    # Check exclude (if any)
                    if exclude_spec:
                        if HAS_PATHSPEC:
                            if exclude_spec.match_file(rel_to_base):
                                continue
                        else:
                            if any(fnmatch.fnmatch(rel_to_base, p) for p in exclude_spec):
                                continue
                    
                    # Check gitignore
                    if respect_gitignore and _is_ignored_by_specs(str(dir_abs), gitignore_specs):
                        continue
                    
                    filtered_dirs.append(d)
                dirs[:] = filtered_dirs

                # Process files: apply include and exclude filters
                for file in files:
                    file_abs = root_path / file
                    try:
                        rel_to_base = str(file_abs.relative_to(base_dir)).replace("\\", "/")
                    except ValueError:
                        rel_to_base = file
                    
                    if not _matches_filters(rel_to_base, include_spec, exclude_spec):
                        continue
                    if respect_gitignore and _is_ignored_by_specs(str(file_abs), gitignore_specs):
                        continue
                    
                    collected.append(file_abs)

    return collected


def glue_files(
    paths,
    output_path=None,
    output_format="plain",
    recursive=False,
    respect_gitignore=False,
    exclude_patterns=None,
    include_patterns=None,
):
    if output_format not in ("plain", "markdown"):
        raise ValueError(f"Invalid output_format: {output_format!r}. Must be 'plain' or 'markdown'.")

    if not paths:
        raise NoFilesError("No paths provided.")

    file_paths = collect_files(
        paths,
        recursive=recursive,
        respect_gitignore=respect_gitignore,
        exclude_patterns=exclude_patterns,
        include_patterns=include_patterns,
    )

    if not file_paths:
        raise NoReadableFilesError("No files could be read after filtering.")

    # Determine output path – smart placement
    if output_path is None:
        first_path = Path(paths[0]).resolve()
        base_dir = first_path if first_path.is_dir() else first_path.parent
        ext = ".md" if output_format == "markdown" else ".txt"
        output_path = str(base_dir / f"glued_code{ext}")
        if os.path.exists(output_path):
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            output_path = str(base_dir / f"glued_code_{ts}{ext}")

    # Determine display base directory (for relative paths in headers)
    display_base_dir = _get_common_base(paths)

    sections = []
    success_count = 0

    for filepath in file_paths:
        if not filepath.is_file():
            logger.warning(f"Skipping '{filepath}' (not a regular file).")
            continue

        try:
            display_name = str(filepath.relative_to(display_base_dir)).replace("\\", "/")
        except ValueError:
            display_name = filepath.name

        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            logger.warning(f"Could not read '{filepath}': {e}")
            continue

        if output_format == "markdown":
            section = build_markdown_section(display_name, content)
        else:
            header = build_header(display_name)
            footer = build_footer(display_name)
            section = f"{header}\n{content}"
            if not section.endswith("\n"):
                section += "\n"
            section += f"{footer}\n"

        sections.append(section)
        success_count += 1

    if not sections:
        raise NoReadableFilesError("No files could be read.")

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
    logging.basicConfig(level=logging.WARNING, format="%(message)s", stream=sys.stderr)

    parser = argparse.ArgumentParser(
        description="Glue multiple code files (and directories) into a single .txt or .md file."
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
        help="Respect .gitignore files (requires pathspec library)."
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

    if args.respect_gitignore and not HAS_PATHSPEC:
        print("Warning: --respect-gitignore requires 'pathspec' library. Install with: pip install pathspec", file=sys.stderr)

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
