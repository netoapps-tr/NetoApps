"""NetoPilot safe PC-control extension contract.

The host owns the actual system adapters.  This module only registers
allow-listed actions and never imports subprocess, os, ctypes or shell APIs.
"""
from __future__ import annotations


PLUGIN_ID = "netopilot"

SAFE_ACTIONS = (
    ("system status", "Bilgisayar durumunu göster", "system_status"),
    ("program aç", "İzin verilen bir programı aç", "launch_program"),
    ("ses ayarla", "Sistem sesini ayarla", "set_volume"),
    ("pencereyi taşı", "Bir pencereyi seçilen ekrana taşı", "move_window"),
)


def register(api):
    api.register_panel(PLUGIN_ID, title="NetoPilot", icon="control")
    for phrase, description, action in SAFE_ACTIONS:
        api.register_command(phrase, description, action, PLUGIN_ID)
    return {"id": PLUGIN_ID, "registered": True, "actions": len(SAFE_ACTIONS)}
