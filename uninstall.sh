#!/usr/bin/env bash
# ============================================================
#  CodeGluer – Uninstaller
#  Removes the gluer script and all file manager integrations.
#  Also cleans up legacy "Code Combiner" files for upgraders.
# ============================================================

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════╗"
echo "║         CodeGluer – Uninstaller          ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

remove_if_exists() {
    if [ -e "$1" ]; then
        rm -f "$1"
        echo -e "  ${GREEN}✔ Removed: $1${NC}"
    else
        echo -e "  ${YELLOW}ℹ  Not found (already removed): $1${NC}"
    fi
}

echo -e "${YELLOW}➜ Removing installed files...${NC}"

# --- New CodeGluer files ---
remove_if_exists "$HOME/.local/bin/codegluer"
remove_if_exists "$HOME/.local/share/nautilus/scripts/Glue Code Files (Plain)"
remove_if_exists "$HOME/.local/share/nautilus/scripts/Glue Code Files (Markdown)"
remove_if_exists "$HOME/.local/share/nemo/actions/codegluer-plain.nemo_action"
remove_if_exists "$HOME/.local/share/nemo/actions/codegluer-markdown.nemo_action"
remove_if_exists "$HOME/.local/share/nemo/actions/codegluer-nemo-plain.sh"
remove_if_exists "$HOME/.local/share/nemo/actions/codegluer-nemo-markdown.sh"

# --- Legacy Code Combiner files (for upgraders) ---
remove_if_exists "$HOME/.local/bin/code-combiner"
remove_if_exists "$HOME/.local/share/nautilus/scripts/Combine Code Files"
remove_if_exists "$HOME/.local/share/nautilus/scripts/Glue Code Files"   # old single entry
remove_if_exists "$HOME/.local/share/nemo/actions/code-combiner.nemo_action"
remove_if_exists "$HOME/.local/share/nemo/actions/code-combiner-nemo.sh"
remove_if_exists "$HOME/.local/share/nemo/actions/codegluer.nemo_action" # old single entry
remove_if_exists "$HOME/.local/share/nemo/actions/codegluer-nemo.sh"     # old single entry

echo ""
echo -e "${GREEN}══════════════════════════════════════════${NC}"
echo -e "${GREEN}  Uninstall complete! 👋${NC}"
echo -e "${GREEN}══════════════════════════════════════════${NC}"
echo ""
