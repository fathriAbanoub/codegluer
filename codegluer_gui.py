#!/usr/bin/env python3
"""
CodeGluer GUI — GTK4 file-manager integration.

Right-click selected files/folders in Nautilus or Nemo, choose "CodeGluer"
from the scripts/actions menu, configure options in a native GTK4 dialog,
and glue them into a single file via the `codegluer` CLI.

Architecture:
    - build_command() is pure logic, no GTK. Tested by test_codegluer_gui.py.
    - CodeGluerWindow is the GTK4 UI. Hard to test (needs display), so kept thin.
    - Theme persistence in ~/.config/codegluer/theme (one line: auto|light|dark|roselle).

Usage:
    codegluer_gui.py <file1> [file2] ...        # from file manager
    codegluer_gui.py --dry-run <file1> ...       # print cmd, don't run
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

# ----------------------------------------------------------------------
# Debug flag – set CODEGLUER_DEBUG=1 to see verbose prints
# ----------------------------------------------------------------------
DEBUG = os.getenv("CODEGLUER_DEBUG", "").lower() in ("1", "true", "yes")

def debug_print(*args, **kwargs):
    if DEBUG:
        print(*args, file=sys.stderr, **kwargs)


CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))) / "codegluer"
CONFIG_FILE = CONFIG_DIR / "theme"

# FIX (2026-07-04): freeze bug — opening the Browse file picker with its
# initial folder pointed at a directory containing node_modules/.next/etc.
# made the native GTK/portal file dialog try to enumerate and thumbnail
# everything in it, hanging so badly a full system restart was required
# (confirmed via journalctl — no clean OOM-kill, i.e. swap-thrash-to-freeze,
# not a normal crash). _looks_heavy() below is the guard against this.
# Do not remove it or re-add an unconditional set_initial_folder/
# set_current_folder call using self.target_dir.
#
# Mirrors codegluer.core.DEFAULT_IGNORE_DIR_NAMES, duplicated (not imported) so
# this script keeps working standalone in ~/.local/bin without the package
# import path. Used only to avoid pointing a file dialog's initial folder at
# something that will make it hang while enumerating/thumbnailing.
_HEAVY_DIR_HINTS = {
    "node_modules", ".git", ".next", ".nuxt", "dist", "build",
    "__pycache__", ".venv", "venv", "target", ".cache", "vendor",
}


def _looks_heavy(path: str, scan_limit: int = 500) -> bool:
    """Cheap heuristic, not a full walk: does this directory contain a known
    dependency/build folder, or an unusually large number of direct entries?
    Opening a native file picker's initial folder inside something like
    node_modules is a known way to freeze GTK file choosers while they
    enumerate and thumbnail everything — this just avoids that trigger."""
    try:
        with os.scandir(path) as it:
            count = 0
            for entry in it:
                count += 1
                if entry.name in _HEAVY_DIR_HINTS and entry.is_dir():
                    return True
                if count > scan_limit:
                    return True
    except OSError:
        return False
    return False


# ──────────────────────────────────────────────────────────────────────
# Pure logic: command builder. No GTK. Fully testable.
# ──────────────────────────────────────────────────────────────────────

def default_name(target_dir: str, fmt: str, existing: set | None = None) -> str:
    """Collision-safe default filename. Glued_Code.md → Glued_Code_1.md → ..."""
    ext = "txt" if fmt == "plain" else "md"
    base = "Glued_Code"
    if existing is None:
        existing = set(os.listdir(target_dir)) if os.path.isdir(target_dir) else set()
    name = f"{base}.{ext}"
    i = 1
    while name in existing:
        name = f"{base}_{i}.{ext}"
        i += 1
        if i > 99:
            name = f"{base}_{os.getpid()}.{ext}"
            break
    return name


def is_any_dir(files: list[str]) -> bool:
    # Treat .zip files as directories (they are expanded and glued recursively)
    return any(os.path.isdir(f) or str(f).lower().endswith(".zip") for f in files)


def target_dir_of(files: list[str]) -> str:
    """Directory where output should land. '.' for bare filenames."""
    if not files:
        return "."
    parent = os.path.dirname(files[0])
    return parent if parent else "."


# ──────────────────────────────────────────────────────────────────────
# Scope enforcement (FIX 2026-07-09: exclude-outside-sel bug)
#
# The exclude feature MUST only operate on files that could actually be
# glued. Without this, the Browse picker lets you select /etc/passwd and
# silently turns it into a `--exclude passwd` glob that strips every file
# named `passwd` from your project. We now compute an explicit "scope"
# (the set of allowed root directories derived from the selection) and
# reject any exclude pattern or picked path that falls outside it.
#
# Zips are deliberately NOT scope roots — their contents are unknown to
# the GUI until the CLI extracts them, so file-picking is meaningless
# for zip inputs. The Browse button is hidden when the scope is empty.
# ──────────────────────────────────────────────────────────────────────

def compute_scope_roots(files: list[str]) -> list[str]:
    """Return the list of absolute directory paths that form the operation
    scope. Only real selected directories count — zip inputs are excluded
    (contents unknown to the GUI), and bare selected files contribute
    nothing (you can only exclude what's actually being glued; for a
    bare file, that's just the file itself — there's nothing to browse).
    """
    roots: list[str] = []
    seen: set[str] = set()
    for f in files:
        if str(f).lower().endswith(".zip"):
            continue
        try:
            p = os.path.realpath(os.path.expanduser(f))
        except OSError:
            continue
        if os.path.isdir(p) and p not in seen:
            seen.add(p)
            roots.append(p)
    return roots


def is_path_in_scope(path: str, scope_roots: list[str]) -> bool:
    """True if `path` resolves to a location inside one of `scope_roots`."""
    if not scope_roots:
        return False
    try:
        resolved = os.path.realpath(os.path.expanduser(path))
    except OSError:
        return False
    for root in scope_roots:
        try:
            root_resolved = os.path.realpath(root)
        except OSError:
            continue
        if resolved == root_resolved:
            return True
        # Path-is-prefix check, with explicit separator to defeat
        # /home/foo vs /home/foobar style confusion.
        if resolved.startswith(root_resolved + os.sep):
            return True
    return False


def relative_to_scope(path: str, scope_roots: list[str]) -> str | None:
    """Return `path` made relative to whichever scope root contains it.
    Returns None if the path is not in any scope root."""
    try:
        resolved = os.path.realpath(os.path.expanduser(path))
    except OSError:
        return None
    best_root = None
    best_rel = None
    for root in scope_roots:
        try:
            root_resolved = os.path.realpath(root)
        except OSError:
            continue
        try:
            rel = os.path.relpath(resolved, root_resolved)
        except ValueError:
            continue
        if rel == ".":
            # Path is the root itself — nothing meaningful to exclude.
            continue
        if rel.startswith(".."):
            continue
        # Pick the longest root (most specific) so the chip shows the
        # tightest relative path.
        if best_root is None or len(root_resolved) > len(best_root):
            best_root = root_resolved
            best_rel = rel
    return best_rel


def validate_exclude_pattern(pattern: str, scope_roots: list[str]) -> tuple[bool, str, str]:
    """Validate a manually-typed or picked exclude pattern.

    Returns (ok, cleaned_pattern, error_message).

    Rules:
      1. Strip whitespace, leading `./`, trailing `/`.
      2. Reject empty.
      3. Reject absolute paths (starts with `/` or resolves to one). The
         GUI has no business excluding absolute filesystem paths — they
         can only ever be a user mistake.
      4. Reject user-home paths (`~...`).
      5. Reject `..` traversals that escape all scope roots.
      6. If the pattern is a real path inside scope, return it as a
         relative path so the chip matches what the user actually picked.
      7. Otherwise (pure glob like `*.py`, `node_modules`, `**/*.log`),
         accept as-is. These can only match inside the input set anyway.
    """
    raw = pattern.strip()
    if raw.startswith("./"):
        raw = raw[2:]
    if raw.endswith("/"):
        raw = raw[:-1]
    if not raw:
        return False, "", "Pattern is empty."

    # Reject obvious absolute / home references up front.
    if raw.startswith("/") or raw.startswith("~"):
        return False, "", (
            f"Absolute paths are not allowed as exclude patterns "
            f"(got {raw!r}). Excludes only apply to files inside the "
            f"selected directory or zip."
        )

    # If the pattern contains path separators OR starts with `..`, it can
    # only be meaningful as a path relative to a scope root. With no scope
    # roots (zip-only selection) there's nothing to anchor against, so
    # reject — the user must type a plain glob without separators instead.
    if os.sep in raw or "/" in raw or raw.startswith(".."):
        if not scope_roots:
            return False, "", (
                f"Pattern {raw!r} contains a path separator or '..', "
                f"but this selection has no browsable scope — only plain "
                f"glob patterns without '/' are allowed here."
            )
        # Try interpreting it as a path relative to each scope root.
        # If it resolves outside all of them, reject.
        in_scope = False
        for root in scope_roots:
            candidate = os.path.realpath(os.path.join(root, raw))
            if is_path_in_scope(candidate, [root]):
                in_scope = True
                break
        if not in_scope:
            return False, "", (
                f"Pattern {raw!r} resolves outside the selected "
                f"directory or zip. Excludes can only target files "
                f"inside the selection."
            )
        # Normalize to forward slashes for pathspec consistency.
        cleaned = raw.replace(os.sep, "/")
        return True, cleaned, ""

    # Pure name/glob pattern (no separators, no `..`). Accept as-is.
    return True, raw, ""



def should_update_default(current_text: str, target_dir: str) -> bool:
    """True if the output field still holds a default value (or is empty),
    meaning a format switch may safely update the extension. False if the
    user typed a custom name that should be preserved."""
    default_md = default_name(target_dir, "markdown")
    default_txt = default_name(target_dir, "plain")
    return current_text in (default_md, default_txt, "")


def build_command(files: list[str], opts: dict) -> list[str]:
    """
    Build the codegluer CLI command from user options.

    opts keys:
        format: 'plain' | 'markdown'
        output: str (filename, empty = default)
        excludes: str (comma-separated patterns)
        stats, estimate_tokens, tree, toc, respect_gitignore: bool
        any_dir: bool (precomputed, drives -r and dir-only flags)
        target_dir: str (where output lands)
    """
    any_dir = opts.get("any_dir", is_any_dir(files))
    target_dir = opts.get("target_dir") or target_dir_of(files)

    fmt = opts.get("format", "plain")
    output = opts.get("output", "").strip()
    if not output:
        output = default_name(target_dir, fmt)

    cmd = ["codegluer", *files]
    cmd += ["--format", fmt]
    if any_dir:
        cmd += ["-r"]
    if opts.get("tree") and any_dir:
        cmd += ["--tree"]
    if opts.get("stats"):
        cmd += ["--stats"]
    if opts.get("toc") and any_dir and fmt == "markdown":
        cmd += ["--toc"]
    if opts.get("estimate_tokens"):
        cmd += ["--estimate-tokens"]
    if opts.get("respect_gitignore") and any_dir:
        cmd += ["--respect-gitignore"]

    excludes = opts.get("excludes", "").strip()
    if excludes:
        for pat in excludes.split(","):
            pat = pat.strip()
            if pat:
                cmd += ["--exclude", pat]

    cmd += ["-o", os.path.join(target_dir, output)]
    return cmd


# ──────────────────────────────────────────────────────────────────────
# Theme management
# ──────────────────────────────────────────────────────────────────────

# Dropdown shows "auto" (placeholder, grays Apply) + real themes (enable Apply).
# "auto" means "follow GTK" — it's in the dropdown as text but acts as no-selection.
THEMES = ["auto", "light", "dark", "roselle"]
REAL_THEMES = ["light", "dark", "roselle"]  # only these enable the Apply button

def read_theme() -> str:
    try:
        t = CONFIG_FILE.read_text().strip()
        if t in THEMES:
            return t
    except (OSError, FileNotFoundError):
        pass
    return "auto"


def save_theme(theme: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(theme)


# ─── CSS ─────────────────────────────────────────────────────────────
# Structural styles (no colors) – colors defined per theme below.
CHIP_CSS_BASE = """
    .chip {
        border-radius: 11px;
        padding: 2px 4px 2px 10px;
    }
    .chip-close {
        background: transparent;
        border-radius: 50%;
        min-width: 18px;
        min-height: 18px;
        padding: 0;
        margin: 0;
        box-shadow: none;
        outline: none;
    }
    .chip-close:hover { background: rgba(255, 255, 255, 0.25); }
    .chip-close:active { background: rgba(255, 255, 255, 0.4); }
    flowboxchild {
        outline: none;
        background: transparent;
        padding: 0;
        border-radius: 11px;
    }
"""

THEME_CSS = {
    "light": """
        window { background: #ffffff; color: #333333; }
        entry { background: #f9f9f9; border: 1px solid #ddd; border-radius: 3px; padding: 4px; color: #333333; }
        checkbutton { color: #333333; }
        dropdown { background: #f9f9f9; border: 1px solid #ddd; border-radius: 3px; }
        button.suggested-action { background: #C62734; color: white; border-radius: 4px; }
        button { padding: 6px 12px; border-radius: 4px; }
        .chip-box { background: #f9f9f9; border: 1px solid #ddd; border-radius: 3px; padding: 6px; }
        .chip { background: #1e3a5f; }
        .chip label { color: #ffffff; }
        .chip-close { color: #ffffff; }
    """,
    "dark": """
        window { background: #2b2b2b; color: #e0e0e0; }
        entry { background: #3a3a3a; border: 1px solid #555; border-radius: 3px; padding: 4px; color: #e0e0e0; }
        checkbutton { color: #e0e0e0; }
        dropdown { background: #3a3a3a; border: 1px solid #555; border-radius: 3px; }
        button.suggested-action { background: #E87672; color: #1a1a1a; border-radius: 4px; }
        button { padding: 6px 12px; border-radius: 4px; }
        .chip-box { background: #3a3a3a; border: 1px solid #555; border-radius: 3px; padding: 6px; }
        .chip { background: #4a6fa5; }
        .chip label { color: #ffffff; }
        .chip-close { color: #ffffff; }
    """,
    "roselle": """
        window { background: #1a0a0a; color: #f0d0d0; }
        entry { background: #2a1515; border: 1px solid #C62734; border-radius: 3px; padding: 4px; color: #f0d0d0; }
        checkbutton { color: #f0d0d0; }
        dropdown { background: #2a1515; border: 1px solid #C62734; border-radius: 3px; }
        button.suggested-action { background: #C62734; color: #fff0f0; border-radius: 4px; }
        button { padding: 6px 12px; border-radius: 4px; }
        .chip-box { background: #2a1515; border: 1px solid #C62734; border-radius: 3px; padding: 6px; }
        .chip { background: #C62734; }
        .chip label { color: #fff0f0; }
        .chip-close { color: #fff0f0; }
    """,
}

def resolve_theme(theme: str) -> str:
    """auto → light/dark via GTK; explicit themes pass through."""
    if theme != "auto":
        return theme
    try:
        result = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
            capture_output=True, text=True, timeout=3
        )
        gtk_theme = result.stdout.strip().strip("'")
        return "dark" if "dark" in gtk_theme.lower() else "light"
    except Exception:
        return "light"


def theme_css(theme: str) -> str:
    resolved = resolve_theme(theme)
    return CHIP_CSS_BASE + THEME_CSS.get(resolved, "")


# ──────────────────────────────────────────────────────────────────────
# GTK4 GUI
# ──────────────────────────────────────────────────────────────────────

def run_gui(files: list[str], dry_run: bool = False) -> None:
    """Launch the GTK4 dialog. Returns the built command via dry_run or executes it."""
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, Gio, GLib, Gdk, Pango

    any_dir = is_any_dir(files)
    target_dir = target_dir_of(files)

    class CodeGluerWindow(Gtk.ApplicationWindow):
        def __init__(self, app):
            super().__init__(application=app, title="CodeGluer")
            self.set_default_size(480, -1)

            self.files = files
            self.any_dir = any_dir
            self.target_dir = target_dir
            self.dry_run = dry_run
            self.current_theme = read_theme()

            # FIX (2026-07-09): operation scope — the set of directories
            # the exclude feature is allowed to operate on. Empty for
            # zip-only inputs, which disables the Browse button.
            self.scope_roots = compute_scope_roots(files)

            # State
            self.format = "markdown"
            self.output_entry = None
            self.excludes_entry = None
            self.manual_exclude_entry = None
            self.chip_flowbox = None
            self.excludes: list[str] = []
            self.format_dropdown = None
            self.theme_dropdown = None
            self.checkboxes = {}

            self._css_provider = None
            self._active_picker = None

            self._build_ui()
            self._apply_theme(self.current_theme)

        def _build_ui(self):
            main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            self.set_child(main_box)

            header = Gtk.HeaderBar()
            self.set_titlebar(header)

            cancel_btn = Gtk.Button(label="Cancel")
            cancel_btn.connect("clicked", lambda *_: self.close())
            header.pack_start(cancel_btn)

            glue_btn = Gtk.Button(label="Glue!")
            glue_btn.add_css_class("suggested-action")
            glue_btn.connect("clicked", self._on_glue)
            header.pack_end(glue_btn)

            self.apply_theme_btn = Gtk.Button(label="Apply Theme")
            self.apply_theme_btn.connect("clicked", self._on_apply_theme)
            self.apply_theme_btn.set_sensitive(False)
            header.pack_end(self.apply_theme_btn)

            content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            content.set_margin_start(16)
            content.set_margin_end(16)
            content.set_margin_top(12)
            content.set_margin_bottom(16)
            main_box.append(content)

            info = Gtk.Label(label=f"Glue {len(self.files)} item(s)  →  {self.target_dir}")
            info.set_halign(Gtk.Align.START)
            info.set_use_markup(True)
            content.append(info)

            # If the scope is empty (e.g. zip-only selection), warn the
            # user that Browse is disabled and excludes must be typed.
            if self.any_dir and not self.scope_roots:
                scope_warn = Gtk.Label(
                    label=(
                        "<i>Zip inputs can't be browsed — type exclude "
                        "patterns manually (e.g. <tt>node_modules</tt>, "
                        "<tt>*.log</tt>).</i>"
                    )
                )
                scope_warn.set_use_markup(True)
                scope_warn.set_halign(Gtk.Align.START)
                content.append(scope_warn)

            grid = Gtk.Grid()
            grid.set_row_spacing(8)
            grid.set_column_spacing(12)
            content.append(grid)

            row = 0

            # Output filename
            grid.attach(Gtk.Label(label="Output filename:", halign=Gtk.Align.END), 0, row, 1, 1)
            default = default_name(self.target_dir, self.format)
            self.output_entry = Gtk.Entry()
            self.output_entry.set_text(default)
            self.output_entry.set_hexpand(True)
            self.output_entry.connect("changed", self._on_output_changed)
            self._user_modified_output = False
            grid.attach(self.output_entry, 1, row, 1, 1)
            row += 1

            # Exclude patterns — only show when directories or zips are selected
            if self.any_dir:
                grid.attach(Gtk.Label(label="Exclude:", halign=Gtk.Align.END, valign=Gtk.Align.START), 0, row, 1, 1)
                exclude_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                exclude_row.set_hexpand(True)
                exclude_row.set_valign(Gtk.Align.START)
                exclude_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                exclude_box.add_css_class("chip-box")
                exclude_box.set_hexpand(True)
                exclude_row.append(exclude_box)
                self.chip_flowbox = Gtk.FlowBox()
                self.chip_flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
                self.chip_flowbox.set_max_children_per_line(20)
                self.chip_flowbox.set_min_children_per_line(1)
                self.chip_flowbox.set_column_spacing(4)
                self.chip_flowbox.set_row_spacing(4)
                self.chip_flowbox.set_visible(False)
                exclude_box.append(self.chip_flowbox)
                self.manual_exclude_entry = Gtk.Entry()
                self.manual_exclude_entry.set_placeholder_text(
                    "Type a pattern and press Enter, or click Browse…"
                )
                self.manual_exclude_entry.set_hexpand(True)
                self.manual_exclude_entry.connect("activate", self._on_manual_exclude_activate)
                exclude_box.append(self.manual_exclude_entry)
                browse_btn = Gtk.Button(label="Browse…")
                browse_btn.set_tooltip_text("Select files to exclude")
                browse_btn.set_valign(Gtk.Align.CENTER)
                browse_btn.connect("clicked", self._on_browse_clicked)
                # FIX (2026-07-09): disable Browse when there is no scope
                # to browse (zip-only inputs). The picker would otherwise
                # land in the zip's parent dir, which has nothing to do
                # with the zip's contents.
                if not self.scope_roots:
                    browse_btn.set_sensitive(False)
                    browse_btn.set_tooltip_text(
                        "Browse is disabled for zip-only selections — "
                        "type patterns manually instead."
                    )
                exclude_row.append(browse_btn)
                grid.attach(exclude_row, 1, row, 1, 1)
                row += 1

            # Format dropdown
            grid.attach(Gtk.Label(label="Format:", halign=Gtk.Align.END), 0, row, 1, 1)
            fmt_model = Gtk.StringList.new(["markdown", "plain"])
            self.format_dropdown = Gtk.DropDown(model=fmt_model)
            self.format_dropdown.connect("notify::selected", self._on_format_changed)
            grid.attach(self.format_dropdown, 1, row, 1, 1)
            row += 1

            # Theme dropdown
            grid.attach(Gtk.Label(label="Theme:", halign=Gtk.Align.END), 0, row, 1, 1)
            theme_model = Gtk.StringList.new(THEMES)
            self.theme_dropdown = Gtk.DropDown(model=theme_model)
            self.theme_dropdown.set_selected(THEMES.index(self.current_theme))
            self.theme_dropdown.connect("notify::selected", self._on_theme_dropdown_changed)
            grid.attach(self.theme_dropdown, 1, row, 1, 1)
            row += 1

            sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            content.append(sep)

            checks_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            content.append(checks_box)

            self.checkboxes["stats"] = Gtk.CheckButton(label="Stats")
            checks_box.append(self.checkboxes["stats"])

            self.checkboxes["estimate_tokens"] = Gtk.CheckButton(label="Estimate tokens")
            checks_box.append(self.checkboxes["estimate_tokens"])

            if self.any_dir:
                self.checkboxes["tree"] = Gtk.CheckButton(label="Tree")
                checks_box.append(self.checkboxes["tree"])
                self.checkboxes["toc"] = Gtk.CheckButton(label="TOC (markdown only)")
                checks_box.append(self.checkboxes["toc"])
                self.checkboxes["respect_gitignore"] = Gtk.CheckButton(label="Respect .gitignore")
                checks_box.append(self.checkboxes["respect_gitignore"])

        def _on_output_changed(self, entry):
            self._user_modified_output = not should_update_default(
                entry.get_text(), self.target_dir
            )

        def _on_format_changed(self, dropdown, _param):
            selected = dropdown.get_selected()
            self.format = ["markdown", "plain"][selected]
            if not self._user_modified_output:
                self.output_entry.set_text(
                    default_name(self.target_dir, self.format)
                )
            if self.format == "plain" and "toc" in self.checkboxes:
                self.checkboxes["toc"].set_active(False)

        def _on_theme_dropdown_changed(self, dropdown, _param):
            selected = THEMES[dropdown.get_selected()]
            self.apply_theme_btn.set_sensitive(selected in REAL_THEMES)

        def _on_apply_theme(self, _btn):
            selected = self.theme_dropdown.get_selected()
            new_theme = THEMES[selected]
            self.current_theme = new_theme
            save_theme(new_theme)
            self._apply_theme(new_theme)
            self.apply_theme_btn.set_sensitive(False)

        def _apply_theme(self, theme):
            css_text = theme_css(theme)
            if not css_text:
                return
            display = Gdk.Display.get_default()
            if self._css_provider:
                Gtk.StyleContext.remove_provider_for_display(display, self._css_provider)
            self._css_provider = Gtk.CssProvider()
            self._css_provider.load_from_data(css_text.encode())
            Gtk.StyleContext.add_provider_for_display(
                display,
                self._css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

        def _collect_opts(self):
            excludes_list = list(self.excludes)
            if self.manual_exclude_entry is not None:
                pending = self.manual_exclude_entry.get_text().strip()
                if pending and pending not in excludes_list:
                    excludes_list.append(pending)
            opts = {
                "format": self.format,
                "output": self.output_entry.get_text(),
                "excludes": ", ".join(excludes_list),
                "stats": self.checkboxes["stats"].get_active(),
                "estimate_tokens": self.checkboxes["estimate_tokens"].get_active(),
                "any_dir": self.any_dir,
                "target_dir": self.target_dir,
            }
            if self.any_dir:
                opts["tree"] = self.checkboxes["tree"].get_active()
                opts["toc"] = self.checkboxes["toc"].get_active()
                opts["respect_gitignore"] = self.checkboxes["respect_gitignore"].get_active()
            return opts

        def _on_glue(self, _btn):
            if self.manual_exclude_entry is not None:
                pending = self.manual_exclude_entry.get_text().strip()
                if pending:
                    self._add_exclude_chip(pending)
                    self.manual_exclude_entry.set_text("")
            opts = self._collect_opts()
            self._execute(opts)

        # ── Exclude chips ────────────────────────────────────────────────

        def _validate_and_clean_pattern(self, text: str) -> tuple[bool, str, str]:
            """Wrap validate_exclude_pattern() with this window's scope_roots."""
            return validate_exclude_pattern(text, self.scope_roots)

        def _create_and_insert_chip(self, normalized: str) -> None:
            """Append `normalized` to self.excludes and insert its chip widget.
            Caller is responsible for dedup check — both callers have
            different dedup behavior (typed-entry logs+skips, picked-path
            returns idempotent success), so dedup stays in the callers.
            Raises whatever GTK raises; callers wrap in their own try/except."""
            self.excludes.append(normalized)
            chip = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            chip.add_css_class("chip")
            chip.set_halign(Gtk.Align.START)
            chip.set_valign(Gtk.Align.CENTER)
            label = Gtk.Label(label=normalized)
            label.set_max_width_chars(30)
            label.set_ellipsize(Pango.EllipsizeMode.END)
            label.set_tooltip_text(normalized)
            chip.append(label)
            close_btn = Gtk.Button(label="✕")
            close_btn.add_css_class("chip-close")
            close_btn.set_tooltip_text(f"Remove {normalized}")
            close_btn.connect(
                "clicked",
                lambda *_: self._remove_exclude_chip(normalized, chip),
            )
            chip.append(close_btn)
            self.chip_flowbox.insert(chip, -1)
            self.chip_flowbox.set_visible(True)

        def _add_exclude_chip(self, text: str) -> None:
            ok, normalized, err = self._validate_and_clean_pattern(text)
            debug_print(
                f"[CodeGluer] _add_exclude_chip({text!r}) -> "
                f"ok={ok}, normalized={normalized!r}, err={err!r}"
            )
            if not ok:
                debug_print(f"[CodeGluer]   rejected: {err}")
                self._show_error_dialog("Invalid exclude pattern", err)
                return
            if not normalized:
                debug_print("[CodeGluer]   skipped: empty after normalization")
                return
            if normalized in self.excludes:
                debug_print("[CodeGluer]   skipped: duplicate")
                return
            try:
                self._create_and_insert_chip(normalized)
                debug_print(f"[CodeGluer]   added. total excludes now: {len(self.excludes)}")
            except Exception as e:
                import traceback
                debug_print(traceback.format_exc())
                self._show_error_dialog("Failed to add exclude chip", str(e))

        def _add_picked_path_as_chip(self, gfile) -> tuple[bool, str]:
            """Convert a picked GFile into a scope-relative exclude chip.

            Returns (accepted, reason). When accepted, the chip is added
            and the relative path is returned. When rejected, reason
            explains why (path outside scope, etc.).
            """
            try:
                path = gfile.get_path()  # absolute local path, or None
            except Exception:
                path = None
            if not path:
                # Fallback: basename only. We can't scope-check it, so be
                # conservative and reject — forces the user to type the
                # pattern manually so they see what they're doing.
                return False, "Selected file has no local path (remote or invalid)."
            if not is_path_in_scope(path, self.scope_roots):
                return False, (
                    f"{path} is outside the selected directory or zip. "
                    f"Excludes can only target files inside the selection."
                )
            rel = relative_to_scope(path, self.scope_roots)
            if not rel:
                return False, f"{path} could not be made relative to the selection."
            # We already proved scope membership with realpath, so bypass
            # validate_exclude_pattern's glob-only assumption for slash-containing
            # relative paths.
            normalized = rel.replace(os.sep, "/")
            if normalized in self.excludes:
                return True, normalized  # idempotent
            try:
                self._create_and_insert_chip(normalized)
            except Exception as e:
                return False, f"Failed to add chip: {e}"
            return True, normalized

        def _remove_exclude_chip(self, text: str, chip_widget) -> None:
            """Remove a chip widget and its pattern from the excludes list."""
            if text in self.excludes:
                self.excludes.remove(text)
            parent = chip_widget.get_parent()
            try:
                self.chip_flowbox.remove(parent)
            except Exception:
                try:
                    self.chip_flowbox.remove(chip_widget)
                except Exception:
                    pass
            # FIX (2026-07-04): Do NOT hide the flowbox when empty.
            # The reflow path has caused chips to silently not appear after
            # the first add (see comment in _add_exclude_chip). Keeping the
            # flowbox visible even when empty avoids that weird state.
            # if not self.excludes: self.chip_flowbox.set_visible(False)

        def _on_manual_exclude_activate(self, entry) -> None:
            text = entry.get_text().strip()
            if text:
                self._add_exclude_chip(text)
                entry.set_text("")

        # ── Browse button ──────────────────────────────────────────────────

        def _on_browse_clicked(self, _btn) -> None:
            gtk_version = (Gtk.get_major_version(), Gtk.get_minor_version())
            debug_print(f"[CodeGluer] Browse clicked. GTK={gtk_version[0]}.{gtk_version[1]}, "
                        f"has FileDialog={hasattr(Gtk, 'FileDialog')}")
            try:
                if self._try_open_file_dialog():
                    return
                self._open_file_chooser_dialog()
            except Exception as e:
                import traceback
                debug_print(traceback.format_exc())
                self._show_error_dialog(
                    "Could not open file picker",
                    f"{type(e).__name__}: {e}",
                )

        def _show_error_dialog(self, message: str, detail: str = "") -> None:
            gtk_version = (Gtk.get_major_version(), Gtk.get_minor_version())
            if gtk_version >= (4, 10):
                d = Gtk.AlertDialog()
                d.set_message(message)
                d.set_detail(detail) if detail else None
                d.set_buttons(["OK"])
                d.show(self)
            else:
                d = Gtk.MessageDialog(
                    transient_for=self,
                    modal=True,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    text=message,
                )
                if detail:
                    d.set_secondary_text(detail)
                d.connect("response", lambda *_: d.destroy())
                d.present()

        def _try_open_file_dialog(self) -> bool:
            gtk_version = (Gtk.get_major_version(), Gtk.get_minor_version())
            if gtk_version < (4, 10):
                return False
            if not hasattr(Gtk, "FileDialog"):
                return False
            self._open_file_dialog()
            return True

        def _open_file_dialog(self) -> None:
            dialog = Gtk.FileDialog()
            dialog.set_title("Select files to exclude")
            dialog.set_modal(True)
            # FIX (2026-07-09): point the picker at a scope root, not at
            # the zip's parent dir. If there are multiple roots we pick
            # the first; the user can still navigate to siblings from
            # there. Out-of-scope picks are rejected in the response
            # callback regardless.
            initial_folder = self.scope_roots[0] if self.scope_roots else None
            try:
                if initial_folder and os.path.isdir(initial_folder) \
                        and not _looks_heavy(initial_folder):
                    dialog.set_initial_folder(Gio.File.new_for_path(initial_folder))
            except Exception:
                pass
            self._active_picker = dialog
            dialog.open_multiple(self, None, self._on_file_dialog_response)

        def _on_file_dialog_response(self, dialog, result) -> None:
            debug_print("[CodeGluer] FileDialog response callback fired")
            self._active_picker = None
            try:
                files = dialog.open_multiple_finish(result)
            except Exception as e:
                debug_print(f"[CodeGluer] open_multiple_finish raised: "
                            f"{type(e).__module__}.{type(e).__name__}: {e}")
                return
            debug_print(f"[CodeGluer] open_multiple_finish returned: {files!r}")
            if files is None:
                debug_print("[CodeGluer] files is None — bailing")
                return
            try:
                n = files.get_n_items()
                debug_print(f"[CodeGluer] number of items selected: {n}")
            except Exception as e:
                debug_print(f"[CodeGluer] get_n_items() failed: {e}")
                return
            if n == 0:
                debug_print("[CodeGluer] no items selected — bailing")
                return
            rejected: list[str] = []
            try:
                for i in range(n):
                    gfile = files.get_item(i)
                    if gfile is None:
                        debug_print(f"[CodeGluer]   item {i} is None")
                        continue
                    ok, info = self._add_picked_path_as_chip(gfile)
                    if ok:
                        debug_print(f"[CodeGluer]   item {i}: accepted as {info!r}")
                    else:
                        rejected.append(info)
                        debug_print(f"[CodeGluer]   item {i}: rejected ({info})")
            except Exception as e:
                import traceback
                debug_print(traceback.format_exc())
                self._show_error_dialog("Failed to process selected files", str(e))
                return
            if rejected:
                # Tell the user which picks were thrown out and why.
                summary = "\n".join(f"• {r}" for r in rejected[:10])
                if len(rejected) > 10:
                    summary += f"\n… and {len(rejected) - 10} more."
                self._show_error_dialog(
                    f"Rejected {len(rejected)} of {n} pick(s)",
                    (
                        "Only files inside the selected directory or zip "
                        "can be excluded.\n\n" + summary
                    ),
                )

        def _open_file_chooser_dialog(self) -> None:
            dialog = Gtk.FileChooserNative.new(
                title="Select files to exclude",
                parent=self,
                action=Gtk.FileChooserAction.OPEN,
                accept_label="_Select",
                cancel_label="_Cancel",
            )
            dialog.set_select_multiple(True)
            initial_folder = self.scope_roots[0] if self.scope_roots else None
            try:
                if initial_folder and os.path.isdir(initial_folder) \
                        and not _looks_heavy(initial_folder):
                    dialog.set_current_folder(Gio.File.new_for_path(initial_folder))
            except Exception:
                pass
            dialog.connect("response", self._on_file_chooser_response)
            self._active_picker = dialog
            dialog.show()

        def _on_file_chooser_response(self, dialog, response) -> None:
            debug_print(f"[CodeGluer] FileChooserNative response: {response}")
            self._active_picker = None
            accepted = response in (
                Gtk.ResponseType.ACCEPT,
                Gtk.ResponseType.OK,
            )
            debug_print(f"[CodeGluer] accepted={accepted}")
            if accepted:
                try:
                    files = dialog.get_files()
                    debug_print(f"[CodeGluer] get_files() returned: {files!r}")
                except Exception as e:
                    debug_print(f"[CodeGluer] get_files() raised: {e}")
                    files = None
                if files is None:
                    debug_print("[CodeGluer] files is None — bailing")
                else:
                    try:
                        n = files.get_n_items()
                        debug_print(f"[CodeGluer] number of items selected: {n}")
                        rejected: list[str] = []
                        for i in range(n):
                            gfile = files.get_item(i)
                            if gfile is None:
                                continue
                            ok, info = self._add_picked_path_as_chip(gfile)
                            if ok:
                                debug_print(f"[CodeGluer]   item {i}: accepted as {info!r}")
                            else:
                                rejected.append(info)
                                debug_print(f"[CodeGluer]   item {i}: rejected ({info})")
                        if rejected:
                            summary = "\n".join(f"• {r}" for r in rejected[:10])
                            if len(rejected) > 10:
                                summary += f"\n… and {len(rejected) - 10} more."
                            self._show_error_dialog(
                                f"Rejected {len(rejected)} of {n} pick(s)",
                                (
                                    "Only files inside the selected directory "
                                    "or zip can be excluded.\n\n" + summary
                                ),
                            )
                    except Exception as e:
                        import traceback
                        debug_print(traceback.format_exc())
                        self._show_error_dialog("Failed to process selected files", str(e))
            else:
                debug_print(f"[CodeGluer] user did not accept (response={response})")
            dialog.destroy()

        def _execute(self, opts):
            codegluer_path = shutil.which("codegluer") or os.path.expanduser("~/.local/bin/codegluer")
            cmd = [codegluer_path, *build_command(self.files, opts)[1:]]

            if self.dry_run:
                print("\n".join(cmd))
                self.close()
                return

            save_theme(self.current_theme)
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if result.returncode == 0:
                    output_name = opts["output"] or default_name(self.target_dir, opts["format"])
                    self._notify("CodeGluer", f"Created: {output_name}")
                else:
                    self._notify("CodeGluer", f"Failed: {result.stderr.strip()}")
            except subprocess.TimeoutExpired:
                self._notify("CodeGluer", "Failed: command timed out after 60 seconds")
            except Exception as e:
                self._notify("CodeGluer", f"Error: {e}")
            self.close()

        def _notify(self, title, body):
            try:
                subprocess.run(["notify-send", title, body], timeout=5)
            except Exception:
                pass

    app = Gtk.Application(application_id="com.codegluer.gui", flags=Gio.ApplicationFlags.FLAGS_NONE)
    win = None

    def on_activate(a):
        nonlocal win
        win = CodeGluerWindow(a)
        win.present()

    app.connect("activate", on_activate)
    app.run(None)


# ──────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    dry_run = False
    if "--dry-run" in args:
        dry_run = True
        args.remove("--dry-run")

    files = [a for a in args if not a.startswith("-")]
    if not files:
        env = os.environ.get("NAUTILUS_SCRIPT_SELECTED_FILE_PATHS", "") or \
              os.environ.get("NEMO_SCRIPT_SELECTED_FILE_PATHS", "")
        files = [f for f in env.splitlines() if f]

    if not files:
        print("Usage: codegluer_gui.py <file1> [file2] ...", file=sys.stderr)
        print("       (or run via file manager right-click)", file=sys.stderr)
        sys.exit(1)

    run_gui(files, dry_run=dry_run)


if __name__ == "__main__":
    main()