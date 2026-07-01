## `tests/test_codegluer_gui.py`

"""
pytest suite for codegluer_gui logic. No GTK required.

Run: pytest tests/
"""

import os
import pytest
from pathlib import Path
import codegluer_gui as cg


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
    # Exact token checks
    assert cmd[0] == "codegluer"
    assert str(src) in cmd
    assert "-r" in cmd
    assert "--format" in cmd
    assert "markdown" in cmd
    assert "--tree" in cmd
    assert "--stats" in cmd
    assert "--toc" in cmd
    assert "--estimate-tokens" in cmd
    assert "--respect-gitignore" in cmd
    assert "--exclude" in cmd
    assert "foo" in cmd
    assert "bar" in cmd
    assert "-o" in cmd
    assert str(tmp_path / "out.md") in cmd
    # Ensure flags use hyphens, not underscores
    assert "--estimate_tokens" not in cmd
    assert "--respect_gitignore" not in cmd


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
    assert "Glued_Code.txt" in cmd
    assert "Glued_Code.md" not in cmd
    assert "-r" in cmd
    assert "--format" in cmd
    assert "plain" in cmd


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
    assert "Glued_Code.md" in cmd


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
    expected = f"Glued_Code_{os.getpid()}.md"
    assert name == expected


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
    assert "-r" not in cmd
    assert "--tree" not in cmd
    assert "--toc" not in cmd
    assert "--respect-gitignore" not in cmd
    assert "--stats" in cmd
    assert "--estimate-tokens" in cmd


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
    assert "Glued_Code_custom.md" in cmd
    assert "Glued_Code_1.md" not in cmd


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
    assert "--exclude" in cmd
    assert "foo.py" in cmd
    assert "bar.py" in cmd


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
    assert "--exclude" not in cmd


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
    assert "--toc" in cmd


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
    assert "--toc" not in cmd


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
    assert str(f1) in cmd
    assert str(f2) in cmd


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