import sys
import pytest
from pathlib import Path
from unittest.mock import patch
import codegluer
from codegluer import cli

# ----------------------------------------------------------------------
# Unit tests
# ----------------------------------------------------------------------
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
        assert codegluer.sanitize_filename_for_markdown("test.py") == "test.py"
        assert codegluer.sanitize_filename_for_markdown("test`file.py") == "test&#96;file.py"
        assert codegluer.sanitize_filename_for_markdown("test\nfile.py") == "test file.py"
        assert codegluer.sanitize_filename_for_markdown("test`\nfile.py") == "test&#96; file.py"

    def test_build_markdown_section(self):
        section = codegluer.build_markdown_section("test.py", "print('hello')")
        assert "### `test.py`" in section
        assert "```python" in section
        assert "print('hello')" in section
        assert section.count("```") == 2

        content_with_backticks = "```\nsome code\n```"
        section = codegluer.build_markdown_section("test.py", content_with_backticks)
        assert "````python" in section or "`````python" in section
        assert "some code" in section

        long_run = "`" * 100 + "code"
        section = codegluer.build_markdown_section("test.py", long_run)
        assert "`" * 101 in section

        tricky_filename = "test`file\nwith_newline.py"
        section = codegluer.build_markdown_section(tricky_filename, "content")
        safe = codegluer.sanitize_filename_for_markdown(tricky_filename)
        assert f"### `{safe}`" in section
        assert "&#96;" in section
        assert "with_newline" in section

# ----------------------------------------------------------------------
# Functional tests using glue_files directly
# ----------------------------------------------------------------------
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

# ----------------------------------------------------------------------
# CLI tests (using patch and capsys)
# ----------------------------------------------------------------------
class TestCLI:
    def test_cli_basic_plain(self, tmp_dir, sample_files, capsys):
        files = list(sample_files.values())
        out_path = tmp_dir / "glued_code.txt"
        test_args = ["codegluer", "-o", str(out_path)] + [str(f) for f in files]
        with patch.object(sys, 'argv', test_args):
            cli.main()
        captured = capsys.readouterr()
        assert "✅ Glued" in captured.out
        assert out_path.exists()
        content = out_path.read_text()
        for name in sample_files:
            assert f"BEGIN FILE: {name}" in content

    def test_cli_markdown_format(self, tmp_dir, sample_files, capsys):
        files = list(sample_files.values())
        out_path = tmp_dir / "out.md"
        test_args = [
            "codegluer", "--format", "markdown", "-o", str(out_path)
        ] + [str(f) for f in files]
        with patch.object(sys, 'argv', test_args):
            cli.main()
        assert out_path.exists()
        content = out_path.read_text()
        for name in sample_files:
            assert f"### `{name}`" in content

    def test_cli_with_output(self, tmp_dir, sample_files, capsys):
        files = list(sample_files.values())
        custom = tmp_dir / "my_output.txt"
        test_args = ["codegluer", "-o", str(custom)] + [str(f) for f in files]
        with patch.object(sys, 'argv', test_args):
            cli.main()
        assert custom.exists()

    def test_cli_error_missing_file(self, tmp_dir, capsys):
        missing = tmp_dir / "does_not_exist.txt"
        test_args = ["codegluer", str(missing)]
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit) as exc:
                cli.main()
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "No files could be read after filtering." in captured.err

    def test_cli_help(self, capsys):
        test_args = ["codegluer", "-h"]
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit) as exc:
                cli.main()
        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "Glue multiple code files" in captured.out

    def test_cli_version(self, capsys):
        test_args = ["codegluer", "--version"]
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit) as exc:
                cli.main()
        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert f"CodeGluer {codegluer.__version__}" in captured.out

# ----------------------------------------------------------------------
# Stress tests
# ----------------------------------------------------------------------
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

# ----------------------------------------------------------------------
# Advanced tests (recursion, gitignore, filters)
# ----------------------------------------------------------------------
class TestAdvancedCollection:
    def test_recursive_directory(self, tmp_dir):
        (tmp_dir / "sub").mkdir()
        (tmp_dir / "sub" / "a.txt").write_text("a")
        (tmp_dir / "b.txt").write_text("b")
        
        files = codegluer.collect_files([str(tmp_dir)], recursive=True)
        assert len(files) == 2
        assert {f.name for f in files} == {"a.txt", "b.txt"}

    def test_include_exclude_with_pathspec(self, tmp_dir):
        (tmp_dir / "src").mkdir()
        (tmp_dir / "src" / "main.py").write_text("")
        (tmp_dir / "src" / "test.js").write_text("")
        (tmp_dir / "dist").mkdir()
        (tmp_dir / "dist" / "bundle.js").write_text("")
        
        files = codegluer.collect_files(
            [str(tmp_dir)], recursive=True,
            include_patterns=["**/*.py", "**/*.js"],
            exclude_patterns=["dist/"]
        )
        
        assert len(files) == 2
        assert {f.name for f in files} == {"main.py", "test.js"}

    def test_gitignore_respect_anchored(self, tmp_dir):
        (tmp_dir / ".gitignore").write_text("/build/\n")
        (tmp_dir / "build").mkdir()
        (tmp_dir / "build" / "out.txt").write_text("ignore me")
        
        (tmp_dir / "sub").mkdir()
        (tmp_dir / "sub" / "build").mkdir()
        (tmp_dir / "sub" / "build" / "keep.txt").write_text("keep me")
        
        files = codegluer.collect_files(
            [str(tmp_dir)], recursive=True, respect_gitignore=True
        )
        
        file_names = {f.name for f in files}
        assert "keep.txt" in file_names
        assert "out.txt" not in file_names

    def test_gitignore_respect_nested(self, tmp_dir):
        (tmp_dir / ".gitignore").write_text("*.log\n")
        (tmp_dir / "sub").mkdir()
        (tmp_dir / "sub" / ".gitignore").write_text("*.tmp\n")
        
        (tmp_dir / "a.log").write_text("log")
        (tmp_dir / "sub" / "b.tmp").write_text("tmp")
        (tmp_dir / "sub" / "c.txt").write_text("text")
        
        files = codegluer.collect_files(
            [str(tmp_dir)], recursive=True, respect_gitignore=True
        )
        
        file_names = {f.name for f in files}
        assert "c.txt" in file_names
        assert "a.log" not in file_names
        assert "b.tmp" not in file_names

    def test_display_names_are_relative(self, tmp_dir):
        (tmp_dir / "src").mkdir()
        (tmp_dir / "src" / "utils.py").write_text("pass")
        
        out_path = tmp_dir / "out.txt"
        codegluer.glue_files([str(tmp_dir / "src")], output_path=str(out_path), recursive=True)
        content = out_path.read_text()
        assert "BEGIN FILE: utils.py" in content 
        
        out_path2 = tmp_dir / "out2.txt"
        codegluer.glue_files([str(tmp_dir)], output_path=str(out_path2), recursive=True)
        content2 = out_path2.read_text()
        assert "BEGIN FILE: src/utils.py" in content2

    def test_exclude_prunes_directories(self, tmp_dir):
        (tmp_dir / "node_modules").mkdir()
        (tmp_dir / "node_modules" / "deep").mkdir()
        (tmp_dir / "node_modules" / "deep" / "file.js").write_text("ignore")
        (tmp_dir / "src").mkdir()
        (tmp_dir / "src" / "main.js").write_text("keep")
        
        files = codegluer.collect_files(
            [str(tmp_dir)], recursive=True,
            exclude_patterns=["node_modules/"]
        )
        assert len(files) == 1
        assert files[0].name == "main.js"

    def test_include_filter_works_with_recursion(self, tmp_dir):
        (tmp_dir / "a.py").write_text("")
        (tmp_dir / "b.js").write_text("")
        (tmp_dir / "sub").mkdir()
        (tmp_dir / "sub" / "c.py").write_text("")
        
        files = codegluer.collect_files(
            [str(tmp_dir)], recursive=True,
            include_patterns=["*.py"]
        )
        assert len(files) == 2
        assert {f.name for f in files} == {"a.py", "c.py"}

    def test_relative_display_names_with_multiple_inputs(self, tmp_dir):
        (tmp_dir / "project1").mkdir()
        (tmp_dir / "project1" / "main.py").write_text("")
        (tmp_dir / "project2").mkdir()
        (tmp_dir / "project2" / "utils.py").write_text("")
        
        out_path = tmp_dir / "out.txt"
        codegluer.glue_files(
            [str(tmp_dir / "project1"), str(tmp_dir / "project2")],
            output_path=str(out_path),
            recursive=True
        )
        content = out_path.read_text()
        assert "BEGIN FILE: project1/main.py" in content
        assert "BEGIN FILE: project2/utils.py" in content
