from __future__ import annotations

from unittest.mock import patch

from neto_remote_pc_actions import (
    handle_remote_pc_command,
    handle_remote_input,
    parse_open_program,
    program_catalog,
)


def test_program_catalog_contains_useful_allowlisted_apps() -> None:
    catalog = program_catalog()

    assert {"chrome", "edge", "vscode", "spotify", "notepad", "calculator"}.issubset(catalog)


def test_open_program_parser_rejects_unknown_programs() -> None:
    assert parse_open_program("PC'de Chrome aç") == "chrome"
    assert parse_open_program("PC'de rastgele.exe çalıştır") is None


def test_open_program_uses_only_resolved_allowlisted_executable() -> None:
    with patch("neto_remote_pc_actions._resolve_executable", return_value=r"C:\Apps\chrome.exe") as resolver:
        with patch("neto_remote_pc_actions.subprocess.Popen") as popen:
            result = handle_remote_pc_command("chrome aç")

    assert result["ok"] is True
    assert result["program"] == "chrome"
    resolver.assert_called_once()
    popen.assert_called_once()
    assert popen.call_args.args[0] == [r"C:\Apps\chrome.exe"]


def test_unknown_remote_pc_command_is_not_executed() -> None:
    with patch("neto_remote_pc_actions.subprocess.Popen") as popen:
        result = handle_remote_pc_command("gizli.exe çalıştır")

    assert result["ok"] is False
    assert result["error"] == "PROGRAM_NOT_ALLOWED"
    popen.assert_not_called()


def test_input_shortcuts_allow_safe_apps_and_navigation_keys() -> None:
    with patch("neto_remote_pc_actions.open_program", return_value={"ok": True, "program": "chrome", "title": "Google Chrome"}):
        assert handle_remote_input("c")["program"] == "chrome"
    with patch("neto_remote_pc_actions._send_virtual_key", return_value=True):
        assert handle_remote_input("up")["key"] == "up"


def test_input_shortcuts_never_execute_unknown_letters() -> None:
    result = handle_remote_input("z")

    assert result["ok"] is False
    assert result["error"] == "INPUT_KEY_NOT_ALLOWED"
