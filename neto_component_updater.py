"""Verified GitHub component updates for NetOps drivers.

Components are staged under LOCALAPPDATA and become active on the next
restart. The running Python process is never hot-reloaded.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Callable

COMPONENTS = {
    "visual_driver": "neto_visual_driver.py",
    "now_playing_driver": "neto_now_playing_driver.py",
}
DEFAULT_MANIFEST_URL = (
    "https://raw.githubusercontent.com/netoapps-tr/Neto-Asistan-download/main/"
    "netops_components.json"
)
NETWORK_TIMEOUT = 18
_CACHE: dict[str, Any] = {"url": "", "manifest": None}
_CACHE_LOCK = threading.RLock()
_CHECK_RUNNING = False


def _app_data_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "NetOps"
    return Path.home() / ".neto_assistant"


def component_root() -> Path:
    path = _app_data_dir() / "components"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _active_path() -> Path:
    return component_root() / "active.json"


def _normalize_digest(value: Any) -> str:
    text = str(value or "").strip().lower()
    if ":" in text:
        prefix, text = text.split(":", 1)
        if prefix.strip() != "sha256":
            return ""
    return text if re.fullmatch(r"[0-9a-f]{64}", text) else ""


def _version_tuple(value: Any) -> tuple[int, ...]:
    match = re.search(r"(?<!\d)(\d+(?:\.\d+){0,5})(?!\d)", str(value or ""))
    if not match:
        return (0, 0, 0, 0, 0, 0)
    parts = tuple(int(item) for item in match.group(1).split("."))
    return parts + (0,) * (6 - len(parts))


def version_is_newer(remote: Any, current: Any) -> bool:
    return _version_tuple(remote) > _version_tuple(current)


def _github_url(value: Any) -> str:
    url = str(value or "").strip()
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    allowed = (
        host in {"github.com", "raw.githubusercontent.com", "objects.githubusercontent.com"}
        or host.endswith(".githubusercontent.com")
    )
    if parsed.scheme != "https" or not host or not allowed:
        raise ValueError("Bileşen URL'si yalnızca HTTPS GitHub adresi olabilir.")
    return url


def _module_name(component: str, item: dict[str, Any]) -> str:
    expected = COMPONENTS.get(component)
    module = str(item.get("module") or expected or "").strip()
    if module != expected:
        raise ValueError(f"{component} için beklenmeyen modül adı.")
    return module


def validate_manifest(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Bileşen manifesti JSON nesnesi değil.")
    components = payload.get("components")
    if not isinstance(components, dict):
        raise ValueError("Bileşen manifestinde components alanı eksik.")
    normalized: dict[str, dict[str, Any]] = {}
    for component, raw in components.items():
        if component not in COMPONENTS or not isinstance(raw, dict):
            continue
        version = str(raw.get("version") or "").strip()
        if not version or _version_tuple(version) == (0, 0, 0, 0, 0, 0):
            raise ValueError(f"{component} sürümü geçersiz.")
        asset_url = _github_url(raw.get("asset_url") or raw.get("download_url"))
        digest = _normalize_digest(raw.get("sha256") or raw.get("digest"))
        if not digest:
            raise ValueError(f"{component} için SHA-256 eksik veya geçersiz.")
        normalized[component] = {
            **raw,
            "id": component,
            "version": version,
            "asset_url": asset_url,
            "sha256": digest,
            "module": _module_name(component, raw),
            "package": str(raw.get("package") or "zip").lower(),
        }
    if not normalized:
        raise ValueError("Manifestte desteklenen bileşen bulunamadı.")
    return {
        "manifest_version": str(payload.get("manifest_version") or "1"),
        "app_min_version": str(payload.get("app_min_version") or "0.0.0"),
        "components": normalized,
    }


def _http_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "NetOps-Component-Updater/1.0",
            "Accept": "application/json",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT) as response:
        return validate_manifest(json.loads(response.read().decode("utf-8", "replace")))


def fetch_manifest(url: str | None = None, force: bool = False) -> dict[str, Any]:
    manifest_url = str(
        url or os.environ.get("NETO_COMPONENT_MANIFEST_URL") or DEFAULT_MANIFEST_URL
    ).strip()
    _github_url(manifest_url)
    with _CACHE_LOCK:
        if not force and _CACHE.get("url") == manifest_url and isinstance(_CACHE.get("manifest"), dict):
            return dict(_CACHE["manifest"])
    manifest = _http_json(manifest_url)
    with _CACHE_LOCK:
        _CACHE["url"] = manifest_url
        _CACHE["manifest"] = dict(manifest)
    return manifest


def current_component_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for component, module_name in COMPONENTS.items():
        try:
            module = __import__(Path(module_name).stem, fromlist=["DRIVER_VERSION"])
            versions[component] = str(getattr(module, "DRIVER_VERSION", "0.0.0"))
        except Exception:
            versions[component] = "0.0.0"
    return versions


def check_for_updates(force: bool = False, manifest_url: str | None = None) -> dict[str, Any]:
    current = current_component_versions()
    try:
        manifest = fetch_manifest(manifest_url, force=force)
        updates = []
        for component, item in manifest["components"].items():
            installed = current.get(component, "0.0.0")
            if version_is_newer(item["version"], installed):
                updates.append({**item, "current_version": installed, "available": True})
        return {
            "ok": True,
            "available": bool(updates),
            "updates": updates,
            "current": current,
            "manifest_version": manifest["manifest_version"],
            "error": "",
        }
    except Exception as exc:
        return {
            "ok": False,
            "available": False,
            "updates": [],
            "current": current,
            "manifest_version": "",
            "error": str(exc),
        }


def _safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    destination = destination.resolve()
    for info in archive.infolist():
        raw = str(info.filename or "").replace("\\", "/")
        if not raw or raw.endswith("/"):
            continue
        parts = [part for part in raw.split("/") if part not in ("", ".")]
        if any(part == ".." for part in parts):
            raise RuntimeError(f"Güvensiz ZIP yolu engellendi: {raw}")
        if Path(raw).suffix.lower() in {".exe", ".dll", ".sys", ".bat", ".cmd", ".ps1", ".vbs"}:
            raise RuntimeError(f"Çalıştırılabilir bileşen dosyası engellendi: {raw}")
        target = destination.joinpath(*parts).resolve()
        try:
            target.relative_to(destination)
        except ValueError as exc:
            raise RuntimeError(f"ZIP yolu hedef dışına çıkıyor: {raw}") from exc
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(info, "r") as source, target.open("wb") as output:
            shutil.copyfileobj(source, output, length=1024 * 1024)


def _download(update: dict[str, Any]) -> Path:
    component = str(update["id"])
    filename = f"{component}-{update['version']}.zip"
    downloads = component_root() / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    target = downloads / filename
    temporary = target.with_suffix(".part")
    hasher = hashlib.sha256()
    request = urllib.request.Request(
        update["asset_url"], headers={"User-Agent": "NetOps-Component-Updater/1.0"}
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response, temporary.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                hasher.update(chunk)
        if hasher.hexdigest() != update["sha256"]:
            raise RuntimeError(f"{component} paketi SHA-256 doğrulamasını geçemedi.")
        os.replace(temporary, target)
        return target
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def _save_active(active: dict[str, Any]) -> None:
    path = _active_path()
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(active, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def active_components() -> dict[str, Any]:
    try:
        value = json.loads(_active_path().read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def installed_component_versions(component: str) -> list[dict[str, Any]]:
    """Return verified local versions, newest first, without importing them."""
    component = str(component or "").strip()
    if component not in COMPONENTS:
        raise ValueError("Desteklenmeyen NetOps bileşeni.")
    active = active_components().get(component, {})
    if not isinstance(active, dict):
        active = {}
    active_version = str(active.get("version") or "") if isinstance(active, dict) else ""
    base = component_root() / component
    records: list[dict[str, Any]] = []
    if not base.is_dir():
        return records
    expected_module = COMPONENTS[component]
    for path in base.iterdir():
        if not path.is_dir():
            continue
        metadata_path = path / "component.json"
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(metadata, dict) or str(metadata.get("module") or "") != expected_module:
            continue
        version = str(metadata.get("version") or "").strip()
        if not version or _version_tuple(version) == (0, 0, 0, 0, 0, 0):
            continue
        if not (path / expected_module).is_file():
            continue
        records.append({
            "id": component,
            "version": version,
            "path": str(path.resolve()),
            "module": expected_module,
            "active": version == active_version and str(path.resolve()) == str(active.get("path") or ""),
        })
    records.sort(key=lambda item: _version_tuple(item["version"]), reverse=True)
    return records


def rollback_component(component: str, version: str | None = None) -> dict[str, Any]:
    """Point the active map at a previously installed, verified component."""
    component = str(component or "").strip()
    if component not in COMPONENTS:
        raise ValueError("Desteklenmeyen NetOps bileşeni.")
    active = active_components()
    current = active.get(component, {}) if isinstance(active.get(component), dict) else {}
    current_version = str(current.get("version") or "0.0.0")
    history = installed_component_versions(component)
    requested = str(version or "").strip()
    candidates = [item for item in history if item["version"] == requested] if requested else [
        item for item in history if version_is_newer(current_version, item["version"])
    ]
    if not candidates:
        raise ValueError(f"{component} için geri alınabilecek doğrulanmış sürüm bulunamadı.")
    target = candidates[0]
    active[component] = {
        "id": component,
        "version": target["version"],
        "path": target["path"],
        "module": target["module"],
    }
    _save_active(active)
    return {"ok": True, **target, "restart_required": True, "previous_version": current_version}


def activate_installed_components() -> dict[str, Any]:
    active = active_components()
    inserted = []
    for component in COMPONENTS:
        item = active.get(component)
        path = Path(str(item.get("path") or "")) if isinstance(item, dict) else Path()
        if not path.is_dir():
            continue
        value = str(path.resolve())
        if value not in sys.path:
            sys.path.insert(0, value)
            inserted.append(value)
    return {"active": active, "inserted": inserted}


def install_component_update(update: dict[str, Any]) -> dict[str, Any]:
    component = str(update.get("id") or "")
    if component not in COMPONENTS:
        raise ValueError("Desteklenmeyen NetOps bileşeni.")
    module = _module_name(component, update)
    archive = _download(update)
    version = str(update["version"])
    target = component_root() / component / version
    if target.exists():
        shutil.rmtree(target)
    staging = Path(tempfile.mkdtemp(prefix=f"neto_{component}_", dir=str(component_root())))
    try:
        with zipfile.ZipFile(archive, "r") as package:
            _safe_extract(package, staging)
        children = list(staging.iterdir())
        source = children[0] if len(children) == 1 and children[0].is_dir() else staging
        if not (source / module).is_file():
            raise RuntimeError(f"{component} paketinde {module} bulunamadı.")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target)
        metadata = {"id": component, "version": version, "module": module}
        (target / "component.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        active = active_components()
        active[component] = {"version": version, "path": str(target), "module": module}
        _save_active(active)
        return {
            "ok": True,
            "id": component,
            "version": version,
            "path": str(target),
            "restart_required": True,
        }
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def schedule_startup_check(
    root: Any = None,
    notify_callback: Callable[[str], Any] | None = None,
    delay_ms: int = 5200,
    auto_install: bool | None = None,
) -> Any:
    global _CHECK_RUNNING
    if str(os.environ.get("NETO_DISABLE_COMPONENT_UPDATES", "")).lower() in {"1", "true", "yes"}:
        return None
    if auto_install is None:
        auto_install = str(os.environ.get("NETO_COMPONENT_AUTO_UPDATE", "1")).lower() not in {"0", "false", "no"}

    def notify(message: str) -> None:
        if callable(notify_callback):
            try:
                notify_callback(message)
            except Exception:
                pass

    def worker() -> None:
        global _CHECK_RUNNING
        if _CHECK_RUNNING:
            return
        _CHECK_RUNNING = True
        try:
            result = check_for_updates(force=True)
            if result.get("available") and auto_install:
                installed = []
                for update in result.get("updates", []):
                    try:
                        install_component_update(update)
                        installed.append(f"{update['id']} v{update['version']}")
                    except Exception:
                        pass
                if installed:
                    notify("NetOps sürücü güncellemesi hazırlandı: " + ", ".join(installed) + ". Yeniden başlatınca etkin olacak.")
            elif result.get("available"):
                notify("NetOps sürücü güncellemesi bulundu.")
        finally:
            _CHECK_RUNNING = False

    def start() -> None:
        threading.Thread(target=worker, name="NetOpsComponentUpdate", daemon=True).start()

    try:
        return root.after(max(0, int(delay_ms)), start) if root is not None else start()
    except Exception:
        return start()
