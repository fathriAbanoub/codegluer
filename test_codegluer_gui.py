#!/usr/bin/env python3
"""
Self-check for codegluer_gui.py logic. No GTK required. No framework.
Tests build_command, default_name, collision avoidance, smart flags,
bare filenames, custom input, exclude parsing, theme save/read.

Run: python3 test_codegluer_gui.py
"""
import os
import sys
import tempfile
import shutil

# Import the module under test
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import codegluer_gui as cg


def assert_present(item, cmd_list):
    if not any(item in str(x) for x in cmd_list):
        print(f"FAIL: expected '{item}' in {cmd_list}")
        sys.exit(1)

def assert_absent(item, cmd_list):
    if any(item in str(x) for x in cmd_list):
        print(f"FAIL: unexpected '{item}' in {cmd_list}")
        sys.exit(1)

def assert_eq(expected, actual, msg=""):
    if expected != actual:
        print(f"FAIL: {msg} — expected {expected!r}, got {actual!r}")
        sys.exit(1)


if __name__ == "__main__":
    TMP = tempfile.mkdtemp()
    def cleanup():
        shutil.rmtree(TMP, ignore_errors=True)
    import atexit
    atexit.register(cleanup)

    # Set up test dirs/files
    os.makedirs(os.path.join(TMP, "src"))
    open(os.path.join(TMP, "src", "file.py"), "w").close()
    open(os.path.join(TMP, "standalone.txt"), "w").close()

    passed = 0

    # ──────────────────────────────────────────────────────────────────────
    # Test 1: markdown + dir → all flags available, correct command built
    # ──────────────────────────────────────────────────────────────────────
    opts = {
        "format": "markdown", "output": "out.md", "excludes": "foo,bar",
        "stats": True, "estimate_tokens": True,
        "tree": True, "toc": True, "respect_gitignore": True,
        "any_dir": True, "target_dir": TMP,
    }
    cmd = cg.build_command([os.path.join(TMP, "src")], opts)
    assert_present("codegluer", cmd)
    assert_present(os.path.join(TMP, "src"), cmd)
    assert_present("-r", cmd)
    assert_present("--format", cmd)
    assert_present("markdown", cmd)
    assert_present("--tree", cmd)
    assert_present("--stats", cmd)
    assert_present("--toc", cmd)
    assert_present("--estimate-tokens", cmd)
    assert_present("--respect-gitignore", cmd)
    assert_present("--exclude", cmd)
    assert_present("foo", cmd)
    assert_present("bar", cmd)
    assert_present("-o", cmd)
    assert_present(os.path.join(TMP, "out.md"), cmd)
    # Ensure flags use hyphens, not underscores
    assert_absent("--estimate_tokens", cmd)
    assert_absent("--respect_gitignore", cmd)
    passed += 1
    print("✓ Test 1: markdown + dir, all flags")

    # ──────────────────────────────────────────────────────────────────────
    # Test 2: plain format, empty output → default Glued_Code.txt
    # ──────────────────────────────────────────────────────────────────────
    opts = {"format": "plain", "output": "", "excludes": "", "stats": False, "estimate_tokens": False,
            "any_dir": True, "target_dir": TMP}
    cmd = cg.build_command([os.path.join(TMP, "src")], opts)
    assert_present("Glued_Code.txt", cmd)
    assert_absent("Glued_Code.md", cmd)
    assert_present("-r", cmd)
    assert_present("--format", cmd)
    assert_present("plain", cmd)
    passed += 1
    print("✓ Test 2: plain format → .txt default")

    # ──────────────────────────────────────────────────────────────────────
    # Test 3: markdown format, empty output → default Glued_Code.md
    # ──────────────────────────────────────────────────────────────────────
    opts = {"format": "markdown", "output": "", "excludes": "", "stats": False, "estimate_tokens": False,
            "any_dir": True, "target_dir": TMP}
    cmd = cg.build_command([os.path.join(TMP, "src")], opts)
    assert_present("Glued_Code.md", cmd)
    passed += 1
    print("✓ Test 3: markdown format → .md default")

    # ──────────────────────────────────────────────────────────────────────
    # Test 4: collision → Glued_Code_1.md
    # ──────────────────────────────────────────────────────────────────────
    open(os.path.join(TMP, "Glued_Code.md"), "w").close()
    opts = {"format": "markdown", "output": "", "excludes": "", "stats": False, "estimate_tokens": False,
            "any_dir": True, "target_dir": TMP}
    cmd = cg.build_command([os.path.join(TMP, "src")], opts)
    assert_present("Glued_Code_1.md", cmd)
    assert_absent("Glued_Code.md", cmd)
    os.remove(os.path.join(TMP, "Glued_Code.md"))
    passed += 1
    print("✓ Test 4: collision → _1 suffix")

    # ──────────────────────────────────────────────────────────────────────
    # Test 5: files-only → no -r, no dir-only flags even if True
    # ──────────────────────────────────────────────────────────────────────
    opts = {
        "format": "markdown", "output": "out.md", "excludes": "",
        "stats": True, "estimate_tokens": True,
        "tree": True, "toc": True, "respect_gitignore": True,
        "any_dir": False, "target_dir": TMP,
    }
    cmd = cg.build_command([os.path.join(TMP, "standalone.txt")], opts)
    assert_absent("-r", cmd)
    assert_absent("--tree", cmd)
    assert_absent("--toc", cmd)
    assert_absent("--respect-gitignore", cmd)
    assert_present("--stats", cmd)
    assert_present("--estimate-tokens", cmd)
    passed += 1
    print("✓ Test 5: files-only hides dir-only flags")

    # ──────────────────────────────────────────────────────────────────────
    # Test 6: bare filename (no directory) → target_dir is "."
    # ──────────────────────────────────────────────────────────────────────
    assert_eq(".", cg.target_dir_of(["file.txt"]), "bare filename target_dir")
    passed += 1
    print("✓ Test 6: bare filename → target_dir='.'")

    # ──────────────────────────────────────────────────────────────────────
    # Test 7: custom output name respected
    # ──────────────────────────────────────────────────────────────────────
    opts = {"format": "markdown", "output": "Glued_Code_custom.md", "excludes": "", "stats": False, "estimate_tokens": False,
            "any_dir": True, "target_dir": TMP}
    cmd = cg.build_command([os.path.join(TMP, "src")], opts)
    assert_present("Glued_Code_custom.md", cmd)
    assert_absent("Glued_Code_1.md", cmd)
    passed += 1
    print("✓ Test 7: custom name respected")

    # ──────────────────────────────────────────────────────────────────────
    # Test 8: exclude with spaces (auto-fixed by GUI before build_command)
    # ──────────────────────────────────────────────────────────────────────
    opts = {"format": "markdown", "output": "out.md", "excludes": "foo.py,bar.py", "stats": False, "estimate_tokens": False,
            "any_dir": True, "target_dir": TMP}
    cmd = cg.build_command([os.path.join(TMP, "src")], opts)
    assert_present("--exclude", cmd)
    assert_present("foo.py", cmd)
    assert_present("bar.py", cmd)
    passed += 1
    print("✓ Test 8: exclude comma-separated")

    # ──────────────────────────────────────────────────────────────────────
    # Test 9: default_name collision cap at 99
    # ──────────────────────────────────────────────────────────────────────
    # Create Glued_Code.md + Glued_Code_1.md through Glued_Code_99.md (100 total)
    open(os.path.join(TMP, "Glued_Code.md"), "w").close()
    for i in range(1, 100):
        open(os.path.join(TMP, f"Glued_Code_{i}.md"), "w").close()
    name = cg.default_name(TMP, "markdown")
    assert name.startswith("Glued_Code_"), f"Expected pid fallback, got {name}"
    assert name.endswith(".md"), f"Expected .md extension, got {name}"
    assert "_" in name and not name.endswith("_100.md"), f"Should use pid, not _100: {name}"
    # Clean up
    os.remove(os.path.join(TMP, "Glued_Code.md"))
    for i in range(1, 100):
        os.remove(os.path.join(TMP, f"Glued_Code_{i}.md"))
    passed += 1
    print(f"✓ Test 9: collision cap → pid fallback ({name})")

    # ──────────────────────────────────────────────────────────────────────
    # Test 10: is_any_dir detection — fixed E712 (no explicit True/False)
    # ──────────────────────────────────────────────────────────────────────
    assert cg.is_any_dir([os.path.join(TMP, "src")])
    assert not cg.is_any_dir([os.path.join(TMP, "standalone.txt")])
    assert cg.is_any_dir([os.path.join(TMP, "src"), os.path.join(TMP, "standalone.txt")])
    passed += 1
    print("✓ Test 10: is_any_dir detection")

    # ──────────────────────────────────────────────────────────────────────
    # Test 11: theme save/read roundtrip
    # ──────────────────────────────────────────────────────────────────────
    cg.CONFIG_DIR = Path = __import__("pathlib").Path
    cg.CONFIG_DIR = Path(TMP) / "config" / "codegluer"
    cg.CONFIG_FILE = cg.CONFIG_DIR / "theme"
    cg.save_theme("roselle")
    assert_eq("roselle", cg.read_theme(), "theme roundtrip")
    passed += 1
    print("✓ Test 11: theme save/read roundtrip")

    # ──────────────────────────────────────────────────────────────────────
    # Test 12: invalid theme falls back to auto
    # ──────────────────────────────────────────────────────────────────────
    cg.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    cg.CONFIG_FILE.write_text("invalid_theme")
    assert_eq("auto", cg.read_theme(), "invalid theme fallback")
    passed += 1
    print("✓ Test 12: invalid theme → auto")

    # ──────────────────────────────────────────────────────────────────────
    # Test 13: missing config file → auto
    # ──────────────────────────────────────────────────────────────────────
    cg.CONFIG_FILE.unlink(missing_ok=True)
    assert_eq("auto", cg.read_theme(), "missing config fallback")
    passed += 1
    print("✓ Test 13: missing config → auto")

    # ──────────────────────────────────────────────────────────────────────
    # Test 14: resolve_theme passes through explicit themes
    # ──────────────────────────────────────────────────────────────────────
    assert_eq("light", cg.resolve_theme("light"), "resolve light")
    assert_eq("dark", cg.resolve_theme("dark"), "resolve dark")
    assert_eq("roselle", cg.resolve_theme("roselle"), "resolve roselle")
    passed += 1
    print("✓ Test 14: resolve_theme explicit passthrough")

    # ──────────────────────────────────────────────────────────────────────
    # Test 15: theme_css returns non-empty for known themes
    # ──────────────────────────────────────────────────────────────────────
    for t in ["light", "dark", "roselle"]:
        css = cg.theme_css(t)
        assert css and len(css) > 10, f"theme_css('{t}') returned empty/short: {css!r}"
    passed += 1
    print("✓ Test 15: theme_css returns CSS for known themes")

    # ──────────────────────────────────────────────────────────────────────
    # Test 16: build_command with no excludes → no --exclude flag
    # ──────────────────────────────────────────────────────────────────────
    opts = {"format": "markdown", "output": "out.md", "excludes": "", "stats": False, "estimate_tokens": False,
            "any_dir": True, "target_dir": TMP}
    cmd = cg.build_command([os.path.join(TMP, "src")], opts)
    assert_absent("--exclude", cmd)
    passed += 1
    print("✓ Test 16: no excludes → no --exclude flag")

    # ──────────────────────────────────────────────────────────────────────
    # Test 17: --toc passed for markdown
    # ──────────────────────────────────────────────────────────────────────
    opts = {"format": "markdown", "output": "out.md", "excludes": "",
            "stats": False, "estimate_tokens": False,
            "tree": False, "toc": True, "respect_gitignore": False,
            "any_dir": True, "target_dir": TMP}
    cmd = cg.build_command([os.path.join(TMP, "src")], opts)
    assert_present("--toc", cmd)
    passed += 1
    print("✓ Test 17: --toc passed for markdown")

    # ──────────────────────────────────────────────────────────────────────
    # Test 18: multiple files passed correctly
    # ──────────────────────────────────────────────────────────────────────
    f1 = os.path.join(TMP, "src", "file.py")
    f2 = os.path.join(TMP, "standalone.txt")
    opts = {"format": "markdown", "output": "out.md", "excludes": "", "stats": False, "estimate_tokens": False,
            "any_dir": True, "target_dir": TMP}
    cmd = cg.build_command([f1, f2], opts)
    assert_present(f1, cmd)
    assert_present(f2, cmd)
    passed += 1
    print("✓ Test 18: multiple files passed correctly")

    # ──────────────────────────────────────────────────────────────────────
    # Test 19: should_update_default — default markdown name → True (update ok)
    # ──────────────────────────────────────────────────────────────────────
    default_md = cg.default_name(TMP, "markdown")
    assert_eq(True, cg.should_update_default(default_md, TMP), "default .md → update")
    passed += 1
    print("✓ Test 19: default markdown name → should_update=True")

    # ──────────────────────────────────────────────────────────────────────
    # Test 20: should_update_default — default plain name → True
    # ──────────────────────────────────────────────────────────────────────
    default_txt = cg.default_name(TMP, "plain")
    assert_eq(True, cg.should_update_default(default_txt, TMP), "default .txt → update")
    passed += 1
    print("✓ Test 20: default plain name → should_update=True")

    # ──────────────────────────────────────────────────────────────────────
    # Test 21: should_update_default — empty string → True
    # ──────────────────────────────────────────────────────────────────────
    assert_eq(True, cg.should_update_default("", TMP), "empty → update")
    passed += 1
    print("✓ Test 21: empty filename → should_update=True")

    # ──────────────────────────────────────────────────────────────────────
    # Test 22: should_update_default — custom name → False (preserve!)
    # Regression: "Glued_Code_custom.md" must NOT be treated as default.
    # ──────────────────────────────────────────────────────────────────────
    assert_eq(False, cg.should_update_default("Glued_Code_custom.md", TMP), "custom → preserve")
    assert_eq(False, cg.should_update_default("my_output.md", TMP), "custom2 → preserve")
    assert_eq(False, cg.should_update_default("report.txt", TMP), "custom3 → preserve")
    passed += 1
    print("✓ Test 22: custom name → should_update=False (regression for startswith bug)")

    # ──────────────────────────────────────────────────────────────────────
    # Test 23: --toc NOT added for plain format (regression guard)
    # ──────────────────────────────────────────────────────────────────────
    opts = {"format": "plain", "output": "out.txt", "excludes": "",
            "stats": False, "estimate_tokens": False,
            "tree": False, "toc": True, "respect_gitignore": False,
            "any_dir": True, "target_dir": TMP}
    cmd = cg.build_command([os.path.join(TMP, "src")], opts)
    assert_absent("--toc", cmd)
    passed += 1
    print("✓ Test 23: --toc absent for plain format")

    print(f"\nPASS: all {passed} tests pass")