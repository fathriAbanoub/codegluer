# 📦 CodeGluer

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/fathriAbanoub/codegluer)

Glue multiple code files (and entire directories) into a single `.txt` or `.md` file.

Perfect for sharing code context with AI assistants, code reviews, documentation, or archiving full projects.

## ✨ Features

- 📁 **Select & Glue** – Select files in your file manager, right‑click, and glue them instantly.
- 🖱️ **GTK4 GUI Dialog** – Native configuration window to set format, exclude patterns, and toggle options before gluing.
- 🎨 **Theme Support** – Choose from **auto** (follows system theme), **light**, **dark**, or **roselle**; persists across sessions.
- 📂 **Directory Recursion** – Pass a folder and use `-r` to recursively grab all files inside.
- 🏷️ **Clear Markers** – Each file gets a `BEGIN FILE` / `END FILE` header and footer (Plain mode).
- 📝 **Markdown Mode** – Output pasteable code blocks with syntax highlighting for AI/Notion workflows.
- 🙈 **`.gitignore` Support** – Use `--respect-gitignore` to automatically exclude ignored files.
- 🎯 **Smart Filtering** – Use `--include` and `--exclude` with advanced glob patterns (e.g., `--exclude "node_modules/**"`).
- 🌳 **Tree Output** – Include a directory tree summary with `--tree` (use `--tree-depth` and `--tree-max-files` to limit).
- 📊 **Stats & Token Estimates** – Show file counts, line counts, and token estimates (powered by `tiktoken` if installed).
- 🔍 **Priority Order** – Control file ordering with `--priority` (glob patterns that appear first).
- 🚫 **`.codegluerignore`** – Project‑specific ignore rules (same format as `.gitignore`).
- 🔬 **Binary File Detection** – Skips files containing null bytes (binary) to avoid gluing garbage.
- 🖱️ **Right‑Click Integration** – Works seamlessly from Nautilus (GNOME) and Nemo (Cinnamon) context menus.
- 🔔 **Desktop Notifications** – Get notified when the GUI operation completes.
- 💻 **CLI Support** – Use it from the terminal with powerful options.
- ⏱️ **Auto‑Timestamping** – Prevents accidental overwrites for default outputs by appending microsecond timestamps (explicit `--output` paths will still overwrite).
- 📤 **Pipe to stdout** – Use `-o -` to write the glued content to standard output for piping to other tools.

## 🖼️ See it in action

**Smart GUI adapts to your selection:**

_When selecting files (directory-only options hidden):_

![GUI for files](screenshots/gui-roselle-files.png)

_When selecting a directory (Tree, TOC, .gitignore appear):_

![GUI for directory](screenshots/gui-roselle-directory.png)

**Clean, pasteable output:**

_Shows stats, tree, TOC, and syntax-highlighted code:_

![Markdown output](screenshots/output-markdown.png)

## 🐧 Why CodeGluer?

Most context-prep tools are built for macOS or run in VS Code. CodeGluer is built for **Linux desktop users**:

- **Native right-click integration** for Nautilus (GNOME) and Nemo (Cinnamon) — no terminal needed.
- **GTK4 native GUI** – clean, fast, and fits your desktop theme.
- **Pipe-friendly CLI** (`-o -`) for scripting and LLM piping workflows.
- **One‑command install** via `pipx` with no Node.js, no npm, no config files.

If you live in a Linux file manager and want to send code to an AI without leaving your workflow, CodeGluer is the tool for that.

## 📦 Dependencies

- **Python 3.8+**
- **pathspec** – Required for `.gitignore` support and advanced globbing (`**/*.py`).
- **PyGObject (GTK4 bindings)** – Required for the GUI. Install system‑wide:
  ```bash
  sudo apt install python3-gi gir1.2-gtk-4.0   # Debian/Ubuntu
  ```
- **tiktoken** – Optional; provides accurate token estimation. If not installed, a fallback `len(text)/4` is used. Install with `pip install tiktoken` or via the `ai` extra: `pip install codegluer[ai]`.

_Note: `pathspec` is automatically installed as a core dependency when you install CodeGluer._

## 📥 Installation

### For Standard Users (GUI + CLI)

```bash
git clone https://github.com/fathriAbanoub/codegluer.git
cd codegluer
chmod +x install.sh
./install.sh
```

The installer will:

1. Install the Python package (and `pathspec`) using `pipx` (or fallback to `pip --user`).
2. Set up one Nautilus right‑click script (named **CodeGluer**).
3. If Nemo is installed, set up one Nemo action (also named **CodeGluer**).

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
   - **Nautilus:** Right‑click → Scripts → **CodeGluer**.
   - **Nemo:** Right‑click → Nemo Actions → **CodeGluer**.
4. A GTK4 configuration dialog appears where you can:
   - Choose output format (Markdown or Plain)
   - Set exclude patterns (comma‑separated)
   - Toggle options (Stats, Token estimate, Tree, TOC, Respect .gitignore)
   - Change the theme (auto/light/dark/roselle)
5. Click **Glue!** – a notification will inform you of success or failure.

_💡 Smart GUI: If you select a folder, the tool automatically applies the `-r` (recursive) flag._

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

# Show a tree summary (limit depth and file count)
codegluer src/ -r --tree --tree-depth 3 --tree-max-files 100

# Prioritise specific files (they appear first)
codegluer src/ -r --priority "README.md" --priority "setup.py"

# Pipe directly to an LLM (no temp file needed)
codegluer src/ -r --format markdown -o - | llm "explain this codebase"

# Use a custom AI prompt from a file (prepended at the top)
codegluer src/ -r --ai-prompt-file context.txt -o output.md
```

## 🖥️ GUI from Terminal

You can also launch the GUI directly from the command line:

```bash
# Open GUI with specific files
codegluer-gui file1.py file2.js

# Preview the command without executing (useful for debugging)
codegluer-gui --dry-run src/
```

This opens the same GTK4 dialog, letting you configure options and glue files interactively.

> **Note:** The `codegluer-gui` command is installed by `install.sh` alongside the Python package. It is **not** a separate entry point in `pyproject.toml`; it is a standalone script placed in `~/.local/bin/` during installation.

## 🧠 Smart CLI Behaviors

- **Auto‑Timestamping:** For the default output (when no `--output` is specified), if the default output file already exists, CodeGluer appends a timestamp with microseconds to prevent overwrites. When you explicitly provide an output path with `--output` or `-o`, any existing file at that path will be overwritten without timestamp protection.
- **Graceful Degradation:** Missing or unreadable files are skipped with a warning; the tool glues the remaining files without crashing.
- **Space & Unicode Safe:** Handles filenames with spaces, parentheses, and special characters flawlessly.
- **Relative Display Names:** When recursing, files are labelled with their relative paths (e.g., `src/utils.py`) to avoid filename collisions.
- **`--ai-prompt` / `--ai-prompt-file`:** Prepend a custom text block before the code sections. Useful for adding instructions, project context, or a description that an AI assistant will see at the top of the file.
- **Binary File Detection:** Files containing null bytes (i.e., binary files) are automatically skipped to prevent corrupting the output.
- **`.codegluerignore`:** Project‑specific ignore rules can be placed in a `.codegluerignore` file (same syntax as `.gitignore`).
- **Exclude Validation (GUI):** If you enter patterns with spaces but no commas (e.g., `*.py *.js`), the GUI will prompt you to fix them (GTK 4.10+) or auto‑correct them to `*.py,*.js` (older GTK). This prevents common mistakes.

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

# Run GUI logic tests (no GTK required)
pytest tests/test_codegluer_gui.py
```

## 📂 Project Structure

```text
codegluer/
├── pyproject.toml               # Package configuration & pytest settings
├── README.md
├── LICENSE
├── install.sh                   # Installs package via pipx/pip & sets up GUI integrations
├── uninstall.sh                 # Removes package & GUI integrations
├── codegluer_gui.py             # GTK4 GUI application (executable script and importable module)
├── codegluer/                   # The core Python package
│   ├── __init__.py
│   ├── core.py                  # Gluing logic, file collection, and filtering
│   └── cli.py                   # Command-line interface
└── tests/                       # Pytest test suite
    ├── conftest.py
    ├── test_codegluer.py        # Core logic tests
    └── test_codegluer_gui.py    # GUI logic tests (no GTK display required)
```

## 🗑️ Uninstall

```bash
cd codegluer
chmod +x uninstall.sh
./uninstall.sh
```

This removes the Python package via `pip`/`pipx`, deletes all Nautilus/Nemo integration files, and cleans up legacy “Code Combiner” leftovers.

## 🔄 GUI Workflow (Sequence Diagram)

```mermaid
sequenceDiagram
    participant User
    participant GUI as CodeGluerWindow
    participant Logic as build_command()
    participant CLI as codegluer CLI
    participant Notify as notify-send

    User->>GUI: Click "Glue!"
    GUI->>GUI: Collect options, validate excludes
    alt Excludes have spaces but no commas
        GUI->>GUI: Show dialog (GTK 4.10+) or auto-fix
    end
    GUI->>Logic: build_command(files, opts)
    Logic-->>GUI: CLI argument list
    GUI->>GUI: save_theme(current_theme)
    GUI->>CLI: subprocess.run(cmd, timeout=60)
    alt Success (returncode == 0)
        CLI-->>GUI: returncode=0
        GUI->>Notify: notify-send "Created: {output_name}"
    else Non‑zero returncode
        CLI-->>GUI: returncode=1, stderr
        GUI->>Notify: notify-send "Failed: {stderr}"
    else Exception (including timeout)
        CLI-->>GUI: raises Exception
        GUI->>Notify: notify-send "Error: {exception}"
    end
    GUI->>GUI: close window
```

## 🤝 Contributing

Contributions are welcome! Feel free to:

- Open issues for bugs or feature requests.
- Submit pull requests.
- Suggest improvements.

## 📝 License

[MIT License](LICENSE) – free for personal and commercial use.
