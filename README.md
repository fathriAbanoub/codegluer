# 📦 CodeGluer

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)

**Glue multiple code files into a single `.txt` file with clear file markers.**

Perfect for sharing code context with AI assistants, code reviews, documentation, or archiving.

## ✨ Features

- 📁 **Select & Glue** – Select files in your file manager, right-click, and glue them instantly
- ️ **Clear Markers** – Each file gets a `BEGIN FILE` / `END FILE` header and footer
- 🖱️ **Right-Click Integration** – Works from Nautilus (GNOME) and Nemo (Cinnamon) context menus
- 🔔 **Desktop Notifications** – Get notified when the operation completes
- 💻 **CLI Support** – Use it from the terminal too
- 🐧 **Ubuntu Native** – No extra dependencies, just Python 3 (pre-installed on Ubuntu)

## 📥 Installation

```bash
git clone https://github.com/fathriAbanoub/codegluer.git
cd codegluer
chmod +x install.sh
./install.sh
```

The installer will:
1. Copy the gluer script to `~/.local/bin/codegluer`
2. Set up a Nautilus right-click script ("Scripts → Glue Code Files")
3. If Nemo is installed, set up a Nemo action too

## 🖱️ Usage (Right-Click)

1. Open your file manager (**Nautilus** or **Nemo**)
2. Select the code files you want to glue (Ctrl+Click or Shift+Click)
3. Right-click on the selection
4. Choose **Scripts → Glue Code Files (Plain)** or **Glue Code Files (Markdown)**
5. A `glued_code.txt` or `glued_code.md` file will appear in the same directory ✅

> **Note:** In Nautilus, scripts appear under **Right-Click → Scripts**.
> **Plain** gives the classic separator markers; **Markdown** gives pasteable code blocks.

##  Usage (Terminal)

```bash
# Glue files (output defaults to glued_code.txt in the same directory)
codegluer main.py utils.py config.json

# Specify a custom output file
codegluer src/*.py -o all_python_code.txt

# Glue specific files with a custom output path
codegluer app.js index.html style.css -o ~/Desktop/project_code.txt
```

### 🧠 Smart CLI Behaviors
- **Auto-Timestamping:** If `glued_code.txt` already exists, CodeGluer automatically creates `glued_code_YYYYMMDD_HHMMSS.txt` to prevent accidental overwrites.
- **Graceful Degradation:** If a file in your list is missing or unreadable, CodeGluer skips it with a warning and successfully glues the remaining files instead of crashing.
- **Space & Unicode Safe:** Handles filenames with spaces, parentheses, and special characters flawlessly.

## 📄 Output Format

The glued file uses clear markers to separate each file:

```text
==================== BEGIN FILE: main.py =====================

def main():
    print("Hello, World!")

if __name__ == "__main__":
    main()

===================== END FILE: main.py ======================

==================== BEGIN FILE: utils.py ====================

def add(a, b):
    return a + b

==================== END FILE: utils.py =====================
```

## 🧪 Testing

This project includes a comprehensive `pytest` suite to ensure reliability. It covers:
- **Unit Tests:** Header/footer formatting and math.
- **Functional Tests:** File reading, missing files, and binary handling.
- **CLI Integration:** End-to-end subprocess testing.
- **Stress Tests:** 1000+ files, 10MB+ files, and deep directory paths.

```bash
# Install pytest (if not already installed)
pip install pytest

# Run all tests
pytest

# Run only the stress tests
pytest tests/test_codegluer.py::TestStress
```

## 🗑️ Uninstall

```bash
cd codegluer
chmod +x uninstall.sh
./uninstall.sh
```

##  Contributing

Contributions are welcome! Feel free to:
- Open issues for bugs or feature requests
- Submit pull requests
- Suggest improvements

##  License

[MIT License](LICENSE) – free for personal and commercial use.
