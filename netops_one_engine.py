# NETOPS ONE ENGINE
# Saf Python: LLM/Ollama/AI API yok. Structured search API -> temiz özet -> PyQt6 kart renderer.

from __future__ import annotations

import html as _html
import json
import os
import re
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

try:
    import neto_sohbet_v2
except Exception:  # pragma: no cover
    neto_sohbet_v2 = None

try:
    from config import KUFUR_LISTESI as _NETOPS_CONFIG_PROFANITY
except Exception:  # pragma: no cover
    _NETOPS_CONFIG_PROFANITY = []

try:
    from neto_adaptive_intent import AdaptiveIntentModel
except Exception:  # pragma: no cover - keep minimal installs usable
    AdaptiveIntentModel = None

VERSION = "2.1"
MEMORY_FILE = "netops_memory.json"
WORD_CORE_FILE = "netops_word_core.json"
FALLBACK_MESSAGE = "Aradığınız konuyla ilgili Türkçe sonuç bulunamadı."

NETOPS_ONE_CORE_SYSTEM_PROMPT = """[NETOPS_ONE_CORE_SYSTEM_PROMPT]
Kimlik: NetOps One Engine.
Rol: Sentetik masaüstü kontrol motoru, yerel bilgi işleyici ve kod mimarisi.
Dil: Türkçe.
Ton: Kısa, net ve doğal.
Yasaklı çıktı: URL dökümü, ham arama listesi, model kimliği, gereksiz nezaket dolgusu.
Kod standardı: Verilen Python, PyQt6 ve Lua örnekleri tam, çalıştırılabilir bloklar olmalıdır.
Güvenlik: Riskli sistem işlemleri onay sistemi dışında çalıştırılamaz.
İç muhakeme: Gizli akıl yürütme, debug bloğu ve durum paneli kullanıcı arayüzünde gösterilmez.
"""

CommandDetector = Callable[[str], str | None]


@dataclass
class NetOpsOneResult:
    ok: bool
    text: str
    intent: str
    source: str = "netops_one"
    command: str | None = None
    cached: bool = False
    learned: bool = False
    query: str = ""
    title: str = "NetOps One"

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "text": self.text,
            "intent": self.intent,
            "source": self.source,
            "command": self.command,
            "cached": self.cached,
            "learned": self.learned,
            "query": self.query,
            "title": self.title,
        }


@dataclass
class SearchItem:
    title: str
    body: str
    url: str = ""


class QueryNormalizer:
    """Regex tabanlı sıkı Türkçe sorgu temizleyici."""

    FILLER_PATTERNS = [
        r"\bbana\b",
        r"\bbenim\s+için\b",
        r"\bbenim\s+icin\b",
        r"\blütfen\b",
        r"\blutfen\b",
        r"\bnedir\b",
        r"\bne\s+demek\b",
        r"\bhakkında\s+bilgi\b",
        r"\bhakkinda\s+bilgi\b",
        r"\bhakkında\b",
        r"\bhakkinda\b",
        r"\btarifini\s+ver\b",
        r"\btarifi\s+ver\b",
        r"\böğrenebilir\s+misin\b",
        r"\bogrenebilir\s+misin\b",
        r"\bverir\s+misin\b",
        r"\bverirmisin\b",
        r"\banlatır\s+mısın\b",
        r"\banlatir\s+misin\b",
        r"\bsöyler\s+misin\b",
        r"\bsoyler\s+misin\b",
        r"\b(webde|webden|internette|internet|google'?da|duckduckgo'?da)\s+(ara|bak|arat|araştır|arastir)\b",
        r"\b(ara|arat|bak|anlat|açıkla|acikla|söyle|soyle|ver)\b",
    ]

    @classmethod
    def clean(cls, user_input: Any) -> str:
        query = str(user_input or "").casefold()
        query = re.sub(r"[\n\r\t]+", " ", query)
        query = cls._normalize_common_suffixes(query)
        for pattern in cls.FILLER_PATTERNS:
            query = re.sub(pattern, " ", query, flags=re.I)
        query = re.sub(r"[^\wçğıöşüÇĞİÖŞÜ0-9\s+-]", " ", query, flags=re.UNICODE)
        query = re.sub(r"\s+", " ", query).strip()
        return query

    @staticmethod
    def _normalize_common_suffixes(query: str) -> str:
        # Örnek hedef: "raspery pi fiyatlarını öğrenebilir misin" -> "raspery pi fiyatları".
        query = re.sub(r"\bfiyatlarını\b", "fiyatları", query, flags=re.I)
        query = re.sub(r"\bfiyatlarini\b", "fiyatları", query, flags=re.I)
        query = re.sub(r"\btarifini\b", "tarifi", query, flags=re.I)
        return query


class StructuredSearchClient:
    """HTML kazımaz; duckduckgo_search veya SearXNG JSON sonucunu kullanır."""

    BLOCKED_HOST_PARTS = (
        "youtube.com", "youtu.be", "tiktok.com", "instagram.com", "facebook.com", "x.com", "twitter.com",
        "reddit.com", "pinterest.", "wiktionary.org", "eksisozluk.com", "sozluk.gov.tr", "genius.com",
        "azlyrics.com", "lyrics.com", "musixmatch.com", "songlyrics.com", "nhl.com", "nba.com", "nfl.com", "espn.com",
    )

    def search(self, query: str, limit: int = 3) -> list[SearchItem]:
        query = str(query or "").strip()
        if not query:
            return []
        items = self._duckduckgo(query, limit=limit)
        if not items:
            items = self._searxng(query, limit=limit)
        return self._filter(items)[:limit]

    def _duckduckgo(self, query: str, limit: int) -> list[SearchItem]:
        try:
            from duckduckgo_search import DDGS
            rows: list[SearchItem] = []
            with DDGS() as ddgs:
                for raw in ddgs.text(keywords=query, region="tr-tr", safesearch="on", max_results=limit * 3):
                    if not isinstance(raw, dict):
                        continue
                    rows.append(SearchItem(
                        title=str(raw.get("title") or "").strip(),
                        body=str(raw.get("body") or raw.get("snippet") or "").strip(),
                        url=str(raw.get("href") or raw.get("url") or "").strip(),
                    ))
            return rows
        except Exception:
            return []

    def _searxng(self, query: str, limit: int) -> list[SearchItem]:
        endpoint = os.environ.get("NETOPS_SEARXNG_URL", "").strip()
        if not endpoint:
            return []
        try:
            import requests
            response = requests.get(
                endpoint,
                params={"q": query, "format": "json", "language": "tr", "safesearch": 1},
                headers={"Accept-Language": "tr-TR,tr;q=0.95", "User-Agent": "NetOpsOne/2.1"},
                timeout=8,
            )
            if response.status_code >= 400:
                return []
            data = response.json()
            rows: list[SearchItem] = []
            for raw in data.get("results") or []:
                if not isinstance(raw, dict):
                    continue
                rows.append(SearchItem(
                    title=str(raw.get("title") or "").strip(),
                    body=str(raw.get("content") or raw.get("body") or "").strip(),
                    url=str(raw.get("url") or "").strip(),
                ))
            return rows[: limit * 3]
        except Exception:
            return []

    def _filter(self, items: list[SearchItem]) -> list[SearchItem]:
        clean: list[SearchItem] = []
        seen: set[str] = set()
        for item in items:
            if not item.title and not item.body:
                continue
            if self.is_blocked(item.url, item.title, item.body):
                continue
            title = TextFormatter.clean_inline(item.title)
            body = TextFormatter.clean_inline(item.body)
            if len(title + body) < 30:
                continue
            key = re.sub(r"\W+", "", f"{title} {body}".casefold())[:120]
            if not key or key in seen:
                continue
            seen.add(key)
            clean.append(SearchItem(title=title, body=body, url=""))
        return clean

    @classmethod
    def is_blocked(cls, url: str = "", title: str = "", body: str = "") -> bool:
        host = urlparse(str(url or "")).netloc.lower().replace("www.", "")
        full = f"{host} {url} {title} {body}".casefold()
        blocked_words = ("lyrics", "şarkı sözü", "sarki sozu", "songtext", "wiktionary", "sözlük", "sozluk")
        return any(part in host for part in cls.BLOCKED_HOST_PARTS) or any(word in full for word in blocked_words)


class TextFormatter:
    """Structured JSON title/body alanlarını temiz, link içermeyen kart metnine çevirir."""

    @classmethod
    def format_results(cls, query: str, items: list[SearchItem]) -> tuple[str, str]:
        cleaned = []
        for item in items[:3]:
            if StructuredSearchClient.is_blocked(item.url, item.title, item.body):
                continue
            text = cls.clean_inline(f"{item.title}. {item.body}")
            if text:
                cleaned.append(text)
        cleaned = cls.dedupe(cleaned)
        if not cleaned:
            return "NetOps One", FALLBACK_MESSAGE
        title = cls.title_from_query(query)
        content = "\n".join(f"• {entry}" for entry in cleaned)
        return title, content[:2600]

    @staticmethod
    def title_from_query(query: str) -> str:
        query = re.sub(r"\s+", " ", str(query or "")).strip()
        if not query:
            return "NetOps One"
        return query[:1].upper() + query[1:80]

    @staticmethod
    def clean_inline(text: str) -> str:
        value = _html.unescape(str(text or ""))
        value = re.sub(r"https?://\S+", " ", value)
        value = re.sub(r"\b(?:[a-z0-9-]+\.)+(?:com|net|org|tr|io|dev|edu|gov|co)(?:/\S*)?", " ", value, flags=re.I)
        value = re.sub(r"(?i)\b(kaynak|source|url|link|snippet|cached)\s*:.*$", " ", value)
        value = re.sub(r"(?i)\b(click here|read more|devamını oku|reklam|sponsored)\b", " ", value)
        value = re.sub(r"\s+", " ", value)
        return value.strip(" -:\n\t")

    @staticmethod
    def dedupe(items: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for item in items:
            clean = re.sub(r"\s+", " ", str(item or "")).strip()
            key = re.sub(r"\W+", "", clean.casefold())[:110]
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(clean)
        return out


class NetOpsOneEngine:
    """Komut -> hızlı cevap -> hafıza -> structured JSON search."""

    def __init__(
        self,
        project_dir: str | Path | None = None,
        command_detector: CommandDetector | None = None,
        internet_enabled: Callable[[], bool] | bool = True,
        max_sources: int = 3,
    ) -> None:
        self.project_dir = Path(project_dir).resolve() if project_dir else Path(__file__).resolve().parent
        self.memory_path = self.project_dir / MEMORY_FILE
        self.word_core_path = self.project_dir / WORD_CORE_FILE
        self.command_detector = command_detector
        self.internet_enabled = internet_enabled
        self.max_sources = max(1, min(3, int(max_sources or 3)))
        self.search_client = StructuredSearchClient()
        self.ensure_memory()

    def answer(self, message: Any, *, agent_mode: bool = False) -> NetOpsOneResult:
        raw = str(message or "").strip()
        normalized = self.normalize(raw)
        if not normalized:
            return NetOpsOneResult(False, "Bir şey yazmadın.", "empty", source="local", title="NetOps One")

        command = self.detect_command(normalized)
        if command:
            return NetOpsOneResult(True, command, "command", source="netops_command", command=command, title="Komut")

        quick = self.quick_reply(raw, agent_mode=agent_mode)
        if quick:
            self._remember_last(raw, quick, intent="quick_chat", source="local")
            return NetOpsOneResult(True, quick, "quick_chat", source="local", title="NetOps One")

        query = self.normalize_query(raw)
        memory_hit = self.memory_lookup(query) or self.memory_lookup(raw)
        if memory_hit:
            return NetOpsOneResult(True, memory_hit, "memory", source=MEMORY_FILE, cached=True, query=query, title="Hafızadan")

        result = self.search_web(raw)
        if result.ok:
            self.memory_store(raw, result.text, source=result.source, query=result.query, title=result.title)
            result.learned = True
        return result

    def detect_command(self, normalized_message: str) -> str | None:
        if not self.command_detector:
            return None
        try:
            command = self.command_detector(normalized_message)
            return command.strip() if isinstance(command, str) and command.strip() else None
        except Exception:
            return None

    def quick_reply(self, message: str, *, agent_mode: bool = False) -> str | None:
        if neto_sohbet_v2 is not None:
            try:
                quick = neto_sohbet_v2.quick_reply(message, agent_modu=agent_mode, project=self.project_dir)
                if quick:
                    return TextFormatter.clean_inline(str(quick))
            except Exception:
                pass
        greetings = {
            "selam": "NETOPS_ONE_READY",
            "merhaba": "NETOPS_ONE_READY",
            "sa": "NETOPS_ONE_READY",
            "slm": "NETOPS_ONE_READY",
        }
        return greetings.get(self.normalize(message))

    def search_web(self, message: str) -> NetOpsOneResult:
        query = self.normalize_query(message)
        if not query or not self._internet_is_enabled():
            return self.fallback_result(query)
        items = self.search_client.search(query, limit=self.max_sources)
        title, text = TextFormatter.format_results(query, items)
        ok = bool(items and text != FALLBACK_MESSAGE)
        return NetOpsOneResult(ok, text, "structured_search" if ok else "search_empty", source="duckduckgo_search", query=query, title=title)

    def fallback_result(self, query: str) -> NetOpsOneResult:
        return NetOpsOneResult(False, FALLBACK_MESSAGE, "search_empty", source="local_fallback", query=query, title="NetOps One")

    def should_search(self, message: str) -> bool:
        return bool(str(message or "").strip())

    def normalize_query(self, message: str) -> str:
        return QueryNormalizer.clean(message)

    def memory_lookup(self, message: str) -> str | None:
        data = self.load_memory()
        items = data.get("items") if isinstance(data, dict) else None
        if not isinstance(items, dict):
            return None
        key = self.normalize(message)
        direct = items.get(key)
        if isinstance(direct, dict) and str(direct.get("answer") or "").strip():
            direct["hits"] = int(direct.get("hits") or 0) + 1
            direct["lastUsedAt"] = self._now()
            self.save_memory(data)
            return TextFormatter.clean_inline(str(direct.get("answer") or ""))
        return None

    def memory_store(self, message: str, answer: str, *, source: str = "web", query: str = "", title: str = "") -> None:
        clean_answer = TextFormatter.clean_inline(str(answer or ""))
        if not clean_answer or clean_answer == FALLBACK_MESSAGE:
            return
        data = self.load_memory()
        items = data.setdefault("items", {})
        key = self.normalize(query or message)
        if not key:
            return
        items[key] = {
            "question": str(message).strip(),
            "query": query or self.normalize_query(message),
            "title": TextFormatter.clean_inline(title or "NetOps One")[:90],
            "answer": clean_answer,
            "source": source,
            "createdAt": self._now(),
            "lastUsedAt": self._now(),
            "hits": 0,
        }
        data["version"] = VERSION
        data["updatedAt"] = self._now()
        self.save_memory(data)

    def ensure_memory(self) -> dict[str, Any]:
        default = {"version": VERSION, "items": {}, "last": {}, "updatedAt": self._now()}
        if not self.memory_path.exists():
            self.memory_path.write_text(json.dumps(default, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return default
        data = self.load_memory()
        changed = False
        if not isinstance(data.get("items"), dict):
            data["items"] = {}
            changed = True
        if not isinstance(data.get("last"), dict):
            data["last"] = {}
            changed = True
        if data.get("version") != VERSION:
            data["version"] = VERSION
            changed = True
        if changed:
            self.save_memory(data)
        return data

    def load_memory(self) -> dict[str, Any]:
        try:
            data = json.loads(self.memory_path.read_text(encoding="utf-8-sig"))
            return data if isinstance(data, dict) else {"version": VERSION, "items": {}, "last": {}}
        except Exception:
            backup = self.memory_path.with_suffix(self.memory_path.suffix + ".bozuk.bak")
            try:
                if self.memory_path.exists():
                    self.memory_path.replace(backup)
            except Exception:
                pass
            return {"version": VERSION, "items": {}, "last": {}, "updatedAt": self._now()}

    def save_memory(self, data: dict[str, Any]) -> None:
        self.memory_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _remember_last(self, message: str, answer: str, *, intent: str, source: str) -> None:
        data = self.load_memory()
        data["last"] = {
            "message": str(message).strip(),
            "answer": TextFormatter.clean_inline(str(answer).strip()),
            "intent": intent,
            "source": source,
            "time": self._now(),
        }
        data["updatedAt"] = self._now()
        self.save_memory(data)

    def _internet_is_enabled(self) -> bool:
        try:
            return bool(self.internet_enabled() if callable(self.internet_enabled) else self.internet_enabled)
        except Exception:
            return True

    @staticmethod
    def normalize(text: Any) -> str:
        if neto_sohbet_v2 is not None:
            try:
                return neto_sohbet_v2.temizle(text)
            except Exception:
                pass
        value = str(text or "").casefold().strip()
        table = str.maketrans({"ı": "i", "İ": "i", "ğ": "g", "ü": "u", "ş": "s", "ö": "o", "ç": "c"})
        value = value.translate(table)
        value = re.sub(r"\s+", " ", value)
        return value.strip(" \t\r\n.!?")

    @staticmethod
    def _now() -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S")


class NetOpsOneCardRenderer:
    """PyQt6 için koyu temalı, yuvarlatılmış, fade-in animasyonlu cevap kartı."""

    def __init__(self, parent_layout: Any) -> None:
        self.parent_layout = parent_layout

    def add_card(self, result: NetOpsOneResult) -> Any:
        try:
            from PyQt6.QtCore import QEasingCurve, QPropertyAnimation
            from PyQt6.QtWidgets import QFrame, QGraphicsOpacityEffect, QLabel, QVBoxLayout
        except Exception:
            return None

        card = QFrame()
        card.setObjectName("netopsOneCard")
        card.setStyleSheet(
            "QFrame#netopsOneCard { background:#151821; border:1px solid #2b7cff; border-radius:18px; }"
            "QLabel#netopsOneTitle { color:#65a8ff; font-size:15px; font-weight:700; }"
            "QLabel#netopsOneContent { color:#f2f6ff; font-size:14px; line-height:1.45; }"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 16)
        layout.setSpacing(10)

        title = QLabel(result.title or "NetOps One")
        title.setObjectName("netopsOneTitle")
        content = QLabel(result.text or FALLBACK_MESSAGE)
        content.setObjectName("netopsOneContent")
        content.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(content)
        self.parent_layout.addWidget(card)

        effect = QGraphicsOpacityEffect(card)
        card.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", card)
        animation.setDuration(260)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        card._netops_fade_animation = animation
        animation.start()
        return card


def ensure_files(project: str | Path = ".") -> dict[str, Any]:
    engine = NetOpsOneEngine(project_dir=project)
    data = engine.ensure_memory()
    return {"ok": True, "path": str(engine.memory_path), "items": len(data.get("items") or {}), "version": VERSION}


def answer(message: Any, **kwargs: Any) -> str:
    allowed = {"project_dir", "command_detector", "internet_enabled", "max_sources"}
    return NetOpsOneEngine(**{k: v for k, v in kwargs.items() if k in allowed}).answer(message).text

# NETOPS ONE 3.0 EXTENSION
# This section supersedes the legacy engine definitions above.
import datetime as _netops_dt
import threading as _netops_threading
from urllib.parse import urlparse as _netops_urlparse

NETOPS_ONE_VERSION = "3.0"
NETOPS_ONE_WORD_CORE_VERSION = "1.0"
NETOPS_ONE_FALLBACK = (
    "Bu konu için güvenilir Türkçe bilgi bulamadım veya içerik okunamadı. "
    "İstersen farklı kelimelerle tekrar arayabilirim."
)
NETOPS_ONE_POLITE_WARNING = "Bu şekilde öğrenemem veya devam edemem. Daha temiz yazarsan yardımcı olurum."
RECIPE_HINTS = (
    "tarif", "malzeme", "hazırlanışı", "hazirlanisi", "yapılışı", "yapilisi",
    "nasıl yapılır", "nasil yapilir",
)
MUSIC_PLAY_RE = re.compile(
    r"\b(?:çal|cal|dinlet|oynat|başlat|baslat)\b|"
    r"\b(?:youtube\s*music|youtube|spotify)\b.*\b(?:aç|ac|çal|cal|oynat)\b",
    flags=re.IGNORECASE,
)
NETOPS_ONE_WORD_CORE = {
    "version": NETOPS_ONE_WORD_CORE_VERSION,
    "intents": {
        "greeting": ["selam", "merhaba", "hey", "sa", "slm", "günaydın", "iyi akşamlar"],
        "wellbeing": ["nasılsın", "naber", "keyfin nasıl", "iyi misin"],
        "capability": [
            "ne yapıyorsun", "ne yapıyosun", "napıyorsun", "napıyon",
            "neler yaparsın", "ne yapabilirsin", "özelliğin ne",
        ],
        "knowledge": ["nedir", "ne demek", "anlat", "açıkla", "hakkında bilgi", "öğrenebilir misin"],
        "recipe": ["tarif", "malzemeler", "hazırlanışı", "nasıl yapılır"],
        "follow_up": ["bu", "bunu", "şu", "şunu", "onu", "peki", "devam et"],
    },
    "synonyms": {
        "internet": ["web", "online", "ara", "bak", "araştır"],
        "play": ["çal", "oynat", "dinlet", "başlat"],
        "open": ["aç", "göster", "başlat"],
    },
}


@dataclass
class NetOpsOneLocation:
    city: str = ""
    region: str = ""
    country: str = ""
    timezone: str = ""
    latitude: float | None = None
    longitude: float | None = None
    source: str = ""
    updated_at: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.city or self.region or self.country)

    @property
    def label(self) -> str:
        result: list[str] = []
        for part in (self.city, self.region, self.country):
            value = str(part or "").strip()
            if value and value not in result:
                result.append(value)
        return ", ".join(result) or "yaklaşık konum"

    def as_dict(self) -> dict[str, Any]:
        return {
            "city": self.city, "region": self.region, "country": self.country,
            "timezone": self.timezone, "latitude": self.latitude,
            "longitude": self.longitude, "source": self.source,
            "updatedAt": self.updated_at,
        }

    @classmethod
    def from_mapping(cls, value: Any) -> "NetOpsOneLocation":
        if not isinstance(value, dict):
            return cls()
        def number(key: str) -> float | None:
            try:
                return float(value[key]) if value.get(key) is not None else None
            except (TypeError, ValueError, KeyError):
                return None
        return cls(
            city=str(value.get("city") or value.get("name") or "").strip(),
            region=str(value.get("region") or value.get("admin1") or "").strip(),
            country=str(value.get("country") or value.get("country_name") or "").strip(),
            timezone=str(value.get("timezone") or "").strip(),
            latitude=number("latitude"), longitude=number("longitude"),
            source=str(value.get("source") or "").strip(),
            updated_at=str(value.get("updatedAt") or value.get("updated_at") or "").strip(),
        )


class NetOpsOneLocationService:
    """IP tabanlı yaklaşık konumu açılışta arka planda hazırlar."""

    _shared: dict[str, "NetOpsOneLocationService"] = {}
    _shared_lock = _netops_threading.RLock()

    def __init__(self, project_dir: str | Path) -> None:
        self.project_dir = Path(project_dir).resolve()
        self.cache_path = self.project_dir / "netops_location.json"
        self._lock = _netops_threading.RLock()
        self._location = self._load_cache()
        self._started = False
        self._refreshing = False
        self._last_attempt = 0.0

    @classmethod
    def shared(cls, project_dir: str | Path | None = None) -> "NetOpsOneLocationService":
        base = Path(project_dir or Path(__file__).resolve().parent).resolve()
        key = str(base).casefold()
        with cls._shared_lock:
            if key not in cls._shared:
                cls._shared[key] = cls(base)
            return cls._shared[key]

    @property
    def enabled(self) -> bool:
        return os.environ.get("NETOPS_LOCATION_ENABLED", "1").strip().lower() not in {
            "0", "false", "off", "no"
        }

    def start_background(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
        _netops_threading.Thread(
            target=self._startup_refresh, name="netops-location", daemon=True
        ).start()

    def _startup_refresh(self) -> None:
        if not self.enabled:
            return
        current = self.get()
        if not current.ok or not self._cache_is_fresh(current):
            self.refresh(silent=True)

    def get(self, force: bool = False) -> NetOpsOneLocation:
        with self._lock:
            current = self._location
        if current.ok and not force:
            return current
        if not self.enabled:
            return current
        return self.refresh(silent=True)

    def refresh(self, silent: bool = True) -> NetOpsOneLocation:
        if not self.enabled:
            return self.get()
        with self._lock:
            now = time.time()
            if self._refreshing or (now - self._last_attempt < 20 and self._location.ok):
                return self._location
            self._refreshing = True
            self._last_attempt = now
        try:
            location = self._from_weather_module()
            if not location.ok:
                location = self._detect_direct()
            if location.ok:
                with self._lock:
                    self._location = location
                self._save_cache(location)
            return location
        except Exception:
            return self.get()
        finally:
            with self._lock:
                self._refreshing = False

    def _from_weather_module(self) -> NetOpsOneLocation:
        try:
            import neto_weather
            return NetOpsOneLocation.from_mapping(
                neto_weather.auto_detect_location(save=True, silent_fail=True)
            )
        except Exception:
            return NetOpsOneLocation()

    def _detect_direct(self) -> NetOpsOneLocation:
        endpoints = [
            ("https://ipapi.co/json/", "ipapi"),
            ("https://ipwho.is/", "ipwho"),
        ]
        token = os.environ.get("NETOPS_IPINFO_TOKEN", "").strip()
        if token:
            endpoints.append((f"https://ipinfo.io/json?token={token}", "ipinfo"))
        for endpoint, provider in endpoints:
            try:
                data = self._get_json(endpoint)
                if provider == "ipwho" and data.get("success") is False:
                    continue
                loc = data.get("loc", "")
                lat, lon = (str(loc).split(",", 1) + [""])[:2]
                result = NetOpsOneLocation.from_mapping({
                    "city": data.get("city") or data.get("region"),
                    "region": data.get("region") or data.get("region_name"),
                    "country": data.get("country_name") or data.get("country"),
                    "timezone": (
                        data.get("timezone", {}).get("id")
                        if isinstance(data.get("timezone"), dict)
                        else data.get("timezone")
                    ),
                    "latitude": data.get("latitude") or lat,
                    "longitude": data.get("longitude") or lon,
                    "source": provider,
                    "updatedAt": self._now(),
                })
                if result.ok:
                    return result
            except Exception:
                continue
        return NetOpsOneLocation()

    @staticmethod
    def _get_json(url: str) -> dict[str, Any]:
        try:
            import requests
            response = requests.get(
                url,
                headers={"Accept-Language": "tr-TR,tr;q=0.95", "User-Agent": "NetOpsOne/3.0"},
                timeout=5,
            )
            response.raise_for_status()
            value = response.json()
            return value if isinstance(value, dict) else {}
        except Exception:
            from urllib.request import Request, urlopen
            request = Request(url, headers={"Accept-Language": "tr-TR,tr;q=0.95", "User-Agent": "NetOpsOne/3.0"})
            with urlopen(request, timeout=5) as response:
                value = json.loads(response.read().decode("utf-8"))
                return value if isinstance(value, dict) else {}

    def _load_cache(self) -> NetOpsOneLocation:
        try:
            return NetOpsOneLocation.from_mapping(
                json.loads(self.cache_path.read_text(encoding="utf-8-sig"))
            )
        except Exception:
            return NetOpsOneLocation()

    def _save_cache(self, location: NetOpsOneLocation) -> None:
        try:
            self.cache_path.write_text(
                json.dumps(location.as_dict(), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except Exception:
            pass

    @staticmethod
    def _now() -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _cache_is_fresh(location: NetOpsOneLocation) -> bool:
        try:
            stamp = _netops_dt.datetime.strptime(location.updated_at, "%Y-%m-%d %H:%M:%S")
            return (_netops_dt.datetime.now() - stamp).total_seconds() < 1800
        except Exception:
            return False

    @staticmethod
    def query_kind(message: Any) -> str:
        value = str(message or "").casefold()
        try:
            import neto_weather
            if neto_weather.is_weather_query(value):
                return "weather"
            if neto_weather.is_location_query(value):
                return "location"
        except Exception:
            pass
        if any(word in value for word in (
            "hava", "derece", "yağmur", "yagmur", "şemsiye", "semsiye",
            "rüzgar", "ruzgar", "nem", "dışarısı", "disarisi",
        )):
            return "weather"
        if any(word in value for word in (
            "burada saat", "burda saat", "yerel saat", "saat kaç", "saat kac",
        )):
            return "time"
        if any(word in value for word in (
            "neredeyim", "nerdeyim", "hangi şehirdeyim", "hangi sehirdeyim",
            "konumumu bul", "konumu bul", "konumumu güncelle", "konumumu guncelle",
        )):
            return "location"
        if any(word in value for word in (
            "yakındaki", "yakindaki", "yakınında", "yakininda",
            "en yakın", "en yakin", "buradaki", "civarındaki", "civarinda",
        )):
            return "nearby"
        return ""

    def needs_fresh(self, message: Any) -> bool:
        return self.query_kind(message) in {"weather", "time", "nearby", "location"}

    def enrich_query(self, query: str, message: Any = "") -> str:
        if self.query_kind(message or query) not in {"weather", "nearby", "time", "location"}:
            return query
        location = self.get()
        if not location.ok or location.label.casefold() in query.casefold():
            return query
        return f"{query} {location.label}".strip()

    def context(self, message: Any = "") -> str:
        location = self.get(force=self.needs_fresh(message))
        if not location.ok:
            return "Kullanıcının konumu alınamadı; kesin konum iddiasında bulunma."
        text = f"Kullanıcının yaklaşık konumu: {location.label}."
        if location.timezone:
            text += f" Saat dilimi: {location.timezone}."
        return text + " Bu konum IP üzerinden yaklaşık belirlenmiştir."

    def dynamic_context(self, message: Any) -> str:
        kind = self.query_kind(message)
        if kind == "weather":
            try:
                import neto_weather
                value = TextFormatter.clean_answer(neto_weather.weather_answer(str(message)))
                if value and "alınamadı" not in value.casefold() and "ulaşılamadı" not in value.casefold():
                    return value
            except Exception:
                pass
        if kind == "time":
            location = self.get(force=True)
            try:
                from zoneinfo import ZoneInfo
                now = _netops_dt.datetime.now(ZoneInfo(location.timezone)) if location.timezone else _netops_dt.datetime.now().astimezone()
            except Exception:
                now = _netops_dt.datetime.now().astimezone()
            return f"{location.label} için yerel saat {now:%H:%M}, tarih {now:%d.%m.%Y}."
        if kind == "location":
            location = self.get()
            if location.ok:
                return f"Yaklaşık konumun {location.label}."
        return ""


class NetOpsOneQueryNormalizer:
    FILLER_PATTERNS = [
        r"\bbana\b", r"\bbenim\s+için\b", r"\bbenim\s+icin\b",
        r"\blütfen\b", r"\blutfen\b", r"\bnedir\b", r"\bne\s+demek\b",
        r"\bhakkında\s+bilgi\b", r"\bhakkinda\s+bilgi\b", r"\bhakkında\b", r"\bhakkinda\b",
        r"\btarifini\s+ver\b", r"\btarifi\s+ver\b", r"\böğrenebilir\s+misin\b",
        r"\bogrenebilir\s+misin\b", r"\bverir\s+misin\b", r"\bverirmisin\b",
        r"\banlatır\s+mısın\b", r"\banlatir\s+misin\b", r"\bsöyler\s+misin\b",
        r"\bsoyler\s+misin\b", r"\b(webde|webden|internette|internet|google'?da|duckduckgo'?da)\s+(ara|bak|arat|araştır|arastir)\b",
        r"\b(ara|arat|bak|anlat|açıkla|acikla|söyle|soyle|ver)\b",
    ]

    @classmethod
    def clean(cls, value: Any) -> str:
        query = str(value or "").casefold()
        query = re.sub(r"[\n\r\t]+", " ", query)
        query = re.sub(r"\bfiyatlarını\b|\bfiyatlarini\b", "fiyatları", query, flags=re.I)
        query = re.sub(r"\btarifini\b", "tarifi", query, flags=re.I)
        for pattern in cls.FILLER_PATTERNS:
            query = re.sub(pattern, " ", query, flags=re.I)
        query = re.sub(r"[^\wçğıöşüÇĞİÖŞÜ0-9\s+.-]", " ", query, flags=re.UNICODE)
        return re.sub(r"\s+", " ", query).strip(" .-")


class NetOpsOneStructuredSearch:
    BLOCKED_HOST_PARTS = (
        "youtube.com", "youtu.be", "tiktok.com", "instagram.com", "facebook.com",
        "x.com", "twitter.com", "reddit.com", "pinterest.", "wiktionary.org",
        "eksisozluk.com", "sozluk.gov.tr", "genius.com", "azlyrics.com",
        "lyrics.com", "musixmatch.com", "songlyrics.com", "nhl.com", "nba.com",
        "nfl.com", "espn.com",
    )
    STOPWORDS = {
        "bana", "benim", "icin", "için", "ver", "lütfen", "lutfen", "nedir",
        "hakkında", "hakkinda", "bilgi", "misin", "mısın", "mi", "mı", "mu", "mü",
        "bir", "bu", "şu", "su", "ne", "nasıl", "nasil", "ara", "bak", "anlat",
        "açıkla", "acikla", "tarifi", "tarifini", "öğrenebilir", "ogrenebilir",
    }

    def search(self, query: str, limit: int = 3) -> list[SearchItem]:
        if not str(query or "").strip():
            return []
        rows = self._duckduckgo(query, limit)
        if not rows:
            rows = self._searxng(query, limit)
        return self._filter(rows, query)[:limit]

    def search_youtube_video(self, query: str, limit: int = 6) -> str:
        """Return a trusted YouTube watch URL without exposing it to the UI."""
        query = str(query or "").strip()
        if not query:
            return ""
        rows = self._duckduckgo(f"{query} site:youtube.com/watch", max(3, limit))
        if not rows:
            rows = self._searxng(f"{query} site:youtube.com/watch", max(3, limit))
        for item in rows:
            parsed = _netops_urlparse(item.url)
            host = parsed.netloc.lower().removeprefix("www.")
            if host == "youtu.be":
                video_id = parsed.path.strip("/").split("/")[0]
                if video_id:
                    return f"https://www.youtube.com/watch?v={video_id}"
            if host.endswith("youtube.com") and parsed.path == "/watch":
                video_id = parse_qs(parsed.query).get("v", [""])[0].strip()
                if video_id:
                    return f"https://www.youtube.com/watch?v={video_id}"
        return ""

    def _duckduckgo(self, query: str, limit: int) -> list[SearchItem]:
        try:
            from duckduckgo_search import DDGS
            rows: list[SearchItem] = []
            with DDGS() as ddgs:
                for raw in ddgs.text(
                    keywords=query, region="tr-tr", safesearch="on", max_results=max(3, limit * 3)
                ):
                    if isinstance(raw, dict):
                        rows.append(SearchItem(
                            title=str(raw.get("title") or "").strip(),
                            body=str(raw.get("body") or raw.get("snippet") or "").strip(),
                            url=str(raw.get("href") or raw.get("url") or "").strip(),
                        ))
            return rows
        except Exception:
            return []

    def _searxng(self, query: str, limit: int) -> list[SearchItem]:
        endpoint = os.environ.get("NETOPS_SEARXNG_URL", "").strip()
        if not endpoint:
            return []
        try:
            import requests
            response = requests.get(
                endpoint,
                params={"q": query, "format": "json", "language": "tr", "safesearch": 1},
                headers={"Accept-Language": "tr-TR,tr;q=0.95", "User-Agent": "NetOpsOne/3.0"},
                timeout=8,
            )
            response.raise_for_status()
            data = response.json()
            rows: list[SearchItem] = []
            for raw in data.get("results") or []:
                if isinstance(raw, dict):
                    rows.append(SearchItem(
                        title=str(raw.get("title") or "").strip(),
                        body=str(raw.get("content") or raw.get("body") or "").strip(),
                        url=str(raw.get("url") or "").strip(),
                    ))
            return rows[:limit * 3]
        except Exception:
            return []

    def _filter(self, items: list[SearchItem], query: str = "") -> list[SearchItem]:
        result: list[SearchItem] = []
        seen: set[str] = set()
        for item in items:
            if not item.title and not item.body:
                continue
            if self.is_blocked(item.url, item.title, item.body):
                continue
            title = NetOpsOneText.clean_inline(item.title)
            body = NetOpsOneText.clean_inline(item.body)
            if len(title + body) < 30:
                continue
            if not self.is_turkish_candidate(title, body):
                continue
            if query and self.relevance_score(query, title, body) < 0.25:
                continue
            key = re.sub(r"\W+", "", f"{title} {body}".casefold())[:140]
            if key and key not in seen:
                seen.add(key)
                result.append(SearchItem(title=title, body=body))
        return result

    @classmethod
    def relevance_score(cls, query: str, title: str, body: str) -> float:
        tokens = [
            token for token in re.findall(r"[\wçğıöşü]+", str(query or "").casefold())
            if len(token) >= 3 and token not in cls.STOPWORDS
        ]
        if not tokens:
            return 0.5
        haystack = f"{title} {body}".casefold()
        hits = sum(1 for token in set(tokens) if token in haystack)
        return hits / max(1, len(set(tokens)))

    @staticmethod
    def is_turkish_candidate(title: str, body: str) -> bool:
        text = f"{title} {body}".casefold()
        if re.search(r"[\u0400-\u04ff\u0600-\u06ff\u0900-\u097f]", text):
            return False
        words = set(re.findall(r"[a-zçğıöşü]+", text))
        english_markers = {"the", "and", "is", "are", "this", "with", "from", "for"}
        return len(words & english_markers) < 3

    @classmethod
    def is_blocked(cls, url: str = "", title: str = "", body: str = "") -> bool:
        host = _netops_urlparse(str(url or "")).netloc.lower().replace("www.", "")
        full = f"{host} {url} {title} {body}".casefold()
        words = ("lyrics", "şarkı sözü", "sarki sozu", "songtext", "wiktionary", "sözlük", "sozluk")
        return (
            any(part in host for part in cls.BLOCKED_HOST_PARTS)
            or any(word in full for word in words)
            or NetOpsOneText.contains_abusive_text(full)
        )


class NetOpsOneText:
    _PROFANITY_CACHE: dict[str, Any] | None = None
    MEMORY_STOPWORDS = {
        "bana", "benim", "icin", "için", "ver", "lütfen", "lutfen", "nedir",
        "hakkında", "hakkinda", "bilgi", "misin", "mısın", "mi", "mı", "mu", "mü",
        "bir", "bu", "şu", "su", "ne", "nasıl", "nasil", "ara", "bak", "anlat",
        "açıkla", "acikla", "tarifi", "tarifini", "öğrenebilir", "ogrenebilir",
    }

    @staticmethod
    def clean_inline(value: Any) -> str:
        text = _html.unescape(str(value or ""))
        text = re.sub(r"https?://\S+", " ", text, flags=re.I)
        text = re.sub(
            r"\b(?:[a-z0-9-]+\.)+(?:com|net|org|tr|io|dev|edu|gov|co)(?:/\S*)?",
            " ", text, flags=re.I
        )
        text = re.sub(r"(?i)\b(kaynak|source|url|link|snippet|cached)\s*:.*$", " ", text)
        text = re.sub(r"(?i)\b(click here|read more|devamını oku|reklam|sponsored)\b", " ", text)
        return re.sub(r"\s+", " ", text).strip(" -:•\n\t")

    @classmethod
    def clean_answer(cls, value: Any) -> str:
        text = _html.unescape(str(value or "")).replace("\r", "")
        text = re.sub(r"https?://\S+", "", text, flags=re.I)
        text = re.sub(
            r"\b(?:[a-z0-9-]+\.)+(?:com|net|org|tr|io|dev|edu|gov|co)(?:/\S*)?",
            "", text, flags=re.I
        )
        text = re.sub(r"(?im)^\s*(?:kaynak|source|url|link|snippet|cached)\s*:.*$", "", text)
        text = re.sub(r"(?i)\b(?:web'de|webde)\s+(?:şunları|sunu|bulduklarım)\b[^:\n]*:?", "", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return "\n".join(line.strip() for line in text.splitlines() if line.strip()).strip(" -:\n\t")

    @classmethod
    def clean_model(cls, value: Any) -> str:
        text = cls.clean_answer(value)
        text = re.sub(r"(?im)^\s*(?:netops one|asistan|assistant)\s*:\s*", "", text)
        text = re.sub(r"(?im)^\s*(?:işte|iste)\s*(?:cevap|yanıt|yanit)\s*:\s*", "", text)
        return text[:5000].strip()

    @classmethod
    def core_tokens(cls, value: Any) -> list[str]:
        return [
            token for token in re.findall(r"[\wçğıöşü]+", str(value or "").casefold())
            if len(token) >= 3 and token not in cls.MEMORY_STOPWORDS
        ]

    @classmethod
    def _profanity_cache(cls) -> dict[str, Any]:
        if cls._PROFANITY_CACHE is not None:
            return cls._PROFANITY_CACHE
        tokens: set[str] = set()
        phrases: set[str] = set()
        obfuscated: list[str] = []
        for raw_bad in _NETOPS_CONFIG_PROFANITY:
            bad = str(raw_bad or "").casefold().strip()
            if not bad:
                continue
            bad_tokens = re.findall(r"[a-z0-9çğıöşü]+", bad)
            if not bad_tokens:
                continue
            if len(bad_tokens) > 1:
                phrases.add(" ".join(bad_tokens))
                continue
            token = bad_tokens[0]
            tokens.add(token)
            if len(token) >= 4:
                obfuscated.append(token)
        cls._PROFANITY_CACHE = {"tokens": tokens, "phrases": phrases, "obfuscated": obfuscated}
        return cls._PROFANITY_CACHE

    @classmethod
    def contains_abusive_text(cls, value: Any) -> bool:
        text = str(value or "").casefold()
        text_tokens = re.findall(r"[a-z0-9çğıöşü]+", text)
        if not text_tokens:
            return False
        spaced_text = " " + " ".join(text_tokens) + " "
        safe_short = {"selam", "merhaba", "hey", "naber", "sa", "slm"}
        if " ".join(text_tokens) in safe_short:
            return False
        cache = cls._profanity_cache()
        if set(text_tokens) & cache["tokens"]:
            return True
        if any(f" {phrase} " in spaced_text for phrase in cache["phrases"]):
            return True
        compact = re.sub(r"[^a-z0-9çğıöşü]+", "", text)
        if any(token in compact for token in cache["obfuscated"]):
            return True
        return False

    @classmethod
    def is_trusted_memory_item(cls, query: str, answer: Any, item: dict[str, Any] | None = None) -> bool:
        clean = cls.clean_model(answer)
        if not clean or not cls.safe(clean):
            return False
        if cls.contains_abusive_text(query) or cls.contains_abusive_text(clean):
            return False
        lowered = clean.casefold()
        if re.search(r"[\u0400-\u04ff\u0600-\u06ff\u0900-\u097f]", clean):
            return False
        if any(marker in lowered for marker in (
            "web'de", "webde şunları", "1. link", "2. link", "kaynak:",
            "lyrics", "songtext", "wiktionary", "microsoft corporation is an",
            "karachi halwa", "› wiki", "› channel", "› watch", "copyright",
            "youtube music", "playlist", "iplocation", "ben neredeyim",
        )):
            return False
        is_recipe = "malzemeler" in lowered and (
            "hazırlan" in lowered or "yapılış" in lowered or "yapilis" in lowered
        )
        list_lines = re.findall(r"(?im)^\s*(?:[-•]|\d+[.)])\s+", clean)
        if not is_recipe and (len(list_lines) >= 2 or clean.count("•") >= 2):
            return False
        source = str((item or {}).get("source") or "").casefold()
        if source in {"explicit_user_correction", "local", "quick_chat"}:
            return True
        tokens = cls.core_tokens(query)
        if tokens and not any(token in lowered for token in tokens):
            return False
        return True

    @classmethod
    def compose_search_answer(
        cls, query: str, items: list[SearchItem], dynamic_context: str = ""
    ) -> str:
        direct = cls.clean_model(dynamic_context)
        if direct and cls.safe(direct):
            return direct[:1600]

        sentences: list[str] = []
        seen: set[str] = set()
        for item in items[:3]:
            text = cls.clean_answer(item.body or item.title)
            if not text:
                continue
            candidates = re.split(r"(?<=[.!?])\s+|\n+|\s+[•-]\s+", text)
            for candidate in candidates:
                candidate = re.sub(r"\s+", " ", candidate).strip(" -:•")
                if len(candidate) < 28:
                    continue
                key = re.sub(r"\W+", "", candidate.casefold())[:150]
                if key and key not in seen:
                    seen.add(key)
                    sentences.append(candidate)
                if len(sentences) >= 4:
                    break
            if len(sentences) >= 4:
                break

        if not sentences:
            return ""
        if len(sentences) == 1:
            return sentences[0][:1100]
        return "\n".join(f"• {sentence}" for sentence in sentences[:4])[:1800]

    @classmethod
    def compose_recipe_answer(cls, query: str, items: list[SearchItem]) -> str:
        """Turn structured snippets into a recipe card, never a source dump."""
        source = " ".join(
            cls.clean_answer(f"{item.title}. {item.body}")
            for item in items[:5]
        )
        source = re.sub(r"\s+", " ", source).strip()
        if not source:
            return ""

        ingredient_match = re.search(
            r"\b(?:gerekli\s+)?malzemeler\b\s*[:\-]?\s*(.*?)(?="
            r"\b(?:hazırlanışı|hazirlanisi|yapılışı|yapilisi|hazırlama|hazirlama|"
            r"yapım\s+aşamaları|yapim\s+asamalari)\b|$)",
            source,
            flags=re.IGNORECASE,
        )
        preparation_match = re.search(
            r"\b(?:hazırlanışı|hazirlanisi|yapılışı|yapilisi|hazırlama|hazirlama|"
            r"yapım\s+aşamaları|yapim\s+asamalari)\b\s*[:\-]?\s*(.*)$",
            source,
            flags=re.IGNORECASE,
        )

        def parts(value: str) -> list[str]:
            pieces = re.split(
                r"\s*(?:[•;]|\b\d+[.)])\s*|(?<=[.!?])\s+",
                value or "",
            )
            cleaned: list[str] = []
            for piece in pieces:
                item = cls.clean_inline(piece).strip(" .:-")
                if len(item) < 3:
                    continue
                if item.casefold() not in {x.casefold() for x in cleaned}:
                    cleaned.append(item)
            return cleaned[:10]

        ingredients = parts(ingredient_match.group(1)) if ingredient_match else []
        preparation = parts(preparation_match.group(1)) if preparation_match else []
        title = re.sub(
            r"\b(?:tarif|tarifi|malzemeler|hazırlanışı|hazirlanisi)\b",
            " ",
            str(query or ""),
            flags=re.IGNORECASE,
        )
        title = re.sub(r"\s+", " ", title).strip().capitalize()
        title = title or "Tarif"

        sections: list[str] = [title]
        if ingredients:
            sections.append("Malzemeler\n" + "\n".join(f"• {item}" for item in ingredients))
        if preparation:
            sections.append("Hazırlanışı\n" + "\n".join(
                f"{index}. {item}" for index, item in enumerate(preparation, 1)
            ))
        if len(sections) == 1:
            summary = cls.compose_search_answer(query, items)
            if not summary:
                return ""
            return f"{title}\n\nTarif özeti\n{summary.replace('• ', '• ')}"[:2600]
        return "\n\n".join(sections)[:2600]

    @classmethod
    def evidence(cls, items: list[SearchItem]) -> str:
        parts: list[str] = []
        for item in items[:3]:
            title = cls.clean_inline(item.title)
            body = cls.clean_inline(item.body)
            text = f"{title}: {body}" if title and body else body or title
            if text:
                parts.append(text)
        unique: list[str] = []
        seen: set[str] = set()
        for part in parts:
            key = re.sub(r"\W+", "", part.casefold())[:140]
            if key and key not in seen:
                seen.add(key)
                unique.append(part)
        return "\n".join(f"- {part}" for part in unique)[:5000]

    @classmethod
    def fallback_text(cls, query: str, items: list[SearchItem]) -> tuple[str, str]:
        evidence = cls.evidence(items)
        if not evidence:
            return "NetOps One", NETOPS_ONE_FALLBACK
        title = re.sub(r"\s+", " ", str(query or "")).strip()
        return (title[:1].upper() + title[1:80] if title else "NetOps One"), evidence[:2600]

    @staticmethod
    def safe(value: str) -> bool:
        lowered = str(value or "").casefold()
        return all(token not in lowered for token in ("http://", "https://", "kaynak:", "web'de"))


class NetOpsOneSynthesizer:
    """Eski API uyumluluğu; v3 motorunda model sağlayıcısı kullanılmaz."""
    SYSTEM_PROMPT = NETOPS_ONE_CORE_SYSTEM_PROMPT

    def __init__(self) -> None:
        self.provider = os.environ.get("NETOPS_LLM_PROVIDER", "auto").strip().lower()
        self.ollama_url = os.environ.get(
            "NETOPS_OLLAMA_URL", "http://127.0.0.1:11434/api/generate"
        ).strip()
        self.ollama_model = os.environ.get("NETOPS_OLLAMA_MODEL", "gemma3:4b").strip()
        self.api_url = os.environ.get("NETOPS_LLM_API_URL", "").strip()
        self.api_key = os.environ.get("NETOPS_LLM_API_KEY", "").strip()
        self.api_model = os.environ.get("NETOPS_LLM_API_MODEL", "netops-one").strip()
        try:
            self.timeout = max(5, min(90, int(os.environ.get("NETOPS_LLM_TIMEOUT", "35") or 35)))
        except ValueError:
            self.timeout = 35
        self._ollama_state: tuple[bool, float] = (False, 0.0)

    def generate(self, question: str, evidence: str, location: str = "") -> tuple[str | None, str]:
        return None, "disabled"

        if not evidence.strip():
            return None, "none"
        prompt = (
            f"Konum bağlamı:\n{location or 'Konum bağlamı yok.'}\n\n"
            f"Arama ve sistem verisi:\n{evidence[:5000]}\n\n"
            f"Kullanıcının sorusu:\n{question}\n\n"
            "Cevap Türkçe, doğrudan ve kısa olsun. Gerekirse madde işaretleri kullan. "
            "Ham veri, URL, alan adı veya kaynak listesi yazma."
        )
        for provider in self._providers():
            try:
                result = NetOpsOneText.clean_model(self._call(provider, prompt))
                if result and "http" not in result.casefold():
                    return result, provider
            except Exception:
                continue
        return None, "none"

    def _providers(self) -> list[str]:
        return []

        if self.provider in {"off", "none", "disabled"}:
            return []
        if self.provider in {"ollama", "api"}:
            return [self.provider]
        providers: list[str] = []
        if self._ollama_available():
            providers.append("ollama")
        if self.api_url:
            providers.append("api")
        return providers

    def _ollama_available(self) -> bool:
        now = time.time()
        available, checked = self._ollama_state
        if now - checked < 30:
            return available
        try:
            import requests
            base = self.ollama_url.rsplit("/api/", 1)[0].rstrip("/")
            response = requests.get(f"{base}/api/tags", timeout=1.5)
            available = response.status_code < 400
        except Exception:
            available = False
        self._ollama_state = (available, now)
        return available

    def _call(self, provider: str, prompt: str) -> str:
        import requests
        if provider == "ollama":
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.ollama_model,
                    "system": self.SYSTEM_PROMPT,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.15, "top_p": 0.8,
                        "num_predict": 420, "repeat_penalty": 1.12,
                    },
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            return str(response.json().get("response") or "")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        response = requests.post(
            self.api_url,
            headers=headers,
            json={
                "model": self.api_model,
                "messages": [
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.15,
                "max_tokens": 420,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices") or []
        if choices and isinstance(choices[0], dict):
            message = choices[0].get("message") or {}
            return str(message.get("content") or choices[0].get("text") or "")
        return str(data.get("response") or data.get("output") or data.get("text") or "")


class NetOpsOneEngineV3:
    def __init__(
        self,
        project_dir: str | Path | None = None,
        command_detector: CommandDetector | None = None,
        internet_enabled: Callable[[], bool] | bool = True,
        max_sources: int = 3,
        internal_opener: Callable[[str, bool], Any] | None = None,
    ) -> None:
        self.project_dir = Path(project_dir).resolve() if project_dir else Path(__file__).resolve().parent
        self.memory_path = self.project_dir / MEMORY_FILE
        self.word_core_path = self.project_dir / WORD_CORE_FILE
        self.command_detector = command_detector
        self.internet_enabled = internet_enabled
        self.max_sources = max(1, min(3, int(max_sources or 3)))
        self.internal_opener = internal_opener
        self.search_client = NetOpsOneStructuredSearch()
        self.location = NetOpsOneLocationService.shared(self.project_dir)
        self.location.start_background()
        # Yanıt üretimi bu sürümde tamamen deterministiktir; Ollama/API çağrısı yok.
        self._turns: deque[dict[str, str]] = deque(maxlen=6)
        self._last_media: dict[str, str] = {}
        self.adaptive_model = AdaptiveIntentModel() if AdaptiveIntentModel is not None else None
        self.ensure_memory()
        self.ensure_word_core()

    def answer(self, message: Any, *, agent_mode: bool = False) -> NetOpsOneResult:
        raw = str(message or "").strip()
        normalized = self.normalize(raw)
        if not normalized:
            return NetOpsOneResult(False, "Bir şey yazmadın.", "empty", source="local", title="NetOps One")

        if NetOpsOneText.contains_abusive_text(raw):
            result = NetOpsOneResult(
                True, NETOPS_ONE_POLITE_WARNING, "safety_filter",
                source="local", query=normalized, title="Güvenlik",
            )
            self._record_turn(raw, normalized, result.text, result.intent)
            return result

        command = None if agent_mode else self.detect_command(normalized)
        if command:
            result = NetOpsOneResult(True, command, "command", source="netops_command", command=command, title="Komut")
            self._record_turn(raw, normalized, result.text, result.intent)
            return result

        correction = self._explicit_correction(raw)
        if correction:
            correction_query, correction_answer = correction
            stored = self.memory_store(
                raw, correction_answer, source="explicit_user_correction",
                query=correction_query, title="Kullanıcı düzeltmesi",
            )
            result = NetOpsOneResult(
                True,
                "Düzeltme hafızaya yazıldı." if stored else "Bu düzeltme güvenli bulunmadığı için hafızaya yazılmadı.",
                "correction",
                source="local", query=correction_query, title="Hafıza",
                learned=bool(stored),
            )
            self._record_turn(raw, correction_query, result.text, result.intent)
            return result

        quick = self.quick_reply(raw, agent_mode=agent_mode)
        if quick:
            result = NetOpsOneResult(True, quick, "quick_chat", source="local", title="NetOps One")
            self._record_turn(raw, normalized, result.text, result.intent)
            return result

        # Public-APIs tool/catalog commands are deterministic local tools, not web-search prose.
        # This makes commands such as "ücretsiz api listele", "public api test et" and
        # "public api çağır Jikan" reach the registry/auditor directly.
        try:
            import neto_public_apis
            public_api_answer = neto_public_apis.format_query_answer(raw)
        except Exception:
            public_api_answer = None
        if public_api_answer:
            result = NetOpsOneResult(
                True, str(public_api_answer), "public_api_tool",
                source="public-apis", query=normalized, title="Public APIs",
            )
            self._record_turn(raw, normalized, result.text, result.intent)
            return result

        draft = self._automation_draft(raw)
        if draft is not None:
            result = NetOpsOneResult(
                True,
                draft["text"],
                "automation_draft",
                source="automation_draft",
                query=normalized,
                title="Otomasyon taslağı",
                action="automation_draft",
                action_status="awaiting_confirmation",
                action_label="Onay bekliyor",
                metadata=draft["draft"],
            )
            self._record_turn(raw, normalized, result.text, result.intent)
            return result

        query = self.normalize_query(raw)
        contextual_query = self._contextual_query(raw, query)
        media_kind, media_query = self._media_intent(raw, contextual_query)
        if media_kind == "recipe":
            result = self._answer_recipe(raw, media_query, agent_mode=agent_mode)
            self._record_turn(raw, media_query, result.text, result.intent)
            return result
        if media_kind == "music_missing":
            result = NetOpsOneResult(
                True,
                "Hangi şarkıyı veya sanatçıyı çalmamı istersin?",
                "media_clarification",
                source="local",
                query="",
                title="Müzik",
            )
            self._record_turn(raw, contextual_query, result.text, result.intent)
            return result
        if media_kind == "music_play":
            result = self._answer_music(raw, media_query)
            self._record_turn(raw, media_query, result.text, result.intent)
            return result

        kind = self.location.query_kind(raw)
        location = self.location.get(force=self.location.needs_fresh(raw))
        dynamic = self.location.dynamic_context(raw)

        if kind == "location" and dynamic:
            result = self._location_result(raw, contextual_query, dynamic, location)
            self._record_turn(raw, contextual_query, result.text, result.intent)
            return result

        if not self.location.needs_fresh(raw):
            hit = self.memory_lookup(contextual_query) or self.memory_lookup(query) or self.memory_lookup(raw)
            if hit:
                result = NetOpsOneResult(
                    True, hit, "memory", source=MEMORY_FILE, cached=True, query=query,
                    title="Hafızadan", location=location.as_dict() if location.ok else None,
                )
                self._record_turn(raw, contextual_query, result.text, result.intent)
                return result
        result = self.search_web(raw, location, dynamic, query_override=contextual_query)
        self._record_turn(raw, result.query or contextual_query, result.text, result.intent)
        return result

    def _media_intent(self, raw: str, contextual_query: str) -> tuple[str, str]:
        normalized = self.normalize(raw)
        last = self._last_media
        follow_up = re.search(
            r"\b(?:bunu|onu|şunu|sunu)\b\s*(?:aç|ac|çal|cal|oynat|dinlet)\b",
            normalized,
            flags=re.IGNORECASE,
        )
        if follow_up and last:
            return last.get("kind", ""), last.get("query", "")

        if any(marker in normalized for marker in RECIPE_HINTS):
            return "recipe", contextual_query or self.normalize_query(raw)

        if not MUSIC_PLAY_RE.search(normalized):
            return "", ""
        music_query = re.sub(
            r"\b(?:youtube\s*music|youtube|spotify|müzik|muzik)\b",
            " ",
            raw,
            flags=re.IGNORECASE,
        )
        music_query = re.sub(
            r"\b(?:çal|cal|dinlet|oynat|başlat|baslat|aç|ac)\b",
            " ",
            music_query,
            flags=re.IGNORECASE,
        )
        music_query = re.sub(
            r"\b([\wçğıöşü]+)['’](?:ı|i|u|ü)\b",
            r"\1",
            music_query,
            flags=re.IGNORECASE,
        )
        music_query = re.sub(r"[^\wçğıöşüÇĞİÖŞÜ\s-]", " ", music_query)
        music_query = re.sub(r"\s+", " ", music_query).strip()
        return ("music_play", music_query) if music_query else ("music_missing", "")

    def _automation_draft(self, raw: str) -> dict[str, Any] | None:
        try:
            from neto_automation_draft import format_draft, parse_draft

            draft = parse_draft(raw)
            if draft is None:
                return None
            return {"text": format_draft(draft), "draft": draft.as_dict()}
        except Exception:
            return None

    def _answer_recipe(self, raw: str, query: str, *, agent_mode: bool = False) -> NetOpsOneResult:
        query = query or self.normalize_query(raw)
        cached = self.memory_lookup(query)
        items: list[SearchItem] = []
        text = cached or ""
        if not text and self._internet_is_enabled():
            items = self.search_client.search(query, limit=self.max_sources)
            text = NetOpsOneText.compose_recipe_answer(query, items)
            if not text:
                enriched = f"{query} malzemeler hazırlanışı".strip()
                items = self.search_client.search(enriched, limit=max(3, self.max_sources))
                text = NetOpsOneText.compose_recipe_answer(query, items)

        video_url = ""
        if self._internet_is_enabled():
            video_url = self.search_client.search_youtube_video(f"{query} tarif")
        action_status = "not_found"
        if video_url:
            action_status = self.open_internal(video_url, autoplay=False)

        recipe_text = text
        if not text:
            text = NETOPS_ONE_FALLBACK
            if video_url:
                text += "\n\nİlgili tarif videosu açılıyor."
        elif video_url:
            text += "\n\nİlgili tarif videosu açılıyor."
        title = re.sub(
            r"\b(?:tarif|tarifi|malzemeler|hazırlanışı|hazirlanisi)\b",
            " ",
            str(query or ""),
            flags=re.IGNORECASE,
        )
        title = re.sub(r"\s+", " ", title).strip().capitalize()
        title = f"Tarif: {title or 'NetOps One'}"
        result = NetOpsOneResult(
            bool(text and text != NETOPS_ONE_FALLBACK) or bool(video_url),
            text,
            "recipe",
            source="recipe_search" if items else ("memory_recipe" if cached else "local_fallback"),
            cached=bool(cached),
            query=query,
            title=title,
            action="open_youtube_video" if video_url else "",
            action_status=action_status,
            action_label="Tarif videosu",
        )
        if items and text != NETOPS_ONE_FALLBACK:
            result.learned = self.memory_store(raw, recipe_text, source="recipe_search", query=query, title=title)
        self._last_media = {"kind": "recipe", "query": query}
        return result

    def _answer_music(self, raw: str, query: str) -> NetOpsOneResult:
        if not query:
            return NetOpsOneResult(
                True,
                "Hangi şarkıyı veya sanatçıyı çalmamı istersin?",
                "media_clarification",
                source="local",
                title="Müzik",
            )
        try:
            import neto_music_search
            search_result = neto_music_search.search_and_play(
                query,
                open_url=self.open_internal,
            )
        except Exception:
            search_result = {"ok": False, "error": "Müzik araması başlatılamadı"}

        if search_result.get("ok") and search_result.get("opened"):
            title = NetOpsOneText.clean_inline(
                str(search_result.get("title") or query)
            ) or query
            text = f"{title} YouTube Music'te açılıyor."
            status = str(search_result.get("action_status") or "queued")
        else:
            text = "Bu şarkı veya sanatçı için YouTube Music sonucu açılamadı."
            status = "failed"
        self._last_media = {"kind": "music_play", "query": query}
        return NetOpsOneResult(
            bool(search_result.get("ok") and search_result.get("opened")),
            text,
            "music_play",
            source="youtube_music",
            query=query,
            title="YouTube Music",
            action="play_music",
            action_status=status,
            action_label=NetOpsOneText.clean_inline(str(search_result.get("title") or query)),
        )

    def open_internal(self, url: str, autoplay: bool = False) -> str:
        if not str(url or "").strip():
            return "not_found"
        if self.internal_opener is not None:
            try:
                result = self.internal_opener(str(url), bool(autoplay))
                if isinstance(result, dict):
                    return "opened" if result.get("ok", True) else "failed"
                return "opened" if result is not False else "failed"
            except Exception:
                return "failed"

        def open_in_background() -> None:
            try:
                import browser_engine
                browser_engine.open_url(str(url))
            except Exception:
                pass

        _netops_threading.Thread(
            target=open_in_background,
            name="netops-internal-media",
            daemon=True,
        ).start()
        return "queued"

    _dispatch_internal = open_internal

    def _location_result(self, raw: str, query: str, dynamic: str, location: NetOpsOneLocation) -> NetOpsOneResult:
        text = NetOpsOneText.clean_model(dynamic)
        return NetOpsOneResult(
            True, text, "location_context", source="location",
            query=query, title="Konum", location=location.as_dict() if location.ok else None,
        )

    def _contextual_query(self, raw: str, query: str) -> str:
        if not query or not self._turns:
            return query
        normalized = self.normalize(raw)
        markers = (
            "bu", "bunu", "şu", "su", "onu", "onun", "peki", "fiyatı", "fiyati",
            "özellikleri", "ozellikleri", "nasıl", "nasil", "kaç", "kac", "neden",
        )
        if not any(marker in normalized.split() for marker in markers):
            return query
        previous = next(
            (turn.get("query", "") for turn in reversed(self._turns) if turn.get("query")),
            "",
        )
        if not previous or previous.casefold() in query.casefold():
            return query
        return f"{previous} {query}".strip()

    def _explicit_correction(self, raw: str) -> tuple[str, str] | None:
        match = re.match(
            r"^\s*(?:doğrusu|dogrusu|düzelt|duzelt|yanlış cevap|yanlis cevap)\s*[:,-]?\s*(.+)$",
            str(raw or ""), flags=re.IGNORECASE,
        )
        if not match:
            return None
        body = match.group(1).strip()
        if not body:
            return None
        if "=" in body:
            query, answer = body.split("=", 1)
            query = self.normalize_query(query)
            answer = NetOpsOneText.clean_model(answer)
            return (query, answer) if query and answer else None
        if "->" in body:
            query, answer = body.split("->", 1)
            query = self.normalize_query(query)
            answer = NetOpsOneText.clean_model(answer)
            return (query, answer) if query and answer else None
        previous = next(
            (turn.get("query", "") for turn in reversed(self._turns) if turn.get("query")),
            "",
        )
        answer = NetOpsOneText.clean_model(body)
        return (previous, answer) if previous and answer else None

    def _record_turn(self, raw: str, query: str, answer: str, intent: str) -> None:
        self._turns.append({
            "message": str(raw or "").strip()[:500],
            "query": self.normalize(query)[:300],
            "answer": NetOpsOneText.clean_model(answer)[:1200],
            "intent": str(intent or "response"),
        })
        if self.adaptive_model is not None and intent in {
            "quick_chat", "command", "music_play", "recipe_search",
            "web_search", "automation_draft",
        }:
            try:
                # Only compact feature counters are persisted by the learner.
                self.adaptive_model.observe(raw, intent)
            except Exception:
                pass

    def detect_command(self, normalized: str) -> str | None:
        if not self.command_detector:
            return None
        try:
            result = self.command_detector(normalized)
            return result.strip() if isinstance(result, str) and result.strip() else None
        except Exception:
            return None

    def quick_reply(self, message: str, *, agent_mode: bool = False) -> str | None:
        normalized = self.normalize(message)
        words = set(normalized.split())
        if normalized in {"selam", "merhaba", "sa", "slm", "hey", "heey", "hey neto", "hey netops"}:
            return "Buradayım. Ne yapmak istiyorsun?"
        if any(phrase in normalized for phrase in ("nasilsin", "naber", "keyfin nasil", "iyi misin")):
            return "İyiyim, sistem hazır. İstersen sohbet edelim, istersen bir şey araştıralım."
        if any(phrase in normalized for phrase in (
            "ne yapiyorsun", "ne yapiyosun", "napiyorsun", "napiyosun",
            "napion", "napiyon", "ne yapiyon", "ne yapion",
            "neler yapiyorsun", "neler yapiyosun", "ne yapabilirsin",
            "ozelligin ne", "neler yaparsin",
        )):
            return (
                "Şu an konuşma motorunu yönetiyorum. Sohbet edebilirim, program komutlarını ayırabilirim, "
                "bilmediğim konularda internete bakıp temiz cevap çıkarabilirim, güvenilir bilgileri hafızaya "
                "alabilirim ve müzik, tarif, otomasyon gibi istekleri doğru moda yönlendirebilirim."
            )
        if normalized in {"tamam", "ok", "eyvallah", "sag ol", "tesekkurler", "tesekkur"}:
            return "Tamam, buradayım."
        if normalized in {"devam", "devam et"} and self._turns:
            previous = next((turn.get("query", "") for turn in reversed(self._turns) if turn.get("query")), "")
            if previous:
                return f"{previous} konusundan devam edebiliriz. Ne tarafını açayım?"
        if words <= {"bu", "bunu", "su", "sunu", "onu", "peki"} and self._turns:
            return "Hangi kısmı istediğini bir kelimeyle yaz; önceki konudan devam edeceğim."
        if neto_sohbet_v2 is not None:
            try:
                result = neto_sohbet_v2.quick_reply(
                    message, agent_modu=agent_mode, project=self.project_dir
                )
                if result and result != "NETOPS_ONE_READY":
                    return NetOpsOneText.clean_inline(result)
            except Exception:
                pass
        # Catch new casual phrasing without allowing an uncertain prediction
        # to suppress the normal memory and web-search fallback.
        if self.adaptive_model is not None:
            try:
                prediction = self.adaptive_model.predict(message)
                if prediction and prediction.label == "quick_chat":
                    return "Buradayım. Bunu konuşabiliriz; ne yapmak istediğini biraz açar mısın?"
            except Exception:
                pass
        return None

    def search_web(
        self, message: str, location: NetOpsOneLocation | None = None,
        dynamic_context: str = "", query_override: str = "",
    ) -> NetOpsOneResult:
        query = query_override or self.normalize_query(message)
        effective_query = self.location.enrich_query(query, message)
        if not query or not self._internet_is_enabled():
            return self.fallback_result(query, location)

        evidence: list[str] = []
        if dynamic_context:
            evidence.append(NetOpsOneText.clean_answer(dynamic_context))
        items = self.search_client.search(effective_query, limit=self.max_sources)
        search_evidence = NetOpsOneText.evidence(items)
        if search_evidence:
            evidence.append(search_evidence)
        combined = "\n".join(part for part in evidence if part).strip()
        if not combined:
            return self.fallback_result(query, location)

        text = NetOpsOneText.compose_search_answer(query, items, dynamic_context)
        if not text or text == NETOPS_ONE_FALLBACK:
            return self.fallback_result(query, location)
        source = "structured_search"
        intent = "location_search" if self.location.query_kind(message) else "web_search"
        result = NetOpsOneResult(
            True, text, intent, source=source, query=query,
            title=(NetOpsOneText.clean_inline(query).capitalize() or "NetOps One"),
            location=location.as_dict() if location and location.ok else None,
        )
        if not self.location.needs_fresh(message):
            result.learned = self.memory_store(message, result.text, source=result.source, query=query, title=result.title)
        return result

    def fallback_result(self, query: str, location: NetOpsOneLocation | None = None) -> NetOpsOneResult:
        return NetOpsOneResult(
            False, NETOPS_ONE_FALLBACK, "search_empty", source="local_fallback",
            query=query, title="NetOps One",
            location=location.as_dict() if location and location.ok else None,
        )


    def normalize_query(self, message: Any) -> str:
        return NetOpsOneQueryNormalizer.clean(message)

    def memory_lookup(self, message: Any) -> str | None:
        data = self.load_memory()
        items = data.get("items") if isinstance(data, dict) else {}
        if not isinstance(items, dict):
            return None
        item = items.get(self.normalize(message))
        if not isinstance(item, dict):
            return None
        answer = NetOpsOneText.clean_model(item.get("answer") or "")
        query = str(item.get("query") or message or "")
        if not NetOpsOneText.is_trusted_memory_item(query, answer, item):
            return None
        item["hits"] = int(item.get("hits") or 0) + 1
        item["lastUsedAt"] = self._now()
        self.save_memory(data)
        return answer

    def memory_store(self, message: str, answer: str, *, source: str = "web", query: str = "", title: str = "") -> bool:
        clean = NetOpsOneText.clean_model(answer)
        stored_query = query or self.normalize_query(message)
        if (
            not clean
            or clean == NETOPS_ONE_FALLBACK
            or not NetOpsOneText.is_trusted_memory_item(stored_query, clean, {"source": source})
        ):
            return False
        data = self.load_memory()
        items = data.setdefault("items", {})
        key = self.normalize(stored_query or message)
        if not key:
            return False
        now = self._now()
        items[key] = {
            "question": str(message).strip(), "query": stored_query,
            "title": NetOpsOneText.clean_inline(title or "NetOps One")[:90],
            "answer": clean, "source": source, "createdAt": now,
            "lastUsedAt": now, "hits": 0,
        }
        data["version"] = NETOPS_ONE_VERSION
        data["updatedAt"] = now
        self.save_memory(data)
        return True

    def ensure_memory(self) -> dict[str, Any]:
        if not self.memory_path.exists():
            default = {"version": NETOPS_ONE_VERSION, "items": {}, "last": {}, "updatedAt": self._now()}
            self.memory_path.write_text(
                json.dumps(default, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            return default
        data = self.load_memory()
        if not isinstance(data.get("items"), dict):
            data["items"] = {}
        original_items = data.get("items") or {}
        cleaned_items: dict[str, Any] = {}
        quarantine: dict[str, Any] = {}
        removed = 0
        migration_changed = False
        for key, item in original_items.items():
            if not isinstance(item, dict):
                quarantine[str(key)] = item
                removed += 1
                continue
            answer = NetOpsOneText.clean_model(item.get("answer") or "")
            query = NetOpsOneQueryNormalizer.clean(
                item.get("query") or item.get("question") or key
            )
            if not query or not NetOpsOneText.is_trusted_memory_item(query, answer, item):
                quarantine[str(key)] = item
                removed += 1
                continue
            item["answer"] = answer
            item["query"] = query
            item["title"] = NetOpsOneText.clean_inline(item.get("title") or "NetOps One")[:90]
            canonical_key = self.normalize(query)
            migration_changed = migration_changed or canonical_key != str(key)
            if canonical_key and canonical_key not in cleaned_items:
                cleaned_items[canonical_key] = item
            elif canonical_key:
                quarantine[str(key)] = item
                removed += 1
        changed = (
            data.get("version") != NETOPS_ONE_VERSION
            or len(cleaned_items) != len(original_items)
            or set(cleaned_items) != set(original_items)
            or migration_changed
            or not isinstance(data.get("last"), dict)
        )
        if removed or set(cleaned_items) != set(original_items):
            data["items"] = cleaned_items
            data["migration"] = {
                "removedLegacyEntries": removed,
                "time": self._now(),
                "backup": str(self.memory_path.with_suffix(".legacy.bak")),
            }
            if quarantine:
                try:
                    quarantine_path = self.memory_path.with_name("netops_memory.quarantine.json")
                    quarantine_path.write_text(
                        json.dumps({"version": 1, "createdAt": self._now(), "items": quarantine},
                                   ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                except Exception:
                    pass
            try:
                backup = self.memory_path.with_suffix(".legacy.bak")
                if not backup.exists():
                    backup.write_text(
                        json.dumps(
                            {"version": data.get("version"), "items": original_items},
                            ensure_ascii=False, indent=2,
                        ) + "\n", encoding="utf-8"
                    )
            except Exception:
                pass
        data["version"] = NETOPS_ONE_VERSION
        if not isinstance(data.get("last"), dict):
            data["last"] = {}
        if changed:
            data["updatedAt"] = self._now()
            self.save_memory(data)
        return data

    def ensure_word_core(self) -> dict[str, Any]:
        """Create/update the local safe vocabulary core without network access."""
        default = json.loads(json.dumps(NETOPS_ONE_WORD_CORE, ensure_ascii=False))
        now = self._now()
        try:
            data = json.loads(self.word_core_path.read_text(encoding="utf-8-sig"))
            if not isinstance(data, dict):
                data = {}
        except Exception:
            data = {}

        changed = data.get("version") != NETOPS_ONE_WORD_CORE_VERSION
        intents = data.setdefault("intents", {})
        synonyms = data.setdefault("synonyms", {})
        for group_name, words in default["intents"].items():
            existing = [
                str(word).strip() for word in intents.get(group_name, [])
                if str(word).strip() and not NetOpsOneText.contains_abusive_text(word)
            ]
            merged = list(dict.fromkeys(existing + [
                word for word in words if not NetOpsOneText.contains_abusive_text(word)
            ]))
            if intents.get(group_name) != merged:
                intents[group_name] = merged
                changed = True
        for group_name, words in default["synonyms"].items():
            existing = [
                str(word).strip() for word in synonyms.get(group_name, [])
                if str(word).strip() and not NetOpsOneText.contains_abusive_text(word)
            ]
            merged = list(dict.fromkeys(existing + [
                word for word in words if not NetOpsOneText.contains_abusive_text(word)
            ]))
            if synonyms.get(group_name) != merged:
                synonyms[group_name] = merged
                changed = True
        data["version"] = NETOPS_ONE_WORD_CORE_VERSION
        data.setdefault("createdAt", now)
        if changed or not self.word_core_path.exists():
            data["updatedAt"] = now
            self.word_core_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        return data

    def load_memory(self) -> dict[str, Any]:
        try:
            value = json.loads(self.memory_path.read_text(encoding="utf-8-sig"))
            return value if isinstance(value, dict) else {"version": NETOPS_ONE_VERSION, "items": {}, "last": {}}
        except Exception:
            return {"version": NETOPS_ONE_VERSION, "items": {}, "last": {}, "updatedAt": self._now()}

    def save_memory(self, data: dict[str, Any]) -> None:
        self.memory_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def _remember_last(self, message: str, answer: str, intent: str, source: str) -> None:
        self._record_turn(message, self.normalize(message), answer, intent)

    def _internet_is_enabled(self) -> bool:
        try:
            return bool(self.internet_enabled() if callable(self.internet_enabled) else self.internet_enabled)
        except Exception:
            return True

    @staticmethod
    def normalize(value: Any) -> str:
        if neto_sohbet_v2 is not None:
            try:
                return neto_sohbet_v2.temizle(value)
            except Exception:
                pass
        text = str(value or "").casefold().strip()
        table = str.maketrans({"ı": "i", "İ": "i", "ğ": "g", "ü": "u", "ş": "s", "ö": "o", "ç": "c"})
        return re.sub(r"\s+", " ", text.translate(table)).strip(" \t\r\n.!?")

    @staticmethod
    def _now() -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S")


# Public compatibility facade: existing NetOps callers now use the v3 pipeline.
NetOpsOneEngine = NetOpsOneEngineV3
VERSION = NETOPS_ONE_VERSION
FALLBACK_MESSAGE = NETOPS_ONE_FALLBACK
_ENGINE_CACHE: dict[str, NetOpsOneEngineV3] = {}
_ENGINE_CACHE_LOCK = _netops_threading.RLock()


def get_engine(
    project_dir: str | Path | None = None,
    command_detector: CommandDetector | None = None,
    internet_enabled: Callable[[], bool] | bool = True,
    max_sources: int = 3,
    internal_opener: Callable[[str, bool], Any] | None = None,
) -> NetOpsOneEngineV3:
    """Uygulama süresince tek sohbet motoru ve tek 6 turluk bağlam kullanır."""
    base = _netops_runtime_project_dir(project_dir)
    key = str(base).casefold()
    with _ENGINE_CACHE_LOCK:
        engine = _ENGINE_CACHE.get(key)
        if engine is None:
            engine = NetOpsOneEngineV3(
                project_dir=base,
                command_detector=command_detector,
                internet_enabled=internet_enabled,
                max_sources=max_sources,
                internal_opener=internal_opener,
            )
            _ENGINE_CACHE[key] = engine
        elif command_detector is not None and engine.command_detector is None:
            engine.command_detector = command_detector
        elif internal_opener is not None and engine.internal_opener is None:
            engine.internal_opener = internal_opener
        return engine


def start_location_service(project: str | Path = ".") -> dict[str, Any]:
    service = NetOpsOneLocationService.shared(project)
    service.start_background()
    with service._lock:
        return service._location.as_dict()


def ensure_files(project: str | Path = ".") -> dict[str, Any]:
    engine = get_engine(project_dir=project)
    data = engine.ensure_memory()
    word_core = engine.ensure_word_core()
    return {
        "ok": True, "path": str(engine.memory_path),
        "items": len(data.get("items") or {}), "version": NETOPS_ONE_VERSION,
        "word_core_path": str(engine.word_core_path),
        "word_core_version": str(word_core.get("version") or ""),
        "location": engine.location.get().as_dict(),
    }


def answer(message: Any, **kwargs: Any) -> str:
    allowed = {
        "project_dir", "command_detector", "internet_enabled", "max_sources",
        "internal_opener",
    }
    engine = get_engine(**{
        key: value for key, value in kwargs.items() if key in allowed
    })
    return engine.answer(message).text


@dataclass
class NetOpsOneResultV3:
    ok: bool
    text: str
    intent: str
    source: str = "netops_one"
    command: str | None = None
    cached: bool = False
    learned: bool = False
    query: str = ""
    title: str = "NetOps One"
    location: dict[str, Any] | None = None
    action: str = ""
    action_status: str = ""
    action_label: str = ""
    metadata: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok, "text": self.text, "intent": self.intent,
            "source": self.source, "command": self.command,
            "cached": self.cached, "learned": self.learned,
            "query": self.query, "title": self.title, "location": self.location,
            "action": self.action, "action_status": self.action_status,
            "action_label": self.action_label, "metadata": self.metadata,
        }


NetOpsOneResult = NetOpsOneResultV3


def _netops_one_from_weather_module_with_stamp(self: NetOpsOneLocationService) -> NetOpsOneLocation:
    try:
        import neto_weather
        location = NetOpsOneLocation.from_mapping(
            neto_weather.auto_detect_location(save=True, silent_fail=True)
        )
        if location.ok and not location.updated_at:
            location.updated_at = self._now()
        return location
    except Exception:
        return NetOpsOneLocation()


NetOpsOneLocationService._from_weather_module = _netops_one_from_weather_module_with_stamp


# Frozen EXE için kalıcı kullanıcı verisi ve paketleme uyumluluğu.
import sys as _netops_sys

def _netops_runtime_project_dir(project: str | Path | None) -> Path:
    if getattr(_netops_sys, "frozen", False):
        appdata = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
        target = appdata / "NetoAsistan"
        target.mkdir(parents=True, exist_ok=True)
        return target
    return Path(project or Path(__file__).resolve().parent).resolve()


_netops_v3_init = NetOpsOneEngineV3.__init__


def _netops_v3_init_persistent(
    self: NetOpsOneEngineV3,
    project_dir: str | Path | None = None,
    command_detector: CommandDetector | None = None,
    internet_enabled: Callable[[], bool] | bool = True,
    max_sources: int = 3,
    internal_opener: Callable[[str, bool], Any] | None = None,
) -> None:
    _netops_v3_init(
        self,
        project_dir=_netops_runtime_project_dir(project_dir),
        command_detector=command_detector,
        internet_enabled=internet_enabled,
        max_sources=max_sources,
        internal_opener=internal_opener,
    )


NetOpsOneEngineV3.__init__ = _netops_v3_init_persistent


def start_location_service(project: str | Path = ".") -> dict[str, Any]:
    service = NetOpsOneLocationService.shared(_netops_runtime_project_dir(project))
    service.start_background()
    with service._lock:
        return service._location.as_dict()


def _netops_one_status_code(result: NetOpsOneResultV3) -> str:
    if not getattr(result, "ok", False):
        return "ERR_CODE"
    if str(getattr(result, "intent", "") or "").lower() in {
        "web_search", "location_search", "recipe", "recipe_search",
        "music_play", "public_api_tool", "location_data", "location_context",
    }:
        return "WEB_SYNC_OK"
    return "EXEC_OK"


def _netops_one_mode_code(result: NetOpsOneResultV3) -> str:
    intent = str(getattr(result, "intent", "") or "").lower()
    action = str(getattr(result, "action", "") or "").lower()
    query = str(getattr(result, "query", "") or "").casefold()
    if intent in {"music_play", "media_clarification"} or action in {"open_music", "open_video"}:
        return "SARKI_MODE"
    if any(token in query for token in ("oyun", "game", "gaming")):
        return "OYUN_MODE"
    if any(token in query for token in ("ders", "çalışma", "calisma", "study")):
        return "DERS_MODE"
    if intent in {"idle", "ambient", "no_mode"}:
        return "NO_MODE"
    return "ACTIVE_MODE"


def _netops_one_memory_code(result: NetOpsOneResultV3) -> str:
    if getattr(result, "learned", False) or str(getattr(result, "intent", "") or "") == "correction":
        return "WRITE_OK"
    return "READ_OK"


def _netops_one_trace(result: NetOpsOneResultV3) -> str:
    intent = str(getattr(result, "intent", "") or "response")
    query = str(getattr(result, "query", "") or getattr(result, "title", "") or "netops_one")
    source = str(getattr(result, "source", "") or "local")
    memory = _netops_one_memory_code(result)
    if source in {"duckduckgo_search", "public-apis", "recipe_search"} or "search" in intent:
        step_2 = "Türkçe yapılandırılmış veri / web senkronizasyonu tamamlandı."
    elif source in {"local", "netops_command", MEMORY_FILE}:
        step_2 = "Yerel motor veya komut katmanı kullanıldı."
    else:
        step_2 = f"Kaynak katmanı işlendi: {source}."
    return (
        "[THINKING_PROCESS]\n"
        f"> Target: {query or intent}\n"
        f"> Step 1: Hafıza/parametre kontrolü: {memory}\n"
        f"> Step 2: {step_2}\n"
        f"> Step 3: Sentetik yanıt formatlandı; gizli muhakeme ifşa edilmedi.\n"
        "> [THINKING_COMPLETE]"
    )


def _netops_one_sanitize_output_text(text: Any) -> str:
    value = str(text or "").strip()
    replacements = {
        "NETOPS_ONE_READY": "Buradayım. Ne yapmak istiyorsun?",
        "Selam, NetOps One hazır. Ne yapıyoruz?": "Buradayım. Ne yapmak istiyorsun?",
        "Merhaba, buradayım. Ne bakıyoruz?": "Buradayım. Ne yapmak istiyorsun?",
        "Selam, buradayım. Ne yapıyoruz?": "Buradayım. Ne yapmak istiyorsun?",
        "Merhaba, buradayım. Ne yapıyoruz?": "Buradayım. Ne yapmak istiyorsun?",
        "Aleyküm selam, sistem hazır.": "Buradayım. Ne yapmak istiyorsun?",
        "Selam, yaz komutu birlikte çözelim.": "Buradayım. Ne yapmak istiyorsun?",
        "Tamam, bu düzeltmeyi hafızama aldım.": "Düzeltme hafızaya yazıldı.",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    if re.match(r"(?is)^\s*(?:selam|merhaba|aleyküm selam|aleykum selam)\b", value):
        value = "Buradayım. Ne yapmak istiyorsun?"
    value = re.sub(r"(?im)^\s*(?:anladım|harika|tabii ki|tabii|işte|iste|rica ederim)[,.!:\s-]*", "", value)
    return value.strip()


def _netops_one_format_result(result: NetOpsOneResultV3) -> NetOpsOneResultV3:
    try:
        text = _netops_one_sanitize_output_text(getattr(result, "text", ""))
        if text.startswith("[STATUS:"):
            return result
        header = (
            f"[STATUS: {_netops_one_status_code(result)} | "
            f"MODE: {_netops_one_mode_code(result)} | "
            f"MEMORY: {_netops_one_memory_code(result)} | "
            "ENGINE: NETOPS_ONE]"
        )
        result.text = f"{header}\n{_netops_one_trace(result)}\n\n{text}"
    except Exception:
        pass
    return result


_netops_one_v3_answer_unformatted = NetOpsOneEngineV3.answer


def _netops_one_v3_answer_formatted(self: NetOpsOneEngineV3, message: Any, *, agent_mode: bool = False) -> NetOpsOneResult:
    return _netops_one_format_result(
        _netops_one_v3_answer_unformatted(self, message, agent_mode=agent_mode)
    )


# The core prompt is for internal development guidance only. The desktop chat UI
# must show clean assistant text, not status panels or processing traces.
NetOpsOneEngineV3.answer = _netops_one_v3_answer_unformatted


# NETOPS HARBILIG ROUTER
# NetOps One adını kullanan eski dosyalar kırılmasın diye public semboller
# yeni Harbilig motoruna yönlendirilir. Eski sınıflar yalnızca geriye dönük
# kaynak olarak dosyada durur; runtime konuşma motoru Harbilig'dir.
try:
    from netops_harbilig_engine import (
        FALLBACK_MESSAGE as NETOPS_ONE_FALLBACK,
        HARBILIG_VERSION as VERSION,
        HarbiligResult as NetOpsOneResult,
        HarbiligResult as NetOpsOneResultV3,
        HarbiligSearchClient as NetOpsOneStructuredSearch,
        HarbiligSearchItem as SearchItem,
        HarbiligText as NetOpsOneText,
        NetOpsHarbiligEngine as NetOpsOneEngine,
        NetOpsHarbiligEngine as NetOpsOneEngineV3,
        answer,
        ensure_files,
        get_engine,
        start_location_service,
    )
except Exception:
    pass
