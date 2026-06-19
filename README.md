# 📦 CodeGluer

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)

Glue multiple code files (and entire directories) into a single `.txt` or `.md` file. 

Perfect for sharing code context with AI assistants, code reviews, documentation, or archiving full projects.

## ✨ Features

- 📁 **Select & Glue** – Select files in your file manager, right‑click, and glue them instantly.
- 📂 **Directory Recursion** – Pass a folder and use `-r` to recursively grab all files inside.
- 🏷️ **Clear Markers** – Each file gets a `BEGIN FILE` / `END FILE` header and footer (Plain mode).
- 📝 **Markdown Mode** – Output pasteable code blocks with syntax highlighting for AI/Notion workflows.
- 🙈 **`.gitignore` Support** – Use `--respect-gitignore` to automatically exclude ignored files.
- 🎯 **Smart Filtering** – Use `--include` and `--exclude` with advanced glob patterns (e.g., `--exclude "node_modules/**"`).
- 🖱️ **Right‑Click Integration** – Works seamlessly from Nautilus (GNOME) and Nemo (Cinnamon) context menus.
- 🔔 **Desktop Notifications** – Get notified when the GUI operation completes.
- 💻 **CLI Support** – Use it from the terminal with powerful options.
- ⏱️ **Auto‑Timestamping** – Prevents accidental overwrites for default outputs by appending microsecond timestamps (explicit `--output` paths will still overwrite).

## 🐧 Why CodeGluer?

Most context-prep tools are built for macOS or run in VS Code. CodeGluer is built for **Linux desktop users**:

- **Native right-click integration** for Nautilus (GNOME) and Nemo (Cinnamon) — no terminal needed.
- **Pipe-friendly CLI** (`-o -`) for scripting and LLM piping workflows.
- Single-file install via `pipx` with no Node.js, no npm, no config files.

If you live in a Linux file manager and want to send code to an AI without leaving your workflow, CodeGluer is the tool for that.

## 📦 Dependencies

- **Python 3.8+**
- **pathspec** – Required for `.gitignore` support and advanced globbing (`**/*.py`).

*Note: `pathspec` is automatically installed as a core dependency when you install CodeGluer.*

## 📥 Installation

### For Standard Users
```bash
git clone https://github.com/fathriAbanoub/codegluer.git
cd codegluer
chmod +x install.sh
./install.sh
```
The installer will:
1. Install the Python package (and `pathspec`) using `pipx` (or fallback to `pip --user`).
2. Set up two Nautilus right‑click scripts (Plain and Markdown).
3. If Nemo is installed, set up two Nemo actions.

### For Developers (Editable Mode)
If you want to modify the code or run the test suite, install the package in editable mode:
```bash
git clone https://github.com/fathriAbanoub/codegluer.git
cd codegluer
pip install -e .
```

## 🖱️ Usage (Right‑Click)

1. Open your file manager (Nautilus or Nemo).
2. Select the files or folders you want to glue (Ctrl+Click or Shift+Click).
3. Right‑click on the selection.
   - **Nautilus:** Right‑click → Scripts → choose *Glue Code Files (Plain)* or *(Markdown)*.
   - **Nemo:** Right‑click → Nemo Actions → choose *Glue Code Files (Plain)* or *(Markdown)*.
4. A `glued_code.txt` or `glued_code.md` file will appear in the selected folder ✅

*💡 Smart GUI: If you select a folder, the tool automatically applies the `-r` (recursive) flag.*

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

# Pipe directly to an LLM (no temp file needed)
codegluer src/ -r --format markdown -o - | llm "explain this codebase"
```

## 🧠 Smart CLI Behaviors

- **Auto‑Timestamping:** For the default output (when no `--output` is specified), if the default output file already exists, CodeGluer appends a timestamp with microseconds to prevent overwrites. When you explicitly provide an output path with `--output` or `-o`, any existing file at that path will be overwritten without timestamp protection.
- **Graceful Degradation:** Missing or unreadable files are skipped with a warning; the tool glues the remaining files without crashing.
- **Space & Unicode Safe:** Handles filenames with spaces, parentheses, and special characters flawlessly.
- **Relative Display Names:** When recursing, files are labelled with their relative paths (e.g., `src/utils.py`) to avoid filename collisions.
- **`--ai-prompt` / `--ai-prompt-file`:** Prepend a custom text block before the code sections. Useful for adding instructions, project context, or a description that an AI assistant will see at the top of the file.

## 📄 Output Format

**Plain (default)**
Uses clear separator markers:
```text
==================== BEGIN FILE: src/main.py =====================

def main():
    print("Hello, World!")

===================== END FILE: src/main.py ======================
```

**Markdown**
Produces pasteable code blocks with syntax highlighting:
````markdown
### `src/main.py`

```python
def main():
    print("Hello, World!")
```
````

## 🧪 Testing

This project includes a comprehensive `pytest` suite covering unit tests, functional tests, CLI integration, advanced filtering, and stress tests.

```bash
# Install pytest (if not already installed)
pip install pytest

# Run all tests
pytest

# Run only the stress tests
pytest tests/test_codegluer.py::TestStress
```

## 📂 Project Structure

```text
codegluer/
├── pyproject.toml           # Package configuration & pytest settings
├── install.sh               # Installs package via pipx/pip & sets up GUI integrations
├── uninstall.sh             # Removes package & GUI integrations
├── codegluer/               # The core Python package
│   ├── __init__.py
│   ├── core.py              # Gluing logic, file collection, and filtering
│   └── cli.py               # Command-line interface
└── tests/                   # Pytest test suite
    ├── conftest.py
    └── test_codegluer.py
```

## 🗑️ Uninstall

```bash
cd codegluer
chmod +x uninstall.sh
./uninstall.sh
```
This removes the Python package via `pip`/`pipx`, deletes all Nautilus/Nemo integration files, and cleans up legacy “Code Combiner” leftovers.

## 🤝 Contributing

Contributions are welcome! Feel free to:
- Open issues for bugs or feature requests.
- Submit pull requests.
- Suggest improvements.

## 📝 License

[MIT License](LICENSE) – free for personal and commercial use.
