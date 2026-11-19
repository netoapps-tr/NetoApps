"""NetoPlay extension contract.

The host owns the real media UI.  This extension only asks the host API for
approved callbacks, so importing the package cannot open windows or start
processes by itself.
"""
from __future__ import annotations


PLUGIN_ID = "netoplay"


def register(api):
    """Register declarative actions with a future NetOpsPluginAPI host."""
    api.register_panel(PLUGIN_ID, title="NetoPlay", icon="music")
    api.register_command("now playing", "NetoPlay ekranını aç", "open_panel", PLUGIN_ID)
    api.register_command("şimdi çalıyor", "NetoPlay ekranını aç", "open_panel", PLUGIN_ID)
    return {"id": PLUGIN_ID, "registered": True}
