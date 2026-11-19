"""Shared safe registration contract for the first-party NetOps extensions."""
from __future__ import annotations


def register_builtin_panel(api, plugin_id: str, title: str, icon: str):
    api.register_panel(plugin_id, title=title, icon=icon)
    return {"id": plugin_id, "registered": True, "mode": "panel_contract"}
