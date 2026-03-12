@echo off
setlocal
echo ========================================
echo    Building Autograder4Canvas.exe
echo ========================================
echo.

:: Find Python
set "PYTHON_CMD="
where python >nul 2>&1 && set "PYTHON_CMD=python"
if not defined PYTHON_CMD where python3 >nul 2>&1 && set "PYTHON_CMD=python3"
if not defined PYTHON_CMD (
    for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
        if exist "%%d\python.exe" set "PYTHON_CMD=%%d\python.exe"
    )
)
if not defined PYTHON_CMD (
    echo ERROR: Python not found. Install from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Using: %PYTHON_CMD%
echo.

:: Install build dependencies
echo Installing build dependencies...
%PYTHON_CMD% -m pip install --quiet pyinstaller requests python-dateutil pytz openpyxl pandas pyyaml
echo.

:: Change to this script's directory
cd /d "%~dp0"

:: Run PyInstaller
echo Running PyInstaller...
echo.
%PYTHON_CMD% -m PyInstaller Autograder4Canvas.spec --noconfirm

if %ERRORLEVEL% == 0 (
    echo.
    echo ========================================
    echo    Build complete!
    echo ========================================
    echo.
    echo Output: %~dp0dist\Autograder4Canvas\
    echo.
    echo The exe and all supporting files are in the dist folder.
    echo You can zip that folder and distribute it.
) else (
    echo.
    echo Build FAILED. Check errors above.
)

echo.
pause
