from __future__ import annotations

from typing import Callable, Optional

FEATURE_TITLES = {
    "now_playing": {"tr": "Şimdi Çalıyor", "en": "Now Playing"},
    "extension_store": {"tr": "Eklenti Mağazası", "en": "Extension Store"},
    "android": {"tr": "Android", "en": "Android"},
    "live_mode": {"tr": "Live Mode", "en": "Live Mode"},
    "updater": {"tr": "Güncelleyici", "en": "Updater"},
    "linux_bridge": {"tr": "Linux köprüsü (WSL)", "en": "Linux bridge (WSL)"},
}
STRICT_MINIMUMS = {}
PROFILE_ORDER = {}
RESTART_FEATURES = {
    "local_api", "startup_animation", "startup_sound", "model_preload",
    "system_tray", "audio_stack", "volume_control",
}


def feature_title(feature: str, lang: str = "tr") -> str:
    language = "en" if str(lang or "").lower().startswith("en") else "tr"
    values = FEATURE_TITLES.get(str(feature), {})
    return str(values.get(language) or feature)


def _profile_label(profile: str, lang: str = "tr") -> str:
    return "Standard" if str(lang or "").lower().startswith("en") else "Standart"


def _runtime_feature_enabled(feature: str, runtime=None) -> bool:
    runtime = runtime
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


def profile_allows(feature: str, runtime=None) -> bool:
    return _runtime_feature_enabled(feature, runtime)


def show_blocked_dialog(root, feature: str, action: Optional[Callable] = None, lang: str = "tr", title: Optional[str] = None):
    if profile_allows(feature):
        return action() if callable(action) else True
    dialog_title = title or feature_title(feature, lang)
    dialog_message = (
        f"{feature_title(feature, lang)} şu an etkin değil. Yine de açmak ister misin?"
        if str(lang or "").lower().startswith("tr")
        else f"{feature_title(feature, lang)} is currently disabled. Do you want to enable it anyway?"
    )
    try:
        from tkinter import messagebox

        accepted = bool(messagebox.askyesno(dialog_title, dialog_message, parent=root))
    except Exception:
        accepted = False
    if accepted and callable(action):
        return action()
    return accepted


def require_feature(root, feature: str, action: Optional[Callable] = None, lang: str = "tr", title: Optional[str] = None):
    if profile_allows(feature):
        return action() if callable(action) else True
    return show_blocked_dialog(root, feature, action=action, lang=lang, title=title)
