from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_native_surface_uses_utility_navigation_not_ai_chat_copy():
    from neto_desktop_surface import dashboard_copy, navigation_items

    keys = [item[0] for item in navigation_items()]
    copy = dashboard_copy("tr")

    assert keys == ["overview", "devices", "now_playing", "automations", "logs", "settings"]
    assert copy["title"] == "Genel Bakış"
    assert "Sana nasıl yardımcı olabilirim" not in copy["title"]


def test_native_surface_has_compact_responsive_contract():
    from neto_desktop_surface import dashboard_cards, layout_contract

    contract = layout_contract()
    cards = dashboard_cards("tr")

    assert contract["min_width"] >= 760
    assert contract["sidebar_width"] <= 260
    assert len(cards) == 4
    assert all(card["key"] for card in cards)


def test_main_source_keeps_chat_switch_hook_without_forcing_dashboard():
    source = (PROJECT_ROOT / "asistan beta.py").read_text(encoding="utf-8-sig")

    assert "home_dashboard_surface" in source
    assert "show_home_dashboard" in source
    assert "build_native_dashboard" not in source


def test_legacy_chat_surface_is_not_forced_off_at_startup():
    source = (PROJECT_ROOT / "asistan beta.py").read_text(encoding="utf-8-sig")

    assert "home_dashboard_surface.pack(fill=\"both\", expand=True)" not in source
    assert "hero_content.pack_forget()" not in source
