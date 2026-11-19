"""NetOps Recovery Mesh.

The mesh coordinates diagnosis, risk classification, backup, verification and
rollback planning.  Planning is intentionally read-only; a repair step must
be approved by the existing permission/operation systems before it can change
anything.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any


RECOVERY_VERSION = "1.0.0"

_SKILL_CATALOG = (
    {
        "id": "observe",
        "name": "Gözlemci",
        "description": "Logları ve sağlık sinyallerini değişiklik yapmadan toplar.",
        "default_mode": "review",
    },
    {
        "id": "classify",
        "name": "Risk Sınıflandırıcı",
        "description": "Hataları bilgi, hata ve kritik olarak sınıflandırır.",
        "default_mode": "review",
    },
    {
        "id": "backup",
        "name": "Geri Dönüş Koruması",
        "description": "Onarım öncesi doğrulanabilir yedek gerektirir.",
        "default_mode": "review",
    },
    {
        "id": "verify",
        "name": "Doğrulayıcı",
        "description": "Onarım sonrası aynı hatanın sürüp sürmediğini kontrol eder.",
        "default_mode": "review",
    },
    {
        "id": "rollback",
        "name": "Geri Alma Bekçisi",
        "description": "Doğrulama başarısızsa yalnızca onaylı yedeğe dönüş önerir.",
        "default_mode": "review",
    },
)


def recovery_skill_catalog() -> tuple[dict[str, str], ...]:
    """Return a copy-like immutable view for UI, agent and plugin callers."""
    return tuple(dict(item) for item in _SKILL_CATALOG)


def _int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _severity(report: dict[str, Any]) -> str:
    if _int(report.get("critical_count")):
        return "critical"
    if _int(report.get("error_count")):
        return "error"
    return "healthy"


def build_recovery_plan(report: dict[str, Any]) -> dict[str, Any]:
    """Build a review-first recovery plan from an error report."""
    if not isinstance(report, dict):
        raise TypeError("Recovery raporu sözlük olmalı.")
    severity = _severity(report)
    base = {
        "schema_version": 1,
        "recovery_version": RECOVERY_VERSION,
        "created_at": time.time(),
        "severity": severity,
        "files_scanned": _int(report.get("files_scanned")),
        "error_count": _int(report.get("error_count")),
        "critical_count": _int(report.get("critical_count")),
        "requires_confirmation": False,
        "status": "healthy" if severity == "healthy" else "review_required",
        "steps": [],
        "findings": list(report.get("findings") or [])[:100],
    }
    if severity == "healthy":
        return base

    base["status"] = "approval_required"
    base["requires_confirmation"] = True
    base["steps"] = [
        {
            "id": "diagnose",
            "skill": "observe",
            "action": "Son logları ve ilgili dosya izlerini yeniden incele",
            "mode": "read_only",
        },
        {
            "id": "backup",
            "skill": "backup",
            "action": "Onarım öncesi doğrulanabilir yedek oluştur",
            "mode": "review",
            "requires_confirmation": True,
        },
        {
            "id": "repair_review",
            "skill": "classify",
            "action": "Sadece güvenli ve sınırlı onarım adaylarını listele",
            "mode": "review",
            "requires_confirmation": True,
        },
        {
            "id": "verify",
            "skill": "verify",
            "action": "Onarım sonrası testleri ve hata sayısını karşılaştır",
            "mode": "read_only",
        },
        {
            "id": "rollback_on_failure",
            "skill": "rollback",
            "action": "Doğrulama başarısızsa geri alma seçeneği sun",
            "mode": "review",
            "requires_confirmation": True,
        },
    ]
    return base


def diagnose(project_dir: str | Path = ".") -> dict[str, Any]:
    """Run the existing non-destructive error detector and build a plan."""
    from neto_error_detection_agent import detect_errors

    project = Path(project_dir).expanduser().resolve()
    report = detect_errors(project)
    plan = build_recovery_plan(report)
    plan["project_dir"] = str(project)
    return plan


def format_plan(plan: dict[str, Any]) -> str:
    """Create a compact Turkish status message for the chat/UI."""
    status = str(plan.get("status") or "unknown")
    if status == "healthy":
        return (
            f"Recovery Mesh: temiz ({plan.get('files_scanned', 0)} dosya tarandı). "
            "Onay gerektiren onarım yok."
        )
    return (
        f"Recovery Mesh: {plan.get('error_count', 0)} hata, "
        f"{plan.get('critical_count', 0)} kritik. Onarım öncesi açık onay ve yedek gerekli."
    )


__all__ = [
    "RECOVERY_VERSION",
    "build_recovery_plan",
    "diagnose",
    "format_plan",
    "recovery_skill_catalog",
]
