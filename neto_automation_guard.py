"""Safety and observability helpers for NetOps automations.

The guard layer deliberately does not execute an automation during health
checks.  It only validates the definition and reports risks so the UI can
offer a calm, explicit preview before a real run.
"""

from __future__ import annotations

import os
import signal
from pathlib import Path
from typing import Any

import neto_automation_core as core


def health_check(automation_id: str) -> dict[str, Any]:
    automation = core.get_automation(automation_id)
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, Any]] = []

    try:
        preview = core.preview_automation(
            name=automation.name,
            trigger_type=automation.trigger_type,
            trigger=automation.trigger,
            actions=automation.actions,
            policy=automation.policy,
        )
        checks.append({"name": "Şema ve izinler", "ok": True, "message": "Tanım geçerli."})
        warnings.extend(str(item) for item in preview.get("warnings", []))
    except Exception as exc:
        errors.append(str(exc))
        checks.append({"name": "Şema ve izinler", "ok": False, "message": str(exc)})

    for index, action in enumerate(automation.actions, 1):
        action_type = str(action.get("type", ""))
        message = f"{index}. {action_type}"
        ok = True
        detail = "Hazır."
        if action_type == "run_program":
            path = Path(str(action.get("path", "")))
            ok = path.is_file()
            detail = "Program bulundu." if ok else f"Program bulunamadı: {path}"
        elif action_type in {"copy_file", "move_file", "backup_folder"}:
            source = Path(str(action.get("source", "")))
            ok = source.exists()
            detail = "Kaynak bulundu." if ok else f"Kaynak bulunamadı: {source}"
        elif action_type == "write_text":
            target = Path(str(action.get("path", "")))
            ok = bool(str(target))
            detail = "Hedef yolu tanımlı."
        elif action_type == "run_command":
            ok = bool(str(action.get("command", "")).strip())
            detail = "Komut tanımlı." if ok else "Komut boş."
        elif action_type in {"open_url", "http_request"}:
            ok = str(action.get("url", "")).startswith(("http://", "https://"))
            detail = "Ağ adresi geçerli." if ok else "Ağ adresi geçersiz."
        elif action_type == "shutdown":
            warnings.append(f"{index}. işlem bilgisayarı kapatabilir.")
            detail = "Tehlikeli işlem; çalıştırma sırasında ayrıca izin gerekir."
        elif action_type == "lua_script":
            warnings.append(f"{index}. işlem Lua kodu çalıştırır.")
            detail = "Lua kodu tanımlı."
        if not ok:
            errors.append(detail)
        checks.append({"name": message, "ok": ok, "message": detail})

    active_queue = [
        item for item in core.list_queue(200)
        if item["automation_id"] == automation_id
        and item["status"] in core.QUEUE_ACTIVE_STATUSES
    ]
    if active_queue:
        warnings.append("Bu otomasyon zaten kuyrukta veya çalışıyor.")
    if core.emergency_stop_active():
        warnings.append("Acil durdurma açık; yeni işlem başlatılamaz.")

    return {
        "automation_id": automation_id,
        "name": automation.name,
        "ok": not errors,
        "risk": "yüksek" if any(
            action.get("type") in {"shutdown", "run_command", "lua_script"}
            for action in automation.actions
        ) else ("orta" if warnings else "düşük"),
        "checks": checks,
        "warnings": warnings,
        "errors": errors,
    }


def dry_run(automation_id: str) -> dict[str, Any]:
    """Run the existing preview path; no action handler is executed."""
    return core.execute_automation(
        automation_id,
        trigger_info={"type": "dry_run", "source": "guard"},
        dry_run=True,
    )


def history(limit: int = 100) -> list[dict[str, Any]]:
    """Return a compact, newest-first view of runs and queued requests."""
    runs = core.list_runs(limit=limit)
    queue = core.list_queue(limit=limit)
    items: list[dict[str, Any]] = []
    for run in runs:
        items.append(
            {
                "kind": "run",
                "id": run["id"],
                "automation_id": run["automation_id"],
                "status": run["status"],
                "ts": run["finished_at"] or run["started_at"],
                "error": run.get("error"),
            }
        )
    for item in queue:
        items.append(
            {
                "kind": "queue",
                "id": item["id"],
                "automation_id": item["automation_id"],
                "status": item["status"],
                "ts": item["finished_at"] or item["started_at"] or item["enqueued_at"],
                "error": item.get("error"),
            }
        )
    return sorted(items, key=lambda item: float(item.get("ts") or 0), reverse=True)[: max(1, min(int(limit), 500))]


def emergency_stop_all(reason: str = "Kullanıcı acil durdurmayı seçti.") -> dict[str, Any]:
    state = core.set_emergency_stop(reason)
    terminated: list[int] = []
    try:
        import psutil

        for run in core.list_runs(limit=200):
            if run.get("status") != "running":
                continue
            pid = int(run.get("pid") or 0)
            if pid <= 0 or pid == os.getpid() or not psutil.pid_exists(pid):
                continue
            try:
                process = psutil.Process(pid)
                process.terminate()
                terminated.append(pid)
            except Exception:
                continue
    except Exception:
        pass
    try:
        core.stop_worker()
    except Exception:
        pass
    return {**state, "terminated_pids": terminated}


def clear_emergency_stop() -> None:
    core.clear_emergency_stop()


def emergency_status() -> dict[str, Any]:
    value = core.get_meta("emergency_stop", {})
    return value if isinstance(value, dict) else {"active": False}


__all__ = [
    "clear_emergency_stop",
    "dry_run",
    "emergency_status",
    "emergency_stop_all",
    "health_check",
    "history",
]
