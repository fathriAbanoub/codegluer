"""
pytest suite for codegluer_gui logic. No GTK required.

Run: pytest tests/
"""

import pytest
from pathlib import Path
import codegluer_gui as cg


# ---- helpers for command-list assertions -----------------------------------

def contains(cmd, item):
    """Return True if item is a substring of any element in cmd."""
    return any(item in str(x) for x in cmd)


# ---- test functions --------------------------------------------------------

def test_build_command_markdown_dir_all_flags(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "file.py").touch()
    opts = {
        "format": "markdown",
        "output": "out.md",
        "excludes": "foo,bar",
        "stats": True,
        "estimate_tokens": True,
        "tree": True,
        "toc": True,
        "respect_gitignore": True,
        "any_dir": True,
        "target_dir": str(tmp_path),
    }
    cmd = cg.build_command([str(src)], opts)
    assert contains(cmd, "codegluer")
    assert contains(cmd, str(src))
    assert contains(cmd, "-r")
    assert contains(cmd, "--format")
    assert contains(cmd, "markdown")
    assert contains(cmd, "--tree")
    assert contains(cmd, "--stats")
    assert contains(cmd, "--toc")
    assert contains(cmd, "--estimate-tokens")
    assert contains(cmd, "--respect-gitignore")
    assert contains(cmd, "--exclude")
    assert contains(cmd, "foo")
    assert contains(cmd, "bar")
    assert contains(cmd, "-o")
    assert contains(cmd, str(tmp_path / "out.md"))
    assert not contains(cmd, "--estimate_tokens")    # hyphen not underscore
    assert not contains(cmd, "--respect_gitignore")  # hyphen not underscore


def test_build_command_plain_empty_output_defaults_to_txt(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    opts = {
        "format": "plain",
        "output": "",
        "excludes": "",
        "stats": False,
        "estimate_tokens": False,
        "any_dir": True,
        "target_dir": str(tmp_path),
    }
    cmd = cg.build_command([str(src)], opts)
    assert contains(cmd, "Glued_Code.txt")
    assert not contains(cmd, "Glued_Code.md")
    assert contains(cmd, "-r")
    assert contains(cmd, "--format")
    assert contains(cmd, "plain")


def test_build_command_markdown_empty_output_defaults_to_md(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    opts = {
        "format": "markdown",
        "output": "",
        "excludes": "",
        "stats": False,
        "estimate_tokens": False,
        "any_dir": True,
        "target_dir": str(tmp_path),
    }
    cmd = cg.build_command([str(src)], opts)
    assert contains(cmd, "Glued_Code.md")


def test_default_name_single_collision_appends_1(tmp_path):
    """When Glued_Code.md exists, default_name returns Glued_Code_1.md"""
    (tmp_path / "Glued_Code.md").touch()
    name = cg.default_name(str(tmp_path), "markdown")
    assert name == "Glued_Code_1.md"


def test_default_name_collision_cap_falls_back_to_pid(tmp_path):
    """When Glued_Code.md through Glued_Code_99.md exist, use pid fallback."""
    # Create 100 files (0 through 99)
    (tmp_path / "Glued_Code.md").touch()
    for i in range(1, 100):
        (tmp_path / f"Glued_Code_{i}.md").touch()

    name = cg.default_name(str(tmp_path), "markdown")
    assert name.startswith("Glued_Code_")
    assert name.endswith(".md")
    # It should not be Glued_Code_100.md; it should be a PID-based name
    assert "_" in name and not name.endswith("_100.md")


def test_build_command_files_only_no_recursive_flags(tmp_path):
    standalone = tmp_path / "standalone.txt"
    standalone.touch()
    opts = {
        "format": "markdown",
        "output": "out.md",
        "excludes": "",
        "stats": True,
        "estimate_tokens": True,
        "tree": True,
        "toc": True,
        "respect_gitignore": True,
        "any_dir": False,
        "target_dir": str(tmp_path),
    }
    cmd = cg.build_command([str(standalone)], opts)
    assert not contains(cmd, "-r")
    assert not contains(cmd, "--tree")
    assert not contains(cmd, "--toc")
    assert not contains(cmd, "--respect-gitignore")
    assert contains(cmd, "--stats")
    assert contains(cmd, "--estimate-tokens")


def test_target_dir_of_bare_filename():
    assert cg.target_dir_of(["file.txt"]) == "."


def test_build_command_custom_output_name_respected(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    opts = {
        "format": "markdown",
        "output": "Glued_Code_custom.md",
        "excludes": "",
        "stats": False,
        "estimate_tokens": False,
        "any_dir": True,
        "target_dir": str(tmp_path),
    }
    cmd = cg.build_command([str(src)], opts)
    assert contains(cmd, "Glued_Code_custom.md")
    assert not contains(cmd, "Glued_Code_1.md")


def test_build_command_exclude_comma_separated(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    opts = {
        "format": "markdown",
        "output": "out.md",
        "excludes": "foo.py,bar.py",
        "stats": False,
        "estimate_tokens": False,
        "any_dir": True,
        "target_dir": str(tmp_path),
    }
    cmd = cg.build_command([str(src)], opts)
    assert contains(cmd, "--exclude")
    assert contains(cmd, "foo.py")
    assert contains(cmd, "bar.py")


def test_is_any_dir_detection(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    standalone = tmp_path / "standalone.txt"
    standalone.touch()
    assert cg.is_any_dir([str(src)]) is True
    assert cg.is_any_dir([str(standalone)]) is False
    assert cg.is_any_dir([str(src), str(standalone)]) is True


def test_theme_save_read_roundtrip(tmp_path, monkeypatch):
    config_dir = tmp_path / "config" / "codegluer"
    monkeypatch.setattr(cg, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(cg, "CONFIG_FILE", config_dir / "theme")
    cg.save_theme("roselle")
    assert cg.read_theme() == "roselle"


def test_theme_invalid_fallback_auto(tmp_path, monkeypatch):
    config_dir = tmp_path / "config" / "codegluer"
    monkeypatch.setattr(cg, "CONFIG_DIR", config_dir)
    config_dir.mkdir(parents=True, exist_ok=True)
    theme_file = config_dir / "theme"
    theme_file.write_text("invalid_theme")
    monkeypatch.setattr(cg, "CONFIG_FILE", theme_file)
    assert cg.read_theme() == "auto"


def test_theme_missing_config_fallback_auto(tmp_path, monkeypatch):
    config_dir = tmp_path / "config" / "codegluer"
    monkeypatch.setattr(cg, "CONFIG_DIR", config_dir)
    theme_file = config_dir / "theme"
    # Ensure file does not exist
    if theme_file.exists():
        theme_file.unlink()
    monkeypatch.setattr(cg, "CONFIG_FILE", theme_file)
    assert cg.read_theme() == "auto"


def test_resolve_theme_explicit_passthrough():
    assert cg.resolve_theme("light") == "light"
    assert cg.resolve_theme("dark") == "dark"
    assert cg.resolve_theme("roselle") == "roselle"


def test_theme_css_returns_nonempty_for_known_themes():
    for theme in ("light", "dark", "roselle"):
        css = cg.theme_css(theme)
        assert css and len(css) > 10


def test_build_command_no_excludes_no_flag(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    opts = {
        "format": "markdown",
        "output": "out.md",
        "excludes": "",
        "stats": False,
        "estimate_tokens": False,
        "any_dir": True,
        "target_dir": str(tmp_path),
    }
    cmd = cg.build_command([str(src)], opts)
    assert not contains(cmd, "--exclude")


def test_build_command_toc_passed_for_markdown(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    opts = {
        "format": "markdown",
        "output": "out.md",
        "excludes": "",
        "stats": False,
        "estimate_tokens": False,
        "tree": False,
        "toc": True,
        "respect_gitignore": False,
        "any_dir": True,
        "target_dir": str(tmp_path),
    }
    cmd = cg.build_command([str(src)], opts)
    assert contains(cmd, "--toc")


def test_build_command_toc_absent_for_plain(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    opts = {
        "format": "plain",
        "output": "out.txt",
        "excludes": "",
        "stats": False,
        "estimate_tokens": False,
        "tree": False,
        "toc": True,
        "respect_gitignore": False,
        "any_dir": True,
        "target_dir": str(tmp_path),
    }
    cmd = cg.build_command([str(src)], opts)
    assert not contains(cmd, "--toc")


def test_build_command_multiple_files(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    f1 = src / "file.py"
    f1.touch()
    f2 = tmp_path / "standalone.txt"
    f2.touch()
    opts = {
        "format": "markdown",
        "output": "out.md",
        "excludes": "",
        "stats": False,
        "estimate_tokens": False,
        "any_dir": True,
        "target_dir": str(tmp_path),
    }
    cmd = cg.build_command([str(f1), str(f2)], opts)
    assert contains(cmd, str(f1))
    assert contains(cmd, str(f2))


def test_should_update_default_markdown_true(tmp_path):
    default = cg.default_name(str(tmp_path), "markdown")
    assert cg.should_update_default(default, str(tmp_path)) is True


def test_should_update_default_plain_true(tmp_path):
    default = cg.default_name(str(tmp_path), "plain")
    assert cg.should_update_default(default, str(tmp_path)) is True


def test_should_update_default_empty_true(tmp_path):
    assert cg.should_update_default("", str(tmp_path)) is True


def test_should_update_default_custom_false(tmp_path):
    assert cg.should_update_default("Glued_Code_custom.md", str(tmp_path)) is False
    assert cg.should_update_default("my_output.md", str(tmp_path)) is False
    assert cg.should_update_default("report.txt", str(tmp_path)) is False