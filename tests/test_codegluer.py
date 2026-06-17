import pytest
import subprocess
import sys
import os
from pathlib import Path

import codegluer


class TestHelpers:
    def test_build_header(self):
        header = codegluer.build_header("test.py")
        assert " BEGIN FILE: test.py " in header
        assert header.startswith("=")
        assert header.endswith("=")
        assert len(header) >= codegluer.SEPARATOR_LENGTH

    def test_build_footer(self):
        footer = codegluer.build_footer("test.py")
        assert " END FILE: test.py " in footer
        assert footer.startswith("=")
        assert footer.endswith("=")
        assert len(footer) >= codegluer.SEPARATOR_LENGTH

    def test_detect_language(self):
        assert codegluer.detect_language("main.py") == "python"
        assert codegluer.detect_language("app.js") == "javascript"
        assert codegluer.detect_language("style.css") == "css"
        assert codegluer.detect_language("unknown.xyz") == ""
        assert codegluer.detect_language("README.md") == "markdown"

    def test_sanitize_filename_for_markdown(self):
        # Normal filename
        assert codegluer.sanitize_filename_for_markdown("test.py") == "test.py"
        # Backticks -> HTML entity
        assert codegluer.sanitize_filename_for_markdown("test`file.py") == "test&#96;file.py"
        # Newlines -> spaces
        assert codegluer.sanitize_filename_for_markdown("test\nfile.py") == "test file.py"
        # Multiple
        assert codegluer.sanitize_filename_for_markdown("test`\nfile.py") == "test&#96; file.py"

    def test_build_markdown_section(self):
        # Basic case
        section = codegluer.build_markdown_section("test.py", "print('hello')")
        assert "### `test.py`" in section
        assert "```python" in section
        assert "print('hello')" in section
        assert section.count("```") == 2

        # Edge: content contains backticks
        content_with_backticks = "```\nsome code\n```"
        section = codegluer.build_markdown_section("test.py", content_with_backticks)
        # Should use a fence longer than 3 because content has 3 backticks
        assert "````python" in section or "`````python" in section
        assert "some code" in section

        # Edge: content has a very long run of backticks
        long_run = "`" * 100 + "code"
        section = codegluer.build_markdown_section("test.py", long_run)
        # Fence should be at least 101
        assert "`" * 101 in section

        # NEW: filename with backticks and newlines
        tricky_filename = "test`file\nwith_newline.py"
        section = codegluer.build_markdown_section(tricky_filename, "content")
        safe = codegluer.sanitize_filename_for_markdown(tricky_filename)
        assert f"### `{safe}`" in section
        # Ensure backticks are escaped and newlines removed
        assert "&#96;" in section
        assert "with_newline" in section  # newline replaced with space


class TestGlueFiles:
    def test_basic_glue_plain(self, tmp_dir, sample_files):
        files = list(sample_files.values())
        output_path = tmp_dir / "glued.txt"
        out, count = codegluer.glue_files(
            files, output_path=str(output_path), output_format="plain"
        )
        assert count == len(files)
        content = output_path.read_text()
        for name in sample_files:
            assert f"BEGIN FILE: {name}" in content
            assert f"END FILE: {name}" in content
            assert sample_files[name].read_text() in content

    def test_basic_glue_markdown(self, tmp_dir, sample_files):
        files = list(sample_files.values())
        output_path = tmp_dir / "glued.md"
        out, count = codegluer.glue_files(
            files, output_path=str(output_path), output_format="markdown"
        )
        assert count == len(files)
        content = output_path.read_text()
        for name, path in sample_files.items():
            assert f"### `{name}`" in content
            if name.endswith(".py"):
                assert "```python" in content
            elif name.endswith(".js"):
                assert "```javascript" in content
            else:
                assert "```text" in content or "```" in content
            assert path.read_text() in content

    def test_glue_without_output_path_plain(self, tmp_dir, sample_files):
        files = list(sample_files.values())
        out, count = codegluer.glue_files(files, output_path=None, output_format="plain")
        expected = tmp_dir / "glued_code.txt"
        assert out == str(expected)
        assert expected.exists()

    def test_glue_without_output_path_markdown(self, tmp_dir, sample_files):
        files = list(sample_files.values())
        out, count = codegluer.glue_files(files, output_path=None, output_format="markdown")
        expected = tmp_dir / "glued_code.md"
        assert out == str(expected)
        assert expected.exists()

    def test_glue_with_existing_output_plain(self, tmp_dir, sample_files):
        files = list(sample_files.values())
        existing = tmp_dir / "glued_code.txt"
        existing.touch()
        out, count = codegluer.glue_files(files, output_path=None, output_format="plain")
        assert out != str(existing)
        assert Path(out).exists()
        assert out.startswith(str(tmp_dir / "glued_code_"))
        assert out.endswith(".txt")

    def test_glue_with_existing_output_markdown(self, tmp_dir, sample_files):
        files = list(sample_files.values())
        existing = tmp_dir / "glued_code.md"
        existing.touch()
        out, count = codegluer.glue_files(files, output_path=None, output_format="markdown")
        assert out != str(existing)
        assert Path(out).exists()
        assert out.startswith(str(tmp_dir / "glued_code_"))
        assert out.endswith(".md")

    def test_glue_with_custom_output(self, tmp_dir, sample_files):
        custom = tmp_dir / "custom.txt"
        files = list(sample_files.values())
        out, count = codegluer.glue_files(
            files, output_path=str(custom), output_format="plain"
        )
        assert out == str(custom)
        assert custom.exists()

    def test_invalid_output_format(self, tmp_dir, sample_files):
        files = list(sample_files.values())
        with pytest.raises(ValueError) as exc:
            codegluer.glue_files(files, output_format="invalid")
        assert "Invalid output_format" in str(exc.value)

    def test_empty_file(self, tmp_dir):
        empty = tmp_dir / "empty.txt"
        empty.touch()
        files = [empty]
        out, count = codegluer.glue_files(
            files, output_path=str(tmp_dir / "out.txt"), output_format="plain"
        )
        assert count == 1
        content = Path(out).read_text()
        assert "BEGIN FILE: empty.txt" in content
        assert "END FILE: empty.txt" in content

    def test_binary_file_content(self, tmp_dir):
        binary = tmp_dir / "binary.bin"
        binary.write_bytes(b"\xff\xfe\x00\x01")
        files = [binary]
        out, count = codegluer.glue_files(
            files, output_path=str(tmp_dir / "out.txt"), output_format="plain"
        )
        assert count == 1
        content = Path(out).read_text(encoding="utf-8", errors="replace")
        assert "BEGIN FILE: binary.bin" in content
        assert "END FILE: binary.bin" in content

    def test_missing_file(self, tmp_dir):
        missing = tmp_dir / "missing.txt"
        files = [missing]
        with pytest.raises(codegluer.NoReadableFilesError):
            codegluer.glue_files(files, output_path=str(tmp_dir / "out.txt"))

    def test_directory_in_files(self, tmp_dir):
        dir_path = tmp_dir / "subdir"
        dir_path.mkdir()
        files = [dir_path]
        with pytest.raises(codegluer.NoReadableFilesError):
            codegluer.glue_files(files, output_path=str(tmp_dir / "out.txt"))

    def test_mixed_valid_and_missing_files(self, tmp_dir, sample_files):
        valid_file = list(sample_files.values())[0]
        missing_file = tmp_dir / "ghost.txt"
        files = [valid_file, missing_file]
        output_path = tmp_dir / "out.txt"
        out, count = codegluer.glue_files(
            files, output_path=str(output_path), output_format="plain"
        )
        assert count == 1
        assert output_path.exists()
        content = output_path.read_text()
        assert "BEGIN FILE: a.py" in content
        assert "ghost.txt" not in content

    def test_no_files(self):
        with pytest.raises(codegluer.NoFilesError):
            codegluer.glue_files([])


class TestCLI:
    def test_cli_basic_plain(self, tmp_dir, sample_files):
        files = list(sample_files.values())
        script_path = Path(__file__).parent.parent / "codegluer.py"
        cmd = [sys.executable, str(script_path)] + [str(f) for f in files]
        result = subprocess.run(cmd, capture_output=True, text=True)
        assert result.returncode == 0
        assert "Glued" in result.stdout
        out_path = tmp_dir / "glued_code.txt"
        assert out_path.exists()
        content = out_path.read_text()
        for name in sample_files:
            assert f"BEGIN FILE: {name}" in content

    def test_cli_markdown_format(self, tmp_dir, sample_files):
        files = list(sample_files.values())
        script_path = Path(__file__).parent.parent / "codegluer.py"
        cmd = [
            sys.executable, str(script_path),
            "--format", "markdown",
            "-o", str(tmp_dir / "out.md")
        ] + [str(f) for f in files]
        result = subprocess.run(cmd, capture_output=True, text=True)
        assert result.returncode == 0
        out_path = tmp_dir / "out.md"
        assert out_path.exists()
        content = out_path.read_text()
        for name in sample_files:
            assert f"### `{name}`" in content

    def test_cli_with_output(self, tmp_dir, sample_files):
        files = list(sample_files.values())
        script_path = Path(__file__).parent.parent / "codegluer.py"
        custom = tmp_dir / "my_output.txt"
        cmd = [sys.executable, str(script_path), "-o", str(custom)] + [str(f) for f in files]
        result = subprocess.run(cmd, capture_output=True, text=True)
        assert result.returncode == 0
        assert custom.exists()

    def test_cli_error_missing_file(self, tmp_dir):
        script_path = Path(__file__).parent.parent / "codegluer.py"
        missing = tmp_dir / "does_not_exist.txt"
        cmd = [sys.executable, str(script_path), str(missing)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        assert result.returncode != 0
        assert "Error: No files could be read." in result.stderr

    def test_cli_help(self, tmp_dir):
        script_path = Path(__file__).parent.parent / "codegluer.py"
        cmd = [sys.executable, str(script_path), "-h"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        assert result.returncode == 0
        assert "Glue multiple code files" in result.stdout


class TestStress:
    def test_many_files(self, tmp_dir):
        files = []
        for i in range(1000):
            p = tmp_dir / f"file_{i:04d}.txt"
            p.write_text(f"Content {i}\n")
            files.append(p)
        output = tmp_dir / "out.txt"
        out, count = codegluer.glue_files(
            files, output_path=str(output), output_format="plain"
        )
        assert count == 1000
        assert output.exists()
        content = output.read_text()
        for i in range(1000):
            assert f"BEGIN FILE: file_{i:04d}.txt" in content

    def test_large_file(self, tmp_dir, large_file):
        files = [large_file]
        output = tmp_dir / "out.txt"
        out, count = codegluer.glue_files(
            files, output_path=str(output), output_format="plain"
        )
        assert count == 1
        assert output.exists()
        size = output.stat().st_size
        expected_min = 10 * 1024 * 1024
        assert size >= expected_min

    def test_deep_nested_paths(self, tmp_dir):
        deep_dir = tmp_dir / "a" / "b" / "c" / "d" / "e"
        deep_dir.mkdir(parents=True)
        deep_file = deep_dir / "deep.txt"
        deep_file.write_text("deep content")
        output = tmp_dir / "out.txt"
        out, count = codegluer.glue_files(
            [deep_file], output_path=str(output), output_format="plain"
        )
        assert count == 1
        content = output.read_text()
        assert "BEGIN FILE: deep.txt" in content
        assert "deep content" in content

    def test_special_characters_in_filename(self, tmp_dir):
        filename = "héllo (1) world!.txt"
        p = tmp_dir / filename
        p.write_text("special")
        output = tmp_dir / "out.txt"
        out, count = codegluer.glue_files(
            [p], output_path=str(output), output_format="plain"
        )
        assert count == 1
        content = output.read_text()
        assert f"BEGIN FILE: {filename}" in content

    def test_very_long_line(self, tmp_dir):
        long_line = "x" * 1024 * 1024
        p = tmp_dir / "long.txt"
        p.write_text(long_line)
        output = tmp_dir / "out.txt"
        out, count = codegluer.glue_files(
            [p], output_path=str(output), output_format="plain"
        )
        assert count == 1
        content = output.read_text()
        assert long_line in content

    def test_mixed_file_types_and_sizes(self, tmp_dir):
        files = []
        for i in range(100):
            p = tmp_dir / f"small_{i}.txt"
            p.write_text("s" * 100)
            files.append(p)
        for i in range(10):
            p = tmp_dir / f"med_{i}.txt"
            p.write_text("m" * 1024 * 100)
            files.append(p)
        large = tmp_dir / "large_one.txt"
        large.write_text("L" * 1024 * 1024)
        files.append(large)

        output = tmp_dir / "out.txt"
        out, count = codegluer.glue_files(
            files, output_path=str(output), output_format="plain"
        )
        assert count == len(files)
        assert output.exists()
        total_size = sum(p.stat().st_size for p in files)
        output_size = output.stat().st_size
        assert output_size > total_size
