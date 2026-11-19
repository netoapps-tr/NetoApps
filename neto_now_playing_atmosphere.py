"""Deterministic, local atmosphere cues for the Now Playing screen."""
from __future__ import annotations

import hashlib
import math


PALETTES = (
    ("#2D7FF9", "#7C3AED"),
    ("#06B6D4", "#2563EB"),
    ("#22C55E", "#0EA5E9"),
    ("#F97316", "#DB2777"),
    ("#EAB308", "#7C3AED"),
)


def atmosphere_for(info: dict | None, frame: int = 0) -> dict[str, object]:
    """Return stable colors and a bounded pulse for one media state."""
    info = info if isinstance(info, dict) else {}
    key = f"{info.get('artist', '')}|{info.get('title', '')}".encode("utf-8", "ignore")
    digest = hashlib.sha256(key or b"netops").digest()
    first, second = PALETTES[digest[0] % len(PALETTES)]
    raw_status = str(info.get("playback_status") or "").lower()
    active = any(token in raw_status for token in ("playing", "play", "4", "3"))
    pulse = (math.sin(float(frame) * (0.18 if active else 0.05)) + 1.0) / 2.0

    def blend(left: str, right: str, amount: float) -> str:
        a = tuple(int(left[index:index + 2], 16) for index in (1, 3, 5))
        b = tuple(int(right[index:index + 2], 16) for index in (1, 3, 5))
        return "#" + "".join(f"{round(x + (y - x) * amount):02X}" for x, y in zip(a, b))

    return {
        "primary": first,
        "secondary": second,
        "color": blend(first, second, pulse),
        "pulse": round(0.18 + pulse * (0.20 if active else 0.06), 3),
        "active": active,
    }


__all__ = ["PALETTES", "atmosphere_for"]
