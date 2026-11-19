from __future__ import annotations

from datetime import timedelta

from pytest import approx

import neto_now_playing as now_playing


def test_media_session_key_is_stable_and_normalized():
    assert now_playing._session_key("Spotify!App", "  Song  ", "Artist") == "spotify!app|song|artist"


def test_timeline_seconds_accepts_winrt_timedelta_values():
    assert now_playing._timeline_seconds(timedelta(seconds=45)) == 45.0
    assert now_playing._timeline_seconds(1_800_000_000) == 180.0


def test_thumbnail_extension_matches_winrt_image_bytes():
    assert now_playing._thumbnail_extension(b"\x89PNG\r\n\x1a\n") == ".png"
    assert now_playing._thumbnail_extension(b"\xff\xd8\xff\xe0") == ".jpg"


def test_cached_cover_is_reused_when_media_session_does_not_return_art(monkeypatch, tmp_path):
    cover_path = tmp_path / "platform_Murat_Evgin_Jenerik_Müziği.png"
    cover_path.write_bytes(b"cached-cover" * 100)
    monkeypatch.setattr(now_playing, "_cover_cache_dir", lambda: str(tmp_path))

    assert now_playing._cached_cover_path("Jenerik Müziği", "Murat Evgin") == str(cover_path)


def test_cover_search_selects_matching_artist_and_track():
    results = [
        {
            "trackName": "Başka Bir Şey",
            "artistName": "Özer Atik",
            "artworkUrl100": "https://example.test/wrong.jpg",
        },
        {
            "trackName": "Yok Böyle Bir Şey",
            "artistName": "Özer Atik",
            "artworkUrl100": "https://example.test/right.jpg",
        },
    ]

    assert (
        now_playing._pick_cover_url(results, "Yok Böyle Bir Şey", "Özer Atik")
        == "https://example.test/right.jpg"
    )


def test_missing_cover_schedules_background_lookup(monkeypatch):
    scheduled = []
    old_last_good = now_playing._last_good_media
    old_last_good_time = now_playing._last_good_time
    old_last_good_monotonic = now_playing._last_good_monotonic
    try:
        now_playing._last_good_media = None
        now_playing._last_good_time = 0.0
        now_playing._last_good_monotonic = 0.0
        monkeypatch.setattr(
            now_playing,
            "_get_visible_music_window",
            lambda: {
                "title": "Yok Böyle Bir Şey",
                "artist": "Özer Atik",
                "app": "Google Chrome",
                "cover_path": "",
            },
        )
        monkeypatch.setattr(
            now_playing,
            "_get_media_session",
            lambda timeout=0.9: {
                "title": "Yok Böyle Bir Şey",
                "artist": "Özer Atik",
                "cover_path": "",
                "playback_status": "playing",
            },
        )
        monkeypatch.setattr(now_playing, "_selected_media_snapshot", lambda timeout=1.0: None)
        monkeypatch.setattr(now_playing, "_cached_cover_path", lambda *_args: "")
        monkeypatch.setattr(
            now_playing,
            "_schedule_cover_lookup",
            lambda media: scheduled.append(dict(media)),
        )

        result = now_playing.get_current_media(force_fresh=True)

        assert result["title"] == "Yok Böyle Bir Şey"
        assert scheduled and scheduled[0]["artist"] == "Özer Atik"
    finally:
        now_playing._last_good_media = old_last_good
        now_playing._last_good_time = old_last_good_time
        now_playing._last_good_monotonic = old_last_good_monotonic


def test_cover_probe_checks_fresh_media_art_each_tick(monkeypatch, tmp_path):
    cover_path = tmp_path / "fresh-cover.png"
    cover_path.write_bytes(b"cover" * 200)
    calls = []
    media = {"title": "Yok Böyle Bir Şey", "artist": "Özer Atik", "cover_path": ""}
    monkeypatch.setattr(now_playing, "_cached_cover_path", lambda *_args: "")

    def media_session(timeout=0.9):
        calls.append(timeout)
        return {
            "title": "Yok Böyle Bir Şey",
            "artist": "Özer Atik",
            "cover_path": str(cover_path),
        }

    monkeypatch.setattr(now_playing, "_get_media_session", media_session)

    result = now_playing._probe_cover_once(media)

    assert result == str(cover_path)
    assert calls == [0.9]


def test_same_song_accepts_media_title_with_artist_prefix():
    visible = {"title": "Kış Masalı", "artist": ""}
    media = {"title": "Sibel Can - Kış Masalı", "artist": "Sibel Can"}

    assert now_playing._same_song(visible, media) is True


def test_missing_cover_retries_media_session_once_for_current_song(monkeypatch, tmp_path):
    cover_path = tmp_path / "cover.png"
    cover_path.write_bytes(b"cover")
    calls = []
    old_retry_key = now_playing._last_cover_retry_key
    old_retry_attempts = getattr(now_playing, "_last_cover_retry_attempts", 0)
    old_last_good = now_playing._last_good_media
    old_last_good_time = now_playing._last_good_time
    old_last_good_monotonic = now_playing._last_good_monotonic
    try:
        now_playing._last_cover_retry_key = ""
        now_playing._last_good_media = None
        now_playing._last_good_time = 0.0
        now_playing._last_good_monotonic = 0.0
        monkeypatch.setattr(
            now_playing,
            "_get_visible_music_window",
            lambda: {"title": "Kış Masalı", "artist": "", "app": "Google Chrome", "cover_path": ""},
        )

        def media_session(timeout=0.9):
            calls.append(timeout)
            if len(calls) == 1:
                return None
            return {
                "title": "Sibel Can - Kış Masalı",
                "artist": "Sibel Can",
                "cover_path": str(cover_path),
                "playback_status": "playing",
            }

        monkeypatch.setattr(now_playing, "_get_media_session", media_session)
        monkeypatch.setattr(now_playing, "_selected_media_snapshot", lambda timeout=1.0: None)

        result = now_playing.get_current_media(force_fresh=True)

        assert result["cover_path"] == str(cover_path)
        assert len(calls) == 2
        assert calls[1] > calls[0]
    finally:
        now_playing._last_cover_retry_key = old_retry_key
        now_playing._last_cover_retry_attempts = old_retry_attempts
        now_playing._last_good_media = old_last_good
        now_playing._last_good_time = old_last_good_time
        now_playing._last_good_monotonic = old_last_good_monotonic


def test_missing_cover_retries_again_when_thumbnail_is_cold(monkeypatch, tmp_path):
    cover_path = tmp_path / "live-cover.png"
    cover_path.write_bytes(b"cover")
    calls = []
    old_retry_key = now_playing._last_cover_retry_key
    old_retry_attempts = getattr(now_playing, "_last_cover_retry_attempts", 0)
    old_last_good = now_playing._last_good_media
    old_last_good_time = now_playing._last_good_time
    old_last_good_monotonic = now_playing._last_good_monotonic
    try:
        now_playing._last_cover_retry_key = ""
        now_playing._last_cover_retry_attempts = 0
        now_playing._last_good_media = None
        now_playing._last_good_time = 0.0
        now_playing._last_good_monotonic = 0.0
        monkeypatch.setattr(
            now_playing,
            "_get_visible_music_window",
            lambda: {"title": "Jenerik Müziği", "artist": "Murat Evgin", "app": "Google Chrome", "cover_path": ""},
        )
        monkeypatch.setattr(now_playing, "_selected_media_snapshot", lambda timeout=1.0: None)
        monkeypatch.setattr(now_playing, "_cached_cover_path", lambda *_args: "")

        def media_session(timeout=0.9):
            calls.append(timeout)
            if len(calls) < 4:
                return None
            return {
                "title": "Jenerik Müziği",
                "artist": "Murat Evgin",
                "cover_path": str(cover_path),
                "playback_status": "playing",
            }

        monkeypatch.setattr(now_playing, "_get_media_session", media_session)

        first = now_playing.get_current_media(force_fresh=True)
        second = now_playing.get_current_media(force_fresh=True)

        assert first.get("cover_path", "") == ""
        assert second["cover_path"] == str(cover_path)
        assert len(calls) == 4
    finally:
        now_playing._last_cover_retry_key = old_retry_key
        now_playing._last_cover_retry_attempts = old_retry_attempts
        now_playing._last_good_media = old_last_good
        now_playing._last_good_time = old_last_good_time
        now_playing._last_good_monotonic = old_last_good_monotonic


def test_current_media_keeps_previous_cover_during_snapshot_gap(monkeypatch, tmp_path):
    cover_path = tmp_path / "stable-cover.png"
    cover_path.write_bytes(b"cover")
    old_last_good = now_playing._last_good_media
    old_last_good_time = now_playing._last_good_time
    old_last_good_monotonic = now_playing._last_good_monotonic
    old_retry_key = now_playing._last_cover_retry_key
    old_retry_attempts = getattr(now_playing, "_last_cover_retry_attempts", 0)
    try:
        now_playing._last_good_media = {
            "title": "Diva Yorgun",
            "artist": "Melike Şahin",
            "app": "Google Chrome",
            "cover_path": str(cover_path),
            "position_seconds": 12.0,
            "duration_seconds": 210.0,
            "playback_status": "playing",
        }
        now_playing._last_good_time = 1.0
        now_playing._last_good_monotonic = 1.0
        now_playing._last_cover_retry_key = "google chrome|diva yorgun|melike şahın"
        now_playing._last_cover_retry_attempts = 3
        monkeypatch.setattr(
            now_playing,
            "_get_visible_music_window",
            lambda: {
                "title": "Diva Yorgun",
                "artist": "Melike Şahin",
                "app": "Google Chrome",
                "cover_path": "",
                "playback_status": "playing",
            },
        )
        monkeypatch.setattr(
            now_playing,
            "_get_media_session",
            lambda timeout=0.9: {
                "title": "Diva Yorgun",
                "artist": "Melike Şahin",
                "cover_path": "",
                "playback_status": "playing",
            },
        )
        monkeypatch.setattr(now_playing, "_selected_media_snapshot", lambda timeout=1.0: None)
        monkeypatch.setattr(now_playing, "_cached_cover_path", lambda *_args: "")

        result = now_playing.get_current_media(force_fresh=True)

        assert result["cover_path"] == str(cover_path)
    finally:
        now_playing._last_good_media = old_last_good
        now_playing._last_good_time = old_last_good_time
        now_playing._last_good_monotonic = old_last_good_monotonic
        now_playing._last_cover_retry_key = old_retry_key
        now_playing._last_cover_retry_attempts = old_retry_attempts


def test_stale_playing_timeline_advances_using_elapsed_time():
    previous = {
        "title": "Test Song",
        "artist": "Test Artist",
        "position_seconds": 3.15,
        "duration_seconds": 180.0,
        "playback_status": "playing",
    }
    current = dict(previous)

    result = now_playing._smooth_live_timeline(current, previous, elapsed=1.2)

    assert result["position_seconds"] == approx(4.35, abs=0.01)


def test_playing_timeline_ignores_small_backward_provider_jitter():
    previous = {
        "title": "Test Song",
        "artist": "Test Artist",
        "position_seconds": 33.91,
        "duration_seconds": 180.0,
        "playback_status": "playing",
    }
    displayed = []
    for raw_position in (34.77, 33.91, 34.72):
        current = dict(previous, position_seconds=raw_position)
        previous = now_playing._smooth_live_timeline(current, previous, elapsed=0.8)
        displayed.append(previous["position_seconds"])

    assert displayed == sorted(displayed)
    assert displayed[-1] > 35.0


def test_playing_timeline_ignores_larger_stale_snapshot_jitter():
    previous = {
        "title": "Test Song",
        "artist": "Test Artist",
        "position_seconds": 14.17,
        "duration_seconds": 180.0,
        "playback_status": "playing",
    }
    current = dict(previous, position_seconds=10.89)

    result = now_playing._smooth_live_timeline(current, previous, elapsed=0.8)

    assert result["position_seconds"] > previous["position_seconds"]


def test_explicit_seek_resets_timeline_anchor():
    old_media = now_playing._last_good_media
    old_time = now_playing._last_good_time
    old_monotonic = now_playing._last_good_monotonic
    try:
        now_playing._last_good_media = {
            "title": "Test Song",
            "artist": "Test Artist",
            "position_seconds": 100.0,
            "duration_seconds": 180.0,
            "playback_status": "playing",
        }
        now_playing._reset_timeline_anchor(12.0)

        assert now_playing._last_good_media["position_seconds"] == 12.0
        result = now_playing._smooth_live_timeline(
            dict(now_playing._last_good_media),
            now_playing._last_good_media,
            elapsed=0.5,
        )
        assert result["position_seconds"] == approx(12.5, abs=0.01)
    finally:
        now_playing._last_good_media = old_media
        now_playing._last_good_time = old_time
        now_playing._last_good_monotonic = old_monotonic


def test_stale_paused_timeline_does_not_advance():
    previous = {
        "title": "Test Song",
        "artist": "Test Artist",
        "position_seconds": 3.15,
        "duration_seconds": 180.0,
        "playback_status": "paused",
    }

    result = now_playing._smooth_live_timeline(dict(previous), previous, elapsed=1.2)

    assert result["position_seconds"] == 3.15


def test_invalid_media_action_is_rejected_without_os_input():
    assert now_playing.media_session_control("run_command") is False


def test_session_selection_is_local_preference():
    old = now_playing.selected_media_session()
    try:
        assert now_playing.select_media_session("spotify|song|artist") is True
        assert now_playing.selected_media_session() == "spotify|song|artist"
        assert now_playing.select_media_session("") is False
        assert now_playing.selected_media_session() == ""
    finally:
        now_playing.select_media_session(old)


def test_visible_media_inherits_timeline_from_matching_media_session(monkeypatch):
    old_last_good = now_playing._last_good_media
    old_last_good_time = now_playing._last_good_time
    old_last_good_monotonic = now_playing._last_good_monotonic
    try:
        now_playing._last_good_media = None
        now_playing._last_good_time = 0.0
        now_playing._last_good_monotonic = 0.0
        monkeypatch.setattr(
            now_playing,
            "_get_visible_music_window",
            lambda: {
                "title": "Test Song",
                "artist": "Test Artist",
                "app": "YouTube Music",
                "cover_path": "",
            },
        )
        monkeypatch.setattr(
            now_playing,
            "_get_media_session",
            lambda timeout=0.9: {
                "title": "Test Song",
                "artist": "Test Artist",
                "album": "Test Album",
                "position_seconds": 45.0,
                "duration_seconds": 180.0,
                "playback_status": "playing",
                "cover_path": "",
            },
        )
        monkeypatch.setattr(now_playing, "_selected_media_snapshot", lambda timeout=1.0: None)

        result = now_playing.get_current_media(force_fresh=True)

        assert result["position_seconds"] == 45.0
        assert result["duration_seconds"] == 180.0
        assert result["album"] == "Test Album"
    finally:
        now_playing._last_good_media = old_last_good
        now_playing._last_good_time = old_last_good_time
        now_playing._last_good_monotonic = old_last_good_monotonic
