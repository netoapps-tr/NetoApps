"""Portable, non-executing backup bundles for NetOps automation data."""

from __future__ import annotations

import copy
import json
import time
import uuid
from pathlib import Path
from typing import Any

import neto_automation_core as core
import neto_scene_engine as scenes


BUNDLE_VERSION = 1
REDACTED_KEYS = {"authorization", "cookie", "x-api-key", "api-key", "token", "password"}


def _safe_action(action: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(action)
    headers = value.get("headers")
    if isinstance(headers, dict):
        value["headers"] = {
            key: ("[yedekten çıkarıldı]" if str(key).casefold() in REDACTED_KEYS else item)
            for key, item in headers.items()
        }
    return value


def export_bundle(path: str | Path) -> dict[str, Any]:
    target = Path(path).expanduser()
    automations = []
    for item in core.list_automations():
        automations.append(
            {
                "name": item.name,
                "enabled": item.enabled,
                "trigger_type": item.trigger_type,
                "trigger": copy.deepcopy(item.trigger),
                "actions": [_safe_action(action) for action in item.actions],
                "policy": copy.deepcopy(item.policy),
            }
        )
    try:
        import neto_user_profiles as profiles

        profile_data = {
            "definitions": profiles.profile_definitions(),
            "state": profiles.get_state(),
        }
    except Exception:
        profile_data = {}
    payload = {
        "format": "netops-automation-bundle",
        "version": BUNDLE_VERSION,
        "created_at": time.time(),
        "automations": automations,
        "scenes": scenes.list_scenes(),
        "profiles": profile_data,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return {
        "path": str(target),
        "automations": len(automations),
        "scenes": len(payload["scenes"]),
        "profiles": len(profile_data.get("definitions", {})),
    }


def import_bundle(path: str | Path) -> dict[str, Any]:
    source = Path(path).expanduser()
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("format") != "netops-automation-bundle":
        raise ValueError("Geçerli bir NetOps yedek paketi değil.")
    imported_automations = 0
    imported_scenes = 0
    warnings: list[str] = []
    for raw in payload.get("automations", []):
        if not isinstance(raw, dict):
            warnings.append("Geçersiz otomasyon kaydı atlandı.")
            continue
        try:
            if bool(raw.get("enabled", False)):
                warnings.append(f"{raw.get('name', 'Otomasyon')} pasif içe aktarıldı; güvenliğin için etkinleştirmen gerekir.")
            core.create_automation(
                name=raw["name"],
                trigger_type=raw["trigger_type"],
                trigger=raw.get("trigger", {}),
                actions=raw.get("actions", []),
                policy=raw.get("policy"),
                enabled=False,
            )
            imported_automations += 1
        except Exception as exc:
            warnings.append(f"Otomasyon içe aktarılamadı: {exc}")
    for raw_scene in payload.get("scenes", []):
        if not isinstance(raw_scene, dict):
            warnings.append("Geçersiz sahne kaydı atlandı.")
            continue
        try:
            scene = copy.deepcopy(raw_scene)
            scene["id"] = uuid.uuid4().hex[:12]
            scene["custom"] = True
            scenes.save_scene(scene)
            imported_scenes += 1
        except Exception as exc:
            warnings.append(f"Sahne içe aktarılamadı: {exc}")
    profile_payload = payload.get("profiles")
    if isinstance(profile_payload, dict):
        active = (profile_payload.get("state") or {}).get("active")
        if active:
            try:
                import neto_user_profiles as profiles

                profiles.apply_profile(active, source="backup_import")
            except Exception as exc:
                warnings.append(f"Profil durumu içe aktarılamadı: {exc}")
    return {
        "automations": imported_automations,
        "scenes": imported_scenes,
        "profile_restored": bool(
            isinstance(profile_payload, dict)
            and (profile_payload.get("state") or {}).get("active")
        ),
        "warnings": warnings,
        "executed": False,
    }


__all__ = ["export_bundle", "import_bundle"]
