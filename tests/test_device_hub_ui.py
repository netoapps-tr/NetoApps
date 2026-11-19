from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_device_hub_ui_registers_live_handlers_before_opening() -> None:
    source = (PROJECT_ROOT / "asistan beta.py").read_text(encoding="utf-8")
    start = source.index("def neto_device_hub_ac_safe")
    end = source.index("def neto_power_center_ac_safe", start)
    block = source[start:end]

    assert "device_hub_set_assistant_handler(neto_remote_assistant_request)" in block
    assert "device_hub_set_media_handler(neto_remote_media_request)" in block
    assert "device_hub_set_input_handler(neto_remote_input_request)" in block


def test_remote_hub_binds_all_local_interfaces_for_usb_reverse() -> None:
    source = (PROJECT_ROOT / "asistan beta.py").read_text(encoding="utf-8")
    start = source.index("def neto_remote_hub_start_safe")
    end = source.index("def ", start + len("def neto_remote_hub_start_safe"))
    block = source[start:end]

    assert 'device_hub_start(host="0.0.0.0", port=8765)' in block


def test_device_hub_requires_explicit_plus_action_for_new_usb_devices() -> None:
    source = (PROJECT_ROOT / "neto_device_hub.py").read_text(encoding="utf-8")

    assert 'text="+ Cihaz Ekle"' in source
    assert "unregistered_authorized_usb_devices" in source
    assert "register_termux_device" in source


def test_usb_reconnect_watcher_is_not_hidden_behind_optional_background_services() -> None:
    source = (PROJECT_ROOT / "asistan beta.py").read_text(encoding="utf-8")
    marker = "root.after(5200, _neto_android_watch_deferred)"
    position = source.index(marker)
    nearby = source[max(0, position - 180) : position]

    assert marker in source
    assert "if _NETOPS_BACKGROUND_SERVICES_ENABLED:" not in nearby
    assert "start_android_usb_autoconnect" in source


def test_remote_hub_start_is_independent_from_optional_background_watchers() -> None:
    source = (PROJECT_ROOT / "asistan beta.py").read_text(encoding="utf-8")
    marker = "root.after(5000, _neto_remote_hub_watchdog_schedule)"
    position = source.index(marker)
    nearby = source[max(0, position - 240) : position]

    assert marker in source
    assert "neto_remote_hub_watchdog()" in nearby
    assert "if _NETOPS_BACKGROUND_SERVICES_ENABLED:" not in nearby


def test_remote_assistant_has_direct_system_command_router() -> None:
    source = (PROJECT_ROOT / "asistan beta.py").read_text(encoding="utf-8")

    assert "def _netops_remote_command_answer" in source
    assert "neto_system_metrics(force=True)" in source
    assert "device_hub_snapshot()" in source
    assert "online" in source


def test_remote_assistant_routes_turkish_media_shortcuts() -> None:
    source = (PROJECT_ROOT / "asistan beta.py").read_text(encoding="utf-8")
    start = source.index("def _netops_remote_command_answer")
    end = source.index("def neto_remote_assistant_request", start)
    block = source[start:end]

    assert "sarki oynat" in block
    assert "play_pause" in block
    assert "neto_remote_media_request" in block


def test_media_requests_refresh_device_liveness() -> None:
    source = (PROJECT_ROOT / "neto_device_hub.py").read_text(encoding="utf-8")
    start = source.index('if kind == "media_request":')
    end = source.index('if kind == "capabilities":', start)
    block = source[start:end]

    assert 'record["last_seen"] = time.time()' in block
    assert 'record["online"] = True' in block


def test_remote_virtual_desktop_commands_precede_desktop_folder_shortcut() -> None:
    source = (PROJECT_ROOT / "asistan beta.py").read_text(encoding="utf-8-sig")
    start = source.index("def _netops_remote_command_answer")
    end = source.index("def neto_remote_assistant_request", start)
    block = source[start:end]

    assert "neto_virtual_desktop.handle_command" in block
    assert block.index("neto_virtual_desktop.handle_command") < block.index("media_action = None")


def test_desktop_and_remote_paths_share_builtin_skill_catalog() -> None:
    source = (PROJECT_ROOT / "asistan beta.py").read_text(encoding="utf-8")

    assert "def _netops_builtin_skill_answer" in source
    assert "_netops_builtin_skill_answer(komut_metni)" in source
    assert "_netops_builtin_skill_answer(str(text or \"\"), device_id)" in source
