# =========================================================
# NETO NOW PLAYING - STABLE LAUNCH BUILD
# Stable rules:
# - No web searches inside detection.
# - No stale old cover on song change.
# - YouTube Music visible title is priority.
# - Media Session is used only when fast and matching.
# =========================================================
import asyncio
import ctypes
import importlib
import os
import re
import threading
import time
from typing import Any

from config import get_user_data_dir

_last_good_media = None
_last_good_time = 0.0
_media_session_checked = False
_media_session_available = False
_media_session_reported = False
_MediaManager = None
_MediaBackend = None

_KNOWN_ONE_WORD_ARTISTS = {
    "simge", "tarkan", "hadise", "teoman", "ceza", "sagopa", "sezen", "yalin",
    "eminem", "rihanna", "adele", "shakira", "madonna", "weeknd", "maneskin"
}

def _norm(s):
    s = str(s or "").lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _is_bad_media_title(text):
    """Reject browser/player landing pages that look like music but are not tracks."""
    title = _norm(text)
    if not title:
        return True
    bad_exact = {
        "youtube music",
        "youtube",
        "music",
        "spotify",
        "ana sayfa",
        "home",
        "search",
        "arama",
        "şarkı veya sanatçı yaz",
        "sarki veya sanatci yaz",
        "en sevdiğiniz şarkılar ve albümleri dinleyin",
        "en sevdiginiz sarkilar ve albumleri dinleyin",
        "listen to your favorite songs and albums",
    }
    bad_fragments = (
        "sevdiğiniz şarkılar",
        "sevdiginiz sarkilar",
        "albümü dinleyin",
        "albumleri dinleyin",
        "favorite songs",
        "music premium",
        "youtube music premium",
        "şarkı veya sanatçı",
        "sarki veya sanatci",
    )
    if title in bad_exact:
        return True
    return any(part in title for part in bad_fragments)

def _tokens(s):
    s = _norm(s)
    s = re.sub(r"[^a-z0-9ığüşöç]+", " ", s, flags=re.I)
    return [t for t in s.split() if t]

def _similarity(a, b):
    try:
        A, B = set(_tokens(a)), set(_tokens(b))
        if not A or not B:
            return 0.0
        return len(A & B) / max(len(A), len(B))
    except Exception:
        return 0.0

def _artist_match(a, b):
    if not a or not b:
        return False
    na, nb = _norm(a), _norm(b)
    return na == nb or na in nb or nb in na or _similarity(na, nb) >= 0.55

def _short_app_name(app_id):
    low = _norm(app_id)
    if "spotify" in low:
        return "Spotify"
    if "chrome" in low:
        return "Google Chrome"
    if "edge" in low:
        return "Microsoft Edge"
    if "firefox" in low:
        return "Firefox"
    if "brave" in low:
        return "Brave"
    if "opera" in low:
        return "Opera"
    if "youtube" in low:
        return "YouTube Music"
    if "music" in low:
        return "Music"
    if "vlc" in low:
        return "VLC"
    return str(app_id or "Unknown app").split("!")[-1].split(".")[-1]

def _cover_cache_dir():
    try:
        p = os.path.join(get_user_data_dir(), "now_playing_cache")
        os.makedirs(p, exist_ok=True)
        return p
    except Exception:
        return os.getcwd()

def _safe_cover_name(title="", artist=""):
    base = f"platform_{artist}_{title}".strip("_") or "platform_cover"
    base = re.sub(r"[^A-Za-z0-9ığüşöçİĞÜŞÖÇ_-]+", "_", base, flags=re.UNICODE).strip("_")
    return (base[:100] or "platform_cover") + ".jpg"

async def _save_media_thumbnail(props, title="", artist=""):
    try:
        thumb = getattr(props, "thumbnail", None)
        if thumb is None:
            return ""
        stream = await thumb.open_read_async()
        size = int(getattr(stream, "size", 0) or 0)
        if size <= 0:
            return ""
        try:
            from winrt.windows.storage.streams import DataReader
        except Exception:
            try:
                DataReader = importlib.import_module(
                    "winsdk.windows.storage.streams"
                ).DataReader
            except Exception:
                return ""
        reader = DataReader(stream)
        await reader.load_async(size)
        data = bytearray(size)
        reader.read_bytes(data)
        path = os.path.join(_cover_cache_dir(), _safe_cover_name(title, artist))
        with open(path, "wb") as f:
            f.write(bytes(data))
        return path if os.path.exists(path) and os.path.getsize(path) > 500 else ""
    except Exception:
        return ""

def _strip_browser_suffix(t):
    t = str(t or "").strip()
    suffixes = [
        " - Google Chrome", " - Microsoft Edge", " - Mozilla Firefox", " - Brave", " - Opera",
        " — Google Chrome", " — Microsoft Edge", " — Mozilla Firefox", " — Brave", " — Opera",
        " – Google Chrome", " – Microsoft Edge", " – Mozilla Firefox", " – Brave", " – Opera",
    ]
    changed = True
    while changed:
        changed = False
        for s in suffixes:
            if t.endswith(s):
                t = t[:-len(s)].strip()
                changed = True
    return t

def _split_artist_title(text):
    raw = str(text or "").strip()
    if " - " in raw:
        parts = [p.strip() for p in raw.split(" - ") if p.strip()]
        if len(parts) >= 2:
            return parts[0], " - ".join(parts[1:])
    if " – " in raw:
        parts = [p.strip() for p in raw.split(" – ") if p.strip()]
        if len(parts) >= 2:
            return parts[0], " – ".join(parts[1:])
    if " — " in raw:
        parts = [p.strip() for p in raw.split(" — ") if p.strip()]
        if len(parts) >= 2:
            return parts[0], " — ".join(parts[1:])

    # Launch-safe heuristic: only split "Simge Kamera" style when first word is known artist.
    words = raw.split()
    if len(words) >= 2 and _norm(words[0]) in _KNOWN_ONE_WORD_ARTISTS:
        return words[0], " ".join(words[1:])
    return "", raw

def _parse_visible_music_title(raw, process=""):
    raw0 = str(raw or "").strip()
    raw = _strip_browser_suffix(raw0)
    low = raw.lower()
    proc = str(process or "").lower()
    if not raw:
        return None

    app = ""
    t = raw
    if "youtube music" in low or "music.youtube" in low:
        app = "YouTube Music"
        if "|" in t:
            left, right = [p.strip() for p in t.split("|", 1)]
            if "youtube" in right.lower() or "music" in right.lower():
                t = left
        for pref in ["YouTube Music - ", "Youtube Music - ", "Music - "]:
            if t.lower().startswith(pref.lower()):
                t = t[len(pref):].strip()
        for suf in [" - YouTube Music", " | YouTube Music", " — YouTube Music", " – YouTube Music"]:
            if t.endswith(suf):
                t = t[:-len(suf)].strip()
    elif "youtube" in low:
        app = "YouTube"
        if "|" in t:
            left, right = [p.strip() for p in t.split("|", 1)]
            if "youtube" in right.lower():
                t = left
        for pref in ["YouTube - ", "Youtube - "]:
            if t.lower().startswith(pref.lower()):
                t = t[len(pref):].strip()
        for suf in [" - YouTube", " | YouTube", " — YouTube", " – YouTube"]:
            if t.endswith(suf):
                t = t[:-len(suf)].strip()
    elif "spotify" in low or proc == "spotify.exe":
        app = "Spotify"
        for suf in [" - Spotify", " | Spotify"]:
            if t.endswith(suf):
                t = t[:-len(suf)].strip()
    elif "vlc" in low or proc == "vlc.exe":
        app = "VLC"
        t = t.replace("VLC media player", "").replace("VLC", "").strip(" -|")
    else:
        return None

    if not t or _is_bad_media_title(t):
        return None

    artist, title = _split_artist_title(t)
    return {
        "title": title or t,
        "artist": artist,
        "album": "",
        "album_artist": "",
        "publisher": artist or app,
        "track_number": "",
        "app": app,
        "app_id": proc or "browser",
        "raw_title": t,
        "cover_path": "",
        "playback_status": "playing",
        "source": "visible_window_title",
        "backend": "visible_window_title",
        "time": time.time(),
    }

def _get_process_name(pid):
    try:
        import psutil
        return psutil.Process(pid).name().lower()
    except Exception:
        return ""

def _enum_windows():
    if os.name != "nt":
        return []
    try:
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        result = []
        def cb(hwnd, lparam):
            try:
                if not user32.IsWindowVisible(hwnd):
                    return True
                ln = user32.GetWindowTextLengthW(hwnd)
                if ln <= 0:
                    return True
                buff = ctypes.create_unicode_buffer(ln + 1)
                user32.GetWindowTextW(hwnd, buff, ln + 1)
                title = buff.value.strip()
                if not title:
                    return True
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                result.append({"hwnd": hwnd, "title": title, "pid": pid.value, "process": _get_process_name(pid.value)})
            except Exception:
                pass
            return True
        user32.EnumWindows(EnumWindowsProc(cb), 0)
        return result
    except Exception:
        return []

def _get_visible_music_window():
    scored = []
    for w in _enum_windows():
        raw = w.get("title", "")
        low = raw.lower()
        proc = w.get("process", "")
        parsed = _parse_visible_music_title(raw, proc)
        if not parsed:
            continue
        score = 0
        if "youtube music" in low or "music.youtube" in low:
            score += 100
        elif "youtube" in low:
            score += 80
        elif "spotify" in low or proc == "spotify.exe":
            score += 70
        elif "vlc" in low or proc == "vlc.exe":
            score += 50
        if "|" in raw or " - " in raw or " – " in raw or " — " in raw:
            score += 10
        scored.append((score, parsed))
    if not scored:
        return None
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]

async def _get_media_session_async():
    global _media_session_checked, _media_session_available, _media_session_reported, _MediaManager, _MediaBackend
    if not _media_session_checked:
        _media_session_checked = True
        try:
            from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as MediaManager
            _MediaManager = MediaManager
            _MediaBackend = "winrt"
            _media_session_available = True
        except Exception:
            try:
                MediaManager = importlib.import_module(
                    "winsdk.windows.media.control"
                ).GlobalSystemMediaTransportControlsSessionManager
                _MediaManager = MediaManager
                _MediaBackend = "winsdk"
                _media_session_available = True
            except Exception:
                _MediaManager = None
                _MediaBackend = None
                _media_session_available = False
                if not _media_session_reported:
                    try:
                        print("[NOW_PLAYING] Media Session unavailable; window-title mode active.", flush=True)
                    except Exception:
                        pass
                    _media_session_reported = True
    if not _media_session_available or _MediaManager is None:
        return None
    try:
        manager = await _MediaManager.request_async()
        session = manager.get_current_session()
        if not session:
            return None
        playback_status = ""
        try:
            playback_status = str(session.get_playback_info().playback_status).lower()
        except Exception:
            pass
        props = await session.try_get_media_properties_async()
        title = str(getattr(props, "title", "") or "").strip()
        artist = str(getattr(props, "artist", "") or "").strip()
        album = str(getattr(props, "album_title", "") or "").strip()
        album_artist = str(getattr(props, "album_artist", "") or "").strip()
        try:
            app_id = str(session.source_app_user_model_id or "").strip()
        except Exception:
            app_id = ""
        if not title:
            return None
        cover_path = await _save_media_thumbnail(props, title, artist)
        app = _short_app_name(app_id)
        return {
            "title": title,
            "artist": artist,
            "album": album,
            "album_artist": album_artist,
            "publisher": album_artist or artist or app,
            "track_number": "",
            "app": app,
            "app_id": app_id,
            "raw_title": f"{artist} - {title}" if artist else title,
            "cover_path": cover_path,
            "playback_status": playback_status,
            "time": time.time(),
            "source": "media_session",
            "backend": _MediaBackend or "media_session",
        }
    except Exception:
        return None

def _get_media_session_direct():
    try:
        return asyncio.run(_get_media_session_async())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_get_media_session_async())
        finally:
            try:
                loop.close()
            except Exception:
                pass
    except Exception:
        return None

def _get_media_session(timeout=1.2):
    result: dict[str, Any] = {"value": None}
    def runner():
        result["value"] = _get_media_session_direct()
    try:
        th = threading.Thread(target=runner, daemon=True)
        th.start()
        th.join(timeout)
        return result.get("value")
    except Exception:
        return None

def _same_song(a, b):
    if not a or not b:
        return False
    ta, tb = a.get("title", ""), b.get("title", "")
    aa, ab = a.get("artist", ""), b.get("artist", "")
    if _similarity(ta, tb) >= 0.55:
        return True
    if aa and ab and _artist_match(aa, ab) and _similarity(ta, tb) >= 0.35:
        return True
    return False

def get_current_media(force_fresh=False):
    global _last_good_media, _last_good_time
    now = time.time()

    visible = _get_visible_music_window()
    media = _get_media_session(timeout=0.9)

    chosen = None
    if visible and visible.get("title"):
        chosen = dict(visible)
        # Merge Media Session ONLY if it is clearly the same song. Prevents stale old cover.
        if media and media.get("title") and _same_song(visible, media):
            if media.get("cover_path"):
                chosen["cover_path"] = media.get("cover_path")
            if media.get("playback_status"):
                chosen["playback_status"] = media.get("playback_status")
            if not chosen.get("artist") and media.get("artist"):
                chosen["artist"] = media.get("artist")
                chosen["publisher"] = media.get("artist")
            if not chosen.get("album") and media.get("album"):
                chosen["album"] = media.get("album")
    elif media and media.get("title"):
        chosen = dict(media)

    if chosen and chosen.get("title") and _is_bad_media_title(chosen.get("title")):
        chosen = None

    if chosen and chosen.get("title"):
        # Safety: if no valid cover for current song, keep blank. UI will show fallback card.
        cover = str(chosen.get("cover_path") or "")
        if cover and not os.path.exists(cover):
            chosen["cover_path"] = ""
        _last_good_media = chosen
        _last_good_time = now
        return chosen

    # Do not keep old track too long; prevents old cover/name after song change.
    if not force_fresh and _last_good_media and now - _last_good_time <= 1.2:
        cached = dict(_last_good_media)
        cached["cached"] = True
        cached["time"] = now
        return cached
    return None

# Controls kept for compatibility.
_MEDIA_KEY_BY_ACTION = {
    "play_pause": 0xB3,  # VK_MEDIA_PLAY_PAUSE
    "next": 0xB0,        # VK_MEDIA_NEXT_TRACK
    "previous": 0xB1,    # VK_MEDIA_PREV_TRACK
}


def _press_media_key(vk_code):
    try:
        if os.name != "nt":
            return False
        user32 = ctypes.windll.user32
        user32.keybd_event(int(vk_code), 0, 0, 0)
        user32.keybd_event(int(vk_code), 0, 2, 0)
        return True
    except Exception:
        return False


def _control(action):
    vk = _MEDIA_KEY_BY_ACTION.get(str(action or "").strip().lower())
    if vk is None:
        return False
    if _press_media_key(vk):
        return True
    return False

def media_play_pause():
    return _control("play_pause")

def media_next():
    return _control("next")

def media_previous():
    return _control("previous")

def media_seek_relative(seconds):
    return False

# Old test helper names kept so TEST files do not crash.
def _fetch_album_cover_from_web(title, artist="", album=""):
    return ""
def _fetch_album_cover_from_google(title, artist="", album=""):
    return ""
def _fetch_album_cover_from_shazam(title, artist="", album=""):
    return ""
def _fetch_album_cover_from_coverartarchive(title, artist="", album=""):
    return ""
