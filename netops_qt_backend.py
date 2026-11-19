"""Service boundary for the native PySide6 NetOps shell."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from collections.abc import Callable, Mapping
import subprocess
from typing import Any


def _plain(value: Any) -> Any:
    if is_dataclass(value):
        return _plain(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _read_devices() -> dict[str, Any]:
    from neto_device_hub import device_hub_snapshot

    return _plain(device_hub_snapshot())


def _read_media() -> Any:
    from neto_now_playing import get_current_media

    return _plain(get_current_media(force_fresh=True) or {})


def _read_automations() -> list[Any]:
    from neto_automation_core import list_automations

    return _plain(list_automations())


def _read_gpu_usage() -> str:
    """Read NVIDIA GPU utilization without making GPU support mandatory."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=0.8,
            check=False,
        )
        for line in str(result.stdout or "").splitlines():
            value = line.strip().replace(",", ".")
            if value:
                return f"{float(value):.0f}%"
    except (FileNotFoundError, OSError, ValueError, subprocess.SubprocessError):
        pass
    return "Bilinmiyor"


def _read_chat(text: str) -> Any:
    from neto_ai import neto_ai_cevap_ver

    return _plain(neto_ai_cevap_ver(text))


def _deny_media_action(_action: str) -> dict[str, Any]:
    return {"ok": False, "error": "Medya kontrol callback'i bağlı değil."}


def _deny_remote(_text: str) -> dict[str, Any]:
    return {"ok": False, "error": "Remote callback'i bağlı değil."}


def _deny_speech(_text: str) -> dict[str, Any]:
    return {"ok": False, "error": "Yerel ses motoru bağlı değil."}


def _empty_notifications() -> list[Any]:
    return []


def _empty_settings() -> dict[str, Any]:
    return {}


def _deny_settings(_data: Mapping[str, Any]) -> dict[str, Any]:
    return {"ok": False, "error": "Ayar kaydetme callback'i bağlı değil."}


def _read_system() -> dict[str, Any]:
    try:
        import psutil

        cpu = round(float(psutil.cpu_percent(interval=None)))
        ram = round(float(psutil.virtual_memory().percent))
    except Exception:
        cpu, ram = "Bilinmiyor", "Bilinmiyor"

    gpu = _read_gpu_usage()

    try:
        devices = _read_devices()
    except Exception:
        devices = {}
    return {
        "cpu": cpu,
        "ram": ram,
        "gpu": gpu,
        "devices": devices.get("online_count", devices.get("device_count", 0)),
        "remote": "Çalışıyor" if devices.get("running") else "Hazır",
    }


def _deny(_value: str) -> dict[str, Any]:
    return {"ok": False, "error": "İşlem callback'i bağlı değil."}


@dataclass
class QtBackend:
    system_snapshot: Callable[[], Mapping[str, Any]]
    devices: Callable[[], Any]
    now_playing: Callable[[], Any]
    automations: Callable[[], Any]
    chat: Callable[[str], Any]
    command: Callable[[str], Any]
    media_control: Callable[[str], Any]
    settings: Callable[[], Any]
    save_settings: Callable[[Mapping[str, Any]], Any]
    remote: Callable[[str], Any] = _deny_remote
    speech: Callable[[str], Any] = _deny_speech
    notifications: Callable[[], Any] = _empty_notifications

    def snapshot(self) -> dict[str, Any]:
        try:
            value = self.system_snapshot()
        except Exception as exc:
            return {"error": str(exc)}
        return dict(_plain(value)) if isinstance(value, Mapping) else {}

    def run(self, key: str, *args: Any) -> Any:
        callback = getattr(self, key, None)
        if not callable(callback):
            return {"ok": False, "error": "İşlem callback'i bağlı değil."}
        try:
            return _plain(callback(*args))
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


def build_qt_backend(
    *,
    system_reader: Callable[[], Mapping[str, Any]] | None = None,
    device_reader: Callable[[], Any] | None = None,
    media_reader: Callable[[], Any] | None = None,
    automation_reader: Callable[[], Any] | None = None,
    chat_reader: Callable[[str], Any] | None = None,
    command_runner: Callable[[str], Any] | None = None,
    media_control_runner: Callable[[str], Any] | None = None,
    settings_reader: Callable[[], Any] | None = None,
    settings_writer: Callable[[Mapping[str, Any]], Any] | None = None,
    remote_reader: Callable[[str], Any] | None = None,
    speech_runner: Callable[[str], Any] | None = None,
    notifications_reader: Callable[[], Any] | None = None,
) -> QtBackend:
    return QtBackend(
        system_snapshot=system_reader or _read_system,
        devices=device_reader or _read_devices,
        now_playing=media_reader or _read_media,
        automations=automation_reader or _read_automations,
        chat=chat_reader or _read_chat,
        command=command_runner or _deny,
        media_control=media_control_runner or _deny_media_action,
        settings=settings_reader or _empty_settings,
        save_settings=settings_writer or _deny_settings,
        remote=remote_reader or _deny_remote,
        speech=speech_runner or _deny_speech,
        notifications=notifications_reader or _empty_notifications,
    )


__all__ = ["QtBackend", "build_qt_backend"]
