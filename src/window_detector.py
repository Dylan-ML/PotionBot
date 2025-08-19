# window_detector.py
"""
Game window detection (no capture) with optional debug overlay border.

- Uses Win32 APIs (no injection, no memory reading).
- DPI-aware: uses DWM extended frame bounds when available.
- Click-through overlay uses four thin topmost windows placed on each edge.
- Fixed critical issues: resource leaks, threading, window procedure
- GUI Integration: Clean start/stop methods for detection and overlay

Typical usage with GUI:
    det = GameWindowDetector(
        proc_names=('tlopo.exe',), 
        title_keywords=('The Legend of Pirates Online', 'TLOPO'),
        log_callback=app.log,  # Connect to GUI logging
        state_callback=app.on_detection_state_changed  # Update GUI state
    )
    
    # Left click: start/stop detection
    det.toggle_detection()
    
    # Right click: start/stop overlay  
    det.toggle_overlay()
    
    # Cleanup on GUI close
    det.cleanup()
"""

from __future__ import annotations

import re
import threading
import time
from typing import Iterable, Optional, Tuple, Callable

# pywin32 imports with fallback handling
try:
    import win32api # type: ignore
    import win32con # type: ignore
    import win32gui # type: ignore
    import win32process # type: ignore
    PYWIN32_AVAILABLE = True
except ImportError as e:
    print(f"pywin32 not properly installed: {e}")
    print("Please run: python -m pip install --force-reinstall pywin32")
    print("Then run: python Scripts/pywin32_postinstall.py -install")
    PYWIN32_AVAILABLE = False
    class DummyWin32Module:
        def __getattr__(self, name):
            raise ImportError(f"pywin32 not available - {name} cannot be used")
    
    win32api = DummyWin32Module()
    win32con = DummyWin32Module()
    win32gui = DummyWin32Module()
    win32process = DummyWin32Module()

# stdlib
import ctypes
from ctypes import wintypes

try:
    import psutil
except ImportError:
    psutil = None


# -----------------------------
# DPI awareness helpers
# -----------------------------
def _enable_dpi_awareness():
    """
    Try to make the current process DPI-aware so window coords map 1:1 to pixels.
    Safe on older Windows (best-effort).
    """
    try:
        # Windows 10+ preferred
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
        return
    except Exception:
        pass

    try:
        # Windows 8.1+
        shcore = ctypes.windll.shcore
        PROCESS_PER_MONITOR_DPI_AWARE = 2
        shcore.SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE)
        return
    except Exception:
        pass

    try:
        # Vista+
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


_enable_dpi_awareness()

# DWM Get extended frame bounds (for accurate outer rect incl. shadow/borders)
DWMWA_EXTENDED_FRAME_BOUNDS = 9
_dwmapi = None
try:
    _dwmapi = ctypes.WinDLL("dwmapi")
except Exception:
    _dwmapi = None


def _get_extended_frame_bounds(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
    if not _dwmapi:
        return None
    rect = wintypes.RECT()
    hr = _dwmapi.DwmGetWindowAttribute(
        wintypes.HWND(hwnd),
        wintypes.DWORD(DWMWA_EXTENDED_FRAME_BOUNDS),
        ctypes.byref(rect),
        ctypes.sizeof(rect),
    )
    if hr == 0:
        return rect.left, rect.top, rect.right, rect.bottom
    return None


# Global window procedure for overlay windows
def _overlay_window_proc(hwnd, msg, wparam, lparam):
    """Simple window procedure for overlay windows."""
    if msg == win32con.WM_DESTROY:
        return 0
    elif msg == win32con.WM_PAINT:
        # Let default handler paint the solid color background
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)
    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)


# -----------------------------
# Main detector
# -----------------------------
class GameWindowDetector:
    _window_class_registered = False
    _registered_brushes = []  # Track brushes for cleanup
    _class_name = "TlopoBorderOverlay"
    
    def __init__(
        self,
        proc_names: Iterable[str] = ("tlopo.exe",),
        title_keywords: Iterable[str] = ("The Legend of Pirates Online", "TLOPO"),
        overlay_poll_ms: int = 25,  # Faster polling for responsive movement tracking
        log_callback: Optional[Callable[[str, str], None]] = None,
        state_callback: Optional[Callable[[bool], None]] = None,
    ):
        """
        Args:
            proc_names: candidate process executable names to match (case-insensitive)
            title_keywords: title substrings/keywords to match (case-insensitive)
            overlay_poll_ms: how often the overlay refreshes to follow the window (lower = more responsive)
            log_callback: Function to call for logging (msg, level) - connects to GUI logging
            state_callback: Function to call when detection state changes (detected: bool)
        """
        # Check if pywin32 is properly installed
        if not PYWIN32_AVAILABLE:
            raise ImportError(
                "pywin32 is not properly installed. Please run:\n"
                "1. pip install --force-reinstall pywin32\n"
                "2. python Scripts/pywin32_postinstall.py -install\n"
                "Or from your venv: python -m pip install --force-reinstall pywin32"
            )
        
        self.proc_names = tuple(n.lower() for n in proc_names)
        self.title_patterns = [re.compile(re.escape(k), re.IGNORECASE) for k in title_keywords]
        self.overlay_poll_ms = max(10, overlay_poll_ms)  # Minimum 10ms to prevent excessive CPU usage

        # GUI integration callbacks
        self.log_callback = log_callback or self._default_log
        self.state_callback = state_callback or self._default_state_callback

        # Thread-safe state
        self._lock = threading.RLock()
        self.game_hwnd: Optional[int] = None
        self.window_rect: Optional[Tuple[int, int, int, int]] = None  # frame rect (l,t,r,b)
        
        # Detection state
        self._detection_active = False
        self._detection_thread: Optional[threading.Thread] = None
        self._detection_stop = threading.Event()

        # Overlay state
        self._overlay_color = (255, 215, 0)  # default gold/yellow
        self._overlay_thickness = 3
        self._overlay_windows = []  # [hwnd_top, hwnd_bottom, hwnd_left, hwnd_right]
        self._overlay_thread: Optional[threading.Thread] = None
        self._overlay_stop = threading.Event()
        self._overlay_active = False
        
        # For efficient change detection
        self._last_overlay_rect = None

    def _default_log(self, msg: str, level: str = "INFO"):
        """Default logging when no callback provided."""
        print(f"[{level}] {msg}")

    def _default_state_callback(self, detected: bool):
        """Default state callback when none provided."""
        pass

    # --------------- GUI Integration Methods ---------------
    
    def toggle_detection(self) -> bool:
        """
        Toggle window detection on/off. Called by GUI on left-click.
        
        Returns:
            bool: New detection state (True = active, False = inactive)
        """
        if self._detection_active:
            self.stop_detection()
            return False
        else:
            self.start_detection()
            return True

    def toggle_overlay(self) -> bool:
        """
        Toggle overlay on/off. Called by GUI on right-click.
        
        Returns:
            bool: New overlay state (True = active, False = inactive)
        """
        if self._overlay_active:
            self.stop_overlay()
            return False
        else:
            if not self.game_hwnd:
                self.log_callback("🪟 No game window detected. Please start detection first.", "WARNING")
                return False
            self.start_overlay()
            return True

    def start_detection(self):
        """Start continuous window detection."""
        if self._detection_active:
            return
            
        self._detection_active = True
        self._detection_stop.clear()
        self._detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
        self._detection_thread.start()
        self.log_callback("🔍 Window detection started", "INFO")

    def stop_detection(self):
        """Stop window detection."""
        if not self._detection_active:
            return
            
        self._detection_active = False
        self._detection_stop.set()
        
        if self._detection_thread and self._detection_thread.is_alive():
            self._detection_thread.join(timeout=1.5)
            
        # Clear detection state
        with self._lock:
            was_detected = self.game_hwnd is not None
            self.game_hwnd = None
            self.window_rect = None
            
        # Notify GUI of state change
        if was_detected:
            self.state_callback(False)
            
        self.log_callback("⏹️ Window detection stopped", "INFO")

    def is_detection_active(self) -> bool:
        """Check if detection is currently active."""
        return self._detection_active

    def is_overlay_active(self) -> bool:
        """Check if overlay is currently active."""
        return self._overlay_active

    def is_window_detected(self) -> bool:
        """Check if game window is currently detected."""
        with self._lock:
            return self.game_hwnd is not None

    def get_current_window_info(self) -> Optional[dict]:
        """
        Get current window information for external use.
        Useful for GUI debugging panels or screen capture coordination.
        
        Returns:
            dict: Window info dict or None if no window detected
        """
        return self.get_window_info()

    def refresh_and_log_window_info(self):
        """
        Manually refresh and log current window information.
        Useful for debugging or when window properties might have changed.
        """
        if not self.is_window_detected():
            self.log_callback("❌ No window detected to get info for", "WARNING")
            return
            
        self.log_callback("🔄 Refreshing window information...", "INFO")
        self.log_window_info()

    # --------------- Detection Loop ---------------
    
    def _detection_loop(self):
        """Continuous detection loop that runs in background thread."""
        last_detection_state = False
        consecutive_failures = 0
        max_failures_before_lost = 3  # Allow 3 consecutive failures before declaring window lost
        
        while not self._detection_stop.is_set():
            # Try to find the game window
            current_detected = self._find_and_validate_window()
            
            # Implement tolerance for transient failures
            if current_detected:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                # Only consider window truly lost after several consecutive failures
                if consecutive_failures < max_failures_before_lost and last_detection_state:
                    current_detected = True  # Keep showing as detected
            
            # Only notify on state changes to avoid spam
            if current_detected != last_detection_state:
                if current_detected:
                    self.log_callback("✅ Game window found and connected", "SUCCESS")
                    # Log detailed window information when first detected
                    self.log_window_info()
                else:
                    self.log_callback("⚠️ Game window lost", "WARNING")
                    
                # Notify GUI of state change
                self.state_callback(current_detected)
                last_detection_state = current_detected
            
            # Check every 1 second
            time.sleep(1.0)

    def _find_and_validate_window(self) -> bool:
        """Find and validate game window. Returns True if found and valid."""
        if self.find_game_window() and self.validate_window():
            return True
        return False

    # --------------- Original Detection Methods (Modified) ---------------
    def find_game_window(self) -> bool:
        """
        Try several strategies:
          1) If psutil is available: find candidate processes by name and then match their top windows.
          2) Fallback: enumerate all top-level windows and match title keywords.
        Updates self.game_hwnd and self.window_rect on success.
        """
        hwnd = None

        # Strategy 1: processes by name
        if psutil is not None and self.proc_names:
            try:
                pids = []
                for p in psutil.process_iter(["pid", "name"]):
                    name = (p.info.get("name") or "").lower()
                    if name in self.proc_names:
                        pids.append(p.info["pid"])
                hwnd = self._find_top_window_by_pids(pids)
            except Exception:
                hwnd = None

        # Strategy 2: enumerate windows by title
        if hwnd is None:
            hwnd = self._find_top_window_by_title()

        with self._lock:
            if hwnd and win32gui.IsWindow(hwnd):
                self.game_hwnd = hwnd
                self.window_rect = self.get_window_rect(kind="frame")
                return True

            self.game_hwnd = None
            self.window_rect = None
            return False

    def _find_top_window_by_pids(self, pids: Iterable[int]) -> Optional[int]:
        if not pids:
            return None

        result = {"hwnd": None}

        def enum_handler(hwnd, lParam):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid in pids:
                    title = (win32gui.GetWindowText(hwnd) or "").strip()
                    if title and any(p.search(title) for p in self.title_patterns) or not self.title_patterns:
                        result["hwnd"] = hwnd
                        return False
            except Exception:
                pass
            return True

        try:
            win32gui.EnumWindows(enum_handler, None)
        except Exception:
            # EnumWindows failed - return None to allow fallback to title-based detection
            return None
        return result["hwnd"]

    def _find_top_window_by_title(self) -> Optional[int]:
        result = {"hwnd": None}

        def enum_handler(hwnd, lParam):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            title = (win32gui.GetWindowText(hwnd) or "").strip()
            if not title:
                return True
            if any(p.search(title) for p in self.title_patterns):
                result["hwnd"] = hwnd
                return False
            return True

        try:
            win32gui.EnumWindows(enum_handler, None)
        except Exception as e:
            # Handle EnumWindows errors silently - this is a known issue with pywin32
            # on some systems and the fallback method works perfectly fine
            return None
        return result["hwnd"]

    def validate_window(self) -> bool:
        """
        Basic validation: exists, visible, not iconic (minimized).
        Updates window_rect on success.
        """
        with self._lock:
            hwnd = self.game_hwnd
            if not hwnd:
                return False
                
            # Add retry logic for transient Windows API failures
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    if not win32gui.IsWindow(hwnd):
                        return False
                    if not win32gui.IsWindowVisible(hwnd):
                        return False
                    if win32gui.IsIconic(hwnd):  # minimized
                        return False

                    new_rect = self.get_window_rect(kind="frame")
                    if new_rect:
                        self.window_rect = new_rect
                        return True
                    
                    # If we couldn't get rect on first try, wait briefly and retry
                    if attempt < max_retries - 1:
                        time.sleep(0.1)
                        continue
                    return False
                    
                except Exception as e:
                    # Handle transient Win32 API errors
                    if attempt < max_retries - 1:
                        time.sleep(0.1)
                        continue
                    # Log the error on final attempt
                    self.log_callback(f"Window validation failed after {max_retries} attempts: {e}", "DEBUG")
                    return False
            
            return False

    # --------------- Geometry ---------------
    def get_window_rect(self, kind: str = "frame") -> Optional[Tuple[int, int, int, int]]:
        """
        Returns window rectangle in screen coordinates.

        kind:
          - 'frame'  : outer window bounds (including frame/shadow if available)
          - 'client' : client area mapped to screen coordinates
        """
        with self._lock:
            hwnd = self.game_hwnd
            if not hwnd:
                return None

            # Add retry logic for transient API failures
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    if not win32gui.IsWindow(hwnd):
                        return None

                    if kind == "frame":
                        # Prefer DWM extended frame bounds for accuracy
                        rect = _get_extended_frame_bounds(hwnd)
                        if rect:
                            return rect
                        # fallback
                        return win32gui.GetWindowRect(hwnd)
                    elif kind == "client":
                        left, top, right, bottom = win32gui.GetClientRect(hwnd)
                        # Map client (0,0) to screen
                        pt = win32gui.ClientToScreen(hwnd, (0, 0))
                        return pt[0], pt[1], pt[0] + (right - left), pt[1] + (bottom - top)
                    else:
                        raise ValueError("kind must be 'frame' or 'client'")
                        
                except Exception as e:
                    # Handle transient Win32 API errors with retry
                    if attempt < max_retries - 1:
                        time.sleep(0.05)  # Brief pause before retry
                        continue
                    # Log error on final attempt for debugging
                    self.log_callback(f"Failed to get window rect after {max_retries} attempts: {e}", "DEBUG")
                    return None
            
            return None

    def get_window_info(self) -> Optional[dict]:
        """
        Get comprehensive window information for debugging and future features.
        
        Returns:
            dict: Comprehensive window information including:
                - dimensions: frame and client rectangles, width, height
                - position: screen coordinates, center point
                - dpi: DPI awareness info and scaling factors
                - monitor: which monitor the window is on, monitor resolution
                - process: PID, process name, executable path
                - window: title, class name, handle, state flags
                - technical: z-order, parent/child relationships
        """
        with self._lock:
            hwnd = self.game_hwnd
            if not hwnd or not win32gui.IsWindow(hwnd):
                return None

            try:
                info = {}
                
                # === Window Rectangles and Dimensions ===
                frame_rect = self.get_window_rect("frame")
                client_rect = self.get_window_rect("client")
                
                if frame_rect:
                    fl, ft, fr, fb = frame_rect
                    info["frame"] = {
                        "left": fl, "top": ft, "right": fr, "bottom": fb,
                        "width": fr - fl, "height": fb - ft,
                        "center_x": (fl + fr) // 2, "center_y": (ft + fb) // 2
                    }
                
                if client_rect:
                    cl, ct, cr, cb = client_rect
                    info["client"] = {
                        "left": cl, "top": ct, "right": cr, "bottom": cb,
                        "width": cr - cl, "height": cb - ct,
                        "center_x": (cl + cr) // 2, "center_y": (ct + cb) // 2
                    }
                
                # === DPI and Scaling Information ===
                try:
                    # Get DPI for the window
                    dpi = ctypes.windll.user32.GetDpiForWindow(hwnd)
                    scale_factor = dpi / 96.0  # 96 DPI is 100% scaling
                    info["dpi"] = {
                        "dpi": dpi,
                        "scale_factor": scale_factor,
                        "scale_percent": int(scale_factor * 100)
                    }
                except Exception:
                    info["dpi"] = {"dpi": 96, "scale_factor": 1.0, "scale_percent": 100}
                
                # === Monitor Information ===
                try:
                    monitor = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
                    monitor_info = win32api.GetMonitorInfo(monitor)
                    work_area = monitor_info["Work"]
                    monitor_area = monitor_info["Monitor"]
                    
                    info["monitor"] = {
                        "handle": monitor,
                        "is_primary": monitor_info["Flags"] == win32con.MONITORINFOF_PRIMARY,
                        "work_area": {
                            "left": work_area[0], "top": work_area[1],
                            "right": work_area[2], "bottom": work_area[3],
                            "width": work_area[2] - work_area[0],
                            "height": work_area[3] - work_area[1]
                        },
                        "full_area": {
                            "left": monitor_area[0], "top": monitor_area[1],
                            "right": monitor_area[2], "bottom": monitor_area[3],
                            "width": monitor_area[2] - monitor_area[0],
                            "height": monitor_area[3] - monitor_area[1]
                        }
                    }
                except Exception:
                    info["monitor"] = {"error": "Could not get monitor info"}
                
                # === Process Information ===
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    # Initialize with mixed types to avoid Pylance type inference issues
                    info["process"] = {"pid": int(pid), "name": "Unknown"}
                    
                    # Get process details if psutil is available
                    if psutil:
                        try:
                            proc = psutil.Process(pid)
                            # Get each piece of info separately to handle potential errors
                            process_details = {}
                            
                            try:
                                process_details["name"] = str(proc.name())
                            except Exception:
                                process_details["name"] = "Unknown"
                            
                            try:
                                process_details["exe"] = str(proc.exe())
                            except Exception:
                                process_details["exe"] = "Unknown"
                            
                            try:
                                process_details["cwd"] = str(proc.cwd())
                            except Exception:
                                process_details["cwd"] = "Unknown"
                            
                            try:
                                memory_bytes = proc.memory_info().rss
                                process_details["memory_mb"] = round(memory_bytes / 1024 / 1024, 1)
                            except Exception:
                                process_details["memory_mb"] = 0.0
                            
                            try:
                                process_details["cpu_percent"] = float(proc.cpu_percent())
                            except Exception:
                                process_details["cpu_percent"] = 0.0
                            
                            try:
                                process_details["create_time"] = float(proc.create_time())
                            except Exception:
                                process_details["create_time"] = 0.0
                            
                            # Now safely update the process info
                            info["process"].update(process_details)
                            
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            info["process"]["access_error"] = "Process access denied"
                    else:
                        # If psutil not available, indicate that
                        info["process"]["note"] = "psutil not available - limited process info"
                        
                except Exception:
                    info["process"] = {"error": "Could not get process info"}
                
                # === Window Properties ===
                try:
                    title = win32gui.GetWindowText(hwnd)
                    class_name = win32gui.GetClassName(hwnd)
                    
                    # Check if window is maximized using GetWindowPlacement
                    try:
                        placement = win32gui.GetWindowPlacement(hwnd)
                        is_maximized = placement[1] == win32con.SW_SHOWMAXIMIZED
                    except Exception:
                        is_maximized = False
                    
                    info["window"] = {
                        "handle": hwnd,
                        "title": title,
                        "class_name": class_name,
                        "is_visible": win32gui.IsWindowVisible(hwnd),
                        "is_minimized": win32gui.IsIconic(hwnd),
                        "is_maximized": is_maximized,
                        "is_enabled": win32gui.IsWindowEnabled(hwnd),
                        "has_focus": win32gui.GetForegroundWindow() == hwnd
                    }
                except Exception:
                    info["window"] = {"handle": hwnd, "error": "Could not get window properties"}
                
                # === Window Hierarchy ===
                try:
                    parent = win32gui.GetParent(hwnd)
                    owner = win32gui.GetWindow(hwnd, win32con.GW_OWNER)
                    
                    info["hierarchy"] = {
                        "parent": parent if parent else None,
                        "owner": owner if owner else None,
                        "is_top_level": parent == 0
                    }
                except Exception:
                    info["hierarchy"] = {"error": "Could not get hierarchy info"}
                
                # === Extended Frame Bounds (DWM) ===
                extended_bounds = _get_extended_frame_bounds(hwnd)
                if extended_bounds:
                    el, et, er, eb = extended_bounds
                    info["extended_frame"] = {
                        "left": el, "top": et, "right": er, "bottom": eb,
                        "width": er - el, "height": eb - et
                    }
                    
                    # Calculate frame border sizes
                    if frame_rect:
                        fl, ft, fr, fb = frame_rect
                        info["frame_borders"] = {
                            "left": fl - el, "top": ft - et,
                            "right": er - fr, "bottom": eb - fb
                        }
                
                return info
                
            except Exception as e:
                return {"error": f"Failed to get window info: {str(e)}"}

    def log_window_info(self):
        """Log comprehensive window information for debugging."""
        info = self.get_window_info()
        if not info:
            self.log_callback("❌ No window info available", "ERROR")
            return
            
        if "error" in info:
            self.log_callback(f"❌ Window info error: {info['error']}", "ERROR")
            return
        
        # Log key information in a readable format
        if "frame" in info:
            f = info["frame"]
            self.log_callback(f"📐 Window: {f['width']}x{f['height']} at ({f['left']}, {f['top']})", "INFO")
        
        if "client" in info:
            c = info["client"]
            self.log_callback(f"📱 Client area: {c['width']}x{c['height']}", "INFO")
        
        if "dpi" in info:
            d = info["dpi"]
            self.log_callback(f"🔍 DPI: {d['dpi']} ({d['scale_percent']}% scaling)", "INFO")
        
        if "monitor" in info and "full_area" in info["monitor"]:
            m = info["monitor"]["full_area"]
            primary = " (Primary)" if info["monitor"].get("is_primary") else ""
            self.log_callback(f"🖥️ Monitor: {m['width']}x{m['height']}{primary}", "INFO")
        
        if "process" in info and "name" in info["process"]:
            p = info["process"]
            mem_info = f", {p['memory_mb']}MB" if "memory_mb" in p else ""
            self.log_callback(f"⚙️ Process: {p['name']} (PID: {p['pid']}{mem_info})", "INFO")
        
        if "window" in info:
            w = info["window"]
            states = []
            if w.get("is_maximized"): states.append("maximized")
            if w.get("is_minimized"): states.append("minimized")
            if w.get("has_focus"): states.append("focused")
            state_str = f" [{', '.join(states)}]" if states else ""
            self.log_callback(f"🪟 Title: \"{w.get('title', 'Unknown')}\"{state_str}", "INFO")

    # --------------- Overlay Methods ---------------
    def start_overlay(self, color=(255, 215, 0), thickness: int = 3):
        """Start the debug border overlay."""
        if not self.validate_window():
            self.log_callback("❌ Cannot start overlay: no valid game window", "ERROR")
            return
            
        if self._overlay_active:
            return
            
        self._overlay_color = color
        self._overlay_thickness = max(1, int(thickness))
        self._overlay_active = True
        
        self._overlay_stop.clear()
        self._ensure_overlay_windows()
        self._overlay_thread = threading.Thread(target=self._overlay_loop, daemon=True)
        self._overlay_thread.start()
        
        self.log_callback("🎯 Overlay started", "SUCCESS")

    def stop_overlay(self):
        """Stop and destroy the overlay windows."""
        if not self._overlay_active:
            return
            
        self._overlay_active = False
        self._overlay_stop.set()
        
        if self._overlay_thread and self._overlay_thread.is_alive():
            self._overlay_thread.join(timeout=1.5)
            
        self._destroy_overlay_windows()
        self._overlay_thread = None
        self._last_overlay_rect = None
        
        self.log_callback("⏹️ Overlay stopped", "INFO")

    def cleanup(self):
        """Call on program exit to clean up all resources."""
        self.stop_detection()
        self.stop_overlay()
        self._cleanup_gdi_resources()

    # --------------- Resource Management ---------------
    @classmethod
    def _cleanup_gdi_resources(cls):
        """Clean up any GDI resources we've created."""
        for brush in cls._registered_brushes:
            try:
                win32gui.DeleteObject(brush)
            except Exception:
                pass
        cls._registered_brushes.clear()

    @classmethod
    def _register_window_class(cls, color):
        """Register window class once per color."""
        if cls._window_class_registered:
            return
            
        hInstance = win32api.GetModuleHandle(None)
        
        # Create brush for background color
        r, g, b = color
        colorref = win32api.RGB(r, g, b)
        hBrush = win32gui.CreateSolidBrush(colorref)
        cls._registered_brushes.append(hBrush)

        # Register window class using setattr to avoid type checking issues
        try:
            wnd_class = win32gui.WNDCLASS()
            # Use setattr to avoid Pylance type checking issues with WNDCLASS attributes
            setattr(wnd_class, 'hInstance', hInstance)
            setattr(wnd_class, 'lpszClassName', cls._class_name) 
            setattr(wnd_class, 'lpfnWndProc', _overlay_window_proc)
            setattr(wnd_class, 'hCursor', win32gui.LoadCursor(None, win32con.IDC_ARROW))
            setattr(wnd_class, 'hbrBackground', hBrush)
            
            win32gui.RegisterClass(wnd_class)
            cls._window_class_registered = True
        except win32gui.error:
            cls._window_class_registered = True

    # --------------- Overlay Implementation ---------------
    def _overlay_loop(self):
        """Main overlay loop - tracks window changes and updates overlay position."""
        while not self._overlay_stop.is_set():
            # Validate window exists and is accessible
            if not self.validate_window():
                self._hide_overlay_windows()
                self._last_overlay_rect = None
            else:
                # Get client area for overlay (excludes title bar and window frame)
                current_rect = self.get_window_rect(kind="client")
                
                # Only update overlay if window moved/resized
                if current_rect and current_rect != self._last_overlay_rect:
                    self._position_overlay(current_rect)
                    self._last_overlay_rect = current_rect
                    
                self._show_overlay_windows()
            
            time.sleep(self.overlay_poll_ms / 1000.0)

    def _ensure_overlay_windows(self):
        """Create overlay windows if they don't exist."""
        if self._overlay_windows:
            return
            
        # Register window class
        self._register_window_class(self._overlay_color)
        
        # Create 4 border windows (top, bottom, left, right)
        for _ in range(4):
            hwnd = self._create_border_window()
            if hwnd:
                self._overlay_windows.append(hwnd)

    def _destroy_overlay_windows(self):
        """Destroy all overlay windows."""
        for hwnd in self._overlay_windows:
            try:
                if win32gui.IsWindow(hwnd):
                    win32gui.DestroyWindow(hwnd)
            except Exception:
                pass
        self._overlay_windows.clear()

    def _hide_overlay_windows(self):
        """Hide overlay windows."""
        for hwnd in self._overlay_windows:
            try:
                if win32gui.IsWindow(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
            except Exception:
                pass

    def _show_overlay_windows(self):
        """Show and ensure overlay windows are topmost."""
        for hwnd in self._overlay_windows:
            try:
                if win32gui.IsWindow(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_SHOWNA)
                    win32gui.SetWindowPos(
                        hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                        win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE
                    )
            except Exception:
                pass

    def _position_overlay(self, rect):
        """Position overlay windows to form a border around the target rect."""
        l, t, r, b = rect
        thick = self._overlay_thickness

        # Calculate positions for top, bottom, left, right borders
        targets = [
            (l, t, r - l, thick),          # top
            (l, b - thick, r - l, thick),  # bottom
            (l, t, thick, b - t),          # left
            (r - thick, t, thick, b - t),  # right
        ]
        
        for hwnd, (x, y, w, h) in zip(self._overlay_windows, targets):
            try:
                if win32gui.IsWindow(hwnd):
                    win32gui.SetWindowPos(
                        hwnd, win32con.HWND_TOPMOST, x, y, max(1, w), max(1, h),
                        win32con.SWP_NOACTIVATE
                    )
            except Exception:
                pass

    def _create_border_window(self) -> Optional[int]:
        """Create a single border window (click-through, transparent)."""
        hInstance = win32api.GetModuleHandle(None)

        # Create window (popup, no taskbar, topmost, layered, transparent to mouse)
        ex_style = (
            win32con.WS_EX_TOOLWINDOW      # No taskbar button
            | win32con.WS_EX_TOPMOST       # Stay on top
            | win32con.WS_EX_LAYERED       # Allows transparency
            | win32con.WS_EX_TRANSPARENT   # Mouse clicks pass through
        )
        style = win32con.WS_POPUP

        try:
            hwnd = win32gui.CreateWindowEx(
                ex_style,
                self._class_name,
                "",  # no title
                style,
                0, 0, 10, 10,  # Initial size/position
                0, 0, hInstance, None,
            )
            
            if not hwnd:
                return None

            # Make the window fully opaque (255 alpha)
            win32gui.SetLayeredWindowAttributes(hwnd, 0, 255, win32con.LWA_ALPHA)

            # Initial hide
            win32gui.ShowWindow(hwnd, win32con.SW_HIDE)

            return hwnd
            
        except Exception:
            return None
