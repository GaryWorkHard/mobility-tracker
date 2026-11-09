@echo off
cd /d "%~dp0"
echo Installing Python packages...
py -m pip install -r requirements.txt
echo Installing the headless browser...
py -m playwright install chromium
echo.
echo Setup finished. You can close this window.
pause
