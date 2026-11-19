# browser_engine.py
from __future__ import annotations

import html as _html
import multiprocessing
import os
import queue
import re
import sys
import threading
import time
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
import xml.etree.ElementTree as ET

import requests

from config import CHROME_USER_AGENT, LOGO_PATH

_BROWSER_PROCESS = None
_BROWSER_COMMAND_QUEUE = None
_BROWSER_RESPONSE_QUEUE = None
_BROWSER_LOCK = threading.Lock()
_LAST_LINKS: list[dict[str, str]] = []

SEARCH_ENGINE = "https://duckduckgo.com/?q={query}"
SEARCH_ENGINE_HTML = "https://html.duckduckgo.com/html/?q={query}&kl=tr-tr"
DEFAULT_BROWSER_URL = "https://duckduckgo.com/"
BING_SEARCH = "https://www.bing.com/search?q={query}&cc=tr&setlang=tr"
GOOGLE_SEARCH = "https://www.google.com/search?q={query}&hl=tr&gl=tr"
MAX_TEXT_CHARS = 5500
TOOL_TIMEOUT = 12.0


class _ReadableHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip = 0
        self.parts: list[str] = []
        self.links: list[dict[str, str]] = []
        self._current_href = ""
        self._current_text: list[str] = []
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        tag = str(tag or "").lower()
        if tag in {"script", "style", "noscript", "svg", "canvas"}:
            self._skip += 1
            return
        if tag == "title":
            self._in_title = True
        if tag == "a":
            attr = dict(attrs or [])
            self._current_href = str(attr.get("href") or "")
            self._current_text = []
        if tag in {"p", "br", "div", "section", "article", "h1", "h2", "h3", "li"} and self._skip == 0:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        tag = str(tag or "").lower()
        if tag in {"script", "style", "noscript", "svg", "canvas"} and self._skip:
            self._skip -= 1
            return
        if tag == "title":
            self._in_title = False
        if tag == "a" and self._current_href:
            text = _clean_text(" ".join(self._current_text))
            href = self._current_href.strip()
            if text and href.startswith(("http://", "https://")):
                self.links.append({"text": text[:160], "url": href})
            self._current_href = ""
            self._current_text = []

    def handle_data(self, data):
        if self._skip:
            return
        text = str(data or "")
        if self._in_title:
            self.title += text
        if self._current_href:
            self._current_text.append(text)
        self.parts.append(text)


def _clean_text(text: str) -> str:
    text = _html.unescape(str(text or ""))
    text = re.sub(r"[\t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    text = re.sub(r"[ ]{2,}", " ", text)
    return text.strip()


def _safe_headers() -> dict[str, str]:
    return {
        "User-Agent": CHROME_USER_AGENT or "Mozilla/5.0 NetOpsBrowser/1.0",
        "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.7",
    }


def _search_url(query: str) -> str:
    return SEARCH_ENGINE.format(query=quote_plus(str(query or "").strip()))


def _html_search_url(query: str) -> str:
    return SEARCH_ENGINE_HTML.format(query=quote_plus(str(query or "").strip()))


def _ddg_href_decode(href: str) -> str:
    href = _html.unescape(str(href or ""))
    try:
        parsed = urlparse(href)
        params = parse_qs(parsed.query)
        if params.get("uddg"):
            return unquote(params["uddg"][0])
    except Exception:
        pass
    return href


def _is_real_web_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        if parsed.scheme not in {"http", "https"} or not host:
            return False
        blocked = (
            "duckduckgo.", "google.", "bing.com", "javascript:", "localhost", "127.0.0.1",
            "youtube.com", "youtu.be", "tiktok.com", "instagram.com", "facebook.com", "x.com", "twitter.com",
            "reddit.com", "pinterest.", "wiktionary.org", "eksisozluk.com", "genius.com", "azlyrics.com",
            "lyrics.com", "musixmatch.com", "songlyrics.com", "nhl.com", "nba.com", "nfl.com", "espn.com",
        )
        return not any(x in host for x in blocked)
    except Exception:
        return False


def _extract_readable(html_text: str, source_url: str = "") -> dict[str, object]:
    parser = _ReadableHTMLParser()
    parser.feed(html_text or "")
    text = _clean_text(" ".join(parser.parts))
    text = re.sub(r"(?i)(cookie|çerez|privacy policy|gizlilik politikası).{0,140}", " ", text)
    text = _clean_text(text)
    title = _clean_text(parser.title)[:180]
    links = []
    seen = set()
    for link in parser.links:
        url = str(link.get("url") or "")
        if url in seen or not _is_real_web_url(url):
            continue
        seen.add(url)
        links.append(link)
        if len(links) >= 40:
            break
    return {"ok": True, "url": source_url, "title": title, "text": text[:MAX_TEXT_CHARS], "links": links}


def _fetch_page(url: str, timeout: float = 10.0) -> dict[str, object]:
    try:
        r = requests.get(url, headers=_safe_headers(), timeout=timeout, allow_redirects=True)
        ctype = str(r.headers.get("content-type") or "").lower()
        if r.status_code >= 400:
            return {"ok": False, "url": url, "error": f"HTTP {r.status_code}"}
        if "text/html" not in ctype and "application/xhtml" not in ctype and not r.text.lstrip().startswith("<"):
            return {"ok": False, "url": url, "error": "Sayfa okunabilir HTML degil"}
        return _extract_readable(r.text, str(r.url or url))
    except Exception as exc:
        return {"ok": False, "url": url, "error": str(exc)[:220]}


def _is_news_query(query: str) -> bool:
    q = str(query or "").lower()
    return any(k in q for k in ("haber", "gündem", "gundem", "son dakika", "bugün", "bugun", "nvidia haber", "gelişme", "gelisme"))


def _rss_news_results(query: str, max_results: int = 8) -> list[dict[str, str]]:
    feeds = [
        "https://www.trthaber.com/sondakika.rss",
        "https://www.ntv.com.tr/gundem.rss",
        "https://www.haberturk.com/rss",
    ]
    q = str(query or "").lower()
    query_words = [w for w in re.findall(r"[a-zA-ZçğıöşüÇĞİÖŞÜ0-9]{3,}", q) if w not in {"haber", "gündem", "gundem", "bugün", "bugun", "son", "dakika", "güncel", "guncel", "bak", "ara", "araştır", "arastir"}]
    items: list[dict[str, str]] = []
    seen = set()
    for feed_url in feeds:
        try:
            r = requests.get(feed_url, headers=_safe_headers(), timeout=8)
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.content)
            channel_items = list(root.findall(".//item"))
            if not channel_items:
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                channel_items = list(root.findall(".//atom:entry", ns))
            for item in channel_items:
                title = item.findtext("title") or item.findtext("{http://www.w3.org/2005/Atom}title") or ""
                desc = item.findtext("description") or item.findtext("summary") or item.findtext("{http://www.w3.org/2005/Atom}summary") or ""
                link = item.findtext("link") or ""
                atom_link = item.find("{http://www.w3.org/2005/Atom}link")
                if not link and atom_link is not None:
                    link = atom_link.attrib.get("href", "")
                pub = item.findtext("pubDate") or item.findtext("published") or item.findtext("{http://www.w3.org/2005/Atom}updated") or ""
                title = _clean_text(re.sub(r"<[^>]+>", " ", title))
                desc = _clean_text(re.sub(r"<[^>]+>", " ", desc))
                haystack = f"{title} {desc}".lower()
                if query_words and not any(w.lower() in haystack for w in query_words):
                    continue
                if not title or not _is_real_web_url(link) or link in seen:
                    continue
                seen.add(link)
                body = _clean_text(f"{desc} {pub}") or title
                items.append({"title": title, "body": body, "href": link})
                if len(items) >= max_results:
                    return items
        except Exception:
            continue
    return items

def _ddgs_package_results(query: str, max_results: int = 8) -> list[dict[str, str]]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            from duckduckgo_search import DDGS
        items = []
        q_lower = str(query or "").lower()
        use_news = any(k in q_lower for k in ("haber", "gündem", "gundem", "son dakika", "bugün", "bugun"))
        with DDGS() as ddgs:
            if use_news and hasattr(ddgs, "news"):
                raw_iter = ddgs.news(query, region="tr-tr", max_results=max_results)
            else:
                raw_iter = ddgs.text(query, region="tr-tr", max_results=max_results)
            for item in raw_iter:
                title = _clean_text(item.get("title", ""))
                url = str(item.get("url") or item.get("href") or "").strip()
                body = _clean_text(item.get("body") or item.get("excerpt") or item.get("source") or "")
                date = _clean_text(item.get("date", ""))
                source = _clean_text(item.get("source", ""))
                if date or source:
                    body = _clean_text(f"{body} {source} {date}")
                if title and _is_real_web_url(url):
                    items.append({"title": title, "body": body or title, "href": url})
                if len(items) >= max_results:
                    break
        return items
    except Exception:
        return []


def _google_results(query: str, max_results: int = 8) -> list[dict[str, str]]:
    try:
        r = requests.get(GOOGLE_SEARCH.format(query=quote_plus(query)), headers=_safe_headers(), timeout=10)
        if r.status_code != 200:
            return []
        html_text = r.text
        results: list[dict[str, str]] = []
        seen = set()
        # Google HTML sik degisir; bu parser bilincli olarak toleransli tutuldu.
        blocks = re.split(r'<div class="g"|<div jscontroller=', html_text)
        if len(blocks) <= 1:
            blocks = re.split(r'<a href="/url\?q=', html_text)
        for block in blocks:
            urls = re.findall(r'href="/url\?q=(https?://[^"&]+)', block)
            urls += re.findall(r'<a href="(https?://[^"#]+)"', block)
            if not urls:
                continue
            url = _html.unescape(unquote(urls[0]))
            if not _is_real_web_url(url) or url in seen:
                continue
            title_match = re.search(r'<h3[^>]*>(.*?)</h3>', block, re.S | re.I)
            if title_match:
                title = _clean_text(re.sub(r"<[^>]+>", " ", title_match.group(1)))
            else:
                title = _clean_text(re.sub(r"<[^>]+>", " ", block[:260]))
            if not title or len(title) < 3:
                continue
            text = _clean_text(re.sub(r"<[^>]+>", " ", block))
            text = re.sub(r"(?i)cached|benzer|translate this page|reklam", " ", text)
            snippet = text.replace(title, "", 1).strip()
            if len(snippet) < 25:
                snippet = title
            seen.add(url)
            results.append({"title": title[:180], "body": snippet[:650], "href": url})
            if len(results) >= max_results:
                break
        return results
    except Exception:
        return []


def _bing_href_decode(href: str) -> str:
    href = _html.unescape(str(href or ""))
    try:
        parsed = urlparse(href)
        params = parse_qs(parsed.query)
        raw = (params.get("u") or [""])[0]
        if raw:
            import base64
            if raw.startswith("a1"):
                raw = raw[2:]
            padding = "=" * (-len(raw) % 4)
            decoded = base64.urlsafe_b64decode((raw + padding).encode("ascii", "ignore")).decode("utf-8", "ignore")
            if decoded.startswith(("http://", "https://")):
                return decoded
    except Exception:
        pass
    return href

def _bing_results(query: str, max_results: int = 8) -> list[dict[str, str]]:
    try:
        r = requests.get(BING_SEARCH.format(query=quote_plus(query)), headers=_safe_headers(), timeout=10)
        if r.status_code != 200:
            return []
        html_text = r.text
        results: list[dict[str, str]] = []
        blocks = re.findall(r'<li[^>]*class="[^"]*b_algo[^"]*"[^>]*>(.*?)</li>', html_text, re.S | re.I)
        if not blocks:
            blocks = [html_text]
        seen = set()
        for block in blocks:
            for link_match in re.finditer(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', block, re.S | re.I):
                url = _bing_href_decode(link_match.group(1))
                title = _clean_text(re.sub(r"<[^>]+>", " ", link_match.group(2)))
                if not title or len(title) < 4 or not _is_real_web_url(url) or url in seen:
                    continue
                seen.add(url)
                after = block[link_match.end(): link_match.end() + 2000]
                snippet_match = re.search(r'<p[^>]*>(.*?)</p>', after, re.S | re.I)
                snippet = _clean_text(re.sub(r"<[^>]+>", " ", snippet_match.group(1))) if snippet_match else ""
                if not snippet:
                    snippet = title
                results.append({"title": title, "body": snippet, "href": url})
                if len(results) >= max_results:
                    return results
        return results
    except Exception:
        return []

def _ddg_results(query: str, max_results: int = 8) -> list[dict[str, str]]:
    try:
        r = requests.get(_html_search_url(query), headers=_safe_headers(), timeout=10)
        if r.status_code != 200:
            return []
        html_text = r.text
        results: list[dict[str, str]] = []
        pattern = re.compile(r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.S)
        for match in pattern.finditer(html_text):
            url = _ddg_href_decode(match.group(1).replace("&amp;", "&"))
            title = _clean_text(re.sub(r"<[^>]+>", " ", match.group(2)))
            tail = html_text[match.end(): match.end() + 1800]
            snippet_match = re.search(r'class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</', tail, re.S)
            snippet = _clean_text(re.sub(r"<[^>]+>", " ", snippet_match.group(1))) if snippet_match else ""
            if not title or not _is_real_web_url(url):
                continue
            results.append({"title": title, "body": snippet, "href": url})
            if len(results) >= max_results:
                break
        return results
    except Exception:
        return []


def _put_response(response_queue, req_id: str, payload: dict[str, object]) -> None:
    try:
        response_queue.put({"id": req_id, **payload})
    except Exception:
        pass


def browser_worker(url, logo_yolu, command_queue=None, response_queue=None):
    try:
        from PyQt6.QtCore import QTimer, QUrl
        from PyQt6.QtGui import QIcon
        from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget
        import asyncio
        from neto_anyspeech_tts import speak_text as anyspeech_speak_text

        voice_lock = threading.Lock()

        class TarayiciWidget(QWidget):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.tarayici_aktif = False
                self.web_view = None
                self.profil = None
                self._last_text = ""
                self._last_links = []
                self._last_title = ""
                self.main_layout = QVBoxLayout(self)
                self.main_layout.setContentsMargins(0, 0, 0, 0)
                self.status = QLabel("NetOps Browser hazir")
                self.status.setStyleSheet("background:#101014;color:#d7e3ff;padding:7px 10px;font-size:12px;")
                self.main_layout.addWidget(self.status)
                self.control_timer = QTimer(self)
                self.control_timer.timeout.connect(self._poll_commands)
                self.control_timer.start(180)

            def _set_status(self, text):
                try:
                    self.status.setText(str(text)[:180])
                except Exception:
                    pass

            def tarayiciyi_baslat(self, hedef_url):
                if self.tarayici_aktif:
                    if self.web_view:
                        self._set_status("Sayfa aciliyor...")
                        self.web_view.setUrl(QUrl(hedef_url))
                    return
                profil = QWebEngineProfile.defaultProfile()
                if profil is None:
                    raise RuntimeError("Qt WebEngine profili olusturulamadi.")
                self.profil = profil
                profil.setHttpUserAgent(CHROME_USER_AGENT)
                profil.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
                ayarlar = profil.settings()
                if ayarlar is None:
                    raise RuntimeError("Qt WebEngine ayarlari alinamadi.")
                ayarlar.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
                ayarlar.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
                ayarlar.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, False)
                sayfa = QWebEnginePage(profil, self)
                self.web_view = QWebEngineView(self)
                self.web_view.setPage(sayfa)
                self.main_layout.addWidget(self.web_view)
                self.web_view.loadStarted.connect(lambda: self._set_status("Web'de sayfa yukleniyor..."))
                self.web_view.loadFinished.connect(self._on_load_finished)
                self.web_view.setUrl(QUrl(hedef_url))
                self.tarayici_aktif = True
                self.izleme_timer = QTimer(self)
                self.izleme_timer.timeout.connect(self.sayfayi_oku_ve_yakala)
                self.izleme_timer.start(2500)

            def _on_load_finished(self, ok):
                self._set_status("Sayfa hazir" if ok else "Sayfa yuklenemedi")
                self._extract_page_state()

            def _extract_page_state(self, req_id=None, want_links=False):
                if not self.web_view or not self.web_view.page():
                    if req_id and response_queue:
                        _put_response(response_queue, req_id, {"ok": False, "error": "Browser hazir degil"})
                    return
                js = """
                (function() {
                    const clean = (s) => (s || '').replace(/\\s+/g, ' ').trim();
                    const links = Array.from(document.querySelectorAll('a[href]')).slice(0, 80).map(a => ({
                        text: clean(a.innerText).slice(0, 160),
                        url: a.href
                    })).filter(x => x.text && /^https?:/i.test(x.url));
                    return {
                        title: document.title || '',
                        url: location.href,
                        text: clean(document.body ? document.body.innerText : '').slice(0, 7000),
                        links: links
                    };
                })();
                """
                def done(data):
                    try:
                        data = data if isinstance(data, dict) else {}
                        self._last_text = str(data.get("text") or "")
                        self._last_title = str(data.get("title") or "")
                        self._last_links = list(data.get("links") or [])
                        if req_id and response_queue:
                            payload = {
                                "ok": True,
                                "url": str(data.get("url") or ""),
                                "title": self._last_title,
                                "text": self._last_text[:MAX_TEXT_CHARS],
                            }
                            if want_links:
                                payload["links"] = self._last_links[:40]
                            _put_response(response_queue, req_id, payload)
                    except Exception as exc:
                        if req_id and response_queue:
                            _put_response(response_queue, req_id, {"ok": False, "error": str(exc)[:220]})
                self.web_view.page().runJavaScript(js, done)

            def _poll_commands(self):
                if command_queue is None:
                    return
                for _ in range(8):
                    try:
                        cmd = command_queue.get_nowait()
                    except queue.Empty:
                        return
                    except Exception:
                        return
                    self._handle_command(cmd)

            def _handle_command(self, cmd):
                if not isinstance(cmd, dict):
                    return
                action = str(cmd.get("action") or "")
                req_id = str(cmd.get("id") or "")
                try:
                    if action in {"open_url", "web_open"}:
                        self.tarayiciyi_baslat(str(cmd.get("url") or DEFAULT_BROWSER_URL))
                        if req_id and response_queue:
                            _put_response(response_queue, req_id, {"ok": True})
                    elif action == "web_search":
                        query = str(cmd.get("query") or "")
                        self._set_status(f"Web'de araniyor: {query[:80]}")
                        self.tarayiciyi_baslat(_search_url(query))
                        if req_id and response_queue:
                            _put_response(response_queue, req_id, {"ok": True, "url": _search_url(query)})
                    elif action in {"read_page", "get_page_text"}:
                        self._extract_page_state(req_id=req_id, want_links=False)
                    elif action == "get_links":
                        self._extract_page_state(req_id=req_id, want_links=True)
                    elif action == "get_current_url":
                        current = self.web_view.url().toString() if self.web_view else ""
                        _put_response(response_queue, req_id, {"ok": True, "url": current})
                    elif action == "get_page_title":
                        _put_response(response_queue, req_id, {"ok": True, "title": self._last_title})
                    elif action == "go_back":
                        if self.web_view:
                            self.web_view.back()
                        _put_response(response_queue, req_id, {"ok": True})
                    elif action == "scroll_page":
                        amount = int(cmd.get("amount") or 700)
                        if self.web_view and self.web_view.page():
                            self.web_view.page().runJavaScript(f"window.scrollBy(0, {amount});")
                        _put_response(response_queue, req_id, {"ok": True})
                except Exception as exc:
                    if req_id and response_queue:
                        _put_response(response_queue, req_id, {"ok": False, "error": str(exc)[:220]})

            def sayfayi_oku_ve_yakala(self):
                if not self.web_view or not self.tarayici_aktif:
                    return
                js_kodu = """
                (function() {
                    var chatElementleri = document.querySelectorAll('.text-fragment, .chat-line__message, .ytp-caption-segment, h1');
                    var toplananMetin = "";
                    chatElementleri.forEach(function(el) { toplananMetin += el.innerText + " "; });
                    if(toplananMetin.trim().length === 0) {
                        return document.body.innerText.substring(0, 1000);
                    }
                    return toplananMetin;
                })();
                """
                sayfa = self.web_view.page()
                if sayfa is not None:
                    sayfa.runJavaScript(js_kodu, self.neto_reaksiyon_motoru)

            async def neto_konustur_asenkron(self, metin):
                try:
                    await asyncio.to_thread(anyspeech_speak_text, metin, logger=lambda msg: print(f"[BROWSER][TTS] {msg}", flush=True))
                except Exception as exc:
                    print(f"Tarayici seslendirme hatasi: {exc}", flush=True)

            def neto_seslendir(self, metin):
                def cal():
                    with voice_lock:
                        loop = asyncio.new_event_loop()
                        try:
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(self.neto_konustur_asenkron(metin))
                        finally:
                            loop.close()
                threading.Thread(target=cal, daemon=True).start()

            def neto_reaksiyon_motoru(self, gelen_metin):
                if not gelen_metin:
                    return
                metin = gelen_metin.lower()
                if "kirmizi balik" in metin or "kırmızı balık" in metin or "baskin" in metin or "baskın" in metin:
                    self.neto_seslendir("Tarayici gizlendi")
                    QTimer.singleShot(500, self.tarayiciyi_kapat)
                    return
                if "kapat" in metin:
                    if not hasattr(self, "son_panik") or time.time() - self.son_panik > 8:
                        self.son_panik = time.time()
                        self.neto_seslendir("tarayici gizlendi")
                elif "oha" in metin or "yok artik" in metin or "yok artık" in metin or "imkansiz" in metin or "imkansız" in metin:
                    if not hasattr(self, "son_sok") or time.time() - self.son_sok > 8:
                        self.son_sok = time.time()
                        self.neto_seslendir("Aha, mevzu var! Neler oluyor orada?")

            def tarayiciyi_kapat(self):
                if hasattr(self, "izleme_timer"):
                    self.izleme_timer.stop()
                if not self.tarayici_aktif or self.web_view is None:
                    return
                self.web_view.stop()
                self.web_view.setPage(None)
                self.main_layout.removeWidget(self.web_view)
                self.web_view.deleteLater()
                self.web_view = None
                if self.profil is not None:
                    self.profil.deleteLater()
                self.tarayici_aktif = False

        app = QApplication(sys.argv)
        win = QMainWindow()
        win.setWindowTitle("NetOps Browser")
        if os.path.exists(logo_yolu):
            win.setWindowIcon(QIcon(logo_yolu))
        win.resize(1150, 750)
        tarayici_bileseni = TarayiciWidget()
        win.setCentralWidget(tarayici_bileseni)
        tarayici_bileseni.tarayiciyi_baslat(url)
        win.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"Tarayici Hatasi: {e}", flush=True)


def _ensure_browser(url: str = DEFAULT_BROWSER_URL) -> bool:
    global _BROWSER_PROCESS, _BROWSER_COMMAND_QUEUE, _BROWSER_RESPONSE_QUEUE
    with _BROWSER_LOCK:
        if _BROWSER_PROCESS is not None and _BROWSER_PROCESS.is_alive():
            return True
        _BROWSER_COMMAND_QUEUE = multiprocessing.Queue()
        _BROWSER_RESPONSE_QUEUE = multiprocessing.Queue()
        _BROWSER_PROCESS = multiprocessing.Process(
            target=browser_worker,
            args=(url, LOGO_PATH, _BROWSER_COMMAND_QUEUE, _BROWSER_RESPONSE_QUEUE),
        )
        _BROWSER_PROCESS.daemon = False
        _BROWSER_PROCESS.start()
        time.sleep(0.4)
        return True


def browser_command(action: str, timeout: float = TOOL_TIMEOUT, **kwargs) -> dict[str, object]:
    try:
        _ensure_browser(str(kwargs.get("url") or DEFAULT_BROWSER_URL))
        req_id = f"{time.time_ns()}-{os.getpid()}"
        payload = {"id": req_id, "action": action, **kwargs}
        _BROWSER_COMMAND_QUEUE.put(payload)
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                response = _BROWSER_RESPONSE_QUEUE.get(timeout=0.25)
            except queue.Empty:
                continue
            if isinstance(response, dict) and response.get("id") == req_id:
                response.pop("id", None)
                return response
        return {"ok": False, "error": "Browser tool timeout"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:220]}


def neto_browser_ac(url=DEFAULT_BROWSER_URL):
    import __main__ as main_mod
    try:
        _ensure_browser(str(url or DEFAULT_BROWSER_URL))
        if _BROWSER_COMMAND_QUEUE is not None:
            _BROWSER_COMMAND_QUEUE.put({"action": "open_url", "url": str(url or DEFAULT_BROWSER_URL)})
    except Exception as e:
        if hasattr(main_mod, "animasyonlu_yazi"):
            main_mod.animasyonlu_yazi(f"Tarayici acilamadi: {e}")


def open_url(url: str) -> dict[str, object]:
    return browser_command("open_url", url=url)


def get_page_text() -> dict[str, object]:
    return browser_command("get_page_text")


def read_page() -> dict[str, object]:
    return get_page_text()


def get_links() -> dict[str, object]:
    return browser_command("get_links")


def go_back() -> dict[str, object]:
    return browser_command("go_back")


def scroll_page(amount: int = 700) -> dict[str, object]:
    return browser_command("scroll_page", amount=int(amount))


def get_current_url() -> dict[str, object]:
    return browser_command("get_current_url")


def get_page_title() -> dict[str, object]:
    return browser_command("get_page_title")


def open_link(link_or_index) -> dict[str, object]:
    global _LAST_LINKS
    if isinstance(link_or_index, int):
        if 0 <= link_or_index < len(_LAST_LINKS):
            return open_url(_LAST_LINKS[link_or_index].get("url", ""))
        return {"ok": False, "error": "Link index bulunamadi"}
    return open_url(str(link_or_index or ""))


def web_search(query: str, max_sources: int = 3, visible: bool = True, read_pages: bool | None = None) -> dict[str, object]:
    """API-free web research. Manual browser stays unchanged; visible=False keeps AI search in chat."""
    global _LAST_LINKS
    query = str(query or "").strip()
    if not query:
        return {"ok": False, "error": "Arama sorgusu bos"}

    if visible:
        neto_browser_ac(_search_url(query))
        browser_command("web_search", query=query, timeout=4.0)

    results = _rss_news_results(query, max_results=8) if _is_news_query(query) else []
    if not results:
        results = _ddg_results(query, max_results=8)
    if not results:
        results = _ddgs_package_results(query, max_results=8)
    if not results:
        results = _bing_results(query, max_results=8)
    if not results:
        results = _google_results(query, max_results=8)
    _LAST_LINKS = [{"text": r.get("title", ""), "url": r.get("href", "")} for r in results]

    if read_pages is None:
        read_pages = bool(visible)

    if not read_pages:
        sources = []
        for result in results[:max_sources]:
            title = str(result.get("title") or "Kaynak")[:180]
            url = str(result.get("href") or "")
            body = _clean_text(str(result.get("body") or title))[:900]
            if body:
                sources.append({"title": title, "url": url, "text": body, "snippet": body})
        if not sources:
            return {"ok": False, "error": "Arama sonucu okunamadi", "query": query, "search_url": _search_url(query)}
        blocks = []
        for index, src in enumerate(sources, start=1):
            blocks.append(f"{index}) {src.get('title')}\n{src.get('text')}\nKaynak: {src.get('url')}")
        return {"ok": True, "query": query, "search_url": _search_url(query), "sources": sources, "text": "\n\n".join(blocks), "links": _LAST_LINKS}

    sources = []
    for result in results:
        url = result.get("href", "")
        if not _is_real_web_url(url):
            continue
        page = _fetch_page(url, timeout=5.0)
        text = str(page.get("text") or "").strip()
        snippet = str(result.get("body") or "").strip()
        if len(text) < 180 and snippet:
            text = snippet
        if len(text) < 80:
            continue
        sources.append({
            "title": str(page.get("title") or result.get("title") or "Kaynak")[:180],
            "url": str(page.get("url") or url),
            "text": text[:1800],
            "snippet": snippet[:500],
        })
        if len(sources) >= max_sources:
            break

    if not sources:
        sources = [
            {
                "title": r.get("title", "Kaynak"),
                "url": r.get("href", ""),
                "text": r.get("body", ""),
                "snippet": r.get("body", ""),
            }
            for r in results[:max_sources]
            if r.get("body")
        ]

    if not sources:
        return {"ok": False, "error": "Arama sonucu okunamadi", "query": query, "search_url": _search_url(query)}

    blocks = []
    for index, src in enumerate(sources, start=1):
        body = _clean_text(src.get("text", ""))[:900]
        blocks.append(f"{index}) {src.get('title')}\n{body}\nKaynak: {src.get('url')}")

    return {
        "ok": True,
        "query": query,
        "search_url": _search_url(query),
        "sources": sources,
        "text": "\n\n".join(blocks),
        "links": _LAST_LINKS,
    }







