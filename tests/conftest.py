import sys
from pathlib import Path

# Ensure the project root is in the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import tempfile
import os
import shutil

@pytest.fixture
def tmp_dir():
    """Create a temporary directory and clean up after test."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)

@pytest.fixture
def sample_files(tmp_dir):
    """Create a set of sample files with known content."""
    files = {}
    contents = {
        "a.py": "print('hello')\n",
        "b.js": "console.log('world');\n",
        "c.txt": "Hello, world!",
    }
    for name, content in contents.items():
        p = tmp_dir / name
        p.write_text(content, encoding="utf-8")
        files[name] = p
    return files

@pytest.fixture
def large_file(tmp_dir):
    """Create a large file (~10 MB) for stress testing."""
    p = tmp_dir / "large.txt"
    chunk = "a" * 1024 * 1024  # 1 MB
    with open(p, "w", encoding="utf-8") as f:
        for _ in range(10):
            f.write(chunk)
    return p
