@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

echo ========================================
echo    Autograder4Canvas
echo ========================================
echo.

:: -------------------------------------------------------
:: Load credentials from credentials.bat
:: -------------------------------------------------------
set "CREDS_FILE=%~dp0credentials.bat"

if not exist "!CREDS_FILE!" (
    echo  ERROR: credentials.bat not found in this folder.
    echo  Make sure credentials.bat is in the same folder as run.bat.
    echo.
    pause
    exit /b 1
)

call "!CREDS_FILE!" /from-run

if "%CANVAS_BASE_URL%"=="https://yourschool.instructure.com" (
    echo  ============================================================
    echo   Setup Required
    echo  ============================================================
    echo.
    echo  Please edit credentials.bat before running:
    echo.
    echo  1. Right-click credentials.bat and choose "Open with Notepad"
    echo  2. Replace  https://yourschool.instructure.com
    echo     with your real Canvas URL
    echo  3. Replace  your_api_token_here
    echo     with your Canvas API token
    echo  4. Save the file, then double-click run.bat again
    echo.
    pause
    exit /b 1
)

if "%CANVAS_API_TOKEN%"=="your_api_token_here" (
    echo  Setup Required - API Token Missing
    echo.
    echo  Please open credentials.bat in Notepad and replace
    echo  "your_api_token_here" with your Canvas API token.
    echo.
    pause
    exit /b 1
)

set "AUTOGRADER_CREDS_FILE=!CREDS_FILE!"

:: -------------------------------------------------------
:: Locate Python 3
:: -------------------------------------------------------
set "PYTHON_CMD="

where python >nul 2>&1
if %ERRORLEVEL% == 0 (
    for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
    if "!PY_VER:~0,1!"=="3" set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    where python3 >nul 2>&1
    if !ERRORLEVEL! == 0 set "PYTHON_CMD=python3"
)

if not defined PYTHON_CMD (
    for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
        if exist "%%d\python.exe" set "PYTHON_CMD=%%d\python.exe"
    )
)

if not defined PYTHON_CMD (
    echo  ERROR: Python 3 not found.
    echo.
    echo  Please install Python 3 from https://www.python.org/downloads/
    echo  On the installer, check "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

echo  Python: !PYTHON_CMD!
echo.

:: -------------------------------------------------------
:: Create/reuse virtual environment
:: -------------------------------------------------------
set "VENV_DIR=%~dp0venv"
set "VENV_PYTHON=!VENV_DIR!\Scripts\python.exe"
set "VENV_PIP=!VENV_DIR!\Scripts\pip.exe"

if not exist "!VENV_PYTHON!" (
    echo  First-time setup: creating local Python environment...
    echo  (This only happens once - may take a minute or two)
    echo.
    !PYTHON_CMD! -m venv "!VENV_DIR!"
    if !ERRORLEVEL! neq 0 (
        echo.
        echo  ERROR: Could not create virtual environment.
        echo  Try right-clicking run.bat and choosing "Run as administrator".
        echo.
        pause
        exit /b 1
    )

    echo  Installing required packages...
    "!VENV_PIP!" install --quiet -r "%~dp0src\requirements.txt"
    if !ERRORLEVEL! neq 0 (
        echo.
        echo  WARNING: Some packages may not have installed.
        echo  If the program fails, open a Command Prompt here and run:
        echo    venv\Scripts\pip install -r src\requirements.txt
        echo.
    ) else (
        echo  Packages installed.
    )
    echo.
)

:: Tell the Python script to use this venv for running sub-scripts
:: (skips the script's own venv creation logic)
set "AUTOGRADER_VENV_PYTHON=!VENV_PYTHON!"

:: -------------------------------------------------------
:: Run the autograder
:: -------------------------------------------------------
cd /d "%~dp0"
"!VENV_PYTHON!" src\run_autograder.py %*
echo.
pause
