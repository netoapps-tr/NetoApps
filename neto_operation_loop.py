"""NetOps Operasyon Döngüsü.

NetOps'un ayırt edici kontrol akışını tek bir yerde toplar:
planla -> onayla -> uygula -> doğrula -> kaydet.

Bu katman mevcut sahne motorunu kullanır; cihaz adaptörlerini veya arayüzü
doğrudan import etmez. Böylece sohbet, UI ve testler aynı güvenli sözleşmeyi
kullanabilir.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from neto_scene_engine import SceneAdapters, preview_scene, restore_snapshot, run_scene, snapshot


OPERATION_SCHEMA_VERSION = 1
OPERATION_LOOP_VERSION = "1.0.0"


def _emit_nodered_event(event: str, payload: dict[str, Any]) -> None:
    """Notify the optional local flow engine without affecting operations."""
    if str(os.environ.get("NETOPS_NODERED_EVENTS", "1")).strip().casefold() in {"0", "false", "off", "no"}:
        return
    try:
        from neto_nodered_bridge import NodeRedBridge

        NodeRedBridge(timeout=0.35).emit(event, payload)
    except Exception:
        # Node-RED is optional; a stopped flow engine must not break NetOps.
        return


def history_path() -> Path:
    override = os.environ.get("NETOPS_OPERATION_HISTORY")
    if override:
        return Path(override).expanduser()
    base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    return base / "NetOps" / "operations.json"


def _now() -> float:
    return time.time()


def _risk_for_plan(preview: dict[str, Any]) -> str:
    if preview.get("requires_confirmation"):
        return "danger"
    if preview.get("warnings"):
        return "warning"
    return "safe"


def create_plan(request: dict[str, Any]) -> dict[str, Any]:
    """Convert a scene preview into a stable, user-visible operation plan."""
    if not isinstance(request, dict) or request.get("status") != "preview":
        raise ValueError("Geçerli bir NetOps operasyon planı bulunamadı.")
    scene = copy.deepcopy(request.get("scene") or {})
    preview = copy.deepcopy(request.get("preview") or preview_scene(scene))
    operation_id = uuid.uuid4().hex[:12]
    steps = []
    for index, step in enumerate(preview.get("steps") or [], 1):
        steps.append(
            {
                "index": index,
                "label": str(step.get("label") or "Bilinmeyen işlem"),
                "kind": str(step.get("kind") or "unknown"),
                "risk": str(step.get("risk") or "safe"),
            }
        )
    return {
        "schema_version": OPERATION_SCHEMA_VERSION,
        "operation_loop_version": OPERATION_LOOP_VERSION,
        "operation_id": operation_id,
        "goal": f"{scene.get('name') or 'NetOps'} modunu hazırla",
        "target_type": "scene",
        "target_id": str(scene.get("id") or ""),
        "scene": scene,
        "steps": steps,
        "warnings": [str(item) for item in preview.get("warnings") or []],
        "risk": _risk_for_plan(preview),
        "requires_confirmation": bool(preview.get("requires_confirmation")),
        "rollback_enabled": bool(scene.get("rollback_on_failure", True)),
        "status": "planned",
        "created_at": _now(),
    }


def _values_match(expected: Any, actual: Any, *, numeric: bool = False) -> bool:
    if numeric:
        try:
            return abs(float(expected) - float(actual)) <= 1.0
        except (TypeError, ValueError):
            return False
    return expected == actual


def verify_plan(plan: dict[str, Any], adapters: SceneAdapters) -> dict[str, Any]:
    """Compare requested scene state with the state reported by adapters."""
    scene = plan.get("scene") or {}
    observed = snapshot(adapters)
    expected = {
        "profile": scene.get("profile"),
        "volume": (scene.get("volume") or {}).get("percent"),
        "muted": (scene.get("volume") or {}).get("muted"),
        "brightness": scene.get("brightness"),
    }
    checks: list[dict[str, Any]] = []
    for key, wanted in expected.items():
        if wanted is None:
            continue
        actual = observed.get(key)
        if actual is None:
            checks.append({"name": key, "status": "unavailable", "expected": wanted})
            continue
        ok = _values_match(wanted, actual, numeric=key in {"volume", "brightness"})
        checks.append(
            {
                "name": key,
                "status": "ok" if ok else "mismatch",
                "expected": wanted,
                "actual": actual,
            }
        )
    if any(item["status"] == "mismatch" for item in checks):
        status = "failed"
    elif any(item["status"] == "unavailable" for item in checks):
        status = "partial"
    else:
        status = "verified"
    return {"status": status, "checks": checks, "observed": observed, "checked_at": _now()}


def _read_history() -> list[dict[str, Any]]:
    try:
        value = json.loads(history_path().read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except (OSError, ValueError, TypeError):
        return []


def _write_history(record: dict[str, Any]) -> None:
    path = history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    records = (_read_history() + [copy.deepcopy(record)])[-100:]
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix="netops-operation-", suffix=".tmp", dir=str(path.parent)
    )
    os.close(file_descriptor)
    temporary = Path(temporary_name)
    try:
        temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def execute_plan(
    plan: dict[str, Any],
    *,
    adapters: Optional[SceneAdapters] = None,
    confirmed: bool = False,
) -> dict[str, Any]:
    """Run a confirmed plan and append a verifiable operation record."""
    if plan.get("requires_confirmation") and not confirmed:
        return {"status": "awaiting_confirmation", "plan": copy.deepcopy(plan)}
    active_adapters = adapters
    if active_adapters is None:
        from neto_scene_engine import default_adapters

        active_adapters = default_adapters()
    result = run_scene(
        plan.get("scene") or plan.get("target_id"),
        adapters=active_adapters,
        confirm=(lambda _message: bool(confirmed)),
    )
    verification = verify_plan(plan, active_adapters) if result.get("status") == "success" else None
    status = str(result.get("status") or "failed")
    if status == "success" and verification and verification["status"] == "failed":
        status = "failed_verification"
        if plan.get("rollback_enabled") and result.get("snapshot"):
            rollback_errors = restore_snapshot(result["snapshot"], active_adapters)
            result["rolled_back"] = True
            if rollback_errors:
                result["error"] = "Doğrulama başarısız; geri alma uyarıları: " + "; ".join(rollback_errors)
    record = {
        "schema_version": OPERATION_SCHEMA_VERSION,
        "operation_id": plan.get("operation_id"),
        "goal": plan.get("goal"),
        "target_type": plan.get("target_type"),
        "target_id": plan.get("target_id"),
        "status": status,
        "result": copy.deepcopy(result),
        "verification": copy.deepcopy(verification),
        "completed_at": _now(),
    }
    try:
        _write_history(record)
    except OSError:
        # A history failure must not turn a successful local operation into a
        # crash. The result reports the operation even when storage is read-only.
        record["history_error"] = "Operasyon geçmişi yazılamadı."
    _emit_nodered_event(
        "netops.operation.completed",
        {
            "operation_id": plan.get("operation_id"),
            "target_id": plan.get("target_id"),
            "status": status,
            "risk": plan.get("risk"),
        },
    )
    return {"status": status, "plan": copy.deepcopy(plan), "result": result, "verification": verification, "record": record}


def recent_operations(limit: int = 10) -> list[dict[str, Any]]:
    try:
        count = max(1, min(100, int(limit)))
    except (TypeError, ValueError):
        count = 10
    return _read_history()[-count:][::-1]


def last_operation() -> Optional[dict[str, Any]]:
    records = recent_operations(1)
    return records[0] if records else None


__all__ = [
    "OPERATION_LOOP_VERSION",
    "OPERATION_SCHEMA_VERSION",
    "create_plan",
    "execute_plan",
    "history_path",
    "last_operation",
    "recent_operations",
    "verify_plan",
]
