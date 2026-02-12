#!/bin/bash
#===============================================================================
#                        CANVAS AUTOGRADER LAUNCHER
#                           macOS / Linux Version
#                               Version 1.3+
#===============================================================================

# Get the directory containing this script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to open URL in browser
open_url() {
    local url="$1"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        open "$url" 2>/dev/null
    elif command -v xdg-open &> /dev/null; then
        xdg-open "$url" 2>/dev/null
    elif command -v gnome-open &> /dev/null; then
        gnome-open "$url" 2>/dev/null
    else
        return 1
    fi
    return 0
}

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Canvas Autograder${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check for Python 3
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    echo -e "${GREEN}✓${NC} Python 3 found: $(python3 --version)"
elif command -v python &> /dev/null; then
    VERSION=$(python --version 2>&1)
    if [[ $VERSION == *"Python 3"* ]]; then
        PYTHON_CMD="python"
        echo -e "${GREEN}✓${NC} Python found: $VERSION"
    fi
fi

if [ -z "$PYTHON_CMD" ]; then
    echo -e "${RED}✗${NC} Python 3 not found!"
    echo ""
    echo "Autograder4Canvas requires Python 3.7 or higher."
    echo ""
    echo "Please install Python:"
    echo ""
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "  Download from: https://www.python.org/downloads/"
        echo "  Or install via Homebrew: brew install python3"
    else
        echo "  Download from: https://www.python.org/downloads/"
        echo ""
        echo "  Or install via package manager:"
        echo "    Ubuntu/Debian: sudo apt install python3 python3-pip python3-venv"
        echo "    Fedora: sudo dnf install python3 python3-pip"
        echo "    Arch: sudo pacman -S python python-pip"
    fi
    echo ""
    echo "Options:"
    echo "  [1] Open Python download page in browser"
    echo "  [2] Exit and install manually"
    echo ""
    
    read -p "Choose option (1 or 2, default=2): " choice
    choice=${choice:-2}
    
    if [ "$choice" = "1" ]; then
        echo ""
        echo "🌐 Opening Python download page in your browser..."
        if open_url "https://www.python.org/downloads/"; then
            echo -e "${GREEN}✓${NC} Browser opened successfully"
        else
            echo -e "${YELLOW}⚠${NC}  Could not open browser automatically"
            echo "   Please manually visit: https://www.python.org/downloads/"
        fi
        echo ""
        echo "After installing Python:"
        if [[ "$OSTYPE" == "darwin"* ]]; then
            echo "  1. Complete the installation"
            echo "  2. Restart this program"
        else
            echo "  1. Complete the installation"
            echo "  2. Restart your terminal"
            echo "  3. Run this program again"
        fi
        echo ""
        read -p "Press Enter to exit..."
    else
        echo ""
        echo "Please install Python 3.7+ and run this program again."
        echo ""
        read -p "Press Enter to exit..."
    fi
    exit 1
fi

# Find the launcher script in src/ directory (version-agnostic)
LAUNCHER=""

# First, look for any run_autograder*.py in src/
if [ -d "$SCRIPT_DIR/src" ]; then
    # Find the newest version by sorting (handles v1-3, v1-4, v2-1, etc.)
    LAUNCHER=$(ls -1 "$SCRIPT_DIR/src"/run_autograder*.py 2>/dev/null | sort -V | tail -n 1)
fi

if [ -z "$LAUNCHER" ] || [ ! -f "$LAUNCHER" ]; then
    echo -e "${RED}✗${NC} Launcher script not found!"
    echo ""
    echo "Expected location: src/run_autograder*.py"
    echo "Current directory: $SCRIPT_DIR"
    echo ""
    echo "Make sure the src/ directory exists and contains the main Python script."
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

echo -e "${GREEN}✓${NC} Found launcher: $(basename "$LAUNCHER")"
echo ""
echo -e "${BLUE}Starting Canvas Autograder...${NC}"
echo -e "${BLUE}The program will guide you through any remaining setup.${NC}"
echo ""

# Run the launcher from the script directory
cd "$SCRIPT_DIR"
$PYTHON_CMD "$LAUNCHER"

# Keep terminal open if there was an error
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo -e "${YELLOW}Program exited with code: $EXIT_CODE${NC}"
    echo ""
    read -p "Press Enter to close..."
fi
