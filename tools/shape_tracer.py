"""
shape_tracer.py — Universal tracer for static UI layouts (boxes + polygons) with TLOPO capture

A comprehensive tool for tracing UI elements in game windows, specifically designed for
The Legend of Pirates Online (TLOPO). Supports both rectangular regions (boxes) and
complex polygonal shapes with real-time overlay testing and aspect-ratio-aware scaling.

Features:
    - Automatic TLOPO window detection and capture
    - True 1:1 pixel accuracy with DPI awareness
    - Interactive zoom and pan controls
    - Rectangle and polygon shape creation/editing
    - Shape categorization and labeling
    - Aspect-ratio-aware coordinate transformation
    - Live overlay testing on game window
    - JSON persistence with scaling support
    - Normalized coordinate export

Dependencies:
    - Pillow: Image processing and display
    - mss: Screen capture functionality
    - psutil: Process management for window detection
    - pywin32: Windows API access for window manipulation

Author: [Your Name]
Version: 1.0
Last Modified: [Date]
"""

from __future__ import annotations

import platform
import ctypes
import json
import math
import os
import threading
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple, Union, Dict

import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, messagebox
from PIL import Image, ImageTk

# Windows-specific capture dependencies
import mss
import psutil
import win32gui
import win32process  # type: ignore

# ================================================================================
# DPI AWARENESS AND IMAGE RESAMPLING CONFIGURATION
# ================================================================================

def enable_windows_dpi_awareness() -> None:
    """
    Enable Windows DPI awareness for crisp display on high-DPI monitors.
    
    This function attempts to set the process DPI awareness to ensure that
    the application renders correctly on displays with different DPI settings.
    Falls back gracefully if DPI awareness cannot be set.
    
    Note:
        Only affects Windows systems. Does nothing on other platforms.
    """
    if platform.system() != "Windows":
        return
    
    try:
        # Try the newer SetProcessDpiAwareness (Windows 8.1+)
        # Parameter 2 = PROCESS_PER_MONITOR_DPI_AWARE
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            # Fall back to older SetProcessDPIAware (Windows Vista+)
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            # If both fail, continue without DPI awareness
            pass

# Configure image resampling method based on Pillow version
try:
    from PIL import Image as _Image
    # Use new-style resampling constant for Pillow 10+
    RESAMPLE = _Image.Resampling.LANCZOS
except Exception:
    # Fall back to legacy constant for older Pillow versions
    RESAMPLE = Image.LANCZOS  # type: ignore

# ================================================================================
# TLOPO WINDOW CAPTURE SYSTEM
# ================================================================================

class TlopoCapture:
    """
    Handles automatic detection and screen capture of TLOPO game windows.
    
    This class provides functionality to locate running TLOPO game instances,
    get their client area coordinates, and capture screenshots of the game
    content for shape tracing purposes.
    
    Attributes:
        EXCLUDE_SUBSTR: Process name substrings to exclude from window detection
        hwnd: Windows handle of the detected TLOPO window
        client_rect: Client area coordinates in screen space (L, T, R, B)
        
    Example:
        capture = TlopoCapture()
        if capture.find_window():
            image = capture.grab()
    """
    
    # Process names containing these substrings are excluded from detection
    EXCLUDE_SUBSTR = ["python", "tk", "debug"]

    def __init__(self, log=lambda *a, **k: None):
        """
        Initialize the TLOPO capture system.
        
        Args:
            log: Optional logging function for status messages
        """
        self.hwnd: Optional[int] = None
        self.client_rect: Optional[Tuple[int, int, int, int]] = None  # L,T,R,B in screen coords
        self._sct = mss.mss()  # Screen capture object
        self.log = log

    def find_window(self) -> bool:
        """
        Locate and select a TLOPO game window for capture.
        
        Enumerates all visible windows, searches for TLOPO-related titles,
        and validates that they belong to actual game processes (not development tools).
        
        Returns:
            bool: True if a valid TLOPO window was found and selected
            
        Note:
            Updates self.hwnd and self.client_rect if successful
        """
        candidates = []
        
        def enum_callback(hwnd: int, accumulator: List) -> bool:
            """Callback function for window enumeration."""
            # Only consider visible windows
            if not win32gui.IsWindowVisible(hwnd):
                return True
                
            # Get window title and check for TLOPO indicators
            title = win32gui.GetWindowText(hwnd) or ""
            title_lower = title.lower()
            
            if not title_lower:
                return True
                
            # Look for TLOPO-related keywords in window title
            if "legend of pirates online" in title_lower or "tlopo" in title_lower:
                try:
                    # Get process information to validate it's actually the game
                    _, process_id = win32process.GetWindowThreadProcessId(hwnd)
                    process_name = psutil.Process(process_id).name().lower()
                except Exception:
                    process_name = ""
                
                # Exclude development/debugging processes
                if not any(excluded in process_name for excluded in self.EXCLUDE_SUBSTR):
                    accumulator.append((hwnd, title, process_name))
                    
            return True
        
        # Enumerate all windows and collect TLOPO candidates
        win32gui.EnumWindows(enum_callback, candidates)
        
        if not candidates:
            self.log("No TLOPO window found.")
            return False
        
        # Use the first valid candidate found
        hwnd, title, process_name = candidates[0]
        
        # Get client area coordinates in screen space
        client_rect = win32gui.GetClientRect(hwnd)
        top_left = win32gui.ClientToScreen(hwnd, (0, 0))
        bottom_right = win32gui.ClientToScreen(hwnd, (client_rect[2], client_rect[3]))
        
        # Store window information
        self.hwnd = hwnd
        self.client_rect = (top_left[0], top_left[1], bottom_right[0], bottom_right[1])
        
        self.log(f"Found: '{title}' (proc={process_name}) client={self.client_rect}")
        return True

    def grab(self) -> Optional[Image.Image]:
        """
        Capture a screenshot of the TLOPO window's client area.
        
        Returns:
            Optional[Image.Image]: PIL Image of the captured area, or None if capture fails
            
        Note:
            Requires that find_window() has been called successfully first
        """
        if not self.client_rect:
            return None
            
        # Extract coordinates and create capture bounding box
        left, top, right, bottom = self.client_rect
        bbox = {
            "left": left, 
            "top": top, 
            "width": right - left, 
            "height": bottom - top
        }
        
        # Perform screen capture and convert to PIL Image
        screenshot = self._sct.grab(bbox)
        return Image.frombytes("RGB", screenshot.size, screenshot.rgb)

# ================================================================================
# SHAPE DATA MODELS AND CONSTANTS
# ================================================================================

# UI interaction constants
HANDLE_R = 7              # Radius of resize handles in pixels
EDGE_GRAB_PX = 6         # Distance for edge grab detection
ZOOM_MIN, ZOOM_MAX = 0.25, 6.0  # Zoom level limits
ZOOM_STEP = 1.15         # Zoom increment multiplier
POLY_EDGE_SNAP = 8       # Distance for polygon edge vertex insertion

@dataclass
class BoxShape:
    """
    Represents a rectangular shape with resize handles and labeling.
    
    Box shapes are defined by two corner points and support interactive
    resizing via corner and edge handles. Coordinates are stored in
    image pixel space.
    
    Attributes:
        x0, y0: First corner coordinates
        x1, y1: Second corner coordinates (can form any oriented rectangle)
        label: Human-readable name for the shape
        category: Classification (button, area, ui element, other)
        color: Hex color code for display
        
    Runtime attributes (managed by UI):
        canvas_rect: Tkinter canvas rectangle item ID
        canvas_text: Tkinter canvas text item ID  
        handles: List of canvas handle item IDs
    """
    x0: float
    y0: float
    x1: float
    y1: float
    label: str = "Box"
    category: str = "button"
    color: str = "#00b7ff"
    
    # Runtime canvas objects (not persisted)
    canvas_rect: Optional[int] = None
    canvas_text: Optional[int] = None
    handles: Optional[List[int]] = None

    def as_tuple(self) -> Tuple[float, float, float, float]:
        """
        Get normalized rectangle coordinates.
        
        Returns:
            Tuple[float, float, float, float]: (x0, y0, x1, y1) with x0 <= x1 and y0 <= y1
        """
        x0 = min(self.x0, self.x1)
        y0 = min(self.y0, self.y1)
        x1 = max(self.x0, self.x1)
        y1 = max(self.y0, self.y1)
        return x0, y0, x1, y1

@dataclass
class PolyShape:
    """
    Represents a polygonal shape with arbitrary vertices.
    
    Polygon shapes can be either open (for drawing in progress) or closed
    (completed shapes). Supports vertex-level editing and edge insertion.
    
    Attributes:
        pts: List of (x, y) vertex coordinates in image space
        closed: Whether the polygon is closed (last vertex connects to first)
        label: Human-readable name for the shape
        category: Classification (button, area, ui element, other)
        color: Hex color code for display
        
    Runtime attributes (managed by UI):
        handles: List of canvas vertex handle item IDs
    """
    pts: List[Tuple[float, float]]
    closed: bool = True
    label: str = "Polygon"
    category: str = "button"
    color: str = "#ff6b00"
    
    # Runtime canvas objects (not persisted)
    handles: Optional[List[int]] = None

# Type alias for either shape type
Shape = Union[BoxShape, PolyShape]

# ================================================================================
# CUSTOM DIALOG FOR SHAPE RENAMING AND CATEGORIZATION
# ================================================================================

class RenameDialog(tk.Toplevel):
    """
    Modal dialog for editing shape labels and categories.
    
    Provides a user-friendly interface for renaming shapes and assigning
    them to predefined categories. Supports keyboard shortcuts and
    automatic focus management.
    
    Attributes:
        result: Tuple of (label, category) if OK was clicked, None if cancelled
    """
    
    def __init__(self, parent: tk.Tk, initial_label: str = "", initial_category: str = "button"):
        """
        Initialize the rename dialog.
        
        Args:
            parent: Parent window for modal behavior
            initial_label: Pre-filled label text
            initial_category: Pre-selected category
        """
        super().__init__(parent)
        self.result: Optional[Tuple[str, str]] = None
        self.initial_label = initial_label
        self.initial_category = initial_category
        
        self._setup_window(parent)
        self.create_widgets()
        self._setup_event_handlers()
        
        # Set focus to label entry and select all text
        self.label_entry.focus_set()
        self.label_entry.select_range(0, tk.END)
    
    def _setup_window(self, parent: tk.Tk) -> None:
        """Configure window properties and positioning."""
        self.title("Rename & Categorize")
        self.transient(parent)
        self.grab_set()  # Make dialog modal
        
        # Set fixed size
        self.geometry("300x150")
        self.resizable(False, False)
        
        # Center dialog relative to parent window
        parent.update_idletasks()
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        
        dialog_x = parent_x + (parent_width // 2) - 150
        dialog_y = parent_y + (parent_height // 2) - 75
        self.geometry(f"300x150+{dialog_x}+{dialog_y}")
    
    def create_widgets(self) -> None:
        """Create and layout all dialog widgets."""
        # Main container with padding
        main_frame = ttk.Frame(self, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        # Label input section
        ttk.Label(main_frame, text="Label:").grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.label_entry = ttk.Entry(main_frame, width=30)
        self.label_entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        self.label_entry.insert(0, self.initial_label)
        
        # Category selection section
        ttk.Label(main_frame, text="Category:").grid(row=2, column=0, sticky="w", pady=(0, 5))
        self.category_var = tk.StringVar(value=self.initial_category)
        category_combo = ttk.Combobox(main_frame, textvariable=self.category_var, width=27)
        category_combo['values'] = ("button", "area", "ui element", "other")
        category_combo['state'] = 'readonly'
        category_combo.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 15))
        
        # Button section
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, sticky="ew")
        
        ttk.Button(button_frame, text="OK", command=self.on_ok).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="Cancel", command=self.on_cancel).pack(side=tk.RIGHT)
        
        # Configure grid weights for responsive layout
        main_frame.columnconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
    
    def _setup_event_handlers(self) -> None:
        """Configure keyboard shortcuts and window close handling."""
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.bind('<Return>', lambda e: self.on_ok())
        self.bind('<Escape>', lambda e: self.on_cancel())
    
    def on_ok(self) -> None:
        """Handle OK button click - validate and store results."""
        label = self.label_entry.get().strip()
        category = self.category_var.get()
        
        # Only accept if label is not empty
        if label:
            self.result = (label, category)
            self.destroy()
    
    def on_cancel(self) -> None:
        """Handle Cancel button click or window close."""
        self.result = None
        self.destroy()

# ================================================================================
# MAIN APPLICATION CLASS
# ================================================================================

class App(tk.Tk):
    """
    Main application window for the Shape Tracer tool.
    
    Provides a complete interface for capturing game windows, creating and editing
    shapes, managing zoom/pan, and exporting coordinate data. Integrates all
    functionality into a cohesive user experience.
    
    Key Features:
        - Automatic TLOPO window detection and capture
        - Interactive shape creation (boxes and polygons)
        - Real-time zoom and pan with mouse/keyboard controls
        - Shape persistence with aspect-ratio-aware loading
        - Live overlay testing on game window
        - Normalized coordinate export for automation
        
    Attributes:
        img: Current loaded PIL Image
        tk_img: Tkinter-compatible PhotoImage for display
        W, H: Image dimensions in pixels
        zoom: Current zoom level (1.0 = 100%)
        shapes: List of all created shapes
        selected: Currently selected shape for editing
        mode: Current interaction mode (idle, drawing_box, etc.)
    """
    
    def __init__(self):
        """Initialize the main application window and all subsystems."""
        # Enable DPI awareness before creating UI
        enable_windows_dpi_awareness()
        super().__init__()
        
        # Disable Tkinter's automatic DPI scaling to maintain pixel accuracy
        self.tk.call('tk', 'scaling', 1.0)
        self.title("Shape Tracer (capture + boxes + polygons)")
        
        # Set application icon
        try:
            # Get the project root (parent of tools folder)
            script_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(script_dir)
            icon_path = os.path.join(project_root, "icon.ico")
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception as e:
            print(f"Warning: Could not load icon for shape tracer: {e}")

        # Initialize core application state
        self._init_state_variables()
        
        # Create user interface
        self._create_toolbar()
        self._create_canvas_area()
        
        # Initialize capture system
        self.cap = TlopoCapture(log=self._log)
        
        # Configure event handlers
        self._setup_event_bindings()
        
        # Auto-initialize: attempt to find and capture TLOPO window
        self.after(100, self.auto_initialize)

    def _init_state_variables(self) -> None:
        """Initialize all application state variables."""
        # Image and display state
        self.img: Optional[Image.Image] = None
        self.tk_img: Optional[ImageTk.PhotoImage] = None
        self.img_item: Optional[int] = None
        self.W = 1  # Image width
        self.H = 1  # Image height
        self.zoom = 1.0
        
        # Shape management
        self.shapes: List[Shape] = []
        self.selected: Optional[Shape] = None
        
        # Interaction state machine
        self.mode = "idle"  # Current interaction mode
        # Modes: idle, drawing_box, drawing_poly, moving, resizing, dragging_vertex, panning
        
        # Temporary interaction state
        self.resize_handle = -1
        self.drag_start_img = (0, 0)
        self.drag_poly_offset: Optional[Tuple[float, float]] = None
        self.drag_vertex_idx: Optional[int] = None
        
        # UI lock state (prevents window resizing after first image load)
        self.locked = False

    def _create_toolbar(self) -> None:
        """Create the main toolbar with controls and status display."""
        toolbar = ttk.Frame(self)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=10, pady=6)
        
        # Primary action buttons
        ttk.Button(toolbar, text="Find TLOPO", command=self.find_tlopo).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Capture (F5)", command=self.capture_once).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(toolbar, text="Save", command=self.save_shapes).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(toolbar, text="Load", command=self.load_shapes).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(toolbar, text="Test Shapes", command=self.test_shapes_on_game).pack(side=tk.LEFT, padx=(8, 0))
        
        # Display options
        self.show_labels_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(toolbar, text="Show Labels", variable=self.show_labels_var, 
                       command=self.redraw).pack(side=tk.LEFT, padx=(8, 0))
        
        # Help text with keyboard shortcuts
        help_text = (" | Hotkeys: B=Box  P=Poly  Enter=Finish  R=Rename  Del=Delete  "
                    "Ctrl+Z=Undo  Ctrl+S=Save  Ctrl+O=Load  Ctrl+T=Test  Ctrl+E=Export")
        ttk.Label(toolbar, text=help_text).pack(side=tk.LEFT, padx=(12, 0))
        
        # Right-aligned controls
        ttk.Button(toolbar, text="Export (Ctrl+E)", command=self.export_norm).pack(side=tk.RIGHT, padx=(8, 0))
        
        # Status display
        self.status = tk.StringVar(value="Finding TLOPO window...")
        ttk.Label(toolbar, textvariable=self.status).pack(side=tk.RIGHT)

    def _create_canvas_area(self) -> None:
        """Create the scrollable canvas area for image display and shape editing."""
        # Container frame for canvas and scrollbars
        canvas_wrapper = ttk.Frame(self)
        canvas_wrapper.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbars
        self.hbar = ttk.Scrollbar(canvas_wrapper, orient=tk.HORIZONTAL)
        self.vbar = ttk.Scrollbar(canvas_wrapper, orient=tk.VERTICAL)
        
        # Main canvas with dark background
        self.canvas = tk.Canvas(canvas_wrapper, bg="#111", highlightthickness=0,
                               xscrollcommand=self.hbar.set, yscrollcommand=self.vbar.set)
        
        # Link scrollbars to canvas
        self.hbar.config(command=self.canvas.xview)
        self.vbar.config(command=self.canvas.yview)
        
        # Grid layout for canvas and scrollbars
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vbar.grid(row=0, column=1, sticky="ns")
        self.hbar.grid(row=1, column=0, sticky="ew")
        
        # Configure grid weights for responsive layout
        canvas_wrapper.rowconfigure(0, weight=1)
        canvas_wrapper.columnconfigure(0, weight=1)

    def _setup_event_bindings(self) -> None:
        """Configure all mouse and keyboard event handlers."""
        # Mouse events for canvas interaction
        self.canvas.bind("<ButtonPress-1>", self.on_left_click)
        self.canvas.bind("<B1-Motion>", self.on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_release)
        self.canvas.bind("<Button-3>", self.on_right_click)
        
        # Middle mouse button for panning
        self.canvas.bind("<ButtonPress-2>", self.start_pan)
        self.canvas.bind("<B2-Motion>", self.do_pan)
        
        # Mouse wheel zoom (Windows)
        self.canvas.bind("<MouseWheel>", self.on_wheel)
        # Mouse wheel zoom (Linux)
        self.canvas.bind("<Button-4>", lambda e: self.zoom_at(e.x, e.y, ZOOM_STEP))
        self.canvas.bind("<Button-5>", lambda e: self.zoom_at(e.x, e.y, 1/ZOOM_STEP))
        
        # Keyboard shortcuts for zoom
        self.bind("<Control-plus>", lambda e: self.zoom_by(ZOOM_STEP))
        self.bind("<Control-minus>", lambda e: self.zoom_by(1/ZOOM_STEP))
        self.bind("<Control-Key-0>", lambda e: self.zoom_reset())
        
        # File operations
        self.bind("<Control-e>", lambda e: self.export_norm())
        self.bind("<Control-s>", lambda e: self.save_shapes())
        self.bind("<Control-o>", lambda e: self.load_shapes())
        self.bind("<Control-t>", lambda e: self.test_shapes_on_game())
        
        # Shape creation and editing
        self.bind("<b>", lambda e: self.start_new_box())
        self.bind("<p>", lambda e: self.start_new_poly())
        self.bind("<Return>", lambda e: self.finish_polygon())
        self.bind("<r>", lambda e: self.rename_selected())
        self.bind("<Delete>", lambda e: self.delete_selected())
        self.bind("<BackSpace>", lambda e: self.delete_selected())
        self.bind("<Control-z>", lambda e: self.undo_last_vertex())
        
        # Capture shortcut
        self.bind("<F5>", lambda e: self.capture_once())

    # ============================================================================
    # LOGGING AND STATUS MANAGEMENT
    # ============================================================================

    def _log(self, message: str) -> None:
        """
        Update status display and print to console.
        
        Args:
            message: Status message to display
        """
        self.status.set(message)
        print(message)

    # ============================================================================
    # AUTO-INITIALIZATION AND WINDOW DETECTION
    # ============================================================================

    def auto_initialize(self) -> None:
        """
        Automatically find and capture TLOPO window on startup.
        
        Called once after the main window is created to attempt automatic
        detection and capture of the game window for immediate use.
        """
        if self.cap.find_window():
            self.capture_once()
        else:
            self.status.set("TLOPO window not found. Click 'Find TLOPO' when game is running.")

    def find_tlopo(self) -> None:
        """
        Manually trigger TLOPO window detection.
        
        Searches for visible TLOPO windows and reports results to the user.
        Updates internal capture state if successful.
        """
        if self.cap.find_window():
            if self.cap.client_rect is not None:
                left, top, right, bottom = self.cap.client_rect
                width, height = right - left, bottom - top
                self._log(f"TLOPO client: {width}×{height} at ({left},{top})")
        else:
            messagebox.showwarning("TLOPO", "Could not find a visible TLOPO window.")

    def capture_once(self) -> None:
        """
        Capture a single screenshot of the TLOPO window.
        
        Performs immediate screen capture and loads the result for shape tracing.
        Handles capture failures gracefully with user feedback.
        """
        captured_image = self.cap.grab()
        if captured_image is None:
            self._log("Capture failed. Make sure the game is visible (not minimized).")
            return
        
        self._display_image(captured_image)

    # ============================================================================
    # IMAGE DISPLAY AND WINDOW MANAGEMENT
    # ============================================================================

    def _display_image(self, img: Image.Image) -> None:
        """
        Display a new image in the canvas and configure window layout.
        
        Args:
            img: PIL Image to display
            
        Note:
            Preserves existing shapes and resets zoom to 100%.
            Locks window size after first image to prevent layout issues.
        """
        # Store image and reset display state
        self.img = img
        self.W, self.H = img.size
        self.zoom = 1.0
        
        # Create Tkinter-compatible image
        self.tk_img = ImageTk.PhotoImage(self.img)
        
        # Clear canvas and display new image
        self.canvas.delete("all")
        self.canvas.configure(width=self.W, height=self.H)
        self.img_item = self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)
        self.canvas.config(scrollregion=(0, 0, self.W, self.H))
        
        # Configure window size on first image load
        if not self.locked:
            self._configure_window_size()
            self.locked = True
        
        # Redraw all existing shapes
        self.redraw()

    def _configure_window_size(self) -> None:
        """
        Set optimal window size based on image dimensions and UI elements.
        
        Calculates required space for canvas, scrollbars, and toolbar,
        then sets window size and constraints accordingly.
        """
        self.update_idletasks()
        
        # Calculate component dimensions
        toolbar_height = self.winfo_children()[0].winfo_height()
        canvas_width = self.canvas.winfo_reqwidth()
        canvas_height = self.canvas.winfo_reqheight()
        scrollbar_width = self.vbar.winfo_reqwidth()
        scrollbar_height = self.hbar.winfo_reqheight()
        
        # Calculate total internal dimensions
        inner_width = canvas_width + scrollbar_width
        inner_height = canvas_height + scrollbar_height + toolbar_height
        
        # Account for window decorations
        decoration_width = self.winfo_rootx() - self.winfo_x()
        decoration_height = self.winfo_rooty() - self.winfo_y()
        
        # Calculate total window dimensions
        total_width = inner_width + decoration_width * 2
        total_height = inner_height + decoration_height + decoration_width
        
        # Apply window size and constraints
        self.geometry(f"{total_width}x{total_height}")
        self.minsize(total_width, total_height)
        self.maxsize(total_width, total_height)
        self.resizable(False, False)

    # ============================================================================
    # ZOOM AND PAN CONTROLS
    # ============================================================================

    def on_wheel(self, event) -> None:
        """
        Handle mouse wheel zoom at cursor position.
        
        Args:
            event: Mouse wheel event with delta information
        """
        zoom_factor = ZOOM_STEP if event.delta > 0 else 1 / ZOOM_STEP
        self.zoom_at(event.x, event.y, zoom_factor)

    def zoom_by(self, factor: float) -> None:
        """
        Zoom by the specified factor centered on the canvas.
        
        Args:
            factor: Zoom multiplier (>1 to zoom in, <1 to zoom out)
        """
        center_x = self.canvas.canvasx(self.canvas.winfo_width() // 2)
        center_y = self.canvas.canvasy(self.canvas.winfo_height() // 2)
        self.zoom_at(center_x, center_y, factor)

    def zoom_reset(self) -> None:
        """Reset zoom level to 100% (1:1 pixel ratio)."""
        if not self.img:
            return
        self.zoom = 1.0
        self.redraw()

    def zoom_at(self, canvas_x: float, canvas_y: float, factor: float) -> None:
        """
        Zoom by the specified factor at a specific canvas position.
        
        Args:
            canvas_x: X coordinate in canvas space to zoom towards
            canvas_y: Y coordinate in canvas space to zoom towards  
            factor: Zoom multiplier
            
        Note:
            Maintains the point under the cursor at the same visual position
            while changing the zoom level.
        """
        if not self.img:
            return
            
        # Calculate new zoom level within constraints
        new_zoom = max(ZOOM_MIN, min(ZOOM_MAX, self.zoom * factor))
        if abs(new_zoom - self.zoom) < 1e-6:
            return  # No significant change
        
        # Calculate image coordinates of the zoom center
        img_x = self.canvas.canvasx(canvas_x) / self.zoom
        img_y = self.canvas.canvasy(canvas_y) / self.zoom
        
        # Apply new zoom level
        self.zoom = new_zoom
        self.redraw()
        
        # Adjust scroll position to keep the zoom center stationary
        new_canvas_x = img_x * self.zoom
        new_canvas_y = img_y * self.zoom
        
        delta_x = new_canvas_x - canvas_x
        delta_y = new_canvas_y - canvas_y
        
        # Update scroll position
        scroll_region_width = self.W * self.zoom
        scroll_region_height = self.H * self.zoom
        
        new_scroll_x = (self.canvas.canvasx(0) + delta_x) / scroll_region_width
        new_scroll_y = (self.canvas.canvasy(0) + delta_y) / scroll_region_height
        
        self.canvas.xview_moveto(new_scroll_x)
        self.canvas.yview_moveto(new_scroll_y)

    def start_pan(self, event) -> None:
        """
        Initialize canvas panning with middle mouse button.
        
        Args:
            event: Mouse button press event
        """
        self.canvas.scan_mark(event.x, event.y)

    def do_pan(self, event) -> None:
        """
        Continue canvas panning during middle mouse drag.
        
        Args:
            event: Mouse motion event
        """
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    # ============================================================================
    # COORDINATE TRANSFORMATION UTILITIES
    # ============================================================================

    def canvas_to_img(self, canvas_x: float, canvas_y: float) -> Tuple[float, float]:
        """
        Convert canvas coordinates to image pixel coordinates.
        
        Args:
            canvas_x: X coordinate in canvas space
            canvas_y: Y coordinate in canvas space
            
        Returns:
            Tuple[float, float]: (x, y) coordinates in image pixel space
            
        Note:
            Accounts for current zoom level and scroll position.
            Clamps coordinates to image boundaries.
        """
        # Convert to image space accounting for zoom and scroll
        img_x = self.canvas.canvasx(canvas_x) / self.zoom
        img_y = self.canvas.canvasy(canvas_y) / self.zoom
        
        # Clamp to image boundaries
        img_x = max(0, min(self.W - 1, img_x))
        img_y = max(0, min(self.H - 1, img_y))
        
        return img_x, img_y

    def img_to_canvas(self, img_x: float, img_y: float) -> Tuple[float, float]:
        """
        Convert image pixel coordinates to canvas coordinates.
        
        Args:
            img_x: X coordinate in image pixel space
            img_y: Y coordinate in image pixel space
            
        Returns:
            Tuple[float, float]: (x, y) coordinates in canvas space
        """
        return img_x * self.zoom, img_y * self.zoom

    # ============================================================================
    # SHAPE CREATION COMMANDS
    # ============================================================================

    def start_new_box(self) -> None:
        """
        Begin interactive box creation mode.
        
        Switches to drawing_box mode where the next mouse click-drag
        will create a new rectangular shape.
        """
        if not self.img:
            return
            
        self.mode = "drawing_box"
        self.selected = None
        self.status.set("Drag to create a new box…")

    def start_new_poly(self) -> None:
        """
        Begin interactive polygon creation mode.
        
        Creates a new empty polygon and switches to drawing_poly mode
        where subsequent clicks add vertices.
        """
        if not self.img:
            return
            
        self.mode = "drawing_poly"
        
        # Create new polygon with unique label and color
        new_polygon = PolyShape(
            pts=[], 
            closed=False, 
            label=f"Poly{self._next_poly_index()}", 
            color=self._next_color()
        )
        
        self.shapes.append(new_polygon)
        self.selected = new_polygon
        
        self.status.set("Click to add vertices. Right-click to undo last vertex. Press Enter when done to close polygon.")

    # ============================================================================
    # HIT TESTING AND INTERACTION DETECTION
    # ============================================================================

    def _get_box_handle_points(self, box: BoxShape) -> List[Tuple[float, float]]:
        """
        Calculate positions of all resize handles for a box shape.
        
        Args:
            box: Box shape to calculate handles for
            
        Returns:
            List[Tuple[float, float]]: Handle positions in image coordinates
            
        Note:
            Returns 8 handles: 4 corners + 4 edge midpoints
        """
        x0, y0, x1, y1 = box.as_tuple()
        x_mid = (x0 + x1) / 2
        y_mid = (y0 + y1) / 2
        
        return [
            (x0, y0),      # Top-left corner
            (x_mid, y0),   # Top edge center  
            (x1, y0),      # Top-right corner
            (x0, y_mid),   # Left edge center
            (x1, y_mid),   # Right edge center
            (x0, y1),      # Bottom-left corner
            (x_mid, y1),   # Bottom edge center
            (x1, y1)       # Bottom-right corner
        ]

    def _hit_test_box_handle(self, box: BoxShape, screen_x: float, screen_y: float) -> int:
        """
        Test if a screen coordinate hits any box resize handle or edge.
        
        Args:
            box: Box shape to test against
            screen_x: X coordinate in screen/canvas space
            screen_y: Y coordinate in screen/canvas space
            
        Returns:
            int: Handle index (0-7 for corners/edges, 8-11 for edge drags, -1 for no hit)
        """
        # Test corner and edge center handles first (highest priority)
        for i, (handle_x, handle_y) in enumerate(self._get_box_handle_points(box)):
            canvas_x, canvas_y = self.img_to_canvas(handle_x, handle_y)
            if (abs(screen_x - canvas_x) <= HANDLE_R * 1.5 and 
                abs(screen_y - canvas_y) <= HANDLE_R * 1.5):
                return i
        
        # Test edge drag areas (for resizing along edges)
        x0, y0, x1, y1 = box.as_tuple()
        x0_canvas, y0_canvas = self.img_to_canvas(x0, y0)
        x1_canvas, y1_canvas = self.img_to_canvas(x1, y1)
        
        # Top edge
        if (abs(screen_y - y0_canvas) <= EDGE_GRAB_PX and 
            x0_canvas <= screen_x <= x1_canvas):
            return 8
        
        # Right edge  
        if (abs(screen_x - x1_canvas) <= EDGE_GRAB_PX and 
            y0_canvas <= screen_y <= y1_canvas):
            return 9
        
        # Bottom edge
        if (abs(screen_y - y1_canvas) <= EDGE_GRAB_PX and 
            x0_canvas <= screen_x <= x1_canvas):
            return 10
        
        # Left edge
        if (abs(screen_x - x0_canvas) <= EDGE_GRAB_PX and 
            y0_canvas <= screen_y <= y1_canvas):
            return 11
        
        return -1  # No handle hit

    def _point_in_box(self, box: BoxShape, screen_x: float, screen_y: float) -> bool:
        """
        Test if a screen coordinate is inside a box shape.
        
        Args:
            box: Box shape to test against
            screen_x: X coordinate in screen/canvas space
            screen_y: Y coordinate in screen/canvas space
            
        Returns:
            bool: True if point is inside the box
        """
        x0, y0, x1, y1 = box.as_tuple()
        x0_canvas, y0_canvas = self.img_to_canvas(x0, y0)
        x1_canvas, y1_canvas = self.img_to_canvas(x1, y1)
        
        # Ensure coordinates are ordered correctly for hit testing
        min_x, max_x = min(x0_canvas, x1_canvas), max(x0_canvas, x1_canvas)
        min_y, max_y = min(y0_canvas, y1_canvas), max(y0_canvas, y1_canvas)
        
        return min_x <= screen_x <= max_x and min_y <= screen_y <= max_y

    def _find_nearest_polygon_vertex(self, poly: PolyShape, screen_x: float, screen_y: float) -> Optional[int]:
        """
        Find the nearest polygon vertex to a screen coordinate.
        
        Args:
            poly: Polygon shape to test against
            screen_x: X coordinate in screen/canvas space
            screen_y: Y coordinate in screen/canvas space
            
        Returns:
            Optional[int]: Index of nearest vertex within grab distance, or None
        """
        nearest_vertex = None
        min_distance = float('inf')
        
        for i, (vertex_x, vertex_y) in enumerate(poly.pts):
            canvas_x, canvas_y = self.img_to_canvas(vertex_x, vertex_y)
            distance = math.hypot(screen_x - canvas_x, screen_y - canvas_y)
            
            if distance < min_distance and distance <= HANDLE_R * 1.7:
                nearest_vertex = i
                min_distance = distance
        
        return nearest_vertex

    def _find_nearest_polygon_edge(self, poly: PolyShape, screen_x: float, screen_y: float) -> Optional[int]:
        """
        Find the nearest polygon edge to a screen coordinate.
        
        Args:
            poly: Polygon shape to test against
            screen_x: X coordinate in screen/canvas space
            screen_y: Y coordinate in screen/canvas space
            
        Returns:
            Optional[int]: Index of nearest edge within snap distance, or None
            
        Note:
            Uses point-to-line distance calculation with proper projection.
        """
        points = poly.pts
        num_points = len(points)
        
        if num_points < 2:
            return None
        
        nearest_edge = None
        min_distance = float('inf')
        
        # Check each edge of the polygon
        edge_count = num_points if poly.closed else num_points - 1
        
        for i in range(edge_count):
            # Get edge endpoints
            x1, y1 = points[i]
            if poly.closed:
                x2, y2 = points[(i + 1) % num_points]
            elif i < num_points - 1:
                x2, y2 = points[i + 1]
            else:
                break  # Open polygon end
            
            # Convert to canvas coordinates
            x1_canvas, y1_canvas = self.img_to_canvas(x1, y1)
            x2_canvas, y2_canvas = self.img_to_canvas(x2, y2)
            
            # Calculate point-to-line distance using vector projection
            edge_vector_x = x2_canvas - x1_canvas
            edge_vector_y = y2_canvas - y1_canvas
            point_vector_x = screen_x - x1_canvas
            point_vector_y = screen_y - y1_canvas
            
            edge_length_squared = edge_vector_x * edge_vector_x + edge_vector_y * edge_vector_y
            
            if edge_length_squared == 0:  # Degenerate edge
                continue
            
            # Project point onto edge line and clamp to edge segment
            projection_t = max(0, min(1, (point_vector_x * edge_vector_x + point_vector_y * edge_vector_y) / edge_length_squared))
            
            # Find closest point on edge segment
            closest_x = x1_canvas + projection_t * edge_vector_x
            closest_y = y1_canvas + projection_t * edge_vector_y
            
            # Calculate distance to closest point
            distance = math.hypot(screen_x - closest_x, screen_y - closest_y)
            
            if distance < min_distance and distance <= POLY_EDGE_SNAP:
                nearest_edge = i
                min_distance = distance
        
        return nearest_edge

    def _point_in_polygon(self, poly: PolyShape, screen_x: float, screen_y: float) -> bool:
        """
        Test if a screen coordinate is inside a closed polygon using ray casting.
        
        Args:
            poly: Polygon shape to test against
            screen_x: X coordinate in screen/canvas space
            screen_y: Y coordinate in screen/canvas space
            
        Returns:
            bool: True if point is inside the polygon
            
        Note:
            Only works for closed polygons with at least 3 vertices.
            Uses the ray casting algorithm in image coordinate space.
        """
        if not poly.closed or len(poly.pts) < 3:
            return False
        
        # Convert screen coordinates to image space for testing
        test_x = self.canvas.canvasx(screen_x) / self.zoom
        test_y = self.canvas.canvasy(screen_y) / self.zoom
        
        # Ray casting algorithm
        inside = False
        points = poly.pts
        num_points = len(points)
        
        j = num_points - 1  # Last vertex
        
        for i in range(num_points):
            vertex_i_x, vertex_i_y = points[i]
            vertex_j_x, vertex_j_y = points[j]
            
            # Check if ray crosses this edge
            if ((vertex_i_y > test_y) != (vertex_j_y > test_y) and 
                (test_x < (vertex_j_x - vertex_i_x) * (test_y - vertex_i_y) / (vertex_j_y - vertex_i_y + 1e-6) + vertex_i_x)):
                inside = not inside
            
            j = i
        
        return inside

    def _find_shape_at_position(self, screen_x: float, screen_y: float) -> Optional[Shape]:
        """
        Find the topmost shape at a given screen position.
        
        Args:
            screen_x: X coordinate in screen/canvas space
            screen_y: Y coordinate in screen/canvas space
            
        Returns:
            Optional[Shape]: The topmost shape at the position, or None
            
        Note:
            Searches shapes in reverse order (most recently created first).
        """
        for shape in reversed(self.shapes):
            if isinstance(shape, BoxShape):
                if self._point_in_box(shape, screen_x, screen_y):
                    return shape
            elif isinstance(shape, PolyShape):
                if self._point_in_polygon(shape, screen_x, screen_y):
                    return shape
        
        return None

    # ============================================================================
    # MOUSE EVENT HANDLERS
    # ============================================================================

    def on_left_click(self, event) -> None:
        """
        Handle left mouse button press for shape creation and selection.
        
        Args:
            event: Mouse button press event
            
        Note:
            Behavior depends on current mode:
            - drawing_box: Start new box creation
            - drawing_poly: Add vertex to current polygon
            - idle: Select shape or start interaction
        """
        if not self.img:
            return
        
        screen_x, screen_y = event.x, event.y
        img_x, img_y = self.canvas_to_img(screen_x, screen_y)

        if self.mode == "drawing_box":
            # Create new box starting at click position
            new_box = BoxShape(
                img_x, img_y, img_x, img_y, 
                label=f"Box{self._next_box_index()}", 
                color=self._next_color()
            )
            
            self.shapes.append(new_box)
            self.selected = new_box
            self.mode = "resizing"
            self.resize_handle = 7  # Bottom-right corner for drag-to-size
            self.redraw()
            return

        if self.mode == "drawing_poly":
            if isinstance(self.selected, PolyShape):
                # Handle Shift+click for edge vertex insertion
                if (event.state & 0x0001) and len(self.selected.pts) >= 2:
                    edge_index = self._find_nearest_polygon_edge(self.selected, screen_x, screen_y)
                    if edge_index is not None:
                        # Insert vertex at the specified edge
                        self.selected.pts.insert(edge_index + 1, (img_x, img_y))
                    else:
                        # Regular vertex addition
                        self.selected.pts.append((img_x, img_y))
                else:
                    # Regular vertex addition
                    self.selected.pts.append((img_x, img_y))
                
                self.redraw()
            return

        # Normal edit mode - handle shape selection and interaction
        clicked_shape = self._find_shape_at_position(screen_x, screen_y)
        
        if isinstance(clicked_shape, BoxShape):
            self.selected = clicked_shape
            
            # Check if click is on a resize handle
            handle_index = self._hit_test_box_handle(clicked_shape, screen_x, screen_y)
            
            if handle_index >= 0:
                # Start resize operation
                self.mode = "resizing"
                self.resize_handle = handle_index
            else:
                # Start move operation
                self.mode = "moving"
                self.drag_start_img = (img_x, img_y)
                
        elif isinstance(clicked_shape, PolyShape):
            self.selected = clicked_shape
            
            # Check if click is on a vertex handle
            vertex_index = self._find_nearest_polygon_vertex(clicked_shape, screen_x, screen_y)
            
            if vertex_index is not None:
                # Start vertex drag operation
                self.mode = "dragging_vertex"
                self.drag_vertex_idx = vertex_index
            else:
                # Handle Shift+click for edge vertex insertion
                if event.state & 0x0001:
                    edge_index = self._find_nearest_polygon_edge(clicked_shape, screen_x, screen_y)
                    if edge_index is not None:
                        clicked_shape.pts.insert(edge_index + 1, (img_x, img_y))
                        self.redraw()
                        return
                
                # Start polygon move operation
                self.mode = "moving"
                self.drag_poly_offset = (img_x, img_y)
        else:
            # Click on empty space - deselect
            self.selected = None
            self.mode = "idle"
        
        self.redraw()

    def on_left_drag(self, event) -> None:
        """
        Handle left mouse button drag for shape manipulation.
        
        Args:
            event: Mouse motion event
            
        Note:
            Behavior depends on current mode and selected shape type.
        """
        if not self.img or not self.selected:
            return
        
        img_x, img_y = self.canvas_to_img(event.x, event.y)
        
        if isinstance(self.selected, BoxShape):
            if self.mode == "moving":
                # Move entire box by drag delta
                start_x, start_y = self.drag_start_img
                delta_x, delta_y = img_x - start_x, img_y - start_y
                self.drag_start_img = (img_x, img_y)
                
                self.selected.x0 += delta_x
                self.selected.x1 += delta_x
                self.selected.y0 += delta_y
                self.selected.y1 += delta_y
                
                self._clamp_box_to_image(self.selected)
                self.redraw()
                
            elif self.mode == "resizing":
                # Resize box using the active handle
                self._apply_box_resize(self.selected, img_x, img_y, self.resize_handle)
                self._clamp_box_to_image(self.selected)
                self.redraw()
                
        elif isinstance(self.selected, PolyShape):
            if self.mode == "dragging_vertex" and self.drag_vertex_idx is not None:
                # Move individual vertex
                self.selected.pts[self.drag_vertex_idx] = (img_x, img_y)
                self.redraw()
                
            elif self.mode == "moving" and self.drag_poly_offset is not None:
                # Move entire polygon by drag delta
                start_x, start_y = self.drag_poly_offset
                delta_x, delta_y = img_x - start_x, img_y - start_y
                self.drag_poly_offset = (img_x, img_y)
                
                # Apply delta to all vertices
                self.selected.pts = [(x + delta_x, y + delta_y) for (x, y) in self.selected.pts]
                self._clamp_polygon_to_image(self.selected)
                self.redraw()

    def on_left_release(self, event) -> None:
        """
        Handle left mouse button release to end interactions.
        
        Args:
            event: Mouse button release event
            
        Note:
            Preserves drawing_poly mode to continue polygon creation.
        """
        # Don't reset mode if we're still drawing a polygon
        if self.mode != "drawing_poly":
            self.mode = "idle"
        
        # Clear temporary interaction state
        self.resize_handle = -1
        self.drag_vertex_idx = None
        self.drag_poly_offset = None

    def on_right_click(self, event) -> None:
        """
        Handle right mouse button press for polygon editing.
        
        Args:
            event: Mouse button press event
            
        Note:
            - During polygon drawing: Remove last vertex
            - On completed polygon: Remove vertex under cursor
        """
        # Handle right-click during polygon drawing (undo last vertex)
        if self.mode == "drawing_poly" and isinstance(self.selected, PolyShape):
            if len(self.selected.pts) > 0:
                self.selected.pts.pop()
                self.redraw()
                
                if len(self.selected.pts) == 0:
                    # No vertices left - cancel polygon creation
                    self.shapes.remove(self.selected)
                    self.selected = None
                    self.mode = "idle"
                    self.status.set("Polygon creation cancelled.")
            return
        
        # Handle right-click on completed polygon vertex (delete vertex)
        if not isinstance(self.selected, PolyShape):
            return
        
        vertex_index = self._find_nearest_polygon_vertex(self.selected, event.x, event.y)
        if vertex_index is not None:
            self.selected.pts.pop(vertex_index)
            self.redraw()

    # ============================================================================
    # BOX SHAPE MANIPULATION HELPERS
    # ============================================================================

    def _apply_box_resize(self, box: BoxShape, img_x: float, img_y: float, handle_index: int) -> None:
        """
        Apply resize operation to a box shape based on the active handle.
        
        Args:
            box: Box shape to resize
            img_x: New X coordinate in image space
            img_y: New Y coordinate in image space
            handle_index: Index of the resize handle being dragged
            
        Note:
            Handle indices correspond to different resize behaviors:
            0-7: Corner and edge center handles
            8-11: Edge drag handles
        """
        if handle_index == 0:    # Top-left corner
            box.x0 = img_x
            box.y0 = img_y
        elif handle_index == 1:  # Top edge center
            box.y0 = img_y
        elif handle_index == 2:  # Top-right corner
            box.x1 = img_x
            box.y0 = img_y
        elif handle_index == 3:  # Left edge center
            box.x0 = img_x
        elif handle_index == 4:  # Right edge center
            box.x1 = img_x
        elif handle_index == 5:  # Bottom-left corner
            box.x0 = img_x
            box.y1 = img_y
        elif handle_index == 6:  # Bottom edge center
            box.y1 = img_y
        elif handle_index == 7:  # Bottom-right corner
            box.x1 = img_x
            box.y1 = img_y
        elif handle_index == 8:  # Top edge drag
            box.y0 = img_y
        elif handle_index == 9:  # Right edge drag
            box.x1 = img_x
        elif handle_index == 10: # Bottom edge drag
            box.y1 = img_y
        elif handle_index == 11: # Left edge drag
            box.x0 = img_x

    def _clamp_box_to_image(self, box: BoxShape) -> None:
        """
        Clamp box coordinates to image boundaries.
        
        Args:
            box: Box shape to clamp
        """
        box.x0 = max(0, min(self.W - 1, box.x0))
        box.x1 = max(0, min(self.W - 1, box.x1))
        box.y0 = max(0, min(self.H - 1, box.y0))
        box.y1 = max(0, min(self.H - 1, box.y1))

    def _clamp_polygon_to_image(self, polygon: PolyShape) -> None:
        """
        Clamp polygon vertices to image boundaries.
        
        Args:
            polygon: Polygon shape to clamp
        """
        polygon.pts = [
            (max(0, min(self.W - 1, x)), max(0, min(self.H - 1, y))) 
            for (x, y) in polygon.pts
        ]

    # ============================================================================
    # SHAPE RENDERING AND DISPLAY
    # ============================================================================

    def redraw(self) -> None:
        """
        Redraw the entire canvas with current image and all shapes.
        
        Handles zoom level changes, creates appropriate image scaling,
        and renders all shapes with proper selection highlighting.
        """
        if not self.img:
            return
        
        # Calculate display dimensions for current zoom level
        display_width = int(round(self.W * self.zoom))
        display_height = int(round(self.H * self.zoom))
        
        # Create appropriately scaled image
        if abs(self.zoom - 1.0) < 1e-6:
            # No scaling needed - use original image
            self.tk_img = ImageTk.PhotoImage(self.img)
        else:
            # Scale image to current zoom level
            scaled_img = self.img.resize((display_width, display_height), RESAMPLE)
            self.tk_img = ImageTk.PhotoImage(scaled_img)
        
        # Clear canvas and display scaled image
        self.canvas.delete("all")
        self.img_item = self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)
        self.canvas.config(scrollregion=(0, 0, display_width, display_height))
        
        # Draw all shapes
        for shape in self.shapes:
            is_selected = (shape is self.selected)
            
            if isinstance(shape, BoxShape):
                self._draw_box_shape(shape, is_selected)
            elif isinstance(shape, PolyShape):
                self._draw_polygon_shape(shape, is_selected)

    def _brighten_color(self, hex_color: str) -> str:
        """
        Create a brighter version of a hex color for selection highlighting.
        
        Args:
            hex_color: Original color in hex format (#RRGGBB)
            
        Returns:
            str: Brightened color in hex format
        """
        hex_color = hex_color.lstrip('#')
        
        # Parse RGB components and brighten
        red = min(255, int(hex_color[0:2], 16) + 40)
        green = min(255, int(hex_color[2:4], 16) + 40)
        blue = min(255, int(hex_color[4:6], 16) + 40)
        
        return f"#{red:02x}{green:02x}{blue:02x}"

    def _draw_box_shape(self, box: BoxShape, selected: bool = False) -> None:
        """
        Draw a box shape on the canvas with optional selection highlighting.
        
        Args:
            box: Box shape to draw
            selected: Whether to show selection highlighting
        """
        # Get normalized coordinates
        x0, y0, x1, y1 = box.as_tuple()
        
        # Convert to canvas coordinates
        x0_canvas, y0_canvas = self.img_to_canvas(x0, y0)
        x1_canvas, y1_canvas = self.img_to_canvas(x1, y1)
        
        # Choose color (brighter if selected)
        color = self._brighten_color(box.color) if selected else box.color
        
        # Draw rectangle outline
        self.canvas.create_rectangle(x0_canvas, y0_canvas, x1_canvas, y1_canvas, 
                                   outline=color, width=3)
        
        # Draw label if enabled
        if self.show_labels_var.get():
            self.canvas.create_text(x0_canvas + 8, y0_canvas - 12, anchor="w",
                                  text=box.label, fill=color, font=("Segoe UI", 12, "bold"))
        
        # Draw resize handles if selected
        if selected:
            for handle_x, handle_y in self._get_box_handle_points(box):
                canvas_x, canvas_y = self.img_to_canvas(handle_x, handle_y)
                self.canvas.create_oval(canvas_x - HANDLE_R, canvas_y - HANDLE_R,
                                      canvas_x + HANDLE_R, canvas_y + HANDLE_R,
                                      fill=color, outline="#111")

    def _draw_polygon_shape(self, polygon: PolyShape, selected: bool = False) -> None:
        """
        Draw a polygon shape on the canvas with optional selection highlighting.
        
        Args:
            polygon: Polygon shape to draw
            selected: Whether to show selection highlighting
        """
        # Draw edges between consecutive vertices
        if len(polygon.pts) >= 2:
            for i in range(len(polygon.pts) - 1):
                x1, y1 = self.img_to_canvas(*polygon.pts[i])
                x2, y2 = self.img_to_canvas(*polygon.pts[i + 1])
                self.canvas.create_line(x1, y1, x2, y2, fill=polygon.color, width=3)
            
            # Draw closing edge for closed polygons
            if polygon.closed and len(polygon.pts) >= 3:
                x1, y1 = self.img_to_canvas(*polygon.pts[-1])
                x2, y2 = self.img_to_canvas(*polygon.pts[0])
                self.canvas.create_line(x1, y1, x2, y2, fill=polygon.color, width=3)
        
        # Draw vertex indicators
        for i, (vertex_x, vertex_y) in enumerate(polygon.pts):
            canvas_x, canvas_y = self.img_to_canvas(vertex_x, vertex_y)
            
            if selected and not polygon.closed:
                # Large handles for selected polygons being drawn
                self.canvas.create_oval(canvas_x - HANDLE_R, canvas_y - HANDLE_R,
                                      canvas_x + HANDLE_R, canvas_y + HANDLE_R,
                                      fill=polygon.color, outline="#111")
            elif selected and polygon.closed:
                # Small selection indicators for completed selected polygons
                self.canvas.create_oval(canvas_x - 3, canvas_y - 3, canvas_x + 3, canvas_y + 3, 
                                      fill=polygon.color, outline="#fff", width=1)
            elif not selected and not polygon.closed:
                # Small dots for unselected polygons being drawn
                self.canvas.create_oval(canvas_x - 3, canvas_y - 3, canvas_x + 3, canvas_y + 3, 
                                      fill=polygon.color, outline=polygon.color)
            # For closed unselected polygons, show no vertex markers
        
        # Draw polygon label
        if polygon.pts and self.show_labels_var.get():
            label_x, label_y = self.img_to_canvas(*polygon.pts[0])
            
            # Add status indicator for polygons being drawn
            status_text = ""
            if self.mode == "drawing_poly" and polygon is self.selected:
                status_text = " (drawing - press Enter to close)"
            
            self.canvas.create_text(label_x + 8, label_y - 24, anchor="w",
                                  text=f"{polygon.label}{status_text}",
                                  fill=polygon.color, font=("Segoe UI", 12, "bold"))

    # ============================================================================
    # POLYGON COMPLETION AND EDITING COMMANDS
    # ============================================================================

    def finish_polygon(self) -> None:
        """
        Complete the current polygon by closing it (triggered by Enter key).
        
        Closes the polygon if it has at least 3 vertices and prompts for
        final naming and categorization.
        """
        if self.mode == "drawing_poly" and isinstance(self.selected, PolyShape):
            if len(self.selected.pts) >= 3:
                # Close the polygon and finish drawing
                self.selected.closed = True
                self.mode = "idle"
                self._complete_polygon_creation()
                self.redraw()
            else:
                self.status.set("Need at least 3 vertices to close polygon.")

    def undo_last_vertex(self) -> None:
        """
        Remove the last vertex from the polygon being drawn (Ctrl+Z).
        
        Cancels polygon creation if no vertices remain.
        """
        if self.mode == "drawing_poly" and isinstance(self.selected, PolyShape):
            if len(self.selected.pts) > 0:
                self.selected.pts.pop()
                self.redraw()
                
                if len(self.selected.pts) == 0:
                    # No points left - cancel polygon creation
                    self.shapes.remove(self.selected)
                    self.selected = None
                    self.mode = "idle"
                    self.status.set("Polygon creation cancelled.")

    def _complete_polygon_creation(self) -> None:
        """
        Handle final steps of polygon creation including naming dialog.
        
        Prompts user for final polygon name and category assignment.
        """
        if isinstance(self.selected, PolyShape):
            current_label = self.selected.label
            current_category = getattr(self.selected, "category", "button")
            
            # Show rename dialog for final naming
            dialog = RenameDialog(self, current_label, current_category)
            self.wait_window(dialog)
            
            if dialog.result:
                label, category = dialog.result
                self.selected.label = label
                self.selected.category = category
            
            self.status.set(f"Polygon '{self.selected.label}' completed.")

    # ============================================================================
    # SHAPE MANAGEMENT COMMANDS
    # ============================================================================

    def rename_selected(self) -> None:
        """
        Open rename dialog for the currently selected shape (R key).
        
        Allows editing of both label and category for the selected shape.
        """
        if not self.selected:
            return
        
        current_label = getattr(self.selected, "label", "")
        current_category = getattr(self.selected, "category", "button")
        
        # Show rename dialog
        dialog = RenameDialog(self, current_label, current_category)
        self.wait_window(dialog)
        
        if dialog.result:
            label, category = dialog.result
            self.selected.label = label
            self.selected.category = category
            self.redraw()

    def delete_selected(self) -> None:
        """
        Delete the currently selected shape (Delete/Backspace keys).
        
        Removes the shape from the shapes list and clears selection.
        """
        if not self.selected:
            return
        
        try:
            self.shapes.remove(self.selected)
        except ValueError:
            pass  # Shape not in list (shouldn't happen)
        
        self.selected = None
        self.redraw()

    # ============================================================================
    # ASPECT RATIO AND COORDINATE TRANSFORMATION
    # ============================================================================

    def _calculate_aspect_ratio_transform(self, orig_width: int, orig_height: int, 
                                        current_width: int, current_height: int) -> Dict:
        """
        Calculate coordinate transformation for aspect ratio changes.
        
        When the game window changes aspect ratio, this function determines
        how to properly scale and offset coordinates to maintain correct
        relative positioning within the actual game content area.
        
        Args:
            orig_width: Original capture width
            orig_height: Original capture height  
            current_width: Current window width
            current_height: Current window height
            
        Returns:
            Dict: Transform parameters with scale_x, scale_y, offset_x, offset_y, method
        """
        original_aspect = orig_width / orig_height
        current_aspect = current_width / current_height
        
        # Check if aspect ratios are similar (within 1% tolerance)
        if abs(original_aspect - current_aspect) < 0.01:
            # Same aspect ratio - simple uniform scaling
            scale = min(current_width / orig_width, current_height / orig_height)
            return {
                'scale_x': scale,
                'scale_y': scale,
                'offset_x': (current_width - orig_width * scale) / 2,
                'offset_y': (current_height - orig_height * scale) / 2,
                'method': 'uniform_scale'
            }
        
        # Different aspect ratios - handle letterboxing/pillarboxing
        if current_aspect > original_aspect:
            # Current window is wider - likely has pillarbox (black bars on sides)
            # Scale based on height and center horizontally
            scale = current_height / orig_height
            scaled_width = orig_width * scale
            return {
                'scale_x': scale,
                'scale_y': scale,
                'offset_x': (current_width - scaled_width) / 2,
                'offset_y': 0,
                'method': 'pillarbox_compensation'
            }
        else:
            # Current window is taller - likely has letterbox (black bars on top/bottom)
            # Scale based on width and center vertically
            scale = current_width / orig_width
            scaled_height = orig_height * scale
            return {
                'scale_x': scale,
                'scale_y': scale,
                'offset_x': 0,
                'offset_y': (current_height - scaled_height) / 2,
                'method': 'letterbox_compensation'
            }

    # ============================================================================
    # FILE OPERATIONS (SAVE/LOAD)
    # ============================================================================

    def save_shapes(self) -> None:
        """
        Save all shapes to object_shapes.json in the configuration folder.
        
        Creates a comprehensive JSON file containing:
        - Image size information
        - Current game window size for reference
        - All shape data with coordinates and metadata
        """
        if not self.img:
            messagebox.showwarning("Save", "No image loaded to save shapes for.")
            return
        
        # Determine save location (configuration folder relative to project root)
        import os
        script_directory = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_directory)  # Go up from tools/ to project root
        configuration_directory = os.path.join(project_root, "configuration")
        save_filepath = os.path.join(configuration_directory, "object_shapes.json")
        
        # Get current game window size for reference
        current_game_size = None
        if self.cap.client_rect:
            left, top, right, bottom = self.cap.client_rect
            current_game_size = {"width": right - left, "height": bottom - top}
        
        # Prepare comprehensive save data
        save_data = {
            "captured_image_size": {"width": self.W, "height": self.H},
            "game_window_size": current_game_size,
            "shapes": []
        }
        
        # Convert all shapes to serializable format
        for shape in self.shapes:
            if isinstance(shape, BoxShape):
                save_data["shapes"].append({
                    "type": "box",
                    "label": shape.label,
                    "category": shape.category,
                    "color": shape.color,
                    "x0": shape.x0,
                    "y0": shape.y0,
                    "x1": shape.x1,
                    "y1": shape.y1
                })
            elif isinstance(shape, PolyShape):
                save_data["shapes"].append({
                    "type": "polygon",
                    "label": shape.label,
                    "category": shape.category,
                    "color": shape.color,
                    "closed": shape.closed,
                    "pts": shape.pts
                })
        
        # Write to file with error handling
        try:
            with open(save_filepath, 'w') as file:
                json.dump(save_data, file, indent=2)
            
            self.status.set(f"Saved {len(self.shapes)} shapes to configuration/object_shapes.json")
            messagebox.showinfo("Save Complete", 
                              f"Saved {len(self.shapes)} shapes to:\nconfiguration/object_shapes.json")
        except Exception as error:
            messagebox.showerror("Save Error", f"Could not save file:\n{error}")

    def load_shapes(self) -> None:
        """
        Load shapes from object_shapes.json with aspect-ratio-aware scaling.
        
        Loads saved shapes and applies appropriate coordinate transformations
        if the current image has different dimensions than the original.
        """
        # Look for save file in configuration folder relative to project root
        import os
        script_directory = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_directory)  # Go up from tools/ to project root
        configuration_directory = os.path.join(project_root, "configuration")
        load_filepath = os.path.join(configuration_directory, "object_shapes.json")
        
        if not os.path.exists(load_filepath):
            messagebox.showinfo("Load", "No object_shapes.json file found in configuration folder.")
            return
        
        try:
            # Load and parse save data
            with open(load_filepath, 'r') as file:
                data = json.load(file)
            
            # Clear existing shapes
            self.shapes.clear()
            self.selected = None
            
            # Calculate coordinate transformation if needed
            scale_x = scale_y = 1.0
            offset_x = offset_y = 0.0
            transform_method = "no_scaling"
            
            if self.img and "captured_image_size" in data:
                original_width = data["captured_image_size"]["width"]
                original_height = data["captured_image_size"]["height"]
                
                if original_width > 0 and original_height > 0:
                    transform = self._calculate_aspect_ratio_transform(
                        original_width, original_height, self.W, self.H
                    )
                    scale_x = transform['scale_x']
                    scale_y = transform['scale_y']
                    offset_x = transform['offset_x']
                    offset_y = transform['offset_y']
                    transform_method = transform['method']
            
            # Prepare scaling information for user feedback
            scaling_info = ""
            if abs(scale_x - 1.0) > 0.01 or abs(scale_y - 1.0) > 0.01:
                scaling_info = (f" (transform: {transform_method}, "
                              f"scale: {scale_x:.2f}, offset: {offset_x:.0f},{offset_y:.0f})")
            
            # Load and transform shapes
            for shape_data in data.get("shapes", []):
                if shape_data["type"] == "box":
                    # Create box with transformed coordinates
                    box = BoxShape(
                        x0=shape_data["x0"] * scale_x + offset_x,
                        y0=shape_data["y0"] * scale_y + offset_y,
                        x1=shape_data["x1"] * scale_x + offset_x,
                        y1=shape_data["y1"] * scale_y + offset_y,
                        label=shape_data["label"],
                        category=shape_data.get("category", "button"),  # Backward compatibility
                        color=shape_data["color"]
                    )
                    self.shapes.append(box)
                    
                elif shape_data["type"] == "polygon":
                    # Create polygon with transformed coordinates
                    transformed_points = [
                        (x * scale_x + offset_x, y * scale_y + offset_y) 
                        for x, y in shape_data["pts"]
                    ]
                    polygon = PolyShape(
                        pts=transformed_points,
                        closed=shape_data["closed"],
                        label=shape_data["label"],
                        category=shape_data.get("category", "button"),  # Backward compatibility
                        color=shape_data["color"]
                    )
                    self.shapes.append(polygon)
            
            # Update display and provide user feedback
            self.redraw()
            success_message = f"Loaded {len(self.shapes)} shapes from configuration/object_shapes.json{scaling_info}"
            self.status.set(success_message)
            messagebox.showinfo("Load Complete", success_message)
            
        except Exception as error:
            messagebox.showerror("Load Error", f"Could not load file:\n{error}")

    # ============================================================================
    # LIVE OVERLAY TESTING
    # ============================================================================

    def test_shapes_on_game(self) -> None:
        """
        Test traced shapes by overlaying them on the live game window.
        
        Creates a semi-transparent overlay window positioned exactly over
        the game window to verify shape accuracy and positioning.
        """
        if not self.shapes:
            messagebox.showwarning("Test Shapes", "No shapes to test. Load or create some shapes first.")
            return
        
        # Refresh window detection to get current game window size
        if not self.cap.find_window():
            messagebox.showwarning("Test Shapes", "TLOPO window not found. Make sure the game is running.")
            return
        
        # Get current game window dimensions
        if self.cap.client_rect:
            left, top, right, bottom = self.cap.client_rect
            current_width, current_height = right - left, bottom - top
        else:
            messagebox.showerror("Test Shapes", "Could not get game window dimensions.")
            return
        
        # Calculate coordinate transformation for current window size
        transform = self._calculate_aspect_ratio_transform(self.W, self.H, current_width, current_height)
        scale_x = transform['scale_x']
        scale_y = transform['scale_y']
        offset_x = transform['offset_x']
        offset_y = transform['offset_y']
        
        transform_info = f"Testing shapes on game window ({transform['method']}: scale {scale_x:.2f}, offset {offset_x:.0f},{offset_y:.0f})"
        self.status.set(transform_info)
        
        # Create semi-transparent overlay window
        overlay = tk.Toplevel(self)
        overlay.title("Shape Test Overlay - Press ESC to close")
        overlay.configure(bg='black')
        overlay.attributes('-topmost', True)    # Keep on top
        overlay.attributes('-alpha', 0.7)       # Semi-transparent
        overlay.overrideredirect(True)          # Remove window decorations
        
        # Position overlay exactly over the game window
        overlay.geometry(f"{current_width}x{current_height}+{left}+{top}")
        
        # Create canvas for drawing overlay shapes
        overlay_canvas = tk.Canvas(overlay, width=current_width, height=current_height,
                                 bg='black', highlightthickness=0)
        overlay_canvas.pack()
        
        # Draw all shapes scaled to current window size
        for shape in self.shapes:
            if isinstance(shape, BoxShape):
                # Transform box coordinates
                x0, y0, x1, y1 = shape.as_tuple()
                scaled_x0 = x0 * scale_x + offset_x
                scaled_y0 = y0 * scale_y + offset_y
                scaled_x1 = x1 * scale_x + offset_x
                scaled_y1 = y1 * scale_y + offset_y
                
                # Draw box outline
                overlay_canvas.create_rectangle(scaled_x0, scaled_y0, scaled_x1, scaled_y1,
                                              outline=shape.color, width=3, fill='')
                
                # Draw box label
                overlay_canvas.create_text(scaled_x0 + 8, scaled_y0 - 12, anchor="w",
                                         text=shape.label, fill=shape.color,
                                         font=("Segoe UI", 12, "bold"))
                
            elif isinstance(shape, PolyShape) and shape.closed:
                # Transform polygon coordinates
                scaled_points = []
                for x, y in shape.pts:
                    scaled_points.extend([x * scale_x + offset_x, y * scale_y + offset_y])
                
                # Draw polygon outline (need at least 3 points)
                if len(scaled_points) >= 6:
                    overlay_canvas.create_polygon(scaled_points, outline=shape.color,
                                                width=3, fill='', smooth=False)
                    
                    # Draw polygon label at first vertex
                    if shape.pts:
                        first_x, first_y = shape.pts[0]
                        label_x = first_x * scale_x + offset_x + 8
                        label_y = first_y * scale_y + offset_y - 12
                        overlay_canvas.create_text(label_x, label_y, anchor="w",
                                                 text=shape.label, fill=shape.color,
                                                 font=("Segoe UI", 12, "bold"))
        
        # Add instruction text
        overlay_canvas.create_text(current_width // 2, 30, anchor="center",
                                 text="Shape Test Overlay - Press ESC to close",
                                 fill="white", font=("Segoe UI", 14, "bold"))
        
        # Show transformation info if significant
        if (abs(scale_x - 1.0) > 0.01 or abs(scale_y - 1.0) > 0.01 or 
            abs(offset_x) > 1 or abs(offset_y) > 1):
            info_text = f"Transform: {transform['method']} (scale: {scale_x:.2f}, offset: {offset_x:.0f},{offset_y:.0f})"
            overlay_canvas.create_text(current_width // 2, 60, anchor="center",
                                     text=info_text, fill="yellow", font=("Segoe UI", 12))
        
        # Configure overlay close events
        def close_overlay(event=None):
            overlay.destroy()
            self.status.set("Shape test completed.")
        
        overlay.bind('<Escape>', close_overlay)
        overlay.bind('<Button-1>', close_overlay)  # Close on click
        overlay.focus_set()
        
        # Auto-close after 10 seconds
        overlay.after(10000, close_overlay)

    # ============================================================================
    # COORDINATE EXPORT FUNCTIONALITY
    # ============================================================================

    def export_norm(self) -> None:
        """
        Export all shapes as normalized coordinates for automation use.
        
        Generates both clipboard text (for quick use) and console JSON
        (for comprehensive data) with normalized coordinates suitable
        for automated clicking and interaction scripts.
        """
        if not self.img or not self.shapes:
            messagebox.showinfo("Export", "No shapes to export.")
            return
        
        image_width, image_height = self.W, self.H
        
        # Prepare export data structures
        export_lines = []  # For clipboard text
        export_data = {    # For JSON output
            "image_size": {"width": image_width, "height": image_height},
            "shapes": []
        }
        
        # Process each shape for export
        for shape in self.shapes:
            if isinstance(shape, BoxShape):
                # Get normalized box coordinates
                x0, y0, x1, y1 = shape.as_tuple()
                
                # Create variable-style export line
                variable_name = shape.label.lower().replace(' ', '_')
                coordinate_text = (f"{variable_name}_norm = "
                                 f"({int(round(x0))}/{image_width}, {int(round(y0))}/{image_height}, "
                                 f"{int(round(x1))}/{image_width}, {int(round(y1))}/{image_height})")
                export_lines.append(coordinate_text)
                
                # Add to structured data
                export_data["shapes"].append({
                    "type": "box",
                    "label": shape.label,
                    "category": shape.category,
                    "abs": [int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1))],
                    "norm": [round(x0/image_width, 6), round(y0/image_height, 6), 
                           round(x1/image_width, 6), round(y1/image_height, 6)]
                })
                
            elif isinstance(shape, PolyShape):
                # Get normalized polygon coordinates
                vertices_absolute = [(int(round(x)), int(round(y))) for (x, y) in shape.pts]
                vertices_normalized = [(round(x/image_width, 6), round(y/image_height, 6)) for (x, y) in shape.pts]
                
                # Create variable-style export line
                variable_name = shape.label.lower().replace(' ', '_')
                coordinate_tuples = ", ".join([f"({x}/{image_width}, {y}/{image_height})" 
                                             for (x, y) in vertices_absolute])
                export_lines.append(f"{variable_name}_poly_norm = [{coordinate_tuples}]")
                
                # Add to structured data
                export_data["shapes"].append({
                    "type": "polygon",
                    "label": shape.label,
                    "category": shape.category,
                    "closed": shape.closed,
                    "abs": vertices_absolute,
                    "norm": vertices_normalized
                })
        
        # Export to clipboard for immediate use
        export_text = "\n".join(export_lines)
        self.clipboard_clear()
        self.clipboard_append(export_text)
        self.update()
        
        # Display export results
        messagebox.showinfo("Exported (copied to clipboard)", export_text)
        
        # Print comprehensive JSON to console for advanced use
        print(json.dumps(export_data, indent=2))

    # ============================================================================
    # UTILITY FUNCTIONS
    # ============================================================================

    def _next_box_index(self) -> int:
        """Get the next sequential index for box naming."""
        return sum(1 for shape in self.shapes if isinstance(shape, BoxShape)) + 1

    def _next_poly_index(self) -> int:
        """Get the next sequential index for polygon naming."""
        return sum(1 for shape in self.shapes if isinstance(shape, PolyShape)) + 1

    def _next_color(self) -> str:
        """
        Get the next color from the predefined palette for new shapes.
        
        Returns:
            str: Hex color code for the new shape
            
        Note:
            Cycles through a predefined palette based on total shape count.
        """
        color_palette = [
            "#00b7ff",  # Bright blue
            "#ff6b00",  # Orange
            "#00ff6b",  # Green
            "#ff006b",  # Pink
            "#6b00ff",  # Purple
            "#ffff00",  # Yellow
            "#00ffff",  # Cyan
            "#ff0000",  # Red
            "#8b4513",  # Brown
            "#ffa500",  # Orange variant
            "#32cd32",  # Lime green
            "#ff1493",  # Deep pink
            "#9400d3",  # Violet
            "#ffd700",  # Gold
            "#40e0d0",  # Turquoise
            "#dc143c",  # Crimson
        ]
        
        return color_palette[len(self.shapes) % len(color_palette)]

# ================================================================================
# APPLICATION ENTRY POINT
# ================================================================================

if __name__ == "__main__":
    # Create and run the main application
    app = App()
    app.mainloop()