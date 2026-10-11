"""Deterministic Autopilot bridge for safe Public-API watch automations.

This module intentionally handles only a narrow, auditable command family:
monitor one verified no-key Public API on an interval/daily schedule and notify
when the provider goes down or recovers. Nothing is created until the user
confirms the Autopilot preview.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


WATCH_MARKERS = (
    "izle", "takip et", "kontrol et", "monitor et", "monitör et",
    "çökerse", "cokerse", "çalışmazsa", "calismazsa", "bozulursa",
    "geri gelirse", "düzelirse", "duzelirse", "erişilemezse", "erisilemezse",
)


@dataclass
class ApiWatchDraft:
    api_id: str
    api_name: str
    source_kind: str
    trigger_type: str
    trigger: dict[str, Any]
    actions: list[dict[str, Any]]
    warnings: list[str] = field(default_factory=list)
    source_text: str = ""

    @property
    def name(self) -> str:
        return f"API izle · {self.api_name}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "api_id": self.api_id,
            "api_name": self.api_name,
            "source_kind": self.source_kind,
            "name": self.name,
            "trigger_type": self.trigger_type,
            "trigger": dict(self.trigger),
            "actions": [dict(x) for x in self.actions],
            "warnings": list(self.warnings),
            "source_text": self.source_text,
        }


def _fold(value: str) -> str:
    table = str.maketrans({
        "ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u",
        "’": "'", "`": "'",
    })
    return str(value or "").casefold().translate(table)


def _compact(value: str) -> str:
    return re.sub(r"[^a-z0-9&+._-]+", "", _fold(value))


def _duration_seconds(amount: int, unit: str) -> int:
    unit = _fold(unit)
    factor = 1
    if unit.startswith("dakika"):
        factor = 60
    elif unit.startswith("saat"):
        factor = 3600
    return max(10, min(int(amount) * factor, 31_536_000))


def _parse_trigger(text: str) -> tuple[str, dict[str, Any], list[str]]:
    folded = _fold(text)
    warnings: list[str] = []

    daily = re.search(r"\bher\s+gun\b.*?\b(?:saat\s*)?([01]?\d|2[0-3]):([0-5]\d)", folded)
    if daily:
        return "daily", {"time": f"{int(daily.group(1)):02d}:{daily.group(2)}"}, warnings

    interval = re.search(r"\bher\s+(\d+)\s*(saniye(?:de)?|dakika(?:da)?|saat(?:te)?)\b", folded)
    if interval:
        seconds = _duration_seconds(int(interval.group(1)), interval.group(2))
        if int(interval.group(1)) > 0 and seconds == 10 and not interval.group(2).startswith("saat"):
            warnings.append("Otomasyon motorunun minimum aralığı 10 saniye olduğu için süre 10 saniyeye ayarlandı.")
        return "interval", {"seconds": seconds}, warnings

    warnings.append("Kontrol aralığı belirtilmedi; varsayılan 5 dakika kullanılacak.")
    return "interval", {"seconds": 300}, warnings


def _resolve_api_mentioned_in_text(text: str) -> dict[str, Any] | None:
    try:
        from neto_public_apis import free_entries, load_catalog, load_verified, verified_health
    except Exception:
        return None

    folded_text = _compact(text)
    verified = list(load_verified().get("apis") or [])
    catalog = list(free_entries(load_catalog().get("entries") or []))
    candidates: list[tuple[int, int, int, dict[str, Any]]] = []

    for api in verified:
        names = [str(api.get("name") or "").strip(), str(api.get("id") or "").strip()]
        best = max((len(_compact(raw)) for raw in names if _compact(raw) and _compact(raw) in folded_text), default=0)
        if best:
            try:
                state = str(verified_health(api).get("state") or "unknown")
                state_rank = {"ok": 0, "unknown": 1, "transient": 2, "failed": 3, "dead": 4, "unsafe_tls": 5}.get(state, 6)
            except Exception:
                state_rank = 6
            candidates.append((best, 0, state_rank, api))

    for entry in catalog:
        raw = str(entry.get("name") or "").strip()
        norm = _compact(raw)
        if norm and norm in folded_text:
            candidates.append((len(norm), 1, 0, entry))

    if not candidates:
        return None
    # Longest textual match wins. Verified semantic endpoints win an exact tie.
    candidates.sort(key=lambda item: (-item[0], item[1], item[2], str(item[3].get("name") or "").casefold()))
    return candidates[0][3]


def parse_api_watch(text: str) -> ApiWatchDraft | None:
    raw = str(text or "").strip()
    folded = _fold(raw)
    if not raw:
        return None
    if "autopilot" not in folded and "neto" not in folded:
        return None
    if not any(_fold(marker) in folded for marker in WATCH_MARKERS):
        return None

    api = _resolve_api_mentioned_in_text(raw)
    if not api:
        return ApiWatchDraft(
            api_id="",
            api_name="",
            source_kind="unknown",
            trigger_type="interval",
            trigger={"seconds": 300},
            actions=[],
            warnings=["İzlenecek API adı katalogdaki doğrulanmış bir servisle eşleşmedi."],
            source_text=raw,
        )

    trigger_type, trigger, warnings = _parse_trigger(raw)
    folded_raw = _fold(raw)
    notify_on = ["down", "recovered"]
    if "sadece" in folded_raw and any(x in folded_raw for x in ("cokerse", "calismazsa", "bozulursa")):
        notify_on = ["down"]
    if "her kontrolde" in folded_raw or "her seferinde" in folded_raw:
        notify_on = ["always"]

    api_id = str(api.get("id") or api.get("name") or "").strip()
    api_name = str(api.get("name") or api_id).strip()
    source_kind = "verified" if api.get("id") else "catalog"
    actions = [
        {
            "type": "public_api_watch",
            "api": api_id,
            "api_label": api_name,
            "notify_on": notify_on,
            "repeat_down": False,
            "title": "NetOps Autopilot · API Watch",
            "timeout_seconds": 8,
            "retries": 0,
        }
    ]
    return ApiWatchDraft(
        api_id=api_id,
        api_name=api_name,
        source_kind=source_kind,
        trigger_type=trigger_type,
        trigger=trigger,
        actions=actions,
        warnings=warnings,
        source_text=raw,
    )


def _trigger_text(draft: ApiWatchDraft) -> str:
    if draft.trigger_type == "daily":
        return f"Her gün {draft.trigger.get('time', '00:00')}"
    seconds = int(draft.trigger.get("seconds", 300))
    if seconds % 3600 == 0:
        return f"Her {seconds // 3600} saatte"
    if seconds % 60 == 0:
        return f"Her {seconds // 60} dakikada"
    return f"Her {seconds} saniyede"


def format_api_watch_preview(draft: ApiWatchDraft) -> str:
    if not draft.api_id:
        return (
            "Neto Autopilot API izleme komutunu anladı ama hangi API'yi izleyeceğini bulamadı. "
            "Örnek: ‘Autopilot APIzone'u her 5 dakikada kontrol et, çökerse bildir.’"
        )
    action = draft.actions[0]
    notify_on = set(action.get("notify_on") or [])
    if "always" in notify_on:
        notify_text = "Her kontrolde"
    elif notify_on == {"down"}:
        notify_text = "Servis çökerse"
    else:
        notify_text = "Servis çökerse ve geri gelirse"
    lines = [
        f"Neto Autopilot: {draft.api_name} için API izleme planı",
        "",
        f"• Tetikleyici: {_trigger_text(draft)}",
        f"• Kaynak: {'verified endpoint' if draft.source_kind == 'verified' else 'ücretsiz public-apis kataloğu'} · {draft.api_id}",
        f"• Bildirim: {notify_text}",
        "• Fallback kullanılmayacak; özellikle seçtiğin sağlayıcının kendi durumu izlenecek.",
    ]
    if draft.warnings:
        lines.extend(["", *[f"⚠️ {warning}" for warning in draft.warnings]])
    lines.extend(["", "Bu otomasyonu kaydedip etkinleştireyim mi? Evet / Hayır"])
    return "\n".join(lines)


def create_api_watch(draft: ApiWatchDraft) -> dict[str, Any]:
    if not draft.api_id:
        raise ValueError("İzlenecek API bulunamadı.")
    import neto_automation_core as core

    automation_id = core.create_automation(
        name=draft.name,
        trigger_type=draft.trigger_type,
        trigger=draft.trigger,
        actions=draft.actions,
        policy={
            "rollback_on_failure": False,
            "continue_on_action_error": False,
            "allow_dangerous_commands": False,
            "max_retries": 1,
            "cooldown_seconds": 0,
        },
        enabled=True,
    )
    worker = core.start_worker()
    return {"automation_id": automation_id, "worker": worker}


__all__ = [
    "ApiWatchDraft",
    "create_api_watch",
    "format_api_watch_preview",
    "parse_api_watch",
]
