from __future__ import annotations

import importlib
import threading
from typing import Any
from pathlib import Path

from neto_runtime_core import get_runtime


def _call_if(namespace, name, *args, **kwargs):
    value = namespace.get(name) if isinstance(namespace, dict) else None
    if callable(value):
        return value(*args, **kwargs)
    return None


def _root_after(runtime, callback, delay=0):
    root = runtime.root
    if root is None:
        return callback()
    try:
        return root.after(max(0, int(delay)), callback)
    except Exception:
        return callback()


def register_main_services(root, namespace):
    runtime = get_runtime()
    runtime.attach_host(root, namespace)
    ns = namespace

    def start_now_playing():
        callback = ns.get("now_playing_safe_start")
        if not callable(callback):
            raise RuntimeError("now_playing_safe_start bulunamadı")
        _root_after(runtime, callback, 0)

    def stop_now_playing():
        stop_event = ns.get("now_playing_monitor_stop")
        try:
            if stop_event is not None:
                stop_event.set()
        except Exception:
            pass

        for job_name in (
            "now_playing_ui_pump_job",
            "now_playing_canvas_job",
            "now_playing_countdown_job",
            "now_playing_vinyl_job",
        ):
            job = ns.get(job_name)
            try:
                if job and root is not None:
                    root.after_cancel(job)
            except Exception:
                pass
            ns[job_name] = None

        _call_if(ns, "now_playing_overlay_kapat")

        try:
            module = importlib.import_module("neto_now_playing")
            for name in ("stop_monitor", "stop_watcher", "shutdown"):
                callback = getattr(module, name, None)
                if callable(callback):
                    callback()
                    break
        except Exception:
            pass

    def start_android():
        callback = ns.get("_neto_android_watch_deferred")
        if callable(callback):
            callback()
            return

        module = importlib.import_module("neto_android_device")
        starter = getattr(module, "start_android_crash_watch", None)
        if not callable(starter):
            raise RuntimeError("Android izleyici başlangıç fonksiyonu bulunamadı")
        starter(lambda *_args, **_kwargs: None, interval=8)

    def stop_android():
        try:
            module = importlib.import_module("neto_android_device")
        except Exception:
            return
        for name in (
            "stop_android_crash_watch",
            "stop_crash_watch",
            "shutdown",
            "stop",
        ):
            callback = getattr(module, name, None)
            if callable(callback):
                callback()
                return

    def start_updater():
        callback = ns.get("_neto_start_update_services")
        if callable(callback):
            callback()
            return
        updater = importlib.import_module("neto_update_ui")
        scheduler = getattr(updater, "schedule_startup_check", None)
        if not callable(scheduler):
            raise RuntimeError("Güncelleme zamanlayıcısı bulunamadı")
        scheduler(root, notify_callback=ns.get("animasyonlu_yazi"))

    def start_live():
        if not runtime.feature_enabled("live_mode"):
            return
        data_loader = ns.get("veri_yukle")
        should_start = False
        if callable(data_loader):
            try:
                data = data_loader()
                if isinstance(data, dict):
                    should_start = bool(
                        data.get("start_live_mode_on_launch")
                        or data.get("live_mode_otomatik_baslat")
                    )
            except Exception:
                should_start = False
        if should_start:
            callback = ns.get("inline_live_start")
            if callable(callback):
                _root_after(runtime, callback, 0)

    def stop_live():
        _call_if(ns, "live_mode_durdur")
        _call_if(ns, "live_panel_kapat_ve_durdur")

    def start_local_api():
        callback = ns.get("sunucuyu_arka_planda_baslat")
        if not callable(callback):
            raise RuntimeError("Yerel API başlangıç fonksiyonu bulunamadı")
        thread = threading.Thread(
            target=callback,
            daemon=True,
            name="NetOpsLocalAPI",
        )
        thread.start()

    def start_model_preload():
        callback = ns.get("_neto_model_adini_gec_yukle")
        if callable(callback):
            callback()

    def start_linux_bridge():
        callback = ns.get("linux_bridge_safe_start")
        if callable(callback):
            callback()
            return
        module = importlib.import_module("neto_wsl_bridge")
        starter = getattr(module, "ensure_bridge_running", None)
        if not callable(starter):
            raise RuntimeError("Linux bridge başlangıç fonksiyonu bulunamadı")
        project_dir = Path(__file__).resolve().parent
        starter(project_dir=project_dir)

    def stop_linux_bridge():
        callback = ns.get("linux_bridge_safe_stop")
        if callable(callback):
            callback()
            return
        module = importlib.import_module("neto_wsl_bridge")
        stopper = getattr(module, "stop_bridge", None)
        if not callable(stopper):
            return
        stopper()

    registrations = [
        ("now_playing", "now_playing", start_now_playing, stop_now_playing, False),
        ("android", "android", start_android, stop_android, False),
        ("updater", "updater", start_updater, None, False),
        ("live_mode", "live_mode", start_live, stop_live, False),
        ("local_api", "local_api", start_local_api, None, True),
        ("linux_bridge", "linux_bridge", start_linux_bridge, stop_linux_bridge, False),
        ("model_preload", "model_preload", start_model_preload, None, False),
    ]

    for name, feature, starter, stopper, restart_required in registrations:
        try:
            runtime.services.register(
                name=name,
                feature=feature,
                starter=starter,
                stopper=stopper,
                restart_required=restart_required,
            )
        except Exception:
            pass

    return runtime.services.snapshot()


def schedule_enabled_services(root=None):
    runtime = get_runtime()
    root = root or runtime.root
    scheduled = []

    for service in runtime.services.snapshot():
        name = service["name"]
        feature = service["feature"]
        if not runtime.feature_enabled(feature):
            continue
        delay = runtime.delay_ms(feature)
        # Negative delay means available on demand but not auto-started.
        if delay < 0:
            continue

        def starter(current=name):
            runtime.services.start(current)

        if root is not None:
            try:
                root.after(max(0, int(delay)), starter)
                scheduled.append({"name": name, "delay_ms": delay})
                continue
            except Exception:
                pass
        starter()
        scheduled.append({"name": name, "delay_ms": 0})

    return scheduled


def apply_profile(profile):
    runtime = get_runtime()
    result = runtime.set_profile(profile)
    return result


def set_custom_feature(feature, enabled):
    return get_runtime().set_custom_feature(feature, enabled)


def service_snapshot():
    return get_runtime().services.snapshot()


def stop_all_services():
    return get_runtime().services.shutdown_all()
