from __future__ import annotations

import argparse
import hashlib
import json
import difflib
import os
import re
import subprocess
import sys
import time
import threading
import traceback
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus
from typing import Any


def _enable_windows_dpi_awareness() -> None:
    """Keep UIA rectangles and physical mouse coordinates in the same DPI space."""
    if os.name != "nt":
        return

    try:
        import ctypes

        user32 = ctypes.windll.user32
        try:
            # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
            if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
                return
        except Exception:
            pass

        try:
            shcore = ctypes.windll.shcore
            # PROCESS_PER_MONITOR_DPI_AWARE
            if shcore.SetProcessDpiAwareness(2) in (0, -2147024891):
                return
        except Exception:
            pass

        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass
    except Exception:
        pass


_enable_windows_dpi_awareness()

from neto_agent_crypto import (
    read_encrypted_json,
    secure_delete,
    write_live_status_json,
    write_vault_record,
)


class NetoSystemCursor:
    """Görev boyunca Windows'un gerçek sistem imlecini mor bir imleçle değiştirir."""

    _CURSOR_IDS = (
        32512,  # OCR_NORMAL
        32513,  # OCR_IBEAM
        32514,  # OCR_WAIT
        32515,  # OCR_CROSS
        32516,  # OCR_UP
        32642,  # OCR_SIZENWSE
        32643,  # OCR_SIZENESW
        32644,  # OCR_SIZEWE
        32645,  # OCR_SIZENS
        32646,  # OCR_SIZEALL
        32648,  # OCR_NO
        32649,  # OCR_HAND
        32650,  # OCR_APPSTARTING
        32651,  # OCR_HELP
        32671,  # OCR_PIN
        32672,  # OCR_PERSON
    )

    def __init__(self, enabled: bool):
        self.enabled = bool(enabled and os.name == "nt")
        self._installed = False
        self._cursor_path: Path | None = None
        self.error: str | None = None
        if self.enabled:
            self._install()
        try:
            import atexit
            atexit.register(self.close)
        except Exception:
            pass

    @staticmethod
    def _point_in_polygon(x: float, y: float, polygon: tuple[tuple[int, int], ...]) -> bool:
        inside = False
        previous = polygon[-1]
        for current in polygon:
            x1, y1 = previous
            x2, y2 = current
            if (y1 > y) != (y2 > y):
                crossing = (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-9) + x1
                if x < crossing:
                    inside = not inside
            previous = current
        return inside

    @classmethod
    def _cursor_bytes(cls) -> bytes:
        """32-bit, 32x32 gerçek Windows CUR dosyası üretir."""
        import struct

        width = 32
        height = 32
        hotspot_x = 3
        hotspot_y = 2
        polygon = (
            (2, 1),
            (2, 25),
            (8, 19),
            (14, 31),
            (20, 28),
            (14, 17),
            (26, 17),
        )

        inside: set[tuple[int, int]] = set()
        for y in range(height):
            for x in range(width):
                if cls._point_in_polygon(x + 0.5, y + 0.5, polygon):
                    inside.add((x, y))

        xor = bytearray()
        mask = bytearray()
        for y in range(height - 1, -1, -1):
            for x in range(width):
                if (x, y) not in inside:
                    xor.extend((0, 0, 0, 0))
                    continue
                boundary = any(
                    (x + dx, y + dy) not in inside
                    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
                )
                if boundary:
                    # BGRA: beyaz dış çizgi
                    xor.extend((255, 255, 255, 255))
                else:
                    # BGRA: Neto moru #8B5CF6
                    xor.extend((246, 92, 139, 255))

            row = bytearray(4)
            for x in range(width):
                if (x, y) not in inside:
                    row[x // 8] |= 1 << (7 - (x % 8))
            mask.extend(row)

        image_size = len(xor) + len(mask)
        bitmap_info = struct.pack(
            '<IiiHHIIiiII',
            40,
            width,
            height * 2,
            1,
            32,
            0,
            image_size,
            0,
            0,
            0,
            0,
        )
        image = bitmap_info + bytes(xor) + bytes(mask)
        directory = struct.pack('<HHH', 0, 2, 1)
        entry = struct.pack(
            '<BBBBHHII',
            width,
            height,
            0,
            0,
            hotspot_x,
            hotspot_y,
            len(image),
            22,
        )
        return directory + entry + image

    @staticmethod
    def restore_system_cursors() -> None:
        if os.name != "nt":
            return
        try:
            import ctypes
            user32 = ctypes.windll.user32
            user32.SystemParametersInfoW(0x0057, 0, None, 0)  # SPI_SETCURSORS
            for _ in range(32):
                if user32.ShowCursor(True) >= 0:
                    break
        except Exception:
            pass

    def _install(self) -> None:
        import ctypes
        import tempfile
        import uuid

        try:
            cursor_path = Path(tempfile.gettempdir()) / f"neto-purple-{uuid.uuid4().hex}.cur"
            cursor_path.write_bytes(self._cursor_bytes())
            self._cursor_path = cursor_path

            user32 = ctypes.windll.user32
            user32.LoadCursorFromFileW.argtypes = [ctypes.c_wchar_p]
            user32.LoadCursorFromFileW.restype = ctypes.c_void_p
            user32.SetSystemCursor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            user32.SetSystemCursor.restype = ctypes.c_bool
            user32.DestroyCursor.argtypes = [ctypes.c_void_p]
            user32.DestroyCursor.restype = ctypes.c_bool

            installed = 0
            for cursor_id in self._CURSOR_IDS:
                handle = user32.LoadCursorFromFileW(str(cursor_path))
                if not handle:
                    continue
                if user32.SetSystemCursor(handle, cursor_id):
                    installed += 1
                else:
                    user32.DestroyCursor(handle)

            self._installed = installed > 0
            if not self._installed:
                raise OSError("Windows mor sistem imlecini yükleyemedi.")
        except Exception as exc:
            self.restore_system_cursors()
            self.enabled = False
            self.error = f"{type(exc).__name__}: {exc}"
        finally:
            if self._cursor_path is not None:
                try:
                    self._cursor_path.unlink(missing_ok=True)
                except Exception:
                    pass

    def move_to(self, point: tuple[int, int] | None, duration: float) -> None:
        # Hareket _move_pointer içindeki PyAutoGUI ile gerçek Windows faresinde yapılır.
        return

    def pulse(self) -> None:
        # Ayrı resim/overlay kullanılmaz; görünen ok doğrudan sistem imlecidir.
        return

    def close(self) -> None:
        if self._installed or self.enabled:
            self.restore_system_cursors()
        self._installed = False
        self.enabled = False


class NetoEdgePulseOverlay:
    """Görev boyunca ekran kenarlarını mor/siyah titreştirir."""

    def __init__(self, enabled: bool):
        self.enabled = bool(enabled)
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None

        if self.enabled:
            self._thread = threading.Thread(
                target=self._run,
                name="NetoAgentEdgePulse",
                daemon=True,
            )
            self._thread.start()
            self._ready.wait(timeout=1.5)

    @staticmethod
    def _click_through(window) -> None:
        try:
            import ctypes
            hwnd = int(window.winfo_id())
            GWL_EXSTYLE = -20
            WS_EX_TRANSPARENT = 0x00000020
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_LAYERED = 0x00080000
            WS_EX_NOACTIVATE = 0x08000000
            user32 = ctypes.windll.user32
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(
                hwnd,
                GWL_EXSTYLE,
                style
                | WS_EX_TRANSPARENT
                | WS_EX_TOOLWINDOW
                | WS_EX_LAYERED
                | WS_EX_NOACTIVATE,
            )
        except Exception:
            pass

    def _run(self) -> None:
        try:
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            root.overrideredirect(True)
            root.configure(bg="#010101")

            screen_w = int(root.winfo_screenwidth())
            screen_h = int(root.winfo_screenheight())
            thickness = 9

            windows = []
            specs = (
                (screen_w, thickness, 0, 0),
                (screen_w, thickness, 0, screen_h - thickness),
                (thickness, screen_h, 0, 0),
                (thickness, screen_h, screen_w - thickness, 0),
            )

            for width, height, x, y in specs:
                window = tk.Toplevel(root)
                window.withdraw()
                window.overrideredirect(True)
                window.configure(bg="#8B5CF6")
                window.geometry(f"{width}x{height}+{x}+{y}")
                try:
                    window.attributes("-topmost", True)
                except Exception:
                    pass
                window.deiconify()
                window.lift()
                window.update_idletasks()
                self._click_through(window)
                windows.append(window)

            self._root = root
            self._windows = windows
            self._ready.set()
            colors = ("#8B5CF6", "#050505")
            state = {"index": 0}

            def pulse() -> None:
                if self._stop.is_set():
                    for window in windows:
                        try:
                            window.destroy()
                        except Exception:
                            pass
                    try:
                        root.destroy()
                    except Exception:
                        pass
                    return

                color = colors[state["index"] % 2]
                state["index"] += 1

                for window in windows:
                    try:
                        window.configure(bg=color)
                        window.lift()
                    except Exception:
                        pass

                root.after(135, pulse)

            root.after(0, pulse)
            root.mainloop()

        except Exception:
            self._ready.set()

    def stop(self) -> None:
        if not self.enabled:
            return
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=0.8)

CHAT_SEARCH_SHORTCUTS = {
    "discord": "^k",
    "whatsapp": "^f",
    "telegram": "^k",
    "signal": "^f",
    "slack": "^k",
    "teams": "^e",
    "messenger": "^k",
    "viber": "^f",
}
MESSAGE_HINTS = (
    "message",
    "mesaj",
    "write",
    "type a message",
    "compose",
    "new message",
    "yaz",
)
SEARCH_CONTROL_HINTS = (
    "search",
    "ara",
    "find",
    "quick switch",
    "jump",
)


def _load_pyautogui():
    try:
        import pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.04
        return pyautogui
    except Exception as exc:
        raise AgentTaskError(
            "Görünür fare bileşeni yüklenemedi. PyAutoGUI bağımlılığını PyApp ile yeniden derle."
        ) from exc


def _mouse_options(
    request: dict[str, Any],
) -> tuple[bool, bool, bool, float]:
    options = request.get("agent_options") or {}
    visible = True
    pointer_enabled = bool(
        options.get("replace_system_cursor", True)
        or options.get("agent_pointer_enabled", False)
    )
    edge_animation = bool(options.get("edge_animation", True))
    try:
        duration = float(options.get("mouse_duration", 0.26))
    except (TypeError, ValueError):
        duration = 0.26
    return (
        visible,
        pointer_enabled,
        edge_animation,
        max(0.06, min(0.8, duration)),
    )


def _control_center(control: Any) -> tuple[int, int] | None:
    try:
        rect = control.rectangle()
        if rect.width() <= 1 or rect.height() <= 1:
            return None
        return int((rect.left + rect.right) / 2), int((rect.top + rect.bottom) / 2)
    except Exception:
        return None


def _window_center(window: Any) -> tuple[int, int] | None:
    try:
        rect = window.rectangle()
        return int((rect.left + rect.right) / 2), int((rect.top + rect.bottom) / 2)
    except Exception:
        return None


def _move_pointer(
    point: tuple[int, int] | None,
    *,
    visible: bool,
    duration: float,
    pointer: NetoSystemCursor | None = None,
) -> None:
    if point is None:
        return

    if pointer is not None:
        pointer.move_to(point, duration)

    if visible:
        pyautogui = _load_pyautogui()
        pyautogui.moveTo(
            point[0],
            point[1],
            duration=max(0.05, duration * 0.65),
        )


def _visible_click(
    control: Any,
    *,
    visible: bool,
    duration: float,
    pointer: NetoSystemCursor | None = None,
) -> None:
    try:
        if not control.is_visible() or not control.is_enabled():
            raise AgentTaskError("Hedef kontrol görünür veya etkin değil.")
    except AgentTaskError:
        raise
    except Exception:
        pass

    point = _control_center(control)
    if point is None:
        raise AgentTaskError("Hedef kontrol için tıklama konumu alınamadı.")

    _move_pointer(
        point,
        visible=visible,
        duration=duration,
        pointer=pointer,
    )

    # Dinamik Windows yüzeylerinde sonuç satırı fare hareketi sırasında yer değiştirebilir.
    # Tıklamadan hemen önce dikdörtgeni tekrar okuyup stale koordinatı reddet.
    time.sleep(0.025)
    refreshed = _control_center(control)
    if refreshed is None:
        raise AgentTaskError("Hedef kontrol tıklamadan önce kayboldu.")
    if abs(refreshed[0] - point[0]) > 4 or abs(refreshed[1] - point[1]) > 4:
        point = refreshed
        _move_pointer(
            point,
            visible=visible,
            duration=max(0.06, duration * 0.45),
            pointer=pointer,
        )

    try:
        if not control.is_visible() or not control.is_enabled():
            raise AgentTaskError("Hedef kontrol tıklamadan önce geçersizleşti.")
    except AgentTaskError:
        raise
    except Exception:
        pass

    if pointer is not None:
        pointer.pulse()

    try:
        control.click_input()
        return
    except Exception:
        pass

    pyautogui = _load_pyautogui()
    pyautogui.click(point[0], point[1])


def _visible_hotkey(keys: str, *, visible: bool, duration: float) -> None:
    _, send_keys = _load_pywinauto()
    send_keys(keys)
    time.sleep(max(0.15, duration / 2))


def _visible_unicode_text(text: str, *, pause: float = 0.025) -> None:
    _, send_keys = _load_pywinauto()
    send_keys(
        str(text),
        with_spaces=True,
        pause=pause,
        vk_packet=True,
    )


def _replace_focused_text_once(text: str, *, pause: float = 0.035) -> None:
    """Replace the focused field and inject the requested text exactly once.

    UIA set_edit_text() can mutate an Electron field and still raise afterward.
    Falling back to keyboard typing in that state produced values such as
    ``abimabim``. This helper uses one deterministic keyboard path only.
    """
    _, send_keys = _load_pywinauto()
    send_keys("^a")
    time.sleep(0.04)
    send_keys("{BACKSPACE}")
    time.sleep(0.06)
    _visible_unicode_text(str(text), pause=pause)


def _process_name(window: Any) -> str:
    try:
        import psutil
        return str(psutil.Process(int(window.process_id())).name() or "").casefold().strip()
    except Exception:
        return ""


def _chat_family(app_name: str, window: Any) -> str:
    combined = " ".join(
        (
            _normalize(app_name),
            _normalize(_window_text(window)),
            _process_name(window),
        )
    )
    for family in CHAT_SEARCH_SHORTCUTS:
        if family in combined:
            return family
    return "generic"


def _candidate_controls(window: Any, control_types: tuple[str, ...]) -> list[Any]:
    controls: list[Any] = []
    for control_type in control_types:
        try:
            controls.extend(window.descendants(control_type=control_type))
        except Exception:
            pass
    return controls


def _best_edit_control(
    window: Any,
    *,
    hints: tuple[str, ...],
    exclude_hints: tuple[str, ...] = (),
    prefer_bottom: bool = False,
    control_types: tuple[str, ...] = ("Edit",),
    minimum_score: float = 1.0,
) -> Any | None:
    """Return a verified input, never merely the least-wrong Edit control.

    The old implementation always returned one control even when every candidate
    had a negative score. In WhatsApp's search screen that made the contact-search
    box become the "message" box and the outgoing text was typed into search.
    """
    scored: list[tuple[float, Any]] = []
    controls: list[Any] = []
    seen: set[tuple[int, int, int, int] | int] = set()

    for control_type in control_types:
        try:
            controls.extend(window.descendants(control_type=control_type))
        except Exception:
            pass

    try:
        window_rect = window.rectangle()
        window_top = float(window_rect.top)
        window_bottom = float(window_rect.bottom)
        window_height = max(1.0, window_bottom - window_top)
    except Exception:
        window_top = 0.0
        window_bottom = 0.0
        window_height = 1.0

    for control in controls:
        try:
            if not control.is_visible() or not control.is_enabled():
                continue
        except Exception:
            pass

        key = _control_rect_key(control) or id(control)
        if key in seen:
            continue
        seen.add(key)

        name = _normalize(_control_name(control))
        matched_hint = any(hint in name for hint in hints)
        matched_exclusion = any(hint in name for hint in exclude_hints)
        score = 0.0

        if matched_hint:
            score += 95.0
        if matched_exclusion:
            score -= 180.0

        try:
            control_type = _control_type_name(control)
        except Exception:
            control_type = ""

        # A generic Document often represents the whole chat history. Accept it
        # only when its accessible label explicitly identifies a composer.
        if control_type == "Document" and not matched_hint:
            continue

        if prefer_bottom:
            try:
                rect = control.rectangle()
                center_y = (float(rect.top) + float(rect.bottom)) / 2.0
                vertical_ratio = (center_y - window_top) / window_height
                if vertical_ratio >= 0.68:
                    score += 115.0
                elif vertical_ratio >= 0.55:
                    score += 35.0
                else:
                    score -= 110.0
                score += max(0.0, 55.0 - abs(window_bottom - float(rect.bottom)) / 7.0)
            except Exception:
                pass

        if not name and control_type == "Edit":
            score += 8.0

        if score >= minimum_score:
            scored.append((score, control))

    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


OPEN_BUTTON_HINTS = (
    "open",
    "aç",
    "ac",
    "launch",
)
TASKBAR_SEARCH_HINTS = (
    "search",
    "ara",
    "windows search",
)


def _desktop_controls(control_types: tuple[str, ...]) -> list[Any]:
    Desktop, _ = _load_pywinauto()
    controls: list[Any] = []

    try:
        desktop = Desktop(backend="uia")
        windows = desktop.windows()
    except Exception:
        windows = []

    for window in windows:
        for control_type in control_types:
            try:
                controls.extend(
                    window.descendants(control_type=control_type)
                )
            except Exception:
                pass

    return controls


def _find_control_by_hints(
    controls: list[Any],
    hints: tuple[str, ...],
) -> Any | None:
    best: tuple[float, Any] | None = None

    for control in controls:
        try:
            if not control.is_visible() or not control.is_enabled():
                continue
        except Exception:
            pass

        label = _normalize(_control_name(control))
        score = 0.0

        for hint in hints:
            normalized_hint = _normalize(hint)
            if label == normalized_hint:
                score += 120.0
            elif normalized_hint in label:
                score += 70.0

        if score and (best is None or score > best[0]):
            best = (score, control)

    return best[1] if best else None


def _find_taskbar_search_control() -> Any | None:
    Desktop, _ = _load_pywinauto()

    for backend in ("uia", "win32"):
        try:
            taskbar = Desktop(backend=backend).window(
                class_name="Shell_TrayWnd"
            )
            if not taskbar.exists(timeout=0.15):
                continue

            controls = []
            for control_type in ("Button", "Edit"):
                try:
                    controls.extend(
                        taskbar.descendants(
                            control_type=control_type
                        )
                    )
                except Exception:
                    pass

            result = _find_control_by_hints(
                controls,
                TASKBAR_SEARCH_HINTS,
            )
            if result is not None:
                return result
        except Exception:
            continue

    return None


def _find_search_surface() -> Any | None:
    Desktop, _ = _load_pywinauto()
    scored: list[tuple[float, Any]] = []

    try:
        windows = Desktop(backend="uia").windows()
    except Exception:
        windows = []

    for window in windows:
        try:
            if not window.is_visible():
                continue
        except Exception:
            pass

        process_name = _process_name(window)
        title = _normalize(_window_text(window))
        score = 0.0

        if process_name in {
            "searchhost.exe",
            "searchapp.exe",
            "startmenuexperiencehost.exe",
        }:
            score += 160.0

        if any(
            token in title
            for token in ("search", "ara", "başlat", "baslat")
        ):
            score += 70.0

        if score:
            scored.append((score, window))

    if not scored:
        return None

    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def _surface_controls(
    surface: Any,
    control_types: tuple[str, ...],
) -> list[Any]:
    controls: list[Any] = []

    if surface is None:
        return controls

    for control_type in control_types:
        try:
            controls.extend(
                surface.descendants(
                    control_type=control_type
                )
            )
        except Exception:
            pass

    return controls

APP_KIND_HINTS = (
    "uygulama",
    "application",
    "desktop app",
    "store app",
)
WEB_RESULT_HINTS = (
    "web de arayin",
    "webde arayin",
    "search the web",
    "diger arama sonuclarina bakin",
    "other search results",
)
BEST_MATCH_HINTS = (
    "en iyi eslesme",
    "best match",
)


def _control_type_name(control: Any) -> str:
    try:
        return str(control.element_info.control_type or "").strip()
    except Exception:
        return ""


def _control_text_parts(control: Any) -> list[str]:
    values: list[str] = []
    for getter in (
        lambda: control.window_text(),
        lambda: control.element_info.name,
        lambda: control.element_info.automation_id,
        lambda: control.element_info.class_name,
    ):
        try:
            value = str(getter() or "").strip()
            if value and value not in values:
                values.append(value)
        except Exception:
            pass
    return values


def _control_context(control: Any, *, levels: int = 4) -> str:
    """Local UIA context without importing unrelated search-result rows."""
    values: list[str] = []
    current = control
    visited: set[int] = set()

    # Initial node and its own children.
    values.extend(_control_text_parts(current))
    try:
        children = list(current.children())[:16]
    except Exception:
        children = []
    for child in children:
        values.extend(_control_text_parts(child))

    row_children_added = _control_type_name(current) in {
        "ListItem", "TreeItem", "Button", "Hyperlink"
    }

    # Ancestor names identify sections. At the nearest clickable row, include
    # that row's direct children so sibling labels such as "Application" or
    # "Other search results" are considered. Never include children of higher
    # ancestors because those are unrelated result rows.
    for _ in range(max(1, levels)):
        marker = id(current)
        if marker in visited:
            break
        visited.add(marker)
        try:
            current = current.parent()
        except Exception:
            break
        if current is None:
            break
        values.extend(_control_text_parts(current))

        if not row_children_added and _control_type_name(current) in {
            "ListItem", "TreeItem", "Button", "Hyperlink"
        }:
            try:
                row_children = list(current.children())[:16]
            except Exception:
                row_children = []
            for child in row_children:
                values.extend(_control_text_parts(child))
            row_children_added = True

    return " ".join(dict.fromkeys(value for value in values if value))


def _nearest_clickable_control(control: Any, *, levels: int = 5) -> Any | None:
    current = control
    for _ in range(max(1, levels)):
        control_type = _control_type_name(current)
        if control_type in {"ListItem", "TreeItem", "Button", "Hyperlink"}:
            return current
        try:
            current = current.parent()
        except Exception:
            return None
        if current is None:
            return None
    return None


def _control_rect_key(control: Any) -> tuple[int, int, int, int] | None:
    try:
        rect = control.rectangle()
        return int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)
    except Exception:
        return None


def _find_app_result_control(
    app_name: str,
    surface: Any,
) -> Any | None:
    """Return only a verified application result; never a web suggestion."""
    query = _normalize(app_name)
    if not query or surface is None:
        return None

    query_tokens = set(query.split())
    scored: list[tuple[float, Any]] = []
    seen: set[tuple[int, int, int, int] | int] = set()

    try:
        surface_rect = surface.rectangle()
        surface_width = max(1, surface_rect.right - surface_rect.left)
        surface_height = max(1, surface_rect.bottom - surface_rect.top)
    except Exception:
        surface_rect = None
        surface_width = 1
        surface_height = 1

    for raw_control in _surface_controls(
        surface,
        ("ListItem", "TreeItem", "Button", "Text"),
    ):
        direct_parts = [_normalize(part) for part in _control_text_parts(raw_control)]
        direct_parts = [part for part in direct_parts if part]
        context = _normalize(_control_context(raw_control))
        context_tokens = set(context.split())
        direct_exact = query in direct_parts
        app_marker = any(hint in context for hint in APP_KIND_HINTS)
        web_marker = any(hint in context for hint in WEB_RESULT_HINTS)

        # The recording showed this exact failure: "not defteri film/indir" was
        # accepted because the old fuzzy score treated query prefixes as apps.
        if web_marker:
            continue
        if not direct_exact and not app_marker:
            continue
        if query_tokens and not query_tokens.issubset(context_tokens):
            continue

        control = _nearest_clickable_control(raw_control)
        if control is None:
            continue

        key = _control_rect_key(control) or id(control)
        if key in seen:
            continue
        seen.add(key)

        control_context = _normalize(_control_context(control))
        if any(hint in control_context for hint in WEB_RESULT_HINTS):
            continue

        score = 0.0
        if direct_exact:
            score += 1200.0
        if app_marker or any(hint in control_context for hint in APP_KIND_HINTS):
            score += 500.0
        if any(hint in control_context for hint in BEST_MATCH_HINTS):
            score += 140.0

        control_type = _control_type_name(control)
        if control_type in {"ListItem", "TreeItem"}:
            score += 100.0
        elif control_type == "Button":
            score += 70.0

        score += min(260.0, _score_name(app_name, " ".join(direct_parts)))

        if surface_rect is not None:
            try:
                rect = control.rectangle()
                center_x = (rect.left + rect.right) / 2
                center_y = (rect.top + rect.bottom) / 2
                if center_x <= surface_rect.left + surface_width * 0.67:
                    score += 45.0
                if center_y <= surface_rect.top + surface_height * 0.58:
                    score += 40.0
            except Exception:
                pass

        scored.append((score, control))

    if not scored:
        return None

    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def _find_open_button(surface: Any, app_name: str) -> Any | None:
    # Do not click an arbitrary "Open" button unless the same surface contains
    # a verified application result for the requested name.
    if _find_app_result_control(app_name, surface) is None:
        return None

    exact_labels = {"open", "ac"}
    candidates: list[tuple[float, Any]] = []
    for control in _surface_controls(surface, ("Button",)):
        label = _normalize(_control_name(control))
        if not label:
            continue
        if any(blocked in label for blocked in ("file location", "dosya konumu")):
            continue
        if label not in exact_labels and not label.startswith("open ") and not label.startswith("ac "):
            continue

        context = _normalize(_control_context(control))
        score = 200.0 if label in exact_labels else 120.0
        if _normalize(app_name) in context:
            score += 180.0
        if any(hint in context for hint in APP_KIND_HINTS):
            score += 80.0
        candidates.append((score, control))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _start_menu_search_launch(
    app_name: str,
    status,
    *,
    visible: bool,
    duration: float,
    pointer: NetoSystemCursor | None,
) -> bool:
    status(
        "windows_search",
        "Gerçek mor Windows faresi arama alanına gidiyor.",
        2,
        8,
    )

    pyautogui = _load_pyautogui()
    screen_w, screen_h = pyautogui.size()
    search_control = _find_taskbar_search_control()

    if search_control is not None:
        _visible_click(
            search_control,
            visible=visible,
            duration=duration,
            pointer=pointer,
        )
    else:
        fallback = (
            max(92, min(410, int(screen_w * 0.18))),
            max(1, int(screen_h - 23)),
        )
        _move_pointer(
            fallback,
            visible=visible,
            duration=duration,
            pointer=pointer,
        )
        if pointer is not None:
            pointer.pulse()
        _, send_keys = _load_pywinauto()
        send_keys("#s")

    time.sleep(0.22)
    surface = _find_search_surface()
    deadline = time.monotonic() + 1.5

    while surface is None and time.monotonic() < deadline:
        time.sleep(0.08)
        surface = _find_search_surface()

    _, send_keys = _load_pywinauto()
    search_edit = _find_control_by_hints(
        _surface_controls(surface, ("Edit",)),
        SEARCH_CONTROL_HINTS,
    )

    if search_edit is not None:
        _visible_click(
            search_edit,
            visible=visible,
            duration=duration,
            pointer=pointer,
        )
        try:
            search_edit.set_edit_text("")
            search_edit.set_edit_text(app_name)
        except Exception:
            send_keys("^a{BACKSPACE}")
            _visible_unicode_text(app_name, pause=0.012)
    else:
        send_keys("^a{BACKSPACE}")
        _visible_unicode_text(app_name, pause=0.012)

    status(
        "windows_search_typed",
        "Uygulama adı arama alanına yazıldı.",
        3,
        8,
    )
    time.sleep(0.85)

    surface = _find_search_surface() or surface
    result_control = _find_app_result_control(app_name, surface)

    if result_control is None:
        status(
            "windows_result_rejected",
            "Uygulama olarak doğrulanmayan web veya dosya sonucu tıklanmadı.",
            4,
            8,
        )
        send_keys("{ESC}")
        return False

    # Windows 11 automatically selects Best Match and shows its Open button.
    # Clicking that verified button is safer than clicking a fuzzy text child.
    open_button = _find_open_button(surface, app_name)
    if open_button is not None:
        status(
            "windows_open_button",
            "Doğrulanmış uygulamanın Aç düğmesine basılıyor.",
            4,
            8,
        )
        _visible_click(
            open_button,
            visible=visible,
            duration=duration,
            pointer=pointer,
        )
        return True

    status(
        "windows_app_result",
        "Yalnızca Uygulama olarak doğrulanan sonuç tıklanıyor.",
        4,
        8,
    )
    _visible_click(
        result_control,
        visible=visible,
        duration=duration,
        pointer=pointer,
    )
    time.sleep(0.45)

    current_surface = _find_search_surface()
    if current_surface is None:
        return True

    # Some Windows builds select the result on first click and require Open.
    open_button = _find_open_button(current_surface, app_name)
    if open_button is not None:
        _visible_click(
            open_button,
            visible=visible,
            duration=max(0.06, duration * 0.7),
            pointer=pointer,
        )
        return True

    # Never press Enter on an unverified remaining search surface: it can open Bing.
    send_keys("{ESC}")
    return False


def _find_message_edit(window: Any) -> Any | None:
    return _best_edit_control(
        window,
        hints=MESSAGE_HINTS,
        exclude_hints=SEARCH_CONTROL_HINTS,
        prefer_bottom=True,
        control_types=("Edit", "Document"),
        minimum_score=20.0,
    )


def _refresh_window(window: Any) -> Any:
    """Reacquire an Electron/UWP window after its UI tree changes."""
    handle = _window_handle(window)
    if not handle:
        return window

    Desktop, _ = _load_pywinauto()
    for backend in ("uia", "win32"):
        try:
            refreshed = Desktop(backend=backend).window(handle=handle)
            if refreshed.exists(timeout=0.15):
                return refreshed
        except Exception:
            continue
    return window


def _wait_for_message_edit(
    window: Any,
    *,
    timeout: float = 3.0,
) -> tuple[Any, Any] | None:
    """Wait until a real composer exists after a chat row was activated."""
    deadline = time.monotonic() + max(0.15, timeout)
    current = window
    while time.monotonic() < deadline:
        current = _refresh_window(current)
        edit = _find_message_edit(current)
        if edit is not None:
            return current, edit
        time.sleep(0.12)
    return None


def _control_has_keyboard_focus(control: Any) -> bool | None:
    try:
        return bool(control.has_keyboard_focus())
    except Exception:
        return None


def _focused_search_control(window: Any) -> Any | None:
    try:
        controls = window.descendants(control_type="Edit")
    except Exception:
        controls = []
    for control in controls:
        name = _normalize(_control_name(control))
        if not any(hint in name for hint in SEARCH_CONTROL_HINTS):
            continue
        if _control_has_keyboard_focus(control) is True:
            return control
    return None


SEARCH_HINTS = (
    "search",
    "find",
    "jump",
    "quick",
    "ara",
    "bul",
    "git",
)


class AgentTaskError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize(value: str) -> str:
    # Unicode decomposition does not map Turkish dotless ı to ASCII i.
    # Translate it first so UI labels such as "Diğer arama sonuçlarına bakın"
    # can be compared reliably with locale-independent safety hints.
    value = str(value or "").translate(str.maketrans({"ı": "i", "İ": "I"}))
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.casefold().strip()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _score_name(query: str, candidate: str) -> float:
    q = _normalize(query)
    c = _normalize(candidate)
    if not q or not c:
        return 0.0
    if q == c:
        return 1000.0
    score = difflib.SequenceMatcher(None, q, c).ratio() * 100.0
    if c.startswith(q) or q.startswith(c):
        score += 80.0
    q_tokens = set(q.split())
    c_tokens = set(c.split())
    if q_tokens:
        score += 100.0 * len(q_tokens & c_tokens) / len(q_tokens)
    return score


def _start_menu_roots() -> list[Path]:
    roots: list[Path] = []
    appdata = os.environ.get("APPDATA")
    programdata = os.environ.get("PROGRAMDATA")
    if appdata:
        roots.append(Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    if programdata:
        roots.append(Path(programdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    return [root for root in roots if root.exists()]


def _resolve_start_menu_entry(app_name: str) -> Path | None:
    candidates: list[tuple[float, Path]] = []
    for root in _start_menu_roots():
        try:
            for path in root.rglob("*.lnk"):
                score = _score_name(app_name, path.stem)
                if score >= 70:
                    candidates.append((score, path))
        except OSError:
            continue
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _load_pywinauto():
    try:
        from pywinauto import Desktop
        from pywinauto.keyboard import send_keys
        return Desktop, send_keys
    except Exception as exc:
        raise AgentTaskError(
            "Windows UI Automation yüklenemedi: "
            f"{type(exc).__name__}: {exc}"
        ) from exc


def _visible_windows(backend: str = "uia") -> list[Any]:
    Desktop, _ = _load_pywinauto()
    try:
        return [window for window in Desktop(backend=backend).windows() if window.is_visible()]
    except Exception:
        return []


def _window_text(window: Any) -> str:
    try:
        return str(window.window_text() or "")
    except Exception:
        return ""


def _window_handle(window: Any) -> int:
    try:
        return int(window.handle)
    except Exception:
        return 0


def _window_snapshot() -> set[int]:
    handles: set[int] = set()
    for backend in ("uia", "win32"):
        for window in _visible_windows(backend):
            handle = _window_handle(window)
            if handle:
                handles.add(handle)
    return handles


def _find_best_window(
    app_name: str,
    *,
    baseline_handles: set[int] | None = None,
) -> Any | None:
    scored: list[tuple[float, Any]] = []
    baseline_handles = baseline_handles or set()
    ignored_processes = {
        "searchhost.exe",
        "searchapp.exe",
        "startmenuexperiencehost.exe",
        "shellexperiencehost.exe",
    }

    for backend in ("uia", "win32"):
        for window in _visible_windows(backend):
            process_name = _process_name(window)
            if process_name in ignored_processes:
                continue

            title = _window_text(window)
            title_score = _score_name(app_name, title)
            process_stem = Path(process_name).stem if process_name else ""
            process_score = _score_name(app_name, process_stem)
            if process_stem in {
                "chrome", "msedge", "firefox", "brave", "opera", "vivaldi"
            } and process_score < 60.0:
                title_score = 0.0
            process_component = process_score + 45.0 if process_score >= 60.0 else 0.0
            score = max(title_score, process_component)

            handle = _window_handle(window)
            if handle and handle not in baseline_handles and score >= 45.0:
                score += 85.0

            try:
                if int(window.process_id()) == os.getpid():
                    continue
            except Exception:
                pass

            if score >= 45.0:
                scored.append((score, window))

        if scored:
            break

    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def _focus_window(
    window: Any,
    *,
    visible: bool = False,
    duration: float = 0.45,
    pointer: NetoSystemCursor | None = None,
) -> None:
    try:
        window.restore()
    except Exception:
        pass

    try:
        window.set_focus()
        return
    except Exception:
        pass

    try:
        point = _window_center(window)
        _move_pointer(
            point,
            visible=visible,
            duration=duration,
            pointer=pointer,
        )
        if pointer is not None:
            pointer.pulse()
        window.click_input()
    except Exception as exc:
        raise AgentTaskError(
            "Uygulama penceresi öne getirilemedi."
        ) from exc


def _resolve_app_path(app_name: str) -> Path | None:
    """Start Menu dışında App Paths ve PATH üzerinden de uygulama bulur."""
    import shutil

    direct = shutil.which(app_name) or shutil.which(f"{app_name}.exe")
    if direct:
        return Path(direct)

    if os.name != "nt":
        return None

    try:
        import winreg
        roots = (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE)
        base = r"Software\Microsoft\Windows\CurrentVersion\App Paths"
        candidates: list[tuple[float, Path]] = []
        for hive in roots:
            try:
                with winreg.OpenKey(hive, base) as key:
                    count = winreg.QueryInfoKey(key)[0]
                    for index in range(count):
                        sub_name = winreg.EnumKey(key, index)
                        score = _score_name(app_name, Path(sub_name).stem)
                        if score < 70:
                            continue
                        try:
                            with winreg.OpenKey(key, sub_name) as sub_key:
                                value, _ = winreg.QueryValueEx(sub_key, "")
                            path = Path(str(value).strip('"'))
                            if path.is_file():
                                candidates.append((score, path))
                        except OSError:
                            continue
            except OSError:
                continue
        if candidates:
            candidates.sort(key=lambda item: item[0], reverse=True)
            return candidates[0][1]
    except Exception:
        pass
    return None


def _resolve_start_app_id(app_name: str) -> str | None:
    """Microsoft Store/UWP uygulamalarını Get-StartApps üzerinden dinamik bulur."""
    if os.name != "nt":
        return None

    import json
    import shutil

    powershell = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
    if not powershell:
        return None

    command = (
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
        "Get-StartApps | Select-Object Name,AppID | "
        "ConvertTo-Json -Compress"
    )
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(
            [powershell, "-NoProfile", "-NonInteractive", "-Command", command],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5.0,
            creationflags=flags,
            check=False,
        )
        if completed.returncode != 0 or not completed.stdout.strip():
            return None
        payload = json.loads(completed.stdout)
        records = payload if isinstance(payload, list) else [payload]
        scored: list[tuple[float, str]] = []
        for record in records:
            if not isinstance(record, dict):
                continue
            name = str(record.get("Name") or "")
            app_id = str(record.get("AppID") or "").strip()
            score = _score_name(app_name, name)
            if app_id and score >= 70.0:
                scored.append((score, app_id))
        if not scored:
            return None
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1]
    except Exception:
        return None


def _direct_launch_fallback(app_name: str) -> bool:
    entry = _resolve_start_menu_entry(app_name)
    if entry is not None:
        os.startfile(str(entry))
        return True

    executable = _resolve_app_path(app_name)
    if executable is not None:
        os.startfile(str(executable))
        return True

    app_id = _resolve_start_app_id(app_name)
    if app_id:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(
            ["explorer.exe", f"shell:AppsFolder\\{app_id}"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            close_fds=True,
        )
        return True
    return False


def _launch_app(
    app_name: str,
    status,
    *,
    visible: bool,
    duration: float,
    pointer: NetoSystemCursor | None,
) -> Any:
    existing = _find_best_window(app_name)

    if existing is not None:
        status(
            "application_found",
            "Uygulama zaten açık; gerçek fare pencereyi öne getiriyor.",
            2,
            8,
        )
        _focus_window(
            existing,
            visible=visible,
            duration=duration,
            pointer=pointer,
        )
        return existing

    baseline = _window_snapshot()
    visual_launch_started = _start_menu_search_launch(
        app_name,
        status,
        visible=visible,
        duration=duration,
        pointer=pointer,
    )

    deadline = time.monotonic() + 20.0
    fallback_at = time.monotonic() + (2.8 if visual_launch_started else 0.0)
    fallback_started = False

    while time.monotonic() < deadline:
        window = _find_best_window(
            app_name,
            baseline_handles=baseline,
        )

        if window is not None:
            _focus_window(
                window,
                visible=visible,
                duration=duration,
                pointer=pointer,
            )
            return window

        if not fallback_started and time.monotonic() >= fallback_at:
            status(
                "application_launch_fallback",
                "Windows araması doğrulanamadı; güvenilir yerel başlatıcı deneniyor.",
                4,
                8,
            )
            fallback_started = _direct_launch_fallback(app_name)
            # Aynı fallback'i her döngüde tekrar çalıştırma.
            if not fallback_started:
                fallback_started = True

        time.sleep(0.14)

    raise AgentTaskError(
        f"'{app_name}' başlatılamadı veya uygulamanın erişilebilir penceresi bulunamadı."
    )


def _control_name(control: Any) -> str:
    values = []
    for getter in (
        lambda: control.window_text(),
        lambda: control.element_info.name,
        lambda: control.element_info.automation_id,
    ):
        try:
            value = str(getter() or "").strip()
            if value:
                values.append(value)
        except Exception:
            pass
    return " ".join(values)


def _select_safe_named_control(query: str, candidates: list[Any]) -> Any | None:
    """Prefer an exact visible label and reject ambiguous fuzzy chat/file results."""
    normalized_query = _normalize(query)
    query_tokens = set(normalized_query.split())
    if not normalized_query:
        return None

    scored: list[tuple[float, bool, Any]] = []
    seen: set[tuple[int, int, int, int] | int] = set()

    for raw_control in candidates:
        parts = [_normalize(part) for part in _control_text_parts(raw_control)]
        parts = [part for part in parts if part]
        context = _normalize(_control_context(raw_control, levels=3))
        context_tokens = set(context.split())
        exact = normalized_query in parts

        if not exact and (not query_tokens or not query_tokens.issubset(context_tokens)):
            continue

        control = _nearest_clickable_control(raw_control)
        if control is None:
            continue
        key = _control_rect_key(control) or id(control)
        if key in seen:
            continue
        seen.add(key)

        control_type = _control_type_name(control)
        score = 1100.0 if exact else _score_name(query, context)
        if control_type in {"ListItem", "TreeItem"}:
            score += 120.0
        elif control_type == "Button":
            score += 70.0

        if not exact and score < 185.0:
            continue
        scored.append((score, exact, control))

    if not scored:
        return None

    scored.sort(key=lambda item: item[0], reverse=True)
    if len(scored) > 1:
        top_score, top_exact, top_control = scored[0]
        second_score, second_exact, second_control = scored[1]
        if (
            not top_exact
            and not second_exact
            and top_control is not second_control
            and top_score - second_score < 28.0
        ):
            return None

    return scored[0][2]


def _has_ancestor_control_type(control: Any, wanted: str, *, levels: int = 6) -> bool:
    current = control
    for _ in range(max(1, levels)):
        if _control_type_name(current) == wanted:
            return True
        try:
            current = current.parent()
        except Exception:
            return False
        if current is None:
            return False
    return False


def _select_safe_chat_result(
    query: str,
    candidates: list[Any],
    *,
    search_edit: Any | None,
) -> Any | None:
    """Select an exact conversation result below the active search field.

    WhatsApp Desktop sometimes exposes the visible contact title only as a Text
    node, without a ListItem parent. Such a title is still physically clickable.
    Search-field descendants and labels outside the left search pane are rejected.
    """
    normalized_query = _normalize(query)
    if not normalized_query:
        return None

    try:
        search_rect = search_edit.rectangle() if search_edit is not None else None
    except Exception:
        search_rect = None

    scored: list[tuple[float, Any]] = []
    seen: set[tuple[int, int, int, int] | int] = set()

    for raw_control in candidates:
        parts = [_normalize(part) for part in _control_text_parts(raw_control)]
        parts = [part for part in parts if part]
        if normalized_query not in parts:
            continue
        if _has_ancestor_control_type(raw_control, "Edit"):
            continue

        try:
            raw_rect = raw_control.rectangle()
            if raw_rect.width() < 4 or raw_rect.height() < 4:
                continue
            center_x = (raw_rect.left + raw_rect.right) / 2.0
            center_y = (raw_rect.top + raw_rect.bottom) / 2.0
            if search_rect is not None:
                if center_y <= search_rect.bottom + 3:
                    continue
                if center_x < search_rect.left - 50 or center_x > search_rect.right + 50:
                    continue
        except Exception:
            continue

        clickable = _nearest_clickable_control(raw_control) or raw_control
        key = _control_rect_key(clickable) or id(clickable)
        if key in seen:
            continue
        seen.add(key)

        control_type = _control_type_name(clickable)
        score = 1200.0
        if control_type in {"ListItem", "TreeItem"}:
            score += 180.0
        elif control_type == "Button":
            score += 120.0
        elif _control_type_name(raw_control) == "Text":
            score += 80.0

        context = _normalize(_control_context(raw_control, levels=3))
        if any(token in context for token in ("sohbetler", "chats", "conversations")):
            score += 90.0
        scored.append((score, clickable))

    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def _generic_open_target(
    window: Any,
    target: str,
    status,
    *,
    visible: bool,
    duration: float,
    pointer: NetoSystemCursor | None,
) -> bool:
    _, send_keys = _load_pywinauto()
    status(
        "target_search",
        "Hedef alan erişilebilirlik ağacında aranıyor.",
        5,
        8,
    )

    edits: list[tuple[float, Any]] = []

    try:
        controls = window.descendants(control_type="Edit")
    except Exception:
        controls = []

    for control in controls:
        try:
            if not control.is_visible() or not control.is_enabled():
                continue
        except Exception:
            pass

        name = _normalize(_control_name(control))
        score = sum(
            35.0 for hint in SEARCH_HINTS if hint in name
        )
        if not name:
            score += 5.0
        edits.append((score, control))

    edits.sort(key=lambda item: item[0], reverse=True)

    for _, edit in edits[:6]:
        try:
            _visible_click(
                edit,
                visible=visible,
                duration=duration,
                pointer=pointer,
            )
            try:
                edit.set_focus()
            except Exception:
                pass
            _replace_focused_text_once(target)

            time.sleep(1.0)

            candidates = _candidate_controls(
                window,
                ("ListItem", "TreeItem", "Button", "Text"),
            )
            selected = _select_safe_named_control(target, candidates)

            if selected is not None:
                _visible_click(
                    selected,
                    visible=visible,
                    duration=duration,
                    pointer=pointer,
                )
                return True

        except Exception:
            continue

    return False


def _find_exact_named_descendant(control: Any, target: str) -> Any | None:
    normalized_target = _normalize(target)
    if not normalized_target:
        return None

    candidates = [control]
    for control_type in ("Text", "Button", "ListItem", "TreeItem"):
        try:
            candidates.extend(control.descendants(control_type=control_type))
        except Exception:
            pass

    scored: list[tuple[float, Any]] = []
    seen: set[tuple[int, int, int, int] | int] = set()
    for candidate in candidates:
        parts = [_normalize(part) for part in _control_text_parts(candidate)]
        if normalized_target not in parts:
            continue
        key = _control_rect_key(candidate) or id(candidate)
        if key in seen:
            continue
        seen.add(key)
        score = 0.0
        control_type = _control_type_name(candidate)
        if control_type == "Text":
            score += 120.0
        elif control_type in {"ListItem", "TreeItem", "Button"}:
            score += 80.0
        try:
            rect = candidate.rectangle()
            if rect.width() >= 8 and rect.height() >= 8:
                score += 30.0
        except Exception:
            continue
        scored.append((score, candidate))

    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def _rects_overlap(a: Any, b: Any) -> bool:
    try:
        return not (
            a.right <= b.left
            or b.right <= a.left
            or a.bottom <= b.top
            or b.bottom <= a.top
        )
    except Exception:
        return False


def _conversation_target_header_visible(
    window: Any,
    target: str,
    *,
    excluded_rect: Any | None = None,
) -> bool:
    """Verify the selected contact outside the search-result row.

    On a wide layout the result remains in the left sidebar, so merely finding
    the same name is insufficient. A matching label must be in the conversation
    header area and outside the clicked result rectangle.
    """
    normalized_target = _normalize(target)
    if not normalized_target:
        return False
    try:
        window_rect = window.rectangle()
        header_limit = window_rect.top + max(90, (window_rect.bottom - window_rect.top) * 0.30)
    except Exception:
        window_rect = None
        header_limit = float("inf")

    candidates = _candidate_controls(window, ("Text", "Button", "TitleBar"))
    for control in candidates:
        parts = [_normalize(part) for part in _control_text_parts(control)]
        if normalized_target not in parts:
            continue
        try:
            rect = control.rectangle()
            if rect.width() < 4 or rect.height() < 4:
                continue
            if excluded_rect is not None and _rects_overlap(rect, excluded_rect):
                continue
            center_y = (rect.top + rect.bottom) / 2.0
            if center_y <= header_limit:
                return True
        except Exception:
            continue
    return False


def _conversation_identity_verified(window: Any, selected: Any, target: str) -> bool:
    try:
        selected_rect = selected.rectangle()
    except Exception:
        selected_rect = None

    # UIA selection state is the strongest signal when the app exposes it.
    try:
        if bool(selected.is_selected()):
            return True
    except Exception:
        pass

    # In narrow/mobile layouts the search-result row disappears after opening.
    try:
        if not selected.exists(timeout=0.05) or not selected.is_visible():
            return True
    except Exception:
        pass

    return _conversation_target_header_visible(
        window,
        target,
        excluded_rect=selected_rect,
    )


def _wait_for_conversation_ready(
    window: Any,
    target: str,
    *,
    selected: Any | None,
    timeout: float,
) -> tuple[Any, Any] | None:
    deadline = time.monotonic() + max(0.2, timeout)
    current = window
    while time.monotonic() < deadline:
        current = _refresh_window(current)
        edit = _find_message_edit(current)
        identity_ok = (
            _conversation_identity_verified(current, selected, target)
            if selected is not None
            else _conversation_target_header_visible(current, target)
        )
        if edit is not None and identity_ok:
            return current, edit
        time.sleep(0.12)
    return None


def _physical_click_point(
    point: tuple[int, int],
    *,
    visible: bool,
    duration: float,
    pointer: NetoSystemCursor | None,
) -> None:
    _move_pointer(
        point,
        visible=visible,
        duration=duration,
        pointer=pointer,
    )
    if pointer is not None:
        pointer.pulse()
    pyautogui = _load_pyautogui()
    pyautogui.click(point[0], point[1])


def _activate_verified_chat_result(
    window: Any,
    selected: Any,
    target: str,
    *,
    visible: bool,
    duration: float,
    pointer: NetoSystemCursor | None,
) -> tuple[Any, Any] | None:
    """Click the verified chat label/row and require the message composer.

    No success is reported merely because click_input() returned. WhatsApp and
    other Electron apps can accept that API call without actually navigating.
    """
    exact_label = _find_exact_named_descendant(selected, target)
    click_targets: list[Any] = []
    if exact_label is not None:
        click_targets.append(exact_label)
    if selected not in click_targets:
        click_targets.append(selected)

    for click_target in click_targets:
        try:
            _visible_click(
                click_target,
                visible=visible,
                duration=duration,
                pointer=pointer,
            )
        except Exception:
            continue
        ready = _wait_for_conversation_ready(
            window,
            target,
            selected=selected,
            timeout=1.35,
        )
        if ready is not None:
            return ready

    # Last mouse-only fallback: click the title-bearing half of the verified row.
    # This avoids dates, menus and preview controls on the far-right side.
    try:
        rect = selected.rectangle()
        width = max(1, rect.right - rect.left)
        height = max(1, rect.bottom - rect.top)
        point = (
            int(rect.left + min(width * 0.46, max(24.0, width - 24.0))),
            int(rect.top + height * 0.5),
        )
        _physical_click_point(
            point,
            visible=visible,
            duration=max(0.08, duration * 0.8),
            pointer=pointer,
        )
    except Exception:
        return None

    return _wait_for_conversation_ready(
        window,
        target,
        selected=selected,
        timeout=1.8,
    )


def _click_chat_search_and_result(
    window: Any,
    target: str,
    status,
    *,
    visible: bool,
    duration: float,
    pointer: NetoSystemCursor | None,
) -> tuple[bool, bool]:
    """Return ``(opened, query_entered)``.

    Once a real search field accepted the target, callers must not invoke another
    strategy that types the same target again. This is the state lock that blocks
    ``abimabim`` and similar duplicate queries.
    """
    status(
        "chat_search_click",
        "Gerçek mor Windows faresi sohbet arama alanına gidiyor.",
        5,
        8,
    )

    search_edit = _best_edit_control(
        window,
        hints=SEARCH_CONTROL_HINTS,
        exclude_hints=MESSAGE_HINTS,
        prefer_bottom=False,
        minimum_score=1.0,
    )

    if search_edit is None:
        search_button = _find_control_by_hints(
            _candidate_controls(window, ("Button", "Text")),
            SEARCH_CONTROL_HINTS,
        )
        if search_button is not None:
            try:
                _visible_click(
                    search_button,
                    visible=visible,
                    duration=duration,
                    pointer=pointer,
                )
                time.sleep(0.35)
                window = _refresh_window(window)
                search_edit = _best_edit_control(
                    window,
                    hints=SEARCH_CONTROL_HINTS,
                    exclude_hints=MESSAGE_HINTS,
                    prefer_bottom=False,
                    minimum_score=1.0,
                )
            except Exception:
                search_edit = None

    if search_edit is None:
        return False, False

    try:
        _visible_click(
            search_edit,
            visible=visible,
            duration=duration,
            pointer=pointer,
        )
        try:
            search_edit.set_focus()
        except Exception:
            pass
        _replace_focused_text_once(target, pause=0.035)
    except Exception:
        return False, False

    # The target was entered exactly once. From this point onward, never run a
    # second typing strategy; wait for the result under the conversation list.
    deadline = time.monotonic() + 5.0
    selected = None
    while time.monotonic() < deadline:
        window = _refresh_window(window)
        candidates = _candidate_controls(
            window,
            ("ListItem", "TreeItem", "Button", "Text"),
        )
        selected = _select_safe_chat_result(
            target,
            candidates,
            search_edit=search_edit,
        )
        if selected is not None:
            break
        time.sleep(0.14)

    if selected is None:
        return False, True

    status(
        "chat_result_click",
        "Sohbetler altındaki doğrulanmış kişi satırına basılıyor.",
        6,
        8,
    )
    ready = _activate_verified_chat_result(
        window,
        selected,
        target,
        visible=visible,
        duration=duration,
        pointer=pointer,
    )
    return ready is not None, True


def _chat_shortcut_skill(
    window: Any,
    app_name: str,
    target: str,
    status,
    *,
    visible: bool,
    duration: float,
    pointer: NetoSystemCursor | None,
) -> bool:
    family = _chat_family(app_name, window)
    shortcut = CHAT_SEARCH_SHORTCUTS.get(family)

    if not shortcut:
        return False

    status(
        "target_shortcut",
        "Doğrudan tıklama bulunamadı; uygulamanın yerel arama yedeği kullanılıyor.",
        5,
        8,
    )

    try:
        _focus_window(
            window,
            visible=visible,
            duration=duration,
            pointer=pointer,
        )
        _visible_hotkey(
            shortcut,
            visible=visible,
            duration=duration,
        )
        time.sleep(0.45)
        _replace_focused_text_once(target, pause=0.035)
        time.sleep(0.95)

        _, send_keys = _load_pywinauto()
        send_keys("{ENTER}")
        return _wait_for_conversation_ready(
            window,
            target,
            selected=None,
            timeout=2.4,
        ) is not None

    except Exception:
        return False


def _is_discord_window(window: Any) -> bool:
    title = _normalize(_window_text(window))
    if "discord" in title:
        return True
    try:
        process_id = int(window.process_id())
        import psutil
        process_name = _normalize(psutil.Process(process_id).name())
        return "discord" in process_name
    except Exception:
        return False


def _open_target(
    window: Any,
    app_name: str,
    target: str,
    status,
    *,
    visible: bool,
    duration: float,
    pointer: NetoSystemCursor | None,
    require_message_field: bool = False,
) -> None:
    if not target:
        return

    # Öncelik doğrudan görünür tıklamadır. Arama alanına hedef bir kez
    # yazıldıysa ikinci bir yöntem aynı hedefi tekrar yazamaz.
    opened, query_entered = _click_chat_search_and_result(
        window,
        target,
        status,
        visible=visible,
        duration=duration,
        pointer=pointer,
    )
    if opened:
        return
    if query_entered:
        raise AgentTaskError(
            "Kişi adı arama alanına bir kez yazıldı ancak Sohbetler altında "
            "tam eşleşen sohbet satırı açılamadı. Aynı ad tekrar yazılmadı."
        )

    # Uygulama UIA alanı sunmuyorsa kısayol yedek olarak kullanılır.
    if _chat_shortcut_skill(
        window,
        app_name,
        target,
        status,
        visible=visible,
        duration=duration,
        pointer=pointer,
    ):
        return

    if _generic_open_target(
        window,
        target,
        status,
        visible=visible,
        duration=duration,
        pointer=pointer,
    ):
        if not require_message_field or _wait_for_conversation_ready(
            window,
            target,
            selected=None,
            timeout=2.2,
        ) is not None:
            return

    raise AgentTaskError(
        "Hedef sohbet satırı seçilemedi veya mesaj yazma alanı açılmadı."
        if require_message_field
        else "Uygulama açıldı ancak hedef konuşma veya öğe bulunamadı."
    )


def _send_chat_message(
    window: Any,
    message: str,
    status,
    *,
    visible: bool,
    duration: float,
    confirmed_send: bool,
    pointer: NetoSystemCursor | None,
) -> dict[str, Any]:
    if not confirmed_send:
        raise AgentTaskError(
            "Mesaj gönderimi kullanıcı tarafından onaylanmadı."
        )
    if not str(message or "").strip():
        raise AgentTaskError("Gönderilecek mesaj boş.")

    send_started = time.monotonic()
    composer_wait_started = send_started

    status(
        "message_field",
        "Sohbet açıldı; gerçek fare 'Bir mesaj yazın' alanına gidiyor.",
        7,
        8,
    )

    ready = _wait_for_message_edit(window, timeout=3.2)
    if ready is None:
        raise AgentTaskError(
            "Mesaj yazma alanı bulunamadı. Arama kutusuna yazmamak için işlem durduruldu."
        )
    window, edit = ready
    composer_ready_seconds = time.monotonic() - composer_wait_started

    _visible_click(
        edit,
        visible=visible,
        duration=duration,
        pointer=pointer,
    )
    try:
        edit.set_focus()
    except Exception:
        pass
    time.sleep(0.16)

    focus_state = _control_has_keyboard_focus(edit)
    if focus_state is False:
        _visible_click(
            edit,
            visible=visible,
            duration=max(0.07, duration * 0.65),
            pointer=pointer,
        )
        time.sleep(0.12)
        focus_state = _control_has_keyboard_focus(edit)
        if focus_state is False:
            raise AgentTaskError(
                "Mesaj alanı odaklanmadı; yanlış alana yazmamak için işlem durduruldu."
            )

    # Hard safety gate: the contact-search box must never own keyboard focus here.
    focused_search = _focused_search_control(window)
    if focused_search is not None:
        raise AgentTaskError(
            "Sohbet arama kutusu hâlâ etkin. Mesaj yanlış yere yazılmasın diye işlem durduruldu."
        )

    # Use one keyboard path only. Electron may mutate a field and still raise from
    # set_edit_text(), which would otherwise duplicate the outgoing message.
    typing_started = time.monotonic()
    _replace_focused_text_once(message, pause=0.025)
    message_type_seconds = time.monotonic() - typing_started

    # Do not rescan WhatsApp's entire UI Automation tree after typing. On some
    # Electron builds that descendants() query blocks indefinitely even though
    # the message is already visible in the composer. Focus and search safety
    # were verified immediately before the single write above.
    time.sleep(0.22)

    # Critical ordering rule: no status, DPAPI, disk or UIA operation is allowed
    # between the completed message text and the physical Enter event. Earlier
    # builds could freeze in status() here and leave the full message unsent.
    pyautogui = _load_pyautogui()
    enter_started = time.monotonic()
    pyautogui.keyDown("enter")
    try:
        time.sleep(0.035)
    finally:
        pyautogui.keyUp("enter")
    enter_dispatch_seconds = time.monotonic() - enter_started

    if pointer is not None:
        pointer.close()

    terminal_status_started = time.monotonic()
    status(
        "message_sent",
        "Fiziksel Enter gönderildi; mesaj görevi tamamlandı.",
        8,
        8,
        done=True,
        ok=True,
    )
    terminal_status_seconds = time.monotonic() - terminal_status_started
    return {
        "composer_ready_seconds": round(max(0.0, composer_ready_seconds), 4),
        "message_type_seconds": round(max(0.0, message_type_seconds), 4),
        "enter_dispatch_seconds": round(max(0.0, enter_dispatch_seconds), 4),
        "terminal_status_seconds": round(max(0.0, terminal_status_seconds), 4),
        "total_send_stage_seconds": round(max(0.0, time.monotonic() - send_started), 4),
        "enter_dispatched": True,
    }


def _write_vault_record_bounded(
    session_id: str,
    value: dict[str, Any],
    *,
    timeout: float = 1.25,
) -> bool:
    """Write the optional local audit record without holding the task UI open.

    DPAPI and NTFS ACL work is normally fast, but a stalled Windows security
    service or icacls process must not leave a successfully sent message task in
    an endless active state. The record is best-effort; task completion and cursor
    restoration take priority.
    """
    finished = threading.Event()
    outcome = {"ok": False}

    def _writer() -> None:
        try:
            write_vault_record(session_id, value)
            outcome["ok"] = True
        except BaseException:
            outcome["ok"] = False
        finally:
            finished.set()

    thread = threading.Thread(
        target=_writer,
        name="NetoAgentVaultWriter",
        daemon=True,
    )
    thread.start()
    finished.wait(max(0.1, float(timeout)))
    return bool(finished.is_set() and outcome["ok"])


def _build_google_search_url(query: str) -> str:
    cleaned = str(query or "").strip()
    if not cleaned:
        raise AgentTaskError("Web araması için sorgu bulunamadı.")
    return "https://www.google.com/search?q=" + quote_plus(cleaned)


def _open_google_search(query: str, status) -> None:
    url = _build_google_search_url(query)
    status(
        "web_search_opening",
        "Varsayılan tarayıcı açılıyor; sorgu Google'a gönderilecek.",
        2,
        5,
        network_data_sent=True,
    )
    try:
        os.startfile(url)
    except Exception as exc:
        raise AgentTaskError("Varsayılan tarayıcı üzerinden web araması açılamadı.") from exc

    time.sleep(1.2)
    status(
        "web_search_opened",
        "Google araması varsayılan tarayıcıda açıldı.",
        4,
        5,
        network_data_sent=True,
    )


def run_request(request_path: Path, status_path: Path) -> int:
    request = read_encrypted_json(request_path)
    secure_delete(request_path)

    session_id = str(request["session_id"])
    kind = str(request.get("kind") or "application").strip()
    app_name = str(request.get("app") or "").strip()
    target = str(request.get("target") or "").strip()
    query = str(request.get("query") or "").strip()
    provider = str(request.get("provider") or "").strip()
    message = str(request.get("message") or "")
    confirmed_send = bool(request.get("confirmed_send", False))

    (
        visible_mouse,
        pointer_enabled,
        edge_animation_enabled,
        mouse_duration,
    ) = _mouse_options(request)

    started_at = _utc_now()
    sequence = 0
    pointer = NetoSystemCursor(pointer_enabled)
    actual_pointer_enabled = bool(pointer.enabled and pointer._installed)
    edges = NetoEdgePulseOverlay(edge_animation_enabled)
    edges_stopped = False

    def stop_edges_now() -> None:
        nonlocal edges_stopped
        if not edges_stopped:
            edges_stopped = True
            edges.stop()

    def status(
        code: str,
        message_text: str,
        step: int,
        total: int,
        *,
        done: bool = False,
        ok: bool | None = None,
        network_data_sent: bool = False,
    ):
        nonlocal sequence
        sequence += 1
        payload = {
            "session_id": session_id,
            "sequence": sequence,
            "code": code,
            "message": message_text,
            "step": step,
            "total": total,
            "done": done,
            "ok": ok,
            "timestamp": _utc_now(),
            "network_data_sent": bool(network_data_sent),
            "screenshots_taken": False,
        }
        # Direct pipe first: the UI receives completion even if disk, DPAPI or
        # Windows ACL services are unhealthy. The JSON file is fallback only.
        live_line = "NETO_AGENT_STATUS:" + json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ) + "\n"
        try:
            print(live_line, end="", flush=True)
        except Exception:
            # PyInstaller windowed builds may set sys.stdout to None even when
            # the parent supplied a pipe. Writing file descriptor 1 preserves
            # the direct channel when the OS standard handle still exists.
            try:
                os.write(1, live_line.encode("utf-8", errors="replace"))
            except Exception:
                pass
        try:
            write_live_status_json(status_path, payload)
        except Exception:
            pass

    result: dict[str, Any] = {
        "session_id": session_id,
        "started_at": started_at,
        "finished_at": None,
        "kind": kind,
        "application": app_name or None,
        "target": target or None,
        "query": query or None,
        "provider": provider or None,
        "message_length": (
            len(message) if kind == "chat_message" else None
        ),
        "message_sha256": (
            hashlib.sha256(
                message.encode("utf-8")
            ).hexdigest()
            if kind == "chat_message"
            else None
        ),
        "purple_cursor": actual_pointer_enabled,
        "edge_animation": edge_animation_enabled,
        "ok": False,
        "error": None,
        "network_data_sent": kind == "web_search",
        "screenshots_taken": False,
        "worker_exited": True,
        "storage": "Encrypted request/vault + direct non-sensitive live status pipe",
        "timings": {},
    }

    try:
        status(
            "initializing",
            (
                (
                    "Gerçek mor Windows imleci ve ekran kenarı animasyonu etkin."
                    if actual_pointer_enabled
                    else (
                        "Gerçek Windows faresi etkin; mor sistem imleci Windows tarafından uygulanamadı."
                        if pointer_enabled and pointer.error
                        else "Ekran kenarı animasyonu ve gerçek Windows faresi etkin."
                    )
                )
                if pointer_enabled or edge_animation_enabled
                else "Geçici yerel ajan başlatıldı."
            ),
            1,
            8,
        )

        if kind == "web_search":
            if provider and provider != "google":
                raise AgentTaskError(
                    "Bu sürümde yalnızca görünür Google araması destekleniyor."
                )
            _open_google_search(query, status)
            stop_edges_now()

        elif kind in {"application", "chat_message"}:
            if not app_name:
                raise AgentTaskError(
                    "Açılacak uygulama adı bulunamadı."
                )

            application_launch_started = time.monotonic()
            window = _launch_app(
                app_name,
                status,
                visible=visible_mouse,
                duration=mouse_duration,
                pointer=pointer,
            )
            result["timings"]["application_launch_seconds"] = round(
                max(0.0, time.monotonic() - application_launch_started),
                4,
            )

            stop_edges_now()

            status(
                "application_ready",
                "Uygulama penceresi hazır; kenar animasyonu kapatıldı.",
                4,
                8,
            )

            if target:
                target_open_started = time.monotonic()
                _open_target(
                    window,
                    app_name,
                    target,
                    status,
                    visible=visible_mouse,
                    duration=mouse_duration,
                    pointer=pointer,
                    require_message_field=(kind == "chat_message"),
                )
                result["timings"]["target_open_seconds"] = round(
                    max(0.0, time.monotonic() - target_open_started),
                    4,
                )
            else:
                status(
                    "application_opened",
                    "Uygulama açıldı.",
                    8,
                    8,
                )

            if kind == "chat_message":
                if not target or not message:
                    raise AgentTaskError(
                        "Mesaj hedefi veya mesaj metni bulunamadı."
                    )
                send_timing = _send_chat_message(
                    window,
                    message,
                    status,
                    visible=visible_mouse,
                    duration=mouse_duration,
                    confirmed_send=confirmed_send,
                    pointer=pointer,
                )
                result["timings"]["message_send"] = send_timing

        else:
            raise AgentTaskError(
                "Desteklenmeyen NetOps Agent görev türü."
            )

        result["ok"] = True
        result["finished_at"] = _utc_now()

        # Chat completion was published immediately after the physical Enter.
        # Other tasks publish their terminal status here. Audit storage remains
        # best-effort and the controller detaches/reaps this worker independently.
        if kind != "chat_message":
            pointer.close()
            status(
                "completed",
                (
                    "Görev tamamlandı; ajan kapatılıyor."
                    if kind == "application"
                    else "Web araması açıldı; ajan kapatılıyor."
                ),
                8,
                8,
                done=True,
                ok=True,
                network_data_sent=kind == "web_search",
            )
        _write_vault_record_bounded(session_id, result)
        return 0

    except BaseException as exc:
        result["finished_at"] = _utc_now()
        result["error"] = str(exc)

        try:
            status(
                "failed",
                f"Görev tamamlanamadı: {exc}",
                8,
                8,
                done=True,
                ok=False,
                network_data_sent=kind == "web_search",
            )
        except Exception:
            pass

        pointer.close()
        _write_vault_record_bounded(session_id, result)
        return 1

    finally:
        stop_edges_now()
        pointer.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--request", required=True)
    parser.add_argument("--status", required=True)
    args = parser.parse_args(argv)
    try:
        return run_request(Path(args.request), Path(args.status))
    except BaseException:
        try:
            traceback.print_exc()
        except Exception:
            pass
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
