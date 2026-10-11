from __future__ import annotations

import json
import os
import platform
import shlex
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional


_ROOT = Path(__file__).resolve().parent
_LOCK = threading.RLock()
_STATE: dict[str, Any] = {
    "process": None,
    "distro": "",
    "port": 0,
    "host": "127.0.0.1",
    "started_at": 0.0,
    "last_error": "",
    "script_path": "",
}


def _wsl_executable() -> str:
    if os.name != "nt":
        return ""
    for name in ("wsl.exe", "wsl"):
        found = shutil.which(name)
        if found:
            return found
    candidates = [
        Path(os.environ.get("WINDIR") or r"C:\Windows") / "System32" / "wsl.exe",
        Path(r"C:\Windows\System32\wsl.exe"),
    ]
    for candidate in candidates:
        try:
            if candidate.is_file():
                return str(candidate)
        except Exception:
            pass
    return ""


def available() -> bool:
    return bool(_wsl_executable())


def list_distributions() -> list[str]:
    exe = _wsl_executable()
    if not exe:
        return []
    try:
        completed = subprocess.run(
            [exe, "-l", "-q"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except Exception:
        return []
    distros = []
    for line in str(completed.stdout or "").splitlines():
        name = line.replace("\x00", "").replace("\ufeff", "").strip()
        if name:
            distros.append(name)
    return distros


def default_distribution() -> str:
    distros = list_distributions()
    return distros[0] if distros else ""


def _to_wsl_path(path: Path) -> str:
    resolved = Path(path).resolve()
    posix = resolved.as_posix()
    drive = resolved.drive.rstrip(":").lower()
    if drive and len(posix) >= 2 and posix[1] == ":":
        return f"/mnt/{drive}{posix[2:]}"
    return posix


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _script_path(project_dir: Optional[Path] = None) -> Path:
    base = Path(project_dir or _ROOT).resolve()
    return base / "wsl" / "netopsd.py"


def _health_url(host: str, port: int) -> str:
    return f"http://{host}:{int(port)}/health"


def _assistant_url(host: str, port: int) -> str:
    return f"http://{host}:{int(port)}/assistant"


def _probe_health(host: str, port: int, timeout: float = 0.75) -> dict[str, Any] | None:
    if not host or not port:
        return None
    request = urllib.request.Request(_health_url(host, port), method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _post_json(url: str, payload: dict[str, Any], timeout: float = 3.0) -> dict[str, Any] | None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _collect_error(proc: subprocess.Popen[Any]) -> str:
    try:
        stdout, stderr = proc.communicate(timeout=0.2)
    except Exception:
        stdout, stderr = "", ""
    parts = [part.strip() for part in (stderr, stdout) if str(part or "").strip()]
    message = " ".join(parts).strip()
    if message:
        return message[-1200:]
    return f"WSL köprüsü kapandı (kod {proc.returncode})."


def _clear_dead_process() -> None:
    with _LOCK:
        proc = _STATE.get("process")
        if proc is not None:
            try:
                if proc.poll() is not None:
                    _STATE["process"] = None
                    _STATE["port"] = 0
            except Exception:
                _STATE["process"] = None
                _STATE["port"] = 0


def _snapshot_locked() -> dict[str, Any]:
    proc = _STATE.get("process")
    distros = list_distributions()
    exe = _wsl_executable()
    is_available = bool(exe)
    running = False
    pid = None
    returncode = None
    if proc is not None:
        try:
            returncode = proc.poll()
            running = returncode is None
            if running:
                pid = getattr(proc, "pid", None)
        except Exception:
            running = False
    port = int(_STATE.get("port") or 0)
    host = str(_STATE.get("host") or "127.0.0.1")
    distro = str(_STATE.get("distro") or "")
    reachable = False
    assistant_available = False
    payload = None
    if running and port:
        payload = _probe_health(host, port)
        reachable = payload is not None
        if isinstance(payload, dict):
            capabilities = payload.get("capabilities") or []
            if isinstance(capabilities, list):
                assistant_available = "assistant" in {str(item) for item in capabilities}
    state = "stopped"
    if not is_available:
        state = "unavailable"
    elif running and reachable:
        state = "running"
    elif running:
        state = "starting"
    elif not distros:
        state = "no_distro"
    elif _STATE.get("last_error"):
        state = "failed"
    hint = ""
    if state == "unavailable":
        hint = "PowerShell'i yönetici olarak açıp `wsl --install` çalıştır."
    elif state == "no_distro":
        hint = "En az bir WSL dağıtımı yükle ve varsayılan yap."
    elif state == "starting":
        hint = "Linux tarafındaki küçük agent henüz hazır olmadı."
    elif state == "failed":
        hint = "Distro içinde Python 3 kurulu mu ve `wsl/netopsd.py` erişilebilir mi kontrol et."
    return {
        "available": is_available,
        "wsl_executable": exe,
        "distros": distros,
        "distro": distro,
        "running": running,
        "ready": reachable,
        "state": state,
        "port": port,
        "host": host,
        "endpoint": _health_url("127.0.0.1", port) if port else "",
        "assistant_endpoint": _assistant_url("127.0.0.1", port) if port else "",
        "assistant_available": assistant_available,
        "script_path": str(_STATE.get("script_path") or _script_path()),
        "script_exists": Path(_STATE.get("script_path") or "").is_file() if _STATE.get("script_path") else _script_path().is_file(),
        "started_at": float(_STATE.get("started_at") or 0.0),
        "pid": pid,
        "returncode": returncode,
        "last_error": str(_STATE.get("last_error") or ""),
        "hint": hint,
        "health": payload,
    }


def status() -> dict[str, Any]:
    _clear_dead_process()
    with _LOCK:
        return _snapshot_locked()


def start_bridge(
    project_dir: Optional[Path] = None,
    distro: Optional[str] = None,
    host: str = "127.0.0.1",
    port: Optional[int] = None,
) -> dict[str, Any]:
    exe = _wsl_executable()
    if not exe:
        raise RuntimeError("WSL bulunamadı. Önce Windows WSL desteğini kur.")

    distros = list_distributions()
    if not distros:
        raise RuntimeError("Yüklü bir WSL dağıtımı bulunamadı.")

    selected = str(distro or default_distribution() or distros[0]).strip()
    script = _script_path(project_dir)
    if not script.is_file():
        raise RuntimeError(f"WSL agent dosyası bulunamadı: {script}")

    chosen_port = int(port or _free_port())
    script_wsl = _to_wsl_path(script)
    command = (
        f"python3 -u {shlex.quote(script_wsl)} --host {shlex.quote(str(host))} --port {int(chosen_port)} "
        f"|| python -u {shlex.quote(script_wsl)} --host {shlex.quote(str(host))} --port {int(chosen_port)}"
    )
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.Popen(
            [exe, "-d", selected, "--", "bash", "-lc", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=flags,
        )
    except Exception as exc:
        raise RuntimeError(f"WSL köprüsü başlatılamadı: {exc}") from exc

    with _LOCK:
        _STATE["process"] = proc
        _STATE["distro"] = selected
        _STATE["port"] = chosen_port
        _STATE["host"] = str(host or "127.0.0.1")
        _STATE["started_at"] = time.time()
        _STATE["last_error"] = ""
        _STATE["script_path"] = str(script)

    deadline = time.time() + 2.0
    while time.time() < deadline:
        if proc.poll() is not None:
            error = _collect_error(proc)
            with _LOCK:
                _STATE["last_error"] = error
                _STATE["process"] = None
                _STATE["port"] = 0
            raise RuntimeError(error)
        health = _probe_health(host, chosen_port, timeout=0.5)
        if health is not None:
            with _LOCK:
                _STATE["last_error"] = ""
            break
        time.sleep(0.2)

    return status()


def ensure_bridge_running(
    project_dir: Optional[Path] = None,
    distro: Optional[str] = None,
    host: str = "127.0.0.1",
    port: Optional[int] = None,
) -> dict[str, Any]:
    current = status()
    if current.get("running"):
        return current
    return start_bridge(project_dir=project_dir, distro=distro, host=host, port=port)


def stop_bridge() -> dict[str, Any]:
    with _LOCK:
        proc = _STATE.get("process")
        _STATE["process"] = None
        _STATE["port"] = 0
    if proc is not None:
        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except Exception:
                    proc.kill()
        except Exception:
            pass
    return status()


def open_wsl_shell(distro: Optional[str] = None) -> bool:
    exe = _wsl_executable()
    if not exe:
        return False
    args = [exe]
    if distro:
        args.extend(["-d", str(distro)])
    try:
        subprocess.Popen(args)
        return True
    except Exception:
        return False


def assistant_request(
    text: str,
    *,
    agent_mode: bool = False,
    allow_quick: bool = True,
    mode: str = "linux",
    timeout: float = 5.0,
) -> dict[str, Any] | None:
    current = status()
    if not current.get("ready"):
        raise RuntimeError("WSL köprüsü hazır değil.")

    host = str(current.get("host") or "127.0.0.1")
    port = int(current.get("port") or 0)
    if not port:
        raise RuntimeError("WSL köprüsünün portu bulunamadı.")

    payload = {
        "text": str(text or ""),
        "agent_mode": bool(agent_mode),
        "allow_quick": bool(allow_quick),
        "mode": str(mode or "linux"),
    }
    return _post_json(_assistant_url(host, port), payload, timeout=timeout)

