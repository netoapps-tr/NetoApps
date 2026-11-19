"""Conservative animation agent for NetOps.

It proposes and validates motion settings but never changes UI content or media labels.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AnimationPlan:
    mode: str = "normal"
    frame_ms: int = 16
    max_parallel_jobs: int = 1
    protect_content_widgets: bool = True


class NetOpsAnimationAgent:
    """Provides bounded motion settings and a content-preservation contract."""

    MODES = {
        "normal": AnimationPlan("normal", 16, 1, True),
        "reduced": AnimationPlan("reduced", 32, 1, True),
        "off": AnimationPlan("off", 0, 0, True),
    }

    def plan(self, mode: str = "normal") -> AnimationPlan:
        return self.MODES.get(str(mode).lower(), self.MODES["normal"])

    def validate_engine(self, project_dir: str | Path) -> dict[str, object]:
        path = Path(project_dir) / "neto_motion_engine_v2.py"
        if not path.is_file():
            return {"ok": False, "errors": ["Animasyon motoru bulunamadı."]}
        source = path.read_text(encoding="utf-8-sig", errors="replace")
        required = ("cancel_prefix", "after_cancel", "winfo_exists")
        errors = [f"Animasyon koruması eksik: {item}" for item in required if item not in source]
        return {"ok": not errors, "errors": errors, "plan": self.plan().__dict__}


__all__ = ["AnimationPlan", "NetOpsAnimationAgent"]
