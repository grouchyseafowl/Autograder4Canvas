@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

:: -------------------------------------------------------
:: Load credentials from credentials.bat
:: -------------------------------------------------------
set "CREDS_FILE=%~dp0credentials.bat"

if not exist "!CREDS_FILE!" (
    echo.
    echo  ERROR: credentials.bat not found in this folder.
    echo  Make sure credentials.bat is in the same folder as run.bat.
    echo.
    pause
    exit /b 1
)

call "!CREDS_FILE!" /from-run

:: Check that the user filled in their credentials
if "%CANVAS_BASE_URL%"=="https://yourschool.instructure.com" (
    echo.
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
    echo  (See the comments inside credentials.bat for how to get a token)
    echo.
    pause
    exit /b 1
)

if "%CANVAS_API_TOKEN%"=="your_api_token_here" (
    echo.
    echo  Setup Required - API Token Missing
    echo.
    echo  Please open credentials.bat in Notepad and replace
    echo  "your_api_token_here" with your Canvas API token.
    echo.
    pause
    exit /b 1
)

:: Pass credentials file path so Python can write back to it on save
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
    echo.
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

:: -------------------------------------------------------
:: Run the autograder (it manages its own .venv on first run)
:: -------------------------------------------------------
cd /d "%~dp0"
"!PYTHON_CMD!" src\run_autograder.py %*
echo.
pause
