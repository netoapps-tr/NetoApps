from neto_youtube_music_panel import YOUTUBE_MUSIC_URL, YouTubeMusicPanel, close_panel


def test_youtube_music_url_is_restricted_to_supported_hosts():
    panel = YouTubeMusicPanel()
    assert panel.open_url("https://music.youtube.com/watch?v=abc") is False
    assert panel.open_url("https://example.com/") is False


def test_panel_does_not_start_without_a_native_host():
    panel = YouTubeMusicPanel()
    assert panel.open(0, 800, 300) is False
    panel.close()


def test_public_url_constant_is_stable():
    assert YOUTUBE_MUSIC_URL == "https://music.youtube.com/"
    close_panel()
