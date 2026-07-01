#!/usr/bin/env bash
# ============================================================
#  CodeGluer GUI – Installer
#  Sets up the Python package and GTK4 right-click context menus.
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════╗"
echo "║      CodeGluer GUI – Installer           ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

# ----------------------------------------------------------
# 1. Check for GTK4 Python bindings (moved earlier)
# ----------------------------------------------------------
echo -e "${YELLOW}➜ Checking GTK4 Python bindings...${NC}"
if python3 -c "import gi; gi.require_version('Gtk', '4.0')" 2>/dev/null; then
    echo -e "  ${GREEN}✔ GTK4 Python bindings available.${NC}"
else
    echo -e "  ${RED}✘ GTK4 Python bindings (PyGObject) not found.${NC}"
    echo -e "  ${YELLOW}  Install with: sudo apt install python3-gi gir1.2-gtk-4.0${NC}"
    echo -e "  ${YELLOW}  (or your distro's equivalent)${NC}"
    exit 1
fi

# ----------------------------------------------------------
# 2. Install the Python package (codegluer CLI)
# ----------------------------------------------------------
echo -e "${YELLOW}➜ Installing CodeGluer Python package...${NC}"
if command -v pipx &>/dev/null; then
    pipx install "$SCRIPT_DIR" --force
    echo -e "  ${GREEN}✔ Installed via pipx.${NC}"
else
    echo -e "  ${YELLOW}⚠ pipx not found, falling back to pip --user.${NC}"
    python3 -m pip install --user "$SCRIPT_DIR"
    echo -e "  ${GREEN}✔ Installed via pip --user.${NC}"
fi

# Ensure ~/.local/bin is on PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo -e "  ${YELLOW}⚠ ~/.local/bin is not on your PATH."
    echo -e "     Add this line to your ~/.bashrc or ~/.zshrc:"
    echo -e "     export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
fi

# ----------------------------------------------------------
# 3. Install the GUI script
# ----------------------------------------------------------
echo -e "${YELLOW}➜ Installing CodeGluer GUI script...${NC}"
GUI_SRC="$SCRIPT_DIR/codegluer_gui.py"
GUI_DEST="$HOME/.local/bin/codegluer-gui"

if [[ ! -f "$GUI_SRC" ]]; then
    echo -e "${RED}✘ codegluer_gui.py not found next to install.sh.${NC}" >&2
    exit 1
fi

# Ensure target directory exists
mkdir -p "$(dirname "$GUI_DEST")"

cp -f "$GUI_SRC" "$GUI_DEST"
chmod +x "$GUI_DEST"
echo -e "  ${GREEN}✔ Installed: $GUI_DEST${NC}"

# ----------------------------------------------------------
# 4. Nautilus integration (GNOME) — script in ~/.local/share/nautilus/scripts/
# ----------------------------------------------------------
NAUTILUS_SCRIPT_DIR="$HOME/.local/share/nautilus/scripts"
echo -e "${YELLOW}➜ Setting up Nautilus right-click integration...${NC}"
mkdir -p "$NAUTILUS_SCRIPT_DIR"

cat > "$NAUTILUS_SCRIPT_DIR/CodeGluer" << 'NAUTILUS_EOF'
#!/usr/bin/env bash
# Nautilus script — launches CodeGluer GUI with selected files.
# Nautilus passes paths via env var (newline-separated), not positional args.
IFS=$'\n' read -r -d '' -a files <<< "$NAUTILUS_SCRIPT_SELECTED_FILE_PATHS"
exec "$HOME/.local/bin/codegluer-gui" "${files[@]}"
NAUTILUS_EOF
chmod +x "$NAUTILUS_SCRIPT_DIR/CodeGluer"
echo -e "  ${GREEN}✔ Nautilus script: CodeGluer${NC}"

# ----------------------------------------------------------
# 5. Nemo integration (Cinnamon) — .nemo_action file
# ----------------------------------------------------------
if command -v nemo &>/dev/null; then
    echo -e "${YELLOW}➜ Nemo detected – setting up Nemo action...${NC}"
    NEMO_ACTION_DIR="$HOME/.local/share/nemo/actions"
    mkdir -p "$NEMO_ACTION_DIR"

    cat > "$NEMO_ACTION_DIR/codegluer.nemo_action" <<EOF
[Nemo Action]
Name=CodeGluer
Comment=Glue selected files/folders into a single file (GTK4 dialog)
Exec=$HOME/.local/bin/codegluer-gui %F
Icon-Name=text-x-generic
Selection=notnone
Extensions=any;
EOF
    echo -e "  ${GREEN}✔ Nemo action: CodeGluer${NC}"
else
    echo -e "  ${YELLOW}ℹ  Nemo not detected – skipping.${NC}"
fi

echo ""
echo -e "${GREEN}══════════════════════════════════════════${NC}"
echo -e "${GREEN}  Installation complete! 🎉${NC}"
echo -e "${GREEN}══════════════════════════════════════════${NC}"
echo ""
echo "  How to use:"
echo "    1. Open your file manager (Nautilus / Nemo)"
echo "    2. Select files or folders"
echo "    3. Right-click → Scripts → CodeGluer  (Nautilus)"
echo "       Right-click → CodeGluer             (Nemo)"
echo "    4. Configure options in the GTK4 dialog"
echo ""
echo "  Terminal usage:"
echo "    codegluer-gui file1.py file2.js"
echo "    codegluer-gui --dry-run src/   (print command, don't run)"
echo ""