# NETOPS SOHBET MOTORU V3
# Genel internet arama router'i: LLM olmadan local cevap, context ve web fallback.

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import neto_sohbet_v2

VERSION = "3.1"
STATE_FILE = "neto_sohbet_v3_state.json"

_WEB_COMMANDS = (
    "internette ara", "webde ara", "webden bak", "internetten bak", "guncel bak",
    "şimdi bak", "simdi bak", "tekrar bak", "yeniden bak", "kontrol et", "dogrula",
    "doğrula", "araştır", "arastir", "ara", "bak",
)
_REPEAT_COMMANDS = {"tekrar bak", "yeniden bak", "bir daha bak", "guncel bak", "güncel bak", "kontrol et", "dogrula", "doğrula", "yenile"}
_LOCAL_ONLY = {
    "tamam", "tm", "ok", "olur", "evet", "hayir", "hayır", "iptal", "vazgec", "vazgeç",
    "sa", "slm", "selam", "merhaba", "naber", "tesekkur", "teşekkür", "sag ol", "sağ ol",
}
_COMMAND_HINTS = (
    "aç", "ac", "başlat", "baslat", "çalıştır", "calistir", "kapat", "ses", "not al",
    "ekran görüntüsü", "ss al", "kendini onar", "doktor", "linux", ".agent", "n.ext",
)
_WEB_HINTS = (
    "ne zaman", "kaç", "kac", "kimdir", "nedir", "ne demek", "nerede", "neden", "nasıl", "nasil",
    "maç", "mac", "puan durumu", "fikstür", "fikstur", "sonraki", "sıradaki", "siradaki",
    "fiyat", "kaç dolar", "kac dolar", "kaç tl", "kac tl", "kur", "dolar", "euro", "altın", "altin",
    "bitcoin", "btc", "ethereum", "eth", "borsa", "hisse", "çöktü", "coktu", "çöktü mü", "coktu mu",
    "son sürüm", "son surum", "güncelleme", "guncelleme", "latest", "version", "sürüm", "surum",
    "haber", "gündem", "gundem", "son dakika", "bugun ne oldu", "bugün ne oldu", "ne oldu", "son deprem", "deprem", "hava durumu", "hava nasıl", "kar yağacak", "kar yagacak", "radar", "fırtına", "firtina", "hava kalitesi", "aqi",
    "nüfus", "nufus", "çıktı mı", "cikti mi", "yeni", "özellik", "ozellik", "karşılaştır", "karsilastir",
)
_STOPWORDS = {"ve", "ile", "mi", "mı", "mu", "mü", "ne", "bir", "bu", "şu", "su", "o", "da", "de"}

_REPLACEMENTS = [
    (r"\bbesiktas(?:in|i|li|lilar)?\b", "Beşiktaş"),
    (r"\bfener bahce(?:nin|nın|li|liler)?\b", "Fenerbahçe"),
    (r"\bfenerbahce(?:nin|nın|li|liler)?\b", "Fenerbahçe"),
    (r"\bgalatasaray\b", "Galatasaray"),
    (r"\btrabzonspor\b", "Trabzonspor"),
    (r"\bmac(?:i|lar|lari)?\b", "maç"),
    (r"\bpuan durumu\b", "puan durumu"),
    (r"\bsuan\b", "şu an"),
    (r"\bşuan\b", "şu an"),
    (r"\bcoktu\b", "çöktü"),
    (r"\bcikti\b", "çıktı"),
    (r"\bsurum\b", "sürüm"),
]


def _base(project: str | Path | None = None) -> Path:
    return Path(project).resolve() if project else Path(__file__).resolve().parent


def _state_path(project: str | Path | None = None) -> Path:
    return _base(project) / STATE_FILE


def load_state(project: str | Path | None = None) -> dict[str, Any]:
    path = _state_path(project)
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_state(state: dict[str, Any], project: str | Path | None = None) -> None:
    path = _state_path(project)
    safe = dict(state or {})
    safe["updatedAt"] = time.strftime("%Y-%m-%d %H:%M:%S")
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ensure_files(project: str | Path = ".") -> dict[str, Any]:
    fixes: list[str] = []
    issues: list[str] = []
    try:
        neto_sohbet_v2.ensure_files(project)
    except Exception as exc:
        issues.append(f"V2 offline dosya kontrolu: {exc}")
    path = _state_path(project)
    if not path.exists():
        save_state({"version": VERSION, "lastUserMessage": "", "lastSearchQuery": "", "lastSearchTopic": "", "lastIntent": ""}, project)
        fixes.append(f"Olusturuldu: {STATE_FILE}")
    else:
        try:
            data = load_state(project)
            if not isinstance(data, dict):
                raise ValueError("state kok nesne degil")
        except Exception as exc:
            issues.append(str(exc))
            save_state({"version": VERSION}, project)
            fixes.append(f"Sifirlandi: {STATE_FILE}")
    return {"ok": not issues, "fixes": fixes, "issues": issues, "path": str(path)}


def _clean(text: Any) -> str:
    return str(text or "").strip()


def _norm(text: Any) -> str:
    return neto_sohbet_v2.temizle(text)


def _strip_web_prefix(message: str) -> str:
    m = message.strip()
    lower = _norm(m)
    for cmd in sorted(_WEB_COMMANDS, key=len, reverse=True):
        c = _norm(cmd)
        if lower == c:
            return ""
        if lower.startswith(c + " "):
            return m[len(cmd):].lstrip(" :,-")
        if lower.startswith(c + ":"):
            return m[len(cmd):].lstrip(" :,-")
    for prefix in ("internette araştır:", "internette arastir:", "webde ara:", "ara:"):
        if lower.startswith(_norm(prefix)):
            return m.split(":", 1)[1].strip() if ":" in m else ""
    return m


def normalize_query(message: str, state: dict[str, Any] | None = None) -> str:
    raw_message = _clean(message)
    query = _strip_web_prefix(raw_message)
    norm_message = _norm(raw_message)
    norm_query = _norm(query)
    explicit_web = norm_query != norm_message or any(
        norm_message == _norm(cmd) or norm_message.startswith(_norm(cmd) + " ") or norm_message.startswith(_norm(cmd) + ":")
        for cmd in _WEB_COMMANDS
    )
    # Arama sorgusunda yazim hatasini azaltmak icin aksanlari once normalize ediyoruz;
    # kullanicinin orijinal mesajina dokunmuyoruz, sadece query iyilesiyor.
    query = norm_query
    state = state or {}

    if norm_query in {_norm(x) for x in _REPEAT_COMMANDS}:
        return str(state.get("lastSearchQuery") or "").strip()

    # Kisa takip sorularinda onceki arama konusunu kullan.
    words = [w for w in re.findall(r"[\wçğıöşüÇĞİÖŞÜ]+", query, re.UNICODE) if _norm(w) not in _STOPWORDS]
    last_topic = str(state.get("lastSearchTopic") or "")
    last_query_norm = _norm(state.get("lastSearchQuery") or "")
    current_has_web_hint = any(h in norm_query for h in _WEB_HINTS)
    if (not explicit_web) and (not current_has_web_hint) and 1 <= len(words) <= 3 and state.get("lastIntent") == "web_search":
        topic = " ".join(words)
        if any(x in last_query_norm or x in _norm(last_topic) for x in ("mac", "fikstur", "sonraki")):
            query = f"{topic} sonraki maç ne zaman"
        elif any(x in last_query_norm for x in ("fiyat", "dolar", "tl", "kur", "ne kadar")):
            query = f"{topic} güncel fiyat"
        elif any(x in last_query_norm for x in ("surum", "guncelleme", "latest", "version")):
            query = f"{topic} son sürüm"
        elif last_topic:
            query = f"{topic} {last_topic}"

    for pattern, replacement in _REPLACEMENTS:
        query = re.sub(pattern, replacement, query, flags=re.IGNORECASE)

    qn = _norm(query)
    if "mac" in qn and "ne zaman" in qn and "sonraki" not in qn and "siradaki" not in qn:
        query += " sonraki maç"
    if "hava" in qn and "durumu" not in qn:
        query += " hava durumu"

    return re.sub(r"\s+", " ", query).strip()


def _looks_local_command(message: str) -> bool:
    m = _norm(message)
    if not m:
        return True
    if m in _LOCAL_ONLY:
        return True
    return any(h in m for h in _COMMAND_HINTS) and not any(w in m for w in _WEB_HINTS)


def should_search(message: str, *, fallback_unknown: bool = True, state: dict[str, Any] | None = None) -> bool:
    m = _norm(message)
    if not m:
        return False
    if m in {_norm(x) for x in _REPEAT_COMMANDS}:
        return bool((state or {}).get("lastSearchQuery"))
    if any(m == _norm(cmd) or m.startswith(_norm(cmd) + " ") or m.startswith(_norm(cmd) + ":") for cmd in _WEB_COMMANDS):
        return True
    if neto_sohbet_v2.should_stay_offline(message) and not any(h in m for h in _WEB_HINTS):
        return False
    if _looks_local_command(message):
        return False
    if any(h in m for h in _WEB_HINTS):
        return True
    if "?" in str(message):
        return True
    return fallback_unknown and len(m) >= 4


def _source_name(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower().replace("www.", "")
        return host or "web"
    except Exception:
        return "web"




def _fix_turkish_mojibake(text: Any) -> str:
    value = str(text or "")
    table = {
        "Ý": "İ", "ý": "ı", "Þ": "Ş", "þ": "ş", "Ð": "Ğ", "ð": "ğ",
        "Ã‡": "Ç", "Ã§": "ç", "Ã–": "Ö", "Ã¶": "ö", "Ãœ": "Ü", "Ã¼": "ü",
    }
    for bad, good in table.items():
        value = value.replace(bad, good)
    return value

def _extract_city_for_weather(query: str) -> str:
    q = _norm(query)
    city = q
    for token in ("hava durumu", "hava nasil", "hava nasıl", "hava", "bugun", "bugün", "yarin", "yarın"):
        city = city.replace(_norm(token), " ")
    city = re.sub(r"\s+", " ", city).strip(" ,.-")
    return city.title() if city else "Istanbul"



def _direct_public_apis_answer(query: str) -> dict[str, Any] | None:
    try:
        import neto_public_apis
        response = neto_public_apis.format_query_answer(query)
        if not response:
            return None
        return {
            "response": response,
            "sources": [{
                "title": "public-apis/public-apis",
                "url": "https://github.com/public-apis/public-apis",
                "text": response,
                "snippet": response[:600],
            }],
        }
    except Exception:
        return None

def _direct_crypto_answer(query: str) -> dict[str, Any] | None:
    q = _norm(query)
    coins: list[tuple[str, str]] = []
    if "bitcoin" in q or "btc" in q:
        coins.append(("bitcoin", "Bitcoin"))
    if "ethereum" in q or "eth" in q:
        coins.append(("ethereum", "Ethereum"))
    if not coins:
        return None
    try:
        import requests
        ids = ",".join(coin_id for coin_id, _ in coins)
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd,try&include_24hr_change=true"
        r = requests.get(url, timeout=8, headers={"User-Agent": "NetOps/3.1"})
        if r.status_code != 200:
            return None
        data = r.json()
        lines = ["Güncel kripto fiyatı:"]
        sources = []
        for coin_id, label in coins:
            item = data.get(coin_id) or {}
            usd = item.get("usd")
            tl = item.get("try")
            change = item.get("usd_24h_change")
            if usd is None:
                continue
            piece = f"{label}: yaklaşık ${usd:,}"
            if tl is not None:
                piece += f" / {tl:,.0f} TL"
            if isinstance(change, (int, float)):
                piece += f" (24s: %{change:.2f})"
            lines.append(piece)
            sources.append({"title": f"CoinGecko {label}", "url": "https://www.coingecko.com/", "text": piece, "snippet": piece})
        if len(lines) == 1:
            return None
        lines.append("Kaynak: CoinGecko. Fiyatlar anlık değişebilir.")
        return {"response": "\n".join(lines), "sources": sources}
    except Exception:
        return None


def _direct_weather_answer(query: str) -> dict[str, Any] | None:
    try:
        import neto_weather
        if not neto_weather.is_weather_query(query):
            return None
        response = neto_weather.weather_answer(query)
        if not response:
            return None
        text = str(response)
        return {
            "response": text,
            "sources": [
                {
                    "title": "NetOps Weather Engine / Open-Meteo",
                    "url": "https://open-meteo.com/",
                    "text": text,
                    "snippet": text,
                }
            ],
        }
    except Exception:
        return None


def _direct_earthquake_answer(query: str) -> dict[str, Any] | None:
    q = _norm(query)
    if "deprem" not in q:
        return None
    try:
        import requests
        url = "http://www.koeri.boun.edu.tr/scripts/lst0.asp"
        r = requests.get(url, timeout=8, headers={"User-Agent": "NetOps/3.1"})
        if r.status_code != 200:
            return None
        lines = [line.strip() for line in r.text.splitlines() if re.match(r"^\d{4}\.\d{2}\.\d{2}", line.strip())]
        if not lines:
            return None
        first = re.split(r"\s+", lines[0], maxsplit=8)
        if len(first) < 9:
            return None
        date, hour, _lat, _lon, depth, md, ml, mw, place = first
        mag = mw if mw != "-.-" else ml if ml != "-.-" else md
        place = _fix_turkish_mojibake(place)
        response = f"Son deprem: {place} | Tarih: {date} {hour} | Büyüklük: {mag} | Derinlik: {depth} km. Kaynak: Kandilli Rasathanesi."
        return {"response": response, "sources": [{"title": "Kandilli son depremler", "url": url, "text": response, "snippet": response}]}
    except Exception:
        return None


def _direct_outage_answer(query: str) -> dict[str, Any] | None:
    q = _norm(query)
    if "discord" not in q or not any(x in q for x in ("coktu", "çöktü", "durum", "status")):
        return None
    try:
        import requests
        url = "https://discordstatus.com/api/v2/status.json"
        r = requests.get(url, timeout=8, headers={"User-Agent": "NetOps/3.1"})
        if r.status_code != 200:
            return None
        data = r.json()
        indicator = (data.get("status") or {}).get("indicator") or "unknown"
        desc = (data.get("status") or {}).get("description") or "durum okunamadı"
        human = "normal görünüyor" if indicator == "none" else f"sorun olabilir: {desc}"
        response = f"Discord durumu: {human}. Kaynak: Discord Status."
        return {"response": response, "sources": [{"title": "Discord Status", "url": "https://discordstatus.com/", "text": response, "snippet": response}]}
    except Exception:
        return None


def _direct_answer(query: str) -> dict[str, Any] | None:
    for resolver in (_direct_public_apis_answer, _direct_crypto_answer, _direct_weather_answer, _direct_earthquake_answer, _direct_outage_answer):
        answer = resolver(query)
        if answer:
            return answer
    return None

def _format_search_response(query: str, result: dict[str, Any]) -> str:
    sources = result.get("sources") or []
    if not sources:
        text = str(result.get("text") or "").strip()
        if text:
            return f"Web'de '{query}' için bulduklarım:\n\n{text}"
        return "Web araması sonuç verdi ama okunabilir özet çıkaramadım."

    lines = [f"Web'de '{query}' için bulduklarım:"]
    for index, src in enumerate(sources[:3], start=1):
        title = str(src.get("title") or "Kaynak").strip()
        snippet = str(src.get("snippet") or src.get("text") or "").strip()
        url = str(src.get("url") or "").strip()
        snippet = re.sub(r"\s+", " ", snippet)[:320]
        source = _source_name(url)
        lines.append(f"{index}. {title}")
        if snippet:
            lines.append(f"   {snippet}")
        if url:
            lines.append(f"   Kaynak: {source} - {url}")
    lines.append("Kesin bilgi gibi uydurmadım; kaynak sonuçlarını özetledim.")
    return "\n".join(lines)


def search_web(message: str, *, project: str | Path | None = None, max_sources: int = 3) -> dict[str, Any]:
    ensure_files(_base(project))
    state = load_state(project)
    query = normalize_query(message, state)
    if not query:
        last = state.get("lastSearchQuery")
        if not last:
            return {"ok": False, "error": "Aranacak sorgu yok. Önce bir konu yaz."}
        query = str(last)
    direct = _direct_answer(query)
    if direct:
        response = str(direct.get("response") or "").strip()
        state.update({
            "version": VERSION,
            "lastUserMessage": message,
            "lastSearchQuery": query,
            "lastSearchTopic": _topic_from_query(query),
            "lastSearchResults": direct.get("sources") or [],
            "lastIntent": "web_search",
            "lastError": "",
        })
        save_state(state, project)
        return {"ok": True, "query": query, "response": response, "raw": {"ok": True, "sources": direct.get("sources") or [], "direct": True}}

    try:
        import browser_engine
        result = browser_engine.web_search(query, max_sources=max_sources, visible=False, read_pages=False)
    except Exception as exc:
        return {"ok": False, "query": query, "error": f"Web araması başlatılamadı: {exc}"}

    if not isinstance(result, dict) or not result.get("ok"):
        error = str((result or {}).get("error") if isinstance(result, dict) else "Bilinmeyen hata")
        state.update({"lastUserMessage": message, "lastSearchQuery": query, "lastSearchTopic": _topic_from_query(query), "lastIntent": "web_search_failed", "lastError": error})
        save_state(state, project)
        return {"ok": False, "query": query, "error": error}

    response = _format_search_response(query, result)
    state.update({
        "version": VERSION,
        "lastUserMessage": message,
        "lastSearchQuery": query,
        "lastSearchTopic": _topic_from_query(query),
        "lastSearchResults": result.get("sources") or [],
        "lastIntent": "web_search",
        "lastError": "",
    })
    save_state(state, project)
    return {"ok": True, "query": query, "response": response, "raw": result}


def _topic_from_query(query: str) -> str:
    q = _norm(query)
    if any(x in q for x in ("mac", "fikstur", "puan durumu")):
        return "sonraki maç"
    if any(x in q for x in ("fiyat", "dolar", "tl", "kur", "ne kadar")):
        return "güncel fiyat"
    if any(x in q for x in ("surum", "guncelleme", "latest", "version")):
        return "son sürüm"
    if any(x in q for x in ("hava", "weather")):
        return "hava durumu"
    return " ".join(re.findall(r"[\wçğıöşüÇĞİÖŞÜ]+", query, re.UNICODE)[:5])


def route_and_answer(message: str, *, agent_modu: bool = False, project: str | Path | None = None, fallback_unknown: bool = True) -> str | None:
    """Eski çağrılar için uyumluluk köprüsü; bağımsız web dökümü üretmez."""
    try:
        from netops_one_engine import get_engine
        result = get_engine(project_dir=project, internet_enabled=True).answer(
            message, agent_mode=agent_modu
        )
        if result.ok or result.intent in {"quick_chat", "memory", "correction"}:
            return str(result.text or "").strip() or None
        return None if not fallback_unknown else str(result.text or "").strip() or None
    except Exception:
        return None







