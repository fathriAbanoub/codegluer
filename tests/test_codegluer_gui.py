"""
pytest suite for codegluer_gui logic. No GTK required.

Run: pytest tests/
"""

import os
import pytest
import datetime
import re
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
    assert any("Glued_Code.txt" in arg for arg in cmd)
    assert "Glued_Code.md" not in " ".join(cmd)
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
    assert any("Glued_Code.md" in arg for arg in cmd)


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
    assert any("Glued_Code_custom.md" in arg for arg in cmd)
    assert "Glued_Code_1.md" not in " ".join(cmd)


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


# ── Scope enforcement (moved from scope_selfcheck.py) ─────────────

def test_scope_roots_only_captures_selected_dirs(tmp_path):
    real_dir = tmp_path / "project"
    real_dir.mkdir()
    bare_file = tmp_path / "lonely.py"
    bare_file.touch()
    zip_file = tmp_path / "a.zip"
    zip_file.write_bytes(b"PK")  # fake zip header

    assert cg.compute_scope_roots([str(real_dir)]) == [str(real_dir.resolve())]
    assert cg.compute_scope_roots([str(bare_file)]) == []
    assert cg.compute_scope_roots([str(zip_file)]) == []
    # Mixed: only the dir counts
    assert cg.compute_scope_roots([str(real_dir), str(bare_file), str(zip_file)]) == [str(real_dir.resolve())]
    # Dedup
    assert cg.compute_scope_roots([str(real_dir), str(real_dir)]) == [str(real_dir.resolve())]


def test_validate_rejects_absolute_and_traversal(tmp_path):
    scope = [str(tmp_path)]
    ok, _, err = cg.validate_exclude_pattern("/etc/passwd", scope)
    assert not ok and "Absolute" in err
    ok, _, err = cg.validate_exclude_pattern("../outside.txt", scope)
    assert not ok and "outside" in err
    # Home‑path branch
    ok, _, err = cg.validate_exclude_pattern("~/secret.txt", scope)
    assert not ok and "Absolute" in err


def test_validate_accepts_in_scope_patterns(tmp_path):
    scope = [str(tmp_path)]
    ok, p, _ = cg.validate_exclude_pattern("*.py", scope)
    assert ok and p == "*.py"
    ok, p, _ = cg.validate_exclude_pattern("sub/file.txt", scope)
    assert ok and p == "sub/file.txt"


def test_validate_empty_scope_rejects_slash_patterns():
    ok, _, err = cg.validate_exclude_pattern("foo/bar.py", [])
    assert not ok and "no browsable scope" in err
    # Pure globs still work with empty scope
    ok, p, _ = cg.validate_exclude_pattern("*.py", [])
    assert ok and p == "*.py"


def test_is_path_in_scope_prefix_trap(tmp_path):
    foo = tmp_path / "foo"
    foo.mkdir()
    foobar = tmp_path / "foobar"
    foobar.mkdir()
    # /tmp/foobar/x must NOT match scope root /tmp/foo
    assert not cg.is_path_in_scope(str(foobar / "x"), [str(foo)])
    assert cg.is_path_in_scope(str(foo / "x"), [str(foo)])


# ── New timestamp tests ─────────────────────────────────────────────

def _frozen_now(frozen):
    class _DT:
        @staticmethod
        def now():
            return frozen
    return _DT


def test_default_name_with_timestamp(tmp_path, monkeypatch):
    """Timestamp flag should inject YYYYMMDD_HHMMSS into the default name."""
    frozen = datetime.datetime(2026, 7, 10, 14, 30, 22)
    monkeypatch.setattr(datetime, "datetime", _frozen_now(frozen))

    name = cg.default_name(str(tmp_path), "markdown", include_timestamp=True)
    assert name == "Glued_Code_20260710_143022.md"


def test_default_name_with_timestamp_collision(tmp_path, monkeypatch):
    """If a timestamped file exists, it should append _1, _2, etc."""
    frozen = datetime.datetime(2026, 7, 10, 14, 30, 22)
    monkeypatch.setattr(datetime, "datetime", _frozen_now(frozen))

    (tmp_path / "Glued_Code_20260710_143022.md").touch()
    name = cg.default_name(str(tmp_path), "markdown", include_timestamp=True)
    assert name == "Glued_Code_20260710_143022_1.md"


def test_should_update_default_recognizes_timestamped(tmp_path):
    """A timestamped default in the entry must still be recognized as a
    default — even though re-calling default_name() would produce a
    different timestamp. This is the regression friend #1's patch had."""
    assert cg.should_update_default("Glued_Code_20260710_143022.md", str(tmp_path)) is True
    assert cg.should_update_default("Glued_Code_20260710_143022_1.md", str(tmp_path)) is True
    # Sanity: custom names still rejected
    assert cg.should_update_default("my_project.md", str(tmp_path)) is False
    assert cg.should_update_default("Glued_Code_custom.md", str(tmp_path)) is False


def test_build_command_with_timestamp_empty_output(tmp_path):
    """If output is empty but timestamp is checked, build_command should
    generate a timestamped name in the -o argument."""
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
        "include_timestamp": True,
    }
    cmd = cg.build_command([str(src)], opts)
    try:
        idx = cmd.index("-o")
        out_path = cmd[idx + 1]
    except ValueError:
        assert False, "-o not in command"
    assert re.search(r"Glued_Code_\d{8}_\d{6}\.md$", out_path)