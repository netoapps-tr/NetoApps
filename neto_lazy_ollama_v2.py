from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional


BUILD = "19.0-lazy-ollama"
BASE_URL = os.environ.get("NETO_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
DEFAULT_MODEL = os.environ.get("NETO_OLLAMA_MODEL", "gemma3:4b")
DEFAULT_KEEP_ALIVE = os.environ.get("NETO_OLLAMA_KEEP_ALIVE", "2m")

_LOCK = threading.RLock()
_HISTORY: list[dict[str, str]] = []
_SERVICE_PROCESS: Optional[subprocess.Popen] = None


def _request_json(
    method: str,
    endpoint: str,
    payload: Optional[dict] = None,
    *,
    timeout: float = 8.0,
) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        BASE_URL + endpoint,
        data=data,
        headers=headers,
        method=method.upper(),
    )
    with urllib.request.urlopen(request, timeout=float(timeout)) as response:
        raw = response.read().decode("utf-8", errors="replace")
        value = json.loads(raw) if raw else {}
        return value if isinstance(value, dict) else {}


def api_ready(timeout: float = 1.5) -> bool:
    try:
        _request_json("GET", "/api/tags", timeout=timeout)
        return True
    except Exception:
        return False


def ollama_executable() -> Optional[str]:
    candidates = [
        shutil.which("ollama"),
        os.environ.get("OLLAMA_EXE"),
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"),
        str(Path(os.environ.get("ProgramFiles", "")) / "Ollama" / "ollama.exe"),
        str(Path.home() / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if path.is_file():
            return str(path)
    return None


def _hidden_flags() -> tuple[int, Any]:
    if os.name != "nt":
        return 0, None
    flags = 0
    for name in ("CREATE_NO_WINDOW", "DETACHED_PROCESS", "CREATE_NEW_PROCESS_GROUP"):
        flags |= int(getattr(subprocess, name, 0))
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    return flags, startup


def start_service_on_demand(wait_seconds: float = 12.0) -> bool:
    global _SERVICE_PROCESS

    if api_ready():
        return True

    executable = ollama_executable()
    if executable is None:
        return False

    with _LOCK:
        if _SERVICE_PROCESS is None or _SERVICE_PROCESS.poll() is not None:
            flags, startup = _hidden_flags()
            try:
                _SERVICE_PROCESS = subprocess.Popen(
                    [executable, "serve"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=flags,
                    startupinfo=startup,
                    close_fds=os.name != "nt",
                )
            except Exception:
                _SERVICE_PROCESS = None

    deadline = time.monotonic() + max(1.0, float(wait_seconds))
    while time.monotonic() < deadline:
        if api_ready(timeout=1.0):
            return True
        time.sleep(0.35)
    return api_ready(timeout=1.0)


def installed_models() -> list[str]:
    if not api_ready():
        return []
    try:
        data = _request_json("GET", "/api/tags", timeout=4.0)
        values = []
        for item in data.get("models", []):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("model") or "").strip()
            if name:
                values.append(name)
        return values
    except Exception:
        return []


def model_available(model: str = DEFAULT_MODEL) -> bool:
    target = str(model).casefold()
    return any(name.casefold() == target for name in installed_models())


def status() -> dict:
    ready = api_ready(timeout=1.2)
    models = installed_models() if ready else []
    return {
        "api_ready": ready,
        "executable": ollama_executable(),
        "model": DEFAULT_MODEL,
        "model_available": any(name.casefold() == DEFAULT_MODEL.casefold() for name in models),
        "models": models,
        "autostart": False,
        "keep_alive": DEFAULT_KEEP_ALIVE,
    }


def _system_prompt() -> str:
    return (
        "Sen NetOps'un yerel bilgi modelisin. Türkçe sorulara Türkçe, İngilizce sorulara İngilizce cevap ver. "
        "Kullanıcının bilgisayarında bir işlem yaptığını iddia etme. Neto'nun yerel komut sistemi zaten eşleşmeyen soruları sana gönderir. "
        "Yanıtı açık, doğru ve gereksiz uzatmadan ver. Emin değilsen bunu belirt."
    )


def answer(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    keep_alive: str | int = DEFAULT_KEEP_ALIVE,
    timeout: float = 180.0,
    system_prompt: Optional[str] = None,
) -> str:
    message = str(prompt or "").strip()
    if not message:
        return "Mesaj boş."

    if not api_ready(timeout=1.2):
        if not start_service_on_demand():
            if ollama_executable() is None:
                return "Yerel model kullanılamıyor: Ollama kurulu değil veya ollama.exe bulunamadı."
            return "Yerel model kullanılamıyor: Ollama servisi yalnızca bu mesaj için başlatılmaya çalışıldı fakat API cevap vermedi."

    if not model_available(model):
        return f"Yerel model bulunamadı: {model}. PowerShell'de `ollama pull {model}` komutunu çalıştır."

    with _LOCK:
        history = list(_HISTORY[-8:])

    messages = [
        {"role": "system", "content": system_prompt or _system_prompt()},
        *history,
        {"role": "user", "content": message},
    ]
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "keep_alive": keep_alive,
        "options": {
            "temperature": 0.2,
            "top_p": 0.85,
        },
    }

    try:
        data = _request_json("POST", "/api/chat", payload, timeout=timeout)
        response = data.get("message")
        content = str(response.get("content") if isinstance(response, dict) else "").strip()
        if not content:
            content = str(data.get("response") or "").strip()
        if not content:
            return "Yerel model boş cevap döndürdü."
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            detail = str(exc)
        return f"Yerel model HTTP hatası: {exc.code} · {detail}"
    except Exception as exc:
        return f"Yerel model yanıt vermedi: {exc}"

    with _LOCK:
        _HISTORY.append({"role": "user", "content": message})
        _HISTORY.append({"role": "assistant", "content": content})
        del _HISTORY[:-12]
    return content


def neto_ai_cevap_ver(prompt: str, *args, **kwargs) -> str:
    return answer(prompt, **{key: value for key, value in kwargs.items() if key in {"model", "keep_alive", "timeout", "system_prompt"}})


def clear_history() -> None:
    with _LOCK:
        _HISTORY.clear()


def unload_model(model: str = DEFAULT_MODEL) -> bool:
    if not api_ready(timeout=1.0):
        return False
    try:
        _request_json(
            "POST",
            "/api/generate",
            {
                "model": model,
                "prompt": "",
                "stream": False,
                "keep_alive": 0,
            },
            timeout=12.0,
        )
        return True
    except Exception:
        return False
