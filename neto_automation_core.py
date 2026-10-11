from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.request
import uuid
import webbrowser
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

try:
    import psutil
except Exception:
    psutil = None


AUTOMATION_BUILD = "1.40.0"
APPDATA_ROOT = Path(
    os.environ.get("LOCALAPPDATA")
    or (Path.home() / "AppData" / "Local")
) / "NetoAssistant" / "automation"
DB_PATH = APPDATA_ROOT / "automation.sqlite3"
LOG_DIR = APPDATA_ROOT / "logs"
TRANSACTION_DIR = APPDATA_ROOT / "transactions"
WORKER_STATE_PATH = APPDATA_ROOT / "worker_state.json"
WORKER_PID_PATH = APPDATA_ROOT / "worker.pid"

APPDATA_ROOT.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
TRANSACTION_DIR.mkdir(parents=True, exist_ok=True)


TRIGGER_TYPES = {
    "manual",
    "interval",
    "daily",
    "startup",
    "file_change",
    "internet_online",
    "resource_threshold",
    "process_open",
}

ACTION_TYPES = {
    "notify",
    "run_program",
    "run_command",
    "open_url",
    "copy_file",
    "move_file",
    "backup_folder",
    "http_request",
    "public_api_watch",
    "wait",
    "write_text",
    "lua_script",
    "shutdown",
    "run_scene",
}

ACTION_PERMISSIONS = {
    "notify": set(),
    "run_program": {"process_run"},
    "run_command": {"process_run"},
    "open_url": {"network"},
    "copy_file": {"file_read", "file_write"},
    "move_file": {"file_read", "file_write"},
    "backup_folder": {"file_read", "file_write"},
    "http_request": {"network"},
    "public_api_watch": {"network"},
    "wait": set(),
    "write_text": {"file_write"},
    "lua_script": set(),
    "shutdown": {"process_run"},
    "run_scene": {"process_run"},
}

DANGEROUS_COMMAND_TOKENS = {
    "remove-item",
    "del ",
    "erase ",
    "format ",
    "diskpart",
    "shutdown",
    "restart-computer",
    "stop-computer",
    "reg delete",
    "rd /s",
    "rmdir /s",
    "taskkill /f",
    "bcdedit",
    "cipher /w",
}


def _ask_permission(permission: str, context: str) -> bool:
    try:
        from tkinter import messagebox

        title = "Neto Otomasyon İzni"
        message = f"{context}\n\nİstenen izin: {permission}\n\nDevam etmek ister misin?"
        return bool(messagebox.askyesno(title, message))
    except Exception:
        return False


def _require_action_permissions(action_type: str, context: dict[str, Any]) -> None:
    permissions = ACTION_PERMISSIONS.get(action_type, set())
    if not permissions:
        return
    try:
        from neto_runtime_core import get_runtime

        runtime = get_runtime()
    except Exception as exc:
        raise ActionFailed("İzin yöneticisi kullanılamıyor.") from exc
    prompt_context = f"{context.get('automation_name', 'Otomasyon')} · {action_type}"
    for permission in sorted(permissions):
        if not runtime.permissions.require(permission, context=prompt_context, ask_callback=_ask_permission):
            raise PermissionDenied(f"İzin reddedildi: {permission}")


class AutomationError(RuntimeError):
    pass


class ValidationError(AutomationError):
    pass


class ActionFailed(AutomationError):
    pass


class PermissionDenied(ActionFailed):
    pass


@dataclass(frozen=True)
class AutomationDefinition:
    id: str
    name: str
    enabled: bool
    trigger_type: str
    trigger: dict[str, Any]
    actions: list[dict[str, Any]]
    policy: dict[str, Any]
    created_at: float
    updated_at: float
    last_run_at: Optional[float]
    next_run_at: Optional[float]


@dataclass
class ActionResult:
    action_type: str
    ok: bool
    message: str
    data: dict[str, Any]
    rollback: Optional[dict[str, Any]] = None


_DB_LOCK = threading.RLock()


def utc_ts() -> float:
    return time.time()


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def json_loads(value: str | bytes | None, default: Any) -> Any:
    if value is None:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def get_connection() -> sqlite3.Connection:
    APPDATA_ROOT.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(
        DB_PATH,
        timeout=20,
        isolation_level=None,
        check_same_thread=False,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=20000")
    return connection


def initialize_database() -> None:
    with _DB_LOCK, contextlib.closing(get_connection()) as connection:
        connection.executescript(
            """
            BEGIN IMMEDIATE;
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS automations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                trigger_type TEXT NOT NULL,
                trigger_json TEXT NOT NULL,
                actions_json TEXT NOT NULL,
                policy_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                last_run_at REAL,
                next_run_at REAL
            );

            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                automation_id TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at REAL NOT NULL,
                finished_at REAL,
                trigger_json TEXT NOT NULL,
                result_json TEXT,
                error TEXT,
                pid INTEGER,
                attempt INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY(automation_id) REFERENCES automations(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                automation_id TEXT,
                ts REAL NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                data_json TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE,
                FOREIGN KEY(automation_id) REFERENCES automations(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS locks (
                automation_id TEXT PRIMARY KEY,
                owner TEXT NOT NULL,
                acquired_at REAL NOT NULL,
                heartbeat_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS automation_queue (
                id TEXT PRIMARY KEY,
                automation_id TEXT NOT NULL,
                status TEXT NOT NULL,
                trigger_json TEXT NOT NULL,
                enqueued_at REAL NOT NULL,
                started_at REAL,
                finished_at REAL,
                error TEXT,
                pid INTEGER,
                FOREIGN KEY(automation_id) REFERENCES automations(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_runs_automation_started
                ON runs(automation_id, started_at DESC);
            CREATE INDEX IF NOT EXISTS idx_events_run_ts
                ON events(run_id, ts);
            CREATE INDEX IF NOT EXISTS idx_automations_enabled
                ON automations(enabled, next_run_at);
            CREATE INDEX IF NOT EXISTS idx_automation_queue_status
                ON automation_queue(status, enqueued_at);

            INSERT INTO meta(key, value)
            VALUES('schema_version', '1')
            ON CONFLICT(key) DO NOTHING;
            UPDATE meta SET value = '2' WHERE key = 'schema_version';
            COMMIT;
            """
        )


initialize_database()


def _row_to_definition(row: sqlite3.Row) -> AutomationDefinition:
    return AutomationDefinition(
        id=str(row["id"]),
        name=str(row["name"]),
        enabled=bool(row["enabled"]),
        trigger_type=str(row["trigger_type"]),
        trigger=json_loads(row["trigger_json"], {}),
        actions=json_loads(row["actions_json"], []),
        policy=json_loads(row["policy_json"], {}),
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
        last_run_at=(
            float(row["last_run_at"])
            if row["last_run_at"] is not None
            else None
        ),
        next_run_at=(
            float(row["next_run_at"])
            if row["next_run_at"] is not None
            else None
        ),
    )


def list_automations() -> list[AutomationDefinition]:
    with contextlib.closing(get_connection()) as connection:
        rows = connection.execute(
            "SELECT * FROM automations ORDER BY updated_at DESC"
        ).fetchall()
    return [_row_to_definition(row) for row in rows]


def get_automation(automation_id: str) -> AutomationDefinition:
    with contextlib.closing(get_connection()) as connection:
        row = connection.execute(
            "SELECT * FROM automations WHERE id = ?",
            (automation_id,),
        ).fetchone()
    if row is None:
        raise AutomationError(f"Otomasyon bulunamadı: {automation_id}")
    return _row_to_definition(row)


def _default_policy(policy: Optional[dict[str, Any]]) -> dict[str, Any]:
    value = {
        "timeout_seconds": 300,
        "max_retries": 1,
        "retry_delay_seconds": 3,
        "rollback_on_failure": True,
        "allow_dangerous_commands": False,
        "continue_on_action_error": False,
        "cooldown_seconds": 0,
    }
    if isinstance(policy, dict):
        value.update(policy)
    value["timeout_seconds"] = max(5, min(int(value["timeout_seconds"]), 86400))
    value["max_retries"] = max(0, min(int(value["max_retries"]), 5))
    value["retry_delay_seconds"] = max(0, min(int(value["retry_delay_seconds"]), 3600))
    value["cooldown_seconds"] = max(0, min(int(value["cooldown_seconds"]), 86400))
    value["rollback_on_failure"] = bool(value["rollback_on_failure"])
    value["allow_dangerous_commands"] = bool(value["allow_dangerous_commands"])
    value["continue_on_action_error"] = bool(value["continue_on_action_error"])
    return value


def _require_text(mapping: dict[str, Any], key: str, label: str) -> str:
    value = str(mapping.get(key, "")).strip()
    if not value:
        raise ValidationError(f"{label} boş bırakılamaz.")
    return value


def _normalize_condition(condition: Any) -> dict[str, Any]:
    if not isinstance(condition, dict):
        raise ValidationError("İşlem koşulu sözlük biçiminde olmalıdır.")
    value = dict(condition)
    condition_type = str(value.get("type", value.get("kind", ""))).strip().lower()
    if condition_type in {"all", "any"}:
        items = value.get("conditions", [])
        if not isinstance(items, list) or not items:
            raise ValidationError("Birleşik koşul en az bir alt koşul içermelidir.")
        return {
            "type": condition_type,
            "conditions": [_normalize_condition(item) for item in items],
        }
    if condition_type == "not":
        return {"type": "not", "condition": _normalize_condition(value.get("condition", {}))}
    if condition_type == "internet_online":
        return {
            "type": condition_type,
            "host": str(value.get("host", "1.1.1.1")).strip() or "1.1.1.1",
            "port": max(1, min(65535, int(value.get("port", 53)))),
            "timeout_seconds": max(0.5, min(15.0, float(value.get("timeout_seconds", 3)))),
        }
    if condition_type == "process_running":
        process_name = _require_text(value, "process_name", "İşlem adı")
        return {"type": condition_type, "process_name": process_name}
    if condition_type == "file_exists":
        path = _require_text(value, "path", "Dosya yolu")
        return {"type": condition_type, "path": path, "exists": bool(value.get("exists", True))}
    if condition_type == "resource_threshold":
        metric = str(value.get("metric", "cpu")).strip().lower()
        if metric not in {"cpu", "memory", "disk"}:
            raise ValidationError("Koşul metriği cpu, memory veya disk olmalıdır.")
        operator = str(value.get("operator", ">=")).strip()
        if operator not in {">=", ">", "<=", "<"}:
            raise ValidationError("Koşul operatörü geçersiz.")
        return {
            "type": condition_type,
            "metric": metric,
            "operator": operator,
            "threshold": max(0.0, min(100.0, float(value.get("threshold", 85)))),
            "path": str(value.get("path", Path.home().anchor or "C:\\")).strip(),
        }
    raise ValidationError(
        "Koşul türü internet_online, process_running, file_exists, "
        "resource_threshold, all, any veya not olmalıdır."
    )


def validate_trigger(trigger_type: str, trigger: dict[str, Any]) -> dict[str, Any]:
    if trigger_type not in TRIGGER_TYPES:
        raise ValidationError(f"Desteklenmeyen tetikleyici: {trigger_type}")
    trigger = dict(trigger or {})

    if trigger_type == "manual":
        return {}

    if trigger_type == "interval":
        seconds = int(trigger.get("seconds", 300))
        if seconds < 10:
            raise ValidationError("Aralık en az 10 saniye olmalıdır.")
        return {"seconds": min(seconds, 31_536_000)}

    if trigger_type == "daily":
        value = _require_text(trigger, "time", "Saat")
        try:
            hour, minute = [int(part) for part in value.split(":", 1)]
        except Exception as exc:
            raise ValidationError("Saat HH:MM biçiminde olmalıdır.") from exc
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValidationError("Geçersiz günlük saat.")
        weekdays = trigger.get("weekdays", [0, 1, 2, 3, 4, 5, 6])
        if not isinstance(weekdays, list):
            raise ValidationError("Hafta günleri liste olmalıdır.")
        normalized = sorted({int(item) for item in weekdays if 0 <= int(item) <= 6})
        if not normalized:
            raise ValidationError("En az bir hafta günü seçilmelidir.")
        return {"time": f"{hour:02d}:{minute:02d}", "weekdays": normalized}

    if trigger_type == "startup":
        delay = max(0, min(int(trigger.get("delay_seconds", 5)), 3600))
        return {"delay_seconds": delay}

    if trigger_type == "process_open":
        process_name = _require_text(trigger, "process_name", "Program adı")
        cooldown = max(10, min(int(trigger.get("cooldown_seconds", 300)), 86400))
        return {"process_name": process_name, "cooldown_seconds": cooldown}

    if trigger_type == "file_change":
        path = _require_text(trigger, "path", "İzlenecek yol")
        debounce = max(1, min(int(trigger.get("debounce_seconds", 3)), 3600))
        recursive = bool(trigger.get("recursive", True))
        return {
            "path": str(Path(path).expanduser()),
            "recursive": recursive,
            "debounce_seconds": debounce,
        }

    if trigger_type == "internet_online":
        host = str(trigger.get("host", "1.1.1.1")).strip() or "1.1.1.1"
        port = int(trigger.get("port", 53))
        timeout = float(trigger.get("timeout_seconds", 3))
        return {
            "host": host,
            "port": max(1, min(port, 65535)),
            "timeout_seconds": max(0.5, min(timeout, 30)),
        }

    if trigger_type == "resource_threshold":
        metric = str(trigger.get("metric", "cpu")).strip().lower()
        if metric not in {"cpu", "memory", "disk"}:
            raise ValidationError("Kaynak metriği cpu, memory veya disk olmalıdır.")
        operator = str(trigger.get("operator", ">=")).strip()
        if operator not in {">=", ">", "<=", "<"}:
            raise ValidationError("Geçersiz eşik operatörü.")
        threshold = float(trigger.get("threshold", 85))
        if not 0 <= threshold <= 100:
            raise ValidationError("Kaynak eşiği 0-100 arasında olmalıdır.")
        sustain = max(1, min(int(trigger.get("sustain_seconds", 10)), 3600))
        cooldown = max(10, min(int(trigger.get("cooldown_seconds", 300)), 86400))
        path = str(trigger.get("path", Path.home().anchor or "C:\\"))
        return {
            "metric": metric,
            "operator": operator,
            "threshold": threshold,
            "sustain_seconds": sustain,
            "cooldown_seconds": cooldown,
            "path": path,
        }

    raise ValidationError("Tetikleyici doğrulanamadı.")


def _normalize_action(action: dict[str, Any], index: int) -> dict[str, Any]:
    if not isinstance(action, dict):
        raise ValidationError(f"{index + 1}. işlem sözlük olmalıdır.")
    action_type = str(action.get("type", "")).strip()
    if action_type not in ACTION_TYPES:
        raise ValidationError(f"Desteklenmeyen işlem: {action_type}")
    value = dict(action)
    value["type"] = action_type
    value["enabled"] = bool(value.get("enabled", True))
    value["timeout_seconds"] = max(1, min(int(value.get("timeout_seconds", 120)), 86400))
    value["retries"] = max(0, min(int(value.get("retries", 0)), 5))
    value["retry_delay_seconds"] = max(0, min(int(value.get("retry_delay_seconds", 2)), 3600))
    if "condition" in value and value["condition"] not in (None, "", {}):
        value["condition"] = _normalize_condition(value["condition"])
    else:
        value.pop("condition", None)

    if action_type == "notify":
        value["title"] = str(value.get("title", "Neto Otomasyon")).strip() or "Neto Otomasyon"
        value["message"] = _require_text(value, "message", "Bildirim mesajı")

    elif action_type == "run_program":
        value["path"] = _require_text(value, "path", "Program yolu")
        args = value.get("args", [])
        if isinstance(args, str):
            args = [item for item in args.splitlines() if item.strip()]
        if not isinstance(args, list):
            raise ValidationError("Program argümanları liste olmalıdır.")
        value["args"] = [str(item) for item in args]
        value["cwd"] = str(value.get("cwd", "")).strip()
        value["wait"] = bool(value.get("wait", False))

    elif action_type == "run_command":
        value["command"] = _require_text(value, "command", "Komut")
        value["cwd"] = str(value.get("cwd", "")).strip()
        value["shell"] = str(value.get("shell", "powershell" if os.name == "nt" else "sh"))

    elif action_type == "open_url":
        url = _require_text(value, "url", "URL")
        if not re_url(url):
            raise ValidationError("URL http:// veya https:// ile başlamalıdır.")
        value["url"] = url

    elif action_type in {"copy_file", "move_file"}:
        value["source"] = _require_text(value, "source", "Kaynak")
        value["destination"] = _require_text(value, "destination", "Hedef")
        value["overwrite"] = bool(value.get("overwrite", False))

    elif action_type == "backup_folder":
        value["source"] = _require_text(value, "source", "Yedeklenecek klasör")
        value["destination"] = _require_text(value, "destination", "ZIP hedefi")
        value["include_timestamp"] = bool(value.get("include_timestamp", True))

    elif action_type == "http_request":
        method = str(value.get("method", "GET")).upper()
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"}:
            raise ValidationError("Desteklenmeyen HTTP yöntemi.")
        url = _require_text(value, "url", "HTTP URL")
        if not re_url(url):
            raise ValidationError("HTTP URL geçersiz.")
        value["method"] = method
        value["url"] = url
        headers = value.get("headers", {})
        if not isinstance(headers, dict):
            raise ValidationError("HTTP başlıkları sözlük olmalıdır.")
        value["headers"] = {str(k): str(v) for k, v in headers.items()}
        value["body"] = value.get("body", "")
        value["expect_status"] = [int(item) for item in value.get("expect_status", [200, 201, 202, 204])]

    elif action_type == "public_api_watch":
        value["api"] = _require_text(value, "api", "API adı veya kimliği")
        value["api_label"] = str(value.get("api_label") or value["api"]).strip() or value["api"]
        notify_on = value.get("notify_on", ["down", "recovered"])
        if isinstance(notify_on, str):
            notify_on = [item.strip() for item in notify_on.split(",") if item.strip()]
        if not isinstance(notify_on, list):
            raise ValidationError("API izleme bildirim türleri liste olmalıdır.")
        allowed_notify = {"down", "recovered", "always"}
        normalized_notify = []
        for item in notify_on:
            key = str(item).strip().lower()
            if key in allowed_notify and key not in normalized_notify:
                normalized_notify.append(key)
        if not normalized_notify:
            normalized_notify = ["down", "recovered"]
        value["notify_on"] = normalized_notify
        value["repeat_down"] = bool(value.get("repeat_down", False))
        value["title"] = str(value.get("title") or "NetOps API Watch").strip() or "NetOps API Watch"
        value["timeout_seconds"] = max(2, min(int(value.get("timeout_seconds", 8)), 60))

    elif action_type == "wait":
        value["seconds"] = max(0, min(float(value.get("seconds", 1)), 86400))
    elif action_type == "shutdown":
        value["delay_seconds"] = max(0, min(int(value.get("delay_seconds", 30)), 86400))
        value["force"] = bool(value.get("force", False))

    elif action_type == "run_scene":
        value["scene_id"] = _require_text(value, "scene_id", "Sahne")


    elif action_type == "write_text":
        value["path"] = _require_text(value, "path", "Dosya yolu")
        value["text"] = str(value.get("text", ""))
        value["append"] = bool(value.get("append", False))
        value["encoding"] = str(value.get("encoding", "utf-8")) or "utf-8"

    elif action_type == "lua_script":
        value["script"] = _require_text(value, "script", "Lua scripti")

    return value


def re_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def validate_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(actions, list) or not actions:
        raise ValidationError("En az bir işlem eklenmelidir.")
    return [_normalize_action(action, index) for index, action in enumerate(actions)]


def validate_definition(
    *,
    name: str,
    trigger_type: str,
    trigger: dict[str, Any],
    actions: list[dict[str, Any]],
    policy: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    normalized_name = str(name).strip()
    if not normalized_name:
        raise ValidationError("Otomasyon adı boş bırakılamaz.")
    if len(normalized_name) > 120:
        raise ValidationError("Otomasyon adı en fazla 120 karakter olabilir.")
    validated_trigger = validate_trigger(trigger_type, trigger)
    validated_actions = validate_actions(actions)
    validated_policy = _default_policy(policy)

    command_warnings = []
    for action in validated_actions:
        if action["type"] != "run_command":
            continue
        lowered = action["command"].casefold()
        matches = sorted(token for token in DANGEROUS_COMMAND_TOKENS if token in lowered)
        if matches:
            command_warnings.extend(matches)

    if command_warnings and not validated_policy["allow_dangerous_commands"]:
        raise ValidationError(
            "Komut tehlikeli işlemler içeriyor: "
            + ", ".join(sorted(set(command_warnings)))
            + ". Kaydetmek için tehlikeli komut iznini açıkça etkinleştir."
        )

    if any(action["type"] == "shutdown" for action in validated_actions) and not validated_policy["allow_dangerous_commands"]:
        raise ValidationError(
            "Bilgisayarı kapatmak için tehlikeli işlem iznini açıkça etkinleştir."
        )

    return {
        "name": normalized_name,
        "trigger_type": trigger_type,
        "trigger": validated_trigger,
        "actions": validated_actions,
        "policy": validated_policy,
    }


def _initial_next_run(trigger_type: str, trigger: dict[str, Any], now: float) -> Optional[float]:
    if trigger_type == "interval":
        return now + int(trigger["seconds"])
    if trigger_type == "daily":
        return next_daily_timestamp(trigger, now)
    if trigger_type == "startup":
        return now + int(trigger.get("delay_seconds", 0))
    return None


def create_automation(
    *,
    name: str,
    trigger_type: str,
    trigger: dict[str, Any],
    actions: list[dict[str, Any]],
    policy: Optional[dict[str, Any]] = None,
    enabled: bool = True,
) -> str:
    value = validate_definition(
        name=name,
        trigger_type=trigger_type,
        trigger=trigger,
        actions=actions,
        policy=policy,
    )
    automation_id = uuid.uuid4().hex
    now = utc_ts()
    next_run = _initial_next_run(value["trigger_type"], value["trigger"], now)
    with _DB_LOCK, contextlib.closing(get_connection()) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO automations(
                id, name, enabled, trigger_type, trigger_json,
                actions_json, policy_json, created_at, updated_at,
                last_run_at, next_run_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
            """,
            (
                automation_id,
                value["name"],
                1 if enabled else 0,
                value["trigger_type"],
                json_dumps(value["trigger"]),
                json_dumps(value["actions"]),
                json_dumps(value["policy"]),
                now,
                now,
                next_run,
            ),
        )
        connection.execute("COMMIT")
    return automation_id


def update_automation(
    automation_id: str,
    *,
    name: str,
    trigger_type: str,
    trigger: dict[str, Any],
    actions: list[dict[str, Any]],
    policy: Optional[dict[str, Any]] = None,
    enabled: bool = True,
) -> None:
    value = validate_definition(
        name=name,
        trigger_type=trigger_type,
        trigger=trigger,
        actions=actions,
        policy=policy,
    )
    now = utc_ts()
    next_run = _initial_next_run(value["trigger_type"], value["trigger"], now)
    with _DB_LOCK, contextlib.closing(get_connection()) as connection:
        connection.execute("BEGIN IMMEDIATE")
        cursor = connection.execute(
            """
            UPDATE automations
            SET name = ?, enabled = ?, trigger_type = ?, trigger_json = ?,
                actions_json = ?, policy_json = ?, updated_at = ?, next_run_at = ?
            WHERE id = ?
            """,
            (
                value["name"],
                1 if enabled else 0,
                value["trigger_type"],
                json_dumps(value["trigger"]),
                json_dumps(value["actions"]),
                json_dumps(value["policy"]),
                now,
                next_run,
                automation_id,
            ),
        )
        if cursor.rowcount == 0:
            connection.execute("ROLLBACK")
            raise AutomationError(f"Otomasyon bulunamadı: {automation_id}")
        connection.execute("COMMIT")


def delete_automation(automation_id: str) -> None:
    with _DB_LOCK, contextlib.closing(get_connection()) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DELETE FROM automations WHERE id = ?", (automation_id,))
        connection.execute("DELETE FROM locks WHERE automation_id = ?", (automation_id,))
        connection.execute("COMMIT")


def set_enabled(automation_id: str, enabled: bool) -> None:
    with contextlib.closing(get_connection()) as connection:
        cursor = connection.execute(
            "UPDATE automations SET enabled = ?, updated_at = ? WHERE id = ?",
            (1 if enabled else 0, utc_ts(), automation_id),
        )
        if cursor.rowcount == 0:
            raise AutomationError(f"Otomasyon bulunamadı: {automation_id}")


def get_required_permissions(actions: list[dict[str, Any]]) -> list[str]:
    permissions = set()
    for action in actions:
        if not action.get("enabled", True):
            continue
        permissions.update(ACTION_PERMISSIONS.get(str(action.get("type")), set()))
    return sorted(permissions)


def preview_automation(
    *,
    name: str,
    trigger_type: str,
    trigger: dict[str, Any],
    actions: list[dict[str, Any]],
    policy: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    value = validate_definition(
        name=name,
        trigger_type=trigger_type,
        trigger=trigger,
        actions=actions,
        policy=policy,
    )
    warnings = []
    irreversible = []
    for index, action in enumerate(value["actions"], 1):
        if action["type"] in {"run_program", "run_command", "open_url", "http_request", "notify", "wait", "run_scene"}:
            irreversible.append(index)
        if action["type"] == "run_scene":
            try:
                from neto_scene_engine import preview_scene

                scene_preview = preview_scene(action["scene_id"])
                warnings.extend(
                    f"{index}. sahne: {warning}"
                    for warning in scene_preview.get("warnings", [])
                )
            except Exception as exc:
                warnings.append(f"{index}. sahne önizlemesi okunamadı: {exc}")
        if action["type"] == "run_command":
            lowered = action["command"].casefold()
            matches = [token for token in DANGEROUS_COMMAND_TOKENS if token in lowered]
            if matches:
                warnings.append(
                    f"{index}. komut tehlikeli anahtarlar içeriyor: {', '.join(sorted(matches))}"
                )
    return {
        **value,
        "permissions": get_required_permissions(value["actions"]),
        "warnings": warnings,
        "irreversible_action_indexes": irreversible,
    }


def next_daily_timestamp(trigger: dict[str, Any], now_ts: Optional[float] = None) -> float:
    now = dt.datetime.fromtimestamp(now_ts or utc_ts())
    hour, minute = [int(part) for part in trigger["time"].split(":", 1)]
    weekdays = set(int(item) for item in trigger.get("weekdays", range(7)))
    for offset in range(0, 8):
        candidate_date = now.date() + dt.timedelta(days=offset)
        candidate = dt.datetime.combine(candidate_date, dt.time(hour=hour, minute=minute))
        if candidate.weekday() not in weekdays:
            continue
        if candidate.timestamp() <= now.timestamp() + 1:
            continue
        return candidate.timestamp()
    return (now + dt.timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0).timestamp()


def _event_log_path() -> Path:
    return LOG_DIR / f"automation-{dt.date.today().isoformat()}.jsonl"


def log_event(
    *,
    level: str,
    message: str,
    automation_id: Optional[str] = None,
    run_id: Optional[str] = None,
    data: Optional[dict[str, Any]] = None,
) -> None:
    payload = {
        "ts": utc_ts(),
        "level": str(level).upper(),
        "message": str(message),
        "automation_id": automation_id,
        "run_id": run_id,
        "data": data or {},
    }
    try:
        with contextlib.closing(get_connection()) as connection:
            connection.execute(
                """
                INSERT INTO events(run_id, automation_id, ts, level, message, data_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    automation_id,
                    payload["ts"],
                    payload["level"],
                    payload["message"],
                    json_dumps(payload["data"]),
                ),
            )
    except Exception:
        pass
    try:
        with _event_log_path().open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


def list_runs(automation_id: Optional[str] = None, limit: int = 50) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 500))
    with contextlib.closing(get_connection()) as connection:
        if automation_id:
            rows = connection.execute(
                "SELECT * FROM runs WHERE automation_id = ? ORDER BY started_at DESC LIMIT ?",
                (automation_id, limit),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    values = []
    for row in rows:
        values.append(
            {
                "id": row["id"],
                "automation_id": row["automation_id"],
                "status": row["status"],
                "started_at": row["started_at"],
                "finished_at": row["finished_at"],
                "trigger": json_loads(row["trigger_json"], {}),
                "result": json_loads(row["result_json"], None),
                "error": row["error"],
                "pid": row["pid"],
                "attempt": row["attempt"],
            }
        )
    return values


def list_events(run_id: str, limit: int = 500) -> list[dict[str, Any]]:
    with contextlib.closing(get_connection()) as connection:
        rows = connection.execute(
            "SELECT * FROM events WHERE run_id = ? ORDER BY ts ASC LIMIT ?",
            (run_id, max(1, min(int(limit), 2000))),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "run_id": row["run_id"],
            "automation_id": row["automation_id"],
            "ts": row["ts"],
            "level": row["level"],
            "message": row["message"],
            "data": json_loads(row["data_json"], {}),
        }
        for row in rows
    ]


def rollback_run(run_id: str) -> dict[str, Any]:
    run = next((item for item in list_runs(limit=500) if item["id"] == str(run_id)), None)
    if run is None:
        raise AutomationError("Çalışma kaydı bulunamadı.")
    if run["status"] not in {"success", "failed"}:
        raise AutomationError("Yalnızca tamamlanmış çalışmalar geri alınabilir.")
    result = run.get("result") or {}
    actions = result.get("actions") if isinstance(result, dict) else None
    if not isinstance(actions, list):
        raise AutomationError("Bu çalışmada geri alınabilir işlem kaydı yok.")
    rolled_back = 0
    errors: list[str] = []
    for action in reversed(actions):
        rollback = action.get("rollback") if isinstance(action, dict) else None
        if not rollback:
            continue
        try:
            rollback_action(rollback)
            rolled_back += 1
        except Exception as exc:
            errors.append(str(exc))
    if rolled_back <= 0 and not errors:
        raise AutomationError("Bu çalışmada geri alınabilir bir işlem yok.")
    payload = {**result, "manual_rollback": True, "rollback_errors": errors}
    with contextlib.closing(get_connection()) as connection:
        connection.execute(
            "UPDATE runs SET status = ?, finished_at = ?, result_json = ?, error = ? WHERE id = ?",
            (
                "rolled_back" if not errors else "rollback_failed",
                utc_ts(),
                json_dumps(payload),
                "; ".join(errors) if errors else None,
                str(run_id),
            ),
        )
    log_event(
        level="INFO" if not errors else "ERROR",
        message=f"Çalışma geri alındı: {rolled_back} işlem.",
        automation_id=run["automation_id"],
        run_id=str(run_id),
        data={"rolled_back": rolled_back, "errors": errors},
    )
    return {"run_id": str(run_id), "rolled_back": rolled_back, "errors": errors}


def acquire_automation_lock(automation_id: str, owner: str, stale_seconds: int = 1800) -> bool:
    now = utc_ts()
    with _DB_LOCK, contextlib.closing(get_connection()) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT owner, heartbeat_at FROM locks WHERE automation_id = ?",
            (automation_id,),
        ).fetchone()
        if row is not None and now - float(row["heartbeat_at"]) <= stale_seconds:
            connection.execute("ROLLBACK")
            return False
        connection.execute(
            """
            INSERT INTO locks(automation_id, owner, acquired_at, heartbeat_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(automation_id) DO UPDATE SET
                owner = excluded.owner,
                acquired_at = excluded.acquired_at,
                heartbeat_at = excluded.heartbeat_at
            """,
            (automation_id, owner, now, now),
        )
        connection.execute("COMMIT")
    return True


def heartbeat_lock(automation_id: str, owner: str) -> None:
    with contextlib.closing(get_connection()) as connection:
        connection.execute(
            "UPDATE locks SET heartbeat_at = ? WHERE automation_id = ? AND owner = ?",
            (utc_ts(), automation_id, owner),
        )


def release_automation_lock(automation_id: str, owner: str) -> None:
    with contextlib.closing(get_connection()) as connection:
        connection.execute(
            "DELETE FROM locks WHERE automation_id = ? AND owner = ?",
            (automation_id, owner),
        )


def automation_locked(automation_id: str, stale_seconds: int = 1800) -> bool:
    with contextlib.closing(get_connection()) as connection:
        row = connection.execute(
            "SELECT heartbeat_at FROM locks WHERE automation_id = ?",
            (automation_id,),
        ).fetchone()
    return bool(row is not None and utc_ts() - float(row["heartbeat_at"]) <= stale_seconds)


GLOBAL_EXECUTION_LOCK = "__netops_global_execution__"
QUEUE_ACTIVE_STATUSES = {"pending", "running"}


def emergency_stop_active() -> bool:
    state = get_meta("emergency_stop", {})
    return bool(isinstance(state, dict) and state.get("active"))


def set_emergency_stop(reason: str = "Kullanıcı tarafından durduruldu.") -> dict[str, Any]:
    state = {
        "active": True,
        "reason": str(reason or "Kullanıcı tarafından durduruldu."),
        "ts": utc_ts(),
    }
    set_meta("emergency_stop", state)
    log_event(level="WARNING", message="Acil durdurma etkinleştirildi.", data=state)
    return state


def clear_emergency_stop() -> None:
    set_meta("emergency_stop", {"active": False, "ts": utc_ts()})
    log_event(level="INFO", message="Acil durdurma kaldırıldı.")


def acquire_global_execution_lock(
    owner: str,
    *,
    wait_seconds: float = 900,
    poll_seconds: float = 0.25,
) -> bool:
    deadline = utc_ts() + max(0.0, float(wait_seconds))
    while True:
        if emergency_stop_active():
            raise AutomationError("NetOps acil durdurma etkin.")
        if acquire_automation_lock(GLOBAL_EXECUTION_LOCK, owner, stale_seconds=86400):
            return True
        if utc_ts() >= deadline:
            return False
        time.sleep(max(0.05, float(poll_seconds)))


def _queue_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "automation_id": row["automation_id"],
        "status": row["status"],
        "trigger": json_loads(row["trigger_json"], {}),
        "enqueued_at": row["enqueued_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "error": row["error"],
        "pid": row["pid"],
    }


def enqueue_automation(
    automation_id: str,
    trigger_info: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    get_automation(automation_id)
    trigger = dict(trigger_info or {"type": "manual"})
    now = utc_ts()
    with _DB_LOCK, contextlib.closing(get_connection()) as connection:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            """
            SELECT * FROM automation_queue
            WHERE automation_id = ? AND status IN ('pending', 'running')
            ORDER BY enqueued_at ASC LIMIT 1
            """,
            (automation_id,),
        ).fetchone()
        if existing is not None:
            connection.execute("COMMIT")
            return {**_queue_row(existing), "deduplicated": True}
        queue_id = uuid.uuid4().hex
        connection.execute(
            """
            INSERT INTO automation_queue(
                id, automation_id, status, trigger_json, enqueued_at, pid
            ) VALUES (?, ?, 'pending', ?, ?, ?)
            """,
            (queue_id, automation_id, json_dumps(trigger), now, os.getpid()),
        )
        connection.execute("COMMIT")
    log_event(
        level="INFO",
        message="Otomasyon kuyruğa alındı.",
        automation_id=automation_id,
        data={"queue_id": queue_id, "trigger": trigger},
    )
    return {
        "id": queue_id,
        "automation_id": automation_id,
        "status": "pending",
        "trigger": trigger,
        "enqueued_at": now,
        "started_at": None,
        "finished_at": None,
        "error": None,
        "pid": os.getpid(),
        "deduplicated": False,
    }


def list_queue(limit: int = 100) -> list[dict[str, Any]]:
    with contextlib.closing(get_connection()) as connection:
        rows = connection.execute(
            "SELECT * FROM automation_queue ORDER BY enqueued_at DESC LIMIT ?",
            (max(1, min(int(limit), 500)),),
        ).fetchall()
    return [_queue_row(row) for row in rows]


def cancel_queued(queue_id: str) -> bool:
    with contextlib.closing(get_connection()) as connection:
        cursor = connection.execute(
            """
            UPDATE automation_queue
            SET status = 'cancelled', finished_at = ?, error = 'Kullanıcı tarafından iptal edildi.'
            WHERE id = ? AND status = 'pending'
            """,
            (utc_ts(), str(queue_id)),
        )
    return bool(cursor.rowcount)


def _set_queue_status(
    queue_id: Optional[str],
    status: str,
    *,
    error: Optional[str] = None,
) -> None:
    if not queue_id:
        return
    now = utc_ts()
    if status == "running":
        query = "UPDATE automation_queue SET status = ?, started_at = ?, pid = ? WHERE id = ?"
        params = (status, now, os.getpid(), queue_id)
    else:
        query = "UPDATE automation_queue SET status = ?, finished_at = ?, error = ? WHERE id = ?"
        params = (status, now, error, queue_id)
    try:
        with contextlib.closing(get_connection()) as connection:
            connection.execute(query, params)
    except Exception:
        pass


def evaluate_condition(condition: Optional[dict[str, Any]]) -> bool:
    if not condition:
        return True
    condition_type = condition.get("type")
    if condition_type == "all":
        return all(evaluate_condition(item) for item in condition.get("conditions", []))
    if condition_type == "any":
        return any(evaluate_condition(item) for item in condition.get("conditions", []))
    if condition_type == "not":
        return not evaluate_condition(condition.get("condition"))
    if condition_type == "internet_online":
        return internet_available(
            str(condition.get("host", "1.1.1.1")),
            int(condition.get("port", 53)),
            float(condition.get("timeout_seconds", 3)),
        )
    if condition_type == "process_running":
        return process_name_running(str(condition.get("process_name", "")))
    if condition_type == "file_exists":
        exists = Path(str(condition.get("path", ""))).exists()
        return exists == bool(condition.get("exists", True))
    if condition_type == "resource_threshold":
        value = resource_value(
            str(condition.get("metric", "cpu")),
            str(condition.get("path", Path.home().anchor or "C:\\")),
        )
        return compare_threshold(
            value,
            str(condition.get("operator", ">=")),
            float(condition.get("threshold", 85)),
        )
    return False


def mark_trigger_queued(automation: AutomationDefinition, now: Optional[float] = None) -> None:
    now = float(now or utc_ts())
    next_run = automation.next_run_at
    if automation.trigger_type == "interval":
        next_run = now + int(automation.trigger["seconds"])
    elif automation.trigger_type == "daily":
        next_run = next_daily_timestamp(automation.trigger, now)
    elif automation.trigger_type == "startup":
        next_run = None
    with contextlib.closing(get_connection()) as connection:
        connection.execute(
            "UPDATE automations SET next_run_at = ? WHERE id = ?",
            (next_run, automation.id),
        )
    set_meta(
        f"automation_queued:{automation.id}",
        {"queued_at": now, "trigger_type": automation.trigger_type},
    )


def _new_run(automation_id: str, trigger_info: dict[str, Any], attempt: int = 1) -> str:
    run_id = uuid.uuid4().hex
    with contextlib.closing(get_connection()) as connection:
        connection.execute(
            """
            INSERT INTO runs(id, automation_id, status, started_at, trigger_json, pid, attempt)
            VALUES (?, ?, 'running', ?, ?, ?, ?)
            """,
            (run_id, automation_id, utc_ts(), json_dumps(trigger_info), os.getpid(), attempt),
        )
    return run_id


def _finish_run(run_id: str, status: str, result: Any = None, error: Optional[str] = None) -> None:
    with contextlib.closing(get_connection()) as connection:
        connection.execute(
            """
            UPDATE runs
            SET status = ?, finished_at = ?, result_json = ?, error = ?
            WHERE id = ?
            """,
            (
                status,
                utc_ts(),
                json_dumps(result) if result is not None else None,
                error,
                run_id,
            ),
        )


def _set_automation_run_times(automation: AutomationDefinition, now: float) -> None:
    next_run = None
    if automation.trigger_type == "interval":
        next_run = now + int(automation.trigger["seconds"])
    elif automation.trigger_type == "daily":
        next_run = next_daily_timestamp(automation.trigger, now)
    elif automation.trigger_type == "startup":
        next_run = None
    with contextlib.closing(get_connection()) as connection:
        connection.execute(
            "UPDATE automations SET last_run_at = ?, next_run_at = ? WHERE id = ?",
            (now, next_run, automation.id),
        )


def _transaction_path(run_id: str) -> Path:
    path = TRANSACTION_DIR / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _backup_existing(path: Path, transaction: Path, label: str) -> Optional[Path]:
    if not path.exists():
        return None
    digest = hashlib.sha256(str(path).encode("utf-8", errors="replace")).hexdigest()[:12]
    target = transaction / f"{label}-{digest}"
    if path.is_dir():
        shutil.copytree(path, target)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    return target


def _render_template(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, str):
        mapping = {
            "automation_id": context.get("automation_id", ""),
            "automation_name": context.get("automation_name", ""),
            "run_id": context.get("run_id", ""),
            "date": dt.date.today().isoformat(),
            "datetime": dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
            "home": str(Path.home()),
            "project": str(context.get("project", "")),
        }
        for key, replacement in mapping.items():
            value = value.replace("{{" + key + "}}", str(replacement))
        return os.path.expandvars(os.path.expanduser(value))
    if isinstance(value, list):
        return [_render_template(item, context) for item in value]
    if isinstance(value, dict):
        return {key: _render_template(item, context) for key, item in value.items()}
    return value


def _notify_windows(title: str, message: str) -> bool:
    if os.name != "nt":
        return False
    escaped_title = title.replace("'", "''")
    escaped_message = message.replace("'", "''")
    script = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml('<toast><visual><binding template="ToastGeneric"><text>{escaped_title}</text><text>{escaped_message}</text></binding></visual></toast>')
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('NetOps').Show($toast)
"""
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-STA", "-Command", script],
            capture_output=True,
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode == 0:
            return True
    except Exception:
        pass
    try:
        subprocess.Popen(
            ["msg.exe", "*", f"{title}\n{message}"],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return True
    except Exception:
        return False


def _execute_action(
    action: dict[str, Any],
    *,
    context: dict[str, Any],
    transaction: Path,
    run_id: str,
    automation_id: str,
    allow_dangerous_commands: bool = False,
) -> ActionResult:
    action = _render_template(action, context)
    action_type = action["type"]
    _require_action_permissions(action_type, context)
    timeout = int(action.get("timeout_seconds", 120))

    if action_type == "notify":
        title = action["title"]
        message = action["message"]
        shown = _notify_windows(title, message)
        return ActionResult(action_type, True, "Bildirim işlendi.", {"shown": shown})

    if action_type == "run_program":
        path = Path(action["path"])
        if not path.exists():
            raise ActionFailed(f"Program bulunamadı: {path}")
        args = [str(item) for item in action.get("args", [])]
        suffix = path.suffix.lower()
        if suffix in {".py", ".pyw"}:
            command = [sys.executable, str(path), *args]
        elif os.name == "nt" and suffix in {".bat", ".cmd"}:
            command = ["cmd.exe", "/d", "/s", "/c", str(path), *args]
        else:
            command = [str(path), *args]
        cwd = action.get("cwd") or str(path.parent)
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" and suffix in {".py", ".pyw", ".bat", ".cmd"} else 0
        process = subprocess.Popen(command, cwd=cwd, creationflags=flags)
        if action.get("wait"):
            code = process.wait(timeout=timeout)
            if code != 0:
                raise ActionFailed(f"Program {code} koduyla kapandı.")
            return ActionResult(action_type, True, "Program tamamlandı.", {"pid": process.pid, "exit_code": code})
        return ActionResult(action_type, True, "Program başlatıldı.", {"pid": process.pid})

    if action_type == "run_scene":
        try:
            from neto_scene_engine import run_scene

            def _scene_progress(payload: dict[str, Any]) -> None:
                event = payload.get("event")
                label = payload.get("label") or event or ""
                if event in {"step_started", "step_completed", "failed", "completed"}:
                    log_event(
                        level="INFO" if event != "failed" else "ERROR",
                        message=f"Sahne: {label}",
                        automation_id=automation_id,
                        run_id=run_id,
                    )

            result = run_scene(
                action["scene_id"],
                confirm=lambda _message: bool(allow_dangerous_commands),
                on_progress=_scene_progress,
            )
        except Exception as exc:
            raise ActionFailed(f"Sahne çalıştırılamadı: {exc}") from exc
        if result.get("status") != "success":
            raise ActionFailed(result.get("error") or "Sahne tamamlanamadı.")
        return ActionResult(action_type, True, "Sahne hazırlandı.", result)

    if action_type == "run_command":
        command_text = action["command"]
        lowered = command_text.casefold()
        matches = [token for token in DANGEROUS_COMMAND_TOKENS if token in lowered]
        if matches and not allow_dangerous_commands:
            raise PermissionDenied(
                "Komut tehlikeli anahtarlar içeriyor: " + ", ".join(sorted(matches))
            )
        shell_name = action.get("shell", "powershell" if os.name == "nt" else "sh")
        if os.name == "nt" and shell_name == "powershell":
            command = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", command_text]
        elif os.name == "nt":
            command = ["cmd.exe", "/d", "/s", "/c", command_text]
        else:
            command = ["/bin/sh", "-lc", command_text]
        result = subprocess.run(
            command,
            cwd=action.get("cwd") or None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
        )
        data = {
            "exit_code": result.returncode,
            "stdout": (result.stdout or "")[-20000:],
            "stderr": (result.stderr or "")[-20000:],
        }
        if result.returncode != 0:
            raise ActionFailed(
                f"Komut {result.returncode} koduyla başarısız oldu.\n{data['stderr'] or data['stdout']}"
            )
        return ActionResult(action_type, True, "Komut tamamlandı.", data)

    if action_type == "shutdown":
        if not allow_dangerous_commands:
            raise PermissionDenied(
                "Bilgisayarı kapatmak için otomasyon politikasında tehlikeli işlemlere açıkça izin verilmelidir."
            )
        delay = int(action.get("delay_seconds", 30))
        if os.name == "nt":
            command = ["shutdown.exe", "/s", "/t", str(delay)]
            if action.get("force"):
                command.append("/f")
        else:
            command = ["systemctl", "poweroff"]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            suffix = f": {detail}" if detail else "."
            raise ActionFailed(f"Bilgisayar kapatma komutu başarısız oldu{suffix}")
        return ActionResult(
            action_type,
            True,
            f"Bilgisayar {delay} saniye sonra kapatılacak.",
            {"delay_seconds": delay, "force": bool(action.get("force")), "cancel_command": "shutdown /a" if os.name == "nt" else None},
        )
    if action_type == "lua_script":
        try:
            from neto_lua_runtime import run_lua_script
        except Exception as exc:
            raise ActionFailed("Lua 5.4 runtime kullanılamıyor.") from exc
        try:
            result = run_lua_script(action["script"], context=context, notify=_notify_windows)
        except Exception as exc:
            raise ActionFailed(f"Lua scripti başarısız oldu: {exc}") from exc
        return ActionResult(action_type, True, "Lua scripti tamamlandı.", result)
    if action_type == "open_url":
        opened = bool(webbrowser.open(action["url"], new=2))
        if not opened:
            raise ActionFailed("URL açılamadı.")
        return ActionResult(action_type, True, "URL açıldı.", {"url": action["url"]})

    if action_type in {"copy_file", "move_file"}:
        source = Path(action["source"])
        destination = Path(action["destination"])
        if not source.exists():
            raise ActionFailed(f"Kaynak bulunamadı: {source}")
        if destination.exists() and not action.get("overwrite"):
            raise ActionFailed(f"Hedef zaten var: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination_backup = _backup_existing(destination, transaction, "destination")
        source_was_dir = source.is_dir()
        if destination.exists():
            if destination.is_dir():
                shutil.rmtree(destination)
            else:
                destination.unlink()
        if action_type == "copy_file":
            if source_was_dir:
                shutil.copytree(source, destination)
            else:
                shutil.copy2(source, destination)
        else:
            shutil.move(str(source), str(destination))
        rollback = {
            "type": action_type,
            "source": str(source),
            "destination": str(destination),
            "destination_backup": str(destination_backup) if destination_backup else None,
            "source_was_dir": source_was_dir,
        }
        return ActionResult(action_type, True, "Dosya işlemi tamamlandı.", {"source": str(source), "destination": str(destination)}, rollback)

    if action_type == "backup_folder":
        source = Path(action["source"])
        if not source.is_dir():
            raise ActionFailed(f"Yedeklenecek klasör bulunamadı: {source}")
        destination = Path(action["destination"])
        if action.get("include_timestamp"):
            stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            if destination.suffix.lower() == ".zip":
                destination = destination.with_name(f"{destination.stem}_{stamp}.zip")
            else:
                destination = destination / f"{source.name}_{stamp}.zip"
        elif destination.suffix.lower() != ".zip":
            destination = destination / f"{source.name}.zip"
        destination.parent.mkdir(parents=True, exist_ok=True)
        existed = destination.exists()
        existing_backup = _backup_existing(destination, transaction, "backup_zip") if existed else None
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in source.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(source.parent))
        rollback = {
            "type": action_type,
            "destination": str(destination),
            "destination_backup": str(existing_backup) if existing_backup else None,
        }
        return ActionResult(action_type, True, "ZIP yedeği oluşturuldu.", {"destination": str(destination)}, rollback)

    if action_type == "http_request":
        body = action.get("body", "")
        if isinstance(body, (dict, list)):
            encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        else:
            encoded = str(body).encode("utf-8") if body not in (None, "") else None
        request = urllib.request.Request(
            action["url"],
            data=encoded,
            method=action["method"],
            headers=action.get("headers", {}),
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                content = response.read(1_000_000)
                status = int(response.status)
                headers = dict(response.headers.items())
        except urllib.error.HTTPError as exc:
            content = exc.read(1_000_000)
            status = int(exc.code)
            headers = dict(exc.headers.items()) if exc.headers else {}
        if status not in action.get("expect_status", [200, 201, 202, 204]):
            raise ActionFailed(f"HTTP isteği beklenmeyen durum döndürdü: {status}")
        return ActionResult(
            action_type,
            True,
            "HTTP isteği tamamlandı.",
            {
                "status": status,
                "headers": headers,
                "body": content.decode("utf-8", errors="replace")[-20000:],
            },
        )

    if action_type == "public_api_watch":
        try:
            from neto_public_apis import (
                call_verified_exact,
                probe_free_entry_exact,
                resolve_free_entry,
                resolve_verified,
            )
        except Exception as exc:
            raise ActionFailed("Public API motoru kullanılamıyor.") from exc

        requested = str(action.get("api") or "").strip()
        api_info = resolve_verified(requested)
        source_kind = "verified"
        if not api_info:
            api_info = resolve_free_entry(requested)
            source_kind = "catalog"
        if not api_info:
            raise ActionFailed(f"İzlenecek API bulunamadı: {requested}")
        api_id = str(api_info.get("id") or api_info.get("name") or requested).strip()
        api_label = str(action.get("api_label") or api_info.get("name") or api_id).strip()
        try:
            if source_kind == "verified":
                result = call_verified_exact(api_id, timeout=int(action.get("timeout_seconds", 8)))
            else:
                result = probe_free_entry_exact(api_label, timeout=int(action.get("timeout_seconds", 8)))
        except Exception as exc:
            result = {"ok": False, "api": api_info, "error": f"{type(exc).__name__}: {exc}"}

        current_state = "up" if bool(result.get("ok")) else "down"
        state_key = f"public_api_watch:{automation_id}:{api_id.casefold()}"
        previous = get_meta(state_key, {})
        previous_state = str(previous.get("state") or "unknown")
        changed = previous_state not in {"unknown", current_state}
        notify_on = set(action.get("notify_on") or ["down", "recovered"])
        should_notify = False
        reason = ""
        if "always" in notify_on:
            should_notify = True
            reason = current_state
        elif current_state == "down" and "down" in notify_on:
            should_notify = previous_state != "down" or bool(action.get("repeat_down"))
            reason = "down"
        elif current_state == "up" and previous_state == "down" and "recovered" in notify_on:
            should_notify = True
            reason = "recovered"

        now = utc_ts()
        set_meta(state_key, {
            "state": current_state,
            "checked_at": now,
            "previous_state": previous_state,
            "status": result.get("status"),
            "source": source_kind,
            "latency_ms": result.get("latency_ms"),
            "error": result.get("error") or "",
        })

        notified = False
        if should_notify:
            if reason == "recovered":
                message = f"{api_label} yeniden erişilebilir durumda."
            elif reason == "down":
                detail = str(result.get("error") or result.get("health_state") or "yanıt alınamadı")
                message = f"{api_label} erişilemiyor: {detail[:300]}"
            else:
                message = f"{api_label}: {'çalışıyor' if current_state == 'up' else 'erişilemiyor'}."
            notified = _notify_windows(str(action.get("title") or "NetOps API Watch"), message)

        return ActionResult(
            action_type,
            True,
            f"{api_label} kontrol edildi: {current_state}.",
            {
                "api": api_id,
                "api_label": api_label,
                "state": current_state,
                "source": source_kind,
                "previous_state": previous_state,
                "changed": changed,
                "notified": notified,
                "status": result.get("status"),
                "latency_ms": result.get("latency_ms"),
                "health_state": result.get("health_state"),
                "error": result.get("error") or "",
            },
        )

    if action_type == "wait":
        seconds = float(action["seconds"])
        time.sleep(seconds)
        return ActionResult(action_type, True, "Bekleme tamamlandı.", {"seconds": seconds})

    if action_type == "write_text":
        path = Path(action["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        existing_backup = _backup_existing(path, transaction, "text_file")
        existed = path.exists()
        mode = "a" if action.get("append") else "w"
        with path.open(mode, encoding=action.get("encoding", "utf-8")) as handle:
            handle.write(action["text"])
        rollback = {
            "type": action_type,
            "path": str(path),
            "existed": existed,
            "backup": str(existing_backup) if existing_backup else None,
        }
        return ActionResult(action_type, True, "Metin yazıldı.", {"path": str(path)}, rollback)

    raise ActionFailed(f"İşlem uygulanamadı: {action_type}")


def rollback_action(rollback: dict[str, Any]) -> None:
    rollback_type = rollback.get("type")
    if rollback_type in {"copy_file", "move_file"}:
        source = Path(rollback["source"])
        destination = Path(rollback["destination"])
        backup = Path(rollback["destination_backup"]) if rollback.get("destination_backup") else None
        if rollback_type == "move_file" and destination.exists():
            source.parent.mkdir(parents=True, exist_ok=True)
            if source.exists():
                if source.is_dir():
                    shutil.rmtree(source)
                else:
                    source.unlink()
            shutil.move(str(destination), str(source))
        elif rollback_type == "copy_file" and destination.exists():
            if destination.is_dir():
                shutil.rmtree(destination)
            else:
                destination.unlink()
        if backup and backup.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            if backup.is_dir():
                shutil.copytree(backup, destination)
            else:
                shutil.copy2(backup, destination)
        return

    if rollback_type == "backup_folder":
        destination = Path(rollback["destination"])
        backup = Path(rollback["destination_backup"]) if rollback.get("destination_backup") else None
        if destination.exists():
            destination.unlink()
        if backup and backup.exists():
            shutil.copy2(backup, destination)
        return

    if rollback_type == "write_text":
        path = Path(rollback["path"])
        backup = Path(rollback["backup"]) if rollback.get("backup") else None
        if backup and backup.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, path)
        elif not rollback.get("existed") and path.exists():
            path.unlink()


_LUA_EVENT_KERNEL: Any = None
_LUA_EVENT_ERROR: Optional[str] = None
_LUA_EVENT_LOCK = threading.RLock()


def _emit_lua_event(
    event: str,
    payload: dict[str, Any],
    *,
    automation_id: Optional[str] = None,
    run_id: Optional[str] = None,
) -> dict[str, Any]:
    """Dispatch a lifecycle event to optional Lua hooks without breaking automation."""
    global _LUA_EVENT_KERNEL, _LUA_EVENT_ERROR
    with _LUA_EVENT_LOCK:
        if _LUA_EVENT_ERROR:
            return {}
        try:
            if _LUA_EVENT_KERNEL is None:
                from neto_lua_kernel import create_default_kernel

                _LUA_EVENT_KERNEL = create_default_kernel(notify=_notify_windows)
            result = _LUA_EVENT_KERNEL.emit(event, payload)
        except Exception as exc:
            _LUA_EVENT_ERROR = str(exc)
            log_event(
                level="WARNING",
                message=f"Lua olay çekirdeği devre dışı: {exc}",
                automation_id=automation_id,
                run_id=run_id,
            )
            return {}
    for message in result.get("events", []):
        log_event(
            level="INFO",
            message=f"Lua: {message}",
            automation_id=automation_id,
            run_id=run_id,
        )
    return result

def execute_automation(
    automation_id: str,
    *,
    trigger_info: Optional[dict[str, Any]] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    automation = get_automation(automation_id)
    if emergency_stop_active():
        raise AutomationError("NetOps acil durdurma etkin.")
    if automation_locked(automation_id):
        raise AutomationError("Bu otomasyon zaten çalışıyor veya kuyrukta.")
    owner = f"{os.getpid()}-{uuid.uuid4().hex}"
    global_acquired = acquire_global_execution_lock(owner)
    if not global_acquired:
        raise AutomationError("Başka bir otomasyon çalışıyor; görev zaman aşımına uğradı.")
    automation_acquired = False
    if not acquire_automation_lock(automation_id, owner):
        release_automation_lock(GLOBAL_EXECUTION_LOCK, owner)
        raise AutomationError("Bu otomasyon zaten çalışıyor.")
    automation_acquired = True

    effective_trigger = dict(trigger_info or {"type": "manual"})
    queue_id = str(effective_trigger.get("queue_id") or "")
    run_id = _new_run(automation_id, effective_trigger)
    _set_queue_status(queue_id, "running")
    context = {
        "automation_id": automation.id,
        "automation_name": automation.name,
        "run_id": run_id,
        "project": os.getcwd(),
    }
    log_event(level="INFO", message="Otomasyon başladı.", automation_id=automation_id, run_id=run_id)
    _emit_lua_event("automation.started", context, automation_id=automation_id, run_id=run_id)
    transaction = _transaction_path(run_id)
    rollback_stack: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    try:
        if dry_run:
            preview = preview_automation(
                name=automation.name,
                trigger_type=automation.trigger_type,
                trigger=automation.trigger,
                actions=automation.actions,
                policy=automation.policy,
            )
            _finish_run(run_id, "preview", preview)
            _set_queue_status(queue_id, "preview")
            return {"run_id": run_id, "status": "preview", "preview": preview}

        for index, action in enumerate(automation.actions, 1):
            if not action.get("enabled", True):
                continue
            if emergency_stop_active():
                raise AutomationError("NetOps acil durdurma etkin; kalan işlemler durduruldu.")
            if not evaluate_condition(action.get("condition")):
                results.append(
                    {
                        "index": index,
                        "type": action["type"],
                        "ok": True,
                        "status": "skipped",
                        "message": "Koşul sağlanmadığı için işlem atlandı.",
                    }
                )
                log_event(
                    level="INFO",
                    message=f"{index}. işlem koşul nedeniyle atlandı.",
                    automation_id=automation.id,
                    run_id=run_id,
                    data={"condition": action.get("condition")},
                )
                continue
            heartbeat_lock(automation.id, owner)
            action_type = action["type"]
            retries = int(action.get("retries", 0))
            retry_delay = int(action.get("retry_delay_seconds", 2))
            last_error: Optional[Exception] = None
            result: Optional[ActionResult] = None

            for attempt in range(1, retries + 2):
                try:
                    log_event(
                        level="INFO",
                        message=f"{index}. işlem başlatıldı: {action_type}",
                        automation_id=automation.id,
                        run_id=run_id,
                        data={"attempt": attempt},
                    )
                    _emit_lua_event(
                        "automation.action_started",
                        {**context, "action_index": index, "action_type": action_type, "attempt": attempt},
                        automation_id=automation.id,
                        run_id=run_id,
                    )
                    result = _execute_action(
                        action,
                        context=context,
                        transaction=transaction,
                        run_id=run_id,
                        automation_id=automation.id,
                        allow_dangerous_commands=bool(automation.policy.get("allow_dangerous_commands")),
                    )
                    break
                except Exception as exc:
                    last_error = exc
                    log_event(
                        level="ERROR",
                        message=f"{index}. işlem hatası: {exc}",
                        automation_id=automation.id,
                        run_id=run_id,
                        data={"attempt": attempt, "traceback": traceback.format_exc()},
                    )
                    if isinstance(exc, PermissionDenied):
                        break
                    if attempt <= retries:
                        time.sleep(retry_delay * attempt)

            if result is None:
                if automation.policy.get("continue_on_action_error"):
                    results.append(
                        {
                            "index": index,
                            "type": action_type,
                            "ok": False,
                            "error": str(last_error),
                        }
                    )
                    continue
                raise ActionFailed(f"{index}. işlem başarısız: {last_error}")

            if result.rollback:
                rollback_stack.append(result.rollback)
            results.append(
                {
                    "index": index,
                    "type": result.action_type,
                    "ok": result.ok,
                    "status": "completed",
                    "message": result.message,
                    "data": result.data,
                    "rollback": result.rollback,
                }
            )
            log_event(
                level="INFO",
                message=f"{index}. işlem tamamlandı: {action_type}",
                automation_id=automation.id,
                run_id=run_id,
                data=result.data,
            )
            _emit_lua_event(
                "automation.action_completed",
                {**context, "action_index": index, "action_type": action_type, "result": result.data},
                automation_id=automation.id,
                run_id=run_id,
            )
        now = utc_ts()
        _set_automation_run_times(automation, now)
        result_payload = {"actions": results, "rolled_back": False}
        _emit_lua_event(
            "automation.completed",
            {**context, "actions": results, "status": "success"},
            automation_id=automation.id,
            run_id=run_id,
        )
        _finish_run(run_id, "success", result_payload)
        _set_queue_status(queue_id, "success")
        log_event(level="INFO", message="Otomasyon başarıyla tamamlandı.", automation_id=automation.id, run_id=run_id)
        return {"run_id": run_id, "status": "success", **result_payload}
    except Exception as exc:
        rolled_back = False
        rollback_errors = []
        if automation.policy.get("rollback_on_failure") and rollback_stack:
            for rollback in reversed(rollback_stack):
                try:
                    rollback_action(rollback)
                    rolled_back = True
                except Exception as rollback_exc:
                    rollback_errors.append(str(rollback_exc))
        error_text = str(exc)
        payload = {
            "actions": results,
            "rolled_back": rolled_back,
            "rollback_errors": rollback_errors,
        }
        _finish_run(run_id, "failed", payload, error_text)
        _set_queue_status(queue_id, "failed", error=error_text)
        _emit_lua_event(
            "automation.failed",
            {**context, "status": "failed", "error": error_text, "actions": results},
            automation_id=automation.id,
            run_id=run_id,
        )
        log_event(
            level="ERROR",
            message=f"Otomasyon başarısız: {error_text}",
            automation_id=automation.id,
            run_id=run_id,
            data={"rolled_back": rolled_back, "rollback_errors": rollback_errors},
        )
        raise
    finally:
        if automation_acquired:
            release_automation_lock(automation.id, owner)
        if global_acquired:
            release_automation_lock(GLOBAL_EXECUTION_LOCK, owner)


def fingerprint_path(path: Path, recursive: bool = True) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    if path.is_file():
        stat = path.stat()
        digest.update(str(path.resolve()).encode())
        digest.update(str(stat.st_size).encode())
        digest.update(str(stat.st_mtime_ns).encode())
        return digest.hexdigest()
    iterator = path.rglob("*") if recursive else path.glob("*")
    count = 0
    for item in iterator:
        if count >= 20000:
            break
        try:
            stat = item.stat()
        except OSError:
            continue
        digest.update(str(item.relative_to(path)).encode("utf-8", errors="replace"))
        digest.update(str(stat.st_size).encode())
        digest.update(str(stat.st_mtime_ns).encode())
        count += 1
    return digest.hexdigest()


def process_name_running(process_name: str) -> bool:
    """Return whether a process name or executable stem is currently running."""
    wanted = Path(str(process_name or "")).stem.casefold()
    if not wanted:
        return False
    if psutil is not None:
        try:
            for process in psutil.process_iter(["name", "cmdline"]):
                info = process.info
                name = str(info.get("name") or "").casefold()
                command = " ".join(info.get("cmdline") or []).casefold()
                if wanted in name or wanted in command:
                    return True
        except Exception:
            pass
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist.exe", "/fo", "csv", "/nh"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return wanted in (result.stdout or "").casefold()
        except Exception:
            return False
    return False


def internet_available(host: str = "1.1.1.1", port: int = 53, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=float(timeout)):
            return True
    except OSError:
        return False


def resource_value(metric: str, path: str = "C:\\") -> float:
    if psutil is None:
        raise AutomationError("psutil kurulu değil.")
    if metric == "cpu":
        return float(psutil.cpu_percent(interval=0.2))
    if metric == "memory":
        memory = psutil.virtual_memory()
        total = float(getattr(memory, "total", 0) or 0)
        available = float(getattr(memory, "available", 0) or 0)
        if total <= 0:
            return float(getattr(memory, "percent", 0.0) or 0.0)
        return max(0.0, min(100.0, ((total - available) / total) * 100.0))
    if metric == "disk":
        return float(psutil.disk_usage(path).percent)
    raise AutomationError(f"Geçersiz kaynak metriği: {metric}")


def compare_threshold(value: float, operator: str, threshold: float) -> bool:
    if operator == ">=":
        return value >= threshold
    if operator == ">":
        return value > threshold
    if operator == "<=":
        return value <= threshold
    if operator == "<":
        return value < threshold
    return False


def set_meta(key: str, value: Any) -> None:
    with contextlib.closing(get_connection()) as connection:
        connection.execute(
            """
            INSERT INTO meta(key, value) VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, json_dumps(value)),
        )


def get_meta(key: str, default: Any = None) -> Any:
    with contextlib.closing(get_connection()) as connection:
        row = connection.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return json_loads(row["value"], default) if row else default


def mark_interrupted_runs(max_age_seconds: int = 7200) -> int:
    """Mark old or orphaned runs so a crashed worker cannot leave them stuck."""
    now = utc_ts()
    cutoff = now - max(0, int(max_age_seconds))
    with contextlib.closing(get_connection()) as connection:
        rows = connection.execute(
            "SELECT id, pid, started_at FROM runs WHERE status = 'running'"
        ).fetchall()
        repaired = 0
        for row in rows:
            pid = int(row["pid"] or 0)
            orphaned = bool(pid) and not process_alive(pid)
            too_old = float(row["started_at"] or 0) < cutoff
            if not orphaned and not too_old:
                continue
            cursor = connection.execute(
                """
                UPDATE runs
                SET status = 'interrupted', finished_at = ?,
                    error = 'Worker veya uygulama beklenmedik şekilde kapandı.'
                WHERE id = ? AND status = 'running'
                """,
                (now, row["id"]),
            )
            repaired += int(cursor.rowcount)
    return repaired

def current_profile() -> str:
    try:
        from neto_strict_profiles import current_profile as profile_getter
        return str(profile_getter())
    except Exception:
        return "balanced"


def profile_allows_panel() -> bool:
    return current_profile() != "force_fast"


def profile_allows_scheduler() -> bool:
    return current_profile() in {"balanced", "full", "custom"}


def get_python_executable(background: bool = False) -> str:
    executable = Path(sys.executable)
    if background and os.name == "nt":
        pythonw = executable.with_name("pythonw.exe")
        if pythonw.is_file():
            return str(pythonw)
    return str(executable)


def worker_script_path() -> Path:
    return Path(__file__).resolve().with_name("neto_automation_worker.py")


def read_worker_state() -> dict[str, Any]:
    try:
        value = json.loads(WORKER_STATE_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if psutil is not None:
        try:
            return bool(psutil.pid_exists(pid))
        except Exception:
            pass
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def worker_status() -> dict[str, Any]:
    state = read_worker_state()
    pid = int(state.get("pid") or 0)
    heartbeat = float(state.get("heartbeat") or 0)
    alive = process_alive(pid) and utc_ts() - heartbeat < 30
    return {**state, "pid": pid, "alive": alive, "stale": pid > 0 and not alive}


def start_worker(force: bool = False) -> dict[str, Any]:
    status = worker_status()
    if status.get("alive"):
        return status
    if not force and not profile_allows_scheduler():
        return {"alive": False, "reason": "profile", "profile": current_profile()}
    if getattr(sys, "frozen", False):
        command = [get_python_executable(background=True), "--netops-automation-worker", "--daemon"]
    else:
        command = [get_python_executable(background=True), str(worker_script_path()), "--daemon"]
    flags = 0
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(
        command,
        cwd=str(worker_script_path().parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=flags,
        close_fds=os.name != "nt",
    )
    for _ in range(20):
        time.sleep(0.15)
        status = worker_status()
        if status.get("alive"):
            return status
    return {"alive": process_alive(process.pid), "pid": process.pid, "starting": True}


def stop_worker() -> bool:
    status = worker_status()
    pid = int(status.get("pid") or 0)
    if pid <= 0:
        return True
    try:
        set_meta("worker_stop_requested", {"pid": pid, "ts": utc_ts()})
        if psutil is not None:
            process = psutil.Process(pid)
            process.terminate()
            try:
                process.wait(timeout=5)
            except psutil.TimeoutExpired:
                process.kill()
        elif os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=10)
        else:
            os.kill(pid, 15)
        return True
    except Exception:
        return False


def run_in_subprocess(automation_id: str, trigger_info: Optional[dict[str, Any]] = None) -> subprocess.Popen:
    if emergency_stop_active():
        raise AutomationError("NetOps acil durdurma etkin; yeni otomasyon kuyruğa alınmadı.")
    queue_item = enqueue_automation(automation_id, trigger_info or {"type": "manual"})
    if queue_item.get("deduplicated"):
        raise AutomationError("Bu otomasyon zaten kuyrukta veya çalışıyor.")
    payload_value = dict(trigger_info or {"type": "manual"})
    payload_value["queue_id"] = queue_item["id"]
    payload = json.dumps(payload_value, ensure_ascii=False)
    if getattr(sys, "frozen", False):
        command = [
            get_python_executable(background=True),
            "--netops-automation-worker",
            "--run",
            automation_id,
            "--trigger-json",
            payload,
        ]
    else:
        command = [
            get_python_executable(background=True),
            str(worker_script_path()),
            "--run",
            automation_id,
            "--trigger-json",
            payload,
        ]
    flags = 0
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        return subprocess.Popen(
            command,
            cwd=str(worker_script_path().parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=flags,
            close_fds=os.name != "nt",
        )
    except Exception as exc:
        _set_queue_status(queue_item["id"], "failed", error=str(exc))
        raise
