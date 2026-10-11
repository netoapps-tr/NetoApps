from __future__ import annotations

import copy
import json
import os
import threading
import time
from pathlib import Path
from typing import Any


class LuaMemoryError(RuntimeError):
    """Raised when Lua memory cannot safely read or write JSON data."""


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


class NetOpsLuaMemory:
    """Small persistent JSON memory store dedicated to Lua extensions."""

    def __init__(self, path: str | Path | None = None, *, max_entries: int = 500) -> None:
        self.path = self.resolve_path(path)
        self.max_entries = max(10, int(max_entries))
        self._lock = threading.RLock()
        self._data: dict[str, Any] = self._load()

    @staticmethod
    def resolve_path(path: str | Path | None = None) -> Path:
        if path:
            return Path(path).expanduser().resolve()
        configured = os.environ.get("NETOPS_LUA_MEMORY_PATH", "").strip()
        if configured:
            return Path(configured).expanduser().resolve()
        appdata = os.environ.get("APPDATA", "").strip()
        if appdata:
            return (Path(appdata) / "NetoAsistan" / "netops_lua_memory.json").resolve()
        return (Path(__file__).resolve().parent / "netops_lua_memory.json").resolve()

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {"version": 1, "entries": {}, "updatedAt": _now()}

    def _load(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return self._empty()
        except (OSError, ValueError, TypeError):
            return self._empty()
        if not isinstance(data, dict) or not isinstance(data.get("entries"), dict):
            return self._empty()
        data.setdefault("version", 1)
        data.setdefault("updatedAt", _now())
        return data

    @staticmethod
    def _key(key: Any) -> str:
        value = " ".join(str(key or "").split()).strip().casefold()
        if not value:
            raise LuaMemoryError("Lua hafıza anahtarı boş bırakılamaz.")
        return value[:160]

    @staticmethod
    def _json_copy(value: Any) -> Any:
        try:
            return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
        except (TypeError, ValueError) as exc:
            raise LuaMemoryError("Lua hafızasına yalnızca JSON uyumlu veri yazılabilir.") from exc

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self._data, ensure_ascii=False, indent=2)
        if len(payload.encode("utf-8")) > 2 * 1024 * 1024:
            raise LuaMemoryError("Lua hafıza dosyası 2 MB sınırını aşamaz.")
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(self.path)

    def get(self, key: Any, default: Any = None) -> Any:
        normalized = self._key(key)
        with self._lock:
            entry = self._data["entries"].get(normalized)
            if not isinstance(entry, dict):
                return copy.deepcopy(default)
            entry["hits"] = int(entry.get("hits") or 0) + 1
            entry["lastUsedAt"] = _now()
            self._save()
            return copy.deepcopy(entry.get("value", default))

    def has(self, key: Any) -> bool:
        normalized = self._key(key)
        with self._lock:
            return normalized in self._data["entries"]

    def set(self, key: Any, value: Any, *, source: str = "lua") -> Any:
        normalized = self._key(key)
        safe_value = self._json_copy(value)
        with self._lock:
            entries = self._data["entries"]
            old = entries.get(normalized)
            created = old.get("createdAt", _now()) if isinstance(old, dict) else _now()
            entries[normalized] = {
                "value": safe_value,
                "source": str(source or "lua")[:80],
                "createdAt": created,
                "updatedAt": _now(),
                "lastUsedAt": _now(),
                "hits": int(old.get("hits") or 0) if isinstance(old, dict) else 0,
            }
            while len(entries) > self.max_entries:
                oldest = min(
                    entries.items(),
                    key=lambda item: str(item[1].get("lastUsedAt", ""))
                    if isinstance(item[1], dict)
                    else "",
                )[0]
                entries.pop(oldest, None)
            self._data["updatedAt"] = _now()
            self._save()
        return copy.deepcopy(safe_value)

    def delete(self, key: Any) -> bool:
        normalized = self._key(key)
        with self._lock:
            removed = self._data["entries"].pop(normalized, None) is not None
            if removed:
                self._data["updatedAt"] = _now()
                self._save()
            return removed

    def list(self, *, limit: int = 50) -> list[dict[str, Any]]:
        size = max(1, min(100, int(limit or 50)))
        with self._lock:
            rows = []
            for key, entry in self._data["entries"].items():
                if isinstance(entry, dict):
                    rows.append({"key": key, **copy.deepcopy(entry)})
            rows.sort(key=lambda row: str(row.get("lastUsedAt", "")), reverse=True)
            return rows[:size]

    def clear(self) -> None:
        with self._lock:
            self._data = self._empty()
            self._save()


__all__ = ["LuaMemoryError", "NetOpsLuaMemory"]