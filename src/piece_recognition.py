# tools/piece_recognition.py
"""
Piece Recognition for PotionGod (TLOPO)

Reads the 'next_piece_left' and 'next_piece_right' polygon ROIs from configuration/object_shapes.json,
captures the live client area using GameWindowDetector + mss, and classifies the piece colors
using arrays of color swatches per token (e.g., multiple "red" shades). Tokens can be R/G/B or
any custom labels you define.

Swatch types supported:
  - HSV range: {"type":"hsv", "h":[lo,hi], "s":[smin,smax]?, "v":[vmin,vmax]?}
  - BGR center+tol: {"type":"bgr", "bgr":[B,G,R], "tol":int}   # Euclidean distance in BGR

Design:
- Reuses the same aspect/letterbox transform used by object_recognition.py so ROIs line up.
- Works without OpenCV (fallback HSV via colorsys), but prefers OpenCV for speed/robustness.
- Returns a compact label per ROI plus per-token coverage ratios for debugging.

Usage (typical):
    det = GameWindowDetector(log_callback=print)
    det.start_detection()
    time.sleep(1)
    # Option A: use defaults (R/G/B)
    recog = PieceRecognizer(detector=det, log_callback=print)
    # Option B: provide swatches dict
    # recog = PieceRecognizer(detector=det, color_swatches={
    #     "R":[{"type":"hsv","h":[0,10]},{"type":"hsv","h":[160,179]}],
    #     "G":[{"type":"hsv","h":[40,85]}],
    #     "B":[{"type":"hsv","h":[95,135]}],
    # })
    # Option C: load from JSON
    # recog = PieceRecognizer(detector=det, swatches_json_path="tools/piece_color_swatches.json")
    result = recog.detect_next_pieces()
    print(result)
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Callable

import mss
import numpy as np

# Prefer OpenCV; gracefully degrade if missing
try:
    import cv2  # type: ignore
    CV2 = True
except Exception:
    cv2 = None  # type: ignore
    CV2 = False

try:
    from PIL import Image, ImageDraw  # type: ignore
    PIL_OK = True
except Exception:
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    PIL_OK = False

# Local dependency (your window detection class)
from window_detector import GameWindowDetector  # noqa: E402


def _default_log(msg: str, level: str = "INFO") -> None:
    print(f"[{level}] {msg}")


# ---------- JSON shape structures ----------
@dataclass
class PolyShape:
    label: str
    category: str
    color: str
    closed: bool
    pts: List[Tuple[float, float]]



# ---------- Transform identical to object recognition ----------
def _calc_aspect_ratio_transform(orig_w: int, orig_h: int, cur_w: int, cur_h: int) -> Dict[str, float]:
    original_aspect = orig_w / max(1, orig_h)
    current_aspect = cur_w / max(1, cur_h)

    if abs(original_aspect - current_aspect) < 0.01:
        scale = min(cur_w / orig_w, cur_h / orig_h)
        return dict(scale_x=scale, scale_y=scale,
                    offset_x=(cur_w - orig_w * scale) / 2,
                    offset_y=(cur_h - orig_h * scale) / 2)

    if current_aspect > original_aspect:
        # pillarbox
        scale = cur_h / orig_h
        scaled_w = orig_w * scale
        return dict(scale_x=scale, scale_y=scale,
                    offset_x=(cur_w - scaled_w) / 2, offset_y=0.0)
    # letterbox
    scale = cur_w / orig_w
    scaled_h = orig_h * scale
    return dict(scale_x=scale, scale_y=scale,
                offset_x=0.0, offset_y=(cur_h - scaled_h) / 2)


def _polygon_mask(h: int, w: int, pts: List[Tuple[int, int]]) -> np.ndarray:
    mask = np.zeros((h, w), dtype=np.uint8)
    if len(pts) < 3:
        return mask
    if CV2 and cv2 is not None:
        arr = np.array(pts, dtype=np.int32).reshape((-1, 1, 2))
        cv2.fillPoly(mask, [arr], color=1)
        return mask
    if PIL_OK and Image is not None and ImageDraw is not None:
        im = Image.fromarray(mask)
        draw = ImageDraw.Draw(im)
        draw.polygon(pts, outline=1, fill=1)
        return (np.array(im) > 0).astype(np.uint8)
    return mask


def _crop_to_polygon(frame_bgra, pts_abs):
    if CV2 and cv2 is not None:
        x, y, w, h = cv2.boundingRect(np.array(pts_abs, dtype=np.int32))
        # Clamp to frame bounds
        H, W = frame_bgra.shape[:2]
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(W, x + w), min(H, y + h)
        if x1 <= x0 or y1 <= y0:
            # Fallback to minimal 1x1 crop if something is off
            x0, y0, x1, y1 = 0, 0, 1, 1
        roi = frame_bgra[y0:y1, x0:x1].copy()
        pts_local = [(px - x0, py - y0) for (px, py) in pts_abs]
        return roi, pts_local, (x0, y0, x1 - x0, y1 - y0)
    else:
        xs = [p[0] for p in pts_abs]; ys = [p[1] for p in pts_abs]
        H, W = frame_bgra.shape[:2]
        x0, y0 = max(0, int(min(xs))), max(0, int(min(ys)))
        x1, y1 = min(W, int(max(xs)) + 1), min(H, int(max(ys)) + 1)
        roi = frame_bgra[y0:y1, x0:x1].copy()
        pts_local = [(px - x0, py - y0) for (px, py) in pts_abs]
        return roi, pts_local, (x0, y0, x1 - x0, y1 - y0)


def _polygon_mask_local(h, w, pts_local):
    m = np.zeros((h, w), dtype=np.uint8)
    if len(pts_local) >= 3:
        if CV2 and cv2 is not None:
            arr = np.array(pts_local, dtype=np.int32).reshape((-1,1,2))
            cv2.fillPoly(m, [arr], 1)
        elif PIL_OK and Image is not None and ImageDraw is not None:
            im = Image.fromarray(m)
            d = ImageDraw.Draw(im)
            d.polygon(pts_local, outline=1, fill=1)
            m = (np.array(im) > 0).astype(np.uint8)
    return m


def _resize_pair(img, mask, max_side=140):
    h, w = img.shape[:2]
    scale = min(1.0, float(max_side)/max(h,w))
    if scale >= 0.999: 
        return img, mask
    new_w, new_h = max(1,int(round(w*scale))), max(1,int(round(h*scale)))
    if CV2 and cv2 is not None:
        img_s = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        mask_s = cv2.resize(mask, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
    else:
        # Fallback: return original if no OpenCV
        img_s = img
        mask_s = mask
    return img_s, mask_s


def _bgra_to_hsv(img_bgra: np.ndarray) -> np.ndarray:
    """
    Returns HSV uint8 image:
      - If OpenCV present: H in [0,179], S,V in [0,255]
      - Fallback: H,S,V in [0,255]
    """
    if CV2 and cv2 is not None:
        bgr = img_bgra[..., :3].copy()
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    # Fallback: manual conversion via colorsys (slower but fine on small ROIs)
    import colorsys
    b = img_bgra[..., 0].astype(np.float32) / 255.0
    g = img_bgra[..., 1].astype(np.float32) / 255.0
    r = img_bgra[..., 2].astype(np.float32) / 255.0
    flat = np.stack([r.ravel(), g.ravel(), b.ravel()], axis=1)
    out = np.zeros_like(flat)
    for i, (rr, gg, bb) in enumerate(flat):
        h, s, v = colorsys.rgb_to_hsv(rr, gg, bb)
        out[i] = (h * 255.0, s * 255.0, v * 255.0)
    return out.reshape((*img_bgra.shape[:2], 3)).astype(np.uint8)


class PieceRecognizer:
    """
    Determines the color(s) of the next pieces (left/right) by hue voting inside
    the 'next_piece_left' and 'next_piece_right' polygon regions from object_shapes.json (in configuration folder).

    Swatches:
        Provide arrays of swatches per token (e.g., all "red" shades). The recognizer unions
        all swatches for a token, measures coverage, then labels like "R/G", "B/B", etc.

    Results:
        {
          "next_piece_left":  {"label":"R/G", "top":[("R",0.62),("G",0.31)], "fractions":{"R":..., "G":..., "B":...}},
          "next_piece_right": {"label":"B/B", "top":[("B",0.88)],            "fractions":{"R":..., "G":..., "B":...}}
        }
    """

    # Global gates; can be overridden per HSV swatch via "s" and "v" keys
    S_MIN = 55      # drop low-saturation pixels
    V_MIN = 55      # drop dark pixels
    MIN_PRIMARY = 0.25   # at least 25% of foreground for primary color
    MIN_SECONDARY = 0.15 # at least 15% for secondary color

    # Default swatches (equivalent to your fixed bands)
    DEFAULT_SWATCHES: Dict[str, List[Dict]] = {
        "R": [
            {"type": "hsv", "h": [0, 10]},    # reds near 0°
            {"type": "hsv", "h": [160, 179]}, # wrap-around reds
        ],
        "G": [
            {"type": "hsv", "h": [40, 85]},
        ],
        "B": [
            {"type": "hsv", "h": [95, 135]},
        ],
    }

    def __init__(
        self,
        detector: GameWindowDetector,
        log_callback: Optional[Callable[[str, str], None]] = None,
        shapes_json_path: Optional[str] = None,
        color_swatches: Optional[Dict[str, List[Dict]]] = None,
        swatches_json_path: Optional[str] = None,
    ):
        self.detector = detector
        self.log = log_callback or _default_log
        self._sct = mss.mss()
        self._baseline_w = 1280
        self._baseline_h = 720
        self._left: Optional[PolyShape] = None
        self._right: Optional[PolyShape] = None
        self._load_shapes(shapes_json_path)

        # Load color swatches (dict > JSON > defaults)
        self._swatches = self._load_color_swatches(color_swatches, swatches_json_path)
        # Precompute token order for stable outputs
        self._tokens = list(self._swatches.keys())
        if not self._tokens:
            raise RuntimeError("No color swatches defined (empty token set).")

        # Cache for scaled polygons & masks per window size
        self._roi_cache = {}  # {(w,h,label): (pts_abs, mask, bbox)}
        self._last_size = None

        # Stability tracking for validation pieces
        self._validation_history = {}  # {roi_label: [(timestamp, label, confidence), ...]}
        self._max_history_frames = 10  # Keep last N frames for stability analysis

        self.log(f"PieceRecognizer: loaded color swatches for tokens: {', '.join(self._tokens)}", "INFO")

    # ---------- shapes ----------
    def _resolve_tools_path(self, filename: str) -> str:
        here = os.path.abspath(os.path.dirname(__file__))
        if os.path.basename(here).lower() == "tools":
            return os.path.join(here, filename)
        if os.path.basename(here).lower() == "src":
            parent_dir = os.path.dirname(here)
            return os.path.join(parent_dir, "tools", filename)
        return os.path.join(here, "tools", filename)

    def _resolve_configuration_path(self, filename: str) -> str:
        here = os.path.abspath(os.path.dirname(__file__))
        if os.path.basename(here).lower() == "src":
            parent_dir = os.path.dirname(here)
            candidate = os.path.join(parent_dir, "configuration", filename)
            if os.path.exists(candidate):
                return candidate
        candidate = os.path.join(here, "configuration", filename)
        if os.path.exists(candidate):
            return candidate
        parent_dir = os.path.dirname(here)
        candidate = os.path.join(parent_dir, "configuration", filename)
        if os.path.exists(candidate):
            return candidate
        return os.path.join(here, filename)

    def _load_shapes(self, shapes_json_path: Optional[str]) -> None:
        path = shapes_json_path or self._resolve_configuration_path("object_shapes.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        cap = data.get("captured_image_size", {}) or {}
        self._baseline_w = int(cap.get("width", 1280))
        self._baseline_h = int(cap.get("height", 720))

        left = right = None
        validation_left = validation_right = None
        for sh in data.get("shapes", []):
            if sh.get("type") != "polygon":
                continue
            label = sh.get("label", "")
            if label in ("next_piece_left", "next_piece_right", "validation_left", "validation_right"):
                pts = [(float(x), float(y)) for x, y in sh["pts"]]
                poly = PolyShape(
                    label=label,
                    category=sh.get("category", "area"),
                    color=sh.get("color", "#00ff6b"),
                    closed=bool(sh.get("closed", True)),
                    pts=pts,
                )
                if label == "next_piece_left":
                    left = poly
                elif label == "next_piece_right":
                    right = poly
                elif label == "validation_left":
                    validation_left = poly
                elif label == "validation_right":
                    validation_right = poly

        self._left, self._right = left, right
        self._validation_left, self._validation_right = validation_left, validation_right
        if not self._left or not self._right:
            raise RuntimeError("next_piece_left / next_piece_right polygons not found in object_shapes.json (configuration folder)")
        if not self._validation_left or not self._validation_right:
            self.log("WARNING: validation_left / validation_right polygons not found in object_shapes.json (configuration folder)", "WARNING")

        self.log("PieceRecognizer: loaded next-piece polygons.", "INFO")

    # ---------- swatches ----------
    def _load_color_swatches(
        self,
        color_swatches: Optional[Dict[str, List[Dict]]],
        swatches_json_path: Optional[str],
    ) -> Dict[str, List[Dict]]:
        swatches = None
        if color_swatches:
            swatches = color_swatches
        elif swatches_json_path:
            path = swatches_json_path
            if not os.path.isabs(path):
                path = self._resolve_tools_path(path)
            with open(path, "r", encoding="utf-8") as f:
                swatches = json.load(f)
        else:
            swatches = self.DEFAULT_SWATCHES

        # Normalize/validate
        norm: Dict[str, List[Dict]] = {}
        for token, arr in swatches.items():
            out = []
            for sw in arr:
                t = (sw.get("type") or "hsv").lower()
                if t == "hsv":
                    h = sw.get("h")
                    if not h or len(h) != 2:
                        raise ValueError(f"HSV swatch for '{token}' missing 'h':[lo,hi]")
                    # Optional S/V per-swatch; fallback to class gates
                    s = sw.get("s")
                    v = sw.get("v")
                    out.append({"type": "hsv", "h": [int(h[0]), int(h[1])],
                                "s": [int(s[0]), int(s[1])] if s else None,
                                "v": [int(v[0]), int(v[1])] if v else None})
                elif t == "bgr":
                    bgr = sw.get("bgr")
                    tol = int(sw.get("tol", 32))
                    if not bgr or len(bgr) != 3:
                        raise ValueError(f"BGR swatch for '{token}' must have 'bgr':[B,G,R]")
                    out.append({"type": "bgr", "bgr": [int(bgr[0]), int(bgr[1]), int(bgr[2])], "tol": tol})
                else:
                    raise ValueError(f"Unknown swatch type '{t}' for token '{token}'")
            if out:
                norm[token] = out

        return norm

    # ---------- capture & classify ----------
    def _capture_client(self) -> Tuple[np.ndarray, Tuple[int, int]]:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                rect = self.detector.get_window_rect(kind="client")
                if not rect:
                    if attempt < max_retries - 1:
                        time.sleep(0.1)  # Brief pause before retry
                        continue
                    raise RuntimeError("No TLOPO client area found")
                
                l, t, r, b = rect
                w, h = int(r - l), int(b - t)
                shot = self._sct.grab({"left": int(l), "top": int(t), "width": w, "height": h})
                frame = np.asarray(shot)  # BGRA
                return frame, (w, h)
                
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(0.1)  # Brief pause before retry
                    continue
                # Re-raise the exception if all retries failed
                raise RuntimeError("No TLOPO client area found") from e
        
        # This line should never be reached due to the exception handling above,
        # but is required to satisfy the return type checker
        raise RuntimeError("Failed to capture client area after all retries")

    def _scale_pts(self, pts: List[Tuple[float, float]], w: int, h: int) -> List[Tuple[int, int]]:
        tr = _calc_aspect_ratio_transform(self._baseline_w, self._baseline_h, w, h)
        sx, sy, ox, oy = tr["scale_x"], tr["scale_y"], tr["offset_x"], tr["offset_y"]
        out = []
        for x, y in pts:
            xx = int(round(x * sx + ox))
            yy = int(round(y * sy + oy))
            out.append((xx, yy))
        return out

    def _get_roi_geom(self, w: int, h: int, poly: PolyShape) -> Tuple[List[Tuple[int, int]], np.ndarray, Tuple[int, int, int, int]]:
        """
        Get cached or compute scaled polygon points, mask, and bbox for given window size.
        Returns: (pts_abs, roi_mask, (bx, by, bw, bh))
        """
        key = (w, h, poly.label)
        cached = self._roi_cache.get(key)
        if cached:
            return cached
        
        # Compute scaled points
        pts_abs = self._scale_pts(poly.pts, w, h)
        
        # Get bbox and local coordinates
        roi_bgra_dummy, pts_local, (bx, by, bw, bh) = _crop_to_polygon(np.zeros((h, w, 4), np.uint8), pts_abs)
        
        # Create mask for the polygon
        roi_mask = _polygon_mask_local(bh, bw, pts_local)
        
        # Cache the result
        result = (pts_abs, roi_mask, (bx, by, bw, bh))
        self._roi_cache[key] = result
        return result

    def _normalize_h(self, lo: int, hi: int) -> Tuple[int, int]:
        """
        Normalize hue bounds for current HSV scale:
          - OpenCV: H in [0,179]
          - Fallback: H in [0,255]
        Input lo/hi are assumed to be OpenCV-style (0..179). If fallback path, rescale.
        """
        if CV2 and cv2 is not None:
            return max(0, lo), min(179, hi)
        # scale 0..179 -> 0..255
        scale = 255.0 / 179.0
        return int(round(lo * scale)), int(round(hi * scale))

    def _classify_roi(self, frame_bgra: np.ndarray, hsv: np.ndarray, mask: np.ndarray) -> Dict[str, float]:
        """
        Returns normalized fractions for each token inside foreground S,V thresholds.
        Applies per-token UNION over swatches.
        """
        H = hsv[..., 0].astype(np.uint16)
        S = hsv[..., 1]
        V = hsv[..., 2]
        BGR = frame_bgra[..., :3]  # (H,W,3), B,G,R order

        # Foreground selection: decent saturation/brightness + inside polygon mask
        base_fg = (S >= self.S_MIN) & (V >= self.V_MIN) & (mask > 0)
        total = int(base_fg.sum())
        if total == 0:
            return {tok: 0.0 for tok in self._tokens}

        def hue_in_range(h_img: np.ndarray, lo: int, hi: int) -> np.ndarray:
            if lo <= hi:
                return (h_img >= lo) & (h_img <= hi)
            # wrap-around band
            return (h_img >= lo) | (h_img <= hi)

        fractions: Dict[str, float] = {}

        for token, swatches in self._swatches.items():
            union = np.zeros_like(base_fg, dtype=bool)

            for sw in swatches:
                stype = sw["type"]
                if stype == "hsv":
                    lo, hi = self._normalize_h(int(sw["h"][0]), int(sw["h"][1]))
                    # optional per-swatch S/V windows
                    s_rng = sw.get("s")
                    v_rng = sw.get("v")
                    s_ok = (S >= (s_rng[0] if s_rng else self.S_MIN)) & (S <= (s_rng[1] if s_rng else 255))
                    v_ok = (V >= (v_rng[0] if v_rng else self.V_MIN)) & (V <= (v_rng[1] if v_rng else 255))
                    sel = hue_in_range(H, lo, hi) & s_ok & v_ok & (mask > 0)
                    union |= sel

                elif stype == "bgr":
                    b, g, r = sw["bgr"]
                    tol = int(sw["tol"])
                    # Euclidean distance in BGR space
                    diff = BGR.astype(np.int16) - np.array([b, g, r], dtype=np.int16)
                    dist2 = (diff * diff).sum(axis=2)  # squared distance
                    sel = (dist2 <= (tol * tol)) & base_fg
                    union |= sel

            count = int(union.sum())
            fractions[token] = count / total if total else 0.0

        return fractions

    def _classify_roi_fast(self, roi_bgra, hsv_roi, poly_mask):
        H = hsv_roi[...,0].astype(np.uint8); S = hsv_roi[...,1]; V = hsv_roi[...,2]
        roi_bgr = roi_bgra[..., :3]
        base_fg = (S >= self.S_MIN) & (V >= self.V_MIN) & (poly_mask > 0)

        total = int(base_fg.sum())
        if total == 0:
            return {tok: 0.0 for tok in self._tokens}

        fractions = {}
        for token, swatches in self._swatches.items():
            union = np.zeros(poly_mask.shape, dtype=np.uint8)

            # HSV ranges
            for sw in (s for s in swatches if s["type"] == "hsv"):
                lo, hi = self._normalize_h(int(sw["h"][0]), int(sw["h"][1]))
                s_rng = sw.get("s"); v_rng = sw.get("v")
                smin, smax = (s_rng if s_rng else (self.S_MIN, 255))
                vmin, vmax = (v_rng if v_rng else (self.V_MIN, 255))
                h_ok = ((H >= lo) & (H <= hi)) if lo <= hi else ((H >= lo) | (H <= hi))
                sel = h_ok & (S >= smin) & (S <= smax) & (V >= vmin) & (V <= vmax) & (poly_mask > 0)
                union |= sel.astype(np.uint8)

            # BGR center+tol via inRange union
            if CV2 and cv2 is not None:
                for sw in (s for s in swatches if s["type"] == "bgr"):
                    b,g,r = sw["bgr"]; t = int(sw["tol"])
                    low  = np.array([max(0, b - t), max(0, g - t), max(0, r - t)], dtype=np.uint8)
                    high = np.array([min(255, b + t), min(255, g + t), min(255, r + t)], dtype=np.uint8)
                    union |= cv2.inRange(roi_bgr, low, high)

            # gate by foreground (polygon + S/V)
            union &= base_fg.astype(np.uint8)
            fractions[token] = int((union > 0).sum()) / total

        return fractions

    @staticmethod
    def _label_from_fractions(frac: Dict[str, float],
                              min_primary: float,
                              min_secondary: float) -> Tuple[str, List[Tuple[str, float]]]:
        # Sort by coverage
        ordered = sorted(frac.items(), key=lambda kv: kv[1], reverse=True)
        top = [(k, v) for k, v in ordered if v >= 1e-6]

        if not top or top[0][1] < min_primary:
            return "Unknown", top[:3]

        # For individual pieces, just return the strongest color
        # No need for compound labels like "G/B" - just the primary color
        primary_color = top[0][0]
        return primary_color, top[:3]  # Return top 3 for debugging info

    def _calculate_confidence(self, fractions: Dict[str, float]) -> float:
        """
        Calculate confidence score based on how clearly defined the primary color is.
        Higher confidence = more distinct primary color vs background/other colors.
        """
        if not fractions:
            return 0.0
        
        values = list(fractions.values())
        if not values:
            return 0.0
            
        # Primary color coverage
        primary = max(values)
        if primary < 0.1:  # Very low coverage
            return 0.0
            
        # Calculate separation between primary and secondary colors
        sorted_vals = sorted(values, reverse=True)
        if len(sorted_vals) > 1:
            secondary = sorted_vals[1]
            separation = primary - secondary
            # Confidence based on both primary strength and separation
            confidence = min(1.0, primary * (1.0 + separation))
        else:
            confidence = primary
            
        return confidence

    def _update_validation_history(self, roi_label: str, label: str, confidence: float) -> bool:
        """
        Update history for a validation ROI and return whether it's stable.
        """
        import time
        timestamp = time.time()
        
        if roi_label not in self._validation_history:
            self._validation_history[roi_label] = []
            
        history = self._validation_history[roi_label]
        history.append((timestamp, label, confidence))
        
        # Keep only recent frames
        if len(history) > self._max_history_frames:
            history.pop(0)
            
        return True  # Will be used by pieces_ready_to_drop for stability check

    def detect_next_pieces(self) -> Dict[str, Dict]:
        """
        Capture once and classify both next-piece ROIs.
        Returns a dict with per-ROI labels and ratios.
        """
        frame, (w, h) = self._capture_client()
        
        # Invalidate cache when window size changes
        if getattr(self, "_last_size", None) != (w, h):
            self._roi_cache.clear()
        self._last_size = (w, h)

        results: Dict[str, Dict] = {}
        for poly in (self._left, self._right):
            assert poly is not None

            # Get cached or compute ROI geometry
            pts_abs, roi_mask, (bx, by, bw, bh) = self._get_roi_geom(w, h, poly)

            # Crop the actual frame data using the cached bbox
            roi_bgra = frame[by:by+bh, bx:bx+bw].copy()

            # (optional) downscale to speed up classification
            roi_bgra, roi_mask = _resize_pair(roi_bgra, roi_mask, max_side=140)

            # convert ONLY the ROI to HSV
            hsv_roi = _bgra_to_hsv(roi_bgra)

            # classify ONLY masked pixels inside the polygon
            frac = self._classify_roi_fast(roi_bgra, hsv_roi, roi_mask)
            label, top = self._label_from_fractions(frac, self.MIN_PRIMARY, self.MIN_SECONDARY)

            results[poly.label] = {
                "label": label,
                "top": [(c, round(p, 3)) for c, p in top],
                "fractions": {k: round(v, 3) for k, v in frac.items()},
                "n_pixels": int((roi_mask > 0).sum()),
                "roi_size": (int(bw), int(bh)),
            }
            # Only log for next_pieces to reduce lag during validation
            if "next_piece" in poly.label:
                self.log(f"• {poly.label}: bbox={bw}x{bh}, masked={int((roi_mask>0).sum())} px → {label}", "INFO")

        return results

    def detect_validation_pieces(self) -> Dict[str, Dict]:
        """
        Capture once and classify both validation ROIs (left/right validation areas).
        Returns a dict with per-ROI labels and ratios.
        This method is used to validate that pieces are ready to be dropped.
        """
        if not self._validation_left or not self._validation_right:
            return {}
            
        frame, (w, h) = self._capture_client()
        
        # Invalidate cache when window size changes
        if getattr(self, "_last_size", None) != (w, h):
            self._roi_cache.clear()
        self._last_size = (w, h)

        results: Dict[str, Dict] = {}
        for poly in (self._validation_left, self._validation_right):
            assert poly is not None

            # Get cached or compute ROI geometry
            pts_abs, roi_mask, (bx, by, bw, bh) = self._get_roi_geom(w, h, poly)

            # Crop the actual frame data using the cached bbox
            roi_bgra = frame[by:by+bh, bx:bx+bw].copy()

            # (optional) downscale to speed up classification
            roi_bgra, roi_mask = _resize_pair(roi_bgra, roi_mask, max_side=140)

            # convert ONLY the ROI to HSV
            hsv_roi = _bgra_to_hsv(roi_bgra)

            # classify ONLY masked pixels inside the polygon
            frac = self._classify_roi_fast(roi_bgra, hsv_roi, roi_mask)
            label, top = self._label_from_fractions(frac, self.MIN_PRIMARY, self.MIN_SECONDARY)
            
            # Calculate confidence and update history
            confidence = self._calculate_confidence(frac)
            self._update_validation_history(poly.label, label, confidence)

            results[poly.label] = {
                "label": label,
                "top": [(c, round(p, 3)) for c, p in top],
                "fractions": {k: round(v, 3) for k, v in frac.items()},
                "confidence": round(confidence, 3),
                "n_pixels": int((roi_mask > 0).sum()),
                "roi_size": (int(bw), int(bh)),
            }
            # Validation logging removed to prevent lag

        return results

    def pieces_ready_to_drop(self, min_stable_frames: int = 3, min_conf: float = 0.35) -> Tuple[bool, Dict]:
        """
        Validate that pieces are ready to be dropped by checking stability across multiple frames.
        
        Args:
            min_stable_frames: Minimum number of consecutive stable frames required
            min_conf: Minimum confidence score required for piece detection
            
        Returns:
            Tuple of (ready: bool, info: dict with details and reasons)
        """
        res = self.detect_validation_pieces()
        if not res:
            return False, {"reason": "no_validation_rois", "latest": {}}

        both_ok = True
        reasons = []
        
        for key in ("validation_left", "validation_right"):
            r = res.get(key, {})
            if not r:
                both_ok = False
                reasons.append(f"{key}:no_read")
                continue
                
            # Check confidence
            confidence = r.get("confidence", 0.0)
            if confidence < min_conf:
                both_ok = False
                reasons.append(f"{key}:low_conf ({confidence:.2f})")
                
            # Check pixel count (minimum mask size)
            n_pixels = r.get("n_pixels", 0)
            if n_pixels < 100:
                both_ok = False
                reasons.append(f"{key}:small_mask ({n_pixels}px)")
                
            # Check stability across recent frames
            history = self._validation_history.get(key, [])
            if len(history) < min_stable_frames:
                both_ok = False
                reasons.append(f"{key}:insufficient_history ({len(history)}/{min_stable_frames})")
                r["stable"] = False
            else:
                # Check last N frames for stability
                recent = history[-min_stable_frames:]
                current_label = r.get("label", "Unknown")
                
                # All recent frames should have the same label and good confidence
                stable = True
                for _, hist_label, hist_conf in recent:
                    if hist_label != current_label or hist_conf < min_conf * 0.8:  # Slightly lower threshold for history
                        stable = False
                        break
                        
                r["stable"] = stable
                if not stable:
                    both_ok = False
                    reasons.append(f"{key}:unstable")
                    
        return both_ok, {"latest": res, "reasons": reasons}


# ---------- quick sanity test ----------
if __name__ == "__main__":
    det = GameWindowDetector(log_callback=_default_log)
    det.start_detection()
    time.sleep(1.0)
    pr = PieceRecognizer(detector=det, log_callback=_default_log)
    try:
        out = pr.detect_next_pieces()
        print(out)
    finally:
        det.cleanup()
