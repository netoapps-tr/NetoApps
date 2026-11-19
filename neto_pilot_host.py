"""Host adapters used by the NetoPilot extension."""
from __future__ import annotations

from typing import Any


def system_status() -> dict[str, Any]:
    try:
        import psutil

        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        return {
            "cpu_percent": float(psutil.cpu_percent(interval=0.0)),
            "memory_percent": float(memory.percent),
            "disk_percent": float(disk.percent),
        }
    except Exception as exc:
        return {"error": f"Sistem durumu okunamadı: {exc}"}


def build_handlers(namespace: dict[str, Any]) -> dict[str, Any]:
    """Build callbacks from existing NetOps functions without shell fallbacks."""
    def launch_program(name: str):
        opener = namespace.get("_neto_agent_uygulama_ac")
        if not callable(opener):
            return {"ok": False, "error": "NetOps program açıcı hazır değil."}
        result = opener(str(name or "").strip())
        return {"ok": result is None, "error": result} if result else {"ok": True}

    def set_volume(value: int | float):
        setter = namespace.get("volume_set_percent") or namespace.get("volume_slider_changed")
        if not callable(setter):
            return {"ok": False, "error": "Ses adaptörü hazır değil."}
        setter(max(0, min(100, float(value))))
        return {"ok": True, "volume": max(0, min(100, float(value)))}

    def move_window(*_args, **_kwargs):
        return {"ok": False, "error": "Pencere taşıma adaptörü bu sürümde etkin değil."}

    return {
        "system_status": system_status,
        "launch_program": launch_program,
        "set_volume": set_volume,
        "move_window": move_window,
    }


__all__ = ["build_handlers", "system_status"]
