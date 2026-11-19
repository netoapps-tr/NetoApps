"""Safe bridge for the one-time NetOps Windows session setup.

The assistant may request a visible Windows user switch, but it never stores a
password or creates a new account on every command. Account provisioning and
the logon task are handled by the explicit administrator setup script.
"""

from __future__ import annotations

import ctypes
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ACCOUNT_NAME = "NetOps"
TASK_NAME = r"\NetOps\NetOps-AutoStart"
TASK_PATH = "\\NetOps\\"
TASK_LEAF_NAME = "NetOps-AutoStart"


def current_user_name() -> str:
    if os.name == "nt":
        try:
            size = ctypes.c_ulong(256)
            buffer = ctypes.create_unicode_buffer(size.value)
            if ctypes.windll.advapi32.GetUserNameW(buffer, ctypes.byref(size)):
                return str(buffer.value or "").strip()
        except Exception:
            pass
    return str(os.environ.get("USERNAME") or os.environ.get("USER") or "").strip()


def local_account_exists(account_name: str = ACCOUNT_NAME) -> bool:
    if os.name != "nt":
        return False
    try:
        result = subprocess.run(
            ["net", "user", str(account_name)],
            capture_output=True,
            text=True,
            timeout=4,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def list_sessions() -> list[dict[str, Any]]:
    """Return best-effort interactive Windows sessions without credentials."""
    if os.name != "nt":
        return []
    try:
        result = subprocess.run(
            ["quser"],
            capture_output=True,
            text=True,
            timeout=4,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return []
    sessions: list[dict[str, Any]] = []
    for raw_line in (result.stdout or "").splitlines():
        line = raw_line.strip().lstrip(">")
        if not line or line.lower().startswith("username"):
            continue
        parts = re.split(r"\s+", line)
        if len(parts) < 4:
            continue
        session_id = next((part for part in parts[1:4] if part.isdigit()), "")
        state = next((part for part in parts[1:] if part.casefold() in {"active", "disc", "listen"}), "unknown")
        sessions.append({"user": parts[0], "session_id": session_id, "state": state})
    return sessions


def netops_sessions() -> list[dict[str, Any]]:
    return [item for item in list_sessions() if str(item.get("user") or "").casefold() == ACCOUNT_NAME.casefold()]


def autostart_task_exists() -> bool:
    if os.name != "nt":
        return False
    try:
        command = (
            "$task = Get-ScheduledTask -TaskPath '\\NetOps\\' "
            "-TaskName 'NetOps-AutoStart' -ErrorAction SilentlyContinue; "
            "if ($null -eq $task) { exit 1 }"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True,
            text=True,
            timeout=4,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def setup_script_path() -> Path | None:
    """Find the bundled or source setup script without depending on CWD."""
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            candidates.append(Path(meipass) / "setup-netops-session.ps1")
        candidates.append(Path(sys.executable).resolve().parent / "setup-netops-session.ps1")
    candidates.append(Path(__file__).resolve().with_name("setup-netops-session.ps1"))
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def launch_admin_setup() -> dict[str, Any]:
    """Start the one-time setup through the normal Windows UAC prompt."""
    if os.name != "nt":
        return {"ok": False, "status": "unsupported", "message": "Bu kurulum yalnızca Windows'ta kullanılabilir."}
    script = setup_script_path()
    if script is None:
        return {"ok": False, "status": "setup_missing", "message": "NetOps kurulum bileşeni bu sürümde bulunamadı."}
    try:
        params = f'-NoProfile -ExecutionPolicy Bypass -File "{script}"'
        result = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            "powershell.exe",
            params,
            str(script.parent),
            1,
        )
        if int(result) <= 32:
            return {"ok": False, "status": "uac_cancelled", "message": "Windows yönetici onayı alınamadı."}
        return {
            "ok": True,
            "status": "setup_started",
            "message": "NetOps oturum kurulumu başlatıldı. Windows izin penceresini onayla; kurulum penceresindeki adımları tamamladıktan sonra oturuma geçebilirsin.",
        }
    except Exception as exc:
        return {"ok": False, "status": "setup_failed", "message": f"NetOps oturum kurulumu başlatılamadı: {exc}"}


def build_autostart_command(executable: str | os.PathLike[str]) -> list[str]:
    path = str(Path(executable).expanduser().resolve())
    return [
        "schtasks",
        "/Create",
        "/SC",
        "ONLOGON",
        "/TN",
        TASK_NAME,
        "/TR",
        f'"{path}" --netops-session',
        "/RU",
        ACCOUNT_NAME,
        "/RL",
        "LIMITED",
        "/F",
    ]


def request_user_switch() -> bool:
    """Open the visible Windows lock/user-switch screen."""
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.user32.LockWorkStation())
    except Exception:
        return False


def switch_to_netops_session() -> dict[str, Any]:
    """Reuse the NetOps account and ask Windows to switch visibly."""
    if os.name != "nt":
        return {"ok": False, "status": "unsupported", "message": "Akıllı Windows oturumu yalnızca Windows'ta kullanılabilir."}
    if current_user_name().casefold() == ACCOUNT_NAME.casefold():
        return {"ok": True, "status": "already_active", "message": "Zaten NetOps oturumundasın; yeni oturum oluşturulmadı."}
    if not local_account_exists():
        return launch_admin_setup()
    if not autostart_task_exists():
        return launch_admin_setup()
    existing = netops_sessions()
    locked = request_user_switch()
    if not locked:
        return {"ok": False, "status": "switch_failed", "sessions": existing, "message": "Windows kullanıcı geçiş ekranı açılamadı."}
    return {
        "ok": True,
        "status": "switch_requested",
        "reused": bool(existing),
        "sessions": existing,
        "message": "Windows kullanıcı geçişi açıldı. NetOps hesabını seç; mevcut oturum varsa yenisi oluşturulmayacak.",
    }


__all__ = [
    "ACCOUNT_NAME",
    "TASK_NAME",
    "TASK_PATH",
    "TASK_LEAF_NAME",
    "autostart_task_exists",
    "build_autostart_command",
    "current_user_name",
    "launch_admin_setup",
    "list_sessions",
    "local_account_exists",
    "netops_sessions",
    "request_user_switch",
    "setup_script_path",
    "switch_to_netops_session",
]
