#!/usr/bin/env python3
"""Small, dependency-free Termux client for the NetOps Device Hub.

The Windows application remains the authority.  This client only uses the
already authenticated assistant and Now Playing protocol; it never executes a
shell command on the PC and never requires Android root access.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform
import secrets
import shutil
import socket
import ssl
import struct
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlsplit


APP_NAME = "netops-shell"
APP_VERSION = "1.2.0"
MAX_FRAME_SIZE = 1024 * 1024
WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
CONFIG_FIELDS = ("endpoint", "device_id", "token", "device_name")
ERROR_TEXT = {
    "PAIRING_REQUIRED": "Bu telefon henüz eşleştirilmemiş.",
    "INVALID_PAIRING_CODE": "Eşleştirme kodu geçersiz veya süresi dolmuş.",
    "ASSISTANT_OFFLINE": "Windows NetOps sohbet motoru hazır değil.",
    "DEVICE_OFFLINE": "Windows cihazına bağlantı yok.",
    "TIMEOUT": "NetOps yanıt vermedi; bağlantıyı ve yerel Wi-Fi'yi kontrol et.",
    "REQUEST_TOO_LONG": "İstek çok uzun.",
    "MEDIA_UNAVAILABLE": "Now Playing hizmeti kullanılamıyor.",
    "CONFIRMATION_REQUIRED": "Bu işlem için açık onay gerekli. Komutu tekrar onaylayarak çalıştır.",
    "UNKNOWN_COMMAND": "Bu güvenli komut tanınmıyor.",
    "INPUT_KEY_NOT_ALLOWED": "Bu tuş NetOps güvenli kontrol listesinde yok.",
    "INPUT_SEND_FAILED": "PC tuşu gönderilemedi.",
    "INPUT_UNAVAILABLE": "Telefon kontrol köprüsü hazır değil.",
}


class NetOpsShellError(RuntimeError):
    """A user-facing Termux client error."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def normalize_endpoint(value: str) -> str:
    """Return a canonical ws:// or wss:// endpoint for the local hub."""
    cleaned = _text(value)
    if not cleaned:
        raise ValueError("WebSocket adresi gerekli.")
    if "://" not in cleaned:
        cleaned = "ws://" + cleaned
    parts = urlsplit(cleaned)
    if parts.scheme.casefold() not in {"ws", "wss"}:
        raise ValueError("Yalnızca ws:// veya wss:// adresi kullanılabilir.")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("WebSocket adresi kullanıcı bilgisi veya sorgu içeremez.")
    host = parts.hostname
    if not host:
        raise ValueError("WebSocket adresinde bilgisayar adı eksik.")
    try:
        port = parts.port or (443 if parts.scheme.casefold() == "wss" else 80)
    except ValueError as exc:
        raise ValueError("WebSocket portu geçersiz.") from exc
    if not 1 <= port <= 65535:
        raise ValueError("WebSocket portu 1-65535 arasında olmalı.")
    host_text = f"[{host}]" if ":" in host and not host.startswith("[") else host
    default_port = 443 if parts.scheme.casefold() == "wss" else 80
    port_text = "" if port == default_port else f":{port}"
    return f"{parts.scheme.casefold()}://{host_text}{port_text}/"


def build_hello(
    *,
    device_name: str,
    pairing_code: str = "",
    device_id: str = "",
    token: str = "",
    agent_version: str = APP_VERSION,
) -> dict[str, Any]:
    """Build the same hello payload used by the native Android client."""
    name = _text(device_name) or platform.node() or "Termux cihazı"
    message: dict[str, Any] = {
        "type": "hello",
        "device_name": name[:120],
        "manufacturer": "Termux",
        "model": platform.machine() or "Android",
        "android_version": _text(os.environ.get("ANDROID_VERSION")),
        "agent_version": f"{APP_NAME}/{agent_version}",
        "network": {"type": "local_wifi"},
        "root": False,
        "capabilities": {
            "assistant_request": True,
            "media_request": True,
            "input_control": True,
            "termux_shell": True,
            "root": False,
        },
    }
    if _text(device_id) and _text(token):
        message["device_id"] = _text(device_id)
        message["token"] = _text(token)
    elif _text(pairing_code):
        message["pairing_code"] = _text(pairing_code)
    return message


def _config_values(data: Any) -> dict[str, str]:
    if not isinstance(data, dict):
        return {}
    return {field: _text(data.get(field)) for field in CONFIG_FIELDS if _text(data.get(field))}


def default_config_path() -> Path:
    configured_home = _text(os.environ.get("NETOPS_SHELL_HOME"))
    if configured_home:
        return Path(configured_home).expanduser() / "config.json"
    return Path.home() / ".config" / "netops-shell" / "config.json"


def load_config(path: Path | None = None) -> dict[str, str]:
    target = Path(path or default_config_path()).expanduser()
    try:
        return _config_values(json.loads(target.read_text(encoding="utf-8")))
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def save_config(data: dict[str, Any], path: Path | None = None) -> Path:
    target = Path(path or default_config_path()).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    values = _config_values(data)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(values, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)
    try:
        target.chmod(0o600)
    except OSError:
        pass
    return target


def termux_install() -> Path:
    """Install the current script as the persistent `netops` Termux command."""
    prefix = Path(os.environ.get("PREFIX") or "/data/data/com.termux/files/usr")
    target = prefix / "lib" / "netops-shell" / "netops_shell.py"
    launcher = prefix / "bin" / "netops"
    source = Path(__file__).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    launcher.parent.mkdir(parents=True, exist_ok=True)
    if source != target:
        temporary = target.with_suffix(target.suffix + ".tmp")
        shutil.copyfile(source, temporary)
        os.replace(temporary, target)
    target.chmod(0o700)
    recovery_ui_source = source.with_name("neto_termux_recovery_ui.py")
    recovery_ui_target = target.with_name("neto_termux_recovery_ui.py")
    if recovery_ui_source.is_file():
        temporary_ui = recovery_ui_target.with_suffix(recovery_ui_target.suffix + ".tmp")
        shutil.copyfile(recovery_ui_source, temporary_ui)
        os.replace(temporary_ui, recovery_ui_target)
        recovery_ui_target.chmod(0o700)
    launcher.write_text(
        "#!/data/data/com.termux/files/usr/bin/sh\n"
        'exec python "$PREFIX/lib/netops-shell/netops_shell.py" "$@"\n',
        encoding="utf-8",
    )
    launcher.chmod(0o700)
    return launcher


def _recv_exact(sock: Any, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = sock.recv(remaining)
        if not chunk:
            raise NetOpsShellError("Windows bağlantısı kapandı.")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def encode_client_text(text: str, mask: bytes | None = None) -> bytes:
    """Encode a masked client WebSocket text frame."""
    payload = _text(text).encode("utf-8")
    if len(payload) > MAX_FRAME_SIZE:
        raise NetOpsShellError("Mesaj çok büyük.")
    mask_key = mask if mask is not None else os.urandom(4)
    if len(mask_key) != 4:
        raise ValueError("WebSocket maskesi 4 byte olmalı.")
    length = len(payload)
    if length < 126:
        header = bytes((0x81, 0x80 | length))
    elif length <= 65535:
        header = bytes((0x81, 0x80 | 126)) + struct.pack("!H", length)
    else:
        header = bytes((0x81, 0x80 | 127)) + struct.pack("!Q", length)
    masked = bytes(byte ^ mask_key[index % 4] for index, byte in enumerate(payload))
    return header + mask_key + masked


def decode_frame_from_socket(sock: Any) -> tuple[int, bytes]:
    """Read one WebSocket frame; used by the client and protocol tests."""
    first, second = _recv_exact(sock, 2)
    opcode = first & 0x0F
    length = second & 0x7F
    if length == 126:
        length = struct.unpack("!H", _recv_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", _recv_exact(sock, 8))[0]
    if length > MAX_FRAME_SIZE:
        raise NetOpsShellError("Windows bağlantısı çok büyük bir mesaj gönderdi.")
    mask_key = _recv_exact(sock, 4) if second & 0x80 else b""
    payload = bytearray(_recv_exact(sock, int(length)))
    if mask_key:
        for index in range(len(payload)):
            payload[index] ^= mask_key[index % 4]
    return opcode, bytes(payload)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="netops", description="NetOps'u yerel Wi-Fi üzerinden yönet.")
    parser.add_argument("--config", type=Path, default=None, help="Özel yapılandırma dosyası")
    parser.add_argument("--json", action="store_true", help="Yanıtı JSON olarak yaz")
    parser.add_argument("--timeout", type=float, default=10.0, help="Bağlantı zaman aşımı (saniye)")
    commands = parser.add_subparsers(dest="command", required=True)

    pair = commands.add_parser(
        "pair", aliases=["eşleştir", "eslestir"], help="PC ile tek kullanımlık kodla eşleş"
    )
    pair.add_argument("--host", required=True, help="PC IP adresi ve portu, ör. 192.168.1.20:8765")
    pair.add_argument("--code", required=True, help="NetOps Device Hub eşleştirme kodu")
    pair.add_argument("--name", default="", help="Bu Termux cihazında görünecek ad")

    commands.add_parser("install", aliases=["kur"], help="Termux'a kalıcı netops komutunu kur")
    agent = commands.add_parser(
        "agent", aliases=["ajan"], help="NetOps'a bağlı kal ve heartbeat gönder"
    )
    agent.add_argument("--name", default="", help="Bağlı cihaz adı")
    agent.add_argument("--background", action="store_true", help="Agent'ı Termux prompt'unu kilitlemeden çalıştır")

    ask = commands.add_parser("ask", aliases=["sor"], help="NetOps'a sohbet/komut gönder")
    ask.add_argument("text", nargs="+", help="Gönderilecek metin")
    commands.add_parser(
        "status", aliases=["durum", "sistem-durumu"], help="NetOps'tan sistem durumunu iste"
    )
    commands.add_parser("ram", aliases=["bellek"], help="RAM kullanımını göster")
    commands.add_parser("cpu", aliases=["işlemci", "islemci"], help="CPU kullanımını göster")
    commands.add_parser("disk", help="Disk kullanımını göster")
    commands.add_parser("network", aliases=["ağ", "ag"], help="Ağ bilgilerini göster")
    commands.add_parser("uptime", aliases=["çalışma-süresi", "calisma-suresi"], help="Çalışma süresini göster")
    commands.add_parser("battery", help="Pil durumunu göster")
    commands.add_parser(
        "commands", aliases=["komutlar"], help="Kullanılabilir NetOps komutlarını göster"
    )
    commands.add_parser("devices", aliases=["cihazlar"], help="Bağlı cihazları NetOps'a sor")
    open_program = commands.add_parser(
        "open", aliases=["aç", "ac"], help="PC'de izinli bir programı aç"
    )
    open_program.add_argument("program", nargs="+", help="Program adı, ör. chrome veya vscode")
    commands.add_parser(
        "pc-commands", aliases=["pc-komutları", "pc-komutlari"],
        help="PC uzaktan kontrol komutlarını göster"
    )
    key = commands.add_parser(
        "key", aliases=["tuş", "tus"], help="Güvenli bir PC tuşu veya uygulama kısayolu gönder"
    )
    key.add_argument("key", help="up/down/left/right/enter veya c/e/f/v/s/n/x/a")
    commands.add_parser(
        "control", aliases=["kontrol"], help="Telefon klavyesiyle güvenli PC kontrol modunu aç"
    )
    commands.add_parser("lock", aliases=["kilitle"], help="PC'yi kilitle")
    commands.add_parser("desktop", aliases=["masaüstü", "masaustu"], help="PC masaüstü klasörünü aç")
    commands.add_parser("documents", aliases=["belgeler"], help="PC Belgeler klasörünü aç")
    commands.add_parser("downloads", aliases=["indirilenler"], help="PC İndirilenler klasörünü aç")
    commands.add_parser("core-restart", aliases=["çekirdek-yenile", "cekirdek-yenile"], help="Axvord çekirdeğini yenile")
    commands.add_parser("recovery", aliases=["kurtarma"], help="NetOps Recovery Mode'u başlat")
    commands.add_parser("reboot", aliases=["yeniden-başlat", "yeniden-baslat"], help="NetOps OS'yi yeniden başlat")
    commands.add_parser("poweroff", aliases=["kapat"], help="NetOps OS'yi kapat")
    now_playing = commands.add_parser(
        "now-playing", aliases=["şimdi-çalan", "simdi-calan"], help="Şu an çalan parçayı sor"
    )
    now_playing.add_argument("--watch", action="store_true", help="Parça değiştikçe telefonda güncelle")
    now_playing.add_argument("--interval", type=float, default=5.0, help="Kontrol aralığı (saniye)")
    commands.add_parser(
        "play-pause",
        aliases=["oynat-duraklat", "oynat", "duraklat", "çal", "cal"],
        help="Oynatmayı duraklat/devam ettir",
    )
    commands.add_parser("next", aliases=["sonraki"], help="Sonraki parçaya geç")
    commands.add_parser("previous", aliases=["önceki", "onceki"], help="Önceki parçaya dön")
    volume = commands.add_parser("volume", aliases=["ses"], help="Windows sesini ayarla")
    volume.add_argument("value", type=int, choices=range(0, 101), metavar="0-100")
    commands.add_parser("forget", aliases=["unut"], help="Bu Termux cihazındaki eşleşmeyi sil")
    parsed = parser.parse_args(list(argv) if argv is not None else None)
    # argparse leaves the alias in ``command``; normalize it so the existing
    # dispatcher keeps one canonical path for English and Turkish commands.
    parsed.command = {
        "eşleştir": "pair", "eslestir": "pair", "kur": "install", "ajan": "agent",
        "sor": "ask", "durum": "status", "sistem-durumu": "status", "bellek": "ram",
        "işlemci": "cpu", "islemci": "cpu", "komutlar": "commands", "cihazlar": "devices",
        "ağ": "network", "ag": "network", "çalışma-süresi": "uptime", "calisma-suresi": "uptime",
        "aç": "open", "ac": "open", "pc-komutları": "pc-commands", "pc-komutlari": "pc-commands",
        "tuş": "key", "tus": "key", "kontrol": "control",
        "kilitle": "lock", "masaüstü": "desktop", "masaustu": "desktop", "belgeler": "documents",
        "indirilenler": "downloads", "şimdi-çalan": "now-playing", "simdi-calan": "now-playing",
        "çekirdek-yenile": "core-restart", "cekirdek-yenile": "core-restart",
        "kurtarma": "recovery",
        "yeniden-başlat": "reboot", "yeniden-baslat": "reboot", "kapat": "poweroff",
        "oynat-duraklat": "play-pause", "oynat": "play-pause", "duraklat": "play-pause",
        "çal": "play-pause", "cal": "play-pause", "sonraki": "next", "önceki": "previous", "onceki": "previous",
        "ses": "volume", "unut": "forget",
    }.get(parsed.command, parsed.command)
    return parsed


class NetOpsShellClient:
    """Minimal synchronous WebSocket client for short CLI requests."""

    def __init__(self, endpoint: str, *, timeout: float = 10.0, device_name: str = "") -> None:
        self.endpoint = normalize_endpoint(endpoint)
        self.timeout = max(1.0, float(timeout))
        self.device_name = _text(device_name) or platform.node() or "Termux cihazı"
        self.socket: Any = None
        self.device_id = ""

    def connect(self, *, pairing_code: str = "", device_id: str = "", token: str = "") -> dict[str, Any]:
        parts = urlsplit(self.endpoint)
        port = parts.port or (443 if parts.scheme == "wss" else 80)
        raw_socket = socket.create_connection((parts.hostname, port), timeout=self.timeout)
        raw_socket.settimeout(self.timeout)
        if parts.scheme == "wss":
            context = ssl.create_default_context()
            raw_socket = context.wrap_socket(raw_socket, server_hostname=parts.hostname)
        self.socket = raw_socket
        try:
            self._handshake(parts, port)
            self._send_json(
                build_hello(
                    device_name=self.device_name,
                    pairing_code=pairing_code,
                    device_id=device_id,
                    token=token,
                )
            )
            response = self._receive_json(expected_type="hello_result")
            if not response.get("ok"):
                raise NetOpsShellError(ERROR_TEXT.get(_text(response.get("error")), "NetOps eşleştirmeyi kabul etmedi."))
            self.device_id = _text(response.get("device_id"))
            return response
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        current, self.socket = self.socket, None
        if current is None:
            return
        try:
            current.sendall(_encode_control_frame(8, b""))
        except Exception:
            pass
        try:
            current.close()
        except Exception:
            pass

    def keep_alive(self, *, interval: float = 10.0, output: Callable[[str], None] = print) -> None:
        """Keep the Termux device visible in Device Hub until Ctrl+C."""
        if self.socket is None or not self.device_id:
            raise NetOpsShellError("NetOps bağlantısı açık değil.")
        heartbeat_interval = max(3.0, float(interval))
        self.socket.settimeout(0.5)
        next_heartbeat = 0.0
        output("NetOps bağlı. Telefon çevrimiçi tutuluyor; çıkmak için Ctrl+C.")
        while True:
            now = time.monotonic()
            if now >= next_heartbeat:
                self._send_json(
                    {
                        "type": "heartbeat",
                        "device_id": self.device_id,
                        "network": {"type": "local_wifi"},
                        "root": False,
                    }
                )
                next_heartbeat = now + heartbeat_interval
            try:
                opcode, payload = decode_frame_from_socket(self.socket)
            except (TimeoutError, socket.timeout):
                continue
            if opcode == 8:
                raise NetOpsShellError("Windows bağlantısı kapandı.")
            if opcode == 9:
                self.socket.sendall(_encode_control_frame(10, payload))
                continue
            if opcode == 1:
                message: Any = None
                try:
                    message = json.loads(payload.decode("utf-8"))
                    if isinstance(message, dict) and _text(message.get("type")) == "command":
                        result = _handle_server_command(message)
                        result.update({"type": "command_result", "id": _text(message.get("id"))})
                        self._send_json(result)
                except (UnicodeDecodeError, json.JSONDecodeError, OSError, NetOpsShellError) as exc:
                    try:
                        self._send_json(
                            {
                                "type": "command_result",
                                "id": _text(message.get("id")) if isinstance(message, dict) else "",
                                "ok": False,
                                "error": str(exc),
                            }
                        )
                    except Exception:
                        pass

    def request_assistant(self, text: str) -> dict[str, Any]:
        request_id = f"termux_{uuid.uuid4().hex}"
        self._send_json({"type": "assistant_request", "id": request_id, "device_id": self.device_id, "text": _text(text)})
        return self._receive_json(expected_type="assistant_response")

    def request_media(self, action: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        request_id = f"termux_media_{uuid.uuid4().hex}"
        self._send_json(
            {
                "type": "media_request",
                "id": request_id,
                "device_id": self.device_id,
                "action": _text(action),
                "args": dict(args or {}),
            }
        )
        return self._receive_json(expected_type="media_response")

    def request_input(self, key: str, modifiers: list[str] | None = None) -> dict[str, Any]:
        request_id = f"termux_input_{uuid.uuid4().hex}"
        self._send_json(
            {
                "type": "input_request",
                "id": request_id,
                "device_id": self.device_id,
                "key": _text(key),
                "modifiers": list(modifiers or []),
            }
        )
        return self._receive_json(expected_type="input_response")

    def control_loop(self, *, output: Callable[[str], None] = print) -> None:
        """Read phone keyboard keys and send only the safe control allowlist."""
        if not sys.stdin.isatty():
            raise NetOpsShellError("Kontrol modu yalnızca etkileşimli Termux oturumunda çalışır.")
        output("Kontrol modu: oklar PC'ye gider, c/e/f/v/s/n/x/a uygulama açar, q çıkar.")
        while True:
            key = _read_control_key()
            if key == "q":
                output("NetOps kontrol modu kapatıldı.")
                return
            result = self.request_input(key)
            _print_result(result, as_json=False, output=output)

    def watch_now_playing(self, *, interval: float = 5.0, output: Callable[[str], None] = print) -> None:
        """Show the current track on the phone whenever it changes."""
        delay = max(2.0, float(interval))
        previous = ""
        output("Now Playing izleniyor. Çıkmak için Ctrl+C.")
        while True:
            result = self.request_media("current")
            media = result.get("media") if isinstance(result, dict) else None
            if isinstance(media, dict):
                signature = "|".join(_text(media.get(key)) for key in ("title", "artist", "app", "status"))
            else:
                signature = _text(result.get("display_text"))
            if signature != previous:
                _print_result(result, as_json=False, output=output)
                previous = signature
            time.sleep(delay)

    def _handshake(self, parts: Any, port: int) -> None:
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        host = parts.hostname or ""
        host_header = f"[{host}]" if ":" in host else host
        if port not in {80, 443}:
            host_header += f":{port}"
        request = (
            f"GET {parts.path or '/'} HTTP/1.1\r\n"
            f"Host: {host_header}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ).encode("ascii")
        self.socket.sendall(request)
        response = bytearray()
        while b"\r\n\r\n" not in response and len(response) < 16384:
            response.extend(_recv_exact(self.socket, 1))
        headers = bytes(response).decode("ascii", errors="replace")
        if not headers.startswith("HTTP/1.1 101") and not headers.startswith("HTTP/1.0 101"):
            raise NetOpsShellError("NetOps WebSocket el sıkışmasını reddetti.")
        expected = base64.b64encode(hashlib.sha1((key + WEBSOCKET_GUID).encode("ascii")).digest()).decode("ascii")
        accepted = ""
        for line in headers.split("\r\n"):
            if line.casefold().startswith("sec-websocket-accept:"):
                accepted = line.split(":", 1)[1].strip()
                break
        if accepted != expected:
            raise NetOpsShellError("WebSocket doğrulaması başarısız.")

    def _send_json(self, payload: dict[str, Any]) -> None:
        if self.socket is None:
            raise NetOpsShellError("Windows bağlantısı açık değil.")
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        self.socket.sendall(encode_client_text(encoded))

    def _receive_json(self, *, expected_type: str) -> dict[str, Any]:
        while True:
            if self.socket is None:
                raise NetOpsShellError("Windows bağlantısı açık değil.")
            opcode, payload = decode_frame_from_socket(self.socket)
            if opcode == 8:
                raise NetOpsShellError("Windows bağlantısı kapandı.")
            if opcode == 9:
                self.socket.sendall(_encode_control_frame(10, payload))
                continue
            if opcode != 1:
                continue
            try:
                message = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise NetOpsShellError("NetOps geçersiz yanıt gönderdi.") from exc
            if not isinstance(message, dict):
                continue
            if _text(message.get("type")) == "error":
                raise NetOpsShellError(ERROR_TEXT.get(_text(message.get("error")), "NetOps bağlantı hatası."))
            if _text(message.get("type")) == expected_type:
                return message


def _encode_control_frame(opcode: int, payload: bytes) -> bytes:
    if len(payload) > 125:
        raise NetOpsShellError("WebSocket kontrol çerçevesi çok büyük.")
    mask = os.urandom(4)
    encoded = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    return bytes((0x80 | opcode, 0x80 | len(payload))) + mask + encoded


def _read_control_key() -> str:
    """Read one printable key or ANSI arrow sequence from a Termux TTY."""
    try:
        import select
        import termios
        import tty
    except ImportError as exc:
        raise NetOpsShellError("Termux kontrol modu için TTY desteği gerekli.") from exc

    fd = sys.stdin.fileno()
    previous = termios.tcgetattr(fd)
    tty.setraw(fd)
    try:
        first = os.read(fd, 1).decode("utf-8", errors="ignore")
        if first == "\x03":
            raise KeyboardInterrupt
        if first == "\x1b":
            sequence = first
            for _ in range(2):
                ready, _, _ = select.select([fd], [], [], 0.05)
                if not ready:
                    break
                sequence += os.read(fd, 1).decode("utf-8", errors="ignore")
            return {
                "\x1b[A": "up",
                "\x1b[B": "down",
                "\x1b[C": "right",
                "\x1b[D": "left",
            }.get(sequence, "escape")
        if first in {"\r", "\n"}:
            return "enter"
        if first == " ":
            return "space"
        return first.casefold()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, previous)


def _stored_client(args: argparse.Namespace, config: dict[str, str]) -> NetOpsShellClient:
    endpoint = config.get("endpoint")
    if not endpoint or not config.get("device_id") or not config.get("token"):
        raise NetOpsShellError("Önce `netops pair --host PC_IP:8765 --code KOD` çalıştırılmalı.")
    return NetOpsShellClient(endpoint, timeout=args.timeout, device_name=config.get("device_name", ""))


def _local_memory_text() -> str:
    try:
        values: dict[str, int] = {}
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition(":")
            if key in {"MemTotal", "MemAvailable"}:
                values[key] = int(value.strip().split()[0])
        if values.get("MemTotal"):
            used = values["MemTotal"] - values.get("MemAvailable", values["MemTotal"])
            return f"RAM {used // 1024} / {values['MemTotal'] // 1024} MB"
    except (OSError, ValueError, IndexError):
        pass
    return "RAM bilgisi alınamıyor"


def _local_status_text() -> str:
    parts = [f"Termux aktif · {platform.system()} {platform.machine()}", _local_memory_text()]
    try:
        usage = shutil.disk_usage(Path.home())
        parts.append(f"Depolama {usage.used // (1024 ** 3)} / {usage.total // (1024 ** 3)} GB")
    except OSError:
        pass
    try:
        uptime = float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0])
        parts.append(f"Çalışma süresi {int(uptime // 60)} dk")
    except (OSError, ValueError, IndexError):
        pass
    return " · ".join(parts)


def _local_chat_reply(text: str) -> str:
    """Answer only local, read-only Termux questions from the PC Remote chat."""
    normalized = _text(text).casefold()
    if any(word in normalized for word in ("durum", "status", "ram", "bellek", "cpu", "işlemci")):
        return _local_status_text()
    if "termux" in normalized or "telefon" in normalized or "android" in normalized:
        return f"Termux ajanı çalışıyor. {_local_memory_text()}"
    if "merhaba" in normalized or "selam" in normalized:
        return "Merhaba. Termux bağlantısı hazır; durum ve güvenli yerel bilgileri paylaşabilirim."
    return "Bu sohbet yalnızca güvenli yerel Termux bilgilerini yanıtlıyor. Durum, RAM veya Termux hakkında sorabilirsiniz."


def _handle_server_command(message: dict[str, Any]) -> dict[str, Any]:
    """Handle authenticated PC->Termux commands without executing shell text."""
    command = _text(message.get("command")).casefold()
    args = message.get("args") if isinstance(message.get("args"), dict) else {}
    if command == "assistant_request":
        text = _text(args.get("text"))
        if not text or len(text) > 4000:
            return {"ok": False, "error": "REQUEST_TOO_LONG" if len(text) > 4000 else "EMPTY_REQUEST"}
        return {"ok": True, "display_text": _local_chat_reply(text)}
    if command == "request_status":
        return {"ok": True, "display_text": _local_status_text()}
    if command == "termux_info":
        return {"ok": True, "display_text": f"{APP_NAME}/{APP_VERSION} · {_local_memory_text()}"}
    return {"ok": False, "error": "UNKNOWN_COMMAND"}


def start_background_agent(args: argparse.Namespace, config_path: Path, output: Callable[[str], None] = print) -> int:
    """Detach the heartbeat loop so the Termux prompt remains usable."""
    log_path = config_path.parent / "agent.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--config",
        str(config_path),
        "agent",
    ]
    if args.name:
        command.extend(["--name", args.name])
    try:
        with log_path.open("a", encoding="utf-8") as log:
            subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )
    except (OSError, ValueError) as exc:
        output(f"NetOps agent arka planda başlatılamadı: {exc}")
        return 1
    output(f"NetOps agent arka planda çalışıyor. Log: {log_path}")
    return 0


def _print_result(result: dict[str, Any], *, as_json: bool, output: Callable[[str], None]) -> None:
    if as_json:
        output(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if not result.get("ok"):
        error = _text(result.get("error"))
        output(ERROR_TEXT.get(error, error or "NetOps isteği başarısız."))
        return
    display = _text(result.get("display_text"))
    if display:
        output(display)
        return
    media = result.get("media")
    if isinstance(media, dict):
        values = [media.get("title"), media.get("artist"), media.get("app")]
        output(" • ".join(_text(value) for value in values if _text(value)) or "Şu an parça bilgisi yok.")
        return
    output("NetOps isteği tamamlandı.")


def _run_recovery_phone_screen(
    client: NetOpsShellClient,
    result: dict[str, Any],
    *,
    output: Callable[[str], None],
) -> dict[str, Any]:
    """Turn the two-step Recovery approval into one phone screen."""
    if not result.get("ok") or "onayla" not in _text(result.get("display_text")).casefold():
        return result
    try:
        from neto_termux_recovery_ui import choose_recovery_action

        choice = choose_recovery_action(output=output)
    except Exception as exc:
        output(f"Recovery ekranı açılamadı: {exc}")
        return result
    if not choice:
        return {**result, "display_text": "Recovery beklemede. Onay için tekrar netops recovery çalıştırın."}
    return client.request_assistant(choice)


def run_cli(argv: Iterable[str] | None = None, *, output: Callable[[str], None] = print) -> int:
    args = parse_args(argv)
    config_path = args.config or default_config_path()
    config = load_config(config_path)
    if args.command == "forget":
        try:
            Path(config_path).unlink()
        except FileNotFoundError:
            pass
        output("Termux eşleşmesi silindi.")
        return 0

    if args.command == "install":
        try:
            launcher = termux_install()
        except (OSError, ValueError) as exc:
            output(f"NetOps Termux kurulamadı: {exc}")
            return 1
        output(f"NetOps komutu kuruldu: {launcher}")
        return 0

    client: NetOpsShellClient | None = None
    try:
        if args.command == "pair":
            endpoint = normalize_endpoint(args.host)
            client = NetOpsShellClient(endpoint, timeout=args.timeout, device_name=args.name)
            hello = client.connect(pairing_code=args.code)
            save_config(
                {
                    "endpoint": endpoint,
                    "device_id": hello.get("device_id"),
                    "token": hello.get("token"),
                    "device_name": args.name,
                },
                config_path,
            )
            output(f"NetOps eşleştirildi: {_text(hello.get('pc_name')) or 'Windows PC'}")
            return 0

        if args.command == "agent":
            if args.background:
                return start_background_agent(args, config_path, output=output)
            client = _stored_client(args, config)
            if args.name:
                client.device_name = _text(args.name)
            hello = client.connect(device_id=config["device_id"], token=config["token"])
            client.keep_alive(interval=float(hello.get("heartbeat_interval") or 10), output=output)
            return 0

        client = _stored_client(args, config)
        client.connect(device_id=config["device_id"], token=config["token"])
        if args.command == "ask":
            result = client.request_assistant(" ".join(args.text))
        elif args.command == "status":
            result = client.request_assistant("sistem durumunu göster")
        elif args.command == "ram":
            result = client.request_assistant("RAM durumunu göster")
        elif args.command == "cpu":
            result = client.request_assistant("CPU durumunu göster")
        elif args.command == "disk":
            result = client.request_assistant("disk durumunu göster")
        elif args.command == "network":
            result = client.request_assistant("ağ durumunu göster")
        elif args.command == "uptime":
            result = client.request_assistant("çalışma süresini göster")
        elif args.command == "battery":
            result = client.request_assistant("pil durumunu göster")
        elif args.command == "commands":
            result = client.request_assistant("komutlarını göster")
        elif args.command == "devices":
            result = client.request_assistant("bağlı cihazları göster")
        elif args.command == "open":
            result = client.request_assistant(f"PC'de {' '.join(args.program)} aç")
        elif args.command == "pc-commands":
            result = client.request_assistant("PC komutları")
        elif args.command == "key":
            result = client.request_input(args.key)
        elif args.command == "control":
            client.control_loop(output=output)
            return 0
        elif args.command == "lock":
            result = client.request_assistant("PC kilitle")
        elif args.command == "desktop":
            result = client.request_assistant("Masaüstünü aç")
        elif args.command == "documents":
            result = client.request_assistant("Belgeleri aç")
        elif args.command == "downloads":
            result = client.request_assistant("İndirilenler aç")
        elif args.command == "core-restart":
            result = client.request_assistant("Axvord çekirdeğini yenile")
        elif args.command == "recovery":
            result = client.request_assistant("/recovery Netops")
            if not args.json:
                result = _run_recovery_phone_screen(client, result, output=output)
        elif args.command == "reboot":
            result = client.request_assistant("NetOps OS'yi yeniden başlat, onayla")
        elif args.command == "poweroff":
            result = client.request_assistant("NetOps OS'yi kapat, onayla")
        elif args.command == "now-playing":
            if args.watch:
                client.watch_now_playing(interval=args.interval, output=output)
                return 0
            result = client.request_media("current")
        elif args.command == "play-pause":
            result = client.request_media("play_pause")
        elif args.command in {"next", "previous"}:
            result = client.request_media(args.command)
        elif args.command == "volume":
            result = client.request_media("set_volume", {"value": args.value})
        else:
            raise NetOpsShellError("Bilinmeyen NetOps komutu.")
        _print_result(result, as_json=args.json, output=output)
        return 0 if result.get("ok") else 1
    except (NetOpsShellError, OSError, ValueError) as exc:
        output(str(exc))
        return 1
    finally:
        if client is not None:
            client.close()


def main() -> int:
    return run_cli()


if __name__ == "__main__":
    raise SystemExit(main())
