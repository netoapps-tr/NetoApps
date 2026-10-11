from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Optional

BUILD = "23.0-animation-performance-only"

APP_DIR = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData/Local")) / "NetoAssistant"
CONFIG_PATH = APP_DIR / "runtime" / "runtime_config.json"
_LOCK = threading.RLock()

ANIMATION_MODES = ("normal", "reduced", "off")
ANIMATION_LABELS = {
    "normal": {"tr": "Normal", "en": "Normal"},
    "reduced": {"tr": "Azaltılmış", "en": "Reduced"},
    "off": {"tr": "Kapalı", "en": "Off"},
}

FEATURE_LABELS = {
    "now_playing": {"tr": "Şimdi Çalıyor", "en": "Now Playing"},
    "extension_store": {"tr": "Eklenti Mağazası", "en": "Extension Store"},
    "android": {"tr": "Android", "en": "Android"},
    "live_mode": {"tr": "Live Mode", "en": "Live Mode"},
    "local_api": {"tr": "Yerel API", "en": "Local API"},
    "ui_animations": {"tr": "Arayüz animasyonları", "en": "UI animations"},
    "startup_animation": {"tr": "Açılış animasyonu", "en": "Startup animation"},
    "startup_sound": {"tr": "Açılış sesi", "en": "Startup sound"},
    "updater": {"tr": "Güncelleyici", "en": "Updater"},
    "model_preload": {"tr": "Model ön yükleme", "en": "Model preload"},
    "diagnostics": {"tr": "Teşhis", "en": "Diagnostics"},
    "desktop_automation": {"tr": "Masaüstü otomasyonu", "en": "Desktop automation"},
    "audio_stack": {"tr": "Ses sistemi", "en": "Audio stack"},
    "volume_control": {"tr": "Ses kontrolü", "en": "Volume control"},
    "system_tray": {"tr": "Sistem tepsisi", "en": "System tray"},
}

# Eski modüllerin import sırasında kırılmaması için davranışsız uyumluluk sabitleri.
PROFILE_ORDER = {"balanced": 0}
PROFILE_LABELS = {"balanced": {"tr": "Standart", "en": "Standard"}}
MINIMUM_PROFILES = {name: "balanced" for name in FEATURE_LABELS}

_AUTO_START_FEATURES = {
    "now_playing",
    "ui_animations",
    "startup_animation",
    "startup_sound",
    "updater",
    "system_tray",
}


def _read_config() -> dict:
    try:
        value = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _write_config(value: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = CONFIG_PATH.with_suffix(".json.tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, CONFIG_PATH)


def _normalize_animation_mode(value: Any) -> str:
    raw = str(value or "").strip().casefold()
    aliases = {
        "normal": "normal",
        "smooth": "normal",
        "full": "normal",
        "tam": "normal",
        "reduced": "reduced",
        "reduce": "reduced",
        "azaltılmış": "reduced",
        "azaltilmis": "reduced",
        "low": "reduced",
        "off": "off",
        "disabled": "off",
        "kapalı": "off",
        "kapali": "off",
        "none": "off",
    }
    return aliases.get(raw, "normal")


def animation_mode() -> str:
    data = _read_config()
    if "animation_mode" in data:
        return _normalize_animation_mode(data.get("animation_mode"))
    enabled = bool(data.get("motion_enabled", True))
    reduced = bool(data.get("reduce_motion", False))
    if not enabled:
        return "off"
    if reduced:
        return "reduced"
    return "normal"


def set_animation_mode(mode: str) -> dict:
    normalized = _normalize_animation_mode(mode)
    with _LOCK:
        data = _read_config()
        for key in (
            "profile",
            "custom_features",
            "legacy_feature_preferences",
            "last_profile_change",
            "motion_enabled",
            "reduce_motion",
            "motion_quality",
        ):
            data.pop(key, None)
        data["animation_mode"] = normalized
        data["animation_updated_at"] = time.time()
        _write_config(data)
    return motion_preferences()


def animation_label(mode: Optional[str] = None, lang: str = "tr") -> str:
    language = "en" if str(lang or "").lower().startswith("en") else "tr"
    normalized = _normalize_animation_mode(mode or animation_mode())
    return ANIMATION_LABELS[normalized][language]


def motion_preferences() -> dict:
    mode = animation_mode()
    if mode == "off":
        return {
            "mode": mode,
            "enabled": False,
            "reduce_motion": True,
            "quality": "off",
            "duration_scale": 0.0,
            "frame_ms": 0,
        }
    if mode == "reduced":
        return {
            "mode": mode,
            "enabled": True,
            "reduce_motion": True,
            "quality": "reduced",
            "duration_scale": 0.35,
            "frame_ms": 33,
        }
    return {
        "mode": "normal",
        "enabled": True,
        "reduce_motion": False,
        "quality": "smooth",
        "duration_scale": 1.0,
        "frame_ms": 14,
    }


def set_motion_preferences(*, enabled: Optional[bool] = None, reduce_motion: Optional[bool] = None, quality: Optional[str] = None) -> dict:
    if enabled is False:
        return set_animation_mode("off")
    if reduce_motion is True:
        return set_animation_mode("reduced")
    if quality is not None:
        return set_animation_mode(str(quality))
    if enabled is True or reduce_motion is False:
        return set_animation_mode("normal")
    return motion_preferences()


# Profil sistemi kaldırıldı. Aşağıdaki fonksiyonlar yalnızca eski çağrıları kırmayan no-op uyumluluk katmanıdır.
def current_profile() -> str:
    return "balanced"


def profile_label(profile: str = "balanced", lang: str = "tr") -> str:
    return "Standard" if str(lang or "").lower().startswith("en") else "Standart"


def minimum_profile(feature: str) -> str:
    return "balanced"


def feature_label(feature: str, lang: str = "tr") -> str:
    language = "en" if str(lang or "").lower().startswith("en") else "tr"
    values = FEATURE_LABELS.get(str(feature), {})
    return str(values.get(language) or feature)


def _runtime_feature_enabled(feature: str, profile: Any = None) -> bool:
    runtime = profile
    if runtime is None:
        try:
            from neto_runtime_core import get_runtime

            runtime = get_runtime()
        except Exception:
            runtime = None
    if runtime is None:
        return False
    try:
        checker = getattr(runtime, "feature_enabled", None)
        if callable(checker):
            return bool(checker(feature))
        config = getattr(runtime, "config", None)
        if config is not None:
            enabled = getattr(config, "enabled", None)
            if callable(enabled):
                return bool(enabled(feature))
    except Exception:
        return False
    return False


def profile_allows(feature: str, profile: Any = None) -> bool:
    return _runtime_feature_enabled(feature, profile)


def auto_start_allows(feature: str, profile: Any = None) -> bool:
    return str(feature) in _AUTO_START_FEATURES


def set_profile(profile: str) -> dict:
    data = _read_config()
    old = data.pop("profile", None)
    data.pop("custom_features", None)
    data.pop("legacy_feature_preferences", None)
    data.pop("last_profile_change", None)
    _write_config(data)
    return {"old": old, "new": None, "removed": True}


def set_custom_feature(feature: str, enabled: bool) -> dict:
    return {"feature": str(feature), "enabled": True, "ignored": True, "profile_system_removed": True}


def show_blocked_dialog(root: Any = None, feature: str = "", lang: str = "tr", title: Optional[str] = None) -> bool:
    if profile_allows(feature):
        return True
    dialog_title = title or feature_label(feature, lang)
    dialog_message = (
        f"{feature_label(feature, lang)} şu an etkin değil. Yine de açmak ister misin?"
        if str(lang or "").lower().startswith("tr")
        else f"{feature_label(feature, lang)} is currently disabled. Do you want to enable it anyway?"
    )
    try:
        from tkinter import messagebox

        askyesno = getattr(messagebox, "askyesno", None)
        if callable(askyesno):
            return bool(askyesno(dialog_title, dialog_message, parent=root))
        return False
    except Exception:
        return False


def require_feature(feature: str, *, root: Any = None, lang: str = "tr", interactive: bool = True, title: Optional[str] = None) -> bool:
    if profile_allows(feature):
        return True
    if not interactive:
        return False
    dialog_title = title or feature_label(feature, lang)
    dialog_message = (
        f"{feature_label(feature, lang)} şu an etkin değil. Yine de açmak ister misin?"
        if str(lang or "").lower().startswith("tr")
        else f"{feature_label(feature, lang)} is currently disabled. Do you want to enable it anyway?"
    )
    try:
        from tkinter import messagebox

        askyesno = getattr(messagebox, "askyesno", None)
        if callable(askyesno):
            return bool(askyesno(dialog_title, dialog_message, parent=root))
        return False
    except Exception:
        return False


def show_toast(root, title: str, message: str, kind: str = "info", duration_ms: int = 3000) -> bool:
    try:
        import customtkinter as ctk
    except Exception:
        return False
    try:
        toast = ctk.CTkToplevel(root)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(fg_color="#15151A")
        frame = ctk.CTkFrame(toast, fg_color="#1B1B20", border_width=1, border_color="#3A3A45", corner_radius=14)
        frame.pack(fill="both", expand=True)
        color = {"success": "#22C55E", "warning": "#F59E0B", "error": "#EF4444"}.get(kind, "#60A5FA")
        ctk.CTkLabel(frame, text=str(title), text_color=color, font=("Segoe UI Semibold", 11), anchor="w").pack(fill="x", padx=13, pady=(10, 2))
        ctk.CTkLabel(frame, text=str(message), text_color="#E7E7EB", font=("Segoe UI", 10), anchor="w", justify="left", wraplength=360).pack(fill="x", padx=13, pady=(0, 11))
        toast.update_idletasks()
        width = max(320, toast.winfo_reqwidth())
        height = max(86, toast.winfo_reqheight())
        screen_w = toast.winfo_screenwidth()
        screen_h = toast.winfo_screenheight()
        toast.geometry(f"{width}x{height}+{screen_w-width-24}+{screen_h-height-72}")
        toast.after(max(800, int(duration_ms)), toast.destroy)
        return True
    except Exception:
        return False
