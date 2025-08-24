@echo off
echo Building PotionBot using spec file...
echo ====================================

:: Check if virtual environment exists
if not exist ".venv\Scripts\activate.bat" (
    echo Error: Virtual environment not found at .venv
    echo Please run setup first or ensure the virtual environment exists.
    pause
    exit /b 1
)

:: Activate virtual environment
call .venv\Scripts\activate.bat

:: Clean previous builds
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

:: Build using the spec file
echo Building executable...
pyinstaller PotionBot.spec

:: Check if build was successful
if exist "dist\PotionBot.exe" (
    echo.
    echo Build successful! 🎉
    echo Executable created: %cd%\dist\PotionBot.exe
    
    :: Show file size
    for %%A in ("dist\PotionBot.exe") do echo File size: %%~zA bytes
    
    echo.
    echo You can now distribute PotionBot.exe as a standalone application.
) else (
    echo.
    echo Build failed! ❌
    echo Check the output above for errors.
)

pause
