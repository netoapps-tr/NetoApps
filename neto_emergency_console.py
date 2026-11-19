"""NetOps owner/admin emergency console.

The trigger is intentionally absent from normal UI. It is not a backdoor:
Windows identity is checked before the panel opens, and every action remains
inside the existing NetOps permission boundary.
"""
from __future__ import annotations

import csv
import getpass
import hashlib
import json
import os
import platform
import secrets
import subprocess
import threading
import time
from pathlib import Path
from typing import Any


TRIGGER = "<Control-Alt-Shift-N>"
OWNER_ROLE = "AAF"
MAX_RECOVERY_ATTEMPTS = 5
RECOVERY_LOCK_SECONDS = 15 * 60


def _state_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "NetoAssistant" / "security"


def current_identity() -> str:
    try:
        completed = subprocess.run(
            ["whoami"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3,
            check=False,
        )
        value = (completed.stdout or "").strip()
        if value:
            return value.casefold()
    except Exception:
        pass
    return str(getpass.getuser() or "unknown").casefold()


def current_sid() -> str:
    """Return the Windows SID, which is safer to pin than a display name."""
    if os.name == "nt":
        try:
            completed = subprocess.run(
                ["whoami", "/user", "/fo", "csv", "/nh"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=3,
                check=False,
            )
            rows = list(csv.reader((completed.stdout or "").splitlines()))
            if rows and len(rows[0]) >= 2 and rows[0][1].strip():
                return rows[0][1].strip().casefold()
        except Exception:
            pass
    return current_identity()


def is_windows_admin() -> bool:
    if os.name != "nt":
        return False
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _owner_path() -> Path:
    return _state_dir() / "emergency-owner.json"


def ensure_owner() -> str:
    """Pin the first local owner identity; administrators remain eligible."""
    identity = current_identity()
    sid = current_sid()
    path = _owner_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            saved_sid = str(data.get("owner_sid") or "").casefold()
            if saved_sid:
                return saved_sid
            saved = str(data.get("owner") or "").casefold()
            if saved:
                return saved
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"role": OWNER_ROLE, "owner": identity, "owner_sid": sid}, ensure_ascii=True),
            encoding="utf-8",
        )
        os.replace(temporary, path)
    except Exception:
        pass
    return sid


def authorized_operator() -> bool:
    identity = current_identity()
    sid = current_sid()
    owner = ensure_owner()
    return bool(identity and (is_windows_admin() or sid == owner or identity == owner))


def _recovery_path() -> Path:
    return _state_dir() / "emergency-recovery.json"


def _recovery_digest(code: str, salt: str) -> str:
    return hashlib.sha256((salt + str(code)).encode("utf-8")).hexdigest()


def enroll_recovery_code() -> str:
    """Generate a one-time code; only its salted digest is persisted."""
    code = secrets.token_urlsafe(18)
    salt = secrets.token_hex(16)
    path = _recovery_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(
            {
                "role": OWNER_ROLE,
                "salt": salt,
                "digest": _recovery_digest(code, salt),
                "used": False,
                "failed_attempts": 0,
                "locked_until": 0,
            },
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )
    os.replace(temporary, path)
    return code


def verify_recovery_code(code: str) -> bool:
    """Verify once, rate-limit failures, and never persist the raw code."""
    path = _recovery_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        now = time.time()
        if data.get("used") or float(data.get("locked_until") or 0) > now:
            return False
        salt = str(data.get("salt") or "")
        expected = str(data.get("digest") or "")
        valid = bool(salt and expected and secrets.compare_digest(_recovery_digest(code, salt), expected))
        if valid:
            data["used"] = True
            data["failed_attempts"] = 0
        else:
            attempts = int(data.get("failed_attempts") or 0) + 1
            data["failed_attempts"] = attempts
            if attempts >= MAX_RECOVERY_ATTEMPTS:
                data["locked_until"] = now + RECOVERY_LOCK_SECONDS
        path.write_text(json.dumps(data, ensure_ascii=True), encoding="utf-8")
        return valid
    except Exception:
        return False


def install(root: Any, workspace: str | os.PathLike[str], *, palette: dict[str, str] | None = None, permission_manager: Any = None) -> str | None:
    """Install the hidden keyboard trigger and return its Tk binding id."""
    ensure_owner()
    if root is None or not hasattr(root, "bind_all"):
        return None

    def _open(_event=None):
        if not authorized_operator():
            return "break"
        show_panel(root, workspace, palette=palette, permission_manager=permission_manager)
        return "break"

    try:
        return root.bind_all(TRIGGER, _open, add="+")
    except Exception:
        return None


def show_panel(root: Any, workspace: str | os.PathLike[str], *, palette: dict[str, str] | None = None, permission_manager: Any = None) -> Any:
    """Open the owner/admin-only panel after identity verification."""
    if not authorized_operator():
        return None
    import customtkinter as ctk

    colors = {
        "bg": (palette or {}).get("bg", "#0B0D12"),
        "card": (palette or {}).get("card", "#181C24"),
        "text": (palette or {}).get("text_main", "#F4F7FB"),
        "muted": (palette or {}).get("text_dim", "#9AA6B8"),
        "accent": (palette or {}).get("neon", "#3B82F6"),
        "border": (palette or {}).get("entry_border", "#303B4D"),
    }
    existing = getattr(root, "_netops_emergency_panel", None)
    try:
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            return existing
    except Exception:
        pass

    panel = ctk.CTkToplevel(root)
    root._netops_emergency_panel = panel
    panel.title("Axvord")
    panel.configure(fg_color="#071B3A")
    panel.transient(root)
    try:
        panel.attributes("-fullscreen", True)
    except Exception:
        panel.geometry("1100x720")
    panel.bind("<Escape>", lambda _event: panel.destroy())

    topbar = ctk.CTkFrame(panel, fg_color="#0A2348", corner_radius=0, height=72)
    topbar.pack(fill="x", side="top")
    topbar.pack_propagate(False)
    ctk.CTkLabel(topbar, text="AXVORD", anchor="w", font=("Segoe UI Semibold", 26), text_color="#FFFFFF").pack(side="left", padx=34, pady=18)
    ctk.CTkLabel(topbar, text="NetOps çekirdek çalışma alanı", anchor="e", font=("Segoe UI", 12), text_color="#9EC5FF").pack(side="right", padx=34, pady=23)

    body = ctk.CTkFrame(panel, fg_color="#071B3A", corner_radius=0)
    body.pack(fill="both", expand=True, padx=34, pady=34)
    hero = ctk.CTkFrame(body, fg_color="#0B2A58", corner_radius=24, border_width=1, border_color="#1D5EAE")
    hero.pack(fill="x", pady=(0, 20))
    ctk.CTkLabel(hero, text="Axvord", anchor="w", font=("Segoe UI Semibold", 42), text_color="#FFFFFF").pack(fill="x", padx=30, pady=(28, 2))
    ctk.CTkLabel(hero, text="NetOps yerel yönetim çekirdeği hazır.", anchor="w", font=("Segoe UI", 15), text_color="#B9D8FF").pack(fill="x", padx=30, pady=(0, 26))

    output = ctk.CTkTextbox(body, height=210, fg_color="#08162F", border_width=1, border_color="#1D5EAE", text_color="#EAF3FF", font=("Consolas", 12))
    output.pack(fill="both", expand=True, pady=(0, 20))

    def write(text: str) -> None:
        try:
            output.configure(state="normal")
            output.delete("1.0", "end")
            output.insert("1.0", text)
            output.configure(state="disabled")
        except Exception:
            pass

    write(f"Yetkili: {current_identity()}\nRol: {OWNER_ROLE}\nSistem: {platform.system()}\nDurum: Hazır\n")

    buttons = ctk.CTkFrame(body, fg_color="transparent")
    buttons.pack(fill="x", pady=(0, 10))

    def show_status() -> None:
        from neto_agent_bridge import AgentToolBridge

        data = AgentToolBridge(workspace, permission_manager=permission_manager).system_status()
        write(json.dumps(data, ensure_ascii=False, indent=2))

    def verify() -> None:
        from neto_local_agent_runner import NetOpsLocalAgentRunner

        runner = NetOpsLocalAgentRunner(workspace)

        def worker() -> None:
            try:
                result = runner.verify()
                text = result.message + "\n\n" + json.dumps(result.data, ensure_ascii=False, indent=2)
            except Exception as exc:
                text = f"Doğrulama başarısız: {exc}"
            try:
                panel.after(0, lambda: write(text))
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()
        write("Güvenli proje doğrulaması çalışıyor...")

    def create_recovery_code() -> None:
        code = enroll_recovery_code()
        write(
            "AXVORD ERİŞİM ANAHTARI (yalnızca şimdi gösteriliyor)\n\n"
            f"{code}\n\nBu kodu güvenli bir parola yöneticisine kaydet."
        )

    ctk.CTkButton(buttons, text="Sistem durumu", command=show_status, fg_color="#123A70", hover_color="#1D5EAE").pack(side="left", padx=(0, 8))
    ctk.CTkButton(buttons, text="Projeyi doğrula", command=verify, fg_color="#2D7FF9", hover_color="#4A91FF").pack(side="left", padx=8)
    ctk.CTkButton(buttons, text="Axvord erişim anahtarı", command=create_recovery_code, fg_color="#123A70", hover_color="#1D5EAE").pack(side="left", padx=8)
    ctk.CTkButton(buttons, text="Kapat  ·  Esc", command=panel.destroy, fg_color="#123A70", hover_color="#1D5EAE").pack(side="right")
    ctk.CTkLabel(body, text="Bu alan yalnızca sahip hesabı veya Windows yöneticisi için kullanılabilir.", anchor="w", text_color="#7FA9D8").pack(fill="x", pady=(0, 8))
    return panel


__all__ = [
    "OWNER_ROLE",
    "TRIGGER",
    "authorized_operator",
    "current_identity",
    "current_sid",
    "enroll_recovery_code",
    "ensure_owner",
    "install",
    "is_windows_admin",
    "show_panel",
    "verify_recovery_code",
]
