from __future__ import annotations

from neto_runtime_policy_v2 import (
    FEATURE_LABELS,
    MINIMUM_PROFILES as STRICT_MINIMUMS,
    PROFILE_LABELS,
    PROFILE_ORDER,
    auto_start_allows,
    current_profile,
    feature_label,
    minimum_profile,
    profile_allows,
    profile_label,
    require_feature,
    set_custom_feature,
    set_profile,
    show_blocked_dialog,
    show_toast,
)


def show_blocked_warning(feature: str, *, root=None, lang="tr", retry=None, **_kwargs):
    accepted = show_blocked_dialog(root, feature, lang=lang)
    if accepted and callable(retry):
        try:
            if root is not None:
                root.after(80, retry)
            else:
                retry()
        except Exception:
            pass
    return accepted
