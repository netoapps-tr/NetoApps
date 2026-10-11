"""Safe, user-facing NetOps profiles.

Profiles describe application preferences only. They do not execute arbitrary
commands, change files outside the NetOps data directory, or alter Windows
power settings without a separate explicit action.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any


APP_DIR = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData/Local")) / "NetOps"
STORE_PATH = APP_DIR / "user_profiles.json"
STORE_VERSION = 1
_LOCK = threading.RLock()


PROFILE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "balanced": {
        "label": "Dengeli",
        "icon": "NET",
        "description": "Günlük kullanım için dengeli NetOps deneyimi.",
        "settings": {
            "animation_mode": "normal",
            "live_mode_on_start": False,
            "now_playing_on_start": True,
            "updates_on_start": True,
            "quiet_mode": False,
        },
    },
    "gaming": {
        "label": "Oyun",
        "icon": "GO",
        "description": "Görsel yükü azaltır ve oyun sırasında gereksiz başlangıç işlemlerini bekletir.",
        "settings": {
            "animation_mode": "reduced",
            "live_mode_on_start": False,
            "now_playing_on_start": False,
            "updates_on_start": False,
            "quiet_mode": True,
        },
    },
    "study": {
        "label": "Ders",
        "icon": "OKU",
        "description": "Sohbet, notlar ve öğrenme akışını sade bir düzende hazırlar.",
        "settings": {
            "animation_mode": "normal",
            "live_mode_on_start": False,
            "now_playing_on_start": False,
            "updates_on_start": True,
            "quiet_mode": True,
        },
    },
    "streaming": {
        "label": "Yayın",
        "icon": "LIVE",
        "description": "Live Mode ve Şimdi Çalıyor akışını yayın kullanımına hazırlar.",
        "settings": {
            "animation_mode": "reduced",
            "live_mode_on_start": True,
            "now_playing_on_start": True,
            "updates_on_start": False,
            "quiet_mode": False,
        },
    },
    "quiet": {
        "label": "Sessiz",
        "icon": "SUS",
        "description": "Sesli ve görsel bildirimleri azaltarak sakin çalışma modu sağlar.",
        "settings": {
            "animation_mode": "off",
            "live_mode_on_start": False,
            "now_playing_on_start": False,
            "updates_on_start": False,
            "quiet_mode": True,
        },
    },
}


PROFILE_ALIASES = {
    "dengeli": "balanced",
    "balanced": "balanced",
    "oyun": "gaming",
    "gaming": "gaming",
    "ders": "study",
    "study": "study",
    "yayin": "streaming",
    "yayın": "streaming",
    "stream": "streaming",
    "streaming": "streaming",
    "sessiz": "quiet",
    "quiet": "quiet",
}


def _default_state() -> dict[str, Any]:
    return {
        "version": STORE_VERSION,
        "active": "balanced",
        "last_applied_at": 0.0,
        "history": [],
    }


def _read_state() -> dict[str, Any]:
    try:
        value = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except Exception:
        value = {}
    state = _default_state()
    if isinstance(value, dict):
        state.update(value)
    active = normalize_profile(state.get("active"))
    state["active"] = active or "balanced"
    history = state.get("history")
    state["history"] = history[-50:] if isinstance(history, list) else []
    return state


def _write_state(state: dict[str, Any]) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="user_profiles_", suffix=".tmp", dir=str(APP_DIR))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
        os.replace(temp_name, STORE_PATH)
    finally:
        try:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        except OSError:
            pass


def normalize_profile(profile: Any) -> str | None:
    value = str(profile or "").strip().casefold()
    return PROFILE_ALIASES.get(value)


def profile_definitions() -> dict[str, dict[str, Any]]:
    return copy.deepcopy(PROFILE_DEFINITIONS)


def profile_info(profile: Any = None) -> dict[str, Any]:
    profile_id = normalize_profile(profile) or get_active_profile()
    info = copy.deepcopy(PROFILE_DEFINITIONS[profile_id])
    info["id"] = profile_id
    return info


def get_active_profile() -> str:
    with _LOCK:
        return _read_state()["active"]


def get_state() -> dict[str, Any]:
    with _LOCK:
        return copy.deepcopy(_read_state())


def apply_profile(profile: Any, *, source: str = "ui") -> dict[str, Any]:
    profile_id = normalize_profile(profile)
    if profile_id is None:
        raise ValueError(f"Bilinmeyen NetOps profili: {profile}")

    with _LOCK:
        state = _read_state()
        previous = state["active"]
        state["active"] = profile_id
        state["last_applied_at"] = time.time()
        history = state.setdefault("history", [])
        history.append(
            {
                "profile": profile_id,
                "previous": previous,
                "source": str(source or "ui"),
                "at": state["last_applied_at"],
            }
        )
        state["history"] = history[-50:]
        _write_state(state)

    info = profile_info(profile_id)
    return {
        "ok": True,
        "profile": profile_id,
        "previous": previous,
        "label": info["label"],
        "description": info["description"],
        "settings": copy.deepcopy(info["settings"]),
        "store_path": str(STORE_PATH),
    }


__all__ = [
    "PROFILE_DEFINITIONS",
    "STORE_PATH",
    "apply_profile",
    "get_active_profile",
    "get_state",
    "normalize_profile",
    "profile_definitions",
    "profile_info",
]
