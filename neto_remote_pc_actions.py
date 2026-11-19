"""Allowlisted PC actions exposed to authenticated NetOps devices."""
from __future__ import annotations

import ctypes
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


_PROGRAMS: dict[str, dict[str, Any]] = {
    "chrome": {"title": "Google Chrome", "commands": ("chrome.exe",), "aliases": ("chrome", "google chrome")},
    "edge": {"title": "Microsoft Edge", "commands": ("msedge.exe",), "aliases": ("edge", "microsoft edge")},
    "firefox": {"title": "Firefox", "commands": ("firefox.exe",), "aliases": ("firefox",)},
    "vscode": {"title": "Visual Studio Code", "commands": ("code.exe", "code"), "aliases": ("vscode", "vs code", "visual studio code")},
    "spotify": {"title": "Spotify", "commands": ("spotify.exe",), "aliases": ("spotify",)},
    "discord": {"title": "Discord", "commands": ("Discord.exe",), "aliases": ("discord",)},
    "notepad": {"title": "Not Defteri", "commands": ("notepad.exe",), "aliases": ("notepad", "not defteri")},
    "calculator": {"title": "Hesap Makinesi", "commands": ("calc.exe",), "aliases": ("calculator", "hesap makinesi", "hesapla")},
    "explorer": {"title": "Dosya Gezgini", "commands": ("explorer.exe",), "aliases": ("explorer", "dosya gezgini")},
    "powershell": {"title": "PowerShell", "commands": ("powershell.exe",), "aliases": ("powershell",)},
    "cmd": {"title": "Komut Istemi", "commands": ("cmd.exe",), "aliases": ("cmd", "komut istemi")},
    "taskmgr": {"title": "Gorev Yoneticisi", "commands": ("taskmgr.exe",), "aliases": ("taskmgr", "gorev yoneticisi")},
    "settings": {"title": "Windows Ayarlari", "commands": ("ms-settings:",), "aliases": ("ayarlar", "windows ayarlari")},
}

_OPEN_WORDS = ("aç", "ac", "başlat", "baslat", "çalıştır", "calistir", "open", "start")

# Remote keyboard input is deliberately an allowlist, not an arbitrary
# keylogger/injection channel. Letters are app shortcuts; navigation keys are
# forwarded to the currently focused Windows application.
_INPUT_APP_SHORTCUTS = {
    "c": "chrome",
    "e": "edge",
    "f": "firefox",
    "v": "vscode",
    "s": "spotify",
    "n": "notepad",
    "x": "explorer",
    "a": "settings",
}
_INPUT_VIRTUAL_KEYS = {
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "enter": 0x0D,
    "escape": 0x1B,
    "esc": 0x1B,
    "space": 0x20,
    "tab": 0x09,
    "home": 0x24,
    "end": 0x23,
}
_INPUT_ALIASES = {
    "\u001b[a": "up",
    "\u001b[b": "down",
    "\u001b[c": "right",
    "\u001b[d": "left",
    "arrowup": "up",
    "arrowdown": "down",
    "arrowleft": "left",
    "arrowright": "right",
    "return": "enter",
}


def program_catalog() -> dict[str, dict[str, Any]]:
    return {key: dict(value) for key, value in _PROGRAMS.items()}


def input_catalog() -> dict[str, Any]:
    """Describe the intentionally small remote control surface."""
    return {
        "app_shortcuts": dict(_INPUT_APP_SHORTCUTS),
        "navigation_keys": tuple(_INPUT_VIRTUAL_KEYS),
    }


def _normalized(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def parse_open_program(command: str) -> str | None:
    value = _normalized(command)
    if not any(word in value for word in _OPEN_WORDS):
        return None
    for program_id, metadata in sorted(_PROGRAMS.items(), key=lambda item: len(item[0]), reverse=True):
        if any(alias in value for alias in metadata["aliases"]):
            return program_id
    return None


def _candidate_paths(command: str) -> tuple[str, ...]:
    if command.casefold().endswith(":"):
        return (command,)
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    local_app_data = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
    name = command.casefold()
    extra: list[str] = []
    if name == "chrome.exe":
        extra.extend((f"{program_files}\\Google\\Chrome\\Application\\chrome.exe", f"{local_app_data}\\Google\\Chrome\\Application\\chrome.exe"))
    elif name == "msedge.exe":
        extra.append(f"{program_files}\\Microsoft\\Edge\\Application\\msedge.exe")
    elif name == "firefox.exe":
        extra.append(f"{program_files}\\Mozilla Firefox\\firefox.exe")
    elif name == "code.exe":
        extra.append(f"{local_app_data}\\Programs\\Microsoft VS Code\\Code.exe")
    elif name == "spotify.exe":
        extra.append(f"{local_app_data}\\Spotify\\Spotify.exe")
    elif name in {"notepad.exe", "calc.exe", "explorer.exe", "powershell.exe", "cmd.exe", "taskmgr.exe"}:
        extra.append(f"{system_root}\\System32\\{command}")
    return (command, *extra)


def _resolve_executable(program_id: str) -> str | None:
    metadata = _PROGRAMS.get(program_id)
    if metadata is None:
        return None
    for command in metadata["commands"]:
        if command == "ms-settings:":
            return command
        found = shutil.which(command)
        if found:
            return found
        for candidate in _candidate_paths(command):
            if Path(candidate).is_file():
                return candidate
    return None


def open_program(program_id: str) -> dict[str, Any]:
    metadata = _PROGRAMS.get(str(program_id or "").strip().casefold())
    if metadata is None:
        return {"ok": False, "error": "PROGRAM_NOT_ALLOWED"}
    if os.name != "nt":
        return {"ok": False, "error": "WINDOWS_ONLY"}
    executable = _resolve_executable(str(program_id).strip().casefold())
    if not executable:
        return {"ok": False, "error": "PROGRAM_NOT_INSTALLED", "title": metadata["title"]}
    try:
        if executable == "ms-settings:":
            os.startfile(executable)  # type: ignore[attr-defined]
        else:
            subprocess.Popen([executable], cwd=str(Path(executable).parent), close_fds=True)
    except (OSError, ValueError) as exc:
        return {"ok": False, "error": "PROGRAM_START_FAILED", "detail": str(exc)}
    return {"ok": True, "program": str(program_id).strip().casefold(), "title": metadata["title"]}


def open_folder(folder_id: str) -> dict[str, Any]:
    folders = {
        "masaüstü": Path.home() / "Desktop",
        "masaustu": Path.home() / "Desktop",
        "belgeler": Path.home() / "Documents",
        "indirilenler": Path.home() / "Downloads",
    }
    target = folders.get(_normalized(folder_id))
    if target is None:
        return {"ok": False, "error": "FOLDER_NOT_ALLOWED"}
    if os.name != "nt":
        return {"ok": False, "error": "WINDOWS_ONLY"}
    try:
        subprocess.Popen(["explorer.exe", str(target)], close_fds=True)
    except (OSError, ValueError) as exc:
        return {"ok": False, "error": "FOLDER_OPEN_FAILED", "detail": str(exc)}
    return {"ok": True, "folder": str(target)}


def _send_virtual_key(key_code: int) -> bool:
    """Press and release one allowlisted Windows virtual key."""
    if os.name != "nt":
        return False

    class _KeyInput(ctypes.Structure):
        _fields_ = [
            ("wVk", ctypes.c_ushort),
            ("wScan", ctypes.c_ushort),
            ("dwFlags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("dwExtraInfo", ctypes.c_void_p),
        ]

    class _Input(ctypes.Structure):
        _fields_ = [("type", ctypes.c_ulong), ("ki", _KeyInput)]

    try:
        user32 = ctypes.windll.user32
        down = _Input(1, _KeyInput(key_code, 0, 0, 0, None))
        up = _Input(1, _KeyInput(key_code, 0, 0x0002, 0, None))
        sent_down = user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(_Input))
        sent_up = user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(_Input))
        return sent_down == 1 and sent_up == 1
    except (AttributeError, OSError, TypeError):
        return False


def handle_remote_input(key: str, modifiers: Any = None) -> dict[str, Any]:
    """Handle one safe phone-control key without accepting arbitrary text."""
    normalized = _normalized(key)
    normalized = _INPUT_ALIASES.get(normalized, normalized)
    if modifiers not in (None, [], (), ""):
        return {"ok": False, "error": "INPUT_MODIFIERS_NOT_ALLOWED"}
    if normalized in _INPUT_APP_SHORTCUTS:
        result = open_program(_INPUT_APP_SHORTCUTS[normalized])
        if result.get("ok"):
            return {**result, "key": normalized, "mode": "app_shortcut"}
        return result
    key_code = _INPUT_VIRTUAL_KEYS.get(normalized)
    if key_code is None:
        return {"ok": False, "error": "INPUT_KEY_NOT_ALLOWED", "key": normalized}
    if not _send_virtual_key(key_code):
        return {"ok": False, "error": "INPUT_SEND_FAILED", "key": normalized}
    return {"ok": True, "key": normalized, "mode": "navigation"}


def handle_remote_pc_command(command: str) -> dict[str, Any] | None:
    value = _normalized(command)
    if not value:
        return None
    program = parse_open_program(value)
    if program is not None:
        return open_program(program)
    if any(word in value for word in _OPEN_WORDS) and (".exe" in value or "program" in value or "uygulama" in value):
        return {"ok": False, "error": "PROGRAM_NOT_ALLOWED"}
    if "masaüstü" in value or "masaustu" in value:
        if any(word in value for word in _OPEN_WORDS):
            return open_folder("masaüstü")
    for folder in ("belgeler", "indirilenler"):
        if folder in value and any(word in value for word in _OPEN_WORDS):
            return open_folder(folder)
    if value in {"pc kilitle", "bilgisayarı kilitle", "bilgisayari kilitle", "ekranı kilitle", "ekrani kilitle"}:
        if os.name != "nt":
            return {"ok": False, "error": "WINDOWS_ONLY"}
        try:
            subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"], close_fds=True)
        except (OSError, ValueError) as exc:
            return {"ok": False, "error": "LOCK_FAILED", "detail": str(exc)}
        return {"ok": True, "action": "lock"}
    return None


def command_catalog_text() -> str:
    names = ", ".join(metadata["title"] for metadata in _PROGRAMS.values())
    return f"PC açma komutları: {names}; Masaüstünü aç; Belgeleri aç; İndirilenler aç; PC kilitle."


__all__ = [
    "command_catalog_text",
    "handle_remote_input",
    "input_catalog",
    "handle_remote_pc_command",
    "open_folder",
    "open_program",
    "parse_open_program",
    "program_catalog",
]
