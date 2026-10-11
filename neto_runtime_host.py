from __future__ import annotations

import os
import sys
import threading
import traceback
from tkinter import messagebox

from neto_command_palette import bind_command_palette
from neto_branding import install_branding
from neto_feature_gate import profile_allows
from neto_runtime_core import (
    attach_host,
    feature_enabled,
    get_runtime,
    mark_healthy,
    record_exception,
    startup_mark,
)
from neto_runtime_services import register_main_services, schedule_enabled_services


_INITIALIZED = False


def _apply_profile_ui_state(root, namespace):
    runtime = get_runtime()

    if not profile_allows("now_playing", runtime):
        try:
            callback = namespace.get("now_playing_overlay_kapat")
            if callable(callback):
                callback()
        except Exception:
            pass
        try:
            stop_event = namespace.get("now_playing_monitor_stop")
            if stop_event is not None:
                stop_event.set()
        except Exception:
            pass

    if not profile_allows("extension_store", runtime):
        try:
            callback = namespace.get("eklenti_magazasi_panel_kapat")
            if callable(callback):
                callback()
        except Exception:
            pass


    try:
        runtime.services.reconcile()
    except Exception:
        pass


def initialize_runtime_host(root, namespace):
    global _INITIALIZED
    runtime = get_runtime()
    attach_host(root, namespace)

    if _INITIALIZED:
        return runtime.status()
    _INITIALIZED = True

    startup_mark("runtime-host-initialize")

    def _record_callback_exception(exc_type, exc_value, exc_traceback):
        try:
            if exc_value is None:
                exc_value = RuntimeError(str(exc_type))
            record_exception(exc_value)
        except Exception:
            pass
        try:
            traceback.print_exception(exc_type, exc_value, exc_traceback)
        except Exception:
            pass

    try:
        root.report_callback_exception = _record_callback_exception
    except Exception:
        pass

    try:
        _old_excepthook = sys.excepthook
        def _neto_excepthook(exc_type, exc_value, exc_traceback):
            try:
                record_exception(exc_value)
            except Exception:
                pass
            _old_excepthook(exc_type, exc_value, exc_traceback)
        sys.excepthook = _neto_excepthook
    except Exception:
        pass

    try:
        _old_thread_hook = threading.excepthook
        def _neto_thread_hook(args):
            try:
                record_exception(args.exc_value)
            except Exception:
                pass
            _old_thread_hook(args)
        threading.excepthook = _neto_thread_hook
    except Exception:
        pass

    try:
        register_main_services(root, namespace)
    except Exception as exc:
        startup_mark("service-register-error", exc)

    try:
        bind_command_palette(root, namespace)
    except Exception as exc:
        startup_mark("command-palette-bind-error", exc)

    try:
        root.bind(
            "<<NetoProfileChanged>>",
            lambda _event: _apply_profile_ui_state(root, namespace),
            add="+",
        )
        _apply_profile_ui_state(root, namespace)
        startup_mark("profile-ui-enforcement-bound")
    except Exception as exc:
        startup_mark("profile-ui-enforcement-error", exc)

    try:
        schedule_enabled_services(root)
    except Exception as exc:
        startup_mark("service-schedule-error", exc)

    if runtime.safe_mode:
        def show_notice():
            try:
                messagebox.showwarning(
                    "Neto Güvenli Mod",
                    "Neto önceki açılışlarda düzgün kapanmadığı için Zorla Hızlı "
                    "profilde başlatıldı.\n\nAyarlar > Sistem bölümünden çökme "
                    "sayacını inceleyebilir veya temizleyebilirsin.",
                    parent=root,
                )
            except Exception:
                pass

        try:
            root.after(450, show_notice)
        except Exception:
            pass

    return runtime.status()


def mark_runtime_healthy():
    try:
        mark_healthy()
        return True
    except Exception:
        return False


def runtime_feature(feature):
    return feature_enabled(feature)


def animation_enabled():
    return feature_enabled("ui_animations")


def startup_animation_enabled():
    return feature_enabled("startup_animation")


def startup_sound_enabled():
    return feature_enabled("startup_sound")
