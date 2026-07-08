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

            # Exclude patterns
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

        def _normalize_exclude_pattern(self, text: str) -> str:
            text = text.strip()
            if text.startswith('./'):
                text = text[2:]
            if text.endswith('/'):
                text = text[:-1]
            return text

        def _add_exclude_chip(self, text: str) -> None:
            normalized = self._normalize_exclude_pattern(text)
            debug_print(f"[CodeGluer] _add_exclude_chip({text!r}) -> normalized {normalized!r}")
            if not normalized:
                debug_print("[CodeGluer]   skipped: empty after normalization")
                return
            if normalized in self.excludes:
                debug_print("[CodeGluer]   skipped: duplicate")
                return
            try:
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
                close_btn.connect("clicked", lambda *_: self._remove_exclude_chip(normalized, chip))
                chip.append(close_btn)

                self.chip_flowbox.insert(chip, -1)
                self.chip_flowbox.set_visible(True)
                debug_print(f"[CodeGluer]   added. total excludes now: {len(self.excludes)}")
            except Exception as e:
                import traceback
                debug_print(traceback.format_exc())
                self._show_error_dialog("Failed to add exclude chip", str(e))

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
            try:
                if (self.target_dir and os.path.isdir(self.target_dir)
                        and not _looks_heavy(self.target_dir)):
                    dialog.set_initial_folder(Gio.File.new_for_path(self.target_dir))
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
            try:
                for i in range(n):
                    gfile = files.get_item(i)
                    if gfile is None:
                        debug_print(f"[CodeGluer]   item {i} is None")
                        continue
                    name = gfile.get_basename()
                    debug_print(f"[CodeGluer]   item {i}: {name!r}")
                    if name:
                        self._add_exclude_chip(name)
            except Exception as e:
                import traceback
                debug_print(traceback.format_exc())
                self._show_error_dialog("Failed to process selected files", str(e))

        def _open_file_chooser_dialog(self) -> None:
            dialog = Gtk.FileChooserNative.new(
                title="Select files to exclude",
                parent=self,
                action=Gtk.FileChooserAction.OPEN,
                accept_label="_Select",
                cancel_label="_Cancel",
            )
            dialog.set_select_multiple(True)
            try:
                if (self.target_dir and os.path.isdir(self.target_dir)
                        and not _looks_heavy(self.target_dir)):
                    dialog.set_current_folder(Gio.File.new_for_path(self.target_dir))
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
                        for i in range(n):
                            gfile = files.get_item(i)
                            if gfile is None:
                                continue
                            name = gfile.get_basename()
                            debug_print(f"[CodeGluer]   item {i}: {name!r}")
                            if name:
                                self._add_exclude_chip(name)
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