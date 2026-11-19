"""Safe, allowlisted desktop actions inspired by AutoHotkey workflows."""
from __future__ import annotations

from typing import Any


HOTKEYS: dict[str, tuple[str, ...]] = {
    "copy": ("ctrl", "c"),
    "paste": ("ctrl", "v"),
    "cut": ("ctrl", "x"),
    "save": ("ctrl", "s"),
    "select_all": ("ctrl", "a"),
    "close_window": ("alt", "f4"),
    "show_desktop": ("win", "d"),
    "task_view": ("win", "tab"),
    "media_play_pause": ("media_play_pause",),
    "media_next": ("media_next",),
    "media_previous": ("media_previous",),
}


def execute_hotkey(name: str) -> dict[str, Any]:
    """Execute one named shortcut; arbitrary key strings are rejected."""
    key = "_".join(str(name or "").strip().casefold().split())
    sequence = HOTKEYS.get(key)
    if sequence is None:
        return {"ok": False, "message": "Bu masaüstü kısayoluna izin verilmiyor."}
    try:
        import pyautogui

        if sequence[0].startswith("media_"):
            try:
                import neto_now_playing

                media_fn = getattr(neto_now_playing, sequence[0], None)
                if not callable(media_fn):
                    return {"ok": False, "name": key, "message": "Medya denetimi kullanılamıyor."}
                result = media_fn()
                return {"ok": bool(result), "name": key, "message": "Medya kısayolu çalıştırıldı."}
            except Exception:
                return {"ok": False, "name": key, "message": "Medya denetimi kullanılamıyor."}
        pyautogui.hotkey(*sequence)
        return {"ok": True, "name": key, "message": "Masaüstü kısayolu çalıştırıldı."}
    except Exception as exc:
        return {"ok": False, "name": key, "message": f"Kısayol çalıştırılamadı: {exc}"}


def focus_window(title: str) -> dict[str, Any]:
    """Focus a matching visible window without sending arbitrary input."""
    wanted = " ".join(str(title or "").split())
    if not wanted or len(wanted) > 160:
        return {"ok": False, "message": "Geçerli bir pencere başlığı gerekli."}
    try:
        import pygetwindow

        matches = pygetwindow.getWindowsWithTitle(wanted)
        for window in matches:
            if getattr(window, "isMinimized", False):
                window.restore()
            window.activate()
            return {"ok": True, "title": str(getattr(window, "title", wanted)), "message": "Pencere öne alındı."}
        return {"ok": False, "message": "Pencere bulunamadı."}
    except Exception as exc:
        return {"ok": False, "message": f"Pencere odaklanamadı: {exc}"}


__all__ = ["HOTKEYS", "execute_hotkey", "focus_window"]
