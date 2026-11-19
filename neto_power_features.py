"""Safe adapters for NetOps power-user features.

This module takes inspiration from mature open-source tools without bundling
their applications or running arbitrary commands. Optional integrations are
detected lazily, while the local features work with the Python standard
library and already-installed optional packages.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any


APP_DATA = Path(
    os.environ.get("LOCALAPPDATA")
    or (Path.home() / "AppData" / "Local")
) / "NetoAssistant" / "power_center"
ACTIVITY_PATH = APP_DATA / "activity.json"
SNIPPETS_PATH = APP_DATA / "snippets.json"
PREFERENCES_PATH = APP_DATA / "preferences.json"


OPTIONAL_APPS: dict[str, dict[str, Any]] = {
    "flow_launcher": {
        "title": "Flow Launcher",
        "commands": ("Flow.Launcher.exe", "flow-launcher"),
        "source": "Flow Launcher",
    },
    "powertoys": {
        "title": "Microsoft PowerToys",
        "commands": ("PowerToys.exe", r"PowerToys\PowerToys.exe"),
        "source": "PowerToys",
    },
    "kde_connect": {
        "title": "KDE Connect",
        "commands": ("kdeconnect-app.exe", "kdeconnect-app"),
        "source": "KDE Connect",
    },
    "localsend": {
        "title": "LocalSend",
        "commands": ("localsend_app.exe", "localsend"),
        "source": "LocalSend",
    },
    "syncthing": {
        "title": "Syncthing",
        "commands": ("syncthing.exe", "syncthing"),
        "source": "Syncthing",
    },
    "espanso": {
        "title": "Espanso",
        "commands": ("espanso.exe", "espanso"),
        "source": "Espanso",
    },
    "obs": {
        "title": "OBS Studio",
        "commands": ("obs64.exe", "obs.exe", "obs"),
        "source": "OBS Studio",
    },
    "keepassxc": {
        "title": "KeePassXC",
        "commands": ("KeePassXC.exe", "keepassxc"),
        "source": "KeePassXC",
    },
    "rustdesk": {
        "title": "RustDesk",
        "commands": ("rustdesk.exe", "rustdesk"),
        "source": "RustDesk",
    },
}


POWER_FEATURES: tuple[dict[str, Any], ...] = (
    {"id": "command_palette", "title": "Komut Paleti", "risk": "low", "mode": "built_in"},
    {"id": "device_hub", "title": "Cihazlar Merkezi", "risk": "medium", "mode": "built_in"},
    {"id": "scenes", "title": "Otomasyon Sahneleri", "risk": "medium", "mode": "built_in"},
    {"id": "screen_capture", "title": "Ekran Yakalama", "risk": "low", "mode": "built_in"},
    {"id": "activity_watch", "title": "Yerel Aktivite Özeti", "risk": "low", "mode": "opt_in"},
    {"id": "snippets", "title": "Metin Şablonları", "risk": "low", "mode": "local"},
    {"id": "sync_manifest", "title": "Senkronizasyon Manifesti", "risk": "low", "mode": "local"},
    {"id": "plugin_guard", "title": "Eklenti Güvenlik Taraması", "risk": "low", "mode": "built_in"},
    {"id": "node_red", "title": "Yerel Akış Motoru", "risk": "medium", "mode": "optional"},
)

_POWER_CENTER_WINDOW: Any = None
_ACTIVITY_WATCHER_ROOT: Any = None
_ACTIVITY_WATCHER_JOB: Any = None


def _ensure_store(path: Path, default: Any) -> Any:
    try:
        if path.is_file():
            value = json.loads(path.read_text(encoding="utf-8"))
            return value
    except (OSError, ValueError, TypeError):
        pass
    return default


def _atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="netops-power-", suffix=".tmp", dir=str(path.parent))
    os.close(fd)
    temporary = Path(name)
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _resolve_command(candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return found
    return None


def integration_status() -> list[dict[str, Any]]:
    """Return optional app status without starting anything."""
    result: list[dict[str, Any]] = []
    for app_id, metadata in OPTIONAL_APPS.items():
        path = _resolve_command(tuple(metadata["commands"]))
        result.append(
            {
                "id": app_id,
                "title": metadata["title"],
                "source": metadata["source"],
                "installed": bool(path),
                "path": path or "",
            }
        )
    return result


def open_optional_app(app_id: str) -> dict[str, Any]:
    """Open one allowlisted optional app; never accepts a raw command."""
    key = str(app_id or "").strip().casefold()
    metadata = OPTIONAL_APPS.get(key)
    if metadata is None:
        return {"ok": False, "error": "Tanımsız dış uygulama."}
    path = _resolve_command(tuple(metadata["commands"]))
    if not path:
        return {"ok": False, "installed": False, "error": f"{metadata['title']} bulunamadı."}
    try:
        subprocess.Popen([path], cwd=str(Path(path).parent), close_fds=True)
    except (OSError, ValueError) as exc:
        return {"ok": False, "installed": True, "error": str(exc)}
    return {"ok": True, "installed": True, "path": path}


def capture_screen(path: str | Path | None = None, *, ocr: bool = False) -> dict[str, Any]:
    """Capture locally; no upload or network operation is performed."""
    destination = Path(path).expanduser() if path else Path.home() / "Desktop" / f"NetOps_SS_{int(time.time())}.png"
    destination.parent.mkdir(parents=True, exist_ok=True)
    image = None
    errors: list[str] = []
    try:
        from PIL import ImageGrab

        image = ImageGrab.grab()
    except Exception as exc:
        errors.append(str(exc))
    if image is None:
        try:
            import pyautogui

            image = pyautogui.screenshot()
        except Exception as exc:
            errors.append(str(exc))
    if image is None:
        return {"ok": False, "error": "Ekran yakalanamadı.", "details": errors}
    try:
        image.save(destination)
    except (OSError, ValueError) as exc:
        return {"ok": False, "error": f"Ekran kaydedilemedi: {exc}"}
    text = ""
    if ocr:
        try:
            import pytesseract

            text = str(pytesseract.image_to_string(image) or "")
        except Exception:
            # OCR is optional and must never make capture fail.
            text = ""
    return {"ok": True, "path": str(destination), "ocr_text": text}


def record_activity(app: str, *, title: str = "", event: str = "focus") -> bool:
    """Store a small local activity record when explicitly enabled."""
    if not activity_enabled():
        return False
    records = _ensure_store(ACTIVITY_PATH, [])
    if not isinstance(records, list):
        records = []
    records.append({"app": str(app)[:160], "title": str(title)[:240], "event": str(event)[:40], "ts": time.time()})
    _atomic_write(ACTIVITY_PATH, records[-2000:])
    return True


def activity_enabled() -> bool:
    preferences = _ensure_store(PREFERENCES_PATH, {})
    if isinstance(preferences, dict) and "activity_enabled" in preferences:
        return bool(preferences.get("activity_enabled"))
    return str(os.environ.get("NETOPS_ACTIVITY_ENABLED", "0")).strip().casefold() in {"1", "true", "on", "yes"}


def set_activity_enabled(enabled: bool) -> bool:
    preferences = _ensure_store(PREFERENCES_PATH, {})
    if not isinstance(preferences, dict):
        preferences = {}
    preferences["activity_enabled"] = bool(enabled)
    _atomic_write(PREFERENCES_PATH, preferences)
    return bool(enabled)


def _foreground_window() -> tuple[str, str]:
    if os.name != "nt":
        return "", ""
    try:
        import ctypes
        import ctypes.wintypes as wintypes

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return "", ""
        title_buffer = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, title_buffer, len(title_buffer))
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        app = ""
        try:
            import psutil

            app = str(psutil.Process(int(pid.value)).name() or "")
        except Exception:
            app = ""
        return app or "Windows", str(title_buffer.value or "")
    except Exception:
        return "", ""


def start_activity_watcher(root, *, interval_ms: int = 4000) -> bool:
    """Start a low-frequency, opt-in local foreground-window sampler."""
    global _ACTIVITY_WATCHER_ROOT, _ACTIVITY_WATCHER_JOB
    if root is None or not hasattr(root, "after"):
        return False
    _ACTIVITY_WATCHER_ROOT = root

    def tick():
        global _ACTIVITY_WATCHER_JOB
        try:
            if not root.winfo_exists():
                _ACTIVITY_WATCHER_JOB = None
                return
        except Exception:
            _ACTIVITY_WATCHER_JOB = None
            return
        if activity_enabled():
            app, title = _foreground_window()
            if app and "netops" not in f"{app} {title}".casefold():
                record_activity(app, title=title)
        try:
            _ACTIVITY_WATCHER_JOB = root.after(max(1000, int(interval_ms)), tick)
        except Exception:
            _ACTIVITY_WATCHER_JOB = None

    try:
        if _ACTIVITY_WATCHER_JOB is None:
            _ACTIVITY_WATCHER_JOB = root.after(1200, tick)
            return True
    except Exception:
        _ACTIVITY_WATCHER_JOB = None
    return False


def stop_activity_watcher() -> None:
    global _ACTIVITY_WATCHER_JOB, _ACTIVITY_WATCHER_ROOT
    if _ACTIVITY_WATCHER_ROOT is not None and _ACTIVITY_WATCHER_JOB is not None:
        try:
            _ACTIVITY_WATCHER_ROOT.after_cancel(_ACTIVITY_WATCHER_JOB)
        except Exception:
            pass
    _ACTIVITY_WATCHER_JOB = None
    _ACTIVITY_WATCHER_ROOT = None


def activity_summary(limit: int = 10) -> list[dict[str, Any]]:
    records = _ensure_store(ACTIVITY_PATH, [])
    if not isinstance(records, list):
        return []
    counts: dict[str, int] = {}
    for item in records:
        if isinstance(item, dict):
            app = str(item.get("app") or "Bilinmeyen")
            counts[app] = counts.get(app, 0) + 1
    return [
        {"app": app, "events": count}
        for app, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0].casefold()))[: max(1, min(50, int(limit)))]
    ]


def save_snippet(trigger: str, replacement: str) -> dict[str, Any]:
    trigger = str(trigger or "").strip()
    replacement = str(replacement or "")
    if not trigger or len(trigger) > 80 or not replacement or len(replacement) > 10000:
        raise ValueError("Şablon tetikleyicisi veya metni geçersiz.")
    snippets = _ensure_store(SNIPPETS_PATH, {})
    if not isinstance(snippets, dict):
        snippets = {}
    snippets[trigger] = replacement
    _atomic_write(SNIPPETS_PATH, snippets)
    return {"trigger": trigger, "replacement": replacement}


def expand_snippet(trigger: str) -> str | None:
    snippets = _ensure_store(SNIPPETS_PATH, {})
    if not isinstance(snippets, dict):
        return None
    value = snippets.get(str(trigger or "").strip())
    return str(value) if value is not None else None


def create_sync_manifest(root: str | Path) -> dict[str, Any]:
    """Create a local, read-only sync manifest without copying files."""
    base = Path(root).expanduser().resolve()
    if not base.is_dir():
        raise ValueError("Senkronizasyon klasörü bulunamadı.")
    files: list[dict[str, Any]] = []
    for path in base.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            relative = path.relative_to(base)
            stat = path.stat()
        except OSError:
            continue
        files.append({"path": relative.as_posix(), "size": stat.st_size, "mtime": stat.st_mtime})
        if len(files) >= 5000:
            break
    return {"root": str(base), "files": files, "created_at": time.time(), "truncated": len(files) >= 5000}


def risk_report() -> list[dict[str, Any]]:
    """Conservative engineering estimate, not a statistical guarantee."""
    return [
        {"feature": item["id"], "risk": item["risk"], "mitigation": "İzin kapısı + bağımsız hata yakalama + test"}
        for item in POWER_FEATURES
    ]


def status_report() -> dict[str, Any]:
    return {
        "features": [dict(item) for item in POWER_FEATURES],
        "integrations": integration_status(),
        "activity_enabled": activity_enabled(),
        "activity": activity_summary(),
    }


def open_power_center(root, namespace: dict[str, Any] | None = None):
    """Open the local feature and integration dashboard without extra deps."""
    global _POWER_CENTER_WINDOW
    try:
        if _POWER_CENTER_WINDOW is not None and _POWER_CENTER_WINDOW.winfo_exists():
            _POWER_CENTER_WINDOW.deiconify()
            _POWER_CENTER_WINDOW.lift()
            _POWER_CENTER_WINDOW.focus_force()
            return _POWER_CENTER_WINDOW
    except Exception:
        _POWER_CENTER_WINDOW = None

    import customtkinter as ctk
    try:
        from temalar import aktif_palet
        palette = dict(aktif_palet)
    except Exception:
        palette = {
            "bg": "#0F1115",
            "sidebar": "#14171C",
            "card": "#1B1F26",
            "entry_bg": "#191D23",
            "entry_border": "#3A4350",
            "accent": "#60CDFF",
            "accent_hover": "#7AD8FF",
            "accent_text": "#07131B",
            "text_main": "#F5F7FA",
            "text_dim": "#B8C0CC",
            "button_fg": "#252A33",
            "button_hover": "#303742",
        }

    window = ctk.CTkToplevel(root)
    _POWER_CENTER_WINDOW = window
    window.title("NetOps Güç Merkezi")
    window.geometry("720x620")
    window.minsize(560, 480)
    window.configure(fg_color=palette["bg"])

    shell = ctk.CTkFrame(window, fg_color=palette["card"], corner_radius=8, border_width=1, border_color=palette["entry_border"])
    shell.pack(fill="both", expand=True, padx=14, pady=14)
    ctk.CTkLabel(shell, text="NetOps Güç Merkezi", font=("Segoe UI Semibold", 22), text_color=palette["text_main"], anchor="w").pack(fill="x", padx=18, pady=(16, 2))
    ctk.CTkLabel(shell, text="Açık kaynak araçlardan ilham alan güvenli yerel yetenekler", font=("Segoe UI", 11), text_color=palette["text_dim"], anchor="w").pack(fill="x", padx=18, pady=(0, 12))

    body = ctk.CTkScrollableFrame(shell, fg_color=palette["bg"], corner_radius=6)
    body.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def notify(title: str, message: str, level: str = "info"):
        callback = namespace.get("neto_toast_goster") if isinstance(namespace, dict) else None
        if callable(callback):
            callback(title, message, level)

    def add_section(title: str):
        ctk.CTkLabel(body, text=title, font=("Segoe UI Semibold", 12), text_color=palette["accent"], anchor="w").pack(fill="x", padx=8, pady=(12, 5))

    def add_row(title: str, subtitle: str, button_text: str = "Aç", command=None, enabled: bool = True):
        row = ctk.CTkFrame(body, fg_color=palette["sidebar"], corner_radius=6, border_width=1, border_color=palette["entry_border"])
        row.pack(fill="x", padx=6, pady=4)
        text_frame = ctk.CTkFrame(row, fg_color="transparent")
        text_frame.pack(side="left", fill="x", expand=True, padx=12, pady=8)
        ctk.CTkLabel(text_frame, text=title, font=("Segoe UI Semibold", 11), text_color=palette["text_main"], anchor="w").pack(fill="x")
        ctk.CTkLabel(text_frame, text=subtitle, font=("Segoe UI", 9), text_color=palette["text_dim"], anchor="w", justify="left", wraplength=460).pack(fill="x")
        ctk.CTkButton(
            row,
            text=button_text,
            width=92,
            height=31,
            corner_radius=6,
            state="normal" if enabled else "disabled",
            fg_color=palette["accent"] if enabled else palette["button_fg"],
            hover_color=palette["accent_hover"] if enabled else palette["button_hover"],
            text_color=palette["accent_text"] if enabled else palette["text_dim"],
            border_width=1,
            border_color=palette["entry_border"],
            command=command or (lambda: None),
        ).pack(side="right", padx=10)

    add_section("NetOps yerel özellikleri")
    add_row("Komut Paleti", "Flow Launcher yaklaşımı: arama, favoriler ve hızlı komutlar.", "Hazır", enabled=False)
    add_row("Cihazlar Merkezi", "KDE Connect yaklaşımı: eşleştirme, bildirim ve medya köprüsü.", "Hazır", enabled=False)
    add_row("Otomasyon Sahneleri", "Home Assistant yaklaşımı: onaylı profil ve işlem zincirleri.", "Hazır", enabled=False)

    def capture_and_notify():
        result = capture_screen()
        notify(
            "Ekran Yakalama",
            str(result.get("path") or result.get("error") or "İşlem tamamlanamadı."),
            "success" if result.get("ok") else "error",
        )

    add_row("Ekran Yakalama", "ShareX yaklaşımı: görüntüyü yalnızca yerel masaüstüne kaydeder.", "Yakala", capture_and_notify)
    def toggle_activity():
        enabled = set_activity_enabled(not activity_enabled())
        notify("Aktivite Takibi", "Yerel takip açıldı." if enabled else "Yerel takip kapatıldı.", "info")

    add_row(
        "Yerel Aktivite",
        "ActivityWatch yaklaşımı; kayıtlar yalnızca bu bilgisayarda tutulur.",
        "Kapat" if activity_enabled() else "Aç",
        toggle_activity,
    )
    add_row("Metin Şablonları", "Espanso yaklaşımı; veriler NetOps yerel klasöründe tutulur.", "Hazır", enabled=False)
    add_row("Senkronizasyon Manifesti", "Syncthing yaklaşımı; ilk aşamada sadece dosya envanteri üretir.", "Hazır", enabled=False)

    add_section("Algılanan açık kaynak uygulamalar")
    for item in integration_status():
        if item["installed"]:
            add_row(item["title"], f"{item['source']} · {item['path']}", "Aç", lambda app_id=item["id"]: open_optional_app(app_id))
        else:
            add_row(item["title"], f"{item['source']} · kurulu değil; NetOps bundan dolayı hata vermez.", "Yok", enabled=False)

    def close():
        global _POWER_CENTER_WINDOW
        _POWER_CENTER_WINDOW = None
        try:
            window.destroy()
        except Exception:
            pass

    window.protocol("WM_DELETE_WINDOW", close)
    window.bind("<Escape>", lambda _event: close())
    window.after(80, window.focus_force)
    return window


__all__ = [
    "POWER_FEATURES",
    "OPTIONAL_APPS",
    "activity_summary",
    "activity_enabled",
    "capture_screen",
    "create_sync_manifest",
    "expand_snippet",
    "integration_status",
    "open_optional_app",
    "open_power_center",
    "record_activity",
    "risk_report",
    "save_snippet",
    "set_activity_enabled",
    "start_activity_watcher",
    "stop_activity_watcher",
    "status_report",
]
