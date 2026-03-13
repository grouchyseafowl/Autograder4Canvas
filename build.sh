#!/bin/bash
#===============================================================================
#                        AUTOGRADER4CANVAS BUILD SCRIPT
#              Creates platform-specific distribution packages
#===============================================================================
#
# This script creates distribution packages from your source files:
#   1. Autograder4Canvas-Mac.dmg      - DMG with .app and Applications shortcut
#   2. Autograder4Canvas-Windows.zip  - Folder with installer batch script
#   3. Autograder4Canvas-Linux.tar.gz - Folder with installer shell script
#
# USAGE:
#   ./build.sh              Build both packages
#   ./build.sh mac          Build Mac package only
#   ./build.sh win          Build Windows/Linux package only
#   ./build.sh clean        Remove build artifacts
#
# REQUIREMENTS:
#   - Run this on macOS (needed to create the .app bundle)
#   - The Autograder4Canvas.app must already exist in this folder
#   - Place icon.jpg in the src/ directory for custom app icon
#
#===============================================================================

set -e  # Exit on error

# Configuration
VERSION="2.0"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
DIST_DIR="$SCRIPT_DIR/distro"

# Source locations
SRC_DIR="$SCRIPT_DIR/src"
APP_SOURCE="$SCRIPT_DIR/Autograder4Canvas.app"
ICON_SOURCE="$SRC_DIR/icon.jpg"
MAIN_SCRIPT=$(ls "$SRC_DIR"/run_autograder*.py 2>/dev/null | head -n 1)
MAIN_SCRIPT_NAME=$(basename "$MAIN_SCRIPT")

# v2 Academic Dishonesty Check directories
V2_CONFIG_DIR="$SRC_DIR/config"
V2_MODULES_DIR="$SRC_DIR/modules"
V2_DOCS_DIR="$SRC_DIR/docs"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Autograder4Canvas Build Script${NC}"
echo -e "${BLUE}   Version: $VERSION${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

#-------------------------------------------------------------------------------
# Helper Functions
#-------------------------------------------------------------------------------

clean_build() {
    echo -e "${YELLOW}Cleaning build artifacts...${NC}"
    rm -rf "$BUILD_DIR" "$DIST_DIR"
    echo -e "${GREEN}✓ Clean complete${NC}"
}

create_icns() {
    local DEST_DIR="$1"
    local ICNS_FILE="$DEST_DIR/AppIcon.icns"
    
    if [ ! -f "$ICON_SOURCE" ]; then
        echo -e "${YELLOW}  ⚠ Icon source not found: $ICON_SOURCE${NC}"
        echo "    Skipping icon creation."
        return 0  # Return success so build continues
    fi
    
    echo "  Creating app icon from $ICON_SOURCE..."
    
    # Check if we're on macOS with sips/iconutil available
    if command -v sips &> /dev/null && command -v iconutil &> /dev/null; then
        # Create iconset directory
        local ICONSET_DIR="$BUILD_DIR/AppIcon.iconset"
        rm -rf "$ICONSET_DIR"  # Clean up any previous failed attempt
        mkdir -p "$ICONSET_DIR"
        
        # First, convert the source image to PNG (in case JPG causes issues)
        local TEMP_PNG="$BUILD_DIR/temp_icon.png"
        if ! sips -s format png "$ICON_SOURCE" --out "$TEMP_PNG" > /dev/null 2>&1; then
            echo -e "${YELLOW}  ⚠ Could not convert icon to PNG - skipping icon${NC}"
            rm -rf "$ICONSET_DIR" "$TEMP_PNG"
            return 0
        fi
        
        # Generate all required icon sizes from the PNG
        sips -z 16 16     "$TEMP_PNG" --out "$ICONSET_DIR/icon_16x16.png" > /dev/null 2>&1
        sips -z 32 32     "$TEMP_PNG" --out "$ICONSET_DIR/icon_16x16@2x.png" > /dev/null 2>&1
        sips -z 32 32     "$TEMP_PNG" --out "$ICONSET_DIR/icon_32x32.png" > /dev/null 2>&1
        sips -z 64 64     "$TEMP_PNG" --out "$ICONSET_DIR/icon_32x32@2x.png" > /dev/null 2>&1
        sips -z 128 128   "$TEMP_PNG" --out "$ICONSET_DIR/icon_128x128.png" > /dev/null 2>&1
        sips -z 256 256   "$TEMP_PNG" --out "$ICONSET_DIR/icon_128x128@2x.png" > /dev/null 2>&1
        sips -z 256 256   "$TEMP_PNG" --out "$ICONSET_DIR/icon_256x256.png" > /dev/null 2>&1
        sips -z 512 512   "$TEMP_PNG" --out "$ICONSET_DIR/icon_256x256@2x.png" > /dev/null 2>&1
        sips -z 512 512   "$TEMP_PNG" --out "$ICONSET_DIR/icon_512x512.png" > /dev/null 2>&1
        sips -z 1024 1024 "$TEMP_PNG" --out "$ICONSET_DIR/icon_512x512@2x.png" > /dev/null 2>&1
        
        # Clean up temp PNG
        rm -f "$TEMP_PNG"
        
        # Convert iconset to icns
        if iconutil -c icns "$ICONSET_DIR" -o "$ICNS_FILE" 2>&1; then
            rm -rf "$ICONSET_DIR"
            echo -e "${GREEN}  ✓ Icon created: AppIcon.icns${NC}"
            return 0
        else
            echo -e "${YELLOW}  ⚠ iconutil failed - app will use default icon${NC}"
            rm -rf "$ICONSET_DIR"
            return 0  # Return success so build continues
        fi
    else
        # Fallback: use ImageMagick if available
        if command -v convert &> /dev/null; then
            echo "  Using ImageMagick fallback (limited icon support)..."
            convert "$ICON_SOURCE" -resize 512x512 "$DEST_DIR/AppIcon.png"
            echo -e "${YELLOW}  ⚠ Created PNG icon (run on macOS for proper .icns)${NC}"
            return 0
        else
            echo -e "${YELLOW}  ⚠ No icon tools available - app will use default icon${NC}"
            return 0  # Return success so build continues
        fi
    fi
}

create_ico() {
    local DEST_DIR="$1"
    local ICO_FILE="$DEST_DIR/icon.ico"
    
    if [ ! -f "$ICON_SOURCE" ]; then
        echo -e "${YELLOW}  ⚠ Icon source not found: $ICON_SOURCE${NC}"
        echo "    Skipping icon creation."
        return 0  # Return success so build continues
    fi
    
    echo "  Creating Windows icon from $ICON_SOURCE..."
    
    # ImageMagick is the best cross-platform option for .ico creation
    if command -v convert &> /dev/null; then
        # Create multi-resolution .ico file (16, 32, 48, 64, 128, 256)
        if convert "$ICON_SOURCE" \
            \( -clone 0 -resize 16x16 \) \
            \( -clone 0 -resize 32x32 \) \
            \( -clone 0 -resize 48x48 \) \
            \( -clone 0 -resize 64x64 \) \
            \( -clone 0 -resize 128x128 \) \
            \( -clone 0 -resize 256x256 \) \
            -delete 0 "$ICO_FILE" 2>/dev/null; then
            echo -e "${GREEN}  ✓ Windows icon created: icon.ico${NC}"
        else
            echo -e "${YELLOW}  ⚠ Could not create Windows icon - skipping${NC}"
        fi
        return 0
    else
        echo -e "${YELLOW}  ⚠ ImageMagick not found - skipping Windows icon${NC}"
        return 0  # Return success so build continues
    fi
}

create_png_icon() {
    local DEST_DIR="$1"
    local PNG_FILE="$DEST_DIR/icon.png"
    
    if [ ! -f "$ICON_SOURCE" ]; then
        echo -e "${YELLOW}  ⚠ Icon source not found: $ICON_SOURCE${NC}"
        echo "    Skipping icon creation."
        return 0  # Return success so build continues
    fi
    
    echo "  Creating Linux icon from $ICON_SOURCE..."
    
    # Check for sips (macOS) or ImageMagick
    if command -v sips &> /dev/null; then
        if sips -z 256 256 "$ICON_SOURCE" --out "$PNG_FILE" > /dev/null 2>&1; then
            echo -e "${GREEN}  ✓ Linux icon created: icon.png${NC}"
        else
            echo -e "${YELLOW}  ⚠ Could not create Linux icon - skipping${NC}"
        fi
        return 0
    elif command -v convert &> /dev/null; then
        if convert "$ICON_SOURCE" -resize 256x256 "$PNG_FILE" 2>/dev/null; then
            echo -e "${GREEN}  ✓ Linux icon created: icon.png${NC}"
        else
            echo -e "${YELLOW}  ⚠ Could not create Linux icon - skipping${NC}"
        fi
        return 0
    else
        # Fallback: just copy the original if it's already a reasonable size
        cp "$ICON_SOURCE" "$PNG_FILE" 2>/dev/null || true
        echo -e "${YELLOW}  ⚠ Copied original image as icon (no resize tools available)${NC}"
        return 0
    fi
}

#-------------------------------------------------------------------------------
# Copy v2 Academic Dishonesty Check files
#-------------------------------------------------------------------------------

copy_v2_files() {
    local DEST_DIR="$1"
    
    echo "  Copying Academic Dishonesty Check v2 files..."
    
    # Copy config directory (YAML marker files, profiles)
    if [ -d "$V2_CONFIG_DIR" ]; then
        echo "    Copying config/ (markers, profiles)..."
        cp -R "$V2_CONFIG_DIR" "$DEST_DIR/"
    else
        echo -e "${YELLOW}    ⚠ config/ directory not found - v2 will use built-in defaults${NC}"
    fi
    
    # Copy modules directory (Python modules)
    if [ -d "$V2_MODULES_DIR" ]; then
        echo "    Copying modules/ (Python modules)..."
        cp -R "$V2_MODULES_DIR" "$DEST_DIR/"
    else
        echo -e "${YELLOW}    ⚠ modules/ directory not found - v2 will use built-in analysis${NC}"
    fi
    
    # Copy docs directory
    if [ -d "$V2_DOCS_DIR" ]; then
        echo "    Copying docs/ (USER_GUIDE, INTEGRATION_GUIDE)..."
        cp -R "$V2_DOCS_DIR" "$DEST_DIR/"
    fi
    
    echo -e "${GREEN}  ✓ v2 files copied${NC}"
}

check_requirements() {
    # Check we're on macOS for full build
    if [[ "$OSTYPE" != "darwin"* ]] && [[ "$1" == "mac" || "$1" == "" ]]; then
        echo -e "${YELLOW}⚠ Not running on macOS${NC}"
        echo "  The Mac .app bundle will be created, but you should test it on a Mac."
        echo ""
    fi
    
    # Check source files exist
    if [ ! -d "$SRC_DIR" ]; then
        echo -e "${RED}✗ Source directory not found: $SRC_DIR${NC}"
        exit 1
    fi
    
    if [ -z "$MAIN_SCRIPT" ] || [ ! -f "$MAIN_SCRIPT" ]; then
        echo -e "${RED}✗ Main script not found: $SRC_DIR/run_autograder*.py${NC}"
        exit 1
    fi
    echo "  Using main script: $MAIN_SCRIPT_NAME"
    
    if [ ! -d "$SRC_DIR/Programs" ]; then
        echo -e "${RED}✗ Programs directory not found: $SRC_DIR/Programs${NC}"
        exit 1
    fi
    
    # Check for v2 files (optional but recommended)
    if [ -d "$V2_CONFIG_DIR" ]; then
        echo "  Found v2 config directory: $V2_CONFIG_DIR"
    else
        echo -e "${YELLOW}  ⚠ v2 config/ not found - builds will use built-in defaults${NC}"
    fi
    
    if [ -d "$V2_MODULES_DIR" ]; then
        echo "  Found v2 modules directory: $V2_MODULES_DIR"
    else
        echo -e "${YELLOW}  ⚠ v2 modules/ not found - builds will use built-in analysis${NC}"
    fi
    
    echo -e "${GREEN}✓ Requirements check passed${NC}"
}

#-------------------------------------------------------------------------------
# Build Local App (for your own use in the source folder)
#-------------------------------------------------------------------------------

build_local_app() {
    echo ""
    echo -e "${BLUE}Building/updating local Autograder4Canvas.app...${NC}"
    
    local APP_DEST="$SCRIPT_DIR/Autograder4Canvas.app"
    local CONTENTS="$APP_DEST/Contents"
    local MACOS="$CONTENTS/MacOS"
    local RESOURCES="$CONTENTS/Resources"
    
    # Remove old app if it exists
    if [ -d "$APP_DEST" ]; then
        echo "  Removing old .app..."
        rm -rf "$APP_DEST"
    fi
    
    # Create the .app bundle structure
    echo "  Creating .app bundle structure..."
    mkdir -p "$MACOS"
    mkdir -p "$RESOURCES/Programs"
    
    # Create app icon
    mkdir -p "$BUILD_DIR"
    create_icns "$RESOURCES"
    
    # Create Info.plist
    echo "  Creating Info.plist..."
    cat > "$CONTENTS/Info.plist" << PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>Autograder4Canvas</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>com.autograder4canvas</string>
    <key>CFBundleName</key>
    <string>Autograder4Canvas</string>
    <key>CFBundleDisplayName</key>
    <string>Autograder4Canvas</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>$VERSION</string>
    <key>CFBundleVersion</key>
    <string>${VERSION}.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSUIElement</key>
    <false/>
    <key>NSAppleScriptEnabled</key>
    <true/>
</dict>
</plist>
PLIST_EOF
    
    # Copy source files into Resources
    echo "  Copying source files into bundle..."
    cp "$MAIN_SCRIPT" "$RESOURCES/run_autograder.py"
    cp "$SRC_DIR/requirements.txt" "$RESOURCES/"
    # Copy utilities if it exists
    [ -f "$SRC_DIR/autograder_utils.py" ] && cp "$SRC_DIR/autograder_utils.py" "$RESOURCES/"
    # Copy bootstrap launcher
    [ -f "$SRC_DIR/bootstrap.py" ] && cp "$SRC_DIR/bootstrap.py" "$RESOURCES/"
    cp "$SRC_DIR/Programs/"*.py "$RESOURCES/Programs/"

    # Copy v2 files
    copy_v2_files "$RESOURCES"
    
    # Create the launcher executable
    echo "  Creating launcher executable..."
    cat > "$MACOS/Autograder4Canvas" << 'LAUNCHER_EOF'
#!/bin/bash

#===============================================================================
# Autograder4Canvas - macOS App Launcher
# This script runs from inside the .app bundle and finds resources there
#===============================================================================

# Get the Resources directory inside the .app bundle
SCRIPT_PATH="$0"
MACOS_DIR="$(dirname "$SCRIPT_PATH")"
CONTENTS_DIR="$(dirname "$MACOS_DIR")"
RESOURCES_DIR="$CONTENTS_DIR/Resources"

# Verify Resources directory exists
if [ ! -d "$RESOURCES_DIR" ]; then
    osascript -e 'display alert "Error" message "Resources folder not found in app bundle. The app may be corrupted." as critical'
    exit 1
fi

# Check for Python
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    VERSION=$(python --version 2>&1)
    if [[ $VERSION == *"Python 3"* ]]; then
        PYTHON_CMD="python"
    fi
fi

if [ -z "$PYTHON_CMD" ]; then
    osascript -e 'display alert "Python 3 Required" message "Autograder4Canvas requires Python 3.7 or higher.\n\nPlease install Python from python.org" as critical buttons {"Download Python", "Cancel"} default button "Download Python"'
    BUTTON=$?
    if [ $BUTTON -eq 0 ]; then
        open "https://www.python.org/downloads/"
    fi
    exit 1
fi

# Find the launcher script in Resources (version-agnostic)
# Look for any run_autograder*.py and get the newest version
LAUNCHER=$(ls -1 "$RESOURCES_DIR"/run_autograder*.py 2>/dev/null | sort -V | tail -n 1)

if [ -z "$LAUNCHER" ] || [ ! -f "$LAUNCHER" ]; then
    osascript -e 'display alert "Error" message "Could not find run_autograder*.py in app bundle. The app may be corrupted." as critical'
    exit 1
fi

# Open Terminal and run the script
osascript << EOF
tell application "Terminal"
    activate
    set newTab to do script "cd '$RESOURCES_DIR' && '$PYTHON_CMD' '$LAUNCHER'; echo ''; echo 'Press Enter to close...'; read"
    set custom title of front window to "Autograder4Canvas"
end tell
EOF
LAUNCHER_EOF

    chmod +x "$MACOS/Autograder4Canvas"
    
    echo -e "${GREEN}✓ Local app created: Autograder4Canvas.app${NC}"
    echo "  You can double-click it or drag it to /Applications"
}

#-------------------------------------------------------------------------------
# Build Mac Distribution
#-------------------------------------------------------------------------------

build_mac() {
    echo ""
    echo -e "${BLUE}Building Mac distribution...${NC}"
    
    local MAC_BUILD="$BUILD_DIR/mac"
    local APP_DEST="$MAC_BUILD/Autograder4Canvas.app"
    local CONTENTS="$APP_DEST/Contents"
    local MACOS="$CONTENTS/MacOS"
    local RESOURCES="$CONTENTS/Resources"
    
    # Create the .app bundle structure from scratch
    echo "  Creating .app bundle structure..."
    mkdir -p "$MACOS"
    mkdir -p "$RESOURCES/Programs"
    
    # Create app icon
    create_icns "$RESOURCES"
    
    # Create Info.plist
    echo "  Creating Info.plist..."
    cat > "$CONTENTS/Info.plist" << PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>Autograder4Canvas</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>com.autograder4canvas</string>
    <key>CFBundleName</key>
    <string>Autograder4Canvas</string>
    <key>CFBundleDisplayName</key>
    <string>Autograder4Canvas</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>$VERSION</string>
    <key>CFBundleVersion</key>
    <string>${VERSION}.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSUIElement</key>
    <false/>
    <key>NSAppleScriptEnabled</key>
    <true/>
</dict>
</plist>
PLIST_EOF
    
    # Copy source files into Resources
    echo "  Copying source files into bundle..."
    cp "$MAIN_SCRIPT" "$RESOURCES/run_autograder.py"
    cp "$SRC_DIR/requirements.txt" "$RESOURCES/"
    # Copy utilities if it exists
    [ -f "$SRC_DIR/autograder_utils.py" ] && cp "$SRC_DIR/autograder_utils.py" "$RESOURCES/"
    # Copy bootstrap launcher
    [ -f "$SRC_DIR/bootstrap.py" ] && cp "$SRC_DIR/bootstrap.py" "$RESOURCES/"
    cp "$SRC_DIR/Programs/"*.py "$RESOURCES/Programs/"

    # Copy v2 files
    copy_v2_files "$RESOURCES"
    
    # Create the launcher executable
    echo "  Creating launcher executable..."
    cat > "$MACOS/Autograder4Canvas" << 'LAUNCHER_EOF'
#!/bin/bash

#===============================================================================
# Autograder4Canvas - macOS App Launcher
# This script runs from inside the .app bundle and finds resources there
#===============================================================================

# Get the Resources directory inside the .app bundle
SCRIPT_PATH="$0"
MACOS_DIR="$(dirname "$SCRIPT_PATH")"
CONTENTS_DIR="$(dirname "$MACOS_DIR")"
RESOURCES_DIR="$CONTENTS_DIR/Resources"

# Verify Resources directory exists
if [ ! -d "$RESOURCES_DIR" ]; then
    osascript -e 'display alert "Error" message "Resources folder not found in app bundle. The app may be corrupted." as critical'
    exit 1
fi

# Check for Python
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    VERSION=$(python --version 2>&1)
    if [[ $VERSION == *"Python 3"* ]]; then
        PYTHON_CMD="python"
    fi
fi

if [ -z "$PYTHON_CMD" ]; then
    osascript -e 'display alert "Python 3 Required" message "Autograder4Canvas requires Python 3.7 or higher.\n\nPlease install Python from python.org" as critical buttons {"Download Python", "Cancel"} default button "Download Python"'
    BUTTON=$?
    if [ $BUTTON -eq 0 ]; then
        open "https://www.python.org/downloads/"
    fi
    exit 1
fi

# Find the launcher script in Resources (version-agnostic)
# Look for any run_autograder*.py and get the newest version
LAUNCHER=$(ls -1 "$RESOURCES_DIR"/run_autograder*.py 2>/dev/null | sort -V | tail -n 1)

if [ -z "$LAUNCHER" ] || [ ! -f "$LAUNCHER" ]; then
    osascript -e 'display alert "Error" message "Could not find run_autograder*.py in app bundle. The app may be corrupted." as critical'
    exit 1
fi

# Open Terminal and run the script
# We use osascript to open Terminal because the app itself is a background process
osascript << EOF
tell application "Terminal"
    activate
    set newTab to do script "cd '$RESOURCES_DIR' && '$PYTHON_CMD' '$LAUNCHER'; echo ''; echo 'Press Enter to close...'; read"
    set custom title of front window to "Autograder4Canvas"
end tell
EOF
LAUNCHER_EOF

    chmod +x "$MACOS/Autograder4Canvas"
    
    # Add README to the same folder as the .app
    echo "  Adding README..."
    cp "$SCRIPT_DIR/README.txt" "$MAC_BUILD/" 2>/dev/null || true
    
    # Create the DMG
    echo "  Creating DMG installer..."
    mkdir -p "$DIST_DIR"
    
    local DMG_NAME="Autograder4Canvas-Mac-v$VERSION.dmg"
    local DMG_PATH="$DIST_DIR/$DMG_NAME"
    local DMG_TEMP="$BUILD_DIR/dmg_temp"
    
    # Check if we can create a DMG (requires macOS)
    if command -v hdiutil &> /dev/null; then
        # Remove any existing DMG
        rm -f "$DMG_PATH"

        if command -v create-dmg &> /dev/null; then
            # Use create-dmg for a polished installer window
            local BG_IMG="$SRC_DIR/assets/dmg_background.png"
            local BG_FLAG=()
            [ -f "$BG_IMG" ] && BG_FLAG=(--background "$BG_IMG" --text-size 13)
            create-dmg \
                --volname "Autograder4Canvas" \
                --volicon "$APP_DEST/Contents/Resources/AppIcon.icns" \
                --window-pos 200 120 \
                --window-size 600 380 \
                --icon-size 100 \
                --icon "Autograder4Canvas.app" 150 175 \
                --app-drop-link 450 175 \
                --no-internet-enable \
                "${BG_FLAG[@]}" \
                "$DMG_PATH" \
                "$APP_DEST"
        else
            # Fallback: plain hdiutil
            local DMG_TEMP="$BUILD_DIR/dmg_temp"
            rm -rf "$DMG_TEMP"
            mkdir -p "$DMG_TEMP"
            cp -R "$APP_DEST" "$DMG_TEMP/"
            ln -s /Applications "$DMG_TEMP/Applications"
            hdiutil create -volname "Autograder4Canvas" \
                -srcfolder "$DMG_TEMP" \
                -ov -format UDZO \
                "$DMG_PATH"
            rm -rf "$DMG_TEMP"
        fi

        echo -e "${GREEN}✓ Mac build complete: distro/$DMG_NAME${NC}"
        echo "  Users can open the DMG and drag the app to Applications."
    else
        # Fallback to zip if not on macOS
        echo -e "${YELLOW}  ⚠ hdiutil not found (not on macOS) - falling back to zip${NC}"
        cd "$MAC_BUILD"
        zip -r "$DIST_DIR/Autograder4Canvas-Mac-v$VERSION.zip" . -x "*.DS_Store"
        echo -e "${GREEN}✓ Mac build complete: distro/Autograder4Canvas-Mac-v$VERSION.zip${NC}"
    fi
    
    echo "  The .app is fully self-contained and can be moved anywhere."
}

#-------------------------------------------------------------------------------
# Build Windows Distribution
#-------------------------------------------------------------------------------

build_windows() {
    echo ""
    echo -e "${BLUE}Building Windows distribution...${NC}"
    
    local WIN_BUILD="$BUILD_DIR/windows/Autograder4Canvas"
    
    # Create build directory structure
    mkdir -p "$WIN_BUILD"
    
    # Create the installer batch script
    echo "  Creating Windows installer..."
    cat > "$WIN_BUILD/INSTALL.bat" << 'INSTALL_EOF'
@echo off
setlocal enabledelayedexpansion

echo ========================================
echo    Autograder4Canvas Installer
echo ========================================
echo.

:: -------------------------------------------------------
:: Check for Python 3
:: -------------------------------------------------------
set "PYTHON_CMD="
where python >nul 2>&1
if %ERRORLEVEL% == 0 (
    for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
    if "!PY_VER:~0,1!"=="3" set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
    where python3 >nul 2>&1
    if %ERRORLEVEL% == 0 (
        set "PYTHON_CMD=python3"
        for /f "tokens=2 delims= " %%v in ('python3 --version 2^>^&1') do set "PY_VER=%%v"
    )
)

if not defined PYTHON_CMD (
    echo.
    echo  ================================================
    echo   Python is needed but isn't installed yet
    echo  ================================================
    echo.
    echo  Autograder4Canvas runs on Python - a free tool
    echo  used by millions of people. We can download and
    echo  install it for you automatically right now!
    echo.
    set /p AUTO_INSTALL="  Install Python automatically? (Y/N): "
    echo.
    if /i "!AUTO_INSTALL!"=="Y" (
        echo  Step 1 of 2: Downloading Python 3.12...
        echo  ^(This usually takes 1-2 minutes^)
        echo.

        :: Write the Python installer script next to INSTALL.bat
        set "PY_PS1=%~dp0install_python.ps1"
        >  "!PY_PS1!" echo $arch = if ([Environment]::Is64BitOperatingSystem) { 'amd64' } else { '' }
        >> "!PY_PS1!" echo $ver  = '3.12.8'
        >> "!PY_PS1!" echo $file = "python-$ver" + $(if ($arch) { "-$arch" } else { "" }) + ".exe"
        >> "!PY_PS1!" echo $url  = "https://www.python.org/ftp/python/$ver/$file"
        >> "!PY_PS1!" echo $out  = Join-Path $env:TEMP 'python_installer.exe'
        >> "!PY_PS1!" echo try {
        >> "!PY_PS1!" echo     Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing
        >> "!PY_PS1!" echo     Write-Host "  Step 2 of 2: Installing Python (please wait)..."
        >> "!PY_PS1!" echo     $p = Start-Process $out -ArgumentList '/quiet InstallAllUsers=0 PrependPath=1 Include_test=0 SimpleInstall=1' -Wait -PassThru
        >> "!PY_PS1!" echo     Remove-Item $out -Force -ErrorAction SilentlyContinue
        >> "!PY_PS1!" echo     if ($p.ExitCode -ne 0) { Write-Host "  Installer exited with code $($p.ExitCode)"; exit 1 }
        >> "!PY_PS1!" echo     Write-Host "  Python installed!"
        >> "!PY_PS1!" echo     exit 0
        >> "!PY_PS1!" echo } catch {
        >> "!PY_PS1!" echo     Write-Host "  Download failed: $_"
        >> "!PY_PS1!" echo     exit 1
        >> "!PY_PS1!" echo }

        powershell -ExecutionPolicy Bypass -File "!PY_PS1!"
        set "PY_RESULT=!ERRORLEVEL!"
        del "!PY_PS1!" >nul 2>&1

        if !PY_RESULT! == 0 (
            echo.
            echo  Done! Adding Python to this session...
            :: Add the user Python install location to PATH for the current session
            :: so we don't need to restart the installer
            for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
                set "PATH=%%d;%%d\Scripts;!PATH!"
            )
            :: Re-detect Python
            where python >nul 2>&1
            if !ERRORLEVEL! == 0 (
                for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
                set "PYTHON_CMD=python"
            )
        ) else (
            echo.
            echo  Automatic installation did not complete.
            echo  See the manual steps below.
        )
    )
)

:: If Python still not found after auto-install attempt, show manual guide
if not defined PYTHON_CMD (
    echo.
    echo  ================================================
    echo   Manual Python installation - follow these steps
    echo  ================================================
    echo.
    echo   1. Open your web browser and go to:
    echo        https://www.python.org/downloads/
    echo.
    echo   2. Click the big yellow "Download Python" button
    echo.
    echo   3. Run the file that downloads
    echo.
    echo   4. IMPORTANT - on the first installer screen:
    echo        Check the box "Add Python to PATH"
    echo        ^(it's at the bottom of the window^)
    echo.
    echo   5. Click "Install Now" and wait for it to finish
    echo.
    echo   6. Come back and run INSTALL.bat again
    echo.
    set /p OPEN_BROWSER="  Open python.org in your browser now? (Y/N): "
    if /i "!OPEN_BROWSER!"=="Y" start https://www.python.org/downloads/
    echo.
    goto :END
)

echo  Python ready: !PYTHON_CMD! ^(!PY_VER!^)
echo.

:: Set install location
set "INSTALL_DIR=%LOCALAPPDATA%\Autograder4Canvas"

echo This will install Autograder4Canvas to:
echo   %INSTALL_DIR%
echo.
set /p CONFIRM="Continue? (Y/N): "
if /i not "%CONFIRM%"=="Y" (
    echo Installation cancelled.
    goto :END
)

echo.
echo Installing...

:: Get the directory where this installer is located
set "SOURCE_DIR=%~dp0"

:: Create install directory
if not exist "%INSTALL_DIR%\Programs" mkdir "%INSTALL_DIR%\Programs"
if not exist "%INSTALL_DIR%\config" mkdir "%INSTALL_DIR%\config"
if not exist "%INSTALL_DIR%\modules" mkdir "%INSTALL_DIR%\modules"
if not exist "%INSTALL_DIR%\docs" mkdir "%INSTALL_DIR%\docs"

:: Copy files
echo   Copying program files...
copy "%SOURCE_DIR%src\run_autograder.py" "%INSTALL_DIR%\" >nul
copy "%SOURCE_DIR%src\requirements.txt" "%INSTALL_DIR%\" >nul
if exist "%SOURCE_DIR%src\autograder_utils.py" copy "%SOURCE_DIR%src\autograder_utils.py" "%INSTALL_DIR%\" >nul
copy "%SOURCE_DIR%src\Programs\*.py" "%INSTALL_DIR%\Programs\" >nul

:: Write xcopy exclusion list to INSTALL_DIR (no spaces in path, unlike %TEMP%)
set "XCOPY_EXCL=%INSTALL_DIR%\excl.tmp"
> "%XCOPY_EXCL%" echo __pycache__
>> "%XCOPY_EXCL%" echo .pyc

:: Copy v2 files
if exist "%SOURCE_DIR%src\config" (
    echo   Copying v2 config files...
    xcopy /E /I /Y /EXCLUDE:"%XCOPY_EXCL%" "%SOURCE_DIR%src\config" "%INSTALL_DIR%\config" >nul
)
if exist "%SOURCE_DIR%src\modules" (
    echo   Copying v2 modules...
    xcopy /E /I /Y /EXCLUDE:"%XCOPY_EXCL%" "%SOURCE_DIR%src\modules" "%INSTALL_DIR%\modules" >nul
)
if exist "%SOURCE_DIR%src\docs" (
    echo   Copying documentation...
    xcopy /E /I /Y "%SOURCE_DIR%src\docs" "%INSTALL_DIR%\docs" >nul
)
del "%XCOPY_EXCL%" >nul 2>&1

:: Copy icon if it exists
if exist "%SOURCE_DIR%icon.ico" copy "%SOURCE_DIR%icon.ico" "%INSTALL_DIR%\" >nul

:: Install Python dependencies
echo   Installing required Python packages...
%PYTHON_CMD% -m pip install --quiet -r "%INSTALL_DIR%\requirements.txt"
if %ERRORLEVEL% neq 0 (
    echo   Warning: Some packages may not have installed correctly.
    echo   The program may still work, or you can run:
    echo     pip install -r "%INSTALL_DIR%\requirements.txt"
    echo   manually to fix this.
)

:: Create launcher batch file
echo   Creating launcher...
(
echo @echo off
echo setlocal enabledelayedexpansion
echo cd /d "%INSTALL_DIR%"
echo.
echo :: Find Python - check PATH first, then common install locations
echo set "PYTHON_CMD="
echo where python >nul 2>&1 && set "PYTHON_CMD=python"
echo if not defined PYTHON_CMD where python3 >nul 2>&1 && set "PYTHON_CMD=python3"
echo.
echo :: Also check standard user-install locations in case PATH wasn't updated
echo if not defined PYTHON_CMD ^(
echo     for /d %%%%d in ^("%LOCALAPPDATA%\Programs\Python\Python3*"^) do ^(
echo         if exist "%%%%d\python.exe" set "PYTHON_CMD=%%%%d\python.exe"
echo     ^)
echo ^)
echo.
echo if not defined PYTHON_CMD ^(
echo     echo.
echo     echo Python is not installed or could not be found.
echo     echo Please install it from https://www.python.org/downloads/
echo     echo Make sure to check "Add Python to PATH" during installation.
echo     echo.
echo     pause
echo     exit /b 1
echo ^)
echo.
echo %%PYTHON_CMD%% run_autograder.py %%*
echo pause
) > "%INSTALL_DIR%\Autograder4Canvas.bat"

:: Copy uninstaller into the install directory so it's always accessible
echo   Installing uninstaller...
copy "%SOURCE_DIR%UNINSTALL.bat" "%INSTALL_DIR%\UNINSTALL.bat" >nul

:: Create shortcuts via a temporary PowerShell script
:: Paths are resolved inside PowerShell (handles OneDrive Desktop, etc.)
echo   Creating shortcuts...
set "PS_TMP=%INSTALL_DIR%\shortcuts.ps1"

::  Write the PS1 line-by-line with >> to avoid block-parser paren issues
>  "%PS_TMP%" echo $installDir    = '%INSTALL_DIR%'
>> "%PS_TMP%" echo $batPath       = Join-Path $installDir 'Autograder4Canvas.bat'
>> "%PS_TMP%" echo $uninstallPath = Join-Path $installDir 'UNINSTALL.bat'
>> "%PS_TMP%" echo $icoPath       = Join-Path $installDir 'icon.ico'
>> "%PS_TMP%" echo $ws            = New-Object -ComObject WScript.Shell
>> "%PS_TMP%" echo(
>> "%PS_TMP%" echo # Resolve real Desktop and Start Menu paths (works with OneDrive redirection)
>> "%PS_TMP%" echo $desktop = [Environment]::GetFolderPath('Desktop')
>> "%PS_TMP%" echo $menuDir = [Environment]::GetFolderPath('Programs')
>> "%PS_TMP%" echo if (-not (Test-Path $menuDir)) { New-Item -Force -ItemType Directory $menuDir ^| Out-Null }
>> "%PS_TMP%" echo(
>> "%PS_TMP%" echo $s = $ws.CreateShortcut((Join-Path $desktop 'Autograder4Canvas.lnk'))
>> "%PS_TMP%" echo $s.TargetPath       = $batPath
>> "%PS_TMP%" echo $s.WorkingDirectory = $installDir
>> "%PS_TMP%" echo if (Test-Path $icoPath) { $s.IconLocation = $icoPath }
>> "%PS_TMP%" echo $s.Save()
>> "%PS_TMP%" echo(
>> "%PS_TMP%" echo $s = $ws.CreateShortcut((Join-Path $menuDir 'Autograder4Canvas.lnk'))
>> "%PS_TMP%" echo $s.TargetPath       = $batPath
>> "%PS_TMP%" echo $s.WorkingDirectory = $installDir
>> "%PS_TMP%" echo if (Test-Path $icoPath) { $s.IconLocation = $icoPath }
>> "%PS_TMP%" echo $s.Save()
>> "%PS_TMP%" echo(
>> "%PS_TMP%" echo $s = $ws.CreateShortcut((Join-Path $menuDir 'Uninstall Autograder4Canvas.lnk'))
>> "%PS_TMP%" echo $s.TargetPath       = $uninstallPath
>> "%PS_TMP%" echo $s.WorkingDirectory = $installDir
>> "%PS_TMP%" echo $s.Description      = 'Uninstall Autograder4Canvas'
>> "%PS_TMP%" echo $s.Save()

powershell -ExecutionPolicy Bypass -File "%PS_TMP%"
if %ERRORLEVEL% neq 0 (
    echo   Warning: Shortcuts could not be created automatically.
    echo   You can still run the program by opening:
    echo     %INSTALL_DIR%\Autograder4Canvas.bat
)
del "%PS_TMP%" >nul 2>&1

echo.
echo ========================================
echo    Installation Complete!
echo ========================================
echo.
echo Program installed to: %INSTALL_DIR%
echo.
echo You can now run Autograder4Canvas by:
echo   1. Clicking the Desktop shortcut
echo   2. Finding it in the Start Menu
echo.
echo To uninstall, run UNINSTALL.bat from the original zip,
echo or from the installed folder at:
echo   %INSTALL_DIR%\UNINSTALL.bat
echo.

:END
pause
INSTALL_EOF

    # Create the uninstaller batch script
    echo "  Creating Windows uninstaller..."
    cat > "$WIN_BUILD/UNINSTALL.bat" << 'UNINSTALL_EOF'
@echo off
setlocal

echo ========================================
echo    Autograder4Canvas Uninstaller
echo ========================================
echo.

set "INSTALL_DIR=%LOCALAPPDATA%\Autograder4Canvas"
set "SHORTCUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Autograder4Canvas.lnk"
set "DESKTOP_SHORTCUT=%USERPROFILE%\Desktop\Autograder4Canvas.lnk"

echo This will remove Autograder4Canvas from your computer:
echo   - Program files: %INSTALL_DIR%
echo   - Desktop shortcut
echo   - Start Menu shortcut
echo.
set /p CONFIRM="Are you sure? (Y/N): "
if /i not "%CONFIRM%"=="Y" (
    echo Uninstall cancelled.
    goto :END
)

echo.
echo Uninstalling...

:: Remove program files
:: cd out first - rmdir can fail if cmd.exe has the bat file open inside the target dir
cd /d "%TEMP%"
if exist "%INSTALL_DIR%" (
    echo   Removing program files...
    rmdir /s /q "%INSTALL_DIR%"
    if exist "%INSTALL_DIR%" (
        echo   Warning: Some files could not be removed. Close any open program windows and try again.
    ) else (
        echo   Done.
    )
) else (
    echo   Program files not found - already removed or not installed.
)

:: Remove shortcuts - use PowerShell to resolve real Desktop/Start Menu paths
echo   Removing shortcuts...
powershell -ExecutionPolicy Bypass -Command "$desktop = [Environment]::GetFolderPath('Desktop'); $menu = [Environment]::GetFolderPath('Programs'); @(Join-Path $desktop 'Autograder4Canvas.lnk', (Join-Path $menu 'Autograder4Canvas.lnk'), (Join-Path $menu 'Uninstall Autograder4Canvas.lnk')) | Where-Object { Test-Path $_ } | ForEach-Object { Remove-Item $_ -Force }"

echo.
echo ========================================
echo    Uninstall Complete!
echo ========================================
echo.
echo Autograder4Canvas has been removed from your computer.
echo.

:END
pause
UNINSTALL_EOF

    # Copy source files
    echo "  Copying source files..."
    mkdir -p "$WIN_BUILD/src/Programs"
    cp "$MAIN_SCRIPT" "$WIN_BUILD/src/run_autograder.py"
    cp "$SRC_DIR/requirements.txt" "$WIN_BUILD/src/"
    # Copy utilities if it exists
    [ -f "$SRC_DIR/autograder_utils.py" ] && cp "$SRC_DIR/autograder_utils.py" "$WIN_BUILD/src/"
    cp "$SRC_DIR/Programs/"*.py "$WIN_BUILD/src/Programs/"
    
    # Copy v2 files
    copy_v2_files "$WIN_BUILD/src"
    
    # Create and copy Windows icon
    create_ico "$WIN_BUILD"
    
    # Copy README
    cp "$SCRIPT_DIR/README.txt" "$WIN_BUILD/" 2>/dev/null || true
    
    # Create the zip (remove any previous version first so we don't accumulate stale entries)
    echo "  Creating zip archive..."
    mkdir -p "$DIST_DIR"
    rm -f "$DIST_DIR/Autograder4Canvas-Windows-v$VERSION.zip"
    # Strip __pycache__ dirs from the build tree before zipping
    find "$BUILD_DIR/windows" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$BUILD_DIR/windows" -name "*.pyc" -delete 2>/dev/null || true
    cd "$BUILD_DIR/windows"
    zip -r "$DIST_DIR/Autograder4Canvas-Windows-v$VERSION.zip" Autograder4Canvas \
        -x "*.DS_Store"
    
    echo -e "${GREEN}✓ Windows build complete: distro/Autograder4Canvas-Windows-v$VERSION.zip${NC}"
}

#-------------------------------------------------------------------------------
# Build Linux Distribution
#-------------------------------------------------------------------------------

build_linux() {
    echo ""
    echo -e "${BLUE}Building Linux distribution...${NC}"
    
    local LINUX_BUILD="$BUILD_DIR/linux/Autograder4Canvas"
    
    # Create build directory structure
    mkdir -p "$LINUX_BUILD"
    
    # Create the installer shell script
    echo "  Creating Linux installer..."
    cat > "$LINUX_BUILD/install.sh" << 'INSTALL_EOF'
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
mkdir -p "$INSTALL_DIR/config"
mkdir -p "$INSTALL_DIR/modules"
mkdir -p "$INSTALL_DIR/docs"
mkdir -p "$BIN_DIR"
mkdir -p "$DESKTOP_DIR"

# Copy files
echo "  Copying program files..."
cp "$SCRIPT_DIR/src/run_autograder.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/src/requirements.txt" "$INSTALL_DIR/"
[ -f "$SCRIPT_DIR/src/autograder_utils.py" ] && cp "$SCRIPT_DIR/src/autograder_utils.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/src/Programs/"*.py "$INSTALL_DIR/Programs/"

# Copy v2 files
if [ -d "$SCRIPT_DIR/src/config" ]; then
    echo "  Copying v2 config files..."
    cp -R "$SCRIPT_DIR/src/config/"* "$INSTALL_DIR/config/"
fi
if [ -d "$SCRIPT_DIR/src/modules" ]; then
    echo "  Copying v2 modules..."
    cp -R "$SCRIPT_DIR/src/modules/"* "$INSTALL_DIR/modules/"
fi
if [ -d "$SCRIPT_DIR/src/docs" ]; then
    echo "  Copying documentation..."
    cp -R "$SCRIPT_DIR/src/docs/"* "$INSTALL_DIR/docs/"
fi

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
INSTALL_EOF
    chmod +x "$LINUX_BUILD/install.sh"

    # Copy source files
    echo "  Copying source files..."
    mkdir -p "$LINUX_BUILD/src/Programs"
    cp "$MAIN_SCRIPT" "$LINUX_BUILD/src/run_autograder.py"
    cp "$SRC_DIR/requirements.txt" "$LINUX_BUILD/src/"
    # Copy utilities if it exists
    [ -f "$SRC_DIR/autograder_utils.py" ] && cp "$SRC_DIR/autograder_utils.py" "$LINUX_BUILD/src/"
    cp "$SRC_DIR/Programs/"*.py "$LINUX_BUILD/src/Programs/"
    
    # Copy v2 files
    copy_v2_files "$LINUX_BUILD/src"
    
    # Create and copy Linux icon
    create_png_icon "$LINUX_BUILD"
    
    # Copy README
    cp "$SCRIPT_DIR/README.txt" "$LINUX_BUILD/" 2>/dev/null || true
    
    # Create the tar.gz
    echo "  Creating tar.gz archive..."
    mkdir -p "$DIST_DIR"
    cd "$BUILD_DIR/linux"
    tar -czvf "$DIST_DIR/Autograder4Canvas-Linux-v$VERSION.tar.gz" Autograder4Canvas
    
    echo -e "${GREEN}✓ Linux build complete: distro/Autograder4Canvas-Linux-v$VERSION.tar.gz${NC}"
}

#-------------------------------------------------------------------------------
# Main
#-------------------------------------------------------------------------------

case "${1:-all}" in
    clean)
        clean_build
        ;;
    local)
        check_requirements mac
        build_local_app
        ;;
    mac)
        check_requirements mac
        mkdir -p "$BUILD_DIR" "$DIST_DIR"
        build_mac
        ;;
    win|windows)
        check_requirements win
        mkdir -p "$BUILD_DIR" "$DIST_DIR"
        build_windows
        ;;
    linux)
        check_requirements win
        mkdir -p "$BUILD_DIR" "$DIST_DIR"
        build_linux
        ;;
    release)
        # Tags the repo and pushes to GitHub, which triggers the Actions workflow
        # to build standalone .exe / .app / Linux binaries via PyInstaller.
        # Usage: ./build.sh release [version]   e.g.  ./build.sh release 2.1
        TAG_VERSION="${2:-$VERSION}"
        TAG="v$TAG_VERSION"

        echo ""
        echo -e "${BLUE}Releasing $TAG via GitHub Actions...${NC}"
        echo ""

        # Ensure working tree is clean
        if ! git diff --quiet || ! git diff --cached --quiet; then
            echo -e "${RED}✗ You have uncommitted changes. Commit or stash them first.${NC}"
            exit 1
        fi

        # Check tag doesn't already exist
        if git rev-parse "$TAG" >/dev/null 2>&1; then
            echo -e "${RED}✗ Tag $TAG already exists. Choose a different version.${NC}"
            exit 1
        fi

        echo "This will:"
        echo "  1. Create git tag $TAG"
        echo "  2. Push tag to GitHub"
        echo "  3. GitHub Actions will build standalone .exe / .app / .tar.gz"
        echo "  4. A GitHub Release will be created with all three files attached"
        echo ""
        read -p "Continue? (y/N): " CONFIRM
        if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
            echo "Release cancelled."
            exit 0
        fi

        git tag -a "$TAG" -m "Release $TAG"
        git push origin "$TAG"

        echo ""
        echo -e "${GREEN}✓ Tag $TAG pushed.${NC}"
        echo ""
        echo "GitHub Actions is now building:"
        echo "  • Autograder4Canvas-macOS.dmg   (standalone .app, no Python needed)"
        echo "  • Autograder4Canvas-Windows.zip  (standalone .exe, no Python needed)"
        echo "  • Autograder4Canvas-Linux.tar.gz (standalone binary)"
        echo ""
        echo "Watch progress at:"
        REMOTE_URL=$(git remote get-url origin 2>/dev/null | sed 's/\.git$//' | sed 's|git@github.com:|https://github.com/|')
        echo "  $REMOTE_URL/actions"
        echo ""
        echo "The release will appear at:"
        echo "  $REMOTE_URL/releases/tag/$TAG"
        ;;
    all|"")
        check_requirements
        clean_build
        mkdir -p "$BUILD_DIR" "$DIST_DIR"
        build_local_app
        build_mac
        build_windows
        build_linux
        echo ""
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}   Build Complete!${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo ""
        echo "Local app updated: $SCRIPT_DIR/Autograder4Canvas.app"
        echo ""
        echo "Distribution files created in: $DIST_DIR/"
        ls -lh "$DIST_DIR/"
        ;;
    *)
        echo "Usage: $0 [clean|local|mac|win|linux|all|release]"
        echo ""
        echo "  clean        Remove build artifacts"
        echo "  local        Build/update the local .app in this folder"
        echo "  mac          Build Mac distribution (DMG with .app)"
        echo "  win          Build Windows distribution (zip with INSTALL.bat, requires Python)"
        echo "  linux        Build Linux distribution (tar.gz with install.sh)"
        echo "  all          Build everything (default)"
        echo "  release [v]  Tag + push to GitHub → triggers standalone .exe/.app build"
        exit 1
        ;;
esac

echo ""
