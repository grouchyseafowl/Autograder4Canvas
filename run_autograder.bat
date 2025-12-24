@echo off
REM ===============================================================================
REM                        CANVAS AUTOGRADER LAUNCHER
REM                             Windows Version
REM ===============================================================================

setlocal enabledelayedexpansion

REM Change to the directory containing this script
cd /d "%~dp0"

echo.
echo ========================================
echo       Canvas Autograder Launcher
echo ========================================
echo.

REM Check for Python
call :check_python
if errorlevel 1 goto :eof

REM Find the launcher script
call :find_launcher
if errorlevel 1 goto :eof

echo.
echo Starting Canvas Autograder...
echo.

REM Run the launcher
%PYTHON_CMD% "%LAUNCHER%"

echo.
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

echo [ERROR] Python 3 not found!
echo.
echo Please install Python 3.7 or higher:
echo.
echo   1. Download from: https://www.python.org/downloads/
echo   2. Run the installer
echo   3. IMPORTANT: Check "Add Python to PATH" during installation
echo.
echo After installing, close and reopen this window.
echo.
pause
exit /b 1

:find_launcher
REM Look for src/run_autograder.py
set LAUNCHER=src\run_autograder.py

if exist "%LAUNCHER%" (
    echo [OK] Found launcher: %LAUNCHER%
    exit /b 0
)

REM Fallback: look for any run_autograder*.py in src/
for %%f in (src\run_autograder*.py) do (
    if exist "%%f" (
        set LAUNCHER=%%f
        echo [OK] Found launcher: !LAUNCHER!
        exit /b 0
    )
)

echo [ERROR] Launcher script not found!
echo.
echo Expected: src\run_autograder.py
echo Current directory: %cd%
echo.
pause
exit /b 1
