# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
