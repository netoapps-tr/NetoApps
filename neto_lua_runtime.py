from __future__ import annotations

import time
from typing import Any, Callable


class LuaRuntimeUnavailable(RuntimeError):
    """Raised when the optional embedded Lua runtime is not available."""


def _load_lua_runtime():
    try:
        from lupa.lua54 import LuaRuntime
        from lupa import lua_type
    except Exception as exc:
        raise LuaRuntimeUnavailable("Lua 5.4 runtime kurulmamış.") from exc
    return LuaRuntime, lua_type


class NetOpsLuaRuntime:
    """Small sandboxed Lua 5.4 runtime for automation worker actions."""

    def __init__(self, *, max_memory: int = 8 * 1024 * 1024):
        LuaRuntime, self._lua_type = _load_lua_runtime()
        try:
            self._lua = LuaRuntime(
                unpack_returned_tuples=True,
                register_eval=False,
                register_builtins=False,
                max_memory=max_memory,
            )
        except TypeError:
            self._lua = LuaRuntime(
                unpack_returned_tuples=True,
                register_eval=False,
                register_builtins=False,
            )
        self._remove_unsafe_globals()

    def _remove_unsafe_globals(self) -> None:
        globals_table = self._lua.globals()
        for name in (
            "os",
            "io",
            "debug",
            "package",
            "require",
            "dofile",
            "loadfile",
            "load",
        ):
            globals_table[name] = None

    def _to_lua(self, value: Any):
        if isinstance(value, dict):
            table = self._lua.table()
            for key, item in value.items():
                table[str(key)] = self._to_lua(item)
            return table
        if isinstance(value, (list, tuple)):
            table = self._lua.table()
            for index, item in enumerate(value, 1):
                table[index] = self._to_lua(item)
            return table
        return value

    def _to_python(self, value: Any, depth: int = 0) -> Any:
        if depth > 8:
            return "<max-depth>"
        if isinstance(value, (dict, list, tuple, str, bytes, int, float, bool)) or value is None:
            return value
        try:
            items = value.items()
        except Exception:
            return value
        result = {}
        for key, item in items:
            result[str(key)] = self._to_python(item, depth + 1)
        return result

    def execute(
        self,
        script: str,
        *,
        context: dict[str, Any] | None = None,
        notify: Callable[[str, str], Any] | None = None,
    ) -> dict[str, Any]:
        script = str(script or "").strip()
        if not script:
            raise ValueError("Lua scripti boş bırakılamaz.")
        events: list[str] = []

        def log(message: Any = "") -> None:
            events.append(str(message))

        def send_notification(title: Any = "NetOps", message: Any = "") -> None:
            if callable(notify):
                notify(str(title), str(message))

        netops = self._lua.table()
        netops["log"] = log
        netops["notify"] = send_notification
        netops["now"] = time.time
        globals_table = self._lua.globals()
        globals_table["netops"] = netops
        globals_table["context"] = self._to_lua(context or {})
        result = self._lua.execute(script)
        return {"result": self._to_python(result), "events": events}


def run_lua_script(
    script: str,
    *,
    context: dict[str, Any] | None = None,
    notify: Callable[[str, str], Any] | None = None,
) -> dict[str, Any]:
    return NetOpsLuaRuntime().execute(script, context=context, notify=notify)


__all__ = ["LuaRuntimeUnavailable", "NetOpsLuaRuntime", "run_lua_script"]