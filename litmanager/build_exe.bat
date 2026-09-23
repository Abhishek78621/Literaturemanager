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
python -m pip install pyinstaller pyarmor

echo.
echo Obfuscating code with PyArmor...
REM Generate obfuscated code for the 'app' module
pyarmor gen -O obfuscated app
if not exist "obfuscated\app" (
    echo PyArmor obfuscation failed.
    pause
    exit /b 1
)

REM Swap the original app folder with the obfuscated one for the build
move app app_original >nul
move obfuscated\app app >nul

echo.
echo Building the executable (this can take a few minutes the first time)...
python -m PyInstaller litmanager.spec --noconfirm

REM Restore the original source code
rmdir /S /Q app
move app_original app >nul
rmdir /S /Q obfuscated


echo.
if exist "dist\LiteratureManager.exe" (
    echo Build succeeded: dist\LiteratureManager.exe
    echo You can now move that .exe anywhere and double-click it to run the app.
) else (
    echo Build did not produce an .exe -- scroll up for the error.
)
pause
