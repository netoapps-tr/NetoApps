"""Built-in NetOps visual driver contract."""
from __future__ import annotations

import os

DRIVER_ID = "visual_driver"
DRIVER_VERSION = "10.37.0"


def health() -> dict:
    return {"id": DRIVER_ID, "version": DRIVER_VERSION, "ok": True, "mode": "user"}


def frame_ms(default: int = 16) -> int:
    try:
        value = int(os.environ.get("NETO_VISUAL_FRAME_MS", default))
    except Exception:
        value = default
    return max(16, min(50, value))


def duration_ms(value: int, minimum: int = 55, maximum: int = 1800) -> int:
    try:
        number = int(value)
    except Exception:
        number = minimum
    return max(minimum, min(maximum, number))
