"""Small, permission-aware host API exposed to NetOps extensions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class RegisteredCommand:
    phrase: str
    description: str
    action: str
    plugin_id: str


ACTION_PERMISSIONS = {
    "open_panel": "panel_open",
    "system_status": "system_status",
    "launch_program": "program_launch",
    "set_volume": "audio_control",
    "move_window": "window_management",
}


class NetOpsPluginAPI:
    """Host boundary for plugins; it contains no shell or process fallback."""

    def __init__(self, *, handlers: dict[str, Callable[..., Any]] | None = None, permission_manager=None):
        self.handlers = dict(handlers or {})
        self.permission_manager = permission_manager
        self.panels: dict[str, dict[str, Any]] = {}
        self.commands: list[RegisteredCommand] = []

    def register_panel(self, plugin_id: str, *, title: str, icon: str = "extension") -> None:
        self.panels[str(plugin_id)] = {"title": str(title), "icon": str(icon)}

    def register_command(self, phrase: str, description: str, action: str, plugin_id: str) -> None:
        if action not in ACTION_PERMISSIONS:
            raise ValueError(f"İzin tanımı olmayan eylem: {action}")
        self.commands.append(RegisteredCommand(str(phrase), str(description), str(action), str(plugin_id)))

    def invoke(self, action: str, *args, ask_callback=None, **kwargs):
        action = str(action)
        permission = ACTION_PERMISSIONS.get(action)
        handler = self.handlers.get(action)
        if permission is None or handler is None:
            return {"ok": False, "error": "Eylem host tarafından kullanılamıyor."}
        if self.permission_manager is not None:
            allowed = self.permission_manager.require(
                permission,
                context=f"plugin_action:{action}",
                ask_callback=ask_callback,
            )
            if not allowed:
                return {"ok": False, "error": "Bu eylem için izin verilmedi.", "permission": permission}
        try:
            return {"ok": True, "result": handler(*args, **kwargs)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


__all__ = ["ACTION_PERMISSIONS", "NetOpsPluginAPI", "RegisteredCommand"]
