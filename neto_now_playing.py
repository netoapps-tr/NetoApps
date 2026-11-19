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
import json
import os
import re
import sys
import threading
import time
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from config import get_user_data_dir

_last_good_media = None
_last_good_time = 0.0
_last_good_monotonic = 0.0
_media_session_checked = False
_media_session_available = False
_media_session_reported = False
_MediaManager = None
_MediaBackend = None
_selected_session_key = ""
_last_cover_retry_key = ""
_last_cover_retry_attempts = 0
_MAX_COVER_RETRY_ATTEMPTS = 3
_TIMELINE_BACKWARD_JITTER_SECONDS = 10.0
_cover_lookup_lock = threading.Lock()
_cover_lookup_inflight = set()
_cover_lookup_last_attempt = {}
_COVER_LOOKUP_RETRY_SECONDS = 60.0
_cover_probe_lock = threading.Lock()
_cover_probe_inflight = set()
_COVER_PROBE_TICKS = 15

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


def _timeline_seconds(value):
    """Normalize WinRT timedeltas and legacy 100-nanosecond values to seconds."""
    if value is None:
        return 0.0
    total_seconds = getattr(value, "total_seconds", None)
    if callable(total_seconds):
        try:
            return max(0.0, float(total_seconds()))
        except (TypeError, ValueError, OverflowError):
            return 0.0
    try:
        return max(0.0, float(value) / 10_000_000.0)
    except (TypeError, ValueError, OverflowError):
        return 0.0


def _is_playing_status(value) -> bool:
    status = str(value or "").strip().lower()
    return status in {"3", "4", "play", "playing"} or "playing" in status


def _smooth_live_timeline(current, previous, *, elapsed: float):
    """Advance a stale Windows snapshot without following small backward jitter."""
    result = dict(current or {})
    if not _is_playing_status(result.get("playback_status")):
        return result
    try:
        current_position = max(0.0, float(result.get("position_seconds") or 0.0))
        previous_position = max(0.0, float((previous or {}).get("position_seconds") or 0.0))
        duration = max(0.0, float(result.get("duration_seconds") or 0.0))
        elapsed = max(0.0, float(elapsed))
    except (TypeError, ValueError):
        return result
    if duration <= 0 or elapsed <= 0:
        return result
    backward_delta = previous_position - current_position
    # Small backwards changes are provider jitter (GSMTC can alternate snapshots).
    if 0.0 < backward_delta <= _TIMELINE_BACKWARD_JITTER_SECONDS:
        current_position = previous_position
    # A large jump is a real external seek or restart, so keep the provider value.
    elif backward_delta > _TIMELINE_BACKWARD_JITTER_SECONDS:
        return result
    projected = min(duration, previous_position + elapsed)
    if projected > current_position:
        result["position_seconds"] = round(projected, 2)
    return result


def _reset_timeline_anchor(position_seconds: float) -> None:
    """Re-anchor the displayed timeline after an explicit user seek."""
    global _last_good_media, _last_good_time, _last_good_monotonic
    target = max(0.0, float(position_seconds))
    if _last_good_media:
        updated = dict(_last_good_media)
        duration = max(0.0, float(updated.get("duration_seconds") or 0.0))
        updated["position_seconds"] = min(target, duration) if duration else target
        _last_good_media = updated
    _last_good_time = time.time()
    _last_good_monotonic = time.monotonic()

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


def _now_playing_debug(message: str) -> None:
    """Write optional media diagnostics without affecting normal playback polling."""
    if os.environ.get("NETOPS_DEBUG_NOW_PLAYING") != "1":
        return
    try:
        log_dir = os.path.join(get_user_data_dir(), "logs")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "now_playing_debug.log"), "a", encoding="utf-8") as log:
            log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except Exception:
        pass

def _thumbnail_extension(data: bytes) -> str:
    """Return an image extension Qt can use to decode the thumbnail bytes."""
    payload = bytes(data or b"")
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if payload.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if payload.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if len(payload) >= 12 and payload[:4] == b"RIFF" and payload[8:12] == b"WEBP":
        return ".webp"
    return ".jpg"


def _safe_cover_name(title="", artist="", extension=".jpg"):
    base = f"platform_{artist}_{title}".strip("_") or "platform_cover"
    base = re.sub(r"[^A-Za-z0-9ığüşöçİĞÜŞÖÇ_-]+", "_", base, flags=re.UNICODE).strip("_")
    extension = str(extension or ".jpg").lower()
    if extension not in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        extension = ".jpg"
    return (base[:100] or "platform_cover") + extension


def _cached_cover_path(title="", artist=""):
    """Reuse an exact cached cover when a later GSMTC snapshot omits art."""
    title = str(title or "").strip()
    artist = str(artist or "").strip()
    if not title:
        return ""
    cache_dir = _cover_cache_dir()
    candidates = []
    for extension in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        path = os.path.join(cache_dir, _safe_cover_name(title, artist, extension))
        try:
            if os.path.isfile(path) and os.path.getsize(path) > 500:
                candidates.append(path)
        except OSError:
            continue
    if not candidates:
        return ""
    return max(candidates, key=lambda item: os.path.getmtime(item))


def _pick_cover_url(results, title="", artist="", album=""):
    """Choose artwork only when the remote result matches the current track."""
    best_url = ""
    best_score = 0.0
    for item in results if isinstance(results, list) else []:
        if not isinstance(item, dict):
            continue
        candidate_title = item.get("trackName") or item.get("title") or ""
        candidate_artist = item.get("artistName")
        if not candidate_artist and isinstance(item.get("artist"), dict):
            candidate_artist = item["artist"].get("name", "")
        candidate_album = item.get("collectionName") or ""
        if not candidate_album and isinstance(item.get("album"), dict):
            candidate_album = item["album"].get("title", "")
        url = item.get("artworkUrl600") or item.get("artworkUrl100")
        if not url and isinstance(item.get("album"), dict):
            url = item["album"].get("cover_xl") or item["album"].get("cover_big")
        url = str(url or "").strip()
        if not url.startswith("https://"):
            continue
        title_score = _similarity(title, candidate_title)
        artist_score = _similarity(artist, candidate_artist) if artist else 1.0
        album_score = _similarity(album, candidate_album) if album and candidate_album else 0.0
        if title_score < 0.55 or (artist and artist_score < 0.35):
            continue
        score = (title_score * 4.0) + (artist_score * 3.0) + album_score
        if score > best_score:
            best_score = score
            best_url = url
    return best_url


def _cover_lookup_json(url):
    request = Request(url, headers={"User-Agent": "NetOps/1.54 (Now Playing)"})
    with urlopen(request, timeout=4.0) as response:
        payload = response.read(1_500_000)
    return json.loads(payload.decode("utf-8", errors="replace"))


def _save_remote_cover(url, title="", artist=""):
    if not str(url or "").startswith("https://"):
        return ""
    request = Request(url, headers={"User-Agent": "NetOps/1.54 (Now Playing)"})
    with urlopen(request, timeout=5.0) as response:
        data = response.read(8_000_000)
    if len(data) < 500:
        return ""
    target = os.path.join(
        _cover_cache_dir(),
        _safe_cover_name(title, artist, _thumbnail_extension(data)),
    )
    temporary = f"{target}.{threading.get_ident()}.tmp"
    try:
        with open(temporary, "wb") as handle:
            handle.write(data)
        os.replace(temporary, target)
    finally:
        try:
            if os.path.exists(temporary):
                os.remove(temporary)
        except OSError:
            pass
    return target if os.path.isfile(target) else ""


def _lookup_cover_url(title="", artist="", album=""):
    query = " ".join(part for part in (artist, title) if str(part or "").strip())
    if not query:
        return ""
    encoded = quote(query)
    try:
        payload = _cover_lookup_json(
            f"https://itunes.apple.com/search?term={encoded}&entity=song&limit=8&country=TR"
        )
        url = _pick_cover_url(payload.get("results"), title, artist, album)
        if url:
            return url.replace("/100x100bb.", "/600x600bb.")
    except Exception as exc:
        _now_playing_debug(f"iTunes cover lookup error: {type(exc).__name__}: {exc}")

    try:
        payload = _cover_lookup_json(
            f"https://api.deezer.com/search?q={encoded}&limit=8"
        )
        return _pick_cover_url(payload.get("data"), title, artist, album)
    except Exception as exc:
        _now_playing_debug(f"Deezer cover lookup error: {type(exc).__name__}: {exc}")
        return ""


def _cover_lookup_worker(media, key):
    try:
        title = str(media.get("title", "") or "").strip()
        artist = str(media.get("artist", "") or "").strip()
        album = str(media.get("album", "") or "").strip()
        url = _lookup_cover_url(title, artist, album)
        saved = _save_remote_cover(url, title, artist) if url else ""
        _now_playing_debug(f"remote cover saved: {saved or 'not found'}")
    except Exception as exc:
        _now_playing_debug(f"remote cover worker error: {type(exc).__name__}: {exc}")
    finally:
        with _cover_lookup_lock:
            _cover_lookup_inflight.discard(key)
            _cover_lookup_last_attempt[key] = time.monotonic()


def _schedule_cover_lookup(media):
    """Resolve missing art in the background so media polling never blocks the UI."""
    if not isinstance(media, dict):
        return
    title = str(media.get("title", "") or "").strip()
    artist = str(media.get("artist", "") or "").strip()
    album = str(media.get("album", "") or "").strip()
    if not title or _is_bad_media_title(title):
        return
    key = _session_key(str(media.get("app_id", "")), title, artist)
    now = time.monotonic()
    with _cover_lookup_lock:
        last_attempt = _cover_lookup_last_attempt.get(key, 0.0)
        if key in _cover_lookup_inflight or now - last_attempt < _COVER_LOOKUP_RETRY_SECONDS:
            return
        _cover_lookup_inflight.add(key)
    threading.Thread(
        target=_cover_lookup_worker,
        args=(dict(media), key),
        daemon=True,
        name="NetOpsCoverLookup",
    ).start()


def _probe_cover_once(media):
    """Read a fresh media thumbnail or the exact cached art for one track."""
    if not isinstance(media, dict):
        return ""
    title = str(media.get("title", "") or "").strip()
    artist = str(media.get("artist", "") or "").strip()
    cached = _cached_cover_path(title, artist)
    if cached:
        return cached
    fresh = _get_media_session(timeout=0.9)
    if not fresh or not fresh.get("cover_path") or not _same_song(media, fresh):
        return ""
    path = str(fresh.get("cover_path") or "")
    return path if os.path.isfile(path) else ""


def _cover_probe_worker(media, key):
    try:
        for tick in range(_COVER_PROBE_TICKS):
            if _probe_cover_once(media):
                _now_playing_debug(f"per-second cover probe succeeded: tick={tick + 1}")
                return
            visible = _get_visible_music_window()
            if visible and visible.get("title") and not _same_song(media, visible):
                return
            if tick + 1 < _COVER_PROBE_TICKS:
                time.sleep(1.0)
    except Exception as exc:
        _now_playing_debug(f"per-second cover probe error: {type(exc).__name__}: {exc}")
    finally:
        with _cover_probe_lock:
            _cover_probe_inflight.discard(key)


def _schedule_cover_probe(media):
    """Run the per-second probe only in the packaged EXE runtime."""
    if not getattr(sys, "frozen", False) or not isinstance(media, dict):
        return
    title = str(media.get("title", "") or "").strip()
    artist = str(media.get("artist", "") or "").strip()
    if not title or _is_bad_media_title(title):
        return
    key = _session_key(str(media.get("app_id", "")), title, artist)
    with _cover_probe_lock:
        if key in _cover_probe_inflight:
            return
        _cover_probe_inflight.add(key)
    threading.Thread(
        target=_cover_probe_worker,
        args=(dict(media), key),
        daemon=True,
        name="NetOpsPerSecondCoverProbe",
    ).start()


async def _save_media_thumbnail(props, title="", artist=""):
    try:
        thumb = getattr(props, "thumbnail", None)
        if thumb is None:
            _now_playing_debug("thumbnail is missing")
            return ""
        stream = await thumb.open_read_async()
        size = int(getattr(stream, "size", 0) or 0)
        if size <= 0:
            _now_playing_debug(f"thumbnail stream is empty: {size}")
            return ""
        try:
            from winrt.windows.storage.streams import DataReader
        except Exception:
            try:
                DataReader = importlib.import_module(
                    "winsdk.windows.storage.streams"
                ).DataReader
            except Exception:
                _now_playing_debug("DataReader import failed")
                return ""
        reader = DataReader(stream)
        await reader.load_async(size)
        data = bytearray(size)
        reader.read_bytes(data)
        path = os.path.join(
            _cover_cache_dir(),
            _safe_cover_name(title, artist, _thumbnail_extension(data)),
        )
        with open(path, "wb") as f:
            f.write(bytes(data))
        saved = path if os.path.exists(path) and os.path.getsize(path) > 500 else ""
        _now_playing_debug(f"thumbnail saved: {saved or 'empty'}")
        return saved
    except Exception as exc:
        _now_playing_debug(f"thumbnail error: {type(exc).__name__}: {exc}")
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
        except Exception as exc:
            _now_playing_debug(f"winrt media import failed: {type(exc).__name__}: {exc}")
            try:
                MediaManager = importlib.import_module(
                    "winsdk.windows.media.control"
                ).GlobalSystemMediaTransportControlsSessionManager
                _MediaManager = MediaManager
                _MediaBackend = "winsdk"
                _media_session_available = True
            except Exception as fallback_exc:
                _now_playing_debug(
                    f"winsdk media import failed: {type(fallback_exc).__name__}: {fallback_exc}"
                )
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
        position_seconds = 0.0
        duration_seconds = 0.0
        try:
            playback_status = str(session.get_playback_info().playback_status).lower()
        except Exception:
            pass
        try:
            timeline = session.get_timeline_properties()
            position_seconds = _timeline_seconds(getattr(timeline, "position", 0))
            duration_seconds = _timeline_seconds(getattr(timeline, "end_time", 0))
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
            "position_seconds": round(position_seconds, 2),
            "duration_seconds": round(duration_seconds, 2),
            "time": time.time(),
            "source": "media_session",
            "backend": _MediaBackend or "media_session",
        }
    except Exception as exc:
        _now_playing_debug(f"media session error: {type(exc).__name__}: {exc}")
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


def _session_key(app_id: str, title: str, artist: str) -> str:
    """Build a stable, non-secret identifier for one media session."""
    return "|".join(_norm(value) for value in (app_id, title, artist))


async def _collect_media_sessions_async():
    """Read all GSMTC sessions without touching Tk or the UI thread."""
    global _media_session_checked, _media_session_available, _media_session_reported, _MediaManager, _MediaBackend
    await _get_media_session_async()
    if not _media_session_available or _MediaManager is None:
        return []
    try:
        manager = await _MediaManager.request_async()
        sessions = list(manager.get_sessions() or [])
        current = manager.get_current_session()
        current_app_id = str(getattr(current, "source_app_user_model_id", "") or "").strip() if current else ""
        result = []
        for session in sessions:
            try:
                props = await session.try_get_media_properties_async()
                title = str(getattr(props, "title", "") or "").strip()
                artist = str(getattr(props, "artist", "") or "").strip()
                if not title or _is_bad_media_title(title):
                    continue
                album = str(getattr(props, "album_title", "") or "").strip()
                album_artist = str(getattr(props, "album_artist", "") or "").strip()
                app_id = str(getattr(session, "source_app_user_model_id", "") or "").strip()
                playback_status = ""
                controls = {}
                try:
                    playback = session.get_playback_info()
                    playback_status = str(getattr(playback, "playback_status", "") or "").lower()
                    controls = {
                        "play": bool(getattr(playback, "controls", None) and getattr(playback.controls, "is_play_enabled", False)),
                        "pause": bool(getattr(playback, "controls", None) and getattr(playback.controls, "is_pause_enabled", False)),
                        "next": bool(getattr(playback, "controls", None) and getattr(playback.controls, "is_next_enabled", False)),
                        "previous": bool(getattr(playback, "controls", None) and getattr(playback.controls, "is_previous_enabled", False)),
                    }
                except Exception:
                    pass
                position = 0.0
                duration = 0.0
                try:
                    timeline = session.get_timeline_properties()
                    position = _timeline_seconds(getattr(timeline, "position", 0))
                    duration = _timeline_seconds(getattr(timeline, "end_time", 0))
                except Exception:
                    pass
                key = _session_key(app_id, title, artist)
                result.append({
                    "session_key": key,
                    "title": title,
                    "artist": artist,
                    "album": album,
                    "album_artist": album_artist,
                    "app": _short_app_name(app_id),
                    "app_id": app_id,
                    "playback_status": playback_status,
                    "position_seconds": round(position, 2),
                    "duration_seconds": round(duration, 2),
                    "controls": controls,
                    "selected": bool(app_id and app_id == current_app_id),
                    "source": "media_session",
                    "backend": _MediaBackend or "media_session",
                    "time": time.time(),
                })
            except Exception:
                continue
        return result
    except Exception:
        return []


def list_media_sessions(timeout=1.5):
    """Return current Windows media sessions as plain dictionaries."""
    result: dict[str, Any] = {"value": []}

    def runner():
        try:
            result["value"] = asyncio.run(_collect_media_sessions_async())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                result["value"] = loop.run_until_complete(_collect_media_sessions_async())
            finally:
                loop.close()
        except Exception:
            result["value"] = []

    thread = threading.Thread(target=runner, daemon=True, name="NetOpsMediaSessions")
    thread.start()
    thread.join(max(0.2, float(timeout)))
    return list(result.get("value") or [])


def select_media_session(session_key: str | None) -> bool:
    """Prefer one session for NetOps without changing the system player."""
    global _selected_session_key
    _selected_session_key = str(session_key or "").strip()
    return bool(_selected_session_key)


def selected_media_session() -> str:
    return str(_selected_session_key)


def _selected_media_snapshot(timeout=1.0):
    key = selected_media_session()
    if not key:
        return None
    for item in list_media_sessions(timeout=timeout):
        if item.get("session_key") == key:
            return item
    return None


def media_session_control(action: str, session_key: str | None = None, *, position_seconds: float | None = None, timeout=1.5) -> bool:
    """Control an allowlisted GSMTC action; keyboard fallback remains separate."""
    wanted = str(session_key or selected_media_session()).strip()
    action = str(action or "").strip().lower()
    allowed = {"play", "pause", "play_pause", "next", "previous", "stop", "seek", "shuffle"}
    if action not in allowed:
        return False
    result = {"ok": False}

    async def run():
        if not _media_session_available or _MediaManager is None:
            await _get_media_session_async()
        if not _media_session_available or _MediaManager is None:
            return False
        manager = await _MediaManager.request_async()
        sessions = list(manager.get_sessions() or [])
        target = manager.get_current_session()
        for session in sessions:
            props = await session.try_get_media_properties_async()
            key = _session_key(
                str(getattr(session, "source_app_user_model_id", "") or ""),
                str(getattr(props, "title", "") or ""),
                str(getattr(props, "artist", "") or ""),
            )
            if wanted and key == wanted:
                target = session
                break
        if target is None:
            return False
        if action == "play":
            return bool(await target.try_play_async())
        if action == "pause":
            return bool(await target.try_pause_async())
        if action == "play_pause":
            return bool(await target.try_toggle_play_pause_async())
        if action == "next":
            return bool(await target.try_skip_next_async())
        if action == "previous":
            return bool(await target.try_skip_previous_async())
        if action == "stop":
            return bool(await target.try_stop_async())
        if action == "shuffle":
            return bool(await target.try_change_shuffle_active_async(True))
        if action == "seek" and position_seconds is not None:
            return bool(await target.try_change_playback_position_async(int(max(0.0, float(position_seconds)) * 10_000_000)))
        return False

    def runner():
        try:
            result["ok"] = bool(asyncio.run(run()))
        except Exception:
            result["ok"] = False

    thread = threading.Thread(target=runner, daemon=True, name="NetOpsMediaControl")
    thread.start()
    thread.join(max(0.2, float(timeout)))
    ok = bool(result.get("ok"))
    if ok and action == "seek" and position_seconds is not None:
        _reset_timeline_anchor(position_seconds)
    return ok

def _same_song(a, b):
    if not a or not b:
        return False
    ta, tb = a.get("title", ""), b.get("title", "")
    aa, ab = a.get("artist", ""), b.get("artist", "")
    title_a, title_b = set(_tokens(ta)), set(_tokens(tb))
    overlap = title_a & title_b
    if _similarity(ta, tb) >= 0.55:
        return True
    # Browser titles sometimes prepend the artist while Media Session omits it.
    if len(overlap) >= 2 and (title_a.issubset(title_b) or title_b.issubset(title_a)):
        return True
    if aa and ab and _artist_match(aa, ab) and _similarity(ta, tb) >= 0.35:
        return True
    return False

def get_current_media(force_fresh=False):
    global _last_good_media, _last_good_time, _last_good_monotonic
    global _last_cover_retry_key, _last_cover_retry_attempts
    now = time.time()
    monotonic_now = time.monotonic()

    visible = _get_visible_music_window()
    media = _get_media_session(timeout=0.9)
    selected = _selected_media_snapshot(timeout=0.7)
    if selected and selected.get("title"):
        media = dict(selected)
        media["cover_path"] = ""
        media["publisher"] = selected.get("album_artist") or selected.get("artist") or selected.get("app")

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
            if not chosen.get("app") and media.get("app"):
                chosen["app"] = media.get("app")
            for field in ("position_seconds", "duration_seconds", "controls"):
                if field in media and not chosen.get(field):
                    chosen[field] = media.get(field)
    elif media and media.get("title"):
        chosen = dict(media)

    # A cold GSMTC request can return after the browser title. Retry once per
    # track so the first successful thumbnail can still reach the UI without
    # blocking every refresh when a player exposes no cover art.
    if chosen and chosen.get("title") and not chosen.get("cover_path"):
        retry_key = _session_key(
            str(chosen.get("app_id", "")),
            str(chosen.get("title", "")),
            str(chosen.get("artist", "")),
        )
        if retry_key and retry_key != _last_cover_retry_key:
            _last_cover_retry_key = retry_key
            _last_cover_retry_attempts = 0
        if retry_key and _last_cover_retry_attempts < _MAX_COVER_RETRY_ATTEMPTS:
            _last_cover_retry_attempts += 1
            retry_media = _get_media_session(timeout=1.5)
            if (
                retry_media
                and retry_media.get("cover_path")
                and _same_song(chosen, retry_media)
            ):
                chosen["cover_path"] = retry_media["cover_path"]
                for field in ("artist", "album", "app", "playback_status", "controls"):
                    if not chosen.get(field) and retry_media.get(field):
                        chosen[field] = retry_media[field]

    if chosen and chosen.get("title") and not chosen.get("cover_path"):
        cached_cover = _cached_cover_path(chosen.get("title"), chosen.get("artist"))
        if cached_cover:
            chosen["cover_path"] = cached_cover
        else:
            _schedule_cover_lookup(chosen)
            _schedule_cover_probe(chosen)

    if chosen and chosen.get("title") and _is_bad_media_title(chosen.get("title")):
        chosen = None

    if chosen and chosen.get("title"):
        if _last_good_media and _same_song(_last_good_media, chosen):
            previous_cover = str(_last_good_media.get("cover_path") or "")
            if (
                not chosen.get("cover_path")
                and previous_cover
                and os.path.isfile(previous_cover)
            ):
                # GSMTC can briefly omit the thumbnail while a track changes.
                # Keep the same track's last valid art instead of flashing blank.
                chosen["cover_path"] = previous_cover
            elapsed = (
                monotonic_now - _last_good_monotonic
                if _last_good_monotonic > 0
                else now - _last_good_time
            )
            chosen = _smooth_live_timeline(
                chosen,
                _last_good_media,
                elapsed=elapsed,
            )
        # Safety: if no valid cover for current song, keep blank. UI will show fallback card.
        cover = str(chosen.get("cover_path") or "")
        if cover and not os.path.exists(cover):
            chosen["cover_path"] = ""
        _last_good_media = chosen
        _last_good_time = now
        _last_good_monotonic = monotonic_now
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
    if media_session_control("play_pause"):
        return True
    return _control("play_pause")

def media_next():
    if media_session_control("next"):
        return True
    return _control("next")

def media_previous():
    if media_session_control("previous"):
        return True
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
