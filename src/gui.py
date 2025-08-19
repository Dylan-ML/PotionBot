# gui.py
"""
Potion God - Control Panel

A modern, professional GUI application for controlling and monitoring the Potion God bot.
Provides a comprehensive interface for window detection, asset recognition, game analysis,
and bot control operations with real-time status monitoring and activity logging.

Features:
- Dark theme with modern styling
- Window detection and screen capture capabilities
- Asset recognition controls
- Game analysis functionality
- Bot control with start/stop operations
- Real-time activity logging with color-coded messages
- Responsive layout with sidebar controls and main content area
- Advanced settings panel with timing configuration

Version: 1.1.0
"""

import customtkinter as ctk
from tkinter import messagebox
import tkinter as tk
from dataclasses import dataclass, field
from typing import Dict
import time
import subprocess
import os
import sys

def get_resource_path(relative_path: str) -> str:
    """
    Get absolute path to resource, works for development and PyInstaller bundle.
    
    Args:
        relative_path: Path relative to the project root (e.g., "configuration/delays.json")
    
    Returns:
        Absolute path to the resource
    """
    if getattr(sys, 'frozen', False):
        # Running as bundled executable
        # PyInstaller stores data files relative to the executable
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        # Running in development mode
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    return os.path.join(base_path, relative_path)


def set_window_icon(window):
    """
    Set the application icon for a window.
    Works for both development and PyInstaller bundle.
    
    Args:
        window: The tkinter/customtkinter window to set the icon for
    """
    try:
        icon_path = get_resource_path("icon.ico")
        if os.path.exists(icon_path):
            window.iconbitmap(icon_path)
    except Exception as e:
        # Icon loading failed, but don't crash the app
        print(f"Warning: Could not load icon: {e}")

# Import the window detector for game window detection
try:
    from window_detector import GameWindowDetector
    WINDOW_DETECTOR_AVAILABLE = True
except ImportError as e:
    print(f"Window detector not available: {e}")
    WINDOW_DETECTOR_AVAILABLE = False
    GameWindowDetector = None

# Import the object recognition engine (will be imported lazily)
OBJECT_RECOGNITION_AVAILABLE = False
ObjectRecognizer = None

# Import the piece recognition engine
try:
    from piece_recognition import PieceRecognizer
    PIECE_RECOGNITION_AVAILABLE = True
except ImportError as e:
    print(f"Piece recognition not available: {e}")
    PIECE_RECOGNITION_AVAILABLE = False
    PieceRecognizer = None


# Set appearance mode and color theme for the application
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Application configuration constants
APP_TITLE = "Potion God - Control Panel"
APP_SIZE = "1200x950"

# Modern color scheme for consistent UI theming
COLORS = {
    "primary": "#1f538d",      # Primary brand color for main actions
    "secondary": "#14375e",    # Secondary color for supporting elements
    "success": "#2FB36D",      # Success state indicator color
    "error": "#E34F4F",        # Error state indicator color
    "warning": "#F0A202",      # Warning state indicator color
    "accent": "#00D4FF",       # Accent color for hover states and highlights
    "bg_dark": "#212121",      # Dark background for main content areas
    "bg_light": "#2B2B2B",     # Lighter background for panels and sections
    "text_primary": "#FFFFFF", # Primary text color for high contrast
    "text_secondary": "#B0B0B0" # Secondary text color for less important content
}

# Font definitions for consistent typography throughout the application
FONTS = {
    "title": ("Segoe UI", 20, "bold"),     # Main page titles and headers
    "heading": ("Segoe UI", 14, "bold"),   # Section headings and labels
    "body": ("Segoe UI", 11),              # Regular body text and descriptions
    "mono": ("Cascadia Code", 10),         # Monospace font for logs and code
    "button": ("Segoe UI", 11, "bold")     # Button text for better readability
}


@dataclass
class BotState:
    """
    Tracks the current state of the bot and its various subsystems.
    
    This dataclass maintains the operational status of different components
    to ensure proper UI state management and feature availability.
    
    Attributes:
        window_detected (bool): Whether the game window has been successfully located
        board_detected (bool): Whether the game board has been detected within the window
        capture_active (bool): Whether screen capture is currently in progress
        features (Dict[str, bool]): Dictionary tracking availability of major features:
            - asset_recognition: Board detection and game state analysis
            - analysis: Current pair analysis and move suggestion
            - piece_recognition: Next piece color identification
    """
    window_detected: bool = False
    board_detected: bool = False
    capture_active: bool = False
    features: Dict[str, bool] = field(default_factory=lambda: {
        "asset_recognition": False,
        "piece_recognition": False
    })


class PotionGodApp:
    """
    Main application class for the Potion God Control Panel.
    
    Provides a comprehensive GUI interface for managing bot operations including
    window detection, screen capture, asset recognition, game analysis, and
    automated bot control. Features a modern dark theme with responsive layout.
    
    The application follows a modular design with separate sections for different
    functionality areas, centralized state management, and comprehensive logging.
    """
    
    def __init__(self) -> None:
        """
        Initialize the application with default state and UI components.
        
        Sets up the main window, configures the layout, initializes all UI sections,
        and starts the status monitoring system. The application starts with most
        features disabled until proper initialization is completed.
        """
        # Initialize application state tracking
        self.state = BotState()
        
        # Track if GUI is still available for logging
        self._gui_available = True
        
        # Initialize window detector placeholder (will be set up after UI creation)
        self.window_detector = None
        
        # Initialize object recognizer placeholder (will be set up after window detector)
        self.object_recognizer = None
        
        # Initialize piece recognizer placeholder (will be set up after window detector)
        self.piece_recognizer = None
        
        # Create main window with modern styling
        self.root = ctk.CTk()
        self.root.title(APP_TITLE)
        self.root.geometry(APP_SIZE)
        self.root.minsize(1100, 950)  # Ensure minimum usable size
        
        # Set application icon
        set_window_icon(self.root)
        
        # Center the window on screen for optimal user experience
        self._center_window()
        
        # Configure main window grid for responsive layout
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Initialize all UI components in proper order
        self._create_main_layout()
        self._schedule_status_refresh()
        
        # Set up window close handler for proper cleanup
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)
        
        # Initialize window detector after UI is created
        self._initialize_window_detector()
        
        # Display welcome message to indicate successful initialization
        self.log("🚀 GUI ready. Use the controls on the left to exercise placeholders.", "SUCCESS")
        
        # Add helpful usage information
        if self.window_detector is not None:
            self.log("🎮 Ready for game window detection. Click 'Find Game Window' to start.", "INFO")
        else:
            self.log("🔧 Running in development mode with simulated window detection.", "INFO")

    def _center_window(self) -> None:
        """
        Center the application window on the screen with optimal positioning.
        
        Calculates the screen center position and applies visual balance adjustments
        to ensure the window appears well-positioned. Includes safety margins to
        prevent the window from extending beyond screen boundaries on smaller displays.
        
        The positioning algorithm accounts for taskbars and other screen elements
        by applying appropriate margins and slight upward adjustment for better
        visual balance.
        """
        # Update the window to ensure accurate dimension calculations
        self.root.update_idletasks()
        
        # Parse application size configuration to get actual window dimensions
        width_str, height_str = APP_SIZE.split('x')
        window_width = int(width_str)
        window_height = int(height_str)
        
        # Get current screen dimensions for positioning calculations
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # Calculate mathematically centered position
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        # Apply safety margins to ensure complete visibility on all screen sizes
        margin = 50
        x = max(margin, min(x, screen_width - window_width - margin))
        y = max(margin, min(y, screen_height - window_height - margin))
        
        # Apply upward adjustment for improved visual balance and taskbar clearance
        y = max(margin, y - 80)
        
        # Apply the calculated position to the window
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")

    # ---------- Modern UI Layout ----------
    
    def _create_main_layout(self) -> None:
        """
        Create the main application layout with header, sidebar, and content areas.
        
        Establishes the primary layout structure using a grid-based approach:
        - Header: Application title and global controls (row 0, spans both columns)
        - Sidebar: Feature controls and settings (row 1, column 0)
        - Main Content: Activity logs and status information (row 1, column 1)
        
        The layout is designed to be responsive and maintains proper proportions
        across different window sizes.
        """
        # Create main container frame that fills the entire window
        main_frame = ctk.CTkFrame(self.root, corner_radius=0)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Initialize layout sections in proper order
        self._create_header(main_frame)
        self._create_sidebar(main_frame)
        self._create_main_content(main_frame)

    def _create_header(self, parent) -> None:
        """
        Create the application header with title and global controls.
        
        The header provides:
        - Application branding with title and icon
        - Quick access to global settings
        - Consistent visual identity across the application
        
        Args:
            parent: Parent widget to contain the header
        """
        # Create header frame with primary brand color
        header = ctk.CTkFrame(parent, height=70, corner_radius=0, fg_color=COLORS["primary"])
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.grid_propagate(False)
        header.columnconfigure(1, weight=1)
        
        # Application title with branding emoji for visual appeal
        title_label = ctk.CTkLabel(
            header, 
            text="🧪 Potion God Control Panel",
            font=FONTS["title"],
            text_color=COLORS["text_primary"]
        )
        title_label.grid(row=0, column=0, padx=20, pady=20, sticky="w")
        
        # Settings button for accessing global configuration options
        settings_btn = ctk.CTkButton(
            header,
            text="⚙️ Settings",
            width=100,
            height=32,
            font=FONTS["body"],
            command=self.on_open_settings,
            fg_color=COLORS["secondary"],
            hover_color=COLORS["accent"]
        )
        settings_btn.grid(row=0, column=1, padx=20, pady=20, sticky="e")

    def _create_sidebar(self, parent) -> None:
        """
        Create the sidebar containing all primary control sections.
        
        The sidebar is organized into logical sections for different functional areas:
        - Window Detection: Game window location and screen capture
        - Asset Recognition: Game board detection and element identification
        - Analysis: Current game state analysis and move suggestions
        - Bot Control: Automated bot start/stop and configuration
        
        Uses a scrollable frame to accommodate all controls while maintaining
        a fixed width for consistent layout.
        
        Args:
            parent: Parent widget to contain the sidebar
        """
        # Create scrollable sidebar with fixed width for consistent layout
        sidebar = ctk.CTkScrollableFrame(
            parent, 
            width=360,
            corner_radius=0,
            fg_color=COLORS["bg_light"]
        )
        sidebar.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        
        # Add top spacing for visual breathing room
        top_spacer = ctk.CTkFrame(sidebar, height=10, fg_color="transparent")
        top_spacer.pack(fill="x")
        
        # Create functional control sections in logical order
        self._create_window_controls(sidebar)
        self._create_asset_controls(sidebar)
        self._create_analysis_controls(sidebar)
        self._create_tools_controls(sidebar)
        
        # Add bottom spacing to prevent controls from touching the bottom
        bottom_spacer = ctk.CTkFrame(sidebar, height=10, fg_color="transparent")
        bottom_spacer.pack(fill="x")

    def _create_window_controls(self, parent) -> None:
        """
        Create window detection and screen capture controls.
        
        This section provides the fundamental functionality for:
        - Locating and connecting to the game window
        - Capturing screen content for analysis
        - Managing window state and capture operations
        
        Window detection must be successful before other features become available.
        
        Args:
            parent: Parent widget to contain the window controls
        """
        section = self._create_section(parent, "🪟 Window Detection")
        
        # Primary window detection button - first step in bot setup
        self.btn_find_window = ctk.CTkButton(
            section,
            text="Find Game Window",
            height=32,
            font=FONTS["button"],
            command=self.on_find_window,
            fg_color=COLORS["primary"],
            hover_color=COLORS["accent"]
        )
        self.btn_find_window.pack(fill="x", pady=(0, 10))
        
        # Add right-click binding for overlay toggle
        self.btn_find_window.bind("<Button-3>", self._on_find_window_right_click)
        
        # Screen capture functionality for game state analysis
        self.btn_capture = ctk.CTkButton(
            section,
            text="📸 Capture Screen",
            height=32,
            font=FONTS["button"],
            command=self.on_capture_screen,
            fg_color=COLORS["secondary"],
            hover_color=COLORS["accent"]
        )
        self.btn_capture.pack(fill="x", pady=0)

    def _create_asset_controls(self, parent) -> None:
        """
        Create object recognition and game element detection controls.
        
        This section handles:
        - Object recognition using predefined shape templates
        - Game element identification and analysis  
        - Visual overlay for debugging shape detection
        
        These controls become available after successful window detection
        and provide detailed analysis of game elements and their properties.
        
        Args:
            parent: Parent widget to contain the asset controls
        """
        section = self._create_section(parent, "🎯 Object Recognition")
        
        # Object recognition - detects and analyzes game elements using shape matching
        self.btn_detect_board = ctk.CTkButton(
            section,
            text="🔍 Run Object Recognition",
            height=32,
            font=FONTS["button"],
            command=self.on_detect_board,
            state="disabled",  # Enabled after window detection
            fg_color=COLORS["primary"],
            hover_color=COLORS["accent"]
        )
        self.btn_detect_board.pack(fill="x", pady=0)
        
        # Add right-click binding for overlay toggle
        self.btn_detect_board.bind("<Button-3>", self._on_detect_board_right_click)

    def _create_analysis_controls(self, parent) -> None:
        """
        Create piece recognition controls.
        
        This section provides:
        - Next piece color identification
        - Piece recognition functionality
        
        Piece recognition functionality requires window detection
        to be completed before becoming available.
        
        Args:
            parent: Parent widget to contain the analysis controls
        """
        section = self._create_section(parent, "🧩 Piece Recognition")
        
        # Piece recognition - identifies the next pieces colors
        self.btn_piece_recognition = ctk.CTkButton(
            section,
            text="🧩 Identify Next Pieces",
            height=32,
            font=FONTS["button"],
            command=self.on_run_piece_recognition,
            state="disabled",  # Enabled after window detection
            fg_color=COLORS["primary"],
            hover_color=COLORS["accent"]
        )
        self.btn_piece_recognition.pack(fill="x", pady=(0, 10))
        
        # Drop next piece - starts continuous auto-dropping with 3s intervals
        self.btn_drop_next_piece = ctk.CTkButton(
            section,
            text="🚀 Auto-Drop Mode",
            height=32,
            font=FONTS["button"],
            command=self.on_drop_next_piece,
            state="disabled",  # Enabled after window detection
            fg_color=COLORS["secondary"],
            hover_color=COLORS["accent"]
        )
        self.btn_drop_next_piece.pack(fill="x", pady=(0, 5))
        
        # Validation checkbox - enables piece validation before dropping
        self.enable_validation = ctk.BooleanVar(value=True)
        self.chk_enable_validation = ctk.CTkCheckBox(
            section,
            text="✓ Validate pieces before dropping",
            variable=self.enable_validation,
            font=FONTS["body"],
            fg_color=COLORS["primary"],
            hover_color=COLORS["accent"]
        )
        self.chk_enable_validation.pack(fill="x", pady=(0, 5))

    def _create_tools_controls(self, parent) -> None:
        """
        Create development tools and utilities controls.
        
        This section provides:
        - Shape Tracer tool for creating coordinate mappings
        - Other development and debugging utilities
        
        These tools are always available and don't require window detection
        or other setup steps as they're independent utilities.
        
        Args:
            parent: Parent widget to contain the tools controls
        """
        section = self._create_section(parent, "🛠️ Development Tools")
        
        # Shape Tracer tool - opens the shape tracer utility for creating coordinate mappings
        self.btn_shape_tracer = ctk.CTkButton(
            section,
            text="📐 Shape Tracer",
            height=32,
            font=FONTS["button"],
            command=self.on_launch_shape_tracer,
            fg_color=COLORS["secondary"],
            hover_color=COLORS["accent"]
        )
        self.btn_shape_tracer.pack(fill="x", pady=0)

    def _create_section(self, parent, title: str) -> ctk.CTkFrame:
        """
        Create a standardized section container with header and content area.
        
        Provides consistent styling and layout for all sidebar sections including:
        - Header with section title and appropriate emoji
        - Padded content area with rounded corners
        - Consistent spacing and visual hierarchy
        
        Args:
            parent: Parent widget to contain the section
            title: Section title with optional emoji prefix
            
        Returns:
            CTkFrame: Inner content frame for placing section controls
        """
        # Create section header with title and consistent styling
        header_frame = ctk.CTkFrame(parent, height=40, fg_color="transparent")
        header_frame.pack(fill="x", pady=(10, 5), padx=10)
        header_frame.pack_propagate(False)  # Maintain fixed header height
        
        # Section title label with left alignment for visual consistency
        header_label = ctk.CTkLabel(
            header_frame,
            text=title,
            font=FONTS["heading"],
            text_color=COLORS["text_primary"],
            anchor="w"
        )
        header_label.pack(side="left", padx=8, pady=10)
        
        # Content container with visual separation and rounded corners
        content_frame = ctk.CTkFrame(parent, fg_color=COLORS["bg_dark"], corner_radius=12)
        content_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        # Inner padding frame to provide consistent spacing for all content
        inner_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        inner_frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        return inner_frame

    def _create_main_content(self, parent) -> None:
        """
        Create the main content area containing activity logs and status information.
        
        The main content area provides:
        - Real-time activity logging with color-coded messages
        - Scrollable text area for viewing extended operation history
        - Log management controls (clear, export, etc.)
        
        This area expands to fill available space and provides the primary
        feedback mechanism for user actions and bot operations.
        
        Args:
            parent: Parent widget to contain the main content area
        """
        # Create main content container with responsive grid layout
        content = ctk.CTkFrame(parent, corner_radius=0)
        content.grid(row=1, column=1, sticky="nsew", padx=0, pady=0)
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)  # Log panel takes all available space
        
        # Initialize the activity log panel
        self._create_log_panel(content)

    def _create_log_panel(self, parent) -> None:
        """
        Create the activity log panel with header controls and scrollable text area.
        
        The log panel provides:
        - Real-time activity monitoring with timestamped entries
        - Color-coded message levels (info, success, warning, error)
        - Scrollable text area with monospace font for readability
        - Log management controls (clear, potentially export in future)
        
        All bot operations, user actions, and system events are logged here
        to provide comprehensive operational visibility.
        
        Args:
            parent: Parent widget to contain the log panel
        """
        # Main log container with visual separation
        log_frame = ctk.CTkFrame(parent, fg_color=COLORS["bg_light"])
        log_frame.grid(row=0, column=0, sticky="nsew", padx=25, pady=25)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(1, weight=1)  # Text area gets expansion priority
        
        # Log panel header with title and management controls
        header_frame = ctk.CTkFrame(log_frame, height=50, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=25, pady=(20, 10))
        header_frame.grid_propagate(False)
        header_frame.columnconfigure(0, weight=1)  # Title expands
        header_frame.columnconfigure(1, weight=0)  # Button stays fixed
        
        # Log section title
        log_title = ctk.CTkLabel(
            header_frame,
            text="📋 Activity Log",
            font=FONTS["title"],
            text_color=COLORS["text_primary"],
            anchor="w"
        )
        log_title.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        
        # Clear log button for log management
        clear_btn = ctk.CTkButton(
            header_frame,
            text="🗑️ Clear",
            width=90,
            height=35,
            font=FONTS["body"],
            command=self.on_clear_log,
            fg_color=COLORS["secondary"],
            hover_color=COLORS["error"]
        )
        clear_btn.grid(row=0, column=1, sticky="e")
        
        # Scrollable text area for activity log display
        self.log_text = ctk.CTkTextbox(
            log_frame,
            font=FONTS["mono"],           # Monospace for consistent formatting
            fg_color=COLORS["bg_dark"],
            text_color=COLORS["text_primary"],
            corner_radius=12
        )
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=25, pady=(0, 20))

    # ---------- Status & Logging ----------
    
    def _schedule_status_refresh(self) -> None:
        """
        Schedule periodic status updates for the application interface.
        
        Maintains a regular refresh cycle to ensure UI state remains synchronized
        with actual bot operations and system status. This method schedules itself
        recursively to provide continuous monitoring.
        
        Note: Status indicators have been removed from the current implementation
        but the refresh cycle is maintained for future extensibility.
        """
        # Schedule the next refresh cycle (500ms interval for responsive updates)
        self.root.after(500, self._schedule_status_refresh)

    def _refresh_status_indicators(self) -> None:
        """
        Update visual status indicators based on current application state.
        
        This method would update any visual status indicators such as:
        - Connection status lights
        - Operation progress indicators
        - Feature availability badges
        
        Currently unused but maintained for future implementation of status displays.
        """
        # Status indicators have been removed in current design
        # This method is preserved for future status display implementations
        pass

    def log(self, msg: str, level: str = "INFO") -> None:
        """
        Add a timestamped, color-coded message to the activity log.
        
        Provides comprehensive logging functionality with visual distinction
        between different message types. Each log entry includes:
        - Precise timestamp for operation tracking
        - Level-specific emoji and color coding
        - Automatic scrolling to show latest entries
        
        Args:
            msg: The message content to log
            level: Message severity level - "INFO", "SUCCESS", "WARNING", or "ERROR"
                  Defaults to "INFO" for general informational messages
        """
        # Generate precise timestamp for operation tracking
        timestamp = time.strftime("%H:%M:%S")
        
        # Define level-specific styling and visual indicators
        level_config = {
            "INFO": {"emoji": "ℹ️", "color": COLORS["text_secondary"]},
            "SUCCESS": {"emoji": "✅", "color": COLORS["success"]},
            "WARNING": {"emoji": "⚠️", "color": COLORS["warning"]},
            "ERROR": {"emoji": "❌", "color": COLORS["error"]}
        }
        
        # Get configuration for the specified level, fallback to INFO if unknown
        config = level_config.get(level, level_config["INFO"])
        formatted_msg = f"[{timestamp}] {config['emoji']} {msg}\n"
        
        # Only try to log to GUI if it's still available
        if self._gui_available and hasattr(self, 'log_text') and self.log_text:
            try:
                # Insert the formatted message and ensure it's visible
                self.log_text.insert("end", formatted_msg)
                self.log_text.see("end")  # Auto-scroll to show latest entry
            except Exception:
                # GUI is being destroyed, print to console instead
                print(f"[GUI Log] {formatted_msg.strip()}")
        else:
            # GUI not available, print to console
            print(f"[GUI Log] {formatted_msg.strip()}")

    # ---------- Event Handlers ----------
    
    def on_open_settings(self) -> None:
        """
        Open the application settings configuration dialog.
        
        Provides access to global application settings including:
        - Visual theme and appearance options
        - Bot behavior and timing configurations
        - Advanced feature toggles and preferences
        
        Opens a comprehensive settings window with organized categories.
        """
        try:
            from settings_gui import SettingsWindow
            settings_window = SettingsWindow(self.root)
            self.log("✅ Opened Settings window")
        except ImportError as e:
            messagebox.showerror("Settings Error", f"Failed to load settings window:\n{str(e)}")
            self.log("❌ Failed to open Settings window", "ERROR")
        except Exception as e:
            messagebox.showerror("Settings Error", f"An error occurred:\n{str(e)}")
            self.log("❌ Error opening Settings window", "ERROR")

    def on_find_window(self) -> None:
        """
        Toggle game window detection using the integrated window detector.
        
        If the window detector is available, this will:
        - Start/stop continuous window detection
        - Handle real game window location and tracking
        - Enable dependent features upon successful detection
        - Provide real-time status updates through callbacks
        
        Falls back to placeholder functionality if detector is unavailable.
        """
        if self.window_detector is not None:
            try:
                # Use the real window detector to toggle detection
                is_active = self.window_detector.toggle_detection()
                
                if is_active:
                    self.log("🔍 Started window detection...", "INFO")
                    self.btn_find_window.configure(text="🔍 Searching...")
                else:
                    self.log("⏹️ Stopped window detection", "INFO")
                    self.btn_find_window.configure(text="Find Game Window")
                    
            except Exception as e:
                self.log(f"❌ Error with window detector: {e}", "ERROR")
                self._fallback_window_detection()
        else:
            # Fallback to placeholder functionality
            self._fallback_window_detection()
    
    def _fallback_window_detection(self) -> None:
        """
        Fallback window detection for when the detector is unavailable.
        
        Provides placeholder functionality to maintain GUI usability
        during development or when the window detector cannot be initialized.
        """
        # Toggle the detection state for simulation purposes
        self.state.window_detected = not self.state.window_detected
        status = "found (simulated)" if self.state.window_detected else "lost (simulated)"
        level = "SUCCESS" if self.state.window_detected else "WARNING"
        self.log(f"Game window {status}", level)
        
        # Update button text based on state
        if self.state.window_detected:
            self.btn_find_window.configure(text="🔗 Window Connected (Sim)")
            self.enable_feature("asset_recognition", True)
        else:
            self.btn_find_window.configure(text="Find Game Window")
            self.enable_feature("asset_recognition", False)

    def _on_find_window_right_click(self, event) -> None:
        """
        Handle right-click on the find window button to toggle overlay.
        
        Right-click provides access to the visual debugging overlay
        functionality when the window detector is available.
        
        Args:
            event: Tkinter event object (unused)
        """
        if self.window_detector is not None:
            try:
                # Toggle the overlay using the window detector
                is_active = self.window_detector.toggle_overlay()
                
                if is_active:
                    self.log("🎯 Visual overlay started", "SUCCESS")
                else:
                    self.log("⏹️ Visual overlay stopped", "INFO")
                    
            except Exception as e:
                self.log(f"❌ Error with overlay: {e}", "ERROR")
        else:
            self.log("⚠️ Overlay not available - window detector not initialized", "WARNING")

    def on_capture_screen(self) -> None:
        """
        Initiate screen capture operation with validation and progress tracking.
        
        Captures the current game window content for analysis purposes.
        Validates prerequisites and provides user feedback throughout the process:
        - Verifies game window is detected and accessible
        - Initiates capture operation with progress indication
        - Simulates realistic capture timing for user experience
        
        In production, this would capture actual screen content and prepare
        it for subsequent analysis operations.
        """
        # Validate that window detection is complete before attempting capture
        if not self.state.window_detected:
            messagebox.showwarning("No Window", "🪟 Please find the game window first!")
            self.log("Capture attempted without a window", "ERROR")
            return
        
        # Begin capture operation with status tracking
        self.state.capture_active = True
        self.log("Screen capture in progress...", "SUCCESS")
        
        # Simulate realistic capture processing time with completion callback
        self.root.after(1500, lambda: self._complete_capture())

    def _complete_capture(self) -> None:
        """
        Complete the screen capture operation and update application state.
        
        Finalizes the capture process by:
        - Updating capture state to reflect completion
        - Logging successful completion for user feedback
        - Preparing captured data for subsequent analysis operations
        
        In production implementation, this would also:
        - Process and validate captured image data
        - Update UI to reflect available analysis options
        - Enable dependent features that require screen capture
        """
        # Update state to reflect capture completion
        self.state.capture_active = False
        self.log("Screen capture completed", "SUCCESS")

    def on_detect_board(self) -> None:
        """
        Run object recognition to detect and analyze game elements.
        
        Uses the ObjectRecognizer to perform one-shot recognition of all
        predefined shapes and elements in the current game window. Provides
        detailed metrics for each detected object including:
        - Mean grayscale values for presence detection
        - Contrast measurements for element clarity
        - Edge strength analysis for boundary detection
        - Pixel count for coverage analysis
        """
        if self.object_recognizer:
            try:
                results = self.object_recognizer.run_recognition_once()
                if results:
                    self.log(f"🎯 Object recognition completed - analyzed {len(results)} shapes", "SUCCESS")
                    self.log(f"📊 Detected elements: {', '.join([str(r['label']) for r in results])}", "INFO")
                    self.state.board_detected = True
                else:
                    self.log("❌ No shapes detected - ensure game window is visible and shapes are loaded", "WARNING")
            except Exception as e:
                self.log(f"❌ Object recognition failed: {e}", "ERROR")
        else:
            self.log("⚠️ Object recognizer not available - ensure window is detected first", "WARNING")

    def _on_detect_board_right_click(self, event) -> None:
        """
        Toggle the object recognition shape overlay on right-click.
        
        Shows/hides a semi-transparent overlay displaying all predefined shapes
        and their labels over the game window for visual verification and debugging.
        The overlay helps validate that shape coordinates are properly aligned
        with the actual game elements.
        """
        if self.object_recognizer:
            try:
                overlay_active = self.object_recognizer.toggle_overlay()
                if overlay_active:
                    self.log("👁️ Object recognition overlay enabled", "INFO")
                else:
                    self.log("👁️ Object recognition overlay disabled", "INFO")
            except Exception as e:
                self.log(f"❌ Failed to toggle overlay: {e}", "ERROR")
        else:
            self.log("⚠️ Object recognizer not available", "WARNING")

    def on_run_piece_recognition(self) -> None:
        """
        Run piece recognition to identify the colors of the next pieces.
        
        Uses the PieceRecognizer to analyze the next piece areas and determine
        their colors (Red, Green, Blue, or combinations).
        """
        if not self.piece_recognizer:
            self.log("❌ Piece recognizer not available", "ERROR")
            return
            
        if not self.window_detector or not self.state.window_detected:
            self.log("❌ Game window must be detected first", "ERROR")
            return
            
        try:
            self.log("🧩 Running piece recognition...", "INFO")
            
            # Run the piece recognition
            results = self.piece_recognizer.detect_next_pieces()
            
            # Log the results
            self.log("✅ Piece recognition completed", "SUCCESS")
            
            # Enable the drop next piece button after successful piece recognition
            if hasattr(self, 'btn_drop_next_piece'):
                self.btn_drop_next_piece.configure(state="normal")
            
            for piece_key, data in results.items():
                label = data.get('label', 'Unknown')
                fractions = data.get('fractions', {})
                n_pixels = data.get('n_pixels', 0)

                piece_name = piece_key.replace('_', ' ').title()
                self.log(f"🎯 {piece_name}: {label}", "SUCCESS")

                # Build a tidy, descending list of token coverages, regardless of token names
                sorted_tokens = sorted(fractions.items(), key=lambda kv: kv[1], reverse=True)
                token_str = ", ".join(f"{k}: {v:.2f}" for k, v in sorted_tokens)
                self.log(f"   Colors - {token_str} ({n_pixels} pixels)", "INFO")
        except Exception as e:
            self.log(f"❌ Piece recognition failed: {str(e)}", "ERROR")

    def on_drop_next_piece(self) -> None:
        """
        Start continuous piece dropping with auto-timing.
        
        This function will start the continuous dropping mechanism that:
        - Automatically drops the next piece every 3 seconds
        - Gives you time to manually drop your current piece between auto-drops
        - Can be stopped by pressing Esc
        """
        if not self.window_detector or not self.state.window_detected:
            self.log("❌ Game window must be detected first", "ERROR")
            return
            
        try:
            from drop_piece import DropPieceController
            if not self.piece_recognizer:
                self.log("❌ Piece recognizer not available", "ERROR")
                return
            self.log("🚀 Starting continuous auto-drop mode (3s intervals)... Press Esc to stop", "INFO")
            dp = DropPieceController(self.window_detector, self.piece_recognizer, self._on_detector_log)
            enable_validation = self.enable_validation.get() if hasattr(self, 'enable_validation') else True
            dp.start_auto_after_prime(
                auto_interval_ms=dp.cfg.get("auto_loop_interval_ms") or 2000,
                enable_validation=enable_validation
            )
            self.log("✅ Continuous dropping stopped", "SUCCESS")
        except Exception as e:
            self.log(f"❌ Failed to start continuous dropping: {e}", "ERROR")

    def on_clear_log(self) -> None:
        """
        Clear the activity log and reset the display.
        
        Removes all entries from the activity log while maintaining
        proper logging by recording the clear action itself. Provides
        a clean slate for monitoring new operations while preserving
        the action history.
        """
        # Clear all existing log content
        self.log_text.delete("1.0", "end")
        # Log the clear action for audit trail
        self.log("Activity log cleared", "INFO")

    def on_launch_shape_tracer(self) -> None:
        """
        Launch the Shape Tracer tool for creating coordinate mappings.
        
        Opens the shape_tracer.py utility in a new process, allowing users
        to create precise coordinate mappings for UI elements. The tool runs
        independently and can be used alongside the main application.
        
        Handles file path resolution and error reporting if the tool cannot
        be launched for any reason.
        """
        try:
            # Get the path to the shape tracer tool
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            shape_tracer_path = os.path.join(project_root, "tools", "shape_tracer.py")
            
            # Check if we're running as a bundled executable
            if getattr(sys, 'frozen', False):
                # Running as bundled executable - shape tracer not available
                self.log("❌ Shape Tracer not available in bundled version", "ERROR")
                self.log("💡 Use the development version to access Shape Tracer", "INFO")
                return
            
            # Check if the shape tracer file exists
            if not os.path.exists(shape_tracer_path):
                self.log(f"❌ Shape Tracer not found at: {shape_tracer_path}", "ERROR")
                return
            
            # Determine Python executable to use
            python_exe = sys.executable
            
            # Launch the shape tracer in a new process
            subprocess.Popen([
                python_exe, 
                shape_tracer_path
            ], cwd=project_root)
            
            self.log("🚀 Shape Tracer launched successfully", "SUCCESS")
            
        except Exception as e:
            self.log(f"❌ Failed to launch Shape Tracer: {str(e)}", "ERROR")

    # ---------- Feature Management ----------
    
    def enable_feature(self, name: str, enabled: bool = True) -> None:
        """
        Enable or disable application features with proper UI state management.
        
        Controls feature availability throughout the application lifecycle:
        - Updates button states to reflect feature availability
        - Maintains consistent user experience with clear visual feedback
        - Prevents access to features that require prerequisite setup
        - Logs feature state changes for operational transparency
        
        Args:
            name: Feature identifier ("asset_recognition", "analysis", or "piece_recognition")
            enabled: Whether to enable (True) or disable (False) the feature
        """
        # Update internal feature state tracking
        self.state.features[name] = enabled
        
        # Determine UI state and user feedback based on enabled status
        state = "normal" if enabled else "disabled"
        status_text = "enabled" if enabled else "disabled"
        
        # Update corresponding UI controls based on feature type
        if name == "asset_recognition":
            self.btn_detect_board.configure(state=state)
        elif name == "piece_recognition":
            if hasattr(self, 'btn_piece_recognition'):
                self.btn_piece_recognition.configure(state=state)
            if hasattr(self, 'btn_drop_next_piece'):
                self.btn_drop_next_piece.configure(state=state)
        
        # Log the feature state change for operational visibility
        self.log(f"Feature '{name}' {status_text}", "INFO")

    # ---------- Window Detector Callbacks ----------
    
    def _on_detector_log(self, msg: str, level: str = "INFO") -> None:
        """
        Handle log messages from the window detector.
        
        Forwards log messages from the window detector to the main GUI log
        with appropriate formatting and level mapping.
        
        Args:
            msg: Log message from the detector
            level: Log level (INFO, SUCCESS, WARNING, ERROR)
        """
        # Forward detector logs to main GUI log with detector prefix
        self.log(f"🔍 {msg}", level)
    
    def _on_detection_state_changed(self, detected: bool) -> None:
        """
        Handle detection state changes from the window detector.
        
        Updates the GUI state and enables/disables features based on
        whether the game window is currently detected.
        
        Args:
            detected: True if game window is detected, False otherwise
        """
        # Update internal state
        self.state.window_detected = detected
        
        # Enable/disable dependent features
        if detected:
            self.enable_feature("asset_recognition", True)
            self.enable_feature("piece_recognition", True)
            # Update button text to reflect active detection
            if hasattr(self, 'btn_find_window'):
                self.btn_find_window.configure(text="🔗 Window Connected")
        else:
            # Disable all dependent features when window is lost
            self.enable_feature("asset_recognition", False)
            self.enable_feature("piece_recognition", False)
            # Reset button text
            if hasattr(self, 'btn_find_window'):
                self.btn_find_window.configure(text="Find Game Window")

    def _on_window_close(self) -> None:
        """
        Handle application window close event.
        
        Ensures proper cleanup before the application terminates.
        """
        # Mark GUI as no longer available to prevent logging errors
        self._gui_available = False
        self.cleanup()
        self.root.destroy()

    def _initialize_window_detector(self) -> None:
        """
        Initialize the window detector after UI components are created.
        
        This method is called after the UI is fully set up, ensuring that
        logging functionality is available when initializing the detector.
        """
        if WINDOW_DETECTOR_AVAILABLE and GameWindowDetector is not None:
            try:
                self.window_detector = GameWindowDetector(
                    proc_names=('tlopo.exe',),
                    title_keywords=('The Legend of Pirates Online', 'TLOPO'),
                    log_callback=self._on_detector_log,
                    state_callback=self._on_detection_state_changed
                )
                self.log("🔍 Window detector initialized", "SUCCESS")
                self.log("💡 Tip: Right-click 'Find Game Window' button to toggle overlay", "INFO")
                
                # Initialize object recognizer after window detector is set up
                self._initialize_object_recognizer()
                
                # Initialize piece recognizer after window detector is set up
                self._initialize_piece_recognizer()
                
            except Exception as e:
                error_msg = str(e)
                if "pywin32" in error_msg.lower():
                    self.log("❌ pywin32 library issue - window detection unavailable", "ERROR")
                    self.log("💡 Try: pip install --force-reinstall pywin32", "INFO")
                else:
                    self.log(f"❌ Failed to initialize window detector: {e}", "ERROR")
                self.window_detector = None
        else:
            self.log("⚠️ Window detector not available - using placeholder functionality", "WARNING")

    def _initialize_object_recognizer(self) -> None:
        """
        Initialize the object recognizer after window detector is set up.
        
        Creates an ObjectRecognizer instance that reuses the existing window detector
        and provides object recognition functionality including shape detection
        and overlay visualization.
        """
        global OBJECT_RECOGNITION_AVAILABLE, ObjectRecognizer
        
        # Try to import object recognition module if not already done
        if not OBJECT_RECOGNITION_AVAILABLE:
            try:
                # Check if we're running as a bundled executable
                if getattr(sys, 'frozen', False):
                    # In bundled mode, try direct import
                    import object_recognition
                    ObjectRecognizer = object_recognition.ObjectRecognizer
                else:
                    # In development mode, use importlib for dynamic loading
                    import importlib.util
                    import os
                    
                    # Use importlib to cleanly import the object recognition module
                    current_dir = os.path.dirname(__file__)
                    object_recog_path = os.path.join(current_dir, "object_recognition.py")
                    
                    if not os.path.exists(object_recog_path):
                        raise ImportError(f"Object recognition file not found at {object_recog_path}")
                    
                    # Create module spec and load it cleanly
                    spec = importlib.util.spec_from_file_location("object_recognition", object_recog_path)
                    if spec is None or spec.loader is None:
                        raise ImportError("Failed to create module spec for object_recognition")
                    
                    mod = importlib.util.module_from_spec(spec)
                    
                    # Add the module to sys.modules to avoid dataclass issues
                    sys.modules['object_recognition'] = mod
                    
                    spec.loader.exec_module(mod)
                    
                    # Extract the ObjectRecognizer class
                    ObjectRecognizer = mod.ObjectRecognizer

                OBJECT_RECOGNITION_AVAILABLE = True
                self.log("📦 Object recognition module imported successfully", "SUCCESS")
                    
            except Exception as e:
                self.log(f"❌ Failed to import object recognition module: {e}", "ERROR")
                self.object_recognizer = None
                return
        
        if OBJECT_RECOGNITION_AVAILABLE and ObjectRecognizer is not None and self.window_detector is not None:
            try:
                self.object_recognizer = ObjectRecognizer(
                    log_callback=self._on_detector_log,
                    state_callback=None,
                    tk_root=self.root,
                    detector=self.window_detector
                )
                self.log("🎯 Object recognizer initialized", "SUCCESS")
                self.log("💡 Tip: Right-click 'Run Object Recognition' button to toggle shape overlay", "INFO")
            except Exception as e:
                self.log(f"❌ Failed to initialize object recognizer: {e}", "ERROR")
                self.object_recognizer = None
        else:
            self.log("⚠️ Object recognition not available - dependencies missing", "WARNING")
            self.object_recognizer = None

    def _get_swatch_json_path(self) -> str:
        """Get the path to the piece color swatches JSON file."""
        return get_resource_path("configuration/piece_color_swatches.json")

    def _initialize_piece_recognizer(self) -> None:
        if PIECE_RECOGNITION_AVAILABLE and PieceRecognizer is not None and self.window_detector is not None:
            try:
                kwargs = {
                    "detector": self.window_detector,
                    "log_callback": self._on_detector_log
                }
                swatch_path = self._get_swatch_json_path()
                if os.path.exists(swatch_path):
                    kwargs["swatches_json_path"] = swatch_path
                    self.log(f"🧩 Using color swatches from: {swatch_path}", "INFO")

                self.piece_recognizer = PieceRecognizer(**kwargs)
                self.log("🧩 Piece recognizer initialized", "SUCCESS")
            except Exception as e:
                self.log(f"❌ Failed to initialize piece recognizer: {e}", "ERROR")
                self.piece_recognizer = None
        else:
            self.log("⚠️ Piece recognition not available - dependencies missing", "WARNING")
            self.piece_recognizer = None

    def cleanup(self) -> None:
        """
        Clean up all application resources before shutdown.
        
        Properly shuts down the window detector, object recognizer, and cleans up
        any resources to prevent memory leaks or hanging processes.
        """
        # Clean up object recognizer first
        if self.object_recognizer:
            try:
                self.object_recognizer.cleanup()
                if self._gui_available:
                    self.log("🧹 Object recognizer cleaned up", "INFO")
            except Exception as e:
                if self._gui_available:
                    self.log(f"❌ Error during object recognizer cleanup: {e}", "ERROR")
                else:
                    print(f"[Cleanup] Error during object recognizer cleanup: {e}")
        
        # Clean up piece recognizer
        if self.piece_recognizer:
            try:
                # Piece recognizer doesn't have a cleanup method currently, but we set it to None
                self.piece_recognizer = None
                if self._gui_available:
                    self.log("🧹 Piece recognizer cleaned up", "INFO")
            except Exception as e:
                if self._gui_available:
                    self.log(f"❌ Error during piece recognizer cleanup: {e}", "ERROR")
                else:
                    print(f"[Cleanup] Error during piece recognizer cleanup: {e}")
        
        # Clean up window detector
        if self.window_detector:
            try:
                self.window_detector.cleanup()
                if self._gui_available:
                    self.log("🧹 Window detector cleaned up", "INFO")
            except Exception as e:
                if self._gui_available:
                    self.log(f"❌ Error during window detector cleanup: {e}", "ERROR")
                else:
                    print(f"[Cleanup] Error during window detector cleanup: {e}")

    def run(self) -> None:
        """
        Start the application with proper feature initialization and main event loop.
        
        Initializes the application in a safe state with all advanced features
        disabled until proper setup is completed. This ensures users follow
        the correct operational sequence:
        1. Window detection first
        2. Asset recognition after window is found
        3. Analysis after board is detected
        4. Bot control after analysis is available
        
        Starts the main tkinter event loop to begin user interaction.
        """
        # Initialize application with all advanced features safely disabled
        self.enable_feature("asset_recognition", False)
        
        # Start the main application event loop
        self.root.mainloop()


# ---------- Application Entry Point ----------

if __name__ == "__main__":
    """
    Application entry point with error handling and cleanup.
    
    Creates and runs the main application instance with proper error handling
    to ensure graceful startup and shutdown in all circumstances.
    """
    app = None
    try:
        # Create and start the main application
        app = PotionGodApp()
        app.run()
    except KeyboardInterrupt:
        # Handle graceful shutdown on Ctrl+C
        print("\nApplication interrupted by user")
    except Exception as e:
        # Handle any unexpected errors during startup or operation
        print(f"Application error: {e}")
        raise
    finally:
        # Ensure cleanup happens regardless of how the app exits
        if app is not None:
            try:
                # Mark GUI as unavailable before cleanup
                app._gui_available = False
                app.cleanup()
            except Exception as cleanup_error:
                print(f"Error during final cleanup: {cleanup_error}")
