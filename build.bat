@echo off
echo Building PotionGod executable with PyInstaller...
echo.

REM Activate virtual environment if it exists
if exist ".venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
)

REM Run pre-build compatibility test
echo Running pre-build compatibility test...
python test_pyinstaller.py
if errorlevel 1 (
    echo.
    echo ❌ Pre-build test failed! Please fix the issues above.
    pause
    exit /b 1
)

REM Install PyInstaller if not already installed
echo.
echo Checking PyInstaller installation...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

REM Clean previous builds
echo Cleaning previous builds...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build

REM Build the executable
echo.
echo Building executable...
pyinstaller --clean potion_god.spec

REM Check if build was successful
if exist "dist\PotionGod.exe" (
    echo.
    echo ===================================
    echo Build completed successfully!
    echo Executable location: dist\PotionGod.exe
    echo File size: 
    for %%I in ("dist\PotionGod.exe") do echo %%~zI bytes
    echo ===================================
    echo.
    echo 💡 Test the executable to ensure all features work properly.
    pause
) else (
    echo.
    echo ===================================
    echo Build failed! Check the output above for errors.
    echo ===================================
    echo.
    pause
)
