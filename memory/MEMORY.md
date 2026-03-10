# Autograder4Canvas - Project Memory

## Key Files
- `build/windows-portable/` — portable no-install Windows distribution
- `build/windows/Autograder4Canvas/` — installer-based Windows build (INSTALL.bat)
- `src/` — canonical source (macOS-primary)
- `distro/` — release zips including `Autograder4Canvas-Windows-Portable.zip`

## Windows Portable Structure
- `run.bat` — loads credentials.bat, creates local venv on first run, launches Python
- `credentials.bat` — user fills in CANVAS_BASE_URL and CANVAS_API_TOKEN once
- `src/run_autograder.py` — patched: encoding='utf-8' on all file opens, Windows credential save writes to credentials.bat via AUTOGRADER_CREDS_FILE env var

## Known Windows Issues Fixed
- `open()` without encoding='utf-8' crashes on Windows with non-ASCII text
- Windows credential "save permanently" was print-only; now writes to credentials.bat
- Added `chcp 65001` to run.bat so UTF-8/emoji output works in cmd.exe

## Python Requirements
requests, python-dateutil, pytz, openpyxl, pandas
