from __future__ import annotations

import neto_android_device


def test_termux_install_command_is_local_and_dependency_free() -> None:
    assert neto_android_device.build_termux_install_command() == "python /sdcard/netops_shell.py install"


def test_termux_pair_command_contains_device_name_and_code() -> None:
    command = neto_android_device.build_termux_pair_command(
        "127.0.0.1:8765",
        "123456",
        "Telefonum",
    )

    assert command == (
        "netops pair --host 127.0.0.1:8765 --code 123456 --name Telefonum"
    )


def test_termux_agent_reconnect_preserves_device_name() -> None:
    assert neto_android_device.build_termux_agent_command("Telefonum", background=True) == "netops agent --background --name Telefonum"


def test_adb_input_text_encodes_spaces_without_shell_execution() -> None:
    encoded = neto_android_device.encode_adb_input_text("netops install --name Telefonum")

    assert encoded == "netops%sinstall%s--name%sTelefonum"
    assert ";" not in encoded
    assert "&" not in encoded


def test_unknown_usb_devices_are_not_auto_connected() -> None:
    devices = [
        {"serial": "known", "state": "device"},
        {"serial": "new", "state": "device"},
        {"serial": "unauthorized", "state": "unauthorized"},
    ]

    result = neto_android_device.unregistered_authorized_usb_devices(
        devices,
        {"known": {"name": "Telefonum"}},
    )

    assert [item["serial"] for item in result] == ["new"]
