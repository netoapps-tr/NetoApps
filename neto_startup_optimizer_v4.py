from __future__ import annotations

import argparse
import ast
import datetime as dt
import os
import re
import shutil
import sys
import textwrap
import traceback
from pathlib import Path
from typing import List, Tuple

PATCH_BUILD = "2026.07.26-under-5-target-v4"

VISIBLE_BOOT_BLOCK = r'''
    # NETO_REAL_WINDOW_FIRST_V4
    # Gerçek NetOps penceresi tüm arayüz bitene kadar gizlenmez. Başlık çubuğu ve
    # uygulama yüzeyi hemen çizilir; ağır widget kurulumu bunun arkasında sürer.
    NETO_LAUNCH_LOADING_WINDOW = None
    _NETO_FAST_REAL_OVERLAY = None
    _NETO_FAST_REAL_STATUS = None
    _NETO_FAST_REAL_PROGRESS = None
    _NETO_FAST_REAL_PROGRESS_VALUE = 0.08
    try:
        root.attributes("-alpha", 1.0)
        root.state("normal")
        root.deiconify()
        root.lift()

        _NETO_FAST_REAL_OVERLAY = tk.Frame(
            app_content,
            bg=aktif_palet.get("bg", "#09090B"),
            bd=0,
            highlightthickness=0,
        )
        _NETO_FAST_REAL_OVERLAY.place(x=0, y=0, relwidth=1, relheight=1)

        _neto_fast_boot_center = tk.Frame(
            _NETO_FAST_REAL_OVERLAY,
            bg=aktif_palet.get("bg", "#09090B"),
            bd=0,
            highlightthickness=0,
        )
        _neto_fast_boot_center.place(relx=0.5, rely=0.47, anchor="center")

        tk.Label(
            _neto_fast_boot_center,
            text="NETO ASİSTAN",
            bg=aktif_palet.get("bg", "#09090B"),
            fg=aktif_palet.get("text_main", "#F4F4F5"),
            font=("Segoe UI Semibold", 25),
        ).pack(pady=(0, 6))

        _NETO_FAST_REAL_STATUS = tk.Label(
            _neto_fast_boot_center,
            text="Hazırlanıyor...",
            bg=aktif_palet.get("bg", "#09090B"),
            fg=aktif_palet.get("text_dim", "#A1A1AA"),
            font=("Segoe UI", 11),
        )
        _NETO_FAST_REAL_STATUS.pack(pady=(0, 24))

        _neto_fast_track = tk.Canvas(
            _neto_fast_boot_center,
            width=330,
            height=7,
            bg=aktif_palet.get("card", "#1B1B20"),
            bd=0,
            highlightthickness=0,
        )
        _neto_fast_track.pack()
        _NETO_FAST_REAL_PROGRESS = _neto_fast_track.create_rectangle(
            0,
            0,
            int(330 * _NETO_FAST_REAL_PROGRESS_VALUE),
            7,
            fill=aktif_palet.get("neon", "#22C55E"),
            outline="",
        )
        globals()["_NETO_FAST_REAL_TRACK"] = _neto_fast_track

        root.update_idletasks()
        root.update()
        neto_time_log("gerçek NetOps penceresi görünür")
    except Exception as _neto_real_window_error:
        try:
            print(f"[REAL_WINDOW_BOOT_ERROR] {_neto_real_window_error}", flush=True)
        except Exception:
            pass

    def _neto_launch_checkpoint(status=None, force=False):
        try:
            if status:
                print(f"[LAUNCH_BUILD] {status}", flush=True)
        except Exception:
            pass

        try:
            if status and _NETO_FAST_REAL_STATUS is not None:
                _NETO_FAST_REAL_STATUS.configure(text=str(status))

            progress_map = {
                "Ana arayüz": 0.16,
                "Preparing main": 0.16,
                "Sol menü": 0.36,
                "Preparing sidebar": 0.36,
                "Ana ekran": 0.62,
                "Preparing home": 0.62,
                "Ayarlar": 0.76,
                "Settings": 0.76,
                "Son arayüz": 0.90,
                "Final interface": 0.90,
                "Açıldı": 1.0,
                "Opened": 1.0,
            }
            text_value = str(status or "")
            target = None
            for key, value in progress_map.items():
                if key in text_value:
                    target = value
                    break
            if target is not None:
                globals()["_NETO_FAST_REAL_PROGRESS_VALUE"] = target
                track = globals().get("_NETO_FAST_REAL_TRACK")
                if track is not None and _NETO_FAST_REAL_PROGRESS is not None:
                    track.coords(_NETO_FAST_REAL_PROGRESS, 0, 0, int(330 * target), 7)

            if _NETO_FAST_REAL_OVERLAY is not None:
                _NETO_FAST_REAL_OVERLAY.lift()
            root.update_idletasks()
            root.update()
        except Exception:
            pass
'''


def read_text(path: Path) -> Tuple[str, str]:
    for encoding in ("utf-8", "utf-8-sig", "cp1254", "cp1252"):
        try:
            return path.read_text(encoding=encoding), encoding
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace"), "utf-8"


def write_atomic(path: Path, text: str) -> None:
    temporary = path.with_suffix(path.suffix + ".v4_tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def detect_project(explicit: str = "") -> Path:
    candidates = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    candidates.extend([
        Path.cwd(),
        Path.home() / "Desktop" / "NETO ASİSTAN SİLME",
        Path(r"C:\Users\PC\Desktop\NETO ASİSTAN SİLME"),
        Path.home() / "Downloads" / "neto_asistan_v10_32_nowplaying_volume (2)",
    ])
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except Exception:
            resolved = candidate
        if (resolved / "asistan beta.py").is_file():
            return resolved
    raise FileNotFoundError("asistan beta.py bulunan NetOps proje klasörü bulunamadı.")


def backup(path: Path) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    output = path.with_name(f"{path.name}.v4_oncesi_{stamp}.bak")
    shutil.copy2(path, output)
    return output


def patch_disable_second_python_splash(source: str, changes: List[str]) -> str:
    old = "_NETO_FAST_SPLASH_PROCESS = _neto_fast_splash_start()"
    new = "_NETO_FAST_SPLASH_PROCESS = None  # V4: ikinci Python süreci kaldırıldı"
    if old in source:
        source = source.replace(old, new, 1)
        changes.append("İkinci Python splash süreci kaldırıldı")
    return source


def patch_lazy_neto_ui(source: str, changes: List[str]) -> str:
    old = "from neto_ui import run_launch_gate"
    if old in source:
        source = source.replace(
            old,
            "def run_launch_gate(*args, **kwargs):\n"
            "    return _neto_lazy_import(\"neto_ui\").run_launch_gate(*args, **kwargs)",
            1,
        )
        changes.append("neto_ui yalnızca giriş ekranı gerektiğinde yükleniyor")
    return source


def patch_disable_pycaw_eager_import(source: str, changes: List[str]) -> str:
    marker = "NETO_FAST_START_NO_PYCAW_IMPORT_V4"
    if marker in source:
        return source

    pattern = re.compile(
        r"(?ms)^try:\n\s+from ctypes import cast, POINTER\n"
        r"\s+from comtypes import CLSCTX_ALL\n"
        r"\s+from pycaw\.pycaw import AudioUtilities, IAudioEndpointVolume\n"
        r"\s+HAS_PYCAW = True\n"
        r"except Exception:\n"
        r"\s+HAS_PYCAW = False\n"
    )
    match = pattern.search(source)
    if not match:
        return source

    replacement = textwrap.dedent(
        '''
        # NETO_FAST_START_NO_PYCAW_IMPORT_V4
        # Pycaw + comtypes açılışta yüklenmez. Projedeki ctypes CoreAudio yedeği
        # ses seviyesi işlemlerini zaten karşılar.
        from ctypes import cast, POINTER
        CLSCTX_ALL = 23
        AudioUtilities = None
        IAudioEndpointVolume = None
        HAS_PYCAW = False
        '''
    ).strip("\n") + "\n"
    source = source[:match.start()] + replacement + source[match.end():]
    changes.append("Pycaw/comtypes başlangıç importu kaldırıldı")
    return source


def patch_visible_real_window(source: str, changes: List[str]) -> str:
    if "NETO_REAL_WINDOW_FIRST_V4" in source:
        return source

    pattern = re.compile(
        r"(?ms)^    NETO_LAUNCH_LOADING_WINDOW = None\n"
        r"    try:\n"
        r"        root\.withdraw\(\)\n"
        r"        root\.attributes\(\"-alpha\", 1\.0\)\n"
        r"    except Exception:\n"
        r"        pass\n\n"
        r"    def _neto_launch_checkpoint\(status=None, force=False\):\n"
        r"        try:\n"
        r"            if status:\n"
        r"                print\(f\"\[LAUNCH_BUILD\] \{status\}\", flush=True\)\n"
        r"        except Exception:\n"
        r"            pass\n"
    )
    match = pattern.search(source)
    if not match:
        raise RuntimeError("Gizli başlangıç kapısı bloğu bulunamadı.")
    replacement = textwrap.dedent(VISIBLE_BOOT_BLOCK).strip("\n") + "\n"
    source = source[:match.start()] + replacement + source[match.end():]
    changes.append("Gerçek NetOps penceresi UI kurulumu tamamlanmadan gösteriliyor")
    return source


def patch_defer_logo(source: str, changes: List[str]) -> str:
    marker = "NETO_DEFER_MAIN_LOGO_V4"
    if marker in source:
        return source

    target = "    ana_gif_oynat()\n"
    if target not in source:
        return source

    replacement = '''    # NETO_DEFER_MAIN_LOGO_V4\n    # Logo dosyaları ana pencere görünene kadar açılmaz.\n    try:\n        gif_ana_label.configure(\n            text=\"NETO\",\n            image=None,\n            text_color=aktif_palet[\"text_main\"],\n            font=(\"Segoe UI Semibold\", 24),\n        )\n    except Exception:\n        pass\n'''
    source = source.replace(target, replacement, 1)
    changes.append("Ana logo karelerinin yüklenmesi mainloop sonrasına taşındı")
    return source


def patch_finish_overlay(source: str, changes: List[str]) -> str:
    marker = "NETO_REAL_WINDOW_READY_V4"
    if marker in source:
        return source

    old = '''        _neto_launch_checkpoint("Açıldı" if str(dil_getir()).lower() == "tr" else "Opened", force=True)\n        neto_time_log("ana arayüz hazır")\n'''
    if old not in source:
        raise RuntimeError("Ana arayüz hazır işareti bulunamadı.")

    new = '''        _neto_launch_checkpoint("Açıldı" if str(dil_getir()).lower() == "tr" else "Opened", force=True)\n        # NETO_REAL_WINDOW_READY_V4\n        try:\n            if _NETO_FAST_REAL_OVERLAY is not None and _NETO_FAST_REAL_OVERLAY.winfo_exists():\n                _NETO_FAST_REAL_OVERLAY.destroy()\n            root.update_idletasks()\n            root.update()\n        except Exception:\n            pass\n        try:\n            root.after(700, ana_gif_oynat)\n        except Exception:\n            pass\n        neto_time_log("ana arayüz hazır")\n'''
    source = source.replace(old, new, 1)
    changes.append("Hazırlık örtüsü gerçek arayüz hazır olunca kaldırılıyor")
    return source


def patch_service_delays(source: str, changes: List[str]) -> str:
    replacements = {
        'root.after(4500, lambda: threading.Thread(target=sunucuyu_arka_planda_baslat, daemon=True, name="NetoLocalAPI").start())':
        'root.after(15000, lambda: threading.Thread(target=sunucuyu_arka_planda_baslat, daemon=True, name="NetoLocalAPI").start())',
        'root.after(5200, now_playing_safe_start)': 'root.after(12000, now_playing_safe_start)',
        'root.after(6500, _neto_start_update_services)': 'root.after(16000, _neto_start_update_services)',
        'root.after(7200, _neto_model_adini_gec_yukle)': 'root.after(18000, _neto_model_adini_gec_yukle)',
        'root.after(9500, _neto_android_watch_deferred)': 'root.after(22000, _neto_android_watch_deferred)',
    }
    count = 0
    for old, new in replacements.items():
        if old in source:
            source = source.replace(old, new)
            count += 1
    if count:
        changes.append(f"{count} arka plan servisi daha ileri ertelendi")
    return source


def patch_minimize_startup_animations(source: str, changes: List[str]) -> str:
    # Başlangıçta iki kez sürüm metni taraması yapmak gereksizdir.
    old = '''        try:\n            root.after(80, _neto_surumu_arayuze_zorla_uygula)\n            root.after(900, _neto_surumu_arayuze_zorla_uygula)\n        except Exception:\n            pass\n'''
    new = '''        try:\n            root.after(1800, _neto_surumu_arayuze_zorla_uygula)\n        except Exception:\n            pass\n'''
    if old in source:
        source = source.replace(old, new, 1)
        changes.append("Çift başlangıç sürüm taraması tek ve geç çalışacak hale getirildi")
    return source


def patch_source(source: str) -> Tuple[str, List[str]]:
    changes: List[str] = []
    source = patch_disable_second_python_splash(source, changes)
    source = patch_lazy_neto_ui(source, changes)
    source = patch_disable_pycaw_eager_import(source, changes)
    source = patch_visible_real_window(source, changes)
    source = patch_defer_logo(source, changes)
    source = patch_finish_overlay(source, changes)
    source = patch_service_delays(source, changes)
    source = patch_minimize_startup_animations(source, changes)
    return source, changes


def static_tests(source: str) -> List[str]:
    errors: List[str] = []
    try:
        compile(source, "asistan beta.py", "exec")
    except Exception as exc:
        errors.append(f"Python compile: {exc}")
        return errors

    try:
        ast.parse(source)
    except Exception as exc:
        errors.append(f"AST parse: {exc}")

    required = [
        "NETO_REAL_WINDOW_FIRST_V4",
        "NETO_REAL_WINDOW_READY_V4",
        "NETO_DEFER_MAIN_LOGO_V4",
        "NETO_FAST_START_NO_PYCAW_IMPORT_V4",
        "gerçek NetOps penceresi görünür",
        "root.after(700, ana_gif_oynat)",
    ]
    for marker in required:
        if marker not in source:
            errors.append(f"Eksik işaret: {marker}")

    if "_NETO_FAST_SPLASH_PROCESS = _neto_fast_splash_start()" in source:
        errors.append("İkinci Python splash süreci hâlâ etkin")
    if re.search(r"(?m)^from neto_ui import run_launch_gate$", source):
        errors.append("neto_ui hâlâ eager import ediliyor")
    if "from pycaw.pycaw import AudioUtilities" in source:
        errors.append("pycaw hâlâ eager import ediliyor")
    if re.search(r"NETO_LAUNCH_LOADING_WINDOW = None\s+try:\s+root\.withdraw\(\)", source):
        errors.append("Ana pencere hâlâ tam UI kurulana kadar gizleniyor")

    return errors


def write_report(project: Path, backup_path: Path, changes: List[str], errors: List[str]) -> None:
    lines = [
        "NETO ASİSTAN 5 SANİYE HEDEF HIZ RAPORU v4",
        f"Yapı: {PATCH_BUILD}",
        f"Tarih: {dt.datetime.now().isoformat(timespec='seconds')}",
        f"Proje: {project}",
        f"Yedek: {backup_path}",
        "",
        "UYGULANANLAR:",
    ]
    lines.extend(f"- {item}" for item in changes)
    lines.extend(["", "TESTLER:"])
    if errors:
        lines.extend(f"- HATA: {error}" for error in errors)
    else:
        lines.extend([
            "- Python compile: GEÇTİ",
            "- AST parse: GEÇTİ",
            "- Gerçek pencereyi erken gösterme: GEÇTİ",
            "- İkinci Python splash kapalı: GEÇTİ",
            "- NetOps UI lazy import: GEÇTİ",
            "- Pycaw/comtypes eager import kapalı: GEÇTİ",
            "- Logo mainloop sonrasına ertelendi: GEÇTİ",
        ])
    lines.extend([
        "",
        "ÖLÇÜM:",
        "Terminalde '[TIME] gerçek NetOps penceresi görünür' satırına bakın.",
        "Bu satır 5.00s altında olmalıdır. Tam widget ağacının hazır olma süresi",
        "ayrıca '[TIME] ana arayüz hazır' satırında gösterilir.",
        "",
        "DÜRÜST SINIR:",
        "Antivirüs taraması, mekanik disk, bozuk Python kurulumu veya çok yavaş",
        "depolama varsa 5 saniye kesin olarak garanti edilemez.",
    ])
    (project / "NETO_5_SANIYE_HIZ_RAPORU.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default="")
    args = parser.parse_args(argv)

    try:
        project = detect_project(args.project)
        main_file = project / "asistan beta.py"
        source, _encoding = read_text(main_file)
        patched, changes = patch_source(source)

        backup_path = backup(main_file)
        errors = static_tests(patched)
        if errors:
            write_report(project, backup_path, changes, errors)
            print("[V4] Statik testler başarısız:", flush=True)
            for error in errors:
                print(f"  - {error}", flush=True)
            return 2

        write_atomic(main_file, patched)

        # İçe aktarılan proje modülleri için pyc önbelleği oluştur. Ana dosya
        # çalışma biçimi değişmez; yalnızca sonraki importların disk maliyeti azalır.
        try:
            import compileall
            compileall.compile_dir(str(project), maxlevels=1, quiet=1, force=False)
        except Exception:
            pass

        write_report(project, backup_path, changes, [])
        print(f"[V4] Proje: {project}", flush=True)
        print(f"[V4] Yedek: {backup_path}", flush=True)
        for change in changes:
            print(f"[V4] {change}", flush=True)
        print("[V4] Tüm statik testler geçti.", flush=True)
        return 0
    except Exception as exc:
        try:
            project = detect_project(args.project)
            report = project / "NETO_5_SANIYE_HIZ_RAPORU.txt"
            report.write_text(
                "V4 KURULUM HATASI\n\n" + str(exc) + "\n\n" + traceback.format_exc(),
                encoding="utf-8",
            )
        except Exception:
            pass
        print(f"[V4_ERROR] {exc}", file=sys.stderr, flush=True)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
