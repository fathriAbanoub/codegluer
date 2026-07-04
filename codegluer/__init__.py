"""CodeGluer - Glue multiple code files into a single document."""
__version__ = '1.0.0'

from .core import (
    SEPARATOR_CHAR,
    SEPARATOR_LENGTH,
    EXT_TO_LANG,
    # FIX (2026-07-04): OOM/freeze guard constants — must stay exported
    # alongside the others above, same reasoning as their definition in core.py.
    DEFAULT_IGNORE_DIR_NAMES,
    DEFAULT_MAX_TOTAL_BYTES,
    CodeGluerError,
    NoFilesError,
    NoReadableFilesError,
    OutputWriteError,
    GlueConfig,
    build_header,
    build_footer,
    build_markdown_section,
    detect_language,
    sanitize_filename_for_markdown,
    TreeNode,
    build_tree_structure,
    render_tree,
    ProjectStats,
    collect_files,
    glue_files,
)

__all__ = [
    "__version__",
    "SEPARATOR_CHAR",
    "SEPARATOR_LENGTH",
    "EXT_TO_LANG",
    # FIX (2026-07-04): keep paired with the import block above.
    "DEFAULT_IGNORE_DIR_NAMES",
    "DEFAULT_MAX_TOTAL_BYTES",
    "CodeGluerError",
    "NoFilesError",
    "NoReadableFilesError",
    "OutputWriteError",
    "GlueConfig",
    "build_header",
    "build_footer",
    "build_markdown_section",
    "detect_language",
    "sanitize_filename_for_markdown",
    "TreeNode",
    "build_tree_structure",
    "render_tree",
    "ProjectStats",
    "collect_files",
    "glue_files",
]