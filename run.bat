@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0"

:: Find a real Python 3 (skip Microsoft Store stubs)
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
    echo  Python 3 not found. Please install from https://www.python.org/downloads/
    start https://www.python.org/downloads/
    pause
    exit /b 1
)

"!PYTHON_CMD!" "%~dp0src\bootstrap.py" %*
pause
