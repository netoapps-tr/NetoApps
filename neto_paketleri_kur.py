from __future__ import annotations

import importlib
import importlib.util
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPORT = BASE / "NETO_PAKET_KURULUM_RAPORU.txt"

GROUPS = [
    ("Temel arayüz ve ağ", BASE / "requirements-neto-core.txt", True),
    ("Live Mode mikrofon ve Whisper", BASE / "requirements-neto-live.txt", True),
    ("Windows Now Playing / WinRT", BASE / "requirements-neto-media.txt", False),
]

IMPORT_TESTS = [
    ("customtkinter", "CustomTkinter"),
    ("PIL.Image", "Pillow"),
    ("pygame", "Pygame"),
    ("flask", "Flask"),
    ("requests", "Requests"),
    ("psutil", "Psutil"),
    ("pyautogui", "PyAutoGUI"),
    ("pywinauto", "PyWinAuto"),
    ("pycaw.pycaw", "Pycaw"),
    ("comtypes", "Comtypes"),
    ("aiohttp", "Aiohttp"),
    ("lxml.etree", "LXML"),
    ("win32api", "PyWin32"),
    ("numpy", "NumPy"),
    ("scipy", "SciPy"),
    ("sounddevice", "SoundDevice"),
    ("faster_whisper", "Faster Whisper"),
    ("winrt.windows.media.control", "WinRT Media Control"),
    ("winrt.windows.storage.streams", "WinRT Storage Streams"),
]


def write_report(lines: list[str]) -> None:
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(command: list[str], lines: list[str], title: str) -> bool:
    lines.append("")
    lines.append("=" * 72)
    lines.append(title)
    lines.append("=" * 72)
    lines.append("Komut: " + subprocess.list2cmdline(command))
    print(f"\n[{title}]")
    try:
        process = subprocess.Popen(
            command,
            cwd=BASE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="")
            lines.append(line.rstrip())
        code = process.wait()
        lines.append(f"Çıkış kodu: {code}")
        return code == 0
    except Exception:
        detail = traceback.format_exc()
        print(detail)
        lines.append(detail)
        return False


def main() -> int:
    started = time.time()
    lines = [
        "NETO ASİSTAN PAKET KURULUM RAPORU",
        f"Python: {sys.executable}",
        f"Sürüm: {sys.version}",
        f"Klasör: {BASE}",
    ]

    print("NetOps bağımlılık kurulumu")
    print("Python:", sys.executable)
    print("Sürüm:", sys.version.split()[0])
    print("importlib:", getattr(importlib, "__file__", "built-in"))

    importlib_path = str(getattr(importlib, "__file__", "") or "")
    project_shadow = BASE / "importlib.py"
    project_shadow_package = BASE / "importlib"
    if project_shadow.exists() or project_shadow_package.exists():
        warning = (
            "HATA: Kurulum klasöründe Python'un standart importlib modülünü "
            "gölgeleyen importlib.py veya importlib klasörü bulundu."
        )
        print(warning)
        lines.append(warning)
        lines.append(f"importlib kaynağı: {importlib_path}")
        write_report(lines)
        return 5

    if sys.version_info < (3, 11):
        lines.append("HATA: Python 3.11 veya daha yeni gerekli.")
        write_report(lines)
        return 2

    # pip yoksa oluştur.
    try:
        pip_spec = importlib.util.find_spec("pip")
    except Exception as exc:
        lines.append(f"pip denetim hatası: {type(exc).__name__}: {exc}")
        pip_spec = None

    if pip_spec is None:
        if not run([sys.executable, "-m", "ensurepip", "--upgrade"], lines, "pip oluşturuluyor"):
            write_report(lines)
            return 3

    # Pygame'in pkg_resources uyarısı ve uyumluluk için setuptools 81 altı.
    if not run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "pip",
            "wheel",
            "setuptools<81",
        ],
        lines,
        "pip / wheel / setuptools hazırlanıyor",
    ):
        write_report(lines)
        return 4

    group_results: dict[str, bool] = {}
    for title, requirement_file, required in GROUPS:
        command = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--prefer-binary",
            "-r",
            str(requirement_file),
        ]
        ok = run(command, lines, title)
        group_results[title] = ok
        if required and not ok:
            lines.append(f"UYARI: Zorunlu grup kurulamadı: {title}")

    lines.append("")
    lines.append("=" * 72)
    lines.append("IMPORT KONTROLLERİ")
    lines.append("=" * 72)

    failed_imports: list[str] = []
    for module, label in IMPORT_TESTS:
        try:
            importlib.import_module(module)
            status = f"OK   {label:<28} ({module})"
            print(status)
            lines.append(status)
        except Exception as exc:
            status = f"HATA {label:<28} ({module}) -> {type(exc).__name__}: {exc}"
            print(status)
            lines.append(status)
            failed_imports.append(module)

    # pip'in kendi bütünlük kontrolü.
    pip_check_ok = run(
        [sys.executable, "-m", "pip", "check"],
        lines,
        "pip bağımlılık bütünlüğü",
    )

    elapsed = time.time() - started
    lines.append("")
    lines.append(f"Toplam süre: {elapsed:.1f} saniye")
    lines.append(f"Başarısız import sayısı: {len(failed_imports)}")
    if failed_imports:
        lines.append("Başarısız importlar:")
        lines.extend(f"  - {name}" for name in failed_imports)

    # WinRT opsiyonel sayılır; diğer importlar zorunlu.
    optional = {
        "winrt.windows.media.control",
        "winrt.windows.storage.streams",
    }
    required_failures = [name for name in failed_imports if name not in optional]

    success = not required_failures and pip_check_ok
    lines.append("")
    lines.append("SONUÇ: " + ("BAŞARILI" if success else "EKSİK/HATALI"))
    write_report(lines)

    print("\nRapor:", REPORT)
    if success:
        print("Temel Neto paketleri ve Live Mode paketleri hazır.")
        return 0

    print("Bazı zorunlu paketler kurulamadı. Rapordaki HATA satırlarına bak.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
