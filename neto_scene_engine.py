"""NetOps v1.39 scene orchestration engine.

Scenes are deliberately kept separate from the automation database.  The
engine provides a small adapter boundary so the desktop UI can connect the
existing profile and audio services without importing the main window.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

try:
    import psutil
except Exception:
    psutil = None


SCENE_SCHEMA_VERSION = 1
STORE_PATH = Path(
    os.environ.get("NETOPS_SCENE_STORE")
    or (
        Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        / "NetOps"
        / "scenes.json"
    )
)

_STORE_LOCK = threading.RLock()
_RUN_LOCK = threading.Lock()
_RUN_STATE: dict[str, Any] = {"scene_id": None, "stop": None, "started_pids": []}


class SceneError(RuntimeError):
    """Base error for scene validation and execution failures."""


class SceneValidationError(SceneError):
    pass


class SceneCancelled(SceneError):
    pass


@dataclass
class SceneAdapters:
    """Safe system integration points used by :func:`run_scene`."""

    get_profile: Callable[[], str] = lambda: "balanced"
    set_profile: Callable[[str], Any] = lambda _profile: None
    get_volume: Callable[[], Optional[int]] = lambda: None
    set_volume: Callable[[int], Any] = lambda _value: False
    get_muted: Callable[[], Optional[bool]] = lambda: None
    set_muted: Callable[[bool], Any] = lambda _value: False
    get_brightness: Callable[[], Optional[int]] = lambda: None
    set_brightness: Callable[[int], Any] = lambda _value: False
    launch_program: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    close_program: Callable[[str], Any] | None = None
    stop_started_processes: Callable[[list[int]], Any] | None = None
    run_automation: Callable[[str], Any] | None = None


@dataclass
class SceneRun:
    scene_id: str
    run_id: str
    status: str
    snapshot: dict[str, Any]
    steps: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""
    rolled_back: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "run_id": self.run_id,
            "status": self.status,
            "snapshot": copy.deepcopy(self.snapshot),
            "steps": copy.deepcopy(self.steps),
            "error": self.error,
            "rolled_back": self.rolled_back,
        }


DEFAULT_SCENES: tuple[dict[str, Any], ...] = (
    {
        "id": "work",
        "name": "Çalışma",
        "description": "Dengeli ses ve NetOps çalışma profiliyle masa başını hazırlar.",
        "icon": "WK",
        "profile": "balanced",
        "volume": {"percent": 35, "muted": False},
        "brightness": None,
        "power": "none",
    },
    {
        "id": "gaming",
        "name": "Oyun",
        "description": "Oyun profilini, daha yüksek sesi ve düşük görsel yükü etkinleştirir.",
        "icon": "GO",
        "profile": "gaming",
        "volume": {"percent": 60, "muted": False},
        "brightness": None,
        "power": "none",
    },
    {
        "id": "study",
        "name": "Ders",
        "description": "Sessiz ders akışı için odaklı profili ve ölçülü sesi seçer.",
        "icon": "OKU",
        "profile": "study",
        "volume": {"percent": 20, "muted": False},
        "brightness": None,
        "power": "none",
    },
    {
        "id": "movie",
        "name": "Film",
        "description": "Film izleme için dengeli profil ve sinema seviyesinde ses ayarı.",
        "icon": "MV",
        "profile": "balanced",
        "volume": {"percent": 45, "muted": False},
        "brightness": None,
        "power": "none",
    },
    {
        "id": "streaming",
        "name": "Yayın",
        "description": "Yayın odaklı profili ve ses akışını tek hamlede kurar.",
        "icon": "LIVE",
        "profile": "streaming",
        "volume": {"percent": 40, "muted": False},
        "brightness": None,
        "power": "none",
    },
    {
        "id": "sleep",
        "name": "Uyku",
        "description": "Sessiz profili seçer ve sesi kapatır; güç işlemi varsayılan olarak çalışmaz.",
        "icon": "ZZ",
        "profile": "quiet",
        "volume": {"percent": 0, "muted": True},
        "brightness": None,
        "power": "none",
    },
)


def _copy_default_scene(value: dict[str, Any]) -> dict[str, Any]:
    scene = copy.deepcopy(value)
    scene.update(
        {
            "version": SCENE_SCHEMA_VERSION,
            "custom": False,
            "programs_to_open": [],
            "programs_to_close": [],
            "automations": [],
            "delay_seconds": 0.25,
            "triggers": [],
            "rollback_on_failure": True,
        }
    )
    return scene


def _default_store() -> dict[str, Any]:
    return {
        "version": SCENE_SCHEMA_VERSION,
        "scenes": [_copy_default_scene(item) for item in DEFAULT_SCENES],
        "updated_at": time.time(),
    }


def _normalize_program(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        path = value.strip()
        return {"path": path, "args": [], "cwd": ""}
    if not isinstance(value, dict):
        raise SceneValidationError("Program tanımı geçersiz.")
    path = str(value.get("path", "")).strip()
    if not path:
        raise SceneValidationError("Program yolu boş bırakılamaz.")
    args = value.get("args", [])
    if isinstance(args, str):
        args = [item for item in args.splitlines() if item.strip()]
    if not isinstance(args, list):
        raise SceneValidationError("Program argümanları liste olmalıdır.")
    return {"path": path, "args": [str(item) for item in args], "cwd": str(value.get("cwd", "")).strip()}


def _normalize_trigger(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SceneValidationError("Sahne tetikleyicisi geçersiz.")
    trigger_type = str(value.get("type", "")).strip().lower()
    if trigger_type == "startup":
        return {"type": "startup", "delay_seconds": max(0, min(3600, int(value.get("delay_seconds", 5))))}
    if trigger_type == "daily":
        time_value = str(value.get("time", "23:00")).strip()
        parts = time_value.split(":", 1)
        if len(parts) != 2:
            raise SceneValidationError("Sahne saati HH:MM biçiminde olmalıdır.")
        hour, minute = int(parts[0]), int(parts[1])
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise SceneValidationError("Sahne saati geçersiz.")
        weekdays = sorted({int(item) for item in value.get("weekdays", [0, 1, 2, 3, 4, 5, 6]) if 0 <= int(item) <= 6})
        return {"type": "daily", "time": f"{hour:02d}:{minute:02d}", "weekdays": weekdays or [0, 1, 2, 3, 4, 5, 6]}
    if trigger_type == "process_open":
        process_name = str(value.get("process_name", "")).strip()
        if not process_name:
            raise SceneValidationError("Program açılışı tetikleyicisi için program adı gereklidir.")
        return {"type": "process_open", "process_name": process_name, "cooldown_seconds": max(10, min(86400, int(value.get("cooldown_seconds", 300))))}
    if trigger_type == "file_change":
        path = str(value.get("path", "")).strip()
        if not path:
            raise SceneValidationError("Dosya tetikleyicisi için yol gereklidir.")
        return {"type": "file_change", "path": path, "debounce_seconds": max(1, min(3600, int(value.get("debounce_seconds", 3))))}
    if trigger_type == "resource_threshold":
        metric = str(value.get("metric", "cpu")).lower()
        if metric not in {"cpu", "memory", "disk"}:
            raise SceneValidationError("Kaynak metriği cpu, memory veya disk olmalıdır.")
        return {"type": "resource_threshold", "metric": metric, "operator": str(value.get("operator", ">=")), "threshold": max(0, min(100, float(value.get("threshold", 85)))), "sustain_seconds": max(1, min(3600, int(value.get("sustain_seconds", 10)))), "cooldown_seconds": max(10, min(86400, int(value.get("cooldown_seconds", 300))))}
    raise SceneValidationError(f"Desteklenmeyen sahne tetikleyicisi: {trigger_type}")


def normalize_scene(value: dict[str, Any], *, scene_id: Optional[str] = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SceneValidationError("Sahne sözlük biçiminde olmalıdır.")
    name = str(value.get("name", "")).strip()
    if not name or len(name) > 80:
        raise SceneValidationError("Sahne adı 1-80 karakter arasında olmalıdır.")
    profile = str(value.get("profile", "balanced")).strip() or "balanced"
    volume_value = value.get("volume") or {}
    if not isinstance(volume_value, dict):
        raise SceneValidationError("Ses ayarı geçersiz.")
    percent = volume_value.get("percent")
    if percent is not None:
        percent = max(0, min(100, int(float(percent))))
    power = str(value.get("power", "none")).strip().lower()
    if power not in {"none", "display_off", "sleep", "shutdown"}:
        raise SceneValidationError("Desteklenmeyen güç ayarı.")
    brightness = value.get("brightness")
    if brightness not in (None, ""):
        brightness = max(0, min(100, int(float(brightness))))
    programs_to_open = [_normalize_program(item) for item in value.get("programs_to_open", [])]
    programs_to_close = [str(item).strip() for item in value.get("programs_to_close", []) if str(item).strip()]
    automations = [str(item).strip() for item in value.get("automations", []) if str(item).strip()]
    triggers = value.get("triggers", [])
    if not isinstance(triggers, list):
        raise SceneValidationError("Sahne tetikleyicileri liste olmalıdır.")
    normalized_triggers = [_normalize_trigger(item) for item in triggers]
    return {
        "version": SCENE_SCHEMA_VERSION,
        "id": str(scene_id or value.get("id") or uuid.uuid4().hex[:12]),
        "name": name,
        "description": str(value.get("description", "")).strip(),
        "icon": str(value.get("icon", "NET")).strip() or "NET",
        "custom": bool(value.get("custom", True)),
        "profile": profile,
        "volume": {"percent": percent, "muted": bool(volume_value.get("muted", False))},
        "brightness": brightness,
        "power": power,
        "programs_to_open": programs_to_open,
        "programs_to_close": programs_to_close,
        "automations": automations,
        "delay_seconds": max(0.0, min(30.0, float(value.get("delay_seconds", 0.25)))),
        "triggers": normalized_triggers,
        "rollback_on_failure": bool(value.get("rollback_on_failure", True)),
    }


def _read_store() -> dict[str, Any]:
    try:
        raw = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except Exception:
        raw = _default_store()
    scenes: list[dict[str, Any]] = []
    if isinstance(raw, dict) and isinstance(raw.get("scenes"), list):
        for item in raw["scenes"]:
            if not isinstance(item, dict):
                continue
            try:
                scenes.append(normalize_scene(item, scene_id=str(item.get("id") or uuid.uuid4().hex[:12])))
            except Exception:
                continue
    existing = {item["id"] for item in scenes}
    for default in _default_store()["scenes"]:
        if default["id"] not in existing:
            scenes.append(default)
    return {"version": SCENE_SCHEMA_VERSION, "scenes": scenes, "updated_at": time.time()}


def _write_store(value: dict[str, Any]) -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = STORE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, STORE_PATH)


def ensure_store() -> list[dict[str, Any]]:
    with _STORE_LOCK:
        state = _read_store()
        if not STORE_PATH.exists():
            _write_store(state)
        return copy.deepcopy(state["scenes"])


def list_scenes() -> list[dict[str, Any]]:
    return ensure_store()


def get_scene(scene_id: str) -> dict[str, Any]:
    for scene in list_scenes():
        if scene["id"] == str(scene_id):
            return scene
    raise SceneError(f"Sahne bulunamadı: {scene_id}")


def save_scene(scene: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_scene(scene)
    with _STORE_LOCK:
        state = _read_store()
        replaced = False
        for index, item in enumerate(state["scenes"]):
            if item["id"] == normalized["id"]:
                state["scenes"][index] = normalized
                replaced = True
                break
        if not replaced:
            state["scenes"].append(normalized)
        state["updated_at"] = time.time()
        _write_store(state)
    return copy.deepcopy(normalized)


def duplicate_scene(scene_id: str, name: Optional[str] = None) -> dict[str, Any]:
    source = get_scene(scene_id)
    source["id"] = uuid.uuid4().hex[:12]
    source["name"] = name or f"{source['name']} Kopya"
    source["custom"] = True
    return save_scene(source)


def delete_scene(scene_id: str) -> None:
    if str(scene_id) in {item["id"] for item in _default_store()["scenes"]}:
        raise SceneError("Hazır sahneler silinemez; kopyalayarak özelleştirebilirsin.")
    with _STORE_LOCK:
        state = _read_store()
        state["scenes"] = [item for item in state["scenes"] if item["id"] != str(scene_id)]
        _write_store(state)


def preview_scene(scene_or_id: str | dict[str, Any]) -> dict[str, Any]:
    scene = get_scene(scene_or_id) if isinstance(scene_or_id, str) else normalize_scene(scene_or_id)
    steps: list[dict[str, Any]] = []
    if scene.get("profile"):
        steps.append({"label": f"NetOps profili: {scene['profile']}", "kind": "profile", "risk": "safe"})
    volume = scene.get("volume") or {}
    if volume.get("percent") is not None:
        steps.append({"label": f"Ses seviyesi: %{volume['percent']}", "kind": "volume", "risk": "safe"})
    if "muted" in volume:
        steps.append({"label": "Sessiz modu aç" if volume["muted"] else "Sessiz modu kapat", "kind": "mute", "risk": "safe"})
    if scene.get("brightness") is not None:
        steps.append({"label": f"Ekran parlaklığı: %{scene['brightness']}", "kind": "brightness", "risk": "optional"})
    for program in scene.get("programs_to_open", []):
        steps.append({"label": f"Program aç: {program['path']}", "kind": "open_program", "risk": "safe"})
    for program in scene.get("programs_to_close", []):
        steps.append({"label": f"Programı normal kapat: {program}", "kind": "close_program", "risk": "warning"})
    for automation_id in scene.get("automations", []):
        steps.append({"label": f"Otomasyonu çalıştır: {automation_id}", "kind": "automation", "risk": "warning"})
    if scene.get("power") != "none":
        steps.append({"label": f"Güç işlemi: {scene['power']}", "kind": "power", "risk": "danger"})
    warnings = []
    if scene.get("programs_to_close"):
        warnings.append("Kapatılan programlarda kaydedilmemiş veri varsa işlem kullanıcıya bırakılır.")
    if scene.get("power") != "none":
        warnings.append("Güç işlemi ayrıca onaylanmadan çalıştırılmaz.")
    if scene.get("brightness") is not None:
        warnings.append("Parlaklık desteği olmayan cihazlarda adım güvenli biçimde atlanır.")
    return {
        "scene": scene,
        "steps": steps,
        "warnings": warnings,
        "requires_confirmation": bool(scene.get("programs_to_close") or scene.get("power") != "none"),
    }


def snapshot(adapters: SceneAdapters) -> dict[str, Any]:
    def safe_call(callback: Callable[[], Any], default: Any = None) -> Any:
        try:
            return callback()
        except Exception:
            return default

    return {
        "profile": safe_call(adapters.get_profile, "balanced"),
        "volume": safe_call(adapters.get_volume),
        "muted": safe_call(adapters.get_muted),
        "brightness": safe_call(adapters.get_brightness),
        "captured_at": time.time(),
        "started_pids": [],
    }


def _default_launch_program(program: dict[str, Any]) -> dict[str, Any]:
    path = Path(os.path.expandvars(os.path.expanduser(program["path"])))
    if not path.exists():
        raise SceneError(f"Program bulunamadı: {path}")
    args = [str(item) for item in program.get("args", [])]
    suffix = path.suffix.lower()
    if suffix in {".bat", ".cmd"} and os.name == "nt":
        command = ["cmd.exe", "/d", "/s", "/c", str(path), *args]
    else:
        command = [str(path), *args]
    process = subprocess.Popen(
        command,
        cwd=program.get("cwd") or str(path.parent),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
    )
    return {"pid": process.pid, "path": str(path)}


def _default_close_program(name: str) -> bool:
    if psutil is None:
        return False
    wanted = Path(str(name)).stem.casefold()
    for process in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            process_name = str(process.info.get("name") or "")
            command = " ".join(process.info.get("cmdline") or [])
            haystack = f"{process_name} {command}".casefold()
            if wanted and wanted in haystack and process.pid != os.getpid():
                process.terminate()
                return True
        except Exception:
            continue
    return False


def _default_stop_started_processes(pids: list[int]) -> None:
    if psutil is None:
        return
    for pid in pids:
        try:
            process = psutil.Process(int(pid))
            if process.is_running() and process.pid != os.getpid():
                process.terminate()
        except Exception:
            continue


def _execute_power(power: str) -> bool:
    if power == "display_off" and os.name == "nt":
        import ctypes

        ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)
        return True
    if power == "sleep":
        if os.name == "nt":
            subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return True
        return False
    if power == "shutdown":
        if os.name == "nt":
            subprocess.Popen(["shutdown.exe", "/s", "/t", "1"], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return True
        return False
    return True


def default_adapters() -> SceneAdapters:
    try:
        from neto_user_profiles import apply_profile, get_active_profile
    except Exception:
        apply_profile = lambda _profile, **_kwargs: None
        get_active_profile = lambda: "balanced"
    try:
        from neto_automation_core import run_in_subprocess
    except Exception:
        run_in_subprocess = None
    return SceneAdapters(
        get_profile=get_active_profile,
        set_profile=lambda profile: apply_profile(profile, source="scene"),
        launch_program=_default_launch_program,
        close_program=_default_close_program,
        stop_started_processes=_default_stop_started_processes,
        run_automation=(lambda automation_id: run_in_subprocess(automation_id, {"type": "scene"})) if run_in_subprocess else None,
    )


def _wait_or_cancel(stop_event: threading.Event, seconds: float) -> None:
    if seconds <= 0:
        return
    if stop_event.wait(seconds):
        raise SceneCancelled("Sahne kullanıcı tarafından durduruldu.")


def restore_snapshot(saved: dict[str, Any], adapters: SceneAdapters) -> list[str]:
    errors: list[str] = []
    for key, callback, value in (
        ("profile", adapters.set_profile, saved.get("profile")),
        ("volume", adapters.set_volume, saved.get("volume")),
        ("muted", adapters.set_muted, saved.get("muted")),
        ("brightness", adapters.set_brightness, saved.get("brightness")),
    ):
        if value is None:
            continue
        try:
            result = callback(value)
            if result is False:
                errors.append(f"{key} desteklenmiyor")
        except Exception as exc:
            errors.append(f"{key}: {exc}")
    pids = [int(item) for item in saved.get("started_pids", []) if str(item).isdigit()]
    if pids and adapters.stop_started_processes:
        try:
            adapters.stop_started_processes(pids)
        except Exception as exc:
            errors.append(f"programlar: {exc}")
    return errors


def stop_scene() -> bool:
    event = _RUN_STATE.get("stop")
    if not isinstance(event, threading.Event):
        return False
    event.set()
    return True


def scene_running() -> Optional[str]:
    return _RUN_STATE.get("scene_id")


def run_scene(
    scene_or_id: str | dict[str, Any],
    *,
    adapters: Optional[SceneAdapters] = None,
    confirm: Optional[Callable[[str], bool]] = None,
    on_progress: Optional[Callable[[dict[str, Any]], None]] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    try:
        from neto_automation_core import emergency_stop_active
        if emergency_stop_active():
            raise SceneError("NetOps acil durdurma etkin.")
    except ImportError:
        pass
    scene = get_scene(scene_or_id) if isinstance(scene_or_id, str) else normalize_scene(scene_or_id)
    plan = preview_scene(scene)
    if dry_run:
        return {"status": "preview", **plan}
    if plan["requires_confirmation"]:
        if confirm is None or not bool(confirm("Bu sahne program kapatma veya güç işlemi içeriyor.")):
            raise SceneError("Riskli sahne adımı kullanıcı tarafından onaylanmadı.")
    if not _RUN_LOCK.acquire(blocking=False):
        raise SceneError("Başka bir sahne hâlihazırda çalışıyor.")
    run_id = uuid.uuid4().hex
    stop_event = threading.Event()
    _RUN_STATE.update({"scene_id": scene["id"], "stop": stop_event, "started_pids": []})
    active_adapters = adapters or default_adapters()
    saved = snapshot(active_adapters)
    run = SceneRun(scene["id"], run_id, "running", saved)
    try:
        operations: list[tuple[str, Callable[[], Any], str]] = []
        operations.append(("Profil", lambda: active_adapters.set_profile(scene["profile"]), "profile"))
        volume = scene.get("volume") or {}
        if volume.get("percent") is not None:
            operations.append(("Ses", lambda: active_adapters.set_volume(int(volume["percent"])), "volume"))
        operations.append(("Sessiz mod", lambda: active_adapters.set_muted(bool(volume.get("muted", False))), "mute"))
        if scene.get("brightness") is not None:
            operations.append(("Parlaklık", lambda: active_adapters.set_brightness(int(scene["brightness"])), "brightness"))
        launch = active_adapters.launch_program or _default_launch_program
        for program in scene.get("programs_to_open", []):
            operations.append((f"Program aç: {program['path']}", lambda p=program: launch(p), "open_program"))
        if scene.get("programs_to_close"):
            close = active_adapters.close_program or _default_close_program
            for program in scene["programs_to_close"]:
                operations.append((f"Programı kapat: {program}", lambda p=program: close(p), "close_program"))
        if active_adapters.run_automation:
            for automation_id in scene.get("automations", []):
                operations.append((f"Otomasyon: {automation_id}", lambda a=automation_id: active_adapters.run_automation(a), "automation"))
        if scene.get("power") != "none":
            operations.append((f"Güç: {scene['power']}", lambda p=scene["power"]: _execute_power(p), "power"))

        for index, (label, callback, kind) in enumerate(operations, 1):
            if stop_event.is_set():
                raise SceneCancelled("Sahne kullanıcı tarafından durduruldu.")
            try:
                from neto_automation_core import emergency_stop_active
                if emergency_stop_active():
                    raise SceneCancelled("NetOps acil durdurma etkin.")
            except ImportError:
                pass
            item = {"index": index, "label": label, "kind": kind, "status": "running"}
            run.steps.append(item)
            _progress(on_progress, {"event": "step_started", **item})
            result = callback()
            if kind == "open_program" and isinstance(result, dict) and result.get("pid"):
                saved["started_pids"].append(int(result["pid"]))
            item["status"] = "skipped" if result is False else "done"
            _progress(on_progress, {"event": "step_completed", **item})
            _wait_or_cancel(stop_event, float(scene.get("delay_seconds", 0.25)))
        run.snapshot = saved
        run.status = "success"
        _progress(on_progress, {"event": "completed", "result": run.as_dict()})
        return run.as_dict()
    except Exception as exc:
        run.error = str(exc)
        run.status = "cancelled" if isinstance(exc, SceneCancelled) else "failed"
        if scene.get("rollback_on_failure", True):
            rollback_errors = restore_snapshot(saved, active_adapters)
            run.rolled_back = True
            if rollback_errors:
                run.error += " | Rollback: " + "; ".join(rollback_errors)
        _progress(on_progress, {"event": "failed", "result": run.as_dict()})
        return run.as_dict()
    finally:
        _RUN_STATE.update({"scene_id": None, "stop": None, "started_pids": []})
        _RUN_LOCK.release()


def _progress(callback: Optional[Callable[[dict[str, Any]], None]], payload: dict[str, Any]) -> None:
    if callback is None:
        return
    try:
        callback(payload)
    except Exception:
        pass


__all__ = [
    "DEFAULT_SCENES",
    "SCENE_SCHEMA_VERSION",
    "STORE_PATH",
    "SceneAdapters",
    "SceneCancelled",
    "SceneError",
    "SceneRun",
    "SceneValidationError",
    "delete_scene",
    "default_adapters",
    "duplicate_scene",
    "ensure_store",
    "get_scene",
    "list_scenes",
    "normalize_scene",
    "preview_scene",
    "restore_snapshot",
    "run_scene",
    "save_scene",
    "scene_running",
    "snapshot",
    "stop_scene",
]
