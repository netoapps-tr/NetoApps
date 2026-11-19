"""Optional local bridge between NetOps and a Node-RED automation flow.

Node-RED is treated as an event/flow engine, not as an unrestricted command
runner. The bridge only talks to loopback and never executes a received value
as a shell command.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_URL = "http://127.0.0.1:1880"
DEFAULT_TIMEOUT = 1.5


def _base_url(value: str | None = None) -> str:
    raw = str(value or os.environ.get("NETOPS_NODERED_URL") or DEFAULT_URL).strip()
    if not raw:
        raw = DEFAULT_URL
    return raw.rstrip("/")


def _loopback_only(url: str) -> bool:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and parsed.hostname in {
        "127.0.0.1",
        "localhost",
        "::1",
    }


def _node_red_executable() -> str | None:
    executable = shutil.which("node-red") or shutil.which("node-red.cmd")
    if executable:
        return executable
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidate = Path(appdata) / "npm" / "node-red.cmd"
        if candidate.is_file():
            return str(candidate)
    return None


@dataclass(frozen=True)
class NodeRedStatus:
    available: bool
    url: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "url": self.url,
            "message": self.message,
        }


class NodeRedBridge:
    """Small, opt-in HTTP client for the local NetOps Node-RED flow."""

    def __init__(self, url: str | None = None, *, timeout: float = DEFAULT_TIMEOUT) -> None:
        self.url = _base_url(url)
        self.timeout = max(0.2, float(timeout))
        self._process: subprocess.Popen[Any] | None = None

    def status(self) -> NodeRedStatus:
        if not _loopback_only(self.url):
            return NodeRedStatus(False, self.url, "Node-RED köprüsü yalnızca yerel adrese izin verir.")
        try:
            import requests

            response = requests.get(f"{self.url}/netops/health", timeout=self.timeout)
            if response.ok:
                return NodeRedStatus(True, self.url, "Node-RED yerel akış motoru hazır.")
            return NodeRedStatus(False, self.url, f"Node-RED HTTP {response.status_code} döndürdü.")
        except Exception as exc:
            return NodeRedStatus(False, self.url, f"Node-RED çalışmıyor: {exc}")

    def emit(self, event: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a structured event to the safe NetOps flow endpoint."""
        if not _loopback_only(self.url):
            return {"ok": False, "message": "Uzak Node-RED adresleri güvenlik nedeniyle kapalı."}
        name = " ".join(str(event or "").split())[:120]
        if not name:
            return {"ok": False, "message": "Olay adı boş olamaz."}
        try:
            import requests

            response = requests.post(
                f"{self.url}/netops/event",
                json={"event": name, "payload": dict(payload or {})},
                timeout=self.timeout,
            )
            data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            if response.ok:
                return {"ok": True, "data": data, "message": "Olay Node-RED akışına gönderildi."}
            return {"ok": False, "message": f"Node-RED HTTP {response.status_code} döndürdü."}
        except Exception as exc:
            return {"ok": False, "message": f"Node-RED olay gönderimi başarısız: {exc}"}

    def start(self, *, user_dir: str | os.PathLike[str] | None = None, port: int = 1880) -> dict[str, Any]:
        """Start Node-RED locally if it is installed and not already running."""
        current = self.status()
        if current.available:
            return {"ok": True, "started": False, "message": current.message}
        executable = _node_red_executable()
        if not executable:
            return {"ok": False, "started": False, "message": "Node-RED kurulumu bulunamadı."}
        resolved_dir = Path(user_dir or (Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "NetOps" / "NodeRed"))
        resolved_dir.mkdir(parents=True, exist_ok=True)
        command = [executable, "--userDir", str(resolved_dir), "--port", str(int(port))]
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self._process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)
        except OSError as exc:
            return {"ok": False, "started": False, "message": f"Node-RED başlatılamadı: {exc}"}
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            time.sleep(0.25)
            current = self.status()
            if current.available:
                return {"ok": True, "started": True, "message": current.message}
        return {"ok": False, "started": True, "message": "Node-RED başlatıldı ancak NetOps akış endpoint'i hazır olmadı."}


__all__ = ["DEFAULT_URL", "NodeRedBridge", "NodeRedStatus"]
