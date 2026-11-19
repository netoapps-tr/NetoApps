from pathlib import Path


def test_entrypoint_has_explicit_native_qt_opt_in():
    source = Path("asistan beta.py").read_text(encoding="utf-8-sig")

    assert "NETOPS_QT_UI" in source
    assert "run_native_qt_app" in source
    assert "build_qt_backend" in source
    assert "NetOpsTextAssistant" in source
    assert "_qt_text_assistant.respond" in source
    assert "chat_reader=_qt_text_assistant.respond" in source
    assert "command_runner=lokal_sistem_islemcisi" in source
    assert "media_control_runner=_qt_media_control" in source
    assert "settings_reader=veri_yukle" in source
    assert "settings_writer=_qt_save_settings" in source
    assert "_qt_devices" in source


def test_native_qt_is_the_default_and_legacy_requires_an_explicit_flag():
    source = Path("asistan beta.py").read_text(encoding="utf-8-sig")

    assert 'os.environ.get("NETOPS_QT_UI", "1") == "1"' in source
    assert 'os.environ.get("NETOPS_LEGACY_UI", "0") != "1"' in source
