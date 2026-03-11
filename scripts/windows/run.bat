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
if "!NEEDS_SETUP!"=="0" goto :creds_done

echo  ============================================================
echo   First-Time Setup
echo  ============================================================
echo  Enter your Canvas credentials below. They will be saved
echo  so you won't be asked again.
echo.

if not "!CANVAS_BASE_URL!"=="https://yourschool.instructure.com" goto :skip_url

echo  Canvas URL -- the web address you use to log in to Canvas.
echo  Example: https://myschool.instructure.com
echo.
set /p "CANVAS_BASE_URL=  Canvas URL: "
echo.
if "!CANVAS_BASE_URL!"=="" (
    echo  No URL entered. Please run again.
    pause
    exit /b 1
)

:skip_url
if not "!CANVAS_API_TOKEN!"=="your_api_token_here" goto :skip_token

echo  API Token -- find it in Canvas:
echo    1. Click your profile picture ^(top right^)
echo    2. Click Settings
echo    3. Scroll to Approved Integrations
echo    4. Click New Access Token, give it a name, click Generate
echo    5. Copy the token and paste it here
echo.
set /p "CANVAS_API_TOKEN=  API Token: "
echo.
if "!CANVAS_API_TOKEN!"=="" (
    echo  No token entered. Please run again.
    pause
    exit /b 1
)

:skip_token
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

:creds_done
set "AUTOGRADER_CREDS_FILE=!CREDS_FILE!"

:: -------------------------------------------------------
:: Locate Python 3
:: NOTE: We skip Microsoft Store app stubs (in WindowsApps).
::       Those stubs report a version number but cannot create venvs.
:: -------------------------------------------------------
set "PYTHON_CMD="

for /f "tokens=*" %%p in ('where python 2^>nul') do (
    if not defined PYTHON_CMD (
        echo %%p | findstr /i "WindowsApps" >nul 2>&1
        if !ERRORLEVEL! neq 0 (
            for /f "tokens=2 delims= " %%v in ('"%%p" --version 2^>^&1') do set "PY_VER=%%v"
            if "!PY_VER:~0,1!"=="3" set "PYTHON_CMD=%%p"
        )
    )
)

if not defined PYTHON_CMD (
    for /f "tokens=*" %%p in ('where python3 2^>nul') do (
        if not defined PYTHON_CMD (
            echo %%p | findstr /i "WindowsApps" >nul 2>&1
            if !ERRORLEVEL! neq 0 set "PYTHON_CMD=%%p"
        )
    )
)

if not defined PYTHON_CMD (
    for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
        if exist "%%d\python.exe" set "PYTHON_CMD=%%d\python.exe"
    )
)

if not defined PYTHON_CMD (
    for /d %%d in ("%PROGRAMFILES%\Python3*") do (
        if exist "%%d\python.exe" set "PYTHON_CMD=%%d\python.exe"
    )
)

if not defined PYTHON_CMD (
    echo  ============================================================
    echo   Python Not Found
    echo  ============================================================
    echo.
    echo  This program needs Python 3, which is not installed yet.
    echo.
    echo  Opening the download page in your browser now...
    start https://www.python.org/downloads/
    echo.
    echo  Once the page opens:
    echo    1. Click the big yellow "Download Python" button
    echo    2. Run the installer that downloads
    echo    3. IMPORTANT: on the first screen, check the box that says
    echo       "Add Python to PATH"  ^<-- this box must be checked
    echo    4. Click "Install Now" and wait for it to finish
    echo    5. Close this window, then double-click run.bat again
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
    echo  Setting up Python environment (one-time, takes a minute)...
    echo.
    !PYTHON_CMD! -m venv "!VENV_DIR!"
    if !ERRORLEVEL! neq 0 (
        echo.
        echo  ============================================================
        echo   Python Setup Failed
        echo  ============================================================
        echo.
        echo  Python was found but could not set up a working environment.
        echo  This usually means Python was installed from the Microsoft
        echo  Store, which does not fully work for this program.
        echo.
        echo  Opening the Python download page in your browser...
        start https://www.python.org/downloads/
        echo.
        echo  To fix this:
        echo    1. Uninstall Python from the Microsoft Store
        echo       (Start ^> Settings ^> Apps ^> search "Python" ^> Uninstall)
        echo    2. Install Python from the page that just opened
        echo    3. IMPORTANT: check "Add Python to PATH" on the first screen
        echo    4. Close this window, then double-click run.bat again
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
