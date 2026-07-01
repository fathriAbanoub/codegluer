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
import json
import subprocess
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))) / "codegluer"
CONFIG_FILE = CONFIG_DIR / "theme"


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
    return any(os.path.isdir(f) for f in files)


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

    cmd = ["codegluer"] + files
    cmd += ["--format", fmt]
    if any_dir:
        cmd += ["-r"]
    if opts.get("tree") and any_dir:
        cmd += ["--tree"]
    if opts.get("stats"):
        cmd += ["--stats"]
    if opts.get("toc") and any_dir:
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


THEME_CSS = {
    "light": """
        window { background: #ffffff; color: #333333; }
        entry { background: #f9f9f9; border: 1px solid #ddd; border-radius: 3px; padding: 4px; color: #333333; }
        checkbutton { color: #333333; }
        dropdown { background: #f9f9f9; border: 1px solid #ddd; border-radius: 3px; }
        button.suggested-action { background: #C62734; color: white; border-radius: 4px; }
        button { padding: 6px 12px; border-radius: 4px; }
    """,
    "dark": """
        window { background: #2b2b2b; color: #e0e0e0; }
        entry { background: #3a3a3a; border: 1px solid #555; border-radius: 3px; padding: 4px; color: #e0e0e0; }
        checkbutton { color: #e0e0e0; }
        dropdown { background: #3a3a3a; border: 1px solid #555; border-radius: 3px; }
        button.suggested-action { background: #E87672; color: #1a1a1a; border-radius: 4px; }
        button { padding: 6px 12px; border-radius: 4px; }
    """,
    "roselle": """
        window { background: #1a0a0a; color: #f0d0d0; }
        entry { background: #2a1515; border: 1px solid #C62734; border-radius: 3px; padding: 4px; color: #f0d0d0; }
        checkbutton { color: #f0d0d0; }
        dropdown { background: #2a1515; border: 1px solid #C62734; border-radius: 3px; }
        button.suggested-action { background: #C62734; color: #fff0f0; border-radius: 4px; }
        button { padding: 6px 12px; border-radius: 4px; }
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
    return THEME_CSS.get(resolved, "")


# ──────────────────────────────────────────────────────────────────────
# GTK4 GUI
# ──────────────────────────────────────────────────────────────────────

def run_gui(files: list[str], dry_run: bool = False) -> None:
    """Launch the GTK4 dialog. Returns the built command via dry_run or executes it."""
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, Gio, GLib, Gdk

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
            self.format_dropdown = None
            self.theme_dropdown = None
            self.checkboxes = {}

            self._build_ui()
            self._apply_theme(self.current_theme)

        def _build_ui(self):
            main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            self.set_child(main_box)

            # Header bar with buttons
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
            self.apply_theme_btn.set_sensitive(False)  # grayed until user picks a theme
            header.pack_end(self.apply_theme_btn)

            # Content area with margin
            content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            content.set_margin_start(16)
            content.set_margin_end(16)
            content.set_margin_top(12)
            content.set_margin_bottom(16)
            main_box.append(content)

            # Info label
            info = Gtk.Label(label=f"Glue {len(self.files)} item(s)  →  {self.target_dir}")
            info.set_halign(Gtk.Align.START)
            info.set_use_markup(True)
            content.append(info)

            # Grid for form fields
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
            grid.attach(Gtk.Label(label="Exclude (comma-separated):", halign=Gtk.Align.END), 0, row, 1, 1)
            self.excludes_entry = Gtk.Entry()
            self.excludes_entry.set_placeholder_text("e.g., *.pyc, __pycache__, .git")
            self.excludes_entry.set_hexpand(True)
            grid.attach(self.excludes_entry, 1, row, 1, 1)
            row += 1

            # Format dropdown
            grid.attach(Gtk.Label(label="Format:", halign=Gtk.Align.END), 0, row, 1, 1)
            fmt_model = Gtk.StringList.new(["markdown", "plain"])
            self.format_dropdown = Gtk.DropDown(model=fmt_model)
            self.format_dropdown.connect("notify::selected", self._on_format_changed)
            grid.attach(self.format_dropdown, 1, row, 1, 1)
            row += 1

            # Theme dropdown shows "auto" (grays Apply) + real themes (enable Apply).
            # Initial selection is the saved theme (or "auto" if none saved).
            grid.attach(Gtk.Label(label="Theme:", halign=Gtk.Align.END), 0, row, 1, 1)
            theme_model = Gtk.StringList.new(THEMES)
            self.theme_dropdown = Gtk.DropDown(model=theme_model)
            # Show saved theme (auto if none saved); Apply grayed if auto
            self.theme_dropdown.set_selected(THEMES.index(self.current_theme))
            self.theme_dropdown.connect("notify::selected", self._on_theme_dropdown_changed)
            grid.attach(self.theme_dropdown, 1, row, 1, 1)
            row += 1

            # Separator
            sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            content.append(sep)

            # Checkboxes
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

        def _on_theme_dropdown_changed(self, dropdown, _param):
            # Only real themes (light/dark/roselle) enable Apply. "auto" grays it.
            selected = THEMES[dropdown.get_selected()]
            self.apply_theme_btn.set_sensitive(selected in REAL_THEMES)

        def _on_apply_theme(self, _btn):
            selected = self.theme_dropdown.get_selected()
            new_theme = THEMES[selected]
            self.current_theme = new_theme
            save_theme(new_theme)
            self._apply_theme(new_theme)
            self.apply_theme_btn.set_sensitive(False)  # applied → gray out again

        def _apply_theme(self, theme):
            css_text = theme_css(theme)
            if not css_text:
                return
            provider = Gtk.CssProvider()
            provider.load_from_data(css_text.encode())
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

        def _collect_opts(self):
            opts = {
                "format": self.format,
                "output": self.output_entry.get_text(),
                "excludes": self.excludes_entry.get_text(),
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
            opts = self._collect_opts()

            # Exclude validation: space without comma
            excludes = opts["excludes"].strip()
            if excludes and " " in excludes and "," not in excludes:
                dialog = Gtk.AlertDialog()
                dialog.set_message("Exclude patterns contain spaces but no commas")
                dialog.set_detail(
                    f'You entered: "{excludes}"\n\n'
                    "Patterns are comma-separated. Replace spaces with commas?"
                )
                dialog.set_buttons(["Cancel", "Keep as-is", "Fix it"])
                dialog.choose(self, None, self._on_exclude_dialog_response, opts)
                return

            self._execute(opts)

        def _on_exclude_dialog_response(self, dialog, result, opts):
            try:
                choice = dialog.choose_finish(result)
            except Exception:
                return
            if choice == 2:  # Fix it
                opts["excludes"] = opts["excludes"].replace(" ", ",")
            elif choice == 0:  # Cancel
                return
            self._execute(opts)

        def _execute(self, opts):
            cmd = build_command(self.files, opts)

            if self.dry_run:
                print("\n".join(cmd))
                self.close()
                return

            save_theme(self.current_theme)
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    output_name = opts["output"] or default_name(self.target_dir, opts["format"])
                    self._notify("CodeGluer", f"Created: {output_name}")
                else:
                    self._notify("CodeGluer", f"Failed: {result.stderr.strip()}")
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
        # No files — maybe launched standalone
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
