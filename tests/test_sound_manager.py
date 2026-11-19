from pathlib import Path
import tempfile

from neto_sound_manager import (
    clear_sound_override,
    resolve_sound,
    save_sound_override,
)


def test_sound_override_is_copied_to_user_directory():
    with tempfile.TemporaryDirectory() as raw:
        tmp_path = Path(raw)
        source = tmp_path / "warning.mp3"
        source.write_bytes(b"fake-audio")

        saved = save_sound_override("recovery_warning", source, user_dir=tmp_path / "user")

        assert saved.exists()
        assert saved.read_bytes() == b"fake-audio"
        assert resolve_sound("recovery_warning", tmp_path, user_dir=tmp_path / "user") == saved


def test_sound_override_rejects_unknown_role_and_extension():
    with tempfile.TemporaryDirectory() as raw:
        tmp_path = Path(raw)
        source = tmp_path / "warning.exe"
        source.write_bytes(b"not-audio")

        for role, path in (("shell", source), ("recovery_warning", source)):
            try:
                save_sound_override(role, path, user_dir=tmp_path / "user")
            except ValueError:
                continue
            raise AssertionError("invalid sound override was accepted")


def test_clear_sound_override_removes_only_selected_role():
    with tempfile.TemporaryDirectory() as raw:
        tmp_path = Path(raw)
        source = tmp_path / "warning.wav"
        source.write_bytes(b"fake-audio")
        saved = save_sound_override("recovery_warning", source, user_dir=tmp_path / "user")

        clear_sound_override("recovery_warning", user_dir=tmp_path / "user")

        assert not saved.exists()
