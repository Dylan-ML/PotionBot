# drop_piece.py
"""
PotionGod – Drop controller (Primed + Auto-loop)

Flow
----
1) Pre-scan & buffer the NEXT pair.
2) Prompt: User manually places the *already held* piece, then presses Enter to start.
3) Drop the buffered pair (flip if needed).
4) Auto-loop forever: [rescan/buffer] → wait interval → drop → repeat. Esc stops.

Notes
-----
- All timing knobs come from configuration/delays.json (with safe defaults).
- The JSON may include enter_timeout_s and loop_enter_timeout_s (kept as null here).
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
import random
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple, Union

# -------- Win32 input ----------
user32 = ctypes.windll.user32
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
GetAsyncKeyState = user32.GetAsyncKeyState
SetCursorPos      = user32.SetCursorPos
SendInput         = user32.SendInput
PUL = ctypes.POINTER(ctypes.c_ulong)

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long), ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong), ("dwExtraInfo", PUL)]

class INPUT(ctypes.Structure):
    class _I(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]
    _anonymous_ = ("i",)
    _fields_ = [("type", ctypes.c_ulong), ("i", _I)]

MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP = 0x0008, 0x0010

def _mouse_left_click(hold_ms: int):
    down = INPUT(type=0); down.mi = MOUSEINPUT(0,0,0,MOUSEEVENTF_LEFTDOWN,0,None)
    SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT))
    if hold_ms and hold_ms > 0: time.sleep(hold_ms/1000.0)
    up = INPUT(type=0); up.mi = MOUSEINPUT(0,0,0,MOUSEEVENTF_LEFTUP,0,None)
    SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT))

def _mouse_right_click(hold_ms: int):
    down = INPUT(type=0); down.mi = MOUSEINPUT(0,0,0,MOUSEEVENTF_RIGHTDOWN,0,None)
    SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT))
    if hold_ms and hold_ms > 0: time.sleep(hold_ms/1000.0)
    up = INPUT(type=0); up.mi = MOUSEINPUT(0,0,0,MOUSEEVENTF_RIGHTUP,0,None)
    SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT))

def _consume_key_press(vk_code: int) -> bool:
    """True if key was pressed since last call (low-order bit)."""
    return (GetAsyncKeyState(vk_code) & 0x0001) != 0

def _check_escape_pressed() -> bool:
    """Check if escape key is currently pressed or was pressed since last check."""
    return (GetAsyncKeyState(VK_ESCAPE) & 0x8000) != 0 or _consume_key_press(VK_ESCAPE)

# -------- helpers ----------
def _default_log(msg: str, level: str = "INFO"):
    print(f"[{level}] {msg}")

def _resolve_path(rel_folder: str, filename: str) -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    p = os.path.join(here, rel_folder, filename)
    if os.path.exists(p): return p
    p = os.path.join(os.path.dirname(here), rel_folder, filename)
    if os.path.exists(p): return p
    return os.path.join(here, filename)

def _shapes_path() -> str: return _resolve_path("configuration", "object_shapes.json")
def _delays_path() -> str: return _resolve_path("configuration", "delays.json")

def _calc_tf(ow:int, oh:int, cw:int, ch:int) -> Dict[str,float]:
    oa, ca = ow/max(1,oh), cw/max(1,ch)
    if abs(oa-ca) < 0.01:
        s = min(cw/ow, ch/oh)
        return dict(scale_x=s, scale_y=s, offset_x=(cw-ow*s)/2, offset_y=(ch-oh*s)/2)
    if ca > oa:  # pillarbox
        s = ch/oh; sw = ow*s
        return dict(scale_x=s, scale_y=s, offset_x=(cw-sw)/2, offset_y=0.0)
    s = cw/ow; sh = oh*s  # letterbox
    return dict(scale_x=s, scale_y=s, offset_x=0.0, offset_y=(ch-sh)/2)

@dataclass
class Box:
    label: str
    x0: float; y0: float; x1: float; y1: float

# -------- controller ----------
class DropPieceController:
    """Primed start + auto loop (2s default), Esc to stop."""

    DEFAULTS: Dict[str, Union[Optional[int], Dict[str, Any]]] = {
        # key polling
        "enter_poll_ms": 30,
        # present in JSON for future modes; kept as None/null here
        "enter_timeout_s": None,
        "loop_enter_timeout_s": None,

        # mouse
        "mouse_move_duration_ms": 120,
        "pre_left_click_sleep_ms": 10,
        "left_click_hold_ms": 25,
        "post_left_click_sleep_ms": 20,

        "pre_right_click_sleep_ms": 10,
        "right_click_hold_ms": 25,
        "flip_click_delay_ms": 60,

        # validation
        "validation_mouse_park_delay_ms": 100,    # delay after parking mouse before validation
        "validation_initial_delay_ms": 500,       # initial delay before first validation attempt
        "validation_retry_delay_ms": 200,         # delay between validation attempts
        "validation_max_attempts": 5,             # max validation attempts

        # cadence
        "post_enter_settle_ms": 80,        # after initial Enter
        "post_drop_sleep_ms": 40,          # tiny pause after click
        "rescan_after_drop_delay_ms": 80,  # give game time to update next area
        "auto_loop_interval_ms": 2000,     # <<< 2 seconds between drops
        
        # new defaults
        "mouse_jitter_px": 2,              # center click jitter radius in px
        "pair_overrides": {}               # per-pair timing overrides
    }

    def __init__(self, detector, piece_recognizer, log_callback: Optional[Callable[[str,str],None]]=None):
        self.detector = detector
        self.recog = piece_recognizer
        self.log = log_callback or _default_log

        self.cfg: Dict[str, Any] = dict(self.DEFAULTS)
        self._baseline_w, self._baseline_h = 1280, 720
        self._drop_boxes: Dict[str, Box] = {}
        self._mouse_parking: Optional[Box] = None

        self._load_shapes()
        self._load_cfg(quiet=True)

    def _coerce_num(self, v, default=None):
        if v is None:
            return default
        if isinstance(v, (int, float)):
            return int(v)
        if isinstance(v, str):
            s = v.strip().lower()
            if s == "null":
                return None
            try:
                return int(float(v))
            except Exception:
                return default
        return default

    def _cfg(self, key: str, pair: Optional[str] = None):
        """
        Read a config value, honoring pair_overrides[pair][key] if present.
        Falls back to global self.cfg[key].
        """
        if pair:
            po = self.cfg.get("pair_overrides") or {}
            mp = po.get(pair)
            if isinstance(mp, dict) and key in mp:
                # Coerce numbers when the global is numeric; otherwise return raw
                base = self.cfg.get(key)
                if isinstance(base, (int, float)) or key.endswith("_ms") or key.endswith("_px"):
                    return self._coerce_num(mp[key], base)
                return mp[key]
        return self.cfg.get(key)

    # ----- io -----
    def _load_cfg(self, quiet=False):
        path = _delays_path()
        try:
            if os.path.exists(path):
                with open(path,"r",encoding="utf-8") as f:
                    loaded = json.load(f) or {}
                for k,v in self.DEFAULTS.items():
                    if k == "pair_overrides":
                        # take nested dict as-is if present
                        po = loaded.get("pair_overrides")
                        if isinstance(po, dict):
                            self.cfg["pair_overrides"] = po
                        else:
                            self.cfg["pair_overrides"] = {}
                        continue

                    val = loaded.get(k, v)
                    if isinstance(val,str) and val.strip().lower()=="null":
                        val = None
                    elif isinstance(val, str) and val.isdigit():
                        val = int(val)
                    self.cfg[k]=val
            elif not quiet:
                self.log(f"No delays.json at {path}. Using defaults.", "WARNING")
        except Exception as e:
            self.log(f"Failed to read delays.json: {e}. Using defaults.", "WARNING")
        if not quiet:
            self.log(f"Delays: {self.cfg}", "INFO")

    def _load_shapes(self):
        with open(_shapes_path(),"r",encoding="utf-8") as f:
            data = json.load(f)
        cap = data.get("captured_image_size",{}) or {}
        self._baseline_w = int(cap.get("width",1280))
        self._baseline_h = int(cap.get("height",720))
        self._drop_boxes.clear()
        self._mouse_parking = None
        for sh in data.get("shapes",[]):
            if sh.get("type")=="box":
                label = str(sh.get("label",""))
                if label.startswith("drop_"):
                    self._drop_boxes[sh["label"]] = Box(sh["label"], float(sh["x0"]), float(sh["y0"]),
                                                        float(sh["x1"]), float(sh["y1"]))
                elif label == "mouse_parking":
                    self._mouse_parking = Box(sh["label"], float(sh["x0"]), float(sh["y0"]),
                                            float(sh["x1"]), float(sh["y1"]))
        if not self._drop_boxes:
            raise RuntimeError("No drop_* boxes found in object_shapes.json (now in configuration folder)")
        self.log(f"Loaded drop boxes: {', '.join(sorted(self._drop_boxes.keys()))}", "INFO")
        if self._mouse_parking:
            self.log(f"Loaded mouse parking area", "INFO")
        else:
            self.log(f"No mouse_parking area found - validation will be skipped", "WARNING")

    # ----- waits -----
    def _wait_for_enter_or_esc(self) -> str:
        """Block until Enter or Esc. Return 'enter' or 'esc'."""
        poll = int(self.cfg.get("enter_poll_ms") or 30)
        while True:
            if (GetAsyncKeyState(VK_RETURN) & 0x8000):
                while (GetAsyncKeyState(VK_RETURN) & 0x8000): time.sleep(0.01)
                return "enter"
            if (GetAsyncKeyState(VK_ESCAPE) & 0x8000):
                while (GetAsyncKeyState(VK_ESCAPE) & 0x8000): time.sleep(0.01)
                return "esc"
            time.sleep(poll/1000.0)

    def _sleep_with_esc(self, ms:int) -> bool:
        """Sleep up to ms; return True if Esc pressed (to stop)."""
        poll = int(self.cfg.get("enter_poll_ms") or 30)
        end = time.time() + max(0, ms)/1000.0
        while time.time() < end:
            if _check_escape_pressed():
                while (GetAsyncKeyState(VK_ESCAPE) & 0x8000): time.sleep(0.01)
                return True
            time.sleep(min(poll, max(1, int((end-time.time())*1000)))/1000.0)
        return False

    # ----- geom/mouse -----
    def _calc_tf(self, cw:int, ch:int) -> Dict[str,float]:
        return _calc_tf(self._baseline_w, self._baseline_h, cw, ch)

    def _scale_box(self, b:Box, cw:int, ch:int) -> Tuple[int,int,int,int]:
        tf = self._calc_tf(cw, ch)
        x0 = int(tf["offset_x"] + b.x0*tf["scale_x"]); y0 = int(tf["offset_y"] + b.y0*tf["scale_y"])
        x1 = int(tf["offset_x"] + b.x1*tf["scale_x"]); y1 = int(tf["offset_y"] + b.y1*tf["scale_y"])
        return x0,y0,x1,y1

    def _move_mouse(self, sx:int,sy:int, ex:int,ey:int, dur_ms:int):
        steps = max(6, dur_ms//10)
        for i in range(1, steps+1):
            t = i/steps
            SetCursorPos(int(sx+(ex-sx)*t), int(sy+(ey-sy)*t))
            time.sleep(dur_ms/steps/1000.0)

    def _left_click_at(self, x:int, y:int, smooth_from: Optional[Tuple[int,int]]=None, pair: Optional[str]=None):
        mv   = int(self._cfg("mouse_move_duration_ms", pair) or 120)
        pre  = int(self._cfg("pre_left_click_sleep_ms", pair) or 0)
        hold = int(self._cfg("left_click_hold_ms",      pair) or 0)
        post = int(self._cfg("post_left_click_sleep_ms",pair) or 0)
        if smooth_from: self._move_mouse(smooth_from[0], smooth_from[1], x, y, mv)
        else: SetCursorPos(x, y)
        if pre>0: time.sleep(pre/1000.0)
        _mouse_left_click(hold)
        if post>0: time.sleep(post/1000.0)

    def _right_click_center(self, left:int, top:int, cw:int, ch:int):
        pre  = int(self.cfg.get("pre_right_click_sleep_ms") or 0)
        hold = int(self.cfg.get("right_click_hold_ms") or 0)
        flip = int(self.cfg.get("flip_click_delay_ms") or 0)
        cx = left + cw//2 + int(random.uniform(-3,3))
        cy = top  + ch//2 + int(random.uniform(-3,3))
        SetCursorPos(cx, cy)
        if pre>0: time.sleep(pre/1000.0)
        _mouse_right_click(hold)
        if flip>0: time.sleep(flip/1000.0)

    # ----- recognition / drop -----
    def _validate_pieces_ready(self, expected_pair: str, max_attempts: Optional[int] = None) -> bool:
        """
        Park the mouse in the mouse_parking area and validate that the expected pieces
        are visible in the validation_left and validation_right areas.
        Returns True if pieces match the expected pair, False otherwise.
        """
        if not self._mouse_parking:
            self.log("No mouse_parking area defined - skipping validation", "WARNING")
            return True  # Skip validation if no parking area defined
            
        # Get window rect for mouse positioning
        rect = self.detector.get_window_rect(kind="client")
        if not rect:
            self.log("No game window detected for validation", "ERROR")
            return False
            
        left, top, right, bottom = rect
        cw, ch = max(1, right - left), max(1, bottom - top)
        
        # Calculate mouse parking position
        x0, y0, x1, y1 = self._scale_box(self._mouse_parking, cw, ch)
        park_x = int((x0 + x1) / 2)
        park_y = int((y0 + y1) / 2)
        screen_x, screen_y = left + park_x, top + park_y
        
        # Park the mouse
        SetCursorPos(screen_x, screen_y)
        park_delay = int(self.cfg.get("validation_mouse_park_delay_ms") or 100)
        time.sleep(park_delay / 1000.0)
        
        # Pair-aware delays
        initial_delay = int(self._cfg("validation_initial_delay_ms", expected_pair) or 500)
        retry_delay   = int(self._cfg("validation_retry_delay_ms",   expected_pair) or 200)
        
        time.sleep(initial_delay / 1000.0)
        
        # Use configured max attempts
        if max_attempts is None:
            max_attempts = int(self.cfg.get("validation_max_attempts") or 5)
        
        # Try validation multiple times
        for attempt in range(max_attempts):
            # Check for escape before each validation attempt
            if _check_escape_pressed():
                self.log("Validation interrupted by user (Esc)", "INFO")
                return False
                
            try:
                validation_result = self.recog.detect_validation_pieces()
                if not validation_result:
                    self.log("No validation areas detected", "WARNING")
                    return True  # Skip validation if no validation areas
                    
                val_left = validation_result.get("validation_left", {}).get("label", "Unknown")
                val_right = validation_result.get("validation_right", {}).get("label", "Unknown")
                
                if "Unknown" in (val_left, val_right):
                    if attempt < max_attempts - 1:
                        time.sleep(retry_delay / 1000.0)
                        continue
                    else:
                        self.log(f"Validation failed: Could not classify pieces after {max_attempts} attempts", "ERROR")
                        return False
                
                detected_pair = f"{val_left}{val_right}"
                if detected_pair == expected_pair:
                    return True
                else:
                    if attempt < max_attempts - 1:
                        # Use progressive delay - longer waits for later attempts
                        progressive_delay = retry_delay + (attempt * 100)  # Add 100ms per attempt
                        time.sleep(progressive_delay / 1000.0)
                        continue
                    else:
                        self.log(f"Validation failed: {detected_pair} != {expected_pair} after {max_attempts} attempts", "ERROR")
                        return False
                        
            except Exception as e:
                if attempt < max_attempts - 1:
                    self.log(f"Validation attempt {attempt + 1} failed: {e}", "WARNING")
                    time.sleep(retry_delay / 1000.0)
                    continue
                else:
                    self.log(f"Validation error after {max_attempts} attempts: {e}", "ERROR")
                    return False
        
        return False

    def _detect_next_pair_once(self) -> Optional[str]:
        max_retries = 3
        for attempt in range(max_retries):
            # Check for escape before each detection attempt
            if _check_escape_pressed():
                self.log("Piece detection interrupted by user (Esc)", "INFO")
                return None
                
            try:
                out = self.recog.detect_next_pieces()
                L = (out.get("next_piece_left")  or {}).get("label", "Unknown")
                R = (out.get("next_piece_right") or {}).get("label", "Unknown")
                if "Unknown" in (L,R):
                    if attempt < max_retries - 1:
                        self.log(f"Could not classify next pieces (attempt {attempt+1}): L={L}, R={R}", "WARNING")
                        time.sleep(0.2)
                        continue
                    self.log(f"Could not classify next pieces: L={L}, R={R}", "ERROR")
                    return None
                pair = f"{L}{R}"
                self.log(f"🧊 Buffered next pair: L={L}, R={R}", "SUCCESS")
                return pair
            except Exception as e:
                if attempt < max_retries - 1:
                    self.log(f"Piece detection failed (attempt {attempt+1}): {e}", "WARNING")
                    time.sleep(0.2)
                    continue
                self.log(f"Piece detection failed: {e}", "ERROR")
                return None
        return None

    def _drop_pair(self, pair:str, allow_flip:bool=True, validate_before_drop:bool=True) -> bool:
        # Check for escape at the start of drop operation
        if _check_escape_pressed():
            self.log("Drop operation interrupted by user (Esc)", "INFO")
            return False
            
        # Validate pieces are ready before attempting to drop
        if validate_before_drop:
            if not self._validate_pieces_ready(pair):
                self.log(f"Piece validation failed for pair '{pair}' - skipping drop", "ERROR")
                return False
        
        # Check for escape after validation
        if _check_escape_pressed():
            self.log("Drop operation interrupted by user (Esc)", "INFO")
            return False
        
        # Add retry logic for getting window rect
        max_retries = 3
        rect = None
        for attempt in range(max_retries):
            # Check for escape before each window detection attempt
            if _check_escape_pressed():
                self.log("Drop operation interrupted by user (Esc)", "INFO")
                return False
                
            rect = self.detector.get_window_rect(kind="client")
            if rect:
                break
            if attempt < max_retries - 1:
                time.sleep(0.1)
                continue
        
        if not rect:
            self.log("No game window detected.", "ERROR"); return False
        left, top, right, bottom = rect
        cw, ch = max(1, right-left), max(1, bottom-top)

        target = f"drop_{pair}"
        box = self._drop_boxes.get(target)

        if not box and allow_flip:
            rev = pair[::-1]
            rev_label = f"drop_{rev}"
            rev_box = self._drop_boxes.get(rev_label)
            if rev_box:
                self.log(f"No '{target}' in shapes; RIGHT-CLICK to flip → '{rev_label}'.", "INFO")
                self._right_click_center(left, top, cw, ch)
                target, box, pair = rev_label, rev_box, rev
                
                # Re-validate after flipping if validation is enabled
                if validate_before_drop:
                    if not self._validate_pieces_ready(pair):
                        self.log(f"Piece validation failed after flip for pair '{pair}' - aborting drop", "ERROR")
                        return False

        if not box:
            self.log(f"Missing drop target for '{pair}' (and reverse).", "ERROR")
            return False

        x0,y0,x1,y1 = self._scale_box(box, cw, ch)
        jitter = int(self._cfg("mouse_jitter_px", pair) or self._cfg("mouse_jitter_px") or 2)
        cx = int((x0+x1)/2 + random.uniform(-jitter, jitter))
        cy = int((y0+y1)/2 + random.uniform(-jitter, jitter))
        sx, sy = left + cx, top + cy

        cur = wintypes.POINT(); user32.GetCursorPos(ctypes.byref(cur))
        self._left_click_at(sx, sy, smooth_from=(cur.x, cur.y), pair=pair)

        post = int(self.cfg.get("post_drop_sleep_ms") or 0)
        if post>0: time.sleep(post/1000.0)

        self.log(f"Dropped '{pair}' at {target} (screen=({sx},{sy}))", "SUCCESS")
        return True

    # ===== Public: Primed auto loop (2s) =====
    def start_auto_after_prime(self, allow_flip: bool=True, auto_interval_ms: Optional[int]=None, enable_validation: bool=True):
        """
        Start once and run forever:
          - Pre-buffer the NEXT pair.
          - Prompt: user manually places current piece; press Enter to start (Esc cancels).
          - Drop buffered pair.
          - Auto-loop: every interval, rescan/buffer → drop. Esc stops.
          
        Args:
            allow_flip: Whether to allow right-click flipping if the exact pair isn't found
            auto_interval_ms: Time between drops in milliseconds 
            enable_validation: Whether to validate pieces are ready before dropping
        """
        interval = int(auto_interval_ms if auto_interval_ms is not None
                       else (self.cfg.get("auto_loop_interval_ms") or 2000))
        rescan_delay = int(self.cfg.get("rescan_after_drop_delay_ms") or 0)
        settle = int(self.cfg.get("post_enter_settle_ms") or 0)

        # Pre-buffer before any user action to avoid “third pair” bug
        self.log("⏳ Scanning next pair…", "INFO")
        pair = self._detect_next_pair_once()
        if not pair: return

        # Clear stale keys, then prime start
        _ = _consume_key_press(VK_RETURN); _ = _consume_key_press(VK_ESCAPE)
        self.log("🔧 Prime: place the CURRENT piece manually, then press Enter (Esc cancels).", "INFO")
        key = self._wait_for_enter_or_esc()
        if key != "enter":
            self.log("Canceled before start.", "INFO")
            return
        if settle>0: time.sleep(settle/1000.0)

        # Drop once immediately
        if not self._drop_pair(pair, allow_flip=allow_flip, validate_before_drop=enable_validation):
            self.log("Stopping: initial drop failed.", "ERROR")
            return
        last_drop = time.time()
        self.log(f"⏱ Auto-loop engaged: every {interval} ms. Press Esc to stop.", "INFO")

        # Loop forever until Esc
        while True:
            # let the game promote next→current
            if rescan_delay>0:
                if self._sleep_with_esc(rescan_delay): self.log("⏹ Stopped (Esc).", "INFO"); return

            # buffer next
            self.log("⏳ Scanning next pair…", "INFO")
            next_pair = self._detect_next_pair_once()
            if not next_pair:
                # Check if detection failed due to escape or other error
                if _check_escape_pressed():
                    self.log("⏹ Stopped (Esc).", "INFO")
                else:
                    self.log("Stopping: failed to detect next pair.", "ERROR")
                return

            # Check for escape after piece detection
            if _check_escape_pressed():
                self.log("⏹ Stopped (Esc).", "INFO")
                return

            # wait remaining time in interval (since last drop)
            elapsed_ms = int((time.time() - last_drop)*1000)
            remaining = interval - elapsed_ms
            if remaining > 0:
                if self._sleep_with_esc(remaining): self.log("⏹ Stopped (Esc).", "INFO"); return

            # drop
            if not self._drop_pair(next_pair, allow_flip=allow_flip, validate_before_drop=enable_validation):
                # Check if drop failed due to escape or other error
                if _check_escape_pressed():
                    self.log("⏹ Stopped (Esc).", "INFO")
                else:
                    self.log("Stopping: drop failed.", "ERROR")
                return
            last_drop = time.time()
            
            # Check for escape after drop operation
            if _check_escape_pressed():
                self.log("⏹ Stopped (Esc).", "INFO")
                return

    # --- Back-compat aliases (in case GUI calls older names) ---
    def start_continuous_drop(self, *args, **kwargs):
        return self.start_auto_after_prime(*args, **kwargs)

    def start_drop_loop(self, *args, **kwargs):
        return self.start_auto_after_prime(*args, **kwargs)

# -------- demo ----------
if __name__ == "__main__":
    from window_detector import GameWindowDetector
    from piece_recognition import PieceRecognizer

    def _log(msg, lvl="INFO"): print(f"[{lvl}] {msg}")

    det = GameWindowDetector(log_callback=_log); det.start_detection(); time.sleep(1.0)
    try:
        recog = PieceRecognizer(detector=det, log_callback=_log)
        dp = DropPieceController(detector=det, piece_recognizer=recog, log_callback=_log)
        dp.start_auto_after_prime(auto_interval_ms=2000)  # 2s cadence, Esc to stop
    finally:
        det.cleanup()
