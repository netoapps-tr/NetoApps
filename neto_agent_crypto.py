from __future__ import annotations

import base64
import ctypes
import getpass
import json
import os
import subprocess
import tempfile
import threading
from ctypes import wintypes
from pathlib import Path
from typing import Any

CRYPTPROTECT_UI_FORBIDDEN = 0x01
_ENTROPY = b"NetoAgent.LocalVault.v10.35"

_ACL_RESULTS: dict[str, bool] = {}
_ACL_LOCK = threading.Lock()


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _require_windows() -> None:
    if os.name != "nt":
        raise OSError("NetOps Agent kasası yalnızca Windows DPAPI üzerinde çalışır.")


def _blob(data: bytes) -> tuple[_DataBlob, Any]:
    if not data:
        return _DataBlob(0, None), None
    buffer = ctypes.create_string_buffer(data, len(data))
    return _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


def protect_bytes(data: bytes, description: str = "NetOps Agent Local Vault") -> bytes:
    """Encrypt bytes with Windows DPAPI for the current Windows user."""
    _require_windows()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    in_blob, in_buffer = _blob(data)
    entropy_blob, entropy_buffer = _blob(_ENTROPY)
    out_blob = _DataBlob()

    ok = crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        description,
        ctypes.byref(entropy_blob),
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob),
    )
    _ = (in_buffer, entropy_buffer)
    if not ok:
        raise ctypes.WinError()

    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        if out_blob.pbData:
            kernel32.LocalFree(out_blob.pbData)


def unprotect_bytes(data: bytes) -> bytes:
    """Decrypt bytes protected by protect_bytes for the same Windows user."""
    _require_windows()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    in_blob, in_buffer = _blob(data)
    entropy_blob, entropy_buffer = _blob(_ENTROPY)
    out_blob = _DataBlob()
    description = wintypes.LPWSTR()

    ok = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        ctypes.byref(description),
        ctypes.byref(entropy_blob),
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob),
    )
    _ = (in_buffer, entropy_buffer)
    if not ok:
        raise ctypes.WinError()

    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        if out_blob.pbData:
            kernel32.LocalFree(out_blob.pbData)
        if description:
            kernel32.LocalFree(description)


def protect_json(value: Any) -> bytes:
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return protect_bytes(raw)


def unprotect_json(data: bytes) -> Any:
    return json.loads(unprotect_bytes(data).decode("utf-8"))


def app_data_root() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "NetoAssistant" / "agent"
    return Path.home() / "AppData" / "Local" / "NetoAssistant" / "agent"


def vault_root() -> Path:
    path = app_data_root() / "vault"
    path.mkdir(parents=True, exist_ok=True)
    restrict_folder_to_current_user(path)
    return path


def runtime_root() -> Path:
    path = app_data_root() / "runtime"
    path.mkdir(parents=True, exist_ok=True)
    restrict_folder_to_current_user(path)
    return path


def config_path() -> Path:
    path = app_data_root()
    path.mkdir(parents=True, exist_ok=True)
    return path / "agent_config.json"


def restrict_folder_to_current_user(path: Path) -> bool:
    """Best-effort NTFS ACL, attempted at most once per folder per process.

    Older builds launched whoami plus four icacls processes for every encrypted
    status write. A single stalled icacls process could therefore leave a task
    active forever after its visible work had already finished. Results are now
    cached and every child process has a strict timeout. DPAPI remains the actual
    confidentiality boundary.
    """
    if os.name != "nt":
        return False

    try:
        key = os.path.normcase(str(Path(path).resolve()))
    except Exception:
        key = os.path.normcase(str(path))

    with _ACL_LOCK:
        if key in _ACL_RESULTS:
            return _ACL_RESULTS[key]
        # Reserve the key immediately so concurrent status writes do not launch
        # duplicate ACL subprocesses. Failure remains best-effort.
        _ACL_RESULTS[key] = False

    success = True
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            identity = subprocess.run(
                ["whoami"],
                capture_output=True,
                text=True,
                check=False,
                timeout=1.0,
                creationflags=flags,
            ).stdout.strip()
        except (subprocess.TimeoutExpired, OSError):
            identity = ""

        if not identity:
            identity = getpass.getuser()

        commands = [
            ["icacls", str(path), "/inheritance:r"],
            ["icacls", str(path), "/grant:r", f"{identity}:(OI)(CI)F"],
            ["icacls", str(path), "/remove:g", "Users"],
            ["icacls", str(path), "/remove:g", "Everyone"],
        ]
        for command in commands:
            try:
                completed = subprocess.run(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    timeout=1.25,
                    creationflags=flags,
                )
                success = success and completed.returncode in (0, 1)
            except (subprocess.TimeoutExpired, OSError):
                success = False
    except Exception:
        success = False

    with _ACL_LOCK:
        _ACL_RESULTS[key] = bool(success)
    return bool(success)


def write_encrypted_json(path: Path, value: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    restrict_folder_to_current_user(path.parent)
    payload = protect_json(value)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def read_encrypted_json(path: Path) -> Any:
    return unprotect_json(Path(path).read_bytes())


def write_live_status_json(path: Path, value: Any) -> None:
    """Atomically publish non-sensitive worker progress without DPAPI/ACL waits.

    Live status contains only step names, generic UI messages and booleans. Task
    content remains in the encrypted request/vault. This channel is deliberately
    independent from Windows DPAPI and icacls so an already typed/sent action can
    never be blocked by the audit/storage layer.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


def read_live_status_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def secure_delete(path: Path) -> None:
    """Best-effort plaintext cleanup.

    SSD wear levelling means overwrite cannot be promised as forensic erasure;
    therefore NetOps Agent avoids writing plaintext task/session content at all.
    """
    path = Path(path)
    try:
        if path.is_file():
            size = path.stat().st_size
            if size > 0:
                with path.open("r+b", buffering=0) as handle:
                    remaining = size
                    zero = b"\x00" * min(1024 * 1024, max(1, size))
                    while remaining > 0:
                        block = zero[: min(len(zero), remaining)]
                        handle.write(block)
                        remaining -= len(block)
                    handle.flush()
                    os.fsync(handle.fileno())
            path.unlink(missing_ok=True)
    except Exception:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass


def make_runtime_file(session_id: str, suffix: str) -> Path:
    safe = "".join(ch for ch in str(session_id) if ch.isalnum() or ch in "-_")[:80]
    return runtime_root() / f"{safe}.{suffix}"


def write_vault_record(session_id: str, value: Any) -> Path:
    safe = "".join(ch for ch in str(session_id) if ch.isalnum() or ch in "-_")[:80]
    path = vault_root() / f"{safe}.netovault"
    write_encrypted_json(path, value)
    return path


def encode_for_debug(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")
