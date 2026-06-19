"""Tests for AI context features (Task 8)."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

import codegluer
from codegluer import (
    GlueConfig, ProjectStats, TreeNode,
    build_tree_structure, render_tree,
    collect_files, glue_files,
)


class TestAIContextFeatures:

    # ── .codegluerignore ──────────────────────────────────────────────

    def test_codegluerignore_is_injected(self, tmp_dir):
        (tmp_dir / ".codegluerignore").write_text("*.log\n")
        (tmp_dir / "keep.py").write_text("x")
        (tmp_dir / "ignore.log").write_text("y")

        original = []
        files = collect_files([str(tmp_dir)], recursive=True, exclude_patterns=original)

        names = {f.name for f in files}
        assert "keep.py" in names
        assert "ignore.log" not in names
        assert original == []  # caller's list not mutated

    def test_codegluerignore_does_not_mutate_caller_list(self, tmp_dir):
        (tmp_dir / ".codegluerignore").write_text("*.tmp\n")
        (tmp_dir / "a.tmp").write_text("t")
        (tmp_dir / "b.py").write_text("p")

        original = []
        collect_files([str(tmp_dir)], recursive=True, exclude_patterns=original)
        assert original == []

    # ── Tree rendering ────────────────────────────────────────────────

    def test_tree_render_truncation(self, tmp_dir):
        for i in range(15):
            (tmp_dir / f"file_{i:02d}.txt").write_text(f"{i}")

        paths = sorted(tmp_dir.glob("file_*.txt"))
        root = build_tree_structure(paths, tmp_dir)
        lines = render_tree(root, max_per_dir=5)

        assert len(lines) == 5  # 4 visible + 1 truncation
        assert "... (11 more items)" in lines[-1]
        assert lines[-1].startswith("└──")

    def test_tree_render_connectors_are_correct(self, tmp_dir):
        for name in ["a.txt", "b.txt", "c.txt"]:
            (tmp_dir / name).write_text("x")

        paths = sorted(tmp_dir.glob("*.txt"))
        root = build_tree_structure(paths, tmp_dir)
        lines = render_tree(root)

        assert lines[0].startswith("├── ")
        assert lines[1].startswith("├── ")
        assert lines[2].startswith("└── ")

    # ── ProjectStats ──────────────────────────────────────────────────

    def test_stats_accuracy(self, tmp_dir):
        a = tmp_dir / "a.py"
        a.write_text("x\ny\n")
        b = tmp_dir / "b.py"
        b.write_text("z\n")
        c = tmp_dir / "c.js"
        c.write_text("w")

        stats = ProjectStats()
        stats.ingest(a, "x\ny\n")
        stats.ingest(b, "z\n")
        stats.ingest(c, "w")

        assert stats.total_files == 3
        assert stats.total_lines == 4
        assert stats.total_chars == len("x\ny\n") + len("z\n") + len("w")
        assert stats.languages["python"] == 2
        assert stats.languages["javascript"] == 1

    # ── Priority sorting ──────────────────────────────────────────────

    def test_priority_sorting(self, tmp_dir):
        (tmp_dir / "a.txt").write_text("aaa")
        (tmp_dir / "b.txt").write_text("bbb")
        (tmp_dir / "README.md").write_text("readme")

        out = tmp_dir / "out.txt"
        config = GlueConfig(
            output_path=str(out), recursive=True,
            priority_patterns=["README.md"],
        )
        glue_files([str(tmp_dir)], config=config)
        content = out.read_text()

        pos_readme = content.index("README.md")
        pos_a = content.index("a.txt")
        pos_b = content.index("b.txt")
        assert pos_readme < pos_a
        assert pos_readme < pos_b

    # ── TOC anchors ───────────────────────────────────────────────────

    def test_toc_anchors_are_outside_code_fence(self, tmp_dir):
        (tmp_dir / "main.py").write_text("print(1)")
        out = tmp_dir / "out.md"
        config = GlueConfig(output_format="markdown", toc=True, output_path=str(out))
        glue_files([str(tmp_dir / "main.py")], config=config)
        content = out.read_text()

        anchor_pos = content.index('<a id="')
        fence_pos = content.index("```python")
        assert anchor_pos < fence_pos

    # ── Token estimation ──────────────────────────────────────────────

    def test_token_estimation_fallback(self, tmp_dir):
        (tmp_dir / "f.txt").write_text("hello world")
        out = tmp_dir / "out.txt"
        config = GlueConfig(estimate_tokens=True, output_path=str(out))

        import importlib
        orig_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def mock_import(name, *args, **kwargs):
            if name == "tiktoken":
                raise ImportError("mocked")
            return orig_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            # Clear tiktoken from cache if present
            tiktoken_mod = sys.modules.pop("tiktoken", None)
            try:
                glue_files([str(tmp_dir / "f.txt")], config=config)
            finally:
                if tiktoken_mod is not None:
                    sys.modules["tiktoken"] = tiktoken_mod

        content = out.read_text()
        assert "estimated (tiktoken not installed)" in content
        assert "🧠 Token Estimate:" in content

    def test_token_estimation_tiers(self, tmp_dir):
        (tmp_dir / "small.txt").write_text("x" * 100)
        out = tmp_dir / "out.txt"
        config = GlueConfig(estimate_tokens=True, output_path=str(out))

        # Mock tiktoken to return a controlled small value
        mock_enc = MagicMock()
        mock_enc.encode.return_value = [0] * 500  # 500 tokens → Small tier
        mock_tiktoken = MagicMock()
        mock_tiktoken.get_encoding.return_value = mock_enc

        with patch.dict(sys.modules, {"tiktoken": mock_tiktoken}):
            glue_files([str(tmp_dir / "small.txt")], config=config)

        content = out.read_text()
        assert "Small" in content

    # ── AI prompt ─────────────────────────────────────────────────────

    def test_ai_prompt_prepended(self, tmp_dir):
        (tmp_dir / "f.txt").write_text("data")
        out = tmp_dir / "out.txt"
        config = GlueConfig(
            ai_prompt="You are a helpful assistant.",
            output_path=str(out),
        )
        glue_files([str(tmp_dir / "f.txt")], config=config)
        content = out.read_text()
        assert content.startswith("<system_context>")
        assert "You are a helpful assistant." in content

    def test_ai_prompt_file(self, tmp_dir):
        prompt_file = tmp_dir / "prompt.txt"
        prompt_file.write_text("Analyze this code carefully.")
        (tmp_dir / "f.py").write_text("pass")
        out = tmp_dir / "out.txt"
        config = GlueConfig(
            ai_prompt_file=str(prompt_file),
            output_path=str(out),
        )
        glue_files([str(tmp_dir / "f.py")], config=config)
        content = out.read_text()
        assert "<system_context>" in content
        assert "Analyze this code carefully." in content
        assert "</system_context>" in content

    # ── Slug collision avoidance ──────────────────────────────────────

    def test_slug_collision_avoidance(self, tmp_dir):
        # Two files that produce the same base slug
        src_dir = tmp_dir / "src"
        src_dir.mkdir()
        (src_dir / "utils.py").write_text("pass")
        (tmp_dir / "src-utils.py").write_text("pass")

        out = tmp_dir / "out.md"
        config = GlueConfig(
            output_format="markdown", toc=True,
            output_path=str(out), recursive=True,
        )
        glue_files([str(tmp_dir)], config=config)
        content = out.read_text()

        # Extract all anchor IDs
        import re
        anchors = re.findall(r'<a id="([^"]+)"', content)
        assert len(anchors) >= 2
        assert len(set(anchors)) == len(anchors)  # all unique

    # ── Default config preserves existing behavior ────────────────────

    def test_glue_config_defaults_preserve_existing_behavior(self, tmp_dir, sample_files):
        files = list(sample_files.values())
        out = tmp_dir / "out.txt"
        _, count = glue_files(files, config=GlueConfig(output_path=str(out)))
        content = out.read_text()

        assert count == len(files)
        # No new features present
        assert "<system_context>" not in content
        assert "📊 PROJECT SUMMARY" not in content
        assert "📂 PROJECT STRUCTURE" not in content
        assert "📑 Table of Contents" not in content
        assert "🧠 Token Estimate" not in content
        # Original content is present
        for name in sample_files:
            assert f"BEGIN FILE: {name}" in content
            assert f"END FILE: {name}" in content
