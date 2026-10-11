"""Optional Arduino UNO/CH340 serial detector for NetOps."""
from __future__ import annotations

import json
import threading
from typing import Any, Callable

try:
    import serial
    from serial.tools import list_ports
except Exception:
    serial = None
    list_ports = None

_stop = threading.Event()
_thread: threading.Thread | None = None
_last_port = ""


def find_uno_port() -> str:
    if list_ports is None:
        return ""
    try:
        ports = list(list_ports.comports())
    except Exception:
        return ""
    for port in ports:
        vid = str(getattr(port, "vid", "") or "").lower().replace("0x", "")
        text = f"{getattr(port, 'description', '')} {getattr(port, 'manufacturer', '')}".lower()
        if vid == "1a86" or "ch340" in text or "ch341" in text:
            return str(port.device)
    return ""


def _watch(callback: Callable[[dict[str, Any]], None], logger: Callable[[str], None]) -> None:
    global _last_port
    previous_presence: bool | None = None
    while not _stop.wait(0.0):
        port = find_uno_port()
        if port != _last_port:
            _last_port = port
            previous_presence = None
            event = {"type": "arduino", "connected": bool(port), "port": port}
            try:
                callback(event)
            except Exception as exc:
                logger(f"[ARDUINO] bildirim hatası: {exc}")
            if port:
                logger(f"[ARDUINO] UNO/CH340 algılandı: {port}")
            else:
                logger("[ARDUINO] UNO/CH340 bağlantısı kesildi.")
        if port and serial is not None:
            try:
                with serial.Serial(port, 115200, timeout=0.35) as device:
                    deadline = __import__("time").monotonic() + 1.6
                    while __import__("time").monotonic() < deadline and not _stop.is_set():
                        line = device.readline().decode("utf-8", errors="ignore").strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            distance = float(data.get("distance_cm"))
                            presence = bool(data.get("presence"))
                        except Exception:
                            continue
                        if previous_presence is None or presence != previous_presence:
                            previous_presence = presence
                            callback({"type": "presence", "presence": presence, "distance_cm": distance, "port": port})
            except Exception:
                pass
        if _stop.wait(2.0):
            break


def start(callback: Callable[[dict[str, Any]], None], logger: Callable[[str], None] = print) -> bool:
    global _thread
    if serial is None or list_ports is None:
        logger("[ARDUINO] pyserial bulunamadı.")
        return False
    if _thread and _thread.is_alive():
        return True
    _stop.clear()
    _thread = threading.Thread(target=_watch, args=(callback, logger), daemon=True, name="NetOpsArduinoWatcher")
    _thread.start()
    return True


def stop() -> None:
    _stop.set()
