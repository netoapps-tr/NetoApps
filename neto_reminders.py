"""Persistent, non-blocking reminders for NetOps."""

from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Optional


APP_DIR = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData/Local")) / "NetOps"
STORE_PATH = APP_DIR / "reminders.json"
DEFAULT_SOUND_NAME = "netops_reminder.wav"
REPEAT_LABELS = {
    "once": "Bir kez",
    "daily": "Her gün",
    "weekdays": "Hafta içi",
    "weekly": "Her hafta",
}


def _runtime_root() -> Path:
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root)
    return Path(__file__).resolve().parent


def default_sound_path() -> Path:
    candidates = (
        _runtime_root() / "sounds" / DEFAULT_SOUND_NAME,
        Path(__file__).resolve().parent / "sounds" / DEFAULT_SOUND_NAME,
        APP_DIR / "sounds" / DEFAULT_SOUND_NAME,
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def play_reminder_sound(path: Optional[str | Path] = None) -> bool:
    sound_path = Path(path) if path else default_sound_path()
    # Reminders persist only the bundled filename. Resolve that filename
    # against the packaged/source sound directory instead of the CWD.
    if path and sound_path.name == DEFAULT_SOUND_NAME and not sound_path.is_file():
        sound_path = default_sound_path()
    if not sound_path.is_file() or os.name != "nt":
        return False
    try:
        import winsound

        winsound.PlaySound(
            str(sound_path),
            winsound.SND_FILENAME | winsound.SND_ASYNC,
        )
        return True
    except Exception:
        return False


def parse_schedule(date_text: str, time_text: str) -> datetime:
    raw_date = str(date_text or "").strip()
    raw_time = str(time_text or "").strip()
    if len(raw_time.split(":")) == 2:
        raw_time = f"{raw_time}:00"
    return datetime.fromisoformat(f"{raw_date}T{raw_time}")


def parse_iso(value: Any) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _default_state() -> dict[str, Any]:
    return {"version": 1, "reminders": []}


class ReminderService:
    def __init__(
        self,
        on_fire: Optional[Callable[[dict[str, Any]], Any]] = None,
        interval: float = 0.8,
    ):
        self.on_fire = on_fire
        self.interval = max(0.25, float(interval))
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _read(self) -> dict[str, Any]:
        try:
            value = json.loads(STORE_PATH.read_text(encoding="utf-8"))
        except Exception:
            value = {}
        state = _default_state()
        if isinstance(value, dict):
            state.update(value)
        reminders = state.get("reminders")
        state["reminders"] = reminders if isinstance(reminders, list) else []
        return state

    def _write(self, state: dict[str, Any]) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix="reminders_", suffix=".tmp", dir=str(APP_DIR))
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

    def list_reminders(self) -> list[dict[str, Any]]:
        with self._lock:
            return copy.deepcopy(self._read().get("reminders", []))

    def add_reminder(
        self,
        title: str,
        message: str,
        scheduled_for: datetime,
        repeat: str = "once",
        sound: Optional[str] = None,
    ) -> dict[str, Any]:
        if repeat not in REPEAT_LABELS:
            raise ValueError("Geçersiz tekrar seçeneği")
        title = str(title or "Hatırlatıcı").strip() or "Hatırlatıcı"
        message = str(message or "").strip()
        if not message:
            raise ValueError("Hatırlatıcı mesajı boş bırakılamaz")
        item = {
            "id": uuid.uuid4().hex,
            "title": title,
            "message": message,
            "next_run": scheduled_for.replace(microsecond=0).isoformat(),
            "repeat": repeat,
            "enabled": True,
            "sound": str(sound or DEFAULT_SOUND_NAME),
            "created_at": time.time(),
            "last_fired_at": 0.0,
        }
        with self._lock:
            state = self._read()
            state.setdefault("reminders", []).append(item)
            self._write(state)
        return copy.deepcopy(item)

    def delete_reminder(self, reminder_id: str) -> bool:
        with self._lock:
            state = self._read()
            before = len(state["reminders"])
            state["reminders"] = [item for item in state["reminders"] if item.get("id") != reminder_id]
            changed = len(state["reminders"]) != before
            if changed:
                self._write(state)
            return changed

    def set_enabled(self, reminder_id: str, enabled: bool) -> bool:
        with self._lock:
            state = self._read()
            for item in state["reminders"]:
                if item.get("id") == reminder_id:
                    item["enabled"] = bool(enabled)
                    self._write(state)
                    return True
            return False

    @staticmethod
    def _next_run(current: datetime, repeat: str, now: datetime) -> Optional[datetime]:
        if repeat == "once":
            return None
        step = timedelta(days=1 if repeat in {"daily", "weekdays"} else 7)
        candidate = current + step
        while candidate <= now:
            candidate += step
        if repeat == "weekdays":
            while candidate.weekday() >= 5:
                candidate += timedelta(days=1)
        return candidate

    def _collect_due(self) -> list[dict[str, Any]]:
        now = datetime.now()
        due: list[dict[str, Any]] = []
        with self._lock:
            state = self._read()
            changed = False
            for item in state["reminders"]:
                if not item.get("enabled"):
                    continue
                scheduled = parse_iso(item.get("next_run"))
                if scheduled is None or scheduled > now:
                    continue
                fired = copy.deepcopy(item)
                fired["fired_at"] = now.isoformat(timespec="seconds")
                due.append(fired)
                item["last_fired_at"] = now.timestamp()
                next_run = self._next_run(scheduled, str(item.get("repeat") or "once"), now)
                if next_run is None:
                    item["enabled"] = False
                    item["next_run"] = None
                else:
                    item["next_run"] = next_run.replace(microsecond=0).isoformat()
                changed = True
            if changed:
                self._write(state)
        return due

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                due = self._collect_due()
                for item in due:
                    callback = self.on_fire
                    if callable(callback):
                        try:
                            callback(item)
                        except Exception:
                            pass
            except Exception:
                pass

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="NetOpsReminder", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.5)
        self._thread = None


__all__ = [
    "DEFAULT_SOUND_NAME",
    "REPEAT_LABELS",
    "ReminderService",
    "STORE_PATH",
    "default_sound_path",
    "parse_schedule",
    "play_reminder_sound",
]
