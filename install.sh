#!/usr/bin/env bash
# ============================================================
#  CodeGluer – Installer
#  Sets up the right-click context menu integration for
#  Nautilus (GNOME Files) and Nemo (Cinnamon Files).
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/.local/bin"
GLUER_BIN="$INSTALL_DIR/codegluer"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════╗"
echo "║         CodeGluer – Installer            ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

# ----------------------------------------------------------
# 1. Install the main script to ~/.local/bin
# ----------------------------------------------------------
echo -e "${YELLOW}➜ Installing CodeGluer script...${NC}"
mkdir -p "$INSTALL_DIR"
cp "$SCRIPT_DIR/codegluer.py" "$GLUER_BIN"
chmod +x "$GLUER_BIN"
echo -e "  ${GREEN}✔ Installed to $GLUER_BIN${NC}"

# Make sure ~/.local/bin is on PATH (warn if not)
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo -e "  ${YELLOW}⚠  ~/.local/bin is not on your PATH."
    echo -e "     Add this line to your ~/.bashrc or ~/.zshrc:"
    echo -e "     export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
fi

# ----------------------------------------------------------
# 2. Nautilus integration (GNOME Files)
# ----------------------------------------------------------
NAUTILUS_SCRIPT_DIR="$HOME/.local/share/nautilus/scripts"

echo -e "${YELLOW}➜ Setting up Nautilus right-click integration...${NC}"
mkdir -p "$NAUTILUS_SCRIPT_DIR"

# Helper function to create a Nautilus script
create_nautilus_script() {
    local name="$1"
    local format="$2"
    local script_path="$NAUTILUS_SCRIPT_DIR/$name"

    # Unquoted heredoc – $format expands now, \$ variables stay for runtime
    cat > "$script_path" << NAUTILUS_EOF
#!/usr/bin/env bash
# Nautilus script – "Glue Code Files"

GLUER="\$HOME/.local/bin/codegluer"

if [ ! -x "\$GLUER" ]; then
    notify-send "CodeGluer" "Error: CodeGluer not found at \$GLUER" --icon=dialog-error
    exit 1
fi

# Collect selected files
FILES=()
while IFS= read -r file; do
    [ -n "\$file" ] && FILES+=("\$file")
done <<< "\$NAUTILUS_SCRIPT_SELECTED_FILE_PATHS"

if [ \${#FILES[@]} -eq 0 ]; then
    notify-send "CodeGluer" "No files selected." --icon=dialog-warning
    exit 1
fi

# Run the gluer with the specified format
OUTPUT=\$("\$GLUER" "\${FILES[@]}" --format $format 2>&1)
EXIT_CODE=\$?

if [ \$EXIT_CODE -eq 0 ]; then
    notify-send "CodeGluer" "\$OUTPUT" --icon=dialog-information
else
    notify-send "CodeGluer" "Error: \$OUTPUT" --icon=dialog-error
fi
NAUTILUS_EOF

    chmod +x "$script_path"
    echo -e "  ${GREEN}✔ Nautilus script: $name${NC}"
}

create_nautilus_script "Glue Code Files (Plain)" "plain"
create_nautilus_script "Glue Code Files (Markdown)" "markdown"

# ----------------------------------------------------------
# 3. Nemo integration (Cinnamon Files) – optional
# ----------------------------------------------------------
if command -v nemo &>/dev/null; then
    echo -e "${YELLOW}➜ Nemo detected – setting up Nemo actions...${NC}"
    NEMO_ACTION_DIR="$HOME/.local/share/nemo/actions"
    mkdir -p "$NEMO_ACTION_DIR"

    # Helper to create a Nemo action and its wrapper
    create_nemo_action() {
        local label="$1"
        local format="$2"
        local action_file="$NEMO_ACTION_DIR/codegluer-${format}.nemo_action"
        local wrapper_file="$NEMO_ACTION_DIR/codegluer-nemo-${format}.sh"

        # Unquoted heredoc – clean and no sed needed
        cat > "$wrapper_file" << NEMO_WRAPPER_EOF
#!/usr/bin/env bash
GLUER="\$HOME/.local/bin/codegluer"

if [ ! -x "\$GLUER" ]; then
    notify-send "CodeGluer" "Error: CodeGluer not found at \$GLUER" --icon=dialog-error
    exit 1
fi

OUTPUT=\$("\$GLUER" "\$@" --format $format 2>&1)
EXIT_CODE=\$?

if [ \$EXIT_CODE -eq 0 ]; then
    notify-send "CodeGluer" "\$OUTPUT" --icon=dialog-information
else
    notify-send "CodeGluer" "Error: \$OUTPUT" --icon=dialog-error
fi
NEMO_WRAPPER_EOF

        chmod +x "$wrapper_file"

        cat > "$action_file" << EOF
[Nemo Action]
Name=$label
Comment=Glue selected files into a single file ($format)
Exec=$wrapper_file %F
Icon-Name=text-x-generic
Selection=notnone
Extensions=any;
EOF

        echo -e "  ${GREEN}✔ Nemo action: $label${NC}"
    }

    create_nemo_action "Glue Code Files (Plain)" "plain"
    create_nemo_action "Glue Code Files (Markdown)" "markdown"
else
    echo -e "  ${YELLOW}ℹ  Nemo not detected – skipping Nemo integration.${NC}"
fi

# ----------------------------------------------------------
# Done
# ----------------------------------------------------------
echo ""
echo -e "${GREEN}══════════════════════════════════════════${NC}"
echo -e "${GREEN}  Installation complete! 🎉${NC}"
echo -e "${GREEN}══════════════════════════════════════════${NC}"
echo ""
echo "  How to use:"
echo "  1. Open your file manager (Nautilus / Nemo)"
echo "  2. Select the code files you want to glue"
echo "  3. Right-click → Scripts → Glue Code Files (Plain) or (Markdown)"
echo "  4. A 'glued_code.txt' or 'glued_code.md' will appear in the same directory"
echo ""
echo "  You can also use it from the terminal:"
echo "    codegluer file1.py file2.js --format markdown -o output.md"
echo ""
