from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPORT = BASE / "NETO_BAGIMLILIK_RAPORU.txt"

GROUPS = {
    "core": {
        "requirements": "requirements-neto-core.txt",
        "imports": [
            "customtkinter", "PIL.Image", "pygame", "flask", "requests", "psutil",
            "pyautogui", "pywinauto", "pycaw.pycaw", "comtypes",
            "aiohttp", "lxml.etree", "win32api",
        ],
    },
    "live": {
        "requirements": "requirements-neto-live.txt",
        "imports": ["numpy", "scipy", "sounddevice", "faster_whisper"],
    },
    "media": {
        "requirements": "requirements-neto-media.txt",
        "imports": ["winrt.windows.media.control", "winrt.windows.storage.streams"],
    },
}


def stream_command(command: list[str], lines: list[str], title: str, timeout: int = 1800) -> bool:
    lines.extend(["", "=" * 72, title, "=" * 72, subprocess.list2cmdline(command)])
    print(f"\n[{title}]")
    try:
        process = subprocess.Popen(
            command, cwd=BASE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
        )
        assert process.stdout is not None
        started = time.time()
        for line in process.stdout:
            print(line, end="")
            lines.append(line.rstrip())
            if time.time() - started > timeout:
                process.kill()
                lines.append("TIMEOUT")
                return False
        code = process.wait()
        lines.append(f"Çıkış kodu: {code}")
        return code == 0
    except Exception as exc:
        lines.append(f"{type(exc).__name__}: {exc}")
        return False


def isolated_import(module: str, timeout: int = 25) -> tuple[bool, str, float, int]:
    started = time.perf_counter()
    code = (
        "import importlib; "
        f"m=importlib.import_module({module!r}); "
        "print(getattr(m,'__file__','built-in'))"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        output = (result.stdout or result.stderr or "").strip()
        return result.returncode == 0, output[-1200:], time.perf_counter() - started, result.returncode
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT", time.perf_counter() - started, 124
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}", time.perf_counter() - started, 125


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--groups", nargs="+", choices=sorted(GROUPS), default=["core"])
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    lines = [
        "NETO BAĞIMLILIK KURUCUSU v3",
        f"Python: {sys.executable}",
        f"Sürüm: {sys.version}",
        f"Gruplar: {', '.join(args.groups)}",
    ]
    print(lines[0])
    print(lines[1])
    print(lines[2])

    shadow = [name for name in ("importlib.py", "pip.py", "json.py") if (BASE / name).exists()]
    if shadow:
        lines.append("HATA: Standart modülü gölgeleyen dosyalar: " + ", ".join(shadow))
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(lines[-1])
        return 2

    if importlib.util.find_spec("pip") is None:
        if not stream_command([sys.executable, "-m", "ensurepip", "--upgrade"], lines, "pip hazırlanıyor"):
            REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return 3

    if not args.check_only:
        if not stream_command(
            [sys.executable, "-m", "pip", "install", "--upgrade", "pip", "wheel", "setuptools<81"],
            lines, "pip / wheel / setuptools",
        ):
            REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return 4

        for group in args.groups:
            req = BASE / GROUPS[group]["requirements"]
            if not req.is_file():
                lines.append(f"HATA: {req.name} bulunamadı")
                continue
            stream_command(
                [sys.executable, "-m", "pip", "install", "--upgrade", "--prefer-binary", "-r", str(req)],
                lines, f"{group} paketleri",
            )

    lines.extend(["", "İZOLE IMPORT TESTLERİ"])
    failed: list[str] = []
    for group in args.groups:
        for module in GROUPS[group]["imports"]:
            ok, output, elapsed, code = isolated_import(module)
            status = "OK" if ok else "HATA"
            line = f"{status:<5} {module:<36} {elapsed:>6.2f} sn  rc={code}  {output}"
            print(line)
            lines.append(line)
            if not ok:
                failed.append(module)

    pip_ok = stream_command([sys.executable, "-m", "pip", "check"], lines, "pip check", timeout=180)
    success = not failed and pip_ok
    lines.extend(["", "SONUÇ: " + ("BAŞARILI" if success else "EKSİK/HATALI")])
    if failed:
        lines.append("Başarısız modüller: " + ", ".join(failed))
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nRapor: {REPORT}")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
