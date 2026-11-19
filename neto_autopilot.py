"""Neto Autopilot: safe natural-language coordinator for scenes and automations."""

from __future__ import annotations

import re
from typing import Any


AUTOPILOT_VERSION = "1.3.0"

MODE_ALIASES = {
    "çalışma": "work", "calisma": "work", "iş": "work", "is": "work",
    "oyun": "gaming", "ders": "study", "film": "movie", "dizi": "movie",
    "yayın": "streaming", "yayin": "streaming", "stream": "streaming",
    "uyku": "sleep", "sessiz": "sleep",
}


def _mode_from_text(text: str) -> str | None:
    folded = str(text or "").casefold()
    for label, scene_id in MODE_ALIASES.items():
        if re.search(rf"(?<!\w){re.escape(label)}(?!\w)", folded):
            return scene_id
    return None


def prepare(text: str) -> dict[str, Any] | None:
    folded = str(text or "").casefold().strip()
    scene_hint = _mode_from_text(folded)
    explicit = any(token in folded for token in (
        "autopilot", "neto hazırla", "neto hazirla", "beni hazırla", "beni hazirla"
    ))
    # Natural Turkish usually places the mode between “beni” and “hazırla”:
    # “Neto beni oyun için hazırla”. The old contiguous-token check missed it
    # and the message fell through to web chat. Any known scene + prepare verb
    # is an Autopilot scene request.
    if not explicit and scene_hint is not None:
        explicit = "hazırla" in folded or "hazirla" in folded
    if not explicit:
        return None

    # Automation bridge runs before scene parsing so commands such as
    # "Autopilot APIzone'u her 5 dakikada kontrol et" do not fall into
    # the scene-mode question.
    try:
        from neto_autopilot_automation import parse_api_watch

        draft = parse_api_watch(text)
        if draft is not None:
            if not draft.api_id:
                return {"status": "needs_api", "draft": draft}
            return {"status": "automation_preview", "draft": draft}
    except Exception:
        # Scene Autopilot must remain available even if the optional automation
        # bridge cannot be imported.
        pass

    scene_id = scene_hint
    if scene_id is None:
        return {"status": "needs_mode", "message": "Autopilot hangi moda geçsin: çalışma, oyun, ders, film, yayın veya uyku?"}
    from neto_scene_engine import get_scene, preview_scene
    scene = get_scene(scene_id)
    return {"status": "preview", "scene_id": scene_id, "scene": scene, "preview": preview_scene(scene)}


def format_preview(request: dict[str, Any]) -> str:
    status = request.get("status")
    if status == "needs_mode":
        return str(request.get("message"))
    if status in {"needs_api", "automation_preview"}:
        from neto_autopilot_automation import format_api_watch_preview

        return format_api_watch_preview(request["draft"])

    scene = request["scene"]
    preview = request["preview"]
    lines = [f"NetOps Operasyon Planı: {scene['name']} modu", "", "Uygulanacak plan:"]
    for index, step in enumerate(preview.get("steps", []), 1):
        risk = " ⚠️" if step.get("risk") in {"warning", "danger"} else ""
        lines.append(f"{index}. {step.get('label', 'Bilinmeyen işlem')}{risk}")
    if not preview.get("steps"):
        lines.append("1. NetOps profili ve temel ses ayarı uygulanacak.")
    lines.extend([
        "",
        f"Risk seviyesi: {('yüksek' if request.get('preview', {}).get('requires_confirmation') else 'düşük')}",
        "Uygulayayım mı? Evet / Hayır",
    ])
    return "\n".join(lines)


def execute(request: dict[str, Any], *, adapters=None, confirmed: bool = False) -> str:
    status = request.get("status")
    if status == "automation_preview":
        from neto_autopilot_automation import create_api_watch

        result = create_api_watch(request["draft"])
        worker = result.get("worker") or {}
        worker_alive = bool(worker.get("alive") or worker.get("running") or worker.get("started"))
        suffix = "Otomasyon worker'ı aktif." if worker_alive else "Otomasyon kaydedildi; worker durumu panelden kontrol edilebilir."
        return (
            f"NetOps {request['draft'].api_name} izleme operasyonunu oluşturdu ve etkinleştirdi. "
            f"{suffix} Kimlik: {result.get('automation_id')}"
        )

    if status != "preview":
        return "Autopilot planı bulunamadı."
    from neto_operation_loop import create_plan, execute_plan

    plan = create_plan(request)
    result = execute_plan(plan, adapters=adapters, confirmed=confirmed)
    if result.get("status") == "awaiting_confirmation":
        return format_preview(request)
    verification = result.get("verification") or {}
    if result.get("status") == "success":
        verify_label = {
            "verified": "Durum doğrulandı.",
            "partial": "İşlem tamamlandı; bazı durumlar doğrulanamadı.",
        }.get(verification.get("status"), "İşlem tamamlandı.")
        return (
            f"NetOps Operasyon {request['scene']['name']} modunu hazırladı. "
            f"{verify_label} Kimlik: {plan['operation_id']}"
        )
    if result.get("status") == "failed_verification":
        return (
            "NetOps işlemi uyguladı ancak sonucu doğrulayamadı; güvenli kontrol gerekli. "
            f"Kimlik: {plan['operation_id']}"
        )
    if result.get("result", {}).get("rolled_back"):
        return (
            "NetOps operasyonunda hata oluştu; değişiklikler geri alındı: "
            f"{result.get('result', {}).get('error') or 'bilinmeyen hata'}"
        )
    return (
        "NetOps operasyonu tamamlanamadı: "
        f"{result.get('result', {}).get('error') or result.get('status', 'bilinmeyen hata')}"
    )


__all__ = ["AUTOPILOT_VERSION", "execute", "format_preview", "prepare"]
