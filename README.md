# 📦 CodeGluer

**Glue multiple code files into a single `.txt` file with clear file markers.**

Perfect for sharing code context with AI assistants, code reviews, documentation, or archiving.

## ✨ Features

- 📁 **Select & Glue** – Select files in your file manager, right-click, and glue them instantly
- 🏷️ **Clear Markers** – Each file gets a `BEGIN FILE` / `END FILE` header and footer
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
4. Choose **Scripts → Glue Code Files**
5. A `glued_code.txt` file will appear in the same directory ✅

> **Note:** In Nautilus, scripts appear under **Right-Click → Scripts → Glue Code Files**.

## 💻 Usage (Terminal)

```bash
# Glue files (output defaults to glued_code.txt in the same directory)
codegluer main.py utils.py config.json

# Specify a custom output file
codegluer src/*.py -o all_python_code.txt

# Glue specific files with a custom output path
codegluer app.js index.html style.css -o ~/Desktop/project_code.txt
```

## 📄 Output Format

The glued file uses clear markers to separate each file:

```
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

## 🗑️ Uninstall

```bash
cd codegluer
chmod +x uninstall.sh
./uninstall.sh
```

## 🤝 Contributing

Contributions are welcome! Feel free to:

- Open issues for bugs or feature requests
- Submit pull requests
- Suggest improvements

## 📝 License

[MIT License](LICENSE) – free for personal and commercial use.
