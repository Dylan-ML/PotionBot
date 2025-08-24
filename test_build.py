#!/usr/bin/env python3
"""
Test script to verify all imports work correctly before building
Run this before building the executable to catch import issues early
"""

import sys
import os

def test_imports():
    """Test all required imports"""
    
    print("Testing imports for PotionBot...")
    print("=" * 50)
    
    # Test standard library imports
    try:
        import tkinter as tk
        import tkinter.messagebox
        from dataclasses import dataclass, field
        from typing import Dict
        import time
        import subprocess
        import json
        import threading
        print("✅ Standard library imports: OK")
    except ImportError as e:
        print(f"❌ Standard library import error: {e}")
        return False
    
    # Test GUI framework
    try:
        import customtkinter as ctk
        print("✅ CustomTkinter: OK")
    except ImportError as e:
        print(f"❌ CustomTkinter import error: {e}")
        return False
    
    # Test image processing
    try:
        from PIL import Image, ImageTk, ImageDraw
        print("✅ Pillow (PIL): OK")
    except ImportError as e:
        print(f"❌ Pillow import error: {e}")
        return False
    
    # Test Windows API
    try:
        import win32gui
        import win32con
        import win32api
        import win32process
        print("✅ pywin32: OK")
    except ImportError as e:
        print(f"❌ pywin32 import error: {e}")
        return False
    
    # Test optional dependencies
    try:
        import numpy as np
        print("✅ NumPy: OK")
    except ImportError as e:
        print(f"⚠️  NumPy not available: {e}")
    
    try:
        import cv2
        print("✅ OpenCV: OK")
    except ImportError as e:
        print(f"⚠️  OpenCV not available: {e}")
    
    try:
        import mss
        print("✅ MSS: OK")
    except ImportError as e:
        print(f"⚠️  MSS not available: {e}")
    
    try:
        import psutil
        print("✅ psutil: OK")
    except ImportError as e:
        print(f"⚠️  psutil not available: {e}")
    
    return True

def test_file_paths():
    """Test that required files exist"""
    
    print("\nTesting file paths...")
    print("=" * 50)
    
    required_files = [
        'src/gui.py',
        'src/window_detector.py',
        'src/object_recognition.py',
        'src/piece_recognition.py',
        'src/drop_piece.py',
        'src/settings_gui.py',
        'configuration/delays.json',
        'configuration/object_shapes.json',
        'configuration/piece_color_swatches.json',
        'icon.ico'
    ]
    
    missing_files = []
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✅ {file_path}: Found")
        else:
            print(f"❌ {file_path}: Missing")
            missing_files.append(file_path)
    
    if missing_files:
        print(f"\n❌ Missing files: {missing_files}")
        return False
    
    return True

def test_main_module():
    """Test that the main GUI module can be imported"""
    
    print("\nTesting main module import...")
    print("=" * 50)
    
    try:
        # Add src to path temporarily
        sys.path.insert(0, os.path.join(os.getcwd(), 'src'))
        
        # Import main GUI module
        import gui
        print("✅ Main GUI module: OK")
        
        # Check for main class
        if hasattr(gui, 'PotionGodApp'):
            print("✅ PotionGodApp class: Found")
        else:
            print("❌ PotionGodApp class: Not found")
            return False
            
        return True
        
    except ImportError as e:
        print(f"❌ Main module import error: {e}")
        return False
    finally:
        # Remove src from path
        if os.path.join(os.getcwd(), 'src') in sys.path:
            sys.path.remove(os.path.join(os.getcwd(), 'src'))

def main():
    """Run all tests"""
    
    print("PotionBot Pre-Build Test Suite")
    print("=" * 50)
    
    all_passed = True
    
    # Run tests
    if not test_imports():
        all_passed = False
    
    if not test_file_paths():
        all_passed = False
    
    if not test_main_module():
        all_passed = False
    
    # Results
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All tests passed! Ready to build executable.")
        print("Run 'build_spec.bat' or 'python build_exe.py' to build.")
    else:
        print("❌ Some tests failed. Please fix issues before building.")
        sys.exit(1)

if __name__ == "__main__":
    main()
