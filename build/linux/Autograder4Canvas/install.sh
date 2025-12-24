#!/bin/bash
#===============================================================================
#                    CANVAS AUTOGRADER INSTALLER - Linux
#===============================================================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Autograder4Canvas Installer${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Set install location
INSTALL_DIR="$HOME/.local/share/Autograder4Canvas"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"

echo "This will install Autograder4Canvas to:"
echo "  $INSTALL_DIR"
echo ""
echo "And create a launcher in:"
echo "  $BIN_DIR/autograder4canvas"
echo "  $DESKTOP_DIR/autograder4canvas.desktop"
echo ""
read -p "Continue? (y/N): " CONFIRM

if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "Installation cancelled."
    exit 0
fi

echo ""
echo "Installing..."

# Get the directory where this installer is located
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Create install directories
mkdir -p "$INSTALL_DIR/Programs"
mkdir -p "$BIN_DIR"
mkdir -p "$DESKTOP_DIR"

# Copy files
echo "  Copying program files..."
cp "$SCRIPT_DIR/src/run_autograder.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/src/requirements.txt" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/src/Programs/"*.py "$INSTALL_DIR/Programs/"
[ -f "$SCRIPT_DIR/icon.png" ] && cp "$SCRIPT_DIR/icon.png" "$INSTALL_DIR/"

# Determine icon path for .desktop file
if [ -f "$INSTALL_DIR/icon.png" ]; then
    ICON_PATH="$INSTALL_DIR/icon.png"
else
    ICON_PATH="utilities-terminal"
fi

# Create the launcher script
echo "  Creating command-line launcher..."
cat > "$BIN_DIR/autograder4canvas" << LAUNCHER
#!/bin/bash
cd "$INSTALL_DIR"
python3 run_autograder.py "\$@"
LAUNCHER
chmod +x "$BIN_DIR/autograder4canvas"

# Create .desktop file for GUI launchers
echo "  Creating desktop entry..."
cat > "$DESKTOP_DIR/autograder4canvas.desktop" << DESKTOP
[Desktop Entry]
Version=1.0
Type=Application
Name=Autograder4Canvas
Comment=Automated grading tools for Canvas LMS
Exec=bash -c 'cd "$INSTALL_DIR" && python3 run_autograder.py; echo ""; read -p "Press Enter to close..."'
Icon=$ICON_PATH
Terminal=true
Categories=Education;Utility;
DESKTOP

chmod +x "$DESKTOP_DIR/autograder4canvas.desktop"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Installation Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Program installed to: $INSTALL_DIR"
echo ""
echo "You can now run Autograder4Canvas by:"
echo "  1. Typing 'autograder4canvas' in terminal"
echo "  2. Finding 'Autograder4Canvas' in your application menu"
echo ""
echo "Note: You may need to log out and back in for the"
echo "      application menu entry to appear."
echo ""
echo "To uninstall, run:"
echo "  rm -rf $INSTALL_DIR"
echo "  rm $BIN_DIR/autograder4canvas"
echo "  rm $DESKTOP_DIR/autograder4canvas.desktop"
echo ""
