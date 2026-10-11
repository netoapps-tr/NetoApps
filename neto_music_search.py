# NetOps - YouTube Music Slot/Profile Player
# v10.32 two-slot queue-safe rewrite
#
# KRİTİK MANTIK:
# - Var olan YouTube Music kuyruğuna K/Space/Enter/Next/PlayPause/mouse gönderilmez.
# - Her şarkı isteği en fazla 2 ayrı güvenli Chrome/Edge app profili arasında yönetilir.
# - 1. slot doluysa 2. slotta açılır.
# - 2 slot da doluysa yeni profil açılmaz; sıradaki slot yeniden kullanılır.
# - Ctrl+Alt+Sol/Sağ app içinden slot 1 / slot 2 arasında geçiş için kullanılır.

from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request
import webbrowser
from typing import Any, Dict, List, cast

CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 180
SLOT_COUNT = 2

ALIASES = {
    "salla": "Atiye Salla",
    "kamera": "Simge Kamera",
    "simge kamera": "Simge Kamera",
    "miş miş": "Simge Miş Miş",
    "mis mis": "Simge Miş Miş",
    "önümüz yaz": "Simge Önümüz Yaz",
    "onumuz yaz": "Simge Önümüz Yaz",
}


def clean_query(query: str) -> str:
    query = str(query or "").strip()
    query = re.sub(r"\s+", " ", query)
    return query


def resolve_alias(query: str) -> str:
    cleaned = clean_query(query)
    return ALIASES.get(cleaned.lower(), cleaned)


def cache_key(query: str) -> str:
    return clean_query(query).lower()


def app_data_dir() -> str:
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
        return os.path.join(root, "NetoAssistant")
    return os.path.join(os.path.expanduser("~"), ".neto_assistant")


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def log(message: str) -> None:
    try:
        log_dir = ensure_dir(os.path.join(app_data_dir(), "logs"))
        with open(os.path.join(log_dir, "music_search.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S") + " " + str(message) + "\n")
    except Exception:
        pass


def slot_root_dir() -> str:
    return ensure_dir(os.path.join(app_data_dir(), "ytmusic_slots"))


def slot_profile_dir(slot: int) -> str:
    slot = 1 if int(slot) == 1 else 2
    return ensure_dir(os.path.join(slot_root_dir(), f"slot_{slot}_profile"))


def state_path() -> str:
    return os.path.join(slot_root_dir(), "slot_state.json")


def default_state() -> Dict[str, Any]:
    return {
        "last_slot": 0,
        "slots": {
            "1": {"used": False, "url": "", "title": "", "updated_at": 0},
            "2": {"used": False, "url": "", "title": "", "updated_at": 0},
        },
    }


def load_state() -> Dict[str, Any]:
    state = default_state()
    try:
        path = state_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                state.update(data)
                slots = state.setdefault("slots", {})
                for s in ("1", "2"):
                    base = default_state()["slots"][s]
                    if not isinstance(slots.get(s), dict):
                        slots[s] = base
                    else:
                        merged = dict(base)
                        merged.update(slots[s])
                        slots[s] = merged
    except Exception as exc:
        log("load_state failed: " + str(exc))
    return state


def save_state(state: Dict[str, Any]) -> None:
    try:
        ensure_dir(slot_root_dir())
        with open(state_path(), "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        log("save_state failed: " + str(exc))


def choose_slot() -> Dict[str, Any]:
    """Return slot decision. Max 2 profiles; never creates 3rd profile."""
    state = load_state()
    slots = state.setdefault("slots", default_state()["slots"])
    used1 = bool(slots.get("1", {}).get("used") or slots.get("1", {}).get("url"))
    used2 = bool(slots.get("2", {}).get("used") or slots.get("2", {}).get("url"))

    if not used1:
        return {"slot": 1, "message": "NetOps: 1. slot boş, 1.'de açıyorum.", "state": state}
    if not used2:
        return {"slot": 2, "message": "NetOps: 1. dolu, 2.'de açıyorum.", "state": state}

    last = int(state.get("last_slot") or 1)
    slot = 2 if last == 1 else 1
    return {"slot": slot, "message": f"NetOps: maksimum 2 slot var, {slot}. slotu değiştiriyorum.", "state": state}


def mark_slot(slot: int, url: str, title: str) -> Dict[str, Any]:
    state = load_state()
    slot = 1 if int(slot) == 1 else 2
    state["last_slot"] = slot
    state.setdefault("slots", default_state()["slots"])[str(slot)] = {
        "used": True,
        "url": str(url or ""),
        "title": str(title or ""),
        "updated_at": time.time(),
    }
    save_state(state)
    return state


def youtube_music_watch_url(video_id: str) -> str:
    video_id = str(video_id or "").strip()
    if not video_id:
        return ""
    # list/queue param yok; böylece mevcut kuyruğa dokunmaz.
    return "https://music.youtube.com/watch?v=" + urllib.parse.quote(video_id)


def normalize_text(value: str) -> str:
    value = str(value or "").lower()
    value = value.replace("ı", "i").replace("ğ", "g").replace("ü", "u").replace("ş", "s").replace("ö", "o").replace("ç", "c")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def similarity_score(query: str, text: str) -> int:
    q_words = [w for w in normalize_text(query).split() if len(w) > 1]
    hay = normalize_text(text)
    if not q_words or not hay:
        return 0
    score = 0
    for word in q_words:
        if word in hay:
            score += 25
    if normalize_text(query) in hay:
        score += 100
    return score


def item_artists(item: Dict[str, Any]) -> str:
    names: List[str] = []
    for artist in item.get("artists", []) or []:
        if isinstance(artist, dict) and artist.get("name"):
            names.append(str(artist.get("name")))
    return ", ".join(names)


def score_ytmusic_item(query: str, item: Dict[str, Any]) -> int:
    title = str(item.get("title") or "")
    artists = item_artists(item)
    album = ""
    if isinstance(item.get("album"), dict):
        album = str(item.get("album", {}).get("name") or "")
    result_type = str(item.get("resultType") or item.get("category") or "").lower()
    combined = f"{title} {artists} {album}"

    score = 0
    if item.get("videoId"):
        score += 500
    if result_type == "song":
        score += 350
    elif "song" in result_type or "şark" in result_type:
        score += 220
    elif result_type == "video":
        score += 30

    score += similarity_score(query, combined)

    title_l = title.lower()
    bad_words = [
        "mix", "playlist", "full album", "album", "1 hour", "hour", "saat",
        "karaoke", "reaction", "cover", "slowed", "sped up", "remix playlist",
    ]
    for bad in bad_words:
        if bad in title_l:
            score -= 80

    return score


def search_with_ytmusicapi(query: str) -> Dict[str, Any]:
    try:
        from ytmusicapi import YTMusic
        ytmusic = YTMusic()

        results = ytmusic.search(query, filter="songs", limit=10) or []
        if not results:
            results = ytmusic.search(query, limit=12) or []

        candidates = [item for item in results if isinstance(item, dict) and item.get("videoId")]
        if not candidates:
            return {"ok": False, "error": "ytmusicapi videoId bulamadı"}

        best = max(candidates, key=lambda item: score_ytmusic_item(query, item))
        video_id = str(best.get("videoId") or "").strip()
        if not video_id:
            return {"ok": False, "error": "ytmusicapi sonucu videoId içermiyor"}

        return {
            "ok": True,
            "video_id": video_id,
            "title": str(best.get("title") or query),
            "artist": item_artists(best),
            "source": "ytmusicapi",
        }
    except Exception as exc:
        return {"ok": False, "error": "ytmusicapi: " + str(exc)}


def extract_video_id(value: str) -> str:
    value = str(value or "")
    match = re.search(r"(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{6,})", value)
    if match:
        return match.group(1)
    if re.match(r"^[A-Za-z0-9_-]{6,}$", value):
        return value
    return ""


def search_with_ytdlp_backup(query: str) -> Dict[str, Any]:
    try:
        from yt_dlp import YoutubeDL
        options: Dict[str, Any] = {
            "quiet": True,
            "skip_download": True,
            "noplaylist": True,
            "extract_flat": True,
            "socket_timeout": 8,
            "default_search": "ytsearch1",
            "nocheckcertificate": True,
        }
        with YoutubeDL(cast(Any, options)) as ydl:
            info = ydl.extract_info("ytsearch1:" + query, download=False)
        info_data: Any = info or {}
        entries_raw: Any = info_data.get("entries") or []
        entries = list(entries_raw)
        if not entries:
            return {"ok": False, "error": "yt-dlp sonuç bulamadı"}
        first = entries[0] or {}
        video_id = extract_video_id(first.get("id") or first.get("url") or first.get("webpage_url") or "")
        if not video_id:
            return {"ok": False, "error": "yt-dlp videoId bulamadı"}
        return {
            "ok": True,
            "video_id": video_id,
            "title": str(first.get("title") or query),
            "artist": "",
            "source": "yt-dlp-backup",
        }
    except Exception as exc:
        return {"ok": False, "error": "yt-dlp: " + str(exc)}


def search_with_html_backup(query: str) -> Dict[str, Any]:
    try:
        url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query)
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 Windows Chrome Safari",
                "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        )
        with urllib.request.urlopen(request, timeout=8) as response:
            html = response.read().decode("utf-8", "ignore")
        ids = re.findall(r'"videoId":"([A-Za-z0-9_-]{6,})"', html)
        unique_ids = []
        for video_id in ids:
            if video_id not in unique_ids:
                unique_ids.append(video_id)
        if not unique_ids:
            return {"ok": False, "error": "HTML fallback videoId bulamadı"}
        return {
            "ok": True,
            "video_id": unique_ids[0],
            "title": query,
            "artist": "",
            "source": "html-backup",
        }
    except Exception as exc:
        return {"ok": False, "error": "html: " + str(exc)}


def find_first_song(query: str) -> Dict[str, Any]:
    original_query = clean_query(query)
    resolved_query = resolve_alias(original_query)
    if not resolved_query:
        return {"ok": False, "error": "empty query"}

    key = cache_key(resolved_query)
    now = time.time()
    cached = CACHE.get(key)
    if cached and now - cached.get("time", 0) < CACHE_TTL_SECONDS:
        return dict(cached["result"])

    result = search_with_ytmusicapi(resolved_query)

    if not result.get("ok"):
        ytdlp_result = search_with_ytdlp_backup(resolved_query)
        if ytdlp_result.get("ok"):
            result = ytdlp_result
        else:
            result["yt_dlp_error"] = ytdlp_result.get("error")

    if not result.get("ok"):
        html_result = search_with_html_backup(resolved_query)
        if html_result.get("ok"):
            result = html_result
        else:
            result["html_error"] = html_result.get("error")

    if result.get("ok"):
        video_id = str(result.get("video_id") or "")
        if not video_id:
            return {"ok": False, "error": "Arama sonucu video kimliği içermiyor"}
        result["query"] = original_query
        result["resolved_query"] = resolved_query
        result["url"] = youtube_music_watch_url(video_id)
        CACHE[key] = {"time": now, "result": dict(result)}

    return result


def hidden_flags() -> int:
    if os.name != "nt":
        return 0
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def browser_candidates() -> List[str]:
    if os.name != "nt":
        return []
    return [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        "chrome.exe",
        "msedge.exe",
    ]


def open_url_in_slot(url: str, slot: int) -> bool:
    """
    Queue-safe open:
    - no keyboard automation
    - no mouse automation
    - max two isolated app profiles
    - does not touch active YouTube Music player's queue/buttons
    """
    url = str(url or "").strip()
    if not url:
        return False
    slot = 1 if int(slot) == 1 else 2
    profile_dir = slot_profile_dir(slot)

    if os.name == "nt":
        for browser in browser_candidates():
            try:
                subprocess.Popen(
                    [
                        browser,
                        "--new-window",
                        "--app=" + url,
                        "--user-data-dir=" + profile_dir,
                        "--no-first-run",
                        "--disable-features=TranslateUI",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=hidden_flags(),
                )
                log(f"slot {slot} opened: {url}")
                return True
            except Exception as exc:
                log(f"browser failed slot {slot}: {browser} / {exc}")
                continue

        try:
            subprocess.Popen(
                ["cmd", "/c", "start", "", url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=hidden_flags(),
            )
            log(f"fallback cmd start slot {slot}: {url}")
            return True
        except Exception as exc:
            log("cmd start failed: " + str(exc))

    try:
        ok = bool(webbrowser.open(url, new=1, autoraise=True))
        if ok:
            log(f"webbrowser opened slot {slot}: {url}")
        return ok
    except Exception as exc:
        log("webbrowser failed: " + str(exc))
        return False


def search_and_play(
    query: str,
    *,
    open_url=None,
    autoplay: bool = True,
) -> Dict[str, Any]:
    """Search a song and open it through the supplied UI adapter when present."""
    result = find_first_song(query)
    if not result.get("ok"):
        return result

    video_id = str(result.get("video_id") or "")
    url = str(result.get("url") or "") or (youtube_music_watch_url(video_id) if video_id else "")
    if not url:
        return {"ok": False, "error": "YouTube Music URL üretilemedi"}

    slot = None
    decision = {"message": ""}
    action_status = ""
    if callable(open_url):
        try:
            opened_result = open_url(url, bool(autoplay))
            if isinstance(opened_result, dict):
                opened = bool(opened_result.get("ok", True))
                action_status = str(opened_result.get("status") or "")
            elif isinstance(opened_result, str):
                action_status = opened_result
                opened = opened_result not in {"failed", "not_found"}
            else:
                opened = opened_result is not False
        except Exception as exc:
            opened = False
            result["adapter_error"] = str(exc)[:220]
        result["opened_via"] = "netops_browser"
    else:
        decision = choose_slot()
        slot = int(decision["slot"])
        opened = open_url_in_slot(url, slot)
        if opened:
            mark_slot(slot, url, result.get("title") or result.get("resolved_query") or query)

    result["opened"] = opened
    result["slot"] = slot
    result["action_status"] = action_status or ("opened" if opened else "failed")
    result["slot_message"] = decision.get("message", "")
    result["max_slots"] = SLOT_COUNT
    result["queue_safe"] = True
    result["keyboard_automation"] = False
    result["mouse_automation"] = False

    if not opened:
        result["ok"] = False
        result["error"] = "YouTube Music slot penceresi açılamadı"
    return result


def switch_to_slot(slot: int) -> Dict[str, Any]:
    slot = 1 if int(slot) == 1 else 2
    state = load_state()
    info = state.get("slots", {}).get(str(slot), {})
    url = str(info.get("url") or "").strip()
    if not url:
        return {"ok": False, "slot": slot, "error": f"{slot}. slot boş"}
    opened = open_url_in_slot(url, slot)
    if opened:
        state["last_slot"] = slot
        save_state(state)
    return {
        "ok": opened,
        "slot": slot,
        "title": info.get("title") or "",
        "url": url,
        "message": f"NetOps: {slot}. slota geçiliyor.",
        "error": "slot açılamadı" if not opened else "",
    }


def reset_slots() -> Dict[str, Any]:
    state = default_state()
    save_state(state)
    return {"ok": True, "message": "NetOps: müzik slotları sıfırlandı."}


# Eski Neto kodları bozulmasın diye uyumluluk fonksiyonları.
def play_song(query: str) -> bool:
    return bool(search_and_play(query).get("ok"))


def find_youtube_music_url(query: str, timeout: int = 8) -> str:
    result = find_first_song(query)
    if not result.get("ok"):
        return ""
    video_id = str(result.get("video_id") or "")
    return str(result.get("url") or "") or (youtube_music_watch_url(video_id) if video_id else "")
