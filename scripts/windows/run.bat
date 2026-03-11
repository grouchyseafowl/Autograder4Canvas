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
    :: File missing entirely - create a blank one so we can write to it
    (
        echo @echo off
        echo set CANVAS_BASE_URL=https://yourschool.instructure.com
        echo set CANVAS_API_TOKEN=your_api_token_here
    ) > "!CREDS_FILE!"
)

call "!CREDS_FILE!"

:: -------------------------------------------------------
:: First-time credential setup (runs once, then saves)
:: -------------------------------------------------------
set "NEEDS_SETUP=0"
if "!CANVAS_BASE_URL!"=="https://yourschool.instructure.com" set "NEEDS_SETUP=1"
if "!CANVAS_API_TOKEN!"=="your_api_token_here" set "NEEDS_SETUP=1"

if "!NEEDS_SETUP!"=="1" (
    echo  First-time setup: enter your Canvas credentials.
    echo  These will be saved so you won't be asked again.
    echo.

    if "!CANVAS_BASE_URL!"=="https://yourschool.instructure.com" (
        echo  Canvas URL -- the address you use to log in to Canvas.
        echo  Example: https://myschool.instructure.com
        echo.
        set /p "CANVAS_BASE_URL=  Canvas URL: "
        echo.
        if "!CANVAS_BASE_URL!"=="" (
            echo  No URL entered. Please run again.
            pause
            exit /b 1
        )
    )

    if "!CANVAS_API_TOKEN!"=="your_api_token_here" (
        echo  API Token -- found in Canvas under:
        echo    Profile picture ^(top right^) ^> Settings ^> Approved Integrations
        echo    Click "+ New Access Token", give it a name, click Generate.
        echo.
        set /p "CANVAS_API_TOKEN=  API Token: "
        echo.
        if "!CANVAS_API_TOKEN!"=="" (
            echo  No token entered. Please run again.
            pause
            exit /b 1
        )
    )

    :: Save credentials to credentials.bat
    (
        echo @echo off
        echo :: Autograder4Canvas -- Credentials
        echo :: To update: delete this file and run run.bat again.
        echo set CANVAS_BASE_URL=!CANVAS_BASE_URL!
        echo set CANVAS_API_TOKEN=!CANVAS_API_TOKEN!
    ) > "!CREDS_FILE!"

    echo  Credentials saved. You won't be asked again.
    echo.
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

:: -------------------------------------------------------
:: Create/reuse virtual environment
:: -------------------------------------------------------
set "VENV_DIR=%~dp0venv"
set "VENV_PYTHON=!VENV_DIR!\Scripts\python.exe"
set "VENV_PIP=!VENV_DIR!\Scripts\pip.exe"

if not exist "!VENV_PYTHON!" (
    echo  Setting up Python environment (one-time, takes a minute)...
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
        echo  WARNING: Some packages may not have installed correctly.
        echo  If the program fails, open a Command Prompt here and run:
        echo    venv\Scripts\pip install -r src\requirements.txt
        echo.
    ) else (
        echo  Done.
    )
    echo.
)

:: Tell Python which venv to use for running sub-scripts
set "AUTOGRADER_VENV_PYTHON=!VENV_PYTHON!"

:: -------------------------------------------------------
:: Run the autograder
:: -------------------------------------------------------
cd /d "%~dp0"
"!VENV_PYTHON!" src\run_autograder.py %*
echo.
pause
