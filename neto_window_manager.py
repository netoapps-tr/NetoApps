"""Lightweight multi-display placement helpers for NetOps windows.

The manager only handles geometry and persisted assignments. It never starts a
second application process and it never executes a system command.
"""

from __future__ import annotations

import ctypes
import json
from pathlib import Path
from typing import Any, Callable


WINDOW_OPTIONS = (
    ("assistant", "Asistan"),
    ("now_playing", "Now Playing"),
    ("automation", "Otomasyon"),
    ("none", "Boş"),
)
DEFAULT_ASSIGNMENTS = {"1": "assistant", "2": "now_playing", "3": "automation"}


def _monitor_enum_callback():
    monitors: list[dict[str, int]] = []
    if not hasattr(ctypes, "windll"):
        return monitors

    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    MONITORINFOF_PRIMARY = 1

    @ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
                        ctypes.POINTER(RECT), ctypes.c_double)
    def callback(_monitor, _dc, rect, _data):
        monitors.append({
            "x": int(rect.contents.left),
            "y": int(rect.contents.top),
            "width": int(rect.contents.right - rect.contents.left),
            "height": int(rect.contents.bottom - rect.contents.top),
            "primary": int(rect.contents.left) == 0 and int(rect.contents.top) == 0,
        })
        return 1

    try:
        ctypes.windll.user32.EnumDisplayMonitors(None, None, callback, 0)
    except Exception:
        return []
    return monitors


def monitors(root=None) -> list[dict[str, int]]:
    found = _monitor_enum_callback()
    if found:
        return found
    try:
        return [{
            "x": 0,
            "y": 0,
            "width": int(root.winfo_screenwidth()),
            "height": int(root.winfo_screenheight()),
        }]
    except Exception:
        return [{"x": 0, "y": 0, "width": 1280, "height": 720}]


def primary_monitor_index(screens: list[dict[str, int]]) -> int:
    for index, screen in enumerate(screens or []):
        if bool(screen.get("primary")) or (int(screen.get("x", 0)) == 0 and int(screen.get("y", 0)) == 0):
            return index
    return 0


def normalize_assignments(value: Any, count: int | None = None) -> dict[str, str]:
    source = value if isinstance(value, dict) else {}
    result = dict(DEFAULT_ASSIGNMENTS)
    for key, selected in source.items():
        key = str(key)
        if key.isdigit() and key not in {"0"}:
            allowed = {item[0] for item in WINDOW_OPTIONS}
            result[key] = str(selected) if str(selected) in allowed else "none"
    if count is not None:
        for index in range(1, max(1, int(count)) + 1):
            result.setdefault(str(index), "none")
    return result


def display_index_for(assignments: dict[str, str], target: str) -> int | None:
    for key, value in normalize_assignments(assignments).items():
        if value == target:
            try:
                return max(0, int(key) - 1)
            except ValueError:
                continue
    return None


def place_window(window, display_index: int | None, root=None, *, fullscreen=False):
    if window is None:
        return False
    screens = monitors(root)
    if not screens:
        return False
    primary_index = primary_monitor_index(screens)
    if display_index is None:
        resolved_index = primary_index
    else:
        display_index = int(display_index)
        # If a saved second/third monitor is unplugged, never open off-screen or
        # clamp to another secondary. Fall back to the primary/default monitor.
        resolved_index = display_index if 0 <= display_index < len(screens) else primary_index
    screen = screens[resolved_index]
    try:
        window.update_idletasks()
        if fullscreen:
            # Windows chooses the current monitor when fullscreen is enabled.
            # Use a borderless geometry instead of Tk's fullscreen flag. Tk's
            # fullscreen flag always resolves against the primary monitor.
            try:
                window.attributes("-fullscreen", False)
            except Exception:
                pass
            try:
                window.overrideredirect(True)
            except Exception:
                pass
            window.geometry(
                f"{screen['width']}x{screen['height']}+{screen['x']}+{screen['y']}"
            )
            window.update_idletasks()
        else:
            width = min(max(720, int(window.winfo_width() or 950)), screen["width"])
            height = min(max(520, int(window.winfo_height() or 694)), screen["height"])
            x = screen["x"] + max(0, (screen["width"] - width) // 2)
            y = screen["y"] + max(0, (screen["height"] - height) // 2)
            window.geometry(f"{width}x{height}+{x}+{y}")
        return True
    except Exception:
        return False


def apply_layout(root, assignments: Any, *, windows: dict[str, Any] | None = None):
    """Place known windows without opening or closing any of them."""
    config = normalize_assignments(assignments)
    windows = windows or {}
    changed = []
    for name, window in windows.items():
        index = display_index_for(config, name)
        if index is not None and place_window(window, index, root, fullscreen=name == "now_playing"):
            changed.append(name)
    return changed


def save_assignments(data: dict[str, Any], assignments: Any) -> dict[str, Any]:
    data["neto_window_assignments"] = normalize_assignments(assignments)
    return data
