@echo off
setlocal
cd /d "%~dp0"
title DataGuard Launcher

echo ========================================
echo          DataGuard Launcher
echo ========================================
echo.
where py >nul 2>nul
if %errorlevel%==0 (
  set "PYTHON=py"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo ERROR: Python was not found.
    echo Install Python 3 from https://www.python.org/downloads/ and select "Add Python to PATH".
    echo Then run this file again.
    pause
    exit /b 1
  )
  set "PYTHON=python"
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating the project's virtual environment...
  %PYTHON% -m venv .venv
  if errorlevel 1 (
    echo ERROR: Could not create virtual environment.
    pause
    exit /b 1
  )
)

echo Installing/checking dependencies...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo ERROR: Dependency installation failed. Check your internet connection and try again.
  pause
  exit /b 1
)

echo.
echo DataGuard will start now. Keep this window open.
echo Open http://127.0.0.1:5000 in your browser.
echo Press Ctrl+C in this window to stop the server.
echo.
".venv\Scripts\python.exe" app.py
if errorlevel 1 (
  echo.
  echo DataGuard stopped with an error. Read the message above.
  pause
)
endlocal
