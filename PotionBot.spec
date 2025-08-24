# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for PotionBot
This file provides fine-grained control over the build process
"""

import os
from pathlib import Path

# Get the directory containing this spec file
SPEC_DIR = Path(SPECPATH)
PROJECT_ROOT = SPEC_DIR

# Define paths
SRC_DIR = PROJECT_ROOT / 'src'
CONFIG_DIR = PROJECT_ROOT / 'configuration'
ICON_FILE = PROJECT_ROOT / 'icon.ico'

block_cipher = None

# Data files to include
datas = [
    (str(CONFIG_DIR), 'configuration'),
    (str(ICON_FILE), '.'),
]

# Hidden imports (modules that PyInstaller might miss)
hiddenimports = [
    'customtkinter',
    'PIL',
    'PIL._tkinter_finder',
    'numpy',
    'cv2',
    'mss',
    'psutil',
    'win32api',
    'win32con',
    'win32gui',
    'win32process',
    'pywintypes',
]

# Analysis step
a = Analysis(
    [str(SRC_DIR / 'gui.py')],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',  # Exclude if not used
        'scipy',       # Exclude if not used
        'pandas',      # Exclude if not used
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Remove duplicate files
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Create the executable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PotionBot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Compress with UPX if available
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window for GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON_FILE),
    version='version_info.txt'  # Optional: version info file
)
