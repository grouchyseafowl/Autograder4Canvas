[README.txt](https://github.com/user-attachments/files/24333327/README.txt)
===============================================================================
                          CANVAS AUTOGRADER
                     Universal Cross-Platform Edition
                              Version 1.3
===============================================================================

DESCRIPTION
-----------
Automated grading tools for Canvas LMS including:
  • Academic Dishonesty Detection
  • Complete/Incomplete Assignment Grading
  • Discussion Forum Grading


SYSTEM REQUIREMENTS
-------------------
  • Python 3.7 or higher
  • Internet connection (for Canvas API access)
  • Canvas API token (instructions provided below)


===============================================================================
                            INSTALLATION
===============================================================================

┌─────────────────────────────────────────────────────────────────────────────┐
│  macOS                                                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. Unzip the downloaded file                                              │
│  2. Drag "CanvasAutograder.app" to your Applications folder                │
│  3. Double-click to run                                                    │
│     (If blocked: Right-click → Open → "Open Anyway")                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  WINDOWS                                                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. Unzip the downloaded file                                              │
│  2. Double-click "INSTALL.bat"                                             │
│  3. Follow the prompts                                                     │
│                                                                             │
│  This installs the program to your AppData folder and creates              │
│  a "Canvas Autograder" shortcut on your Desktop.                           │
│                                                                             │
│  To uninstall: Delete the Desktop shortcut and the folder at               │
│  %LOCALAPPDATA%\CanvasAutograder                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  LINUX                                                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. Extract: tar -xzf CanvasAutograder-Linux-v*.tar.gz                     │
│  2. Run: ./CanvasAutograder/install.sh                                     │
│  3. Follow the prompts                                                     │
│                                                                             │
│  This installs to ~/.local/share/CanvasAutograder and creates:             │
│    • Command: canvas-autograder (in ~/.local/bin)                          │
│    • App menu entry (in ~/.local/share/applications)                       │
│                                                                             │
│  To uninstall:                                                             │
│    rm -rf ~/.local/share/CanvasAutograder                                  │
│    rm ~/.local/bin/canvas-autograder                                       │
│    rm ~/.local/share/applications/canvas-autograder.desktop                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘


===============================================================================
                          FIRST TIME SETUP
===============================================================================

When you run the program for the FIRST TIME:

1. It will check for Python 3 (if not installed, it will guide you)
2. It will create a virtual environment (.venv folder)
3. It will install required dependencies (takes ~30 seconds)
4. You'll be prompted for your Canvas API token

After the first run, the program starts much faster.


===============================================================================
                      GETTING YOUR CANVAS API TOKEN
===============================================================================

1. Log in to Canvas
2. Go to Account → Settings (click your profile picture → Settings)
3. Scroll down to "Approved Integrations"
4. Click "+ New Access Token"
5. Give it a purpose (e.g., "Autograder")
6. Click "Generate Token"
7. COPY THE TOKEN immediately (you can't see it again!)
8. Paste it when the program asks for it

⚠️  KEEP YOUR TOKEN SECRET - it has access to your Canvas account!


===============================================================================
                           FOLDER STRUCTURE
===============================================================================

CanvasAutograder/
├── CanvasAutograder.app       ← macOS double-click app
├── run_autograder.sh          ← Mac/Linux launcher
├── run_autograder.bat         ← Windows launcher
├── README.txt                 ← This file
└── src/
    ├── run_autograder.py      ← Main program
    ├── requirements.txt       ← Python dependencies
    └── Programs/
        ├── Academic_Dishonesty_Check_v1-2.py
        ├── Autograder_Complete-Incomplete_v1-2.py
        └── Autograder_Discussion_Forum_v1-2.py


===============================================================================
                           OUTPUT FILES
===============================================================================

All grading reports are saved to:
  ~/Documents/Grading_Rationales/

Organized by type:
  • Academic_Dishonesty/
  • Discussion_Forums/
  • Complete-Incomplete_Assignments/


===============================================================================
                          TROUBLESHOOTING
===============================================================================

PYTHON NOT FOUND
  macOS:    brew install python3  (or download from python.org)
  Windows:  Download from python.org — CHECK "Add Python to PATH"!
  Linux:    sudo apt install python3 python3-pip python3-venv

PERMISSION DENIED (Mac/Linux)
  chmod +x run_autograder.sh

MACOS APP BLOCKED
  Right-click → Open → "Open Anyway"

MODULE NOT FOUND
  The program auto-installs dependencies. If issues persist:
  pip install -r src/requirements.txt


===============================================================================
                    © 2025 Canvas Autograder Project
===============================================================================
