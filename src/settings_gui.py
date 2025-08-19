# settings_gui.py
"""
Potion God - Settings Window

A modern settings interface for configuring the Potion God application.
Provides essential configuration tabs with consistent design matching the main application.

Features:
- Dark theme with modern styling consistent with main GUI
- Appearance and Advanced settings categories
- Streamlined interface for core configuration options
- Responsive layout with tabbed sections

Version: 1.0
"""

import customtkinter as ctk
from tkinter import messagebox
import tkinter as tk
import os

# Import color scheme and fonts from main GUI for consistency
from gui import COLORS, FONTS, set_window_icon

# Settings window configuration
SETTINGS_TITLE = "Potion God - Settings"
SETTINGS_SIZE = "800x700"


class SettingsWindow:
    """
    Settings configuration window for the Potion God application.
    
    Provides tabs for configuration options including appearance and advanced features.
    Uses a tabbed interface for organized access to different setting categories.
    """
    
    def __init__(self, parent=None) -> None:
        """
        Initialize the settings window with placeholder content.
        
        Args:
            parent: Parent window for modal behavior (optional)
        """
        self.parent = parent
        
        # Create the settings window
        self._create_window()
        self._create_layout()

    def _create_window(self) -> None:
        """Create and configure the main settings window."""
        self.window = ctk.CTkToplevel(self.parent) if self.parent else ctk.CTk()
        self.window.title(SETTINGS_TITLE)
        self.window.geometry(SETTINGS_SIZE)
        self.window.minsize(700, 600)
        
        # Set application icon
        set_window_icon(self.window)
        
        # Center the window on screen
        self._center_window()
        
        # Configure grid layout
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        
        # Make window modal if parent is provided
        if self.parent:
            self.window.transient(self.parent)
            self.window.grab_set()
        
        # Handle window close event
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

    def _center_window(self) -> None:
        """Center the settings window on screen or relative to parent."""
        self.window.update_idletasks()
        
        # Parse window dimensions
        width_str, height_str = SETTINGS_SIZE.split('x')
        window_width = int(width_str)
        window_height = int(height_str)
        
        if self.parent:
            # Center relative to parent window
            parent_x = self.parent.winfo_x()
            parent_y = self.parent.winfo_y()
            parent_width = self.parent.winfo_width()
            parent_height = self.parent.winfo_height()
            
            x = parent_x + (parent_width - window_width) // 2
            y = parent_y + (parent_height - window_height) // 2
        else:
            # Center on screen
            screen_width = self.window.winfo_screenwidth()
            screen_height = self.window.winfo_screenheight()
            
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
        
        self.window.geometry(f"{window_width}x{window_height}+{x}+{y}")

    def _create_layout(self) -> None:
        """Create the main layout with header, tabbed content, and buttons."""
        # Main container
        main_frame = ctk.CTkFrame(self.window, corner_radius=0)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Create layout sections
        self._create_header(main_frame)
        self._create_tabbed_content(main_frame)
        self._create_button_panel(main_frame)

    def _create_header(self, parent) -> None:
        """Create the settings window header."""
        header = ctk.CTkFrame(parent, height=60, corner_radius=0, fg_color="#212121")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        
        # Settings title
        title_label = ctk.CTkLabel(
            header,
            text="⚙️ Application Settings",
            font=FONTS["title"],
            text_color=COLORS["text_primary"]
        )
        title_label.pack(pady=20)

    def _create_tabbed_content(self, parent) -> None:
        """Create the main tabbed interface for settings categories."""
        # Tabbed view for different settings categories
        self.tabview = ctk.CTkTabview(parent, corner_radius=8)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        
        # Create tabs for different settings categories
        self.tab_appearance = self.tabview.add("Appearance")
        self.tab_advanced = self.tabview.add("Advanced")
        
        # Populate each tab with placeholder content
        self._create_appearance_placeholder()
        self._create_advanced_placeholder()

    def _create_appearance_placeholder(self) -> None:
        """Create placeholder content for appearance settings."""
        tab = self.tab_appearance
        
        placeholder_label = ctk.CTkLabel(
            tab,
            text="🎨 Appearance Settings\n\nThis section will contain visual theme and appearance options.\nComing soon...",
            font=FONTS["body"],
            text_color=COLORS["text_secondary"],
            justify="center"
        )
        placeholder_label.pack(expand=True, pady=50)

    def _create_advanced_placeholder(self) -> None:
        """Create placeholder content for advanced settings."""
        tab = self.tab_advanced
        
        placeholder_label = ctk.CTkLabel(
            tab,
            text="⚡ Advanced Settings\n\nThis section will contain advanced configuration and debugging options.\nComing soon...",
            font=FONTS["body"],
            text_color=COLORS["text_secondary"],
            justify="center"
        )
        placeholder_label.pack(expand=True, pady=50)

    def _create_button_panel(self, parent) -> None:
        """Create the bottom button panel with close button."""
        button_frame = ctk.CTkFrame(parent, height=80, corner_radius=0, fg_color=COLORS["bg_light"])
        button_frame.grid(row=2, column=0, sticky="ew")
        button_frame.grid_propagate(False)
        
        # Button container for centering
        button_container = ctk.CTkFrame(button_frame, fg_color="transparent")
        button_container.pack(expand=True)
        
        # Close button
        close_btn = ctk.CTkButton(
            button_container,
            text="✅ Close",
            width=130,
            height=35,
            font=FONTS["button"],
            command=self._close_window,
            fg_color=COLORS["primary"],
            hover_color=COLORS["accent"]
        )
        close_btn.pack(pady=20)

    # ---------- Event Handlers ----------
    
    def _close_window(self) -> None:
        """Close the settings window."""
        self.window.destroy()

    def _on_close(self) -> None:
        """Handle window close event."""
        self._close_window()

    def show(self) -> None:
        """Show the settings window and bring it to focus."""
        self.window.lift()
        self.window.focus()


def show_settings(parent=None) -> None:
    """
    Show the settings window.
    
    Args:
        parent: Parent window for modal behavior (optional)
    """
    settings_window = SettingsWindow(parent)
    
    # Wait for window to close if modal
    if parent:
        parent.wait_window(settings_window.window)


# For testing the settings window standalone
if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    
    # Create standalone settings window
    settings = SettingsWindow()
    settings.window.mainloop()
