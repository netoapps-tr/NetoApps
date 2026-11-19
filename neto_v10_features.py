"""Small, dependency-light feature facade for the NetOps v10 release.

The UI imports this module lazily. It intentionally performs no network work;
the existing updater remains the only place that talks to GitHub.
"""
from __future__ import annotations

import importlib
import platform
import sys
from pathlib import Path
from typing import Any

from neto_version import (
    APP_CHANNEL,
    APP_VERSION,
    RELEASE_HIGHLIGHTS,
    RELEASE_NAME,
    RELEASE_REPOSITORY,
    RELEASE_TAG,
)


def _driver_health(module_name: str, component: str) -> dict[str, Any]:
    try:
        module = importlib.import_module(module_name)
        health = getattr(module, "health", None)
        result = health() if callable(health) else {}
        if not isinstance(result, dict):
            result = {}
        return {
            "id": component,
            "version": str(result.get("version") or getattr(module, "DRIVER_VERSION", "0.0.0")),
            "ok": bool(result.get("ok", True)),
            "mode": str(result.get("mode") or "built-in"),
        }
    except Exception as exc:
        return {"id": component, "version": "0.0.0", "ok": False, "error": str(exc)}


def health_snapshot(project: str | Path | None = None) -> dict[str, Any]:
    """Collect local release health without blocking on network requests."""
    from neto_component_updater import (
        DEFAULT_MANIFEST_URL,
        active_components,
        current_component_versions,
        installed_component_versions,
    )

    base = Path(project or Path(__file__).resolve().parent).resolve()
    try:
        from neto_doctor import quick_check

        doctor = quick_check(str(base), repair=False)
    except Exception as exc:
        doctor = {"ok": False, "message": str(exc), "issues": [str(exc)], "checks": []}

    histories: dict[str, list[dict[str, Any]]] = {}
    for component in ("visual_driver", "now_playing_driver"):
        try:
            histories[component] = installed_component_versions(component)
        except Exception:
            histories[component] = []

    try:
        from neto_ui_guard_agent import NetOpsUIGuardAgent
        from neto_animation_agent import NetOpsAnimationAgent
        from neto_error_detection_agent import NetOpsErrorDetectionAgent

        ui_guard = NetOpsUIGuardAgent(base).run().as_dict()
        animation_agent = NetOpsAnimationAgent().validate_engine(base)
        error_agent = NetOpsErrorDetectionAgent(base).run().as_dict()
    except Exception as exc:
        ui_guard = {"ok": False, "error_count": 1, "errors": [str(exc)]}
        animation_agent = {"ok": False, "errors": [str(exc)]}
        error_agent = {"ok": False, "error_count": 1, "critical_count": 1, "findings": [str(exc)]}

    return {
        "release": {
            "name": RELEASE_NAME,
            "version": APP_VERSION,
            "tag": RELEASE_TAG,
            "channel": APP_CHANNEL,
            "repository": RELEASE_REPOSITORY,
            "highlights": list(RELEASE_HIGHLIGHTS),
        },
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(aliased=True),
            "frozen": bool(getattr(sys, "frozen", False)),
        },
        "doctor": {
            "ok": bool(doctor.get("ok")),
            "message": str(doctor.get("message") or ""),
            "issues": list(doctor.get("issues") or [])[:3],
        },
        "ui_guard": ui_guard,
        "animation_agent": animation_agent,
        "error_detection_agent": error_agent,
        "drivers": [
            _driver_health("neto_visual_driver", "visual_driver"),
            _driver_health("neto_now_playing_driver", "now_playing_driver"),
        ],
        "component_versions": current_component_versions(),
        "active_components": active_components(),
        "histories": histories,
        "manifest_url": DEFAULT_MANIFEST_URL,
    }


def rollback_driver(component: str, version: str | None = None) -> dict[str, Any]:
    """Rollback one installed driver; activation takes effect after restart."""
    from neto_component_updater import rollback_component

    return rollback_component(component, version)
