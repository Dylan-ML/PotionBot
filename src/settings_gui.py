# settings_gui.py
"""
Potion God - Settings Window

A modern settings interface for configuring the Potion God application.
Provides essential configuration tabs with consistent design matching the main application.

Features:
- Dark theme with modern styling consistent with main GUI
- Appearance and Advanced settings categories
- Advanced timing delays configuration with interactive editor
- Comprehensive delay parameter management and validation
- Settings load, save, and reset functionality
- Responsive layout with tabbed sections

Version: 1.1.0
"""

from typing import Callable, Optional, Any
import customtkinter as ctk
from tkinter import messagebox, filedialog
import tkinter as tk
import os
import json
from pathlib import Path

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
        
        # Initialize delays configuration
        self.delays_config = {}
        self.delays_path = self._get_delays_path()
        
        # Create the settings window
        self._create_window()
        self._create_layout()
        
        # Load delays configuration
        self._load_delays_config()

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
        """Create content for advanced settings with delays configuration."""
        tab = self.tab_advanced
        
        # Create scrollable frame for advanced settings
        scrollable_frame = ctk.CTkScrollableFrame(tab, corner_radius=8)
        scrollable_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Title
        title_label = ctk.CTkLabel(
            scrollable_frame,
            text="⚡ Advanced Settings",
            font=FONTS["title"],
            text_color=COLORS["text_primary"]
        )
        title_label.pack(pady=(10, 20))
        
        # Delays Configuration Section
        self._create_delays_section(scrollable_frame)

    def _create_delays_section(self, parent) -> None:
        """Create the delays configuration section."""
        # Section frame
        delays_frame = ctk.CTkFrame(parent, corner_radius=8)
        delays_frame.pack(fill="x", padx=10, pady=10)
        
        # Section title
        section_title = ctk.CTkLabel(
            delays_frame,
            text="⏱️ Timing Delays Configuration",
            font=FONTS["heading"],
            text_color=COLORS["text_primary"]
        )
        section_title.pack(pady=(15, 10))
        
        # Description
        desc_label = ctk.CTkLabel(
            delays_frame,
            text="Configure timing delays for mouse movements, clicks, and automation intervals.",
            font=FONTS["body"],
            text_color=COLORS["text_secondary"],
            wraplength=600
        )
        desc_label.pack(pady=(0, 15))
        
        # Buttons frame
        buttons_frame = ctk.CTkFrame(delays_frame, fg_color="transparent")
        buttons_frame.pack(fill="x", padx=20, pady=10)
        
        # Load button
        load_btn = ctk.CTkButton(
            buttons_frame,
            text="📂 Load Config",
            width=120,
            height=35,
            font=FONTS["button"],
            command=self._load_delays_file,
            fg_color=COLORS["primary"],
            hover_color=COLORS["accent"]
        )
        load_btn.pack(side="left", padx=(0, 10))
        
        # View/Edit button
        self.view_edit_btn = ctk.CTkButton(
            buttons_frame,
            text="👁️ View & Edit",
            width=120,
            height=35,
            font=FONTS["button"],
            command=self._show_delays_editor,
            fg_color=COLORS["primary"],
            hover_color=COLORS["accent"]
        )
        self.view_edit_btn.pack(side="left", padx=(0, 10))
        
        # Save button
        self.save_btn = ctk.CTkButton(
            buttons_frame,
            text="💾 Save Config",
            width=120,
            height=35,
            font=FONTS["button"],
            command=self._save_delays_config,
            fg_color=COLORS["success"],
            hover_color="#2d5a2d",
            state="disabled"
        )
        self.save_btn.pack(side="left", padx=(0, 10))
        
        # Reset button
        reset_btn = ctk.CTkButton(
            buttons_frame,
            text="🔄 Reset to Defaults",
            width=140,
            height=35,
            font=FONTS["button"],
            command=self._reset_to_defaults,
            fg_color="#d32f2f",
            hover_color="#b71c1c"
        )
        reset_btn.pack(side="right")
        
        # Status label
        self.status_label = ctk.CTkLabel(
            delays_frame,
            text="Click 'Load Config' to load the current delays.json file",
            font=FONTS["body"],
            text_color=COLORS["text_secondary"]
        )
        self.status_label.pack(pady=(10, 15))

    # ---------- Delays Configuration Methods ----------
    
    def _get_delays_path(self) -> str:
        """Get the path to the delays.json file."""
        # Get the project root directory
        current_dir = Path(__file__).parent
        project_root = current_dir.parent
        return str(project_root / "configuration" / "delays.json")
    
    def _load_delays_config(self) -> None:
        """Load the delays configuration from file."""
        try:
            if os.path.exists(self.delays_path):
                with open(self.delays_path, 'r', encoding='utf-8') as f:
                    self.delays_config = json.load(f)
                self._update_status(f"Loaded {len(self.delays_config)} settings from delays.json", "success")
                self._enable_save_button()
            else:
                self._update_status("delays.json file not found", "warning")
                self.delays_config = {}
        except Exception as e:
            self._update_status(f"Error loading delays.json: {str(e)}", "error")
            self.delays_config = {}
    
    def _load_delays_file(self) -> None:
        """Load delays configuration from file."""
        file_path = filedialog.askopenfilename(
            title="Load Delays Configuration",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=os.path.dirname(self.delays_path)
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.delays_config = json.load(f)
                self._update_status(f"Loaded configuration from {os.path.basename(file_path)}", "success")
                self._enable_save_button()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load configuration:\n{str(e)}")
                self._update_status("Failed to load configuration", "error")
    
    def _save_delays_config(self) -> None:
        """Save the current delays configuration to file."""
        try:
            # Ensure the configuration directory exists
            os.makedirs(os.path.dirname(self.delays_path), exist_ok=True)
            
            with open(self.delays_path, 'w', encoding='utf-8') as f:
                json.dump(self.delays_config, f, indent=2)
            
            self._update_status("Configuration saved successfully", "success")
            messagebox.showinfo("Success", "Delays configuration saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration:\n{str(e)}")
            self._update_status("Failed to save configuration", "error")
    
    def _show_delays_editor(self) -> None:
        """Show the delays configuration editor window."""
        if not self.delays_config:
            messagebox.showwarning("Warning", "No configuration loaded. Please load a configuration first.")
            return
        
        DelaysEditorWindow(self.window, self.delays_config, self._on_config_updated)
    
    def _on_config_updated(self, updated_config: dict) -> None:
        """Callback when configuration is updated in the editor."""
        self.delays_config = updated_config
        self._enable_save_button()
        self._update_status("Configuration updated", "success")
    
    def _reset_to_defaults(self) -> None:
        """Reset delays configuration to default values."""
        result = messagebox.askyesno(
            "Confirm Reset",
            "This will reset all delay settings to their default values. Continue?"
        )
        
        if result:
            # Default delays configuration based on the drop_piece.py DEFAULTS
            default_config = {
                "_comments": {
                    "enter_poll_ms": "How often (ms) to poll keys (Enter/Esc).",
                    "enter_timeout_s": "Not used in auto-loop; keep null.",
                    "loop_enter_timeout_s": "Not used in auto-loop; keep null.",
                    "post_enter_settle_ms": "After the initial Enter (you place the current piece), wait this long before the first automated drop.",
                    "rescan_after_drop_delay_ms": "Pause (ms) after each drop so the game updates the Next area before re-scanning.",
                    "mouse_move_duration_ms": "Smooth mouse move time (ms) into the target box.",
                    "pre_left_click_sleep_ms": "Pause (ms) after the cursor arrives, before left click.",
                    "left_click_hold_ms": "How long (ms) to hold the left button before release.",
                    "post_left_click_sleep_ms": "Pause (ms) after the left click finishes.",
                    "pre_right_click_sleep_ms": "Pause (ms) before the right-click flip (if needed).",
                    "right_click_hold_ms": "How long (ms) to hold the right button before release.",
                    "flip_click_delay_ms": "Delay (ms) after the right-click flip so the game updates piece order.",
                    "post_drop_sleep_ms": "Small pause (ms) right after dropping (before any other actions).",
                    "validation_mouse_park_delay_ms": "Delay (ms) after parking mouse in mouse_parking area before validating pieces.",
                    "validation_initial_delay_ms": "Initial delay (ms) before first validation attempt to let game animations complete.",
                    "validation_retry_delay_ms": "Delay (ms) between validation retry attempts.",
                    "validation_max_attempts": "Maximum number of validation attempts before failing.",
                    "auto_loop_interval_ms": "Time (ms) between automated drops AFTER the first one."
                },
                "enter_poll_ms": 30,
                "enter_timeout_s": None,
                "loop_enter_timeout_s": None,
                "post_enter_settle_ms": 80,
                "rescan_after_drop_delay_ms": 80,
                "mouse_move_duration_ms": 120,
                "pre_left_click_sleep_ms": 10,
                "left_click_hold_ms": 25,
                "post_left_click_sleep_ms": 20,
                "pre_right_click_sleep_ms": 10,
                "right_click_hold_ms": 25,
                "flip_click_delay_ms": 60,
                "post_drop_sleep_ms": 40,
                "validation_mouse_park_delay_ms": 100,
                "validation_initial_delay_ms": 500,
                "validation_retry_delay_ms": 200,
                "validation_max_attempts": 5,
                "auto_loop_interval_ms": 2000,
                "mouse_jitter_px": 2,
                "pair_overrides": {}
            }
            
            self.delays_config = default_config
            self._enable_save_button()
            self._update_status("Reset to default configuration", "success")
    
    def _enable_save_button(self) -> None:
        """Enable the save button when configuration is loaded."""
        self.save_btn.configure(state="normal")
    
    def _update_status(self, message: str, status_type: str = "info") -> None:
        """Update the status label with a message."""
        color_map = {
            "success": "#4caf50",
            "warning": "#ff9800", 
            "error": "#f44336",
            "info": COLORS["text_secondary"]
        }
        
        color = color_map.get(status_type, COLORS["text_secondary"])
        self.status_label.configure(text=message, text_color=color)

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


class DelaysEditorWindow:
    """
    Editor window for delays configuration settings.
    Provides a detailed interface for viewing and editing all delay parameters.
    """
    
    def __init__(self, parent, config: dict, callback: Callable[[dict], None]) -> None:
        """
        Initialize the delays editor window.
        
        Args:
            parent: Parent window
            config: Current delays configuration dictionary
            callback: Function to call when configuration is updated
        """
        self.parent = parent
        self.config = config.copy()  # Work with a copy
        self.callback = callback
        self.entry_widgets = {}
        
        self._create_window()
        self._create_layout()
        self._populate_fields()

    def _create_window(self) -> None:
        """Create and configure the editor window."""
        self.window = ctk.CTkToplevel(self.parent)
        self.window.title("Delays Configuration Editor")
        self.window.geometry("900x700")
        self.window.minsize(800, 600)
        
        # Set application icon
        set_window_icon(self.window)
        
        # Center the window
        self._center_window()
        
        # Configure grid layout
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        
        # Make window modal
        self.window.transient(self.parent)
        self.window.grab_set()
        
        # Handle window close event
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

    def _center_window(self) -> None:
        """Center the editor window on the parent."""
        self.window.update_idletasks()
        
        window_width = 900
        window_height = 700
        
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()
        
        x = parent_x + (parent_width - window_width) // 2
        y = parent_y + (parent_height - window_height) // 2
        
        self.window.geometry(f"{window_width}x{window_height}+{x}+{y}")

    def _create_layout(self) -> None:
        """Create the main layout for the editor."""
        # Main container
        main_frame = ctk.CTkFrame(self.window, corner_radius=0)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Create layout sections
        self._create_header(main_frame)
        self._create_editor_content(main_frame)
        self._create_button_panel(main_frame)

    def _create_header(self, parent) -> None:
        """Create the editor window header."""
        header = ctk.CTkFrame(parent, height=60, corner_radius=0, fg_color="#212121")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        
        # Editor title
        title_label = ctk.CTkLabel(
            header,
            text="⏱️ Delays Configuration Editor",
            font=FONTS["title"],
            text_color=COLORS["text_primary"]
        )
        title_label.pack(pady=20)

    def _create_editor_content(self, parent) -> None:
        """Create the main editor content area."""
        # Scrollable frame for all settings
        self.scroll_frame = ctk.CTkScrollableFrame(parent, corner_radius=8)
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        
        # Configure scrollable frame
        self.scroll_frame.columnconfigure(1, weight=1)

    def _populate_fields(self) -> None:
        """Populate the editor with configuration fields."""
        row = 0
        
        # Group related settings
        groups = {
            "Key Polling": ["enter_poll_ms", "enter_timeout_s", "loop_enter_timeout_s"],
            "Timing & Cadence": ["post_enter_settle_ms", "rescan_after_drop_delay_ms", "auto_loop_interval_ms"],
            "Mouse Movement": ["mouse_move_duration_ms", "mouse_jitter_px"],
            "Left Click": ["pre_left_click_sleep_ms", "left_click_hold_ms", "post_left_click_sleep_ms"],
            "Right Click": ["pre_right_click_sleep_ms", "right_click_hold_ms", "flip_click_delay_ms"],
            "Validation": ["validation_mouse_park_delay_ms", "validation_initial_delay_ms", 
                          "validation_retry_delay_ms", "validation_max_attempts"],
            "Other": ["post_drop_sleep_ms"]
        }
        
        for group_name, keys in groups.items():
            # Group header
            group_label = ctk.CTkLabel(
                self.scroll_frame,
                text=f"📋 {group_name}",
                font=FONTS["heading"],
                text_color=COLORS["text_primary"]
            )
            group_label.grid(row=row, column=0, columnspan=3, sticky="w", pady=(20, 10))
            row += 1
            
            # Add fields for this group
            for key in keys:
                if key in self.config:
                    row = self._add_field(key, self.config[key], row)
        
        # Special handling for pair_overrides
        if "pair_overrides" in self.config and self.config["pair_overrides"]:
            # Pair overrides section
            group_label = ctk.CTkLabel(
                self.scroll_frame,
                text="🔧 Pair Overrides",
                font=FONTS["heading"],
                text_color=COLORS["text_primary"]
            )
            group_label.grid(row=row, column=0, columnspan=3, sticky="w", pady=(20, 10))
            row += 1
            
            # Show pair overrides as read-only text for now
            overrides_text = json.dumps(self.config["pair_overrides"], indent=2)
            text_widget = ctk.CTkTextbox(
                self.scroll_frame,
                height=100,
                font=("Consolas", 10)
            )
            text_widget.grid(row=row, column=0, columnspan=3, sticky="ew", pady=5)
            text_widget.insert("1.0", overrides_text)
            text_widget.configure(state="disabled")

    def _add_field(self, key: str, value, row: int) -> int:
        """Add a field for editing a configuration value."""
        # Get description from comments if available
        comments = self.config.get("_comments", {})
        description = comments.get(key, "")
        
        # Label
        label_text = key.replace("_", " ").title()
        label = ctk.CTkLabel(
            self.scroll_frame,
            text=label_text,
            font=FONTS["body"],
            text_color=COLORS["text_primary"],
            width=200,
            anchor="w"
        )
        label.grid(row=row, column=0, sticky="w", padx=(10, 5), pady=5)
        
        # Entry field
        entry = ctk.CTkEntry(
            self.scroll_frame,
            width=100,
            height=30,
            font=FONTS["body"]
        )
        entry.grid(row=row, column=1, sticky="w", padx=5, pady=5)
        
        # Set current value
        if value is None:
            entry.insert(0, "null")
        else:
            entry.insert(0, str(value))
        
        # Store reference to entry widget
        self.entry_widgets[key] = entry
        
        # Description label
        if description:
            desc_label = ctk.CTkLabel(
                self.scroll_frame,
                text=description,
                font=("Arial", 10),
                text_color=COLORS["text_secondary"],
                wraplength=400,
                justify="left"
            )
            desc_label.grid(row=row, column=2, sticky="w", padx=(10, 5), pady=5)
        
        return row + 1

    def _create_button_panel(self, parent) -> None:
        """Create the bottom button panel."""
        button_frame = ctk.CTkFrame(parent, height=80, corner_radius=0, fg_color=COLORS["bg_light"])
        button_frame.grid(row=2, column=0, sticky="ew")
        button_frame.grid_propagate(False)
        
        # Button container
        button_container = ctk.CTkFrame(button_frame, fg_color="transparent")
        button_container.pack(expand=True)
        
        # Cancel button
        cancel_btn = ctk.CTkButton(
            button_container,
            text="❌ Cancel",
            width=120,
            height=35,
            font=FONTS["button"],
            command=self._on_cancel,
            fg_color="#d32f2f",
            hover_color="#b71c1c"
        )
        cancel_btn.pack(side="left", padx=(0, 10), pady=20)
        
        # Apply button
        apply_btn = ctk.CTkButton(
            button_container,
            text="✅ Apply Changes",
            width=140,
            height=35,
            font=FONTS["button"],
            command=self._on_apply,
            fg_color=COLORS["success"],
            hover_color="#2d5a2d"
        )
        apply_btn.pack(side="left", padx=10, pady=20)

    def _on_apply(self) -> None:
        """Apply the changes and close the editor."""
        try:
            # Validate and update configuration with values from entry widgets
            validation_errors = []
            
            for key, entry in self.entry_widgets.items():
                value_str = entry.get().strip()
                
                try:
                    if value_str.lower() == "null" or value_str == "":
                        self.config[key] = None
                    elif value_str.isdigit():
                        value = int(value_str)
                        # Basic validation for reasonable values
                        if value < 0:
                            validation_errors.append(f"{key}: Cannot be negative")
                        elif value > 10000 and "ms" in key:  # 10 second max for ms values
                            validation_errors.append(f"{key}: Value too large (max 10000ms)")
                        else:
                            self.config[key] = value
                    elif value_str.replace(".", "").isdigit():
                        value = float(value_str)
                        if value < 0:
                            validation_errors.append(f"{key}: Cannot be negative")
                        else:
                            self.config[key] = value
                    else:
                        validation_errors.append(f"{key}: Invalid value '{value_str}'")
                except Exception as e:
                    validation_errors.append(f"{key}: {str(e)}")
            
            # Show validation errors if any
            if validation_errors:
                error_msg = "Please fix the following errors:\n\n" + "\n".join(validation_errors)
                messagebox.showerror("Validation Errors", error_msg)
                return
            
            # Call the callback with updated configuration
            self.callback(self.config)
            
            # Show success message
            messagebox.showinfo("Success", "Configuration updated successfully!")
            
            # Close the window
            self.window.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply changes:\n{str(e)}")

    def _on_cancel(self) -> None:
        """Cancel changes and close the editor."""
        self.window.destroy()

    def _on_close(self) -> None:
        """Handle window close event."""
        self._on_cancel()


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
