from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

from neto_lua_memory import LuaMemoryError, NetOpsLuaMemory
from neto_lua_plugins import NetOpsLuaPluginManager
from neto_lua_runtime import LuaRuntimeUnavailable, NetOpsLuaRuntime


class LuaKernelError(RuntimeError):
    """Raised when the persistent Lua event kernel cannot load or dispatch."""


class NetOpsLuaKernel:
    """Persistent, sandboxed Lua event bus with plugins and JSON memory."""

    def __init__(
        self,
        *,
        notify: Optional[Callable[[str, str], Any]] = None,
        memory_path: str | Path | None = None,
        plugin_dir: str | Path | None = None,
        auto_load_plugins: bool = True,
    ) -> None:
        try:
            self.runtime = NetOpsLuaRuntime()
        except Exception as exc:
            raise LuaKernelError("Lua 5.4 çekirdeği kullanılamıyor.") from exc
        self._lua = self.runtime._lua
        self._lock = threading.RLock()
        self._handlers: dict[str, list[Any]] = {}
        self._events: list[str] = []
        self._notify_callback = notify
        self.memory = NetOpsLuaMemory(memory_path)

        netops = self._lua.table()
        netops["on"] = self._register_handler
        netops["emit"] = self._emit_from_lua
        netops["log"] = self._log
        netops["notify"] = self._notify
        netops["now"] = time.time

        memory = self._lua.table()
        memory["get"] = self._memory_get
        memory["has"] = self._memory_has
        memory["set"] = self._memory_set
        memory["delete"] = self._memory_delete
        memory["list"] = self._memory_list
        netops["memory"] = memory

        self._lua.globals()["netops"] = netops
        self._lua.globals()["context"] = self.runtime._to_lua({})

        bundled_plugins = Path(__file__).resolve().with_name("lua") / "plugins"
        user_plugins = self.memory.path.parent / "lua" / "plugins"
        default_plugins = plugin_dir or [bundled_plugins, user_plugins]
        self.plugins = NetOpsLuaPluginManager(self, default_plugins)
        if auto_load_plugins:
            self.plugins.load_all()

    def _register_handler(self, event: Any, handler: Any) -> bool:
        name = str(event or "").strip()
        if not name or not callable(handler):
            raise ValueError("netops.on(event, handler) geçerli bir olay ve fonksiyon ister.")
        with self._lock:
            self._handlers.setdefault(name, []).append(handler)
        return True

    def _log(self, message: Any = "") -> None:
        value = str(message)
        with self._lock:
            self._events.append(value)

    def _notify(self, title: Any = "NetOps", message: Any = "") -> None:
        if callable(self._notify_callback):
            self._notify_callback(str(title), str(message))

    def _memory_get(self, key: Any, default: Any = None) -> Any:
        value = self.memory.get(key, self.runtime._to_python(default))
        return self.runtime._to_lua(value)

    def _memory_has(self, key: Any) -> bool:
        return self.memory.has(key)

    def _memory_set(self, key: Any, value: Any, source: Any = "lua") -> Any:
        python_value = self.runtime._to_python(value)
        stored = self.memory.set(key, python_value, source=str(source or "lua"))
        return self.runtime._to_lua(stored)

    def _memory_delete(self, key: Any) -> bool:
        return self.memory.delete(key)

    def _memory_list(self, limit: Any = 50) -> Any:
        return self.runtime._to_lua(self.memory.list(limit=int(limit or 50)))

    def _emit_from_lua(self, event: Any, payload: Any = None) -> dict[str, Any]:
        return self.emit(str(event or ""), self.runtime._to_python(payload or {}))

    def emit(self, event: str, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        name = str(event or "").strip()
        if not name:
            raise ValueError("Lua olayı adı boş bırakılamaz.")
        data = payload if isinstance(payload, dict) else {"value": payload}
        results: list[Any] = []
        with self._lock:
            handlers = list(self._handlers.get(name, ()))
        lua_payload = self.runtime._to_lua(data)
        for handler in handlers:
            try:
                results.append(self.runtime._to_python(handler(lua_payload)))
            except Exception as exc:
                raise LuaKernelError(f"Lua olayı başarısız: {name}: {exc}") from exc
        return {"event": name, "handled": len(handlers), "results": results, "events": self.drain_events()}

    def execute(self, script: str, *, context: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        source = str(script or "").strip()
        if not source:
            raise ValueError("Lua scripti boş bırakılamaz.")
        with self._lock:
            self._lua.globals()["context"] = self.runtime._to_lua(context or {})
            try:
                result = self._lua.execute(source)
            except Exception as exc:
                raise LuaKernelError(f"Lua scripti başarısız: {exc}") from exc
        return {"result": self.runtime._to_python(result), "events": self.drain_events()}

    def load_file(self, path: str | Path, *, context: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        script_path = Path(path)
        if not script_path.is_file():
            raise FileNotFoundError(script_path)
        return self.execute(script_path.read_text(encoding="utf-8"), context=context)

    def list_plugins(self) -> list[dict[str, Any]]:
        return self.plugins.list()

    def drain_events(self) -> list[str]:
        with self._lock:
            events = list(self._events)
            self._events.clear()
            return events


def create_default_kernel(
    *,
    notify: Optional[Callable[[str, str], Any]] = None,
    memory_path: str | Path | None = None,
    plugin_dir: str | Path | None = None,
) -> NetOpsLuaKernel:
    kernel = NetOpsLuaKernel(
        notify=notify,
        memory_path=memory_path,
        plugin_dir=plugin_dir,
    )
    hooks = Path(__file__).resolve().with_name("lua") / "netops_hooks.lua"
    if hooks.is_file():
        kernel.load_file(hooks)
    return kernel


__all__ = [
    "LuaKernelError",
    "NetOpsLuaKernel",
    "create_default_kernel",
    "LuaRuntimeUnavailable",
    "LuaMemoryError",
]