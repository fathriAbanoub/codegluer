from __future__ import annotations
import os
import re
import datetime
import logging
from dataclasses import dataclass, field
from pathlib import Path
import pathspec

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

def detect_language(filename):
    ext = os.path.splitext(filename)[1].lower()
    return EXT_TO_LANG.get(ext, "")

def sanitize_filename_for_markdown(filename):
    sanitized = filename.replace('`', '&#96;')
    sanitized = sanitized.replace('\n', ' ').replace('\r', ' ')
    return sanitized

class CodeGluerError(Exception):
    pass

class NoFilesError(CodeGluerError):
    pass

class NoReadableFilesError(CodeGluerError):
    pass

class OutputWriteError(CodeGluerError):
    pass

# ─────────────────────────────────────────────────────────────────────
# GlueConfig dataclass
# ─────────────────────────────────────────────────────────────────────

@dataclass
class GlueConfig:
    # ── Existing options (preserve defaults exactly) ──────────────────────
    output_path: str | None = None
    output_format: str = "plain"
    recursive: bool = False
    respect_gitignore: bool = False
    exclude_patterns: list = field(default_factory=list)
    include_patterns: list = field(default_factory=list)
    # ── New options ───────────────────────────────────────────────────────
    show_tree: bool = False
    tree_depth: int | None = None
    tree_max_files: int = 10
    show_stats: bool = False
    estimate_tokens: bool = False
    toc: bool = False
    ai_prompt: str | None = None
    ai_prompt_file: str | None = None   # Path to a file containing the prompt text
    priority_patterns: list = field(default_factory=list)

# ─────────────────────────────────────────────────────────────────────
# Header / Footer / Markdown builders
# ─────────────────────────────────────────────────────────────────────

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
# Helper to determine common base directory
# ---------------------------------------------------------
def _get_common_base(resolved_paths):
    """Determine the common base directory from a list of resolved Path objects."""
    if not resolved_paths:
        return Path.cwd()
    if len(resolved_paths) == 1:
        p = resolved_paths[0]
        return p if p.is_dir() else p.parent
    try:
        base = Path(os.path.commonpath(resolved_paths))
        return base if base.is_dir() else base.parent
    except ValueError:
        # Paths on different drives (Windows)
        return Path.cwd()

# ---------------------------------------------------------
# Filtering & .gitignore Logic
# ---------------------------------------------------------
def _build_filter_spec(patterns):
    if not patterns:
        return None
    return pathspec.PathSpec.from_lines('gitignore', patterns)

def _matches_filters(rel_path_str, include_spec, exclude_spec):
    if exclude_spec and exclude_spec.match_file(rel_path_str):
        return False
    if include_spec and not include_spec.match_file(rel_path_str):
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

# ─────────────────────────────────────────────────────────────────────
# TreeNode + Tree Builder + Tree Renderer
# ─────────────────────────────────────────────────────────────────────

class TreeNode:
    def __init__(self, name: str, is_dir: bool):
        self.name = name
        self.is_dir = is_dir
        self.children: list | None = [] if is_dir else None


def build_tree_structure(file_paths, base_dir) -> TreeNode:
    """Build a TreeNode tree from a flat list of resolved Path objects relative to base_dir."""
    root = TreeNode(".", is_dir=True)

    for filepath in file_paths:
        try:
            rel = filepath.relative_to(base_dir)
            parts = list(rel.parts)
        except ValueError:
            parts = [filepath.name]

        current = root
        for i, part in enumerate(parts):
            is_last = (i == len(parts) - 1)
            is_dir = not is_last

            # Look for existing child
            existing = None
            if current.children is not None:
                for child in current.children:
                    if child.name == part and child.is_dir == is_dir:
                        existing = child
                        break

            if existing:
                current = existing
            else:
                new_node = TreeNode(part, is_dir=is_dir)
                current.children.append(new_node)
                current = new_node

    # Sort each directory's children: directories first, then files, alphabetically
    def sort_children(node):
        if node.children is not None:
            node.children.sort(key=lambda c: (0 if c.is_dir else 1, c.name.lower()))
            for child in node.children:
                if child.is_dir:
                    sort_children(child)

    sort_children(root)
    return root


def render_tree(node, prefix="", max_per_dir=10, max_depth=None, depth=0) -> list[str]:
    """Render the tree as a list of strings using box-drawing connectors."""
    lines = []

    if node.children is None:
        return lines

    if max_depth is not None and depth > max_depth:
        return lines

    children = list(node.children)

    # Apply truncation BEFORE drawing connectors
    if len(children) > max_per_dir:
        hidden = len(children) - (max_per_dir - 1)
        children = children[:max_per_dir - 1]
        synthetic = TreeNode(f"... ({hidden} more items)", is_dir=False)
        children.append(synthetic)

    for i, child in enumerate(children):
        is_last = (i == len(children) - 1)
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{child.name}")

        if child.is_dir and child.children is not None:
            extension = "    " if is_last else "│   "
            sub_lines = render_tree(
                child,
                prefix=prefix + extension,
                max_per_dir=max_per_dir,
                max_depth=max_depth,
                depth=depth + 1,
            )
            lines.extend(sub_lines)

    return lines

# ─────────────────────────────────────────────────────────────────────
# ProjectStats
# ─────────────────────────────────────────────────────────────────────

class ProjectStats:
    def __init__(self):
        self.total_files = 0
        self.total_lines = 0
        self.total_chars = 0
        self.languages: dict[str, int] = {}

    def ingest(self, filepath: Path, content: str) -> None:
        """Call once per file, inside the existing read loop."""
        self.total_files += 1
        line_count = content.count('\n')
        if content and not content.endswith('\n'):
            line_count += 1
        self.total_lines += line_count
        self.total_chars += len(content)
        lang = detect_language(filepath.name) or "Other"
        self.languages[lang] = self.languages.get(lang, 0) + 1

    def format_summary(self) -> str:
        sorted_langs = sorted(self.languages.items(), key=lambda x: x[1], reverse=True)
        lang_str = ", ".join(f"{k} ({v})" for k, v in sorted_langs)
        return (
            f"📊 PROJECT SUMMARY\n"
            f"Total Files: {self.total_files} | "
            f"Total Lines: {self.total_lines:,} | "
            f"Total Chars: {self.total_chars:,}\n"
            f"Languages: {lang_str}"
        )

# ─────────────────────────────────────────────────────────────────────
# collect_files (with .codegluerignore support)
# ─────────────────────────────────────────────────────────────────────

def collect_files(
    paths,
    recursive=False,
    respect_gitignore=False,
    exclude_patterns=None,
    include_patterns=None,
):
    """
    Collect files from the given paths, applying filtering and .gitignore rules.

    Returns a list of resolved Path objects, preserving input order and
    with duplicates removed.
    """
    exclude_patterns = list(exclude_patterns or [])   # copy, never mutate caller's list
    include_patterns = list(include_patterns or [])

    # Resolve paths first so we can compute base_dir for .codegluerignore lookup
    resolved_paths = [Path(p).resolve() for p in paths]
    base_dir = _get_common_base(resolved_paths)

    # .codegluerignore injection
    for search_dir in [base_dir, Path.cwd()]:
        gluer_ignore = search_dir / ".codegluerignore"
        if gluer_ignore.exists():
            try:
                with open(gluer_ignore, "r", encoding="utf-8") as f:
                    extra = [ln.strip() for ln in f
                             if ln.strip() and not ln.strip().startswith('#')]
                    exclude_patterns.extend(extra)
            except Exception as e:
                logger.debug(f"Could not parse {gluer_ignore}: {e}")
            break   # stop at first found

    exclude_spec = _build_filter_spec(exclude_patterns)
    include_spec = _build_filter_spec(include_patterns)

    collected = []

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

                if respect_gitignore:
                    gi_file = root_path / ".gitignore"
                    if gi_file.exists():
                        try:
                            with open(gi_file, "r", encoding="utf-8", errors="ignore") as f:
                                spec = pathspec.PathSpec.from_lines('gitignore', f)
                                gitignore_specs[str(root_path)] = spec
                        except Exception as e:
                            logger.debug(f"Could not parse {gi_file}: {e}")

                # Filter directories: exclude patterns and gitignore
                filtered_dirs = []
                for d in dirs:
                    dir_abs = root_path / d
                    try:
                        rel_to_base = str(dir_abs.relative_to(base_dir)).replace("\\", "/")
                    except ValueError:
                        rel_to_base = d

                    if exclude_spec and exclude_spec.match_file(rel_to_base):
                        continue
                    if respect_gitignore and _is_ignored_by_specs(str(dir_abs), gitignore_specs):
                        continue
                    filtered_dirs.append(d)
                dirs[:] = filtered_dirs

                # Process files: include and exclude
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

    # Deduplicate while preserving insertion order (dict is ordered as of Python 3.7+)
    collected = list(dict.fromkeys(collected))
    return collected

# ─────────────────────────────────────────────────────────────────────
# glue_files (with GlueConfig support + backward compatibility)
# ─────────────────────────────────────────────────────────────────────

def glue_files(
    paths,
    config: GlueConfig | None = None,
    # ── Legacy keyword arguments for backward compatibility ──
    output_path=None,
    output_format="plain",
    recursive=False,
    respect_gitignore=False,
    exclude_patterns=None,
    include_patterns=None,
):
    # Ensure paths can be iterated multiple times (e.g., if a generator is passed)
    paths = list(paths)

    # Build config: if config is provided, use it; otherwise build from legacy kwargs
    if config is None:
        config = GlueConfig(
            output_path=output_path,
            output_format=output_format,
            recursive=recursive,
            respect_gitignore=respect_gitignore,
            exclude_patterns=exclude_patterns or [],
            include_patterns=include_patterns or [],
        )

    if config.output_format not in ("plain", "markdown"):
        raise ValueError(f"Invalid output_format: {config.output_format!r}. Must be 'plain' or 'markdown'.")

    if not paths:
        raise NoFilesError("No paths provided.")

    # collect_files resolves everything once and returns resolved Path objects
    file_paths = collect_files(
        paths,
        recursive=config.recursive,
        respect_gitignore=config.respect_gitignore,
        exclude_patterns=config.exclude_patterns,
        include_patterns=config.include_patterns,
    )

    if not file_paths:
        raise NoReadableFilesError("No files could be read after filtering.")

    # Compute output base from first input path to ensure writable location
    resolved_input_paths = [Path(p).resolve() for p in paths]
    first_resolved = resolved_input_paths[0]
    output_base_dir = first_resolved.parent if first_resolved.is_file() else first_resolved
    # Compute display base as common base for relative paths
    display_base_dir = _get_common_base(resolved_input_paths)

    # Priority file sorting
    if config.priority_patterns:
        priority_spec = _build_filter_spec(config.priority_patterns)
        priority_files, normal_files = [], []
        for p in file_paths:
            try:
                rel_str = str(p.relative_to(display_base_dir)).replace("\\", "/")
            except ValueError:
                rel_str = p.name
            if priority_spec.match_file(rel_str):
                priority_files.append(p)
            else:
                normal_files.append(p)
        file_paths = priority_files + normal_files

    output_path = config.output_path
    if output_path is None:
        ext = ".md" if config.output_format == "markdown" else ".txt"
        output_path = str(output_base_dir / f"glued_code{ext}")
        if os.path.exists(output_path):
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            output_path = str(output_base_dir / f"glued_code_{ts}{ext}")

    # Initialise optional accumulators
    stats = ProjectStats() if config.show_stats else None
    sections = []
    slug_counts: dict[str, int] = {}   # for TOC collision avoidance
    anchors: list[tuple[str, str]] = []
    success_count = 0

    for filepath in file_paths:
        if not filepath.is_file():
            logger.warning(f"Skipping '{filepath}' (not a regular file).")
            continue

        # --- display_name (unchanged logic) ---
        try:
            if display_base_dir == Path("/"):
                display_name = str(filepath).replace("\\", "/")
            else:
                display_name = str(filepath.relative_to(display_base_dir)).replace("\\", "/")
        except ValueError:
            display_name = filepath.name

        # --- read file (unchanged logic) ---
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            logger.warning(f"Could not read '{filepath}': {e}")
            continue

        # --- stats (zero overhead when disabled) ---
        if stats:
            stats.ingest(filepath, content)

        # --- build section ---
        if config.output_format == "markdown":
            section = build_markdown_section(display_name, content)

            # TOC anchor — injected BEFORE the section heading, NOT inside the fence
            if config.toc:
                base_slug = "file-" + re.sub(r'[^a-z0-9]+', '-',
                                              display_name.lower()).strip('-')
                count = slug_counts.get(base_slug, 0)
                slug_counts[base_slug] = count + 1
                slug = base_slug if count == 0 else f"{base_slug}-{count}"
                anchors.append((display_name, slug))
                section = f'<a id="{slug}"></a>\n\n' + section
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

    # ── Build header blocks ────────────────────────────────────────────────

    header_blocks: list[str] = []

    # 1. AI system prompt (from string or file)
    ai_prompt_text = config.ai_prompt
    if config.ai_prompt_file:
        try:
            ai_prompt_text = Path(config.ai_prompt_file).read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Could not read ai_prompt_file '{config.ai_prompt_file}': {e}")
    if ai_prompt_text:
        header_blocks.append(f"<system_context>\n{ai_prompt_text.strip()}\n</system_context>")

    # 2. Stats block
    if stats:
        sep = "=" * 50
        header_blocks.append(f"{sep}\n{stats.format_summary()}\n{sep}")

    # 3. Project tree
    if config.show_tree:
        tree_root = build_tree_structure(file_paths, display_base_dir)
        tree_lines = render_tree(
            tree_root,
            max_per_dir=config.tree_max_files,
            max_depth=config.tree_depth,
        )
        header_blocks.append("📂 PROJECT STRUCTURE\n" + "\n".join(tree_lines))

    # 4. Table of Contents (markdown only)
    if config.toc and config.output_format == "markdown" and anchors:
        toc_lines = ["## 📑 Table of Contents\n"]
        for name, slug in anchors:
            toc_lines.append(f"- [{name}](#{slug})")
        header_blocks.append("\n".join(toc_lines))

    # ── Build footer blocks ────────────────────────────────────────────────

    footer_blocks: list[str] = []

    if config.estimate_tokens:
        full_text_preview = "\n\n".join(header_blocks + sections)
        try:
            import tiktoken
            enc = tiktoken.get_encoding("cl100k_base")
            token_count = len(enc.encode(full_text_preview))
            method = "tiktoken"
        except ImportError:
            token_count = int(len(full_text_preview) / 3.0)
            method = "estimated (tiktoken not installed)"

        if token_count < 8_000:
            tier = "Small — fits all models"
        elif token_count < 32_000:
            tier = "Medium — fits most modern models"
        elif token_count < 128_000:
            tier = "Large — requires long-context models"
        else:
            tier = "Very Large — consider splitting"

        sep = "=" * 50
        footer_blocks.append(
            f"{sep}\n"
            f"🧠 Token Estimate: ~{token_count:,} ({method})\n"
            f"Context Size: {tier}\n"
            f"{sep}"
        )

    # ── Final assembly ─────────────────────────────────────────────────────

    all_blocks = header_blocks + sections + footer_blocks
    sep_char = "\n\n" if config.output_format == "markdown" else "\n"
    glued_content = sep_char.join(all_blocks)

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(glued_content)
    except Exception as e:
        raise OutputWriteError(f"Could not write output file: {e}") from e

    return output_path, success_count
