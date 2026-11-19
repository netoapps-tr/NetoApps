"""NETOPS device hub.

PC tarafinda Android Agent baglantilari, pairing, heartbeat ve komut yonetimi
icin hafif bir WebSocket sunucusu.
"""
from __future__ import annotations

import base64
import asyncio
import contextlib
import json
import os
import ipaddress
import secrets
import socket
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Any, Callable

try:
    import websockets
except Exception:  # pragma: no cover - runtime fallback
    websockets = None


_DEVICE_HUB_WINDOW: Any = None
_DEVICE_HUB_SINGLETON: "NetOpsDeviceHub | None" = None
_AUDIO_STREAM_PATH: str | None = None
_AUDIO_STREAM_LOCK = threading.Lock()
_ASSISTANT_REQUEST_HANDLER: Callable[[str, str], Any] | None = None
_MEDIA_REQUEST_HANDLER: Callable[[str, dict[str, Any], str], Any] | None = None
_INPUT_REQUEST_HANDLER: Callable[[str, Any, str], Any] | None = None


def _project_root() -> Path:
    return Path(__file__).resolve().parent


def _app_data_root() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "NetoAssistant"
    return Path.home() / ".neto_assistant"


def _state_dir() -> Path:
    path = _app_data_root() / "device_hub"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _pairing_code_path() -> Path:
    return _state_dir() / "pairing_code.txt"


def _logs_dir() -> Path:
    path = _project_root() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_log(message: str) -> None:
    try:
        log_path = _logs_dir() / "device_hub.log"
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(f"[{stamp}] {message}\n")
    except Exception:
        pass


def device_hub_set_audio_stream_path(path: str | None) -> str:
    global _AUDIO_STREAM_PATH
    cleaned = _safe_text(path)
    with _AUDIO_STREAM_LOCK:
        _AUDIO_STREAM_PATH = cleaned or None
        if _AUDIO_STREAM_PATH:
            try:
                audio_path = Path(_AUDIO_STREAM_PATH)
                audio_path.parent.mkdir(parents=True, exist_ok=True)
                audio_path.write_text("", encoding="utf-8")
            except Exception as exc:
                _write_log(f"audio stream reset error: {exc}")
    return _AUDIO_STREAM_PATH or ""


def device_hub_clear_audio_stream_path() -> None:
    global _AUDIO_STREAM_PATH
    with _AUDIO_STREAM_LOCK:
        _AUDIO_STREAM_PATH = None


def _append_audio_stream(packet: dict[str, Any]) -> None:
    path = None
    with _AUDIO_STREAM_LOCK:
        path = _AUDIO_STREAM_PATH
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8", buffering=1) as handle:
            handle.write(json.dumps(packet, ensure_ascii=False) + "\n")
    except Exception as exc:
        _write_log(f"audio stream write error: {exc}")


def _safe_int(value: Any, default: int | None = None) -> int | None:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if value is None:
        return default
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "on", "evet"}:
        return True
    if text in {"0", "false", "no", "off", "hayir", "hayır"}:
        return False
    return default


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _time_ago(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    if seconds < 1.5:
        return "az once"
    if seconds < 60:
        return f"{int(seconds)} sn once"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes} dk once"
    hours = int(minutes // 60)
    if hours < 24:
        return f"{hours} sa once"
    days = int(hours // 24)
    return f"{days} g once"


def _local_ip_address() -> str:
    """Return a reachable physical-LAN address, not a VPN or virtual adapter."""
    candidates: list[tuple[int, str]] = []
    try:
        import psutil

        ignored_interface_words = ("warp", "tailscale", "vpn", "virtual", "vmware", "hyper-v", "loopback")
        for interface_name, addresses in psutil.net_if_addrs().items():
            interface_key = str(interface_name).casefold()
            if any(word in interface_key for word in ignored_interface_words):
                continue
            for address in addresses:
                if address.family != socket.AF_INET:
                    continue
                value = str(address.address or "").strip()
                try:
                    parsed = ipaddress.ip_address(value)
                except ValueError:
                    continue
                if parsed.is_loopback or parsed.is_link_local:
                    continue
                if parsed.is_private:
                    # Prefer normal home/office LAN ranges over fallback adapters.
                    score = 3 if value.startswith("192.168.") else 2 if value.startswith("10.") else 1
                    candidates.append((score, value))
        if candidates:
            candidates.sort(key=lambda item: (-item[0], item[1]))
            return candidates[0][1]
    except Exception:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            value = sock.getsockname()[0]
            if value and not value.startswith("127."):
                return value
    except Exception:
        pass
    return "127.0.0.1"


def _default_device_record(device_id: str, token: str) -> dict[str, Any]:
    now = time.time()
    return {
        "device_id": device_id,
        "token": token,
        "alias": "",
        "device_name": "",
        "manufacturer": "",
        "model": "",
        "android_version": "",
        "sdk_int": None,
        "agent_version": "",
        "paired_at": now,
        "connected_at": now,
        "last_seen": now,
        "online": True,
        "ip": "",
        "battery": {"level": None, "charging": False},
        "screen": "unknown",
        "volume": None,
        "network": {"type": "unknown"},
        "root": False,
        "capabilities": {},
        "media": {},
        "last_error": "",
    }


def _normalize_capabilities(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, Any] = {}
    for key, item in value.items():
        if key is None:
            continue
        normalized[str(key)] = item
    return normalized


def _normalize_media(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, Any] = {}
    for key, item in value.items():
        if key is None:
            continue
        normalized[str(key)] = item
    return normalized


class NetOpsDeviceHub:
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8765,
        offline_after: int = 28,
        heartbeat_interval: int = 10,
        pairing_ttl: int = 900,
    ) -> None:
        self.host = host
        self.port = int(port)
        self.offline_after = int(offline_after)
        self.heartbeat_interval = int(heartbeat_interval)
        self.pairing_ttl = int(pairing_ttl)

        self._state_path = _state_dir() / "device_hub_state.json"
        self._state_lock = threading.RLock()
        self._devices: dict[str, dict[str, Any]] = {}
        self._pairings: dict[str, dict[str, Any]] = {}
        self._connections: dict[str, Any] = {}
        self._pending_commands: dict[str, asyncio.Future] = {}

        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server: Any = None
        self._async_stop: asyncio.Event | None = None
        self._watchdog_task: asyncio.Task | None = None
        self._ready = threading.Event()
        self._start_error = ""
        self._current_pairing_code = ""
        self._current_pairing_expires_at = 0.0

        self._load_state()
        self._load_pairing_file()

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------
    def _load_state(self) -> None:
        try:
            if not self._state_path.is_file():
                return
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return
            devices = data.get("devices", {})
            if isinstance(devices, dict):
                for device_id, record in devices.items():
                    if not isinstance(record, dict):
                        continue
                    key = str(device_id)
                    base = _default_device_record(key, _safe_text(record.get("token")) or secrets.token_urlsafe(32))
                    base.update(record)
                    base["device_id"] = key
                    base["battery"] = dict(base.get("battery") or {})
                    base["network"] = dict(base.get("network") or {})
                    base["capabilities"] = _normalize_capabilities(base.get("capabilities"))
                    base["media"] = _normalize_media(base.get("media"))
                    self._devices[key] = base
            host = _safe_text(data.get("host"))
            if host:
                self.host = host
            port = _safe_int(data.get("port"))
            if port:
                self.port = int(port)
        except Exception as exc:
            _write_log(f"state load error: {exc}")

    def _load_pairing_file(self) -> None:
        """Restore the QR code shown by the desktop UI after an app restart."""
        try:
            path = _pairing_code_path()
            if not path.is_file():
                return
            data = json.loads(path.read_text(encoding="utf-8"))
            code = _safe_text(data.get("pairing_code"))
            expires_at = _safe_float(data.get("expires_at"), 0.0)
            now = time.time()
            if not code or bool(data.get("used")) or expires_at <= now:
                return
            self._current_pairing_code = code
            self._current_pairing_expires_at = expires_at
            self._pairings[code] = {
                "code": code,
                "token": secrets.token_urlsafe(32),
                "created_at": max(0.0, expires_at - self.pairing_ttl),
                "expires_at": expires_at,
                "used": False,
            }
        except Exception as exc:
            _write_log(f"pairing state load error: {exc}")

    def _restore_pairing_from_file(self, code: str, now: float) -> None:
        """Recover a still-valid QR code if the hub and UI were recreated out of order."""
        try:
            data = json.loads(_pairing_code_path().read_text(encoding="utf-8"))
            stored_code = _safe_text(data.get("pairing_code"))
            expires_at = _safe_float(data.get("expires_at"), 0.0)
            if stored_code != code or bool(data.get("used")) or expires_at <= now:
                return
            self._current_pairing_code = stored_code
            self._current_pairing_expires_at = expires_at
            self._pairings[stored_code] = {
                "code": stored_code,
                "token": secrets.token_urlsafe(32),
                "created_at": max(0.0, expires_at - self.pairing_ttl),
                "expires_at": expires_at,
                "used": False,
            }
        except Exception as exc:
            _write_log(f"pairing restore error: {exc}")

    def _save_state(self) -> None:
        with self._state_lock:
            payload = {
                "host": self.host,
                "port": self.port,
                "devices": self._devices,
            }
            tmp = self._state_path.with_suffix(".tmp")
            try:
                tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                os.replace(tmp, self._state_path)
            except Exception as exc:
                _write_log(f"state save error: {exc}")
                with contextlib.suppress(Exception):
                    if tmp.exists():
                        tmp.unlink()

    # ------------------------------------------------------------------
    # Runtime
    # ------------------------------------------------------------------
    def is_running(self) -> bool:
        server = self._server
        sockets = getattr(server, "sockets", None) if server is not None else None
        return bool(self._thread and self._thread.is_alive() and self._loop and server and sockets)

    def local_endpoints(self) -> list[str]:
        ip = _local_ip_address()
        hostnames = [socket.gethostname()]
        endpoints = [f"ws://{ip}:{self.port}"]
        for name in hostnames:
            if name and name not in endpoints:
                endpoints.append(f"ws://{name}:{self.port}")
        endpoints.append(f"ws://127.0.0.1:{self.port}")
        seen: set[str] = set()
        ordered: list[str] = []
        for item in endpoints:
            if item not in seen:
                seen.add(item)
                ordered.append(item)
        return ordered

    def start(self, host: str | None = None, port: int | None = None) -> dict[str, Any]:
        if websockets is None:
            return {"ok": False, "error": "websockets paketi bulunamadi."}

        with self._state_lock:
            active_thread = self._thread
            if self.is_running():
                return self.snapshot()
            if active_thread is not None and active_thread.is_alive():
                # A Windows event-loop startup can occasionally stall before
                # asyncio has a chance to report an exception. Do not create
                # another orphan worker for every press of the UI button.
                return {
                    "ok": False,
                    "error": self._start_error or "Cihazlar bağlantı servisi hazırlanamadı; önceki deneme halen yanıt vermiyor.",
                }

        requested_port = int(port if port is not None else self.port)
        # Port 8765 is the documented default. A stale NetOps process or a
        # different local tool can own it, so try a small neighbouring range
        # instead of leaving the Device Hub button with no usable result.
        candidate_ports = [requested_port]
        if requested_port == 8765:
            candidate_ports.extend(range(8766, 8776))

        last_error = "Cihazlar başlatılamadı."
        for candidate_port in candidate_ports:
            with self._state_lock:
                if host:
                    self.host = str(host)
                self.port = int(candidate_port)
                if self.is_running():
                    return self.snapshot()
                self._start_error = ""
                self._ready.clear()
                self._async_stop = None

            self._thread = threading.Thread(target=self._thread_main, name="NetOpsDeviceHub", daemon=True)
            self._thread.start()
            if not self._ready.wait(timeout=2.5):
                # Keep the failure explicit: callers can render their UI and
                # let users retry instead of freezing while a background
                # asyncio setup is blocked by the host environment.
                last_error = self._start_error or "Cihazlar bağlantı servisi zaman aşımına uğradı."
            elif self._start_error:
                last_error = self._start_error
            elif self.is_running():
                self.ensure_pairing_code()
                return self.snapshot()
            else:
                last_error = "Cihazlar bağlantı servisi başlatılamadı."

            # Retry only the common local port collision. Other failures such
            # as a missing networking dependency remain visible to the caller.
            error_text = str(last_error).casefold()
            if "10048" not in error_text and "address already in use" not in error_text and "yalnızca bir kullanıma" not in error_text:
                return {"ok": False, "error": last_error}

        return {"ok": False, "error": last_error}

    def stop(self) -> dict[str, Any]:
        if not self._thread:
            return {"ok": True, "running": False}
        _write_log("server stop requested")
        with self._state_lock:
            loop = self._loop
            stopper = self._async_stop
        if loop and stopper:
            try:
                loop.call_soon_threadsafe(stopper.set)
            except Exception:
                pass
        thread = self._thread
        self._thread = None
        if thread.is_alive():
            thread.join(timeout=3.0)
        return {"ok": True, "running": False}

    def _thread_main(self) -> None:
        try:
            _write_log(f"server thread start: {self.host}:{self.port}")
            asyncio.run(self._async_main())
            _write_log("server thread exit: normal")
        except Exception as exc:
            self._start_error = str(exc)
            _write_log(f"server thread error: {exc}\n{traceback.format_exc()}")
            self._ready.set()

    async def _async_main(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._async_stop = asyncio.Event()
        try:
            _write_log(f"server bind begin: {self.host}:{self.port}")
            self._server = await websockets.serve(
                self._handle_client,
                self.host,
                self.port,
                ping_interval=20,
                ping_timeout=20,
                max_size=2**20,
            )
            _write_log(f"server bind ready: {self.host}:{self.port}")
            self.ensure_pairing_code()
            self._ready.set()
            self._watchdog_task = asyncio.create_task(self._watchdog_loop())
            await self._async_stop.wait()
        finally:
            with contextlib.suppress(Exception):
                if self._watchdog_task:
                    self._watchdog_task.cancel()
                    with contextlib.suppress(Exception):
                        await self._watchdog_task
            with contextlib.suppress(Exception):
                if self._server:
                    self._server.close()
                    await self._server.wait_closed()
            with self._state_lock:
                self._loop = None
                self._server = None
                self._async_stop = None
                self._watchdog_task = None
            _write_log("server socket closed")
            self._ready.set()

    async def _watchdog_loop(self) -> None:
        try:
            while self._async_stop and not self._async_stop.is_set():
                await asyncio.sleep(3.0)
                now = time.time()
                stale: list[str] = []
                with self._state_lock:
                    for device_id, record in self._devices.items():
                        last_seen = _safe_float(record.get("last_seen"), 0.0)
                        if record.get("online") and (now - last_seen) > self.offline_after:
                            stale.append(device_id)
                for device_id in stale:
                    self._mark_offline(device_id, reason="heartbeat timeout")
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            _write_log(f"watchdog error: {exc}")

    # ------------------------------------------------------------------
    # Pairing
    # ------------------------------------------------------------------
    def ensure_pairing_code(self) -> str:
        now = time.time()
        with self._state_lock:
            if self._current_pairing_code and now < self._current_pairing_expires_at:
                self._write_pairing_code_file(self._current_pairing_code, self._current_pairing_expires_at)
                return self._current_pairing_code
            code = f"{secrets.randbelow(900000) + 100000}"
            self._current_pairing_code = code
            self._current_pairing_expires_at = now + self.pairing_ttl
            self._pairings[code] = {
                "code": code,
                "token": secrets.token_urlsafe(32),
                "created_at": now,
                "expires_at": self._current_pairing_expires_at,
                "used": False,
            }
            self._write_pairing_code_file(code, self._current_pairing_expires_at)
            return code

    def _write_pairing_code_file(self, code: str, expires_at: float) -> None:
        try:
            pairing = self._pairings.get(code) or {}
            payload = {
                "pairing_code": code,
                "expires_at": expires_at,
                "expires_in": max(0, int(expires_at - time.time())),
                "server": f"ws://{_local_ip_address()}:{self.port}",
                "used": bool(pairing.get("used")),
            }
            _pairing_code_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            _write_log(f"pairing file write error: {exc}")

    def pairing_info(self) -> dict[str, Any]:
        code = self.ensure_pairing_code()
        return {
            "code": code,
            "expires_at": self._current_pairing_expires_at,
            "expires_in": max(0, int(self._current_pairing_expires_at - time.time())),
        }

    # ------------------------------------------------------------------
    # Snapshot and device updates
    # ------------------------------------------------------------------
    def _device_view(self, record: dict[str, Any]) -> dict[str, Any]:
        now = time.time()
        battery = dict(record.get("battery") or {})
        network = dict(record.get("network") or {})
        media = dict(record.get("media") or {})
        capabilities = _normalize_capabilities(record.get("capabilities"))
        alias = _safe_text(record.get("alias"))
        device_name = _safe_text(record.get("device_name")) or _safe_text(record.get("model")) or "Android"
        display_name = alias or device_name
        last_seen = _safe_float(record.get("last_seen"), now)
        online = bool(record.get("online")) and (now - last_seen) <= self.offline_after
        battery_level = battery.get("level")
        charging = _safe_bool(battery.get("charging"), False)
        media_title = _safe_text(media.get("title"))
        media_artist = _safe_text(media.get("artist"))
        media_app = _safe_text(media.get("app"))
        media_state = _safe_text(media.get("state"))
        if media_title or media_artist or media_app:
            media_text = " • ".join(item for item in [media_app, media_title, media_artist] if item)
        else:
            media_text = "Yok"
        if charging:
            battery_text = f"%{battery_level}" if battery_level is not None else "Bilinmiyor"
            battery_text = f"{battery_text} / Sarj oluyor"
        else:
            battery_text = f"%{battery_level}" if battery_level is not None else "Bilinmiyor"
        return {
            "device_id": _safe_text(record.get("device_id")),
            "display_name": display_name,
            "alias": alias,
            "device_name": device_name,
            "manufacturer": _safe_text(record.get("manufacturer")),
            "model": _safe_text(record.get("model")),
            "android_version": _safe_text(record.get("android_version")),
            "sdk_int": record.get("sdk_int"),
            "agent_version": _safe_text(record.get("agent_version")),
            "status": "ONLINE" if online else "OFFLINE",
            "online": online,
            "paired_at": _safe_float(record.get("paired_at"), now),
            "connected_at": _safe_float(record.get("connected_at"), now),
            "last_seen": last_seen,
            "last_seen_text": _time_ago(now - last_seen),
            "battery": battery,
            "battery_text": battery_text,
            "charging": charging,
            "screen": _safe_text(record.get("screen"), "unknown"),
            "volume": record.get("volume"),
            "network": network,
            "network_type": _safe_text(network.get("type"), "unknown"),
            "root": _safe_bool(record.get("root"), False),
            "capabilities": capabilities,
            "media": media,
            "media_text": media_text,
            "media_state": media_state,
            "ip": _safe_text(record.get("ip")),
            "last_error": _safe_text(record.get("last_error")),
        }

    def snapshot(self) -> dict[str, Any]:
        now = time.time()
        with self._state_lock:
            devices = [self._device_view(record) for record in self._devices.values()]
            devices.sort(key=lambda item: (not item["online"], item["display_name"].casefold(), item["last_seen"]), reverse=False)
            code = self.ensure_pairing_code()
            running = self.is_running()
            total = len(devices)
            online_count = sum(1 for item in devices if item["online"])
            return {
                "ok": True,
                "running": running,
                "host": self.host,
                "port": self.port,
                "endpoints": self.local_endpoints(),
                "pairing_code": code,
                "pairing_expires_in": max(0, int(self._current_pairing_expires_at - now)),
                "devices": devices,
                "device_count": total,
                "online_count": online_count,
                "pc_name": socket.gethostname(),
            }

    def _apply_device_payload(self, record: dict[str, Any], payload: dict[str, Any], *, connected: bool = False) -> None:
        now = time.time()
        if connected:
            record["connected_at"] = now
        record["last_seen"] = now
        record["online"] = True
        record["last_error"] = ""
        if "device_name" in payload:
            record["device_name"] = _safe_text(payload.get("device_name"))
        if "manufacturer" in payload:
            record["manufacturer"] = _safe_text(payload.get("manufacturer"))
        if "model" in payload:
            record["model"] = _safe_text(payload.get("model"))
        if "android_version" in payload:
            record["android_version"] = _safe_text(payload.get("android_version"))
        if "sdk_int" in payload:
            record["sdk_int"] = _safe_int(payload.get("sdk_int"))
        if "agent_version" in payload:
            record["agent_version"] = _safe_text(payload.get("agent_version"))
        if "battery" in payload and isinstance(payload.get("battery"), dict):
            battery = dict(record.get("battery") or {})
            battery_payload = dict(payload.get("battery") or {})
            if "level" in battery_payload:
                battery["level"] = _safe_int(battery_payload.get("level"))
            if "charging" in battery_payload:
                battery["charging"] = _safe_bool(battery_payload.get("charging"))
            record["battery"] = battery
        if "screen" in payload:
            record["screen"] = _safe_text(payload.get("screen"), "unknown") or "unknown"
        if "volume" in payload:
            record["volume"] = _safe_int(payload.get("volume"))
        if "network" in payload and isinstance(payload.get("network"), dict):
            network = dict(record.get("network") or {})
            network.update({str(k): v for k, v in dict(payload.get("network") or {}).items() if k is not None})
            record["network"] = network
        if "root" in payload:
            record["root"] = _safe_bool(payload.get("root"))
        if "capabilities" in payload:
            merged = dict(record.get("capabilities") or {})
            merged.update(_normalize_capabilities(payload.get("capabilities")))
            record["capabilities"] = merged
        if "media" in payload and isinstance(payload.get("media"), dict):
            merged_media = dict(record.get("media") or {})
            merged_media.update(_normalize_media(payload.get("media")))
            record["media"] = merged_media
        if "ip" in payload:
            record["ip"] = _safe_text(payload.get("ip"))
        if "last_error" in payload:
            record["last_error"] = _safe_text(payload.get("last_error"))

    def rename_device(self, device_id: str, alias: str) -> dict[str, Any]:
        device_id = _safe_text(device_id)
        alias = _safe_text(alias)
        with self._state_lock:
            record = self._devices.get(device_id)
            if not record:
                return {"ok": False, "error": "DEVICE_NOT_FOUND"}
            record["alias"] = alias
            self._save_state()
            return {"ok": True, "device": self._device_view(record)}

    def _bind_device(self, websocket: Any, device_id: str) -> None:
        with self._state_lock:
            self._connections[device_id] = websocket

    def _unbind_device(self, websocket: Any, device_id: str | None) -> None:
        with self._state_lock:
            if device_id and self._connections.get(device_id) is websocket:
                self._connections.pop(device_id, None)

    def _mark_offline(self, device_id: str, reason: str = "") -> None:
        with self._state_lock:
            record = self._devices.get(device_id)
            if not record:
                return
            record["online"] = False
            if reason:
                record["last_error"] = reason
            self._connections.pop(device_id, None)
            self._save_state()

    # ------------------------------------------------------------------
    # WebSocket protocol
    # ------------------------------------------------------------------
    async def _handle_client(self, websocket: Any) -> None:
        device_id: str | None = None
        try:
            async for raw in websocket:
                message = self._decode_message(raw)
                if not isinstance(message, dict):
                    await websocket.send(json.dumps({"type": "error", "error": "INVALID_JSON"}, ensure_ascii=False))
                    continue
                response, device_id = await self._process_message(websocket, message, device_id)
                if response is not None:
                    await websocket.send(json.dumps(response, ensure_ascii=False))
        except Exception as exc:
            _write_log(f"client error: {exc}")
        finally:
            if device_id:
                self._unbind_device(websocket, device_id)
                self._mark_offline(device_id, reason="connection closed")

    def _decode_message(self, raw: Any) -> Any:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except Exception:
                return None
        return None

    async def _process_message(self, websocket: Any, message: dict[str, Any], current_device_id: str | None) -> tuple[dict[str, Any] | None, str | None]:
        kind = _safe_text(message.get("type")).casefold()
        if kind == "hello":
            response, device_id = self._handle_hello(websocket, message)
            return response, device_id
        if kind in {"heartbeat", "device_status", "status"}:
            device_id = _safe_text(message.get("device_id")) or current_device_id
            if not device_id:
                return {"type": "error", "error": "MISSING_DEVICE_ID"}, current_device_id
            with self._state_lock:
                record = self._devices.get(device_id)
                if not record:
                    return {"type": "error", "error": "UNKNOWN_DEVICE"}, current_device_id
                self._apply_device_payload(record, message)
                self._save_state()
            return {"type": "heartbeat_ack", "device_id": device_id, "timestamp": time.time()}, device_id
        if kind == "assistant_request":
            device_id = _safe_text(message.get("device_id")) or current_device_id
            request_id = _safe_text(message.get("id")) or f"req_{uuid.uuid4().hex}"
            text = _safe_text(message.get("text"))
            if not device_id:
                return {"type": "assistant_response", "id": request_id, "ok": False, "error": "MISSING_DEVICE_ID"}, current_device_id
            if not text:
                return {"type": "assistant_response", "id": request_id, "ok": False, "error": "EMPTY_REQUEST"}, current_device_id
            if len(text) > 4000:
                return {"type": "assistant_response", "id": request_id, "ok": False, "error": "REQUEST_TOO_LONG"}, current_device_id
            with self._state_lock:
                known = self._devices.get(device_id)
                handler = _ASSISTANT_REQUEST_HANDLER
            if not known:
                return {"type": "assistant_response", "id": request_id, "ok": False, "error": "UNKNOWN_DEVICE"}, current_device_id
            if handler is None:
                return {"type": "assistant_response", "id": request_id, "ok": False, "error": "ASSISTANT_OFFLINE"}, current_device_id
            try:
                result = await asyncio.to_thread(handler, text, device_id)
                if isinstance(result, dict):
                    response = {"type": "assistant_response", "id": request_id, "ok": bool(result.get("ok", True))}
                    response.update({str(key): value for key, value in result.items() if key not in {"type", "id"}})
                else:
                    response = {"type": "assistant_response", "id": request_id, "ok": True, "display_text": _safe_text(result)}
                return response, device_id
            except Exception as exc:
                _write_log(f"assistant request error: {exc}\n{traceback.format_exc()}")
                return {"type": "assistant_response", "id": request_id, "ok": False, "error": "ASSISTANT_REQUEST_FAILED"}, device_id
        if kind == "media_request":
            device_id = _safe_text(message.get("device_id")) or current_device_id
            request_id = _safe_text(message.get("id")) or f"media_{uuid.uuid4().hex}"
            action = _safe_text(message.get("action")).casefold()
            args = dict(message.get("args") or {}) if isinstance(message.get("args"), dict) else {}
            allowed_actions = {"play_pause", "next", "previous", "current", "set_volume"}
            if action not in allowed_actions:
                return {"type": "media_response", "id": request_id, "ok": False, "error": "MEDIA_ACTION_NOT_ALLOWED"}, current_device_id
            with self._state_lock:
                record = self._devices.get(device_id) if device_id else None
                handler = _MEDIA_REQUEST_HANDLER
                if record:
                    record["last_seen"] = time.time()
                    record["online"] = True
                    record["last_error"] = ""
                    self._save_state()
            if not record:
                return {"type": "media_response", "id": request_id, "ok": False, "error": "UNKNOWN_DEVICE"}, current_device_id
            if handler is None:
                return {"type": "media_response", "id": request_id, "ok": False, "error": "MEDIA_UNAVAILABLE"}, device_id
            try:
                result = await asyncio.to_thread(handler, action, args, device_id)
                if isinstance(result, dict):
                    response = {"type": "media_response", "id": request_id, "ok": bool(result.get("ok", True))}
                    response.update({str(key): value for key, value in result.items() if key not in {"type", "id"}})
                else:
                    response = {"type": "media_response", "id": request_id, "ok": True, "display_text": _safe_text(result)}
                return response, device_id
            except Exception as exc:
                _write_log(f"media request error: {exc}\n{traceback.format_exc()}")
                return {"type": "media_response", "id": request_id, "ok": False, "error": "MEDIA_REQUEST_FAILED"}, device_id
        if kind == "input_request":
            device_id = _safe_text(message.get("device_id")) or current_device_id
            request_id = _safe_text(message.get("id")) or f"input_{uuid.uuid4().hex}"
            key = _safe_text(message.get("key")).casefold()
            modifiers = message.get("modifiers")
            if not device_id:
                return {"type": "input_response", "id": request_id, "ok": False, "error": "MISSING_DEVICE_ID"}, current_device_id
            if not key or len(key) > 32:
                return {"type": "input_response", "id": request_id, "ok": False, "error": "INPUT_KEY_INVALID"}, current_device_id
            with self._state_lock:
                record = self._devices.get(device_id)
                handler = _INPUT_REQUEST_HANDLER
                if record:
                    record["last_seen"] = time.time()
                    record["online"] = True
                    record["last_error"] = ""
                    self._save_state()
            if not record:
                return {"type": "input_response", "id": request_id, "ok": False, "error": "UNKNOWN_DEVICE"}, current_device_id
            if handler is None:
                return {"type": "input_response", "id": request_id, "ok": False, "error": "INPUT_UNAVAILABLE"}, device_id
            try:
                result = await asyncio.to_thread(handler, key, modifiers, device_id)
                if isinstance(result, dict):
                    response = {"type": "input_response", "id": request_id, "ok": bool(result.get("ok", True))}
                    response.update({str(key_name): value for key_name, value in result.items() if key_name not in {"type", "id"}})
                else:
                    response = {"type": "input_response", "id": request_id, "ok": True, "display_text": _safe_text(result)}
                return response, device_id
            except Exception as exc:
                _write_log(f"input request error: {exc}\n{traceback.format_exc()}")
                return {"type": "input_response", "id": request_id, "ok": False, "error": "INPUT_REQUEST_FAILED"}, device_id
        if kind == "capabilities":
            device_id = _safe_text(message.get("device_id")) or current_device_id
            if not device_id:
                return {"type": "error", "error": "MISSING_DEVICE_ID"}, current_device_id
            with self._state_lock:
                record = self._devices.get(device_id)
                if not record:
                    return {"type": "error", "error": "UNKNOWN_DEVICE"}, current_device_id
                record["capabilities"] = dict(record.get("capabilities") or {})
                record["capabilities"].update(_normalize_capabilities(message))
                record["last_seen"] = time.time()
                record["online"] = True
                self._save_state()
            return {"type": "capabilities_ack", "device_id": device_id}, device_id
        if kind == "command_result":
            command_id = _safe_text(message.get("id"))
            if command_id:
                with self._state_lock:
                    future = self._pending_commands.pop(command_id, None)
                if future and not future.done():
                    try:
                        future.set_result(message)
                    except Exception:
                        pass
            return None, current_device_id
        if kind in {"audio_stream_start", "audio_chunk", "audio_stream_stop"}:
            device_id = _safe_text(message.get("device_id")) or current_device_id
            if not device_id:
                return {"type": "error", "error": "MISSING_DEVICE_ID"}, current_device_id
            with self._state_lock:
                record = self._devices.get(device_id)
                if not record:
                    return {"type": "error", "error": "UNKNOWN_DEVICE"}, current_device_id
                record["last_seen"] = time.time()
                record["online"] = True
                live_audio = dict(record.get("live_audio") or {})
                live_audio["device_id"] = device_id
                live_audio["updated_at"] = time.time()
                if kind == "audio_stream_start":
                    live_audio["active"] = True
                    live_audio["source"] = "tablet"
                    live_audio["sample_rate"] = _safe_int(message.get("sample_rate"), 16000)
                    live_audio["channels"] = _safe_int(message.get("channels"), 1)
                    live_audio["chunk_ms"] = _safe_int(message.get("chunk_ms"), 100)
                    live_audio["label"] = _safe_text(message.get("label")) or "Tablet mikrofonu"
                    _append_audio_stream(
                        {
                            "event": "start",
                            "device_id": device_id,
                            "sample_rate": live_audio.get("sample_rate"),
                            "channels": live_audio.get("channels"),
                            "chunk_ms": live_audio.get("chunk_ms"),
                            "label": live_audio.get("label"),
                            "timestamp": time.time(),
                        }
                    )
                elif kind == "audio_chunk":
                    chunk_b64 = _safe_text(message.get("pcm16_b64") or message.get("pcm16") or message.get("audio"))
                    if not chunk_b64:
                        return {"type": "error", "error": "MISSING_AUDIO_DATA"}, current_device_id
                    try:
                        base64.b64decode(chunk_b64.encode("ascii"), validate=True)
                    except Exception:
                        return {"type": "error", "error": "INVALID_AUDIO_DATA"}, current_device_id
                    live_audio["active"] = True
                    live_audio["last_level"] = _safe_float(message.get("level"), 0.0)
                    live_audio["sample_rate"] = _safe_int(message.get("sample_rate"), 16000)
                    live_audio["channels"] = _safe_int(message.get("channels"), 1)
                    live_audio["label"] = _safe_text(message.get("label")) or live_audio.get("label") or "Tablet mikrofonu"
                    _append_audio_stream(
                        {
                            "event": "chunk",
                            "device_id": device_id,
                            "seq": _safe_int(message.get("seq")),
                            "sample_rate": live_audio.get("sample_rate"),
                            "channels": live_audio.get("channels"),
                            "chunk_ms": _safe_int(message.get("chunk_ms"), 100),
                            "level": live_audio.get("last_level"),
                            "timestamp": _safe_float(message.get("timestamp"), time.time()),
                            "pcm16_b64": chunk_b64,
                        }
                    )
                else:
                    live_audio["active"] = False
                    live_audio["stopped_at"] = time.time()
                    _append_audio_stream(
                        {
                            "event": "stop",
                            "device_id": device_id,
                            "reason": _safe_text(message.get("reason")) or "tablet_request",
                            "timestamp": time.time(),
                        }
                    )
                record["live_audio"] = live_audio
                self._save_state()
            return None, device_id
        if kind == "pong":
            return None, current_device_id
        return {"type": "error", "error": "UNSUPPORTED_MESSAGE"}, current_device_id

    def _handle_hello(self, websocket: Any, message: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
        now = time.time()
        provided_device_id = _safe_text(message.get("device_id"))
        provided_token = _safe_text(message.get("token"))
        pairing_code = _safe_text(message.get("pairing_code"))
        device_name = _safe_text(message.get("device_name"))
        model = _safe_text(message.get("model"))
        manufacturer = _safe_text(message.get("manufacturer"))

        with self._state_lock:
            record = None
            paired = False
            reconnected = False

            if provided_device_id and provided_token:
                candidate = self._devices.get(provided_device_id)
                if candidate and _safe_text(candidate.get("token")) == provided_token:
                    record = candidate
                    reconnected = True
            if record is None and pairing_code:
                pairing = self._pairings.get(pairing_code)
                if pairing is None:
                    # The QR file is the hand-off between the desktop UI and
                    # this long-running hub. Restore it if the UI was opened
                    # before the hub object was recreated.
                    self._restore_pairing_from_file(pairing_code, now)
                    pairing = self._pairings.get(pairing_code)
                if pairing and not pairing.get("used") and now < _safe_float(pairing.get("expires_at"), 0.0):
                    device_id = f"netops_{uuid.uuid4().hex[:12]}"
                    token = _safe_text(pairing.get("token")) or secrets.token_urlsafe(32)
                    record = _default_device_record(device_id, token)
                    if device_name:
                        record["device_name"] = device_name
                    if model:
                        record["model"] = model
                    if manufacturer:
                        record["manufacturer"] = manufacturer
                    record["paired_at"] = now
                    record["connected_at"] = now
                    record["last_seen"] = now
                    record["online"] = True
                    record["ip"] = _safe_text(getattr(websocket, "remote_address", ("", 0))[0] if getattr(websocket, "remote_address", None) else "")
                    self._devices[device_id] = record
                    pairing["used"] = True
                    pairing["device_id"] = device_id
                    self._write_pairing_code_file(pairing_code, _safe_float(pairing.get("expires_at"), now))
                    paired = True
                else:
                    return {
                        "type": "hello_result",
                        "ok": False,
                        "error": "INVALID_PAIRING_CODE",
                    }, None
            if record is None:
                return {
                    "type": "hello_result",
                    "ok": False,
                    "error": "PAIRING_REQUIRED",
                }, None

            self._apply_device_payload(record, message, connected=True)
            self._connections[record["device_id"]] = websocket
            self._save_state()
            device_view = self._device_view(record)

        response = {
            "type": "hello_result",
            "ok": True,
            "paired": paired,
            "reconnected": reconnected,
            "device_id": device_view["device_id"],
            "token": _safe_text(record.get("token")),
            "heartbeat_interval": self.heartbeat_interval,
            "offline_after": self.offline_after,
            "pc_name": socket.gethostname(),
            "pc_ip": _local_ip_address(),
            "server_time": now,
            "device": device_view,
        }
        return response, device_view["device_id"]

    async def _send_command_async(self, device_id: str, command: str, args: dict[str, Any] | None = None, timeout: int = 12) -> dict[str, Any]:
        device_id = _safe_text(device_id)
        command = _safe_text(command)
        args = dict(args or {})
        with self._state_lock:
            websocket = self._connections.get(device_id)
            loop = self._loop
        if websocket is None or loop is None:
            return {"ok": False, "error": "DEVICE_OFFLINE"}

        command_id = f"cmd_{uuid.uuid4().hex}"
        payload = {
            "type": "command",
            "id": command_id,
            "command": command,
            "args": args,
        }
        future: asyncio.Future = loop.create_future()
        with self._state_lock:
            self._pending_commands[command_id] = future

        try:
            await websocket.send(json.dumps(payload, ensure_ascii=False))
        except Exception as exc:
            with self._state_lock:
                self._pending_commands.pop(command_id, None)
            return {"ok": False, "error": str(exc)}

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            if isinstance(result, dict):
                return result
            return {"ok": True, "result": result}
        except asyncio.TimeoutError:
            with self._state_lock:
                self._pending_commands.pop(command_id, None)
            return {"ok": False, "error": "TIMEOUT"}
        except Exception as exc:
            with self._state_lock:
                self._pending_commands.pop(command_id, None)
            return {"ok": False, "error": str(exc)}

    def send_command(self, device_id: str, command: str, args: dict[str, Any] | None = None, timeout: int = 12) -> dict[str, Any]:
        with self._state_lock:
            loop = self._loop
        if loop is None:
            return {"ok": False, "error": "SERVER_NOT_RUNNING"}
        future = asyncio.run_coroutine_threadsafe(
            self._send_command_async(device_id, command, args=args, timeout=timeout),
            loop,
        )
        try:
            return future.result(timeout=max(1, timeout + 2))
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def request_status(self, device_id: str) -> dict[str, Any]:
        return self.send_command(device_id, "request_status", {}, timeout=8)


def get_device_hub() -> NetOpsDeviceHub:
    global _DEVICE_HUB_SINGLETON
    if _DEVICE_HUB_SINGLETON is None:
        _DEVICE_HUB_SINGLETON = NetOpsDeviceHub()
    return _DEVICE_HUB_SINGLETON


def device_hub_start(host: str | None = None, port: int | None = None) -> dict[str, Any]:
    return get_device_hub().start(host=host, port=port)


def device_hub_stop() -> dict[str, Any]:
    return get_device_hub().stop()


def device_hub_snapshot() -> dict[str, Any]:
    return get_device_hub().snapshot()


def device_hub_create_pairing_code() -> str:
    return get_device_hub().ensure_pairing_code()


def device_hub_rename(device_id: str, alias: str) -> dict[str, Any]:
    return get_device_hub().rename_device(device_id, alias)


def device_hub_send_command(device_id: str, command: str, args: dict[str, Any] | None = None, timeout: int = 12) -> dict[str, Any]:
    return get_device_hub().send_command(device_id, command, args=args, timeout=timeout)


def device_hub_set_assistant_handler(handler: Callable[[str, str], Any] | None) -> None:
    """Register the desktop NetOps One handler for authenticated mobile requests."""
    global _ASSISTANT_REQUEST_HANDLER
    _ASSISTANT_REQUEST_HANDLER = handler


def device_hub_set_media_handler(handler: Callable[[str, dict[str, Any], str], Any] | None) -> None:
    """Register the allowlisted desktop Now Playing handler."""
    global _MEDIA_REQUEST_HANDLER
    _MEDIA_REQUEST_HANDLER = handler


def device_hub_set_input_handler(handler: Callable[[str, Any, str], Any] | None) -> None:
    """Register the allowlisted phone keyboard/navigation handler."""
    global _INPUT_REQUEST_HANDLER
    _INPUT_REQUEST_HANDLER = handler


def open_device_hub_window(parent=None, T=None, palette=None, say_callback=None):
    """Open a compact device management window."""
    global _DEVICE_HUB_WINDOW
    try:
        import tkinter as tk
        import tkinter.messagebox as messagebox
        import tkinter.simpledialog as simpledialog

        import customtkinter as ctk
    except Exception as exc:
        _write_log(f"ui import error: {exc}")
        return None

    hub = get_device_hub()
    hub.ensure_pairing_code()

    root = parent or getattr(tk, "_default_root", None)
    if root is None:
        return None

    if _DEVICE_HUB_WINDOW is not None:
        try:
            if _DEVICE_HUB_WINDOW.winfo_exists():
                _DEVICE_HUB_WINDOW.deiconify()
                _DEVICE_HUB_WINDOW.lift()
                _DEVICE_HUB_WINDOW.focus_force()
                return _DEVICE_HUB_WINDOW
        except Exception:
            _DEVICE_HUB_WINDOW = None

    def _pal(key: str, fallback: str) -> str:
        if isinstance(palette, dict):
            value = palette.get(key)
            if value:
                return str(value)
        return fallback

    window = ctk.CTkToplevel(root)
    _DEVICE_HUB_WINDOW = window
    window.title("NetOps Cihazlar")
    window.geometry("900x720")
    window.minsize(820, 620)
    window.configure(fg_color=_pal("bg", "#0B1020"))

    try:
        window.transient(root)
        window.attributes("-topmost", True)
        window.after(350, lambda: window.attributes("-topmost", False))
    except Exception:
        pass

    status_var = tk.StringVar(value="Cihaz baglanti servisi hazirlaniyor...")
    endpoint_var = tk.StringVar(value="")
    pairing_var = tk.StringVar(value="")
    count_var = tk.StringVar(value="")
    selection_var = tk.StringVar(value="Secili cihaz yok.")
    auto_pair_attempted = False
    hub_status_override = "Cihaz baglanti servisi hazirlaniyor..."

    shell = ctk.CTkFrame(
        window,
        fg_color=_pal("card", "#121A2D"),
        corner_radius=8,
        border_width=1,
        border_color=_pal("entry_border", "#2B3550"),
    )
    shell.pack(fill="both", expand=True, padx=14, pady=14)
    shell.grid_columnconfigure(0, weight=1)
    shell.grid_rowconfigure(2, weight=1)

    header = ctk.CTkFrame(shell, fg_color="transparent")
    header.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 10))
    header.grid_columnconfigure(0, weight=1)

    title = ctk.CTkLabel(
        header,
        text="Cihazlar",
        text_color=_pal("text_main", "#F5F7FF"),
        font=("Segoe UI Semibold", 24),
        anchor="w",
    )
    title.grid(row=0, column=0, sticky="w")

    subtitle = ctk.CTkLabel(
        header,
        text="Tanidigin USB cihazlarini + ile ekle; NetOps komutlari ve medya baglantisini yonet.",
        text_color=_pal("text_dim", "#9FA9C1"),
        font=("Segoe UI", 11),
        anchor="w",
    )
    subtitle.grid(row=1, column=0, sticky="w", pady=(2, 0))

    controls = ctk.CTkFrame(shell, fg_color="transparent")
    controls.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 12))
    controls.grid_columnconfigure((0, 1, 2), weight=1, uniform="hub")

    server_card = ctk.CTkFrame(
        controls,
        fg_color=_pal("sidebar", "#0F1830"),
        corner_radius=6,
    )
    server_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
    server_card.grid_columnconfigure(0, weight=1)

    pairing_card = ctk.CTkFrame(
        controls,
        fg_color=_pal("sidebar", "#0F1830"),
        corner_radius=6,
    )
    pairing_card.grid(row=0, column=1, sticky="nsew", padx=8)
    pairing_card.grid_columnconfigure(0, weight=1)

    action_card = ctk.CTkFrame(
        controls,
        fg_color=_pal("sidebar", "#0F1830"),
        corner_radius=6,
    )
    action_card.grid(row=0, column=2, sticky="nsew", padx=(8, 0))
    action_card.grid_columnconfigure((0, 1), weight=1)

    ctk.CTkLabel(
        server_card,
        text="PC LAN adresi",
        text_color=_pal("text_dim", "#9FA9C1"),
        font=("Segoe UI", 10),
        anchor="w",
    ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 0))
    endpoint_label = ctk.CTkLabel(
        server_card,
        textvariable=endpoint_var,
        text_color=_pal("text_main", "#F5F7FF"),
        font=("Segoe UI Semibold", 13),
        anchor="w",
        justify="left",
    )
    endpoint_label.grid(row=1, column=0, sticky="w", padx=14, pady=(4, 2))
    count_label = ctk.CTkLabel(
        server_card,
        textvariable=count_var,
        text_color=_pal("text_dim", "#9FA9C1"),
        font=("Segoe UI", 10),
        anchor="w",
    )
    count_label.grid(row=2, column=0, sticky="w", padx=14, pady=(0, 12))

    ctk.CTkLabel(
        pairing_card,
        text="Pairing kodu",
        text_color=_pal("text_dim", "#9FA9C1"),
        font=("Segoe UI", 10),
        anchor="w",
    ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 0))
    pairing_entry = ctk.CTkEntry(
        pairing_card,
        textvariable=pairing_var,
        height=34,
        fg_color=_pal("entry_bg", "#10182A"),
        border_color=_pal("entry_border", "#2B3550"),
        text_color=_pal("text_main", "#F5F7FF"),
    )
    pairing_entry.grid(row=1, column=0, sticky="ew", padx=14, pady=(4, 8))

    pairing_button_row = ctk.CTkFrame(pairing_card, fg_color="transparent")
    pairing_button_row.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 12))
    pairing_button_row.grid_columnconfigure((0, 1, 2), weight=1, uniform="pair")

    def _copy_pairing_code() -> None:
        try:
            code = pairing_var.get().strip()
            window.clipboard_clear()
            window.clipboard_append(code)
            window.update()
            status_var.set("Pairing kodu kopyalandi.")
        except Exception:
            status_var.set("Pairing kodu kopyalanamadi.")

    def _new_pairing_code() -> None:
        code = hub.ensure_pairing_code()
        pairing_var.set(code)
        status_var.set("Yeni pairing kodu olusturuldu.")

    def _show_pairing_qr() -> None:
        try:
            import qrcode
            from PIL import ImageTk

            snapshot = hub.snapshot()
            payload = json.dumps(
                {
                    "server": f"ws://{_local_ip_address()}:{hub.port}",
                    "pairing_code": pairing_var.get().strip() or hub.ensure_pairing_code(),
                    "name": snapshot.get("pc_name") or socket.gethostname(),
                },
                ensure_ascii=False,
            )
            image = qrcode.make(payload).convert("RGB").resize((300, 300))
            qr_window = ctk.CTkToplevel(window)
            qr_window.title("NetOps cihaz eslestirme")
            qr_window.geometry("360x400")
            qr_window.configure(fg_color=_pal("bg", "#0B1020"))
            qr_window.transient(window)
            qr_window.grab_set()
            image_ref = ImageTk.PhotoImage(image)
            qr_label = ctk.CTkLabel(qr_window, text="", image=image_ref)
            qr_label.image = image_ref
            qr_label.pack(padx=24, pady=(24, 10))
            ctk.CTkLabel(
                qr_window,
                text="Android uygulamasinda Cihaz ekle > QR kod ile tara sec.",
                text_color=_pal("text_dim", "#9FA9C1"),
                wraplength=300,
            ).pack(padx=18, pady=(0, 16))
        except Exception as exc:
            status_var.set(f"QR olusturulamadi: {exc}")

    def _send_pairing_to_tablet() -> None:
        nonlocal auto_pair_attempted
        auto_pair_attempted = True

        def worker() -> None:
            try:
                import neto_android_device
            except Exception as exc:
                try:
                    window.after(0, lambda: status_var.set(f"ADB modulu acilamadi: {exc}"))
                except Exception:
                    pass
                return

            pairing_code = pairing_var.get().strip() or hub.ensure_pairing_code()
            server_url = f"ws://127.0.0.1:{hub.port}"
            serial, error = neto_android_device._first_authorized_device()
            if not serial:
                message = error or "USB Android cihaz bulunamadi."
                try:
                    window.after(0, lambda: status_var.set(message))
                except Exception:
                    pass
                return

            result = neto_android_device.launch_netops_agent(serial, server_url, pairing_code)
            message = str(result.get("message") or result.get("error") or "Tablet acilamadi.")
            try:
                window.after(0, lambda: status_var.set(message))
                window.after(0, lambda: selection_var.set(f"Eslestirme hedefi: {serial}"))
            except Exception:
                pass
            if result.get("ok"):
                try:
                    window.after(900, lambda: _refresh_ui(schedule_next=False))
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()

    ctk.CTkButton(
        pairing_button_row,
        text="Yeni Kod",
        height=30,
        command=_new_pairing_code,
    ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
    ctk.CTkButton(
        pairing_button_row,
        text="Kopyala",
        height=30,
        command=_copy_pairing_code,
    ).grid(row=0, column=1, sticky="ew", padx=6)
    ctk.CTkButton(
        pairing_button_row,
        text="QR Goster",
        height=30,
        command=_show_pairing_qr,
    ).grid(row=0, column=2, sticky="ew", padx=(6, 0))

    ctk.CTkLabel(
        action_card,
        text="Actions",
        text_color=_pal("text_dim", "#9FA9C1"),
        font=("Segoe UI", 10),
        anchor="w",
    ).grid(row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(12, 0))

    def _toggle_server() -> None:
        if hub.is_running():
            hub.stop()
            _set_hub_status("Cihazlar durduruldu.")
            _refresh_ui(schedule_next=False)
        else:
            _start_hub_async(manual=True)

    start_stop_button = ctk.CTkButton(action_card, text="Baslat / Durdur", height=30, command=_toggle_server)
    start_stop_button.grid(row=1, column=0, columnspan=2, sticky="ew", padx=14, pady=(6, 6))

    refresh_button = ctk.CTkButton(action_card, text="Yenile", height=30, command=lambda: _refresh_ui(schedule_next=False))
    refresh_button.grid(row=2, column=0, sticky="ew", padx=(14, 6), pady=(0, 12))

    def _open_logs_folder() -> None:
        try:
            if os.name == "nt":
                os.startfile(str(_logs_dir()))
            else:
                import subprocess

                subprocess.Popen(["xdg-open", str(_logs_dir())])
        except Exception as exc:
            status_var.set(f"Log klasoru acilamadi: {exc}")

    log_button = ctk.CTkButton(
        action_card,
        text="Loglar",
        height=30,
        command=_open_logs_folder,
    )
    log_button.grid(row=2, column=1, sticky="ew", padx=(6, 14), pady=(0, 12))

    send_button = ctk.CTkButton(
        action_card,
        text="Tablete Gonder",
        height=30,
        command=_send_pairing_to_tablet,
    )
    send_button.grid(row=3, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 12))

    def _add_usb_device() -> None:
        """Explicitly approve one authorized USB device for Termux auto-connect."""
        try:
            import neto_android_device
        except Exception as exc:
            _set_hub_status(f"Android USB modulu acilamadi: {exc}")
            return
        listed = neto_android_device.list_usb_devices()
        usb_devices = listed.get("usb_devices") or []
        registry = neto_android_device.load_usb_registry()
        candidates = neto_android_device.unregistered_authorized_usb_devices(usb_devices, registry)
        if not candidates:
            unauthorized = [item for item in usb_devices if item.get("state") != "device"]
            if unauthorized:
                _set_hub_status("USB cihaz bulundu ancak USB hata ayiklama izni onaylanmamis.")
            else:
                _set_hub_status("Taninmayan yetkili USB cihaz yok. Telefonu bagla ve + ile tekrar dene.")
            return
        serial = str(candidates[0].get("serial") or "")
        if len(candidates) > 1:
            choices = ", ".join(str(item.get("serial") or "") for item in candidates)
            selected = simpledialog.askstring(
                "USB cihaz sec",
                f"Taninmayan cihaz seri numaralari:\n{choices}\n\nSeri numarasini yaz:",
                initialvalue=serial,
                parent=window,
            )
            if selected is None:
                return
            serial = selected.strip()
        if not any(str(item.get("serial") or "") == serial for item in candidates):
            _set_hub_status("Bu cihaz taninmadi; yalnizca yetkili USB listesinden secim yapilabilir.")
            return
        name = simpledialog.askstring(
            "Cihaz adi",
            "NetOps'ta gorunecek cihaz adini gir:",
            initialvalue="Telefonum",
            parent=window,
        )
        if name is None or not name.strip():
            return
        _set_hub_status("Termux'a netops komutu kuruluyor ve cihaz eslestiriliyor...")

        def worker() -> None:
            result = neto_android_device.register_termux_device(
                serial,
                f"ws://127.0.0.1:{hub.port}",
                hub.ensure_pairing_code(),
                name.strip(),
            )

            def apply_result() -> None:
                message = str(result.get("message") or result.get("error") or "USB cihaz eklenemedi.")
                _set_hub_status(message)
                selection_var.set(f"USB hedefi: {serial}")
                _refresh_ui(schedule_next=False)

            try:
                window.after(0, apply_result)
            except Exception:
                pass

        threading.Thread(target=worker, name="NetOpsUsbDeviceRegistrar", daemon=True).start()

    add_device_button = ctk.CTkButton(
        action_card,
        text="+ Cihaz Ekle",
        height=30,
        command=_add_usb_device,
    )
    add_device_button.grid(row=4, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 12))

    content = ctk.CTkFrame(shell, fg_color="transparent")
    content.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 8))
    content.grid_columnconfigure(0, weight=1)
    content.grid_rowconfigure(0, weight=1)

    scroll = ctk.CTkScrollableFrame(
        content,
        fg_color=_pal("bg", "#0B1020"),
        corner_radius=8,
        border_width=1,
        border_color=_pal("entry_border", "#2B3550"),
    )
    scroll.grid(row=0, column=0, sticky="nsew")
    scroll.grid_columnconfigure(0, weight=1)

    footer = ctk.CTkFrame(shell, fg_color="transparent")
    footer.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 14))
    footer.grid_columnconfigure(0, weight=1)

    status_label = ctk.CTkLabel(
        footer,
        textvariable=status_var,
        text_color=_pal("text_dim", "#9FA9C1"),
        font=("Segoe UI", 10),
        anchor="w",
    )
    status_label.grid(row=0, column=0, sticky="ew")

    selection_label = ctk.CTkLabel(
        footer,
        textvariable=selection_var,
        text_color=_pal("text_main", "#F5F7FF"),
        font=("Segoe UI Semibold", 11),
        anchor="w",
    )
    selection_label.grid(row=1, column=0, sticky="ew", pady=(2, 0))

    def _set_status(message: str) -> None:
        status_var.set(message)

    def _clipboard_copy(value: str) -> None:
        try:
            window.clipboard_clear()
            window.clipboard_append(value)
            window.update()
        except Exception:
            pass

    def _send_command(device_id: str, command: str, args: dict[str, Any] | None = None) -> None:
        def worker() -> None:
            result = hub.send_command(device_id, command, args=args or {}, timeout=12)
            if result.get("ok") or result.get("success"):
                text = f"{command} gonderildi: {device_id}"
            else:
                text = f"{command} basarisiz: {result.get('error', 'bilinmiyor')}"
            try:
                window.after(0, lambda: _set_status(text))
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _rename_device(device_id: str, current_name: str) -> None:
        new_name = simpledialog.askstring(
            "Cihaz Adi",
            "Yeni cihaz takma adini gir:",
            initialvalue=current_name,
            parent=window,
        )
        if new_name is None:
            return
        result = hub.rename_device(device_id, new_name.strip())
        if result.get("ok"):
            selection_var.set(f"Ad guncellendi: {result['device']['display_name']}")
            _set_status("Cihaz adi guncellendi.")
        else:
            _set_status(f"Ad guncellenemedi: {result.get('error', 'bilinmiyor')}")

    def _build_card(parent, device: dict[str, Any], row: int) -> None:
        online = bool(device.get("online"))
        accent = _pal("neon", "#3B82F6") if online else "#5C6475"
        card = ctk.CTkFrame(
            parent,
            fg_color=_pal("sidebar", "#10182A"),
            corner_radius=6,
            border_width=1,
            border_color=accent if online else _pal("entry_border", "#2B3550"),
        )
        card.grid(row=row, column=0, sticky="ew", padx=10, pady=8)
        card.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 4))
        top.grid_columnconfigure(0, weight=1)

        name = device.get("display_name") or device.get("device_name") or device.get("model") or "Android"
        title_line = f"{name}   {'ONLINE' if online else 'OFFLINE'}"
        ctk.CTkLabel(
            top,
            text=title_line,
            text_color=_pal("text_main", "#F5F7FF"),
            font=("Segoe UI Semibold", 14),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        id_label = ctk.CTkLabel(
            top,
            text=f"ID: {device.get('device_id', '')}",
            text_color=_pal("text_dim", "#9FA9C1"),
            font=("Segoe UI", 10),
            anchor="w",
        )
        id_label.grid(row=1, column=0, sticky="w", pady=(2, 0))

        status_chip = ctk.CTkLabel(
            top,
            text=device.get("status", "OFFLINE"),
            text_color=_pal("bg", "#0B1020"),
            fg_color=accent,
            corner_radius=999,
            font=("Segoe UI Semibold", 10),
            padx=10,
            pady=2,
        )
        status_chip.grid(row=0, column=1, rowspan=2, sticky="e", padx=(12, 0))

        lines = [
            f"{device.get('manufacturer', '')} {device.get('model', '')}".strip(),
            f"Android: {device.get('android_version', 'Bilinmiyor')} | SDK: {device.get('sdk_int', '?')}",
            f"Battery: {device.get('battery_text', 'Bilinmiyor')} | Network: {device.get('network_type', 'unknown')} | Screen: {device.get('screen', 'unknown')}",
            f"Root: {'Evet' if device.get('root') else 'Hayir'} | Volume: {device.get('volume', 'Bilinmiyor')} | Last seen: {device.get('last_seen_text', 'bilinmiyor')}",
        ]
        media = device.get("media_text") or "Yok"
        lines.append(f"Media: {media}")
        body = ctk.CTkLabel(
            card,
            text="\n".join(line for line in lines if line.strip()),
            text_color=_pal("text_dim", "#9FA9C1"),
            font=("Segoe UI", 10),
            anchor="w",
            justify="left",
        )
        body.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))

        capabilities = device.get("capabilities") or {}
        capability_text = ", ".join([key for key, value in capabilities.items() if _safe_bool(value, False)])
        if capability_text:
            caps = ctk.CTkLabel(
                card,
                text=f"Capabilities: {capability_text}",
                text_color=_pal("text_dim", "#9FA9C1"),
                font=("Segoe UI", 9),
                anchor="w",
            )
            caps.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 8))

        button_row = ctk.CTkFrame(card, fg_color="transparent")
        button_row.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 12))
        for index in range(6):
            button_row.grid_columnconfigure(index, weight=1, uniform=f"b{row}")

        def _device_button(text: str, command, column: int, enabled: bool = True):
            btn = ctk.CTkButton(
                button_row,
                text=text,
                height=30,
                command=command,
                state="normal" if enabled else "disabled",
            )
            btn.grid(row=0, column=column, sticky="ew", padx=3)
            return btn

        _device_button("Ad Degistir", lambda did=device.get("device_id"), current=name: _rename_device(did, current), 0, enabled=online)
        _device_button("Copy ID", lambda did=device.get("device_id"): _clipboard_copy(did), 1, enabled=True)
        _device_button("Play/Pause", lambda did=device.get("device_id"): _send_command(did, "media_play_pause"), 2, enabled=online)
        _device_button("Next", lambda did=device.get("device_id"): _send_command(did, "media_next"), 3, enabled=online)
        _device_button("Prev", lambda did=device.get("device_id"): _send_command(did, "media_previous"), 4, enabled=online)
        _device_button("Stop", lambda did=device.get("device_id"): _send_command(did, "media_stop"), 5, enabled=online)

    def _refresh_ui(schedule_next: bool = True) -> None:
        nonlocal auto_pair_attempted
        try:
            if not window.winfo_exists():
                return
        except Exception:
            return
        snap = hub.snapshot()
        endpoint_text = " | ".join(snap.get("endpoints") or [])
        endpoint_var.set(f"Server: {endpoint_text}")
        pairing = snap.get("pairing_code", "")
        pairing_var.set(pairing)
        count_var.set(f"{snap.get('online_count', 0)}/{snap.get('device_count', 0)} cihaz online")
        if hub_status_override:
            status_var.set(hub_status_override)
        else:
            status_var.set(f"Server {'calisiyor' if snap.get('running') else 'durdu'} | PC: {snap.get('pc_name', '')}")
        selection_var.set(f"{snap.get('device_count', 0)} cihaz listelendi.")
        for child in scroll.winfo_children():
            child.destroy()
        devices = snap.get("devices") or []
        if not devices:
            empty = ctk.CTkLabel(
                scroll,
                text="Henüz taninan cihaz yok. USB hata ayiklamayi ac, telefonu bagla ve + Cihaz Ekle'ye bas.",
                text_color=_pal("text_dim", "#9FA9C1"),
                font=("Segoe UI", 12),
                anchor="center",
            )
            empty.grid(row=0, column=0, sticky="ew", padx=20, pady=30)
        else:
            for index, device in enumerate(devices):
                _build_card(scroll, device, index)
        if schedule_next:
            window.after(1000, _refresh_ui)

    def _set_hub_status(message: str) -> None:
        nonlocal hub_status_override
        hub_status_override = message
        status_var.set(message)

    def _start_hub_async(manual: bool = False) -> None:
        """Start the LAN service without ever blocking the Tk event loop."""
        if hub.is_running():
            _set_hub_status("Cihazlar çalışıyor.")
            _refresh_ui(schedule_next=False)
            return

        _set_hub_status("Cihazlar bağlantı servisi başlatılıyor...")

        def worker() -> None:
            # USB reverse reaches the PC through loopback; the firewall still
            # limits unsolicited LAN access to the configured local subnet.
            result = hub.start(host="0.0.0.0", port=hub.port)

            def apply_result() -> None:
                try:
                    if not window.winfo_exists():
                        return
                except Exception:
                    return
                if result.get("ok") or result.get("running"):
                    _set_hub_status("Cihazlar çalışıyor. Telefonu QR veya eşleştirme kodu ile bağlayabilirsin.")
                else:
                    error = _safe_text(result.get("error"), "bilinmeyen hata")
                    _set_hub_status(f"Cihaz penceresi hazir, ag servisi acilamadi: {error}")
                _refresh_ui(schedule_next=False)

            try:
                window.after(0, apply_result)
            except Exception:
                pass

        threading.Thread(target=worker, name="NetOpsDeviceHubStarter", daemon=True).start()

    def _on_close() -> None:
        global _DEVICE_HUB_WINDOW
        try:
            _DEVICE_HUB_WINDOW = None
            window.destroy()
        except Exception:
            pass

    window.protocol("WM_DELETE_WINDOW", _on_close)
    def _apply_fluent_theme() -> None:
        try:
            from temalar import _tum_widgetlari_guncelle
            _tum_widgetlari_guncelle(window, "dark")
        except Exception:
            # The device window remains usable even if the optional theme
            # refresh is unavailable during a lazy import.
            pass

    window.after_idle(_apply_fluent_theme)
    _refresh_ui()
    _start_hub_async()
    return window


def neto_device_hub_ac_safe(parent=None, T=None, palette=None, say_callback=None):
    try:
        return open_device_hub_window(parent=parent, T=T, palette=palette, say_callback=say_callback)
    except Exception as exc:
        _write_log(f"open error: {exc}")
        return None
