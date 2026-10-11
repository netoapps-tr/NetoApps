"""Built-in NetOps Now Playing driver contract."""
from __future__ import annotations

DRIVER_ID = "now_playing_driver"
DRIVER_VERSION = "10.37.0"

_DEFAULTS = {
    "monitor_active_wait_s": 0.35,
    "monitor_idle_wait_s": 0.55,
    "monitor_error_wait_s": 1.0,
    "ui_pump_ms": 120,
    "visualizer_ms": 33,
    "stable_poll_ms": 500,
}


def health() -> dict:
    return {"id": DRIVER_ID, "version": DRIVER_VERSION, "ok": True, "mode": "user"}


def interval(name: str, default: int | float | None = None):
    value = _DEFAULTS.get(str(name), default)
    if value is None:
        return 0
    if isinstance(value, float):
        return max(0.05, min(5.0, float(value)))
    return max(16, min(5000, int(value)))
