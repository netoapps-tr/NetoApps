from pathlib import Path
import tempfile

from neto_recovery_surface import (
    build_boot_lines,
    is_recovery_cancellation,
    is_recovery_confirmation,
    is_recovery_command,
    is_recovery_exit,
    recovery_confirmation_prompt,
    recovery_command_answer,
    transition_asset_path,
)


ROOT = Path(__file__).resolve().parents[1]


def test_recovery_command_has_explicit_name():
    assert is_recovery_command("/recovery Netops") is True
    assert is_recovery_command("recovery netops") is True
    assert is_recovery_command("recovery") is False


def test_recovery_confirmation_is_explicit_and_localized():
    assert is_recovery_confirmation("onayla") is True
    assert is_recovery_confirmation("EVET") is True
    assert is_recovery_confirmation("recovery onayla") is True
    assert is_recovery_confirmation("başlat") is False
    assert is_recovery_cancellation("iptal") is True
    assert is_recovery_cancellation("hayır") is True
    assert "onayla" in recovery_confirmation_prompt().casefold()


def test_recovery_exit_is_explicit_and_localized():
    assert is_recovery_exit("çıkış") is True
    assert is_recovery_exit("cikis") is True
    assert is_recovery_exit("kapat") is True
    assert is_recovery_exit("exit") is True
    assert is_recovery_exit("ana ekranı aç") is False


def test_recovery_boot_is_a_ten_second_visual_sequence():
    lines = build_boot_lines(10)
    assert len(lines) == 10
    assert lines[0].startswith("RECOVERY NETOPS")
    assert lines[-1].startswith("RECOVERY NETOPS")
    assert all("[" in line and "]" in line for line in lines)


def test_recovery_transition_uses_remote_logo_asset():
    asset = transition_asset_path(ROOT)
    assert asset.name == "Remote.gif"
    assert asset.is_file()


def test_recovery_chat_only_accepts_allowlisted_read_only_commands():
    with tempfile.TemporaryDirectory() as temp_dir:
        status = recovery_command_answer("durum", temp_dir)
        assert "Recovery Mesh" in status
        blocked = recovery_command_answer("shell rm -rf /", temp_dir)
        assert "izinli" in blocked.casefold()


def test_main_routes_recovery_mode_without_virtual_desktop():
    source = (ROOT / "asistan beta.py").read_text(encoding="utf-8")
    assert "neto_recovery_surface_launch_safe" in source
    assert "root.withdraw()" in source
    assert "_NETO_RECOVERY_CONFIRMATION_PENDING" in source
    assert "recovery_confirmation_prompt" in source
    assert "show_recovery_transition" in source
    assert "duration_ms=3000" in source
    assert "request_recovery_close" in source


def test_recovery_surface_launch_is_deferred_before_tk_mutation():
    source = (ROOT / "asistan beta.py").read_text(encoding="utf-8")
    start = source.index("def neto_recovery_surface_launch_safe")
    end = source.index("def neto_recovery_assistant_request", start)
    block = source[start:end]
    assert "app_root.after(0, _open_recovery)" in block
    withdraw_line = next(line for line in block.splitlines() if "app_root.withdraw()" in line)
    schedule_line = next(line for line in block.splitlines() if "app_root.after(0, _open_recovery)" in line)
    assert len(withdraw_line) - len(withdraw_line.lstrip()) > len(schedule_line) - len(schedule_line.lstrip())
