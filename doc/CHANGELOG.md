# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - 2025-08-24

### Added

- **PyInstaller Integration** - Complete build system for creating standalone executables
- **Single Executable Distribution** - Build PotionBot as a single .exe file with all dependencies included
- **Advanced Build Configuration** - Custom PyInstaller spec file with optimized settings
- **Build Automation** - Comprehensive build script with testing and validation
- **Pre-Build Testing** - Automated dependency and import validation before building
- **Windows Executable Properties** - Professional version information and application icon
- **Build Documentation** - Complete build instructions and troubleshooting guide

### Enhanced

- **Distribution Options** - Users can now choose between Python source or standalone executable
- **Resource Path Handling** - Improved resource loading for both development and bundled modes
- **Requirements Management** - Updated PyInstaller to latest version (6.0.0+)
- **Documentation** - Updated README with executable download and build instructions
- **User Experience** - Simplified installation with standalone executable option

### Technical

- **PotionBot.spec** - Advanced PyInstaller specification with hidden imports and data files
- **version_info.txt** - Windows version resource file with application metadata
- **build.bat** - Unified build script with testing, cleaning, and validation
- **test_build.py** - Comprehensive pre-build testing for dependencies and file paths
- **build_exe.py** - Cross-platform Python build script with error handling
- **Resource Bundling** - Automatic inclusion of configuration files, icons, and assets
- **UPX Compression** - Optimized executable size with UPX compression
- **Build Validation** - Post-build verification and file size reporting

### Distribution

- **Standalone Executable** - No Python installation required on target machines
- **Embedded Dependencies** - All libraries (CustomTkinter, PIL, pywin32, etc.) included
- **Configuration Embedding** - JSON configuration files bundled within executable
- **Professional Packaging** - Windows executable with proper icon and version information

## [1.2.0] - 2025-08-19

### Fixed

- **Escape Key Responsiveness** - Significantly improved escape key handling during auto-drop operations
- **Auto-Drop Interruption** - Auto-drop can now be interrupted immediately at multiple points in the cycle
- **Long Operation Interruption** - Piece detection, validation, and drop operations can be stopped mid-process
- **User Feedback** - Better distinction between escape interruption and actual errors in log messages

### Enhanced

- **Drop Controller** - Added comprehensive escape key checking throughout the drop cycle
- **Piece Detection** - Escape key checking added to piece detection retry loops
- **Validation Process** - Validation attempts can now be interrupted with escape key
- **Window Detection** - Window detection retries respect escape key interruption
- **Main Loop** - Multiple escape check points added to the auto-drop main loop

### Technical

- **\_check_escape_pressed()** - New centralized function for reliable escape key detection
- **Enhanced Error Handling** - Better differentiation between user interruption and system errors
- **Improved Responsiveness** - Escape key now checked at critical points instead of only during sleep periods
- **Backward Compatibility** - All existing functionality preserved with enhanced escape handling

## [1.1.0] - 2025-08-19

### Added

- **Advanced Settings Panel** - New settings GUI with comprehensive timing configuration
- **Delays Configuration Editor** - Interactive editor for all timing delays in delays.json
- **Settings Management** - Load, view, edit, and save timing configurations
- **Input Validation** - Comprehensive validation for timing parameters with error checking
- **Reset to Defaults** - One-click restore of default timing values
- **Categorized Settings** - Organized timing parameters by function (Mouse, Validation, etc.)
- **Status Feedback** - Real-time status messages with color-coded feedback
- **File Management** - Browse and load custom delay configurations from any location

### Enhanced

- **Settings GUI** - Replaced placeholder advanced settings with fully functional delays configuration
- **User Experience** - Professional interface matching main application theme
- **Documentation** - Updated README with comprehensive settings usage guide
- **Error Handling** - Robust error handling for configuration file operations

### Technical

- **DelaysEditorWindow Class** - New modal window for detailed timing parameter editing
- **Configuration Validation** - Input sanitization and range checking for timing values
- **JSON Integration** - Seamless integration with existing delays.json configuration system
- **Type Safety** - Proper type conversion and null value handling

## [1.0.0] - 2025-08-19

### Added

- Initial release of the Potion God tool.
