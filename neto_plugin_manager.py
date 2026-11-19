"""Discovery and safe staging of NetOps ``.nops`` extensions."""
from __future__ import annotations

import json
import importlib.util
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from neto_plugin_security import PluginFinding, PluginScanReport, scan_plugin


@dataclass(frozen=True)
class NopsManifest:
    plugin_id: str
    name: str
    version: str
    entry: str
    permissions: tuple[str, ...]
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NopsManifest":
        plugin_id = str(data.get("id", "")).strip().lower()
        if not plugin_id or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for ch in plugin_id):
            raise ValueError("Manifest id yalnızca küçük harf, sayı, '-' ve '_' içerebilir")
        entry = str(data.get("entry", "main.py")).strip()
        if not entry or Path(entry).is_absolute() or ".." in Path(entry).parts:
            raise ValueError("Manifest entry yolu güvenli değil")
        permissions = tuple(str(item) for item in data.get("permissions", []) if str(item).strip())
        return cls(
            plugin_id=plugin_id,
            name=str(data.get("name") or plugin_id),
            version=str(data.get("version") or "1.0.0"),
            entry=entry,
            permissions=permissions,
            description=str(data.get("description") or ""),
        )


@dataclass
class NopsPlugin:
    manifest: NopsManifest
    path: Path
    scan: PluginScanReport
    enabled: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.manifest.plugin_id,
            "name": self.manifest.name,
            "version": self.manifest.version,
            "path": str(self.path),
            "permissions": list(self.manifest.permissions),
            "enabled": self.enabled,
            "scan": self.scan.as_dict(),
        }


class NetOpsPluginManager:
    """Manages metadata and staging; plugin Python is not imported automatically."""

    def __init__(self, plugin_dir: str | Path | None = None) -> None:
        self.plugin_dir = Path(plugin_dir or Path(__file__).with_name("plugins"))
        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        self.registry_path = self.plugin_dir / "installed_plugins.json"
        self._plugins: dict[str, NopsPlugin] = {}

    @property
    def plugins(self) -> list[NopsPlugin]:
        return list(self._plugins.values())

    def discover(self) -> list[NopsPlugin]:
        self._plugins.clear()
        for manifest_path in sorted(self.plugin_dir.glob("*/plugin.json")):
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest = NopsManifest.from_dict(data)
                scan = scan_plugin(manifest.plugin_id, manifest_path.parent)
                self._plugins[manifest.plugin_id] = NopsPlugin(manifest, manifest_path.parent, scan)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                plugin_id = manifest_path.parent.name.lower()
                report = PluginScanReport(plugin_id)
                report.findings.append(PluginFinding("high", "PLUGIN_MANIFEST", str(exc), str(manifest_path)))
                self._plugins[plugin_id] = NopsPlugin(
                    NopsManifest(plugin_id, plugin_id, "", "", ()), manifest_path.parent, report
                )
        return self.plugins

    def list(self) -> list[dict[str, Any]]:
        return [plugin.as_dict() for plugin in self.discover()]

    def activate(self, plugin_id: str, api: Any) -> dict[str, Any]:
        """Load one reviewed entry point and let it register with the host API."""
        plugin = self._plugins.get(str(plugin_id).lower())
        if plugin is None:
            return {"ok": False, "error": "Eklenti bulunamadı."}
        if not plugin.scan.safe_to_review:
            return {"ok": False, "error": "Eklenti kritik güvenlik bulguları içeriyor."}
        entry = (plugin.path / plugin.manifest.entry).resolve()
        try:
            entry.relative_to(plugin.path.resolve())
        except ValueError:
            return {"ok": False, "error": "Eklenti giriş yolu güvenli değil."}
        if not entry.is_file():
            return {"ok": False, "error": "Eklenti giriş dosyası bulunamadı."}
        module_name = f"netops_plugin_{plugin.manifest.plugin_id}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, entry)
            if spec is None or spec.loader is None:
                raise ImportError("Eklenti modülü hazırlanamadı")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            register = getattr(module, "register", None)
            if not callable(register):
                raise TypeError("Eklenti register(api) fonksiyonu içermiyor")
            result = register(api)
            plugin.enabled = True
            return {"ok": True, "result": result}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def stage_nops(self, archive: str | Path) -> NopsPlugin:
        """Validate and stage a .nops zip without activating or importing it."""
        archive_path = Path(archive).resolve()
        if archive_path.suffix.lower() != ".nops":
            raise ValueError("Yalnızca .nops dosyaları içe aktarılabilir")
        # Keep staging beside the managed plugin directory so restricted
        # Windows environments do not block cleanup of the system temp path.
        with tempfile.TemporaryDirectory(prefix=".staging_", dir=self.plugin_dir) as temp_name:
            temp_root = Path(temp_name).resolve()
            with zipfile.ZipFile(archive_path) as bundle:
                for member in bundle.infolist():
                    target = (temp_root / member.filename).resolve()
                    try:
                        target.relative_to(temp_root)
                    except ValueError:
                        raise ValueError("Eklenti arşivinde güvenli olmayan yol bulundu")
                bundle.extractall(temp_root)
            manifest_path = temp_root / "plugin.json"
            if not manifest_path.is_file():
                nested = list(temp_root.glob("*/plugin.json"))
                manifest_path = nested[0] if len(nested) == 1 else manifest_path
            if not manifest_path.is_file():
                raise ValueError(".nops içinde plugin.json bulunamadı")
            manifest = NopsManifest.from_dict(json.loads(manifest_path.read_text(encoding="utf-8")))
            report = scan_plugin(manifest.plugin_id, manifest_path.parent)
            if not report.safe_to_review:
                raise ValueError("Eklenti kritik güvenlik bulguları içeriyor; kurulmadı")
            destination = self.plugin_dir / manifest.plugin_id
            # Never remove an installed plugin. Copying over the reviewed files
            # keeps user-added state and makes re-imports durable across restarts.
            destination.mkdir(parents=True, exist_ok=True)
            shutil.copytree(manifest_path.parent, destination, dirs_exist_ok=True)
        self.discover()
        self._remember_installed(manifest)
        return self._plugins[manifest.plugin_id]

    def _remember_installed(self, manifest: NopsManifest) -> None:
        """Persist installation metadata; this registry is append/update only."""
        try:
            current = json.loads(self.registry_path.read_text(encoding="utf-8")) if self.registry_path.is_file() else {}
            if not isinstance(current, dict):
                current = {}
        except (OSError, json.JSONDecodeError):
            current = {}
        plugins = current.setdefault("plugins", {})
        if not isinstance(plugins, dict):
            plugins = {}
            current["plugins"] = plugins
        plugins[manifest.plugin_id] = {
            "name": manifest.name,
            "version": manifest.version,
            "installed": True,
        }
        self.registry_path.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def install_bundled(self, directories: list[str | Path]) -> list[dict[str, Any]]:
        """Install every bundled .nops package without deleting existing plugins."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for directory in directories:
            folder = Path(directory)
            if not folder.is_dir():
                continue
            for archive in sorted(folder.glob("*.nops")):
                try:
                    # The manifest id is the durable de-duplication key.
                    with zipfile.ZipFile(archive) as bundle:
                        raw = json.loads(bundle.read("plugin.json").decode("utf-8"))
                    plugin_id = NopsManifest.from_dict(raw).plugin_id
                    if plugin_id in seen:
                        continue
                    seen.add(plugin_id)
                    plugin = self.stage_nops(archive)
                    results.append({"id": plugin.manifest.plugin_id, "ok": True})
                except Exception as exc:
                    results.append({"id": archive.stem.lower(), "ok": False, "error": str(exc)})
        return results


__all__ = ["NetOpsPluginManager", "NopsManifest", "NopsPlugin"]
