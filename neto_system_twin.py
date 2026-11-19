"""Yerel NetOps Sistem İkizi.

Network erişimi olmadan cihazın o anki kaynaklarını ve çalışan uygulamalarını
özetler. Bu ilk sürüm karar vermez veya işlem yapmaz; yalnızca operasyon
planına güvenilir bir gözlem katmanı sağlar.
"""

from __future__ import annotations

import os
import platform
import time
from typing import Any

try:
    import psutil
except Exception:  # pragma: no cover - optional on minimal installations
    psutil = None


SYSTEM_TWIN_VERSION = "1.0.0"


def _round(value: Any, digits: int = 1) -> float | None:
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def collect_snapshot(process_limit: int = 24) -> dict[str, Any]:
    """Collect a small, local-only view of the current machine."""
    captured_at = time.time()
    snapshot: dict[str, Any] = {
        "version": SYSTEM_TWIN_VERSION,
        "captured_at": captured_at,
        "host": {
            "name": platform.node() or "NetOps cihazı",
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "metrics": {"cpu_percent": None, "memory_percent": None, "disk_percent": None},
        "processes": [],
        "nodes": [],
        "edges": [],
    }
    snapshot["nodes"].append({"id": "host", "type": "host", "label": snapshot["host"]["name"]})
    if psutil is None:
        return snapshot
    try:
        snapshot["metrics"]["cpu_percent"] = _round(psutil.cpu_percent(interval=0.0))
    except Exception:
        pass
    try:
        snapshot["metrics"]["memory_percent"] = _round(psutil.virtual_memory().percent)
    except Exception:
        pass
    try:
        snapshot["metrics"]["disk_percent"] = _round(psutil.disk_usage(os.path.abspath(os.sep)).percent)
    except Exception:
        pass

    processes = []
    try:
        for process in psutil.process_iter(["pid", "name", "status", "memory_percent", "username"]):
            info = process.info
            name = str(info.get("name") or "").strip()
            if not name:
                continue
            item = {
                "pid": int(info.get("pid") or 0),
                "name": name,
                "status": str(info.get("status") or "unknown"),
                "memory_percent": _round(info.get("memory_percent")),
                "user": str(info.get("username") or ""),
            }
            processes.append(item)
    except Exception:
        processes = []
    processes.sort(key=lambda item: float(item.get("memory_percent") or 0), reverse=True)
    snapshot["processes"] = processes[: max(1, min(100, int(process_limit)))]
    for item in snapshot["processes"]:
        node_id = f"process:{item['pid']}"
        snapshot["nodes"].append({"id": node_id, "type": "process", "label": item["name"], "pid": item["pid"]})
        snapshot["edges"].append({"from": node_id, "to": "host", "type": "runs_on"})
    return snapshot


def impact_report(action: str, snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    """Find running processes that a plain-language action appears to target."""
    text = str(action or "").casefold().strip()
    current = snapshot or collect_snapshot()
    closing = any(word in text for word in ("kapat", "sonlandır", "sonlandir", "bitir", "durdur"))
    if not closing:
        return {"action": str(action or ""), "matches": [], "risk": "safe", "requires_confirmation": False}
    matches = []
    for process in current.get("processes") or []:
        name = str(process.get("name") or "")
        stem = name.rsplit(".", 1)[0].casefold()
        if stem and stem in text:
            matches.append(process)
    risk = "warning" if matches else "unknown"
    return {
        "action": str(action or ""),
        "matches": matches,
        "risk": risk,
        "requires_confirmation": bool(matches),
    }


def format_snapshot(snapshot: dict[str, Any]) -> str:
    """Create a compact Turkish report suitable for a chat bubble."""
    host = snapshot.get("host") or {}
    metrics = snapshot.get("metrics") or {}
    processes = snapshot.get("processes") or []
    cpu = metrics.get("cpu_percent")
    memory = metrics.get("memory_percent")
    disk = metrics.get("disk_percent")
    lines = [
        f"NetOps Sistem İkizi · {host.get('name') or 'cihaz'}",
        f"Platform: {host.get('system') or 'bilinmiyor'} {host.get('release') or ''}".strip(),
        f"CPU: %{cpu if cpu is not None else '?'} · RAM: %{memory if memory is not None else '?'} · Disk: %{disk if disk is not None else '?'}",
        f"Haritada {len(snapshot.get('nodes') or [])} düğüm, {len(snapshot.get('edges') or [])} bağlantı var.",
    ]
    if processes:
        names = ", ".join(str(item.get("name")) for item in processes[:5])
        lines.append(f"Öne çıkan süreçler: {names}")
    else:
        lines.append("Süreç envanteri bu cihazda kullanılamıyor.")
    return "\n".join(lines)


__all__ = ["SYSTEM_TWIN_VERSION", "collect_snapshot", "format_snapshot", "impact_report"]
