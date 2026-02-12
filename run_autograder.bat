@echo off
REM ===============================================================================
REM                        CANVAS AUTOGRADER LAUNCHER
REM                             Windows Version
REM                               Version 1.3+
REM ===============================================================================

setlocal enabledelayedexpansion

REM Change to the directory containing this script
cd /d "%~dp0"

echo.
echo ========================================
echo    Canvas Autograder
echo ========================================
echo.

REM Check for Python
call :check_python
if errorlevel 1 goto :python_not_found

REM Find the launcher script in src/
call :find_launcher
if errorlevel 1 goto :error_exit

echo.
echo Starting Canvas Autograder...
echo The program will guide you through any remaining setup.
echo.

REM Run the launcher
%PYTHON_CMD% "%LAUNCHER%"

REM Check exit code
if errorlevel 1 (
    echo.
    echo [WARNING] Program exited with an error
    echo.
)

pause
goto :eof

REM ========================================
REM           HELPER FUNCTIONS
REM ========================================

:check_python
REM Try 'python' first (Windows default)
where python >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
    echo [OK] Python found: !PYVER!
    set PYTHON_CMD=python
    exit /b 0
)

REM Try 'python3' (some installations)
where python3 >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=2" %%v in ('python3 --version 2^>^&1') do set PYVER=%%v
    echo [OK] Python 3 found: !PYVER!
    set PYTHON_CMD=python3
    exit /b 0
)

REM Try 'py' launcher
where py >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=2" %%v in ('py --version 2^>^&1') do set PYVER=%%v
    echo [OK] Python found via py launcher: !PYVER!
    set PYTHON_CMD=py
    exit /b 0
)

REM Python not found
exit /b 1

:python_not_found
echo [ERROR] Python 3 not found!
echo.
echo Autograder4Canvas requires Python 3.7 or higher.
echo.
echo Please install Python:
echo.
echo   Download from: https://www.python.org/downloads/
echo.
echo   IMPORTANT: During installation, check "Add Python to PATH"
echo.
echo Options:
echo   [1] Open Python download page in browser
echo   [2] Exit and install manually
echo.

set /p choice="Choose option (1 or 2, default=2): "
if "%choice%"=="" set choice=2

if "%choice%"=="1" (
    echo.
    echo Opening Python download page in your browser...
    start https://www.python.org/downloads/
    echo.
    echo After installing Python:
    echo   1. Make sure to check "Add Python to PATH" during installation
    echo   2. Complete the installation
    echo   3. Close and reopen this window
    echo   4. Run this program again
    echo.
    pause
) else (
    echo.
    echo Please install Python 3.7+ and run this program again.
    echo.
    pause
)
exit /b 1

:find_launcher
REM Look for any run_autograder*.py in src/ directory (version-agnostic)
set LAUNCHER=
set NEWEST_VERSION=

REM Check if src directory exists
if not exist "%~dp0src\" (
    echo [ERROR] src\ directory not found!
    echo.
    echo Expected location: src\run_autograder*.py
    echo Current directory: %cd%
    echo.
    goto :eof
)

REM Find all run_autograder*.py files and get the newest
for %%f in ("%~dp0src\run_autograder*.py") do (
    if exist "%%f" (
        set LAUNCHER=%%f
        REM Keep last one found (works for simple version ordering)
    )
)

if "%LAUNCHER%"=="" (
    echo [ERROR] Launcher script not found!
    echo.
    echo Expected location: src\run_autograder*.py
    echo Current directory: %cd%
    echo.
    echo Make sure the src\ directory contains the main Python script.
    echo.
    exit /b 1
)

REM Extract just the filename for display
for %%f in ("%LAUNCHER%") do set LAUNCHER_NAME=%%~nxf
echo [OK] Found launcher: !LAUNCHER_NAME!
exit /b 0

:error_exit
pause
exit /b 1
