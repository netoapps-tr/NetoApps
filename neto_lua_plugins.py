from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class LuaPlugin:
    plugin_id: str
    path: str
    name: str
    version: str
    description: str
    loaded: bool
    error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.plugin_id,
            "path": self.path,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "loaded": self.loaded,
            "error": self.error,
        }


class NetOpsLuaPluginManager:
    """Discovers Lua plugins without Python imports or shell access."""

    def __init__(self, kernel: Any, plugin_dir: str | Path | Iterable[str | Path]) -> None:
        self.kernel = kernel
        if isinstance(plugin_dir, (str, Path)):
            self.plugin_dirs = [Path(plugin_dir)]
        else:
            self.plugin_dirs = [Path(item) for item in plugin_dir]
        self._plugins: dict[str, LuaPlugin] = {}

    @property
    def plugins(self) -> list[LuaPlugin]:
        return list(self._plugins.values())

    def load_all(self) -> list[LuaPlugin]:
        candidates: dict[str, Path] = {}
        for directory in self.plugin_dirs:
            directory.mkdir(parents=True, exist_ok=True)
            for path in sorted(directory.glob("*.lua")):
                # Later directories override bundled plugins with the same id.
                candidates[path.stem.casefold()] = path
        for plugin_id in sorted(candidates):
            self._load_one(candidates[plugin_id])
        return self.plugins

    def _load_one(self, path: Path) -> LuaPlugin:
        plugin_id = path.stem.casefold()
        try:
            result = self.kernel.load_file(path)
            metadata = result.get("result") if isinstance(result, dict) else {}
            if not isinstance(metadata, dict):
                metadata = {}
            plugin = LuaPlugin(
                plugin_id=plugin_id,
                path=str(path),
                name=str(metadata.get("name") or path.stem),
                version=str(metadata.get("version") or "1.0"),
                description=str(metadata.get("description") or ""),
                loaded=True,
            )
        except Exception as exc:
            plugin = LuaPlugin(
                plugin_id=plugin_id,
                path=str(path),
                name=path.stem,
                version="",
                description="",
                loaded=False,
                error=str(exc),
            )
        self._plugins[plugin_id] = plugin
        return plugin

    def reload(self) -> list[LuaPlugin]:
        self._plugins.clear()
        return self.load_all()

    def list(self) -> list[dict[str, Any]]:
        return [plugin.as_dict() for plugin in self.plugins]


__all__ = ["LuaPlugin", "NetOpsLuaPluginManager"]