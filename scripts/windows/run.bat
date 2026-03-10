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

call "!CREDS_FILE!"

:: Check that the user filled in their credentials
if "%CANVAS_BASE_URL%"=="https://yourschool.instructure.com" (
    echo  ============================================================
    echo   Setup Required
    echo  ============================================================
    echo.
    echo  Please edit credentials.bat before running:
    echo.
    echo  1. Right-click credentials.bat and choose "Open with Notepad"
    echo  2. Replace  https://yourschool.instructure.com
    echo     with your real Canvas URL (e.g. https://myschool.instructure.com)
    echo  3. Replace  your_api_token_here
    echo     with your Canvas API token
    echo  4. Save the file, then double-click run.bat again
    echo.
    echo  (See the comments inside credentials.bat for how to get your token)
    echo.
    pause
    exit /b 1
)

if "%CANVAS_API_TOKEN%"=="your_api_token_here" (
    echo  ============================================================
    echo   Setup Required - API Token Missing
    echo  ============================================================
    echo.
    echo  Please open credentials.bat in Notepad and replace
    echo  "your_api_token_here" with your Canvas API token.
    echo.
    pause
    exit /b 1
)

:: Export so child processes see them
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
    if %ERRORLEVEL% == 0 set "PYTHON_CMD=python3"
)

if not defined PYTHON_CMD (
    for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
        if exist "%%d\python.exe" set "PYTHON_CMD=%%d\python.exe"
    )
)

if not defined PYTHON_CMD (
    echo  Python is not installed or could not be found.
    echo.
    echo  Please install Python 3 from:
    echo    https://www.python.org/downloads/
    echo.
    echo  IMPORTANT: On the first screen of the installer,
    echo  check the box "Add Python to PATH" at the bottom.
    echo.
    pause
    exit /b 1
)

echo  Python found: !PYTHON_CMD!
echo.

:: -------------------------------------------------------
:: Create/reuse local virtual environment
:: -------------------------------------------------------
set "VENV_DIR=%~dp0venv"
set "VENV_PYTHON=!VENV_DIR!\Scripts\python.exe"
set "VENV_PIP=!VENV_DIR!\Scripts\pip.exe"

if not exist "!VENV_PYTHON!" (
    echo  First-time setup: creating local Python environment...
    echo  (This only happens once and takes about a minute)
    echo.
    !PYTHON_CMD! -m venv "!VENV_DIR!"
    if !ERRORLEVEL! neq 0 (
        echo  ERROR: Could not create virtual environment.
        echo  Try running this file as Administrator.
        echo.
        pause
        exit /b 1
    )

    echo  Installing required packages...
    "!VENV_PIP!" install --quiet -r "%~dp0src\requirements.txt"
    if !ERRORLEVEL! neq 0 (
        echo  WARNING: Some packages may not have installed correctly.
        echo  The program will still try to run. If it fails, open a
        echo  Command Prompt here and run:
        echo    venv\Scripts\pip install -r src\requirements.txt
        echo.
    ) else (
        echo  Packages installed.
    )
    echo.
)

:: -------------------------------------------------------
:: Run the autograder
:: -------------------------------------------------------
cd /d "%~dp0"
"!VENV_PYTHON!" src\run_autograder.py %*
echo.
pause
