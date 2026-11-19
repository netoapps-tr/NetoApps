"""NetOps updater.

Public GitHub Releases Atom feed is used for release discovery. The module is
safe to import during application startup: it performs no network request until
a check function is called.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
import threading
import time
import tempfile
import urllib.parse
import urllib.request
import webbrowser
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

REPO_OWNER = "netoapps-tr"
REPO_NAME = "NetoApps"
REPO_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}"
API_URL = "https://api.github.com"
RELEASES_URL = f"{REPO_URL}/releases"
RELEASES_API_URL = f"{API_URL}/repos/{REPO_OWNER}/{REPO_NAME}/releases"
RELEASE_BY_TAG_API_URL = f"{RELEASES_API_URL}/tags/{{tag}}"
FEED_URL = f"{RELEASES_URL}.atom"
EXPANDED_ASSETS_URL = f"{REPO_URL}/releases/expanded_assets/{{tag}}"
NETWORK_TIMEOUT = 18
CACHE_SECONDS = 15 * 60
UPDATER_BUILD = "neto-v1.42.0-release"

_CACHE: Dict[str, Any] = {"at": 0.0, "result": None}
_CACHE_LOCK = threading.RLock()


def _app_data_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "NetOps"
    return Path.home() / ".neto_assistant"


def _state_path() -> Path:
    return _app_data_dir() / "update_state.json"


def _can_write_directory(path: Path) -> bool:
    """Create and probe a directory without assuming Windows TEMP works."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".netops-write-{os.getpid()}-{threading.get_ident()}"
        probe.write_bytes(b"ok")
        probe.unlink(missing_ok=True)
        return True
    except (OSError, ValueError):
        return False


def _update_root() -> Path:
    """Return a stable writable location for downloads and updater jobs.

    PyInstaller/Windows TEMP can be unavailable because of a policy, a full
    disk, or a stale locked directory. The updater must not depend on it.
    """
    local_appdata = os.environ.get("LOCALAPPDATA")
    appdata = os.environ.get("APPDATA")
    candidates = [
        Path(local_appdata) / "NetOps" / "updates" if local_appdata else None,
        Path(appdata) / "NetOps" / "updates" if appdata else None,
        Path.home() / ".neto_assistant" / "updates",
    ]
    try:
        candidates.append(Path(tempfile.gettempdir()) / "NetOps" / "updates")
    except (OSError, ValueError):
        pass
    candidates.append(Path.cwd() / ".neto_updates")
    for candidate in candidates:
        if candidate is not None and _can_write_directory(candidate):
            return candidate
    raise RuntimeError("Güncelleme için yazılabilir klasör oluşturulamadı.")


def _downloads_dir() -> Path:
    return _update_root()


def _early_version_tuple(value: Any) -> Optional[Tuple[int, ...]]:
    match = re.search(r"(?<!\d)(\d+(?:\.\d+){0,5})(?!\d)", str(value or ""))
    if not match:
        return None
    try:
        parts = tuple(int(piece) for piece in match.group(1).split("."))
        return parts + (0,) * (6 - len(parts))
    except Exception:
        return None


def _get_version_from_project() -> str:
    candidates: List[str] = []

    try:
        from neto_version import get_app_version
        candidates.append(str(get_app_version() or ""))
    except Exception:
        pass

    try:
        from neto_version import APP_VERSION
        candidates.append(str(APP_VERSION or ""))
    except Exception:
        pass

    roots = [Path.cwd(), Path(__file__).resolve().parent]
    for root in roots:
        for filename in ("APP_VERSION.txt", "VERSION.txt"):
            try:
                candidate = root / filename
                if candidate.is_file():
                    candidates.append(candidate.read_text(encoding="utf-8").strip())
            except Exception:
                pass

    try:
        main_file = Path(__file__).resolve().parent / "asistan beta.py"
        if main_file.is_file():
            head = main_file.read_text(encoding="utf-8", errors="replace")[:180000]
            candidates.extend(
                re.findall(r"(?<!\\d)10\\.\\d+(?:\\.\\d+)?(?!\\d)", head)
            )
    except Exception:
        pass

    # Prefer the dedicated version module.  The main UI file can contain old
    # compatibility markers and must not override the current release value.
    for value in candidates:
        cleaned = value.lstrip("vV")
        if _early_version_tuple(cleaned):
            return cleaned
    return "0.0.0"


CURRENT_VERSION = _get_version_from_project()
USER_AGENT = f"NetOps-Updater/{CURRENT_VERSION} (Windows; +{REPO_URL})"


def get_current_version() -> str:
    return _get_version_from_project()


def _version_tuple(value: Any) -> Optional[Tuple[int, ...]]:
    match = re.search(r"(?<!\d)(\d+(?:\.\d+){0,5})(?!\d)", str(value or ""))
    if not match:
        return None
    try:
        parts = tuple(int(piece) for piece in match.group(1).split("."))
        return parts + (0,) * (6 - len(parts))
    except Exception:
        return None


def _comparison_version_tuple(value: Any) -> Optional[Tuple[int, ...]]:
    """Compare legacy 10.x builds with the public 1.x release train.

    Early NetOps builds used ``10.39`` while GitHub releases use ``1.40``.
    Treating those strings literally made every old installation believe that
    the newer public release was older.  The display value is left untouched;
    only ordering is normalized here.
    """
    parsed = _version_tuple(value)
    if not parsed:
        return None
    if parsed[0] == 10 and parsed[1] >= 0:
        return (1, parsed[1], *parsed[2:])
    return parsed


def version_is_newer(remote: Any, current: Any = None) -> bool:
    current = get_current_version() if current is None else current
    remote_tuple = _comparison_version_tuple(remote)
    current_tuple = _comparison_version_tuple(current)
    return bool(remote_tuple and current_tuple and remote_tuple > current_tuple)


def _stable_id(*parts: Any) -> str:
    text = "|".join(str(part or "") for part in parts)
    return hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()[:20]


def _http_get(url: str, timeout: int = NETWORK_TIMEOUT, accept: str = "*/*") -> Tuple[bytes, Dict[str, str], int]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": accept,
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(), {k.lower(): v for k, v in response.headers.items()}, int(response.status)


def _normalize_digest(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if ":" in text:
        prefix, digest = text.split(":", 1)
        if prefix.strip().casefold() != "sha256":
            return ""
        text = digest.strip()
    text = text.lower()
    return text if re.fullmatch(r"[0-9a-f]{64}", text) else ""


def _asset_digest(asset: Dict[str, Any]) -> str:
    if not isinstance(asset, dict):
        return ""
    for key in ("digest", "sha256", "checksum"):
        digest = _normalize_digest(asset.get(key))
        if digest:
            return digest
    return ""


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def _html_to_text(value: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(value or "")
        parser.close()
        return "\n".join(parser.parts).strip()
    except Exception:
        return html.unescape(re.sub(r"<[^>]+>", "", value or "")).strip()


class _AssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.assets: List[Dict[str, Any]] = []
        self._href = ""
        self._text: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag.lower() != "a":
            return
        values = {str(k).lower(): str(v or "") for k, v in attrs}
        href = values.get("href", "")
        expected = f"/{REPO_OWNER}/{REPO_NAME}/releases/download/"
        if href.startswith(expected):
            self._href = href
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href and data.strip():
            self._text.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._href:
            return
        url = urllib.parse.urljoin("https://github.com", self._href)
        path_name = urllib.parse.unquote(Path(urllib.parse.urlparse(url).path).name)
        label = " ".join(self._text).strip()
        name = label if "." in label else path_name
        if name:
            self.assets.append(
                {
                    "id": _stable_id(url),
                    "name": name,
                    "browser_download_url": url,
                    "size": 0,
                    "content_type": "application/octet-stream",
                }
            )
        self._href = ""
        self._text = []


def _entry_text(entry: ET.Element, name: str) -> str:
    for child in entry:
        if child.tag.rsplit("}", 1)[-1] == name:
            return str(child.text or "").strip()
    return ""


def _entry_link(entry: ET.Element) -> str:
    fallback = ""
    for child in entry:
        if child.tag.rsplit("}", 1)[-1] != "link":
            continue
        href = str(child.attrib.get("href") or "")
        rel = str(child.attrib.get("rel") or "alternate")
        if rel == "alternate" and href:
            return href
        if href and not fallback:
            fallback = href
    return fallback


def _tag_from_url(url: str) -> str:
    marker = "/releases/tag/"
    if marker in str(url):
        return urllib.parse.unquote(str(url).split(marker, 1)[1].split("?", 1)[0].strip("/"))
    return ""


def _looks_prerelease(*values: Any) -> bool:
    text = " ".join(str(v or "") for v in values).casefold()
    words = ("alpha", "beta", "preview", "pre-release", "prerelease", "rc", "demo")
    return any(re.search(rf"(^|[^a-z]){re.escape(word)}([^a-z]|$)", text) for word in words)


def _fetch_releases() -> List[Dict[str, Any]]:
    payload, _headers, _status = _http_get(FEED_URL, accept="application/atom+xml, application/xml;q=0.9, */*;q=0.1")
    root = ET.fromstring(payload)
    releases: List[Dict[str, Any]] = []
    for entry in root.iter():
        if entry.tag.rsplit("}", 1)[-1] != "entry":
            continue
        title = _entry_text(entry, "title") or "GitHub yayını"
        updated = _entry_text(entry, "updated") or _entry_text(entry, "published")
        entry_id = _entry_text(entry, "id")
        link = _entry_link(entry)
        tag = _tag_from_url(link)
        if not tag:
            tag = title
        content = _entry_text(entry, "content") or _entry_text(entry, "summary")
        version_match = re.search(r"\d+(?:\.\d+)+", tag) or re.search(r"\d+(?:\.\d+)+", title)
        releases.append(
            {
                "release_id": _stable_id(link, tag, updated, entry_id),
                "id": _stable_id(link, tag, updated, entry_id),
                "tag_name": tag,
                "latest_version": version_match.group(0) if version_match else tag,
                "name": title,
                "body": _html_to_text(content),
                "html_url": link or RELEASES_URL,
                "published_at": updated,
                "created_at": updated,
                "prerelease": _looks_prerelease(title, tag),
                "assets": [],
                "source": "github_atom",
            }
        )
    if not releases:
        raise RuntimeError("GitHub yayın akışında sürüm bulunamadı.")
    return releases


def _fetch_assets(tag: str) -> List[Dict[str, Any]]:
    if not tag:
        return []
    api_url = RELEASE_BY_TAG_API_URL.format(tag=urllib.parse.quote(tag, safe=""))
    try:
        payload, _headers, _status = _http_get(api_url, accept="application/vnd.github+json")
        release = json.loads(payload.decode("utf-8", "replace"))
        assets = release.get("assets") if isinstance(release, dict) else []
        normalized: List[Dict[str, Any]] = []
        for asset in assets if isinstance(assets, list) else []:
            if not isinstance(asset, dict):
                continue
            url = str(asset.get("browser_download_url") or "")
            name = str(asset.get("name") or "").strip()
            if not (url and name):
                continue
            normalized.append(
                {
                    "id": str(asset.get("id") or _stable_id(url)),
                    "name": name,
                    "browser_download_url": url,
                    "size": int(asset.get("size") or 0),
                    "content_type": str(asset.get("content_type") or "application/octet-stream"),
                    "digest": _asset_digest(asset),
                    "source": "github_api",
                }
            )
        if normalized:
            return normalized
    except Exception:
        pass

    url = EXPANDED_ASSETS_URL.format(tag=urllib.parse.quote(tag, safe=""))
    payload, _headers, _status = _http_get(url, accept="text/html, */*;q=0.1")
    parser = _AssetParser()
    parser.feed(payload.decode("utf-8", "replace"))
    parser.close()
    unique: Dict[str, Dict[str, Any]] = {}
    for asset in parser.assets:
        unique[str(asset.get("browser_download_url"))] = asset
    return list(unique.values())


def _pick_asset(assets: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not assets:
        return None
    priority = {".zip": 0, ".exe": 1, ".msi": 2}
    ranked = sorted(
        assets,
        key=lambda item: (
            priority.get(Path(str(item.get("name") or "")).suffix.lower(), 10),
            str(item.get("name") or "").casefold(),
        ),
    )
    for item in ranked:
        if Path(str(item.get("name") or "")).suffix.lower() in priority:
            return item
    return ranked[0]


def load_state() -> Dict[str, Any]:
    default = {
        "installed_release_id": None,
        "installed_tag": "",
        "last_notified_release_id": None,
        "last_notified_at": 0,
        "last_check_at": 0,
        "last_error": "",
    }
    try:
        path = _state_path()
        if path.is_file():
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                default.update(value)
    except Exception:
        pass
    return default


def save_state(state: Dict[str, Any]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def check_for_updates(force: bool = False, include_prerelease: bool = False, **_: Any) -> Dict[str, Any]:
    now = time.time()
    with _CACHE_LOCK:
        cached = _CACHE.get("result")
        if not force and isinstance(cached, dict) and now - float(_CACHE.get("at") or 0) < CACHE_SECONDS:
            return dict(cached)

    current = get_current_version()
    state = load_state()
    # The 1.42 channel is file-level only. If its manifest is unavailable,
    # report that state instead of silently downloading a full program.
    try:
        from neto_system_updater import check_for_updates as check_system_updates

        system_result = check_system_updates(force=force)
        if system_result.get("manifest_ok"):
            state["last_check_at"] = int(now)
            state["last_error"] = ""
            save_state(state)
            with _CACHE_LOCK:
                _CACHE["at"] = now
                _CACHE["result"] = dict(system_result)
            return system_result
        return system_result
    except Exception as exc:
        return {
            "available": False,
            "update_available": False,
            "is_available": False,
            "update_mode": "system_files",
            "manifest_ok": False,
            "current_version": current,
            "latest_version": current,
            "tag_name": "",
            "system_files": [],
            "verified": False,
            "download_url": "",
            "error": str(exc),
            "message": f"Sistem guncellemesi kontrol edilemedi: {exc}",
        }
    try:
        releases = _fetch_releases()
        candidates = [release for release in releases if include_prerelease or not release.get("prerelease")]
        if not candidates:
            raise RuntimeError("Seçilen yayın kanalında sürüm bulunamadı.")

        def release_key(item: Dict[str, Any]) -> Tuple[int, ...]:
            return _comparison_version_tuple(item.get("latest_version") or item.get("tag_name")) or (0,) * 6

        release = max(candidates, key=release_key)
        try:
            assets = _fetch_assets(str(release.get("tag_name") or ""))
        except Exception:
            assets = []
        asset = _pick_asset(assets)
        asset_digest = _asset_digest(asset or {})
        release["assets"] = assets
        release["asset"] = asset or {}
        release["asset_name"] = str((asset or {}).get("name") or "")
        release["asset_size"] = int((asset or {}).get("size") or 0)
        release["download_url"] = str((asset or {}).get("browser_download_url") or "")
        release["asset_digest"] = asset_digest
        release["verified"] = bool(asset_digest)
        available = version_is_newer(release.get("latest_version") or release.get("tag_name"), current)
        release.update(
            {
                "available": available,
                "update_available": available,
                "is_available": available,
                "current_version": current,
                "error": "",
                "message": (
                    f"Yeni güncelleme bulundu ve doğrulandı: {release.get('tag_name') or release.get('name')}."
                    if available and asset_digest
                    else (
                        f"Yeni güncelleme bulundu ancak SHA-256 doğrulaması eksik: {release.get('tag_name') or release.get('name')}."
                        if available
                        else f"NetOps güncel. Kurulu sürüm: {current}."
                    )
                ),
            }
        )
        if not available:
            message = f"NetOps güncel. Kurulu sürüm: {current}."
        else:
            message = (
                f"Yeni güncelleme bulundu ve doğrulandı: {release.get('tag_name') or release.get('name')}."
                if asset_digest
                else f"Yeni güncelleme bulundu ancak SHA-256 doğrulaması eksik: {release.get('tag_name') or release.get('name')}."
            )
        release["message"] = message
        state["last_check_at"] = int(now)
        state["last_error"] = ""
        save_state(state)
        with _CACHE_LOCK:
            _CACHE["at"] = now
            _CACHE["result"] = dict(release)
        return release
    except Exception as exc:
        result = {
            "available": False,
            "update_available": False,
            "is_available": False,
            "current_version": current,
            "latest_version": current,
            "tag_name": "",
            "name": "",
            "body": "",
            "html_url": RELEASES_URL,
            "assets": [],
            "asset": {},
            "asset_name": "",
            "asset_size": 0,
            "download_url": "",
            "asset_digest": "",
            "verified": False,
            "error": str(exc),
            "message": f"Güncelleme kontrolü başarısız: {exc}",
            "source": "none",
        }
        state["last_check_at"] = int(now)
        state["last_error"] = str(exc)
        try:
            save_state(state)
        except Exception:
            pass
        return result


def check_for_update(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    return check_for_updates(*args, **kwargs)


def check_update(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    return check_for_updates(*args, **kwargs)


def check_latest_release(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    return check_for_updates(*args, **kwargs)


def get_update_status(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    return check_for_updates(*args, **kwargs)


def get_latest_release(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    return check_for_updates(*args, **kwargs)


def is_update_available(*args: Any, **kwargs: Any) -> bool:
    return bool(check_for_updates(*args, **kwargs).get("available"))


def check_for_updates_async(callback: Callable[[Dict[str, Any]], Any], **kwargs: Any) -> threading.Thread:
    def worker() -> None:
        result = check_for_updates(**kwargs)
        try:
            callback(result)
        except Exception:
            pass

    thread = threading.Thread(target=worker, name="NetoUpdateCheck", daemon=True)
    thread.start()
    return thread


def _safe_filename(name: str, fallback: str = "neto_update.bin") -> str:
    value = re.sub(r"[^A-Za-z0-9._()\- ]+", "_", str(name or "")).strip(" .")
    return value or fallback


def download_update(
    update: Optional[Dict[str, Any]] = None,
    destination: Optional[str] = None,
    progress_callback: Optional[Callable[..., Any]] = None,
    **_: Any,
) -> str:
    update = update or check_for_updates(force=True)
    if not isinstance(update, dict):
        raise ValueError("Güncelleme bilgisi geçersiz.")
    if update.get("update_mode") == "system_files":
        from neto_system_updater import download_files

        return download_files(update, progress_callback=progress_callback)
    raise RuntimeError("1.42 guncelleme kanali yalnizca degisen sistem dosyalarini kabul eder.")


def download_release(*args: Any, **kwargs: Any) -> str:
    return download_update(*args, **kwargs)


def download_asset(*args: Any, **kwargs: Any) -> str:
    return download_update(*args, **kwargs)


def open_release_page(update: Optional[Dict[str, Any]] = None) -> bool:
    update = update or check_for_updates(force=True)
    url = str((update or {}).get("html_url") or RELEASES_URL)
    try:
        return bool(webbrowser.open(url))
    except Exception:
        return False


def mark_release_notified(update: Dict[str, Any]) -> None:
    state = load_state()
    state["last_notified_release_id"] = update.get("release_id") or update.get("id")
    state["last_notified_at"] = int(time.time())
    save_state(state)


def mark_post_update_success_from_argv(argv: Optional[List[str]] = None) -> bool:
    args = list(sys.argv if argv is None else argv)
    release_id = ""
    tag = ""
    for arg in args:
        if str(arg).startswith("--neto-updated-release-id="):
            release_id = str(arg).split("=", 1)[1]
        elif str(arg).startswith("--neto-updated-tag="):
            tag = str(arg).split("=", 1)[1]
    if not release_id and not tag:
        return False
    state = load_state()
    state["installed_release_id"] = release_id or state.get("installed_release_id")
    state["installed_tag"] = tag or state.get("installed_tag")
    state["last_error"] = ""
    save_state(state)
    return True


def install_update(path: str, **kwargs: Any) -> Dict[str, Any]:
    try:
        plan = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(plan, dict) and plan.get("update_mode") == "system_files":
            from neto_system_updater import install_downloaded

            return install_downloaded(path, restart=bool(kwargs.get("restart", True)))
    except (OSError, ValueError, UnicodeError, TypeError):
        pass
    from neto_update_helper import install_update as helper_install
    return helper_install(path, **kwargs)


def apply_update(path: str, **kwargs: Any) -> Dict[str, Any]:
    return install_update(path, **kwargs)


try:
    print(f"[UPDATER] {UPDATER_BUILD} enabled", flush=True)
except Exception:
    pass
