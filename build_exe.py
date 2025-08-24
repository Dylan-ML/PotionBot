#!/usr/bin/env python3
"""
Build Script for PotionBot
Creates a single executable file using PyInstaller
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def clean_build_dirs():
    """Remove previous build artifacts"""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            print(f"Cleaning {dir_name}...")
            shutil.rmtree(dir_name)
    
    # Clean pycache in src directory
    src_pycache = os.path.join('src', '__pycache__')
    if os.path.exists(src_pycache):
        print(f"Cleaning {src_pycache}...")
        shutil.rmtree(src_pycache)

def build_executable():
    """Build the executable using PyInstaller"""
    
    # Ensure we're in the project root
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    print("Building PotionBot executable...")
    
    # Clean previous builds
    clean_build_dirs()
    
    # PyInstaller command
    cmd = [
        'pyinstaller',
        '--onefile',                    # Single file executable
        '--windowed',                   # No console window (GUI app)
        '--name=PotionBot',            # Executable name
        '--icon=icon.ico',             # Application icon
        '--add-data=configuration;configuration',  # Include configuration folder
        '--add-data=icon.ico;.',       # Include icon in root
        '--distpath=dist',             # Output directory
        '--workpath=build',            # Temporary build directory
        '--specpath=.',                # Spec file location
        '--noconfirm',                 # Overwrite without asking
        '--clean',                     # Clean cache before building
        'src/gui.py'                   # Main script
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("Build completed successfully!")
        print(f"Executable created: {os.path.abspath('dist/PotionBot.exe')}")
        
        # Show file size
        exe_path = 'dist/PotionBot.exe'
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"File size: {size_mb:.1f} MB")
            
    except subprocess.CalledProcessError as e:
        print(f"Build failed with error: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        return False
    
    return True

def main():
    """Main build function"""
    print("PotionBot Build Script")
    print("=" * 40)
    
    # Check if PyInstaller is installed
    try:
        subprocess.run(['pyinstaller', '--version'], 
                      check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("PyInstaller not found. Installing...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller'], 
                      check=True)
    
    # Build the executable
    if build_executable():
        print("\nBuild successful! 🎉")
        print("The executable is located in the 'dist' folder.")
        print("You can now distribute PotionBot.exe as a standalone application.")
    else:
        print("\nBuild failed! ❌")
        sys.exit(1)

if __name__ == "__main__":
    main()
