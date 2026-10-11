from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path


BASE = Path(__file__).resolve().parent
REPORT = BASE / "NETO_TUM_MODULLER_RAPORU.txt"
JSON_REPORT = BASE / "NETO_TUM_MODULLER_RAPORU.json"
WHEELHOUSE = BASE / "NETO_WHEELS"

GROUPS = [
    ("Temel arayüz, ağ ve veri", BASE / "requirements-neto-core.txt", True),
    ("Medya, Live Mode ve STT/TTS", BASE / "requirements-neto-media.txt", False),
    ("Windows otomasyonu", BASE / "requirements-neto-automation.txt", False),
    ("Windows Now Playing / modern PyWinRT", BASE / "requirements-neto-winrt.txt", False),
]

IMPORT_TESTS = [
    ("customtkinter", "CustomTkinter", True),
    ("PIL.Image", "Pillow", True),
    ("flask", "Flask", True),
    ("flask_cors", "Flask-Cors", True),
    ("requests", "Requests", True),
    ("httpx", "HTTPX", True),
    ("aiohttp", "Aiohttp", True),
    ("multidict", "Multidict", True),
    ("yarl", "Yarl", True),
    ("propcache", "Propcache", True),
    ("frozenlist", "Frozenlist", True),
    ("markupsafe", "MarkupSafe", True),
    ("yaml", "PyYAML", True),
    ("tqdm", "Tqdm", True),
    ("numpy", "NumPy", True),
    ("psutil", "Psutil", True),
    ("lxml.etree", "LXML", True),
    ("dotenv", "Python-dotenv", True),
    ("cryptography", "Cryptography", True),
    ("websockets", "Websockets", True),
    ("pyperclip", "Pyperclip", True),

    ("pygame", "Pygame-CE", False),
    ("sounddevice", "SoundDevice", False),
    ("soundfile", "SoundFile", False),
    ("scipy", "SciPy", False),
    ("speech_recognition", "SpeechRecognition", False),
    ("pyttsx3", "Pyttsx3", False),
    ("faster_whisper", "Faster Whisper", False),

    ("pyautogui", "PyAutoGUI", False),
    ("pywinauto", "PyWinAuto", False),
    ("win32api", "PyWin32", False),
    ("comtypes", "Comtypes", False),
    ("pycaw.pycaw", "Pycaw", False),
    ("pynput", "Pynput", False),

    ("winrt", "WinRT namespace", False),
    ("winrt.windows.foundation", "WinRT Foundation", False),
    ("winrt.windows.foundation.collections", "WinRT Foundation Collections", False),
    ("winrt.windows.media.control", "WinRT Media Control", False),
    ("winrt.windows.storage.streams", "WinRT Storage Streams", False),
]


def command_text(command: list[str]) -> str:
    return subprocess.list2cmdline([str(part) for part in command])


def run_stream(
    command: list[str],
    title: str,
    lines: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> tuple[bool, int]:
    lines.extend(["", "=" * 78, title, "=" * 78, "Komut: " + command_text(command)])
    print(f"\n[{title}]")
    print(command_text(command))

    try:
        process = subprocess.Popen(
            [str(part) for part in command],
            cwd=str(cwd or BASE),
            env=env,
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
        code = int(process.wait())
        lines.append(f"Çıkış kodu: {code}")
        return code == 0, code
    except Exception:
        detail = traceback.format_exc()
        print(detail)
        lines.append(detail)
        return False, -999


def ensure_pip(lines: list[str]) -> bool:
    if importlib.util.find_spec("pip") is not None:
        return True
    ok, _ = run_stream(
        [sys.executable, "-m", "ensurepip", "--upgrade"],
        "pip oluşturuluyor",
        lines,
    )
    return ok


def read_requirements(path: Path) -> list[str]:
    packages: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        packages.append(line)
    return packages


def download_group(title: str, requirement: Path, lines: list[str]) -> bool:
    WHEELHOUSE.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "pip",
        "download",
        "--dest",
        str(WHEELHOUSE),
        "--prefer-binary",
        "--only-binary=:all:",
        "-r",
        str(requirement),
    ]
    ok, _ = run_stream(command, f"İNDİR: {title}", lines)
    if ok:
        return True

    # Bazı saf Python paketlerinde wheel çözümü başarısız olursa kaynak
    # arşivine izin vererek ikinci kez dener.
    command = [
        sys.executable,
        "-m",
        "pip",
        "download",
        "--dest",
        str(WHEELHOUSE),
        "--prefer-binary",
        "-r",
        str(requirement),
    ]
    retry_ok, _ = run_stream(command, f"İNDİR TEKRAR: {title}", lines)
    return retry_ok


def install_group(title: str, requirement: Path, lines: list[str]) -> bool:
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "--prefer-binary",
        "--find-links",
        str(WHEELHOUSE),
        "-r",
        str(requirement),
    ]
    ok, _ = run_stream(command, f"KUR: {title}", lines)
    return ok


def remove_conflicts(lines: list[str]) -> None:
    # Eski winrt paketi CPython 3.13 için uygun değildir. Modern bölünmüş
    # PyWinRT paketleri kurulacağı için eski paket kaldırılır.
    run_stream(
        [
            sys.executable,
            "-m",
            "pip",
            "uninstall",
            "-y",
            "winrt",
            "pygame",
        ],
        "Eski WinRT / Pygame çakışmaları temizleniyor",
        lines,
    )


def isolated_import_test(
    module: str,
    label: str,
    required: bool,
    lines: list[str],
) -> dict[str, object]:
    script = (
        "import importlib, sys\n"
        f"module = importlib.import_module({module!r})\n"
        f"print('IMPORT_OK: {module}')\n"
        "print('MODULE_FILE:', getattr(module, '__file__', 'built-in'))\n"
    )

    command = [
        sys.executable,
        "-X",
        "faulthandler",
        "-c",
        script,
    ]

    try:
        completed = subprocess.run(
            command,
            cwd=str(BASE),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
        )
        output = ((completed.stdout or "") + (completed.stderr or "")).strip()
        ok = completed.returncode == 0
        status = "OK" if ok else "HATA"
        summary = (
            f"{status:<4} {label:<32} {module:<42} "
            f"EXIT={completed.returncode}"
        )
        print(summary)
        lines.append(summary)
        if output:
            lines.extend("    " + line for line in output.splitlines()[-12:])
        return {
            "module": module,
            "label": label,
            "required": required,
            "ok": ok,
            "exit_code": completed.returncode,
            "output": output[-6000:],
        }
    except subprocess.TimeoutExpired as exc:
        summary = f"HATA {label:<32} {module:<42} ZAMAN AŞIMI"
        print(summary)
        lines.append(summary)
        return {
            "module": module,
            "label": label,
            "required": required,
            "ok": False,
            "exit_code": -408,
            "output": str(exc),
        }
    except Exception:
        detail = traceback.format_exc()
        lines.append(detail)
        return {
            "module": module,
            "label": label,
            "required": required,
            "ok": False,
            "exit_code": -999,
            "output": detail,
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="NetOps bağımlılıklarını tek seferde indir, kur ve test et."
    )
    parser.add_argument(
        "--download-only",
        action="store_true",
        help="Yalnızca NETO_WHEELS klasörüne indir.",
    )
    parser.add_argument(
        "--install-only",
        action="store_true",
        help="NETO_WHEELS içinden kur ve test et.",
    )
    args = parser.parse_args()

    started = time.time()
    lines = [
        "NETO ASİSTAN — TÜM MODÜLLER TEK SEFERDE",
        f"Python: {sys.executable}",
        f"Sürüm: {sys.version}",
        f"Platform: {platform.platform()}",
        f"Mimari: {platform.machine()}",
        f"Kurulum klasörü: {BASE}",
        f"Wheel klasörü: {WHEELHOUSE}",
    ]

    if os.name != "nt":
        lines.append("HATA: Bu paket Windows NetOps kurulumu için hazırlanmıştır.")
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(lines[-1])
        return 2

    if sys.version_info < (3, 11):
        lines.append("HATA: Python 3.11 veya daha yeni gereklidir.")
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(lines[-1])
        return 3

    if not ensure_pip(lines):
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 4

    bootstrap_ok, _ = run_stream(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "pip",
            "setuptools",
            "wheel",
            "packaging",
        ],
        "pip / setuptools / wheel hazırlanıyor",
        lines,
    )
    if not bootstrap_ok:
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 5

    remove_conflicts(lines)

    group_results: list[dict[str, object]] = []

    if not args.install_only:
        for title, requirement, required in GROUPS:
            ok = download_group(title, requirement, lines)
            group_results.append({
                "phase": "download",
                "title": title,
                "required": required,
                "ok": ok,
            })

    if args.download_only:
        elapsed = time.time() - started
        lines.extend([
            "",
            f"Toplam süre: {elapsed:.1f} saniye",
            f"İndirilen dosya sayısı: {len(list(WHEELHOUSE.glob('*')))}",
            "SONUÇ: İNDİRME TAMAMLANDI",
        ])
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        JSON_REPORT.write_text(
            json.dumps(
                {
                    "mode": "download-only",
                    "groups": group_results,
                    "wheel_count": len(list(WHEELHOUSE.glob("*"))),
                },
                ensure_ascii=False,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
        print("\nRapor:", REPORT)
        return 0 if all(
            item["ok"] or not item["required"] for item in group_results
        ) else 1

    for title, requirement, required in GROUPS:
        ok = install_group(title, requirement, lines)
        group_results.append({
            "phase": "install",
            "title": title,
            "required": required,
            "ok": ok,
        })

    lines.extend(["", "=" * 78, "AYRI SÜREÇTE IMPORT / NATIVE CRASH TESTLERİ", "=" * 78])
    import_results = [
        isolated_import_test(module, label, required, lines)
        for module, label, required in IMPORT_TESTS
    ]

    pip_check_ok, pip_check_code = run_stream(
        [sys.executable, "-m", "pip", "check"],
        "pip bağımlılık bütünlüğü",
        lines,
    )

    required_group_failures = [
        item for item in group_results
        if item["required"] and not item["ok"]
    ]
    required_import_failures = [
        item for item in import_results
        if item["required"] and not item["ok"]
    ]
    optional_import_failures = [
        item for item in import_results
        if not item["required"] and not item["ok"]
    ]

    elapsed = time.time() - started
    success = (
        not required_group_failures
        and not required_import_failures
        and pip_check_ok
    )

    lines.extend([
        "",
        "=" * 78,
        "SONUÇ",
        "=" * 78,
        f"Toplam süre: {elapsed:.1f} saniye",
        f"Wheel dosyası: {len(list(WHEELHOUSE.glob('*')))}",
        f"Zorunlu import hatası: {len(required_import_failures)}",
        f"Opsiyonel import hatası: {len(optional_import_failures)}",
        f"pip check çıkış kodu: {pip_check_code}",
        "GENEL SONUÇ: " + ("BAŞARILI" if success else "EKSİK / HATALI"),
    ])

    if optional_import_failures:
        lines.append("")
        lines.append("Opsiyonel başarısız modüller:")
        lines.extend(
            f"  - {item['label']} ({item['module']}) EXIT={item['exit_code']}"
            for item in optional_import_failures
        )

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    JSON_REPORT.write_text(
        json.dumps(
            {
                "python": sys.executable,
                "version": sys.version,
                "platform": platform.platform(),
                "elapsed_seconds": elapsed,
                "success": success,
                "groups": group_results,
                "imports": import_results,
                "pip_check_ok": pip_check_ok,
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    print("\nMetin raporu:", REPORT)
    print("JSON raporu:", JSON_REPORT)

    if success:
        print("Neto'nun zorunlu modülleri hazır.")
        return 0

    print("Kurulum tamamlandı fakat raporda hata bulunan modüller var.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
