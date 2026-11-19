from neto_command_arena import CommandArenaModel, classify_command
from pathlib import Path


def test_command_arena_classifies_safe_command_stream():
    assert classify_command("RAM durumunu söyle", {"ok": True}) == "status"
    assert classify_command("şarkıyı duraklat", {"ok": True}) == "media"
    assert classify_command("recovery durum", {"ok": True}) == "recovery"
    assert classify_command("bilinmeyen işlem", {"ok": False}) == "error"


def test_command_arena_keeps_latest_events_and_counts_health():
    arena = CommandArenaModel(max_events=2)
    arena.record("RAM durumunu söyle", "Telefonum", {"ok": True, "display_text": "RAM %42"})
    arena.record("şarkıyı duraklat", "Telefonum", {"ok": True, "display_text": "Duraklatıldı"})
    arena.record("bilinmeyen işlem", "Telefonum", {"ok": False, "display_text": "Reddedildi"})

    events = arena.snapshot()
    assert len(events) == 2
    assert events[0]["kind"] == "media"
    assert events[1]["kind"] == "error"
    assert arena.stats() == {"total": 2, "success": 1, "errors": 1}


def test_main_ui_exposes_command_arena_and_remote_feed_hook():
    source = (Path(__file__).resolve().parents[1] / "asistan beta.py").read_text(encoding="utf-8")
    assert "neto_command_arena_ac_safe" in source
    assert "Komut Arenası" in source
    assert "_neto_command_arena_record" in source
