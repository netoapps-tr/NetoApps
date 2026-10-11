from __future__ import annotations

import json
import os
import random
import re
import subprocess
import webbrowser
from pathlib import Path
from typing import Any

FEATURE_FILE = Path(__file__).with_name("netops_ozellikler.json")

DEFAULT_DATA: dict[str, Any] = {
    "version": 1,
    "assistant_name": "NetOps",
    "mode": "normal",
    "startup_message": "Hazirim.",
    "replies": {},
    "web_commands": {},
    "app_commands": {},
}

SAFE_APPS = {
    "not defteri": "notepad.exe",
    "notepad": "notepad.exe",
    "hesap makinesi": "calc.exe",
    "calculator": "calc.exe",
    "paint": "mspaint.exe",
    "wordpad": "write.exe",
    "dosya gezgini": "explorer.exe",
    "explorer": "explorer.exe",
}

MODE_PREFIX = {
    "normal": "",
    "sakaci": "",
    "ciddi": "Kisa cevap: ",
    "sessiz": "",
    "korumaci": "Kontrol ettim: ",
}


def _norm(text: str) -> str:
    return " ".join(str(text or "").casefold().strip().split())


def _load() -> dict[str, Any]:
    if not FEATURE_FILE.exists():
        _save(dict(DEFAULT_DATA))
    try:
        data = json.loads(FEATURE_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    merged = dict(DEFAULT_DATA)
    merged.update(data)
    for key in ("replies", "web_commands", "app_commands"):
        if not isinstance(merged.get(key), dict):
            merged[key] = {}
    return merged


def _save(data: dict[str, Any]) -> None:
    FEATURE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _valid_url(url: str) -> bool:
    value = str(url or "").strip()
    return value.startswith("https://") or value.startswith("http://")


def _split_teach(text: str) -> tuple[str, str] | None:
    raw = str(text or "").strip()
    patterns = [
        r"^(.+?)\s+deyince\s+(.+?)\s+(?:de|desin|soyle|söyle)$",
        r"^(.+?)\s+yazinca\s+(.+?)\s+(?:de|desin|soyle|söyle)$",
        r"^(.+?)\s+yazınca\s+(.+?)\s+(?:de|desin|soyle|söyle)$",
        r"^komut\s+ekle\s*[:=]\s*(.+?)\s*(?:=>|->|=)\s*(.+)$",
        r"^cevap\s+ekle\s*[:=]\s*(.+?)\s*(?:=>|->|=)\s*(.+)$",
    ]
    for pattern in patterns:
        match = re.match(pattern, raw, flags=re.IGNORECASE)
        if match:
            trigger = _norm(match.group(1))
            reply = str(match.group(2)).strip()
            if trigger and reply:
                return trigger, reply
    return None


def _add_reply(text: str) -> str | None:
    pair = _split_teach(text)
    if not pair:
        return None
    trigger, reply = pair
    data = _load()
    replies = data.setdefault("replies", {})
    current = replies.get(trigger)
    if isinstance(current, list):
        if reply not in current:
            current.append(reply)
    elif isinstance(current, str) and current:
        replies[trigger] = [current, reply] if current != reply else [current]
    else:
        replies[trigger] = [reply]
    _save(data)
    return f"Ozellik eklendi: '{trigger}' deyince cevap verecegim."


def _add_web(text: str) -> str | None:
    raw = str(text or "").strip()
    match = re.match(r"^(?:web|site)\s+komutu\s+ekle\s*[:=]\s*(.+?)\s*(?:=>|->|=)\s*(https?://\S+)$", raw, re.IGNORECASE)
    if not match:
        return None
    trigger = _norm(match.group(1))
    url = str(match.group(2)).strip()
    if not _valid_url(url):
        return "Web komutu icin adres http:// veya https:// ile baslamali."
    data = _load()
    data.setdefault("web_commands", {})[trigger] = url
    _save(data)
    return f"Web ozelligi eklendi: '{trigger}' deyince acacagim."


def _add_app(text: str) -> str | None:
    raw = _norm(text)
    match = re.match(r"^(?:program|uygulama) komutu ekle[:= ]+(.+?)\s*(?:=>|->|=)\s*(.+)$", raw, re.IGNORECASE)
    if not match:
        return None
    trigger = _norm(match.group(1))
    app_name = _norm(match.group(2))
    exe = SAFE_APPS.get(app_name)
    if not exe:
        allowed = ", ".join(sorted(SAFE_APPS))
        return "Guvenlik icin sadece hazir listedeki programlari ekleyebilirim: " + allowed
    data = _load()
    data.setdefault("app_commands", {})[trigger] = exe
    _save(data)
    return f"Program ozelligi eklendi: '{trigger}' deyince {app_name} acilacak."


def _set_mode(text: str) -> str | None:
    raw = _norm(text)
    match = re.match(r"^(?:mod|modu)\s+(normal|sakaci|şakacı|ciddi|sessiz|korumaci|korumacı)\s+(?:yap|olsun|sec|seç)$", raw)
    if not match:
        return None
    mode = match.group(1).replace("ş", "s").replace("ı", "i")
    data = _load()
    data["mode"] = mode
    _save(data)
    return f"Mod degisti: {mode}."


def _set_startup(text: str) -> str | None:
    raw = str(text or "").strip()
    match = re.match(r"^(?:baslangic|başlangıç)\s+mesaji\s*[:=]\s*(.+)$", raw, re.IGNORECASE)
    if not match:
        return None
    msg = match.group(1).strip()
    data = _load()
    data["startup_message"] = msg
    _save(data)
    return "Baslangic mesaji kaydedildi."


def _delete_feature(text: str) -> str | None:
    raw = _norm(text)
    match = re.match(r"^(?:ozellik|özellik|komut)\s+sil\s*[:=]?\s*(.+)$", raw)
    if not match:
        return None
    trigger = _norm(match.group(1))
    data = _load()
    removed = False
    for bucket in ("replies", "web_commands", "app_commands"):
        if trigger in data.get(bucket, {}):
            data[bucket].pop(trigger, None)
            removed = True
    if removed:
        _save(data)
        return f"Ozellik silindi: {trigger}"
    return "Bu isimde ozellik bulamadim."


def _list_features() -> str | None:
    data = _load()
    lines = ["Ogrenen ozellikler:"]
    for title, key in (("Cevap", "replies"), ("Web", "web_commands"), ("Program", "app_commands")):
        items = data.get(key, {})
        if items:
            lines.append(f"{title}: " + ", ".join(sorted(items.keys())[:12]))
    if len(lines) == 1:
        lines.append("Henuz eklenmis ozellik yok.")
    lines.append("Ornek: selam deyince merhaba kral de")
    return "\n".join(lines)


def _answer_from_data(text: str) -> str | None:
    data = _load()
    raw = _norm(text)
    mode = str(data.get("mode") or "normal")
    prefix = MODE_PREFIX.get(mode, "")

    for trigger, replies in data.get("replies", {}).items():
        if _norm(trigger) in raw:
            if isinstance(replies, list):
                reply = random.choice([str(x) for x in replies if str(x).strip()] or [""])
            else:
                reply = str(replies or "")
            return prefix + reply if reply else None

    for trigger, url in data.get("web_commands", {}).items():
        if _norm(trigger) in raw:
            webbrowser.open(str(url))
            return prefix + f"Actim: {trigger}"

    for trigger, exe in data.get("app_commands", {}).items():
        if _norm(trigger) in raw:
            subprocess.Popen([str(exe)], shell=False)
            return prefix + f"Actim: {trigger}"

    return None


def handle(text: str) -> str | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    low = _norm(raw)

    if low in {"ozellikleri listele", "özellikleri listele", "ogrendiklerini listele", "öğrendiklerini listele"}:
        return _list_features()

    for fn in (_delete_feature, _set_mode, _set_startup, _add_web, _add_app, _add_reply):
        result = fn(raw)
        if result:
            return result

    return _answer_from_data(raw)


def startup_message() -> str:
    data = _load()
    return str(data.get("startup_message") or "Hazirim.")
