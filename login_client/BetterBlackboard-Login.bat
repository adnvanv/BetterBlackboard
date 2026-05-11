@echo off
REM Double-click launcher for the BetterBlackboard login GUI.

cd /d "%~dp0"

if exist ".venv\Scripts\pythonw.exe" goto :launch

echo First-time setup. This takes a couple of minutes...
echo.

REM Find a working Python interpreter.
set "PY="
py -3 --version >nul 2>nul
if not errorlevel 1 set "PY=py -3"

if not defined PY (
    python --version >nul 2>nul
    if not errorlevel 1 set "PY=python"
)

if not defined PY goto :nopython

echo Using Python: %PY%
%PY% -m venv .venv
if errorlevel 1 goto :venvfail

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
if errorlevel 1 goto :pipfail

pip install -r requirements.txt
if errorlevel 1 goto :pipfail

python -m playwright install chromium
if errorlevel 1 goto :pwfail

if not exist "config.json" (
    if exist "config.example.json" copy /Y "config.example.json" "config.json" >nul
    echo.
    echo Opening config.json for you to edit. Fill in server URL and token, save, close.
    notepad config.json
)

echo.
echo Setup complete. Launching GUI...

:launch
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0app.py"
exit /b 0

:nopython
echo.
echo ERROR: Python 3 is not installed or not on PATH.
echo Install Python 3.11+ from https://www.python.org/downloads/
echo During install, tick "Add Python to PATH".
echo.
pause
exit /b 1

:venvfail
echo.
echo ERROR: Failed to create virtual environment.
pause
exit /b 1

:pipfail
echo.
echo ERROR: pip install failed. Scroll up to see why.
pause
exit /b 1

:pwfail
echo.
echo ERROR: playwright install chromium failed. Scroll up to see why.
pause
exit /b 1
