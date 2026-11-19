from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_remote_surface_exposes_safe_termux_actions():
    source = (ROOT / "neto_remote_surface.py").read_text(encoding="utf-8")
    assert "REMOTE_GIF_NAME" in source
    assert "Termux" in source
    assert "device_hub_set_input_handler" in source
    assert "_remote_input_request" in source
    assert "request_status" in source
    assert "install_termux_shell" in source
    assert "register_termux_device" in source
    assert "Termux sohbeti" in source
    assert '"assistant_request"' in source


def test_termux_agent_accepts_authenticated_remote_chat_commands():
    source = (ROOT / "mobile" / "termux" / "netops_shell.py").read_text(encoding="utf-8")
    assert "_handle_server_command" in source
    assert '"command_result"' in source
    assert '"assistant_request"' in source


def test_termux_remote_chat_is_read_only_and_local():
    import importlib.util

    path = ROOT / "mobile" / "termux" / "netops_shell.py"
    spec = importlib.util.spec_from_file_location("netops_termux_shell_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module._handle_server_command({"command": "assistant_request", "args": {"text": "Termux durumu"}})
    assert result["ok"] is True
    assert "Termux aktif" in result["display_text"]
    blocked = module._handle_server_command({"command": "shell", "args": {"text": "rm -rf /"}})
    assert blocked == {"ok": False, "error": "UNKNOWN_COMMAND"}


def test_remote_surface_does_not_offer_arbitrary_shell_execution():
    source = (ROOT / "neto_remote_surface.py").read_text(encoding="utf-8")
    assert "subprocess" not in source
    assert "shell=True" not in source


def test_main_ui_routes_visible_device_entries_to_remote():
    source = (ROOT / "asistan beta.py").read_text(encoding="utf-8")
    assert "NetOps Remote" in source
    assert "neto_remote_surface_launch_safe" in source
    assert '"Cihazlar" if tr else "Devices"' not in source
