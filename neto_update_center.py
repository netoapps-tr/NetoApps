"""NUC: Neto Update Center.

The standalone updater discovers supported Neto applications, reads the
central GitHub Releases catalog, and downloads verified EXE packages without
coupling itself to the main NetOps GUI.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import threading
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable


APP_NAME = "Neto Update Center"
APP_SHORT_NAME = "NUC"
APP_VERSION = "1.1.0"
REPOSITORY = "netoapps-tr/NetoApps"
REPOSITORY_URL = f"https://github.com/{REPOSITORY}"
RELEASES_API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases?per_page=100"
NETWORK_TIMEOUT = 25
MIN_SUPPORTED_VERSIONS = {
    "neto_asistan": (10, 36, 0),
    "netops": (1, 0, 0),
}
PRODUCT_LABELS = {
    "neto_asistan": "Neto Asistan",
    "netops": "NetOps",
}
USER_AGENT = f"NUC/{APP_VERSION} (Windows; +{REPOSITORY_URL})"


def version_tuple(value: Any) -> tuple[int, ...]:
    match = re.search(r"(?<!\d)(\d+(?:\.\d+){0,5})(?!\d)", str(value or ""))
    if not match:
        return (0, 0, 0, 0, 0, 0)
    parts = tuple(int(piece) for piece in match.group(1).split("."))
    return parts + (0,) * (6 - len(parts))


def is_supported_version(product_id: str, value: Any) -> bool:
    minimum = MIN_SUPPORTED_VERSIONS.get(str(product_id or "").strip())
    return bool(minimum and version_tuple(value) >= minimum)


def comparison_version_tuple(product_id: str, value: Any) -> tuple[int, ...]:
    parsed = version_tuple(value)
    if product_id == "netops" and parsed[0] == 10:
        return (1, parsed[1], *parsed[2:])
    return parsed


def update_state(product_id: str, installed_version: Any, latest_version: Any) -> str:
    if not str(installed_version or "").strip() or version_tuple(installed_version) == (0, 0, 0, 0, 0, 0):
        return "unknown"
    if comparison_version_tuple(product_id, latest_version) > comparison_version_tuple(product_id, installed_version):
        return "available"
    return "current"


def _normalize_digest(value: Any) -> str:
    text = str(value or "").strip().lower()
    if ":" in text:
        prefix, text = text.split(":", 1)
        if prefix.strip() != "sha256":
            return ""
    return text if re.fullmatch(r"[0-9a-f]{64}", text) else ""


def _is_github_download(url: Any) -> bool:
    parsed = urllib.parse.urlparse(str(url or "").strip())
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (
        host == "github.com" or host.endswith(".githubusercontent.com")
    )


def _classify_asset(name: Any) -> str:
    normalized = str(name or "").strip().casefold()
    if re.match(r"^netops(?:[-_. ]|$)", normalized):
        return "netops"
    if re.match(r"^neto[._ -]?asistan(?:[-_. ]|$)", normalized):
        return "neto_asistan"
    return ""


def _asset_version(asset_name: str, tag_name: str, release_name: str) -> str:
    for value in (asset_name, tag_name, release_name):
        match = re.search(r"(?<!\d)(\d+(?:\.\d+){1,5})(?!\d)", str(value or ""))
        if match:
            return match.group(1)
    return "0.0.0"


def _release_item(release: dict[str, Any], asset: dict[str, Any], product_id: str) -> dict[str, Any] | None:
    asset_name = str(asset.get("name") or "").strip()
    download_url = str(asset.get("browser_download_url") or asset.get("url") or "").strip()
    if not asset_name.lower().endswith(".exe") or not _is_github_download(download_url):
        return None
    version = _asset_version(
        asset_name,
        str(release.get("tag_name") or ""),
        str(release.get("name") or ""),
    )
    digest = _normalize_digest(asset.get("digest") or asset.get("sha256"))
    return {
        "product_id": product_id,
        "product_name": PRODUCT_LABELS[product_id],
        "version": version,
        "tag_name": str(release.get("tag_name") or ""),
        "release_name": str(release.get("name") or ""),
        "release_url": str(release.get("html_url") or REPOSITORY_URL),
        "asset_name": asset_name,
        "download_url": download_url,
        "asset_digest": digest,
        "prerelease": bool(release.get("prerelease")),
        "supported_minimum": is_supported_version(product_id, version),
    }


def catalog_from_releases(releases: Any) -> dict[str, dict[str, Any]]:
    """Return the newest supported package for each known Neto product."""
    catalog: dict[str, dict[str, Any]] = {}
    if not isinstance(releases, list):
        return catalog
    for release in releases:
        if not isinstance(release, dict) or release.get("draft"):
            continue
        release_prerelease = bool(release.get("prerelease"))
        for asset in release.get("assets") or []:
            if not isinstance(asset, dict):
                continue
            product_id = _classify_asset(asset.get("name"))
            if not product_id:
                continue
            if product_id == "netops" and release_prerelease:
                continue
            item = _release_item(release, asset, product_id)
            if not item or not item["supported_minimum"]:
                continue
            previous = catalog.get(product_id)
            if previous is None or (
                version_tuple(item["version"],) > version_tuple(previous["version"])
                or (
                    version_tuple(item["version"]) == version_tuple(previous["version"])
                    and not item["prerelease"]
                    and previous["prerelease"]
                )
            ):
                catalog[product_id] = item
    return catalog


def _http_get_json(url: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8", "replace"))


def fetch_releases() -> list[dict[str, Any]]:
    payload = _http_get_json(RELEASES_API_URL)
    return payload if isinstance(payload, list) else []


def fetch_catalog() -> dict[str, dict[str, Any]]:
    return catalog_from_releases(fetch_releases())


def _download_bytes(url: str) -> bytes:
    if not _is_github_download(url):
        raise ValueError("NUC sadece HTTPS GitHub indirme adreslerini kabul eder.")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/octet-stream"},
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        chunks: list[bytes] = []
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)


def download_release(
    release: dict[str, Any],
    destination_dir: Path,
    progress_callback: Callable[[int, int], Any] | None = None,
) -> str:
    asset_name = Path(str(release.get("asset_name") or "")).name
    url = str(release.get("download_url") or "").strip()
    if not asset_name.lower().endswith(".exe") or asset_name in {".", ""}:
        raise ValueError("Gecersiz NUC paket adi.")
    if not _is_github_download(url):
        raise ValueError("Gecersiz NUC indirme adresi.")
    destination_dir = Path(destination_dir).expanduser()
    destination_dir.mkdir(parents=True, exist_ok=True)
    target = destination_dir / asset_name
    temporary = target.with_name(f".{target.name}.part")
    payload = _download_bytes(url)
    expected = _normalize_digest(release.get("asset_digest"))
    actual = hashlib.sha256(payload).hexdigest()
    if not expected:
        raise RuntimeError("Paket SHA-256 bilgisi olmadan indirilemez.")
    if actual != expected:
        raise RuntimeError("Indirilen NUC paketi SHA-256 dogrulamasini gecemedi.")
    temporary.write_bytes(payload)
    os.replace(temporary, target)
    if callable(progress_callback):
        progress_callback(len(payload), len(payload))
    return str(target)


def _version_from_path(path: Path) -> str:
    for value in (path.name, path.stem):
        match = re.search(r"(?<!\d)(\d+(?:\.\d+){1,5})(?!\d)", value)
        if match:
            return match.group(1)
    for filename in ("APP_VERSION.txt", "VERSION.txt"):
        sidecar = path.parent / filename
        try:
            if sidecar.is_file():
                value = sidecar.read_text(encoding="utf-8").strip()
                if version_tuple(value) != (0, 0, 0, 0, 0, 0):
                    return value.lstrip("vV")
        except OSError:
            pass
    return ""


def _registry_entries() -> list[dict[str, str]]:
    if os.name != "nt":
        return []
    try:
        import winreg
    except ImportError:
        return []
    entries: list[dict[str, str]] = []
    locations = (
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    )
    for hive, base in locations:
        try:
            with winreg.OpenKey(hive, base) as root:
                for index in range(winreg.QueryInfoKey(root)[0]):
                    try:
                        child_name = winreg.EnumKey(root, index)
                        with winreg.OpenKey(root, child_name) as child:
                            values: dict[str, str] = {}
                            for value_name in ("DisplayName", "DisplayVersion", "DisplayIcon", "InstallLocation"):
                                try:
                                    values[value_name] = str(winreg.QueryValueEx(child, value_name)[0] or "")
                                except OSError:
                                    pass
                            entries.append(values)
                    except OSError:
                        continue
        except OSError:
            continue
    return entries


def _path_product_id(value: Any) -> str:
    product_id = _classify_asset(Path(str(value or "")).name)
    if product_id:
        return product_id
    text = str(value or "").casefold()
    if "neto asistan" in text or "neto.asistan" in text or "netoasistan" in text:
        return "neto_asistan"
    if "netops" in text:
        return "netops"
    return ""


def discover_installed_products() -> list[dict[str, str]]:
    """Find likely installations without scanning the entire system drive."""
    discovered: dict[tuple[str, str], dict[str, str]] = {}

    def add(product_id: str, path_value: Any, version: Any = "", source: str = "") -> None:
        path = Path(str(path_value or "")).expanduser()
        if not path.is_file() or path.suffix.casefold() != ".exe":
            return
        product_id = product_id or _path_product_id(path)
        if not product_id:
            return
        item = {
            "product_id": product_id,
            "product_name": PRODUCT_LABELS[product_id],
            "path": str(path.resolve()),
            "version": str(version or _version_from_path(path)),
            "display_version": str(version or _version_from_path(path) or path.stem),
            "source": source,
        }
        discovered[(product_id, item["path"].casefold())] = item

    for entry in _registry_entries():
        display = entry.get("DisplayName", "")
        product_id = _path_product_id(display) or _path_product_id(entry.get("DisplayIcon"))
        if not product_id:
            continue
        icon_path = entry.get("DisplayIcon", "").split(",", 1)[0].strip('"')
        install_path = Path(entry.get("InstallLocation", "")) if entry.get("InstallLocation") else None
        candidates = [Path(icon_path)] if icon_path else []
        if install_path:
            candidates.extend([install_path / "NetOps.exe", install_path / "Neto.Asistan.exe"])
        for candidate in candidates:
            add(product_id, candidate, entry.get("DisplayVersion", ""), "registry")

    roots = [
        Path.home() / "Downloads",
        Path.home() / "Desktop",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" if os.environ.get("LOCALAPPDATA") else None,
        Path(os.environ.get("PROGRAMFILES", "")) if os.environ.get("PROGRAMFILES") else None,
        Path(os.environ.get("PROGRAMFILES(X86)", "")) if os.environ.get("PROGRAMFILES(X86)") else None,
    ]
    patterns = ("NetOps*.exe", "Neto.Asistan*.exe", "Neto Asistan*.exe", "NetoAsistan*.exe")
    for root in [item for item in roots if item and item.is_dir()]:
        try:
            for pattern in patterns:
                for candidate in root.glob(pattern):
                    add("", candidate, source="filesystem")
                for candidate in root.glob(f"*/{pattern}"):
                    add("", candidate, source="filesystem")
        except OSError:
            continue
    return sorted(discovered.values(), key=lambda item: (item["product_id"], item["path"].casefold()))


def _open_folder(path: str) -> None:
    if os.name == "nt":
        os.startfile(str(Path(path).parent))
    else:
        import subprocess
        subprocess.Popen(["xdg-open", str(Path(path).parent)])


class UpdateCenterApp:
    def __init__(self, root: Any) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.root = root
        self.tk = tk
        self.ttk = ttk
        self.root.title(f"NUC | {APP_NAME}")
        self.root.geometry("760x430")
        self.root.minsize(640, 360)
        try:
            ttk.Style(self.root).theme_use("vista")
        except tk.TclError:
            pass
        self.catalog: dict[str, dict[str, Any]] = {}
        self.installed: list[dict[str, str]] = []
        self.status_var = tk.StringVar(value="GitHub merkezi kontrol ediliyor...")
        self.details_var = tk.StringVar(value="")
        self.container = ttk.Frame(root, padding=16)
        self.container.pack(fill="both", expand=True)
        self._build_header()
        content = ttk.Frame(self.container)
        content.pack(fill="both", expand=True, pady=(16, 8))
        columns = ("product", "installed", "latest", "status")
        self.table = ttk.Treeview(content, columns=columns, show="headings", height=7)
        headings = {
            "product": "Program",
            "installed": "Kurulu sürüm",
            "latest": "GitHub sürümü",
            "status": "Durum",
        }
        widths = {"product": 190, "installed": 170, "latest": 150, "status": 180}
        for column in columns:
            self.table.heading(column, text=headings[column])
            self.table.column(column, width=widths[column], anchor="w")
        self.table.tag_configure("available", foreground="#c62828")
        self.table.tag_configure("current", foreground="#2e7d32")
        self.table.tag_configure("unknown", foreground="#6b7280")
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(content, orient="vertical", command=self.table.yview)
        scrollbar.pack(side="right", fill="y")
        self.table.configure(yscrollcommand=scrollbar.set)
        ttk.Label(
            self.container,
            textvariable=self.details_var,
            justify="left",
            anchor="w",
        ).pack(fill="x", pady=(0, 8))
        self.status_label = ttk.Label(
            root,
            textvariable=self.status_var,
            anchor="w",
            padding=(16, 8),
        )
        self.status_label.pack(fill="x")
        self.refresh()

    def _build_header(self) -> None:
        ttk = self.ttk
        header = ttk.Frame(self.container)
        header.pack(fill="x")
        ttk.Label(header, text="NUC", font=("Segoe UI", 16, "bold")).pack(side="left")
        ttk.Label(
            header,
            text="Neto Update Center | Merkezi sürüm kontrolü",
        ).pack(side="left", padx=(12, 0))
        self.refresh_button = ttk.Button(
            header,
            text="GitHub'dan kontrol et",
            command=self.refresh,
        )
        self.refresh_button.pack(side="right")

    def refresh(self) -> None:
        self.status_var.set("GitHub merkezi kontrol ediliyor...")
        self.refresh_button.configure(state="disabled")
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self) -> None:
        try:
            catalog = fetch_catalog()
            installed = discover_installed_products()
            self.root.after(0, lambda: self._render(catalog, installed, "Merkez güncel.") )
        except Exception as exc:
            self.root.after(0, lambda: self._render({}, [], f"Merkez kontrolü başarısız: {exc}"))

    def _render(self, catalog: dict[str, dict[str, Any]], installed: list[dict[str, str]], status: str) -> None:
        self.catalog = catalog
        self.installed = installed
        for item in self.table.get_children():
            self.table.delete(item)
        details: list[str] = []
        for product_id in ("netops", "neto_asistan"):
            latest = catalog.get(product_id)
            matches = [item for item in installed if item["product_id"] == product_id]
            installed_item = matches[0] if matches else None
            installed_version = installed_item.get("version", "") if installed_item else ""
            latest_version = latest.get("version", "") if latest else ""
            state = update_state(product_id, installed_version, latest_version) if latest else "unknown"
            title = PRODUCT_LABELS[product_id]
            installed_text = (
                installed_item.get("display_version") or installed_item.get("version")
                if installed_item
                else "Kurulu değil"
            )
            latest_text = latest["version"] if latest else "Bulunamadı"
            status_text = {
                "available": "Güncelleme var",
                "current": "Güncel",
                "unknown": "Kurulu sürüm karşılaştırılamadı",
            }.get(state, "GitHub paketi bulunamadı")
            detail = "Kurulu uygulama bulunamadı."
            if installed_item:
                detail = installed_item["path"]
            if product_id == "neto_asistan":
                detail += "\nMinimum destek: Neto Asistan 10.36"
            dot = "●" if state == "available" else "○"
            self.table.insert(
                "",
                "end",
                values=(title, installed_text, latest_text, f"{dot} {status_text}"),
                tags=(state,),
            )
            details.append(f"{title}: {detail}")
        self.details_var.set("\n".join(details))
        self.status_var.set(status)
        self.refresh_button.configure(state="normal")

    def _download(self, release: dict[str, Any] | None) -> None:
        if not release:
            return
        self.status_var.set(f"{release['product_name']} {release['version']} indiriliyor...")
        destination = Path.home() / "Downloads" / "NetoUpdateCenter"
        threading.Thread(target=self._download_worker, args=(release, destination), daemon=True).start()

    def _download_worker(self, release: dict[str, Any], destination: Path) -> None:
        try:
            path = download_release(release, destination)
            self.root.after(0, lambda: self._download_done(path))
        except Exception as exc:
            self.root.after(0, lambda: self.status_var.set(f"İndirme başarısız: {exc}"))

    def _download_done(self, path: str) -> None:
        import tkinter.messagebox as messagebox

        self.status_var.set(f"Doğrulandı: {path}")
        messagebox.showinfo("NUC", f"Paket indirildi ve SHA-256 doğrulandı.\n\n{path}")
        _open_folder(path)


def main() -> None:
    import tkinter as tk

    root = tk.Tk()
    UpdateCenterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
