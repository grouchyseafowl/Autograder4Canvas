@echo off
setlocal enabledelayedexpansion

echo ========================================
echo    Autograder4Canvas Installer
echo ========================================
echo.

:: -------------------------------------------------------
:: Check for Python 3
:: -------------------------------------------------------
set "PYTHON_CMD="
where python >nul 2>&1
if %ERRORLEVEL% == 0 (
    for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
    if "!PY_VER:~0,1!"=="3" set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
    where python3 >nul 2>&1
    if %ERRORLEVEL% == 0 (
        set "PYTHON_CMD=python3"
        for /f "tokens=2 delims= " %%v in ('python3 --version 2^>^&1') do set "PY_VER=%%v"
    )
)

if not defined PYTHON_CMD (
    echo.
    echo  ================================================
    echo   Python is needed but isn't installed yet
    echo  ================================================
    echo.
    echo  Autograder4Canvas runs on Python - a free tool
    echo  used by millions of people. We can download and
    echo  install it for you automatically right now!
    echo.
    set /p AUTO_INSTALL="  Install Python automatically? (Y/N): "
    echo.
    if /i "!AUTO_INSTALL!"=="Y" (
        echo  Step 1 of 2: Downloading Python 3.12...
        echo  ^(This usually takes 1-2 minutes^)
        echo.

        :: Write the Python installer script next to INSTALL.bat
        set "PY_PS1=%~dp0install_python.ps1"
        >  "!PY_PS1!" echo $arch = if ([Environment]::Is64BitOperatingSystem) { 'amd64' } else { '' }
        >> "!PY_PS1!" echo $ver  = '3.12.8'
        >> "!PY_PS1!" echo $file = "python-$ver" + $(if ($arch) { "-$arch" } else { "" }) + ".exe"
        >> "!PY_PS1!" echo $url  = "https://www.python.org/ftp/python/$ver/$file"
        >> "!PY_PS1!" echo $out  = Join-Path $env:TEMP 'python_installer.exe'
        >> "!PY_PS1!" echo try {
        >> "!PY_PS1!" echo     Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing
        >> "!PY_PS1!" echo     Write-Host "  Step 2 of 2: Installing Python (please wait)..."
        >> "!PY_PS1!" echo     $p = Start-Process $out -ArgumentList '/quiet InstallAllUsers=0 PrependPath=1 Include_test=0 SimpleInstall=1' -Wait -PassThru
        >> "!PY_PS1!" echo     Remove-Item $out -Force -ErrorAction SilentlyContinue
        >> "!PY_PS1!" echo     if ($p.ExitCode -ne 0) { Write-Host "  Installer exited with code $($p.ExitCode)"; exit 1 }
        >> "!PY_PS1!" echo     Write-Host "  Python installed!"
        >> "!PY_PS1!" echo     exit 0
        >> "!PY_PS1!" echo } catch {
        >> "!PY_PS1!" echo     Write-Host "  Download failed: $_"
        >> "!PY_PS1!" echo     exit 1
        >> "!PY_PS1!" echo }

        powershell -ExecutionPolicy Bypass -File "!PY_PS1!"
        set "PY_RESULT=!ERRORLEVEL!"
        del "!PY_PS1!" >nul 2>&1

        if !PY_RESULT! == 0 (
            echo.
            echo  Done! Adding Python to this session...
            :: Add the user Python install location to PATH for the current session
            :: so we don't need to restart the installer
            for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
                set "PATH=%%d;%%d\Scripts;!PATH!"
            )
            :: Re-detect Python
            where python >nul 2>&1
            if !ERRORLEVEL! == 0 (
                for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
                set "PYTHON_CMD=python"
            )
        ) else (
            echo.
            echo  Automatic installation did not complete.
            echo  See the manual steps below.
        )
    )
)

:: If Python still not found after auto-install attempt, show manual guide
if not defined PYTHON_CMD (
    echo.
    echo  ================================================
    echo   Manual Python installation - follow these steps
    echo  ================================================
    echo.
    echo   1. Open your web browser and go to:
    echo        https://www.python.org/downloads/
    echo.
    echo   2. Click the big yellow "Download Python" button
    echo.
    echo   3. Run the file that downloads
    echo.
    echo   4. IMPORTANT - on the first installer screen:
    echo        Check the box "Add Python to PATH"
    echo        ^(it's at the bottom of the window^)
    echo.
    echo   5. Click "Install Now" and wait for it to finish
    echo.
    echo   6. Come back and run INSTALL.bat again
    echo.
    set /p OPEN_BROWSER="  Open python.org in your browser now? (Y/N): "
    if /i "!OPEN_BROWSER!"=="Y" start https://www.python.org/downloads/
    echo.
    goto :END
)

echo  Python ready: !PYTHON_CMD! ^(!PY_VER!^)
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

:: Write xcopy exclusion list to INSTALL_DIR (no spaces in path, unlike %TEMP%)
set "XCOPY_EXCL=%INSTALL_DIR%\excl.tmp"
> "%XCOPY_EXCL%" echo __pycache__
>> "%XCOPY_EXCL%" echo .pyc

:: Copy v2 files
if exist "%SOURCE_DIR%src\config" (
    echo   Copying v2 config files...
    xcopy /E /I /Y /EXCLUDE:"%XCOPY_EXCL%" "%SOURCE_DIR%src\config" "%INSTALL_DIR%\config" >nul
)
if exist "%SOURCE_DIR%src\modules" (
    echo   Copying v2 modules...
    xcopy /E /I /Y /EXCLUDE:"%XCOPY_EXCL%" "%SOURCE_DIR%src\modules" "%INSTALL_DIR%\modules" >nul
)
if exist "%SOURCE_DIR%src\docs" (
    echo   Copying documentation...
    xcopy /E /I /Y "%SOURCE_DIR%src\docs" "%INSTALL_DIR%\docs" >nul
)
del "%XCOPY_EXCL%" >nul 2>&1

:: Copy icon if it exists
if exist "%SOURCE_DIR%icon.ico" copy "%SOURCE_DIR%icon.ico" "%INSTALL_DIR%\" >nul

:: Install Python dependencies
echo   Installing required Python packages...
%PYTHON_CMD% -m pip install --quiet -r "%INSTALL_DIR%\requirements.txt"
if %ERRORLEVEL% neq 0 (
    echo   Warning: Some packages may not have installed correctly.
    echo   The program may still work, or you can run:
    echo     pip install -r "%INSTALL_DIR%\requirements.txt"
    echo   manually to fix this.
)

:: Create launcher batch file
echo   Creating launcher...
(
echo @echo off
echo setlocal enabledelayedexpansion
echo cd /d "%INSTALL_DIR%"
echo.
echo :: Find Python - check PATH first, then common install locations
echo set "PYTHON_CMD="
echo where python >nul 2>&1 && set "PYTHON_CMD=python"
echo if not defined PYTHON_CMD where python3 >nul 2>&1 && set "PYTHON_CMD=python3"
echo.
echo :: Also check standard user-install locations in case PATH wasn't updated
echo if not defined PYTHON_CMD ^(
echo     for /d %%%%d in ^("%LOCALAPPDATA%\Programs\Python\Python3*"^) do ^(
echo         if exist "%%%%d\python.exe" set "PYTHON_CMD=%%%%d\python.exe"
echo     ^)
echo ^)
echo.
echo if not defined PYTHON_CMD ^(
echo     echo.
echo     echo Python is not installed or could not be found.
echo     echo Please install it from https://www.python.org/downloads/
echo     echo Make sure to check "Add Python to PATH" during installation.
echo     echo.
echo     pause
echo     exit /b 1
echo ^)
echo.
echo %%PYTHON_CMD%% run_autograder.py %%*
echo pause
) > "%INSTALL_DIR%\Autograder4Canvas.bat"

:: Copy uninstaller into the install directory so it's always accessible
echo   Installing uninstaller...
copy "%SOURCE_DIR%UNINSTALL.bat" "%INSTALL_DIR%\UNINSTALL.bat" >nul

:: Create shortcuts via a temporary PowerShell script
:: Paths are resolved inside PowerShell (handles OneDrive Desktop, etc.)
echo   Creating shortcuts...
set "PS_TMP=%INSTALL_DIR%\shortcuts.ps1"

::  Write the PS1 line-by-line with >> to avoid block-parser paren issues
>  "%PS_TMP%" echo $installDir    = '%INSTALL_DIR%'
>> "%PS_TMP%" echo $batPath       = Join-Path $installDir 'Autograder4Canvas.bat'
>> "%PS_TMP%" echo $uninstallPath = Join-Path $installDir 'UNINSTALL.bat'
>> "%PS_TMP%" echo $icoPath       = Join-Path $installDir 'icon.ico'
>> "%PS_TMP%" echo $ws            = New-Object -ComObject WScript.Shell
>> "%PS_TMP%" echo(
>> "%PS_TMP%" echo # Resolve real Desktop and Start Menu paths (works with OneDrive redirection)
>> "%PS_TMP%" echo $desktop = [Environment]::GetFolderPath('Desktop')
>> "%PS_TMP%" echo $menuDir = [Environment]::GetFolderPath('Programs')
>> "%PS_TMP%" echo if (-not (Test-Path $menuDir)) { New-Item -Force -ItemType Directory $menuDir ^| Out-Null }
>> "%PS_TMP%" echo(
>> "%PS_TMP%" echo $s = $ws.CreateShortcut((Join-Path $desktop 'Autograder4Canvas.lnk'))
>> "%PS_TMP%" echo $s.TargetPath       = $batPath
>> "%PS_TMP%" echo $s.WorkingDirectory = $installDir
>> "%PS_TMP%" echo if (Test-Path $icoPath) { $s.IconLocation = $icoPath }
>> "%PS_TMP%" echo $s.Save()
>> "%PS_TMP%" echo(
>> "%PS_TMP%" echo $s = $ws.CreateShortcut((Join-Path $menuDir 'Autograder4Canvas.lnk'))
>> "%PS_TMP%" echo $s.TargetPath       = $batPath
>> "%PS_TMP%" echo $s.WorkingDirectory = $installDir
>> "%PS_TMP%" echo if (Test-Path $icoPath) { $s.IconLocation = $icoPath }
>> "%PS_TMP%" echo $s.Save()
>> "%PS_TMP%" echo(
>> "%PS_TMP%" echo $s = $ws.CreateShortcut((Join-Path $menuDir 'Uninstall Autograder4Canvas.lnk'))
>> "%PS_TMP%" echo $s.TargetPath       = $uninstallPath
>> "%PS_TMP%" echo $s.WorkingDirectory = $installDir
>> "%PS_TMP%" echo $s.Description      = 'Uninstall Autograder4Canvas'
>> "%PS_TMP%" echo $s.Save()

powershell -ExecutionPolicy Bypass -File "%PS_TMP%"
if %ERRORLEVEL% neq 0 (
    echo   Warning: Shortcuts could not be created automatically.
    echo   You can still run the program by opening:
    echo     %INSTALL_DIR%\Autograder4Canvas.bat
)
del "%PS_TMP%" >nul 2>&1

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
echo To uninstall, run UNINSTALL.bat from the original zip,
echo or from the installed folder at:
echo   %INSTALL_DIR%\UNINSTALL.bat
echo.

:END
pause
