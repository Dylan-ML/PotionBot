# 🧪 Potion God

## 📋 Overview

Potion God provides an intuitive interface for managing game automation features including:

- **Window Detection** - Locate and capture game windows
- **Asset Recognition** - Detect game board elements
- **Game Analysis** - Analyze current game state
- **Bot Control** - Start/stop automation processes

## ✨ Features

- **Real-time Logging** - Activity log with colored status messages and timestamps
- **Modular Controls** - Organized sections for different automation features
- **Status Indicators** - Visual feedback for all system states
- **Responsive Layout** - Adaptive UI that scales with window size

## 🚀 Quick Start

### Prerequisites

- Python 3.7 or higher
- Windows OS (currently optimized for Windows)

### Installation

1. **Clone or download** this repository
2. **Navigate** to the project directory:

   ```powershell
   cd PotionGod
   ```

3. **Create a virtual environment** (recommended):

   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   ```

4. **Install dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```

### Running the Application

**Option 1: Using Python directly**

```powershell
python src\gui.py
```

**Option 2: Using the batch file**

```powershell
run.bat
```

**Option 3: Using the script from scripts folder**

```powershell
scripts\run_gui.bat
```

## 🎮 Usage

### Getting Started

1. **Launch** the application using one of the methods above
2. **Find Game Window** - Click to detect the target game window
3. **Capture Screen** - Take a screenshot for analysis
4. **Use Controls** - Access various automation features from the sidebar

### Interface Overview

#### Sidebar Controls

- **🪟 Window Detection** - Find and capture game windows
- **🎯 Asset Recognition** - Detect game board elements
- **🔍 Game Analysis** - Analyze current game state
- **🤖 Bot Control** - Start/stop automation

#### Main Panel

- **📋 Activity Log** - Real-time status updates and system messages
- **Clear Button** - Reset the activity log

### Status Messages

The activity log uses color-coded messages:

- **ℹ️ Info** - General information (Gray)
- **✅ Success** - Successful operations (Green)
- **⚠️ Warning** - Warnings and alerts (Orange)
- **❌ Error** - Errors and failures (Red)

## � Project Structure

```
PotionGod/
├── src/                 # Source code
│   └── gui.py          # Main GUI application
├── docs/               # Documentation
│   ├── README.md       # This file
│   ├── CHANGELOG.md    # Version history
│   ├── LICENSE         # License information
│   └── game docs/      # Game-related documentation
├── assets/             # Game assets and images
│   ├── board/          # Board-related images
│   └── ingredients/    # Ingredient token images
├── scripts/            # Build and utility scripts
│   └── run_gui.bat     # Application launcher
├── .venv/              # Virtual environment (not in git)
├── .gitignore          # Git ignore rules
├── requirements.txt    # Python dependencies
├── run.bat             # Quick launcher
└── VERSION             # Version identifier
```

## �🛠️ Development

### Customization

#### Colors

Modify the `COLORS` dictionary in `src/gui.py` to change the theme:

```python
COLORS = {
    "primary": "#1f538d",      # Main button color
    "secondary": "#14375e",    # Secondary elements
    "success": "#2FB36D",      # Success messages
    "error": "#E34F4F",        # Error messages
    "warning": "#F0A202",      # Warning messages
    # ... more colors
}
```

#### Fonts

Update the `FONTS` dictionary to change typography:

```python
FONTS = {
    "title": ("Segoe UI", 20, "bold"),
    "heading": ("Segoe UI", 14, "bold"),
    "body": ("Segoe UI", 11),
    # ... more font styles
}
```

## 📦 Dependencies

- **customtkinter** - Modern UI framework
- **tkinter** - Base GUI toolkit (included with Python)
- **pillow** - Image processing capabilities

## 🔧 Configuration

The application uses default settings optimized for most systems:

- **Window Size**: 1200x950 pixels
- **Theme**: Dark mode with blue accents
- **Font**: Segoe UI (Windows) with Cascadia Code for logs

## 🐛 Troubleshooting

### Common Issues

**"Module not found" errors**

- Ensure you've activated the virtual environment
- Install dependencies: `pip install -r requirements.txt`

**GUI not appearing**

- Check that you're running on a system with GUI support
- Ensure Python tkinter is properly installed

## 📄 License

This project is for educational and personal use. Please respect game terms of service and use responsibly.

---

**Made with ❤️. -DL**
