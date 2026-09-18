@echo off
REM Builds LiteratureManager.exe on Windows.
REM Run this from the project folder (double-click it, or run in a terminal).

echo === Personal Literature Manager - build script ===
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found on PATH. Install Python 3.10+ from python.org first,
    echo making sure to check "Add python.exe to PATH" during install.
    pause
    exit /b 1
)

echo Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

echo.
echo Building the executable (this can take a few minutes the first time)...
REM Using "python -m PyInstaller" instead of the bare "pyinstaller" command:
REM pip sometimes installs console scripts into a Scripts folder that isn't
REM on PATH (you'll see a warning about this above if it happened). Calling
REM it as a module sidesteps that entirely, since Python always knows where
REM its own installed packages are.
python -m PyInstaller litmanager.spec --noconfirm

echo.
if exist "dist\LiteratureManager.exe" (
    echo Build succeeded: dist\LiteratureManager.exe
    echo You can now move that .exe anywhere and double-click it to run the app.
) else (
    echo Build did not produce an .exe -- scroll up for the error.
)
pause
