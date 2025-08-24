# Building PotionBot Executable

This document explains how to build PotionBot into a single executable file using PyInstaller.

## Prerequisites

1. **Python Environment**: Ensure you have a Python virtual environment set up with all dependencies installed:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **PyInstaller**: Should be installed automatically with requirements.txt, but you can install it manually:
   ```bash
   pip install pyinstaller>=6.0.0
   ```

## Build Methods

### Recommended: Complete Build Process

Use the comprehensive build script:

```batch
build.bat
```

This will:

- Test all dependencies and imports
- Activate the virtual environment
- Clean previous builds
- Update PyInstaller if needed
- Build using the PyInstaller spec file
- Validate build results
- Optionally test the executable

### Alternative Method 1: Quick Spec Build

For faster builds when everything is working:

```batch
build_spec.bat
```

### Alternative Method 2: Python Build Script

For cross-platform compatibility:

```bash
python build_exe.py
```

### Alternative Method 3: Manual PyInstaller Command

For advanced users who want full control:

```bash
# Activate virtual environment first
.venv\Scripts\activate

# Build with PyInstaller
pyinstaller PotionBot.spec
```

## Build Output

The executable will be created in the `dist` folder:

- **File**: `dist/PotionBot.exe`
- **Size**: Approximately 50-100 MB (includes Python runtime and all dependencies)
- **Dependencies**: None (fully standalone)

## Build Configuration

### Files Included in the Executable:

- All Python source code from `src/`
- Configuration files from `configuration/`
- Application icon (`icon.ico`)
- All required Python libraries and dependencies

### PyInstaller Spec File (`PotionBot.spec`)

The spec file provides fine-grained control over:

- Data files to include
- Hidden imports for proper module detection
- Executable properties (icon, version info, etc.)
- Optimization settings

### Version Information (`version_info.txt`)

Contains Windows executable properties:

- Version numbers
- Company information
- File description
- Copyright information

## Troubleshooting

### Common Issues:

1. **Missing Dependencies**: If the executable fails to run, check that all imports are included in the spec file's `hiddenimports` list.

2. **File Not Found Errors**: Ensure data files (configuration, icons) are properly included in the `datas` list in the spec file.

3. **Large File Size**: The executable includes the entire Python runtime. This is normal for PyInstaller builds.

4. **Antivirus False Positives**: Some antivirus software may flag PyInstaller executables. This is a known issue with packed executables.

### Debug Build:

To create a debug build with console output:

1. Edit `PotionBot.spec` and change `console=False` to `console=True`
2. Rebuild with `pyinstaller PotionBot.spec`

## Distribution

The resulting `PotionBot.exe` file is completely standalone and can be:

- Copied to any Windows computer without Python installed
- Distributed without any additional files (except user preferences)
- Run directly without installation

## File Structure After Build

```
PotionBot/
├── dist/
│   └── PotionBot.exe          # ← The final executable
├── build/                     # ← Temporary build files (can be deleted)
├── PotionBot.spec            # ← Build configuration
├── build_exe.py              # ← Python build script
├── build_spec.bat            # ← Windows build script
├── version_info.txt          # ← Windows version information
└── ...                       # ← Source files
```

## Performance Notes

- **Startup Time**: First run may be slightly slower as PyInstaller extracts files
- **Memory Usage**: Similar to running the Python script directly
- **File Size**: Larger than source code but includes everything needed to run

## Advanced Configuration

To customize the build further, edit `PotionBot.spec`:

- **Add more data files**: Extend the `datas` list
- **Include additional modules**: Add to `hiddenimports`
- **Change compression**: Modify `upx=True/False`
- **Debug options**: Set `debug=True` for verbose output

## Security Considerations

- The executable contains the source code (compiled to bytecode)
- Configuration files are embedded and can be extracted
- Consider obfuscation tools if source protection is needed

---

For more information about PyInstaller options, visit: https://pyinstaller.readthedocs.io/
