# NETOPS SOHBET V2
# Basit sohbetleri, yerel komut niyetlerini ve offline cevaplari hizli cozer.

from __future__ import annotations

import ast
import datetime as _dt
import json
import operator
import random
import re
from pathlib import Path
from typing import Any

_VERSION = "2.0"

_DEFAULT_OFFLINE = {
    "version": 1,
    "replies": {
        "minecraft nedir": "Minecraft, bloklarla inşa yapabildiğin ve hayatta kalmaya çalıştığın sandbox oyunudur.",
        "netops nedir": "NetOps, bu bilgisayarda çalışan kişisel asistan ve araç merkezidir.",
        "sen kimsin": "Ben NetOps, bu bilgisayardaki kişisel asistanınım.",
        "seni kim yaptı": "Beni bu proje içinde beraber geliştirdiniz; ben NetOps çekirdeğiyle çalışıyorum."
    },
    "tips": [
        "İstersen 'kendini onar' yazarak yerel onarım başlatabilirsin.",
        "İstersen 'internet kapat' yazarak cevapları daha offline tutabilirsin.",
        "Program açma komutlarında net isim yazarsan daha hızlı davranırım."
    ]
}

_MONTHS_TR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
_DAYS_TR = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

_SAFE_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_SAFE_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def version() -> str:
    return _VERSION


def temizle(metin: Any) -> str:
    text = str(metin or "").casefold().strip()
    ceviri = str.maketrans({"ı": "i", "İ": "i", "ğ": "g", "ü": "u", "ş": "s", "ö": "o", "ç": "c"})
    text = text.translate(ceviri)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" \t\r\n.!?")


def ensure_files(project: str | Path = ".") -> dict[str, Any]:
    base = Path(project).resolve()
    path = base / "neto_offline_bilgi.json"
    fixes: list[str] = []
    issues: list[str] = []
    if not path.exists():
        path.write_text(json.dumps(_DEFAULT_OFFLINE, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        fixes.append("Olusturuldu: neto_offline_bilgi.json")
    else:
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(data, dict):
                raise ValueError("kok nesne degil")
            changed = False
            for key, value in _DEFAULT_OFFLINE.items():
                if key not in data:
                    data[key] = value
                    changed = True
            if not isinstance(data.get("replies"), dict):
                data["replies"] = dict(_DEFAULT_OFFLINE["replies"])
                changed = True
            if changed:
                path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                fixes.append("Tamamlandi: neto_offline_bilgi.json")
        except Exception as exc:
            backup = path.with_name(path.name + ".bozuk.bak")
            try:
                path.replace(backup)
            except Exception:
                pass
            path.write_text(json.dumps(_DEFAULT_OFFLINE, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            fixes.append("Bozuk offline bilgi dosyasi sifirlandi")
            issues.append(str(exc))
    return {"ok": not issues, "fixes": fixes, "issues": issues, "path": str(path)}


def _load_replies(project: str | Path | None = None) -> dict[str, str]:
    base = Path(project).resolve() if project else Path(__file__).resolve().parent
    ensure_files(base)
    try:
        data = json.loads((base / "neto_offline_bilgi.json").read_text(encoding="utf-8-sig"))
        replies = data.get("replies", {})
        if isinstance(replies, dict):
            return {temizle(k): str(v) for k, v in replies.items() if str(k).strip() and str(v).strip()}
    except Exception:
        pass
    return {temizle(k): v for k, v in _DEFAULT_OFFLINE["replies"].items()}


def _eval_math(expr: str) -> str | None:
    raw = expr.casefold()
    raw = raw.replace("x", "*").replace(",", ".")
    raw = raw.replace("artı", "+").replace("arti", "+")
    raw = raw.replace("eksi", "-").replace("çarpı", "*").replace("carpi", "*")
    raw = raw.replace("bölü", "/").replace("bolu", "/")
    raw = re.sub(r"[^0-9+\-*/().%\s]", " ", raw)
    raw = re.sub(r"\s+", "", raw)
    if not raw or not re.search(r"\d", raw) or not re.search(r"[+\-*/%]", raw):
        return None
    try:
        tree = ast.parse(raw, mode="eval")
        def walk(node):
            if isinstance(node, ast.Expression):
                return walk(node.body)
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return node.value
            if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_BINOPS:
                left, right = walk(node.left), walk(node.right)
                if isinstance(node.op, ast.Pow) and abs(right) > 8:
                    raise ValueError("us cok buyuk")
                return _SAFE_BINOPS[type(node.op)](left, right)
            if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_UNARY:
                return _SAFE_UNARY[type(node.op)](walk(node.operand))
            raise ValueError("guvensiz ifade")
        result = walk(tree)
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        return f"Sonuç: {result}"
    except Exception:
        return None


def should_stay_offline(metin: Any) -> bool:
    m = temizle(metin)
    if not m:
        return True
    offline_patterns = (
        "selam", "merhaba", "sa", "slm", "naber", "nasilsin", "tesekkur", "sag ol",
        "saat", "saat kac", "tarih", "bugun", "gunlerden ne", "hangi gun",
        "kendini onar", "doktor", "yardim", "neler yapabilirsin", "sen kimsin",
        "yanimda", "laf at", "espri", "saka", "moral", "tamam", "olur",
    )
    return any(p in m for p in offline_patterns)


def internet_gerekli(metin: Any) -> bool:
    m = temizle(metin)
    if should_stay_offline(m):
        return False
    internet_words = (
        "haber", "son dakika", "guncel", "bugun ne oldu", "dolar", "euro", "altin",
        "bitcoin", "fiyat", "kur", "hava durumu", "kimdir", "nerede", "ne zaman",
        "en iyi", "oner", "tavsiye", "karsilastir", "indir", "site", "internet ara",
    )
    return any(w in m for w in internet_words) or m.endswith("?")


def quick_reply(metin: Any, *, agent_modu: bool = False, project: str | Path | None = None) -> str | None:
    original = str(metin or "").strip()
    m = temizle(original)
    if not m:
        return None

    now = _dt.datetime.now()

    greetings = {"selam", "merhaba", "sa", "slm", "hey", "naber"}
    if m in greetings or any(m.startswith(g + " ") for g in greetings):
        return random.choice([
            "Selam, buradayım. Ne yapıyoruz?",
            "Merhaba, hazırım. İstersen direkt komutu yaz.",
            "Selam. Bugün işi hızlı çözelim."
        ])

    if any(x in m for x in ("nasilsin", "keyfin nasil", "iyi misin")):
        return "İyiyim, sistem hazır. Sen ne yapmak istiyorsan oradan devam edelim."

    if any(x in m for x in ("tesekkur", "sag ol", "eyvallah")):
        return "Rica ederim. Takıldığın yerde beraber toparlarız."

    if ("saat" in m and ("kac" in m or m == "saat")) or m in {"saati soyle"}:
        return f"Şu an saat {now.strftime('%H:%M')}."

    if any(x in m for x in ("gunlerden ne", "hangi gun", "hangi gundeyiz", "tarih", "ayin kaci")):
        return f"Bugün {_DAYS_TR[now.weekday()]}, {now.day} {_MONTHS_TR[now.month - 1]} {now.year}."

    math_answer = _eval_math(m)
    if math_answer:
        return math_answer

    if any(x in m for x in ("sen kimsin", "adin ne", "ismin ne", "modelin ne")):
        return "Ben NetOps. Yerel komutları, sohbeti, offline bilgi bankasını ve gerektiğinde web aramasını yöneten asistanım."

    if any(x in m for x in ("neler yapabilirsin", "yardim", "ne yapabiliyorsun")):
        return "Şunları yapabilirim: sohbet, saat/tarih, hesaplama, program açma komutları, web arama, notlar, müzik durumu, yerel onarım ve offline bilgi cevapları."


    if any(x in m for x in ("yanimda kiz", "yanimda biri", "kiz var", "biri var", "laf at", "espri yap", "saka yap")):
        return random.choice([
            "Ortama hafif gir: 'Ben konuşmaya dahil olayım mı, yoksa gizli modda mı kalayım?'",
            "Doğal söyle: 'Sohbet iyi gidiyor, ben de bir cümle bırakıp kaçayım.'",
            "Kasma. Gülümseyip 'NetOps bile buradaysa bu ortam ciddidir' de, yeter."
        ])

    replies = _load_replies(project)
    if m in replies:
        return replies[m]
    for key, value in replies.items():
        words = key.split()
        if words and len(words) <= 5 and all(w in m for w in words):
            return value

    if agent_modu and len(m) <= 80 and not internet_gerekli(m):
        return "Anladım. Bunu yerel modda ele alıyorum; istersen daha net komuta çevirebilirim."

    return None


