@echo off
REM ===============================================================================
REM                    CANVAS AUTOGRADER INSTALLER - Windows
REM ===============================================================================

setlocal enabledelayedexpansion

echo.
echo ========================================
echo   Autograder4Canvas Installer
echo ========================================
echo.

REM Set install location
set "INSTALL_DIR=%LOCALAPPDATA%\Autograder4Canvas"

echo This will install Autograder4Canvas to:
echo   %INSTALL_DIR%
echo.
echo And create a launcher on your Desktop.
echo.
set /p CONFIRM="Continue? (Y/N): "
if /i not "%CONFIRM%"=="Y" (
    echo Installation cancelled.
    pause
    exit /b 0
)

echo.
echo Installing...

REM Create install directory
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if not exist "%INSTALL_DIR%\Programs" mkdir "%INSTALL_DIR%\Programs"

REM Copy files
echo   Copying program files...
copy /Y "%~dp0src\run_autograder.py" "%INSTALL_DIR%\" >nul
copy /Y "%~dp0src\requirements.txt" "%INSTALL_DIR%\" >nul
copy /Y "%~dp0src\Programs\*.py" "%INSTALL_DIR%\Programs\" >nul
if exist "%~dp0icon.ico" copy /Y "%~dp0icon.ico" "%INSTALL_DIR%\" >nul

REM Create the launcher batch file in install directory (hidden)
echo   Creating launcher...
set "LAUNCHER_SCRIPT=%INSTALL_DIR%\launch.bat"

(
echo @echo off
echo cd /d "%INSTALL_DIR%"
echo.
echo REM Check for Python
echo where python ^>nul 2^>^&1
echo if %%errorlevel%% equ 0 ^(
echo     python run_autograder.py
echo ^) else ^(
echo     where py ^>nul 2^>^&1
echo     if %%errorlevel%% equ 0 ^(
echo         py run_autograder.py
echo     ^) else ^(
echo         echo Python not found. Please install Python 3.7+ from python.org
echo         pause
echo         exit /b 1
echo     ^)
echo ^)
echo pause
) > "%LAUNCHER_SCRIPT%"

REM Create desktop shortcut with icon using PowerShell
echo   Creating desktop shortcut...
set "DESKTOP=%USERPROFILE%\Desktop"
set "SHORTCUT=%DESKTOP%\Autograder4Canvas.lnk"
set "ICON_PATH=%INSTALL_DIR%\icon.ico"

powershell -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $s = $ws.CreateShortcut('%SHORTCUT%'); ^
   $s.TargetPath = '%LAUNCHER_SCRIPT%'; ^
   $s.WorkingDirectory = '%INSTALL_DIR%'; ^
   if (Test-Path '%ICON_PATH%') { $s.IconLocation = '%ICON_PATH%' }; ^
   $s.Save()"

echo.
echo ========================================
echo   Installation Complete!
echo ========================================
echo.
echo Program installed to: %INSTALL_DIR%
echo Desktop shortcut created: %SHORTCUT%
echo.
echo You can now double-click "Autograder4Canvas" on your Desktop.
echo.
echo To uninstall, simply delete:
echo   - The Desktop shortcut
echo   - The folder: %INSTALL_DIR%
echo.
pause
