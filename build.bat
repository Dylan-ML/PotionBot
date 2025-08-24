@echo off
echo PotionBot Complete Build Process
echo ================================

:: Check if virtual environment exists
if not exist ".venv\Scripts\activate.bat" (
    echo Error: Virtual environment not found at .venv
    echo Please run the following commands first:
    echo   python -m venv .venv
    echo   .venv\Scripts\activate
    echo   pip install -r requirements.txt
    pause
    exit /b 1
)

:: Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat

:: Test imports and dependencies first
echo.
echo Step 1: Testing dependencies and imports...
python test_build.py
if errorlevel 1 (
    echo.
    echo Build cancelled due to test failures.
    pause
    exit /b 1
)

:: Clean previous builds
echo.
echo Step 2: Cleaning previous builds...
if exist "build" (
    echo Removing build directory...
    rmdir /s /q "build"
)
if exist "dist" (
    echo Removing dist directory...
    rmdir /s /q "dist"
)

:: Update PyInstaller if needed
echo.
echo Step 3: Ensuring PyInstaller is up to date...
pip install --upgrade pyinstaller

:: Build the executable
echo.
echo Step 4: Building executable with PyInstaller...
echo This may take a few minutes...
pyinstaller PotionBot.spec

:: Check build results
echo.
echo Step 5: Checking build results...
if exist "dist\PotionBot.exe" (
    echo.
    echo ✅ Build successful! 🎉
    echo.
    echo Executable location: %cd%\dist\PotionBot.exe
    
    :: Show file information
    for %%A in ("dist\PotionBot.exe") do (
        echo File size: %%~zA bytes ^(~%%~nzA KB^)
        echo Modified: %%~tA
    )
    
    echo.
    echo 📦 Distribution Notes:
    echo - The executable is completely standalone
    echo - No Python installation required on target machines
    echo - All dependencies are included
    echo - Configuration files are embedded
    echo.
    echo 🚀 Ready for distribution!
    
    :: Ask if user wants to test the executable
    echo.
    set /p test_exe="Would you like to test the executable now? (y/n): "
    if /i "%test_exe%"=="y" (
        echo Testing executable...
        start "PotionBot Test" "dist\PotionBot.exe"
    )
    
) else (
    echo.
    echo ❌ Build failed!
    echo.
    echo Check the output above for error messages.
    echo Common issues:
    echo - Missing dependencies in requirements.txt
    echo - Import errors in source code
    echo - Missing data files
    echo.
    echo Try running 'python test_build.py' to diagnose issues.
)

echo.
echo Build process complete.
pause
