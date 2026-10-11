from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ESSENTIAL_FILES = [
    "asistan beta.py", "config.py", "temalar.py", "lang.py", "neto_ai.py",
]
OPTIONAL_FILES = [
    "neto_live_mode.py", "neto_live_app.py", "neto_now_playing.py", "neto_chat.py",
    "neto_agent.py", "neto_agent_worker.py", "neto_updater.py", "neto_android_device.py",
]
IMPORTS = [
    ("tkinter", True), ("customtkinter", True), ("PIL.Image", True),
    ("requests", True), ("psutil", True), ("flask", False), ("pygame", False),
    ("pyautogui", False), ("pywinauto", False), ("edge_tts", False),
    ("aiohttp", False), ("lxml.etree", False), ("numpy", False),
    ("sounddevice", False), ("faster_whisper", False),
    ("winrt.windows.media.control", False),
]
SHADOW_NAMES = ["importlib.py", "json.py", "tkinter.py", "PIL.py", "requests.py", "pygame.py"]


def isolated_import(module: str, timeout: int = 15) -> tuple[bool, str, float]:
    started = time.perf_counter()
    code = (
        "import importlib,sys,time; "
        f"m=importlib.import_module({module!r}); "
        "print(getattr(m,'__file__','built-in'))"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        elapsed = time.perf_counter() - started
        output = (result.stdout or result.stderr or "").strip()
        return result.returncode == 0, output[-1200:], elapsed
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT", time.perf_counter() - started
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}", time.perf_counter() - started


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default=".")
    args = parser.parse_args()
    project = Path(args.project).expanduser().resolve()
    report: list[str] = [
        "NETO DOCTOR v5", f"Tarih: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Python: {sys.executable}", f"Sürüm: {sys.version}", f"Proje: {project}", "",
    ]
    fatal = False

    report.append("DOSYALAR")
    for name in ESSENTIAL_FILES:
        exists = (project / name).is_file()
        report.append(f"{'OK' if exists else 'EKSİK'}  {name}")
        fatal = fatal or not exists
    for name in OPTIONAL_FILES:
        report.append(f"{'OK' if (project / name).is_file() else 'OPSİYONEL EKSİK'}  {name}")

    report.extend(["", "GÖLGELEME KONTROLÜ"])
    for name in SHADOW_NAMES:
        exists = (project / name).exists()
        report.append(f"{'HATA' if exists else 'OK'}  {name}")
        fatal = fatal or exists

    report.extend(["", "PYTHON DERLEME / AST"])
    py_files = sorted(project.glob("*.py"))
    for path in py_files:
        try:
            text = path.read_text(encoding="utf-8-sig")
            compile(text, str(path), "exec")
            ast.parse(text)
            report.append(f"OK    {path.name}")
        except Exception as exc:
            report.append(f"HATA  {path.name}: {type(exc).__name__}: {exc}")
            fatal = True

    report.extend(["", "İZOLE MODÜL TESTLERİ"])
    for module, essential in IMPORTS:
        ok, output, elapsed = isolated_import(module)
        label = "OK" if ok else ("HATA" if essential else "OPSİYONEL HATA")
        report.append(f"{label:<14} {module:<34} {elapsed:>6.2f} sn  {output}")
        if essential and not ok:
            fatal = True

    app = project / "asistan beta.py"
    if app.is_file():
        text = app.read_text(encoding="utf-8-sig", errors="replace")
        report.extend(["", "STABILITY V5 İŞARETLERİ"])
        for marker in [
            "NETO_STABILITY_V5", "NETO_STABILITY_V5_LAZY_NETO_CODE",
            "_neto_quick_child_ready(root, _neto_launch_started)",
        ]:
            ok = marker in text
            report.append(f"{'OK' if ok else 'EKSİK'}  {marker}")
            fatal = fatal or not ok

    report.extend(["", f"SONUÇ: {'HATALI' if fatal else 'BAŞARILI'}"])
    out = project / "NETO_DOCTOR_RAPORU.txt"
    out.write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    print(f"\nRapor: {out}")
    if os.name == "nt":
        try:
            os.startfile(out)
        except Exception:
            pass
    input("\nKapatmak için Enter…")
    return 1 if fatal else 0


if __name__ == "__main__":
    raise SystemExit(main())

# NetOps in-app health API. The packaged EXE must not look for source files.
ESSENTIAL_RUNTIME_FILES = [
    "config.py", "temalar.py", "lang.py", "neto_ai.py",
    "neto_sohbet_v2.py", "neto_sohbet_v3.py", "netops_one_engine.py",
]
RUNTIME_DIRS = ["logs", "now_playing_cache", "arduino"]
DEFAULT_MEMORY = {
    "ayarlar": "OZEL_AYARLAR_PANELI",
    "google aç": "https://www.google.com",
    "youtube aç": "https://www.youtube.com",
}
DEFAULT_FEATURES = {"replies": {}, "web_commands": {}, "app_commands": {}}


def _runtime_base(project: str | os.PathLike[str] = ".") -> tuple[Path, bool]:
    frozen = bool(getattr(sys, "frozen", False))
    if frozen:
        return Path(os.environ.get("APPDATA") or Path.home()) / "NetoAsistan", True
    return Path(project).expanduser().resolve(), False


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _ensure_json(path: Path, defaults: dict[str, Any], fixes: list[str]) -> None:
    if not path.exists():
        _write_json(path, defaults)
        fixes.append(f"Olusturuldu: {path.name}")
        return
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(value, dict):
            raise ValueError("JSON nesnesi bekleniyordu")
    except Exception:
        backup = path.with_name(path.name + ".bozuk.bak")
        try:
            path.replace(backup)
        except Exception:
            pass
        _write_json(path, defaults)
        fixes.append(f"Sifirlandi: {path.name}")
        return
    changed = False
    for key, default in defaults.items():
        if key not in value:
            value[key] = default
            changed = True
    if changed:
        _write_json(path, value)
        fixes.append(f"Tamamlandi: {path.name}")


def self_heal(project: str | os.PathLike[str] = ".") -> dict[str, Any]:
    base, frozen = _runtime_base(project)
    fixes: list[str] = []
    issues: list[str] = []
    checks: list[dict[str, Any]] = []
    for dirname in RUNTIME_DIRS:
        try:
            (base / dirname).mkdir(parents=True, exist_ok=True)
            checks.append({"name": f"dir:{dirname}", "ok": True})
        except Exception as exc:
            checks.append({"name": f"dir:{dirname}", "ok": False, "output": str(exc)})
            issues.append(f"Klasor olusturulamadi: {dirname}")
    for filename, defaults in (("hafiza.json", DEFAULT_MEMORY), ("netops_ozellikler.json", DEFAULT_FEATURES)):
        try:
            _ensure_json(base / filename, defaults, fixes)
            checks.append({"name": f"json:{filename}", "ok": True})
        except Exception as exc:
            checks.append({"name": f"json:{filename}", "ok": False, "output": str(exc)})
            issues.append(f"JSON onarilamadi: {filename}")
    if frozen:
        checks.append({"name": "frozen_bundle", "ok": True, "output": "EXE kaynak kontrolu atlandi."})
    else:
        app_file = base / "asistan beta.py"
        try:
            compile(app_file.read_text(encoding="utf-8-sig"), str(app_file), "exec")
            checks.append({"name": "compile:asistan beta.py", "ok": True})
        except Exception as exc:
            checks.append({"name": "compile:asistan beta.py", "ok": False, "output": str(exc)})
            issues.append(f"Ana dosya derleme hatasi: {type(exc).__name__}: {exc}")
    return {"ok": not issues, "issues": issues, "fixes": fixes, "checks": checks, "project": str(base)}


def quick_check(project: str | os.PathLike[str] = ".", repair: bool = True) -> dict[str, Any]:
    base, frozen = _runtime_base(project)
    issues: list[str] = []
    fixes: list[str] = []
    details: dict[str, Any] = {"project": str(base), "checks": []}
    if frozen:
        exe = Path(sys.executable)
        ok = exe.is_file()
        details["checks"].append({"name": "frozen_bundle", "ok": ok, "output": str(exe)})
        if not ok:
            issues.append("EXE dosyasi bulunamadi")
    else:
        for name in ESSENTIAL_RUNTIME_FILES + ["asistan beta.py"]:
            ok = (base / name).is_file()
            details["checks"].append({"name": f"file:{name}", "ok": ok})
            if not ok:
                issues.append(f"Eksik dosya: {name}")
        app_file = base / "asistan beta.py"
        if app_file.is_file():
            try:
                compile(app_file.read_text(encoding="utf-8-sig"), str(app_file), "exec")
                details["checks"].append({"name": "compile:asistan beta.py", "ok": True})
            except Exception as exc:
                details["checks"].append({"name": "compile:asistan beta.py", "ok": False, "output": str(exc)})
                issues.append(f"Ana dosya derleme hatasi: {type(exc).__name__}: {exc}")
    if repair:
        healed = self_heal(project)
        fixes.extend(healed.get("fixes", []))
        issues.extend(healed.get("issues", []))
        details["self_heal"] = healed
    ok = not issues
    message = "Mini Doktor: Sistem hazir." if ok else "Mini Doktor: " + " | ".join(issues[:2])
    if ok and fixes:
        message = "Mini Doktor: Yerel onarim hazir."
    return {"ok": ok, "message": message, "issues": issues, "fixes": fixes, "details": details}