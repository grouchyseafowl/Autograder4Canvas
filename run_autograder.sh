#!/bin/bash
#===============================================================================
#                        CANVAS AUTOGRADER LAUNCHER
#                           macOS / Linux Version
#===============================================================================

# Change to the directory containing this script
cd "$(dirname "$0")"

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}       Canvas Autograder Launcher${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check for Python 3
check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
        echo -e "${GREEN}✓${NC} Python 3 found: $(python3 --version)"
        return 0
    elif command -v python &> /dev/null; then
        VERSION=$(python --version 2>&1)
        if [[ $VERSION == *"Python 3"* ]]; then
            PYTHON_CMD="python"
            echo -e "${GREEN}✓${NC} Python found: $VERSION"
            return 0
        fi
    fi
    
    echo -e "${RED}✗${NC} Python 3 not found!"
    echo ""
    echo "Please install Python 3.7 or higher:"
    echo ""
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "  Option 1: Download from https://www.python.org/downloads/"
        echo "  Option 2: Install via Homebrew: brew install python3"
    else
        echo "  Option 1: Download from https://www.python.org/downloads/"
        echo "  Option 2: Install via package manager:"
        echo "            Ubuntu/Debian: sudo apt install python3 python3-pip python3-venv"
        echo "            Fedora: sudo dnf install python3 python3-pip"
        echo "            Arch: sudo pacman -S python python-pip"
    fi
    echo ""
    read -p "Press Enter to exit..."
    exit 1
}

# Check for the main launcher script in src/
find_launcher() {
    LAUNCHER="src/run_autograder.py"
    
    if [ -f "$LAUNCHER" ]; then
        echo -e "${GREEN}✓${NC} Found launcher: $LAUNCHER"
        return 0
    fi
    
    # Fallback: look for any run_autograder*.py in src/
    LAUNCHER=$(ls src/run_autograder*.py 2>/dev/null | head -n 1)
    
    if [ -n "$LAUNCHER" ]; then
        echo -e "${GREEN}✓${NC} Found launcher: $LAUNCHER"
        return 0
    fi
    
    echo -e "${RED}✗${NC} Launcher script not found!"
    echo ""
    echo "Expected: src/run_autograder.py"
    echo "Current directory: $(pwd)"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
}

# Main execution
check_python
find_launcher

echo ""
echo -e "${BLUE}Starting Canvas Autograder...${NC}"
echo ""

# Run the launcher
$PYTHON_CMD "$LAUNCHER"

# Keep terminal open if there was an error
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo -e "${YELLOW}Program exited with code: $EXIT_CODE${NC}"
    read -p "Press Enter to close..."
fi
