def test_native_qt_shell_exposes_netops_pages_without_fluent_widgets():
    from netops_qt_shell import (
        native_legacy_layout_contract,
        native_animation_contract,
        native_brand_contract,
        native_command_bar_contract,
        native_help_center_contract,
        native_motion_contract,
        native_now_playing_contract,
        native_page_keys,
        native_settings_sections,
        native_sidebar_contract,
        native_sidebar_chat_contract,
        native_sidebar_extension_contract,
        native_sidebar_icon_contract,
        native_sidebar_motion_contract,
        native_settings_animation_contract,
        native_visual_contract,
        native_window_contract,
    )

    assert native_page_keys() == (
        "chat",
        "devices",
        "now_playing",
        "automations",
        "remote",
        "system",
        "notifications",
        "settings",
    )
    contract = native_legacy_layout_contract()
    assert contract["top_status"] == ("SİSTEM", "REMOTE", "BİLDİRİMLER", "NOW PLAYING")
    assert contract["sidebar"] == (
        "Genel Bakış",
        "Cihazlar",
        "Now Playing",
        "Otomasyonlar",
        "Remote",
        "Ayarlar",
    )
    assert contract["bottom_input"] == "Mesajını yaz..."
    motion = native_motion_contract()
    assert motion == {"startup_ms": 220, "page_ms": 180, "property": "windowOpacity"}
    assert native_animation_contract() == {
        "logo_fade_ms": 260,
        "sidebar_stagger_ms": 35,
        "button_feedback_ms": 120,
    }
    assert native_brand_contract() == {
        "app_name": "NetOps",
        "version": "1.52",
        "window_title": "NetOps 1.52",
        "logo_file": "Logo.png",
    }
    assert native_command_bar_contract() == {
        "navigation": ("Geri", "İleri", "Görünüm"),
        "menus": ("Dosya", "Düzenle", "Görünüm", "Yardım"),
        "overflow": "...",
        "height_px": 36,
    }
    assert native_help_center_contract() == {
        "name": "OpsCenter",
        "url": "https://sites.google.com/view/nqdestek/opscenter",
        "instruction": "Opscenter'a Gitmek için başka cihaz ile okutun.",
    }
    assert native_visual_contract() == {
        "now_playing_poll_ms": 1000,
        "system_poll_ms": 1000,
        "button_radius_px": 10,
        "button_feedback_ms": 120,
    }
    assert native_window_contract() == {"start_maximized": True}
    assert native_settings_sections() == (
        "Genel",
        "Sistem",
        "Görünüm",
        "Pencere Yöneticisi",
        "Netolab",
        "Güvenlik",
        "Güncellemeler",
        "Hakkında",
    )
    assert native_sidebar_contract() == {
        "settings_button_count": 1,
        "panel_radius_px": 16,
        "status_message": "",
        "settings_position": "bottom",
    }
    assert native_sidebar_extension_contract() == {
        "sections": ("YAKIN ZAMANLAR",),
        "quick_actions": (),
        "plan_action": "＋  Yeni sohbet",
    }
    assert native_sidebar_chat_contract() == {
        "header": "Yakın zamanlar",
        "new_chat": "＋  Yeni sohbet",
        "max_items": 24,
        "settings_button_count": 1,
        "resource_metrics": ("cpu", "ram", "gpu"),
    }
    assert native_sidebar_motion_contract() == {
        "edge_trigger_px": 18,
        "open_ms": 220,
        "close_ms": 160,
        "poll_ms": 50,
    }
    assert native_settings_animation_contract() == {
        "surface_ms": 220,
        "tab_ms": 160,
        "start_opacity": 0.78,
    }
    assert native_sidebar_icon_contract() == {
        "chat": "message",
        "devices": "computer",
        "now_playing": "media",
        "automations": "workflow",
        "system": "system",
        "settings": "settings",
    }
    assert native_now_playing_contract() == {
        "fullscreen_title": "ŞU AN ÇALIYOR",
        "standby_title": "BEKLEME MODU",
        "refresh_ms": 1000,
    }


def test_native_qt_backend_keeps_command_execution_explicit():
    from netops_qt_backend import build_qt_backend

    backend = build_qt_backend()

    result = backend.run("command", "deneme")

    assert result["ok"] is False
    assert "bağlı" in result["error"]


def test_native_qt_backend_normalizes_chat_callback():
    from netops_qt_backend import build_qt_backend

    backend = build_qt_backend(chat_reader=lambda text: f"NetOps: {text}")

    assert backend.run("chat", "merhaba") == "NetOps: merhaba"


def test_native_qt_backend_exposes_remote_and_notifications_callbacks():
    from netops_qt_backend import build_qt_backend

    backend = build_qt_backend(
        remote_reader=lambda text: {"ok": True, "display_text": f"uzak: {text}"},
        notifications_reader=lambda: [{"title": "Test", "detail": "Bildirim hazır"}],
    )

    assert backend.run("remote", "telefon durumu") == {"ok": True, "display_text": "uzak: telefon durumu"}
    assert backend.run("notifications") == [{"title": "Test", "detail": "Bildirim hazır"}]


def test_native_qt_backend_uses_existing_netops_chat_engine(monkeypatch):
    import sys
    from types import SimpleNamespace

    from netops_qt_backend import build_qt_backend

    monkeypatch.setitem(
        sys.modules,
        "neto_ai",
        SimpleNamespace(neto_ai_cevap_ver=lambda text: f"cevap: {text}"),
    )

    assert build_qt_backend().run("chat", "test") == "cevap: test"


def test_native_qt_backend_can_speak_chat_replies_without_blocking_chat():
    from netops_qt_backend import build_qt_backend

    spoken = []
    backend = build_qt_backend(
        chat_reader=lambda text: f"cevap: {text}",
        speech_runner=lambda text: spoken.append(text) or {"ok": True},
    )

    assert backend.run("chat", "merhaba") == "cevap: merhaba"
    assert backend.run("speech", "cevap: merhaba") == {"ok": True}
    assert spoken == ["cevap: merhaba"]


def test_native_qt_window_builds_all_pages_offscreen():
    from PySide6.QtWidgets import QApplication

    from netops_qt_backend import build_qt_backend
    from netops_qt_shell import NetOpsQtWindow, native_page_keys

    app = QApplication.instance() or QApplication([])
    window = NetOpsQtWindow(
        build_qt_backend(system_reader=lambda: {"cpu": 1, "ram": 2, "devices": 0, "remote": "Hazır"})
    )

    assert tuple(window._pages) == native_page_keys()
    assert window.windowTitle() == "NetOps 1.52"
    window.close()
    app.processEvents()


def test_native_qt_english_language_retranslates_shell_and_settings_offscreen():
    from PySide6.QtWidgets import QApplication

    from netops_qt_backend import build_qt_backend
    from netops_qt_shell import NetOpsQtWindow

    saved = []
    app = QApplication.instance() or QApplication([])
    window = NetOpsQtWindow(
        build_qt_backend(
            settings_reader=lambda: {"dil": "tr"},
            settings_writer=lambda data: saved.append(dict(data)) or {"ok": True},
        )
    )

    language = window._settings_controls["dil"]
    language.setCurrentIndex(language.findData("en"))
    app.processEvents()

    assert window._language == "en"
    assert window._command_bar_actions["Geri"].text() == "Back"
    assert window._sidebar_chat_new_button.text() == "＋  New chat"
    assert window._sidebar_recent_title.text() == "Recent chats"
    assert window._chat_input.placeholderText() == "Type your message..."
    assert window._chat_send_button.text() == "Send"

    window._open_native_page("settings")
    assert tuple(window._settings_tabs.tabText(index) for index in range(window._settings_tabs.count())) == (
        "General",
        "System",
        "Appearance",
        "Window Manager",
        "Netolab",
        "Security",
        "Updates",
        "About",
    )

    window._save_settings(window._status)
    assert saved[-1]["dil"] == "en"
    window.close()
    app.processEvents()


def test_native_qt_settings_auto_save_after_control_change_offscreen():
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from netops_qt_backend import build_qt_backend
    from netops_qt_shell import NetOpsQtWindow

    saved = []
    app = QApplication.instance() or QApplication([])
    window = NetOpsQtWindow(
        build_qt_backend(
            settings_reader=lambda: {"dil": "tr"},
            settings_writer=lambda data: saved.append(dict(data)) or {"ok": True},
        )
    )

    control = window._settings_controls["auto_update_check"]
    control.setChecked(True)
    QTest.qWait(350)

    assert saved
    assert saved[-1]["auto_update_check"] is True
    window.close()
    app.processEvents()


def test_native_qt_window_builds_desktop_command_bar_offscreen():
    from PySide6.QtWidgets import QApplication

    from netops_qt_backend import build_qt_backend
    from netops_qt_shell import NetOpsQtWindow

    app = QApplication.instance() or QApplication([])
    window = NetOpsQtWindow(build_qt_backend())

    assert set(window._command_bar_actions) >= {"Geri", "İleri", "Görünüm"}
    assert not window._command_bar_actions["Geri"].icon().isNull()
    assert not window._command_bar_actions["İleri"].icon().isNull()
    assert not window._command_bar_actions["Görünüm"].icon().isNull()
    assert window._command_bar.actions()[-1].text() == "..."
    window.close()
    app.processEvents()


def test_native_qt_uses_embedded_non_windows_icon_pack_offscreen():
    from PySide6.QtWidgets import QApplication

    from netops_icon_pack import icon as netops_icon
    from netops_qt_backend import build_qt_backend
    from netops_qt_shell import NetOpsQtWindow

    app = QApplication.instance() or QApplication([])
    window = NetOpsQtWindow(build_qt_backend())

    for name in (
        "message",
        "devices",
        "media",
        "workflow",
        "remote",
        "settings",
        "back",
        "forward",
        "view",
    ):
        assert not netops_icon(name).isNull()

    assert not window._sidebar_chat_new_button.icon().isNull()
    assert window._command_bar_actions["Geri"].icon().cacheKey() == netops_icon("back", size=16).cacheKey()
    assert window._command_bar_actions["İleri"].icon().cacheKey() == netops_icon("forward", size=16).cacheKey()
    assert window._command_bar_actions["Görünüm"].icon().cacheKey() == netops_icon("view", size=16).cacheKey()

    window.close()
    app.processEvents()


def test_native_qt_command_bar_history_overflow_and_now_playing_toggle_offscreen():
    from PySide6.QtWidgets import QApplication

    from netops_qt_backend import build_qt_backend
    from netops_qt_shell import NetOpsQtWindow

    app = QApplication.instance() or QApplication([])
    window = NetOpsQtWindow(build_qt_backend())

    window._open_native_page("devices")
    window._command_bar_actions["Geri"].trigger()
    assert window._page_stack.currentWidget() is window._pages["chat"]
    window._command_bar_actions["İleri"].trigger()
    assert window._page_stack.currentWidget() is window._pages["devices"]
    assert set(window._overflow_menu_action_texts) >= {"Sistem", "Remote", "Bildirimler"}

    window._now_playing_toggle_action.trigger()
    assert window._top_status_buttons["NOW PLAYING"].isHidden()
    assert not window._now_playing_timer.isActive()
    window._now_playing_toggle_action.trigger()
    assert not window._top_status_buttons["NOW PLAYING"].isHidden()
    assert window._now_playing_timer.isActive()
    window.close()
    app.processEvents()


def test_native_qt_sidebar_has_quick_actions_and_live_summary_offscreen():
    from PySide6.QtWidgets import QApplication

    from netops_qt_backend import build_qt_backend
    from netops_qt_shell import NetOpsQtWindow

    app = QApplication.instance() or QApplication([])
    window = NetOpsQtWindow(
        build_qt_backend(
            system_reader=lambda: {"cpu": 12, "ram": 34, "gpu": 5, "devices": 2, "remote": "Çalışıyor"},
            notifications_reader=lambda: [
                {"at": "12:00", "source": "Test", "title": "Bağlantı", "message": "Cihaz hazır"}
            ],
        )
    )

    assert window._sidebar_recent_title.text() == "Yakın zamanlar"
    assert window._sidebar_chat_new_button.text() == "＋  Yeni sohbet"
    assert window._sidebar_recent_list.count() >= 1
    assert not window._sidebar_quick_actions
    assert window._sidebar_plan_button is None
    assert window._sidebar_resource_card.objectName() == "sidebarResourceCard"
    assert tuple(window._sidebar_resource_values) == ("cpu", "ram", "gpu")
    assert all(label.objectName().startswith("sidebarResourceValue_") for label in window._sidebar_resource_values.values())
    assert window._sidebar_settings_button.objectName() == "sidebarSettingsButton"
    assert window._sidebar_settings_button.text() == "Ayarlar"
    assert tuple(label.text() for label in window._sidebar_resource_values.values()) == ("12", "34", "5")
    assert window._sidebar_settings_button in window._sidebar_widget.findChildren(type(window._sidebar_settings_button))
    window._sidebar_settings_button.click()
    assert window._page_stack.currentWidget() is window._pages["settings"]
    window.close()
    app.processEvents()


def test_native_qt_sidebar_keeps_zero_cpu_usage_visible_offscreen():
    from PySide6.QtWidgets import QApplication

    from netops_qt_backend import build_qt_backend
    from netops_qt_shell import NetOpsQtWindow

    app = QApplication.instance() or QApplication([])
    window = NetOpsQtWindow(
        build_qt_backend(
            system_reader=lambda: {"cpu": 0, "ram": 0, "gpu": "0%", "devices": 0, "remote": "Hazır"}
        )
    )

    assert window._sidebar_resource_values["cpu"].text() == "0"
    assert window._sidebar_resource_values["ram"].text() == "0"
    window.close()
    app.processEvents()


def test_native_qt_sidebar_starts_hidden_and_can_open_as_edge_drawer_offscreen():
    from PySide6.QtWidgets import QApplication

    from netops_qt_backend import build_qt_backend
    from netops_qt_shell import NetOpsQtWindow

    app = QApplication.instance() or QApplication([])
    window = NetOpsQtWindow(build_qt_backend())

    assert window._sidebar_widget.isHidden()
    assert window._sidebar_hover_timer.isActive()

    window._set_sidebar_open(True, animate=False)
    assert window._sidebar_open
    assert not window._sidebar_widget.isHidden()

    window._set_sidebar_open(False, animate=False)
    assert not window._sidebar_open
    assert window._sidebar_widget.isHidden()
    window.close()
    app.processEvents()


def test_native_qt_window_builds_opscenter_qr_offscreen():
    from PySide6.QtWidgets import QApplication

    from netops_qt_backend import build_qt_backend
    from netops_qt_shell import NetOpsQtWindow

    app = QApplication.instance() or QApplication([])
    window = NetOpsQtWindow(build_qt_backend())

    qr = window._opscenter_qr_pixmap()

    assert not qr.isNull()
    window.close()
    app.processEvents()


def test_native_theme_palette_uses_saved_legacy_theme_and_accent():
    from netops_qt_shell import native_theme_palette

    palette = native_theme_palette({"tema": "light", "renk_temasi": "blue"})

    assert palette["bg"] == "#F4F5F7"
    assert palette["sidebar"] == "#FFFFFF"
    assert palette["accent"] == "#3B82F6"
    assert palette["accent_hover"] == "#326DCF"


def test_native_settings_exposes_saved_color_theme_offscreen():
    from PySide6.QtWidgets import QApplication

    from netops_qt_backend import build_qt_backend
    from netops_qt_shell import NetOpsQtWindow

    app = QApplication.instance() or QApplication([])
    window = NetOpsQtWindow(
        build_qt_backend(settings_reader=lambda: {"tema": "light", "renk_temasi": "green"})
    )

    assert "renk_temasi" in window._settings_controls
    assert window._native_palette["accent"] == "#22C55E"
    assert "#F4F5F7" in window.styleSheet()
    assert "QCheckBox::indicator:checked" in window.styleSheet()
    assert "QAbstractItemView::item:selected" in window.styleSheet()
    window.close()
    app.processEvents()


def test_native_settings_tabs_use_fluent_sizing_and_navigation_offscreen():
    from PySide6.QtWidgets import QApplication

    from netops_qt_shell import NetOpsQtWindow

    app = QApplication.instance() or QApplication([])
    window = NetOpsQtWindow()
    tabs = window._settings_tabs

    assert tabs is not None
    assert tabs.documentMode() is True
    assert tabs.usesScrollButtons() is False
    assert tabs.tabBar().expanding() is False
    assert tabs.tabBar().minimumHeight() >= 40
    window.close()
    app.processEvents()


def test_native_settings_tabs_animate_when_opened_and_changed_offscreen(monkeypatch):
    from PySide6.QtWidgets import QApplication

    from netops_qt_shell import NetOpsQtWindow

    monkeypatch.delenv("NETOPS_REDUCE_MOTION", raising=False)
    app = QApplication.instance() or QApplication([])
    window = NetOpsQtWindow()

    window._open_native_page("settings")
    app.processEvents()
    assert window._settings_tabs.graphicsEffect() is None

    window._settings_tabs.setCurrentIndex(2)
    app.processEvents()
    assert window._settings_tabs.tabBar().graphicsEffect() is None
    window.close()
    app.processEvents()


def test_native_settings_tab_content_stays_renderable_after_switch_offscreen(monkeypatch):
    from PySide6.QtWidgets import QApplication

    from netops_qt_shell import NetOpsQtWindow

    monkeypatch.delenv("NETOPS_REDUCE_MOTION", raising=False)
    app = QApplication.instance() or QApplication([])
    window = NetOpsQtWindow()

    window._open_native_page("settings")
    window._settings_tabs.setCurrentIndex(2)
    app.processEvents()

    assert window._settings_tabs.currentWidget().graphicsEffect() is None
    window.close()
    app.processEvents()


def test_native_settings_tab_bar_stays_renderable_after_switch_offscreen(monkeypatch):
    from PySide6.QtWidgets import QApplication

    from netops_qt_shell import NetOpsQtWindow

    monkeypatch.delenv("NETOPS_REDUCE_MOTION", raising=False)
    app = QApplication.instance() or QApplication([])
    window = NetOpsQtWindow()
    window.show()

    window._open_native_page("settings")
    window._settings_tabs.setCurrentIndex(6)
    app.processEvents()

    tab_bar = window._settings_tabs.tabBar()
    assert tab_bar.graphicsEffect() is None
    assert all(tab_bar.tabRect(index).width() > 0 for index in range(window._settings_tabs.count()))
    window.close()
    app.processEvents()


def test_native_qt_page_change_adds_small_navigation_focus_animation_offscreen(monkeypatch):
    from PySide6.QtWidgets import QApplication

    from netops_qt_shell import NetOpsQtWindow

    monkeypatch.delenv("NETOPS_REDUCE_MOTION", raising=False)
    app = QApplication.instance() or QApplication([])
    window = NetOpsQtWindow()

    button = window._sidebar_chat_new_button
    button.click()
    app.processEvents()

    assert id(button) in window._button_feedback_animations
    window.close()
    app.processEvents()


def test_native_qt_window_has_live_now_playing_timer_offscreen():
    from PySide6.QtWidgets import QApplication

    from netops_qt_backend import build_qt_backend
    from netops_qt_shell import NetOpsQtWindow

    app = QApplication.instance() or QApplication([])
    window = NetOpsQtWindow(
        build_qt_backend(media_reader=lambda: {"title": "Test Parça", "artist": "Test Sanatçı"})
    )

    assert window._now_playing_timer.interval() == 1000
    window._refresh_now_playing()
    assert not hasattr(window, "_sidebar_now_playing")
    assert window._now_playing_compact_title.text() == "Test Parça"
    window.close()
    app.processEvents()


def test_native_qt_now_playing_uses_compact_album_card_offscreen():
    from PySide6.QtWidgets import QApplication

    from netops_qt_backend import build_qt_backend
    from netops_qt_shell import NetOpsQtWindow

    app = QApplication.instance() or QApplication([])
    window = NetOpsQtWindow(
        build_qt_backend(media_reader=lambda: {"title": "Uzun parça adı", "artist": "Sanatçı"})
    )

    status_layout = window.centralWidget().layout().itemAt(0).layout()
    now_playing_card = window._now_playing_card

    assert status_layout.itemAt(status_layout.count() - 1).widget() is now_playing_card
    assert now_playing_card.objectName() == "nowPlayingCompactCard"
    assert now_playing_card.minimumWidth() == 76
    assert now_playing_card.maximumWidth() == 76
    assert now_playing_card.minimumHeight() == 76
    assert window._now_playing_compact_cover.size().width() == 64
    assert window._now_playing_compact_cover._compact_circle is True
    assert window._now_playing_compact_info.isHidden()
    assert "now_playing" not in window._nav_buttons
    assert window._now_playing_compact_title.text() == "Uzun parça adı"
    assert window._now_playing_compact_detail.text() == "Sanatçı • Bilinmiyor"
    assert status_layout.indexOf(window._now_playing_island) == -1
    now_playing_card.clicked.emit()
    assert window._now_playing_compact_expanded is True
    assert not window._now_playing_compact_info.isHidden()
    window.close()
    app.processEvents()


def test_native_qt_compact_now_playing_long_press_opens_settings_offscreen(monkeypatch):
    from PySide6.QtWidgets import QApplication

    from netops_qt_backend import build_qt_backend
    from netops_qt_shell import NetOpsQtWindow

    monkeypatch.setenv("NETOPS_REDUCE_MOTION", "1")
    app = QApplication.instance() or QApplication([])
    window = NetOpsQtWindow(
        build_qt_backend(
            media_reader=lambda: {
                "title": "Test Parça",
                "artist": "Test Sanatçı",
                "duration_seconds": 180,
            },
            media_control_runner=lambda _action: {"ok": True, "value": 42, "muted": False},
        )
    )

    window._open_native_page("chat")
    window._now_playing_card.longPressed.emit()
    app.processEvents()

    assert window._page_stack.currentWidget() is window._pages["settings"]
    assert window._settings_tabs.tabText(window._settings_tabs.currentIndex()) in {
        "Pencere Yöneticisi",
        "Window Manager",
    }
    window.close()
    app.processEvents()


def test_native_qt_compact_now_playing_uses_live_volume_and_collapses_on_leave(monkeypatch):
    from PySide6.QtWidgets import QApplication

    from netops_qt_backend import build_qt_backend
    from netops_qt_shell import NetOpsQtWindow

    monkeypatch.setenv("NETOPS_REDUCE_MOTION", "1")
    app = QApplication.instance() or QApplication([])
    actions = []

    def media_control(action):
        actions.append(action)
        if action == "volume_get":
            return {"ok": True, "value": 73, "muted": False}
        return {"ok": True}

    window = NetOpsQtWindow(
        build_qt_backend(
            media_reader=lambda: {"title": "Test Parça", "artist": "Test Sanatçı"},
            media_control_runner=media_control,
        )
    )

    window._now_playing_card.clicked.emit()
    app.processEvents()
    assert window._now_playing_compact_volume.value() == 73
    assert window._now_playing_compact_volume_value.text() == "%73"
    assert actions
    assert set(actions) == {"volume_get"}

    window._now_playing_card.mouseLeft.emit()
    app.processEvents()
    assert window._now_playing_compact_expanded is False
    assert window._now_playing_card.minimumWidth() == 76
    assert window._now_playing_card.minimumHeight() == 76
    assert window._now_playing_compact_info.isHidden()
    assert window._now_playing_compact_cover._compact_circle is True
    window.close()
    app.processEvents()


def test_native_qt_compact_media_buttons_use_embedded_icons_offscreen(monkeypatch):
    from PySide6.QtWidgets import QApplication

    from netops_icon_pack import icon as netops_icon
    from netops_qt_backend import build_qt_backend
    from netops_qt_shell import NetOpsQtWindow

    monkeypatch.setenv("NETOPS_REDUCE_MOTION", "1")
    app = QApplication.instance() or QApplication([])
    window = NetOpsQtWindow(build_qt_backend())
    window._now_playing_card.longPressed.emit()
    app.processEvents()

    controls = (
        (window._now_playing_compact_previous, "previous"),
        (window._now_playing_compact_play_pause, "play"),
        (window._now_playing_compact_next, "next"),
    )
    for button, icon_name in controls:
        assert button.text() == ""
        assert button.icon().cacheKey() == netops_icon(icon_name, size=18).cacheKey()

    window.close()
    app.processEvents()


def test_native_qt_top_status_buttons_start_at_left_without_logo_offscreen():
    from PySide6.QtWidgets import QApplication, QPushButton

    from netops_qt_backend import build_qt_backend
    from netops_qt_shell import NetOpsQtWindow

    app = QApplication.instance() or QApplication([])
    window = NetOpsQtWindow(build_qt_backend())
    status_layout = window.centralWidget().layout().itemAt(0).layout()

    assert status_layout is not None
    assert isinstance(status_layout.itemAt(0).widget(), QPushButton)
    assert status_layout.itemAt(0).widget() is window._top_status_buttons["SİSTEM"]
    assert window._top_logo is None
    window.close()
    app.processEvents()


def test_native_qt_window_refreshes_separate_ram_and_gpu_every_second_offscreen():
    from PySide6.QtWidgets import QApplication

    from netops_qt_backend import build_qt_backend
    from netops_qt_shell import NetOpsQtWindow

    app = QApplication.instance() or QApplication([])
    window = NetOpsQtWindow(
        build_qt_backend(system_reader=lambda: {"cpu": 4, "ram": 61, "gpu": 27, "devices": 0, "remote": "Hazır"})
    )

    assert window._system_timer.interval() == 1000
    assert set(window._system_values) >= {"ram", "gpu"}
    assert not hasattr(window, "_sidebar_now_playing")
    window._refresh_system()
    assert window._system_values["ram"][0].text() == "61"
    assert window._system_values["gpu"][0].text() == "27"
    window.close()
    app.processEvents()


def test_native_qt_backend_reads_gpu_utilization_from_nvidia_smi(monkeypatch):
    import subprocess

    from netops_qt_backend import _read_gpu_usage

    class Completed:
        stdout = "42\n"

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: Completed())

    assert _read_gpu_usage() == "42%"


def test_native_qt_window_builds_settings_page_and_button_feedback_offscreen():
    from PySide6.QtWidgets import QApplication

    from netops_qt_shell import NetOpsQtWindow, native_page_keys

    app = QApplication.instance() or QApplication([])
    window = NetOpsQtWindow()

    assert "settings" in native_page_keys()
    assert "remote" in native_page_keys()
    assert "notifications" in native_page_keys()
    assert window._pages["settings"] is not None
    assert window._settings_tabs.count() == 8
    assert window._button_feedback_animations == {}
    assert window._buttons_with_feedback
    window.close()
    app.processEvents()


def test_native_qt_chat_composer_is_modern_and_functional_offscreen():
    from PySide6.QtWidgets import QApplication, QFrame

    from netops_qt_shell import NetOpsQtWindow

    app = QApplication.instance() or QApplication([])
    window = NetOpsQtWindow()

    assert isinstance(window._chat_composer, QFrame)
    assert window._chat_composer.objectName() == "chatComposer"
    assert window._chat_input.objectName() == "chatComposerInput"
    assert window._chat_send_button.objectName() == "chatSendButton"
    assert window._chat_mode_button is None
    assert window._chat_new_chat_button.objectName() == "chatNewChatButton"
    assert window._chat_new_chat_button.text() == "+"
    assert window._chat_input.minimumHeight() >= 40
    assert window._chat_send_button.text() == "Gönder"
    assert window._chat_send_button.minimumWidth() >= 84
    assert not window._chat_send_button.icon().isNull()
    assert window._chat_input.placeholderText() == "Mesajını yaz..."
    assert "QPushButton#chatNewChatButton" in window.styleSheet()
    assert "QLineEdit#chatComposerInput:focus" in window.styleSheet()
    window.close()
    app.processEvents()


def test_native_qt_chat_uses_centered_copilot_like_surface_offscreen():
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QApplication, QLabel, QSizePolicy

    from netops_qt_shell import NetOpsQtWindow

    app = QApplication.instance() or QApplication([])
    window = NetOpsQtWindow()

    assert window._chat_output.maximumWidth() == 1100
    assert window._chat_composer.maximumWidth() == 1100
    assert window._chat_output.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding
    assert window._chat_composer.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding
    assert isinstance(window._chat_hero_logo, QLabel)
    assert window._chat_hero_logo.objectName() == "netopsHeroLogo"
    assert window._chat_hero_logo.pixmap().width() == 170
    assert QColor(window._chat_hero_logo.pixmap().toImage().pixelColor(0, 0)).alpha() == 0
    assert window._chat_hero_title.text() == "Sana nasıl yardımcı olabilirim?"
    assert window._chat_hero_title.font().pointSize() >= 22
    assert window._chat_hero_subtitle.objectName() == "chatHeroKicker"
    assert window._chat_hero_subtitle.text() == "NETOPS  /  OPERATÖR MERKEZİ"
    assert window._chat_hero_greeting.objectName() == "chatHeroGreeting"
    assert window._chat_hero_greeting.text() == "Merhaba! Ben NetOps. Sana nasıl yardımcı olabilirim?"
    assert len(window._chat_hero_widgets) == 4
    assert "QScrollArea#chatOutput" in window.styleSheet()
    assert "QFrame#chatUserBubble" in window.styleSheet()
    assert "QFrame#chatAssistantBubble" in window.styleSheet()
    window.close()
    app.processEvents()


def test_native_qt_chat_renders_whatsapp_bubbles_and_async_typing_offscreen(monkeypatch):
    from threading import Event

    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from netops_qt_backend import build_qt_backend
    from netops_qt_shell import NetOpsQtWindow

    monkeypatch.setenv("NETOPS_REDUCE_MOTION", "1")
    app = QApplication.instance() or QApplication([])
    started = Event()
    release = Event()

    def chat_reader(text):
        started.set()
        release.wait(2)
        return f"cevap: {text}"

    window = NetOpsQtWindow(build_qt_backend(chat_reader=chat_reader))
    window.show()
    app.processEvents()
    window._chat_input.setText("Merhaba NetOps")
    window._submit_chat()

    assert started.wait(1)
    assert all(not widget.isVisible() for widget in window._chat_hero_widgets)
    assert window._chat_output._messages[0]["role"] == "user"
    assert window._chat_output._messages[0]["text"] == "Merhaba NetOps"
    assert window._chat_output._typing_indicator is not None
    assert window._chat_output._typing_indicator.isVisible()
    assert window._chat_output._typing_indicator._movie is not None
    assert window._chat_output._typing_indicator._movie.isValid()
    assert not window._chat_input.isEnabled()

    release.set()
    for _ in range(100):
        app.processEvents()
        if not window._chat_pending:
            break
        QTest.qWait(20)

    assert not window._chat_pending
    assert [message["role"] for message in window._chat_output._messages] == ["user", "assistant"]
    assert window._chat_output._messages[1]["text"] == "cevap: Merhaba NetOps"
    assert not window._chat_output._typing_indicator.isVisible()
    assert window._chat_input.isEnabled()
    window.close()
    app.processEvents()


def test_native_qt_button_click_starts_feedback_animation_offscreen(monkeypatch):
    from PySide6.QtWidgets import QApplication

    from netops_qt_shell import NetOpsQtWindow

    monkeypatch.delenv("NETOPS_REDUCE_MOTION", raising=False)
    app = QApplication.instance() or QApplication([])
    window = NetOpsQtWindow()
    button = window._sidebar_chat_new_button

    button.click()
    app.processEvents()

    assert id(button) in window._button_feedback_animations
    window.close()
    app.processEvents()


def test_native_qt_now_playing_page_has_media_controls_offscreen():
    from PySide6.QtWidgets import QApplication

    from netops_qt_backend import build_qt_backend
    from netops_qt_shell import NetOpsQtWindow

    app = QApplication.instance() or QApplication([])
    actions = []
    window = NetOpsQtWindow(
        build_qt_backend(
            media_reader=lambda: {"title": "Test Parça", "artist": "Test Sanatçı"},
            media_control_runner=lambda action: actions.append(action) or {"ok": True},
        )
    )

    window._media_action("next")
    assert actions == ["next"]
    assert window._now_playing_values["title"].text() == "Test Parça"
    window.close()
    app.processEvents()


def test_native_qt_now_playing_compact_card_gestures_open_fullscreen_and_settings():
    from PySide6.QtWidgets import QApplication

    from netops_qt_shell import NetOpsQtWindow

    app = QApplication.instance() or QApplication([])
    window = NetOpsQtWindow()
    window.show()
    app.processEvents()

    window._open_native_page("chat")
    window._now_playing_card.doubleClicked.emit()
    app.processEvents()
    assert window._now_playing_overlay is not None
    assert window._now_playing_overlay.isVisible()
    window._close_now_playing_fullscreen()

    window._open_native_page("chat")
    window._now_playing_card.longPressed.emit()
    app.processEvents()
    assert window._page_stack.currentWidget() is window._pages["settings"]

    window.close()
    app.processEvents()


def test_native_qt_now_playing_page_has_volume_controls_offscreen():
    from PySide6.QtWidgets import QApplication

    from netops_qt_backend import build_qt_backend
    from netops_qt_shell import NetOpsQtWindow

    app = QApplication.instance() or QApplication([])
    actions = []
    window = NetOpsQtWindow(
        build_qt_backend(
            media_reader=lambda: {"title": "Test Parça"},
            media_control_runner=lambda action: actions.append(action) or {"ok": True, "value": 42, "muted": False},
        )
    )

    window._open_native_page("now_playing")
    assert window._volume_slider.value() == 42
    window._volume_slider.setValue(42)
    window._set_volume()
    window._toggle_mute()

    assert actions == ["volume_get", "volume_set:42", "mute_toggle"]
    window.close()
    app.processEvents()


def test_native_qt_compact_now_playing_refreshes_metadata_and_seeks(monkeypatch):
    from PySide6.QtWidgets import QApplication

    from netops_qt_backend import build_qt_backend
    from netops_qt_shell import NetOpsQtWindow

    monkeypatch.setenv("NETOPS_REDUCE_MOTION", "1")
    app = QApplication.instance() or QApplication([])
    actions = []
    media = {
        "title": "Test Parça",
        "artist": "Test Sanatçı",
        "album": "Test Albüm",
        "app": "YouTube Music",
        "position_seconds": 45,
        "duration_seconds": 180,
    }
    window = NetOpsQtWindow(
        build_qt_backend(
            media_reader=lambda: dict(media),
            media_control_runner=lambda action: actions.append(action) or {"ok": True},
        )
    )

    window._refresh_now_playing()

    assert window._now_playing_compact_title.text() == "Test Parça"
    assert window._now_playing_compact_detail.text() == "Test Sanatçı • YouTube Music"
    assert window._now_playing_compact_album.text() == "Test Albüm"
    assert window._now_playing_compact_progress.value() == 250
    assert window._now_playing_page_timeline.text() == "00:45 / 03:00"
    assert window._now_playing_page_progress.value() == 250

    media["position_seconds"] = 46
    window._refresh_now_playing()
    assert window._now_playing_compact_timeline.text() == "00:46 / 03:00"
    assert window._now_playing_page_timeline.text() == "00:46 / 03:00"

    window._now_playing_compact_progress.setValue(500)
    window._set_compact_position()
    assert actions[-1] == "seek:90.00"
    window._now_playing_page_progress.setValue(750)
    window._set_now_playing_page_position()
    assert actions[-1] == "seek:135.00"
    window.close()
    app.processEvents()


def test_native_qt_fullscreen_now_playing_has_platform_volume_and_playback_controls(monkeypatch):
    from PySide6.QtWidgets import QApplication, QPushButton

    from netops_qt_backend import build_qt_backend
    from netops_qt_shell import NetOpsQtWindow, NowPlayingCover

    monkeypatch.delenv("NETOPS_REDUCE_MOTION", raising=False)
    app = QApplication.instance() or QApplication([])
    actions = []
    window = NetOpsQtWindow(
        build_qt_backend(
            media_reader=lambda: {
                "title": "Test Parça",
                "artist": "Test Sanatçı",
                "album": "Test Albüm",
                "app": "YouTube Music",
                "playback_status": "Playing",
                "position_seconds": 45,
                "duration_seconds": 180,
            },
            media_control_runner=lambda action: actions.append(action) or {"ok": True, "value": 64, "muted": False},
        )
    )

    window._open_now_playing_fullscreen()
    assert window._now_playing_overlay_platform.text() == "Platform: YouTube Music"
    assert isinstance(window._now_playing_overlay_cover, NowPlayingCover)
    assert window._now_playing_overlay_cover.objectName() == "nowPlayingOverlayCover"
    assert 170 <= window._now_playing_overlay_cover.width() <= 280
    assert window._now_playing_overlay_play_pause.text() == ""
    assert not window._now_playing_overlay_play_pause.icon().isNull()
    media_buttons = window._now_playing_overlay.findChildren(
        QPushButton,
        "nowPlayingControlButton",
    )
    assert len(media_buttons) == 4
    assert all(not button.icon().isNull() for button in media_buttons)
    assert window._now_playing_overlay.findChild(QPushButton, "nowPlayingCloseButton") is not None
    assert window._now_playing_overlay_volume_slider.value() == 64
    assert window._now_playing_overlay_album.text() == "Albüm: Test Albüm"
    assert window._now_playing_overlay_timeline.text() == "00:45 / 03:00"
    assert window._now_playing_overlay_progress.value() == 250
    assert window._now_playing_overlay_visualizer.text()

    window._now_playing_overlay_volume_slider.setValue(72)
    window._set_fullscreen_volume()
    window._fullscreen_media_action("previous")
    window._fullscreen_media_action("play_pause")
    window._fullscreen_media_action("next")
    window._fullscreen_media_action("mute_toggle")
    assert actions[-5:] == ["volume_set:72", "previous", "play_pause", "next", "mute_toggle"]
    window._close_now_playing_fullscreen()
    window.close()
    app.processEvents()


def test_native_qt_update_flow_waits_for_confirmation_and_restart(monkeypatch):
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QApplication

    from netops_qt_backend import build_qt_backend
    from netops_qt_shell import NetOpsQtWindow

    app = QApplication.instance() or QApplication([])
    window = NetOpsQtWindow(build_qt_backend(settings_reader=lambda: {}))
    window._open_native_page("settings")

    assert window._update_check_button.text() == "Güncellemeleri kontrol et"
    assert window._update_status_label.text() == "Yapılandırma"
    assert window._update_restart_button.isHidden()
    assert window._update_progress.isHidden()
    assert window._update_rollback_button is not None
    assert window._update_log_view is not None

    monkeypatch.setattr(window, "_ask_update_confirmation", lambda _update: False)
    window._handle_update_check_result(
        {
            "ok": True,
            "available": True,
            "latest_version": "1.53.0",
            "message": "Yeni sürüm hazır.",
        }
    )
    assert window._update_status_label.text() == "Güncelleme iptal edildi"
    assert window._update_restart_button.isHidden()

    window._update_pending = True
    event = QCloseEvent()
    window.closeEvent(event)
    assert not event.isAccepted()
    window._update_pending = False
    window.close()
    app.processEvents()


def test_native_qt_update_center_reports_latest_rollback(monkeypatch):
    from PySide6.QtWidgets import QApplication

    import neto_system_updater
    from netops_qt_backend import build_qt_backend
    from netops_qt_shell import NetOpsQtWindow

    app = QApplication.instance() or QApplication([])
    window = NetOpsQtWindow(build_qt_backend(settings_reader=lambda: {}))
    window._open_native_page("settings")
    monkeypatch.setattr(
        neto_system_updater,
        "latest_rollback",
        lambda: {
            "version": "1.52.1",
            "release_tag": "v1.52.1",
            "created_at": 1795022400,
            "files": [{"path": "netops_qt_shell.py"}],
        },
    )

    window._refresh_update_center()

    assert window._update_rollback_button.isEnabled()
    assert "1.52.1" in window._update_rollback_status.text()
    assert "Geri alma kaydı" in window._update_log_view.toPlainText()
    window.close()
    app.processEvents()


def test_native_qt_update_restart_shows_loading_screen(monkeypatch):
    from PySide6.QtWidgets import QApplication

    from netops_qt_backend import build_qt_backend
    from netops_qt_shell import NetOpsQtWindow

    app = QApplication.instance() or QApplication([])
    window = NetOpsQtWindow(build_qt_backend(settings_reader=lambda: {}))
    window.show()
    app.processEvents()

    window._open_native_page("settings")
    window._show_update_loading_screen()
    app.processEvents()

    assert window._update_loading_overlay is not None
    assert window._update_loading_overlay.isVisible()
    assert window._update_loading_label.text() == "Güncelleme yükleniyor..."
    assert window._update_loading_progress.value() == 0

    window._hide_update_loading_screen()
    assert window._update_loading_overlay.isHidden()
    window.close()
    app.processEvents()
