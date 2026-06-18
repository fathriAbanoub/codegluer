#!/usr/bin/env bash
# ============================================================
#  CodeGluer – Installer
#  Sets up the Python package and right-click context menus.
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
echo "║         CodeGluer – Installer            ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

# ----------------------------------------------------------
# 1. Install the Python package
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

# Ensure ~/.local/bin is on PATH (warn if not)
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo -e "  ${YELLOW}⚠ ~/.local/bin is not on your PATH."
    echo -e "     Add this line to your ~/.bashrc or ~/.zshrc:"
    echo -e "     export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
fi

# ----------------------------------------------------------
# 2. Nautilus integration (GNOME)
# ----------------------------------------------------------
NAUTILUS_SCRIPT_DIR="$HOME/.local/share/nautilus/scripts"
echo -e "${YELLOW}➜ Setting up Nautilus right-click integration...${NC}"
mkdir -p "$NAUTILUS_SCRIPT_DIR"

create_nautilus_script() {
    local name="$1"
    local format="$2"
    local script_path="$NAUTILUS_SCRIPT_DIR/$name"

    cat > "$script_path" << 'NAUTILUS_EOF'
#!/usr/bin/env bash
# Nautilus script – "Glue Code Files"

# 🧠 Robust PATH resolution (GUI shells don't source .bashrc)
GLUER="$HOME/.local/bin/codegluer"
if [ ! -x "$GLUER" ]; then
    GLUER="codegluer"
    if ! command -v "$GLUER" &>/dev/null; then
        notify-send "CodeGluer" "Error: CodeGluer not found in PATH" --icon=dialog-error
        exit 1
    fi
fi

# Collect selected files
FILES=()
while IFS= read -r file; do
    [ -n "$file" ] && FILES+=("$file")
done <<< "$NAUTILUS_SCRIPT_SELECTED_FILE_PATHS"

if [ ${#FILES[@]} -eq 0 ]; then
    notify-send "CodeGluer" "No files selected." --icon=dialog-warning
    exit 1
fi

# Smart GUI: automatically add -r if a folder is selected
RECURSIVE_FLAG=""
for file in "${FILES[@]}"; do
    if [ -d "$file" ]; then
        RECURSIVE_FLAG="-r"
        break
    fi
done

OUTPUT=$("$GLUER" "${FILES[@]}" $RECURSIVE_FLAG --format FORMAT_PLACEHOLDER 2>&1)
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    notify-send "CodeGluer" "$OUTPUT" --icon=dialog-information
else
    notify-send "CodeGluer" "Error: $OUTPUT" --icon=dialog-error
fi
NAUTILUS_EOF

    # Safe replacement that works on Linux & macOS (with error handling)
    tmp_file=$(mktemp)
    if sed "s/FORMAT_PLACEHOLDER/$format/g" "$script_path" > "$tmp_file"; then
        mv "$tmp_file" "$script_path"
        chmod +x "$script_path"
        echo -e "  ${GREEN}✔ Nautilus script: $name${NC}"
    else
        rm -f "$tmp_file"
        echo -e "  ${RED}✘ Failed to process $script_path${NC}" >&2
        exit 1
    fi
}

create_nautilus_script "Glue Code Files (Plain)" "plain"
create_nautilus_script "Glue Code Files (Markdown)" "markdown"

# ----------------------------------------------------------
# 3. Nemo integration (Cinnamon)
# ----------------------------------------------------------
if command -v nemo &>/dev/null; then
    echo -e "${YELLOW}➜ Nemo detected – setting up Nemo actions...${NC}"
    NEMO_ACTION_DIR="$HOME/.local/share/nemo/actions"
    mkdir -p "$NEMO_ACTION_DIR"

    create_nemo_action() {
        local label="$1"
        local format="$2"
        local action_file="$NEMO_ACTION_DIR/codegluer-${format}.nemo_action"
        local wrapper_file="$NEMO_ACTION_DIR/codegluer-nemo-${format}.sh"

        cat > "$wrapper_file" << 'NEMO_WRAPPER_EOF'
#!/usr/bin/env bash
# 🧠 Robust PATH resolution (GUI shells don't source .bashrc)
GLUER="$HOME/.local/bin/codegluer"
if [ ! -x "$GLUER" ]; then
    GLUER="codegluer"
    if ! command -v "$GLUER" &>/dev/null; then
        notify-send "CodeGluer" "Error: CodeGluer not found in PATH" --icon=dialog-error
        exit 1
    fi
fi

# Smart GUI: automatically add -r if a folder is selected
RECURSIVE_FLAG=""
for arg in "$@"; do
    if [ -d "$arg" ]; then
        RECURSIVE_FLAG="-r"
        break
    fi
done

OUTPUT=$("$GLUER" "$@" $RECURSIVE_FLAG --format FORMAT_PLACEHOLDER 2>&1)
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    notify-send "CodeGluer" "$OUTPUT" --icon=dialog-information
else
    notify-send "CodeGluer" "Error: $OUTPUT" --icon=dialog-error
fi
NEMO_WRAPPER_EOF

        # Safe replacement with error handling
        tmp_file=$(mktemp)
        if sed "s/FORMAT_PLACEHOLDER/$format/g" "$wrapper_file" > "$tmp_file"; then
            mv "$tmp_file" "$wrapper_file"
            chmod +x "$wrapper_file"
        else
            rm -f "$tmp_file"
            echo -e "  ${RED}✘ Failed to process $wrapper_file${NC}" >&2
            exit 1
        fi

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
    echo -e "  ${YELLOW}ℹ  Nemo not detected – skipping.${NC}"
fi

echo ""
echo -e "${GREEN}══════════════════════════════════════════${NC}"
echo -e "${GREEN}  Installation complete! 🎉${NC}"
echo -e "${GREEN}══════════════════════════════════════════${NC}"
echo ""
echo "  How to use:"
echo "  1. Open your file manager (Nautilus / Nemo)"
echo "  2. Select files or folders"
echo "  3. Right-click → Scripts → Glue Code Files (Plain/Markdown)"
echo "  4. A 'glued_code.txt' or 'glued_code.md' will appear"
echo ""
echo "  Terminal usage:"
echo "    codegluer file1.py file2.js --format markdown -o output.md"
echo ""
