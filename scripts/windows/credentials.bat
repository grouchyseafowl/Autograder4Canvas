@echo off
:: ============================================================
:: Autograder4Canvas -- Credentials Configuration
:: ============================================================
:: This file is READ by run.bat -- do not double-click it.
::
:: To set up your credentials:
::   1. Right-click THIS file and choose "Open with Notepad"
::   2. Replace the placeholder Canvas URL with your school's URL
::      (e.g. https://myschool.instructure.com)
::   3. Replace "your_api_token_here" with your Canvas API token
::   4. Save and close Notepad
::   5. Double-click run.bat to start the autograder
::
:: How to find your Canvas URL:
::   It is the web address you use to log into Canvas.
::
:: How to get your API Token:
::   1. Log into Canvas
::   2. Click your profile picture (top right)
::   3. Click "Settings"
::   4. Scroll down to "Approved Integrations"
::   5. Click "+ New Access Token"
::   6. Give it a name (e.g. Autograder) and click Generate Token
::   7. Copy the token and paste it below (replace the placeholder)
::
:: IMPORTANT: Do not add spaces around the = signs.
:: ============================================================

:: run.bat passes /from-run when calling this file.
:: If that argument is absent, the user double-clicked it directly.
if /i "%~1"=="/from-run" goto :load_credentials

chcp 65001 >nul 2>&1
echo.
echo  ============================================================
echo   Autograder4Canvas - Setup Instructions
echo  ============================================================
echo.
echo  This file stores your Canvas credentials.
echo  Edit it in Notepad -- do not double-click to run it.
echo.
echo  To set up:
echo    1. Right-click credentials.bat
echo       and choose "Open with Notepad"
echo    2. Replace the placeholder Canvas URL with your school URL
echo    3. Replace your_api_token_here with your Canvas API token
echo    4. Save and close Notepad
echo    5. Double-click run.bat to start the autograder
echo.
pause
exit /b 0

:load_credentials
set CANVAS_BASE_URL=https://yourschool.instructure.com
set CANVAS_API_TOKEN=your_api_token_here
