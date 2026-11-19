from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from mobile.termux import netops_shell


def test_normalize_endpoint_accepts_local_host_and_websocket_scheme() -> None:
    assert netops_shell.normalize_endpoint("192.168.1.20:8765") == "ws://192.168.1.20:8765/"
    assert netops_shell.normalize_endpoint("ws://netops-pc:8765") == "ws://netops-pc:8765/"


def test_normalize_endpoint_rejects_non_websocket_scheme() -> None:
    with pytest.raises(ValueError, match="ws"):
        netops_shell.normalize_endpoint("https://example.com")


def test_build_hello_uses_pairing_code_without_leaking_saved_token() -> None:
    message = netops_shell.build_hello(
        device_name="Test Telefon",
        pairing_code="123456",
        device_id="",
        token="",
    )

    assert message["type"] == "hello"
    assert message["pairing_code"] == "123456"
    assert "token" not in message
    assert message["network"]["type"] == "local_wifi"
    assert message["capabilities"]["assistant_request"] is True


def test_build_hello_reconnects_with_device_token() -> None:
    message = netops_shell.build_hello(
        device_name="Test Telefon",
        pairing_code="",
        device_id="netops_abc",
        token="secret-token",
    )

    assert message["device_id"] == "netops_abc"
    assert message["token"] == "secret-token"
    assert "pairing_code" not in message


def test_config_round_trip_uses_only_expected_fields(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    netops_shell.save_config(
        {
            "endpoint": "ws://192.168.1.20:8765/",
            "device_id": "netops_abc",
            "token": "secret-token",
            "unexpected": "must not be persisted",
        },
        path,
    )

    loaded = netops_shell.load_config(path)

    assert loaded == {
        "endpoint": "ws://192.168.1.20:8765/",
        "device_id": "netops_abc",
        "token": "secret-token",
    }
    assert "unexpected" not in json.loads(path.read_text(encoding="utf-8"))


def test_client_frame_is_masked_and_can_be_decoded() -> None:
    frame = netops_shell.encode_client_text('{"type":"ping"}', mask=b"1234")
    opcode, payload = netops_shell.decode_frame_from_socket(_BytesSocket(frame))

    assert opcode == 1
    assert payload == b'{"type":"ping"}'


def test_parse_cli_supports_remote_assistant_request() -> None:
    args = netops_shell.parse_args(["ask", "sistem durumunu göster"])

    assert args.command == "ask"
    assert args.text == ["sistem durumunu göster"]


def test_parse_cli_supports_direct_system_shortcuts() -> None:
    assert netops_shell.parse_args(["ram"]).command == "ram"
    assert netops_shell.parse_args(["cpu"]).command == "cpu"
    assert netops_shell.parse_args(["disk"]).command == "disk"
    assert netops_shell.parse_args(["battery"]).command == "battery"
    assert netops_shell.parse_args(["commands"]).command == "commands"
    assert netops_shell.parse_args(["ağ"]).command == "network"
    assert netops_shell.parse_args(["uptime"]).command == "uptime"
    assert netops_shell.parse_args(["reboot"]).command == "reboot"
    assert netops_shell.parse_args(["kapat"]).command == "poweroff"
    assert netops_shell.parse_args(["çekirdek-yenile"]).command == "core-restart"
    assert netops_shell.parse_args(["recovery"]).command == "recovery"
    assert netops_shell.parse_args(["kurtarma"]).command == "recovery"


def test_recovery_cli_has_a_phone_screen_flow() -> None:
    result = {"ok": True, "display_text": "Telefondan onayla yazın."}
    assert netops_shell._run_recovery_phone_screen
    assert "onayla" in result["display_text"]


def test_termux_install_copies_recovery_screen_module() -> None:
    source = (Path(__file__).resolve().parents[1] / "mobile" / "termux" / "netops_shell.py").read_text(encoding="utf-8")
    assert "neto_termux_recovery_ui.py" in source


def test_parse_cli_supports_persistent_agent_mode() -> None:
    args = netops_shell.parse_args(["agent", "--background", "--name", "Telefonum"])

    assert args.command == "agent"
    assert args.name == "Telefonum"
    assert args.background is True


def test_parse_cli_supports_now_playing_watch_mode() -> None:
    args = netops_shell.parse_args(["now-playing", "--watch", "--interval", "5"])

    assert args.command == "now-playing"
    assert args.watch is True
    assert args.interval == 5.0


def test_parse_cli_supports_persistent_install_command() -> None:
    assert netops_shell.parse_args(["install"]).command == "install"


def test_parse_cli_supports_remote_pc_commands() -> None:
    open_args = netops_shell.parse_args(["open", "chrome"])
    assert open_args.command == "open"
    assert open_args.program == ["chrome"]
    assert netops_shell.parse_args(["lock"]).command == "lock"
    assert netops_shell.parse_args(["pc-commands"]).command == "pc-commands"


def test_parse_cli_supports_safe_remote_keyboard_mode() -> None:
    key_args = netops_shell.parse_args(["key", "up"])
    control_args = netops_shell.parse_args(["control"])

    assert key_args.command == "key"
    assert key_args.key == "up"
    assert control_args.command == "control"


def test_parse_cli_supports_turkish_command_aliases() -> None:
    assert netops_shell.parse_args(["durum"]).command == "status"
    assert netops_shell.parse_args(["komutlar"]).command == "commands"
    assert netops_shell.parse_args(["cihazlar"]).command == "devices"
    assert netops_shell.parse_args(["aç", "chrome"]).command == "open"
    assert netops_shell.parse_args(["kilitle"]).command == "lock"
    assert netops_shell.parse_args(["masaüstü"]).command == "desktop"
    assert netops_shell.parse_args(["şimdi-çalan"]).command == "now-playing"
    assert netops_shell.parse_args(["oynat-duraklat"]).command == "play-pause"
    assert netops_shell.parse_args(["oynat"]).command == "play-pause"
    assert netops_shell.parse_args(["duraklat"]).command == "play-pause"
    assert netops_shell.parse_args(["cal"]).command == "play-pause"
    assert netops_shell.parse_args(["sonraki"]).command == "next"


class _BytesSocket:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def recv(self, size: int) -> bytes:
        if not self._data:
            return b""
        chunk, self._data = self._data[:size], self._data[size:]
        return chunk
