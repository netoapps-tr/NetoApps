from __future__ import annotations

import os
import platform
import re
import sys
from pathlib import Path

MINI_LINUX_ROOT = Path.home() / ".netops-mini-linux"
MINI_LINUX_DIRS = ("home", "notes", "tmp", "logs", "tools")


def bootstrap() -> Path:
    MINI_LINUX_ROOT.mkdir(parents=True, exist_ok=True)
    for name in MINI_LINUX_DIRS:
        (MINI_LINUX_ROOT / name).mkdir(parents=True, exist_ok=True)
    readme = MINI_LINUX_ROOT / "README.txt"
    if not readme.exists():
        readme.write_text(
            "NetOps Mini Linux alani. Agent burada guvenli sekilde gezer.\n"
            "Serbest shell yok; ana Windows dosyalarina dokunmaz.\n",
            encoding="utf-8",
        )
    return MINI_LINUX_ROOT


def safe_path(raw: str = "") -> Path:
    root = bootstrap().resolve()
    value = str(raw or "home").strip().lstrip("/") or "home"
    target = (root / value).resolve()
    try:
        target.relative_to(root)
    except Exception as exc:
        raise ValueError("Mini Linux alaninin disina cikamam.") from exc
    return target


def list_path(raw_path: str = "") -> str:
    target = safe_path(raw_path)
    if not target.exists():
        return f"Yok: {target.relative_to(MINI_LINUX_ROOT)}"
    if target.is_file():
        return f"Dosya: {target.name} ({target.stat().st_size} bayt)"
    rows = []
    for item in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.casefold()))[:80]:
        kind = "dosya" if item.is_file() else "klasor"
        rows.append(f"{kind:6} {item.name}")
    return "Mini Linux liste:\n" + ("\n".join(rows) if rows else "bos")


def read_file(raw_path: str) -> str:
    target = safe_path(raw_path)
    if not target.is_file():
        return "Okunacak dosya bulamadim."
    data = target.read_text(encoding="utf-8", errors="replace")
    return data[:3000] if data else "Dosya bos."


def write_file(raw: str) -> str:
    if ":" not in raw:
        return "Yazmak icin ornek: linux yaz notes/plan.txt: bugun bunu yap"
    name, content = raw.split(":", 1)
    target = safe_path(name.strip())
    if target.suffix.lower() not in {".txt", ".md", ".json", ".log"}:
        return "Guvenlik icin sadece .txt, .md, .json, .log yazabilirim."
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content.strip() + "\n", encoding="utf-8")
    return f"Yazildi: {target.relative_to(MINI_LINUX_ROOT)}"


def info() -> str:
    root = bootstrap()
    try:
        stat = os.statvfs(str(root))
        free_mb = int((stat.f_bavail * stat.f_frsize) / (1024 * 1024))
    except Exception:
        free_mb = 0
    return (
        "Mini Linux aktif.\n"
        f"Kok: {root}\n"
        f"Distro: {os.environ.get('WSL_DISTRO_NAME') or 'bilinmiyor'}\n"
        f"Python: {sys.version.split()[0]}\n"
        f"Makine: {platform.machine()}\n"
        f"Bos alan: {free_mb} MB"
    )


def handle(text: str) -> str | None:
    metin = str(text or "").strip()
    low = metin.casefold()
    if not any(key in low for key in ("linux", "wsl", "ubuntu", "mini")):
        return None

    if any(key in low for key in ("mini linux kur", "linux alanı kur", "linux alani kur", "linux hazırla", "linux hazirla")):
        root = bootstrap()
        return f"Mini Linux hazir: {root}\nKlasorler: " + ", ".join(MINI_LINUX_DIRS)

    if any(key in low for key in ("linux durum", "linux sistem", "mini durum", "wsl durum")):
        return info()

    if any(key in low for key in ("linux nerede", "linux neredesin", "linux pwd", "linux konum")):
        root = bootstrap()
        return f"Mini Linux kok: {root}\nCalisma alani: {root / 'home'}"

    if any(key in low for key in ("linux liste", "linux ls", "linux dosyalar")):
        cleaned = re.sub(r".*?(?:linux liste|linux ls|linux dosyalar)", "", low).strip()
        return list_path(cleaned)

    if low.startswith(("linux oku", "mini oku")):
        name = re.sub(r"^(linux oku|mini oku)\s*", "", metin, flags=re.IGNORECASE).strip()
        return read_file(name)

    if low.startswith(("linux yaz", "mini yaz")):
        rest = re.sub(r"^(linux yaz|mini yaz)\s*", "", metin, flags=re.IGNORECASE).strip()
        return write_file(rest)

    if any(key in low for key in ("linux yardım", "linux yardim", "mini yardım", "mini yardim")):
        return (
            "Mini Linux komutlari:\n"
            "linux hazirla\n"
            "linux durum\n"
            "linux nerede\n"
            "linux liste home\n"
            "linux yaz notes/plan.txt: metin\n"
            "linux oku notes/plan.txt"
        )

    return None
