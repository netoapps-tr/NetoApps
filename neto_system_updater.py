"""Manifest-based NetOps system-file updater.

The updater downloads only files listed in the signed-by-digest manifest. It
never treats a full EXE or a repository archive as the normal update payload.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
import threading
import urllib.parse
import urllib.request
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, Callable

REPOSITORY = "netoapps-tr/NetoApps"
DEFAULT_MANIFEST_URL = (
    f"https://raw.githubusercontent.com/{REPOSITORY}/main/netops_system_manifest.json"
)
NETWORK_TIMEOUT = 18
_CACHE: dict[str, Any] = {"url": "", "manifest": None}
_CACHE_LOCK = threading.RLock()
_ROLLBACK_CODE = "-".join(("nops", "restore", "141"))


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _app_data_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "NetOps"
    return Path.home() / ".neto_assistant"


def _can_write(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".netops-system-{os.getpid()}-{uuid.uuid4().hex}"
        probe.write_bytes(b"ok")
        probe.unlink(missing_ok=True)
        return True
    except (OSError, ValueError):
        return False


def update_root() -> Path:
    candidates = [
        _app_data_dir() / "system_updates",
        Path.home() / ".neto_assistant" / "system_updates",
    ]
    try:
        candidates.append(Path(tempfile.gettempdir()) / "NetOps" / "system_updates")
    except (OSError, ValueError):
        pass
    for candidate in candidates:
        if _can_write(candidate):
            return candidate
    raise RuntimeError("Sistem guncellemesi icin yazilabilir klasor olusturulamadi.")


def _version_tuple(value: Any) -> tuple[int, ...]:
    match = re.search(r"(?<!\d)(\d+(?:\.\d+){0,5})(?!\d)", str(value or ""))
    if not match:
        return (0, 0, 0, 0, 0, 0)
    parts = tuple(int(piece) for piece in match.group(1).split("."))
    return parts + (0,) * (6 - len(parts))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_digest(value: Any) -> str:
    text = str(value or "").strip().lower()
    if ":" in text:
        prefix, text = text.split(":", 1)
        if prefix.strip() != "sha256":
            return ""
    return text if re.fullmatch(r"[0-9a-f]{64}", text) else ""


def _safe_relative_path(value: Any) -> str:
    raw = str(value or "").replace("\\", "/").strip()
    path = PurePosixPath(raw)
    if not raw or raw.startswith("/") or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"Gecersiz sistem dosyasi yolu: {raw}")
    if Path(raw).suffix.lower() in {".exe", ".dll", ".sys", ".bat", ".cmd", ".ps1", ".vbs", ".pyd"}:
        raise ValueError(f"Calistirilabilir sistem dosyasi guncellenemez: {raw}")
    return "/".join(path.parts)


def _github_url(value: Any) -> str:
    url = str(value or "").strip()
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    allowed = host in {"raw.githubusercontent.com", "github.com"} or host.endswith(".githubusercontent.com")
    if parsed.scheme != "https" or not allowed:
        raise ValueError("Sistem manifest URL'si HTTPS GitHub adresi olmali.")
    return url


def validate_manifest(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Sistem manifesti JSON nesnesi degil.")
    raw_files = payload.get("files")
    if not isinstance(raw_files, list) or not raw_files:
        raise ValueError("Sistem manifestinde files alani eksik.")
    files: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_files:
        if not isinstance(raw, dict):
            raise ValueError("Sistem manifestinde gecersiz dosya kaydi var.")
        relative_path = _safe_relative_path(raw.get("path") or raw.get("relative_path"))
        if relative_path in seen:
            raise ValueError(f"Sistem manifestinde yinelenen dosya: {relative_path}")
        seen.add(relative_path)
        url = _github_url(raw.get("url") or raw.get("download_url"))
        digest = _normalize_digest(raw.get("sha256") or raw.get("digest"))
        if not digest:
            raise ValueError(f"{relative_path} icin SHA-256 eksik veya gecersiz.")
        files.append({**raw, "path": relative_path, "url": url, "sha256": digest})
    return {
        "manifest_version": str(payload.get("manifest_version") or "1"),
        "version": str(payload.get("version") or payload.get("app_version") or "0.0.0"),
        "release_tag": str(payload.get("release_tag") or payload.get("release") or ""),
        "files": files,
    }


def fetch_manifest(url: str | None = None, force: bool = False) -> dict[str, Any]:
    manifest_url = str(url or os.environ.get("NETO_SYSTEM_MANIFEST_URL") or DEFAULT_MANIFEST_URL).strip()
    _github_url(manifest_url)
    with _CACHE_LOCK:
        if not force and _CACHE.get("url") == manifest_url and isinstance(_CACHE.get("manifest"), dict):
            return dict(_CACHE["manifest"])
    request = urllib.request.Request(
        manifest_url,
        headers={"User-Agent": "NetOps-System-Updater/1.0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT) as response:
        manifest = validate_manifest(json.loads(response.read().decode("utf-8", "replace")))
    with _CACHE_LOCK:
        _CACHE["url"] = manifest_url
        _CACHE["manifest"] = dict(manifest)
    return manifest


def _current_version() -> str:
    try:
        from neto_version import get_app_version
        return str(get_app_version() or "0.0.0")
    except Exception:
        return "0.0.0"


def check_for_updates(force: bool = False, manifest_url: str | None = None) -> dict[str, Any]:
    current_version = _current_version()
    try:
        manifest = fetch_manifest(manifest_url, force=force)
        changed: list[dict[str, Any]] = []
        for item in manifest["files"]:
            local = project_root() / Path(item["path"])
            if not local.is_file() or _sha256(local) != item["sha256"]:
                changed.append({**item, "current_path": str(local), "available": True})
        version_available = _version_tuple(manifest["version"]) > _version_tuple(current_version)
        available = bool(changed) and (version_available or bool(changed))
        return {
            "ok": True,
            "manifest_ok": True,
            "update_mode": "system_files",
            "available": available,
            "update_available": available,
            "is_available": available,
            "current_version": current_version,
            "latest_version": manifest["version"],
            "tag_name": manifest["release_tag"],
            "system_files": changed,
            "file_count": len(changed),
            "verified": True,
            "download_url": "",
            "asset_digest": "",
            "body": str(manifest.get("notes") or ""),
            "message": (
                f"{len(changed)} sistem dosyasi icin guncelleme hazir."
                if available else "Sistem dosyalari guncel."
            ),
            "error": "",
        }
    except Exception as exc:
        return {
            "ok": False,
            "manifest_ok": False,
            "update_mode": "system_files",
            "available": False,
            "update_available": False,
            "is_available": False,
            "current_version": current_version,
            "latest_version": current_version,
            "tag_name": "",
            "system_files": [],
            "file_count": 0,
            "verified": False,
            "download_url": "",
            "asset_digest": "",
            "body": "",
            "message": f"Sistem manifesti kontrol edilemedi: {exc}",
            "error": str(exc),
        }


def download_files(
    update: dict[str, Any],
    progress_callback: Callable[..., Any] | None = None,
) -> str:
    files = update.get("system_files") if isinstance(update, dict) else None
    if not isinstance(files, list) or not files:
        raise RuntimeError("Indirilecek degisen sistem dosyasi yok.")
    job = update_root() / f"system-job-{os.getpid()}-{uuid.uuid4().hex}"
    payload = job / "payload"
    payload.mkdir(parents=True, exist_ok=False)
    downloaded: list[dict[str, Any]] = []
    try:
        total_files = len(files)
        for index, item in enumerate(files, start=1):
            relative_path = _safe_relative_path(item.get("path"))
            destination = payload / Path(relative_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.part")
            request = urllib.request.Request(
                str(item["url"]),
                headers={"User-Agent": "NetOps-System-Updater/1.0", "Accept": "application/octet-stream"},
            )
            digest = hashlib.sha256()
            try:
                with urllib.request.urlopen(request, timeout=90) as response, temporary.open("wb") as output:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)
                        digest.update(chunk)
                    output.flush()
                    os.fsync(output.fileno())
                if digest.hexdigest() != item["sha256"]:
                    raise RuntimeError(f"{relative_path} SHA-256 dogrulamasini gecemedi.")
                os.replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)
            downloaded.append({"path": relative_path, "staged_path": str(destination)})
            if callable(progress_callback):
                try:
                    progress_callback(index, total_files)
                except TypeError:
                    progress_callback(index / total_files)
        plan = {
            "update_mode": "system_files",
            "root": str(project_root()),
            "job": str(job),
            "release_tag": str(update.get("tag_name") or ""),
            "version": str(update.get("latest_version") or ""),
            "files": downloaded,
        }
        plan_path = job / "plan.json"
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return str(plan_path)
    except Exception:
        import shutil
        shutil.rmtree(job, ignore_errors=True)
        raise


def install_downloaded(plan_path: str, restart: bool = True) -> dict[str, Any]:
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    if plan.get("update_mode") != "system_files":
        raise ValueError("Sistem guncelleme plani gecersiz.")
    from neto_update_helper import install_file_update
    return install_file_update(plan, restart=restart, plan_path=plan_path)


def latest_rollback() -> dict[str, Any] | None:
    history_root = update_root() / "rollback"
    if not history_root.is_dir():
        return None
    candidates: list[dict[str, Any]] = []
    for history in history_root.iterdir():
        if not history.is_dir():
            continue
        metadata_path = history / "rollback.json"
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(metadata, dict) or not isinstance(metadata.get("files"), list):
            continue
        metadata["history_dir"] = str(history.resolve())
        metadata["created_at"] = int(metadata.get("created_at") or history.stat().st_mtime)
        candidates.append(metadata)
    return max(candidates, key=lambda item: int(item.get("created_at") or 0)) if candidates else None


def hidden_rollback_command(text: Any) -> dict[str, Any] | None:
    """Handle the private rollback phrase without adding a visible UI button."""
    normalized = " ".join(str(text or "").casefold().split())
    if normalized != _ROLLBACK_CODE:
        return None
    record = latest_rollback()
    if record is None:
        return {"ok": False, "message": "Geri alinacak guvenli bir onceki sistem kaydi yok."}
    try:
        from neto_update_helper import install_rollback_update

        result = install_rollback_update(record, restart=True)
        result["message"] = "Onceki sistem dosyalari hazirlandi. NetOps yeniden baslatiliyor."
        return result
    except Exception as exc:
        return {"ok": False, "message": f"Geri alma baslatilamadi: {exc}"}

