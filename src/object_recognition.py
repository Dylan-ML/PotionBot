# tools/object_recognition.py
"""
Object Recognition Engine for PotionGod (TLOPO)

Responsibilities:
- Load configuration/object_shapes.json (boxes + polygons traced at 1280x720)
- Use window_detector.GameWindowDetector to find the TLOPO client area
- Capture the client area with mss (no injection, no memory reading)
- Rescale shapes from baseline to the live client size with aspect-ratio
  compensation (letterbox/pillarbox) analogous to shape_tracer.py
- LEFT CLICK behavior: run one-shot recognition -> compute simple presence
  metrics for each shape (mean grayscale + contrast/stddev; optional edge strength)
- RIGHT CLICK behavior: toggle a debug overlay that draws all scaled boxes/polygons
  with labels so you can visually confirm alignment

Notes:
- Designed to be called from the GUI similarly to window_detector:
    recognizer = ObjectRecognizer(
        log_callback=app.log, state_callback=None,
        tk_root=app.root, detector=app.window_detector
    )
    # Left-click:
    recognizer.run_recognition_once()
    # Right-click:
    recognizer.toggle_overlay()

- The overlay requires a Tk root (tk_root). If not provided, overlay is disabled.

Author: you :)
"""

from __future__ import annotations

import json
import os
import threading
import time
import tkinter
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple, Union, TypedDict

# External deps
import mss
import numpy as np

# Optional deps for polygon masking / edge strength
try:
    import cv2  # type: ignore
    CV2_AVAILABLE = True
except Exception:
    cv2 = None  # type: ignore
    CV2_AVAILABLE = False

try:
    from PIL import Image, ImageDraw  # type: ignore
    PIL_AVAILABLE = True
except Exception:
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    PIL_AVAILABLE = False

# Local dependency: window detection / client rects
from window_detector import GameWindowDetector  # :contentReference[oaicite:0]{index=0}


# A precise mapping for aspect/letterbox transform values
class AspectTransform(TypedDict):
    scale_x: float
    scale_y: float
    offset_x: float
    offset_y: float
    method: str


# -----------------------------
# Data structures
# -----------------------------
@dataclass
class BoxShape:
    label: str
    category: str
    color: str
    x0: float
    y0: float
    x1: float
    y1: float

@dataclass
class PolyShape:
    label: str
    category: str
    color: str
    closed: bool
    pts: List[Tuple[float, float]]


Shape = Union[BoxShape, PolyShape]


# -----------------------------
# Helpers
# -----------------------------
def _default_log(msg: str, level: str = "INFO") -> None:
    """Fallback logger (mirrors GUI log signature)."""
    print(f"[{level}] {msg}")


def _resolve_tools_path(filename: str) -> str:
    """
    Resolve 'tools/<filename>' relative to this file OR the project root.
    Works when packaged differently during development.
    """
    here = os.path.abspath(os.path.dirname(__file__))
    # If this file is already under tools/, step up to find project root
    if os.path.basename(here).lower() == "tools":
        candidate = os.path.join(here, filename)
        if os.path.exists(candidate):
            return candidate
        # try project_root/tools/filename anyway
        project_root = os.path.dirname(here)
        candidate = os.path.join(project_root, "tools", filename)
        return candidate
    else:
        # object_recognition.py may sit in project root or src directory
        # First try current_dir/tools/filename
        candidate = os.path.join(here, "tools", filename)
        if os.path.exists(candidate):
            return candidate
        
        # Try parent_dir/tools/filename (for when we're in src/)
        parent_dir = os.path.dirname(here)
        candidate = os.path.join(parent_dir, "tools", filename)
        if os.path.exists(candidate):
            return candidate
        
        # Fallback to current directory
        return os.path.join(here, filename)


def _resolve_configuration_path(filename: str) -> str:
    """
    Resolve 'configuration/<filename>' relative to this file OR the project root.
    Works when packaged differently during development.
    """
    here = os.path.abspath(os.path.dirname(__file__))
    
    # If we're in src/, try parent_dir/configuration/filename first
    if os.path.basename(here).lower() == "src":
        parent_dir = os.path.dirname(here)
        candidate = os.path.join(parent_dir, "configuration", filename)
        if os.path.exists(candidate):
            return candidate
    
    # Try current_dir/configuration/filename
    candidate = os.path.join(here, "configuration", filename)
    if os.path.exists(candidate):
        return candidate
    
    # Try parent_dir/configuration/filename
    parent_dir = os.path.dirname(here)
    candidate = os.path.join(parent_dir, "configuration", filename)
    if os.path.exists(candidate):
        return candidate
    
    # Fallback to current directory
    return os.path.join(here, filename)


def _calc_aspect_ratio_transform(
    orig_w: int, orig_h: int, cur_w: int, cur_h: int
) -> AspectTransform:
    """
    Port of the transform logic used by shape_tracer.py to handle letter/pillarboxing.
    Returns scale_x, scale_y, offset_x, offset_y and 'method' for info.
    """
    original_aspect = orig_w / max(1, orig_h)
    current_aspect = cur_w / max(1, cur_h)

    # Within ~1% -> simple uniform scale + centering
    if abs(original_aspect - current_aspect) < 0.01:
        scale = min(cur_w / orig_w, cur_h / orig_h)
        return {
            "scale_x": scale,
            "scale_y": scale,
            "offset_x": (cur_w - orig_w * scale) / 2,
            "offset_y": (cur_h - orig_h * scale) / 2,
            "method": "uniform_scale",
        }

    # Wider -> pillarbox (side bars)
    if current_aspect > original_aspect:
        scale = cur_h / orig_h
        scaled_w = orig_w * scale
        return {
            "scale_x": scale,
            "scale_y": scale,
            "offset_x": (cur_w - scaled_w) / 2,
            "offset_y": 0.0,
            "method": "pillarbox_compensation",
        }

    # Taller -> letterbox (top/bottom bars)
    scale = cur_w / orig_w
    scaled_h = orig_h * scale
    return {
        "scale_x": scale,
        "scale_y": scale,
        "offset_x": 0.0,
        "offset_y": (cur_h - scaled_h) / 2,
        "method": "letterbox_compensation",
    }


def _to_gray_from_mss_bgra(img_bgra: np.ndarray) -> np.ndarray:
    """
    MSS returns BGRA. Produce float32 grayscale in range [0,255].
    No OpenCV dependency required.
    """
    # img_bgra shape: (H, W, 4), dtype=uint8
    b = img_bgra[..., 0].astype(np.float32)
    g = img_bgra[..., 1].astype(np.float32)
    r = img_bgra[..., 2].astype(np.float32)
    # Standard luminance
    gray = 0.114 * b + 0.587 * g + 0.299 * r
    return gray


def _polygon_mask(h: int, w: int, poly_pts: List[Tuple[int, int]]) -> np.ndarray:
    """
    Create a boolean mask for polygon points (int pixel coords).
    Uses cv2 if available, else PIL. Falls back to a simple even-odd fill via PIL.
    """
    mask = np.zeros((h, w), dtype=np.uint8)

    if len(poly_pts) < 3:
        return mask  # not enough points
    if CV2_AVAILABLE and cv2 is not None:
        pts = np.array(poly_pts, dtype=np.int32).reshape((-1, 1, 2))
        cv2.fillPoly(mask, [pts], color=1)
        return mask

    if PIL_AVAILABLE and Image is not None and ImageDraw is not None:
        pil_mask = Image.fromarray(mask * 255)
        draw = ImageDraw.Draw(pil_mask)
        draw.polygon(poly_pts, outline=1, fill=1)
        return (np.array(pil_mask) > 0).astype(np.uint8)

    # Very rare case: neither cv2 nor PIL available.
    # Return zero mask (no pixels) to avoid crashes.
    return mask


def _presence_metrics(
    gray: np.ndarray, roi_mask: Optional[np.ndarray] = None
) -> Dict[str, float]:
    """
    Compute simple presence metrics within ROI:
      - mean_gray
      - contrast (stddev)
      - norm_contrast (std/mean)
      - edge_strength (if OpenCV available)
      - n_pixels
    """
    if roi_mask is not None:
        pixels = gray[roi_mask > 0]
    else:
        pixels = gray.ravel()

    if pixels.size == 0:
        return {
            "mean_gray": 0.0,
            "contrast": 0.0,
            "norm_contrast": 0.0,
            "edge_strength": 0.0,
            "n_pixels": 0,
        }

    mean = float(pixels.mean())
    std = float(pixels.std())
    normc = float(std / (mean + 1e-6))
    edge_strength = 0.0
    if CV2_AVAILABLE and cv2 is not None:
        # Use Sobel on entire region (cheaper than Canny); mask if provided
        if roi_mask is not None:
            roi = np.zeros_like(gray, dtype=np.float32)
            roi[roi_mask > 0] = gray[roi_mask > 0]
        else:
            roi = gray.astype(np.float32)

        gx = cv2.Sobel(roi, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(roi, cv2.CV_32F, 0, 1, ksize=3)
        mag = np.sqrt(gx * gx + gy * gy)
        if roi_mask is not None:
            edge_strength = float(mag[roi_mask > 0].mean()) if pixels.size else 0.0
        else:
            edge_strength = float(mag.mean())

    return {
        "mean_gray": round(mean, 3),
        "contrast": round(std, 3),
        "norm_contrast": round(normc, 4),
        "edge_strength": round(edge_strength, 3),
        "n_pixels": int(pixels.size),
    }


# -----------------------------
# Main engine
# -----------------------------
class ObjectRecognizer:
    """
    Object recognition engine that reuses GameWindowDetector for window tracking
    and provides:
      - run_recognition_once()  -> left-click behavior
      - toggle_overlay()        -> right-click behavior
      - cleanup()
    """

    def __init__(
        self,
        log_callback: Optional[Callable[[str, str], None]] = None,
        state_callback: Optional[Callable[[bool], None]] = None,
        tk_root: Optional["tkinter.Tk"] = None,
        detector: Optional[GameWindowDetector] = None,
        shapes_json_path: Optional[str] = None,
        proc_names: Tuple[str, ...] = ("tlopo.exe",),
        title_keywords: Tuple[str, ...] = ("The Legend of Pirates Online", "TLOPO"),
    ):
        self.log = log_callback or _default_log
        self.state_callback = state_callback
        self.tk_root = tk_root

        # Window detector (can reuse GUI's instance)
        self.detector = detector or GameWindowDetector(
            proc_names=proc_names,
            title_keywords=title_keywords,
            log_callback=self.log,
            state_callback=self._on_detector_state,
        )

        # Capture session
        self._sct = mss.mss()

        # Shape storage
        self._baseline_w = 1280
        self._baseline_h = 720
        self._raw_shapes: List[Shape] = []
        self._load_shapes(shapes_json_path)

        # Last results
        self.last_results: List[Dict[str, Union[str, float, int]]] = []

        # Overlay state
        self._overlay_active = False
        self._overlay_win = None  # type: ignore
        self._overlay_canvas = None  # type: ignore
        self._overlay_job = None  # type: ignore
        self._overlay_transform = None  # type: ignore
        self._overlay_color_bg = "#000000"
        self._overlay_alpha = 0.35

    # ---------- Shapes ----------
    def _load_shapes(self, shapes_json_path: Optional[str]) -> None:
        path = shapes_json_path or _resolve_configuration_path("object_shapes.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            cap = data.get("captured_image_size", {}) or {}
            self._baseline_w = int(cap.get("width", 1280))
            self._baseline_h = int(cap.get("height", 720))
            raw = []
            for sh in data.get("shapes", []):
                t = sh.get("type")
                if t == "box":
                    raw.append(
                        BoxShape(
                            label=sh["label"],
                            category=sh.get("category", "button"),
                            color=sh.get("color", "#00b7ff"),
                            x0=float(sh["x0"]),
                            y0=float(sh["y0"]),
                            x1=float(sh["x1"]),
                            y1=float(sh["y1"]),
                        )
                    )
                elif t == "polygon":
                    pts = [(float(x), float(y)) for x, y in sh["pts"]]
                    raw.append(
                        PolyShape(
                            label=sh["label"],
                            category=sh.get("category", "button"),
                            color=sh.get("color", "#ff6b00"),
                            closed=bool(sh.get("closed", True)),
                            pts=pts,
                        )
                    )
            self._raw_shapes = raw
            self.log(f"Loaded {len(self._raw_shapes)} shapes (baseline {self._baseline_w}×{self._baseline_h}).", "INFO")
        except Exception as e:
            self.log(f"Failed to load object_shapes.json: {e}", "ERROR")
            self._raw_shapes = []

    def _scaled_shapes_for_size(self, cur_w: int, cur_h: int) -> Tuple[List[Shape], AspectTransform]:
        tr = _calc_aspect_ratio_transform(self._baseline_w, self._baseline_h, cur_w, cur_h)
        sx, sy = tr["scale_x"], tr["scale_y"]
        ox, oy = tr["offset_x"], tr["offset_y"]

        scaled: List[Shape] = []
        for s in self._raw_shapes:
            if isinstance(s, BoxShape):
                scaled.append(
                    BoxShape(
                        label=s.label,
                        category=s.category,
                        color=s.color,
                        x0=s.x0 * sx + ox,
                        y0=s.y0 * sy + oy,
                        x1=s.x1 * sx + ox,
                        y1=s.y1 * sy + oy,
                    )
                )
            else:
                pts = [(x * sx + ox, y * sy + oy) for (x, y) in s.pts]
                scaled.append(
                    PolyShape(
                        label=s.label,
                        category=s.category,
                        color=s.color,
                        closed=s.closed,
                        pts=pts,
                    )
                )
        return scaled, tr

    # ---------- Detector state ----------
    def _on_detector_state(self, detected: bool) -> None:
        if self.state_callback:
            try:
                self.state_callback(detected)
            except Exception:
                pass

    # ---------- Public actions ----------
    def run_recognition_once(self) -> List[Dict[str, Union[str, float, int]]]:
        """
        LEFT CLICK behavior: capture once and compute metrics for each shape.
        Returns the per-shape metrics list and stores it in self.last_results.
        """
        # Ensure we have a live window
        if not self.detector.is_window_detected():
            # try to find once
            self.detector.find_game_window()

        rect = self.detector.get_window_rect(kind="client")
        if not rect:
            self.log("No TLOPO client area found. Make sure the window is visible.", "WARNING")
            return []

        l, t, r, b = rect
        cur_w, cur_h = int(r - l), int(b - t)
        if cur_w < 5 or cur_h < 5:
            self.log("Client area too small to capture.", "ERROR")
            return []

        # Capture
        bbox = {"left": int(l), "top": int(t), "width": cur_w, "height": cur_h}
        shot = self._sct.grab(bbox)
        # MSS returns BGRA in a flat bytes buffer; turn into ndarray (H, W, 4)
        frame = np.asarray(shot)  # dtype=uint8, BGRA
        gray = _to_gray_from_mss_bgra(frame)  # float32

        # Transform shapes
        shapes, tr = self._scaled_shapes_for_size(cur_w, cur_h)
        self.log(f"Recognition (transform: {tr['method']}, scale={tr['scale_x']:.3f}, offset={int(tr['offset_x'])},{int(tr['offset_y'])})", "INFO")

        # Analyze
        results: List[Dict[str, Union[str, float, int]]] = []
        H, W = gray.shape[:2]

        def _clip(v: float, lo: int, hi: int) -> int:
            return int(max(lo, min(hi, round(v))))

        for s in shapes:
            if isinstance(s, BoxShape):
                x0 = _clip(s.x0, 0, W - 1)
                y0 = _clip(s.y0, 0, H - 1)
                x1 = _clip(s.x1, 1, W)
                y1 = _clip(s.y1, 1, H)
                if x1 <= x0 or y1 <= y0:
                    metrics = _presence_metrics(np.empty((0, 0), dtype=np.float32))
                else:
                    roi = gray[y0:y1, x0:x1]
                    metrics = _presence_metrics(roi)

                result = {
                    "label": s.label,
                    "type": "box",
                    "category": s.category,
                    "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                    **metrics,
                }
                results.append(result)
                self.log(f"• {s.label}: mean={metrics['mean_gray']}, contrast={metrics['contrast']}, n={metrics['n_pixels']}", "INFO")

            elif isinstance(s, PolyShape) and s.closed and len(s.pts) >= 3:
                pts = [( _clip(x, 0, W - 1), _clip(y, 0, H - 1) ) for (x, y) in s.pts]
                mask = _polygon_mask(H, W, pts)
                metrics = _presence_metrics(gray, mask)
                result = {
                    "label": s.label,
                    "type": "polygon",
                    "category": s.category,
                    "n_vertices": len(pts),
                    **metrics,
                }
                results.append(result)
                self.log(f"• {s.label}: mean={metrics['mean_gray']}, contrast={metrics['contrast']}, n={metrics['n_pixels']}", "INFO")
            else:
                self.log(f"• {getattr(s, 'label', 'poly')}: polygon not closed or too few points.", "WARNING")

        self.last_results = results
        self.log(f"Recognition complete for {len(results)} shapes.", "SUCCESS")
        return results

    def toggle_overlay(self) -> bool:
        """
        RIGHT CLICK behavior: show/hide a semi-transparent overlay with all shapes.
        Returns the new overlay state (True=shown).
        """
        if not self.tk_root:
            self.log("Overlay requires tk_root (parent Tk). Not provided.", "WARNING")
            return False

        if self._overlay_active:
            self._stop_overlay()
            return False
        else:
            self._start_overlay()
            return True

    def cleanup(self) -> None:
        """Make sure overlay is removed and resources freed."""
        self._stop_overlay()

    # ---------- Overlay internals ----------
    def _start_overlay(self) -> None:
        rect = self.detector.get_window_rect(kind="client")
        if not rect:
            self.log("Cannot show overlay: no valid game window.", "ERROR")
            return

        import tkinter as tk  # local import to avoid hard dependency for headless tests

        l, t, r, b = rect
        cur_w, cur_h = int(r - l), int(b - t)
        self._overlay_active = True

        # Create the overlay Toplevel
        self._overlay_win = tk.Toplevel(self.tk_root)
        self._overlay_win.title("Object Recognition Overlay")
        self._overlay_win.overrideredirect(True)
        self._overlay_win.attributes("-topmost", True)
        # semi-transparent
        try:
            self._overlay_win.attributes("-alpha", self._overlay_alpha)
        except Exception:
            pass

        # Position over the client rect
        self._overlay_win.geometry(f"{cur_w}x{cur_h}+{l}+{t}")

        # Canvas for drawing
        self._overlay_canvas = tk.Canvas(
            self._overlay_win, width=cur_w, height=cur_h, bg=self._overlay_color_bg, highlightthickness=0
        )
        self._overlay_canvas.pack(fill="both", expand=True)

        # Draw immediately; then schedule updates
        self._draw_overlay_once()
        if self.tk_root:
            self._overlay_job = self.tk_root.after(33, self._overlay_loop)
        self.log("Debug overlay started.", "SUCCESS")

    def _stop_overlay(self) -> None:
        if not self._overlay_active:
            return
        self._overlay_active = False
        try:
            if self._overlay_job and self.tk_root:
                self.tk_root.after_cancel(self._overlay_job)
        except Exception:
            pass
        self._overlay_job = None

        try:
            if self._overlay_win:
                self._overlay_win.destroy()
        except Exception:
            pass
        self._overlay_win = None
        self._overlay_canvas = None
        self._overlay_transform = None
        self.log("Debug overlay stopped.", "INFO")

    def _overlay_loop(self) -> None:
        if not self._overlay_active or not self._overlay_win or not self._overlay_canvas:
            return

        rect = self.detector.get_window_rect(kind="client")
        if rect:
            l, t, r, b = rect
            cur_w, cur_h = int(r - l), int(b - t)
            # Reposition/resize if moved or resized
            try:
                self._overlay_win.geometry(f"{cur_w}x{cur_h}+{l}+{t}")
            except Exception:
                pass
            self._draw_overlay_once()

        # Schedule next tick
        if self.tk_root and self._overlay_active:
            self._overlay_job = self.tk_root.after(33, self._overlay_loop)

    def _draw_overlay_once(self) -> None:
        if not self._overlay_canvas or not self._overlay_win:
            return
        rect = self.detector.get_window_rect(kind="client")
        if not rect:
            return
        l, t, r, b = rect
        cur_w, cur_h = int(r - l), int(b - t)
        self._overlay_canvas.delete("all")

        # Compute transform & scaled shapes
        shapes, tr = self._scaled_shapes_for_size(cur_w, cur_h)
        # Draw shapes
        for s in shapes:
            if isinstance(s, BoxShape):
                x0, y0, x1, y1 = s.x0, s.y0, s.x1, s.y1
                self._overlay_canvas.create_rectangle(
                    x0, y0, x1, y1, outline=s.color, width=3
                )
                self._overlay_canvas.create_text(
                    x0 + 8, y0 - 12, anchor="w", text=s.label, fill=s.color, font=("Segoe UI", 12, "bold")
                )
            elif isinstance(s, PolyShape) and s.closed and len(s.pts) >= 3:
                flat = []
                for (x, y) in s.pts:
                    flat.extend([x, y])
                self._overlay_canvas.create_polygon(
                    *flat, outline=s.color, width=3, fill=""
                )
                fx, fy = s.pts[0]
                self._overlay_canvas.create_text(
                    fx + 8, fy - 12, anchor="w", text=s.label, fill=s.color, font=("Segoe UI", 12, "bold")
                )

        # Top banner with transform info
        info = f"Overlay — transform: {tr['method']} (scale {tr['scale_x']:.2f}, offset {int(tr['offset_x'])},{int(tr['offset_y'])})"
        self._overlay_canvas.create_text(
            cur_w // 2, 20, anchor="center", text=info, fill="#ffffff", font=("Segoe UI", 12, "bold")
        )


# -----------------------------
# Standalone test (optional)
# -----------------------------
if __name__ == "__main__":
    """
    Minimal manual test:
      - Finds the window
      - Runs one-shot recognition
      - Shows overlay for ~5 seconds
    """
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()  # hide

    recog = ObjectRecognizer(tk_root=root)
    recog.detector.start_detection()
    time.sleep(1.0)

    recog.run_recognition_once()
    recog.toggle_overlay()

    def close():
        recog.cleanup()
        root.destroy()

    root.after(5000, close)
    root.mainloop()
