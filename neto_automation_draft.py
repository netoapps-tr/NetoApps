"""Safe, deterministic automation drafts created from natural Turkish text.

Drafts are previews only. The caller must explicitly pass confirm=True
to create an automation, and creation never starts the worker by itself.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class AutomationDraft:
    name: str
    trigger_type: str
    trigger: dict[str, Any]
    actions: list[dict[str, Any]]
    warnings: list[str] = field(default_factory=list)
    confidence: float = 0.0
    source_text: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _duration_seconds(value: str, unit: str) -> int:
    amount = max(1, int(value))
    return amount * {"saniye": 1, "dakika": 60, "saat": 3600}.get(unit, 1)


def parse_draft(text: str) -> AutomationDraft | None:
    raw = str(text or "").strip()
    normalized = raw.casefold()
    if not raw or not any(
        marker in normalized
        for marker in ("otomasyon", "her gün", "her gun", "açılışta", "acilista", "zamanla")
    ):
        return None

    warnings = [
        "Bu yalnızca bir taslaktır; kaydetmeden önce adımları kontrol et.",
    ]
    trigger_type = "manual"
    trigger: dict[str, Any] = {}
    confidence = 0.55

    daily = re.search(r"\bher\s+gün\b.*?\b(?:saat\s*)?([01]?\d|2[0-3]):([0-5]\d)", normalized)
    if not daily:
        daily = re.search(r"\bher\s+gun\b.*?\b(?:saat\s*)?([01]?\d|2[0-3]):([0-5]\d)", normalized)
    if daily:
        trigger_type = "daily"
        trigger = {"time": f"{int(daily.group(1)):02d}:{daily.group(2)}"}
        confidence = 0.85
    else:
        interval = re.search(r"\bher\s+(\d+)\s+(saniye|dakika|saat)\b", normalized)
        if interval:
            trigger_type = "interval"
            trigger = {"seconds": _duration_seconds(interval.group(1), interval.group(2))}
            confidence = 0.82
        elif "açılışta" in normalized or "acilista" in normalized:
            trigger_type = "startup"
            trigger = {"delay_seconds": 5}
            confidence = 0.8
        else:
            warnings.append("Tetikleyici net değil; taslak Manuel olarak oluşturuldu.")

    actions: list[dict[str, Any]] = []
    program_path = re.search(
        r"([A-Za-z]:[\\/][^\n]+?\.(?:exe|bat|cmd|pyw?))",
        raw,
        flags=re.IGNORECASE,
    )
    if program_path and any(marker in normalized for marker in ("aç", "ac", "çalıştır", "calistir")):
        actions.append({"type": "run_program", "path": program_path.group(1), "args": [], "wait": False})
        confidence = min(0.95, confidence + 0.08)
    else:
        actions.append(
            {
                "type": "notify",
                "title": "NetOps otomasyon taslağı",
                "message": raw[:500],
            }
        )
        warnings.append("Belirli bir uygulama yolu bulunmadığı için güvenli bildirim adımı eklendi.")

    if "internet varsa" in normalized or "internet gelince" in normalized:
        actions[0]["condition"] = {"type": "internet_online"}

    name = "Sohbetten oluşturulan otomasyon"
    if trigger_type == "daily":
        name = f"Günlük otomasyon · {trigger['time']}"
    elif trigger_type == "interval":
        name = "Aralıklı otomasyon"
    elif trigger_type == "startup":
        name = "Açılış otomasyonu"
    return AutomationDraft(
        name=name,
        trigger_type=trigger_type,
        trigger=trigger,
        actions=actions,
        warnings=warnings,
        confidence=confidence,
        source_text=raw,
    )


def format_draft(draft: AutomationDraft) -> str:
    lines = [
        "Otomasyon taslağı hazır. Henüz hiçbir işlem çalıştırılmadı.",
        f"Ad: {draft.name}",
        f"Tetikleyici: {draft.trigger_type}",
        "Adımlar:",
    ]
    for index, action in enumerate(draft.actions, 1):
        lines.append(f"{index}. {action.get('type', 'işlem')}")
    if draft.warnings:
        lines.extend(["", "Kontrol et:", *[f"- {item}" for item in draft.warnings]])
    lines.append("")
    lines.append("Kaydetmek için taslağı Otomasyon Merkezi'nde açıp onaylaman gerekir.")
    return "\n".join(lines)


def create_from_draft(draft: AutomationDraft, *, confirm: bool = False) -> str:
    if not confirm:
        raise PermissionError("Taslak yalnızca açık kullanıcı onayıyla kaydedilebilir.")
    import neto_automation_core as core

    return core.create_automation(
        name=draft.name,
        trigger_type=draft.trigger_type,
        trigger=draft.trigger,
        actions=draft.actions,
        policy={"rollback_on_failure": True},
        enabled=False,
    )


__all__ = ["AutomationDraft", "create_from_draft", "format_draft", "parse_draft"]
