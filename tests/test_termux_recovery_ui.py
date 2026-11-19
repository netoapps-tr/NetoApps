from neto_termux_recovery_ui import normalize_choice, recovery_screen_lines


def test_recovery_ui_accepts_keyboard_choices_without_command_text():
    assert normalize_choice("1") == "onayla"
    assert normalize_choice("onayla") == "onayla"
    assert normalize_choice("2") == "iptal"
    assert normalize_choice("iptal") == "iptal"
    assert normalize_choice("x") is None


def test_recovery_ui_has_clear_phone_actions():
    screen = "\n".join(recovery_screen_lines(selected=0))
    assert "RECOVERY NETOPS" in screen
    assert "ONAYLA" in screen
    assert "İPTAL" in screen
