from __future__ import annotations

import json
import queue
import os
import re
import subprocess
import sys
import threading
import time
import traceback
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

if "--neto-agent-worker" in sys.argv:
    try:
        from neto_agent_worker import main as _neto_agent_worker_main

        _neto_agent_worker_argv = [
            arg for arg in sys.argv[1:] if arg != "--neto-agent-worker"
        ]
        raise SystemExit(_neto_agent_worker_main(_neto_agent_worker_argv))
    except SystemExit:
        raise
    except BaseException as _neto_agent_worker_boot_error:
        try:
            print(
                f"NETO_AGENT_WORKER_BOOT_ERROR: {_neto_agent_worker_boot_error}",
                file=sys.stderr,
                flush=True,
            )
            traceback.print_exc()
        except Exception:
            pass
        raise SystemExit(70)

from neto_agent_crypto import (
    config_path,
    make_runtime_file,
    read_encrypted_json,
    read_live_status_json,
    restrict_folder_to_current_user,
    secure_delete,
    vault_root,
    write_encrypted_json,
)

AGENT_VERSION = "10.37.13"
DEFAULT_CONFIG = {
    "enabled": False,
    "visible_actions": True,
    "visible_mouse": True,
    "agent_pointer_enabled": False,
    "replace_system_cursor": True,
    "edge_animation": True,
    "last_chat_app": "",
    "confirm_message_send": True,
    "mouse_duration": 0.45,
    "cloud_access": False,
    "screenshots": False,
    "clipboard": False,
    "encrypted_vault": True,
}


def _ensure_windows_cursor_visible() -> None:
    if os.name != "nt":
        return
    try:
        import ctypes
        user32 = ctypes.windll.user32
        user32.SystemParametersInfoW(0x0057, 0, None, 0)  # SPI_SETCURSORS
        for _ in range(32):
            if user32.ShowCursor(True) >= 0:
                break
    except Exception:
        pass

_CONFIG_LOCK = threading.RLock()


def load_config() -> dict[str, Any]:
    with _CONFIG_LOCK:
        result = dict(DEFAULT_CONFIG)
        path = config_path()
        try:
            if path.is_file():
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    for key in DEFAULT_CONFIG:
                        if key in loaded:
                            result[key] = loaded[key]
        except Exception:
            pass
        return result


def save_config(config: dict[str, Any]) -> None:
    with _CONFIG_LOCK:
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        restrict_folder_to_current_user(path.parent)
        safe = dict(DEFAULT_CONFIG)
        for key in DEFAULT_CONFIG:
            if key in config:
                safe[key] = config[key]
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(safe, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temporary, path)


def get_config_value(name: str, default: Any = None) -> Any:
    return load_config().get(name, default)


def set_config_value(name: str, value: Any) -> None:
    config = load_config()
    config[name] = value
    save_config(config)


def is_enabled() -> bool:
    return bool(get_config_value("enabled", False))


def set_enabled(value: bool) -> None:
    set_config_value("enabled", bool(value))


_WEB_SEARCH_PROVIDER_RE = re.compile(
    r"(?ix)(?:"
    r"google(?:['’]?(?:da|de))?|google\s+(?:üzerinden|uzerinden)|"
    r"internette|internet(?:te)?|web(?:['’]?(?:de|da))?|"
    r"tarayıcıda|tarayicida|browser(?:da)?"
    r")"
)
_WEB_SEARCH_ACTION_RE = re.compile(
    r"(?ix)\b(?:ara|arat|arasın|arasin|arama\s+yap|search|search\s+for)\b"
)
_WEB_SEARCH_PATTERNS = (
    re.compile(
        r"(?ix)^\s*(?P<provider>"
        r"google(?:['’]?(?:da|de))?|google\s+(?:üzerinden|uzerinden)|"
        r"internette|internet(?:te)?|web(?:['’]?(?:de|da))?|"
        r"tarayıcıda|tarayicida|browser(?:da)?"
        r")\s+(?P<query>.+?)\s+"
        r"(?:ara|arat|arasın|arasin|arama\s+yap|search|search\s+for)\s*$"
    ),
    re.compile(
        r"(?ix)^\s*(?P<provider>"
        r"google(?:['’]?(?:da|de))?|google\s+(?:üzerinden|uzerinden)|"
        r"internette|internet(?:te)?|web(?:['’]?(?:de|da))?|"
        r"tarayıcıda|tarayicida|browser(?:da)?"
        r")\s+"
        r"(?:ara|arat|arama\s+yap|search|search\s+for)\s+"
        r"(?P<query>.+?)\s*$"
    ),
    re.compile(
        r"(?ix)^\s*(?P<query>.+?)\s+"
        r"(?P<provider>"
        r"google(?:['’]?(?:da|de))?|google\s+(?:üzerinden|uzerinden)|"
        r"internette|internet(?:te)?|web(?:['’]?(?:de|da))?|"
        r"tarayıcıda|tarayicida|browser(?:da)?"
        r")\s+"
        r"(?:ara|arat|arasın|arasin|arama\s+yap|search|search\s+for)\s*$"
    ),
)


def _clean_search_query(value: str) -> str:
    value = _clean_spacing(value)
    value = re.sub(
        r"(?ix)^(?:lütfen|lutfen|please|benim\s+için|benim\s+icin)\s+",
        "",
        value,
    )
    value = re.sub(
        r"(?ix)\s+(?:lütfen|lutfen|please)$",
        "",
        value,
    )
    return _clean_spacing(value)


def _parse_web_search(raw: str):
    for pattern in _WEB_SEARCH_PATTERNS:
        match = pattern.match(raw)
        if not match:
            continue
        query = _clean_search_query(match.group("query"))
        if not query or len(query) > 240:
            return None
        return ParsedTask(
            kind="web_search",
            app=None,
            target=None,
            query=query,
            provider="google",
            message=None,
            confidence=0.98,
        )
    return None


_CHAT_SEND_RE = re.compile(
    r"(?ix)\b(?:"
    r"gönder|gondersin|göndersin|yolla|yollasın|yollasin|"
    r"mesaj\s+at|mesaj\s+gönder|mesaj\s+gonder|"
    r"send|send\s+message"
    r")\b[\s.!?]*$"
)
_CHAT_TARGET_NOUN_RE = re.compile(
    r"(?ix)\b(?:"
    r"sohbetini|sohbetine|sohbeti|sohbet|"
    r"konuşmasını|konusmasini|konuşmasına|konusmasina|konuşma|konusma|"
    r"chatini|chatine|chat|conversation"
    r")\b"
)
_CHAT_OPEN_TARGET_RE = re.compile(
    r"(?ix)^\s*(?P<target>.+?)\s+"
    r"(?:sohbetini|sohbetine|sohbeti|sohbet|"
    r"konuşmasını|konusmasini|konuşmasına|konusmasina|"
    r"chatini|chatine|chat|conversation)\s+"
    r"(?:aç|ac|gir|git|bul|seç|sec|open|enter|find|select)"
    r"[\s,;:-]*(?:ve\s+|sonra\s+|ardından\s+|ardindan\s+)?"
    r"(?P<message>.+?)\s*$"
)
_CHAT_RECIPIENT_RE = re.compile(
    r"(?ix)^\s*(?P<target>.+?)"
    r"(?:['’](?:a|e|ya|ye)|\s+(?:kişisine|kisisine|kişiye|kisiye))\s+"
    r"(?P<message>.+?)\s*$"
)

_CHAT_COMPOSE_ONLY_RE = re.compile(
    r"(?ix)^\s*(?P<target>.+?)\s+"
    r"(?:(?:kişisine|kisisine|kişiye|kisiye|"
    r"sohbetine|sohbetini|sohbeti|chatine|chatini)\s+)?"
    r"(?:mesaj\s+at|mesaj\s+gönder|mesaj\s+gonder|"
    r"mesaj\s+yolla|message\s+send)\s*[.!?]*\s*$"
)

_CHAT_LOCATIVE_APP_RE = re.compile(
    r"(?ix)^\s*(?P<app>.+?)"
    r"(?:['’](?:da|de|ta|te)|\s+uygulamasında|\s+uygulamasinda|\s+içinde|\s+icinde)\s+"
    r"(?P<remainder>.+?)\s*$"
)


def _clean_message_text(value: str) -> str:
    value = _clean_spacing(value)
    value = re.sub(
        r"(?ix)\s+(?:mesajını|mesajini|mesajı|mesaji|mesaj)\s*$",
        "",
        value,
    )
    value = re.sub(
        r"(?ix)\s+(?:yazıp|yazip|yaz|type|write)(?:\s+ve)?\s*$",
        "",
        value,
    )
    return _clean_spacing(value)


def _extract_quoted_message(value: str) -> tuple[str | None, str]:
    match = re.search(r'["“](.+?)["”]', value)
    if match is None:
        return None, value
    message = _clean_message_text(match.group(1))
    remaining = _clean_spacing(value[: match.start()] + " " + value[match.end() :])
    return message or None, remaining


def _parse_bare_dative_recipient(value: str) -> tuple[str, str] | None:
    """Apostrofsuz Türkçe hedefleri işler: abime, anneme, Ahmete gibi."""
    match = re.match(r"^\s*(?P<word>\S{3,}?)\s+(?P<message>.+?)\s*$", value)
    if match is None:
        return None

    word = match.group("word")
    lowered = word.casefold()
    if lowered.endswith(("ya", "ye")):
        stem = word[:-2]
    elif lowered.endswith(("a", "e")):
        stem = word[:-1]
    else:
        return None

    # Serbest mesajın ilk kelimesini yanlışlıkla hedef saymamak için:
    # özel adlarda büyük harf, ilişki adlarında ise iyelik eki beklenir.
    stem_folded = stem.casefold()
    looks_like_name = bool(stem[:1].isupper())
    looks_like_possessive = stem_folded.endswith(("m", "n", "ım", "im", "um", "üm"))
    if not (looks_like_name or looks_like_possessive):
        return None

    target = _clean_target_name(stem)
    message = _clean_message_text(match.group("message"))
    if not target or not message:
        return None
    return target, message


def _parse_chat_message(raw: str):
    compose_only = _CHAT_COMPOSE_ONLY_RE.match(raw)
    if compose_only is not None:
        target = _clean_target_name(compose_only.group("target"))
        if target and len(target) <= 160:
            return ParsedTask(
                kind="chat_message",
                app=None,
                target=target,
                query=None,
                provider=None,
                message=None,
                confidence=0.94,
            )

    send_match = _CHAT_SEND_RE.search(raw)
    if send_match is None:
        return None

    before_send = _clean_spacing(raw[: send_match.start()])
    if not before_send:
        return None

    app = ""
    remainder = ""

    open_action = _OPEN_ACTION_RE.search(before_send)
    if open_action is not None:
        app = _clean_app_name(before_send[: open_action.start()])
        remainder = _clean_spacing(before_send[open_action.end() :])
    else:
        locative = _CHAT_LOCATIVE_APP_RE.match(before_send)
        if locative is None:
            return None
        app = _clean_app_name(locative.group("app"))
        remainder = _clean_spacing(locative.group("remainder"))

    for _ in range(4):
        updated = _SEQUENCE_PREFIX_RE.sub("", remainder)
        if updated == remainder:
            break
        remainder = updated

    if not app or not remainder or len(app) > 120:
        return None

    quoted_message, remainder_without_quote = _extract_quoted_message(remainder)
    target = ""
    message = quoted_message or ""

    open_target = _CHAT_OPEN_TARGET_RE.match(remainder_without_quote)
    if open_target is not None:
        target = _clean_target_name(open_target.group("target"))
        if not message:
            message = _clean_message_text(open_target.group("message"))
    else:
        recipient = _CHAT_RECIPIENT_RE.match(remainder_without_quote)
        if recipient is not None:
            target = _clean_target_name(recipient.group("target"))
            if not message:
                message = _clean_message_text(recipient.group("message"))
        else:
            bare_recipient = _parse_bare_dative_recipient(remainder_without_quote)
            if bare_recipient is not None:
                target, bare_message = bare_recipient
                if not message:
                    message = bare_message

    if quoted_message and not target:
        target_candidate = _CHAT_TARGET_NOUN_RE.sub(" ", remainder_without_quote)
        target_candidate = _TARGET_ACTION_RE.sub(" ", target_candidate)
        target = _clean_target_name(target_candidate)

    if not target or not message:
        return None
    if len(target) > 160 or len(message) > 4000:
        return None

    return ParsedTask(
        kind="chat_message",
        app=app,
        target=target,
        query=None,
        provider=None,
        message=message,
        confidence=0.97,
    )


_OPEN_ACTION_RE = re.compile(
    r"(?ix)\b(?:"
    r"açıp|acip|açtıktan\s+sonra|actiktan\s+sonra|"
    r"açabilir\s+misin|acabilir\s+misin|açar\s+mısın|acar\s+misin|"
    r"açın|acin|açsın|acsin|açacak|acacak|aç|ac|"
    r"başlatıp|baslatip|başlat|baslat|"
    r"çalıştırıp|calistirip|çalıştır|calistir|çalışsın|calissin|"
    r"open|launch|start|run"
    r")\b"
)
_TARGET_ACTION_RE = re.compile(
    r"(?ix)\b(?:"
    r"aç|ac|gir|girsin|git|bul|seç|sec|göster|goster|"
    r"open|enter|select|show|find|go"
    r")\b"
)
_SEQUENCE_PREFIX_RE = re.compile(
    r"(?ix)^(?:"
    r"ve\s+sonra|sonra|ardından|ardindan|daha\s+sonra|"
    r"ve|then|afterwards|and\s+then"
    r")\b[\s,;:-]*"
)
_LOCATIVE_TASK_RE = re.compile(
    r"(?ix)^\s*(?P<app>.+?)"
    r"(?:\s+uygulamasında|\s+uygulamasinda|\s+içinde|\s+icinde|"
    r"['’](?:da|de|ta|te))\s+"
    r"(?P<target>.+?)\s+"
    r"(?:sohbetini|sohbetine|sohbeti|sohbet|"
    r"konuşmasını|konusmasini|konuşmasına|konusmasina|konuşmayı|konusmayi|"
    r"görüşmesini|gorusmesini|görüşmesine|gorusmesine|"
    r"chatini|chatine|chat|conversation)"
    r"(?:\s+(?:aç|ac|gir|git|bul|seç|sec|open|enter|select|find))?\s*$"
)
_TARGET_NOUN_RE = re.compile(
    r"(?ix)\b(?:"
    r"sohbetini|sohbetine|sohbeti|sohbet|"
    r"konuşmasını|konusmasini|konuşmasına|konusmasina|konuşmayı|konusmayi|konuşma|konusma|"
    r"görüşmesini|gorusmesini|görüşmesine|gorusmesine|görüşme|gorusme|"
    r"chatini|chatine|chat|conversation|öğeyi|ogeyi|öğe|oge"
    r")\b"
)
_FILLER_RE = re.compile(
    r"(?ix)\b(?:"
    r"uygulamasını|uygulamasini|uygulamayı|uygulamayi|uygulama|"
    r"programını|programini|programı|programi|program|"
    r"lütfen|lutfen|please|benim\s+için|benim\s+icin"
    r")\b"
)


def _clean_spacing(value: str) -> str:
    value = str(value or "").replace("\u00a0", " ")
    value = re.sub(r"[\t\r\n]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(' \t\r\n,.;:!?"“”')


def _strip_terminal_name_suffix(value: str) -> str:
    """Remove only Turkish grammatical suffixes separated by an apostrophe."""
    value = _clean_spacing(value)
    value = re.sub(
        r"(?i)(?:['’](?:y?[ıiuü]|n[ıiuü]n|[dt][ae]|y[ae]))$",
        "",
        value,
    )
    return _clean_spacing(value)


def _clean_app_name(value: str) -> str:
    value = _FILLER_RE.sub(" ", str(value or ""))
    value = _SEQUENCE_PREFIX_RE.sub("", value)
    value = _clean_spacing(value)
    return _strip_terminal_name_suffix(value)


def _clean_target_name(value: str) -> str:
    value = _SEQUENCE_PREFIX_RE.sub("", str(value or ""))
    value = _TARGET_ACTION_RE.sub(" ", value)
    value = _TARGET_NOUN_RE.sub(" ", value)
    value = _FILLER_RE.sub(" ", value)
    value = _clean_spacing(value)
    return _strip_terminal_name_suffix(value)


@dataclass(frozen=True)
class ParsedTask:
    kind: str
    app: str | None
    target: str | None
    query: str | None
    provider: str | None
    message: str | None
    confidence: float


def parse_task(text: str) -> ParsedTask | None:
    """Yerel uygulama ve görünür web arama görevlerini sabit adlar olmadan ayrıştır."""
    raw = _clean_spacing(text)
    if not raw or len(raw) > 320:
        return None

    web_task = _parse_web_search(raw)
    if web_task is not None:
        return web_task

    chat_task = _parse_chat_message(raw)
    if chat_task is not None:
        return chat_task

    locative = _LOCATIVE_TASK_RE.match(raw)
    if locative:
        app = _clean_app_name(locative.group("app"))
        target = _clean_target_name(locative.group("target"))
        if app and target and len(app) <= 120 and len(target) <= 160:
            return ParsedTask(kind="application", app=app, target=target, query=None, provider=None, message=None, confidence=0.95)

    action = _OPEN_ACTION_RE.search(raw)
    if action is None:
        return None

    app = _clean_app_name(raw[: action.start()])
    remainder = _clean_spacing(raw[action.end() :])
    for _ in range(3):
        updated = _SEQUENCE_PREFIX_RE.sub("", remainder)
        if updated == remainder:
            break
        remainder = updated

    # "Discord'u aç" yanında "aç Discord'u" ve "programı aç Discord" da çalışır.
    if not app and remainder:
        action_first_app = _clean_app_name(remainder)
        if action_first_app and not _TARGET_NOUN_RE.search(remainder):
            app = action_first_app
            remainder = ""

    if not app or len(app) > 120:
        return None

    target = _clean_target_name(remainder) if remainder else ""
    if target and len(target) > 160:
        return None
    if remainder and not target:
        return None

    return ParsedTask(
        kind="application",
        app=app,
        target=target or None,
        query=None,
        provider=None,
        message=None,
        confidence=0.96 if target else 0.88,
    )

class AgentController:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.process: subprocess.Popen | None = None
        self.session_id: str | None = None
        self.request_path: Path | None = None
        self.status_path: Path | None = None
        self.last_sequence = 0
        self.last_status: dict[str, Any] | None = None
        self.launcher_script: str | None = None
        self._status_queue: queue.SimpleQueue[dict[str, Any]] = queue.SimpleQueue()
        self._reader_thread: threading.Thread | None = None
        self._last_activity_monotonic = time.monotonic()
        self._completed_processes: set[int] = set()

    def active(self) -> bool:
        with self._lock:
            process = self.process
            return process is not None and process.poll() is None

    def start(
        self,
        task: ParsedTask,
        launcher_script: str | None = None,
        *,
        confirmed_send: bool = False,
    ) -> str:
        if not is_enabled():
            raise RuntimeError("NetOps Agent ayarlardan kapalı.")
        if os.name != "nt":
            raise RuntimeError("NetOps Agent yalnızca Windows üzerinde çalışır.")

        with self._lock:
            if self.active():
                raise RuntimeError("NetOps Agent şu anda başka bir görev yürütüyor.")

            # A user can start the next task before the UI's delayed cleanup runs.
            # Remove only the previous terminal status here; never let that delayed
            # cleanup delete the new session's status file.
            if self.last_status and self.last_status.get("done") and self.status_path is not None:
                secure_delete(self.status_path)
                self.status_path = None
                self.request_path = None

            session_id = uuid.uuid4().hex
            request_path = make_runtime_file(session_id, "request.dpapi")
            status_path = make_runtime_file(session_id, "status.json")
            write_encrypted_json(
                request_path,
                {
                    "session_id": session_id,
                    "kind": task.kind,
                    "app": task.app,
                    "target": task.target,
                    "query": task.query,
                    "provider": task.provider,
                    "message": task.message,
                    "confirmed_send": bool(
                        task.kind != "chat_message" or confirmed_send
                    ),
                    "agent_options": {
                        "visible_mouse": True,
                        "agent_pointer_enabled": bool(
                            get_config_value("replace_system_cursor", True)
                        ),
                        "replace_system_cursor": bool(
                            get_config_value("replace_system_cursor", True)
                        ),
                        "edge_animation": bool(
                            get_config_value("edge_animation", True)
                        ),
                        "visible_actions": bool(
                            get_config_value("visible_actions", True)
                        ),
                        "mouse_duration": float(
                            get_config_value("mouse_duration", 0.26)
                        ),
                    },
                    "created_at": time.time(),
                    "privacy": {
                        "cloud_access": False,
                        "screenshots": False,
                        "clipboard": False,
                    },
                },
            )

            command = self._worker_command(request_path, status_path, launcher_script)
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=flags,
                close_fds=True,
            )
            self.process = process
            self._status_queue = queue.SimpleQueue()
            self._last_activity_monotonic = time.monotonic()
            self.session_id = session_id
            self.request_path = request_path
            self.status_path = status_path
            self.last_sequence = 0
            self.last_status = None
            self.launcher_script = launcher_script
            self._start_status_reader(process, session_id)
            return session_id

    def _start_status_reader(
        self,
        process: subprocess.Popen,
        session_id: str,
    ) -> None:
        """Drain worker stdout so progress never blocks on a full pipe."""

        status_queue = self._status_queue

        def _reader() -> None:
            stream = process.stdout
            if stream is None:
                return
            try:
                for raw_line in stream:
                    line = str(raw_line or "").strip()
                    if not line.startswith("NETO_AGENT_STATUS:"):
                        continue
                    try:
                        payload = json.loads(line.split(":", 1)[1])
                    except Exception:
                        continue
                    if not isinstance(payload, dict):
                        continue
                    if str(payload.get("session_id") or "") != session_id:
                        continue
                    status_queue.put(payload)
                    self._last_activity_monotonic = time.monotonic()
                    if payload.get("done"):
                        self._detach_completed_process(process)
            finally:
                try:
                    stream.close()
                except Exception:
                    pass

        thread = threading.Thread(
            target=_reader,
            name=f"NetoAgentStatusReader-{session_id[:8]}",
            daemon=True,
        )
        self._reader_thread = thread
        thread.start()

    def _detach_completed_process(
        self,
        process: subprocess.Popen | None = None,
        *,
        grace_seconds: float = 2.0,
    ) -> None:
        """Release the UI immediately, then reap/kill a stuck audit worker."""
        with self._lock:
            current = process or self.process
            if current is None:
                return
            pid = int(getattr(current, "pid", 0) or 0)
            if pid and pid in self._completed_processes:
                if self.process is current:
                    self.process = None
                return
            if pid:
                self._completed_processes.add(pid)
            if self.process is current:
                self.process = None

        def _reap() -> None:
            try:
                current.wait(timeout=max(0.2, float(grace_seconds)))
            except subprocess.TimeoutExpired:
                try:
                    current.terminate()
                    current.wait(timeout=0.6)
                except Exception:
                    try:
                        current.kill()
                    except Exception:
                        pass
            except Exception:
                pass
            finally:
                if pid:
                    with self._lock:
                        self._completed_processes.discard(pid)

        threading.Thread(
            target=_reap,
            name=f"NetoAgentWorkerReaper-{pid or 'unknown'}",
            daemon=True,
        ).start()

    def _worker_command(self, request_path: Path, status_path: Path, launcher_script: str | None) -> list[str]:
        args = [
            "--neto-agent-worker",
            "--request",
            str(request_path),
            "--status",
            str(status_path),
        ]
        executable = Path(sys.executable)
        if getattr(sys, "frozen", False) or executable.suffix.lower() == ".exe" and "python" not in executable.name.casefold():
            return [str(executable), *args]
        script = Path(launcher_script or "").resolve() if launcher_script else None
        if script is not None and script.is_file():
            return [str(executable), str(script), *args]
        worker_script = Path(__file__).resolve().with_name("neto_agent_worker.py")
        if worker_script.is_file():
            return [str(executable), str(worker_script), "--request", str(request_path), "--status", str(status_path)]
        raise RuntimeError("NetOps Agent worker başlangıç dosyası bulunamadı.")

    def poll(self) -> dict[str, Any] | None:
        with self._lock:
            path = self.status_path
            process = self.process

            newest: dict[str, Any] | None = None
            while True:
                try:
                    candidate = self._status_queue.get_nowait()
                except queue.Empty:
                    break
                if isinstance(candidate, dict):
                    if newest is None or int(candidate.get("sequence", 0)) >= int(newest.get("sequence", 0)):
                        newest = candidate

            if newest is None and path is not None and path.exists():
                try:
                    candidate = read_live_status_json(path)
                    if isinstance(candidate, dict):
                        newest = candidate
                except Exception:
                    newest = None

            if newest is not None:
                sequence = int(newest.get("sequence", 0))
                if sequence > self.last_sequence:
                    self.last_sequence = sequence
                    self.last_status = newest
                    self._last_activity_monotonic = time.monotonic()
                    if newest.get("done"):
                        _ensure_windows_cursor_visible()
                        self._detach_completed_process(process)
                        self._finalize_runtime_files(keep_status=True)
                    return newest

            # Defensive watchdog for older/mixed workers: once a physical Enter
            # acknowledgement is observed, no storage/audit code may hold the UI.
            if (
                self.last_status
                and self.last_status.get("code") == "message_sent"
                and not self.last_status.get("done")
                and time.monotonic() - self._last_activity_monotonic >= 2.0
            ):
                status = {
                    **self.last_status,
                    "sequence": self.last_sequence + 1,
                    "code": "completed_watchdog",
                    "message": "Enter gönderildi; görev watchdog tarafından kapatıldı.",
                    "done": True,
                    "ok": True,
                }
                self.last_sequence += 1
                self.last_status = status
                _ensure_windows_cursor_visible()
                self._detach_completed_process(process, grace_seconds=0.1)
                self._finalize_runtime_files(keep_status=True)
                return status

            if process is not None and process.poll() is not None:
                _ensure_windows_cursor_visible()
                if self.last_status is None or not self.last_status.get("done"):
                    status = {
                        "session_id": self.session_id,
                        "sequence": self.last_sequence + 1,
                        "code": "worker_exited",
                        "message": "Ajan süreci beklenmedik biçimde kapandı.",
                        "step": 8,
                        "total": 8,
                        "done": True,
                        "ok": False,
                        "network_data_sent": False,
                        "screenshots_taken": False,
                    }
                    self.last_sequence += 1
                    self.last_status = status
                    self._finalize_runtime_files(keep_status=False)
                    return status
                self._finalize_runtime_files(keep_status=False)
            return None

    def stop(self, reason: str = "Kullanıcı tarafından durduruldu.") -> None:
        with self._lock:
            process = self.process
            if process is not None and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=2.5)
                except Exception:
                    try:
                        process.kill()
                    except Exception:
                        pass
            self.last_sequence += 1
            self.last_status = {
                "session_id": self.session_id,
                "sequence": self.last_sequence,
                "code": "stopped",
                "message": reason,
                "step": 5,
                "total": 5,
                "done": True,
                "ok": False,
                "network_data_sent": False,
                "screenshots_taken": False,
            }
            self._finalize_runtime_files(keep_status=False)
            _ensure_windows_cursor_visible()

    def _finalize_runtime_files(self, *, keep_status: bool) -> None:
        if self.request_path is not None:
            secure_delete(self.request_path)
        if not keep_status and self.status_path is not None:
            secure_delete(self.status_path)
        if self.process is not None and self.process.poll() is not None:
            self.process = None

    def cleanup_completed_status(self, session_id: str | None = None) -> None:
        with self._lock:
            if session_id and str(self.session_id or "") != str(session_id):
                return
            if self.status_path is not None:
                secure_delete(self.status_path)
            self.status_path = None
            self.request_path = None


_CONTROLLER = AgentController()


def get_controller() -> AgentController:
    return _CONTROLLER


def start_text_task(text: str, launcher_script: str | None = None) -> str:
    task = parse_task(text)
    if task is None:
        raise ValueError("NetOps Agent bu görevi güvenli ve kesin biçimde ayrıştıramadı.")
    if task.kind == "chat_message":
        raise PermissionError(
            "Mesaj gönderme görevi NetOps Agent sekmesindeki görünür onaydan başlatılmalıdır."
        )
    return get_controller().start(task, launcher_script=launcher_script)


def try_handle_text(text: str, launcher_script: str | None = None) -> str | None:
    if not is_enabled():
        return None
    task = parse_task(text)
    if task is None:
        return None

    if task.kind == "web_search":
        return (
            "Bu web araması sorguyu Google'a gönderecek. "
            "Görevi NetOps Agent sekmesinden başlatıp aktarımı onayla."
        )

    if task.kind == "chat_message":
        return (
            "Mesaj gönderme işlemi görünür kullanıcı onayı gerektiriyor. "
            "Görevi NetOps Agent sekmesinden başlat."
        )

    get_controller().start(task, launcher_script=launcher_script)
    return "NetOps Agent görevi başlatıldı. Adımları NetOps Agent sekmesinden görebilirsin."


def clear_vault() -> int:
    count = 0
    for path in vault_root().glob("*.netovault"):
        try:
            secure_delete(path)
            count += 1
        except Exception:
            pass
    return count


def create_agent_panel(
    parent,
    *,
    root,
    palette_getter: Callable[[], dict[str, str]],
    launcher_script: str,
    close_command: Callable[[], None] | None = None,
):
    import customtkinter as ctk
    from tkinter import messagebox

    palette = palette_getter()
    frame = ctk.CTkFrame(parent, fg_color=palette["sidebar"], corner_radius=0)
    frame.pack(fill="both", expand=True, padx=16, pady=16)

    top = ctk.CTkFrame(frame, fg_color=palette["card"], corner_radius=14)
    top.pack(fill="x", pady=(0, 12))

    title_box = ctk.CTkFrame(top, fg_color="transparent")
    title_box.pack(side="left", fill="x", expand=True, padx=16, pady=14)
    ctk.CTkLabel(
        title_box,
        text="NetOps Agent",
        anchor="w",
        font=("Segoe UI Semibold", 22),
        text_color=palette["text_main"],
    ).pack(fill="x")
    status_label = ctk.CTkLabel(
        title_box,
        text="Kapalı" if not is_enabled() else "Hazır",
        anchor="w",
        font=("Segoe UI", 11),
        text_color=palette["text_dim"],
    )
    status_label.pack(fill="x", pady=(2, 0))

    enabled_var = ctk.BooleanVar(value=is_enabled())

    def toggle_agent():
        value = bool(enabled_var.get())
        set_enabled(value)
        status_label.configure(text="Hazır" if value else "Kapalı")
        start_button.configure(state="normal" if value else "disabled")
        if not value:
            append_log("NetOps Agent kapatıldı; aktif worker durduruldu.")

    switch = ctk.CTkSwitch(
        top,
        text="Açık",
        variable=enabled_var,
        command=toggle_agent,
        progress_color=palette["neon"],
        text_color=palette["text_main"],
    )
    switch.pack(side="right", padx=16, pady=14)

    privacy = ctk.CTkFrame(frame, fg_color=palette["card"], corner_radius=14)
    privacy.pack(fill="x", pady=(0, 12))
    ctk.CTkLabel(
        privacy,
        text="Mahremiyet",
        anchor="w",
        font=("Segoe UI Semibold", 15),
        text_color=palette["text_main"],
    ).pack(fill="x", padx=16, pady=(14, 4))
    ctk.CTkLabel(
        privacy,
        text=(
            "Yerel uygulama görevlerinde buluta veri gönderilmez • ekran görüntüsü alınmaz • "
            "pano okunmaz • görünür fare hareketi isteğe bağlıdır • worker görev sonunda kapanır • "
            "oturum kaydı Windows DPAPI ile şifrelenir.\n"
            "Not: Windows yöneticisi veya işletim sistemi çekirdeğine karşı mutlak görünmezlik garanti edilemez."
        ),
        justify="left",
        anchor="w",
        wraplength=760,
        font=("Segoe UI", 11),
        text_color=palette["text_dim"],
    ).pack(fill="x", padx=16, pady=(0, 14))


    options_card = ctk.CTkFrame(frame, fg_color=palette["card"], corner_radius=14)
    options_card.pack(fill="x", pady=(0, 12))

    visible_mouse_var = ctk.BooleanVar(
        value=bool(get_config_value("visible_mouse", True))
    )
    agent_pointer_var = ctk.BooleanVar(
        value=bool(get_config_value("replace_system_cursor", True))
    )
    edge_animation_var = ctk.BooleanVar(
        value=bool(get_config_value("edge_animation", True))
    )
    confirm_send_var = ctk.BooleanVar(
        value=bool(get_config_value("confirm_message_send", True))
    )

    def update_visible_mouse():
        set_config_value("visible_mouse", bool(visible_mouse_var.get()))
        append_log(
            "Görünür fare açıldı."
            if visible_mouse_var.get()
            else "Görünür fare kapatıldı."
        )

    def toggle_agent_pointer():
        enabled = not bool(agent_pointer_var.get())
        agent_pointer_var.set(enabled)
        set_config_value("replace_system_cursor", enabled)
        pointer_button.configure(
            text=(
                "➤ Gerçek Mor Windows İmleci: AÇIK"
                if enabled
                else "➤ Gerçek Mor Windows İmleci: KAPALI"
            ),
            fg_color=(
                palette["neon"]
                if enabled
                else palette.get("button_bg", palette["card"])
            ),
        )
        append_log(
            "Windows sistem imleci görev sırasında gerçek mor imleçle değiştirilecek."
            if enabled
            else "Gerçek mor Windows imleci kapatıldı."
        )

    def update_edge_animation():
        enabled = bool(edge_animation_var.get())
        set_config_value("edge_animation", enabled)
        append_log(
            "Ekran kenarı görev animasyonu açıldı."
            if enabled
            else "Ekran kenarı görev animasyonu kapatıldı."
        )

    def update_confirm_send():
        set_config_value(
            "confirm_message_send",
            bool(confirm_send_var.get()),
        )
        append_log(
            "Mesaj gönderme onayı açıldı."
            if confirm_send_var.get()
            else "Mesaj gönderme onayı kapatıldı."
        )

    ctk.CTkLabel(
        options_card,
        text="Agent davranışı",
        anchor="w",
        font=("Segoe UI Semibold", 15),
        text_color=palette["text_main"],
    ).pack(fill="x", padx=16, pady=(14, 8))

    ctk.CTkLabel(
        options_card,
        text=f"Agent motoru {AGENT_VERSION}",
        anchor="w",
        font=("Segoe UI", 10),
        text_color=palette["text_dim"],
    ).pack(fill="x", padx=16, pady=(0, 8))


    pointer_button = ctk.CTkButton(
        options_card,
        text=(
            "➤ Gerçek Mor Windows İmleci: AÇIK"
            if agent_pointer_var.get()
            else "➤ Gerçek Mor Windows İmleci: KAPALI"
        ),
        command=toggle_agent_pointer,
        fg_color=(
            palette["neon"]
            if agent_pointer_var.get()
            else palette.get("button_bg", palette["card"])
        ),
        hover_color=palette.get("accent_hover", palette["button_hover"]),
        text_color="#FFFFFF",
        anchor="w",
        height=40,
    )
    pointer_button.pack(fill="x", padx=16, pady=(0, 8))

    ctk.CTkSwitch(
        options_card,
        text="Görev sırasında ekran kenarlarını mor/siyah canlandır",
        variable=edge_animation_var,
        command=update_edge_animation,
        progress_color=palette["neon"],
        text_color=palette["text_main"],
    ).pack(anchor="w", padx=16, pady=(0, 8))

    ctk.CTkSwitch(
        options_card,
        text="Mesaj göndermeden önce onay iste",
        variable=confirm_send_var,
        command=update_confirm_send,
        progress_color=palette["neon"],
        text_color=palette["text_main"],
    ).pack(anchor="w", padx=16, pady=(0, 14))

    task_card = ctk.CTkFrame(frame, fg_color=palette["card"], corner_radius=14)
    task_card.pack(fill="x", pady=(0, 12))
    task_entry = ctk.CTkEntry(
        task_card,
        placeholder_text="Görevi doğal dille yaz",
        height=42,
        fg_color=palette["entry_bg"],
        border_color=palette["entry_border"],
        text_color=palette["text_main"],
    )
    task_entry.pack(fill="x", padx=14, pady=(14, 8))

    actions = ctk.CTkFrame(task_card, fg_color="transparent")
    actions.pack(fill="x", padx=14, pady=(0, 14))

    log_box = ctk.CTkTextbox(
        frame,
        fg_color=palette["entry_bg"],
        border_width=1,
        border_color=palette["entry_border"],
        text_color=palette["text_main"],
        corner_radius=14,
    )
    log_box.pack(fill="both", expand=True)
    log_box.configure(state="disabled")


    def show_task_started_toast(task: ParsedTask):
        try:
            toast = ctk.CTkToplevel(root)
            toast.withdraw()
            toast.overrideredirect(True)
            toast.attributes("-topmost", True)

            width = 350
            height = 112
            screen_width = int(root.winfo_screenwidth())
            target_x = max(8, screen_width - width - 18)
            start_x = screen_width + 8
            y = 64

            toast.geometry(f"{width}x{height}+{start_x}+{y}")

            shell = ctk.CTkFrame(
                toast,
                fg_color=palette["card"],
                border_width=2,
                border_color=palette["neon"],
                corner_radius=16,
            )
            shell.pack(fill="both", expand=True)

            ctk.CTkLabel(
                shell,
                text="NetOps Agent görevi başladı",
                anchor="w",
                font=("Segoe UI Semibold", 16),
                text_color=palette["text_main"],
            ).pack(fill="x", padx=16, pady=(14, 3))

            detail = (
                "Gerçek mor Windows imleci ve ekran kenarı animasyonu etkin."
                if get_config_value("replace_system_cursor", True)
                else "Görev görünür yerel otomasyonla yürütülüyor."
            )
            ctk.CTkLabel(
                shell,
                text=detail,
                anchor="w",
                font=("Segoe UI", 11),
                text_color=palette["text_dim"],
            ).pack(fill="x", padx=16)

            progress = ctk.CTkProgressBar(
                shell,
                progress_color=palette["neon"],
                fg_color=palette["entry_bg"],
                height=5,
            )
            progress.pack(fill="x", padx=16, pady=(12, 12))
            progress.set(0.12)

            toast.deiconify()
            toast.lift()

            steps = 12

            def slide(index=0):
                if not toast.winfo_exists():
                    return
                ratio = min(1.0, index / steps)
                eased = 1.0 - (1.0 - ratio) ** 3
                x = int(start_x + (target_x - start_x) * eased)
                toast.geometry(f"{width}x{height}+{x}+{y}")
                progress.set(min(1.0, 0.12 + ratio * 0.88))
                if index < steps:
                    root.after(16, lambda: slide(index + 1))
                else:
                    root.after(
                        3600,
                        lambda: toast.destroy()
                        if toast.winfo_exists()
                        else None,
                    )

            slide()
        except Exception:
            pass


    def append_log(text: str):
        try:
            log_box.configure(state="normal")
            stamp = time.strftime("%H:%M:%S")
            log_box.insert("end", f"[{stamp}] {text}\n")
            log_box.see("end")
            log_box.configure(state="disabled")
        except Exception:
            pass

    def start_task():
        if not is_enabled():
            messagebox.showwarning("NetOps Agent", "Önce NetOps Agent'ı aç.")
            return
        text = task_entry.get().strip()
        try:
            task = parse_task(text)
            if task is None:
                raise ValueError(
                    "Görev anlaşılamadı. Uygulama açma, sohbet içinde mesaj gönderme "
                    "veya web arama işlemini tek cümlede açıkça yaz."
                )

            if task.kind == "chat_message":
                resolved_app = str(task.app or "").strip()
                resolved_message = str(task.message or "").strip()

                if not resolved_app:
                    remembered_app = str(
                        get_config_value("last_chat_app", "") or ""
                    ).strip()

                    if remembered_app:
                        resolved_app = remembered_app
                        append_log(
                            "Son kullanılan sohbet uygulaması seçildi."
                        )
                    else:
                        app_dialog = ctk.CTkInputDialog(
                            title="NetOps Agent",
                            text="Mesajın gönderileceği uygulamanın adını yaz:",
                        )
                        resolved_app = str(
                            app_dialog.get_input() or ""
                        ).strip()

                if not resolved_app:
                    append_log("Mesaj görevi iptal edildi: uygulama seçilmedi.")
                    return

                if not resolved_message:
                    message_dialog = ctk.CTkInputDialog(
                        title="NetOps Agent",
                        text="Gönderilecek mesajı yaz:",
                    )
                    resolved_message = str(
                        message_dialog.get_input() or ""
                    ).strip()

                if not resolved_message:
                    append_log("Mesaj görevi iptal edildi: mesaj yazılmadı.")
                    return

                set_config_value("last_chat_app", resolved_app)

                task = ParsedTask(
                    kind="chat_message",
                    app=resolved_app,
                    target=task.target,
                    query=None,
                    provider=None,
                    message=resolved_message,
                    confidence=task.confidence,
                )

                append_log(
                    f"Mesaj görevi hazır: uygulama={task.app}, hedef={task.target}"
                )

            if task.kind == "web_search":
                approved = messagebox.askyesno(
                    "NetOps Agent • Ağ Onayı",
                    (
                        "Bu görev arama sorgusunu varsayılan tarayıcı üzerinden "
                        "Google'a gönderecek. Devam edilsin mi?"
                    ),
                )
                if not approved:
                    append_log("Web araması kullanıcı tarafından iptal edildi.")
                    return

            send_approved = task.kind != "chat_message"

            if task.kind == "chat_message":
                if bool(get_config_value("confirm_message_send", True)):
                    approved = messagebox.askyesno(
                        "NetOps Agent • Mesaj Onayı",
                        (
                            f"Uygulama: {task.app}\n"
                            f"Hedef: {task.target}\n\n"
                            f"Gönderilecek mesaj:\n{task.message}\n\n"
                            "Agent bu mesajı gerçekten göndersin mi?"
                        ),
                    )
                    if not approved:
                        append_log("Mesaj gönderme kullanıcı tarafından iptal edildi.")
                        return
                send_approved = True

            get_controller().start(
                task,
                launcher_script=launcher_script,
                confirmed_send=send_approved,
            )
            show_task_started_toast(task)
            append_log(
                "Görev başladı: gerçek Windows faresi ve kenar animasyonu hazırlanıyor."
            )
            status_label.configure(text="Çalışıyor")
            start_button.configure(state="disabled")
            stop_button.configure(state="normal")
        except Exception as exc:
            messagebox.showerror("NetOps Agent", str(exc))

    def stop_task():
        get_controller().stop()
        append_log("Acil durdurma uygulandı.")
        status_label.configure(text="Durduruldu")
        start_button.configure(state="normal" if is_enabled() else "disabled")
        stop_button.configure(state="disabled")

    def open_vault():
        try:
            os.startfile(str(vault_root()))
        except Exception as exc:
            messagebox.showerror("NetOps Agent", str(exc))

    def wipe_vault():
        if not messagebox.askyesno("NetOps Agent", "Şifreli yerel ajan kayıtları silinsin mi?"):
            return
        count = clear_vault()
        append_log(f"Şifreli kasadan {count} kayıt silindi.")

    start_button = ctk.CTkButton(
        actions,
        text="Görevi Başlat",
        command=start_task,
        fg_color=palette["neon"],
        hover_color=palette.get("accent_hover", palette["button_hover"]),
        text_color="#FFFFFF",
        state="normal" if is_enabled() else "disabled",
    )
    start_button.pack(side="left")

    stop_button = ctk.CTkButton(
        actions,
        text="Acil Durdur",
        command=stop_task,
        fg_color="#B91C1C",
        hover_color="#991B1B",
        text_color="#FFFFFF",
        state="normal" if get_controller().active() else "disabled",
    )
    stop_button.pack(side="left", padx=(8, 0))

    ctk.CTkButton(
        actions,
        text="Şifreli Kasayı Aç",
        command=open_vault,
        fg_color=palette["entry_bg"],
        hover_color=palette["button_hover"],
        text_color=palette["text_main"],
    ).pack(side="right")
    ctk.CTkButton(
        actions,
        text="Kasayı Temizle",
        command=wipe_vault,
        fg_color=palette["entry_bg"],
        hover_color=palette["button_hover"],
        text_color=palette["text_main"],
    ).pack(side="right", padx=(0, 8))

    poll_job = {"id": None, "last": 0}

    def poll_status():
        try:
            status = get_controller().poll()
            if status is not None:
                sequence = int(status.get("sequence", 0))
                if sequence > poll_job["last"]:
                    poll_job["last"] = sequence
                    append_log(str(status.get("message") or status.get("code") or "Durum güncellendi."))
                    step = status.get("step")
                    total = status.get("total")
                    if status.get("done"):
                        _ensure_windows_cursor_visible()
                        ok = bool(status.get("ok"))
                        status_label.configure(text="Tamamlandı" if ok else "Başarısız")
                        start_button.configure(state="normal" if is_enabled() else "disabled")
                        stop_button.configure(state="disabled")
                        completed_session = str(status.get("session_id") or "")
                        root.after(
                            800,
                            lambda sid=completed_session: get_controller().cleanup_completed_status(sid),
                        )
                    elif step and total:
                        status_label.configure(text=f"Çalışıyor • {step}/{total}")
                        stop_button.configure(state="normal")
        finally:
            try:
                poll_job["id"] = root.after(250, poll_status)
            except Exception:
                poll_job["id"] = None

    poll_status()

    def cleanup():
        job = poll_job.get("id")
        if job:
            try:
                root.after_cancel(job)
            except Exception:
                pass
        poll_job["id"] = None

    setattr(frame, "_neto_agent_cleanup", cleanup)
    setattr(frame, "_neto_agent_refresh_palette", lambda: None)
    return frame
