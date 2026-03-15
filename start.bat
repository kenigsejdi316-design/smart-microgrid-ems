@echo off
setlocal
cd /d "%~dp0"

echo [1/4] Checking Python...
where py >nul 2>nul
if %errorlevel%==0 (
  set "PY_CMD=py -3"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python 3 was not found. Please install Python 3.10+ and run start.bat again.
    pause
    exit /b 1
  )
  set "PY_CMD=python"
)

echo [2/4] Preparing virtual environment...
if not exist ".venv\Scripts\python.exe" (
  %PY_CMD% -m venv .venv
  if errorlevel 1 (
    echo Failed to create virtual environment.
    pause
    exit /b 1
  )
)

call .venv\Scripts\activate.bat

echo [3/4] Installing dependencies...
python -m pip install --upgrade pip
if errorlevel 1 (
  echo Failed to upgrade pip.
  pause
  exit /b 1
)

python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Failed to install dependencies.
  pause
  exit /b 1
)

echo [4/4] Launching platform...
echo Open http://127.0.0.1:5000 in your browser.
python app.py
