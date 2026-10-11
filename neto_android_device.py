"""NetOps Android USB Device Doctor.

Local-only ADB diagnostics and a small set of non-destructive convenience
commands. Wi-Fi/TCP ADB, root, flashing, bootloader and wipe operations are not
used.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional, Tuple

WARRANTY_SAFE_MODE = True
USB_ONLY_MODE = True
_FORBIDDEN = (
    "fastboot", "oem unlock", "flashing unlock", "flash", "root", "magisk",
    "factory reset", "wipe data", "recovery --wipe_data", "pm uninstall",
)
_WATCH_RUNNING = False
_WATCH_SEEN: set[str] = set()
_ANDROID_DEVICE_WINDOW = None
_LAST_ANDROID_DEVICE_AUTO_OPEN = 0.0
_ANDROID_DEVICE_AUTO_OPEN_COOLDOWN = 45.0

_APP_PACKAGES = {
    "youtube": ["com.google.android.youtube"],
    "youtube music": ["com.google.android.apps.youtube.music"],
    "spotify": ["com.spotify.music"],
    "discord": ["com.discord"],
    "chrome": ["com.android.chrome", "com.chrome.beta"],
    "whatsapp": ["com.whatsapp", "com.whatsapp.w4b"],
    "telegram": ["org.telegram.messenger"],
    "instagram": ["com.instagram.android"],
    "tiktok": ["com.zhiliaoapp.musically"],
    "gmail": ["com.google.android.gm"],
    "play store": ["com.android.vending"],
    "ayarlar": ["com.android.settings"],
    "settings": ["com.android.settings"],
}

_NETOPS_AGENT_PACKAGE = "com.example.neto_flutter"
_NETOPS_AGENT_ACTIVITY = "com.example.neto_flutter/.MainActivity"


def local_app_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "NetoAssistant"
    return Path.home() / ".neto_assistant"


def report_dir() -> Path:
    path = local_app_dir() / "android_device_reports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def hidden_flags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def adb_path() -> str:
    found = shutil.which("adb")
    if found:
        return found
    candidates: List[str] = []
    if os.name == "nt":
        candidates.extend(
            [
                os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
                os.path.expandvars(r"%USERPROFILE%\AppData\Local\Android\Sdk\platform-tools\adb.exe"),
                str(Path.cwd() / "platform-tools" / "adb.exe"),
                str(Path.cwd() / "adb.exe"),
                str(Path(__file__).resolve().parent / "platform-tools" / "adb.exe"),
                str(Path(__file__).resolve().parent / "adb.exe"),
            ]
        )
    else:
        candidates.extend(["/usr/bin/adb", "/usr/local/bin/adb", str(Path.cwd() / "platform-tools" / "adb")])
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return ""


def adb_available() -> bool:
    return bool(adb_path())


def command_is_safe(args: List[str]) -> Tuple[bool, str]:
    joined = " ".join(str(value).casefold() for value in args)
    for forbidden in _FORBIDDEN:
        if forbidden in joined:
            return False, f"Güvenlik nedeniyle engellendi: {forbidden}"
    return True, "safe"


def run_cmd(args: List[str], timeout: int = 12, binary: bool = False) -> Dict[str, Any]:
    allowed, reason = command_is_safe(args)
    if not allowed:
        return {"ok": False, "returncode": -999, "stdout": b"" if binary else "", "stderr": reason, "args": args}
    if not args or not args[0]:
        return {"ok": False, "returncode": -1, "stdout": b"" if binary else "", "stderr": "ADB bulunamadı. Android platform-tools kur veya adb.exe dosyasını NetOps klasörüne koy.", "args": args}
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            timeout=timeout,
            text=not binary,
            encoding=None if binary else "utf-8",
            errors=None if binary else "replace",
            creationflags=hidden_flags(),
        )
        return {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "stdout": completed.stdout if completed.stdout is not None else (b"" if binary else ""),
            "stderr": completed.stderr if completed.stderr is not None else (b"" if binary else ""),
            "args": args,
        }
    except FileNotFoundError:
        return {"ok": False, "returncode": -1, "stdout": b"" if binary else "", "stderr": "ADB bulunamadı.", "args": args}
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": -2, "stdout": b"" if binary else "", "stderr": "ADB komutu zaman aşımına uğradı.", "args": args}
    except Exception as exc:
        return {"ok": False, "returncode": -3, "stdout": b"" if binary else "", "stderr": str(exc), "args": args}


def adb(args: List[str], timeout: int = 12, binary: bool = False) -> Dict[str, Any]:
    path = adb_path()
    return run_cmd(([path] if path else [""]) + list(args), timeout=timeout, binary=binary)


def adb_device(serial: str, args: List[str], timeout: int = 12, binary: bool = False) -> Dict[str, Any]:
    serial = str(serial or "").strip()
    if not serial:
        return {"ok": False, "returncode": -4, "stdout": b"" if binary else "", "stderr": "USB cihaz seçilmedi.", "args": []}
    return adb(["-s", serial] + list(args), timeout=timeout, binary=binary)


def adb_shell(serial: str, command: str, timeout: int = 12) -> Dict[str, Any]:
    return adb_device(serial, ["shell", command], timeout=timeout)


def _server_url_port(server_url: str, fallback: int = 8765) -> int:
    raw = str(server_url or "").strip()
    if not raw:
        return int(fallback)
    try:
        parsed = urlparse(raw)
        if parsed.port:
            return int(parsed.port)
    except Exception:
        pass
    match = re.search(r":(\d+)(?:/|$)", raw)
    if match:
        try:
          return int(match.group(1))
        except Exception:
          return int(fallback)
    return int(fallback)


def _server_url_needs_reverse(server_url: str) -> bool:
    raw = str(server_url or "").strip().casefold()
    if not raw:
        return True
    try:
        parsed = urlparse(raw)
        host = str(parsed.hostname or "").strip().casefold()
    except Exception:
        host = ""
    if host in {"", "127.0.0.1", "localhost", "::1"}:
        return True
    return raw.startswith("ws://127.0.0.1") or raw.startswith("wss://127.0.0.1") or raw.startswith("ws://localhost") or raw.startswith("wss://localhost")


def _shell_quote_value(value: Any) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").replace("\t", " ").strip()
    escaped = (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("$", "\\$")
        .replace("`", "\\`")
    )
    return f'"{escaped}"'


def _is_usb_serial(serial: str, detail: str = "") -> bool:
    value = str(serial or "").strip().casefold()
    info = str(detail or "").casefold()
    if not value or ":" in value or value.startswith("emulator-"):
        return False
    if "tcpip" in info:
        return False
    return True


def parse_adb_devices(output: str) -> List[Dict[str, str]]:
    devices: List[Dict[str, str]] = []
    for raw_line in str(output or "").splitlines():
        line = raw_line.strip()
        if not line or line.casefold().startswith("list of devices"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        detail = " ".join(parts[2:])
        devices.append(
            {
                "serial": serial,
                "state": state,
                "detail": detail,
                "usb_only": str(_is_usb_serial(serial, detail)),
            }
        )
    return devices


def list_usb_devices() -> Dict[str, Any]:
    if not adb_available():
        return {"ok": False, "adb": "", "all_devices": [], "usb_devices": [], "error": "ADB bulunamadı. Android platform-tools kur veya adb.exe dosyasını NetOps klasörüne koy."}
    adb(["start-server"], timeout=8)
    result = adb(["devices", "-l"], timeout=10)
    devices = parse_adb_devices(str(result.get("stdout") or ""))
    usb_devices = [item for item in devices if item.get("usb_only") == "True"]
    return {
        "ok": bool(result.get("ok")),
        "adb": adb_path(),
        "all_devices": devices,
        "usb_devices": usb_devices,
        "error": str(result.get("stderr") or ""),
    }


def _first_authorized_device() -> Tuple[str, str]:
    result = list_usb_devices()
    devices = result.get("usb_devices") or []
    for device in devices:
        if device.get("state") == "device":
            return str(device.get("serial") or ""), ""
    if devices:
        state = str(devices[0].get("state") or "unknown")
        return "", f"USB cihaz bulundu fakat ADB durumu '{state}'. Telefonda USB hata ayıklama iznini onayla."
    return "", str(result.get("error") or "USB ile bağlı Android cihaz bulunamadı.")


def _getprop(serial: str, prop: str) -> str:
    result = adb_shell(serial, f"getprop {prop}", timeout=8)
    return str(result.get("stdout") or "").strip()


def safe_android_summary(serial: str) -> str:
    serial = str(serial or "").strip()
    if not serial:
        return "Android cihaz seçilmedi."
    brand = _getprop(serial, "ro.product.manufacturer") or "Bilinmiyor"
    model = _getprop(serial, "ro.product.model") or "Bilinmiyor"
    version = _getprop(serial, "ro.build.version.release") or "?"
    sdk = _getprop(serial, "ro.build.version.sdk") or "?"
    battery = adb_shell(serial, "dumpsys battery", timeout=10)
    level_match = re.search(r"level:\s*(\d+)", str(battery.get("stdout") or ""))
    battery_text = f"%{level_match.group(1)}" if level_match else "Bilinmiyor"
    return f"{brand} {model} | Android {version} (SDK {sdk}) | Pil {battery_text} | USB ADB"


def diagnose_device(serial: str) -> Dict[str, Any]:
    summary = safe_android_summary(serial)
    storage = adb_shell(serial, "df -h /data", timeout=10)
    root_state = detect_root_state(serial)
    warnings: List[str] = []
    for line in str(storage.get("stdout") or "").splitlines():
        match = re.search(r"(\d+)%", line)
        if match and int(match.group(1)) >= 90:
            warnings.append(f"Depolama doluluk oranı yüksek: %{match.group(1)}")
    return {
        "ok": bool(serial),
        "serial": serial,
        "summary": summary,
        "storage": str(storage.get("stdout") or storage.get("stderr") or ""),
        "root": root_state,
        "warnings": warnings,
    }


def detect_root_state(serial: str) -> Dict[str, Any]:
    probe = adb_shell(serial, "su -c id", timeout=12)
    probe_output = str(probe.get("stdout") or probe.get("stderr") or "")
    rooted = bool(probe.get("ok")) and "uid=0(root)" in probe_output
    detail = probe_output.strip()

    if not rooted:
        fallback = adb_shell(serial, "id", timeout=8)
        fallback_output = str(fallback.get("stdout") or fallback.get("stderr") or "")
        if not detail:
            detail = fallback_output.strip()
        elif fallback_output.strip() and fallback_output.strip() not in detail:
            detail = f"{detail} | {fallback_output.strip()}"
        rooted = rooted or ("uid=0(root)" in fallback_output)
        ok = bool(probe.get("ok") or fallback.get("ok"))
    else:
        ok = bool(probe.get("ok"))

    return {"ok": ok, "rooted": rooted, "detail": detail or "Root probe failed"}


def collect_crash_log(serial: str, lines: int = 120) -> Dict[str, Any]:
    lines = max(20, min(500, int(lines)))
    result = adb_device(serial, ["logcat", "-d", "-t", str(lines)], timeout=15)
    log = str(result.get("stdout") or result.get("stderr") or "")
    signals = ("FATAL EXCEPTION", "AndroidRuntime", "ANR in ", "native crash", "Fatal signal")
    detected = any(signal.casefold() in log.casefold() for signal in signals)
    return {"ok": bool(result.get("ok")), "detected": detected, "log": log, "serial": serial}


def take_screenshot(serial: str) -> Dict[str, Any]:
    result = adb_device(serial, ["exec-out", "screencap", "-p"], timeout=15, binary=True)
    data = result.get("stdout") if isinstance(result.get("stdout"), (bytes, bytearray)) else b""
    if not result.get("ok") or not data:
        return {"ok": False, "error": str(result.get("stderr") or "Ekran görüntüsü alınamadı.")}
    target = report_dir() / f"android_screenshot_{time.strftime('%Y%m%d_%H%M%S')}.png"
    target.write_bytes(bytes(data))
    return {"ok": True, "path": str(target), "message": f"Ekran görüntüsü kaydedildi: {target}"}


def _installed_packages(serial: str) -> set[str]:
    result = adb_shell(serial, "pm list packages", timeout=18)
    return {line.split(":", 1)[-1].strip() for line in str(result.get("stdout") or "").splitlines() if line.strip()}


def open_android_app(serial: str, app_name: str) -> Dict[str, Any]:
    key = str(app_name or "").strip().casefold()
    candidates = _APP_PACKAGES.get(key, [])
    if not candidates:
        # Explicit package names are allowed when syntactically valid.
        if re.fullmatch(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+", key):
            candidates = [key]
        else:
            return {"ok": False, "error": f"Uygulama eşlemesi bulunamadı: {app_name}"}
    installed = _installed_packages(serial)
    package = next((value for value in candidates if value in installed), "")
    if not package:
        return {"ok": False, "error": f"Uygulama telefonda bulunamadı: {app_name}"}
    result = adb_shell(serial, f"monkey -p {package} -c android.intent.category.LAUNCHER 1", timeout=12)
    return {"ok": bool(result.get("ok")), "package": package, "message": f"{app_name} açıldı." if result.get("ok") else str(result.get("stderr") or result.get("stdout") or "Açılamadı.")}


def launch_netops_agent(serial: str, server_url: str, pairing_code: str) -> Dict[str, Any]:
    serial = str(serial or "").strip()
    server_url = str(server_url or "").strip() or "ws://127.0.0.1:8765"
    pairing_code = str(pairing_code or "").strip()
    if not serial:
        return {"ok": False, "error": "USB cihaz seçilmedi."}
    if not pairing_code:
        return {"ok": False, "error": "Pairing kodu boş."}

    stop_result = adb_shell(serial, f"am force-stop {_NETOPS_AGENT_PACKAGE}", timeout=8)
    reverse_result: Dict[str, Any] = {"ok": True, "skipped": True}
    if _server_url_needs_reverse(server_url):
        port = _server_url_port(server_url, fallback=8765)
        adb_device(serial, ["reverse", "--remove", f"tcp:{port}"], timeout=8)
        reverse_result = adb_device(serial, ["reverse", f"tcp:{port}", f"tcp:{port}"], timeout=10)
    start_command = (
        f"am start -n {_NETOPS_AGENT_ACTIVITY} "
        f"-a android.intent.action.MAIN -c android.intent.category.LAUNCHER "
        f"--es server_url {_shell_quote_value(server_url)} "
        f"--es pairing_code {_shell_quote_value(pairing_code)}"
    )
    start_result = adb_shell(serial, start_command, timeout=15)
    ok = bool(start_result.get("ok"))
    if ok:
        message = "NETOPS Agent tablete gonderildi."
    else:
        message = str(start_result.get("stderr") or start_result.get("stdout") or "NETOPS Agent acilamadi.")
    return {
        "ok": ok,
        "serial": serial,
        "server_url": server_url,
        "pairing_code": pairing_code,
        "reverse": reverse_result,
        "stop": stop_result,
        "start": start_result,
        "message": message,
    }


def is_android_command(text: Any) -> bool:
    value = str(text or "").casefold()
    markers = ("telefon", "android", "adb", "usb cihaz", "telefonda", "telefonun")
    return any(marker in value for marker in markers)


def handle_assistant_android_command(text: Any) -> str:
    value = str(text or "").strip()
    serial, error = _first_authorized_device()
    if not serial:
        return "📱 " + (error or "USB Android cihaz bulunamadı.")
    normalized = value.casefold()
    if "ekran görünt" in normalized or "screenshot" in normalized:
        result = take_screenshot(serial)
        return "📱 " + str(result.get("message") or result.get("error"))
    if "kamera" in normalized or "camera" in normalized:
        result = adb_shell(serial, "am start -a android.media.action.STILL_IMAGE_CAMERA", timeout=10)
        return "📱 Kamera açıldı." if result.get("ok") else "📱 Kamera açılamadı: " + str(result.get("stderr") or result.get("stdout"))
    if "ayarlar" in normalized or "settings" in normalized:
        result = adb_shell(serial, "am start -a android.settings.SETTINGS", timeout=10)
        return "📱 Ayarlar açıldı." if result.get("ok") else "📱 Ayarlar açılamadı."
    if any(word in normalized for word in ("sesi aç", "ses yükselt", "volume up")):
        adb_shell(serial, "input keyevent 24", timeout=8)
        return "📱 Telefon sesi yükseltildi."
    if any(word in normalized for word in ("sesi kıs", "ses azalt", "volume down")):
        adb_shell(serial, "input keyevent 25", timeout=8)
        return "📱 Telefon sesi azaltıldı."
    if any(word in normalized for word in ("sessize", "sustur", "mute")):
        adb_shell(serial, "input keyevent 164", timeout=8)
        return "📱 Telefon sessize alındı."
    for app_name in sorted(_APP_PACKAGES, key=len, reverse=True):
        if app_name in normalized and any(word in normalized for word in ("aç", "ac", "open")):
            result = open_android_app(serial, app_name)
            return "📱 " + str(result.get("message") or result.get("error"))
    if any(word in normalized for word in ("tara", "durum", "bilgi", "özet", "ozet")):
        return "📱 " + safe_android_summary(serial)
    return "📱 Komut anlaşılmadı. Örnek: Telefon kamera aç, Telefon ekran görüntüsü al, Telefonda Discord aç."


def start_android_crash_watch(on_crash=None, interval: int = 8) -> Dict[str, Any]:
    global _WATCH_RUNNING, _WATCH_SEEN
    if _WATCH_RUNNING:
        return {"ok": True, "message": "Android crash watcher already running."}
    if not adb_available():
        return {"ok": False, "message": "ADB bulunamadığı için Android izleyicisi başlatılmadı."}
    _WATCH_RUNNING = True
    _WATCH_SEEN = set()

    def worker() -> None:
        global _WATCH_RUNNING
        baseline_done = False
        while _WATCH_RUNNING:
            try:
                devices = [item for item in (list_usb_devices().get("usb_devices") or []) if item.get("state") == "device"]
                for device in devices[:2]:
                    serial = str(device.get("serial") or "")
                    crash = collect_crash_log(serial, lines=120)
                    log = str(crash.get("log") or "")
                    if not crash.get("detected") or not log.strip():
                        continue
                    signature = hashlib.sha256(log[-4000:].encode("utf-8", "replace")).hexdigest()
                    if not baseline_done:
                        _WATCH_SEEN.add(signature)
                        continue
                    if signature in _WATCH_SEEN:
                        continue
                    _WATCH_SEEN.add(signature)
                    if callable(on_crash):
                        on_crash(serial, log)
                baseline_done = True
            except Exception:
                pass
            time.sleep(max(5, int(interval)))

    threading.Thread(target=worker, name="NetoAndroidCrashWatch", daemon=True).start()
    return {"ok": True, "message": "Android crash watcher started."}


def stop_android_crash_watch() -> Dict[str, Any]:
    global _WATCH_RUNNING
    _WATCH_RUNNING = False
    return {"ok": True, "message": "Android crash watcher stopped."}


def android_device_doctor_ac(parent=None, T=None, palette=None, say_callback=None, crash_alert_log=None):
    global _ANDROID_DEVICE_WINDOW, _LAST_ANDROID_DEVICE_AUTO_OPEN
    import customtkinter as ctk

    colors = palette or {}
    background = colors.get("bg", "#0F0F14")
    card = colors.get("card", "#181820")
    text_main = colors.get("text_main", "#FFFFFF")
    text_dim = colors.get("text_dim", "#9CA3AF")
    accent = colors.get("neon", "#22C55E")

    now = time.monotonic()
    if _ANDROID_DEVICE_WINDOW is not None:
        try:
            if _ANDROID_DEVICE_WINDOW.winfo_exists():
                if crash_alert_log:
                    _LAST_ANDROID_DEVICE_AUTO_OPEN = now
                _ANDROID_DEVICE_WINDOW.deiconify()
                _ANDROID_DEVICE_WINDOW.lift()
                _ANDROID_DEVICE_WINDOW.focus_force()
                return _ANDROID_DEVICE_WINDOW
        except Exception:
            _ANDROID_DEVICE_WINDOW = None

    if crash_alert_log and (now - _LAST_ANDROID_DEVICE_AUTO_OPEN) < _ANDROID_DEVICE_AUTO_OPEN_COOLDOWN:
        return _ANDROID_DEVICE_WINDOW

    window = ctk.CTkToplevel(parent) if parent is not None else ctk.CTkToplevel()
    _ANDROID_DEVICE_WINDOW = window
    if crash_alert_log:
        _LAST_ANDROID_DEVICE_AUTO_OPEN = now
    window.title("Android USB Device Doctor")
    window.geometry("760x620")
    window.configure(fg_color=background)
    try:
        window.transient(parent)
    except Exception:
        pass

    ctk.CTkLabel(window, text="Android USB Device Doctor", font=("Segoe UI Semibold", 24), text_color=text_main).pack(pady=(18, 4))
    ctk.CTkLabel(
        window,
        text="Yalnızca USB • Yerel çalışma • Root/flash/reset yok",
        font=("Segoe UI", 12),
        text_color=text_dim,
    ).pack(pady=(0, 12))

    status = ctk.CTkLabel(window, text="", text_color=text_dim, font=("Segoe UI", 11), wraplength=700)
    status.pack(fill="x", padx=20, pady=(0, 8))
    output = ctk.CTkTextbox(window, fg_color=card, text_color=text_main, font=("Consolas", 11), wrap="word")
    output.pack(fill="both", expand=True, padx=20, pady=(0, 12))
    actions = ctk.CTkFrame(window, fg_color="transparent")
    actions.pack(fill="x", padx=20, pady=(0, 18))
    state = {"serial": ""}

    def set_output(value: str) -> None:
        output.delete("1.0", "end")
        output.insert("1.0", str(value))

    def close() -> None:
        global _ANDROID_DEVICE_WINDOW
        try:
            if _ANDROID_DEVICE_WINDOW is window:
                _ANDROID_DEVICE_WINDOW = None
        except Exception:
            _ANDROID_DEVICE_WINDOW = None
        try:
            window.destroy()
        except Exception:
            pass

    def refresh() -> None:
        listed = list_usb_devices()
        devices = listed.get("usb_devices") or []
        authorized = [item for item in devices if item.get("state") == "device"]
        if not authorized:
            state["serial"] = ""
            message = str(listed.get("error") or "Yetkili USB Android cihaz bulunamadı.")
            status.configure(text=message)
            set_output(message)
            return
        state["serial"] = str(authorized[0].get("serial") or "")
        report = diagnose_device(state["serial"])
        status.configure(text=report.get("summary"))
        lines = [str(report.get("summary") or ""), "", "Depolama:", str(report.get("storage") or "")]
        warnings = report.get("warnings") or []
        if warnings:
            lines.extend(["", "Uyarılar:", *["- " + str(item) for item in warnings]])
        if crash_alert_log:
            lines.extend(["", "Yakalanan çökme kaydı:", str(crash_alert_log)])
        set_output("\n".join(lines))

    def screenshot() -> None:
        serial = state.get("serial")
        result = take_screenshot(serial) if serial else {"ok": False, "error": "Cihaz seçilmedi."}
        status.configure(text=str(result.get("message") or result.get("error")))

    def crash_log() -> None:
        serial = state.get("serial")
        if not serial:
            set_output("Cihaz seçilmedi.")
            return
        result = collect_crash_log(serial, lines=250)
        set_output(str(result.get("log") or "Çökme kaydı bulunamadı."))

    ctk.CTkButton(actions, text="Yenile", width=110, fg_color=accent, command=refresh).pack(side="left")
    ctk.CTkButton(actions, text="Ekran Görüntüsü", width=145, command=screenshot).pack(side="left", padx=8)
    ctk.CTkButton(actions, text="Crash Log", width=110, command=crash_log).pack(side="left")
    try:
        window.protocol("WM_DELETE_WINDOW", close)
    except Exception:
        pass
    ctk.CTkButton(actions, text="Kapat", width=100, command=close).pack(side="right")
    window.after(80, refresh)
    return window
