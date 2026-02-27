#!/bin/bash
# Script to build a patchpal wheel file with alternative security defaults
# This script modifies config.py to set:
# - ENABLE_WEB=false (prevent information leakage via web requests)
# - RESTRICT_TO_REPO=true (prevent reading files with PII outside repo)
# Then builds the wheel, copies it to a target directory, and restores the original

set -e  # Exit on error

# Help message
if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    echo "Usage: $(basename "$0") [output_dir]"
    echo ""
    echo "Build a PatchPal wheel with alternative security defaults and copy it to output_dir."
    echo ""
    echo "Arguments:"
    echo "  output_dir  Optional. Destination directory for the built wheel."
    echo "              Default: <project_root>/dist/alt-default-wheel"
    exit 0
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Building PatchPal Wheel with Alternative Defaults ===${NC}"
echo -e "${YELLOW}This wheel will have enhanced security defaults:${NC}"
echo -e "${YELLOW}  - ENABLE_WEB=false (no web access)${NC}"
echo -e "${YELLOW}  - RESTRICT_TO_REPO=true (no file access outside repo)${NC}\n"

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
DEFAULT_WHEEL_OUTPUT_DIR="$PROJECT_ROOT/dist/alt-default-wheel"
WHEEL_OUTPUT_DIR="${1:-$DEFAULT_WHEEL_OUTPUT_DIR}"

echo "Project root: $PROJECT_ROOT"
echo "Wheel output dir: $WHEEL_OUTPUT_DIR"
echo ""

# Navigate to project root
cd "$PROJECT_ROOT"

# Backup the original config.py
CONFIG_FILE="patchpal/config.py"
BACKUP_FILE="patchpal/config.py.backup"

echo -e "${YELLOW}Step 1: Backing up config.py${NC}"
cp "$CONFIG_FILE" "$BACKUP_FILE"

# Function to restore config.py on exit (success or failure)
cleanup() {
    if [ -f "$BACKUP_FILE" ]; then
        echo -e "\n${YELLOW}Restoring original config.py${NC}"
        mv "$BACKUP_FILE" "$CONFIG_FILE"
        echo -e "${GREEN}✓ Original config.py restored${NC}"
    fi
}
trap cleanup EXIT

# Modify config.py to set ENABLE_WEB default to false
echo -e "${YELLOW}Step 2: Modifying config.py security defaults${NC}"
sed -i 's/return _get_env_bool("PATCHPAL_ENABLE_WEB", "true")/return _get_env_bool("PATCHPAL_ENABLE_WEB", "false")/' "$CONFIG_FILE"
sed -i 's/return _get_env_bool("PATCHPAL_RESTRICT_TO_REPO", "false")/return _get_env_bool("PATCHPAL_RESTRICT_TO_REPO", "true")/' "$CONFIG_FILE"

# Verify the changes
if grep -q 'PATCHPAL_ENABLE_WEB", "false"' "$CONFIG_FILE" && grep -q 'PATCHPAL_RESTRICT_TO_REPO", "true"' "$CONFIG_FILE"; then
    echo -e "${GREEN}✓ config.py modified successfully${NC}"
else
    echo -e "${RED}✗ Failed to modify config.py${NC}"
    exit 1
fi

# Clean previous builds
echo -e "\n${YELLOW}Step 3: Cleaning previous builds${NC}"
rm -rf dist/ build/ *.egg-info patchpal.egg-info
echo -e "${GREEN}✓ Clean complete${NC}"

# Build the wheel
echo -e "\n${YELLOW}Step 4: Building wheel${NC}"
python -m pip install --upgrade build >/dev/null 2>&1 || true
python -m build --wheel

# Check if wheel was created
WHEEL_FILE=$(ls dist/*.whl 2>/dev/null | head -n 1)
if [ -z "$WHEEL_FILE" ]; then
    echo -e "${RED}✗ Failed to build wheel${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Wheel built: $(basename "$WHEEL_FILE")${NC}"

# Copy wheel to output directory
echo -e "\n${YELLOW}Step 5: Copying wheel to output directory${NC}"
mkdir -p "$WHEEL_OUTPUT_DIR"
cp "$WHEEL_FILE" "$WHEEL_OUTPUT_DIR/"
echo -e "${GREEN}✓ Wheel copied to: $WHEEL_OUTPUT_DIR/$(basename "$WHEEL_FILE")${NC}"

# Summary
echo -e "\n${GREEN}=== Build Complete ===${NC}"
echo -e "Wheel file: ${GREEN}$(basename "$WHEEL_FILE")${NC}"
echo -e "Location: ${GREEN}$WHEEL_OUTPUT_DIR/${NC}"
echo -e "\n${YELLOW}Security defaults for this wheel:${NC}"
echo -e "${YELLOW}  - ENABLE_WEB=false (can override with PATCHPAL_ENABLE_WEB=true)${NC}"
echo -e "${YELLOW}  - RESTRICT_TO_REPO=true (can override with PATCHPAL_RESTRICT_TO_REPO=false)${NC}"
echo -e "\n${YELLOW}The default wheel has ENABLE_WEB=true and RESTRICT_TO_REPO=false by default${NC}"
