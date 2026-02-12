@echo off
setlocal enabledelayedexpansion

echo ========================================
echo    Autograder4Canvas Installer
echo ========================================
echo.

:: Set install location
set "INSTALL_DIR=%LOCALAPPDATA%\Autograder4Canvas"

echo This will install Autograder4Canvas to:
echo   %INSTALL_DIR%
echo.
set /p CONFIRM="Continue? (Y/N): "
if /i not "%CONFIRM%"=="Y" (
    echo Installation cancelled.
    goto :END
)

echo.
echo Installing...

:: Get the directory where this installer is located
set "SOURCE_DIR=%~dp0"

:: Create install directory
if not exist "%INSTALL_DIR%\Programs" mkdir "%INSTALL_DIR%\Programs"
if not exist "%INSTALL_DIR%\config" mkdir "%INSTALL_DIR%\config"
if not exist "%INSTALL_DIR%\modules" mkdir "%INSTALL_DIR%\modules"
if not exist "%INSTALL_DIR%\docs" mkdir "%INSTALL_DIR%\docs"

:: Copy files
echo   Copying program files...
copy "%SOURCE_DIR%src\run_autograder.py" "%INSTALL_DIR%\" >nul
copy "%SOURCE_DIR%src\requirements.txt" "%INSTALL_DIR%\" >nul
if exist "%SOURCE_DIR%src\autograder_utils.py" copy "%SOURCE_DIR%src\autograder_utils.py" "%INSTALL_DIR%\" >nul
copy "%SOURCE_DIR%src\Programs\*.py" "%INSTALL_DIR%\Programs\" >nul

:: Copy v2 files
if exist "%SOURCE_DIR%src\config" (
    echo   Copying v2 config files...
    xcopy /E /I /Y "%SOURCE_DIR%src\config" "%INSTALL_DIR%\config" >nul
)
if exist "%SOURCE_DIR%src\modules" (
    echo   Copying v2 modules...
    xcopy /E /I /Y "%SOURCE_DIR%src\modules" "%INSTALL_DIR%\modules" >nul
)
if exist "%SOURCE_DIR%src\docs" (
    echo   Copying documentation...
    xcopy /E /I /Y "%SOURCE_DIR%src\docs" "%INSTALL_DIR%\docs" >nul
)

:: Copy icon if it exists
if exist "%SOURCE_DIR%icon.ico" copy "%SOURCE_DIR%icon.ico" "%INSTALL_DIR%\" >nul

:: Create launcher batch file
echo   Creating launcher...
(
echo @echo off
echo cd /d "%INSTALL_DIR%"
echo python run_autograder.py %%*
echo pause
) > "%INSTALL_DIR%\Autograder4Canvas.bat"

:: Create Start Menu shortcut using PowerShell
echo   Creating Start Menu shortcut...
set "SHORTCUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Autograder4Canvas.lnk"
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = '%INSTALL_DIR%\Autograder4Canvas.bat'; $s.WorkingDirectory = '%INSTALL_DIR%'; if (Test-Path '%INSTALL_DIR%\icon.ico') { $s.IconLocation = '%INSTALL_DIR%\icon.ico' }; $s.Save()"

:: Create Desktop shortcut
echo   Creating Desktop shortcut...
set "DESKTOP_SHORTCUT=%USERPROFILE%\Desktop\Autograder4Canvas.lnk"
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%DESKTOP_SHORTCUT%'); $s.TargetPath = '%INSTALL_DIR%\Autograder4Canvas.bat'; $s.WorkingDirectory = '%INSTALL_DIR%'; if (Test-Path '%INSTALL_DIR%\icon.ico') { $s.IconLocation = '%INSTALL_DIR%\icon.ico' }; $s.Save()"

echo.
echo ========================================
echo    Installation Complete!
echo ========================================
echo.
echo Program installed to: %INSTALL_DIR%
echo.
echo You can now run Autograder4Canvas by:
echo   1. Clicking the Desktop shortcut
echo   2. Finding it in the Start Menu
echo.
echo To uninstall, delete:
echo   - %INSTALL_DIR%
echo   - The Desktop shortcut
echo   - The Start Menu shortcut
echo.

:END
pause
