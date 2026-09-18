@echo off
REM Runs the app directly with Python (no .exe build needed).
REM Useful while you're still testing/tweaking things.

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found on PATH. Install Python 3.10+ from python.org first.
    pause
    exit /b 1
)

python -m pip install -r requirements.txt -q
python run.py
pause
