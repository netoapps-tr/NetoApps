from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import sys
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


os.environ.setdefault("NETO_SKIP_LINUX_BRIDGE", "1")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from neto_assistant_engine import AssistantEngine
import mini_linux

try:
    import neto_ai
except Exception:  # pragma: no cover - WSL tarafında AI modülü yoksa da sağlık servisi çalışmalı.
    neto_ai = None


def _linux_quick_resolver(text, agent_modu=False):
    metin = str(text or "").casefold().strip()
    if not metin:
        return None

    if any(
        anahtar in metin
        for anahtar in (
            "linux durumu",
            "ubuntu durumu",
            "wsl durumu",
            "bridge durumu",
            "motor durumu",
            "asistan durumu",
            "netops durumu",
        )
    ):
        return (
            f"WSL köprüsü hazır. Distro: {os.environ.get('WSL_DISTRO_NAME') or 'Ubuntu-24.04'}. "
            f"Python: {sys.version.split()[0]}. Host: {socket.gethostname()}."
        )

    if metin in {"saat", "saat kaç", "saat kactır", "saat kac"}:
        return f"Saat {datetime.now().strftime('%H:%M')}."

    if "tarih" in metin:
        return f"Bugünün tarihi {datetime.now().strftime('%d.%m.%Y')}."

    if any(anahtar in metin for anahtar in ("python sürüm", "python versiyon", "python version")):
        return f"Python {sys.version.split()[0]} çalışıyor."

    if any(anahtar in metin for anahtar in ("terminal", "bash", "shell")):
        return "Bu köprü terminal açmaz; Linux komutlarını metin olarak yorumlayabilirim."

    if any(anahtar in metin for anahtar in ("apt", "paket", "distro", "daemon", "systemctl", "kernel")):
        return (
            f"Linux ortamı aktif. Platform: {platform.platform()}. "
            f"CWD: {os.getcwd()}."
        )

    return None


def _linux_ai_resolver(text, agent_modu=False):
    if neto_ai is None:
        return "AI modülü yüklenemedi."
    return neto_ai.neto_ai_cevap_ver(text, agent_modu=agent_modu)


_ENGINE = AssistantEngine(
    quick_resolver=_linux_quick_resolver,
    ai_responder=_linux_ai_resolver,
    normalizer=lambda value: str(value or "").strip(),
    name="netopsd",
)


class _Server(ThreadingHTTPServer):
    allow_reuse_address = True


class _Handler(BaseHTTPRequestHandler):
    server_version = "NetOpsWSL/1.0"

    def _payload(self) -> dict[str, object]:
        return {
            "ok": True,
            "service": "netopsd",
            "capabilities": ["health", "assistant"],
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "time": time.time(),
            "cwd": os.getcwd(),
            "argv": sys.argv[1:],
        }

    def _send(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A003 - stdlib API signature
        return

    def do_GET(self):  # noqa: N802 - stdlib API signature
        if self.path in {"/", "/health", "/info"}:
            payload = self._payload()
            if self.path == "/info":
                payload["details"] = {
                    "executable": sys.executable,
                    "version": platform.version(),
                    "machine": platform.machine(),
                    "release": platform.release(),
                    "assistant_engine": "available",
                }
            self._send(200, payload)
            return
        self._send(
            404,
            {
                "ok": False,
                "error": "not_found",
                "path": self.path,
            },
        )

    def do_POST(self):  # noqa: N802 - stdlib API signature
        if self.path not in {"/assistant", "/route"}:
            self._send(
                404,
                {
                    "ok": False,
                    "error": "not_found",
                    "path": self.path,
                },
            )
            return

        try:
            length = int(self.headers.get("Content-Length") or 0)
        except Exception:
            length = 0

        body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(body.decode("utf-8", errors="replace"))
            if not isinstance(payload, dict):
                payload = {}
        except Exception:
            payload = {}

        text = payload.get("text") or payload.get("message") or payload.get("query") or ""
        mode = str(payload.get("mode") or "linux").strip().lower()
        agent_mode = bool(payload.get("agent_mode") or payload.get("agent_modu"))
        allow_quick = payload.get("allow_quick")
        if allow_quick is None:
            allow_quick = mode not in {"chat", "agent"}

        mini_text = mini_linux.handle(str(text or ""))
        if mini_text:
            self._send(200, {
                "ok": True,
                "kind": "response",
                "source": "mini_linux",
                "text": mini_text,
                "command": None,
                "raw_input": text,
                "normalized_input": str(text or "").strip(),
                "agent_mode": agent_mode,
                "metadata": {"mode": mode, "source": "wsl", "mini_linux": True},
            })
            return
        result = _ENGINE.route(
            text,
            agent_modu=agent_mode,
            allow_quick=bool(allow_quick),
            metadata={"mode": mode, "source": "wsl"},
        )
        response = {
            "ok": True,
            "kind": result.kind,
            "source": result.source,
            "text": result.text,
            "command": result.command,
            "raw_input": result.raw_input,
            "normalized_input": result.normalized_input,
            "agent_mode": result.agent_mode,
            "metadata": result.metadata,
        }
        self._send(200, response)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NetOps WSL bridge agent")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    server = _Server((str(args.host), int(args.port)), _Handler)
    try:
        server.serve_forever(poll_interval=0.4)
    except KeyboardInterrupt:
        return 0
    finally:
        try:
            server.server_close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())




