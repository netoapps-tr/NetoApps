"""Small, dependency-free task planning layer for NetOps.

The planner deliberately previews multi-step requests before execution. It does
not guess permissions or run commands by itself; the existing command router
remains the only execution boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


_STEP_SEPARATOR = re.compile(
    r"\s*;\s*"
    r"|\s*,\s*(?:ve\s+)?(?:sonra|ardından|ardindan)\s*"
    r"|\s+(?:(?:ve|daha)\s+)?(?:sonra|ardından|ardindan)\s+",
    flags=re.IGNORECASE,
)

_DESTRUCTIVE_MARKERS = (
    "sil",
    "kaldır",
    "kaldir",
    "format",
    "kapat",
    "durdur",
    "yeniden başlat",
    "yeniden baslat",
    "restart",
    "shutdown",
    "kur",
    "yükle",
    "yukle",
    "geri al",
    "delete",
)

_HARD_DESTRUCTIVE_MARKERS = tuple(marker for marker in _DESTRUCTIVE_MARKERS if marker not in {"durdur", "kapat"})

_MEDIA_MARKERS = (
    "şark",
    "sark",
    "müz",
    "muz",
    "now playing",
    "spotify",
    "youtube music",
)

_REMOTE_MARKERS = (
    "uzaktan",
    "remote",
    "adb",
    "termux",
    "cihazına",
    "cihazina",
    "telefonu",
)


@dataclass(frozen=True)
class PlanStep:
    """One human-readable action in a task plan."""

    index: int
    text: str
    category: str
    risk_level: str = "düşük"
    requires_confirmation: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "text": self.text,
            "category": self.category,
            "risk_level": self.risk_level,
            "requires_confirmation": self.requires_confirmation,
        }


@dataclass(frozen=True)
class TaskPlan:
    """A previewable multi-step request."""

    original: str
    steps: tuple[PlanStep, ...]
    risk_level: str
    requires_confirmation: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "original": self.original,
            "risk_level": self.risk_level,
            "requires_confirmation": self.requires_confirmation,
            "steps": [step.as_dict() for step in self.steps],
        }


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip(" ,;")


def _category(text: str) -> str:
    normalized = text.casefold()
    if any(marker in normalized for marker in ("telefon", "android", "adb", "termux", "cihaz")):
        return "Cihaz"
    if any(marker in normalized for marker in ("ram", "cpu", "gpu", "sistem durumu", "kaynak")):
        return "Sistem"
    if any(marker in normalized for marker in ("şark", "sark", "müz", "muz", "now playing", "çal", "cal", "durdur")):
        return "Now Playing"
    if any(marker in normalized for marker in ("hava", "saat", "tarih", "internet")):
        return "Güncel bilgi"
    if any(marker in normalized for marker in ("dosya", "pdf", "not", "kaydet")):
        return "Dosya"
    return "Genel"


def _step_risk(text: str) -> tuple[str, bool]:
    normalized = text.casefold()
    is_media_step = any(marker in normalized for marker in _MEDIA_MARKERS)
    if is_media_step and not any(marker in normalized for marker in _HARD_DESTRUCTIVE_MARKERS):
        return "düşük", False
    if any(marker in normalized for marker in _DESTRUCTIVE_MARKERS):
        return "yüksek", True
    if any(marker in normalized for marker in _REMOTE_MARKERS):
        return "orta", True
    return "düşük", False


def _split_steps(message: Any) -> list[str]:
    text = _clean(message)
    if not text:
        return []
    pieces = [_clean(piece) for piece in _STEP_SEPARATOR.split(text)]
    return [re.sub(r"^\s*(?:\d+\s*[.)]|[-*])\s*", "", piece) for piece in pieces if piece]


def build_task_plan(message: Any) -> TaskPlan | None:
    """Return a plan only when the input clearly contains multiple steps."""

    original = _clean(message)
    pieces = _split_steps(original)
    if len(pieces) < 2:
        return None

    steps: list[PlanStep] = []
    for index, piece in enumerate(pieces, start=1):
        risk_level, requires_confirmation = _step_risk(piece)
        steps.append(
            PlanStep(
                index=index,
                text=piece,
                category=_category(piece),
                risk_level=risk_level,
                requires_confirmation=requires_confirmation,
            )
        )

    if any(step.risk_level == "yüksek" for step in steps):
        risk_level = "yüksek"
    elif any(step.risk_level == "orta" for step in steps):
        risk_level = "orta"
    else:
        risk_level = "düşük"
    return TaskPlan(original=original, steps=tuple(steps), risk_level=risk_level)


def format_task_plan(plan: TaskPlan, *, can_execute: bool) -> str:
    """Render a compact Turkish preview suitable for the chat transcript."""

    lines = ["Görev planı hazırlandı:"]
    for step in plan.steps:
        marker = "onay gerekli" if step.requires_confirmation else "hazır"
        lines.append(f"{step.index}. {step.category}: {step.text} ({marker})")
    lines.append(f"Risk seviyesi: {plan.risk_level}")
    if can_execute:
        lines.append('Çalıştırmak için "onayla", vazgeçmek için "iptal" yaz.')
    else:
        lines.append("Yürütücü bağlı olmadığı için plan henüz çalıştırılmadı.")
    return "\n".join(lines)


def is_confirmation(message: Any) -> bool:
    return bool(re.fullmatch(r"\s*(?:onayla|uygula|başlat|baslat|evet)\s*[.!]?\s*", str(message or ""), flags=re.IGNORECASE))


def is_cancellation(message: Any) -> bool:
    return bool(re.fullmatch(r"\s*(?:iptal|vazgeç|vazgec|hayır|hayir)\s*[.!]?\s*", str(message or ""), flags=re.IGNORECASE))


__all__ = [
    "PlanStep",
    "TaskPlan",
    "build_task_plan",
    "format_task_plan",
    "is_confirmation",
    "is_cancellation",
]
