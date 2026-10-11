# NETOPS HARBILIG ENGINE
# Scrapling destekli, harici LLM kullanmayan NetOps konuşma ve bilgi motoru.

from __future__ import annotations

import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

try:
    from config import KUFUR_LISTESI as _PROFANITY_LIST
except Exception:  # pragma: no cover
    _PROFANITY_LIST = []

try:
    import neto_sohbet_v2
except Exception:  # pragma: no cover
    neto_sohbet_v2 = None


HARBILIG_VERSION = "1.0"
MEMORY_FILE = "netops_memory.json"
WORD_CORE_FILE = "netops_word_core.json"
FALLBACK_MESSAGE = (
    "Bu konu için güvenilir Türkçe bilgi bulamadım veya içerik okunamadı. "
    "İstersen farklı kelimelerle tekrar arayabilirim."
)
POLITE_WARNING = "Bu şekilde öğrenemem veya devam edemem. Daha temiz yazarsan yardımcı olurum."
CommandDetector = Callable[[str], str | None]

WORD_CORE = {
    "version": HARBILIG_VERSION,
    "engine": "netops_harbilig",
    "intents": {
        "greeting": ["selam", "merhaba", "hey", "sa", "slm", "günaydın", "iyi akşamlar"],
        "wellbeing": ["nasılsın", "naber", "keyfin nasıl", "iyi misin"],
        "capability": [
            "ne yapıyorsun", "ne yapıyosun", "napıyorsun", "napıyosun",
            "napıyon", "ne yapıyon", "neler yaparsın", "ne yapabilirsin",
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
class HarbiligResult:
    ok: bool
    text: str
    intent: str
    source: str = "netops_harbilig"
    command: str | None = None
    cached: bool = False
    learned: bool = False
    query: str = ""
    title: str = "NetOps Harbilig"
    location: dict[str, Any] | None = None
    action: str = ""
    action_status: str = ""
    action_label: str = ""
    metadata: dict[str, Any] | None = None

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
            "location": self.location,
            "action": self.action,
            "action_status": self.action_status,
            "action_label": self.action_label,
            "metadata": self.metadata,
        }


@dataclass
class HarbiligSearchItem:
    title: str
    body: str
    url: str = ""


class HarbiligText:
    _PROFANITY_CACHE: dict[str, Any] | None = None
    STOPWORDS = {
        "bana", "benim", "icin", "için", "ver", "lütfen", "lutfen", "nedir",
        "hakkında", "hakkinda", "bilgi", "misin", "mısın", "mi", "mı", "mu", "mü",
        "bir", "bu", "şu", "su", "ne", "nasıl", "nasil", "ara", "bak", "anlat",
        "açıkla", "acikla", "tarifi", "tarifini", "öğrenebilir", "ogrenebilir",
    }

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
    def clean_inline(value: Any) -> str:
        text = html.unescape(str(value or ""))
        text = re.sub(r"https?://\S+", " ", text, flags=re.I)
        text = re.sub(r"\b(?:[a-z0-9-]+\.)+(?:com|net|org|tr|io|dev|edu|gov|co)(?:/\S*)?", " ", text, flags=re.I)
        text = re.sub(r"(?i)\b(kaynak|source|url|link|snippet|cached)\s*:.*$", " ", text)
        text = re.sub(r"(?i)\b(click here|read more|devamını oku|reklam|sponsored)\b", " ", text)
        return re.sub(r"\s+", " ", text).strip(" -:•\n\t")

    @classmethod
    def clean_answer(cls, value: Any) -> str:
        text = html.unescape(str(value or "")).replace("\r", "")
        text = re.sub(r"https?://\S+", "", text, flags=re.I)
        text = re.sub(r"\b(?:[a-z0-9-]+\.)+(?:com|net|org|tr|io|dev|edu|gov|co)(?:/\S*)?", "", text, flags=re.I)
        text = re.sub(r"(?im)^\s*(?:kaynak|source|url|link|snippet|cached)\s*:.*$", "", text)
        text = re.sub(r"(?i)\b(?:web'de|webde)\s+(?:şunları|sunu|bulduklarım)\b[^:\n]*:?", "", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return "\n".join(line.strip() for line in text.splitlines() if line.strip()).strip(" -:\n\t")

    @classmethod
    def clean_model(cls, value: Any) -> str:
        text = cls.clean_answer(value)
        text = re.sub(r"(?im)^\s*(?:netops one|netops harbilig|asistan|assistant)\s*:\s*", "", text)
        text = re.sub(r"(?im)^\s*(?:işte|iste)\s*(?:cevap|yanıt|yanit)\s*:\s*", "", text)
        return text[:5000].strip()

    @classmethod
    def _profanity_cache(cls) -> dict[str, Any]:
        if cls._PROFANITY_CACHE is not None:
            return cls._PROFANITY_CACHE
        tokens: set[str] = set()
        phrases: set[str] = set()
        obfuscated: list[str] = []
        for raw_bad in _PROFANITY_LIST:
            bad_tokens = re.findall(r"[a-z0-9çğıöşü]+", str(raw_bad or "").casefold())
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
        tokens = re.findall(r"[a-z0-9çğıöşü]+", text)
        if not tokens:
            return False
        if " ".join(tokens) in {"selam", "merhaba", "hey", "naber", "sa", "slm"}:
            return False
        cache = cls._profanity_cache()
        spaced = " " + " ".join(tokens) + " "
        compact = re.sub(r"[^a-z0-9çğıöşü]+", "", text)
        return (
            bool(set(tokens) & cache["tokens"])
            or any(f" {phrase} " in spaced for phrase in cache["phrases"])
            or any(token in compact for token in cache["obfuscated"])
        )

    @classmethod
    def core_tokens(cls, value: Any) -> list[str]:
        return [
            token for token in re.findall(r"[\wçğıöşü]+", str(value or "").casefold())
            if len(token) >= 3 and token not in cls.STOPWORDS
        ]

    @classmethod
    def safe(cls, value: Any) -> bool:
        lowered = str(value or "").casefold()
        return all(token not in lowered for token in ("http://", "https://", "kaynak:", "web'de"))

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
        blocked = (
            "web'de", "webde şunları", "1. link", "2. link", "kaynak:",
            "lyrics", "songtext", "wiktionary", "microsoft corporation is an",
            "karachi halwa", "› wiki", "› channel", "› watch", "copyright",
            "youtube music", "playlist", "iplocation", "ben neredeyim",
        )
        if any(marker in lowered for marker in blocked):
            return False
        is_recipe = "malzemeler" in lowered and ("hazırlan" in lowered or "yapılış" in lowered or "yapilis" in lowered)
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
    def compose_search_answer(cls, query: str, items: list[HarbiligSearchItem], dynamic_context: str = "") -> str:
        direct = cls.clean_model(dynamic_context)
        if direct and cls.safe(direct):
            return direct[:1600]
        sentences: list[str] = []
        seen: set[str] = set()
        for item in items[:4]:
            text = cls.clean_answer(item.body or item.title)
            for candidate in re.split(r"(?<=[.!?])\s+|\n+|\s+[•-]\s+", text):
                candidate = re.sub(r"\s+", " ", candidate).strip(" -:•")
                if len(candidate) < 28 or cls.contains_abusive_text(candidate):
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
    def compose_recipe_answer(cls, query: str, items: list[HarbiligSearchItem]) -> str:
        source = " ".join(cls.clean_answer(f"{item.title}. {item.body}") for item in items[:5])
        source = re.sub(r"\s+", " ", source).strip()
        if not source:
            return ""
        ingredient_match = re.search(
            r"\b(?:gerekli\s+)?malzemeler\b\s*[:\-]?\s*(.*?)(?=\b(?:hazırlanışı|hazirlanisi|yapılışı|yapilisi|hazırlama|hazirlama)\b|$)",
            source,
            flags=re.I,
        )
        preparation_match = re.search(
            r"\b(?:hazırlanışı|hazirlanisi|yapılışı|yapilisi|hazırlama|hazirlama)\b\s*[:\-]?\s*(.*)$",
            source,
            flags=re.I,
        )

        def parts(value: str) -> list[str]:
            cleaned: list[str] = []
            for piece in re.split(r"\s*(?:[•;]|\b\d+[.)])\s*|(?<=[.!?])\s+", value or ""):
                item = cls.clean_inline(piece).strip(" .:-")
                if len(item) >= 3 and item.casefold() not in {x.casefold() for x in cleaned}:
                    cleaned.append(item)
            return cleaned[:10]

        ingredients = parts(ingredient_match.group(1)) if ingredient_match else []
        preparation = parts(preparation_match.group(1)) if preparation_match else []
        title = re.sub(r"\b(?:tarif|tarifi|malzemeler|hazırlanışı|hazirlanisi)\b", " ", str(query or ""), flags=re.I)
        title = re.sub(r"\s+", " ", title).strip().capitalize() or "Tarif"
        sections = [title]
        if ingredients:
            sections.append("Malzemeler\n" + "\n".join(f"• {item}" for item in ingredients))
        if preparation:
            sections.append("Hazırlanışı\n" + "\n".join(f"{index}. {item}" for index, item in enumerate(preparation, 1)))
        if len(sections) == 1:
            summary = cls.compose_search_answer(query, items)
            if not summary:
                return ""
            sections.append("Kısa özet\n" + summary)
        return "\n\n".join(sections)[:2400]


class HarbiligQueryNormalizer:
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


class HarbiligSearchClient:
    BLOCKED_HOST_PARTS = (
        "youtube.com", "youtu.be", "tiktok.com", "instagram.com", "facebook.com",
        "x.com", "twitter.com", "reddit.com", "pinterest.", "wiktionary.org",
        "eksisozluk.com", "sozluk.gov.tr", "genius.com", "azlyrics.com",
        "lyrics.com", "musixmatch.com", "songlyrics.com",
    )

    def search(self, query: str, limit: int = 3) -> list[HarbiligSearchItem]:
        query = str(query or "").strip()
        if not query:
            return []
        rows = self._scrapling_search(query, limit)
        if not rows:
            rows = self._duckduckgo_html(query, limit)
        return self._filter(rows, query)[:limit]

    def fetch_page_text(self, url: str) -> str:
        if not str(url or "").strip():
            return ""
        try:
            from scrapling import Fetcher  # type: ignore
            page = Fetcher.get(url)
            if hasattr(page, "text"):
                return HarbiligText.clean_answer(page.text)
            return HarbiligText.clean_answer(str(page))
        except Exception:
            pass
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "NetOpsHarbilig/1.0"})
            with urllib.request.urlopen(request, timeout=8) as response:
                raw = response.read(512_000).decode("utf-8", "ignore")
            return self._html_to_text(raw)
        except Exception:
            return ""

    def search_youtube_video(self, query: str, limit: int = 6) -> str:
        rows = self._duckduckgo_html(f"{query} site:youtube.com/watch", max(3, limit))
        for item in rows:
            parsed = urllib.parse.urlparse(item.url)
            host = parsed.netloc.lower().removeprefix("www.")
            if host == "youtu.be":
                video_id = parsed.path.strip("/").split("/")[0]
                if video_id:
                    return f"https://www.youtube.com/watch?v={video_id}"
            if host.endswith("youtube.com") and parsed.path == "/watch":
                video_id = urllib.parse.parse_qs(parsed.query).get("v", [""])[0].strip()
                if video_id:
                    return f"https://www.youtube.com/watch?v={video_id}"
        return ""

    def _scrapling_search(self, query: str, limit: int) -> list[HarbiligSearchItem]:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(query)}&kl=tr-tr"
        try:
            from scrapling import Fetcher  # type: ignore
            page = Fetcher.get(url)
            html_text = str(getattr(page, "html", "") or getattr(page, "body", "") or page)
            return self._parse_duckduckgo_html(html_text, limit)
        except Exception:
            return []

    def _duckduckgo_html(self, query: str, limit: int) -> list[HarbiligSearchItem]:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(query)}&kl=tr-tr"
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "NetOpsHarbilig/1.0"})
            with urllib.request.urlopen(request, timeout=8) as response:
                raw = response.read(700_000).decode("utf-8", "ignore")
            return self._parse_duckduckgo_html(raw, limit)
        except Exception:
            return []

    def _parse_duckduckgo_html(self, html_text: str, limit: int) -> list[HarbiligSearchItem]:
        rows: list[HarbiligSearchItem] = []
        chunks = re.split(r'class=["\'][^"\']*result__a[^"\']*["\']', html_text)
        for chunk in chunks[1 : limit * 4 + 1]:
            href_match = re.search(r'href=["\']([^"\']+)["\']', chunk)
            title_match = re.search(r">\s*(.*?)\s*</a>", chunk, flags=re.S)
            snippet_match = re.search(r'class=["\'][^"\']*result__snippet[^"\']*["\'][^>]*>(.*?)</', chunk, flags=re.S)
            url = html.unescape(href_match.group(1)) if href_match else ""
            if "uddg=" in url:
                try:
                    url = urllib.parse.unquote(urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("uddg", [url])[0])
                except Exception:
                    pass
            title = HarbiligText.clean_inline(re.sub(r"<.*?>", " ", title_match.group(1))) if title_match else ""
            body = HarbiligText.clean_inline(re.sub(r"<.*?>", " ", snippet_match.group(1))) if snippet_match else ""
            if title or body:
                rows.append(HarbiligSearchItem(title=title, body=body, url=url))
        return rows

    def _html_to_text(self, html_text: str) -> str:
        text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html_text)
        text = re.sub(r"(?is)<br\s*/?>", "\n", text)
        text = re.sub(r"(?is)</p>|</h[1-6]>|</li>", "\n", text)
        text = re.sub(r"(?is)<.*?>", " ", text)
        return HarbiligText.clean_answer(text)

    def _filter(self, items: list[HarbiligSearchItem], query: str = "") -> list[HarbiligSearchItem]:
        result: list[HarbiligSearchItem] = []
        seen: set[str] = set()
        for item in items:
            if not item.title and not item.body:
                continue
            if self.is_blocked(item.url, item.title, item.body):
                continue
            title = HarbiligText.clean_inline(item.title)
            body = HarbiligText.clean_inline(item.body)
            if len(title + body) < 30:
                continue
            if query and self.relevance_score(query, title, body) < 0.25:
                continue
            key = re.sub(r"\W+", "", f"{title} {body}".casefold())[:140]
            if key and key not in seen:
                seen.add(key)
                result.append(HarbiligSearchItem(title=title, body=body, url=item.url))
        return result

    def relevance_score(self, query: str, title: str, body: str) -> float:
        tokens = HarbiligText.core_tokens(query)
        if not tokens:
            return 0.5
        haystack = f"{title} {body}".casefold()
        hits = sum(1 for token in set(tokens) if token in haystack)
        return hits / max(1, len(set(tokens)))

    def is_blocked(self, url: str = "", title: str = "", body: str = "") -> bool:
        host = urllib.parse.urlparse(str(url or "")).netloc.lower().replace("www.", "")
        full = f"{host} {url} {title} {body}".casefold()
        words = ("lyrics", "şarkı sözü", "sarki sozu", "songtext", "wiktionary", "sözlük", "sozluk")
        return (
            any(part in host for part in self.BLOCKED_HOST_PARTS)
            or any(word in full for word in words)
            or HarbiligText.contains_abusive_text(full)
        )


class NetOpsHarbiligEngine:
    def __init__(
        self,
        project_dir: str | Path | None = None,
        command_detector: CommandDetector | None = None,
        internet_enabled: Callable[[], bool] | bool = True,
        max_sources: int = 3,
        internal_opener: Callable[[str, bool], Any] | None = None,
    ) -> None:
        self.project_dir = self._runtime_project_dir(project_dir)
        self.memory_path = self.project_dir / MEMORY_FILE
        self.word_core_path = self.project_dir / WORD_CORE_FILE
        self.command_detector = command_detector
        self.internet_enabled = internet_enabled
        self.max_sources = max(1, min(3, int(max_sources or 3)))
        self.internal_opener = internal_opener
        self.search_client = HarbiligSearchClient()
        self._turns: deque[dict[str, str]] = deque(maxlen=6)
        self._last_media: dict[str, str] = {}
        self._restore_recent_turns(self.ensure_memory())
        self.ensure_word_core()

    def answer(self, message: Any, *, agent_mode: bool = False) -> HarbiligResult:
        raw = str(message or "").strip()
        normalized = self.normalize(raw)
        if not normalized:
            return HarbiligResult(False, "Bir şey yazmadın.", "empty", source="local")
        if HarbiligText.contains_abusive_text(raw):
            result = HarbiligResult(True, POLITE_WARNING, "safety_filter", source="local", query=normalized, title="Güvenlik")
            self._record_turn(raw, normalized, result.text, result.intent)
            return result
        command = None if agent_mode else self.detect_command(normalized)
        if command:
            result = HarbiligResult(True, command, "command", source="netops_command", command=command, title="Komut")
            self._record_turn(raw, normalized, result.text, result.intent)
            return result
        correction = self._explicit_correction(raw)
        if correction:
            correction_query, correction_answer = correction
            stored = self.memory_store(raw, correction_answer, source="explicit_user_correction", query=correction_query, title="Kullanıcı düzeltmesi")
            result = HarbiligResult(
                True,
                "Düzeltme hafızaya yazıldı." if stored else "Bu düzeltme güvenli bulunmadığı için hafızaya yazılmadı.",
                "correction",
                source="local",
                query=correction_query,
                title="Hafıza",
                learned=stored,
            )
            self._record_turn(raw, correction_query, result.text, result.intent)
            return result
        recall = self._recall_reply(raw)
        if recall:
            result = HarbiligResult(True, recall, "conversation_memory", source="local", query=normalized, title="Sohbet hafızası")
            self._record_turn(raw, normalized, result.text, result.intent)
            return result
        quick = self.quick_reply(raw, agent_mode=agent_mode)
        if quick:
            result = HarbiligResult(True, quick, "quick_chat", source="local")
            self._record_turn(raw, normalized, result.text, result.intent)
            return result

        query = self.normalize_query(raw)
        contextual_query = self._contextual_query(raw, query)
        media_kind, media_query = self._media_intent(raw, contextual_query)
        if media_kind == "recipe":
            result = self._answer_recipe(raw, media_query)
        elif media_kind == "music_missing":
            result = HarbiligResult(True, "Hangi şarkıyı veya sanatçıyı çalmamı istersin?", "media_clarification", source="local", title="Müzik")
        elif media_kind == "music_play":
            result = self._answer_music(raw, media_query)
        else:
            hit = self.memory_lookup(contextual_query) or self.memory_lookup(query) or self.memory_lookup(raw)
            if hit:
                result = HarbiligResult(True, hit, "memory", source=MEMORY_FILE, cached=True, query=query, title="Hafızadan")
            else:
                result = self.search_web(raw, query_override=contextual_query)
        self._record_turn(raw, result.query or contextual_query, result.text, result.intent)
        return result

    def quick_reply(self, message: str, *, agent_mode: bool = False) -> str | None:
        normalized = self.normalize(message)
        words = set(normalized.split())
        if any(phrase in normalized for phrase in (
            "canim sikiliyor", "canim sikildi", "sikiliyorum", "bunaldim",
            "moralim bozuk", "keyfim yok", "canim cok sikiliyor",
        )):
            return (
                "Anladım, bunu arama konusu yapmıyorum. İstersen hemen bir şey seçelim: "
                "müzik açabiliriz, kısa bir oyun/sohbet yapabiliriz, yeni özellik fikri üretebiliriz "
                "ya da birlikte küçük bir görev planlayabiliriz."
            )
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
                "Şu an NetOps Harbilig konuşma motorunu yönetiyorum. Sohbet edebilirim, program komutlarını ayırabilirim, "
                "Scrapling varsa sayfadan daha temiz bilgi çıkarabilirim, bilmediğim konularda internete bakabilirim "
                "ve güvenilir bilgileri hafızaya alabilirim."
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
                result = neto_sohbet_v2.quick_reply(message, agent_modu=agent_mode, project=self.project_dir)
                if result and result != "NETOPS_ONE_READY":
                    return HarbiligText.clean_inline(result)
            except Exception:
                pass
        return None

    def search_web(self, message: str, location: Any = None, dynamic_context: str = "", query_override: str = "") -> HarbiligResult:
        query = query_override or self.normalize_query(message)
        if not query or not self._internet_is_enabled():
            return self.fallback_result(query)
        items = self.search_client.search(query, limit=self.max_sources)
        if not items:
            return self.fallback_result(query)
        enriched_items: list[HarbiligSearchItem] = []
        for item in items[: self.max_sources]:
            page_text = self.search_client.fetch_page_text(item.url) if item.url else ""
            body = page_text[:2200] if page_text else item.body
            enriched_items.append(HarbiligSearchItem(item.title, body, item.url))
        text = HarbiligText.compose_search_answer(query, enriched_items, dynamic_context)
        if not text:
            return self.fallback_result(query)
        result = HarbiligResult(True, text, "web_search", source="scrapling_search", query=query, title=HarbiligText.clean_inline(query).capitalize() or "NetOps Harbilig")
        result.learned = self.memory_store(message, result.text, source=result.source, query=query, title=result.title)
        return result

    def fallback_result(self, query: str, location: Any = None) -> HarbiligResult:
        return HarbiligResult(False, FALLBACK_MESSAGE, "search_empty", source="local_fallback", query=query, title="NetOps Harbilig")

    def _media_intent(self, raw: str, contextual_query: str) -> tuple[str, str]:
        normalized = self.normalize(raw)
        if re.search(r"\b(?:bunu|onu|şunu|sunu)\b\s*(?:aç|ac|çal|cal|oynat|dinlet)\b", normalized) and self._last_media:
            return self._last_media.get("kind", ""), self._last_media.get("query", "")
        if any(hint in normalized for hint in ("tarif", "malzeme", "nasil yapilir", "nasıl yapılır")):
            return "recipe", contextual_query
        if re.search(r"\b(?:çal|cal|dinlet|oynat|başlat|baslat)\b", normalized):
            query = re.sub(r"\b(?:çal|cal|dinlet|oynat|başlat|baslat|youtube|music|spotify)\b", " ", normalized, flags=re.I)
            query = re.sub(r"\s+", " ", query).strip()
            return ("music_play", query) if query else ("music_missing", "")
        return "", contextual_query

    def _answer_recipe(self, raw: str, query: str) -> HarbiligResult:
        query = query or self.normalize_query(raw)
        cached = self.memory_lookup(query)
        items: list[HarbiligSearchItem] = []
        text = cached or ""
        if not text and self._internet_is_enabled():
            items = self.search_client.search(query, limit=self.max_sources)
            text = HarbiligText.compose_recipe_answer(query, items)
            if not text:
                items = self.search_client.search(f"{query} malzemeler hazırlanışı", limit=max(3, self.max_sources))
                text = HarbiligText.compose_recipe_answer(query, items)
        video_url = self.search_client.search_youtube_video(f"{query} tarif") if self._internet_is_enabled() else ""
        action_status = self.open_internal(video_url, autoplay=False) if video_url else "not_found"
        recipe_text = text
        if not text:
            text = FALLBACK_MESSAGE
            if video_url:
                text += "\n\nİlgili tarif videosu açılıyor."
        elif video_url:
            text += "\n\nİlgili tarif videosu açılıyor."
        title = re.sub(r"\b(?:tarif|tarifi|malzemeler|hazırlanışı|hazirlanisi)\b", " ", str(query or ""), flags=re.I)
        title = f"Tarif: {re.sub(r'\\s+', ' ', title).strip().capitalize() or 'NetOps Harbilig'}"
        result = HarbiligResult(
            bool(text and text != FALLBACK_MESSAGE) or bool(video_url),
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
        if items and recipe_text and recipe_text != FALLBACK_MESSAGE:
            result.learned = self.memory_store(raw, recipe_text, source="recipe_search", query=query, title=title)
        self._last_media = {"kind": "recipe", "query": query}
        return result

    def _answer_music(self, raw: str, query: str) -> HarbiligResult:
        if not query:
            return HarbiligResult(True, "Hangi şarkıyı veya sanatçıyı çalmamı istersin?", "media_clarification", source="local", title="Müzik")
        try:
            import neto_music_search
            search_result = neto_music_search.search_and_play(query, open_url=self.open_internal)
        except Exception:
            search_result = {"ok": False, "error": "Müzik araması başlatılamadı"}
        if search_result.get("ok") and search_result.get("opened"):
            title = HarbiligText.clean_inline(str(search_result.get("title") or query)) or query
            text = f"{title} YouTube Music'te açılıyor."
            status = str(search_result.get("action_status") or "queued")
        else:
            text = "Bu şarkı veya sanatçı için YouTube Music sonucu açılamadı."
            status = "failed"
        self._last_media = {"kind": "music_play", "query": query}
        return HarbiligResult(
            bool(search_result.get("ok") and search_result.get("opened")),
            text,
            "music_play",
            source="youtube_music",
            query=query,
            title="YouTube Music",
            action="play_music",
            action_status=status,
            action_label=HarbiligText.clean_inline(str(search_result.get("title") or query)),
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
        return "queued"

    _dispatch_internal = open_internal

    def detect_command(self, normalized: str) -> str | None:
        if not self.command_detector:
            return None
        try:
            result = self.command_detector(normalized)
            return result.strip() if isinstance(result, str) and result.strip() else None
        except Exception:
            return None

    def normalize_query(self, message: Any) -> str:
        return HarbiligQueryNormalizer.clean(message)

    def memory_lookup(self, message: Any) -> str | None:
        data = self.load_memory()
        items = data.get("items") if isinstance(data, dict) else {}
        if not isinstance(items, dict):
            return None
        item = items.get(self.normalize(message))
        if not isinstance(item, dict):
            return None
        answer = HarbiligText.clean_model(item.get("answer") or "")
        query = str(item.get("query") or message or "")
        if not HarbiligText.is_trusted_memory_item(query, answer, item):
            return None
        item["hits"] = int(item.get("hits") or 0) + 1
        item["lastUsedAt"] = self._now()
        self.save_memory(data)
        return answer

    def memory_store(self, message: str, answer: str, *, source: str = "web", query: str = "", title: str = "") -> bool:
        clean = HarbiligText.clean_model(answer)
        stored_query = query or self.normalize_query(message)
        if not clean or clean == FALLBACK_MESSAGE or not HarbiligText.is_trusted_memory_item(stored_query, clean, {"source": source}):
            return False
        data = self.load_memory()
        items = data.setdefault("items", {})
        key = self.normalize(stored_query or message)
        if not key:
            return False
        now = self._now()
        items[key] = {
            "question": str(message).strip(),
            "query": stored_query,
            "title": HarbiligText.clean_inline(title or "NetOps Harbilig")[:90],
            "answer": clean,
            "source": source,
            "createdAt": now,
            "lastUsedAt": now,
            "hits": 0,
        }
        data["version"] = HARBILIG_VERSION
        data["engine"] = "netops_harbilig"
        data["updatedAt"] = now
        self.save_memory(data)
        return True

    def ensure_memory(self) -> dict[str, Any]:
        if not self.memory_path.exists():
            default = {"version": HARBILIG_VERSION, "engine": "netops_harbilig", "items": {}, "last": {}, "updatedAt": self._now()}
            self.memory_path.write_text(json.dumps(default, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return default
        data = self.load_memory()
        if not isinstance(data.get("items"), dict):
            data["items"] = {}
        original_items = data.get("items") or {}
        cleaned_items: dict[str, Any] = {}
        quarantine: dict[str, Any] = {}
        removed = 0
        for key, item in original_items.items():
            if not isinstance(item, dict):
                quarantine[str(key)] = item
                removed += 1
                continue
            answer = HarbiligText.clean_model(item.get("answer") or "")
            query = HarbiligQueryNormalizer.clean(item.get("query") or item.get("question") or key)
            if not query or not HarbiligText.is_trusted_memory_item(query, answer, item):
                quarantine[str(key)] = item
                removed += 1
                continue
            item["answer"] = answer
            item["query"] = query
            item["title"] = HarbiligText.clean_inline(item.get("title") or "NetOps Harbilig")[:90]
            canonical_key = self.normalize(query)
            if canonical_key and canonical_key not in cleaned_items:
                cleaned_items[canonical_key] = item
            elif canonical_key:
                quarantine[str(key)] = item
                removed += 1
        changed = data.get("version") != HARBILIG_VERSION or set(cleaned_items) != set(original_items) or removed
        if removed or set(cleaned_items) != set(original_items):
            data["items"] = cleaned_items
            data["migration"] = {"removedLegacyEntries": removed, "time": self._now(), "backup": str(self.memory_path.with_suffix(".legacy.bak"))}
            if quarantine:
                try:
                    self.memory_path.with_name("netops_memory.quarantine.json").write_text(
                        json.dumps({"version": 1, "createdAt": self._now(), "items": quarantine}, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                except Exception:
                    pass
        data["version"] = HARBILIG_VERSION
        data["engine"] = "netops_harbilig"
        data.setdefault("last", {})
        if changed:
            data["updatedAt"] = self._now()
            self.save_memory(data)
        return data

    def ensure_word_core(self) -> dict[str, Any]:
        default = json.loads(json.dumps(WORD_CORE, ensure_ascii=False))
        now = self._now()
        try:
            data = json.loads(self.word_core_path.read_text(encoding="utf-8-sig"))
            if not isinstance(data, dict):
                data = {}
        except Exception:
            data = {}
        changed = data.get("version") != HARBILIG_VERSION or data.get("engine") != "netops_harbilig"
        intents = data.setdefault("intents", {})
        synonyms = data.setdefault("synonyms", {})
        for group_name, words in default["intents"].items():
            existing = [str(word).strip() for word in intents.get(group_name, []) if str(word).strip() and not HarbiligText.contains_abusive_text(word)]
            merged = list(dict.fromkeys(existing + [word for word in words if not HarbiligText.contains_abusive_text(word)]))
            if intents.get(group_name) != merged:
                intents[group_name] = merged
                changed = True
        for group_name, words in default["synonyms"].items():
            existing = [str(word).strip() for word in synonyms.get(group_name, []) if str(word).strip() and not HarbiligText.contains_abusive_text(word)]
            merged = list(dict.fromkeys(existing + [word for word in words if not HarbiligText.contains_abusive_text(word)]))
            if synonyms.get(group_name) != merged:
                synonyms[group_name] = merged
                changed = True
        data["version"] = HARBILIG_VERSION
        data["engine"] = "netops_harbilig"
        data.setdefault("createdAt", now)
        if changed or not self.word_core_path.exists():
            data["updatedAt"] = now
            self.word_core_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return data

    def load_memory(self) -> dict[str, Any]:
        try:
            value = json.loads(self.memory_path.read_text(encoding="utf-8-sig"))
            return value if isinstance(value, dict) else {"version": HARBILIG_VERSION, "items": {}, "last": {}}
        except Exception:
            return {"version": HARBILIG_VERSION, "items": {}, "last": {}, "updatedAt": self._now()}

    def save_memory(self, data: dict[str, Any]) -> None:
        self.memory_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _contextual_query(self, raw: str, query: str) -> str:
        if not query or not self._turns:
            return query
        normalized = self.normalize(raw)
        markers = ("bu", "bunu", "şu", "su", "onu", "onun", "peki", "fiyatı", "fiyati", "özellikleri", "ozellikleri", "nasıl", "nasil", "kaç", "kac", "neden")
        if not any(marker in normalized.split() for marker in markers):
            return query
        previous = next((turn.get("query", "") for turn in reversed(self._turns) if turn.get("query")), "")
        if not previous or previous.casefold() in query.casefold():
            return query
        return f"{previous} {query}".strip()

    def _explicit_correction(self, raw: str) -> tuple[str, str] | None:
        match = re.match(r"^\s*(?:doğrusu|dogrusu|düzelt|duzelt|yanlış cevap|yanlis cevap)\s*[:,-]?\s*(.+)$", str(raw or ""), flags=re.I)
        if not match:
            return None
        body = match.group(1).strip()
        if not body:
            return None
        if "=" in body:
            query, answer = body.split("=", 1)
            query = self.normalize_query(query)
            answer = HarbiligText.clean_model(answer)
            return (query, answer) if query and answer else None
        if "->" in body:
            query, answer = body.split("->", 1)
            query = self.normalize_query(query)
            answer = HarbiligText.clean_model(answer)
            return (query, answer) if query and answer else None
        previous = next((turn.get("query", "") for turn in reversed(self._turns) if turn.get("query")), "")
        answer = HarbiligText.clean_model(body)
        return (previous, answer) if previous and answer else None

    def _recall_reply(self, raw: str) -> str | None:
        normalized = self.normalize(raw)
        if not self._turns:
            if any(phrase in normalized for phrase in ("ilk yazdigim", "ilk mesaj", "son yazdigim", "az once ne yazdim", "ne yazdim")):
                return "Bu oturumda hatırlayabileceğim önceki mesaj yok."
            return None

        user_turns = [
            turn for turn in self._turns
            if turn.get("message") and not HarbiligText.contains_abusive_text(turn.get("message"))
        ]
        if not user_turns:
            return None
        if any(phrase in normalized for phrase in (
            "ilk yazdigim", "ilk yazdigimi", "ilk mesajim", "ilk mesaj",
            "basa ne yazdim", "en basta ne yazdim",
        )):
            first = user_turns[0].get("message", "").strip()
            return f"İlk yazdığın mesaj şuydu: “{first}”" if first else "İlk mesajı bulamadım."
        if any(phrase in normalized for phrase in (
            "son yazdigim", "son mesajim", "az once ne yazdim", "az once yazdigim",
            "once ne yazdim", "ne yazdim",
        )):
            last = user_turns[-1].get("message", "").strip()
            return f"Son yazdığın mesaj şuydu: “{last}”" if last else "Son mesajı bulamadım."
        if any(phrase in normalized for phrase in ("hatirliyor musun", "hatirladin mi")):
            last = user_turns[-1].get("message", "").strip()
            return f"Evet, son konumuz şuydu: “{last}”" if last else None
        return None

    def _record_turn(self, raw: str, query: str, answer: str, intent: str) -> None:
        turn = {
            "message": str(raw or "").strip()[:500],
            "query": self.normalize(query)[:300],
            "answer": HarbiligText.clean_model(answer)[:1200],
            "intent": str(intent or "response"),
        }
        self._turns.append(turn)
        self._persist_recent_turns()

    def _restore_recent_turns(self, data: dict[str, Any] | None = None) -> None:
        try:
            source = data if isinstance(data, dict) else self.load_memory()
            recent = ((source.get("last") or {}).get("recentTurns") or [])
            if not isinstance(recent, list):
                return
            for item in recent[-6:]:
                if not isinstance(item, dict):
                    continue
                message = str(item.get("message") or "").strip()
                if not message or HarbiligText.contains_abusive_text(message):
                    continue
                self._turns.append({
                    "message": message[:500],
                    "query": self.normalize(item.get("query") or message)[:300],
                    "answer": HarbiligText.clean_model(item.get("answer") or "")[:1200],
                    "intent": str(item.get("intent") or "response"),
                })
        except Exception:
            pass

    def _persist_recent_turns(self) -> None:
        try:
            safe_turns = [
                turn for turn in self._turns
                if turn.get("message") and not HarbiligText.contains_abusive_text(turn.get("message"))
            ][-6:]
            data = self.load_memory()
            last = data.setdefault("last", {})
            last["recentTurns"] = safe_turns
            last["updatedAt"] = self._now()
            data["version"] = HARBILIG_VERSION
            data["engine"] = "netops_harbilig"
            data["updatedAt"] = self._now()
            self.save_memory(data)
        except Exception:
            pass

    def _internet_is_enabled(self) -> bool:
        try:
            return bool(self.internet_enabled() if callable(self.internet_enabled) else self.internet_enabled)
        except Exception:
            return True

    @staticmethod
    def normalize(value: Any) -> str:
        return HarbiligText.normalize(value)

    @staticmethod
    def _now() -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _runtime_project_dir(project: str | Path | None) -> Path:
        if getattr(sys, "frozen", False):
            appdata = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
            target = appdata / "NetoAsistan"
            target.mkdir(parents=True, exist_ok=True)
            return target
        return Path(project or Path(__file__).resolve().parent).resolve()


_ENGINE_CACHE: dict[str, NetOpsHarbiligEngine] = {}


def get_engine(
    project_dir: str | Path | None = None,
    command_detector: CommandDetector | None = None,
    internet_enabled: Callable[[], bool] | bool = True,
    max_sources: int = 3,
    internal_opener: Callable[[str, bool], Any] | None = None,
) -> NetOpsHarbiligEngine:
    base = NetOpsHarbiligEngine._runtime_project_dir(project_dir)
    key = str(base).casefold()
    engine = _ENGINE_CACHE.get(key)
    if engine is None:
        engine = NetOpsHarbiligEngine(
            project_dir=base,
            command_detector=command_detector,
            internet_enabled=internet_enabled,
            max_sources=max_sources,
            internal_opener=internal_opener,
        )
        _ENGINE_CACHE[key] = engine
    else:
        if command_detector is not None:
            engine.command_detector = command_detector
        if internal_opener is not None:
            engine.internal_opener = internal_opener
        engine.internet_enabled = internet_enabled
        engine.max_sources = max(1, min(3, int(max_sources or 3)))
    return engine


def ensure_files(project: str | Path = ".") -> dict[str, Any]:
    engine = get_engine(project_dir=project)
    data = engine.ensure_memory()
    word_core = engine.ensure_word_core()
    return {
        "ok": True,
        "engine": "netops_harbilig",
        "path": str(engine.memory_path),
        "items": len(data.get("items") or {}),
        "version": HARBILIG_VERSION,
        "word_core_path": str(engine.word_core_path),
        "word_core_version": str(word_core.get("version") or ""),
    }


def start_location_service(project: str | Path = ".") -> dict[str, Any]:
    return {"city": "", "region": "", "country": "", "timezone": "", "latitude": None, "longitude": None, "source": "netops_harbilig", "updatedAt": ""}


def answer(message: Any, **kwargs: Any) -> str:
    allowed = {"project_dir", "command_detector", "internet_enabled", "max_sources", "internal_opener"}
    engine = get_engine(**{key: value for key, value in kwargs.items() if key in allowed})
    return engine.answer(message).text


NetOpsOneEngine = NetOpsHarbiligEngine
NetOpsOneEngineV3 = NetOpsHarbiligEngine
NetOpsOneResult = HarbiligResult
NetOpsOneResultV3 = HarbiligResult
SearchItem = HarbiligSearchItem
NetOpsOneStructuredSearch = HarbiligSearchClient
NetOpsOneText = HarbiligText
NetOpsOneQueryNormalizer = HarbiligQueryNormalizer
VERSION = HARBILIG_VERSION
