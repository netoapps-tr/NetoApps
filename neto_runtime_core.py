from __future__ import annotations

import copy
import importlib
import json
import os
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional


APP_DIR = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData/Local")) / "NetoAssistant"
RUNTIME_DIR = APP_DIR / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_PATH = RUNTIME_DIR / "runtime_config.json"
STARTUP_HISTORY_PATH = RUNTIME_DIR / "startup_history.json"
SESSION_MARKER_PATH = RUNTIME_DIR / "active_session.json"
CRASH_STATE_PATH = RUNTIME_DIR / "crash_state.json"
TASK_HISTORY_PATH = RUNTIME_DIR / "task_history.json"
PERMISSION_PATH = RUNTIME_DIR / "permissions.json"

PROFILE_LABELS = {
    "force_fast": {"tr": "Zorla Hızlı", "en": "Forced Fast"},
    "fast": {"tr": "Hızlı", "en": "Fast"},
    "balanced": {"tr": "Dengeli", "en": "Balanced"},
    "full": {"tr": "Tam", "en": "Full"},
    "custom": {"tr": "Özel", "en": "Custom"},
}

FEATURE_METADATA = {'chat_core': {'restart': False, 'label_tr': 'Ana sohbet', 'label_en': 'Core chat'},
 'chat_history': {'restart': False, 'label_tr': 'Sohbet geçmişi', 'label_en': 'Chat history'},
 'extension_store': {'restart': False,
                     'label_tr': 'Eklenti Mağazası',
                     'label_en': 'Extension Store'},
 'agent': {'restart': False, 'label_tr': 'NetOps Agent', 'label_en': 'NetOps Agent'},
 'now_playing': {'restart': True, 'label_tr': 'Şimdi Çalıyor', 'label_en': 'Now Playing'},
 'android': {'restart': True, 'label_tr': 'Android izleyicisi', 'label_en': 'Android watcher'},
 'live_mode': {'restart': True, 'label_tr': 'Live Mode', 'label_en': 'Live Mode'},
 'updater': {'restart': False, 'label_tr': 'Otomatik güncelleme', 'label_en': 'Automatic updater'},
 'local_api': {'restart': True, 'label_tr': 'Yerel API', 'label_en': 'Local API'},
 'linux_bridge': {'restart': False, 'label_tr': 'Linux köprüsü (WSL)', 'label_en': 'Linux bridge (WSL)'},
 'startup_animation': {'restart': True,
                       'label_tr': 'Açılış animasyonu',
                       'label_en': 'Startup animation'},
 'ui_animations': {'restart': False,
                   'label_tr': 'Arayüz animasyonları',
                   'label_en': 'UI animations'},
 'startup_sound': {'restart': True, 'label_tr': 'Açılış sesi', 'label_en': 'Startup sound'},
 'model_preload': {'restart': True,
                   'label_tr': 'Modeli önceden hazırla',
                   'label_en': 'Preload model'},
 'plugin_scan': {'restart': True,
                 'label_tr': 'Tam plugin taraması',
                 'label_en': 'Full plugin scan'},
 'system_tray': {'restart': True, 'label_tr': 'Sistem tepsisi', 'label_en': 'System tray'},
 'diagnostics': {'restart': False,
                 'label_tr': 'Ayrıntılı teşhis',
                 'label_en': 'Detailed diagnostics'},
 'desktop_automation': {'restart': True,
                        'label_tr': 'Masaüstü otomasyonu',
                        'label_en': 'Desktop automation'},
 'audio_stack': {'restart': True, 'label_tr': 'Ses modülleri', 'label_en': 'Audio stack'},
 'volume_control': {'restart': True,
                    'label_tr': 'Sistem ses kontrolü',
                    'label_en': 'System volume control'}}

PROFILE_FEATURES = {'force_fast': {'chat_core': True,
                'chat_history': True,
                'extension_store': False,
                'agent': True,
                'now_playing': False,
                'android': False,
                'live_mode': False,
                'updater': False,
                'local_api': False,
                'linux_bridge': False,
                'startup_animation': False,
                'ui_animations': False,
                'startup_sound': False,
                'model_preload': False,
                'plugin_scan': False,
                'system_tray': False,
                'diagnostics': False,
                'desktop_automation': False,
                'audio_stack': False,
                'volume_control': False},
 'fast': {'chat_core': True,
          'chat_history': True,
          'extension_store': False,
          'agent': True,
          'now_playing': True,
          'android': False,
          'live_mode': True,
          'updater': True,
          'local_api': False,
          'linux_bridge': False,
          'startup_animation': False,
          'ui_animations': False,
          'startup_sound': False,
          'model_preload': False,
          'plugin_scan': False,
          'system_tray': True,
          'diagnostics': False,
          'desktop_automation': True,
          'audio_stack': True,
          'volume_control': False},
 'balanced': {'chat_core': True,
              'chat_history': True,
              'extension_store': True,
              'agent': True,
              'now_playing': True,
              'android': True,
              'live_mode': True,
              'updater': True,
              'local_api': False,
              'linux_bridge': False,
              'startup_animation': True,
              'ui_animations': True,
              'startup_sound': True,
              'model_preload': False,
              'plugin_scan': True,
              'system_tray': True,
              'diagnostics': False,
              'desktop_automation': True,
              'audio_stack': True,
              'volume_control': True},
 'full': {'chat_core': True,
          'chat_history': True,
          'extension_store': True,
          'agent': True,
          'now_playing': True,
          'android': True,
          'live_mode': True,
          'updater': True,
          'local_api': True,
          'linux_bridge': False,
          'startup_animation': True,
          'ui_animations': True,
          'startup_sound': True,
          'model_preload': True,
          'plugin_scan': True,
          'system_tray': True,
          'diagnostics': True,
          'desktop_automation': True,
          'audio_stack': True,
          'volume_control': True}}

PROFILE_DELAYS_MS = {
    "force_fast": {
        "updater": 60000,
        "now_playing": 0,
        "android": 0,
        "live_mode": 0,
        "model_preload": 0,
    },
    "fast": {
        "updater": 45000,
        "now_playing": -1,
        "android": 0,
        "live_mode": 0,
        "model_preload": 0,
    },
    "balanced": {
        "updater": 12000,
        "now_playing": 7000,
        "android": 12000,
        "live_mode": 9000,
        "model_preload": 15000,
    },
    "full": {
        "updater": 4000,
        "now_playing": 3500,
        "android": 6500,
        "live_mode": 5000,
        "model_preload": 8000,
    },
}

PERMISSION_KEYS = {
    "file_read": {"tr": "Dosya okuma", "en": "Read files"},
    "file_write": {"tr": "Dosya değiştirme", "en": "Modify files"},
    "process_run": {"tr": "Komut çalıştırma", "en": "Run commands"},
    "program_open": {"tr": "Program açma", "en": "Open programs"},
    "program_close": {"tr": "Program kapatma", "en": "Close programs"},
    "input_control": {"tr": "Klavye ve fare kontrolü", "en": "Keyboard and mouse control"},
    "microphone": {"tr": "Mikrofon", "en": "Microphone"},
    "camera": {"tr": "Kamera", "en": "Camera"},
    "android_adb": {"tr": "Android ADB", "en": "Android ADB"},
    "network": {"tr": "Ağ erişimi", "en": "Network access"},
}

PERMISSION_PROFILES = {
    "restricted": {
        "file_read": "ask",
        "file_write": "deny",
        "process_run": "deny",
        "program_open": "ask",
        "program_close": "deny",
        "input_control": "deny",
        "microphone": "ask",
        "camera": "deny",
        "android_adb": "deny",
        "network": "ask",
    },
    "balanced": {
        "file_read": "allow",
        "file_write": "ask",
        "process_run": "ask",
        "program_open": "allow",
        "program_close": "ask",
        "input_control": "ask",
        "microphone": "ask",
        "camera": "deny",
        "android_adb": "ask",
        "network": "allow",
    },
    "full": {key: "allow" for key in PERMISSION_KEYS},
}


class AtomicJSONStore:
    def __init__(self, path: Path, defaults: Any):
        self.path = Path(path)
        self.defaults = copy.deepcopy(defaults)
        self.lock = threading.RLock()

    def read(self):
        with self.lock:
            try:
                value = json.loads(self.path.read_text(encoding="utf-8"))
                return value
            except Exception:
                return copy.deepcopy(self.defaults)

    def write(self, value):
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix(self.path.suffix + ".tmp")
            temp.write_text(
                json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temp, self.path)


class RuntimeConfig:
    DEFAULTS = {
        "profile": "balanced",
        "custom_features": copy.deepcopy(PROFILE_FEATURES["balanced"]),
        "last_profile_change": 0.0,
        "safe_mode_override": False,
    }

    def __init__(self):
        self.store = AtomicJSONStore(CONFIG_PATH, self.DEFAULTS)
        self.lock = threading.RLock()
        self.data = self._normalize(self.store.read())

    def _normalize(self, value):
        data = copy.deepcopy(self.DEFAULTS)
        if isinstance(value, dict):
            data.update(value)
        profile = str(data.get("profile") or "balanced")
        if profile not in {"force_fast", "fast", "balanced", "full", "custom"}:
            profile = "balanced"
        data["profile"] = profile

        custom = copy.deepcopy(PROFILE_FEATURES["balanced"])
        raw_custom = data.get("custom_features")
        if isinstance(raw_custom, dict):
            for key in FEATURE_METADATA:
                if key in raw_custom:
                    custom[key] = bool(raw_custom[key])
        data["custom_features"] = custom
        return data

    def reload(self):
        with self.lock:
            self.data = self._normalize(self.store.read())
            return copy.deepcopy(self.data)

    def save(self):
        with self.lock:
            self.store.write(self.data)

    @property
    def profile(self):
        return str(self.data.get("profile") or "balanced")

    def set_profile(self, profile):
        profile = str(profile or "balanced")
        if profile not in {"force_fast", "fast", "balanced", "full", "custom"}:
            raise ValueError(f"Geçersiz profil: {profile}")
        with self.lock:
            old = self.profile
            self.data["profile"] = profile
            self.data["last_profile_change"] = time.time()
            self.save()
        return old, profile

    def set_custom_feature(self, feature, enabled):
        if feature not in FEATURE_METADATA:
            raise KeyError(feature)
        with self.lock:
            self.data["custom_features"][feature] = bool(enabled)
            self.data["profile"] = "custom"
            self.data["last_profile_change"] = time.time()
            self.save()

    def features(self, profile=None):
        profile = str(profile or self.profile)
        if profile == "custom":
            return copy.deepcopy(self.data["custom_features"])
        return copy.deepcopy(PROFILE_FEATURES.get(profile, PROFILE_FEATURES["balanced"]))

    def enabled(self, feature):
        if feature not in FEATURE_METADATA:
            return False
        return bool(self.features().get(feature, False))

    def delay_ms(self, feature):
        profile = self.profile
        if profile == "custom":
            profile = "balanced"
        return int(PROFILE_DELAYS_MS.get(profile, {}).get(feature, 0))

    def restart_changes(self, old_profile, new_profile):
        old_features = self.features(old_profile)
        new_features = self.features(new_profile)
        changed = []
        for feature, meta in FEATURE_METADATA.items():
            if old_features.get(feature) != new_features.get(feature) and meta.get("restart"):
                changed.append(feature)
        return changed


class StartupProfiler:
    def __init__(self):
        self.started = time.perf_counter()
        self.wall_started = time.time()
        self.events = []
        self.lock = threading.RLock()
        self.finished = False

    def reset(self):
        with self.lock:
            self.started = time.perf_counter()
            self.wall_started = time.time()
            self.events = []
            self.finished = False

    def mark(self, name, detail=None):
        with self.lock:
            item = {
                "name": str(name),
                "seconds": round(time.perf_counter() - self.started, 4),
            }
            if detail is not None:
                item["detail"] = str(detail)
            self.events.append(item)
            return copy.deepcopy(item)

    def snapshot(self):
        with self.lock:
            return {
                "started_at": self.wall_started,
                "elapsed": round(time.perf_counter() - self.started, 4),
                "events": copy.deepcopy(self.events),
            }

    def finish(self, profile, status="healthy"):
        with self.lock:
            if self.finished:
                return
            self.finished = True
            record = self.snapshot()
            record["profile"] = str(profile)
            record["status"] = str(status)
            record["finished_at"] = time.time()

        store = AtomicJSONStore(STARTUP_HISTORY_PATH, [])
        history = store.read()
        if not isinstance(history, list):
            history = []
        history.append(record)
        store.write(history[-10:])

    def history(self):
        value = AtomicJSONStore(STARTUP_HISTORY_PATH, []).read()
        return value if isinstance(value, list) else []


class CrashRecovery:
    DEFAULTS = {
        "consecutive_unclean_starts": 0,
        "last_unclean_at": 0.0,
        "last_clean_at": 0.0,
        "last_healthy_at": 0.0,
        "safe_mode_recommended": False,
        "last_traceback": "",
    }

    def __init__(self):
        self.store = AtomicJSONStore(CRASH_STATE_PATH, self.DEFAULTS)
        self.state = self._normalize(self.store.read())
        self.session_id = None
        self.lock = threading.RLock()
        self.clean = False

    def _normalize(self, value):
        data = copy.deepcopy(self.DEFAULTS)
        if isinstance(value, dict):
            data.update(value)
        return data

    def begin(self):
        with self.lock:
            previous = None
            try:
                previous = json.loads(SESSION_MARKER_PATH.read_text(encoding="utf-8"))
            except Exception:
                previous = None

            if isinstance(previous, dict) and not previous.get("clean"):
                self.state["consecutive_unclean_starts"] = (
                    int(self.state.get("consecutive_unclean_starts", 0)) + 1
                )
                self.state["last_unclean_at"] = time.time()
                self.state["safe_mode_recommended"] = (
                    self.state["consecutive_unclean_starts"] >= 2
                )

            self.session_id = uuid.uuid4().hex
            marker = {
                "session_id": self.session_id,
                "pid": os.getpid(),
                "started_at": time.time(),
                "clean": False,
            }
            AtomicJSONStore(SESSION_MARKER_PATH, {}).write(marker)
            self.store.write(self.state)
            return copy.deepcopy(self.state)

    def mark_healthy(self):
        # Sağlıklı UI açılışı, önceki oturumun temiz kapandığı anlamına gelmez.
        # Sayaç yalnızca açık bir temiz kapanışta sıfırlanır.
        with self.lock:
            self.state["last_healthy_at"] = time.time()
            self.store.write(self.state)

    def mark_clean(self):
        with self.lock:
            self.clean = True
            self.state["last_clean_at"] = time.time()
            self.state["consecutive_unclean_starts"] = 0
            self.state["safe_mode_recommended"] = False
            self.store.write(self.state)
            try:
                marker = {
                    "session_id": self.session_id,
                    "pid": os.getpid(),
                    "finished_at": time.time(),
                    "clean": True,
                }
                AtomicJSONStore(SESSION_MARKER_PATH, {}).write(marker)
                SESSION_MARKER_PATH.unlink(missing_ok=True)
            except Exception:
                pass

    def record_exception(self, exc):
        with self.lock:
            self.state["last_traceback"] = "".join(
                traceback.format_exception(type(exc), exc, exc.__traceback__)
            )[-12000:]
            self.store.write(self.state)

    def clear(self):
        with self.lock:
            self.state = copy.deepcopy(self.DEFAULTS)
            self.store.write(self.state)
            try:
                SESSION_MARKER_PATH.unlink(missing_ok=True)
            except Exception:
                pass

    def safe_mode_needed(self):
        return bool(
            self.state.get("safe_mode_recommended")
            or os.environ.get("NETO_SAFE_MODE") == "1"
        )


class PermissionManager:
    DEFAULTS = {
        "profile": "balanced",
        "overrides": {},
        "audit": [],
    }

    def __init__(self):
        self.store = AtomicJSONStore(PERMISSION_PATH, self.DEFAULTS)
        self.lock = threading.RLock()
        self.data = self._normalize(self.store.read())

    def _normalize(self, value):
        data = copy.deepcopy(self.DEFAULTS)
        if isinstance(value, dict):
            data.update(value)
        if data.get("profile") not in PERMISSION_PROFILES:
            data["profile"] = "balanced"
        if not isinstance(data.get("overrides"), dict):
            data["overrides"] = {}
        if not isinstance(data.get("audit"), list):
            data["audit"] = []
        return data

    def save(self):
        with self.lock:
            self.store.write(self.data)

    def set_profile(self, profile):
        if profile not in PERMISSION_PROFILES:
            raise ValueError(profile)
        with self.lock:
            self.data["profile"] = profile
            self.save()

    def set(self, permission, decision):
        if permission not in PERMISSION_KEYS:
            raise KeyError(permission)
        if decision not in {"allow", "ask", "deny"}:
            raise ValueError(decision)
        with self.lock:
            self.data["overrides"][permission] = decision
            self.save()

    def decision(self, permission):
        if permission not in PERMISSION_KEYS:
            return "deny"
        override = self.data.get("overrides", {}).get(permission)
        if override in {"allow", "ask", "deny"}:
            return override
        profile = self.data.get("profile", "balanced")
        return PERMISSION_PROFILES[profile].get(permission, "deny")

    def audit(self, permission, decision, context=""):
        with self.lock:
            entry = {
                "time": time.time(),
                "permission": str(permission),
                "decision": str(decision),
                "context": str(context or ""),
            }
            audit = self.data.setdefault("audit", [])
            audit.append(entry)
            self.data["audit"] = audit[-300:]
            self.save()

    def require(self, permission, context="", ask_callback=None):
        decision = self.decision(permission)
        if decision == "allow":
            self.audit(permission, "allow", context)
            return True
        if decision == "deny":
            self.audit(permission, "deny", context)
            return False
        accepted = False
        if callable(ask_callback):
            try:
                accepted = bool(ask_callback(permission, context))
            except Exception:
                accepted = False
        self.audit(permission, "allow_once" if accepted else "deny_once", context)
        return accepted


@dataclass
class TaskRecord:
    task_id: str
    title: str
    status: str = "queued"
    progress: float = 0.0
    detail: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    cancellable: bool = True
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)

    def public(self):
        return {
            "task_id": self.task_id,
            "title": self.title,
            "status": self.status,
            "progress": round(float(self.progress), 4),
            "detail": self.detail,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "cancellable": self.cancellable,
        }


class TaskCenter:
    def __init__(self):
        self.tasks = {}
        self.lock = threading.RLock()
        self.listeners = []

    def create(self, title, cancellable=True):
        task = TaskRecord(
            task_id=uuid.uuid4().hex,
            title=str(title),
            cancellable=bool(cancellable),
        )
        with self.lock:
            self.tasks[task.task_id] = task
        self._emit()
        return task.task_id

    def update(self, task_id, **changes):
        with self.lock:
            task = self.tasks.get(task_id)
            if task is None:
                return False
            for key in ("status", "detail"):
                if key in changes:
                    setattr(task, key, str(changes[key]))
            if "progress" in changes:
                task.progress = max(0.0, min(1.0, float(changes["progress"])))
            task.updated_at = time.time()
            if task.status in {"completed", "failed", "cancelled"}:
                self._persist(task)
        self._emit()
        return True

    def cancel(self, task_id):
        with self.lock:
            task = self.tasks.get(task_id)
            if task is None or not task.cancellable:
                return False
            task.cancel_event.set()
            task.status = "cancelled"
            task.updated_at = time.time()
            self._persist(task)
        self._emit()
        return True

    def cancelled(self, task_id):
        with self.lock:
            task = self.tasks.get(task_id)
            return bool(task and task.cancel_event.is_set())

    def list(self):
        with self.lock:
            values = sorted(
                self.tasks.values(),
                key=lambda task: task.updated_at,
                reverse=True,
            )
            return [task.public() for task in values]

    def subscribe(self, listener):
        if callable(listener):
            self.listeners.append(listener)

    def _emit(self):
        snapshot = self.list()
        for listener in list(self.listeners):
            try:
                listener(snapshot)
            except Exception:
                pass

    def _persist(self, task):
        store = AtomicJSONStore(TASK_HISTORY_PATH, [])
        history = store.read()
        if not isinstance(history, list):
            history = []
        history.append(task.public())
        store.write(history[-100:])


@dataclass
class ServiceDefinition:
    name: str
    feature: str
    starter: Callable[[], Any]
    stopper: Optional[Callable[[], Any]] = None
    restart_required: bool = False
    status: str = "stopped"
    error: str = ""
    started_at: float = 0.0


class ServiceManager:
    def __init__(self, runtime):
        self.runtime = runtime
        self.services = {}
        self.lock = threading.RLock()
        self.listeners = []

    def register(
        self,
        name,
        feature,
        starter,
        stopper=None,
        restart_required=None,
    ):
        if feature not in FEATURE_METADATA:
            raise KeyError(feature)
        if not callable(starter):
            raise TypeError("starter callable olmalı")
        if restart_required is None:
            restart_required = bool(FEATURE_METADATA[feature].get("restart"))
        with self.lock:
            self.services[name] = ServiceDefinition(
                name=str(name),
                feature=str(feature),
                starter=starter,
                stopper=stopper if callable(stopper) else None,
                restart_required=bool(restart_required),
            )
        self._emit()

    def start(self, name):
        with self.lock:
            service = self.services.get(name)
            if service is None:
                return False
            if service.status in {"starting", "running"}:
                return True
            if not self.runtime.feature_enabled(service.feature):
                service.status = "disabled"
                self._emit()
                return False
            service.status = "starting"
            service.error = ""
        self._emit()
        try:
            service.starter()
            with self.lock:
                service.status = "running"
                service.started_at = time.time()
            self._emit()
            return True
        except Exception as exc:
            with self.lock:
                service.status = "failed"
                service.error = str(exc)
            self._emit()
            return False

    def stop(self, name):
        with self.lock:
            service = self.services.get(name)
            if service is None:
                return False
            if service.status in {"stopped", "disabled"}:
                return True
            if service.stopper is None:
                service.status = "restart_required"
                self._emit()
                return False
            service.status = "stopping"
        self._emit()
        try:
            service.stopper()
            with self.lock:
                service.status = "stopped"
                service.error = ""
            self._emit()
            return True
        except Exception as exc:
            with self.lock:
                service.status = "failed"
                service.error = str(exc)
            self._emit()
            return False

    def reconcile(self):
        result = {"started": [], "stopped": [], "restart_required": []}
        with self.lock:
            names = list(self.services)
        for name in names:
            service = self.services[name]
            enabled = self.runtime.feature_enabled(service.feature)
            if enabled and service.status in {"stopped", "disabled", "failed"}:
                if service.restart_required and service.status == "disabled":
                    result["restart_required"].append(name)
                elif self.start(name):
                    result["started"].append(name)
            elif not enabled and service.status in {"running", "starting"}:
                if service.restart_required and service.stopper is None:
                    service.status = "restart_required"
                    result["restart_required"].append(name)
                elif self.stop(name):
                    result["stopped"].append(name)
        self._emit()
        return result

    def shutdown_all(self):
        with self.lock:
            names = list(self.services)
        for name in reversed(names):
            try:
                self.stop(name)
            except Exception:
                pass

    def snapshot(self):
        with self.lock:
            return [
                {
                    "name": service.name,
                    "feature": service.feature,
                    "status": service.status,
                    "error": service.error,
                    "started_at": service.started_at,
                    "restart_required": service.restart_required,
                }
                for service in self.services.values()
            ]

    def subscribe(self, listener):
        if callable(listener):
            self.listeners.append(listener)

    def _emit(self):
        snapshot = self.snapshot()
        for listener in list(self.listeners):
            try:
                listener(snapshot)
            except Exception:
                pass


class LazyModule:
    def __init__(self, module_name):
        self._module_name = str(module_name)
        self._module = None
        self._lock = threading.RLock()

    def _load(self):
        with self._lock:
            if self._module is None:
                self._module = importlib.import_module(self._module_name)
            return self._module

    def __getattr__(self, name):
        return getattr(self._load(), name)


class NetoRuntime:
    def __init__(self):
        self.config = RuntimeConfig()
        self.profiler = StartupProfiler()
        self.crash = CrashRecovery()
        self.permissions = PermissionManager()
        self.tasks = TaskCenter()
        self.services = ServiceManager(self)
        self.root = None
        self.namespace = None
        self.started = False
        self.safe_mode = False
        self.healthy = False
        self.crashed = False
        self.lock = threading.RLock()

    def begin(self):
        with self.lock:
            if self.started:
                return self
            self.started = True
            self.profiler.reset()
            state = self.crash.begin()
            self.safe_mode = self.crash.safe_mode_needed()
            if self.safe_mode:
                self.config.set_profile("force_fast")
                os.environ["NETO_SAFE_MODE"] = "1"
            self.profiler.mark("runtime-core-ready", self.config.profile)
            return self

    def attach_host(self, root=None, namespace=None):
        self.root = root
        self.namespace = namespace
        self.profiler.mark("host-attached")

    def feature_enabled(self, feature):
        return self.config.enabled(feature)

    def delay_ms(self, feature):
        return self.config.delay_ms(feature)

    def _emit_profile_change(self):
        root = self.root
        if root is None:
            return
        try:
            root.event_generate("<<NetoProfileChanged>>", when="tail")
        except Exception:
            pass

    def set_profile(self, profile):
        old, new = self.config.set_profile(profile)
        restart = self.config.restart_changes(old, new)
        reconcile = self.services.reconcile()
        self._emit_profile_change()
        return {
            "old": old,
            "new": new,
            "restart_features": restart,
            "services": reconcile,
        }

    def set_custom_feature(self, feature, enabled):
        old_features = self.config.features()
        self.config.set_custom_feature(feature, enabled)
        new_features = self.config.features()
        restart = []
        if old_features.get(feature) != new_features.get(feature):
            if FEATURE_METADATA[feature].get("restart"):
                restart.append(feature)
        reconcile = self.services.reconcile()
        self._emit_profile_change()
        return {
            "feature": feature,
            "enabled": bool(enabled),
            "restart_features": restart,
            "services": reconcile,
        }

    def mark_healthy(self):
        self.healthy = True
        self.crash.mark_healthy()
        self.profiler.mark("application-healthy")
        self.profiler.finish(self.config.profile, "healthy")

    def shutdown(self):
        if self.crashed:
            return
        try:
            self.services.shutdown_all()
        finally:
            self.crash.mark_clean()
            if not self.profiler.finished:
                self.profiler.finish(self.config.profile, "clean-shutdown")

    def record_exception(self, exc):
        self.crashed = True
        try:
            self.crash.record_exception(exc)
        except Exception:
            pass
        try:
            self.profiler.mark("runtime-exception", exc)
            if not self.profiler.finished:
                self.profiler.finish(self.config.profile, "crashed")
        except Exception:
            pass

    def status(self):
        return {
            "profile": self.config.profile,
            "features": self.config.features(),
            "safe_mode": self.safe_mode,
            "crash_state": copy.deepcopy(self.crash.state),
            "services": self.services.snapshot(),
            "startup": self.profiler.snapshot(),
        }


_RUNTIME = NetoRuntime()


def get_runtime():
    return _RUNTIME


def begin_runtime():
    return _RUNTIME.begin()


def attach_host(root=None, namespace=None):
    return _RUNTIME.attach_host(root, namespace)


def feature_enabled(feature):
    return _RUNTIME.feature_enabled(feature)


def feature_delay_ms(feature):
    return _RUNTIME.delay_ms(feature)


def startup_mark(name, detail=None):
    return _RUNTIME.profiler.mark(name, detail)


def mark_healthy():
    return _RUNTIME.mark_healthy()


def clean_shutdown():
    return _RUNTIME.shutdown()


def record_exception(exc):
    return _RUNTIME.record_exception(exc)


def lazy_module(module_name):
    return LazyModule(module_name)


