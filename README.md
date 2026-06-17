# 📦 CodeGluer

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)

**Glue multiple code files (and entire directories) into a single `.txt` or `.md` file.**

Perfect for sharing code context with AI assistants, code reviews, documentation, or archiving full projects.

---

## ✨ Features

- 📁 **Select & Glue** – Select files in your file manager, right‑click, and glue them instantly.
- 📂 **Directory Recursion** – Pass a folder and use `-r` to recursively grab all files inside.
- 🏷️ **Clear Markers** – Each file gets a `BEGIN FILE` / `END FILE` header and footer (Plain mode).
- 📝 **Markdown Mode** – Output pasteable code blocks with syntax highlighting for AI/Notion workflows.
- 🙈 **`.gitignore` Support** – Use `--respect-gitignore` to automatically exclude ignored files (requires `pathspec`).
- 🎯 **Smart Filtering** – Use `--include` and `--exclude` with glob patterns (e.g., `--exclude "node_modules/**"`).
- 🖱️ **Right‑Click Integration** – Works from Nautilus (GNOME) and Nemo (Cinnamon) context menus.
- 🔔 **Desktop Notifications** – Get notified when the operation completes.
- 💻 **CLI Support** – Use it from the terminal with powerful options.
- 🐧 **Ubuntu Native** – Minimal dependencies; Python 3 is pre‑installed on Ubuntu.

---

## 📦 Dependencies

- **Python 3.8+** (standard)
- **Optional but recommended:** [pathspec](https://pypi.org/project/pathspec/) for `.gitignore` support and advanced globbing (`**/*.py`).

If `pathspec` is not installed, CodeGluer gracefully falls back to basic `fnmatch` filtering.

```bash
pip install pathspec
```

*The installer (`install.sh`) will attempt to install `pathspec` automatically.*

---

## 📥 Installation

```bash
git clone https://github.com/fathriAbanoub/codegluer.git
cd codegluer
chmod +x install.sh
./install.sh
```

The installer will:
1. Copy the gluer script to `~/.local/bin/codegluer`.
2. Automatically install the `pathspec` library (if not already present).
3. Set up two Nautilus right‑click scripts (**Glue Code Files (Plain)** and **Glue Code Files (Markdown)**).
4. If Nemo is installed, set up two Nemo actions with the same names.

---

## 🖱️ Usage (Right‑Click)

1. Open your file manager (**Nautilus** or **Nemo**).
2. Select the files or folders you want to glue (Ctrl+Click or Shift+Click).
3. Right‑click on the selection.
4. Depending on your file manager:
   - **Nautilus**: Right‑click → **Scripts** → choose **Glue Code Files (Plain)** or **Glue Code Files (Markdown)**.
   - **Nemo**: Right‑click → **Nemo Actions** (or directly in the context menu) → choose **Glue Code Files (Plain)** or **Glue Code Files (Markdown)**.
5. A `glued_code.txt` or `glued_code.md` file will appear in the selected folder ✅

> **Note:** The **Plain** option gives the classic separator markers; **Markdown** gives pasteable code blocks.

---

## 💻 Usage (Terminal)

```bash
# Glue explicit files (plain format)
codegluer main.py utils.py config.json

# Glue files in Markdown format (defaults to glued_code.md)
codegluer main.py utils.py --format markdown

# Recursively glue a whole directory
codegluer src/ -r --format markdown -o project_dump.md

# Respect .gitignore and exclude specific folders
codegluer . -r --respect-gitignore --exclude "dist/**" --exclude "*.log"

# Only include specific file types (using glob patterns)
codegluer src/ -r --include "**/*.py" --include "**/*.ts"

# Combine explicit files and directories with custom output
codegluer main.py lib/ --recursive --format plain -o combined.txt

# Use advanced exclude patterns (with pathspec installed)
codegluer project/ -r --respect-gitignore --exclude "**/__pycache__/" --exclude "*.tmp"
```

### 🧠 Smart CLI Behaviors
- **Auto‑Timestamping:** If the output file already exists, CodeGluer appends a timestamp with microseconds to prevent overwrites.
- **Graceful Degradation:** Missing or unreadable files are skipped with a warning; the tool glues the remaining files without crashing.
- **Space & Unicode Safe:** Handles filenames with spaces, parentheses, and special characters flawlessly.
- **Relative Display Names:** When recursing, files are labelled with their relative paths (e.g., `src/utils.py`) to avoid filename collisions.

---

## 📄 Output Format

### Plain (default)
Uses clear separator markers:
```text
==================== BEGIN FILE: src/main.py =====================

def main():
    print("Hello, World!")

===================== END FILE: src/main.py ======================
```

### Markdown
Produces pasteable code blocks with syntax highlighting:
````markdown
### `src/main.py`

```python
def main():
    print("Hello, World!")
```
````

---

## 🧪 Testing

This project includes a comprehensive `pytest` suite covering:
- **Unit Tests:** Header/footer formatting, markdown fencing, language detection.
- **Functional Tests:** File reading, missing files, binary handling, format validation.
- **CLI Integration:** End‑to‑end subprocess testing.
- **Advanced Features:** Recursion, `.gitignore` respect, include/exclude filters, and relative display names.
- **Stress Tests:** 1000+ files, 10MB+ files, deep directory paths.

```bash
# Install pytest (if not already installed)
pip install pytest

# Run all tests
pytest

# Run only the stress tests
pytest tests/test_codegluer.py::TestStress
```

---

## 🗑️ Uninstall

```bash
cd codegluer
chmod +x uninstall.sh
./uninstall.sh
```

This removes the main script, all Nautilus/Nemo integration files, and cleans up legacy “Code Combiner” leftovers.

---

## 🤝 Contributing

Contributions are welcome! Feel free to:
- Open issues for bugs or feature requests.
- Submit pull requests.
- Suggest improvements.

---

## 📝 License

[MIT License](LICENSE) – free for personal and commercial use.
