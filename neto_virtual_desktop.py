"""Safe, local QEMU virtual desktop control for NetOps v1.50.

The manager deliberately owns only the child process it starts. It never
uses a shell, never accepts arbitrary QEMU arguments, and defaults to a
snapshot so a guest cannot unexpectedly modify its base disk.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import threading
import unicodedata
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable


MIN_MEMORY_MB = 512
MAX_MEMORY_MB = 4096
MIN_CPUS = 1
MAX_CPUS = 4
MIN_DISK_IMAGE_BYTES = 1024 * 1024
SYSTEM_DISK_IMAGE = Path(r"C:\NetOpsVM\netops-os.qcow2")
SYSTEM_BOOT_DISK_IMAGE = Path(r"C:\NetOpsVM\netops-os-boot.vhdx")


@dataclass(frozen=True)
class VirtualDesktopConfig:
    project_root: Path
    qemu_path: Path | None = None
    disk_image: Path | None = None
    memory_mb: int = 1024
    cpus: int = 2
    use_whpx: bool = True
    snapshot: bool = True
    display: str = "sdl"
    name: str = "NetOps Virtual Desktop"

    def normalized(self) -> "VirtualDesktopConfig":
        memory = max(MIN_MEMORY_MB, min(MAX_MEMORY_MB, int(self.memory_mb)))
        cpus = max(MIN_CPUS, min(MAX_CPUS, int(self.cpus)))
        display = self.display if self.display in {"sdl", "gtk", "none"} else "sdl"
        return replace(self, memory_mb=memory, cpus=cpus, display=display)


def _existing_file(value: str | Path | None) -> Path | None:
    if not value:
        return None
    path = Path(value).expanduser()
    return path if path.is_file() else None


def _usable_disk_image(value: str | Path | None) -> Path | None:
    path = _existing_file(value)
    if path is None:
        return None
    try:
        if path.stat().st_size < MIN_DISK_IMAGE_BYTES:
            return None
    except OSError:
        return None
    return path


def find_qemu(project_root: Path) -> Path | None:
    """Resolve QEMU from explicit config, the project bundle, or PATH."""
    configured = _existing_file(os.environ.get("NETOPS_QEMU"))
    if configured:
        return configured

    root = Path(project_root).resolve()
    for candidate in (
        root / "runtime" / "qemu" / "qemu-system-x86_64.exe",
        root / "qemu" / "qemu-system-x86_64.exe",
        root / "tools" / "qemu" / "qemu-system-x86_64.exe",
    ):
        if candidate.is_file():
            return candidate

    command = shutil.which("qemu-system-x86_64")
    if command:
        return Path(command)
    for candidate in (
        Path(r"C:\Program Files\qemu\qemu-system-x86_64.exe"),
        Path(r"C:\Program Files\QEMU\qemu-system-x86_64.exe"),
    ):
        if candidate.is_file():
            return candidate
    return None


def find_disk_image(project_root: Path) -> Path | None:
    """Resolve only known NetOps guest image locations."""
    configured = _usable_disk_image(os.environ.get("NETOPS_VM_DISK"))
    if configured:
        return configured

    root = Path(project_root).resolve()
    for candidate in (
        SYSTEM_DISK_IMAGE,
        SYSTEM_BOOT_DISK_IMAGE,
        root / "netops_os" / "artifacts" / "netops-os.qcow2",
        root / "netops_os" / "artifacts" / "netops-os-boot.vhdx",
    ):
        usable = _usable_disk_image(candidate)
        if usable:
            return usable
    return None


def _short_windows_path(path: Path) -> str:
    """Return an ASCII 8.3 path when Windows provides one for QEMU."""
    resolved = str(Path(path).resolve())
    if os.name != "nt":
        return resolved
    try:
        import ctypes

        get_short_path = ctypes.windll.kernel32.GetShortPathNameW
        get_short_path.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
        get_short_path.restype = ctypes.c_uint32
        buffer = ctypes.create_unicode_buffer(32768)
        length = get_short_path(resolved, buffer, len(buffer))
        if length:
            return str(buffer.value)
    except Exception:
        pass
    return resolved


def build_qemu_command(
    config: VirtualDesktopConfig,
    qemu_path: Path,
    disk_path: Path,
) -> list[str]:
    """Build a fixed-shape QEMU argv list; callers must use shell=False."""
    config = config.normalized()
    disk_format = "vhdx" if disk_path.suffix.casefold() == ".vhdx" else "qcow2"
    accel = "whpx,kernel-irqchip=off" if config.use_whpx else "tcg"
    command = [
        str(qemu_path),
        "-name",
        config.name,
        "-machine",
        "q35",
        "-accel",
        accel,
        "-m",
        str(config.memory_mb),
        "-smp",
        str(config.cpus),
        "-display",
        config.display,
        "-drive",
        f"file={_short_windows_path(disk_path)},format={disk_format},if=virtio",
        "-nic",
        "user,model=virtio",
        "-no-reboot",
    ]
    if config.snapshot:
        command.append("-snapshot")
    return command


def _normalize_command(text: str) -> str:
    value = str(text or "").casefold().strip()
    value = value.translate(str.maketrans({"ı": "i", "ğ": "g", "ü": "u", "ş": "s", "ö": "o", "ç": "c"}))
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(character)
    )


def handle_command(text: str, *, manager: Any | None = None) -> dict[str, Any] | None:
    """Route only explicit virtual-desktop phrases; return None otherwise."""
    normalized = _normalize_command(text)
    if not normalized:
        return None
    manager = manager or get_manager()

    if "sanal masaustu" not in normalized:
        return None
    if "yeniden baslat" in normalized or "restart" in normalized:
        return manager.restart()
    if any(phrase in normalized for phrase in ("durumu", "durum", "calisiyor mu")):
        return manager.status()
    if any(phrase in normalized for phrase in ("durdur", "kapat")):
        return manager.stop()
    if any(phrase in normalized for phrase in ("baslat", "ac")):
        return manager.start()
    return None


def format_result(result: dict[str, Any]) -> str:
    message = str(result.get("message") or "Sanal masaustu durumu alinamadi.")
    return message


class VirtualDesktopManager:
    def __init__(
        self,
        config: VirtualDesktopConfig,
        *,
        qemu_path: Path | None = None,
        disk_path: Path | None = None,
        popen: Callable[..., Any] | None = None,
    ) -> None:
        self.config = config.normalized()
        self.qemu_path = qemu_path
        self.disk_path = disk_path
        self._popen = popen or subprocess.Popen
        self._process: Any | None = None
        self._log_handle: Any | None = None
        self._lock = threading.RLock()

    def _resolve_dependencies(self) -> tuple[Path | None, Path | None]:
        qemu = self.qemu_path or find_qemu(self.config.project_root)
        disk = self.disk_path or find_disk_image(self.config.project_root)
        return _existing_file(qemu), _existing_file(disk)

    def _result(self, ok: bool, state: str, message: str, **extra: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ok": bool(ok),
            "state": state,
            "message": message,
            "pid": getattr(self._process, "pid", None),
        }
        payload.update(extra)
        return payload

    def _reap_if_exited(self) -> None:
        if self._process is None:
            return
        try:
            exited = self._process.poll() is not None
        except Exception:
            exited = True
        if exited:
            self._process = None
            self._close_log()

    def _close_log(self) -> None:
        if self._log_handle is not None:
            try:
                self._log_handle.close()
            except Exception:
                pass
            self._log_handle = None

    def status(self) -> dict[str, Any]:
        with self._lock:
            self._reap_if_exited()
            if self._process is not None:
                return self._result(True, "running", "Sanal masaustu calisiyor.")
            qemu, disk = self._resolve_dependencies()
            if qemu is None or disk is None:
                missing = "QEMU" if qemu is None else "sanal disk"
                return self._result(False, "unavailable", f"{missing} bulunamadi; sanal masaustu hazir degil.")
            return self._result(True, "stopped", "Sanal masaustu duruyor.", qemu=str(qemu), disk=str(disk))

    def start(self) -> dict[str, Any]:
        with self._lock:
            self._reap_if_exited()
            if self._process is not None:
                return self._result(True, "running", "Sanal masaustu zaten calisiyor.")

            qemu, disk = self._resolve_dependencies()
            if qemu is None or disk is None:
                missing = "QEMU" if qemu is None else "sanal disk"
                return self._result(False, "unavailable", f"{missing} bulunamadi; NetOps kapanmadan devam ediyor.")

            command = build_qemu_command(self.config, qemu, disk)
            log_dir = self.config.project_root / "logs"
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
                self._log_handle = (log_dir / "netops-virtual-desktop.log").open("ab")
                creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                self._process = self._popen(
                    command,
                    cwd=str(self.config.project_root),
                    stdin=subprocess.DEVNULL,
                    stdout=self._log_handle,
                    stderr=subprocess.STDOUT,
                    creationflags=creationflags,
                    shell=False,
                )
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                self._process = None
                self._close_log()
                return self._result(False, "error", f"Sanal masaustu baslatilamadi: {exc}")
            return self._result(True, "running", "Sanal masaustu baslatildi.")

    def stop(self) -> dict[str, Any]:
        with self._lock:
            self._reap_if_exited()
            if self._process is None:
                self._close_log()
                return self._result(True, "stopped", "Sanal masaustu zaten kapali.")
            process = self._process
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    process.kill()
                    process.wait(timeout=2)
                except (OSError, subprocess.SubprocessError):
                    pass
            except (OSError, subprocess.SubprocessError):
                pass
            finally:
                self._process = None
                self._close_log()
            return self._result(True, "stopped", "Sanal masaustu durduruldu.")

    def restart(self) -> dict[str, Any]:
        stopped = self.stop()
        if not stopped.get("ok"):
            return stopped
        return self.start()


_MANAGER: VirtualDesktopManager | None = None
_MANAGER_LOCK = threading.Lock()


def get_manager(project_root: Path | None = None) -> VirtualDesktopManager:
    global _MANAGER
    with _MANAGER_LOCK:
        if _MANAGER is None:
            root = Path(project_root or Path(__file__).resolve().parent).resolve()
            _MANAGER = VirtualDesktopManager(VirtualDesktopConfig(project_root=root))
        return _MANAGER


def reset_manager_for_tests() -> None:
    global _MANAGER
    with _MANAGER_LOCK:
        if _MANAGER is not None:
            _MANAGER.stop()
        _MANAGER = None

