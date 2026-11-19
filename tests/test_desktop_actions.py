from __future__ import annotations

from neto_desktop_actions import execute_hotkey, focus_window


def test_desktop_actions_are_allowlisted() -> None:
    result = execute_hotkey("arbitrary_key_sequence")
    assert result["ok"] is False


def test_focus_window_rejects_empty_title() -> None:
    result = focus_window("")
    assert result["ok"] is False
