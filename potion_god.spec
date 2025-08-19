# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

# Get the current directory
current_dir = Path('.')

# Define paths
src_dir = current_dir / 'src'
assets_dir = current_dir / 'assets'
config_dir = current_dir / 'configuration'
tools_dir = current_dir / 'tools'

# Data files to include
datas = [
    (str(config_dir / 'delays.json'), 'configuration'),
    (str(config_dir / 'piece_color_swatches.json'), 'configuration'),
    (str(config_dir / 'object_shapes.json'), 'configuration'),
    (str(current_dir / 'icon.ico'), '.'),
]

# Hidden imports that PyInstaller might miss
hiddenimports = [
    'customtkinter',
    'PIL',
    'PIL._tkinter_finder',
    'numpy',
    'cv2',
    'mss',
    'pywin32',
    'psutil',
    'tkinter',
    'tkinter.messagebox',
    'win32gui',
    'win32process',
    'win32api',
    'win32con',
    # Local modules that are imported dynamically
    'object_recognition',
    'piece_recognition',
    'window_detector',
    'drop_piece',
    'settings_gui',
]

a = Analysis(
    [
        str(src_dir / 'gui.py'),
        str(src_dir / 'object_recognition.py'),
        str(src_dir / 'piece_recognition.py'),
        str(src_dir / 'window_detector.py'),
        str(src_dir / 'drop_piece.py'),
        str(src_dir / 'settings_gui.py'),
    ],
    pathex=[str(current_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PotionGod',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to True if you want to see console output for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(current_dir / 'icon.ico'),  # Application icon
)
