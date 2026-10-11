from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
import traceback
from pathlib import Path
from typing import Any

from neto_automation_core import (
    WORKER_PID_PATH,
    WORKER_STATE_PATH,
    automation_locked,
    atomic_write_json,
    compare_threshold,
    current_profile,
    emergency_stop_active,
    execute_automation,
    fingerprint_path,
    get_automation,
    get_meta,
    internet_available,
    list_automations,
    log_event,
    mark_interrupted_runs,
    mark_trigger_queued,
    next_daily_timestamp,
    profile_allows_scheduler,
    process_name_running,
    resource_value,
    run_in_subprocess,
    set_meta,
    utc_ts,
)


POLL_SECONDS = 2.0
_STOP = False
_SESSION_ID = f"{os.getpid()}-{int(time.time())}"


class WorkerInstanceLock:
    def __init__(self):
        self.path = WORKER_PID_PATH.with_suffix(".lock")
        self.handle = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+b")
        try:
            if os.name == "nt":
                import msvcrt
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.handle.seek(0)
            self.handle.truncate()
            self.handle.write(str(os.getpid()).encode("ascii"))
            self.handle.flush()
            return True
        except Exception:
            try:
                self.handle.close()
            except Exception:
                pass
            self.handle = None
            return False

    def release(self) -> None:
        if self.handle is None:
            return
        try:
            if os.name == "nt":
                import msvcrt
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            self.handle.close()
        except Exception:
            pass
        self.handle = None


def _signal_handler(_signum, _frame):
    global _STOP
    _STOP = True


for _name in ("SIGTERM", "SIGINT"):
    if hasattr(signal, _name):
        signal.signal(getattr(signal, _name), _signal_handler)


def _write_state(**extra: Any) -> None:
    value = {
        "pid": os.getpid(),
        "session_id": _SESSION_ID,
        "heartbeat": utc_ts(),
        "profile": current_profile(),
        "mode": "daemon",
        **extra,
    }
    atomic_write_json(WORKER_STATE_PATH, value)
    try:
        WORKER_PID_PATH.write_text(str(os.getpid()), encoding="utf-8")
    except Exception:
        pass


def _trigger_state_key(automation_id: str) -> str:
    return f"automation_trigger_state:{automation_id}"


def _scene_trigger_state_key(scene_id: str, index: int) -> str:
    return f"scene_trigger_state:{scene_id}:{index}"


def _schedule_interval(automation, now: float) -> bool:
    next_run = automation.next_run_at
    return next_run is None or now >= float(next_run)


def _schedule_daily(automation, now: float) -> bool:
    next_run = automation.next_run_at
    return next_run is not None and now >= float(next_run)


def _schedule_startup(automation, now: float) -> bool:
    key = _trigger_state_key(automation.id)
    state = get_meta(key, {})
    if state.get("session_id") == _SESSION_ID:
        return False
    ready_at = float(state.get("ready_at") or (now + int(automation.trigger.get("delay_seconds", 0))))
    if "ready_at" not in state:
        set_meta(key, {"session_id": None, "ready_at": ready_at})
    if now < ready_at:
        return False
    set_meta(key, {"session_id": _SESSION_ID, "ready_at": ready_at, "fired_at": now})
    return True


def _schedule_process_open(automation, now: float) -> bool:
    key = _trigger_state_key(automation.id)
    state = get_meta(key, {})
    running = process_name_running(automation.trigger.get("process_name", ""))
    previous = bool(state.get("running"))
    last_fired = float(state.get("last_fired") or 0)
    cooldown = int(automation.trigger.get("cooldown_seconds", 300))
    set_meta(key, {"running": running, "checked_at": now, "last_fired": last_fired})
    if not running or previous or now - last_fired < cooldown:
        return False
    set_meta(key, {"running": True, "checked_at": now, "last_fired": now})
    return True


def _schedule_file_change(automation, now: float) -> bool:
    key = _trigger_state_key(automation.id)
    state = get_meta(key, {})
    path = Path(automation.trigger["path"])
    fingerprint = fingerprint_path(path, bool(automation.trigger.get("recursive", True)))
    previous = state.get("fingerprint")
    changed_at = float(state.get("changed_at") or 0)
    debounce = int(automation.trigger.get("debounce_seconds", 3))

    if previous is None:
        set_meta(key, {"fingerprint": fingerprint, "changed_at": 0, "last_fired": 0})
        return False

    if fingerprint != previous:
        set_meta(
            key,
            {
                "fingerprint": fingerprint,
                "changed_at": now,
                "last_fired": state.get("last_fired", 0),
            },
        )
        return False

    last_fired = float(state.get("last_fired") or 0)
    if changed_at and now - changed_at >= debounce and changed_at > last_fired:
        set_meta(
            key,
            {
                "fingerprint": fingerprint,
                "changed_at": changed_at,
                "last_fired": now,
            },
        )
        return True
    return False


def _schedule_internet_online(automation, now: float) -> bool:
    key = _trigger_state_key(automation.id)
    state = get_meta(key, {})
    online = internet_available(
        automation.trigger.get("host", "1.1.1.1"),
        int(automation.trigger.get("port", 53)),
        float(automation.trigger.get("timeout_seconds", 3)),
    )
    previous = state.get("online")
    set_meta(key, {"online": online, "checked_at": now})
    return previous is False and online is True


def _schedule_resource_threshold(automation, now: float) -> bool:
    key = _trigger_state_key(automation.id)
    state = get_meta(key, {})
    trigger = automation.trigger
    value = resource_value(trigger["metric"], trigger.get("path", "C:\\"))
    matched = compare_threshold(value, trigger["operator"], float(trigger["threshold"]))
    active_since = float(state.get("active_since") or 0)
    last_fired = float(state.get("last_fired") or 0)
    cooldown = int(trigger.get("cooldown_seconds", 300))
    sustain = int(trigger.get("sustain_seconds", 10))

    if not matched:
        set_meta(key, {"active_since": 0, "last_fired": last_fired, "last_value": value})
        return False

    if active_since <= 0:
        set_meta(key, {"active_since": now, "last_fired": last_fired, "last_value": value})
        return False

    if now - active_since < sustain:
        set_meta(key, {"active_since": active_since, "last_fired": last_fired, "last_value": value})
        return False

    if now - last_fired < cooldown:
        return False

    set_meta(key, {"active_since": active_since, "last_fired": now, "last_value": value})
    return True


def should_fire(automation, now: float) -> bool:
    if not automation.enabled:
        return False
    trigger_type = automation.trigger_type
    if trigger_type == "manual":
        return False
    if trigger_type == "interval":
        return _schedule_interval(automation, now)
    if trigger_type == "daily":
        return _schedule_daily(automation, now)
    if trigger_type == "startup":
        return _schedule_startup(automation, now)
    if trigger_type == "process_open":
        return _schedule_process_open(automation, now)
    if trigger_type == "file_change":
        return _schedule_file_change(automation, now)
    if trigger_type == "internet_online":
        return _schedule_internet_online(automation, now)
    if trigger_type == "resource_threshold":
        return _schedule_resource_threshold(automation, now)
    return False


def _cooldown_allows(automation, now: float) -> bool:
    cooldown = int(automation.policy.get("cooldown_seconds", 0))
    return not automation.last_run_at or now - float(automation.last_run_at) >= cooldown


def _run_scheduled(automation, now: float) -> None:
    if automation_locked(automation.id):
        return
    trigger_info = {
        "type": automation.trigger_type,
        "scheduled_at": now,
        "worker_session": _SESSION_ID,
    }
    try:
        mark_trigger_queued(automation, now)
        run_in_subprocess(automation.id, trigger_info)
        log_event(
            level="INFO",
            message="Otomasyon worker tarafından kuyruğa alındı.",
            automation_id=automation.id,
            data=trigger_info,
        )
    except Exception as exc:
        log_event(
            level="ERROR",
            message=f"Otomasyon başlatılamadı: {exc}",
            automation_id=automation.id,
            data={"traceback": traceback.format_exc()},
        )


def _scene_trigger_should_fire(scene: dict[str, Any], index: int, trigger: dict[str, Any], now: float) -> bool:
    key = _scene_trigger_state_key(scene["id"], index)
    state = get_meta(key, {})
    trigger_type = trigger.get("type")
    if trigger_type == "startup":
        if state.get("session_id") == _SESSION_ID:
            return False
        ready_at = float(state.get("ready_at") or now + int(trigger.get("delay_seconds", 0)))
        if now < ready_at:
            set_meta(key, {"ready_at": ready_at, "session_id": None})
            return False
        set_meta(key, {"ready_at": ready_at, "session_id": _SESSION_ID, "fired_at": now})
        return True
    if trigger_type == "daily":
        next_run = state.get("next_run")
        if next_run is None:
            next_run = next_daily_timestamp(trigger, now - 86400)
            set_meta(key, {"next_run": next_run})
            return False
        if now < float(next_run):
            return False
        set_meta(key, {"next_run": next_daily_timestamp(trigger, now)})
        return True
    if trigger_type == "process_open":
        running = process_name_running(trigger.get("process_name", ""))
        previous = bool(state.get("running"))
        last_fired = float(state.get("last_fired") or 0)
        cooldown = int(trigger.get("cooldown_seconds", 300))
        set_meta(key, {"running": running, "last_fired": last_fired, "checked_at": now})
        if not running or previous or now - last_fired < cooldown:
            return False
        set_meta(key, {"running": True, "last_fired": now, "checked_at": now})
        return True
    if trigger_type == "file_change":
        path = Path(trigger.get("path", ""))
        fingerprint = fingerprint_path(path)
        previous = state.get("fingerprint")
        changed_at = float(state.get("changed_at") or 0)
        debounce = int(trigger.get("debounce_seconds", 3))
        if previous is None:
            set_meta(key, {"fingerprint": fingerprint, "changed_at": 0, "last_fired": 0})
            return False
        if fingerprint != previous:
            set_meta(key, {"fingerprint": fingerprint, "changed_at": now, "last_fired": state.get("last_fired", 0)})
            return False
        if changed_at and now - changed_at >= debounce and changed_at > float(state.get("last_fired") or 0):
            set_meta(key, {"fingerprint": fingerprint, "changed_at": changed_at, "last_fired": now})
            return True
        return False
    if trigger_type == "resource_threshold":
        value = resource_value(trigger.get("metric", "cpu"), trigger.get("path", "C:\\"))
        matched = compare_threshold(value, trigger.get("operator", ">="), float(trigger.get("threshold", 85)))
        active_since = float(state.get("active_since") or 0)
        last_fired = float(state.get("last_fired") or 0)
        if not matched:
            set_meta(key, {"active_since": 0, "last_fired": last_fired})
            return False
        if active_since <= 0:
            set_meta(key, {"active_since": now, "last_fired": last_fired})
            return False
        if now - active_since < int(trigger.get("sustain_seconds", 10)) or now - last_fired < int(trigger.get("cooldown_seconds", 300)):
            return False
        set_meta(key, {"active_since": active_since, "last_fired": now})
        return True
    return False


def _run_scheduled_scene(scene: dict[str, Any], trigger_info: dict[str, Any]) -> None:
    try:
        from neto_scene_engine import run_scene

        result = run_scene(scene["id"], confirm=lambda _message: False)
        log_event(
            level="INFO" if result.get("status") == "success" else "WARNING",
            message=f"Sahne tetikleyicisi: {scene.get('name', scene['id'])} · {result.get('status')}",
            data={"scene_id": scene["id"], "trigger": trigger_info, "result": result},
        )
    except Exception as exc:
        log_event(level="ERROR", message=f"Sahne başlatılamadı: {exc}", data={"scene_id": scene.get("id"), "trigger": trigger_info, "traceback": traceback.format_exc()})
def daemon_loop() -> int:
    instance_lock = WorkerInstanceLock()
    if not instance_lock.acquire():
        return 0
    if not profile_allows_scheduler():
        _write_state(alive=False, reason="profile_blocked")
        instance_lock.release()
        return 0

    repaired = mark_interrupted_runs()
    _write_state(alive=True, started_at=utc_ts(), repaired_runs=repaired)
    log_event(level="INFO", message="Otomasyon worker başladı.")

    while not _STOP:
        now = utc_ts()
        if emergency_stop_active():
            _write_state(alive=True, emergency_stop=True)
            time.sleep(POLL_SECONDS)
            continue
        try:
            from neto_scene_engine import list_scenes

            scenes = list_scenes()
            _write_state(alive=True, automation_count=len(list_automations()), scene_count=len(scenes))
            for scene in scenes:
                for index, trigger in enumerate(scene.get("triggers", [])):
                    if _scene_trigger_should_fire(scene, index, trigger, now):
                        _run_scheduled_scene(scene, {"type": trigger.get("type"), "scheduled_at": now, "worker_session": _SESSION_ID})
            for automation in list_automations():
                if not automation.enabled or not _cooldown_allows(automation, now):
                    continue
                try:
                    if should_fire(automation, now):
                        _run_scheduled(automation, now)
                except Exception as exc:
                    log_event(
                        level="ERROR",
                        message=f"Tetikleyici denetimi başarısız: {exc}",
                        automation_id=automation.id,
                        data={"traceback": traceback.format_exc()},
                    )
        except Exception as exc:
            log_event(
                level="ERROR",
                message=f"Worker döngüsü hatası: {exc}",
                data={"traceback": traceback.format_exc()},
            )
        for _ in range(int(POLL_SECONDS * 10)):
            if _STOP:
                break
            time.sleep(0.1)

    _write_state(alive=False, stopped_at=utc_ts())
    log_event(level="INFO", message="Otomasyon worker durdu.")
    instance_lock.release()
    return 0


def run_once(automation_id: str, trigger_json: str) -> int:
    try:
        trigger_info = json.loads(trigger_json) if trigger_json else {"type": "manual"}
    except Exception:
        trigger_info = {"type": "manual"}
    try:
        execute_automation(automation_id, trigger_info=trigger_info)
        return 0
    except Exception as exc:
        print(f"[NETO_AUTOMATION_RUN_ERROR] {exc}", file=sys.stderr, flush=True)
        traceback.print_exc()
        return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument("--run")
    parser.add_argument("--trigger-json", default="{}")
    args = parser.parse_args()
    if args.run:
        return run_once(args.run, args.trigger_json)
    return daemon_loop()


if __name__ == "__main__":
    raise SystemExit(main())
