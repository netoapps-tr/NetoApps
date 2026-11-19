from __future__ import annotations

import json
from pathlib import Path

import neto_power_features as power
from neto_command_palette import _commands


def test_power_status_is_local_and_has_allowlisted_integrations():
    report = power.status_report()
    assert {item["id"] for item in report["features"]} >= {
        "command_palette",
        "device_hub",
        "screen_capture",
        "activity_watch",
        "snippets",
    }
    assert {item["id"] for item in report["integrations"]} >= {
        "flow_launcher",
        "powertoys",
        "kde_connect",
        "obs",
    }


def test_snippets_are_atomic_and_local(tmp_path, monkeypatch):
    path = tmp_path / "snippets.json"
    monkeypatch.setattr(power, "SNIPPETS_PATH", path)
    power.save_snippet(":hello", "Merhaba NetOps")
    assert power.expand_snippet(":hello") == "Merhaba NetOps"
    assert json.loads(path.read_text(encoding="utf-8"))[":hello"] == "Merhaba NetOps"


def test_activity_is_opt_in(tmp_path, monkeypatch):
    path = tmp_path / "activity.json"
    monkeypatch.setattr(power, "ACTIVITY_PATH", path)
    monkeypatch.setenv("NETOPS_ACTIVITY_ENABLED", "0")
    assert power.record_activity("test") is False
    assert power.activity_summary() == []
    monkeypatch.setenv("NETOPS_ACTIVITY_ENABLED", "1")
    assert power.record_activity("test", title="window") is True
    assert power.activity_summary()[0] == {"app": "test", "events": 1}


def test_sync_manifest_does_not_copy_files(tmp_path):
    (tmp_path / "one.txt").write_text("one", encoding="utf-8")
    manifest = power.create_sync_manifest(tmp_path)
    assert manifest["root"] == str(tmp_path.resolve())
    assert manifest["files"][0]["path"] == "one.txt"


def test_optional_app_rejects_arbitrary_commands():
    result = power.open_optional_app("arbitrary-command")
    assert result["ok"] is False


def test_command_palette_exposes_power_features():
    commands = _commands({"__file__": str(Path(__file__))})
    ids = {item["id"] for item in commands}
    assert {"power_center_status", "capture_screen", "activity_summary", "open_obs"} <= ids
