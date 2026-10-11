# asistan_beta.py (Modüler Yapı, Daha Akıllı Son Sürüm + NetOps Agent + Chat Penceresi)
import asyncio
import datetime
import threading
import traceback
import os
import sys
import re
import shutil
import json
import webbrowser
import difflib
import time
import queue
import math
from typing import Any, cast


def _neto_detach_terminal_for_gui():
    """Main GUI should not talk to the launching terminal in normal use."""
    try:
        if os.name != "nt":
            return
        if os.environ.get("NETOPS_KEEP_CONSOLE") == "1":
            return
        worker_flags = {
            "-c",
            "--neto-live-worker",
            "--netops-automation-worker",
            "--neto-wake-bridge",
            "--neto-install-wake",
        }
        if any(arg in worker_flags for arg in sys.argv[1:]):
            return

        os.makedirs("logs", exist_ok=True)
        log_path = os.path.join("logs", "terminal_detached.log")
        stream = open(log_path, "a", encoding="utf-8", buffering=1)
        sys.stdout = stream
        sys.stderr = stream

        try:
            import ctypes

            ctypes.windll.kernel32.FreeConsole()
        except Exception:
            pass
        print(f"\n[DETACHED] {datetime.datetime.now().isoformat(timespec='seconds')} NetOps GUI started.", flush=True)
    except Exception:
        pass


_neto_detach_terminal_for_gui()

# Verified component paths are inserted before built-in modules so a GitHub
# driver becomes active only after the next clean application start.
try:
    from neto_component_updater import activate_installed_components
    _NETO_ACTIVE_COMPONENTS = activate_installed_components()
except Exception as _neto_component_boot_error:
    _NETO_ACTIVE_COMPONENTS = {"active": {}, "inserted": [], "error": str(_neto_component_boot_error)}
    print(f"[COMPONENT_BOOT] {_neto_component_boot_error}", flush=True)

try:
    from neto_user_profiles import (
        apply_profile as _neto_profile_apply,
        get_active_profile as _neto_profile_active,
        profile_definitions as _neto_profile_definitions,
    )
except Exception as _neto_profile_boot_error:
    _neto_profile_apply = None
    _neto_profile_active = lambda: "balanced"
    _neto_profile_definitions = lambda: {}
    print(f"[PROFILE_BOOT] {_neto_profile_boot_error}", flush=True)

try:
    from neto_reminders import (
        DEFAULT_SOUND_NAME as _NETO_REMINDER_SOUND_NAME,
        REPEAT_LABELS as _NETO_REMINDER_REPEAT_LABELS,
        ReminderService as _NetoReminderService,
        parse_schedule as _neto_reminder_parse_schedule,
        play_reminder_sound as _neto_play_reminder_sound,
    )
except Exception as _neto_reminder_boot_error:
    _NETO_REMINDER_SOUND_NAME = "netops_reminder.wav"
    _NETO_REMINDER_REPEAT_LABELS = {"once": "Bir kez"}
    _NetoReminderService = None
    _neto_reminder_parse_schedule = None
    _neto_play_reminder_sound = lambda *_args, **_kwargs: False
    print(f"[REMINDER_BOOT] {_neto_reminder_boot_error}", flush=True)

try:
    from neto_now_playing_driver import interval as _neto_now_playing_interval
except Exception:
    def _neto_now_playing_interval(_name, default):
        return default

try:
    from neto_tray import (
        TRAY_AKTIF as _NETO_TRAY_AKTIF,
        tray_baslat as _neto_tray_baslat,
        tray_durdur as _neto_tray_durdur,
    )
except Exception as _neto_tray_boot_error:
    _NETO_TRAY_AKTIF = False

    def _neto_tray_baslat(*_args, **_kwargs):
        return False

    def _neto_tray_durdur():
        pass
    print(f"[TRAY] pystray yok, sistem tepsisi kapali (pip install pystray): {_neto_tray_boot_error}", flush=True)

# ------------------------------------------------------------
# ISOLATED NETO LIVE WORKER BOOTSTRAP
# PyInstaller/EXE worker mode must exit before Tk, Qt, Flask or AI modules load.
# This keeps native Whisper/CTranslate2 DLLs outside the main UI process.
# ------------------------------------------------------------
# PyInstaller frozen children use ``NetOps.exe -c <code>`` for dependency probes
# and multiprocessing bootstrap. Execute child code without starting another GUI.
if len(sys.argv) >= 3 and sys.argv[1] == "-c":
    try:
        exec(sys.argv[2], {"__name__": "__main__"})
    except BaseException as _neto_frozen_child_error:
        try:
            print(f"NETO_FROZEN_CHILD_ERROR: {_neto_frozen_child_error}", file=sys.stderr, flush=True)
        except Exception:
            pass
    raise SystemExit(0)

if "--neto-live-worker" in sys.argv:
    try:
        from neto_live_mode import run_worker_from_argv as _neto_live_worker_run
        raise SystemExit(_neto_live_worker_run(sys.argv))
    except SystemExit:
        raise
    except BaseException as _neto_live_worker_boot_error:
        try:
            print(f"NETO_LIVE_WORKER_BOOT_ERROR: {_neto_live_worker_boot_error}", file=sys.stderr, flush=True)
            traceback.print_exc()
        except Exception:
            pass
        raise SystemExit(70)

# ------------------------------------------------------------
# EXE AUTOMATION WORKER BOOTSTRAP
# Handle this before any GUI setup so scheduler children never create a window.
if "--netops-automation-worker" in sys.argv:
    try:
        sys.argv = [arg for arg in sys.argv if arg != "--netops-automation-worker"]
        from neto_automation_worker import main as _netops_worker_run
        raise SystemExit(_netops_worker_run())
    except SystemExit:
        raise
    except BaseException as _netops_worker_boot_error:
        try:
            print(f"NETOPS_AUTOMATION_WORKER_BOOT_ERROR: {_netops_worker_boot_error}", file=sys.stderr, flush=True)
            traceback.print_exc()
        except Exception:
            pass
        raise SystemExit(70)

# ------------------------------------------------------------
# PERFORMANCE TIMER / TERMINAL SPEED LOG
# ------------------------------------------------------------
# ------------------------------------------------------------
# LAN WAKE BRIDGE BOOTSTRAP
# The bridge runs without creating the main Tk window and accepts only
# token-protected wake requests from the local network.
if "--neto-wake-bridge" in sys.argv:
    try:
        from neto_wake_bridge import main as _neto_wake_bridge_main
        raise SystemExit(_neto_wake_bridge_main(sys.argv[1:]))
    except SystemExit:
        raise
    except BaseException as _neto_wake_bridge_error:
        print(f"NETO_WAKE_BRIDGE_ERROR: {_neto_wake_bridge_error}", file=sys.stderr, flush=True)
        raise SystemExit(71)

if "--neto-install-wake" in sys.argv:
    try:
        from neto_wake_bridge import install_startup as _neto_install_wake
        raise SystemExit(_neto_install_wake(start_now=True))
    except SystemExit:
        raise
    except BaseException as _neto_install_wake_error:
        print(f"NETO_WAKE_INSTALL_ERROR: {_neto_install_wake_error}", file=sys.stderr, flush=True)
        raise SystemExit(72)

NETO_WAKE_LAUNCH = "--neto-wake" in sys.argv
NETO_PERF_START = time.perf_counter()

NETO_START_TIME_FOR_STARTUP_FIX = time.time()
def neto_startup_phase(seconds=10):
    try:
        return (time.time() - NETO_START_TIME_FOR_STARTUP_FIX) < seconds
    except Exception:
        return False


def neto_time_log(ad):
    try:
        print(f"[TIME] {ad}: {time.perf_counter() - NETO_PERF_START:.2f}s", flush=True)
    except Exception:
        pass

neto_time_log("asistan beta.py başladı")
NETO_STARTUP_FIX_VERSION = "14.6-ui-motion-single-settings-gear"
print(f"[BOOT] Startup fix: {NETO_STARTUP_FIX_VERSION}", flush=True)
import subprocess
import tempfile
from pathlib import Path
import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog, messagebox

# ------------------------------------------------------------
# CUSTOMTKINTER CTkTextbox DESTROY/AFTER GUARD
#
# CTkTextbox kendi scrollbar durumunu belirli araliklarla ``after`` ile
# kontrol eder. Gömülü NetOps çalışma alanı kapatıldığında Tcl alt-widget'i
# parent ile birlikte yok olabilir; CustomTkinter'ın önceden planlanmış
# callback'i ise bir kez daha çalışıp ``invalid command name ...!text``
# TclError üretebilir. Bu koruma, yok edilmiş textbox üzerinde callback'in
# devam etmesini engeller. Normal/yaşayan textbox davranışını değiştirmez.
# ------------------------------------------------------------
def _neto_patch_ctk_textbox_after_guard():
    try:
        textbox_cls = getattr(ctk, "CTkTextbox", None)
        original = getattr(textbox_cls, "_check_if_scrollbars_needed", None)
        if textbox_cls is None or not callable(original):
            return False
        if getattr(original, "_neto_destroy_guard", False):
            return True

        def _safe_check(self, *args, **kwargs):
            try:
                if not bool(self.winfo_exists()):
                    return None
                inner = getattr(self, "_textbox", None)
                if inner is not None and not bool(inner.winfo_exists()):
                    return None
            except tk.TclError:
                return None
            try:
                return original(self, *args, **kwargs)
            except tk.TclError as exc:
                # Destroy edilmiş Tcl widget'ına ait gecikmiş callback.
                if "invalid command name" in str(exc).lower():
                    return None
                raise

        _safe_check._neto_destroy_guard = True
        _safe_check._neto_original = original
        setattr(textbox_cls, "_check_if_scrollbars_needed", _safe_check)
        return True
    except Exception as exc:
        try:
            print(f"[CTK_TEXTBOX_GUARD] {exc}", flush=True)
        except Exception:
            pass
        return False

_NETO_CTK_TEXTBOX_GUARD_ACTIVE = _neto_patch_ctk_textbox_after_guard()
from PIL import Image, ImageTk, ImageDraw, ImageSequence
import multiprocessing
from flask import Flask, jsonify, request
import logging
import importlib
import ctypes

# Ağır ve yalnızca özellik kullanıldığında gereken modüller başlangıçta yüklenmez.
# Böylece açılış ekranından ana menüye geçerken UI thread uzun süre bloke olmaz.
_NETO_LAZY_MODULES = {}
_NETO_LAZY_LOCK = threading.RLock()

def _neto_lazy_import(module_name):
    with _NETO_LAZY_LOCK:
        module = _NETO_LAZY_MODULES.get(module_name)
        if module is None:
            module = importlib.import_module(module_name)
            _NETO_LAZY_MODULES[module_name] = module
        return module


def _neto_arduino_bildirim(event):
    """Show UNO/CH340 connection changes without blocking the UI."""
    try:
        event_type = str(event.get("type", ""))
        port = str(event.get("port", "") or "")
        if event_type == "arduino":
            if event.get("connected"):
                message = f"Arduino UNO algılandı ({port}). Sensör bağlantısı bekleniyor."
            else:
                message = "Arduino UNO bağlantısı kesildi. Yeniden bağlanınca tekrar denenecek."
        elif event_type == "presence":
            if event.get("presence"):
                messages = ("Hoş geldin!", "Seni gördüm, hoş geldin.", "Yaklaştığını fark ettim.", "NetOps burada, hoş geldin!")
                message = messages[int(time.time()) % len(messages)]
            else:
                message = "Görüşürüz, uzaklaştığını fark ettim."
        else:
            return
        print(f"[ARDUINO_EVENT] {message}", flush=True)
        app_root = globals().get("root")
        if app_root is not None:
            app_root.after(0, lambda: animasyonlu_yazi(message))
    except Exception as exc:
        print(f"[ARDUINO_EVENT_ERROR] {exc}", flush=True)


def _neto_arduino_izleyicisini_baslat():
    try:
        module = _neto_lazy_import("neto_arduino_sensor")
        module.start(_neto_arduino_bildirim, logger=lambda msg: print(msg, flush=True))
    except Exception as exc:
        print(f"[ARDUINO_START_ERROR] {exc}", flush=True)

class _NetoLazyModule:
    def __init__(self, module_name):
        self._module_name = module_name
    def __getattr__(self, name):
        return getattr(_neto_lazy_import(self._module_name), name)

def neto_chat_ac(*args, **kwargs):
    return _neto_lazy_import("neto_chat").neto_chat_ac(*args, **kwargs)

neto_time_log("lazy modül köprüsü hazır")

# ------------------------------------------------------------
# MODÜLLERDEN İMPORT
# ------------------------------------------------------------
import crash_guard
crash_guard.install("NetOps")
from config import *                           # Tüm yollar, sabitler, paletler
from temalar import tema_uygula as _temalar_tema_uygula, aktif_palet
import temalar as _temalar_modulu
from neto_modern_ui import input_icon as _neto_input_icon

# ------------------------------------------------------------
# NETO TEMA + VURGU MOTORU
# Koyu/açık tema birbirinden ayrıdır. Vurgu rengi yalnızca seçili
# kontrolleri, kenarlıkları ve ana eylem düğmelerini renklendirir.
# ------------------------------------------------------------
_orijinal_tema_uygula = _temalar_tema_uygula
NETO_TEMA_TABAN_PALETLERI = {
    "dark": {
        "bg": "#09090B",
        "sidebar": "#111114",
        "card": "#1B1B20",
        "entry_bg": "#141418",
        "entry_border": "#34343C",
        "text_main": "#F4F4F5",
        "text_dim": "#A1A1AA",
        "button_hover": "#2A2A31",
    },
    "light": {
        "bg": "#F4F5F7",
        "sidebar": "#FFFFFF",
        "card": "#E8EAEF",
        "entry_bg": "#FFFFFF",
        "entry_border": "#C8CDD6",
        "text_main": "#18181B",
        "text_dim": "#64646F",
        "button_hover": "#D9DDE5",
    },
}

NETO_VURGU_RENKLERI = {
    "green": "#22C55E",
    "blue": "#3B82F6",
    "dark-blue": "#2563EB",
    "purple": "#8B5CF6",
    "violet": "#8B5CF6",
    "pink": "#EC4899",
    "red": "#EF4444",
    "orange": "#F97316",
    "yellow": "#EAB308",
    "teal": "#14B8A6",
    "cyan": "#06B6D4",
}

NETO_LIQUID_GLASS_TABAN_PALETLERI = SURFACE_PALETS.get("liquid-glass", {
    "dark": {
        "bg": "#070B16",
        "sidebar": "#0C1430",
        "card": "#101B38",
        "entry_bg": "#0D1730",
        "entry_border": "#5C89FF",
        "text_main": "#F7FAFF",
        "text_dim": "#B8C3E0",
        "button_fg": "#14274D",
        "button_hover": "#1D3465",
        "button_text": "#F7FAFF",
        "neon": "#72A7FF",
    },
    "light": {
        "bg": "#EEF4FF",
        "sidebar": "#F7FAFF",
        "card": "#FFFFFF",
        "entry_bg": "#F4F8FF",
        "entry_border": "#7A9DFF",
        "text_main": "#10203A",
        "text_dim": "#5A6780",
        "button_fg": "#E5EEFF",
        "button_hover": "#D8E6FF",
        "button_text": "#10203A",
        "neon": "#2F6BFF",
    },
})


def _neto_tema_adi(secim=None):
    deger = str(secim or "dark").strip().lower()
    if deger in {"light", "açık", "acik", "white", "beyaz"}:
        return "light"
    return "dark"


def _neto_arayuz_stili(secim=None):
    deger = str(secim or "classic").strip().lower()
    aliases = {
        "glass": "liquid-glass",
        "liquid glass": "liquid-glass",
        "liquid_glass": "liquid-glass",
        "sıvı cam": "liquid-glass",
        "sivi cam": "liquid-glass",
        "cam": "liquid-glass",
        "experians 2.5": "experians",
        "neto experians": "experians",
        "experians": "experians",
        "klasik": "classic",
    }
    deger = aliases.get(deger, deger)
    try:
        valid = {str(x).strip().lower() for x in VALID_SURFACE_STYLES}
    except Exception:
        valid = {"classic", "liquid-glass", "experians"}
    if deger in valid:
        return deger
    return "classic"


def _neto_hafizadan_tema_oku():
    data = {"tema": "light", "renk_temasi": "blue", "arayuz_stili": "experians"}
    try:
        if os.path.exists(FILE_PATH):
            with open(FILE_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                data.update(loaded)
    except Exception:
        pass
    return data


def _neto_vurgu_adi(secim=None):
    deger = str(secim or "green").strip().lower()
    aliases = {
        "dark_blue": "dark-blue", "darkblue": "dark-blue",
        "mor": "purple", "pembe": "pink", "kırmızı": "red", "kirmizi": "red",
        "turuncu": "orange", "sarı": "yellow", "sari": "yellow",
        "yeşil": "green", "yesil": "green", "mavi": "blue",
    }
    deger = aliases.get(deger, deger)
    try:
        valid = {str(x).strip().lower() for x in VALID_COLOR_THEMES}
    except Exception:
        valid = set(NETO_VURGU_RENKLERI)
    if deger in valid or deger in NETO_VURGU_RENKLERI:
        return deger
    return "green"


def _neto_hex_karistir(hex_renk, hedef="#000000", oran=0.18):
    try:
        a = hex_renk.lstrip("#")
        b = hedef.lstrip("#")
        rgb_a = [int(a[i:i+2], 16) for i in (0, 2, 4)]
        rgb_b = [int(b[i:i+2], 16) for i in (0, 2, 4)]
        out = [round(x + (y - x) * float(oran)) for x, y in zip(rgb_a, rgb_b)]
        return "#" + "".join(f"{max(0, min(255, v)):02X}" for v in out)
    except Exception:
        return hex_renk


def _neto_kontrast_metin(hex_renk):
    try:
        h = str(hex_renk).lstrip("#")
        r, g, b = [int(h[i:i+2], 16) for i in (0, 2, 4)]
        parlaklik = (0.299 * r) + (0.587 * g) + (0.114 * b)
        return "#111114" if parlaklik >= 155 else "#FFFFFF"
    except Exception:
        return "#FFFFFF"


def _neto_palet_uret(mod, vurgu_adi, arayuz_stili="classic"):
    stil = _neto_arayuz_stili(arayuz_stili)
    taban_haritasi = {
        "classic": NETO_TEMA_TABAN_PALETLERI,
        "liquid-glass": NETO_LIQUID_GLASS_TABAN_PALETLERI,
        "experians": SURFACE_PALETS.get("experians", NETO_LIQUID_GLASS_TABAN_PALETLERI),
    }
    tabanlar = taban_haritasi.get(stil, NETO_TEMA_TABAN_PALETLERI)
    palet = dict(tabanlar.get(mod, NETO_TEMA_TABAN_PALETLERI[mod]))
    vurgu = NETO_VURGU_RENKLERI.get(vurgu_adi)
    if not vurgu:
        # CustomTkinter'a sonradan eklenen tema adlarında güvenli varsayılan.
        vurgu = NETO_VURGU_RENKLERI["green"]
    hover_hedef = "#FFFFFF" if mod == "dark" else "#000000"
    palet.update({
        "neon": vurgu,
        "accent": vurgu,
        "accent_hover": _neto_hex_karistir(vurgu, hover_hedef, 0.16),
        "accent_text": _neto_kontrast_metin(vurgu),
        "button_fg": palet["card"],
        "button_text": palet["text_main"],
    })
    return palet


_NETO_TEMA_DURUM = {
    "mod": None,
    "vurgu": None,
    "stil": None,
    "taban_hazir": False,
    "ctk_mod": None,
    "appearance_job": None,
    "appearance_cover": None,
}
_NETO_SCROLLABLE_REPAIR_STATE = {"token": 0}


def _neto_global_appearance_gecis(mod):
    """CustomTkinter iç bileşenlerini tutarlı biçimde yeni moda geçirir.

    OptionMenu açılır listesi ve ScrollableFrame canvas gibi CTk'nin kendi
    oluşturduğu parçalar yalnızca global appearance modu değişirse doğru renk
    alır. Geçiş sırasında eski tema renginde tek parça bir örtü gösterilir;
    ara siyah/beyaz kareler kullanıcıya yansıtılmaz.
    """
    root_obj = globals().get("root")
    hedef = "light" if mod == "light" else "dark"
    if root_obj is None or not _neto_ui_hazir_mi():
        try:
            ctk.set_appearance_mode("Light" if hedef == "light" else "Dark")
            _NETO_TEMA_DURUM["ctk_mod"] = hedef
        except Exception:
            pass
        return

    try:
        old_job = _NETO_TEMA_DURUM.get("appearance_job")
        if old_job:
            root_obj.after_cancel(old_job)
    except Exception:
        pass

    try:
        old_cover = _NETO_TEMA_DURUM.get("appearance_cover")
        if old_cover is not None and old_cover.winfo_exists():
            old_cover.destroy()
    except Exception:
        pass

    onceki_mod = _NETO_TEMA_DURUM.get("ctk_mod") or ("light" if hedef == "dark" else "dark")
    onceki_bg = NETO_TEMA_TABAN_PALETLERI.get(onceki_mod, NETO_TEMA_TABAN_PALETLERI[hedef])["bg"]
    try:
        cover = tk.Frame(root_obj, bg=onceki_bg, bd=0, highlightthickness=0)
        cover.place(x=0, y=0, relwidth=1, relheight=1)
        cover.lift()
        _NETO_TEMA_DURUM["appearance_cover"] = cover
    except Exception:
        cover = None

    def _uygula():
        _NETO_TEMA_DURUM["appearance_job"] = None
        try:
            ctk.set_appearance_mode("Light" if hedef == "light" else "Dark")
            _NETO_TEMA_DURUM["ctk_mod"] = hedef
        except Exception as exc:
            try:
                print(f"[CTK_APPEARANCE_ERROR] {exc}", flush=True)
            except Exception:
                pass

        try:
            planla = globals().get("_neto_tema_yenile_planla")
            if callable(planla):
                planla(settings=True, delay=0)
            else:
                yenile = globals().get("arayuz_renklerini_yenile")
                if callable(yenile):
                    yenile()
        except Exception:
            pass

        def _ortuyu_kaldir():
            current = _NETO_TEMA_DURUM.get("appearance_cover")
            _NETO_TEMA_DURUM["appearance_cover"] = None
            try:
                if current is not None and current.winfo_exists():
                    current.destroy()
            except Exception:
                pass
            try:
                root_obj.lift()
            except Exception:
                pass

        try:
            root_obj.after(140, _ortuyu_kaldir)
        except Exception:
            _ortuyu_kaldir()

    try:
        _NETO_TEMA_DURUM["appearance_job"] = root_obj.after_idle(_uygula)
    except Exception:
        _uygula()


def _neto_tema_kaydet(mod, vurgu_adi, arayuz_stili=None):
    """Tema dosyasını yalnızca gerçek değer değiştiğinde yazar."""
    try:
        data = _neto_hafizadan_tema_oku()
        stil_adi = _neto_arayuz_stili(arayuz_stili if arayuz_stili is not None else data.get("arayuz_stili", "experians"))
        if (
            data.get("tema") == mod
            and data.get("renk_temasi") == vurgu_adi
            and data.get("arayuz_stili") == stil_adi
        ):
            return False
        data["tema"] = mod
        data["renk_temasi"] = vurgu_adi
        data["arayuz_stili"] = stil_adi
        folder = os.path.dirname(FILE_PATH)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except Exception:
        return False


def _neto_ui_hazir_mi():
    try:
        root_obj = globals().get("root")
        main_obj = globals().get("main_c")
        return bool(root_obj is not None and main_obj is not None and root_obj.winfo_exists())
    except Exception:
        return False


def _neto_aktif_paleti_yaz(palet):
    hedefler = [aktif_palet, getattr(_temalar_modulu, "aktif_palet", None)]
    gorulen = set()
    for hedef in hedefler:
        if not isinstance(hedef, dict) or id(hedef) in gorulen:
            continue
        gorulen.add(id(hedef))
        hedef.clear()
        hedef.update(palet)
    try:
        _temalar_modulu.aktif_palet = aktif_palet
    except Exception:
        pass


def _neto_scrollable_frame_renklendir(widget, palet=None, bg_key="sidebar"):
    """CTkScrollableFrame'in iç canvas rengini de aktif palete eşitler."""
    palet = palet or aktif_palet
    bg = palet.get(bg_key) or palet.get("bg", "#09090B")
    scroll = palet.get("entry_border", palet.get("card", bg))
    hover = palet.get("button_hover", scroll)
    try:
        widget.configure(
            fg_color=bg,
            scrollbar_button_color=scroll,
            scrollbar_button_hover_color=hover,
        )
    except Exception:
        pass
    try:
        parent_frame = getattr(widget, "_parent_frame", None)
        if parent_frame is not None:
            parent_frame.configure(fg_color=bg)
    except Exception:
        pass
    try:
        parent_canvas = getattr(widget, "_parent_canvas", None)
        if parent_canvas is not None:
            parent_canvas.configure(bg=bg, highlightthickness=0)
    except Exception:
        pass
    try:
        scrollbar = getattr(widget, "_scrollbar", None)
        if scrollbar is not None:
            scrollbar.configure(
                fg_color=bg,
                button_color=scroll,
                button_hover_color=hover,
            )
    except Exception:
        pass


def _neto_scrollable_frame_renklendir_planla(delays=(40, 160, 360)):
    """CTk appearance geçişinden sonra beyaz kalan iç canvas'ları tekrar boyar."""
    root_obj = globals().get("root")
    _NETO_SCROLLABLE_REPAIR_STATE["token"] += 1
    token = _NETO_SCROLLABLE_REPAIR_STATE["token"]

    def _repair_once():
        if token != _NETO_SCROLLABLE_REPAIR_STATE.get("token"):
            return
        for name, bg_key in (
            ("sidebar_content", "sidebar"),
            ("agent_sidebar_content", "sidebar"),
            ("store_apps_frame", "bg"),
        ):
            try:
                widget = globals().get(name)
                if widget is not None and widget.winfo_exists():
                    _neto_scrollable_frame_renklendir(widget, aktif_palet, bg_key)
            except Exception:
                pass

    if root_obj is None:
        _repair_once()
        return

    _repair_once()
    for delay in delays:
        try:
            root_obj.after(max(0, int(delay)), _repair_once)
        except Exception:
            pass


def tema_uygula(secim=None, renk_temasi=None, arayuz_stili=None):
    """Donmadan koyu/açık tema ve vurgu uygular.

    Ağır CustomTkinter görünüm değişimi yalnızca koyu/açık mod gerçekten
    değiştiğinde çalışır. Vurgu değişiminde bütün CTk widget ağacı yeniden
    çizilmez; yalnızca Neto paleti güncellenip tek bir birleştirilmiş UI turu
    planlanır.
    """
    ayar = _neto_hafizadan_tema_oku()
    raw = str(secim).strip().lower() if secim is not None else ""
    tema_degerleri = {"dark", "light", "koyu", "açık", "acik", "white", "beyaz"}
    stil_degerleri = {"classic", "liquid-glass", "glass", "liquid glass", "sıvı cam", "sivi cam", "cam", "klasik"}
    stil_degerleri.update({"experians", "experians 2.5", "neto experians"})
    if raw and raw in stil_degerleri and arayuz_stili is None and renk_temasi is None:
        arayuz_stili = raw
        secim = None
    elif raw and raw not in tema_degerleri and raw not in stil_degerleri and renk_temasi is None:
        renk_temasi = raw
        secim = None

    mod = _neto_tema_adi(secim if secim is not None else ayar.get("tema", "dark"))
    vurgu_adi = _neto_vurgu_adi(
        renk_temasi if renk_temasi is not None else ayar.get("renk_temasi", "green")
    )
    stil_adi = _neto_arayuz_stili(
        arayuz_stili if arayuz_stili is not None else ayar.get("arayuz_stili", "experians")
    )

    onceki_mod = _NETO_TEMA_DURUM.get("mod")
    onceki_vurgu = _NETO_TEMA_DURUM.get("vurgu")
    onceki_stil = _NETO_TEMA_DURUM.get("stil")
    mod_degisti = onceki_mod != mod
    vurgu_degisti = onceki_vurgu != vurgu_adi
    stil_degisti = onceki_stil != stil_adi
    ui_hazir = _neto_ui_hazir_mi()

    # Projenin eski tema motorunu yalnızca UI kurulmadan önce bir kez çalıştır.
    # Çalışma anında tekrar çağırmak CTk appearance + tüm widget taramasını ikiye
    # katlayıp Windows'un "Yanıt vermiyor" göstermesine neden oluyordu.
    if not ui_hazir and not _NETO_TEMA_DURUM.get("taban_hazir"):
        eski_ok = False
        try:
            _orijinal_tema_uygula(mod, vurgu_adi, stil_adi)
            eski_ok = True
        except TypeError:
            try:
                _orijinal_tema_uygula(mod)
                eski_ok = True
            except Exception:
                pass
        except Exception:
            pass
        if not eski_ok:
            try:
                ctk.set_appearance_mode("Light" if mod == "light" else "Dark")
            except Exception:
                pass
        _NETO_TEMA_DURUM["taban_hazir"] = True
        _NETO_TEMA_DURUM["ctk_mod"] = mod
    elif mod_degisti:
        # CTk'nin dahili canvas/dropdown parçaları da yeni modu almalı. Geçiş
        # tek renkli örtü arkasında yapıldığı için kullanıcı ara kare görmez.
        _neto_global_appearance_gecis(mod)

    palet = _neto_palet_uret(mod, vurgu_adi, stil_adi)
    _neto_aktif_paleti_yaz(palet)
    _NETO_TEMA_DURUM["mod"] = mod
    _NETO_TEMA_DURUM["vurgu"] = vurgu_adi
    _NETO_TEMA_DURUM["stil"] = stil_adi
    _NETO_TEMA_DURUM["gecis_aktif"] = bool(ui_hazir and (mod_degisti or vurgu_degisti or stil_degisti))
    _neto_tema_kaydet(mod, vurgu_adi, stil_adi)

    # Açık Şimdi Çalıyor ekranı ve sol bölüm küçük bir widget grubudur;
    # ana tema turunu beklemeden yeni vurguyu alır.
    if ui_hazir and (mod_degisti or vurgu_degisti or stil_degisti):
        try:
            root_obj = globals().get("root")
            np_apply = globals().get("now_playing_theme_apply")
            if root_obj is not None and callable(np_apply):
                root_obj.after_idle(np_apply)
            if root_obj is not None:
                root_obj.after(180, lambda: _NETO_TEMA_DURUM.__setitem__("gecis_aktif", False))
        except Exception:
            _NETO_TEMA_DURUM["gecis_aktif"] = False
        try:
            _neto_scrollable_frame_renklendir_planla()
        except Exception:
            pass

    # Aynı seçim tekrar geldiyse gereksiz yüzlerce configure çağrısı yapma.
    if ui_hazir and (mod_degisti or vurgu_degisti or stil_degisti):
        try:
            # Tema modu değişiminde global CTk geçişi kendi yenilemesini planlar.
            # Sadece vurgu değiştiyse doğrudan hafif palet turu yeterlidir.
            if not mod_degisti:
                planla = globals().get("_neto_tema_yenile_planla")
                if callable(planla):
                    planla(settings=True, delay=1)
                else:
                    root_obj = globals().get("root")
                    refresh = globals().get("arayuz_renklerini_yenile")
                    if root_obj is not None and callable(refresh):
                        root_obj.after_idle(refresh)
        except Exception:
            pass

    return aktif_palet


def _tema_vurgu_metin_rengi():
    try:
        return _neto_kontrast_metin(aktif_palet.get("neon", "#22C55E"))
    except Exception:
        return "#FFFFFF"
# Browser Engine lazy import: PyQt6/WebEngine açılışta donma yapmasın.
def neto_browser_ac(*args, **kwargs):
    t = time.perf_counter()
    print("[TIME] NetOps Browser lazy import", flush=True)
    from browser_engine import neto_browser_ac as _real_browser
    sonuc = _real_browser(*args, **kwargs)
    print(f"[TIME] NetOps Browser dönüşü: {time.perf_counter() - t:.2f}s", flush=True)
    return sonuc
from ayarlar import (                          # Ayarlar pencereleri
    gelismis_ayarlar_penceresi_ac,
    ozel_ayarlar_penceresi_ac
)
neto_ai = _NetoLazyModule("neto_ai")
_NETO_AUTOPILOT_PENDING = None
import neto_live_mode
neto_weather = _NetoLazyModule("neto_weather")
neto_now_playing = _NetoLazyModule("neto_now_playing")
import neto_security
neto_updater = _NetoLazyModule("neto_updater")
neto_update_ui = _NetoLazyModule("neto_update_ui")
from neto_ui import run_launch_gate
def create_settings_page(*args, **kwargs):
    return _neto_lazy_import("neto_settings_page").create_settings_page(*args, **kwargs)

# PyInstaller tek EXE desteği: NetOps v10.1 Traliçe.exe --live
if "--live" in sys.argv:
    try:
        import neto_live_app
        neto_live_app.main()
    except Exception as e:
        try:
            import tkinter.messagebox as _mb
            _mb.showerror("NetOps Live", f"Live Mode başlatılamadı:\n{e}")
        except Exception:
            print(e)
    sys.exit(0)

def neto_ai_cevap_ver(*args, **kwargs):
    return _neto_lazy_import("neto_ai").neto_ai_cevap_ver(*args, **kwargs)


# Unified in-app Settings bridge.
# Old popup functions remain for backward compatibility, but normal UI routes here.
def ayarlar_sayfasi_ac(section="general"):
    try:
        opener = globals().get("_neto_settings_page_open")
        if callable(opener):
            return bool(opener(section))
    except Exception as exc:
        try:
            print(f"[SETTINGS_PAGE_OPEN_ERROR] {exc}", flush=True)
        except Exception:
            pass
    return False


_NETO_PROFILE_WINDOW = None


def _neto_apply_user_profile(profile_id):
    """Persist a profile and sync safe app-level preferences immediately."""
    if not callable(_neto_profile_apply):
        raise RuntimeError("Profil motoru yüklenemedi.")

    result = _neto_profile_apply(profile_id, source="ui")
    settings = dict(result.get("settings") or {})

    # Keep the existing local settings file as the single startup preference
    # source for the legacy services already used by NetOps.
    try:
        current = veri_yukle()
        current["netops_active_profile"] = result.get("profile", profile_id)
        current["netops_profile_settings"] = settings
        current["live_mode_otomatik_baslat"] = bool(settings.get("live_mode_on_start"))
        current["start_live_mode_on_launch"] = bool(settings.get("live_mode_on_start"))
        current["now_playing_on_start"] = bool(settings.get("now_playing_on_start"))
        current["netops_quiet_mode"] = bool(settings.get("quiet_mode"))
        veri_kaydet(current)
    except Exception as exc:
        result["settings_warning"] = str(exc)

    try:
        from neto_runtime_policy_v2 import set_animation_mode

        result["motion"] = set_animation_mode(str(settings.get("animation_mode") or "normal"))
    except Exception as exc:
        result["motion_warning"] = str(exc)

    # Starting Live Mode is safe to offer immediately; stopping an active
    # session is intentionally left to the user so a profile click cannot
    # unexpectedly interrupt a broadcast.
    if settings.get("live_mode_on_start"):
        callback = globals().get("inline_live_start")
        app_root = globals().get("root")
        try:
            if callable(callback) and app_root is not None:
                app_root.after(0, callback)
        except Exception as exc:
            result["live_warning"] = str(exc)

    return result


def netops_profiller_penceresi_ac():
    """Open the card-based profile picker without blocking the main window."""
    global _NETO_PROFILE_WINDOW
    app_root = globals().get("root")
    if app_root is None:
        return None

    try:
        if _NETO_PROFILE_WINDOW is not None and _NETO_PROFILE_WINDOW.winfo_exists():
            _NETO_PROFILE_WINDOW.lift()
            _NETO_PROFILE_WINDOW.focus_force()
            return _NETO_PROFILE_WINDOW
    except Exception:
        _NETO_PROFILE_WINDOW = None

    palette = dict(globals().get("aktif_palet") or {})
    bg = palette.get("bg", "#09090B")
    card = palette.get("card", "#19191F")
    text_main = palette.get("text_main", "#F5F5F5")
    text_dim = palette.get("text_dim", "#A7A7B2")
    neon = palette.get("neon", "#22C55E")
    hover = palette.get("button_hover", "#292936")

    window = ctk.CTkToplevel(app_root)
    _NETO_PROFILE_WINDOW = window
    window.title("NetOps Profilleri")
    window.geometry("720x560")
    window.minsize(620, 460)
    window.configure(fg_color=bg)
    window.transient(app_root)

    def close_window():
        global _NETO_PROFILE_WINDOW
        _NETO_PROFILE_WINDOW = None
        try:
            window.destroy()
        except Exception:
            pass

    window.protocol("WM_DELETE_WINDOW", close_window)

    ctk.CTkLabel(
        window,
        text="NetOps Profilleri",
        text_color=text_main,
        font=("Segoe UI Semibold", 25),
        anchor="w",
    ).pack(fill="x", padx=28, pady=(24, 2))
    ctk.CTkLabel(
        window,
        text="Tek tıkla NetOps çalışma şeklini değiştir.",
        text_color=text_dim,
        font=("Segoe UI", 12),
        anchor="w",
    ).pack(fill="x", padx=28, pady=(0, 16))

    status = ctk.CTkLabel(
        window,
        text="",
        text_color=neon,
        font=("Segoe UI Semibold", 12),
        anchor="w",
        justify="left",
        wraplength=650,
    )
    status.pack(fill="x", padx=28, pady=(0, 10))

    cards = ctk.CTkScrollableFrame(window, fg_color="transparent")
    cards.pack(fill="both", expand=True, padx=20, pady=(0, 16))

    def render_cards(message=""):
        for child in cards.winfo_children():
            child.destroy()
        active = _neto_profile_active()
        status.configure(text=message or f"Aktif profil: {_neto_profile_definitions().get(active, {}).get('label', active)}")

        for profile_id, info in _neto_profile_definitions().items():
            is_active = profile_id == active
            item = ctk.CTkFrame(
                cards,
                fg_color=neon if is_active else card,
                border_width=1,
                border_color=neon if is_active else palette.get("entry_border", "#30303A"),
                corner_radius=14,
            )
            item.pack(fill="x", padx=8, pady=6)

            left = ctk.CTkFrame(item, fg_color="transparent")
            left.pack(side="left", fill="both", expand=True, padx=16, pady=12)
            ctk.CTkLabel(
                left,
                text=f"{info.get('icon', 'NET')}   {info.get('label', profile_id)}",
                text_color="#000000" if is_active else text_main,
                font=("Segoe UI Semibold", 14),
                anchor="w",
            ).pack(fill="x")
            ctk.CTkLabel(
                left,
                text=str(info.get("description") or ""),
                text_color="#102017" if is_active else text_dim,
                font=("Segoe UI", 11),
                anchor="w",
                justify="left",
                wraplength=470,
            ).pack(fill="x", pady=(4, 0))

            ctk.CTkButton(
                item,
                text="Aktif" if is_active else "Uygula",
                width=96,
                height=34,
                corner_radius=9,
                fg_color="#E7FBEF" if is_active else neon,
                hover_color="#CFF5DC" if is_active else hover,
                text_color="#0D1710" if is_active else "#000000",
                state="disabled" if is_active else "normal",
                command=lambda selected=profile_id: activate(selected),
            ).pack(side="right", padx=16, pady=12)

    def activate(profile_id):
        try:
            result = _neto_apply_user_profile(profile_id)
            render_cards(f"{result.get('label', profile_id)} profili uygulandı.")
            try:
                app_root.after(0, lambda: animasyonlu_yazi(f"Profil aktif: {result.get('label', profile_id)}"))
            except Exception:
                pass
        except Exception as exc:
            status.configure(text=f"Profil uygulanamadı: {exc}", text_color="#F59E0B")

    ctk.CTkButton(
        window,
        text="Kapat",
        width=110,
        height=36,
        corner_radius=10,
        fg_color=card,
        hover_color=hover,
        command=close_window,
    ).pack(anchor="e", padx=28, pady=(0, 22))

    render_cards()
    return window


_NETO_REMINDER_SERVICE = None
_NETO_REMINDER_WINDOW = None


def _neto_reminder_ui_fire(item):
    """Play the selected sound and notify the Tk UI without blocking it."""
    app_root = globals().get("root")

    def notify():
        try:
            # The supplied track is bundled with NetOps; do not depend on CWD.
            _neto_play_reminder_sound()
        except Exception:
            pass
        title = str(item.get("title") or "Hatırlatıcı")
        message = str(item.get("message") or "Zamanı geldi.")
        try:
            animasyonlu_yazi(f"🔔 {title}: {message}")
        except Exception:
            pass
        try:
            refresh = getattr(_NETO_REMINDER_WINDOW, "_neto_refresh", None)
            if callable(refresh):
                refresh()
        except Exception:
            pass

    if app_root is not None:
        try:
            app_root.after(0, notify)
            return
        except Exception:
            pass
    notify()


def _neto_reminder_service_start():
    global _NETO_REMINDER_SERVICE
    if _NetoReminderService is None:
        return None
    if _NETO_REMINDER_SERVICE is None:
        _NETO_REMINDER_SERVICE = _NetoReminderService(on_fire=_neto_reminder_ui_fire)
    _NETO_REMINDER_SERVICE.start()
    return _NETO_REMINDER_SERVICE


def _neto_reminder_service_stop():
    service = globals().get("_NETO_REMINDER_SERVICE")
    if service is not None:
        try:
            service.stop()
        except Exception:
            pass


_NETO_TIMER_WINDOW = None
_NETO_TIMER_STATE = {
    "running": False,
    "remaining": 0,
    "duration": 0,
    "task": "",
    "after_id": None,
    "status_widget": None,
}


def _neto_timer_format(seconds):
    total = max(0, int(seconds or 0))
    minutes, seconds = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _neto_timer_parse_duration(value):
    """Accept MM:SS, HH:MM:SS, seconds with 's', or plain minutes."""
    raw = str(value or "").strip().lower().replace(" ", "")
    if not raw:
        raise ValueError("Süre boş bırakılamaz.")
    if raw.endswith("s"):
        seconds = int(float(raw[:-1]))
    else:
        parts = raw.split(":")
        if len(parts) == 1:
            seconds = int(float(parts[0])) * 60
        elif len(parts) == 2:
            seconds = int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        else:
            raise ValueError("Süreyi MM:SS biçiminde yaz.")
    if seconds <= 0:
        raise ValueError("Süre sıfırdan büyük olmalı.")
    return seconds


def _neto_timer_cancel():
    state = _NETO_TIMER_STATE
    after_id = state.get("after_id")
    app_root = globals().get("root")
    if after_id and app_root is not None:
        try:
            app_root.after_cancel(after_id)
        except Exception:
            pass
    state.update({"running": False, "remaining": 0, "duration": 0, "after_id": None})
    status_widget = state.get("status_widget")
    if status_widget is not None:
        try:
            status_widget.configure(text="Hazır")
        except Exception:
            pass
    state["status_widget"] = None


def _neto_timer_tick():
    state = _NETO_TIMER_STATE
    if not state.get("running"):
        return
    state["remaining"] = max(0, int(state.get("remaining", 0)) - 1)
    status_widget = state.get("status_widget")
    if status_widget is not None:
        try:
            status_widget.configure(text=f"Çalışıyor: {_neto_timer_format(state['remaining'])}")
        except Exception:
            state["status_widget"] = None
    if state["remaining"] <= 0:
        state["running"] = False
        state["after_id"] = None
        task = str(state.get("task") or "Görevini tamamla")
        duration = int(state.get("duration") or 0)
        state["status_widget"] = None
        netops_zamanlayici_suresi_doldu(duration, task)
        return
    app_root = globals().get("root")
    if app_root is not None:
        try:
            state["after_id"] = app_root.after(1000, _neto_timer_tick)
        except Exception:
            _neto_timer_cancel()


def netops_zamanlayici_baslat(duration_seconds, task, status_widget=None):
    app_root = globals().get("root")
    if app_root is None:
        return False
    _neto_timer_cancel()
    task = str(task or "Görevini tamamla").strip() or "Görevini tamamla"
    _NETO_TIMER_STATE.update({
        "running": True,
        "remaining": int(duration_seconds),
        "duration": int(duration_seconds),
        "task": task,
        "status_widget": status_widget,
    })
    if status_widget is not None:
        try:
            status_widget.configure(text=f"Çalışıyor: {_neto_timer_format(duration_seconds)}")
        except Exception:
            pass
    _NETO_TIMER_STATE["after_id"] = app_root.after(1000, _neto_timer_tick)
    return True


def netops_zamanlayici_suresi_doldu(duration_seconds, task):
    """Show the large, editable completion screen from the supplied mockup."""
    global _NETO_TIMER_WINDOW
    app_root = globals().get("root")
    if app_root is None:
        return None
    try:
        _neto_play_reminder_sound()
    except Exception:
        pass
    try:
        if _NETO_TIMER_WINDOW is not None and _NETO_TIMER_WINDOW.winfo_exists():
            _NETO_TIMER_WINDOW.lift()
            _NETO_TIMER_WINDOW.focus_force()
            return _NETO_TIMER_WINDOW
    except Exception:
        _NETO_TIMER_WINDOW = None

    palette = dict(globals().get("aktif_palet") or {})
    bg = palette.get("bg", "#050505")
    card = palette.get("card", "#19191F")
    text_main = palette.get("text_main", "#FFFFFF")
    text_dim = palette.get("text_dim", "#A7A7B2")
    border = palette.get("entry_border", "#30303A")
    neon = palette.get("neon", "#22C55E")

    window = ctk.CTkToplevel(app_root)
    _NETO_TIMER_WINDOW = window
    window.title("NetOps · Zamanlayıcı")
    window.geometry("760x760")
    window.minsize(600, 620)
    # Completion is a real full-screen alert, not a normal child panel.
    window.configure(fg_color="#000000")
    window.transient(app_root)
    try:
        window.overrideredirect(True)
        window.attributes("-fullscreen", True)
        window.attributes("-topmost", True)
    except Exception:
        try:
            window.geometry(f"{window.winfo_screenwidth()}x{window.winfo_screenheight()}+0+0")
        except Exception:
            pass
    window.bind("<Escape>", lambda _event: stop_timer())

    def close_window():
        global _NETO_TIMER_WINDOW
        _NETO_TIMER_WINDOW = None
        try:
            window.destroy()
        except Exception:
            pass

    def stop_timer():
        _neto_timer_cancel()
        close_window()
        try:
            animasyonlu_yazi("Zamanlayıcı durduruldu.")
        except Exception:
            pass

    def postpone_timer():
        new_task = task_entry.get().strip() or "Görevini tamamla"
        close_window()
        netops_zamanlayici_baslat(5 * 60, new_task)
        try:
            animasyonlu_yazi(f"5 dakika ertelendi: {new_task}")
        except Exception:
            pass

    window.protocol("WM_DELETE_WINDOW", stop_timer)
    window.grid_rowconfigure(3, weight=1)
    window.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(
        window,
        text=_neto_timer_format(0),
        text_color=text_main,
        font=("Segoe UI Semibold", 78),
    ).grid(row=0, column=0, pady=(68, 0))
    ctk.CTkLabel(
        window,
        text="Zamanlayıcı süresi doldu",
        text_color=text_main,
        font=("Segoe UI Semibold", 29),
    ).grid(row=1, column=0, pady=(4, 0))
    ctk.CTkLabel(
        window,
        text="Görevi düzenleyebilir veya 5 dakika erteleyebilirsin.",
        text_color=text_dim,
        font=("Segoe UI", 12),
    ).grid(row=2, column=0, pady=(8, 20))

    task_card = ctk.CTkFrame(window, fg_color="#000000", corner_radius=16, border_width=0, border_color=border)
    task_card.grid(row=3, column=0, sticky="nsew", padx=56, pady=(0, 24))
    task_card.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(
        task_card,
        text="Görev",
        text_color=text_dim,
        font=("Segoe UI Semibold", 12),
        anchor="w",
    ).grid(row=0, column=0, sticky="ew", padx=22, pady=(22, 7))
    task_entry = ctk.CTkEntry(
        task_card,
        height=52,
        fg_color=bg,
        border_color=neon,
        text_color=text_main,
        font=("Segoe UI Semibold", 17),
    )
    task_entry.insert(0, str(task or "Görevini tamamla"))
    task_entry.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 22))
    ctk.CTkLabel(
        task_card,
        text=f"Tamamlanan süre: {_neto_timer_format(duration_seconds)}",
        text_color=text_dim,
        font=("Segoe UI", 11),
    ).grid(row=2, column=0, pady=(0, 22))

    controls = ctk.CTkFrame(window, fg_color="transparent")
    controls.grid(row=4, column=0, pady=(0, 42))
    ctk.CTkButton(
        controls,
        text="Durdur",
        width=180,
        height=54,
        corner_radius=27,
        fg_color="#EF4444",
        hover_color="#B91C1C",
        text_color="#FFFFFF",
        font=("Segoe UI Semibold", 15),
        command=stop_timer,
    ).pack(side="left", padx=10)
    ctk.CTkButton(
        controls,
        text="Ertele · 5 dk",
        width=180,
        height=54,
        corner_radius=27,
        fg_color="#F5F5F5",
        hover_color="#D4D4D8",
        text_color="#09090B",
        font=("Segoe UI Semibold", 15),
        command=postpone_timer,
    ).pack(side="left", padx=10)
    try:
        window.focus_force()
        task_entry.focus_set()
    except Exception:
        pass
    return window


def netops_hatirlaticilar_penceresi_ac():
    """Open the persistent reminder scheduler used by the NetOps sidebar."""
    global _NETO_REMINDER_WINDOW
    app_root = globals().get("root")
    if app_root is None:
        return None
    service = _neto_reminder_service_start()
    if service is None:
        try:
            animasyonlu_yazi("Hatırlatıcı motoru yüklenemedi.")
        except Exception:
            pass
        return None

    try:
        if _NETO_REMINDER_WINDOW is not None and _NETO_REMINDER_WINDOW.winfo_exists():
            _NETO_REMINDER_WINDOW.lift()
            _NETO_REMINDER_WINDOW.focus_force()
            return _NETO_REMINDER_WINDOW
    except Exception:
        _NETO_REMINDER_WINDOW = None

    palette = dict(globals().get("aktif_palet") or {})
    bg = palette.get("bg", "#09090B")
    card = palette.get("card", "#19191F")
    entry = palette.get("entry", "#121217")
    border = palette.get("entry_border", "#30303A")
    text_main = palette.get("text_main", "#F5F5F5")
    text_dim = palette.get("text_dim", "#A7A7B2")
    neon = palette.get("neon", "#22C55E")
    hover = palette.get("button_hover", "#292936")

    window = ctk.CTkToplevel(app_root)
    _NETO_REMINDER_WINDOW = window
    window.title("NetOps Hatırlatıcılar")
    window.geometry("780x820")
    window.minsize(660, 680)
    window.configure(fg_color=bg)
    window.transient(app_root)

    def close_window():
        global _NETO_REMINDER_WINDOW
        _NETO_REMINDER_WINDOW = None
        try:
            window.destroy()
        except Exception:
            pass

    window.protocol("WM_DELETE_WINDOW", close_window)

    ctk.CTkLabel(
        window,
        text="NetOps Hatırlatıcılar",
        text_color=text_main,
        font=("Segoe UI Semibold", 25),
        anchor="w",
    ).pack(fill="x", padx=28, pady=(22, 2))
    ctk.CTkLabel(
        window,
        text="Saat programı gibi ayarla; NetOps zamanı gelince sana bildirip gönderdiğin sesi çalsın.",
        text_color=text_dim,
        font=("Segoe UI", 11),
        anchor="w",
        justify="left",
    ).pack(fill="x", padx=28, pady=(0, 14))

    form = ctk.CTkFrame(window, fg_color=card, corner_radius=14, border_width=1, border_color=border)
    form.pack(fill="x", padx=20, pady=(0, 12))
    form.grid_columnconfigure(0, weight=1)
    form.grid_columnconfigure(1, weight=1)

    def field_label(parent, text, row, column=0, colspan=1):
        ctk.CTkLabel(
            parent,
            text=text,
            text_color=text_dim,
            font=("Segoe UI Semibold", 11),
            anchor="w",
        ).grid(row=row, column=column, columnspan=colspan, sticky="ew", padx=14, pady=(10, 3))

    field_label(form, "Başlık", 0, colspan=2)
    title_entry = ctk.CTkEntry(form, height=36, fg_color=entry, border_color=border, text_color=text_main)
    title_entry.insert(0, "NetOps Hatırlatıcı")
    title_entry.grid(row=1, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 4))

    field_label(form, "Mesaj", 2, colspan=2)
    message_box = ctk.CTkTextbox(form, height=66, fg_color=entry, border_width=1, border_color=border, text_color=text_main)
    message_box.insert("1.0", "Hatırlatıcının zamanı geldi.")
    message_box.grid(row=3, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 4))

    default_schedule = datetime.datetime.now() + datetime.timedelta(minutes=5)
    field_label(form, "Tarih (YYYY-AA-GG)", 4, 0)
    date_entry = ctk.CTkEntry(form, height=36, fg_color=entry, border_color=border, text_color=text_main)
    date_entry.insert(0, default_schedule.strftime("%Y-%m-%d"))
    date_entry.grid(row=5, column=0, sticky="ew", padx=(14, 7), pady=(0, 4))

    field_label(form, "Saat (SS:DD)", 4, 1)
    time_entry = ctk.CTkEntry(form, height=36, fg_color=entry, border_color=border, text_color=text_main)
    time_entry.insert(0, default_schedule.strftime("%H:%M"))
    time_entry.grid(row=5, column=1, sticky="ew", padx=(7, 14), pady=(0, 4))

    repeat_by_label = {label: key for key, label in _NETO_REMINDER_REPEAT_LABELS.items()}
    repeat_values = list(repeat_by_label) or ["Bir kez"]
    field_label(form, "Tekrar", 6, 0)
    repeat_menu = ctk.CTkOptionMenu(
        form,
        values=repeat_values,
        height=36,
        fg_color=entry,
        button_color=neon,
        button_hover_color=hover,
        text_color=text_main,
        dropdown_fg_color=card,
        dropdown_hover_color=hover,
    )
    repeat_menu.set(repeat_values[0])
    repeat_menu.grid(row=7, column=0, sticky="ew", padx=(14, 7), pady=(0, 14))

    sound_area = ctk.CTkFrame(form, fg_color="transparent")
    sound_area.grid(row=7, column=1, sticky="ew", padx=(7, 14), pady=(0, 14))
    sound_area.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(
        sound_area,
        text="Ses: gönderdiğin WAV",
        text_color=text_dim,
        font=("Segoe UI", 10),
        anchor="w",
    ).grid(row=0, column=0, sticky="ew")
    ctk.CTkButton(
        sound_area,
        text="Test sesi",
        width=92,
        height=30,
        corner_radius=8,
        fg_color=hover,
        hover_color=neon,
        text_color=text_main,
        command=lambda: _neto_play_reminder_sound(),
    ).grid(row=0, column=1, padx=(8, 0))

    status = ctk.CTkLabel(window, text="", text_color=neon, font=("Segoe UI Semibold", 11), anchor="w")
    status.pack(fill="x", padx=28, pady=(0, 8))

    list_frame = ctk.CTkScrollableFrame(window, fg_color="transparent")
    list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 12))

    def format_run(value):
        if not value:
            return "Tekrar etmeyecek"
        try:
            return datetime.datetime.fromisoformat(str(value)).strftime("%d.%m.%Y %H:%M")
        except Exception:
            return str(value)

    def render_list(message=""):
        for child in list_frame.winfo_children():
            child.destroy()
        items = service.list_reminders()
        status.configure(text=message or (f"{len(items)} hatırlatıcı kayıtlı" if items else "Henüz hatırlatıcı yok."))
        for item in items:
            enabled = bool(item.get("enabled"))
            item_card = ctk.CTkFrame(
                list_frame,
                fg_color=card,
                border_width=1,
                border_color=neon if enabled else border,
                corner_radius=12,
            )
            item_card.pack(fill="x", padx=8, pady=5)
            info = ctk.CTkFrame(item_card, fg_color="transparent")
            info.pack(side="left", fill="both", expand=True, padx=14, pady=10)
            ctk.CTkLabel(
                info,
                text=("🔔 " if enabled else "⏸ ") + str(item.get("title") or "Hatırlatıcı"),
                text_color=text_main,
                font=("Segoe UI Semibold", 13),
                anchor="w",
            ).pack(fill="x")
            ctk.CTkLabel(
                info,
                text=f"{item.get('message', '')}\n{_NETO_REMINDER_REPEAT_LABELS.get(item.get('repeat'), 'Bir kez')} • {format_run(item.get('next_run'))}",
                text_color=text_dim,
                font=("Segoe UI", 10),
                anchor="w",
                justify="left",
                wraplength=475,
            ).pack(fill="x", pady=(3, 0))
            actions = ctk.CTkFrame(item_card, fg_color="transparent")
            actions.pack(side="right", padx=10, pady=10)
            ctk.CTkButton(
                actions,
                text="Durdur" if enabled else "Etkinleştir",
                width=92,
                height=30,
                corner_radius=8,
                fg_color=hover,
                hover_color=neon,
                text_color=text_main,
                command=lambda rid=item.get("id"), state=enabled: toggle(rid, state),
            ).pack(pady=(0, 5))
            ctk.CTkButton(
                actions,
                text="Sil",
                width=92,
                height=28,
                corner_radius=8,
                fg_color="#5C2026",
                hover_color="#8F2932",
                text_color="#FFFFFF",
                command=lambda rid=item.get("id"): remove(rid),
            ).pack()

    def toggle(reminder_id, enabled):
        if service.set_enabled(reminder_id, not enabled):
            render_list("Hatırlatıcı durumu güncellendi.")

    def remove(reminder_id):
        if service.delete_reminder(reminder_id):
            render_list("Hatırlatıcı silindi.")

    def add_reminder():
        try:
            scheduled_for = _neto_reminder_parse_schedule(date_entry.get(), time_entry.get())
            if scheduled_for <= datetime.datetime.now():
                raise ValueError("Tarih ve saat gelecekte olmalı.")
            repeat_key = repeat_by_label.get(repeat_menu.get(), "once")
            item = service.add_reminder(
                title_entry.get(),
                message_box.get("1.0", "end").strip(),
                scheduled_for,
                repeat=repeat_key,
                sound=_NETO_REMINDER_SOUND_NAME,
            )
            message_box.delete("1.0", "end")
            message_box.insert("1.0", "Hatırlatıcının zamanı geldi.")
            render_list(f"Kaydedildi: {format_run(item.get('next_run'))}")
        except Exception as exc:
            status.configure(text=f"Hatırlatıcı kaydedilemedi: {exc}", text_color="#F59E0B")

    ctk.CTkButton(
        form,
        text="Hatırlatıcı ekle",
        height=38,
        corner_radius=9,
        fg_color=neon,
        hover_color=hover,
        text_color="#000000",
        command=add_reminder,
    ).grid(row=8, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 14))

    timer_card = ctk.CTkFrame(window, fg_color=card, corner_radius=14, border_width=1, border_color=border)
    timer_card.pack(fill="x", padx=20, pady=(0, 10))
    timer_card.grid_columnconfigure(0, weight=1)
    timer_card.grid_columnconfigure(1, weight=1)
    ctk.CTkLabel(
        timer_card,
        text="Hızlı Zamanlayıcı",
        text_color=text_main,
        font=("Segoe UI Semibold", 14),
        anchor="w",
    ).grid(row=0, column=0, columnspan=2, sticky="ew", padx=14, pady=(10, 2))
    ctk.CTkLabel(
        timer_card,
        text="Süre (MM:SS)",
        text_color=text_dim,
        font=("Segoe UI", 10),
        anchor="w",
    ).grid(row=1, column=0, sticky="ew", padx=(14, 7), pady=(5, 3))
    ctk.CTkLabel(
        timer_card,
        text="Görev",
        text_color=text_dim,
        font=("Segoe UI", 10),
        anchor="w",
    ).grid(row=1, column=1, sticky="ew", padx=(7, 14), pady=(5, 3))
    timer_duration_entry = ctk.CTkEntry(timer_card, height=34, fg_color=entry, border_color=border, text_color=text_main)
    timer_duration_entry.insert(0, "00:10")
    timer_duration_entry.grid(row=2, column=0, sticky="ew", padx=(14, 7), pady=(0, 7))
    timer_task_entry = ctk.CTkEntry(timer_card, height=34, fg_color=entry, border_color=border, text_color=text_main)
    timer_task_entry.insert(0, "Ders çalış")
    timer_task_entry.grid(row=2, column=1, sticky="ew", padx=(7, 14), pady=(0, 7))
    timer_status = ctk.CTkLabel(timer_card, text="Hazır", text_color=neon, font=("Segoe UI Semibold", 10), anchor="w")
    timer_status.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 10))

    def start_countdown():
        try:
            seconds = _neto_timer_parse_duration(timer_duration_entry.get())
            task_text = timer_task_entry.get().strip() or "Görevini tamamla"
            if netops_zamanlayici_baslat(seconds, task_text, timer_status):
                timer_status.configure(text=f"Çalışıyor: {_neto_timer_format(seconds)}", text_color=neon)
        except Exception as exc:
            timer_status.configure(text=f"Başlatılamadı: {exc}", text_color="#F59E0B")

    def stop_countdown():
        _neto_timer_cancel()
        timer_status.configure(text="Durduruldu", text_color=text_dim)

    timer_actions = ctk.CTkFrame(timer_card, fg_color="transparent")
    timer_actions.grid(row=3, column=1, sticky="e", padx=14, pady=(0, 8))
    ctk.CTkButton(
        timer_actions,
        text="Başlat",
        width=92,
        height=30,
        corner_radius=8,
        fg_color=neon,
        hover_color=hover,
        text_color="#000000",
        command=start_countdown,
    ).pack(side="left", padx=(0, 6))
    ctk.CTkButton(
        timer_actions,
        text="Durdur",
        width=92,
        height=30,
        corner_radius=8,
        fg_color="#5C2026",
        hover_color="#8F2932",
        text_color="#FFFFFF",
        command=stop_countdown,
    ).pack(side="left")

    setattr(window, "_neto_refresh", render_list)
    render_list()
    return window

neto_time_log("modül importları tamamlandı")
print(f"[NETO_SYSTEM] NetOps {APP_VERSION} motion & UI pipeline ready", flush=True)


# ------------------------------------------------------------
# HARİCİ SİSTEM MODÜLLERİ
# ------------------------------------------------------------
pygame: Any = None
pyautogui: Any = None
psutil: Any = None
anyspeech_speak_text: Any = None
anyspeech_set_warning_callback: Any = None
POINTER: Any = None
CLSCTX_ALL: Any = None
AudioUtilities: Any = None
IAudioEndpointVolume: Any = None

try:
    import pygame
    pygame.mixer.pre_init(44100, -16, 2, 250)
    pygame.mixer.init()
    K_PYGAME = True
    neto_time_log("pygame mixer hazır")
except Exception:
    K_PYGAME = False
    neto_time_log("pygame yok / pas geçildi")

try:
    import pyautogui
    K_WIN = True
except Exception:
    K_WIN = False

try:
    import psutil
    K_PSUTIL = True
except Exception:
    K_PSUTIL = False

_NETO_SYSTEM_METRICS_CACHE: dict[str, Any] = {
    "ok": False,
    "ts": 0.0,
    "cpu": 0.0,
    "ram": 0.0,
    "ram_used_gb": 0.0,
    "ram_total_gb": 0.0,
}


def neto_system_metrics(force: bool = False) -> dict[str, Any]:
    """Return one consistent CPU/RAM sample for every visible system widget."""
    cache = _NETO_SYSTEM_METRICS_CACHE
    try:
        if not K_PSUTIL or psutil is None:
            return dict(cache)
        now = time.monotonic()
        if not force and bool(cache.get("ok")) and (now - float(cache.get("ts") or 0.0)) < 0.85:
            return dict(cache)
        try:
            cpu = float(psutil.cpu_percent(interval=0.05 if force else None))
        except Exception:
            cpu = float(cache.get("cpu") or 0.0)
        vm = psutil.virtual_memory()
        total = float(getattr(vm, "total", 0) or 0)
        available = float(getattr(vm, "available", 0) or 0)
        used = max(0.0, total - available)
        if total > 0:
            ram = (used / total) * 100.0
        else:
            ram = float(getattr(vm, "percent", 0.0) or 0.0)
        data = {
            "ok": True,
            "ts": now,
            "cpu": max(0.0, min(100.0, round(cpu, 1))),
            "ram": max(0.0, min(100.0, round(ram, 1))),
            "ram_used_gb": round(used / (1024 ** 3), 1) if total > 0 else 0.0,
            "ram_total_gb": round(total / (1024 ** 3), 1) if total > 0 else 0.0,
        }
        cache.update(data)
        return dict(cache)
    except Exception:
        return dict(cache)

try:
    from neto_anyspeech_tts import (
        speak_text as anyspeech_speak_text,
        set_warning_callback as anyspeech_set_warning_callback,
        reset_voice_cache as anyspeech_reset_voice_cache,
        preload_voice as anyspeech_preload_voice,
    )
    K_ANYSPEECH = True
except Exception:
    K_ANYSPEECH = False

try:
    from ctypes import cast as ctypes_cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    HAS_PYCAW = True
except Exception:
    HAS_PYCAW = False

# ------------------------------------------------------------
# FLASK VE MOBİL API ENTEGRASYONU
# ------------------------------------------------------------
app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

son_tetiklenme_zamani = 0
NETO_LOCAL_API_TOKEN = neto_security.get_or_create_local_api_token()

@app.route('/uyandir', methods=['GET'])
def uyandir_api():
    """Local wake endpoint.
    Security fix: loopback + token required. No LAN exposure by default.
    Token file: %LOCALAPPDATA%\\NetoAssistant\\local_api_token.txt
    """
    global son_tetiklenme_zamani
    remote = request.remote_addr or ""
    token = request.headers.get("X-Neto-Token") or request.args.get("token") or ""
    if not neto_security.is_loopback(remote):
        return jsonify({"durum": "reddedildi", "hata": "Sadece yerel PC erişimi açık."}), 403
    if token != NETO_LOCAL_API_TOKEN:
        return jsonify({"durum": "reddedildi", "hata": "Token gerekli."}), 401

    simdi = time.time()
    if simdi - son_tetiklenme_zamani > 3:
        son_tetiklenme_zamani = simdi
        print("\n Yerel uyanma emri geldi. NetOps tetikleniyor...")
        if 'root' in globals() and root:
            root.after(0, telefondan_tetikle)
    return jsonify({"durum": "basarili", "mesaj": "NetOps uyandırıldı."})

def telefondan_tetikle():
    h = veri_yukle()
    selam_metni = h.get("merhaba", T("main_hello"))
    animasyonlu_yazi(selam_metni)

def sunucuyu_arka_planda_baslat():
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)

# ------------------------------------------------------------
# SES VE ÇIKTI MOTORLARI (Exe Uyumlu)
# ------------------------------------------------------------
NETO_STARTUP_SOUND_ASSET = "neto_startup_sound.mp3"
NETO_UPDATE_SOUND_ASSET = "neto_update_notification.mp3"
_NETO_UPDATE_SOUND_LAST_PLAYED = 0.0


def ses_oynat(durum):
    """NetOps'un kısa arayüz seslerini UI thread'ini engellemeden oynatır.

    start  -> short-modern-logo: açılış sesi
    update -> universfield-new-notification: sistem güncelleme sesi
    """
    if not K_PYGAME:
        return

    def cal():
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)

            yol = None
            if durum == "start":
                h_ayar = veri_yukle()
                ozel_ses_adi = str(h_ayar.get("secilen_ses", "varsayilan") or "varsayilan")

                # Eski paket adı varsayılan olarak kaydedilmişse yeni birinci sese geçir.
                if ozel_ses_adi in ("varsayilan", "Neto Asistan giriş.mp3", NETO_STARTUP_SOUND_ASSET):
                    bundled = get_asset_path(NETO_STARTUP_SOUND_ASSET)
                    yol = bundled if bundled and os.path.exists(bundled) else START_SOUND_DEFAULT
                else:
                    yol = get_data_path(ozel_ses_adi)
                    if not os.path.exists(yol):
                        yol = get_asset_path(ozel_ses_adi)

            elif durum == "update":
                bundled = get_asset_path(NETO_UPDATE_SOUND_ASSET)
                yol = bundled if bundled and os.path.exists(bundled) else DONE_SOUND

            else:
                ses_map = {"tamam": DONE_SOUND, "hata": ERROR_SOUND}
                yol = ses_map.get(durum)

            if yol and os.path.exists(yol):
                sound = pygame.mixer.Sound(yol)
                sound.play()
                time.sleep(0.02)
        except Exception as e:
            print(f"Ses oynatma hatası ({durum}): {e}", flush=True)

    threading.Thread(target=cal, daemon=True).start()


def neto_guncelleme_sesi_tetikle(metin):
    """Gerçek bir yeni sürüm bildirimi geldiğinde güncelleme sesini bir kez çalar.

    'Son sürümdesin' veya yalnızca kontrol edildiğini söyleyen mesajlarda ses çalmaz.
    Aynı bildirimin birkaç UI katmanından gelmesine karşı zaman kilidi vardır.
    """
    global _NETO_UPDATE_SOUND_LAST_PLAYED
    try:
        ham = str(metin or "").strip().lower()
        if not ham:
            return False

        olumlu = (
            "yeni güncelleme paketi", "yeni paket", "güncelleme mevcut",
            "güncelleme bulundu", "güncelleme hazır", "indirilmeye hazır",
            "sistem güncellemesi", "update available", "new version",
            "new update", "update is ready", "ready to download",
        )
        olumsuz = (
            "son sürüm", "güncelsin", "güncelleme yok", "güncelleme bulunamadı",
            "kontrol ediliyor", "kontrol edildi", "up to date", "no update",
            "checking for updates", "already latest",
        )

        if not any(kelime in ham for kelime in olumlu):
            return False
        if any(kelime in ham for kelime in olumsuz):
            return False

        simdi = time.monotonic()
        if simdi - float(_NETO_UPDATE_SOUND_LAST_PLAYED or 0.0) < 10.0:
            return False

        _NETO_UPDATE_SOUND_LAST_PLAYED = simdi
        ses_oynat("update")
        return True
    except Exception as exc:
        try:
            print(f"[UPDATE_SOUND_ERROR] {exc}", flush=True)
        except Exception:
            pass
        return False

async def anyspeech_motoru(metin):
    if not K_PYGAME:
        return

    try:
        if anyspeech_speak_text is None:
            raise RuntimeError("Yerel TTS ses motoru yuklenemedi.")
        await asyncio.to_thread(
            anyspeech_speak_text,
            metin,
            logger=lambda msg: print(msg, flush=True),
        )
    except Exception as exc:
        print(f"[TTS] Genel ses hatası: {exc}", flush=True)

def sesli_oku(metin):
    metin = str(metin or "").strip()
    if not metin:
        return

    def baslat():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(anyspeech_motoru(metin))
        finally:
            try:
                loop.close()
            except Exception:
                pass

    threading.Thread(target=baslat, daemon=True).start()

# ------------------------------------------------------------
# HAFIZA VE VERİ MOTORU
# ------------------------------------------------------------
def veri_yukle():
    varsayilan = {
        "ayarlar": "OZEL_AYARLAR_PANELI",
        "google aç": "https://www.google.com",
        "youtube aç": "https://www.youtube.com",
        "whatsapp aç": "https://web.whatsapp.com",
        "hava durumu": "https://www.mgm.gov.tr",
        "ekran görüntüsü": "WIN_SS",
        "bilgisayarı kapat": "WIN_SHUTDOWN",
        "saat kaç": "SISTEM_SAAT",
        "merhaba": "NetOps hazır merhaba!",
        "secilen_gif": "yukleme.gif",
        "secilen_ses": "varsayilan",
        "ogrenme_modu_acik": False,
        "kufur_filtresi": True,
        "tema": "light",
        "renk_temasi": "blue",
        "arayuz_stili": "experians",
        "dil": "en"
    }
    if os.path.exists(FILE_PATH):
        try:
            with open(FILE_PATH, "r", encoding="utf-8") as f:
                varsayilan.update(json.load(f))
        except Exception: pass
    varsayilan["renk_temasi"] = _neto_vurgu_adi(varsayilan.get("renk_temasi", "green"))
    varsayilan["arayuz_stili"] = _neto_arayuz_stili(varsayilan.get("arayuz_stili", "experians"))
    return varsayilan

def veri_kaydet(hafiza):
    try:
        hafiza = dict(hafiza or {})
        hafiza["renk_temasi"] = _neto_vurgu_adi(hafiza.get("renk_temasi", "green"))
        hafiza["arayuz_stili"] = _neto_arayuz_stili(hafiza.get("arayuz_stili", "experians"))
        with open(FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(hafiza, f, ensure_ascii=False, indent=4)
        return True
    except Exception: return False


# ------------------------------------------------------------
# DİL MOTORU / LANGUAGE ENGINE
# Merkezi dil motoru: lang.py
# ------------------------------------------------------------
try:
    from lang import T, set_lang as dil_kaydet, get_lang as dil_getir, LANG as DIL_METINLERI
except Exception:
    def T(key: str, **kwargs) -> str:
        tr = {
            "app_title": f"NetOps {APP_VERSION}",
            "language_selection": "Dil Seçimi",
            "language_title": "NetOps'e Hoş Geldin",
            "language_desc": "Lütfen uygulama dilini seç.",
            "turkish": "Türkçe",
            "english": "English",
            "loading": "Açılıyor...",
            "system_status": "Sistem Durumu",
            "notes": "📌 Notlar",
            "system": "⚙️ Sistem",
            "netolab": "⚙️ NetOps Lab",
            "advanced_settings": "🔧 Gelişmiş Ayarlar",
            "neto_ai": "🌐 Web Sohbeti",
            "android_device": "📱 Android Cihaz",
            "language": "🌐 Dil",
            "extension_status_off": "Eklenti Durumu: KAPALI",
            "extension_status_on": "Eklenti Durumu: AÇIK",
            "extension_store": "🛒 Eklenti Mağazası",
            "main_question": "Sana nasıl yardımcı olabilirim?",
            "welcome_question": "Sana nasıl yardımcı olabilirim?",
            "main_hello": "Merhaba! Ben NetOps. Sana nasıl yardımcı olabilirim? 👋",
            "hello_text": "Merhaba! Ben NetOps. Sana nasıl yardımcı olabilirim? 👋",
            "send": "Gönder",
            "entry_placeholder": "Mesajını yaz...",
            "thinking": "Düşünüyor...",
            "ready": "Hazır.",
            "tts_unavailable": "⚠️ Yerel TTS kullanılamıyor. Model indirilemedi ya da yüklenemedi.",
            "polite_warning": "⚠️ Bu şekilde konuşamam. Daha kibar yazarsan yardımcı olurum.",
            "goodbye": "Görüşürüz! Kendine iyi bak 😊",
            "thanks_reply": "Rica ederim! 🙏",
            "how_are_you": "İyiyim, sana nasıl yardımcı olabilirim?",
            "who_are_you": "Ben NetOps, senin kişisel asistanınım.",
            "chat_no_answer": "Cevap alınamadı.",
            "not_understood": "Bunu tam anlayamadım.",
            "ask_learning": "Bunu öğrenmemi ister misin?",
            "help_text": "Yardım: Komut yazabilir, ayarları açabilir veya NetOps Agent kullanabilirsin.",
            "main_opening_run": "Açılıyor...",
            "main_opening_netolab": "NetOps Lab açılıyor...",
            "main_opening_advanced": "Gelişmiş ayarlar açılıyor...",
            "live_confirm_title": "NetOps Live Mode",
            "live_confirm_msg": "Live Mode'a geçmek istediğine emin misin?\n\nAsistan kapanacak ve NetOps Live açılacak.",
            "live_back_title": "NetOps Live",
            "live_back_msg": "Asistana geri dönmek istiyor musun?\n\nLive Mode kapanacak ve NetOps açılacak.",
            "live_start": "▶ Başlat",
            "live_stop": "⏸ Durdur",
            "live_closed": "Kapalı",
            "live_starting": "Başlatılıyor...",
            "live_mic_waiting": "Mikrofon: Bekleniyor",
            "live_voice": "Ses: Yerel Piper Türkçe Erkek",
            "live_error": "Hata",
            "ai_start_title": "NetOps Agent Başlatılıyor",
            "ai_start_message": "Yerel cevap motoru hazır.\n\nDevam etmek istiyor musun?",
            "ai_preparing_title": "NetOps Agent Hazırlanıyor",
            "ai_preparing": "🧠 Yerel cevap motoru hazırlanıyor...",
            "ollama_checking": "Yerel motor kontrol ediliyor...",
            "ollama_api_checking": "Yerel cevap akışı kontrol ediliyor...",
            "ollama_starting": "Yerel cevap motoru başlatılıyor...",
            "model_list_checking": "Model listesi kontrol ediliyor...",
            "model_downloading": "Yerel cevap motoru hazırlanıyor...",
            "model_ready": "Cevap motoru hazır. Sohbet açılıyor...",
            "ollama_needed_title": "Yerel AI Hazır Değil",
            "ollama_needed_msg": "Yerel cevap motoru bu bilgisayarda hazır değil.\n\nAma yine de sohbet edebilirsin.",
            "ollama_start_failed_title": "Yerel AI Başlatılamadı",
            "ollama_start_failed_msg": "Yerel cevap motoru şu an cevap vermiyor.",
            "ai_error_title": "NetOps Agent Hatası",
            "model_list_failed": "Model listesi alınamadı.",
            "model_download_started_title": "Yerel Motor Hazırlanıyor",
            "model_download_started_msg": "Yerel cevap motoru hazırlanıyor.",
            "model_download_failed": "Yerel motor başlatılamadı:\n{error}",
            "ai_prepare_error": "Yerel AI hazırlanırken hata oluştu:\n{error}",
        }
        en = {
        "app_title": f"NetOps {APP_VERSION}",
            "language_selection": "Language Selection",
            "language_title": "Welcome to NetOps",
            "language_desc": "Please select the app language.",
            "turkish": "Türkçe",
            "english": "English",
            "loading": "Opening...",
            "system_status": "System Status",
            "notes": "📌 Notes",
            "system": "⚙️ System",
            "netolab": "⚙️ NetOps Lab",
            "advanced_settings": "🔧 Advanced Settings",
            "neto_ai": "🌐 Web Chat",
            "language": "🌐 Language",
            "extension_status_off": "Extension Status: OFF",
            "extension_status_on": "Extension Status: ON",
            "extension_store": "🛒 Extension Store",
            "main_question": "How can I help you?",
            "welcome_question": "How can I help you?",
            "main_hello": "Hello! I am NetOps. How can I help you? 👋",
            "hello_text": "Hello! I am NetOps. How can I help you? 👋",
            "send": "Send",
            "entry_placeholder": "Type your message...",
            "thinking": "Thinking...",
            "ready": "Ready.",
            "tts_unavailable": "⚠️ Local TTS unavailable. The model could not be downloaded or loaded.",
            "polite_warning": "⚠️ I cannot continue like this. Please write more politely.",
            "goodbye": "Goodbye! Take care 😊",
            "thanks_reply": "You're welcome! 🙏",
            "how_are_you": "I'm good. How can I help you?",
            "who_are_you": "I am NetOps, your personal assistant.",
            "chat_no_answer": "No response received.",
            "not_understood": "I did not fully understand that.",
            "ask_learning": "Do you want me to learn this?",
            "help_text": "Help: You can type a command, open settings, or use NetOps Agent.",
            "main_opening_run": "Opening...",
            "main_opening_netolab": "Opening NetOps Lab...",
            "main_opening_advanced": "Opening advanced settings...",
            "live_confirm_title": "NetOps Live Mode",
            "live_confirm_msg": "Are you sure you want to switch to Live Mode?\n\nAssistant will close and NetOps Live will open.",
            "live_back_title": "NetOps Live",
            "live_back_msg": "Do you want to return to Assistant?\n\nLive Mode will close and NetOps will open.",
            "live_start": "▶ Start",
            "live_stop": "⏸ Stop",
            "live_closed": "Closed",
            "live_starting": "Starting...",
            "live_mic_waiting": "Microphone: Waiting",
            "live_voice": "Voice: Local Piper Turkish Male",
            "live_error": "Error",
            "ai_start_title": "Starting NetOps Agent",
            "ai_start_message": "The local reply engine is ready.\n\nDo you want to continue?",
            "ai_preparing_title": "Preparing NetOps Agent",
            "ai_preparing": "🧠 Preparing the local reply engine...",
            "ollama_checking": "Checking local engine...",
            "ollama_api_checking": "Checking reply flow...",
            "ollama_starting": "Starting local reply engine...",
            "model_list_checking": "Checking model list...",
            "model_downloading": "Preparing local reply engine...",
            "model_ready": "Reply engine is ready. Opening chat...",
            "ollama_needed_title": "Local AI Not Ready",
            "ollama_needed_msg": "The local reply engine is not ready on this computer.\n\nYou can still chat.",
            "ollama_start_failed_title": "Could Not Start Local AI",
            "ollama_start_failed_msg": "The local reply engine is not responding right now.",
            "ai_error_title": "NetOps Agent Error",
            "model_list_failed": "Could not get the model list.",
            "model_download_started_title": "Preparing Local Engine",
            "model_download_started_msg": "The local reply engine is being prepared.",
            "model_download_failed": "Could not start the local engine:\n{error}",
            "ai_prepare_error": "An error occurred while preparing the local AI:\n{error}",
        }
        try:
            aktif = dil_getir()
        except Exception:
            aktif = "en"
        text = (tr if aktif == "tr" else en).get(key, en.get(key, tr.get(key, key)))
        if not isinstance(text, str):
            text = str(key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except Exception:
                pass
        return str(text)

    def dil_kaydet(lang: str) -> str:
        h = veri_yukle()
        h["dil"] = lang if lang in ("tr", "en") else "en"
        veri_kaydet(h)
        return h["dil"]

    def dil_getir() -> str:
        h = veri_yukle()
        return h.get("dil", "en") if h.get("dil", "en") in ("tr", "en") else "en"

    DIL_METINLERI = {
        "tr": {"turkish": "Türkçe", "english": "English"},
        "en": {"turkish": "Türkçe", "english": "English"},
    }

_NETO_QUICK_ACTIONS_WINDOW = None
_NETO_LOG_WINDOW = None


def _neto_app_root():
    return globals().get("root")


def _neto_project_root():
    try:
        return Path(__file__).resolve().parent
    except Exception:
        return Path.cwd()


def _neto_open_path(path):
    try:
        target = Path(path)
    except Exception:
        return False
    try:
        if os.name == "nt":
            os.startfile(str(target))
        else:
            webbrowser.open(target.as_uri() if target.exists() else str(target))
        return True
    except Exception:
        return False


def _neto_logs_dir():
    return _neto_project_root() / "logs"


def _neto_tail_text(path, max_lines=500):
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"Dosya okunamadı: {exc}"
    lines = text.splitlines()
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
    return "\n".join(lines).rstrip() or "(Boş)"


def neto_toast_goster(title, message, kind="info", duration_ms=2600):
    root_obj = _neto_app_root()
    try:
        from neto_runtime_policy_v2 import show_toast as _show_toast

        if callable(_show_toast) and root_obj is not None:
            return bool(
                _show_toast(
                    root_obj,
                    str(title),
                    str(message),
                    kind=str(kind or "info"),
                    duration_ms=int(duration_ms),
                )
            )
    except Exception:
        pass
    try:
        animasyonlu_yazi(f"{title}: {message}")
        return True
    except Exception:
        return False


def neto_logs_klasorunu_ac():
    path = _neto_logs_dir()
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return _neto_open_path(path)


def neto_log_penceresi_ac(log_name=None):
    global _NETO_LOG_WINDOW
    root_obj = _neto_app_root()
    if root_obj is None:
        return False
    try:
        if _NETO_LOG_WINDOW is not None and _NETO_LOG_WINDOW.winfo_exists():
            _NETO_LOG_WINDOW.deiconify()
            _NETO_LOG_WINDOW.lift()
            _NETO_LOG_WINDOW.focus_force()
            return True
    except Exception:
        _NETO_LOG_WINDOW = None

    log_dir = _neto_logs_dir()
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    tr = False
    try:
        tr = str(dil_getir()).lower().startswith("tr")
    except Exception:
        pass

    window = ctk.CTkToplevel(root_obj)
    _NETO_LOG_WINDOW = window
    window.title("Günlükler" if tr else "Logs")
    window.geometry("860x620")
    window.minsize(720, 500)
    window.configure(fg_color=aktif_palet["bg"])
    try:
        window.transient(root_obj)
        window.attributes("-topmost", True)
        window.after(500, lambda: window.attributes("-topmost", False))
    except Exception:
        pass

    shell = ctk.CTkFrame(
        window,
        fg_color=aktif_palet["card"],
        corner_radius=18,
        border_width=1,
        border_color=aktif_palet["entry_border"],
    )
    shell.pack(fill="both", expand=True, padx=14, pady=14)

    header = ctk.CTkFrame(shell, fg_color="transparent")
    header.pack(fill="x", padx=16, pady=(14, 6))

    ctk.CTkLabel(
        header,
        text="Günlükler" if tr else "Logs",
        text_color=aktif_palet["text_main"],
        font=("Segoe UI Semibold", 20),
        anchor="w",
    ).pack(side="left")

    ctk.CTkLabel(
        header,
        text=log_dir.name,
        text_color=aktif_palet["text_dim"],
        font=("Segoe UI", 10),
        anchor="e",
    ).pack(side="right")

    toolbar = ctk.CTkFrame(shell, fg_color="transparent")
    toolbar.pack(fill="x", padx=16, pady=(0, 10))

    available = [
        name for name in (
            "boot_trace.log",
            "last_run.log",
            "fault.log",
            "crash.log",
            "now_playing.log",
            "weather.log",
        )
        if (log_dir / name).exists()
    ]
    if not available:
        available = [
            "boot_trace.log",
            "last_run.log",
            "fault.log",
            "crash.log",
            "now_playing.log",
            "weather.log",
        ]

    default_log = log_name if log_name in available else available[0]
    log_var = ctk.StringVar(value=default_log)

    log_menu = ctk.CTkOptionMenu(
        toolbar,
        values=available,
        variable=log_var,
        fg_color=aktif_palet["entry_bg"],
        button_color=aktif_palet["neon"],
        button_hover_color=aktif_palet.get("accent_hover", aktif_palet["button_hover"]),
        text_color=aktif_palet["text_main"],
    )
    log_menu.pack(side="left", fill="x", expand=True, padx=(0, 8))

    log_text = ctk.CTkTextbox(
        shell,
        fg_color=aktif_palet["entry_bg"],
        text_color=aktif_palet["text_main"],
        corner_radius=12,
        border_width=1,
        border_color=aktif_palet["entry_border"],
        font=("Consolas", 11),
    )
    log_text.pack(fill="both", expand=True, padx=16, pady=(0, 12))

    def _log_yaz(text):
        try:
            log_text.configure(state="normal")
            log_text.delete("1.0", "end")
            log_text.insert("1.0", text)
            log_text.configure(state="disabled")
        except Exception:
            pass

    def yenile():
        log_name_now = log_var.get()
        path = log_dir / log_name_now
        try:
            if path.exists():
                content = _neto_tail_text(path, max_lines=700)
                header_text = f"{log_name_now} · {path.stat().st_size // 1024} KB"
            else:
                content = f"Dosya bulunamadı: {path}"
                header_text = f"{log_name_now} · missing"
        except Exception as exc:
            content = f"Log okunamadı: {exc}"
            header_text = log_name_now
        try:
            window.title(f"{'Günlükler' if tr else 'Logs'} · {log_name_now}")
        except Exception:
            pass
        _log_yaz(f"[{header_text}]\n\n{content}")

    def open_folder():
        neto_logs_klasorunu_ac()

    def close():
        global _NETO_LOG_WINDOW
        _NETO_LOG_WINDOW = None
        try:
            window.destroy()
        except Exception:
            pass

    ctk.CTkButton(
        toolbar,
        text="Yenile" if tr else "Refresh",
        width=88,
        height=34,
        corner_radius=10,
        fg_color=aktif_palet["card"],
        hover_color=aktif_palet["button_hover"],
        text_color=aktif_palet["text_main"],
        command=yenile,
    ).pack(side="left", padx=(0, 8))

    ctk.CTkButton(
        toolbar,
        text="Klasör" if tr else "Folder",
        width=88,
        height=34,
        corner_radius=10,
        fg_color=aktif_palet["card"],
        hover_color=aktif_palet["button_hover"],
        text_color=aktif_palet["text_main"],
        command=open_folder,
    ).pack(side="left", padx=(0, 8))

    ctk.CTkButton(
        toolbar,
        text="Kapat" if tr else "Close",
        width=88,
        height=34,
        corner_radius=10,
        fg_color=aktif_palet["neon"],
        hover_color=aktif_palet.get("accent_hover", aktif_palet["button_hover"]),
        text_color=_tema_vurgu_metin_rengi(),
        command=close,
    ).pack(side="right")

    log_menu.configure(command=lambda _value: yenile())
    window.bind("<Escape>", lambda _event: close())
    window.protocol("WM_DELETE_WINDOW", close)
    yenile()
    try:
        window.lift()
        window.focus_force()
    except Exception:
        pass
    return True


def neto_v10_pulse_ac():
    """Open the v10 release health and driver control center."""
    root_obj = _neto_app_root()
    if root_obj is None:
        return None
    try:
        from neto_v10_center import open_v10_pulse

        return open_v10_pulse(root_obj, globals())
    except Exception as exc:
        neto_toast_goster("NetOps v10", f"Pulse merkezi açılamadı: {exc}", "error")
        return None


def neto_quick_actions_penceresi_ac():
    global _NETO_QUICK_ACTIONS_WINDOW
    root_obj = _neto_app_root()
    if root_obj is None:
        return False
    try:
        if _NETO_QUICK_ACTIONS_WINDOW is not None and _NETO_QUICK_ACTIONS_WINDOW.winfo_exists():
            _NETO_QUICK_ACTIONS_WINDOW.deiconify()
            _NETO_QUICK_ACTIONS_WINDOW.lift()
            _NETO_QUICK_ACTIONS_WINDOW.focus_force()
            return True
    except Exception:
        _NETO_QUICK_ACTIONS_WINDOW = None

    tr = False
    try:
        tr = str(dil_getir()).lower().startswith("tr")
    except Exception:
        pass

    window = ctk.CTkToplevel(root_obj)
    _NETO_QUICK_ACTIONS_WINDOW = window
    window.title("Hızlı İşlemler" if tr else "Quick Actions")
    window.geometry("560x500")
    window.minsize(480, 420)
    window.configure(fg_color=aktif_palet["bg"])
    try:
        window.transient(root_obj)
        window.attributes("-topmost", True)
        window.after(500, lambda: window.attributes("-topmost", False))
    except Exception:
        pass

    shell = ctk.CTkFrame(
        window,
        fg_color=aktif_palet["card"],
        corner_radius=18,
        border_width=1,
        border_color=aktif_palet["entry_border"],
    )
    shell.pack(fill="both", expand=True, padx=14, pady=14)

    ctk.CTkLabel(
        shell,
        text="Hızlı İşlemler" if tr else "Quick Actions",
        text_color=aktif_palet["text_main"],
        font=("Segoe UI Semibold", 20),
        anchor="w",
    ).pack(fill="x", padx=16, pady=(14, 2))

    ctk.CTkLabel(
        shell,
        text="Sık kullanılan yardımcılar burada." if tr else "Frequently used helpers live here.",
        text_color=aktif_palet["text_dim"],
        font=("Segoe UI", 11),
        anchor="w",
    ).pack(fill="x", padx=16, pady=(0, 12))

    grid = ctk.CTkFrame(shell, fg_color="transparent")
    grid.pack(fill="both", expand=True, padx=16, pady=(0, 16))
    grid.grid_columnconfigure((0, 1), weight=1, uniform="quick")

    def _card_button(parent, title, subtitle, command, accent=False, row=0, column=0):
        card = ctk.CTkFrame(
            parent,
            fg_color=aktif_palet["sidebar"] if not accent else aktif_palet["neon"],
            corner_radius=16,
        )
        card.grid(row=row, column=column, sticky="nsew", padx=6, pady=6)
        ctk.CTkLabel(
            card,
            text=title,
            text_color=_tema_vurgu_metin_rengi() if accent else aktif_palet["text_main"],
            font=("Segoe UI Semibold", 13),
            anchor="w",
        ).pack(fill="x", padx=14, pady=(12, 2))
        ctk.CTkLabel(
            card,
            text=subtitle,
            text_color=_tema_vurgu_metin_rengi() if accent else aktif_palet["text_dim"],
            font=("Segoe UI", 10),
            anchor="w",
            justify="left",
            wraplength=210,
        ).pack(fill="x", padx=14, pady=(0, 10))
        btn = ctk.CTkButton(
            card,
            text=title,
            height=34,
            corner_radius=10,
            fg_color=aktif_palet["card"] if not accent else _tema_vurgu_metin_rengi(),
            hover_color=aktif_palet["button_hover"] if not accent else aktif_palet.get("accent_hover", aktif_palet["button_hover"]),
            text_color=aktif_palet["text_main"] if not accent else aktif_palet["sidebar"],
            command=command,
        )
        btn.pack(fill="x", padx=14, pady=(0, 14))
        return card

    quick_items = [
        (
            "Komut Paleti" if tr else "Command Palette",
            "Ctrl+K ile arama yap, hızlı komut çalıştır." if tr else "Search and run commands with Ctrl+K.",
            lambda: _neto_lazy_import("neto_command_palette").open_command_palette(root_obj, globals()),
            True,
        ),
        (
            "Görünüm Ayarları" if tr else "Appearance",
            "Tema ve arayüz seçeneklerine git." if tr else "Jump to theme and UI options.",
            lambda: ayarlar_sayfasi_ac("appearance"),
            False,
        ),
        (
            "Sistem Ayarları" if tr else "System",
            "Performans ve sistem araçlarını aç." if tr else "Open performance and system tools.",
            lambda: ayarlar_sayfasi_ac("system"),
            False,
        ),
        (
            "Bildirim Testi" if tr else "Toast Test",
            "Küçük bir başarı bildirimi göster." if tr else "Show a sample success toast.",
            lambda: neto_toast_goster(APP_NAME, "Toast sistemi çalışıyor." if tr else "The toast system is working.", "success"),
            False,
        ),
        (
            "Günlükler" if tr else "Logs",
            "Son hata ve boot günlüklerini aç." if tr else "Open recent error and boot logs.",
            lambda: neto_log_penceresi_ac(),
            False,
        ),
        (
            "Log Klasörü" if tr else "Log Folder",
            "Log klasörünü doğrudan aç." if tr else "Open the log folder directly.",
            lambda: neto_logs_klasorunu_ac(),
            False,
        ),
        (
            "Device Hub" if tr else "Device Hub",
            "Pairing, heartbeat ve medya komutları için cihaz merkezini aç." if tr else "Open the device center for pairing, heartbeat and media commands.",
            lambda: neto_device_hub_ac_safe(),
            True,
        ),
    ]

    for index, (title, subtitle, command, accent) in enumerate(quick_items):
        _card_button(
            grid,
            title,
            subtitle,
            command,
            accent=accent,
            row=index // 2,
            column=index % 2,
        )

    footer = ctk.CTkFrame(shell, fg_color="transparent")
    footer.pack(fill="x", padx=16, pady=(0, 16))
    ctk.CTkButton(
        footer,
        text="Kapat" if tr else "Close",
        width=96,
        height=34,
        corner_radius=10,
        fg_color=aktif_palet["card"],
        hover_color=aktif_palet["button_hover"],
        text_color=aktif_palet["text_main"],
        command=lambda: close(),
    ).pack(side="right")

    def close():
        global _NETO_QUICK_ACTIONS_WINDOW
        _NETO_QUICK_ACTIONS_WINDOW = None
        try:
            window.destroy()
        except Exception:
            pass

    window.bind("<Escape>", lambda _event: close())
    window.protocol("WM_DELETE_WINDOW", close)
    try:
        window.lift()
        window.focus_force()
    except Exception:
        pass
    return True


def arayuz_diline_cevir(metin):
    """Ana ekrandaki yerel/sabit cevapları seçili arayüz diline göre gösterir."""
    if metin is None:
        return metin
    try:
        if dil_getir() != "en":
            return metin
    except Exception:
        return metin

    raw = str(metin).strip()
    if raw.startswith("__"):
        return raw

    exact = {
        "⚠️ Lütfen daha nazik bir dil kullan.": T("polite_warning"),
        "Merhaba! 👋 Sana nasıl yardımcı olabilirim?": "Hello! 👋 How can I help you?",
        "Görüşürüz! Kendine iyi bak 😊": T("goodbye"),
        "Rica ederim, ne demek! 🙏": T("thanks_reply"),
        "Harikayım, seni gördüğüme sevindim! ☺️ Sen nasılsın?": T("how_are_you"),
        "Ben NetOps, senin kişisel asistanınım. Sana yardım etmek için buradayım! 🤖": T("who_are_you"),
        "Birçok şey yapabilirim: hava durumu, şifre oluşturma, yazı tura, IP sorgulama, sistem komutları, hesaplama, not alma, web arama ve daha fazlası. 💪": T("help_text"),
        "Hangi şehir?": "Which city?",
        "Hava durumu alınamadı.": "Weather information could not be retrieved.",
        "Hesaplayamadım.": "I could not calculate that.",
        "Örnek: hesapla 5+3": "Example: calculate 5+3",
        "Görev yöneticisi açılıyor... 📋": "Task Manager is opening... 📋",
        "Denetim masası açılıyor... ⚙️": "Control Panel is opening... ⚙️",
        "Çalıştır penceresi açılıyor... 🏃": T("main_opening_run"),
        "Komut istemi açılıyor... 💻": "Command Prompt is opening... 💻",
        "PowerShell açılıyor... 🟦": "PowerShell is opening... 🟦",
        "Not defteri açılıyor... 📝": "Notepad is opening... 📝",
        "Hesap makinesi açılıyor... 🧮": "Calculator is opening... 🧮",
        "Ses ayarları penceresi açılıyor... 🔊": "Sound settings are opening... 🔊",
        "Masaüstü açılıyor... 📂": "Desktop is opening... 📂",
        "Belgeler klasörü açılıyor... 📁": "Documents folder is opening... 📁",
        "İndirilenler klasörü açılıyor... ⬇️": "Downloads folder is opening... ⬇️",
        "Dosya seçimi iptal edildi.": "File selection was cancelled.",
        "IP adresi alınamadı.": "IP address could not be retrieved.",
        "İnternet bağlantısı aktif ✅": "Internet connection is active ✅",
        "İnternet bağlantısı yok ❌": "No internet connection ❌",
        "kaldırılmış gömülü editör opened! 🐍": T("main_opening_code"),
        "NetOps Lab opened! ⚙️": T("main_opening_netolab"),
        "Advanced settings opened! 🔧": T("main_opening_advanced"),
        "Bu işlemi yapamadım.": "I could not perform this operation.",
        "Üzgünüm, bunu cevaplayamıyorum.": T("not_understood"),
        "Bunu bilmiyorum, cevabı ne olsun?": T("ask_learning"),
        "İşlem iptal.": "Operation cancelled.",
        "Görüşürüz...": "Goodbye...",
        "Anladım, hafızama ekledim.": "Understood. I saved it to memory.",
        "Dosya hatası!": "File error!",
        "Açıyorum...": "Opening...",
        "Komut çalıştırıldı.": "Command executed.",
    }

    if raw in exact:
        return exact[raw]
    if raw.startswith("Şu an saat "):
        return raw.replace("Şu an saat", "The time is", 1)
    if raw.startswith("Bugün "):
        return raw.replace("Bugün", "Today is", 1)
    if raw.startswith("Ekran görüntüsü"):
        return "Screenshot saved to the desktop. 📸"
    if raw.startswith("Bilgisayar yeniden başlatılıyor"):
        return "The computer is restarting... 🔄"
    if raw.startswith("Uyku moduna geçiliyor"):
        return "Entering sleep mode... 😴"
    if raw.startswith("Bilgisayarı yeniden başlatmamı onaylıyor musun"):
        return "Do you confirm restarting the computer? (Yes/No) 🔄"
    if raw.startswith("Bilgisayarı uyku moduna almamı onaylıyor musun"):
        return "Do you confirm putting the computer to sleep? (Yes/No) 😴"
    if raw.startswith("Bilgisayarı kapatmamı onaylıyor musun"):
        return "Do you confirm shutting down the computer? (Yes/No) 🔌"
    if raw.startswith("Seçilen dosya:"):
        return raw.replace("Seçilen dosya:", "Selected file:", 1)
    if raw.startswith("Yerel IP adresin:"):
        return raw.replace("Yerel IP adresin:", "Your local IP address is:", 1)
    if raw.startswith("Bilgisayar adı:"):
        return raw.replace("Bilgisayar adı:", "Computer name:", 1).replace("İşletim sistemi:", "Operating system:")
    if raw.startswith("Sonuç:"):
        return raw.replace("Sonuç:", "Result:", 1)
    if raw.startswith("Ses seviyesi") or raw.startswith("🔊 Ses"):
        return raw.replace("Ses seviyesi", "Volume level").replace("olarak ayarlandı", "has been set").replace("yaklaşık", "approximately")
    if raw.startswith("Hocam"):
        return raw.replace("Hocam ", "")
    if raw.startswith("✅ Komut alındı:"):
        return raw.replace("✅ Komut alındı:", "✅ Command received:", 1)
    if raw.startswith("❌ Hata:"):
        return raw.replace("❌ Hata:", "❌ Error:", 1)
    return raw

# ------------------------------------------------------------
# AKILLI KÜFÜR FİLTRESİ (Tam kelime eşleşmesi)
# ------------------------------------------------------------
def kufur_var_mi(metin):
    """Kaba dili yakalar; masum kelimelerde parca eslesmesi yapmaz."""
    metin_lower = str(metin or "").casefold()
    kelimeler = re.findall(r"[a-z0-9çğıöşü]+", metin_lower)
    metin_aralikli = " " + " ".join(kelimeler) + " "

    guvenli_kisa_ifadeler = {"selam", "merhaba", "hey", "naber", "sa", "slm"}
    if " ".join(kelimeler) in guvenli_kisa_ifadeler:
        return False

    for kufur in KUFUR_LISTESI:
        kufur_lower = str(kufur or "").casefold().strip()
        if not kufur_lower:
            continue
        kufur_kelimeler = re.findall(r"[a-z0-9çğıöşü]+", kufur_lower)
        if not kufur_kelimeler:
            continue

        if len(kufur_kelimeler) > 1:
            phrase = " ".join(kufur_kelimeler)
            if f" {phrase} " in metin_aralikli:
                return True
            continue

        token = kufur_kelimeler[0]
        if token in kelimeler:
            return True

        if len(token) >= 4:
            spaced = r"\b" + r"[^a-z0-9çğıöşü]*".join(re.escape(ch) for ch in token) + r"\b"
            if re.search(spaced, metin_lower):
                return True
    return False

# ------------------------------------------------------------
# EMOJİ VE YAZI ARAÇLARI
# ------------------------------------------------------------
def emoji_ekle(metin):
    emoji_map = {
        "merhaba": "👋", "hazır": "✅", "açıyorum": "🚀", "başarıyla": "🎉",
        "kaydedildi": "💾", "silindi": "🗑️", "hata": "❌", "saat": "⏰",
        "hava": "🌤️", "müzik": "🎵", "not": "📝", "görüşürüz": "👋😊",
        "teşekkür": "🙏", "bilmiyorum": "🤔", "öğrenme": "📚", "ayarlar": "⚙️",
        "kapat": "🔌", "arama": "🔍", "video": "▶️", "hesap": "🧮",
        "sistem": "🖥️", "anladım": "👍", "tamam": "✔️", "üzgünüm": "😔",
        "dikkat": "⚠️",
    }
    for anahtar, emoji in emoji_map.items():
        if anahtar in metin.lower():
            # Aynı emoji metinde zaten varsa ikinci kez ekleme.
            # Özellikle karşılama metnindeki çift el sallama sorununu önler.
            if emoji in metin:
                return metin
            return f"{metin} {emoji}"
    return metin

def metinden_emoji_temizle(metin):
    return re.sub(r'[^\w\s.,!?;:\'\"@#&*()\-+=/\\<>\[\]{}|~`%^]', '', metin).strip()

# ------------------------------------------------------------
# GLOBAL DEĞİŞKENLER
# ------------------------------------------------------------
ogrenme_modu, silme_modu, onay_modu, son_soru, animasyon_id = False, False, False, "", None
secili_resim_yolu = None
secili_resim_preview_ref = None
live_mode_controller = None
live_panel_acik = False
now_playing_overlay: Any = None
now_playing_island: Any = None
now_playing_island_frame: Any = None
now_playing_island_title_label: Any = None
now_playing_island_artist_label: Any = None
now_playing_island_status_label: Any = None
now_playing_island_action_label: Any = None
now_playing_island_pull_label: Any = None
now_playing_island_state: dict[str, Any] = {}
now_playing_current_key = None
now_playing_hidden_until_key = None
now_playing_canvas_job = None
now_playing_countdown_job = None
now_playing_countdown_label: Any = None
now_playing_idle_job = None
now_playing_idle_frame: Any = None
now_playing_idle_header_label: Any = None
now_playing_idle_clock_label: Any = None
now_playing_idle_active = False
now_playing_idle_last_activity = 0.0
now_playing_idle_deadline = 0.0
now_playing_idle_global_click_bound = False
now_playing_idle_last_media_key = ""
now_playing_idle_change_until = 0.0
now_playing_idle_refreshing = False
now_playing_idle_bg_label: Any = None
now_playing_idle_bg_canvas: Any = None
now_playing_idle_bg_image_item: Any = None
now_playing_idle_canvas_items: dict[str, Any] = {}
now_playing_idle_bg_job = None
now_playing_idle_bg_frames: list[Any] = []
now_playing_idle_bg_frame_index = 0
now_playing_idle_bg_size = (0, 0)
now_playing_end_time = 0
now_playing_last_key = None
now_playing_paused = False
eklenti_aktif_mi = False
volume_label = None
volume_slider = None
volume_slider_dragging = False
now_playing_volume_label: Any = None
now_playing_volume_slider: Any = None
now_playing_title_label: Any = None
now_playing_artist_label: Any = None
now_playing_source_label: Any = None
now_playing_status_label: Any = None
now_playing_visual_frame: Any = None
now_playing_visual_canvas: Any = None
now_playing_visual_logo_label: Any = None
now_playing_visual_mode_button: Any = None
now_playing_current_info = None
now_playing_vinyl_canvas: Any = None
now_playing_vinyl_job = None
now_playing_vinyl_photo = None
now_playing_display_cover_path = None
now_playing_display_cover_key = None
now_playing_cover_transition_step = 0
now_playing_vinyl_angle = 0
now_playing_scratch_enabled = True
now_playing_scratch_last_angle = None
now_playing_scratch_last_time = 0
now_playing_scratch_last_seek = 0
now_playing_scratch_button: Any = None
now_playing_first_launch_prompt_shown = False
now_playing_first_launch_info = None
now_playing_first_prompt_window = None
# Açık Şimdi Çalıyor ekranındaki bileşenler tema/vurgu değişiminde
# yeniden oluşturulmadan güncellenir.
now_playing_theme_widgets = {}
# Otomatik Şimdi Çalıyor izleyicisi: tek worker + ana-thread UI kuyruğu.
now_playing_monitor_started = False
now_playing_monitor_thread = None
now_playing_monitor_queue = queue.Queue(maxsize=6)
now_playing_monitor_stop = threading.Event()
now_playing_monitor_last_info = None
now_playing_monitor_last_seen = 0.0
now_playing_ui_pump_job = None

# VPN / tünel uyarı sistemi
_NETO_VPN_UYARI_PENCERESI = None
_NETO_VPN_IZLEYICI_DURUMU = {
    "monitor_started": False,
    "first_seen": {},
    "last_signature": None,
    "countdown_job": None,
    "escalation_job": None,
    "escalation_active": False,
    "countdown_left": 30,
    "last_ack_time": 0.0,
    "tracked_pids": set(),
}

def komut_token_temizle(metin):
    """AI cevaplarının içinde görünen teknik komut tokenlarını kullanıcıdan gizler."""
    if metin is None:
        return ""

    metin = str(metin).strip()

    if not metin:
        return ""

    # Token cevabın ortasında veya sonunda kaldıysa ekrana basma.
    # Örnek: "İstanbul güzel bir şehir. __KOMUT__:..." -> "İstanbul güzel bir şehir."
    tokenlar = [
        "__KOMUT__:",
        "__KOMUT__",
        "__SES__:",
        "__SES__",
        "__HESAPLA__:",
        "__HESAPLA__",
        "__HAVA__:",
        "__HAVA__",
    ]

    for token in tokenlar:
        if token in metin:
            metin = metin.split(token, 1)[0].strip()

    # Model bazen alt satıra tek başına token yazabiliyor.
    temiz_satirlar = []
    for satir in metin.splitlines():
        s = satir.strip()
        if s.startswith("__KOMUT__") or s.startswith("__SES__") or s.startswith("__HESAPLA__") or s.startswith("__HAVA__"):
            continue
        temiz_satirlar.append(satir)

    metin = "\n".join(temiz_satirlar).strip()

    return metin


def _neto_sohbet_ekrani_ac():
    """Karşılama ekranından ChatGPT benzeri sohbet geçmişine geçer."""
    try:
        shell = globals().get("chat_bubble_shell")
        if shell is None or not shell.winfo_exists():
            return False
        from neto_motion_engine_v2 import get_motion_engine
        get_motion_engine(root).cancel("hero-intro")
        for widget_name in ("gif_ana_label", "lbl_welcome"):
            widget = globals().get(widget_name)
            if widget is not None and widget.winfo_exists():
                widget.pack_forget()
        status = globals().get("hero_status_frame")
        if status is not None and status.winfo_exists():
            status.pack_forget()
        if not shell.winfo_manager():
            shell.pack(fill="both", expand=True, padx=30, pady=(4, 0))
        return True
    except Exception:
        return False


def _neto_sohbet_temizle():
    try:
        alan = globals().get("chat_bubble_area")
        if alan is not None and alan.winfo_exists():
            for child in alan.winfo_children():
                try:
                    child.destroy()
                except Exception:
                    pass
        return True
    except Exception:
        return False


def _neto_sohbet_mesaj_sil(widget):
    try:
        if widget is not None and widget.winfo_exists():
            widget.destroy()
            return True
    except Exception:
        pass
    return False


def _neto_sohbet_balonu_ekle(metin, rol="assistant"):
    """Jarvis esintili NetOps sohbet kartları: temiz, neon vurgulu, link dökümü göstermeyen akış."""
    try:
        alan = globals().get("chat_bubble_area")
        if alan is None or not alan.winfo_exists():
            return None
        metin = komut_token_temizle(str(metin or "")).strip()
        if not metin:
            return None
        try:
            metin = arayuz_diline_cevir(metin)
        except Exception:
            pass

        rol_norm = str(rol).lower()
        is_user = rol_norm in {"user", "kullanici", "kullanıcı"}
        is_thinking = rol_norm in {"thinking", "dusunuyor", "düşünüyor"}

        try:
            if neto_startup_phase(10) and not is_user:
                return None
        except Exception:
            pass

        _neto_sohbet_ekrani_ac()

        accent = aktif_palet.get("neon", "#2B7CFF")
        bg = aktif_palet.get("bg", "#07090F")
        card = aktif_palet.get("card", "#151821")
        dim = aktif_palet.get("text_dim", "#9AA7B8")
        text_main = aktif_palet.get("text_main", "#F4F7FF")

        row = ctk.CTkFrame(alan, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(9, 9))

        if is_user:
            bubble = ctk.CTkFrame(
                row,
                fg_color="#22252D",
                corner_radius=19,
                border_width=1,
                border_color="#343946",
            )
            bubble.pack(side="right", anchor="e", padx=(120, 4))
            label = ctk.CTkLabel(
                bubble,
                text=emoji_ekle(metin),
                text_color="#F7F7F8",
                font=("Segoe UI Semibold", 13),
                justify="left",
                wraplength=390,
            )
            label.pack(padx=16, pady=11)
        else:
            left = ctk.CTkFrame(row, fg_color="transparent")
            left.pack(side="left", anchor="w", fill="x", expand=True, padx=(4, 58))

            avatar = ctk.CTkFrame(
                left,
                width=34,
                height=34,
                corner_radius=17,
                fg_color=bg,
                border_width=1,
                border_color=accent,
            )
            avatar.pack(side="left", anchor="n", padx=(0, 11), pady=(1, 0))
            avatar.pack_propagate(False)
            ctk.CTkLabel(
                avatar,
                text="N",
                text_color=accent,
                font=("Segoe UI Black", 13),
            ).pack(expand=True)

            shell = ctk.CTkFrame(
                left,
                fg_color=card,
                corner_radius=18,
                border_width=1,
                border_color="#143D4A" if is_thinking else accent,
            )
            shell.pack(side="left", fill="x", expand=True)

            top = ctk.CTkFrame(shell, fg_color="transparent")
            top.pack(fill="x", padx=15, pady=(12, 4))
            ctk.CTkLabel(
                top,
                text="NETOPS HARBILIG" if not is_thinking else "HARBILIG CORE",
                text_color=accent,
                font=("Segoe UI Semibold", 11),
                anchor="w",
            ).pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(
                top,
                text="● READY" if not is_thinking else "● PROCESSING",
                text_color="#00D4C0" if not is_thinking else "#FFCC00",
                font=("Segoe UI", 10),
                anchor="e",
            ).pack(side="right")

            ctk.CTkFrame(shell, fg_color=accent, height=1, corner_radius=0).pack(fill="x", padx=15, pady=(0, 9))

            if is_thinking:
                body_text = "NetOps veriyi hazırlıyor..."
                body_color = dim
                body_font = ("Segoe UI", 12, "italic")
            else:
                body_text = emoji_ekle(metin)
                body_color = text_main
                body_font = ("Segoe UI", 13)

            label = ctk.CTkLabel(
                shell,
                text=body_text,
                text_color=body_color,
                font=body_font,
                justify="left",
                anchor="w",
                wraplength=650,
            )
            label.pack(fill="x", padx=15, pady=(0, 14))

        children = list(alan.winfo_children())
        if len(children) > 40:
            for child in children[:-40]:
                try:
                    child.destroy()
                except Exception:
                    pass
        try:
            canvas = getattr(alan, "_parent_canvas", None)
            if canvas is not None:
                alan.after(70, lambda: canvas.yview_moveto(1.0))
        except Exception:
            pass
        return row
    except Exception as exc:
        try:
            print(f"[CHAT_BUBBLE_ERROR] {exc}", flush=True)
        except Exception:
            pass
        return None

def animasyonlu_yazi(metin):
    """Ana ekrana yazı basar.

    Eski harf harf animasyon uzun AI cevaplarında Windows'un "Yanıt Vermiyor"
    göstermesine sebep olabiliyordu. Bu sürüm cevabı direkt basar.
    """
    global animasyon_id

    try:
        metin = komut_token_temizle(metin)
    except Exception:
        metin = str(metin) if metin is not None else ""

    try:
        metin = arayuz_diline_cevir(metin)
    except Exception:
        metin = str(metin or "")

    if not metin:
        metin = "Done."

    # Güncelleme modülünden gerçek yeni sürüm bildirimi gelirse ikinci sesi çal.
    # Bu kontrol yalnızca güçlü "yeni sürüm mevcut" ifadelerinde tetiklenir.
    try:
        neto_guncelleme_sesi_tetikle(metin)
    except Exception:
        pass
    try:
        _netops_anyspeech_warning_temizle(metin)
    except Exception:
        pass

    if 'root' in globals() and root:
        try:
            if animasyon_id:
                root.after_cancel(animasyon_id)
                animasyon_id = None
        except Exception:
            pass
        try:
            _neto_sohbet_balonu_ekle(metin, "assistant")
        except Exception:
            pass

        if 'etiket' in globals():
            try:
                etiket.configure(text=emoji_ekle(metin))
            except Exception:
                try:
                    etiket.configure(text=str(metin))
                except Exception:
                    pass

    # Sesli okuma UI'yi kasmasın diye arka planda ve kısa cevaplarda çalışsın.
    try:
        okunacak = metinden_emoji_temizle(str(metin))
        if okunacak and len(okunacak) <= 220 and not neto_startup_phase(10):
            threading.Thread(target=lambda: sesli_oku(okunacak), daemon=True).start()
    except Exception:
        pass


_NETOPS_ANYSPEECH_UYARI_DURUMU: dict[str, Any] = {
    "active": False,
    "text": "",
    "ts": 0.0,
    "job": None,
    "token": 0,
}


def _netops_anyspeech_warning_temizle(metin=None, force=False):
    durum = _NETOPS_ANYSPEECH_UYARI_DURUMU
    if not durum.get("active"):
        return
    if not force:
        mevcut = str(metin or "").strip()
        if mevcut and mevcut == str(durum.get("text") or ""):
            return

    durum["active"] = False
    durum["text"] = ""
    durum["ts"] = 0.0
    durum["token"] = int(durum.get("token") or 0) + 1

    try:
        job = durum.get("job")
        root_obj = globals().get("root")
        if job and root_obj is not None and root_obj.winfo_exists():
            root_obj.after_cancel(job)
    except Exception:
        pass
    durum["job"] = None

    try:
        if "hero_status_frame" in globals() and hero_status_frame and hero_status_frame.winfo_exists():
            hero_status_frame.configure(
                border_color=aktif_palet["entry_border"],
                fg_color=aktif_palet["card"],
            )
    except Exception:
        pass
    try:
        if "etiket" in globals() and etiket and etiket.winfo_exists():
            etiket.configure(text_color=aktif_palet["neon"])
    except Exception:
        pass


def _netops_anyspeech_uyari_goster(metin):
    mesaj = str(metin or "").strip()
    if not mesaj:
        return

    durum = _NETOPS_ANYSPEECH_UYARI_DURUMU
    now = time.monotonic()
    if mesaj == str(durum.get("text") or "") and (now - float(durum.get("ts") or 0.0)) < 12.0:
        return

    durum["active"] = True
    durum["text"] = mesaj
    durum["ts"] = now
    durum["token"] = int(durum.get("token") or 0) + 1
    token = int(durum["token"])
    warning_text = T("tts_unavailable") if "T" in globals() else "⚠️ Yerel TTS kullanılamıyor. Model indirilemedi ya da yüklenemedi."

    try:
        print(f"[TTS_UI_WARNING] {warning_text}", flush=True)
    except Exception:
        pass

    root_obj = globals().get("root")

    def _uygula():
        if token != int(_NETOPS_ANYSPEECH_UYARI_DURUMU.get("token") or 0):
            return
        try:
            if "hero_status_frame" in globals() and hero_status_frame and hero_status_frame.winfo_exists():
                hero_status_frame.configure(
                    border_color="#ef4444",
                    fg_color=aktif_palet["card"],
                )
        except Exception:
            pass
        try:
            if "etiket" in globals() and etiket and etiket.winfo_exists():
                etiket.configure(text=warning_text, text_color="#ff7b7b")
        except Exception:
            pass

        try:
            old_job = _NETOPS_ANYSPEECH_UYARI_DURUMU.get("job")
            if old_job and root_obj is not None and root_obj.winfo_exists():
                try:
                    root_obj.after_cancel(old_job)
                except Exception:
                    pass
            if root_obj is not None and root_obj.winfo_exists():
                _NETOPS_ANYSPEECH_UYARI_DURUMU["job"] = root_obj.after(
                    9000,
                    lambda: _netops_anyspeech_warning_temizle(force=True),
                )
        except Exception:
            pass

    if root_obj is not None and hasattr(root_obj, "after"):
        try:
            root_obj.after(0, _uygula)
        except Exception:
            _uygula()
    else:
        _uygula()


try:
    if callable(anyspeech_set_warning_callback):
        anyspeech_set_warning_callback(_netops_anyspeech_uyari_goster)
except Exception:
    pass


def _netops_tts_isit():
    def _worker():
        try:
            preload_fn = globals().get("anyspeech_preload_voice")
            if callable(preload_fn):
                preload_fn(logger=lambda msg: print(f"[TTS_WARMUP] {msg}", flush=True))
        except Exception as exc:
            try:
                print(f"[TTS_WARMUP_ERR] {exc}", flush=True)
            except Exception:
                pass

    threading.Thread(target=_worker, daemon=True).start()


_NETO_SELF_HEAL_DURUMU: dict[str, float] = {"ts": 0.0}


def _neto_kendini_onar(kaynak: str = "", hata: Exception | str | None = None) -> None:
    now = time.monotonic()
    onceki = float(_NETO_SELF_HEAL_DURUMU.get("ts") or 0.0)
    if (now - onceki) < 1.0:
        return
    _NETO_SELF_HEAL_DURUMU["ts"] = now

    try:
        print(f"[SELF_HEAL] {kaynak}: {hata}", flush=True)
    except Exception:
        pass

    try:
        reset_fn = globals().get("anyspeech_reset_voice_cache")
        if callable(reset_fn):
            reset_fn()
    except Exception:
        pass

    try:
        root_obj = globals().get("root")
        if root_obj is not None and hasattr(root_obj, "after"):
            root_obj.after(120, _netops_tts_isit)
        else:
            _netops_tts_isit()
    except Exception:
        pass

    def _uygula():
        try:
            if "giris" in globals() and giris and giris.winfo_exists():
                giris.configure(state="normal")
                _neto_widget_focus_guvenli(giris, kaynak="self_heal_focus")
        except Exception:
            pass
        try:
            if "btn_gonder" in globals() and btn_gonder and btn_gonder.winfo_exists():
                btn_gonder.configure(state="normal")
        except Exception:
            pass
        try:
            if "main_c" in globals() and main_c and main_c.winfo_exists():
                main_c.update_idletasks()
        except Exception:
            pass
        try:
            tema_yenile = globals().get("_neto_tema_yenile_planla")
            if callable(tema_yenile):
                tema_yenile(settings=False, delay=0)
        except Exception:
            pass

    try:
        root_obj = globals().get("root")
        if root_obj is not None and hasattr(root_obj, "after"):
            root_obj.after(0, _uygula)
        else:
            _uygula()
    except Exception:
        _uygula()




def _neto_mini_doctor_baslat() -> None:
    """Run a tiny startup doctor without blocking the Tk UI."""
    def _ui_message(message: str, ok: bool) -> None:
        try:
            color = aktif_palet["neon"] if ok else "#ff7b7b"
            if "hero_status_frame" in globals() and hero_status_frame and hero_status_frame.winfo_exists():
                hero_status_frame.configure(
                    fg_color=aktif_palet["card"],
                    border_color=aktif_palet["entry_border"] if ok else "#ef4444",
                    border_width=1,
                )
            if "etiket" in globals() and etiket and etiket.winfo_exists():
                etiket.configure(text=message, text_color=color)
        except Exception:
            pass

    def _worker() -> None:
        try:
            module = _neto_lazy_import("neto_doctor")
            result = module.quick_check(Path(__file__).resolve().parent)
            ok = bool(result.get("ok"))
            message = str(result.get("message") or "Mini Doktor: Kontrol tamamlandi.")
            try:
                print(f"[MINI_DOCTOR] {message}", flush=True)
                if result.get("fixes"):
                    print(f"[MINI_DOCTOR_FIX_HINT] {result.get('fixes')}", flush=True)
            except Exception:
                pass
            root_obj = globals().get("root")
            if root_obj is not None and hasattr(root_obj, "after"):
                root_obj.after(0, lambda: _ui_message(message, ok))
        except Exception as exc:
            try:
                print(f"[MINI_DOCTOR_ERROR] {exc}", flush=True)
            except Exception:
                pass
            try:
                _neto_kendini_onar("mini_doctor", exc)
            except Exception:
                pass

    threading.Thread(target=_worker, daemon=True).start()

def _neto_widget_focus_guvenli(widget, *, force: bool = False, kaynak: str = "focus") -> bool:
    try:
        if widget is None:
            return False
        exists = getattr(widget, "winfo_exists", None)
        if callable(exists) and not exists():
            return False
        if force and hasattr(widget, "focus_force"):
            widget.focus_force()
        elif hasattr(widget, "focus_set"):
            widget.focus_set()
        elif hasattr(widget, "focus"):
            widget.focus()
        return True
    except Exception as exc:
        _neto_kendini_onar(kaynak, exc)
        return False


_NETO_LIVE_SELF_HEAL_DURUMU: dict[str, Any] = {
    "ts": 0.0,
    "scheduled": False,
    "attempts": 0,
    "last_reason": "",
}


def _neto_live_otomatik_toparla(neden: str = "") -> None:
    controller = globals().get("live_mode_controller")
    try:
        if controller and controller.is_running():
            return
    except Exception:
        pass

    durum = _NETO_LIVE_SELF_HEAL_DURUMU
    now = time.monotonic()
    if bool(durum.get("scheduled")):
        return
    if (now - float(durum.get("ts") or 0.0)) < 12.0 and int(durum.get("attempts") or 0) >= 1:
        return

    durum["scheduled"] = True
    durum["ts"] = now
    durum["attempts"] = int(durum.get("attempts") or 0) + 1
    durum["last_reason"] = str(neden or "")

    def _retry():
        durum["scheduled"] = False
        try:
            ctrl = globals().get("live_mode_controller")
            if ctrl and ctrl.is_running():
                durum["attempts"] = 0
                return
        except Exception:
            pass

        try:
            if live_mode_baslat():
                durum["attempts"] = 0
                print(f"[SELF_HEAL] Live yeniden baslatildi: {neden}", flush=True)
                return
        except Exception as exc:
            _neto_kendini_onar("live_auto_restart", exc)

        print(f"[SELF_HEAL] Live yeniden baslatilamadi: {neden}", flush=True)

    root_obj = globals().get("root")
    if root_obj is not None and hasattr(root_obj, "after"):
        try:
            root_obj.after(1400, _retry)
        except Exception:
            _retry()


# ------------------------------------------------------------
# VOLUME CONTROL v10.34
# Real Windows master volume for Now Playing.
# Backend order:
# 1) pycaw/comtypes
# 2) pure ctypes Windows CoreAudio fallback, no pip needed
# ------------------------------------------------------------
def volume_lang():
    try:
        lang = dil_getir()
        return "tr" if str(lang).lower().startswith("tr") else "en"
    except Exception:
        try:
            h = veri_yukle()
            return "tr" if str(h.get("dil", "en")).lower().startswith("tr") else "en"
        except Exception:
            return "en"

def volume_text(key) -> str:
    tr = {
        "label": "Ses",
        "unavailable": "Ses: Windows sesine bağlanamadı",
        "changed": "Ses seviyesi {value}% yapıldı.",
        "error": "Ses ayarlanamadı",
        "backend_ok": "Windows sesi bağlı",
        "backend_missing": "Windows sesine bağlanamadı",
        "backend_ctypes": "Windows sesi bağlı (CoreAudio)",
        "backend_pycaw": "Windows sesi bağlı (pycaw)",
        "muted": "Sessiz",
        "unmuted": "Açık",
    }
    en = {
        "label": "Volume",
        "unavailable": "Volume: could not connect to Windows audio",
        "changed": "Volume set to {value}%.",
        "error": "Could not set volume",
        "backend_ok": "Windows volume connected",
        "backend_missing": "Could not connect to Windows volume",
        "backend_ctypes": "Windows volume connected (CoreAudio)",
        "backend_pycaw": "Windows volume connected (pycaw)",
        "muted": "Muted",
        "unmuted": "Unmuted",
    }
    return str((tr if volume_lang() == "tr" else en).get(key, key))

def _volume_com_release(ptr):
    try:
        import ctypes
        if not ptr:
            return
        vtbl = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl[2])
        release(ptr)
    except Exception:
        pass

def _volume_guid_from_string(guid_text):
    import ctypes, uuid
    u = uuid.UUID(guid_text)
    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", ctypes.c_ulong),
            ("Data2", ctypes.c_ushort),
            ("Data3", ctypes.c_ushort),
            ("Data4", ctypes.c_ubyte * 8),
        ]
    return GUID(
        u.time_low,
        u.time_mid,
        u.time_hi_version,
        (ctypes.c_ubyte * 8).from_buffer_copy(u.bytes[8:])
    )

def volume_get_endpoint_pycaw():
    """Returns IAudioEndpointVolume using pycaw.

    Supports both APIs:
    - Old pycaw/comtypes: device.Activate(...)
    - Newer pycaw AudioDevice: device.EndpointVolume
    """
    try:
        if not HAS_PYCAW:
            return None

        device = AudioUtilities.GetSpeakers()

        # Newer pycaw versions may return an AudioDevice with EndpointVolume already attached.
        for attr in ("EndpointVolume", "endpoint_volume", "volume"):
            try:
                endpoint = getattr(device, attr, None)
                if endpoint is not None and hasattr(endpoint, "GetMasterVolumeLevelScalar"):
                    return endpoint
            except Exception:
                pass

        # Old pycaw / comtypes API.
        if hasattr(device, "Activate"):
            interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            endpoint = ctypes_cast(interface, POINTER(IAudioEndpointVolume))
            return endpoint

        try:
            now_playing_log(f"[VOLUME_PYCAW_ENDPOINT_ERROR] unsupported pycaw device: {type(device)} attrs={dir(device)[:40]}")
        except Exception:
            pass
        return None

    except Exception as e:
        try:
            now_playing_log(f"[VOLUME_PYCAW_ENDPOINT_ERROR] {e}")
        except Exception:
            pass
        return None


def volume_get_endpoint_ctypes():
    """Returns raw IAudioEndpointVolume pointer using ctypes only, or None."""
    try:
        import ctypes
        from ctypes import wintypes

        if os.name != "nt":
            return None

        ole32 = ctypes.OleDLL("ole32")
        try:
            ole32.CoInitialize(None)
        except Exception:
            pass

        CLSID_MMDeviceEnumerator = _volume_guid_from_string("BCDE0395-E52F-467C-8E3D-C4579291692E")
        IID_IMMDeviceEnumerator = _volume_guid_from_string("A95664D2-9614-4F35-A746-DE8DB63617E6")
        IID_IAudioEndpointVolume = _volume_guid_from_string("5CDF2C82-841E-4546-9722-0CF74078229A")

        CLSCTX_ALL_LOCAL = 23
        eRender = 0
        eMultimedia = 1

        enumerator = ctypes.c_void_p()
        hr = ole32.CoCreateInstance(
            ctypes.byref(CLSID_MMDeviceEnumerator),
            None,
            CLSCTX_ALL_LOCAL,
            ctypes.byref(IID_IMMDeviceEnumerator),
            ctypes.byref(enumerator)
        )
        if hr != 0 or not enumerator.value:
            return None

        try:
            enum_vtbl = ctypes.cast(enumerator, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
            GetDefaultAudioEndpoint = ctypes.WINFUNCTYPE(
                ctypes.c_long,
                ctypes.c_void_p,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.POINTER(ctypes.c_void_p)
            )(enum_vtbl[4])

            device = ctypes.c_void_p()
            hr = GetDefaultAudioEndpoint(enumerator, eRender, eMultimedia, ctypes.byref(device))
            if hr != 0 or not device.value:
                return None

            try:
                dev_vtbl = ctypes.cast(device, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
                Activate = ctypes.WINFUNCTYPE(
                    ctypes.c_long,
                    ctypes.c_void_p,
                    ctypes.POINTER(type(IID_IAudioEndpointVolume)),
                    wintypes.DWORD,
                    ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_void_p)
                )(dev_vtbl[3])

                endpoint = ctypes.c_void_p()
                hr = Activate(
                    device,
                    ctypes.byref(IID_IAudioEndpointVolume),
                    CLSCTX_ALL_LOCAL,
                    None,
                    ctypes.byref(endpoint)
                )
                if hr != 0 or not endpoint.value:
                    return None

                return endpoint
            finally:
                _volume_com_release(device)
        finally:
            _volume_com_release(enumerator)

    except Exception as e:
        try:
            now_playing_log(f"[VOLUME_CTYPES_ENDPOINT_ERROR] {e}")
        except Exception:
            pass
        return None


def volume_backend_debug():
    """Returns short debug text for terminal/logging."""
    try:
        parts = []
        try:
            dev = AudioUtilities.GetSpeakers() if HAS_PYCAW else None
            parts.append(f"pycaw_device={type(dev).__name__ if dev is not None else 'None'}")
            if dev is not None:
                parts.append(f"has_Activate={hasattr(dev, 'Activate')}")
                parts.append(f"has_EndpointVolume={hasattr(dev, 'EndpointVolume')}")
        except Exception as e:
            parts.append(f"pycaw_error={e}")

        try:
            v = volume_get_percent()
            parts.append(f"volume={v}")
        except Exception as e:
            parts.append(f"get_error={e}")

        try:
            parts.append(f"backend={volume_backend_name()}")
        except Exception as e:
            parts.append(f"backend_error={e}")

        return " | ".join(parts)
    except Exception as e:
        return f"debug_error={e}"


def volume_backend_name():
    try:
        if HAS_PYCAW and volume_get_endpoint_pycaw() is not None:
            return "pycaw"
    except Exception:
        pass
    try:
        ep = volume_get_endpoint_ctypes()
        if ep is not None:
            _volume_com_release(ep)
            return "ctypes"
    except Exception:
        pass
    return None

def volume_backend_available():
    return volume_backend_name() is not None

def volume_get_percent():
    """Returns real Windows master output volume percent or None."""
    # Try pycaw first.
    try:
        endpoint = volume_get_endpoint_pycaw()
        if endpoint is not None:
            return int(round(endpoint.GetMasterVolumeLevelScalar() * 100))
    except Exception as e:
        try:
            now_playing_log(f"[VOLUME_PYCAW_GET_ERROR] {e}")
        except Exception:
            pass

    # ctypes CoreAudio fallback.
    try:
        import ctypes
        endpoint = volume_get_endpoint_ctypes()
        if endpoint is None:
            return None
        try:
            vtbl = ctypes.cast(endpoint, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
            GetMasterVolumeLevelScalar = ctypes.WINFUNCTYPE(
                ctypes.c_long,
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_float)
            )(vtbl[9])
            level = ctypes.c_float()
            hr = GetMasterVolumeLevelScalar(endpoint, ctypes.byref(level))
            if hr != 0:
                return None
            return int(round(float(level.value) * 100))
        finally:
            _volume_com_release(endpoint)
    except Exception as e:
        try:
            now_playing_log(f"[VOLUME_CTYPES_GET_ERROR] {e}")
        except Exception:
            pass
        return None

def volume_get_mute():
    # Try pycaw first.
    try:
        endpoint = volume_get_endpoint_pycaw()
        if endpoint is not None:
            return bool(endpoint.GetMute())
    except Exception:
        pass

    # ctypes CoreAudio fallback.
    try:
        import ctypes
        from ctypes import wintypes
        endpoint = volume_get_endpoint_ctypes()
        if endpoint is None:
            return None
        try:
            vtbl = ctypes.cast(endpoint, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
            GetMute = ctypes.WINFUNCTYPE(
                ctypes.c_long,
                ctypes.c_void_p,
                ctypes.POINTER(wintypes.BOOL)
            )(vtbl[15])
            muted = wintypes.BOOL()
            hr = GetMute(endpoint, ctypes.byref(muted))
            if hr != 0:
                return None
            return bool(muted.value)
        finally:
            _volume_com_release(endpoint)
    except Exception:
        return None

def volume_set_mute(muted, announce=False):
    """Sets the real Windows master mute state."""
    try:
        hedef = bool(muted)

        # Try pycaw first.
        endpoint = volume_get_endpoint_pycaw()
        if endpoint is not None:
            endpoint.SetMute(hedef, None)
            volume_ui_update()
            if announce:
                animasyonlu_yazi(volume_text("muted" if hedef else "unmuted"))
            return True

        # ctypes CoreAudio fallback.
        try:
            import ctypes
            from ctypes import wintypes

            endpoint2 = volume_get_endpoint_ctypes()
            if endpoint2 is None:
                if announce:
                    animasyonlu_yazi(volume_text("unavailable"))
                volume_ui_update(None, backend_missing=True)
                return False

            try:
                vtbl = ctypes.cast(endpoint2, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
                SetMute = ctypes.WINFUNCTYPE(
                    ctypes.c_long,
                    ctypes.c_void_p,
                    wintypes.BOOL,
                    ctypes.c_void_p
                )(vtbl[14])
                hr = SetMute(endpoint2, wintypes.BOOL(hedef), None)
                if hr != 0:
                    if announce:
                        animasyonlu_yazi(volume_text("unavailable"))
                    return False
                volume_ui_update()
                if announce:
                    animasyonlu_yazi(volume_text("muted" if hedef else "unmuted"))
                return True
            finally:
                _volume_com_release(endpoint2)
        except Exception as e:
            try:
                now_playing_log(f"[VOLUME_CTYPES_MUTE_ERROR] {e}")
            except Exception:
                pass
    except Exception as e:
        try:
            now_playing_log(f"[VOLUME_MUTE_ERROR] {e}")
        except Exception:
            pass
        try:
            if announce:
                animasyonlu_yazi(f"{volume_text('error')}: {e}")
        except Exception:
            pass

    try:
        volume_ui_update(None, backend_missing=True)
    except Exception:
        pass
    return False

def volume_set_percent(value, announce=False):
    """Sets real Windows master output volume percent using pycaw or ctypes CoreAudio."""
    try:
        hedef = int(max(0, min(100, float(value))))

        # Try pycaw first.
        endpoint = volume_get_endpoint_pycaw()
        if endpoint is not None:
            try:
                if hedef > 0:
                    endpoint.SetMute(False, None)
            except Exception:
                pass
            endpoint.SetMasterVolumeLevelScalar(hedef / 100.0, None)
            volume_ui_update(hedef)
            if announce:
                animasyonlu_yazi(volume_text("changed").format(value=hedef))
            return True

        # ctypes CoreAudio fallback.
        try:
            import ctypes
            from ctypes import wintypes
            endpoint2 = volume_get_endpoint_ctypes()
            if endpoint2 is None:
                if announce:
                    animasyonlu_yazi(volume_text("unavailable"))
                volume_ui_update(hedef, backend_missing=True)
                return False

            try:
                vtbl = ctypes.cast(endpoint2, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents

                if hedef > 0:
                    try:
                        SetMute = ctypes.WINFUNCTYPE(
                            ctypes.c_long,
                            ctypes.c_void_p,
                            wintypes.BOOL,
                            ctypes.c_void_p
                        )(vtbl[14])
                        SetMute(endpoint2, wintypes.BOOL(False), None)
                    except Exception:
                        pass

                SetMasterVolumeLevelScalar = ctypes.WINFUNCTYPE(
                    ctypes.c_long,
                    ctypes.c_void_p,
                    ctypes.c_float,
                    ctypes.c_void_p
                )(vtbl[7])
                hr = SetMasterVolumeLevelScalar(endpoint2, ctypes.c_float(hedef / 100.0), None)
                if hr != 0:
                    if announce:
                        animasyonlu_yazi(volume_text("unavailable"))
                    return False

                volume_ui_update(hedef)
                if announce:
                    animasyonlu_yazi(volume_text("changed").format(value=hedef))
                return True
            finally:
                _volume_com_release(endpoint2)
        except Exception as e:
            try:
                now_playing_log(f"[VOLUME_CTYPES_SET_ERROR] {e}")
            except Exception:
                pass

    except Exception as e:
        try:
            now_playing_log(f"[VOLUME_SET_ERROR] {e}")
        except Exception:
            pass
        try:
            if announce:
                animasyonlu_yazi(f"{volume_text('error')}: {e}")
        except Exception:
            pass

    try:
        volume_ui_update(None, backend_missing=True)
    except Exception:
        pass
    return False

def volume_ui_update(value=None, backend_missing=False):
    """Updates Now Playing volume label/slider. Reads real Windows volume if value is None."""
    try:
        if value is None and not backend_missing:
            value = volume_get_percent()

        lbl = globals().get("volume_label") or globals().get("now_playing_volume_label")
        sld = globals().get("volume_slider") or globals().get("now_playing_volume_slider")

        if value is None or backend_missing:
            if lbl:
                lbl.configure(text=f"🔊 {volume_text('unavailable')}")
            return

        value = int(max(0, min(100, value)))
        mute = volume_get_mute()
        mute_text = ""
        if mute is True:
            mute_text = f" • {volume_text('muted')}"

        if lbl:
            lbl.configure(text=f"🔊 {volume_text('label')}: {value}%{mute_text}")

        if sld and not globals().get("volume_slider_dragging", False):
            try:
                sld.set(value)
            except Exception:
                pass
    except Exception as e:
        try:
            now_playing_log(f"[VOLUME_UI_UPDATE_ERROR] {e}")
        except Exception:
            pass

_NETOPS_TABLET_VOICE_LOCK = threading.RLock()
_NETOPS_TABLET_VOICE_SIGNATURE = None
_NETOPS_TABLET_AUDIO_REASONS: set[str] = set()
_NETOPS_TABLET_AUDIO_MUTED_BY_NETOPS = False
_NETOPS_TABLET_AUDIO_STREAM_PATH = ""


def _netops_normalize_text(metin):
    return re.sub(r"\s+", " ", str(metin or "")).strip()


def _netops_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return float(default)


def _netops_device_hub_module():
    try:
        return _neto_lazy_import("neto_device_hub")
    except Exception:
        return None


def _netops_tablet_audio_stream_path() -> str:
    global _NETOPS_TABLET_AUDIO_STREAM_PATH
    if _NETOPS_TABLET_AUDIO_STREAM_PATH:
        return _NETOPS_TABLET_AUDIO_STREAM_PATH
    try:
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        audio_dir = Path(base) / "NetoAssistant" / "logs"
        audio_dir.mkdir(parents=True, exist_ok=True)
        fd, raw_path = tempfile.mkstemp(prefix="neto_tablet_audio_", suffix=".jsonl", dir=str(audio_dir))
        os.close(fd)
        try:
            Path(raw_path).write_text("", encoding="utf-8")
        except Exception:
            pass
        _NETOPS_TABLET_AUDIO_STREAM_PATH = raw_path
        mod = _netops_device_hub_module()
        if mod is not None and hasattr(mod, "device_hub_set_audio_stream_path"):
            try:
                mod.device_hub_set_audio_stream_path(raw_path)
            except Exception:
                pass
        return raw_path
    except Exception:
        _NETOPS_TABLET_AUDIO_STREAM_PATH = ""
        return ""


def _netops_tablet_audio_stream_clear(remove_file: bool = True) -> None:
    global _NETOPS_TABLET_AUDIO_STREAM_PATH
    path = _NETOPS_TABLET_AUDIO_STREAM_PATH
    _NETOPS_TABLET_AUDIO_STREAM_PATH = ""
    mod = _netops_device_hub_module()
    if mod is not None and hasattr(mod, "device_hub_clear_audio_stream_path"):
        try:
            mod.device_hub_clear_audio_stream_path()
        except Exception:
            pass
    if remove_file and path:
        try:
            os.remove(path)
        except Exception:
            pass


def _netops_online_tablet_devices():
    mod = _netops_device_hub_module()
    if mod is None:
        return []
    try:
        snapshot = mod.device_hub_snapshot()
        devices = []
        for item in snapshot.get("devices", []) or []:
            if isinstance(item, dict) and item.get("online"):
                devices.append(dict(item))
        devices.sort(
            key=lambda item: (
                _netops_float(item.get("last_seen"), 0.0),
                str(item.get("display_name") or item.get("device_name") or "").casefold(),
            ),
            reverse=True,
        )
        return devices
    except Exception as exc:
        try:
            now_playing_log(f"[TABLET_VOICE_SNAPSHOT_ERROR] {exc}")
        except Exception:
            pass
        return []


def _netops_pick_tablet_voice_device(devices):
    if not devices:
        return None
    for device in devices:
        caps = device.get("capabilities")
        if not isinstance(caps, dict):
            caps = {}
        blob = " ".join(
            [
                str(device.get("alias") or ""),
                str(device.get("display_name") or ""),
                str(device.get("device_name") or ""),
                str(device.get("manufacturer") or ""),
                str(device.get("model") or ""),
                " ".join(f"{k}:{v}" for k, v in caps.items()),
            ]
        ).lower()
        if any(keyword in blob for keyword in ("tablet", "android", "voice_output", "speaker_output", "tts_output")):
            return device
    return devices[0]


def _netops_voice_level_for_state(state):
    return {
        "idle": 0,
        "stopped": 0,
        "off": 0,
        "live": 24,
        "mic": 38,
        "listening": 68,
        "thinking": 52,
        "answer": 62,
        "speaking": 92,
        "ready": 40,
    }.get(str(state or "").strip().lower(), 48)


def _netops_tablet_audio_set_active(reason, active):
    global _NETOPS_TABLET_AUDIO_MUTED_BY_NETOPS
    reason = str(reason or "tablet_voice").strip() or "tablet_voice"
    active = bool(active)
    with _NETOPS_TABLET_VOICE_LOCK:
        if active:
            _NETOPS_TABLET_AUDIO_REASONS.add(reason)
        else:
            _NETOPS_TABLET_AUDIO_REASONS.discard(reason)
        should_mute = bool(_NETOPS_TABLET_AUDIO_REASONS)
        muted_by_us = _NETOPS_TABLET_AUDIO_MUTED_BY_NETOPS

    if should_mute:
        try:
            current = volume_get_mute()
        except Exception:
            current = None
        if current is not True and volume_set_mute(True):
            with _NETOPS_TABLET_VOICE_LOCK:
                _NETOPS_TABLET_AUDIO_MUTED_BY_NETOPS = True
    elif muted_by_us:
        if volume_set_mute(False):
            with _NETOPS_TABLET_VOICE_LOCK:
                _NETOPS_TABLET_AUDIO_MUTED_BY_NETOPS = False


def _netops_send_tablet_voice_event(state, text="", level=None, speak=False, reason="tablet_voice", broadcast=None, async_dispatch=False):
    state = str(state or "idle").strip().lower() or "idle"
    reason = str(reason or "tablet_voice").strip() or "tablet_voice"
    text = _netops_normalize_text(text)
    if level is None:
        level = _netops_voice_level_for_state(state)
    try:
        level_value = int(max(0, min(100, round(float(level)))))
    except Exception:
        level_value = _netops_voice_level_for_state(state)

    if broadcast is None:
        broadcast = not bool(speak)

    def worker():
        nonlocal state, text, level_value, speak, reason, broadcast
        devices = _netops_online_tablet_devices()
        if not devices:
            _netops_tablet_audio_set_active(reason, False)
            return False

        targets = devices if broadcast else [_netops_pick_tablet_voice_device(devices)]
        targets = [device for device in targets if isinstance(device, dict) and device.get("device_id")]
        if not targets:
            _netops_tablet_audio_set_active(reason, False)
            return False

        signature = (
            reason,
            state,
            text[:120],
            level_value,
            bool(speak),
            tuple(str(device.get("device_id")) for device in targets),
        )
        with _NETOPS_TABLET_VOICE_LOCK:
            global _NETOPS_TABLET_VOICE_SIGNATURE
            if signature == _NETOPS_TABLET_VOICE_SIGNATURE:
                _netops_tablet_audio_set_active(reason, state not in {"idle", "stopped", "off"})
                return True
            _NETOPS_TABLET_VOICE_SIGNATURE = signature

        _netops_tablet_audio_set_active(reason, state not in {"idle", "stopped", "off"})
        mod = _netops_device_hub_module()
        if mod is None:
            return False

        ok = True
        for index, device in enumerate(targets):
            payload = {
                "state": state,
                "text": text,
                "level": level_value,
                "speak": bool(speak and index == 0),
                "reason": reason,
            }
            try:
                result = mod.device_hub_send_command(device["device_id"], "voice_event", payload, timeout=8)
                if not result.get("ok", False):
                    ok = False
            except Exception as exc:
                ok = False
                try:
                    now_playing_log(f"[TABLET_VOICE_SEND_ERROR] {exc}")
                except Exception:
                    pass
        return ok

    if async_dispatch:
        threading.Thread(target=worker, daemon=True).start()
        return True
    return worker()


def _netops_tablet_voice_state_from_status(metin):
    text = _netops_normalize_text(metin).lower()
    if not text:
        return None
    if any(keyword in text for keyword in ("live durdu", "live kapat", "live kapandi", "live kapandı", "off")):
        return "idle"
    if any(keyword in text for keyword in ("yazıya çevir", "yaziya cevir", "whisper", "işleniyor", "isleniyor", "komut/neteops agent işleniyor", "komut/netops agent işleniyor")):
        return "thinking"
    if any(keyword in text for keyword in ("dinliyor", "mikrofon", "ses seviyesi", "ses düşük", "ses dusuk", "hazırlanıyor", "hazirlaniyor", "hazır", "hazir", "konuşabilirsin", "konusabilirsin", "ready")):
        return "listening"
    if any(keyword in text for keyword in ("cevap", "konuşuyor", "konusuyor", "sesli okuma")):
        return "speaking"
    return None


def _netops_tablet_voice_speak(metin):
    metin = _netops_normalize_text(metin)
    if not metin:
        return False
    devices = _netops_online_tablet_devices()
    if not devices:
        return False
    duration = max(2.0, min(14.0, len(metin) / 18.0))
    if not _netops_send_tablet_voice_event(
        "speaking",
        text=metin,
        level=92,
        speak=True,
        reason="tts",
        broadcast=True,
        async_dispatch=False,
    ):
        return False
    try:
        time.sleep(duration)
    finally:
        _netops_send_tablet_voice_event(
            "idle",
            text="",
            level=0,
            speak=False,
            reason="tts",
            broadcast=True,
            async_dispatch=False,
        )
    return True


def _netops_send_tablet_command(command, args=None, broadcast=True, reason="tablet", async_dispatch=False):
    command = str(command or "").strip()
    if not command:
        return False
    payload_args = dict(args or {})

    def worker():
        devices = _netops_online_tablet_devices()
        if not devices:
            return False
        targets = devices if broadcast else [_netops_pick_tablet_voice_device(devices)]
        targets = [device for device in targets if isinstance(device, dict) and device.get("device_id")]
        if not targets:
            return False
        mod = _netops_device_hub_module()
        if mod is None:
            return False
        ok = True
        for device in targets:
            try:
                result = mod.device_hub_send_command(device["device_id"], command, dict(payload_args), timeout=8)
                if not result.get("ok", False):
                    ok = False
            except Exception as exc:
                ok = False
                try:
                    now_playing_log(f"[TABLET_CMD_ERROR] {command}: {exc}")
                except Exception:
                    pass
        return ok

    if async_dispatch:
        threading.Thread(target=worker, daemon=True).start()
        return True
    return worker()

def volume_slider_changed(value):
    global volume_slider_dragging
    try:
        volume_slider_dragging = True
        value = int(round(float(value)))
        ok = volume_set_percent(value, announce=False)
        lbl = globals().get("volume_label") or globals().get("now_playing_volume_label")
        if lbl:
            if ok:
                lbl.configure(text=f"🔊 {volume_text('label')}: {value}%")
            else:
                lbl.configure(text=f"🔊 {volume_text('unavailable')}")
    except Exception as e:
        try:
            now_playing_log(f"[VOLUME_SLIDER_ERROR] {e}")
        except Exception:
            pass
    finally:
        try:
            root.after(180, lambda: globals().__setitem__("volume_slider_dragging", False))
        except Exception:
            volume_slider_dragging = False

def volume_refresh_loop():
    try:
        volume_ui_update()
        root.after(1000, volume_refresh_loop)
    except Exception:
        pass

def now_playing_volume_set(value):
    """Volume slider handler for Now Playing screen."""
    return volume_slider_changed(value)

def now_playing_volume_refresh():
    """Refresh volume label/slider inside Now Playing overlay from real Windows volume."""
    try:
        volume_ui_update()
    except Exception:
        pass

def now_playing_volume_refresh_loop():
    """Runs while Now Playing overlay exists; keeps Windows volume percentage live."""
    try:
        if now_playing_overlay and now_playing_overlay.winfo_exists():
            now_playing_volume_refresh()
            root.after(500, now_playing_volume_refresh_loop)
    except Exception:
        pass

# ------------------------------------------------------------
# GENİŞLETİLMİŞ SİSTEM İŞLEMCİSİ (DAHA AKILLI + NetOps Agent)
# ------------------------------------------------------------
_NETO_POWER_ACTIONS = {
    "shutdown": (["shutdown.exe", "/s", "/t", "1"], "Bilgisayar kapatılıyor... 🔌"),
    "restart": (["shutdown.exe", "/r", "/t", "1"], "Bilgisayar yeniden başlatılıyor... 🔄"),
    "sleep": (["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], "Uyku moduna geçiliyor... 😴"),
}


def _neto_power_action_execute(action):
    command_and_message = _NETO_POWER_ACTIONS.get(str(action or ""))
    if not command_and_message:
        return "İşlem iptal."
    command, message = command_and_message
    try:
        subprocess.Popen(
            command,
            shell=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return message
    except Exception as exc:
        crash_guard.log(f"[POWER_ACTION_ERROR] action={action}: {exc}")
        return f"Sistem işlemi başlatılamadı: {exc}"



_NETO_MINI_LINUX_WINDOW = None


def _neto_mini_linux_ekran_ac():
    """Mini Linux ana ekranini acar; Agent'in kendi Linux alanini gosterir."""
    global _NETO_MINI_LINUX_WINDOW
    try:
        root_obj = globals().get("root")
        if root_obj is None or not root_obj.winfo_exists():
            return False

        if _NETO_MINI_LINUX_WINDOW is not None and _NETO_MINI_LINUX_WINDOW.winfo_exists():
            _NETO_MINI_LINUX_WINDOW.lift()
            _NETO_MINI_LINUX_WINDOW.focus_force()
            return True

        win = ctk.CTkToplevel(root_obj)
        _NETO_MINI_LINUX_WINDOW = win
        win.title("Mini Linux")
        win.geometry("720x520")
        win.minsize(560, 420)
        win.configure(fg_color=aktif_palet["bg"])
        try:
            win.transient(root_obj)
            win.lift()
            win.focus_force()
        except Exception:
            pass

        shell = ctk.CTkFrame(win, fg_color=aktif_palet["bg"], corner_radius=0)
        shell.pack(fill="both", expand=True, padx=18, pady=18)
        shell.grid_columnconfigure(0, weight=1)
        shell.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(shell, fg_color=aktif_palet["card"], corner_radius=14, border_width=1, border_color=aktif_palet["entry_border"])
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(header, text="Mini Linux Ana Ekrani", text_color=aktif_palet["text_main"], font=("Segoe UI Semibold", 20), anchor="w")
        title.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 2))
        subtitle = ctk.CTkLabel(header, text="Agent'in guvenli Linux alani", text_color=aktif_palet["text_dim"], font=("Segoe UI", 12), anchor="w")
        subtitle.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 12))

        status_label = ctk.CTkLabel(shell, text="Mini Linux hazirlaniyor...", text_color=aktif_palet["neon"], font=("Segoe UI", 12), anchor="w")
        status_label.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        text_box = ctk.CTkTextbox(shell, fg_color=aktif_palet["card"], text_color=aktif_palet["text_main"], border_width=1, border_color=aktif_palet["entry_border"], corner_radius=12, font=("Consolas", 12), wrap="word")
        text_box.grid(row=2, column=0, sticky="nsew")
        text_box.insert("end", "Mini Linux ekrani acildi.\n")
        text_box.configure(state="disabled")

        bar = ctk.CTkFrame(shell, fg_color="transparent")
        bar.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        bar.grid_columnconfigure((0, 1, 2, 3), weight=1)

        def _write(content):
            try:
                text_box.configure(state="normal")
                text_box.delete("1.0", "end")
                text_box.insert("end", str(content or ""))
                text_box.configure(state="disabled")
            except Exception:
                pass

        def _set_status(content, ok=True):
            try:
                status_label.configure(text=str(content or ""), text_color=aktif_palet["neon"] if ok else "#ff7b7b")
            except Exception:
                pass

        def _linux_request(command, label="Komut"):
            _set_status(f"{label} calisiyor...")
            def worker():
                try:
                    import neto_wsl_bridge
                    durum = neto_wsl_bridge.ensure_bridge_running(Path(__file__).resolve().parent)
                    if not durum.get("ready"):
                        root_obj.after(0, lambda: _set_status("Mini Linux basliyor, tekrar dene.", False))
                        return
                    response = neto_wsl_bridge.assistant_request(command, mode="linux", allow_quick=True, timeout=7.0)
                    text = str((response or {}).get("text") or "Mini Linux cevap vermedi.")
                    root_obj.after(0, lambda: (_set_status("Mini Linux hazir."), _write(text)))
                except Exception as exc:
                    root_obj.after(0, lambda e=exc: (_set_status(f"Mini Linux hatasi: {e}", False), _write(f"Hata: {e}")))
            threading.Thread(target=worker, daemon=True).start()

        def _ana_ekran():
            _set_status("Ana ekran yukleniyor...")
            def worker():
                try:
                    import neto_wsl_bridge
                    durum = neto_wsl_bridge.ensure_bridge_running(Path(__file__).resolve().parent)
                    if not durum.get("ready"):
                        root_obj.after(0, lambda: _set_status("Mini Linux basliyor, tekrar dene.", False))
                        return
                    parts = []
                    for command in ("linux durum", "linux liste home", "linux liste notes"):
                        response = neto_wsl_bridge.assistant_request(command, mode="linux", allow_quick=True, timeout=7.0)
                        parts.append(f"$ {command}\n{str((response or {}).get('text') or '')}")
                    root_obj.after(0, lambda: (_set_status("Mini Linux hazir."), _write("\n\n".join(parts))))
                except Exception as exc:
                    root_obj.after(0, lambda e=exc: (_set_status(f"Mini Linux hatasi: {e}", False), _write(f"Hata: {e}")))
            threading.Thread(target=worker, daemon=True).start()

        ctk.CTkButton(bar, text="Ana Ekran", height=36, fg_color=aktif_palet["neon"], text_color=_tema_vurgu_metin_rengi(), command=_ana_ekran).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(bar, text="Home", height=36, fg_color=aktif_palet["card"], hover_color=aktif_palet["button_hover"], text_color=aktif_palet["text_main"], command=lambda: _linux_request("linux liste home", "Home")).grid(row=0, column=1, sticky="ew", padx=4)
        ctk.CTkButton(bar, text="Notlar", height=36, fg_color=aktif_palet["card"], hover_color=aktif_palet["button_hover"], text_color=aktif_palet["text_main"], command=lambda: _linux_request("linux liste notes", "Notlar")).grid(row=0, column=2, sticky="ew", padx=4)
        ctk.CTkButton(bar, text="Kapat", height=36, fg_color=aktif_palet["card"], hover_color=aktif_palet["button_hover"], text_color=aktif_palet["text_main"], command=win.destroy).grid(row=0, column=3, sticky="ew", padx=(8, 0))

        def close():
            global _NETO_MINI_LINUX_WINDOW
            _NETO_MINI_LINUX_WINDOW = None
            try:
                win.destroy()
            except Exception:
                pass

        win.protocol("WM_DELETE_WINDOW", close)
        win.bind("<Escape>", lambda _event: close())
        _ana_ekran()
        return True
    except Exception as exc:
        try:
            print(f"[MINI_LINUX_SCREEN_ERROR] {exc}", flush=True)
        except Exception:
            pass
        return False

def netops_one_local_format(body, *, status="EXEC_OK", mode="ACTIVE_MODE", memory="READ_OK", target="local_command", step2="Yerel komut katmanı kullanıldı."):
    try:
        return str(body or "").strip()
    except Exception:
        return str(body or "")


def netops_one_now_playing_status_text():
    try:
        info = (
            globals().get("now_playing_current_info")
            or globals().get("now_playing_monitor_last_info")
            or globals().get("now_playing_last_info")
            or {}
        )
        try:
            if not now_playing_media_info_valid_basic(info):
                fresh = neto_now_playing.get_current_media(force_fresh=True)
                if now_playing_media_info_valid_basic(fresh):
                    info = fresh
        except Exception:
            pass
        try:
            if not now_playing_media_info_valid_basic(info):
                saved = now_playing_load_last_media()
                if now_playing_media_info_valid_basic(saved):
                    info = saved
        except Exception:
            pass
        if not now_playing_media_info_valid_basic(info):
            return netops_one_local_format(
                "Şu an çalan parça algılanmadı.",
                status="ERR_CODE",
                mode="SARKI_MODE",
                target="now_playing_status",
                step2="Yerel medya oturumu ve son geçerli kayıt kontrol edildi.",
            )
        title = str(info.get("title") or "").strip()
        artist = str(info.get("artist") or "").strip()
        app = str(info.get("app") or info.get("source") or "").strip()
        status_text = now_playing_status_text_from_info(info)
        line = f"{artist} - {title}" if artist else title
        details = [line]
        if app:
            details.append(f"Kaynak: {app}")
        if status_text:
            details.append(f"Durum: {status_text}")
        return netops_one_local_format(
            "\n".join(details),
            status="EXEC_OK",
            mode="SARKI_MODE",
            target="now_playing_status",
            step2="Yerel medya oturumu ve son geçerli kayıt kontrol edildi.",
        )
    except Exception as exc:
        return netops_one_local_format(
            f"Now Playing durumu okunamadı: {exc}",
            status="ERR_CODE",
            mode="SARKI_MODE",
            target="now_playing_status",
        )


def lokal_sistem_islemcisi(komut_metni):
    global ogrenme_modu, onay_modu, son_soru, _NETO_AUTOPILOT_PENDING  # Global değişkenleri fonksiyon başında tanımla

    k = komut_metni.lower().strip()
    h_ayar = veri_yukle()

    if onay_modu:
        yanit = k.strip(" \t\r\n.!?")
        bekleyen_islem = son_soru
        if yanit in {"evet", "e", "onayla", "onaylıyorum", "yes", "y", "confirm"}:
            onay_modu, son_soru = False, ""
            return _neto_power_action_execute(bekleyen_islem)
        if yanit in {"hayır", "hayir", "h", "iptal", "vazgeç", "vazgec", "no", "n", "cancel"}:
            onay_modu, son_soru = False, ""
            return "İşlem iptal."
        return "Lütfen bekleyen sistem işlemi için Evet veya Hayır yaz."

    if _NETO_AUTOPILOT_PENDING is not None:
        yanit = k.strip(" \t\r\n.!?")
        bekleyen = _NETO_AUTOPILOT_PENDING
        if yanit in {"evet", "e", "onayla", "onaylıyorum", "yes", "y", "confirm"}:
            _NETO_AUTOPILOT_PENDING = None
            try:
                import neto_autopilot
                return neto_autopilot.execute(bekleyen, adapters=_neto_scene_adapters())
            except Exception as exc:
                return f"Neto Autopilot çalıştırılamadı: {exc}"
        if yanit in {"hayır", "hayir", "h", "iptal", "vazgeç", "vazgec", "no", "n", "cancel"}:
            _NETO_AUTOPILOT_PENDING = None
            return "Neto Autopilot iptal edildi; bilgisayarda değişiklik yapılmadı."
        return "Autopilot planı bekliyor. Uygulamak için Evet, vazgeçmek için Hayır yaz."

    try:
        import neto_autopilot
        autopilot_request = neto_autopilot.prepare(komut_metni)
        if autopilot_request is not None:
            if autopilot_request.get("status") in {"needs_mode", "needs_api"}:
                return neto_autopilot.format_preview(autopilot_request)
            _NETO_AUTOPILOT_PENDING = autopilot_request
            return neto_autopilot.format_preview(autopilot_request)
    except Exception as exc:
        return f"Neto Autopilot hazırlanamadı: {exc}"

    
    tehlikeli_kelimeler = neto_security.dangerous_command_words(komut_metni)
    if tehlikeli_kelimeler:
        return "🛡️ Güvenlik nedeniyle reddedildi: " + ", ".join(tehlikeli_kelimeler)

    
    # Genel sohbet ve web bilgisi kanonik NetOpsOneEngine'e bırakılır.
    # Burada ikinci bir V3 araması yapılmadığı için aynı mesaj iki kez yönlenmez.
    if any(x in k for x in ("kendini onar", "doktor calistir", "doktor çalıştır", "yerel onarim", "yerel onarım", "sistemi onar", "netops onar")):
        try:
            import neto_doctor
            sonuc = neto_doctor.self_heal(Path(__file__).resolve().parent)
            duzeltmeler = sonuc.get("fixes") or []
            sorunlar = sonuc.get("issues") or []
            if sorunlar:
                return "Yerel onarım çalıştı ama güvenli mod gerekebilir: " + " | ".join(str(x) for x in sorunlar[:2])
            if duzeltmeler:
                return "Yerel onarım tamamlandı: " + " | ".join(str(x) for x in duzeltmeler[:3])
            return "Yerel onarım tamamlandı. Kritik sorun yok."
        except Exception as e:
            return f"Yerel onarım çalışmadı: {e}"

    if any(x in k for x in ("linux ekran", "linux ana ekran", "mini linux ekran", "wsl ekran")):
        try:
            root.after(0, _neto_mini_linux_ekran_ac)
            return "Mini Linux ekrani aciliyor."
        except Exception as e:
            return f"Mini Linux ekrani acilamadi: {e}"
    # Mini Linux / WSL Agent: Agent'in hafif Linux alaninda gezmesi icin kopru.
    if any(x in k for x in ("linux", "wsl", "ubuntu", "mini linux")):
        try:
            import neto_wsl_bridge
            durum = neto_wsl_bridge.ensure_bridge_running(Path(__file__).resolve().parent)
            if not durum.get("ready"):
                return "Mini Linux baslatiliyor. Birazdan tekrar 'linux durum' yaz."
            cevap = neto_wsl_bridge.assistant_request(komut_metni, mode="linux", allow_quick=True, timeout=6.0)
            if cevap and cevap.get("text"):
                return str(cevap.get("text"))
            return "Mini Linux cevap vermedi ama kopru ayakta."
        except Exception as e:
            try:
                print(f"[MINI_LINUX_BRIDGE_ERROR] {e}", flush=True)
            except Exception:
                pass
            return f"Mini Linux baslatilamadi: {e}"
    # AI'siz ogrenilen ozellikler: yeni cevap, web komutu, program komutu, mod.
    try:
        import netops_ozellik_motoru
        ogrenilen_cevap = netops_ozellik_motoru.handle(komut_metni)
        if ogrenilen_cevap:
            return ogrenilen_cevap
    except Exception as e:
        try:
            print(f"[FEATURE_ENGINE_ERROR] {e}", flush=True)
        except Exception:
            pass
    # --- AG TARAMA / CIHAZ ENVANTERI (v1.40 eklentisi) ---
    # Yalnizca ekleme amaclidir: modul yoksa veya hata verirse sessizce
    # atlanir ve asagidaki mevcut akis aynen devam eder. Eslesme katı ifade
    # listesiyle yapilir; normal sohbet cumleleri buraya takilmaz.
    try:
        _neto_net_cevap = _neto_lazy_import("neto_network_scan").handle_command(komut_metni)
    except Exception as _neto_net_hata:
        _neto_net_cevap = None
        try:
            print(f"[NETWORK_SCAN_ERROR] {_neto_net_hata}", flush=True)
        except Exception:
            pass
    if _neto_net_cevap:
        return _neto_net_cevap

    agent_agir_acma_komutlari = (
        "youtube aç", "google aç", "whatsapp aç", "spotify aç", "instagram aç",
        "twitter aç", "twitch aç", "github aç", "google maps aç", "cmd",
        "komut istemi", "powershell", "not defteri", "hesap makinesi",
        "görev yöneticisi", "denetim masası", "dosya gezgini", "explorer aç",
        "çalıştır", "masaüstü", "belgeler", "indirilenler",
    )
    if not globals().get("_NETO_AGENT_MODU", False) and any(x in k for x in agent_agir_acma_komutlari):
        return "Uygulama açma için `.agent` yaz. Normal sohbet modunda kalıyorum."

    # --- VOLUME SET COMMAND v10.32 ---
    if (not any(_x in k for _x in ["telefon", "android", "cihaz", "telefonda", "telefonu", "telefona"])) and ("volume" in k or "ses" in k) and re.search(r"\d+", k) and any(x in k for x in ["set", "make", "yap", "ayarla", "getir"]):
        try:
            hedef = int(re.findall(r"\d+", k)[0])
            hedef = max(0, min(100, hedef))
            if volume_set_percent(hedef, announce=False):
                return volume_text("changed").format(value=hedef)
            return volume_text("unavailable")
        except Exception as e:
            return f"{volume_text('error')}: {e}"

# --- VOLUME CONTROL UI / COMMAND ---
    if (not any(_x in k for _x in ["telefon", "android", "cihaz", "telefonda", "telefonu", "telefona"])) and ("volume" in k or "ses" in k) and any(x in k for x in ["kaç", "göster", "show", "level", "seviyesi"]):
        v = volume_get_percent()
        if v is None:
            return volume_text("unavailable")
        return f"🔊 {volume_text('label')}: {v}%"


    # --- NOW PLAYING AYAR KOMUTU ---
    np_ayar = now_playing_ayar_komutu(komut_metni)
    if np_ayar:
        return np_ayar


    # --- ANDROID USB GLOBAL COMMANDS v10.32.1 ---
    # Works from the normal assistant command box; user does not need to open Android panel first.
    try:
        import neto_android_device
        if neto_android_device.is_android_command(komut_metni):
            cevap = neto_android_device.handle_assistant_android_command(komut_metni)
            # If a crash/log command is requested, also open the panel with red log.
            try:
                if any(x in k for x in ["çökme", "crash", "kırmızı log", "logcat"]):
                    root.after(0, lambda: neto_android_device_ac_safe(crash_alert_log=cevap))
            except Exception:
                pass
            return cevap
    except Exception as e:
        return f"📱 Android komutu çalışmadı: {e}"

    # --- HAVA DURUMU / KONUM ---
    # AI'ye gitmeden gerçek Open-Meteo motoru cevaplar.
    try:
        if neto_weather.is_location_query(komut_metni):
            return neto_weather.location_answer(komut_metni)
        if neto_weather.is_weather_query(komut_metni):
            return neto_weather.weather_answer(komut_metni)
    except Exception as e:
        return f"Hava durumu alınamadı: {e}"

    # Akıllı küfür kontrolü
    if h_ayar.get("kufur_filtresi", True) and kufur_var_mi(komut_metni):
        return "⚠️ Lütfen daha nazik bir dil kullan."

    # --- SELAMLAŞMA VE TEMEL İFADELER ---
    if any(x in k for x in ("hangi şarkı", "hangi sarki", "ne çalıyor", "ne caliyor", "şu an çalan", "su an calan", "şu an hangi", "su an hangi")) and any(x in k for x in ("şarkı", "sarki", "müzik", "muzik", "çalıyor", "caliyor", "çalan", "calan")):
        return netops_one_now_playing_status_text()
    if any(kelime in k for kelime in ["merhaba", "selam", "hey", "iyi günler", "naber"]):
        return netops_one_local_format("Buradayım. Ne yapmak istiyorsun?", target="greeting")
    if any(kelime in k for kelime in ["ne yapıyorsun", "ne yapıyosun", "napıyorsun", "napıyosun", "napıyon", "ne yapıyon", "neler yaparsın", "ne yapabilirsin"]):
        return netops_one_local_format(
            "Şu an konuşma motorunu yönetiyorum. Sohbet edebilirim, program komutlarını ayırabilirim, "
            "bilmediğim konularda internete bakıp temiz cevap çıkarabilirim, güvenilir bilgileri hafızaya "
            "alabilirim ve müzik, tarif, otomasyon gibi istekleri doğru moda yönlendirebilirim.",
            target="capability",
        )
    if any(kelime in k for kelime in ["görüşürüz", "hoşça kal", "bye", "kendine iyi bak"]):
        return netops_one_local_format("Oturum kapatılmadı. Komut bekleme modu aktif.", target="farewell")
    if any(kelime in k for kelime in ["teşekkür", "sağ ol", "eyvallah", "teşekkürler"]):
        return netops_one_local_format("İşlem tamamlandı.", target="acknowledgement")
    if "nasılsın" in k or "keyfin nasıl" in k:
        return netops_one_local_format("İyiyim, sistem hazır. İstersen sohbet edelim, istersen bir şey araştıralım.", target="health_check")
    if ("saat" in k and ("kaç" in k or "kac" in k)) or k in {"saat", "saati söyle", "saati soyle"}:
        from datetime import datetime
        return f"Şu an saat {datetime.now().strftime('%H:%M')} ⏰"
    if any(x in k for x in (
        "tarih", "bugün ayın kaçı", "bugun ayin kaci", "hangi gün", "hangi gun",
        "günlerden ne", "gunlerden ne", "bugün günlerden ne", "bugun gunlerden ne",
        "bugün hangi gün", "bugun hangi gun", "hangi gündeyiz", "hangi gundeyiz"
    )):
        from datetime import datetime
        aylar = ["Ocak","Şubat","Mart","Nisan","Mayıs","Haziran","Temmuz","Ağustos","Eylül","Ekim","Kasım","Aralık"]
        gunler = ["Pazartesi","Salı","Çarşamba","Perşembe","Cuma","Cumartesi","Pazar"]
        simdi = datetime.now()
        return f"Bugün {gunler[simdi.weekday()]}, {simdi.day} {aylar[simdi.month-1]} {simdi.year} 📅"
    if "sen kimsin" in k or "adın ne" in k or "kimsin" in k:
        return "Ben NetOps, senin kişisel asistanınım. Sana yardım etmek için buradayım! 🤖"
    if "yardım" in k or "neler yapabilirsin" in k:
        return ("Birçok şey yapabilirim: hava durumu, şifre oluşturma, yazı tura, IP sorgulama, "
                "sistem komutları, hesaplama, not alma, web arama ve daha fazlası. 💪")

    # --- PYTHON DERSLERİ ---

    # --- KOD ŞABLONLARI ---


    # --- HAVA DURUMU (legacy yol; merkezi Weather Engine'e yönlendir) ---
    if "hava durumu" in k:
        try:
            return neto_weather.weather_answer(komut_metni)
        except Exception as e:
            return f"Hava durumu alınamadı: {e}"

    # --- ŞİFRE OLUŞTURUCU ---
    if "şifre oluştur" in k:
        sayi = re.findall(r'\d+', k)
        uzunluk = int(sayi[0]) if sayi else 12
        import random, string
        sifre = ''.join(random.choices(string.ascii_letters + string.digits + "!@#$%&*", k=uzunluk))
        return f"🔐 Şifren: {sifre}"

    # --- YAZI TURA ---
    if "yazı tura" in k:
        import random
        return f"🪙 {random.choice(['Yazı', 'Tura'])} geldi!"

    # --- IP SORGULAMA ---
    if "ip adresim" in k:
        try:
            import urllib.request
            return f"🌍 IP: {urllib.request.urlopen('https://api.ipify.org').read().decode('utf-8')}"
        except: return "IP alınamadı."

    # --- SİSTEM KOMUTLARI (GENİŞLETİLMİŞ 20+) ---
    # 1. Yeniden başlat
    if "bilgisayarı yeniden başlat" in k or "pc'yi yeniden başlat" in k:
        onay_modu, son_soru = True, "restart"
        return "Bilgisayarı yeniden başlatmamı onaylıyor musun? (Evet/Hayır) 🔄"

    # 2. Uyku modu
    if "bilgisayarı uyut" in k or "uyku moduna al" in k:
        onay_modu, son_soru = True, "sleep"
        return "Bilgisayarı uyku moduna almamı onaylıyor musun? (Evet/Hayır) 😴"

    # 3. Close
    if "bilgisayarı kapat" in k or "pc'yi kapat" in k:
        onay_modu, son_soru = True, "shutdown"
        return "Bilgisayarı kapatmamı onaylıyor musun? (Evet/Hayır) 🔌"

    # 4. Ekran görüntüsü
    if "ekran görüntüsü" in k or "ss al" in k:
        if K_WIN:
            import pyautogui
            pyautogui.screenshot(os.path.join(os.path.expanduser("~"), "Desktop", f"SS_{int(time.time())}.png"))
        return "Ekran görüntüsü masaüstüne kaydedildi. 📸"

    # 5. Görev yöneticisi
    if "görev yöneticisi" in k:
        os.system("taskmgr")
        return "Görev yöneticisi açılıyor... 📋"

    # 6. Denetim masası
    if "denetim masası" in k:
        os.system("control")
        return "Denetim masası açılıyor... ⚙️"

    # 7. Çalıştır
    if "çalıştır" in k:
        os.system("start shell:AppsFolder\\Windows.System.Launcher.exe")
        return "Çalıştır penceresi açılıyor... 🏃"

    # 8. Komut istemi (CMD)
    if "cmd" in k or "komut istemi" in k:
        os.system("start cmd")
        return "Komut istemi açılıyor... 💻"

    # 9. PowerShell
    if "powershell" in k:
        os.system("start powershell")
        return "PowerShell açılıyor... 🟦"

    # 10. Not defteri
    if "not defteri" in k:
        os.system("start notepad")
        return "Not defteri açılıyor... 📝"

    # 11. Hesap makinesi
    if "hesap makinesi" in k:
        os.system("start calc")
        return "Hesap makinesi açılıyor... 🧮"

    # 12. Ses ayarları penceresi
    if "ses ayarları" in k or "ses penceresi" in k:
        os.system("start mmsys.cpl")
        return "Ses ayarları penceresi açılıyor... 🔊"

    # 13. Klasör aç (Masaüstü)
    if "masaüstünü aç" in k or "masaüstü" in k:
        os.system(f'explorer "{os.path.expanduser("~")}\\Desktop"')
        return "Masaüstü açılıyor... 📂"

    # 14. Belgeler klasörü
    if "belgeleri aç" in k or "belgeler" in k:
        os.system(f'explorer "{os.path.expanduser("~")}\\Documents"')
        return "Belgeler klasörü açılıyor... 📁"

    # 15. İndirilenler klasörü
    if "indirilenler" in k:
        os.system(f'explorer "{os.path.expanduser("~")}\\Downloads"')
        return "İndirilenler klasörü açılıyor... ⬇️"

    # 16. Klasör seçici
    if "dosya seç" in k or "klasör aç" in k:
        from tkinter import filedialog
        dosya = filedialog.askopenfilename(title="Bir dosya seçin")
        if dosya:
            return f"Seçilen dosya: {dosya}"
        return "Dosya seçimi iptal edildi."

    # 17. IP adresi (hızlı)
    if "ip adresim" in k or "ip'm ne" in k:
        import socket
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            return f"Yerel IP adresin: {ip} 🌍"
        except:
            return "IP adresi alınamadı."

    # 18. Ağ durumu
    if "internet kontrol" in k or "bağlantı kontrol" in k:
        import urllib.request
        try:
            urllib.request.urlopen("https://www.google.com", timeout=3)
            return "İnternet bağlantısı aktif ✅"
        except:
            return "İnternet bağlantısı yok ❌"

    # 19. Hızlı sistem bilgisi
    if "sistem bilgisi" in k or "bilgisayar modeli" in k:
        import platform
        try:
            return f"Bilgisayar adı: {platform.node()}, İşletim sistemi: {platform.system()} ({platform.machine()})"
        except: pass

    # 20. Saat ve tarih (hızlı)
    if "saat" in k and ("kaç" in k or "göster" in k or "söyle" in k):
        from datetime import datetime
        return f"Şu an saat {datetime.now().strftime('%H:%M')} ⏰"
    if "tarih" in k and ("ne" in k or "göster" in k or "bugün" in k):
        from datetime import datetime
        aylar = ["Ocak","Şubat","Mart","Nisan","Mayıs","Haziran","Temmuz","Ağustos","Eylül","Ekim","Kasım","Aralık"]
        simdi = datetime.now()
        return f"Bugün {simdi.day} {aylar[simdi.month-1]} {simdi.year} 📅"

    # 21. Ses seviyesi ayarı (güncellenmiş)
    if "sesi" in k and ("ayarla" in k or "yap" in k or "getir" in k or "kıs" in k or "aç" in k or "arttır" in k or "azalt" in k):
        try:
            sayilar = [int(s) for s in re.findall(r'\d+', k)]
            if "kıs" in k or "azalt" in k:
                hedef = sayilar[0] if sayilar else 15
            elif "aç" in k or "arttır" in k:
                hedef = sayilar[0] if sayilar else 85
            else:
                hedef = sayilar[0] if sayilar else 60
            hedef = max(0, min(100, hedef))

            # Yöntem 1: Pycaw
            if HAS_PYCAW:
                try:
                    devices = AudioUtilities.GetSpeakers()
                    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                    volume = ctypes_cast(interface, POINTER(IAudioEndpointVolume))
                    volume.SetMasterVolumeLevelScalar(hedef / 100.0, None)
                    return f"🔊 Ses seviyesi %{hedef} olarak ayarlandı."
                except: pass

            # Yöntem 2: Klavye kısayolu
            import ctypes
            VK_VOLUME_DOWN = 0xAE
            VK_VOLUME_UP = 0xAF
            def key_press(vk):
                ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
                time.sleep(0.01)
                ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
            for _ in range(50):
                key_press(VK_VOLUME_DOWN)
            for _ in range(int(hedef / 2)):
                key_press(VK_VOLUME_UP)
            return f"🔊 Ses seviyesi yaklaşık %{hedef} yapıldı."
        except Exception as e:
            return f"Ses ayarlanamadı: {str(e)[:80]}"

    # --- HESAPLAMA ---
    if "hesapla" in k:
        islem = re.sub(r'[^0-9\+\-\*\/\.\(\)\s]', '', k.replace("hesapla", ""))
        if islem:
            try: return f"Sonuç: {neto_security.safe_eval_math(islem)} 🧮"
            except: return "Hesaplayamadım."
        else: return "Örnek: hesapla 5+3"

    # --- NOTLAR ---
    if "nota ekle" in k or "not al" in k:
        not_metni = komut_metni.replace("nota ekle", "").replace("not al", "").strip()
        if not_metni and 'not_alani' in globals():
            not_alani.insert(tk.END, f"\n• {not_metni}")
            return f"Hocam şu notu yan panele ekledim: {not_metni}"
    if "notları temizle" in k or "notu sil" in k:
        if 'not_alani' in globals():
            not_alani.delete("1.0", tk.END)
            return "Yan paneldeki tüm yerel notlarınızı temizledim hocam."
    if "notları oku" in k or "notumda ne var" in k:
        if 'not_alani' in globals():
            mevcut_notlar = not_alani.get("1.0", tk.END).strip()
            if mevcut_notlar:
                return f"Hocam notlarınızda şunlar yazıyor: {mevcut_notlar}"
            return "Hocam yerel not defteriniz şu an tamamen boş."

    # --- DİSK DURUMU ---
    if "boş alan" in k or "disk durumu" in k or "hafıza ne kadar" in k:
        try:
            toplam, kullanilan, bos = shutil.disk_usage(BASE_DIR)
            return f"Hocam şu an ana sürücüde {bos // (2**30)} GB boş yer var. (Toplam: {toplam // (2**30)} GB)"
        except Exception: pass

    # --- SİSTEM BİLGİSİ ---
    if "sistem bilgisi" in k or "bilgisayar modeli" in k:
        import platform
        try:
            return f"Hocam bu bilgisayarın adı {platform.node()}, İşletim sistemi {platform.system()} ({platform.machine()})."
        except Exception: pass

    # --- GÖREV KAPATMA ---
    if "görevi kapat" in k or "işlemi bitir" in k or "programı kapat" in k:
        hedef_surec = k.replace("görevi kapat", "").replace("işlemi bitir", "").replace("programı kapat", "").strip()
        if hedef_surec:
            ok, detay = neto_security.safe_taskkill(hedef_surec)
            if ok:
                return f"Hocam {hedef_surec} sonlandırıldı."
            return f"Görev kapatma reddedildi/başarısız: {detay}"

    # --- DOSYA OLUŞTURMA ---
    if "dosya oluştur" in k or "metin belgesi aç" in k:
        dosya_adi = neto_security.sanitize_filename(komut_metni.replace("dosya oluştur", "").replace("metin belgesi aç", "").strip() or f"Neto_Not_{int(time.time())}")
        try:
            tam_yol = os.path.join(os.path.expanduser("~"), "Desktop", f"{dosya_adi}.txt")
            with open(tam_yol, "w", encoding="utf-8") as f: f.write("NetOps Notu\n")
            return f"Masaüstünde '{dosya_adi}.txt' başarıyla oluşturuldu."
        except Exception as e: return f"Hata: {e}"

    # 🧠 Hiçbir komut eşleşmezse NetOps Agent devreye girer
    ai_cevap = neto_ai_cevap_ver(komut_metni)

    # NetOps Agent'ten gelen özel komutları işle

    # Ses komutu işleme
    if ai_cevap.startswith("__SES__:"):
        try:
            hedef = int(ai_cevap.split(":")[1])
            if HAS_PYCAW:
                try:
                    devices = AudioUtilities.GetSpeakers()
                    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                    volume = ctypes_cast(interface, POINTER(IAudioEndpointVolume))
                    volume.SetMasterVolumeLevelScalar(hedef / 100.0, None)
                    return f"🔊 Ses %{hedef} yapıldı."
                except: pass
            # Klavye kısayolu ile yedek
            import ctypes
            VK_VOLUME_DOWN = 0xAE
            VK_VOLUME_UP = 0xAF
            def key_press(vk):
                ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
                time.sleep(0.01)
                ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
            for _ in range(50): key_press(VK_VOLUME_DOWN)
            for _ in range(int(hedef / 2)): key_press(VK_VOLUME_UP)
            return f"🔊 Ses yaklaşık %{hedef} yapıldı."
        except Exception as e:
            return f"Ses ayarlanamadı: {str(e)[:80]}"

    # Hesaplama komutu işleme
    if ai_cevap.startswith("__HESAPLA__:"):
        islem = ai_cevap.split(":", 1)[1].strip()
        try:
            sonuc = neto_security.safe_eval_math(islem)
            return f"Hesaplama sonucu: {sonuc} 🧮"
        except:
            return "Bu işlemi yapamadım."

    # Hava durumu komutu işleme - tek kaynak: neto_weather / WeatherEngine
    if ai_cevap.startswith("__HAVA__:"):
        sehir = ai_cevap.split(":", 1)[1].strip()
        if not sehir:
            return neto_weather.weather_answer("hava durumu")
        try:
            return neto_weather.weather_answer(f"{sehir} hava durumu")
        except Exception as e:
            return f"Hava durumu alınamadı: {e}"

    # Özel komut değilse sohbet cevabı olarak döndür
    return ai_cevap


def neto_remote_assistant_request(text, device_id=""):
    """Serve an authenticated Android chat request through the existing engine."""
    try:
        answer = lokal_sistem_islemcisi(str(text or "").strip())
        return {
            "ok": True,
            "display_text": komut_token_temizle(str(answer or "Bir yanıt oluşturulamadı.")),
            "device_id": str(device_id or ""),
        }
    except Exception as exc:
        try:
            crash_guard.log(f"[REMOTE_ASSISTANT_REQUEST_ERROR] {exc}")
        except Exception:
            pass
        return {"ok": False, "error": "REMOTE_ASSISTANT_REQUEST_FAILED"}


def neto_remote_media_request(action, args=None, device_id=""):
    """Handle only safe Now Playing controls from an authenticated device."""
    action = str(action or "").strip().casefold()
    args = dict(args or {}) if isinstance(args, dict) else {}
    try:
        if action == "play_pause":
            result = now_playing_safe_media_call("media_play_pause")
            return {"ok": bool(result is not False), "display_text": "Oynatma durumu değiştirildi."}
        if action == "next":
            result = now_playing_safe_media_call("media_next")
            return {"ok": bool(result is not False), "display_text": "Sonraki parçaya geçildi."}
        if action == "previous":
            result = now_playing_safe_media_call("media_previous")
            return {"ok": bool(result is not False), "display_text": "Önceki parçaya geçildi."}
        if action == "set_volume":
            try:
                value = max(0, min(100, int(float(args.get("value")))))
            except Exception:
                return {"ok": False, "error": "INVALID_VOLUME"}
            ok = volume_set_percent(value, announce=False)
            return {"ok": bool(ok), "display_text": f"Bilgisayar sesi %{value} yapıldı." if ok else "Bilgisayar sesi ayarlanamadı."}
        if action == "current":
            info = neto_now_playing.get_current_media(force_fresh=True) or {}
            safe_info = {
                "title": str(info.get("title") or ""),
                "artist": str(info.get("artist") or ""),
                "album": str(info.get("album") or ""),
                "app": str(info.get("app") or ""),
                "playback_status": str(info.get("playback_status") or ""),
            }
            title = safe_info["title"] or "Şu an parça bilgisi yok."
            artist = safe_info["artist"]
            return {"ok": True, "media": safe_info, "display_text": " • ".join(item for item in (title, artist) if item)}
    except Exception as exc:
        try:
            now_playing_log(f"[REMOTE_MEDIA_REQUEST_ERROR] {action}: {exc}")
        except Exception:
            pass
        return {"ok": False, "error": "REMOTE_MEDIA_REQUEST_FAILED"}
    return {"ok": False, "error": "MEDIA_ACTION_NOT_ALLOWED"}


def neto_remote_assistant_request(text, device_id=""):
    """Serve an authenticated Android chat request through the existing engine."""
    try:
        answer = lokal_sistem_islemcisi(str(text or "").strip())
        return {
            "ok": True,
            "display_text": komut_token_temizle(str(answer or "Bir yanıt oluşturulamadı.")),
            "device_id": str(device_id or ""),
        }
    except Exception as exc:
        try:
            crash_guard.log(f"[REMOTE_ASSISTANT_REQUEST_ERROR] {exc}")
        except Exception:
            pass
        return {"ok": False, "error": "REMOTE_ASSISTANT_REQUEST_FAILED"}


def neto_remote_media_request(action, args=None, device_id=""):
    """Handle only safe Now Playing controls from an authenticated device."""
    action = str(action or "").strip().casefold()
    args = dict(args or {}) if isinstance(args, dict) else {}
    try:
        if action == "play_pause":
            result = now_playing_safe_media_call("media_play_pause")
            return {"ok": bool(result is not False), "display_text": "Oynatma durumu değiştirildi."}
        if action == "next":
            result = now_playing_safe_media_call("media_next")
            return {"ok": bool(result is not False), "display_text": "Sonraki parçaya geçildi."}
        if action == "previous":
            result = now_playing_safe_media_call("media_previous")
            return {"ok": bool(result is not False), "display_text": "Önceki parçaya geçildi."}
        if action == "set_volume":
            try:
                value = max(0, min(100, int(float(args.get("value")))) )
            except Exception:
                return {"ok": False, "error": "INVALID_VOLUME"}
            ok = volume_set_percent(value, announce=False)
            return {"ok": bool(ok), "display_text": f"Bilgisayar sesi %{value} yapıldı." if ok else "Bilgisayar sesi ayarlanamadı."}
        if action == "current":
            info = neto_now_playing.get_current_media(force_fresh=True) or {}
            safe_info = {
                "title": str(info.get("title") or ""),
                "artist": str(info.get("artist") or ""),
                "album": str(info.get("album") or ""),
                "app": str(info.get("app") or ""),
                "playback_status": str(info.get("playback_status") or ""),
            }
            title = safe_info["title"] or "Şu an parça bilgisi yok."
            artist = safe_info["artist"]
            return {"ok": True, "media": safe_info, "display_text": " • ".join(item for item in (title, artist) if item)}
    except Exception as exc:
        try:
            now_playing_log(f"[REMOTE_MEDIA_REQUEST_ERROR] {action}: {exc}")
        except Exception:
            pass
        return {"ok": False, "error": "REMOTE_MEDIA_REQUEST_FAILED"}
    return {"ok": False, "error": "MEDIA_ACTION_NOT_ALLOWED"}

# ------------------------------------------------------------
# CEVAP VER FONKSİYONU
# ------------------------------------------------------------

def ekli_resim_karti_goster(yol):
    global secili_resim_preview_ref
    try:
        ad = os.path.basename(yol)
        kb = max(1, os.path.getsize(yol) // 1024)
        try:
            img = Image.open(yol)
            img = img.convert("RGBA")
            img.thumbnail((46, 46))
            secili_resim_preview_ref = ctk.CTkImage(light_image=img, dark_image=img, size=(46, 46))
            lbl_resim_preview.configure(image=secili_resim_preview_ref, text="")
        except Exception:
            lbl_resim_preview.configure(image="", text="🖼")
        lbl_resim_dosya.configure(text=f"{ad}  {kb} KB")
        ekli_resim_frame.pack(fill="x", padx=6, pady=(0, 7))
    except Exception as e:
        print(f"[IMAGE] önizleme hata: {e}", flush=True)


def ekli_resim_karti_gizle():
    global secili_resim_yolu, secili_resim_preview_ref
    secili_resim_yolu = None
    secili_resim_preview_ref = None
    try:
        ekli_resim_frame.pack_forget()
    except Exception:
        pass
    try:
        btn_resim.configure(text="", image=_neto_input_icon("plus", 22, "#EAF0FF"))
    except Exception:
        pass


def resim_yukle():
    global secili_resim_yolu
    try:
        yol = filedialog.askopenfilename(
            title="Select image",
            filetypes=[("Resim Dosyaları", "*.png *.jpg *.jpeg *.webp *.gif *.bmp"), ("Tüm Dosyalar", "*.*")]
        )
        if not yol:
            return
        secili_resim_yolu = yol
        btn_resim.configure(text="", image=_neto_input_icon("plus", 22, "#EAF0FF"))
        ekli_resim_karti_goster(yol)
        animasyonlu_yazi(f"Image attached: {os.path.basename(yol)}")
    except Exception as e:
        animasyonlu_yazi(f"Image upload error: {e}")


def kevra_model_degistir():
    try:
        mevcut = neto_ai.aktif_modeli_getir()
    except Exception:
        mevcut = "NetOps Agent K1"
    yeni = "NetOps Agent K2" if mevcut == "NetOps Agent K1" else "NetOps Agent K1"
    try:
        neto_ai.aktif_modeli_ayarla(yeni)
    except Exception:
        pass
    try:
        btn_model.configure(text="K2" if yeni == "NetOps Agent K2" else "K1")
    except Exception:
        pass
    animasyonlu_yazi(f"{yeni} aktif edildi.")


def live_acilis_sesi_oynat():
    """Live Mode tam ekranı açılırken kısa açılış sesi çalar."""
    try:
        if not K_PYGAME:
            return
        yol = None
        try:
            yol = LIVE_OPEN_SOUND
        except Exception:
            yol = get_asset_path("denielcz-done-463074.mp3")
        if yol and os.path.exists(yol):
            s = pygame.mixer.Sound(yol)
            s.set_volume(0.45)
            s.play()
    except Exception as e:
        try:
            print(f"[LIVE] açılış sesi hata: {e}", flush=True)
        except Exception:
            pass


# ------------------------------------------------------------
# LIVE MODE v3 - ANA EKRAN İÇİ PANEL
# ------------------------------------------------------------
def live_running_mi():
    try:
        return bool(live_mode_controller and live_mode_controller.is_running())
    except Exception:
        return False


def live_panel_goster():
    global live_panel_acik
    try:
        live_panel_acik = True
        live_acilis_sesi_oynat()
        live_panel.place(x=0, y=0, relwidth=1, relheight=1)
        live_panel.lift()
        live_animasyon_baslat()
    except Exception as e:
        animasyonlu_yazi(f"Live panel açılamadı: {e}")


def live_panel_gizle():
    global live_panel_acik
    try:
        live_panel_acik = False
        live_animasyon_durdur()
        live_panel.place_forget()
    except Exception:
        pass


live_animasyon_id = None
live_animasyon_adim = 0

def live_animasyon_baslat():
    global live_animasyon_id, live_animasyon_adim
    try:
        live_animasyon_durdur()
        live_animasyon_adim = 0
        live_animasyon_dongu()
    except Exception:
        pass


def live_animasyon_durdur():
    global live_animasyon_id
    try:
        if live_animasyon_id:
            root.after_cancel(live_animasyon_id)
            live_animasyon_id = None
    except Exception:
        pass


def live_animasyon_dongu():
    global live_animasyon_id, live_animasyon_adim
    try:
        if not live_panel_acik:
            return
        if live_wave and hasattr(live_wave, "winfo_exists") and live_wave.winfo_exists():
            frames = [
                "|   ||   ||   |",
                "||  |||  |||  ||",
                "||| |||| |||| |||",
                "|||||||||||||||||",
                "||| |||| |||| |||",
                "||  |||  |||  ||",
                "|   ||   ||   |",
            ]
            live_wave.configure(text=frames[live_animasyon_adim % len(frames)])
            live_animasyon_adim += 1
            live_animasyon_id = root.after(92 if live_running_mi() else 120, live_animasyon_dongu)
            return
        dalgalar = [
            "▁▂▃▄▅▆▇▆▅▄▃▂▁",
            "▁▁▂▃▄▅▆▇▆▅▄▃▂",
            "▂▃▄▅▆▇▆▅▄▃▂▁▂",
            "▂▂▃▄▅▆▇▆▅▄▃▂▁",
            "▃▄▅▆▇▆▅▄▃▂▁▂▃",
            "▃▃▄▅▆▇▆▅▄▃▂▁▂",
            "▄▅▆▇▆▅▄▃▂▁▂▃▄",
            "▄▅▆▇▇▆▅▄▃▂▁▂▃",
            "▅▆▇▆▅▄▃▂▁▂▃▄▅",
            "▄▅▆▇▆▅▄▃▂▁▁▂▃",
        ]
        live_wave.configure(text=dalgalar[live_animasyon_adim % len(dalgalar)])
        live_animasyon_adim += 1
        live_animasyon_id = root.after(92, live_animasyon_dongu)
    except Exception:
        pass


def live_panel_toggle():
    if live_panel_acik:
        live_panel_gizle()
    else:
        live_panel_goster()


def live_status_guncelle(metin):
    try:
        root.after(0, lambda: live_durum_label.configure(text=str(metin)))
        state = _netops_tablet_voice_state_from_status(metin)
        if state:
            _netops_send_tablet_voice_event(
                state,
                text=str(metin),
                level=_netops_voice_level_for_state(state),
                speak=False,
                reason="live",
                broadcast=True,
                async_dispatch=True,
            )
    except Exception:
        pass


def live_mic_guncelle(metin):
    try:
        root.after(0, lambda: live_mic_label.configure(text=f"Mikrofon: {metin}"))
        _netops_send_tablet_voice_event(
            "mic",
            text=str(metin),
            level=_netops_voice_level_for_state("mic"),
            speak=False,
            reason="live",
            broadcast=True,
            async_dispatch=True,
        )
    except Exception:
        pass


def live_transcript_guncelle(metin):
    try:
        root.after(0, lambda: live_text_label.configure(text=str(metin)))
        root.after(0, lambda: animasyonlu_yazi(f"🎤 Sen: {metin}"))
        _netops_send_tablet_voice_event(
            "listening",
            text=str(metin),
            level=_netops_voice_level_for_state("listening"),
            speak=False,
            reason="live",
            broadcast=True,
            async_dispatch=True,
        )
    except Exception:
        pass


def live_cevap_guncelle(metin):
    try:
        root.after(0, lambda: live_answer_label.configure(text=str(metin)))
        root.after(0, lambda: animasyonlu_yazi(metin))
        _netops_send_tablet_voice_event(
            "answer",
            text=str(metin),
            level=_netops_voice_level_for_state("answer"),
            speak=False,
            reason="live",
            broadcast=True,
            async_dispatch=True,
        )
    except Exception:
        pass


def live_worker_beklenmedik_durdu(neden=""):
    """Native Live worker dies without taking the main Neto window with it."""
    def _ui_reset():
        try:
            fn = globals().get("inline_live_force_stop")
            if callable(fn):
                fn(str(neden or "Live ses motoru durdu."))
                return
        except Exception:
            pass
        try:
            btn_live.configure(text="", image=_neto_input_icon("waveform", 22, "#EAF0FF"))
        except Exception:
            pass
        try:
            live_durum_label.configure(text="Off")
        except Exception:
            pass
        try:
            animasyonlu_yazi(
                "Live motoru durdu; NetOps açık kaldı. "
                "Ayrıntı: %LOCALAPPDATA%\\NetoAssistant\\logs"
            )
        except Exception:
            pass
        try:
            _netops_send_tablet_voice_event(
                "idle",
                text="",
                level=0,
                speak=False,
                reason="live",
                broadcast=True,
                async_dispatch=True,
            )
        except Exception:
            pass
        try:
            _netops_send_tablet_command(
                "live_screen",
                {"show": False, "title": "NETOPS LIVE MODE"},
                broadcast=True,
                reason="live",
                async_dispatch=True,
            )
        except Exception:
            pass
        try:
            _netops_send_tablet_command(
                "tablet_audio_stream",
                {"enabled": False, "reason": "live_worker_stopped"},
                broadcast=True,
                reason="live",
                async_dispatch=True,
            )
        except Exception:
            pass
        try:
            _netops_tablet_audio_stream_clear(remove_file=True)
        except Exception:
            pass

        try:
            _neto_live_otomatik_toparla(str(neden or "live_worker"))
        except Exception:
            pass

    try:
        root.after(0, _ui_reset)
    except Exception:
        _ui_reset()


def live_cevap_motoru(metin):
    """Live Mode için sesli komutları ana asistan motorundan geçirir."""
    try:
        komut = str(metin or "").strip()
        if not komut:
            return "Komut algılanamadı."

        try:
            import neto_live_commands

            hizli_cevap = neto_live_commands.handle_live_command(komut)
            if hizli_cevap is not None:
                return komut_token_temizle(str(hizli_cevap))
        except Exception:
            pass

        cevap = lokal_sistem_islemcisi(komut)
        if cevap is None:
            cevap = neto_ai.neto_ai_cevap_ver(komut)
        try:
            cevap = komut_token_temizle(cevap)
        except Exception:
            pass
        return cevap if cevap else "Komut işlendi."
    except Exception as e:
        return f"Live komut hatası: {e}"


def live_metin_cevap_ver(metin):
    """Mikrofon yokken Live Mode içinde yazılan komutu işler."""
    try:
        komut = str(metin or "").strip()
        if not komut:
            return

        try:
            giris.delete(0, tk.END)
        except Exception:
            pass

        try:
            giris.configure(state="disabled")
            btn_gonder.configure(state="disabled")
        except Exception:
            pass

        try:
            live_transcript_guncelle(komut)
        except Exception:
            pass

        def arka_planda_calistir():
            try:
                cevap = live_cevap_motoru(komut)
                if not cevap:
                    cevap = T("chat_no_answer") if "T" in globals() else "No response received."
            except Exception as exc:
                _neto_kendini_onar("live_metin_cevap_ver", exc)
                try:
                    cevap = lokal_sistem_islemcisi(komut)
                except Exception:
                    cevap = T("chat_no_answer") if "T" in globals() else "No response received."

            def ui_guncelle():
                try:
                    cevap_temiz = komut_token_temizle(cevap)
                    if not cevap_temiz:
                        cevap_temiz = T("ready") if "T" in globals() else "Done."
                    live_cevap_guncelle(cevap_temiz)
                    try:
                        sesli_oku(cevap_temiz)
                    except Exception:
                        pass
                finally:
                    try:
                        giris.configure(state="normal")
                        btn_gonder.configure(state="normal")
                        _neto_widget_focus_guvenli(giris, kaynak="live_metin_cevap_ver_ui")
                    except Exception:
                        pass

            root.after(0, ui_guncelle)

        threading.Thread(target=arka_planda_calistir, daemon=True).start()
    except Exception as e:
        try:
            animasyonlu_yazi(f"Live metin hatası: {e}")
            giris.configure(state="normal")
            btn_gonder.configure(state="normal")
        except Exception:
            pass


def live_mode_baslat():
    global live_mode_controller
    try:
        if live_mode_controller and live_mode_controller.is_running():
            return True

        _netops_tablet_audio_stream_clear(remove_file=True)
        tablet_audio_path = ""
        try:
            if _netops_online_tablet_devices():
                tablet_audio_path = _netops_tablet_audio_stream_path()
        except Exception:
            tablet_audio_path = ""

        live_mode_controller = neto_live_mode.NetoLiveMode(
            answer_func=live_cevap_motoru,
            speak_func=sesli_oku,
            status_callback=live_status_guncelle,
            transcript_callback=live_transcript_guncelle,
            answer_callback=live_cevap_guncelle,
            mic_callback=live_mic_guncelle,
            stopped_callback=live_worker_beklenmedik_durdu,
            preferred_keywords=("AudioRelay", "Audio Relay", "WO Mic", "Microphone", "Mikrofon"),
            model_size="small",
            language="tr",
            record_seconds=5.5,
            sample_rate=16000,
            silence_threshold=0.006,
            tts_enabled=True,
            tablet_audio_path=tablet_audio_path or None,
        )
        started = bool(live_mode_controller.start())
        if not started:
            _netops_tablet_audio_stream_clear(remove_file=True)
            return False
        try:
            durum = _NETO_LIVE_SELF_HEAL_DURUMU
            durum["attempts"] = 0
            durum["scheduled"] = False
            durum["last_reason"] = ""
        except Exception:
            pass
        btn_live.configure(
            text="", image=_neto_input_icon("waveform", 22, "#EAF0FF"),
            fg_color="transparent", hover_color="#7587FF", border_width=0
        )
        live_durum_label.configure(text="Starting... speak when ready")
        _netops_send_tablet_command(
            "live_screen",
            {"show": True, "title": "NETOPS LIVE MODE", "subtitle": "PC canlı akışı tablet üzerinde"},
            broadcast=True,
            reason="live",
            async_dispatch=True,
        )
        if tablet_audio_path:
            _netops_send_tablet_command(
                "tablet_audio_stream",
                {
                    "enabled": True,
                    "sample_rate": 16000,
                    "channels": 1,
                    "chunk_ms": 100,
                    "label": "Tablet mikrofonu",
                },
                broadcast=False,
                reason="live",
                async_dispatch=True,
            )
        return True
    except Exception as e:
        _netops_tablet_audio_stream_clear(remove_file=True)
        animasyonlu_yazi(f"Live Mode başlatılamadı: {e}")
        return False


def live_mode_durdur():
    try:
        if live_mode_controller:
            live_mode_controller.stop()
        btn_live.configure(
            text="", image=_neto_input_icon("waveform", 22, "#EAF0FF"),
            fg_color="transparent", hover_color="#7587FF", border_width=0
        )
        live_durum_label.configure(text="Off")
        try:
            durum = _NETO_LIVE_SELF_HEAL_DURUMU
            durum["attempts"] = 0
            durum["scheduled"] = False
            durum["last_reason"] = ""
        except Exception:
            pass
        _netops_send_tablet_command(
            "tablet_audio_stream",
            {"enabled": False, "reason": "live_stopped"},
            broadcast=True,
            reason="live",
            async_dispatch=True,
        )
        _netops_send_tablet_command(
            "live_screen",
            {"show": False, "title": "NETOPS LIVE MODE"},
            broadcast=True,
            reason="live",
            async_dispatch=True,
        )
        _netops_send_tablet_voice_event(
            "idle",
            text="",
            level=0,
            speak=False,
            reason="live",
            broadcast=True,
            async_dispatch=True,
        )
        _netops_tablet_audio_stream_clear(remove_file=True)
    except Exception:
        pass


def live_panel_kapat_ve_durdur():
    live_mode_durdur()
    live_panel_gizle()


def neto_patch_log(metin):
    """v10.1 patch basit log sistemi."""
    try:
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "patch.log"), "a", encoding="utf-8") as f:
            f.write(str(metin) + "\n")
    except Exception:
        pass


def live_gecis_onayla():
    """v10.34: Live artık ayrı program/panel değil, alt modern çubuk içinde çalışır."""
    try:
        fn = globals().get("inline_live_toggle")
        if callable(fn):
            return fn()
        # UI daha kurulmadıysa controller'ı güvenli başlat.
        return live_mode_baslat()
    except Exception as e:
        try:
            animasyonlu_yazi(f"Live başlatılamadı: {e}")
        except Exception:
            pass


def neto_weather_try_answer(metin):
    """Ana sohbet için hava/konum komutlarını AI'ye gitmeden cevaplar."""
    try:
        if neto_weather.is_location_query(metin):
            return neto_weather.location_answer(metin)
        if neto_weather.is_weather_query(metin):
            return neto_weather.weather_answer(metin)
    except Exception as e:
        try:
            os.makedirs("logs", exist_ok=True)
            with open("logs/weather.log", "a", encoding="utf-8") as f:
                f.write(str(e) + "\n")
        except Exception:
            pass
        return f"Hava durumu alınamadı: {e}"
    return None


def _neto_agent_modu_metin(tr_text: str, en_text: str) -> str:
    try:
        return tr_text if str(dil_getir()).lower().startswith("tr") else en_text
    except Exception:
        return tr_text


def _neto_agent_modu_guncelle(acik: bool, duyuru: bool = True) -> None:
    globals()["_NETO_AGENT_MODU"] = bool(acik)
    try:
        _neto_agent_panellerini_guncelle = globals().get("_neto_agent_panellerini_guncelle")
        if callable(_neto_agent_panellerini_guncelle):
            _neto_agent_panellerini_guncelle(acik)
    except Exception:
        pass
    try:
        if "giris" in globals() and giris.winfo_exists():
            giris.configure(
                placeholder_text=(
                    _neto_agent_modu_metin(
                        "Agent açık. Bana yaz, ben AI gibi cevap vereyim. n.ext ile kapat.",
                        "Agent is on. Type to chat with the AI. Use n.ext to close.",
                    )
                    if acik
                    else T("entry_placeholder")
                )
            )
    except Exception:
        pass
    if duyuru:
        try:
            animasyonlu_yazi(
                _neto_agent_modu_metin(
                    "Agent açık. Benimle sohbet edebilirsin.",
                    "Agent is open. You can chat with me.",
                )
                if acik
                else _neto_agent_modu_metin("Agent kapatıldı.", "Agent closed.")
            )
        except Exception:
            pass


def _neto_sohbet_modu_odakla(event=None):
    """Barı tıklayınca sohbet modunda kal ve yazı alanına odaklan."""
    _neto_agent_modu_guncelle(False, duyuru=False)
    try:
        if "giris" in globals() and giris.winfo_exists():
            _neto_widget_focus_guvenli(giris, kaynak="sohbet_modu_odakla")
    except Exception:
        pass


def _neto_vpn_norm(metin):
    return re.sub(r"[^a-z0-9]+", " ", str(metin or "").casefold()).strip()


def _neto_vpn_parca_listesi(proc_info):
    parcaciklar = []
    try:
        for alan in ("name", "exe"):
            raw = proc_info.get(alan)
            if not raw:
                continue
            stem = os.path.splitext(os.path.basename(str(raw)))[0]
            norm = _neto_vpn_norm(stem)
            if norm:
                parcaciklar.append(norm)
    except Exception:
        pass

    try:
        for raw in proc_info.get("cmdline") or []:
            stem = os.path.splitext(os.path.basename(str(raw)))[0]
            norm = _neto_vpn_norm(stem)
            if norm:
                parcaciklar.append(norm)
    except Exception:
        pass

    return parcaciklar


def _neto_vpn_parca_eslesir_mi(parca, ipucu):
    parca_norm = _neto_vpn_norm(parca)
    ipucu_norm = _neto_vpn_norm(ipucu)
    if not parca_norm or not ipucu_norm:
        return False

    parca_compact = parca_norm.replace(" ", "")
    ipucu_compact = ipucu_norm.replace(" ", "")

    if parca_norm == ipucu_norm or parca_compact == ipucu_compact:
        return True

    if " " in ipucu_norm:
        if f" {ipucu_norm} " in f" {parca_norm} ":
            return True
        if ipucu_compact in parca_compact:
            return True
        return False

    if ipucu_norm in parca_norm.split():
        return True

    return ipucu_compact == parca_compact


def _neto_vpn_etiket_bul(metin):
    parcaciklar = _neto_vpn_parca_listesi({"name": metin, "exe": metin, "cmdline": []})
    if not parcaciklar:
        return None

    for grup in globals().get("VPN_TESPIT_LISTESI", []):
        etiket = str(grup.get("etiket") or "VPN").strip() or "VPN"
        for ipucu in grup.get("ipuclari", []):
            if any(_neto_vpn_parca_eslesir_mi(parca, ipucu) for parca in parcaciklar):
                return etiket

    return None


def _neto_vpn_aktif_prosesleri():
    sonuc = []
    if psutil is None:
        return sonuc

    try:
        for proc in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
            try:
                bilgi = getattr(proc, "info", {}) or {}
                parcaciklar = _neto_vpn_parca_listesi(bilgi)
                ad = " | ".join(parcaciklar).strip()
                etiket = None
                for grup in globals().get("VPN_TESPIT_LISTESI", []):
                    aday_etiket = str(grup.get("etiket") or "VPN").strip() or "VPN"
                    if any(
                        _neto_vpn_parca_eslesir_mi(parca, ipucu)
                        for parca in parcaciklar
                        for ipucu in grup.get("ipuclari", [])
                    ):
                        etiket = aday_etiket
                        break
                if etiket:
                    sonuc.append(
                        {
                            "pid": int(bilgi.get("pid") or proc.pid),
                            "etiket": etiket,
                            "ad": ad,
                        }
                    )
            except Exception:
                continue
    except Exception:
        return sonuc

    return sonuc


def _neto_vpn_process_kapat(pid):
    try:
        if psutil is not None:
            proc = psutil.Process(int(pid))
            for cocuk in proc.children(recursive=True):
                try:
                    cocuk.kill()
                except Exception:
                    pass
            try:
                proc.kill()
            except Exception:
                proc.terminate()
            return True
    except Exception:
        pass

    try:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(int(pid))],
            capture_output=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return True
    except Exception:
        return False


def _neto_vpn_eslesenleri_kapat(eslesenler):
    basarili = False
    for item in eslesenler:
        try:
            if _neto_vpn_process_kapat(item.get("pid")):
                basarili = True
        except Exception:
            pass
    return basarili


def _neto_vpn_izleyici_calisabilir_mi():
    try:
        if not globals().get("root") or not root.winfo_exists():
            return False
        try:
            pencere_durumu = str(root.state()).lower()
        except Exception:
            pencere_durumu = ""
        return pencere_durumu not in {"iconic", "withdrawn"}
    except Exception:
        return False


class _NetoVpnUyariPenceresi:
    def __init__(self, root_ref, eslesenler):
        self.root = root_ref
        self.eslesenler = list(eslesenler or [])
        self.bubble = ctk.CTkToplevel(root_ref)
        self.bubble.title(f"{APP_NAME} Agent")
        self.bubble.resizable(False, False)
        self.bubble.attributes("-topmost", True)
        try:
            self.bubble.overrideredirect(True)
        except Exception:
            pass
        try:
            self.bubble.attributes("-alpha", 0.98)
        except Exception:
            pass
        try:
            screen_w = root_ref.winfo_screenwidth()
            screen_h = root_ref.winfo_screenheight()
            self.bubble.geometry(f"380x210+{max(20, screen_w - 410)}+{max(20, screen_h - 260)}")
        except Exception:
            pass

        self.bubble.configure(fg_color="#101114")
        self.bubble.bind("<Double-Button-1>", self._asistani_ac)

        self.frame = ctk.CTkFrame(
            self.bubble,
            fg_color="#16181d",
            corner_radius=15,
            border_width=2,
            border_color="#8b5cf6",
        )
        self.frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.frame.bind("<Double-Button-1>", self._asistani_ac)

        self.baslik = ctk.CTkLabel(
            self.frame,
            text="VPN açık. Kapatılsın mı?",
            font=("Segoe UI", 18, "bold"),
            text_color="#ffffff",
        )
        self.baslik.pack(pady=(16, 6), padx=16)
        self.baslik.bind("<Double-Button-1>", self._asistani_ac)

        self.detay = ctk.CTkLabel(
            self.frame,
            text=self._detay_metin(),
            font=("Segoe UI", 13),
            text_color="#cfcfe8",
            wraplength=330,
            justify="center",
        )
        self.detay.pack(pady=(0, 10), padx=16)
        self.detay.bind("<Double-Button-1>", self._asistani_ac)

        self.sayac = ctk.CTkLabel(
            self.frame,
            text="İlk uyarı",
            font=("Segoe UI", 16, "bold"),
            text_color="#f5d0fe",
        )
        self.sayac.pack(pady=(0, 10))
        self.sayac.bind("<Button-1>", self._buradayim)
        self.sayac.bind("<Double-Button-1>", self._asistani_ac)

        butonlar = ctk.CTkFrame(self.frame, fg_color="transparent")
        butonlar.pack(fill="x", padx=14, pady=(0, 10))

        self.kapat_buton = ctk.CTkButton(
            butonlar,
            text="VPN'yi Kapat",
            fg_color="#dc2626",
            hover_color="#ef4444",
            text_color="#ffffff",
            corner_radius=14,
            command=self._vpn_kapat,
        )
        self.kapat_buton.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.ben_buradayim_buton = ctk.CTkButton(
            butonlar,
            text="Ben buradayım",
            fg_color="#334155",
            hover_color="#475569",
            text_color="#ffffff",
            corner_radius=14,
            command=self._buradayim,
        )
        self.ben_buradayim_buton.pack(side="left", fill="x", expand=True, padx=(6, 0))

        alt = ctk.CTkLabel(
            self.frame,
            text="Çift tıkla: NetOps açılır",
            font=("Segoe UI", 11),
            text_color="#9ca3af",
        )
        alt.pack(pady=(0, 12))
        alt.bind("<Double-Button-1>", self._asistani_ac)

    def _detay_metin(self):
        etiketler = []
        for item in self.eslesenler[:3]:
            etiket = str(item.get("etiket") or "VPN")
            if etiket not in etiketler:
                etiketler.append(etiket)
        if not etiketler:
            return "Bir VPN süreci çalışıyor gibi görünüyor. Kapatıp kapatmamamı söyleyebilirsin."
        return "Algılanan süreçler: " + ", ".join(etiketler) + "."

    def _guncelle(self, metin=None, renk=None):
        if not self.bubble or not self.bubble.winfo_exists():
            return
        if metin is not None:
            try:
                self.detay.configure(text=str(metin))
            except Exception:
                pass
        if renk is not None:
            try:
                self.sayac.configure(text_color=str(renk))
            except Exception:
                pass

    def _asistani_ac(self, event=None):
        try:
            root.after(
                0,
                lambda: neto_chat_ac(
                    root,
                    acilis_mesaji="Sistemi daha hızlı kullanmak için VPN'yi kapatmanı öneriyorum.",
                ),
            )
        except Exception:
            try:
                neto_chat_ac(
                    root,
                    acilis_mesaji="Sistemi daha hızlı kullanmak için VPN'yi kapatmanı öneriyorum.",
                )
            except Exception:
                pass
        return "break"

    def _buradayim(self, event=None):
        durum = _NETO_VPN_IZLEYICI_DURUMU
        durum["last_ack_time"] = time.time()
        durum["countdown_left"] = 30
        durum["escalation_active"] = False
        try:
            if durum.get("countdown_job"):
                root.after_cancel(durum["countdown_job"])
        except Exception:
            pass
        durum["countdown_job"] = None
        try:
            durum["first_seen"] = {pid: time.time() for pid in durum.get("tracked_pids", set())}
        except Exception:
            pass
        try:
            self.sayac.configure(text="Ben buradayım", text_color="#86efac")
            self._guncelle("Tamam, seni burada görüyorum. Geri sayım durduruldu.")
        except Exception:
            pass
        return "break"

    def _vpn_kapat(self):
        kapanan = _neto_vpn_eslesenleri_kapat(self.eslesenler)
        try:
            self._guncelle("VPN süreci kapatılıyor..." if kapanan else "VPN kapatılamadı.", "#fbbf24" if kapanan else "#f87171")
            self.sayac.configure(text="Kapatılıyor..." if kapanan else "Kapatılamadı", text_color="#fbbf24" if kapanan else "#f87171")
        except Exception:
            pass
        if kapanan:
            self.kapat()
        return kapanan

    def countdown_baslat(self, saniye=30):
        durum = _NETO_VPN_IZLEYICI_DURUMU
        durum["escalation_active"] = True
        durum["countdown_left"] = int(saniye)
        self._countdown_tick()

    def _countdown_tick(self):
        durum = _NETO_VPN_IZLEYICI_DURUMU
        if not self.bubble or not self.bubble.winfo_exists():
            return

        kalan = int(durum.get("countdown_left", 0))
        if kalan <= 0:
            self.sayac.configure(text="VPN otomatik kapatılıyor", text_color="#f87171")
            self._guncelle("30 saniye içinde yanıt gelmedi. VPN kapatılıyor.", "#f87171")
            self._vpn_kapat()
            return

        self.sayac.configure(text=f"{kalan} sn", text_color="#f5d0fe")
        self._guncelle(
            f"Buradaysan saniyeye tıkla. Cevap gelmezse VPN {kalan} saniye içinde kapanacak.",
            "#f5d0fe",
        )
        durum["countdown_left"] = kalan - 1
        try:
            durum["countdown_job"] = root.after(1000, self._countdown_tick)
        except Exception:
            durum["countdown_job"] = None

    def kapat(self):
        durum = _NETO_VPN_IZLEYICI_DURUMU
        try:
            if durum.get("countdown_job"):
                root.after_cancel(durum["countdown_job"])
        except Exception:
            pass
        durum["countdown_job"] = None
        durum["last_signature"] = None
        try:
            if self.bubble and self.bubble.winfo_exists():
                self.bubble.destroy()
        except Exception:
            pass
        globals()["_NETO_VPN_UYARI_PENCERESI"] = None


def _neto_vpn_uyari_penceresi_kapat():
    pencere = globals().get("_NETO_VPN_UYARI_PENCERESI")
    if pencere is not None:
        try:
            pencere.kapat()
        except Exception:
            globals()["_NETO_VPN_UYARI_PENCERESI"] = None


def _neto_vpn_uyari_penceresi_ac(eslesenler):
    global _NETO_VPN_UYARI_PENCERESI
    if not globals().get("VPN_KORUMA_AKTIF", True):
        return

    if not eslesenler:
        return

    if _NETO_VPN_UYARI_PENCERESI is not None:
        try:
            if _NETO_VPN_UYARI_PENCERESI.bubble.winfo_exists():
                _NETO_VPN_UYARI_PENCERESI.eslesenler = list(eslesenler)
                _NETO_VPN_UYARI_PENCERESI._guncelle(_NETO_VPN_UYARI_PENCERESI._detay_metin())
                return
        except Exception:
            _NETO_VPN_UYARI_PENCERESI = None

    try:
        _NETO_VPN_UYARI_PENCERESI = _NetoVpnUyariPenceresi(root, eslesenler)
    except Exception as e:
        try:
            print(f"[VPN_UYARI_ACILAMADI] {e}", flush=True)
        except Exception:
            pass
        _NETO_VPN_UYARI_PENCERESI = None


def _neto_vpn_izleyicisi_belirle():
    if not globals().get("VPN_KORUMA_AKTIF", True):
        return
    durum = _NETO_VPN_IZLEYICI_DURUMU

    if not _neto_vpn_izleyici_calisabilir_mi():
        durum["first_seen"].clear()
        durum["tracked_pids"] = set()
        durum["last_signature"] = None
        durum["escalation_active"] = False
        durum["countdown_left"] = 30
        try:
            if durum.get("countdown_job"):
                root.after_cancel(durum["countdown_job"])
        except Exception:
            pass
        durum["countdown_job"] = None
        root.after(0, _neto_vpn_uyari_penceresi_kapat)
        return

    aktifler = _neto_vpn_aktif_prosesleri()
    aktif_pidler = {item["pid"] for item in aktifler}
    durum["tracked_pids"] = set(aktif_pidler)

    simdi = time.time()

    if aktifler:
        for item in aktifler:
            pid = item["pid"]
            durum["first_seen"].setdefault(pid, simdi)

        for pid in list(durum["first_seen"].keys()):
            if pid not in aktif_pidler:
                durum["first_seen"].pop(pid, None)

        signature = tuple(sorted(f"{item['pid']}:{item['etiket']}" for item in aktifler))
        pencere = globals().get("_NETO_VPN_UYARI_PENCERESI")
        pencere_var = False
        try:
            pencere_var = pencere is not None and pencere.bubble.winfo_exists()
        except Exception:
            pencere_var = False

        if signature != durum.get("last_signature") or not pencere_var:
            durum["last_signature"] = signature
            root.after(0, lambda items=list(aktifler): _neto_vpn_uyari_penceresi_ac(items))

        ilk_gorus = min(durum["first_seen"].values() or [simdi])
        gecen = simdi - float(ilk_gorus)

        if gecen >= 600 and not durum.get("escalation_active", False):
            durum["escalation_active"] = True
            try:
                pencere = globals().get("_NETO_VPN_UYARI_PENCERESI")
                if pencere is not None and pencere.bubble.winfo_exists():
                    root.after(0, lambda p=pencere: p.countdown_baslat(30))
            except Exception:
                pass

        return

    durum["first_seen"].clear()
    durum["tracked_pids"] = set()
    durum["last_signature"] = None
    durum["escalation_active"] = False
    durum["countdown_left"] = 30
    try:
        if durum.get("countdown_job"):
            root.after_cancel(durum["countdown_job"])
    except Exception:
        pass
    durum["countdown_job"] = None
    root.after(0, _neto_vpn_uyari_penceresi_kapat)


def _neto_vpn_izleyici_dongusu():
    if not globals().get("VPN_KORUMA_AKTIF", True):
        return
    durum = _NETO_VPN_IZLEYICI_DURUMU
    if not globals().get("root") or not root.winfo_exists():
        durum["monitor_started"] = False
        return

    try:
        _neto_vpn_izleyicisi_belirle()
    except Exception as e:
        try:
            print(f"[VPN_IZLEYICI_HATA] {e}", flush=True)
        except Exception:
            pass

    try:
        root.after(4000, _neto_vpn_izleyici_dongusu)
    except Exception:
        durum["monitor_started"] = False


def _neto_vpn_izleyicisini_baslat():
    if not globals().get("VPN_KORUMA_AKTIF", True):
        return
    durum = _NETO_VPN_IZLEYICI_DURUMU
    if durum.get("monitor_started"):
        return
    durum["monitor_started"] = True
    try:
        root.after(6500, _neto_vpn_izleyici_dongusu)
    except Exception:
        durum["monitor_started"] = False


def _neto_agent_modu_ac(duyuru: bool = True) -> None:
    _neto_agent_modu_guncelle(True, duyuru=duyuru)
    try:
        if "giris" in globals() and giris.winfo_exists():
            _neto_widget_focus_guvenli(giris, kaynak="agent_modu_ac")
    except Exception:
        pass


def _neto_agent_modu_kapat(duyuru: bool = True) -> None:
    _neto_agent_modu_guncelle(False, duyuru=duyuru)
    try:
        if "giris" in globals() and giris.winfo_exists():
            _neto_widget_focus_guvenli(giris, kaynak="agent_modu_kapat")
    except Exception:
        pass


def _neto_agent_uygulama_ac(app_name: str) -> str | None:
    query = str(app_name or "").strip()
    if not query:
        return _neto_agent_modu_metin(
            "Uygulama adı boş olamaz.",
            "App name cannot be empty.",
        )

    if os.name != "nt" or not K_WIN:
        return _neto_agent_modu_metin(
            "Bu özellik şu an yalnızca Windows'ta çalışır.",
            "This feature currently works only on Windows.",
        )

    try:
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.03
        width, height = pyautogui.size()
        pyautogui.moveTo(max(10, width // 2), max(10, height - 24), duration=0.18)
        time.sleep(0.10)
        pyautogui.press("winleft")
        time.sleep(0.30)
        pyautogui.write(query, interval=0.03)
        time.sleep(0.08)
        pyautogui.press("enter")
        return None
    except Exception as exc:
        try:
            pyautogui.press("winleft")
            time.sleep(0.20)
            pyautogui.write(query, interval=0.04)
            time.sleep(0.08)
            pyautogui.press("enter")
            return None
        except Exception as fallback_exc:
            return str(fallback_exc or exc)


globals()["_NETO_AGENT_MODU"] = False


def _neto_autopilot_intercept(text: str) -> bool:
    """Return True when a chat message must be routed to local Autopilot first.

    Agent/Web mode normally sends messages straight to the AI engine. Autopilot
    commands and pending Evet/Hayır confirmations are local control commands, so
    they must bypass that route.
    """
    try:
        if globals().get("_NETO_AUTOPILOT_PENDING") is not None:
            return True
        folded = str(text or "").casefold().strip()
        if not folded:
            return False
        # Fast path keeps normal Agent chat untouched.
        # Only inspect messages that look like an Autopilot request.
        if not any(marker in folded for marker in ("autopilot", "hazırla", "hazirla")):
            return False

        # Deterministic scene guard. This is intentionally duplicated at the
        # router boundary so a missing/stale optional module can NEVER turn a
        # clear local command into a web search.
        scene_words = (
            "çalışma", "calisma", "iş", "is", "oyun", "ders", "film",
            "dizi", "yayın", "yayin", "stream", "uyku", "sessiz",
        )
        if ("hazırla" in folded or "hazirla" in folded) and any(
            re.search(rf"(?<!\w){re.escape(word)}(?!\w)", folded)
            for word in scene_words
        ):
            return True

        import neto_autopilot
        return neto_autopilot.prepare(text) is not None
    except Exception:
        # If Autopilot itself has a problem, let lokal_sistem_islemcisi surface
        # the real error instead of silently turning the command into web chat.
        folded = str(text or "").casefold()
        return "autopilot" in folded or "hazırla" in folded or "hazirla" in folded


def cevap_ver():
    global ogrenme_modu, onay_modu, son_soru, secili_resim_yolu

    try:
        cevap_baslangic = time.perf_counter()
        m = giris.get().strip()
        m_kucuk = m.casefold().strip()

        if m_kucuk == ".agent":
            giris.delete(0, tk.END)
            _neto_agent_modu_ac()
            return

        if m_kucuk == "n.ext":
            giris.delete(0, tk.END)
            _neto_agent_modu_kapat()
            return

        # Autopilot is a local control-plane command. Detect it BEFORE the
        # inline Live/Text route, otherwise Live text mode can consume phrases
        # such as “Oyun için hazırla” and send them to the web answer engine.
        _autopilot_local_request = bool(m and _neto_autopilot_intercept(m))
        if _autopilot_local_request:
            try:
                print(f"[AUTOPILOT_ROUTER] local intercept: {m}", flush=True)
            except Exception:
                pass

        live_state = globals().get("inline_live_state", {})
        if live_state.get("active") and live_state.get("text_mode") and not _autopilot_local_request:
            return live_metin_cevap_ver(m)

        resim_analiz_yolu = None
        if secili_resim_yolu:
            resim_analiz_yolu = secili_resim_yolu
            if not m:
                m = "Bu resmi analiz et."
            try:
                ekli_resim_karti_gizle()
            except Exception:
                pass

        if not m:
            return
        giris.delete(0, tk.END)
        thinking_row = None
        try:
            _neto_sohbet_balonu_ekle(m, "user")
            thinking_row = None
        except Exception:
            thinking_row = None

        try:
            giris.configure(state="disabled")
            btn_gonder.configure(state="disabled")
        except Exception:
            pass

        def arka_planda_calistir():
            try:
                h = veri_yukle()

                if h.get("kufur_filtresi", True) and kufur_var_mi(m):
                    cevap = T("polite_warning") if "T" in globals() else "⚠️ Lütfen daha nazik bir dil kullan."
                elif resim_analiz_yolu:
                    try:
                        cevap = neto_ai.neto_ai_resim_analiz_et(m, resim_analiz_yolu)
                    except Exception as e:
                        cevap = f"Resim analizi hatası: {e}"
                elif _autopilot_local_request:
                    # Autopilot is a local control plane. It takes precedence over
                    # Agent/Web/Live-text chat so phrases like “Oyun için hazırla”
                    # cannot be misread as a generic web query.
                    cevap = lokal_sistem_islemcisi(m)
                elif globals().get("_NETO_AGENT_MODU", False):
                    if m_kucuk in {"internet aç", "interneti aç", "web aç"}:
                        try:
                            neto_ai.internet_durum_ayarla(True)
                        except Exception:
                            pass
                        cevap = "İnternet açıldı."
                    elif m_kucuk in {"internet kapat", "interneti kapat", "web kapat"}:
                        try:
                            neto_ai.internet_durum_ayarla(False)
                        except Exception:
                            pass
                        cevap = "İnternet kapatıldı."
                    else:
                        try:
                            if m_kucuk.startswith(("hangi ilaç", "hangi ilac", "hangi araç", "hangi arac", "hangi araba", "hangi otomobil")):
                                neto_ai.internet_durum_ayarla(True)
                        except Exception:
                            pass
                        cevap = neto_ai.neto_ai_cevap_ver(m, agent_modu=True)
                else:
                    cevap = lokal_sistem_islemcisi(m)
                    try:
                        print(f"[TIME] Ana cevap üretimi: {time.perf_counter() - cevap_baslangic:.2f}s", flush=True)
                    except Exception:
                        pass

                if not cevap:
                    cevap = T("chat_no_answer") if "T" in globals() else "No response received."

            except Exception as e:
                _neto_kendini_onar("cevap_ver", e)
                try:
                    cevap = lokal_sistem_islemcisi(m)
                except Exception:
                    cevap = T("chat_no_answer") if "T" in globals() else "No response received."

            def ui_guncelle():
                try:
                    try:
                        _neto_sohbet_mesaj_sil(thinking_row)
                    except Exception:
                        pass
                    cevap_temiz = komut_token_temizle(cevap)
                    if not cevap_temiz:
                        cevap_temiz = T("ready") if "T" in globals() else "Done."
                    animasyonlu_yazi(cevap_temiz)
                finally:
                    try:
                        giris.configure(state="normal")
                        btn_gonder.configure(state="normal")
                        _neto_widget_focus_guvenli(giris, kaynak="cevap_ver_ui")
                    except Exception:
                        pass

            root.after(0, ui_guncelle)

        threading.Thread(target=arka_planda_calistir, daemon=True).start()

    except Exception as e:
        try:
            _neto_kendini_onar("cevap_ver_outer", e)
            animasyonlu_yazi(T("chat_no_answer") if "T" in globals() else "No response received.")
        except Exception:
            pass

# ------------------------------------------------------------
# NETO AI BAŞLATMA UYARISI
# ------------------------------------------------------------
def neto_ai_baslat():
    neto_time_log("NetOps Agent butonuna basıldı")
    """Web tabanlı sohbeti açar; ek kurulum istemez."""

    cevap = messagebox.askyesno(
        "Web Sohbeti",
        "Web tabanlı sohbeti açmak istiyor musun?\n\nYanıtlar internet üzerinden hazırlanır."
    )

    if not cevap:
        return

    try:
        def _agent_sohbeti_hazirla(attempt=0):
            opener = globals().get("neto_ai_chat_uygulama_icinde_ac")
            if callable(opener):
                try:
                    if opener() is not None:
                        return
                except Exception as exc:
                    if attempt >= 30:
                        raise exc
            if attempt < 30:
                root.after(120, lambda: _agent_sohbeti_hazirla(attempt + 1))
                return
            raise RuntimeError("Agent sohbet yüzeyi zamanında hazırlanamadı.")

        root.after(100, _agent_sohbeti_hazirla)
    except Exception as e:
        try:
            messagebox.showerror("NetOps Agent Hatası", f"NetOps Agent açılamadı:\n{e}")
        except Exception:
            pass


# ------------------------------------------------------------
# ANİMASYONLU DİL SEÇİMİ
# ------------------------------------------------------------


def neto_android_device_ac_safe(crash_alert_log=None):
    """Open Android USB Device Doctor without loading ADB during startup."""
    try:
        import neto_android_device
        return neto_android_device.android_device_doctor_ac(
            root,
            T=T,
            palette=aktif_palet,
            say_callback=animasyonlu_yazi,
            crash_alert_log=crash_alert_log,
        )
    except Exception as e:
        try:
            messagebox.showerror("Android Device", f"Android Device Doctor açılamadı:\n{e}")
        except Exception:
            print(e)


def neto_device_hub_ac_safe():
    """Open the NETOPS Android device hub."""
    try:
        mod = _neto_lazy_import("neto_device_hub")
        return mod.neto_device_hub_ac_safe(
            parent=root,
            T=T,
            palette=aktif_palet,
            say_callback=animasyonlu_yazi,
        )
    except Exception as e:
        try:
            messagebox.showerror("NETOPS Device Hub", f"Device Hub açılamadı:\n{e}")
        except Exception:
            print(e)


def neto_remote_hub_start_safe():
    """Start the paired mobile bridge on the PC's active LAN address only."""
    try:
        settings = veri_yukle()
        if settings.get("remote_link_enabled", True) is False:
            return {"ok": True, "disabled": True}
        mod = _neto_lazy_import("neto_device_hub")
        mod.device_hub_set_assistant_handler(neto_remote_assistant_request)
        mod.device_hub_set_media_handler(neto_remote_media_request)
        lan_ip = getattr(mod, "_local_ip_address", lambda: "127.0.0.1")()
        result = mod.device_hub_start(host=lan_ip, port=8765)
        if not result.get("ok"):
            print(f"[REMOTE_HUB_START_ERROR] {result.get('error', 'unknown')}", flush=True)
        else:
            print(f"[REMOTE_HUB] local PC endpoint={lan_ip}:{result.get('port')}", flush=True)
        return result
    except Exception as exc:
        try:
            print(f"[REMOTE_HUB_START_ERROR] {exc}", flush=True)
        except Exception:
            pass
        return {"ok": False, "error": str(exc)}


def dil_secim_penceresi_ac(parent, zorunlu=False, sonra=None):
    """İlk açılışta veya Dil butonundan animasyonlu dil seçimi açar."""
    pencere = ctk.CTkToplevel(parent)
    pencere.title(T("language_selection"))
    pencere.geometry("430x250")
    pencere.resizable(False, False)
    pencere.configure(fg_color="#050505")
    pencere.attributes("-topmost", True)

    if zorunlu:
        try:
            pencere.grab_set()
        except Exception:
            pass

    try:
        parent.update_idletasks()
        x = int((parent.winfo_screenwidth() / 2) - (430 / 2))
        y = int((parent.winfo_screenheight() / 2) - (250 / 2))
        pencere.geometry(f"430x250+{x}+{y}")
    except Exception:
        pass

    try:
        pencere.attributes("-alpha", 0.0)
    except Exception:
        pass

    baslik = ctk.CTkLabel(
        pencere,
        text=T("language_title"),
        font=("Segoe UI", 24, "bold"),
        text_color="#ffffff"
    )
    baslik.pack(pady=(35, 8))

    aciklama = ctk.CTkLabel(
        pencere,
        text=T("language_desc"),
        font=("Segoe UI", 14),
        text_color="#bdbdbd"
    )
    aciklama.pack(pady=(0, 22))

    buton_frame = ctk.CTkFrame(pencere, fg_color="transparent")
    buton_frame.pack(pady=5)

    def sec(dil):
        dil_kaydet(dil)
        try:
            pencere.destroy()
        except Exception:
            pass
        if callable(sonra):
            try:
                sonra()
            except Exception:
                pass

    ctk.CTkButton(
        buton_frame,
        text="🇹🇷 " + DIL_METINLERI["tr"]["turkish"],
        width=150,
        height=42,
        corner_radius=18,
        fg_color="#1f1f1f",
        hover_color="#2f2f2f",
        text_color="#ffffff",
        command=lambda: sec("tr")
    ).pack(side="left", padx=10)

    ctk.CTkButton(
        buton_frame,
        text="🇬🇧 " + DIL_METINLERI["en"]["english"],
        width=150,
        height=42,
        corner_radius=18,
        fg_color="#1f1f1f",
        hover_color="#2f2f2f",
        text_color="#ffffff",
        command=lambda: sec("en")
    ).pack(side="left", padx=10)

    def fade(i=0):
        try:
            if not pencere.winfo_exists():
                return
            t = min(1.0, i / 14)
            oran = 1.0 if t >= 1.0 else max(0.0, min(1.0, 1.0 - (2.0 ** (-8.0 * t))))
            pencere.attributes("-alpha", oran)
            if i < 14:
                pencere.after(14, lambda: fade(i + 1))
        except Exception:
            pass

    fade()


# Ayarlar sayfası ve ana arayüzde modül içinde sabit bırakılmış metinler için
# iki yönlü çalışma-zamanı çeviri tablosu. Yalnızca tam eşleşen UI metinleri
# değiştirilir; kullanıcının yazdığı içeriklere ve şarkı adlarına dokunulmaz.
_UI_EN_TR = {
    "Settings": "Ayarlar",
    "App settings": "Uygulama ayarları",
    "All NetOps settings in one place.": "Tüm NetOps ayarları tek yerde.",
    "Hello! I am NetOps. How can I help you? 👋": "Merhaba! Ben NetOps. Sana nasıl yardımcı olabilirim? 👋",
    "Live listening stopped.": "Canlı dinleme durdu.",
    "SETTINGS": "AYARLAR",
    "General": "Genel",
    "Appearance": "Görünüm",
    "Security": "Güvenlik",
    "Updates": "Güncellemeler",
    "About": "Hakkında",
    "Core app behavior and language.": "Temel uygulama davranışı ve dil.",
    "Application language": "Uygulama dili",
    "Language changes are applied instantly on the same screen.": "Dil değişiklikleri aynı ekrana anında uygulanır.",
    "Startup behavior": "Başlangıç davranışı",
    "Choose which features start with the app.": "Uygulamayla hangi özelliklerin başlayacağını seç.",
    "Start Live Mode automatically": "Live Mode'u otomatik başlat",
    "Learning mode": "Öğrenme modu",
    "Local operation": "Yerel çalışma",
    "Local API": "Yerel API",
    "Keep the local assistant API enabled.": "Yerel asistan API'sini açık tut.",
    "Theme and visual preferences.": "Tema ve görünüm tercihleri.",
    "Theme mode": "Tema modu",
    "Accent color": "Vurgu rengi",
    "Select Neto's main interface accent.": "NetOps arayüzünün ana vurgu rengini seç.",
    "Color theme": "Renk teması",
    "Dark": "Koyu",
    "Light": "Açık",
    "Use dark theme": "Koyu temayı kullan",
    "Use light theme": "Açık temayı kullan",
    "Startup animation and sound.": "Açılış animasyonu ve sesi.",
    "Startup animation": "Açılış animasyonu",
    "Startup sound": "Açılış sesi",
    "Active GIF": "Aktif GIF",
    "Select new GIF": "Yeni GIF seç",
    "Active sound": "Aktif ses",
    "Select new sound": "Yeni ses seç",
    "Factory reset": "Fabrika ayarlarına dön",
    "Restore defaults": "Varsayılanları geri yükle",
    "Safety and filtering.": "Güvenlik ve filtreleme.",
    "Swear filter": "Küfür filtresi",
    "Security settings": "Güvenlik ayarları",
    "Update settings": "Güncelleme ayarları",
    "Keep NetOps up to date.": "NetOps'u güncel tut.",
    "Check for updates": "Güncellemeleri kontrol et",
    "Checking for updates...": "Güncellemeler kontrol ediliyor...",
    "Current version": "Mevcut sürüm",
    "Latest version": "En son sürüm",
    "You already have the latest version.": "Zaten en son sürümü kullanıyorsun.",
    "Download update": "Güncellemeyi indir",
    "Restart and update": "Yeniden başlat ve güncelle",
    "Application information.": "Uygulama bilgileri.",
    "Version": "Sürüm",
    "Developer": "Geliştirici",
    "Close settings": "Ayarları kapat",
    "Back": "Geri",
    "Save": "Kaydet",
    "Apply": "Uygula",
    "Reset": "Sıfırla",
    "Enabled": "Açık",
    "Disabled": "Kapalı",
    "On": "Açık",
    "Off": "Kapalı",
    "Notes": "Notlar",
    "My Notes": "Notlarım",
    "System": "Sistem",
    "Open Store  Ctrl+E": "Mağazayı Aç  Ctrl+E",
    "Extension Store": "Eklenti Mağazası",
    "Open apps quickly inside Assistant.": "Uygulamaları Asistan içinde hızlıca aç.",
    "Search extensions...": "Eklentilerde ara...",
    "Click to open": "Açmak için tıkla",
    "Open": "Aç",
    "No results found.": "Sonuç bulunamadı.",
    "Preparing store...": "Mağaza hazırlanıyor...",
    "Extension Status: OFF": "Eklenti Durumu: KAPALI",
    "Extension Status: ON": "Eklenti Durumu: AÇIK",
    "Start Now Playing": "Şimdi Çalıyor'u Aç",
    "Now Playing Settings": "Şimdi Çalıyor Ayarları",
    "Type your message...": "Mesajını yaz...",
    "Send": "Gönder",
}
_UI_TR_EN = {v: k for k, v in _UI_EN_TR.items()}
# Türkçe karşılığı farklı bir İngilizce ifadeye dönmesi gereken istisnalar.
_UI_TR_EN.update({
    "Ayarlar": "Settings",
    "Uygulama ayarları": "App settings",
    "Notlarım": "My Notes",
    "Şimdi Çalıyor'u Aç": "Open Now Playing",
    "Şimdi Çalıyor Ayarları": "Now Playing Settings",
})


def _ui_metin_cevir(metin, hedef_dil):
    try:
        raw = str(metin)
        stripped = raw.strip()
        if not stripped:
            return raw
        tablo = _UI_EN_TR if hedef_dil == "tr" else _UI_TR_EN
        if stripped in tablo:
            ceviri = tablo[stripped]
            return raw.replace(stripped, ceviri, 1)

        # Menü düğmelerinde başta ikon bulunabiliyor (ör. "⌂  General").
        # İkonu koruyup yalnızca sonundaki gerçek UI metnini değiştir.
        for kaynak, ceviri in sorted(tablo.items(), key=lambda item: len(item[0]), reverse=True):
            if stripped.endswith(kaynak) and stripped != kaynak:
                baslangic = stripped[:-len(kaynak)]
                if not baslangic or baslangic[-1].isspace() or not baslangic[-1].isalnum():
                    yeni_stripped = baslangic + ceviri
                    return raw.replace(stripped, yeni_stripped, 1)

        # Dinamik ayar satırları.
        dinamik = [
            (r"^Active GIF:\s*(.+)$", r"Aktif GIF: \1"),
            (r"^Aktif GIF:\s*(.+)$", r"Active GIF: \1"),
            (r"^Active sound:\s*(.+)$", r"Aktif ses: \1"),
            (r"^Aktif ses:\s*(.+)$", r"Active sound: \1"),
            (r"^Current version:\s*(.+)$", r"Mevcut sürüm: \1"),
            (r"^Mevcut sürüm:\s*(.+)$", r"Current version: \1"),
        ]
        for pattern, repl in dinamik:
            if (hedef_dil == "tr" and pattern.startswith("^Active")) or \
               (hedef_dil == "tr" and pattern.startswith("^Current")) or \
               (hedef_dil == "en" and (pattern.startswith("^Aktif") or pattern.startswith("^Mevcut"))):
                if re.match(pattern, stripped, flags=re.I):
                    return re.sub(pattern, repl, stripped, flags=re.I)
        return raw
    except Exception:
        return metin


def _arayuz_metnini_derin_yenile(widget=None):
    """Açık olan bütün CTk/Tk yüzeylerinde sabit UI metinlerini seçili dile çevirir."""
    try:
        hedef_dil = "tr" if str(dil_getir()).lower().startswith("tr") else "en"
        if widget is None:
            widget = globals().get("root")
        if widget is None:
            return

        try:
            mevcut = widget.cget("text")
        except Exception:
            mevcut = None
        if isinstance(mevcut, str):
            yeni = _ui_metin_cevir(mevcut, hedef_dil)
            if yeni != mevcut:
                try:
                    widget.configure(text=yeni)
                except Exception:
                    pass

        try:
            placeholder = widget.cget("placeholder_text")
        except Exception:
            placeholder = None
        if isinstance(placeholder, str):
            yeni_placeholder = _ui_metin_cevir(placeholder, hedef_dil)
            if yeni_placeholder != placeholder:
                try:
                    widget.configure(placeholder_text=yeni_placeholder)
                except Exception:
                    pass

        try:
            children = list(widget.winfo_children())
        except Exception:
            children = []
        for child in children:
            _arayuz_metnini_derin_yenile(child)
    except Exception:
        pass


def dil_uygula():
    """Seçili dili ana ekran, Ayarlar ve açık alt yüzeylere anında uygular."""
    try:
        root.title(T("app_title"))
    except Exception:
        pass
    try:
        titlebar_title.configure(text=APP_NAME if "APP_NAME" in globals() else "NetOps")
    except Exception:
        pass

    degisecekler = [
        ("lbl_sistem_durumu", "system_status"),
        ("lbl_notlar", "notes"),
        ("lbl_magaza", "extension_store"),
        ("lbl_welcome", "main_question"),
        
        ("btn_netoai", "neto_ai"),
        ("btn_android_device", "device_hub"),
        ("btn_gonder", "send"),
    ]

    for isim, anahtar in degisecekler:
        try:
            obj = globals().get(isim)
            if obj:
                obj.configure(text=T(anahtar))
        except Exception:
            pass

    try:
        lbl_sistem.configure(text="Araçlar" if str(dil_getir()).lower().startswith("tr") else "Tools")
    except Exception:
        pass

    try:
        if not eklenti_aktif_mi:
            btn_anahtar.configure(text=T("extension_status_off"))
        else:
            btn_anahtar.configure(text=T("extension_status_on"))
    except Exception:
        pass

    try:
        giris.configure(placeholder_text=T("entry_placeholder"))
    except Exception:
        pass

    try:
        turkce = str(dil_getir()).lower().startswith("tr")
        settings_profile_name.configure(text="Ayarlar" if turkce else "Settings")
        settings_title_label.configure(text="Uygulama ayarları" if turkce else "App settings")
        compact_settings_btn.configure(text="⚙  Ayarlar" if turkce else "⚙  Settings")
        btn_automation.configure(text="Otomasyon Merkezi" if turkce else "Automation Center")
        btn_scenes.configure(text="Neto Hazırla" if turkce else "Neto Prepare")
        btn_store_panel.configure(text="Mağazayı Aç  Ctrl+E" if turkce else "Open Store  Ctrl+E")
    except Exception:
        pass

    # Açık veya önceden hazırlanmış mağaza paneli de aynı anda dil değiştirir.
    try:
        fn = globals().get("_neto_store_refresh_language")
        if callable(fn):
            fn()
    except Exception:
        pass

    # Şimdi Çalıyor alanı da dil değişiminde beklemeden yenilenir.
    try:
        btn_now_playing_ayar.configure(text=now_playing_text("settings_short"))
        btn_now_playing_baslat.configure(text=now_playing_text("open_button_short"))
        home_settings = globals().get("home_now_playing_settings")
        home_open = globals().get("home_now_playing_open")
        if home_settings:
            home_settings.configure(text=now_playing_text("settings_short"))
        if home_open:
            home_open.configure(text=now_playing_text("open_button_short"))
        mevcut_info = globals().get("now_playing_monitor_last_info")
        now_playing_sidebar_guncelle(mevcut_info)
    except Exception:
        pass

    try:
        sidebar_yenile = globals().get("_sidebar_metinleri_yenile")
        if callable(sidebar_yenile):
            sidebar_yenile()
    except Exception:
        pass

    # Ana karşılama mesajı kullanıcı bir şey yazmadıysa seçili dile dönsün.
    # Eski sürümde başlık İngilizce olurken bu satır Türkçe kalabiliyordu.
    try:
        mevcut_cevap = str(etiket.cget("text") or "").strip()
        selam_isaretleri = (
            "Merhaba! Ben NetOps",
            "Hello! I am NetOps",
        )
        if any(isaret in mevcut_cevap for isaret in selam_isaretleri):
            etiket.configure(text=T("main_hello"))
    except Exception:
        pass

    try:
        fn = globals().get("_neto_settings_page_refresh_language")
        if callable(fn):
            fn()
    except Exception:
        pass

    try:
        _workspace_theme = globals().get("_neto_workspace_theme_refresh")
        if callable(_workspace_theme):
            _workspace_theme()
    except Exception:
        pass

    # Art arda gelen dil callback'lerini tek derin taramada birleştir.
    try:
        old_job = globals().get("_neto_language_refresh_job")
        if old_job:
            root.after_cancel(old_job)
        globals()["_neto_language_refresh_job"] = root.after(24, _arayuz_metnini_derin_yenile)
    except Exception:
        _arayuz_metnini_derin_yenile()


def now_playing_log(message):
    try:
        os.makedirs("logs", exist_ok=True)
        with open("logs/now_playing.log", "a", encoding="utf-8") as f:
            f.write(str(message) + "\n")
    except Exception:
        pass

def now_playing_last_media_path():
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        cache_dir = os.path.join(base_dir, "now_playing_cache")
        os.makedirs(cache_dir, exist_ok=True)
        return os.path.join(cache_dir, "last_media.json")
    except Exception:
        return os.path.join(os.getcwd(), "last_media.json")

def now_playing_placeholder_title(title):
    try:
        text = str(title or "").strip().lower()
        text = re.sub(r"\s+", " ", text)
        if not text:
            return True
        bad_exact = {
            "müzik bilgisi alınıyor...",
            "müzik algılanmadı",
            "şarkı aranıyor...",
            "detecting track...",
            "no track detected",
            "waiting for music",
            "şarkı algılanamadı",
            "şu an parça bilgisi yok.",
            "youtube music",
            "youtube",
            "music",
            "spotify",
            "ana sayfa",
            "home",
            "search",
            "arama",
            "şarkı veya sanatçı yaz",
            "sarki veya sanatci yaz",
            "en sevdiğiniz şarkılar ve albümleri dinleyin",
            "en sevdiginiz sarkilar ve albumleri dinleyin",
            "listen to your favorite songs and albums",
        }
        bad_fragments = (
            "sevdiğiniz şarkılar",
            "sevdiginiz sarkilar",
            "favorite songs",
            "music premium",
            "youtube music premium",
            "şarkı veya sanatçı",
            "sarki veya sanatci",
        )
        if text in bad_exact:
            return True
        return any(part in text for part in bad_fragments)
    except Exception:
        return True

def now_playing_media_info_valid_basic(info):
    try:
        if not isinstance(info, dict) or info.get("error"):
            return False
        title = str(info.get("title") or "").strip()
        return bool(title) and not now_playing_placeholder_title(title)
    except Exception:
        return False

def now_playing_save_last_media(info):
    try:
        if not now_playing_media_info_valid_basic(info):
            return False
        data = dict(info)
        data["saved_at"] = time.time()
        with open(now_playing_last_media_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as exc:
        try:
            now_playing_log(f"[LAST_MEDIA_SAVE_ERROR] {exc}")
        except Exception:
            pass
        return False

def now_playing_load_last_media():
    try:
        path = now_playing_last_media_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if now_playing_media_info_valid_basic(data):
                return data
            try:
                now_playing_log(f"[LAST_MEDIA_INVALID] path={path} data={data}")
            except Exception:
                pass
        else:
            try:
                now_playing_log(f"[LAST_MEDIA_MISSING] path={path}")
            except Exception:
                pass
    except Exception:
        try:
            now_playing_log(f"[LAST_MEDIA_LOAD_ERROR] path={now_playing_last_media_path()}")
        except Exception:
            pass

    try:
        import ast
        log_path = os.path.join("logs", "now_playing.log")
        if not os.path.exists(log_path):
            return {}
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()[-260:]
        for line in reversed(lines):
            if "[MANUAL_FOUND]" not in line:
                continue
            raw = line.split("[MANUAL_FOUND]", 1)[1].strip()
            data = ast.literal_eval(raw)
            if now_playing_media_info_valid_basic(data):
                now_playing_save_last_media(data)
                return data
    except Exception:
        pass
    return {}

# ------------------------------------------------------------
# NOW PLAYING GLOBAL SAFE HELPERS v10.18
# Must stay at module scope, before the main UI block.
# ------------------------------------------------------------
def now_playing_lang():
    try:
        lang = dil_getir()
        return "tr" if str(lang).lower().startswith("tr") else "en"
    except Exception:
        try:
            return "tr" if str(veri_yukle().get("dil", "en")).lower().startswith("tr") else "en"
        except Exception:
            return "en"

def now_playing_text(key) -> str:
    tr = {
        "none": "🎵 Şimdi Çalıyor: Yok",
        "label": "🎵 Şimdi Çalıyor",
        "screen": "ŞU AN ÇALIYOR",
        "settings": "🎵 Şimdi Çalıyor Ayarları",
        "settings_desc": "Şimdi Çalıyor ekranının açık kalma süresini ve otomatik açılma ayarını düzenle.",
        "artist_missing": "Sanatçı bilgisi yok",
        "source": "Kaynak",
        "album": "Albüm",
        "publisher": "Yayınlayan/Oluşturan",
        "countdown": "Kalan süre",
        "auto_close": "Otomatik kapanma",
        "close_hint": "Sağ üstteki ✕ ile çıkabilirsin.",
        "save": "Kaydet",
        "test": "Şimdi Çalıyor'u Test Aç",
        "close": "Kapat",
        "auto_fullscreen": "Şarkı değişince tam ekranı otomatik aç",
        "not_found": "Şu an çalan şarkı bulunamadı. Spotify/YouTube Music açık mı ve şarkı çalıyor mu kontrol et.",
        "detecting": "Şarkı aranıyor...",
        "no_track": "Şarkı algılanamadı",
        "first_prompt_title": "Müzik Algılandı",
        "first_prompt_message": "Müzik çalıyor. Şimdi Çalıyor tam ekran açılsın mı?",
        "yes": "Evet",
        "no": "Hayır",
        "prev": "Önceki",
        "play_pause": "Başlat/Durdur",
        "next": "Sonraki",
        "refresh": "Yenile",
        "open_button": "▶ Şimdi Çalıyor'u Aç",
        "open_button_short": "▶ Aç",
        "settings_short": "⚙ Ayarlar",
        "home_idle_title": "Müzik bekleniyor",
        "home_idle_status": "Algılama açık",
        "dynamic_island": "▰ Dinamik Ada",
        "dynamic_island_hint": "Üst merkezde ada olarak göster",
        "island_no_track": "Çalan yok",
        "monitor_active": "Otomatik algılama açık",
        "now_playing_settings": "Şimdi Çalıyor Ayarları",
        "kevra_k1_active": "NetOps Agent K1 aktif",
        "kevra_k2_active": "NetOps Agent K2 aktif",
        "k1_active": "K1 aktif",
        "k2_active": "K2 aktif",
        "status": "Durum",
        "status_playing": "Çalıyor",
        "status_paused": "Duraklatıldı",
        "status_stopped": "Durduruldu",
        "status_unknown": "Bilinmiyor",
        "visual_wave": "Dalga",
        "visual_vinyl": "Plak",
        "switch_to_vinyl": "🖼️ Albüm Kapağına Geç",
        "scratch_on": "Kapak Modu Açık",
        "scratch_off": "Kapak Modu Kapalı",
        "scratch_hint": "Plak üstünde fareyle sürükle: ileri sar / geri al / vıjı scratch sesi.",
        "switch_to_wave": "〰️ Dalgaya Geç",
        "search_song": "Şarkı ara",
        "search_placeholder": "Şarkı veya sanatçı yaz...",
        "search_play": "Çal",
        "search_hint": "Şarkıyı yaz, Çal: direkt link bulunur ve oynatma zorlanır.",
        "search_empty": "Önce şarkı adı yaz.",
        "searching_song": "Güvenli link bulunuyor...",
        "search_opened": "Açıldı: {query}",
        "search_error": "YouTube Music hatası",
        "search_playing": "Güvenli link açıldı: {query}",
    }
    en = {
        "none": "🎵 Now Playing: None",
        "label": "🎵 Now Playing",
        "screen": "NOW PLAYING",
        "settings": "🎵 Now Playing Settings",
        "settings_desc": "Set how long the Now Playing screen stays open and whether it opens automatically.",
        "artist_missing": "Artist unavailable",
        "source": "Source",
        "album": "Album",
        "publisher": "Publisher/Creator",
        "countdown": "Time left",
        "auto_close": "Auto close",
        "close_hint": "Use ✕ in the top-right to exit.",
        "save": "Save",
        "test": "Open Now Playing Test",
        "close": "Close",
        "auto_fullscreen": "Auto-open fullscreen when track changes",
        "not_found": "No current track was found. Check if Spotify/YouTube Music is open and playing.",
        "detecting": "Detecting track...",
        "no_track": "No track detected",
        "first_prompt_title": "Music Detected",
        "first_prompt_message": "Music is playing. Open Now Playing fullscreen?",
        "yes": "Yes",
        "no": "No",
        "prev": "Previous",
        "play_pause": "Play/Pause",
        "next": "Next",
        "refresh": "Refresh",
        "open_button": "▶ Open Now Playing",
        "open_button_short": "▶ Open",
        "settings_short": "⚙ Settings",
        "home_idle_title": "Waiting for music",
        "home_idle_status": "Detection active",
        "dynamic_island": "▰ Dynamic Island",
        "dynamic_island_hint": "Show as a top-center island",
        "island_no_track": "Nothing playing",
        "monitor_active": "Automatic detection active",
        "now_playing_settings": "Now Playing Settings",
        "kevra_k1_active": "NetOps Agent K1 active",
        "kevra_k2_active": "NetOps Agent K2 active",
        "k1_active": "K1 active",
        "k2_active": "K2 active",
        "status": "Status",
        "status_playing": "Playing",
        "status_paused": "Paused",
        "status_stopped": "Stopped",
        "status_unknown": "Unknown",
        "visual_wave": "Wave",
        "visual_vinyl": "Vinyl",
        "switch_to_vinyl": "🖼️ Switch to Album Cover",
        "scratch_on": "Cover Mode On",
        "scratch_off": "Cover Mode Off",
        "scratch_hint": "Drag the vinyl with your mouse: seek forward/backward and scratch sound.",
        "switch_to_wave": "〰️ Switch to Wave",
        "search_song": "Search song",
        "search_placeholder": "Type song or artist...",
        "search_play": "Play",
        "search_hint": "Type a song, Play: direct YouTube Music link opens.",
        "search_empty": "Type a song first.",
        "searching_song": "Finding safe link...",
        "search_opened": "Opened: {query}",
        "search_error": "YouTube Music error",
        "search_playing": "Safe link opened: {query}",
    }
    return str((tr if now_playing_lang() == "tr" else en).get(key, key))


def now_playing_ui_palette():
    """Şimdi Çalıyor için anlık tema ve vurgu renklerini döndürür."""
    try:
        return {
            "bg": aktif_palet.get("bg", "#09090B"),
            "card": aktif_palet.get("card", "#1B1B20"),
            "entry": aktif_palet.get("entry_bg", "#141418"),
            "border": aktif_palet.get("entry_border", "#34343C"),
            "text": aktif_palet.get("text_main", "#F4F4F5"),
            "dim": aktif_palet.get("text_dim", "#A1A1AA"),
            "accent": aktif_palet.get("neon", "#22C55E"),
            "accent_hover": aktif_palet.get("accent_hover", aktif_palet.get("button_hover", "#2A2A31")),
            "accent_text": aktif_palet.get("accent_text", _tema_vurgu_metin_rengi()),
            "hover": aktif_palet.get("button_hover", "#2A2A31"),
        }
    except Exception:
        return {
            "bg": "#09090B", "card": "#1B1B20", "entry": "#141418",
            "border": "#34343C", "text": "#F4F4F5", "dim": "#A1A1AA",
            "accent": "#22C55E", "accent_hover": "#34D399",
            "accent_text": "#111114", "hover": "#2A2A31",
        }


def now_playing_widget_kaydet(ad, widget, rol="secondary"):
    try:
        now_playing_theme_widgets[ad] = (widget, rol)
    except Exception:
        pass
    return widget


def now_playing_theme_apply():
    """Açık Şimdi Çalıyor ekranını kapatmadan seçili tema/vurguya bağlar."""
    try:
        pal = now_playing_ui_palette()
        overlay_alive = globals().get("now_playing_overlay_alive")
        if callable(overlay_alive) and overlay_alive():
            try:
                now_playing_overlay.configure(fg_color=pal["bg"])
            except Exception:
                pass

        stale = []
        for ad, kayit in list(now_playing_theme_widgets.items()):
            try:
                widget, rol = kayit
                widget_alive = globals().get("now_playing_widget_alive")
                if callable(widget_alive) and not widget_alive(widget):
                    stale.append(ad)
                    continue
                if rol == "primary":
                    widget.configure(fg_color=pal["accent"], hover_color=pal["accent_hover"], text_color=pal["accent_text"])
                elif rol == "secondary":
                    widget.configure(fg_color=pal["card"], hover_color=pal["hover"], text_color=pal["text"])
                elif rol == "entry":
                    widget.configure(fg_color=pal["entry"], border_color=pal["border"], text_color=pal["text"])
                elif rol == "title":
                    widget.configure(text_color=pal["text"])
                elif rol == "dim":
                    widget.configure(text_color=pal["dim"])
                elif rol == "accent_text":
                    widget.configure(text_color=pal["accent"])
                elif rol == "slider":
                    widget.configure(progress_color=pal["accent"], button_color=pal["accent"], button_hover_color=pal["accent_hover"], fg_color=pal["border"])
                elif rol == "accent_frame":
                    widget.configure(fg_color=pal["card"], border_color=pal["accent"], border_width=2)
            except Exception:
                pass
        for ad in stale:
            now_playing_theme_widgets.pop(ad, None)

        widget_alive = globals().get("now_playing_widget_alive")
        for canvas in (globals().get("now_playing_visual_canvas"), globals().get("now_playing_vinyl_canvas")):
            try:
                if canvas and (not callable(widget_alive) or widget_alive(canvas)):
                    canvas.configure(bg=pal["bg"])
            except Exception:
                pass
        render = globals().get("now_playing_render_visual")
        if callable(render):
            try:
                render()
            except Exception:
                pass
        island_update = globals().get("now_playing_dynamic_island_update")
        island_alive = globals().get("now_playing_dynamic_island_alive")
        if callable(island_update) and callable(island_alive) and island_alive():
            island_update(globals().get("now_playing_current_info") or globals().get("now_playing_monitor_last_info"))
    except Exception as exc:
        try:
            now_playing_log(f"[THEME_APPLY_ERROR] {exc}")
        except Exception:
            pass


def now_playing_auto_fullscreen_enabled():
    try:
        return bool(veri_yukle().get("now_playing_auto_fullscreen", False))
    except Exception:
        return False

def now_playing_set_auto_fullscreen(value):
    try:
        h = veri_yukle()
        h["now_playing_auto_fullscreen"] = bool(value)
        veri_kaydet(h)
        return True
    except Exception:
        return False

def now_playing_idle_seconds():
    try:
        value = int(veri_yukle().get("now_playing_idle_seconds", 300))
        return max(0, min(7200, value))
    except Exception:
        return 300

def now_playing_set_idle_seconds(value):
    try:
        h = veri_yukle()
        h["now_playing_idle_seconds"] = max(0, min(7200, int(value)))
        veri_kaydet(h)
        return True
    except Exception:
        return False


# ------------------------------------------------------------
# STARTUP LOGO FIX
# ------------------------------------------------------------
def neto_safe_startup_logo_path():
    try:
        for p in [get_asset_path("NetoAsistan.png"), LOGO_PATH, GIF_PATH, ICO_PATH, get_asset_path("Logo.png"), get_asset_path("yukleme.gif"), get_asset_path("Neto.gif"), get_asset_path("kevra.png"), get_asset_path("kevr.png")]:
            try:
                if p and os.path.exists(p):
                    return p
            except Exception:
                pass
    except Exception:
        pass
    return ""


_NETO_AUTOMATION_WINDOW = None
_NETO_AUTOMATION_PAGE = None
_NETO_SCENE_PAGE = None


def _neto_automation_button_refresh(active=None):
    """Keep the sidebar automation button in sync with its window state."""
    try:
        button = globals().get("btn_automation")
        palette = globals().get("aktif_palet")
        if button is None or palette is None or not button.winfo_exists():
            return
        if active is None:
            page = globals().get("_NETO_AUTOMATION_PAGE")
            active = bool(page is not None and page.winfo_exists())
        button.configure(
            fg_color=palette["neon"] if active else palette["card"],
            hover_color=(
                palette.get("accent_hover", palette["button_hover"])
                if active else palette["button_hover"]
            ),
            text_color=(
                _tema_vurgu_metin_rengi() if active else palette["text_main"]
            ),
        )
    except Exception:
        pass


def _neto_scene_button_refresh(active=None):
    try:
        button = globals().get("btn_scenes")
        palette = globals().get("aktif_palet")
        if button is None or palette is None or not button.winfo_exists():
            return
        if active is None:
            page = globals().get("_NETO_SCENE_PAGE")
            active = bool(page is not None and page.winfo_exists())
        button.configure(
            fg_color=palette["neon"] if active else palette["card"],
            hover_color=(palette.get("accent_hover", palette["button_hover"]) if active else palette["button_hover"]),
            text_color=(_tema_vurgu_metin_rengi() if active else palette["text_main"]),
        )
    except Exception:
        pass


def neto_otomasyon_merkezi_ac():
    """Otomasyon merkezini ana pencere içinde tek çalışma alanı olarak açar."""
    global _NETO_AUTOMATION_WINDOW, _NETO_AUTOMATION_PAGE

    try:
        scene_page = globals().get("_NETO_SCENE_PAGE")
        if scene_page is not None and scene_page.winfo_exists():
            scene_controller = getattr(scene_page, "_neto_scene_controller", None)
            if scene_controller is not None:
                scene_controller.cleanup()
            scene_page.destroy()
            globals()["_NETO_SCENE_PAGE"] = None
            _neto_scene_button_refresh(False)
    except Exception:
        pass

    try:
        if _NETO_AUTOMATION_PAGE is not None and _NETO_AUTOMATION_PAGE.winfo_exists():
            existing_window = _NETO_AUTOMATION_WINDOW or _NETO_AUTOMATION_PAGE
            existing_window.lift()
            _neto_automation_button_refresh(True)
            return _NETO_AUTOMATION_PAGE
    except Exception:
        _NETO_AUTOMATION_PAGE = None

    try:
        parent = globals().get("root")
        content = globals().get("main_c")
        if parent is None or not parent.winfo_exists() or content is None or not content.winfo_exists():
            raise RuntimeError("Ana NetOps penceresi hazır değil.")

        automation_ui = _neto_lazy_import("neto_automation_ui")
        chat = globals().get("chat_container")
        input_bar = globals().get("input_container")
        live = globals().get("live_panel")
        page = None
        automation_host = None
        embedded = True

        try:
            from neto_window_manager import display_index_for, monitors
            assignments = veri_yukle().get("neto_window_assignments")
            automation_display = display_index_for(assignments, "automation")
            assistant_display = display_index_for(assignments, "assistant")
            embedded = not (
                automation_display is not None
                and automation_display != assistant_display
                and len(monitors(parent)) > automation_display
            )
        except Exception:
            embedded = True

        def _hide_widget(widget):
            if widget is None or not widget.winfo_exists():
                return
            manager = widget.winfo_manager()
            if manager == "pack":
                widget.pack_forget()
            elif manager == "place":
                widget.place_forget()
            elif manager == "grid":
                widget.grid_remove()

        if embedded:
            _hide_widget(live)
            _hide_widget(chat)
            _hide_widget(input_bar)
            page_parent = content
        else:
            automation_host = tk.Toplevel(parent)
            automation_host.title("NetOps · Otomasyon Merkezi")
            automation_host.configure(bg=aktif_palet["bg"])
            automation_host.protocol("WM_DELETE_WINDOW", lambda: close_automation_page())
            page_parent = automation_host

        page = ctk.CTkFrame(page_parent, fg_color=aktif_palet["bg"], corner_radius=0)
        _NETO_AUTOMATION_PAGE = page
        _NETO_AUTOMATION_WINDOW = automation_host
        page.pack(fill="both", expand=True)
        if automation_host is not None:
            try:
                from neto_window_manager import display_index_for, place_window
                target = display_index_for(veri_yukle().get("neto_window_assignments"), "automation")
                place_window(automation_host, target, parent)
            except Exception:
                pass

        def close_automation_page():
            global _NETO_AUTOMATION_PAGE, _NETO_AUTOMATION_WINDOW
            try:
                frame = getattr(page, "_neto_automation_panel", None)
                controller = getattr(frame, "_neto_automation_controller", None)
                if controller is not None:
                    controller.cleanup()
            except Exception:
                pass
            try:
                page.destroy()
            except Exception:
                pass
            _NETO_AUTOMATION_PAGE = None
            _NETO_AUTOMATION_WINDOW = None
            _neto_automation_button_refresh(False)
            try:
                if embedded and chat is not None and chat.winfo_exists():
                    chat.pack(side="top", expand=True, fill="both", padx=24, pady=(12, 6))
                restore_input = globals().get("_neto_input_bar_konumla")
                if callable(restore_input):
                    restore_input()
                restore_layout = globals().get("mini_ekran_uygula")
                if callable(restore_layout):
                    parent.after_idle(restore_layout)
            except Exception:
                pass
            try:
                if automation_host is not None and automation_host.winfo_exists():
                    automation_host.destroy()
            except Exception:
                pass

        automation_ui.create_automation_panel(
            page,
            root=parent,
            palette_getter=lambda: aktif_palet,
            close_command=close_automation_page,
        )
        _neto_automation_button_refresh(True)
        page.lift()
        return page
    except Exception as exc:
        try:
            if page is not None and page.winfo_exists():
                page.destroy()
            if chat is not None and chat.winfo_exists():
                chat.pack(side="top", expand=True, fill="both", padx=24, pady=(12, 6))
            restore_input = globals().get("_neto_input_bar_konumla")
            if callable(restore_input):
                restore_input()
        except Exception:
            pass
        _NETO_AUTOMATION_PAGE = None
        _NETO_AUTOMATION_WINDOW = None
        _neto_automation_button_refresh(False)
        try:
            print(f"[AUTOMATION_UI_ERROR] {exc}", flush=True)
        except Exception:
            pass
        try:
            messagebox.showerror(
                "Otomasyon Merkezi",
                f"Otomasyon merkezi açılamadı:\n{exc}",
                parent=globals().get("root"),
            )
        except Exception:
            pass
        return None


def _neto_scene_adapters():
    """Bridge scene actions to the already loaded NetOps desktop services."""
    from neto_scene_engine import SceneAdapters, default_adapters

    base = default_adapters()

    def _brightness_get():
        try:
            import screen_brightness_control as sbc

            values = sbc.get_brightness()
            return int(values[0]) if values else None
        except Exception:
            return None

    def _brightness_set(value):
        try:
            import screen_brightness_control as sbc

            sbc.set_brightness(int(value))
            return True
        except Exception:
            return False

    def _volume_get():
        try:
            return volume_get_percent()
        except Exception:
            return None

    def _volume_set(value):
        try:
            return bool(volume_set_percent(value, announce=False))
        except Exception:
            return False

    def _mute_get():
        try:
            return volume_get_mute()
        except Exception:
            return None

    def _mute_set(value):
        try:
            return bool(volume_set_mute(value, announce=False))
        except Exception:
            return False

    return SceneAdapters(
        get_profile=lambda: _neto_profile_active(),
        set_profile=lambda profile: _neto_apply_user_profile(profile),
        get_volume=_volume_get,
        set_volume=_volume_set,
        get_muted=_mute_get,
        set_muted=_mute_set,
        get_brightness=_brightness_get,
        set_brightness=_brightness_set,
        launch_program=base.launch_program,
        close_program=base.close_program,
        stop_started_processes=base.stop_started_processes,
        run_automation=base.run_automation,
    )


def neto_sahneler_merkezi_ac():
    """Open Neto Hazırla as an in-app page, never as a second main window."""
    global _NETO_SCENE_PAGE
    try:
        automation_page = globals().get("_NETO_AUTOMATION_PAGE")
        if automation_page is not None and automation_page.winfo_exists():
            automation_controller = getattr(automation_page, "_neto_automation_panel", None)
            automation_controller = getattr(automation_controller, "_neto_automation_controller", None)
            if automation_controller is not None:
                automation_controller.cleanup()
            automation_page.destroy()
            globals()["_NETO_AUTOMATION_PAGE"] = None
            _neto_automation_button_refresh(False)
    except Exception:
        pass
    try:
        if _NETO_SCENE_PAGE is not None and _NETO_SCENE_PAGE.winfo_exists():
            _NETO_SCENE_PAGE.lift()
            return _NETO_SCENE_PAGE
    except Exception:
        _NETO_SCENE_PAGE = None

    parent = globals().get("root")
    content = globals().get("main_c")
    if parent is None or content is None or not content.winfo_exists():
        return None
    scene_ui = _neto_lazy_import("neto_scene_ui")
    chat = globals().get("chat_container")
    input_bar = globals().get("input_container")
    live = globals().get("live_panel")
    page = ctk.CTkFrame(content, fg_color=aktif_palet["bg"], corner_radius=0)
    _NETO_SCENE_PAGE = page

    def hide(widget):
        if widget is None or not widget.winfo_exists():
            return
        manager = widget.winfo_manager()
        if manager == "pack":
            widget.pack_forget()
        elif manager == "place":
            widget.place_forget()
        elif manager == "grid":
            widget.grid_remove()

    def close_page():
        global _NETO_SCENE_PAGE
        try:
            controller = getattr(page, "_neto_scene_controller", None)
            if controller is not None:
                controller.cleanup()
        except Exception:
            pass
        try:
            page.destroy()
        except Exception:
            pass
        _NETO_SCENE_PAGE = None
        _neto_scene_button_refresh(False)
        try:
            if chat is not None and chat.winfo_exists():
                chat.pack(side="top", expand=True, fill="both", padx=24, pady=(12, 6))
            restore_input = globals().get("_neto_input_bar_konumla")
            if callable(restore_input):
                restore_input()
            restore_layout = globals().get("mini_ekran_uygula")
            if callable(restore_layout):
                parent.after_idle(restore_layout)
        except Exception:
            pass

    try:
        hide(chat)
        hide(input_bar)
        hide(live)
        page.pack(fill="both", expand=True)
        scene_ui.create_scene_panel(
            page,
            root=parent,
            palette_getter=lambda: aktif_palet,
            close_command=close_page,
            adapters_getter=_neto_scene_adapters,
        )
        _neto_scene_button_refresh(True)
        page.lift()
        return page
    except Exception as exc:
        try:
            page.destroy()
        except Exception:
            pass
        _NETO_SCENE_PAGE = None
        _neto_scene_button_refresh(False)
        try:
            if chat is not None and chat.winfo_exists():
                chat.pack(side="top", expand=True, fill="both", padx=24, pady=(12, 6))
                restore_input = globals().get("_neto_input_bar_konumla")
                if callable(restore_input):
                    restore_input()
            messagebox.showerror("Neto Hazırla", f"Sahne alanı açılamadı:\n{exc}", parent=parent)
        except Exception:
            pass
        return None
# ------------------------------------------------------------
# ANA ARAYÜZ
# ------------------------------------------------------------
if __name__ == '__main__':
    multiprocessing.freeze_support()

    # PyInstaller EXE worker mode: run the scheduler without opening the GUI.
    if "--netops-automation-worker" in sys.argv:
        sys.argv = [arg for arg in sys.argv if arg != "--netops-automation-worker"]
        from neto_automation_worker import main as _netops_worker_main
        raise SystemExit(_netops_worker_main())

    # ------------------------------------------------------------
    # NOW PLAYING v10.9 - Şu An Çalıyor
    # ------------------------------------------------------------
    def now_playing_get_max_seconds():
        try:
            return int(veri_yukle().get("now_playing_max_seconds", 1800))
        except Exception:
            return 1800

    def now_playing_set_max_seconds(seconds):
        try:
            seconds = max(10, min(7200, int(seconds)))
            h = veri_yukle()
            h["now_playing_max_seconds"] = seconds
            veri_kaydet(h)
            return seconds
        except Exception:
            return None

    def now_playing_ayar_komutu(metin):
        try:
            k = str(metin or "").lower()
            if not any(x in k for x in ["çalıyor", "sarki", "şarkı", "muzik", "müzik"]):
                return None
            if not any(x in k for x in ["süre", "sure", "saniye", "dakika", "dk"]):
                return None
            sayilar = re.findall(r"\d+", k)
            if not sayilar:
                return "Süre için sayı söylemelisin. Örnek: Şu an çalıyor süresi 30 dakika."
            n = int(sayilar[0])
            saniye = n * 60 if ("dakika" in k or "dk" in k) else n
            sonuc = now_playing_set_max_seconds(saniye)
            if sonuc:
                return f"Şu An Çalıyor ekran süresi {sonuc // 60} dakika yapıldı." if sonuc >= 60 else f"Şu An Çalıyor ekran süresi {sonuc} saniye yapıldı."
            return "Şu An Çalıyor süresi ayarlanamadı."
        except Exception as e:
            return f"Şu An Çalıyor ayar hatası: {e}"

    def now_playing_sidebar_guncelle(info):
        """Updates the sidebar Now Playing status."""
        try:
            globals()["now_playing_last_info"] = dict(info) if isinstance(info, dict) else info
            lbl = globals().get("lbl_now_playing")
            detay_lbl = globals().get("lbl_now_playing_detay")
            home_lbl = globals().get("home_now_playing_title")
            home_detay = globals().get("home_now_playing_detail")
            home_status = globals().get("home_now_playing_status")
            sidebar_compact = bool(sidebar_state.get("compact", False))

            def _safe_set(widget, text):
                try:
                    if widget:
                        widget.configure(text=text)
                except Exception:
                    pass

            if not lbl:
                return

            if not info or info.get("error") or not info.get("title"):
                none_text = now_playing_text("none")
                _safe_set(lbl, "♪" if sidebar_compact else f"♪ {now_playing_text('home_idle_title')}")
                _safe_set(detay_lbl, "")
                _safe_set(home_lbl, now_playing_text("home_idle_title"))
                _safe_set(home_detay, "")
                _safe_set(home_status, now_playing_text("home_idle_status"))
                island_update = globals().get("now_playing_dynamic_island_update")
                island_alive = globals().get("now_playing_dynamic_island_alive")
                if callable(island_update) and callable(island_alive) and island_alive():
                    island_update(None)
                return

            title = str(info.get("title", "")).strip()
            artist = str(info.get("artist", "")).strip()
            app = str(info.get("app", "Unknown app")).strip()
            source = str(info.get("source", "")).strip()
            album = str(info.get("album", "")).strip()
            publisher = str(info.get("publisher", "")).strip()

            sidebar_title = "♪" if sidebar_compact else f"♪ {title}"
            _safe_set(lbl, sidebar_title)

            if artist:
                detay = f"{artist} • {app}"
            else:
                detay = f"{now_playing_text('source')}: {app}"

            if album:
                detay += f" • {now_playing_text('album')}: {album}"
            if publisher and publisher not in detay:
                detay += f" • {now_playing_text('publisher')}: {publisher}"

            if source == "media_session":
                detay += " • Media Session"
            elif source == "window_title":
                detay += " • Window title"

            _safe_set(detay_lbl, "" if sidebar_compact else detay)
            _safe_set(home_lbl, title)
            _safe_set(home_detay, detay)

            home_status_text = f"{now_playing_text('source')}: {app}"
            if source == "media_session":
                home_status_text += " • Media Session"
            elif source == "window_title":
                home_status_text += " • Window title"
            _safe_set(home_status, home_status_text)
            island_update = globals().get("now_playing_dynamic_island_update")
            island_alive = globals().get("now_playing_dynamic_island_alive")
            if callable(island_update) and callable(island_alive) and island_alive():
                island_update(info)

        except Exception as e:
            try:
                print(f"[NOW_PLAYING] sidebar error: {e}", flush=True)
            except Exception:
                pass

    def now_playing_open_settings_safe():
        try:
            now_playing_ayar_penceresi_ac()
        except Exception as e:
            now_playing_log(f"[SETTINGS_ERROR] {e}")
            try:
                messagebox.showerror("Now Playing", f"Settings error:\n{e}")
            except Exception:
                pass


    def now_playing_ayar_penceresi_ac():
        try:
            pencere = ctk.CTkToplevel(root)
            pencere.title(now_playing_text("settings"))
            pencere.geometry("560x640")
            pencere.configure(fg_color=aktif_palet["bg"])
            pencere.transient(root)
            try:
                pencere.lift()
            except Exception:
                pass
            try:
                pencere.attributes("-topmost", True)
            except Exception:
                pass
            try:
                pencere.grab_set()
            except Exception:
                pass

            ctk.CTkLabel(
                pencere,
                text=now_playing_text("settings"),
                text_color=aktif_palet["text_main"],
                font=("Segoe UI Semibold", 20)
            ).pack(pady=(22, 8))

            ctk.CTkLabel(
                pencere,
                text=now_playing_text("settings_desc"),
                text_color=aktif_palet["text_dim"],
                font=("Segoe UI", 12),
                wraplength=370
            ).pack(pady=(0, 14))

            mevcut = now_playing_get_max_seconds()
            secenekler = {
                "10 seconds / 10 saniye": 10,
                "30 seconds / 30 saniye": 30,
                "1 minute / 1 dakika": 60,
                "5 minutes / 5 dakika": 300,
                "10 minutes / 10 dakika": 600,
                "30 minutes / 30 dakika": 1800,
                "2 hours / 2 saat": 7200,
            }

            def label_for_value(v):
                for k, val in secenekler.items():
                    if val == v:
                        return k
                return "30 minutes / 30 dakika"

            secim = ctk.StringVar(value=label_for_value(mevcut))
            ctk.CTkOptionMenu(
                pencere,
                values=list(secenekler.keys()),
                variable=secim,
                width=270,
                height=38,
                fg_color=aktif_palet["card"],
                button_color=aktif_palet["neon"],
                button_hover_color=aktif_palet.get("accent_hover", aktif_palet["button_hover"]),
                text_color=aktif_palet["text_main"]
            ).pack(pady=8)

            ctk.CTkLabel(
                pencere,
                text="Bekleme ekranı (saat, tarih ve şarkı)",
                text_color=aktif_palet["text_main"],
                font=("Segoe UI Semibold", 12),
            ).pack(pady=(10, 2))
            idle_seconds = now_playing_idle_seconds()
            idle_options = {
                "Kapalı": 0,
                "30 saniye": 30,
                "1 dakika": 60,
                "5 dakika": 300,
                "10 dakika": 600,
                "30 dakika": 1800,
                "2 saat": 7200,
            }
            idle_label = next((label for label, value in idle_options.items() if value == idle_seconds), "5 dakika")
            idle_var = ctk.StringVar(value=idle_label)
            ctk.CTkOptionMenu(
                pencere,
                values=list(idle_options.keys()),
                variable=idle_var,
                width=270,
                height=38,
                fg_color=aktif_palet["card"],
                button_color=aktif_palet["neon"],
                button_hover_color=aktif_palet.get("accent_hover", aktif_palet["button_hover"]),
                text_color=aktif_palet["text_main"],
            ).pack(pady=(2, 8))

            auto_var = ctk.BooleanVar(value=now_playing_auto_fullscreen_enabled())
            ctk.CTkCheckBox(
                pencere,
                text=now_playing_text("auto_fullscreen"),
                variable=auto_var,
                text_color=aktif_palet["text_main"],
                fg_color=aktif_palet["neon"],
                hover_color=aktif_palet["button_hover"]
            ).pack(pady=(8, 10))

            durum = ctk.CTkLabel(
                pencere,
                text=f"Current / Mevcut: {mevcut // 60} min" if mevcut >= 60 else f"Current / Mevcut: {mevcut} sec",
                text_color=aktif_palet["text_dim"],
                font=("Segoe UI", 12)
            )
            durum.pack(pady=(4, 16))

            def kaydet():
                val = secenekler.get(secim.get(), 1800)
                sonuc = now_playing_set_max_seconds(val)
                now_playing_set_idle_seconds(idle_options.get(idle_var.get(), 300))
                now_playing_set_auto_fullscreen(auto_var.get())
                if sonuc:
                    durum.configure(text=f"Saved / Kaydedildi: {sonuc // 60} min" if sonuc >= 60 else f"Saved / Kaydedildi: {sonuc} sec")
                else:
                    durum.configure(text="Could not save / Kaydedilemedi")

            ctk.CTkButton(
                pencere,
                text=now_playing_text("save"),
                height=38,
                corner_radius=12,
                fg_color=aktif_palet["neon"],
                text_color=_tema_vurgu_metin_rengi(),
                hover_color=aktif_palet.get("accent_hover", aktif_palet["button_hover"]),
                command=kaydet
            ).pack(pady=6)

            ctk.CTkButton(
                pencere,
                text=now_playing_text("test"),
                height=38,
                corner_radius=12,
                fg_color=aktif_palet["card"],
                hover_color=aktif_palet["button_hover"],
                text_color=aktif_palet["text_main"],
                command=lambda: now_playing_manual_open(force=True)
            ).pack(pady=6)

            def bekleme_ekrani_test():
                try:
                    try:
                        pencere.grab_release()
                    except Exception:
                        pass
                    try:
                        pencere.destroy()
                    except Exception:
                        pass
                    if not now_playing_overlay_alive():
                        now_playing_manual_open(force=True)
                        root.after(700, now_playing_idle_enter)
                    else:
                        now_playing_idle_enter()
                except Exception:
                    pass

            ctk.CTkButton(
                pencere,
                text="Bekleme ekranını test et",
                height=38,
                corner_radius=12,
                fg_color=aktif_palet["card"],
                hover_color=aktif_palet["button_hover"],
                text_color=aktif_palet["text_main"],
                command=bekleme_ekrani_test
            ).pack(pady=6)

            ctk.CTkButton(
                pencere,
                text=now_playing_text("close"),
                height=34,
                corner_radius=12,
                fg_color=aktif_palet["card"],
                hover_color=aktif_palet["button_hover"],
                text_color=aktif_palet["text_main"],
                command=pencere.destroy
            ).pack(pady=(18, 0))

        except Exception as e:
            try:
                messagebox.showerror("Now Playing", f"Settings could not be opened:\n{e}")
            except Exception:
                pass

    def now_playing_countdown_loop():
        global now_playing_countdown_job
        try:
            if not now_playing_overlay_alive():
                return
            kalan = int(max(0, now_playing_end_time - time.time()))
            dk = kalan // 60
            sn = kalan % 60
            lbl = globals().get("now_playing_countdown_label")
            if lbl:
                lbl.configure(text=f"{now_playing_text('countdown')}: {dk:02d}:{sn:02d}")
            if kalan <= 0:
                now_playing_overlay_kapat()
                return
            now_playing_countdown_job = root.after(1000, now_playing_countdown_loop)
        except Exception:
            pass

    def now_playing_manual_open(force=True):
        """Click handler: always responds. If no track is detected, opens a diagnostic Now Playing screen."""
        try:
            info = None
            last_error = None

            # v10.32 fixed: hızlı ilk yakalama.
            # Açılır açılmaz şarkıyı görmek için daha fazla ama kısa aralıklı deneme yap.
            for _ in range(12):
                info = neto_now_playing.get_current_media(force_fresh=True)
                if info and info.get("error"):
                    last_error = info.get("error")
                    now_playing_log(f"[MANUAL_ERROR] {last_error}")
                if info and not info.get("error") and info.get("title"):
                    break
                time.sleep(0.12)

            if info and not info.get("error") and info.get("title"):
                now_playing_log(f"[MANUAL_FOUND] {info}")
                now_playing_save_last_media(info)
                now_playing_sidebar_guncelle(info)
                now_playing_overlay_goster(info, force=True)
                return

            # Kullanıcı basınca hiçbir şey olmamış gibi görünmesin:
            # teşhis ekranı aç.
            fallback_info = {
                "title": now_playing_text("detecting"),
                "artist": now_playing_text("not_found"),
                "album": "",
                "publisher": "NetOps",
                "app": "Windows Media Session",
                "source": "diagnostic",
                "backend": "manual_click",
            }
            if last_error:
                fallback_info["album"] = f"Error: {last_error}"

            now_playing_sidebar_guncelle(None)
            now_playing_overlay_goster(fallback_info, force=True)
            now_playing_log(f"[MANUAL_NOT_FOUND] last_error={last_error}")

        except Exception as e:
            now_playing_log(f"[MANUAL_EXCEPTION] {e}")
            try:
                fallback_info = {
                    "title": "Now Playing Error" if now_playing_lang() != "tr" else "Şimdi Çalıyor Hatası",
                    "artist": str(e),
                    "album": "",
                    "publisher": "NetOps",
                    "app": "NetOps",
                    "source": "error",
                }
                now_playing_overlay_goster(fallback_info, force=True)
            except Exception:
                try:
                    animasyonlu_yazi(f"Now Playing error: {e}")
                except Exception:
                    print(e, flush=True)


    def now_playing_widget_alive(widget):
        try:
            return bool(widget) and bool(widget.winfo_exists())
        except Exception:
            return False

    def now_playing_overlay_alive():
        try:
            return bool(now_playing_overlay) and bool(now_playing_overlay.winfo_exists())
        except Exception:
            return False

    def now_playing_first_launch_check():
        """STARTUP FIX: disabled. Automatic media scan froze the UI at launch.
        User can click Start Now Playing manually after the window opens.
        """
        return

    def now_playing_quick_detect_loop(attempt=0, max_attempts=45):
        """Fast scan after overlay opens. Safe against closed/destroyed windows."""
        global now_playing_current_key
        try:
            if attempt >= max_attempts:
                return
            if not now_playing_overlay_alive():
                return

            info = neto_now_playing.get_current_media(force_fresh=True)
            if info and not info.get("error") and info.get("title"):
                now_playing_save_last_media(info)
                key = now_playing_info_key(info)
                now_playing_sidebar_guncelle(info)

                if key and key != now_playing_current_key:
                    now_playing_current_key = key
                    try:
                        if now_playing_widget_alive(now_playing_title_label):
                            now_playing_title_label.configure(text=info.get("title", ""))
                    except Exception:
                        pass
                    try:
                        artist = info.get("artist") or now_playing_text("artist_missing")
                        if now_playing_widget_alive(now_playing_artist_label):
                            now_playing_artist_label.configure(text=artist)
                    except Exception:
                        pass
                    try:
                        app = info.get("app") or info.get("source") or ""
                        if now_playing_widget_alive(now_playing_source_label):
                            now_playing_source_label.configure(text=f"{now_playing_text('source')}: {app}")
                    except Exception:
                        pass
                    now_playing_log(f"[QUICK_UPDATE] {info}")

            try:
                root.after(180, lambda: now_playing_quick_detect_loop(attempt + 1, max_attempts))
            except Exception:
                pass
        except Exception as e:
            try:
                now_playing_log(f"[QUICK_DETECT_ERROR] {e}")
            except Exception:
                pass


    def now_playing_live_update_loop():
        """Continuously update Now Playing overlay while it is open."""
        global now_playing_current_key
        try:
            if not now_playing_overlay_alive():
                return

            info = neto_now_playing.get_current_media(force_fresh=True)
            if info and not info.get("error") and info.get("title"):
                now_playing_save_last_media(info)
                key = now_playing_info_key(info)
                now_playing_sidebar_guncelle(info)

                # Always refresh visible labels, even if key looks same.
                try:
                    if now_playing_widget_alive(now_playing_title_label):
                        now_playing_title_label.configure(text=info.get("title", ""))
                except Exception:
                    pass
                try:
                    artist = info.get("artist") or now_playing_text("artist_missing")
                    if now_playing_widget_alive(now_playing_artist_label):
                        now_playing_artist_label.configure(text=artist)
                except Exception:
                    pass
                try:
                    app = info.get("app") or info.get("source") or ""
                    if now_playing_widget_alive(now_playing_source_label):
                        now_playing_source_label.configure(text=f"{now_playing_text('source')}: {app}")
                except Exception:
                    pass
                try:
                    if now_playing_widget_alive(now_playing_status_label):
                        now_playing_status_label.configure(text=f"{now_playing_text('status')}: {now_playing_status_text_from_info(info)}")
                except Exception:
                    pass

                if key:
                    now_playing_current_key = key

            try:
                root.after(350, now_playing_live_update_loop)
            except Exception:
                pass
        except Exception as e:
            try:
                now_playing_log(f"[LIVE_UPDATE_ERROR] {e}")
            except Exception:
                pass


    def now_playing_idle_artist_name(info):
        try:
            artist = str((info or {}).get("artist") or "").strip()
            if not artist or artist.lower() == now_playing_text("artist_missing").lower():
                return ""
            return artist
        except Exception:
            return ""

    def now_playing_idle_song_text(info):
        try:
            title = str((info or {}).get("title") or "").strip()
            artist = now_playing_idle_artist_name(info)
            if not title:
                return "Müzik algılanmadı"
            return f"{artist} - {title}" if artist else title
        except Exception:
            return "Müzik algılanmadı"

    def now_playing_idle_meta_text(info):
        try:
            artist = now_playing_idle_artist_name(info)
            app = str((info or {}).get("app") or (info or {}).get("source") or "").strip()
            parts = []
            if artist:
                parts.append(f"Sanatçı: {artist}")
            if app:
                parts.append(f"Kaynak: {app}")
            return "  •  ".join(parts)
        except Exception:
            return ""

    def now_playing_idle_header_compact(info):
        try:
            status_text = now_playing_status_text_from_info(info)
            app = str((info or {}).get("app") or (info or {}).get("source") or "").strip()
            if now_playing_idle_info_valid(info):
                source_part = f"\nKaynak: {app}" if app else ""
                return f"ŞU AN ÇALIYOR{source_part}\nDurum: {status_text}"
        except Exception:
            pass
        return "ŞU AN ÇALIYOR\nMüzik algılanmadı\nDurum: Bekleniyor"

    def now_playing_idle_bg_asset_path():
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            return os.path.join(base_dir, "assets", "now_playing_idle_bg.gif")
        except Exception:
            return os.path.join(os.getcwd(), "assets", "now_playing_idle_bg.gif")

    def now_playing_idle_cover_resize(img, target_w, target_h):
        try:
            iw, ih = img.size
            if iw <= 0 or ih <= 0 or target_w <= 0 or target_h <= 0:
                return img
            scale = max(float(target_w) / float(iw), float(target_h) / float(ih))
            nw = max(1, int(iw * scale))
            nh = max(1, int(ih * scale))
            resample = getattr(Image, "Resampling", Image).LANCZOS
            resized = img.resize((nw, nh), resample)
            left = max(0, (nw - target_w) // 2)
            top = max(0, (nh - target_h) // 2)
            return resized.crop((left, top, left + target_w, top + target_h))
        except Exception:
            return img

    def now_playing_idle_load_bg_frames(target_w, target_h):
        global now_playing_idle_bg_frames, now_playing_idle_bg_size
        try:
            target_w = max(800, int(target_w or 1280))
            target_h = max(450, int(target_h or 720))
            if now_playing_idle_bg_frames and now_playing_idle_bg_size == (target_w, target_h):
                return now_playing_idle_bg_frames
            path = now_playing_idle_bg_asset_path()
            if not os.path.exists(path):
                return []
            img = Image.open(path)
            frame_count = int(getattr(img, "n_frames", 1) or 1)
            max_frames = 30
            step = max(1, math.ceil(frame_count / max_frames))
            frames = []
            for idx in range(0, frame_count, step):
                try:
                    img.seek(idx)
                    frame_img = img.convert("RGBA")
                    frame_img = now_playing_idle_cover_resize(frame_img, target_w, target_h)
                    frames.append(ImageTk.PhotoImage(frame_img))
                except Exception:
                    continue
            now_playing_idle_bg_frames = frames
            now_playing_idle_bg_size = (target_w, target_h) if frames else (0, 0)
            return frames
        except Exception as exc:
            try:
                now_playing_log(f"[IDLE_BG_LOAD_ERROR] {exc}")
            except Exception:
                pass
            return []

    def now_playing_idle_bg_tick():
        global now_playing_idle_bg_job, now_playing_idle_bg_frame_index
        try:
            if not now_playing_idle_active:
                now_playing_idle_bg_job = None
                return
            canvas = globals().get("now_playing_idle_bg_canvas")
            image_item = globals().get("now_playing_idle_bg_image_item")
            frames = globals().get("now_playing_idle_bg_frames") or []
            if not now_playing_widget_alive(canvas) or not image_item or not frames:
                now_playing_idle_bg_job = None
                return
            now_playing_idle_bg_frame_index = (now_playing_idle_bg_frame_index + 1) % len(frames)
            canvas.itemconfig(image_item, image=frames[now_playing_idle_bg_frame_index])
            canvas.image = frames[now_playing_idle_bg_frame_index]
            now_playing_idle_bg_job = root.after(70, now_playing_idle_bg_tick)
        except Exception as exc:
            try:
                now_playing_log(f"[IDLE_BG_TICK_ERROR] {exc}")
            except Exception:
                pass
            now_playing_idle_bg_job = None

    def now_playing_idle_start_bg(frame, win):
        global now_playing_idle_bg_label, now_playing_idle_bg_canvas, now_playing_idle_bg_image_item, now_playing_idle_bg_job, now_playing_idle_bg_frame_index
        try:
            try:
                win.update_idletasks()
                frame.update_idletasks()
            except Exception:
                pass
            target_w = int(win.winfo_width() or win.winfo_screenwidth() or 1280)
            target_h = int(win.winfo_height() or win.winfo_screenheight() or 720)
            frames = now_playing_idle_load_bg_frames(target_w, target_h)
            if not frames:
                return False
            now_playing_idle_bg_frame_index = 0
            canvas = tk.Canvas(frame, bg="#000000", bd=0, highlightthickness=0, relief="flat")
            canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
            image_item = canvas.create_image(0, 0, image=frames[0], anchor="nw")
            canvas.image = frames[0]
            now_playing_idle_bg_canvas = canvas
            now_playing_idle_bg_label = canvas
            now_playing_idle_bg_image_item = image_item
            if now_playing_idle_bg_job:
                try:
                    root.after_cancel(now_playing_idle_bg_job)
                except Exception:
                    pass
            now_playing_idle_bg_job = root.after(60, now_playing_idle_bg_tick)
            return True
        except Exception as exc:
            try:
                now_playing_log(f"[IDLE_BG_START_ERROR] {exc}")
            except Exception:
                pass
            return False

    def now_playing_idle_turkish_date():
        try:
            now = datetime.datetime.now()
            days = [
                "Pazartesi",
                "Salı",
                "Çarşamba",
                "Perşembe",
                "Cuma",
                "Cumartesi",
                "Pazar",
            ]
            months = [
                "Ocak",
                "Şubat",
                "Mart",
                "Nisan",
                "Mayıs",
                "Haziran",
                "Temmuz",
                "Ağustos",
                "Eylül",
                "Ekim",
                "Kasım",
                "Aralık",
            ]
            return f"{days[now.weekday()]}, {now.day} {months[now.month - 1]} {now.year}"
        except Exception:
            return time.strftime("%d.%m.%Y")

    def now_playing_idle_canvas_draw_text(info):
        global now_playing_idle_canvas_items
        try:
            canvas = globals().get("now_playing_idle_bg_canvas")
            if not now_playing_widget_alive(canvas):
                return False
            try:
                canvas.update_idletasks()
            except Exception:
                pass
            w = int(canvas.winfo_width() or canvas.winfo_reqwidth() or 1280)
            h = int(canvas.winfo_height() or canvas.winfo_reqheight() or 720)
            if w < 200 or h < 200:
                return False
            song = now_playing_idle_song_text(info)
            clock = time.strftime("%H:%M")
            date = now_playing_idle_turkish_date()

            def text_with_shadow(key, x, y, text, font, anchor="nw", width=0):
                shadow_key = f"{key}_shadow"
                item_width = int(width or 0)
                create_kwargs = {
                    "text": text,
                    "font": font,
                    "anchor": anchor,
                }
                if item_width > 0:
                    create_kwargs["width"] = item_width
                if key not in now_playing_idle_canvas_items:
                    now_playing_idle_canvas_items[shadow_key] = canvas.create_text(
                        x + 3, y + 3, fill="#000000", **create_kwargs,
                    )
                    now_playing_idle_canvas_items[key] = canvas.create_text(
                        x, y, fill="#FFFFFF", **create_kwargs,
                    )
                else:
                    canvas.coords(now_playing_idle_canvas_items[shadow_key], x + 3, y + 3)
                    canvas.coords(now_playing_idle_canvas_items[key], x, y)
                    canvas.itemconfig(now_playing_idle_canvas_items[shadow_key], **create_kwargs)
                    canvas.itemconfig(now_playing_idle_canvas_items[key], **create_kwargs)

            text_with_shadow("song", int(w * 0.035), int(h * 0.075), song, ("Segoe UI Semibold", 42), "nw", max(520, int(w * 0.5)))
            text_with_shadow("clock", int(w * 0.04), int(h * 0.72), clock, ("Segoe UI Semibold", 112), "w", 0)
            text_with_shadow("date", int(w * 0.96), int(h * 0.78), date, ("Segoe UI Semibold", 28), "e", 0)
            return True
        except Exception as exc:
            try:
                now_playing_log(f"[IDLE_CANVAS_TEXT_ERROR] {exc}")
            except Exception:
                pass
            return False

    def now_playing_idle_update():
        global now_playing_idle_last_media_key, now_playing_idle_change_until
        try:
            if not now_playing_overlay_alive() or not now_playing_idle_active:
                return
            info = now_playing_idle_best_info()
            if not now_playing_idle_info_valid(info):
                info = now_playing_load_last_media()
            now_playing_idle_refresh_media_async()
            current_key = now_playing_info_key(info) if info else ""
            if current_key and now_playing_idle_last_media_key and current_key != now_playing_idle_last_media_key:
                now_playing_idle_change_until = time.time() + 5.0
            if current_key:
                now_playing_idle_last_media_key = current_key
            now_playing_idle_canvas_draw_text(info)
            if now_playing_widget_alive(now_playing_idle_clock_label):
                now_playing_idle_clock_label.configure(text=time.strftime("%H:%M"))
            date_label = globals().get("now_playing_idle_date_label")
            if now_playing_widget_alive(date_label):
                date_label.configure(text=now_playing_idle_turkish_date())
            song_label = globals().get("now_playing_idle_song_label")
            title = str(info.get("title") or "Müzik algılanmadı").strip()
            artist = str(info.get("artist") or "Sanatçı algılanmadı").strip()
            app = str(info.get("app") or info.get("source") or "").strip()
            status_text = now_playing_status_text_from_info(info)
            header_label = globals().get("now_playing_idle_header_label")
            if now_playing_widget_alive(header_label):
                header_label.configure(text="")
            if now_playing_widget_alive(song_label):
                song_label.configure(text=now_playing_idle_song_text(info))
            title_label = globals().get("now_playing_idle_title_label")
            if now_playing_widget_alive(title_label):
                title_label.configure(text="")
            artist_label = globals().get("now_playing_idle_artist_label")
            if now_playing_widget_alive(artist_label):
                artist_label.configure(text="")
            status_label = globals().get("now_playing_idle_status_label")
            if now_playing_widget_alive(status_label):
                status_label.configure(text="")
            change_label = globals().get("now_playing_idle_change_label")
            if now_playing_widget_alive(change_label):
                if time.time() < float(now_playing_idle_change_until or 0):
                    change_label.configure(text="")
                else:
                    change_label.configure(text="")
            volume_label_idle = globals().get("now_playing_idle_volume_label")
            if now_playing_widget_alive(volume_label_idle):
                volume_label_idle.configure(text="")
            root.after(1000, now_playing_idle_update)
        except Exception as exc:
            try:
                now_playing_log(f"[IDLE_UPDATE_ERROR] {exc}")
            except Exception:
                pass

    def now_playing_idle_header_text(info):
        try:
            if now_playing_idle_info_valid(info):
                return now_playing_idle_header_compact(info)
        except Exception:
            pass
        return "ŞU AN ÇALIYOR\nMüzik algılanmadı\nDurum: Bekleniyor"

    def now_playing_idle_best_info():
        """Return the best non-empty Now Playing state for idle screen labels."""
        for key in ("now_playing_current_info", "now_playing_monitor_last_info", "now_playing_last_info"):
            try:
                info = globals().get(key)
                if now_playing_idle_info_valid(info):
                    return info
            except Exception:
                pass
        visible_info = now_playing_idle_info_from_visible_labels()
        if now_playing_idle_info_valid(visible_info):
            return visible_info
        saved_info = now_playing_load_last_media()
        if now_playing_idle_info_valid(saved_info):
            return saved_info
        return {}

    def now_playing_idle_label_text(name):
        try:
            widget = globals().get(name)
            if now_playing_widget_alive(widget):
                return str(widget.cget("text") or "").strip()
        except Exception:
            pass
        return ""

    def now_playing_idle_info_from_visible_labels():
        """Build media state from already visible Now Playing labels."""
        try:
            title = now_playing_idle_label_text("now_playing_title_label")
            artist = now_playing_idle_label_text("now_playing_artist_label")
            source = now_playing_idle_label_text("now_playing_source_label")
            status = now_playing_idle_label_text("now_playing_status_label")
            if ":" in source:
                source = source.split(":", 1)[1].strip()
            if ":" in status:
                status = status.split(":", 1)[1].strip()
            if not title:
                return {}
            return {
                "title": title,
                "artist": artist,
                "app": source or "Now Playing",
                "source": "overlay_labels",
                "playback_status": status or "playing",
                "time": time.time(),
            }
        except Exception:
            return {}

    def now_playing_idle_info_valid(info):
        try:
            if not isinstance(info, dict) or info.get("error"):
                return False
            title = str(info.get("title") or "").strip()
            if not title:
                return False
            bad_titles = {
                now_playing_text("detecting").strip().lower(),
                "müzik bilgisi alınıyor...",
                "müzik algılanmadı",
                "şarkı aranıyor...",
                "detecting track...",
                "no track detected",
                "waiting for music",
                "şarkı algılanamadı",
                "şu an parça bilgisi yok.",
            }
            return title.lower() not in bad_titles and not now_playing_placeholder_title(title)
        except Exception:
            return False

    def now_playing_idle_apply_info(info):
        """Update idle screen immediately after a fresh media detection."""
        global now_playing_idle_last_media_key, now_playing_idle_change_until
        try:
            if not now_playing_idle_active or not now_playing_idle_info_valid(info):
                return
            current_key = now_playing_info_key(info)
            if current_key and now_playing_idle_last_media_key and current_key != now_playing_idle_last_media_key:
                now_playing_idle_change_until = time.time() + 5.0
            if current_key:
                now_playing_idle_last_media_key = current_key

            title = str(info.get("title") or "").strip()
            artist = now_playing_idle_artist_name(info)
            status_text = now_playing_status_text_from_info(info)

            header_label = globals().get("now_playing_idle_header_label")
            if now_playing_widget_alive(header_label):
                header_label.configure(text="")

            song_label = globals().get("now_playing_idle_song_label")
            if now_playing_widget_alive(song_label):
                song_label.configure(text=now_playing_idle_song_text(info))
            now_playing_idle_canvas_draw_text(info)

            title_label = globals().get("now_playing_idle_title_label")
            if now_playing_widget_alive(title_label):
                title_label.configure(text="")

            artist_label = globals().get("now_playing_idle_artist_label")
            if now_playing_widget_alive(artist_label):
                artist_label.configure(text="")

            status_label = globals().get("now_playing_idle_status_label")
            if now_playing_widget_alive(status_label):
                status_label.configure(text="")

            change_label = globals().get("now_playing_idle_change_label")
            if now_playing_widget_alive(change_label) and time.time() < float(now_playing_idle_change_until or 0):
                change_label.configure(text="")
        except Exception:
            pass

    def now_playing_idle_refresh_media_async():
        global now_playing_idle_refreshing
        if now_playing_idle_refreshing:
            return
        now_playing_idle_refreshing = True

        def worker():
            try:
                fresh_info = neto_now_playing.get_current_media(force_fresh=True)
                if not fresh_info:
                    fresh_info = neto_now_playing.get_current_media(force_fresh=False)
            except Exception:
                fresh_info = None

            def apply_result():
                global now_playing_idle_refreshing
                try:
                    if now_playing_idle_info_valid(fresh_info):
                        now_playing_save_last_media(fresh_info)
                        globals()["now_playing_current_info"] = fresh_info
                        globals()["now_playing_monitor_last_info"] = fresh_info
                        globals()["now_playing_last_info"] = fresh_info
                        now_playing_idle_apply_info(fresh_info)
                finally:
                    now_playing_idle_refreshing = False

            try:
                root.after(0, apply_result)
            except Exception:
                now_playing_idle_refreshing = False

        try:
            threading.Thread(target=worker, daemon=True).start()
        except Exception:
            now_playing_idle_refreshing = False

    def now_playing_idle_exit(_event=None):
        global now_playing_idle_active, now_playing_idle_frame, now_playing_idle_last_activity, now_playing_idle_deadline, now_playing_idle_bg_job, now_playing_idle_bg_label, now_playing_idle_bg_canvas, now_playing_idle_bg_image_item, now_playing_idle_canvas_items
        now_playing_idle_last_activity = time.time()
        now_playing_idle_deadline = now_playing_idle_last_activity + max(1, now_playing_idle_seconds())
        if not now_playing_idle_active:
            return
        now_playing_idle_active = False
        try:
            if now_playing_idle_bg_job:
                root.after_cancel(now_playing_idle_bg_job)
        except Exception:
            pass
        now_playing_idle_bg_job = None
        now_playing_idle_bg_label = None
        now_playing_idle_bg_canvas = None
        now_playing_idle_bg_image_item = None
        now_playing_idle_canvas_items = {}
        try:
            if now_playing_idle_frame is not None and now_playing_idle_frame.winfo_exists():
                now_playing_idle_frame.destroy()
        except Exception:
            pass
        now_playing_idle_frame = None

    def now_playing_idle_click_exit(event=None):
        try:
            if now_playing_idle_active:
                root.after(1, now_playing_idle_exit)
                return "break"
        except Exception:
            pass
        return None

    def now_playing_idle_bind_global_click():
        global now_playing_idle_global_click_bound
        if now_playing_idle_global_click_bound:
            return
        try:
            root.bind_all("<Button-1>", now_playing_idle_click_exit, add="+")
            root.bind_all("<ButtonRelease-1>", now_playing_idle_click_exit, add="+")
            now_playing_idle_global_click_bound = True
        except Exception:
            pass

    def now_playing_idle_enter():
        global now_playing_idle_active, now_playing_idle_frame, now_playing_idle_header_label, now_playing_idle_clock_label, now_playing_idle_last_media_key, now_playing_idle_change_until
        if now_playing_idle_active or not now_playing_overlay_alive() or now_playing_idle_seconds() <= 0:
            return
        now_playing_idle_active = True
        win = now_playing_overlay
        pal = now_playing_ui_palette()
        info = now_playing_idle_best_info()
        if not now_playing_idle_info_valid(info):
            info = now_playing_load_last_media()
        now_playing_idle_last_media_key = now_playing_info_key(info) if info else ""
        now_playing_idle_change_until = 0.0
        frame = ctk.CTkFrame(win, fg_color="#080B1F", corner_radius=0)
        now_playing_idle_frame = frame
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        now_playing_idle_start_bg(frame, win)
        now_playing_idle_header_label = ctk.CTkLabel(
            frame,
            text="",
            text_color="#FFFFFF",
            font=("Segoe UI Semibold", 25),
            anchor="w",
            justify="left",
        )
        now_playing_idle_clock_label = None
        globals()["now_playing_idle_date_label"] = None
        _idle_title = str(info.get("title") or "").strip() if now_playing_idle_info_valid(info) else ""
        _idle_artist = now_playing_idle_artist_name(info) if _idle_title else ""
        _idle_app = str(info.get("app") or info.get("source") or "").strip() if _idle_title else ""
        _idle_status = now_playing_status_text_from_info(info) if _idle_title else "Bekleniyor"
        song_label = ctk.CTkLabel(
            frame,
            text=now_playing_idle_song_text(info),
            text_color="#FFFFFF",
            font=("Segoe UI Semibold", 42),
            wraplength=1300,
            anchor="w",
            justify="left",
        )
        globals()["now_playing_idle_song_label"] = song_label
        title_label = ctk.CTkLabel(frame, text="", text_color="#D9E1FF", font=("Segoe UI Semibold", 23), wraplength=1200, anchor="w", justify="left")
        globals()["now_playing_idle_title_label"] = title_label
        artist_label = ctk.CTkLabel(
            frame,
            text="",
            text_color="#D7DBF4",
            font=("Segoe UI", 24),
            anchor="w",
            justify="left",
        )
        globals()["now_playing_idle_artist_label"] = artist_label
        status_label = ctk.CTkLabel(frame, text="", text_color=pal["accent"], font=("Segoe UI Semibold", 23), anchor="w", justify="left")
        globals()["now_playing_idle_status_label"] = status_label
        change_label = ctk.CTkLabel(frame, text="", text_color="#7DEBFF", font=("Segoe UI Semibold", 22), wraplength=1200, anchor="w", justify="left")
        globals()["now_playing_idle_change_label"] = change_label
        volume_label_idle = ctk.CTkLabel(frame, text="", text_color=pal["accent"], font=("Segoe UI Semibold", 23), anchor="w", justify="left")
        globals()["now_playing_idle_volume_label"] = volume_label_idle
        now_playing_idle_canvas_draw_text(info)
        try:
            now_playing_log(f"[IDLE_ENTER_INFO] valid={now_playing_idle_info_valid(info)} info={info}")
        except Exception:
            pass
        if now_playing_idle_info_valid(info):
            now_playing_idle_apply_info(info)
        now_playing_idle_bind_activity(win)
        now_playing_idle_bind_activity(frame)
        try:
            frame.after(120, lambda: now_playing_idle_bind_activity(frame))
        except Exception:
            pass
        try:
            canvas = globals().get("now_playing_idle_bg_canvas")
            if now_playing_widget_alive(canvas):
                now_playing_idle_bind_activity(canvas)
        except Exception:
            pass
        now_playing_idle_bind_global_click()
        now_playing_idle_update()
        try:
            root.after(250, now_playing_idle_update)
            root.after(900, now_playing_idle_update)
            root.after(120, lambda info=info: now_playing_idle_canvas_draw_text(info))
        except Exception:
            pass

    def now_playing_idle_watchdog():
        global now_playing_idle_job
        try:
            if not now_playing_overlay_alive():
                now_playing_idle_job = None
                return
            if not now_playing_idle_active and now_playing_idle_seconds() > 0:
                deadline = now_playing_idle_deadline or (now_playing_idle_last_activity + now_playing_idle_seconds())
                if time.time() >= deadline:
                    now_playing_idle_enter()
            now_playing_idle_job = root.after(1000, now_playing_idle_watchdog)
        except Exception:
            now_playing_idle_job = None

    def now_playing_idle_bind_activity(widget, exit_on_double_click=False):
        try:
            callback = now_playing_idle_click_exit
            if exit_on_double_click:
                widget.bind("<Double-Button-1>", callback, add="+")
            else:
                widget.bind("<Button-1>", callback, add="+")
                widget.bind("<ButtonRelease-1>", callback, add="+")
            widget.bind("<KeyPress>", callback, add="+")
            for attr in ("_canvas", "_text_label", "_image_label", "_label"):
                inner = getattr(widget, attr, None)
                if inner is not None:
                    try:
                        if exit_on_double_click:
                            inner.bind("<Double-Button-1>", callback, add="+")
                        else:
                            inner.bind("<Button-1>", callback, add="+")
                            inner.bind("<ButtonRelease-1>", callback, add="+")
                    except Exception:
                        pass
            for child in widget.winfo_children():
                now_playing_idle_bind_activity(child, exit_on_double_click=exit_on_double_click)
        except Exception:
            pass

    def now_playing_overlay_kapat():
        global now_playing_overlay, now_playing_canvas_job, now_playing_hidden_until_key, now_playing_countdown_job, now_playing_idle_job, now_playing_idle_active, now_playing_idle_frame, now_playing_idle_bg_job, now_playing_idle_bg_label, now_playing_idle_bg_canvas, now_playing_idle_bg_image_item, now_playing_idle_canvas_items
        try:
            if now_playing_canvas_job:
                root.after_cancel(now_playing_canvas_job)
                now_playing_canvas_job = None
        except Exception:
            pass
        try:
            if now_playing_idle_job:
                root.after_cancel(now_playing_idle_job)
                now_playing_idle_job = None
        except Exception:
            pass
        try:
            if now_playing_idle_bg_job:
                root.after_cancel(now_playing_idle_bg_job)
                now_playing_idle_bg_job = None
        except Exception:
            pass
        now_playing_idle_bg_label = None
        now_playing_idle_bg_canvas = None
        now_playing_idle_bg_image_item = None
        now_playing_idle_canvas_items = {}
        now_playing_idle_active = False
        now_playing_idle_frame = None
        try:
            if now_playing_countdown_job:
                root.after_cancel(now_playing_countdown_job)
                now_playing_countdown_job = None
        except Exception:
            pass
        try:
            now_playing_hidden_until_key = now_playing_current_key
            if now_playing_overlay_alive():
                try:
                    now_playing_overlay.destroy()
                except Exception:
                    pass
        except Exception:
            pass
        now_playing_overlay = None
        try:
            now_playing_theme_widgets.clear()
        except Exception:
            pass

    def now_playing_visualizer_loop(canvas, step=0):
        global now_playing_canvas_job
        try:
            if not now_playing_overlay_alive():
                return
            try:
                if now_playing_visual_mode_get() != "wave":
                    return
            except Exception:
                pass
            try:
                if not now_playing_widget_alive(canvas):
                    return
            except Exception:
                return
            canvas.delete("all")
            w = max(420, canvas.winfo_width())
            h = max(130, canvas.winfo_height())
            bars, gap = 46, 4
            bw = max(5, int((w - (bars + 1) * gap) / bars))
            import math
            key = str(now_playing_current_key or "neto")
            seed = sum(ord(c) for c in key) % 31
            pal = now_playing_ui_palette()
            accent = pal["accent"]
            dim_accent = _neto_hex_karistir(pal["card"], accent, 0.55)
            phase = step * 0.18
            for i in range(bars):
                # Şarkı adına göre değişen ama sürekli hareket eden görsel ritim
                wave = (math.sin(phase + i * 0.42 + seed) + 1) / 2
                wave2 = (math.sin((phase * 1.8) + i * 0.93 + seed * 0.35) + 1) / 2
                pulse = (math.sin(phase * 0.75 + seed) + 1) / 2
                level = 0.20 + (0.28 * wave) + (0.38 * wave2) + (0.14 * pulse)
                bh = int(12 + (h - 24) * max(0.0, min(1.0, level)))
                x1 = gap + i * (bw + gap)
                fill = accent if i % 3 else dim_accent
                canvas.create_rectangle(x1, h - bh, x1 + bw, h, fill=fill, outline="")
                if i % 4 == 0:
                    canvas.create_oval(x1, h - bh - 4, x1 + bw, h - bh + 4, fill=fill, outline="")
            now_playing_canvas_job = root.after(
                int(_neto_now_playing_interval("visualizer_ms", 33)),
                lambda: now_playing_visualizer_loop(canvas, step + 1),
            )
        except Exception:
            pass

    def now_playing_status_text_from_info(info):
        """Return localized playback status text."""
        try:
            raw = str((info or {}).get("playback_status", "") or "").lower()
            if "playing" in raw or raw in ("4", "3"):
                return now_playing_text("status_playing")
            if "paused" in raw or "pause" in raw or raw in ("5", "2"):
                return now_playing_text("status_paused")
            if "stopped" in raw or "stop" in raw:
                return now_playing_text("status_stopped")
            # Visible window-title fallback cannot always know pause state.
            # If a current title is visible, show it as playing instead of unknown.
            if info and info.get("title"):
                return now_playing_text("status_playing")
        except Exception:
            pass
        return now_playing_text("status_unknown")

    def now_playing_visual_mode_get():
        try:
            h = veri_yukle()
            mode = str(h.get("now_playing_visual_mode", "vinyl")).lower()
            # internal value "vinyl" is kept for compatibility, but UI shows it as Album Cover.
            return mode if mode in ("wave", "vinyl") else "vinyl"
        except Exception:
            return "vinyl"

    def now_playing_visual_mode_set(mode):
        try:
            mode = "wave" if str(mode).lower() == "wave" else "vinyl"
            h = veri_yukle()
            h["now_playing_visual_mode"] = mode
            veri_kaydet(h)
            return mode
        except Exception:
            return "vinyl"

    def now_playing_cover_key(info):
        try:
            return f"{(info or {}).get('app','')}|{(info or {}).get('artist','')}|{(info or {}).get('title','')}"
        except Exception:
            return ""

    def now_playing_select_cover_for_display(info):
        """Stable: if song changes and current cover is missing, never show old song cover."""
        global now_playing_display_cover_path, now_playing_display_cover_key, now_playing_cover_transition_step
        try:
            key = now_playing_cover_key(info)
            new_cover = str((info or {}).get("cover_path", "") or "")
            if key != now_playing_display_cover_key:
                now_playing_display_cover_key = key
                now_playing_display_cover_path = None
                now_playing_cover_transition_step = 0
            if new_cover and os.path.exists(new_cover):
                now_playing_display_cover_path = new_cover
                return new_cover
            return ""
        except Exception:
            return ""

    def now_playing_draw_album_cover(canvas, info=None):
        global now_playing_vinyl_photo
        try:
            if not now_playing_widget_alive(canvas):
                return
            canvas.update_idletasks()
            canvas.delete("all")
            w = max(340, int(canvas.winfo_width() or 340))
            h = max(330, int(canvas.winfo_height() or 330))
            cx, cy = w // 2, h // 2
            size = min(292, w - 44, h - 34)
            x, y = cx - size // 2, cy - size // 2

            cover_path = now_playing_select_cover_for_display(info)
            if cover_path and os.path.exists(cover_path) and Image is not None and ImageTk is not None:
                try:
                    im = Image.open(cover_path).convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
                    now_playing_vinyl_photo = ImageTk.PhotoImage(im)
                    canvas.create_rectangle(x-10, y-10, x+size+10, y+size+10, fill=now_playing_ui_palette()["card"], outline=now_playing_ui_palette()["border"], width=2)
                    canvas.create_image(cx, cy, image=now_playing_vinyl_photo)
                    canvas.create_rectangle(x, y, x+size, y+size, outline=now_playing_ui_palette()["accent"], width=3)
                    return
                except Exception:
                    pass

            # Clean fallback card. No random wrong cover.
            canvas.create_rectangle(x-10, y-10, x+size+10, y+size+10, fill=now_playing_ui_palette()["card"], outline=now_playing_ui_palette()["border"], width=2)
            canvas.create_rectangle(x, y, x+size, y+size, fill=now_playing_ui_palette()["entry"], outline=now_playing_ui_palette()["accent"], width=3)
            canvas.create_text(cx, cy-44, text="♪", fill=now_playing_ui_palette()["accent"], font=("Segoe UI Emoji", 72, "bold"))
            try:
                title = str((info or {}).get("title", "") or "")[:32]
                artist = str((info or {}).get("artist", "") or "")[:30]
                if title:
                    canvas.create_text(cx, cy+54, text=title, fill=now_playing_ui_palette()["text"], font=("Segoe UI Semibold", 14), width=size-28, justify="center")
                if artist:
                    canvas.create_text(cx, cy+82, text=artist, fill=now_playing_ui_palette()["dim"], font=("Segoe UI", 11), width=size-28, justify="center")
            except Exception:
                pass
        except Exception as e:
            try:
                now_playing_log(f"[ALBUM_COVER_DRAW_ERROR] {e}")
            except Exception:
                pass

    def now_playing_render_visual():
        """Render either wave animation or album-cover mode inside existing overlay."""
        global now_playing_canvas_job, now_playing_vinyl_job, now_playing_visual_canvas, now_playing_visual_logo_label, now_playing_vinyl_canvas
        try:
            if not now_playing_widget_alive(now_playing_visual_frame):
                return
            try:
                if now_playing_canvas_job:
                    root.after_cancel(now_playing_canvas_job)
            except Exception:
                pass
            now_playing_canvas_job = None
            try:
                if now_playing_vinyl_job:
                    root.after_cancel(now_playing_vinyl_job)
            except Exception:
                pass
            now_playing_vinyl_job = None
            try:
                for child in now_playing_visual_frame.winfo_children():
                    try:
                        child.destroy()
                    except Exception:
                        pass
            except Exception:
                pass
            mode = now_playing_visual_mode_get()
            if mode == "vinyl":
                canvas = tk.Canvas(now_playing_visual_frame, bg=now_playing_ui_palette()["bg"], width=340, height=330, highlightthickness=0, bd=0)
                canvas.pack(pady=(8, 14))
                globals()["now_playing_vinyl_canvas"] = canvas
                globals()["now_playing_visual_canvas"] = None
                now_playing_draw_album_cover(canvas, now_playing_current_info)
            else:
                canvas = tk.Canvas(now_playing_visual_frame, bg=now_playing_ui_palette()["bg"], height=150, highlightthickness=0, bd=0)
                canvas.pack(fill="x", padx=100, pady=(22, 14))
                globals()["now_playing_visual_canvas"] = canvas
                globals()["now_playing_vinyl_canvas"] = None
                now_playing_visualizer_loop(canvas)
            try:
                if now_playing_widget_alive(now_playing_visual_mode_button):
                    now_playing_visual_mode_button.configure(
                        text=now_playing_text("switch_to_wave") if mode == "vinyl" else now_playing_text("switch_to_vinyl")
                    )
            except Exception:
                pass
        except Exception as e:
            try:
                now_playing_log(f"[VISUAL_RENDER_ERROR] {e}")
            except Exception:
                pass

    def now_playing_visual_mode_toggle():
        try:
            current = now_playing_visual_mode_get()
            now_playing_visual_mode_set("vinyl" if current == "wave" else "wave")
            now_playing_render_visual()
        except Exception as e:
            try:
                now_playing_log(f"[VISUAL_TOGGLE_ERROR] {e}")
            except Exception:
                pass

    def now_playing_overlay_update(info):
        """Update existing Now Playing overlay labels. Never destroys/recreates window."""
        global now_playing_current_key
        try:
            if not info or info.get("error") or not info.get("title"):
                return False

            title = str(info.get("title", "") or "").strip()
            artist = str(info.get("artist", "") or "").strip() or now_playing_text("artist_missing")
            app = str(info.get("app", "") or info.get("source", "") or "Unknown").strip()
            key = now_playing_info_key(info)
            if key:
                now_playing_current_key = key
            globals()["now_playing_current_info"] = info
            globals()["now_playing_monitor_last_info"] = info
            globals()["now_playing_last_info"] = info
            now_playing_save_last_media(info)

            try:
                if now_playing_widget_alive(now_playing_title_label):
                    now_playing_title_label.configure(text=title)
            except Exception:
                pass
            try:
                if now_playing_widget_alive(now_playing_artist_label):
                    now_playing_artist_label.configure(text=artist)
            except Exception:
                pass
            try:
                if now_playing_widget_alive(now_playing_source_label):
                    now_playing_source_label.configure(text=f"{now_playing_text('source')}: {app}")
            except Exception:
                pass
            try:
                if now_playing_widget_alive(now_playing_status_label):
                    now_playing_status_label.configure(text=f"{now_playing_text('status')}: {now_playing_status_text_from_info(info)}")
            except Exception:
                pass
            try:
                if now_playing_visual_mode_get() == "vinyl" and now_playing_widget_alive(now_playing_vinyl_canvas):
                    now_playing_draw_album_cover(now_playing_vinyl_canvas, info)
            except Exception:
                pass
            return True
        except Exception as e:
            try:
                now_playing_log(f"[OVERLAY_UPDATE_ERROR] {e}")
            except Exception:
                pass
            return False

    def now_playing_dynamic_island_alive():
        try:
            return bool(now_playing_island) and bool(now_playing_island.winfo_exists())
        except Exception:
            return False

    def now_playing_dynamic_island_geometry(width=430, height=86, y=18):
        try:
            screen_w = int(root.winfo_screenwidth())
            x = max(0, (screen_w - int(width)) // 2)
            return f"{int(width)}x{int(height)}+{x}+{int(y)}"
        except Exception:
            return f"{int(width)}x{int(height)}+480+18"

    def now_playing_dynamic_island_place(width=430, height=86, y=None, keep_center=True):
        try:
            if not now_playing_dynamic_island_alive():
                return False
            win = now_playing_island
            width = int(width)
            height = int(height)
            if y is None:
                try:
                    y = int(win.winfo_y())
                    if y < -10:
                        y = 18
                except Exception:
                    y = 18
            if keep_center:
                screen_w = int(root.winfo_screenwidth())
                try:
                    center = int(now_playing_island_state.get("anim_center_x") or 0)
                    if center <= 0:
                        center = int(win.winfo_x()) + max(1, int(win.winfo_width())) // 2
                except Exception:
                    center = screen_w // 2
                x = max(0, min(screen_w - width, center - (width // 2)))
                win.geometry(f"{width}x{height}+{x}+{int(y)}")
            else:
                win.geometry(now_playing_dynamic_island_geometry(width, height, int(y)))
            now_playing_island_state["width"] = width
            now_playing_island_state["height"] = height
            now_playing_island_state["y"] = int(y)
            return True
        except Exception:
            return False

    def now_playing_dynamic_island_animate(width=430, height=86, y=None, steps=14, on_complete=None):
        if not now_playing_dynamic_island_alive():
            return False
        from neto_motion_engine_v2 import get_motion_engine
        engine = get_motion_engine(root)
        win = now_playing_island
        state = now_playing_island_state
        start = (win.winfo_width(), win.winfo_height(), win.winfo_y())
        target = (int(width), int(height), start[2] if y is None else int(y))
        state["anim_center_x"] = win.winfo_x() + start[0] // 2
        last = [start]
        def update(progress):
            if not now_playing_dynamic_island_alive():
                engine.cancel("music-island")
                return
            values = tuple(round(a + (b - a) * progress) for a, b in zip(start, target))
            if values != last[0]:
                now_playing_dynamic_island_place(*values, keep_center=True)
                last[0] = values
        def finish():
            state["anim_job"] = None
            state.pop("anim_center_x", None)
            if callable(on_complete):
                on_complete()
        state["anim_job"] = engine.tween("music-island", 220, update, on_complete=finish)
        return True

    def now_playing_dynamic_island_action_mode(mode="normal", message=None):
        try:
            if not now_playing_dynamic_island_alive():
                return False
            pal = now_playing_ui_palette()
            action_label = globals().get("now_playing_island_action_label")
            pull_label = globals().get("now_playing_island_pull_label")
            now_playing_island_state["mode"] = mode
            if action_label:
                try:
                    if mode == "normal":
                        action_label.grid_remove()
                    else:
                        action_label.grid()
                        action_label.configure(
                            text=str(message or ("Now Playing'e geri dön" if now_playing_lang() == "tr" else "Return to Now Playing")),
                            fg_color=_neto_hex_karistir(pal["card"], pal["accent"], 0.16),
                            text_color=pal["text"],
                            border_color=pal["accent"],
                        )
                except Exception:
                    pass
            if pull_label:
                try:
                    pull_label.configure(
                        text="↔" if mode == "normal" else "›",
                        fg_color=pal["accent"] if mode != "normal" else pal["entry"],
                        text_color=pal["accent_text"] if mode != "normal" else pal["text"],
                    )
                except Exception:
                    pass
            return True
        except Exception:
            return False

    def now_playing_dynamic_island_sistem_metni():
        try:
            if not K_PSUTIL:
                return "CPU/RAM okunamadı" if now_playing_lang() == "tr" else "CPU/RAM unavailable"
            metrics = neto_system_metrics(force=True)
            if not metrics.get("ok"):
                return "CPU/RAM okunamadı" if now_playing_lang() == "tr" else "CPU/RAM unavailable"
            cpu = float(metrics.get("cpu") or 0.0)
            ram = float(metrics.get("ram") or 0.0)
            return f"CPU %{cpu:.0f}  •  RAM %{ram:.0f}"
        except Exception:
            return "CPU/RAM okunamadı" if now_playing_lang() == "tr" else "CPU/RAM unavailable"

    def now_playing_dynamic_island_normal_don(width=430, height=86, y=18, animate=True):
        try:
            if not now_playing_dynamic_island_alive():
                return
            now_playing_dynamic_island_action_mode("normal")
            now_playing_dynamic_island_update(globals().get("now_playing_current_info") or globals().get("now_playing_monitor_last_info"))
            if animate:
                now_playing_dynamic_island_animate(width, height, y, steps=16)
            else:
                now_playing_dynamic_island_place(width, height, y, keep_center=True)
        except Exception:
            pass

    def now_playing_dynamic_island_sistem_goster(keep_shape=False, auto_return_ms=1900):
        try:
            if not now_playing_dynamic_island_alive():
                return False
            win = now_playing_island
            pal = now_playing_ui_palette()
            now_playing_island_state["hold_done"] = True
            try:
                restore_width = max(1, int(win.winfo_width()))
                restore_height = max(1, int(win.winfo_height()))
                restore_y = int(win.winfo_y())
            except Exception:
                restore_width, restore_height, restore_y = 430, 86, 18
            sistem_metni = now_playing_dynamic_island_sistem_metni()
            now_playing_dynamic_island_action_mode(
                "stats",
                sistem_metni,
            )
            try:
                now_playing_island_status_label.configure(
                    text="SYS",
                    fg_color=pal["accent"],
                    text_color=pal["accent_text"],
                    font=("Segoe UI Semibold", 11),
                )
                now_playing_island_title_label.configure(
                    text="Sistem durumu" if now_playing_lang() == "tr" else "System status",
                    text_color=pal["text"],
                )
                now_playing_island_artist_label.configure(
                    text="Ç hızlı bakış" if keep_shape and now_playing_lang() == "tr"
                    else ("Quick glance" if keep_shape else ("3 sn sonra eski haline döner" if now_playing_lang() == "tr" else "Returns automatically")),
                    text_color=pal["dim"],
                )
            except Exception:
                pass
            if keep_shape:
                now_playing_dynamic_island_place(restore_width, restore_height, restore_y, keep_center=True)
            else:
                now_playing_dynamic_island_animate(610, 92, 18, steps=16)
            try:
                old_job = now_playing_island_state.get("stats_job")
                if old_job:
                    root.after_cancel(old_job)
            except Exception:
                pass

            def _sistemden_don():
                try:
                    now_playing_island_state["stats_job"] = None
                    if keep_shape:
                        now_playing_dynamic_island_normal_don(restore_width, restore_height, restore_y, animate=False)
                    else:
                        now_playing_dynamic_island_normal_don()
                except Exception:
                    pass

            try:
                now_playing_island_state["stats_job"] = root.after(int(auto_return_ms), _sistemden_don)
            except Exception:
                pass
            return True
        except Exception:
            return False

    def now_playing_dynamic_island_now_playinge_don():
        try:
            now_playing_dynamic_island_kapat()
        except Exception:
            pass
        try:
            root.after(60, lambda: now_playing_manual_open(force=True))
        except Exception:
            try:
                now_playing_manual_open(force=True)
            except Exception:
                pass

    def now_playing_dynamic_island_kapat():
        global now_playing_island, now_playing_island_frame
        global now_playing_island_title_label, now_playing_island_artist_label, now_playing_island_status_label
        global now_playing_island_action_label, now_playing_island_pull_label, now_playing_island_state
        try:
            try:
                old_job = now_playing_island_state.get("anim_job")
                if old_job:
                    root.after_cancel(old_job)
                stats_job = now_playing_island_state.get("stats_job")
                if stats_job:
                    root.after_cancel(stats_job)
                hold_job = now_playing_island_state.get("hold_job")
                if hold_job:
                    root.after_cancel(hold_job)
                hold_hint_job = now_playing_island_state.get("hold_hint_job")
                if hold_hint_job:
                    root.after_cancel(hold_hint_job)
                click_job = now_playing_island_state.get("click_job")
                if click_job:
                    root.after_cancel(click_job)
            except Exception:
                pass
            if now_playing_dynamic_island_alive():
                now_playing_island.destroy()
        except Exception:
            pass
        now_playing_island = None
        now_playing_island_frame = None
        now_playing_island_title_label = None
        now_playing_island_artist_label = None
        now_playing_island_status_label = None
        now_playing_island_action_label = None
        now_playing_island_pull_label = None
        now_playing_island_state = {}

    def now_playing_dynamic_island_update(info=None):
        try:
            if not now_playing_dynamic_island_alive():
                return False
            pal = now_playing_ui_palette()
            data = info if isinstance(info, dict) else globals().get("now_playing_current_info")
            island_mode = str(now_playing_island_state.get("mode") or "normal")
            if not isinstance(data, dict) or data.get("error") or not str(data.get("title") or "").strip():
                title = now_playing_text("island_no_track")
                meta = now_playing_text("home_idle_status")
                status = "♪"
            else:
                title = str(data.get("title") or "").strip()
                artist = str(data.get("artist") or "").strip()
                app = str(data.get("app") or data.get("source") or "").strip()
                meta = artist if artist else app
                if artist and app:
                    meta = f"{artist} • {app}"
                status = "▶" if now_playing_status_text_from_info(data) == now_playing_text("status_playing") else "⏸"

            try:
                now_playing_island.configure(fg_color="#010203")
                now_playing_island.attributes("-topmost", True)
                now_playing_island.attributes("-transparentcolor", "#010203")
            except Exception:
                pass
            try:
                now_playing_island_frame.configure(
                    fg_color=pal["card"],
                    border_color=pal["accent"],
                )
            except Exception:
                pass
            try:
                if island_mode != "stats":
                    now_playing_island_status_label.configure(
                        text=status,
                        fg_color=pal["accent"],
                        text_color=pal["accent_text"],
                        font=("Segoe UI Semibold", 18),
                    )
            except Exception:
                pass
            try:
                if island_mode != "stats":
                    now_playing_island_title_label.configure(text=title[:54], text_color=pal["text"])
            except Exception:
                pass
            try:
                if island_mode != "stats":
                    now_playing_island_artist_label.configure(text=meta[:64], text_color=pal["dim"])
            except Exception:
                pass
            try:
                for child in now_playing_island_frame.winfo_children():
                    if isinstance(child, ctk.CTkButton):
                        child.configure(
                            fg_color=pal["entry"],
                            hover_color=pal["hover"],
                            text_color=pal["text"],
                        )
            except Exception:
                pass
            try:
                action_label = globals().get("now_playing_island_action_label")
                if action_label:
                    action_label.configure(
                        fg_color=_neto_hex_karistir(pal["card"], pal["accent"], 0.16),
                        text_color=pal["text"],
                        border_color=pal["accent"],
                    )
            except Exception:
                pass
            try:
                pull_label = globals().get("now_playing_island_pull_label")
                if pull_label:
                    pull_label.configure(
                        fg_color=pal["accent"] if island_mode != "normal" else pal["entry"],
                        text_color=pal["accent_text"] if island_mode != "normal" else pal["text"],
                    )
            except Exception:
                pass
            return True
        except Exception as exc:
            try:
                now_playing_log(f"[DYNAMIC_ISLAND_UPDATE_ERROR] {exc}")
            except Exception:
                pass
            return False

    def now_playing_dynamic_island_goster(info=None):
        global now_playing_island, now_playing_island_frame
        global now_playing_island_title_label, now_playing_island_artist_label, now_playing_island_status_label
        global now_playing_island_action_label, now_playing_island_pull_label, now_playing_island_state
        try:
            data = info if isinstance(info, dict) else None
            if data is None:
                data = globals().get("now_playing_current_info") or globals().get("now_playing_monitor_last_info") or {}

            if now_playing_dynamic_island_alive():
                try:
                    now_playing_island.deiconify()
                    now_playing_island.lift()
                except Exception:
                    pass
                return now_playing_dynamic_island_update(data)

            pal = now_playing_ui_palette()
            width, height = 430, 86
            win: Any = ctk.CTkToplevel(root)
            now_playing_island = win
            now_playing_island_state = {
                "mode": "normal",
                "width": width,
                "height": height,
                "pressing": False,
                "dragged": False,
                "pulling": False,
                "hold_done": False,
            }
            win.title(now_playing_text("dynamic_island"))
            win.configure(fg_color="#010203")
            win.geometry(now_playing_dynamic_island_geometry(width, height, -height))
            try:
                win.overrideredirect(True)
                win.attributes("-topmost", True)
                win.attributes("-alpha", 0.96)
                win.attributes("-transparentcolor", "#010203")
            except Exception:
                pass

            now_playing_island_frame = ctk.CTkFrame(
                win,
                fg_color=pal["card"],
                corner_radius=36,
                border_width=2,
                border_color=pal["accent"],
            )
            now_playing_island_frame.pack(fill="both", expand=True, padx=6, pady=6)
            now_playing_island_frame.grid_columnconfigure(1, weight=1)
            now_playing_island_frame.grid_columnconfigure(2, weight=0)

            now_playing_island_status_label = ctk.CTkLabel(
                now_playing_island_frame,
                text="♪",
                width=50,
                height=50,
                corner_radius=25,
                fg_color=pal["accent"],
                text_color=pal["accent_text"],
                font=("Segoe UI Semibold", 18),
            )
            now_playing_island_status_label.grid(row=0, column=0, rowspan=2, padx=(14, 10), pady=13)

            now_playing_island_title_label = ctk.CTkLabel(
                now_playing_island_frame,
                text="",
                text_color=pal["text"],
                font=("Segoe UI Semibold", 14),
                anchor="w",
            )
            now_playing_island_title_label.grid(row=0, column=1, sticky="ew", pady=(15, 0))

            now_playing_island_artist_label = ctk.CTkLabel(
                now_playing_island_frame,
                text="",
                text_color=pal["dim"],
                font=("Segoe UI", 11),
                anchor="w",
            )
            now_playing_island_artist_label.grid(row=1, column=1, sticky="ew", pady=(0, 14))

            now_playing_island_action_label = ctk.CTkLabel(
                now_playing_island_frame,
                text="",
                width=168,
                height=36,
                corner_radius=18,
                fg_color=_neto_hex_karistir(pal["card"], pal["accent"], 0.16),
                text_color=pal["text"],
                border_width=1,
                border_color=pal["accent"],
                font=("Segoe UI Semibold", 11),
                anchor="center",
            )
            now_playing_island_action_label.grid(row=0, column=2, rowspan=2, padx=(8, 4), pady=18)
            now_playing_island_action_label.grid_remove()

            play_btn = ctk.CTkButton(
                now_playing_island_frame,
                text="⏯",
                width=38,
                height=34,
                corner_radius=17,
                fg_color=pal["entry"],
                hover_color=pal["hover"],
                text_color=pal["text"],
                command=now_playing_play_pause,
            )
            play_btn.grid(row=0, column=3, rowspan=2, padx=(8, 4))

            close_btn = ctk.CTkButton(
                now_playing_island_frame,
                text="×",
                width=34,
                height=34,
                corner_radius=17,
                fg_color=pal["entry"],
                hover_color=pal["hover"],
                text_color=pal["text"],
                command=now_playing_dynamic_island_kapat,
            )
            close_btn.grid(row=0, column=4, rowspan=2, padx=(2, 4))

            now_playing_island_pull_label = ctk.CTkLabel(
                now_playing_island_frame,
                text="↔",
                width=32,
                height=34,
                corner_radius=17,
                fg_color=pal["entry"],
                text_color=pal["text"],
                font=("Segoe UI Semibold", 16),
                cursor="sb_h_double_arrow",
            )
            now_playing_island_pull_label.grid(row=0, column=5, rowspan=2, padx=(2, 14))

            def _ada_job_iptal(anahtar):
                try:
                    job = now_playing_island_state.get(anahtar)
                    if job:
                        root.after_cancel(job)
                except Exception:
                    pass
                now_playing_island_state[anahtar] = None

            def _ada_tek_tik_ac():
                try:
                    now_playing_island_state["click_job"] = None
                    if time.time() < float(now_playing_island_state.get("ignore_click_until", 0) or 0):
                        return
                    now_playing_dynamic_island_now_playinge_don()
                except Exception:
                    pass

            def _ada_basili_tutma_ipucu():
                try:
                    if not now_playing_island_state.get("pressing") or now_playing_island_state.get("dragged"):
                        return
                    now_playing_dynamic_island_action_mode(
                        "hold",
                        "Sağa çek • Çift tık durdur • Ç: CPU/RAM" if now_playing_lang() == "tr"
                        else "Pull right • Double click pause • C: CPU/RAM",
                    )
                    now_playing_dynamic_island_animate(580, 86, 18, steps=16)
                except Exception:
                    pass

            def _ada_basili_tutma_sistem():
                try:
                    if now_playing_island_state.get("pressing") and not now_playing_island_state.get("dragged"):
                        now_playing_dynamic_island_sistem_goster()
                except Exception:
                    pass

            def _ada_basili_tutma_planla():
                _ada_job_iptal("hold_hint_job")
                _ada_job_iptal("hold_job")
                try:
                    now_playing_island_state["hold_hint_job"] = root.after(650, _ada_basili_tutma_ipucu)
                    now_playing_island_state["hold_job"] = root.after(3000, _ada_basili_tutma_sistem)
                except Exception:
                    pass

            def _ada_surukle_basla(event):
                try:
                    try:
                        sagdan = (int(event.x_root) - int(win.winfo_rootx())) >= max(0, int(win.winfo_width()) - 94)
                    except Exception:
                        sagdan = False
                    if sagdan and event.widget is not now_playing_island_action_label:
                        return _ada_sagdan_cek_basla(event)
                    now_playing_island_state.update({
                        "pressing": True,
                        "dragged": False,
                        "pulling": False,
                        "hold_done": False,
                        "press_x": event.x_root,
                        "press_y": event.y_root,
                        "press_time": time.time(),
                    })
                    win._neto_drag_start = (event.x_root, event.y_root, win.winfo_x(), win.winfo_y())
                    _ada_basili_tutma_planla()
                except Exception:
                    pass

            def _ada_surukle(event):
                try:
                    if now_playing_island_state.get("pulling"):
                        return _ada_sagdan_cek(event)
                    sx, sy, wx, wy = getattr(win, "_neto_drag_start", (event.x_root, event.y_root, win.winfo_x(), win.winfo_y()))
                    hareket = abs(event.x_root - sx) + abs(event.y_root - sy)
                    if hareket > 8:
                        now_playing_island_state["dragged"] = True
                        _ada_job_iptal("hold_hint_job")
                        _ada_job_iptal("hold_job")
                    win.geometry(f"+{wx + event.x_root - sx}+{wy + event.y_root - sy}")
                except Exception:
                    pass

            def _ada_tik_bitti(event=None):
                try:
                    if now_playing_island_state.get("pulling"):
                        return _ada_sagdan_birak(event)
                    _ada_job_iptal("hold_hint_job")
                    _ada_job_iptal("hold_job")
                    now_playing_island_state["pressing"] = False
                    if now_playing_island_state.get("hold_done"):
                        now_playing_island_state["hold_done"] = False
                        return "break"
                    if now_playing_island_state.get("dragged"):
                        now_playing_island_state["dragged"] = False
                        return "break"
                    _ada_job_iptal("click_job")
                    now_playing_island_state["click_job"] = root.after(230, _ada_tek_tik_ac)
                    return "break"
                except Exception:
                    return "break"

            def _ada_cift_tik(event=None):
                try:
                    _ada_job_iptal("click_job")
                    _ada_job_iptal("hold_hint_job")
                    _ada_job_iptal("hold_job")
                    now_playing_island_state.update({
                        "pressing": False,
                        "pulling": False,
                        "dragged": False,
                        "ignore_click_until": time.time() + 0.45,
                    })
                    now_playing_play_pause(refresh_overlay=False)
                    now_playing_dynamic_island_action_mode(
                        "pause",
                        "Şarkı duraklatıldı" if now_playing_lang() == "tr" else "Playback paused",
                    )
                    try:
                        now_playing_island_status_label.configure(text="⏸")
                    except Exception:
                        pass
                    now_playing_dynamic_island_animate(528, 86, 18, steps=13)
                    root.after(950, now_playing_dynamic_island_normal_don)
                except Exception:
                    pass
                return "break"

            def _ada_sagdan_cek_basla(event):
                try:
                    _ada_job_iptal("click_job")
                    _ada_job_iptal("hold_hint_job")
                    _ada_job_iptal("hold_job")
                    now_playing_island_state.update({
                        "pressing": False,
                        "pulling": True,
                        "dragged": False,
                        "hold_done": False,
                        "pull_start_x": event.x_root,
                        "pull_start_time": time.time(),
                        "pull_distance": 0,
                    })
                    now_playing_dynamic_island_action_mode(
                        "pull",
                        "Now Playing'e geri dön" if now_playing_lang() == "tr" else "Return to Now Playing",
                    )
                    now_playing_dynamic_island_animate(560, 86, 18, steps=14)

                    def _pull_sistem():
                        try:
                            if now_playing_island_state.get("pulling"):
                                now_playing_dynamic_island_sistem_goster()
                        except Exception:
                            pass

                    now_playing_island_state["hold_job"] = root.after(3000, _pull_sistem)
                except Exception:
                    pass
                return "break"

            def _ada_sagdan_cek(event):
                try:
                    if not now_playing_island_state.get("pulling"):
                        return "break"
                    start_x = int(now_playing_island_state.get("pull_start_x", event.x_root))
                    mesafe = max(0, int(event.x_root) - start_x)
                    now_playing_island_state["pull_distance"] = mesafe
                    hedef = min(660, max(520, 430 + mesafe))
                    now_playing_dynamic_island_action_mode(
                        "pull",
                        "Now Playing'e geri dön" if now_playing_lang() == "tr" else "Return to Now Playing",
                    )
                    now_playing_dynamic_island_place(hedef, 86, 18, keep_center=True)
                except Exception:
                    pass
                return "break"

            def _ada_sagdan_birak(event=None):
                try:
                    _ada_job_iptal("hold_job")
                    pulling = bool(now_playing_island_state.get("pulling"))
                    hold_done = bool(now_playing_island_state.get("hold_done"))
                    mesafe = int(now_playing_island_state.get("pull_distance", 0) or 0)
                    baslangic = float(now_playing_island_state.get("pull_start_time", time.time()) or time.time())
                    sure = time.time() - baslangic
                    now_playing_island_state.update({"pulling": False, "pressing": False})
                    if hold_done:
                        now_playing_island_state["hold_done"] = False
                        return "break"
                    if pulling and (mesafe >= 20 or sure < 3.0):
                        now_playing_dynamic_island_now_playinge_don()
                    else:
                        now_playing_dynamic_island_normal_don()
                except Exception:
                    pass
                return "break"

            def _ada_klavye_sistem(event=None):
                try:
                    try:
                        focus = root.focus_get()
                    except Exception:
                        focus = None
                    if focus is not None:
                        try:
                            focus_class = str(focus.winfo_class()).lower()
                            focus_name = str(focus).lower()
                            if "entry" in focus_class or "text" in focus_class or "entry" in focus_name or "textbox" in focus_name:
                                return None
                        except Exception:
                            pass
                    if not now_playing_dynamic_island_alive():
                        opened = now_playing_dynamic_island_goster(
                            globals().get("now_playing_current_info") or globals().get("now_playing_monitor_last_info")
                        )
                        if opened:
                            try:
                                root.after(180, lambda: now_playing_dynamic_island_sistem_goster(keep_shape=True, auto_return_ms=1500))
                            except Exception:
                                pass
                            return "break"
                    now_playing_dynamic_island_sistem_goster(keep_shape=True, auto_return_ms=1500)
                except Exception:
                    pass
                return "break"

            try:
                for drag_widget in (
                    now_playing_island_frame,
                    now_playing_island_status_label,
                    now_playing_island_title_label,
                    now_playing_island_artist_label,
                    now_playing_island_action_label,
                ):
                    drag_widget.bind("<ButtonPress-1>", _ada_surukle_basla)
                    drag_widget.bind("<B1-Motion>", _ada_surukle)
                    drag_widget.bind("<ButtonRelease-1>", _ada_tik_bitti)
                    drag_widget.bind("<Double-Button-1>", _ada_cift_tik)
            except Exception:
                pass

            try:
                for pull_widget in (now_playing_island_pull_label,):
                    pull_widget.bind("<ButtonPress-1>", _ada_sagdan_cek_basla)
                    pull_widget.bind("<B1-Motion>", _ada_sagdan_cek)
                    pull_widget.bind("<ButtonRelease-1>", _ada_sagdan_birak)
                    pull_widget.bind("<Double-Button-1>", _ada_cift_tik)
            except Exception:
                pass

            try:
                if not getattr(root, "_neto_now_playing_island_keys_bound", False):
                    for seq in ("<KeyPress-ccedilla>", "<KeyPress-Ccedilla>"):
                        try:
                            root.bind_all(seq, _ada_klavye_sistem, add="+")
                        except Exception:
                            pass
                    root._neto_now_playing_island_keys_bound = True
            except Exception:
                pass

            now_playing_dynamic_island_update(data)

            def _ada_giris(step=0):
                try:
                    if not now_playing_dynamic_island_alive():
                        return
                    steps = 16
                    progress = max(0.0, min(1.0, step / steps))
                    eased = 1.0 if step >= steps else 1.0 - ((1.0 - progress) ** 4)
                    y = round(-height + ((18 + height) * eased))
                    win.geometry(now_playing_dynamic_island_geometry(width, height, y))
                    try:
                        win.attributes("-alpha", 0.58 + (0.38 * min(1.0, max(0.0, eased))))
                    except Exception:
                        pass
                    if step < steps:
                        root.after(11, lambda: _ada_giris(step + 1))
                except Exception:
                    pass

            _ada_giris()
            return True
        except Exception as exc:
            try:
                now_playing_log(f"[DYNAMIC_ISLAND_OPEN_ERROR] {exc}")
            except Exception:
                pass
            return False

    def now_playing_dynamic_island_gecis(info=None):
        try:
            now_playing_dynamic_island_goster(info)
        except Exception:
            pass
        try:
            now_playing_overlay_kapat()
        except Exception:
            pass

    def now_playing_stable_poll_loop():
        """Stable live updater. Does not blink, does not recreate fullscreen."""
        try:
            if not now_playing_overlay_alive():
                return

            info = neto_now_playing.get_current_media(force_fresh=True)
            if info and not info.get("error") and info.get("title"):
                now_playing_sidebar_guncelle(info)
                now_playing_overlay_update(info)

            try:
                now_playing_volume_refresh()
            except Exception:
                pass

            try:
                root.after(
                    int(_neto_now_playing_interval("stable_poll_ms", 500)),
                    now_playing_stable_poll_loop,
                )
            except Exception:
                pass
        except Exception as e:
            try:
                now_playing_log(f"[STABLE_POLL_ERROR] {e}")
            except Exception:
                pass

    def now_playing_search_play_song(entry: Any = None, status_label: Any = None):
        """Find first result and PLAY it directly in YouTube Music. Non-blocking."""
        try:
            query = ""
            try:
                query = str(entry.get() if entry is not None else "").strip()
            except Exception:
                query = ""

            if not query:
                try:
                    if now_playing_widget_alive(status_label):
                        status_label.configure(text=now_playing_text("search_empty"), text_color="#ffb3b3")
                except Exception:
                    pass
                return

            try:
                if now_playing_widget_alive(status_label):
                    status_label.configure(text=now_playing_text("searching_song"), text_color=now_playing_ui_palette()["accent"])
            except Exception:
                pass

            def worker(q=query):
                try:
                    import neto_music_search
                    result = neto_music_search.search_and_play(q)

                    def update():
                        try:
                            if not now_playing_widget_alive(status_label):
                                return
                            if result.get("ok"):
                                title = result.get("title") or q
                                slot_msg = str(result.get("slot_message") or "").strip()
                                play_msg = now_playing_text("search_playing").format(query=title)
                                if slot_msg:
                                    play_msg = f"{slot_msg}  |  {play_msg}"
                                status_label.configure(text=play_msg, text_color=now_playing_ui_palette()["accent"])
                            else:
                                status_label.configure(text=f"{now_playing_text('search_error')}: {result.get('error','not found')}", text_color="#ffb3b3")
                        except Exception:
                            pass
                    try:
                        root.after(0, update)
                    except Exception:
                        pass
                except Exception as e:
                    def err_update(error=e):
                        try:
                            if now_playing_widget_alive(status_label):
                                status_label.configure(text=f"{now_playing_text('search_error')}: {error}", text_color="#ffb3b3")
                        except Exception:
                            pass
                    try:
                        root.after(0, err_update)
                    except Exception:
                        pass

            try:
                threading.Thread(target=worker, daemon=True).start()
            except Exception:
                worker()
        except Exception as e:
            try:
                print(f"[NOW_PLAYING_SEARCH_ERROR] {e}", flush=True)
            except Exception:
                pass

    def now_playing_place_overlay_window(win):
        """Place Now Playing on its assigned monitor, falling back to primary if missing."""
        try:
            if win is None or not bool(win.winfo_exists()):
                return False
            from neto_window_manager import display_index_for, place_window
            assignments = veri_yukle().get("neto_window_assignments")
            target_display = display_index_for(assignments, "now_playing")
            return bool(place_window(win, target_display, root, fullscreen=True))
        except Exception as exc:
            try:
                now_playing_log(f"[DISPLAY_PLACEMENT_ERROR] {exc}")
            except Exception:
                pass
            try:
                win.attributes("-fullscreen", False)
            except Exception:
                pass
            try:
                win.overrideredirect(True)
            except Exception:
                pass
            try:
                win.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0")
                return True
            except Exception:
                return False

    def now_playing_overlay_goster(info, force=False):
        """Open fullscreen once. On track change only update labels; never recreate."""
        global now_playing_overlay, now_playing_current_key, now_playing_hidden_until_key, now_playing_countdown_label, now_playing_end_time
        try:
            if not info or info.get("error") or not info.get("title"):
                return

            key = now_playing_info_key(info)
            if now_playing_hidden_until_key == key and not force:
                return

            # If overlay is already open, update in-place. No destroy, no blink.
            if now_playing_overlay_alive():
                now_playing_place_overlay_window(now_playing_overlay)
                now_playing_overlay_update(info)
                return

            title = str(info.get("title", "") or "").strip()
            artist = str(info.get("artist", "") or "").strip()
            app = str(info.get("app", "Unknown app") or "Unknown app").strip()
            if not title:
                return

            now_playing_current_key = key
            globals()["now_playing_current_info"] = info
            globals()["now_playing_monitor_last_info"] = info
            globals()["now_playing_last_info"] = info
            now_playing_save_last_media(info)
            now_playing_log(f"[OVERLAY_OPEN_STABLE] {key}")

            win: Any = ctk.CTkToplevel(root)
            now_playing_overlay = win

            # NETO_V24_NOW_PLAYING_REVEAL_SETUP
            try:
                from neto_runtime_policy_v2 import animation_mode as _neto_np_animation_mode
                _neto_np_motion_mode = _neto_np_animation_mode()
            except Exception:
                _neto_np_motion_mode = "normal"
            if _neto_np_motion_mode != "off":
                try:
                    win.attributes("-alpha", 0.0)
                except Exception:
                    pass
            now_playing_theme_widgets.clear()
            _np_pal = now_playing_ui_palette()
            win.title(now_playing_text("screen").title())
            win.configure(fg_color=_np_pal["bg"])
            try:
                win.attributes("-fullscreen", True)
                win.attributes("-topmost", True)
            except Exception:
                win.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0")
            now_playing_place_overlay_window(win)

            top = ctk.CTkFrame(win, fg_color="transparent")
            top.pack(fill="x", padx=28, pady=(24, 0))

            _np_screen_title = now_playing_widget_kaydet("screen_title", ctk.CTkLabel(
                top, text=now_playing_text("screen"), text_color=_np_pal["text"],
                font=("Segoe UI Semibold", 28)
            ), "title")
            _np_screen_title.pack(side="left")

            _np_close = now_playing_widget_kaydet("close", ctk.CTkButton(
                top, text="✕", width=48, height=40, corner_radius=14,
                fg_color=_np_pal["card"], hover_color=_np_pal["hover"],
                text_color=_np_pal["text"], command=now_playing_overlay_kapat
            ), "secondary")
            _np_close.pack(side="right")

            center = ctk.CTkFrame(win, fg_color="transparent")
            center.pack(expand=True, fill="both", padx=60, pady=30)

            globals()["now_playing_title_label"] = ctk.CTkLabel(
                center,
                text=title,
                text_color=_np_pal["text"],
                font=("Segoe UI Semibold", 46),
                wraplength=1100
            )
            globals()["now_playing_title_label"].pack(pady=(55, 12))
            now_playing_widget_kaydet("title", globals()["now_playing_title_label"], "title")

            globals()["now_playing_artist_label"] = ctk.CTkLabel(
                center,
                text=artist if artist else now_playing_text("artist_missing"),
                text_color=_np_pal["dim"],
                font=("Segoe UI", 24),
                wraplength=1000
            )
            globals()["now_playing_artist_label"].pack(pady=(0, 10))
            now_playing_widget_kaydet("artist", globals()["now_playing_artist_label"], "dim")

            globals()["now_playing_source_label"] = ctk.CTkLabel(
                center,
                text=f"{now_playing_text('source')}: {app}",
                text_color=_np_pal["dim"],
                font=("Segoe UI", 18)
            )
            globals()["now_playing_source_label"].pack(pady=(0, 6))
            now_playing_widget_kaydet("source", globals()["now_playing_source_label"], "dim")

            globals()["now_playing_status_label"] = ctk.CTkLabel(
                center,
                text=f"{now_playing_text('status')}: {now_playing_status_text_from_info(info)}",
                text_color=_np_pal["accent"],
                font=("Segoe UI Semibold", 16)
            )
            globals()["now_playing_status_label"].pack(pady=(0, 6))
            now_playing_widget_kaydet("status", globals()["now_playing_status_label"], "accent_text")

            globals()["now_playing_visual_frame"] = ctk.CTkFrame(
                center, fg_color=_np_pal["card"], corner_radius=18,
                border_width=2, border_color=_np_pal["accent"],
            )
            globals()["now_playing_visual_frame"].pack(fill="x", padx=0, pady=(8, 10))
            now_playing_widget_kaydet("visual_frame", globals()["now_playing_visual_frame"], "accent_frame")
            now_playing_render_visual()

            controls = ctk.CTkFrame(center, fg_color="transparent")
            controls.pack(pady=(4, 14))

            _np_prev = now_playing_widget_kaydet("prev", ctk.CTkButton(
                controls, text="⏮", width=58, height=42, corner_radius=14,
                fg_color=_np_pal["card"], hover_color=_np_pal["hover"],
                text_color=_np_pal["text"], command=now_playing_prev_track
            ), "secondary")
            _np_prev.pack(side="left", padx=6)

            _np_play = now_playing_widget_kaydet("play", ctk.CTkButton(
                controls, text=f"▶ / ⏸ {now_playing_text('play_pause')}",
                width=190, height=42, corner_radius=14,
                fg_color=_np_pal["accent"], hover_color=_np_pal["accent_hover"],
                text_color=_np_pal["accent_text"], command=now_playing_play_pause
            ), "primary")
            _np_play.pack(side="left", padx=6)

            _np_next = now_playing_widget_kaydet("next", ctk.CTkButton(
                controls, text="⏭", width=58, height=42, corner_radius=14,
                fg_color=_np_pal["card"], hover_color=_np_pal["hover"],
                text_color=_np_pal["text"], command=now_playing_next_track
            ), "secondary")
            _np_next.pack(side="left", padx=6)

            _np_refresh = now_playing_widget_kaydet("refresh", ctk.CTkButton(
                controls, text=f"🔄 {now_playing_text('refresh')}",
                width=110, height=42, corner_radius=14,
                fg_color=_np_pal["card"], hover_color=_np_pal["hover"],
                text_color=_np_pal["text"], command=lambda: now_playing_manual_open(force=True)
            ), "secondary")
            _np_refresh.pack(side="left", padx=6)

            globals()["now_playing_visual_mode_button"] = now_playing_widget_kaydet("visual_mode", ctk.CTkButton(
                controls,
                text=now_playing_text("switch_to_wave") if now_playing_visual_mode_get() == "vinyl" else now_playing_text("switch_to_vinyl"),
                width=150, height=42, corner_radius=14,
                fg_color=_np_pal["card"], hover_color=_np_pal["hover"],
                text_color=_np_pal["text"], command=now_playing_visual_mode_toggle
            ), "secondary")
            globals()["now_playing_visual_mode_button"].pack(side="left", padx=6)

            _np_island = now_playing_widget_kaydet("dynamic_island", ctk.CTkButton(
                controls,
                text=now_playing_text("dynamic_island"),
                width=138,
                height=42,
                corner_radius=14,
                fg_color=_np_pal["accent"],
                hover_color=_np_pal["accent_hover"],
                text_color=_np_pal["accent_text"],
                command=lambda current=info: now_playing_dynamic_island_gecis(globals().get("now_playing_current_info") or current),
            ), "primary")
            _np_island.pack(side="left", padx=6)

            _np_scratch_hint = now_playing_widget_kaydet("scratch_hint", ctk.CTkLabel(
                center, text=now_playing_text("scratch_hint"), text_color=_np_pal["dim"],
                font=("Segoe UI", 12), wraplength=900
            ), "dim")
            _np_scratch_hint.pack(pady=(0, 8))


            # Song search inside Now Playing
            search_box = ctk.CTkFrame(center, fg_color="transparent")
            search_box.pack(pady=(0, 10))

            globals()["now_playing_search_entry"] = ctk.CTkEntry(
                search_box,
                width=460,
                height=40,
                corner_radius=14,
                placeholder_text=now_playing_text("search_placeholder"),
                fg_color=_np_pal["entry"],
                border_color=_np_pal["border"],
                text_color=_np_pal["text"]
            )
            globals()["now_playing_search_entry"].pack(side="left", padx=(0, 8))
            now_playing_widget_kaydet("search_entry", globals()["now_playing_search_entry"], "entry")

            globals()["now_playing_search_status"] = ctk.CTkLabel(
                center,
                text=now_playing_text("search_hint"),
                text_color=_np_pal["dim"],
                font=("Segoe UI", 12),
                wraplength=900
            )
            globals()["now_playing_search_status"].pack(pady=(0, 8))
            now_playing_widget_kaydet("search_status", globals()["now_playing_search_status"], "dim")

            _np_search_button = now_playing_widget_kaydet("search_button", ctk.CTkButton(
                search_box, text=f"▶ {now_playing_text('search_play')}",
                width=115, height=40, corner_radius=14,
                fg_color=_np_pal["accent"], hover_color=_np_pal["accent_hover"],
                text_color=_np_pal["accent_text"],
                command=lambda e=globals()["now_playing_search_entry"], s=globals()["now_playing_search_status"]: now_playing_search_play_song(e, s)
            ), "primary")
            _np_search_button.pack(side="left")

            try:
                globals()["now_playing_search_entry"].bind(
                    "<Return>",
                    lambda event, e=globals()["now_playing_search_entry"], s=globals()["now_playing_search_status"]: now_playing_search_play_song(e, s)
                )
            except Exception:
                pass

            # Volume inside Now Playing
            volume_box = ctk.CTkFrame(center, fg_color="transparent")
            volume_box.pack(pady=(0, 12))

            globals()["now_playing_volume_label"] = ctk.CTkLabel(
                volume_box,
                text=f"🔊 {volume_text('label')}: --%",
                text_color=_np_pal["text"],
                font=("Segoe UI Semibold", 15)
            )
            globals()["now_playing_volume_label"].pack(pady=(0, 6))
            now_playing_widget_kaydet("volume_label", globals()["now_playing_volume_label"], "title")

            globals()["now_playing_volume_slider"] = ctk.CTkSlider(
                volume_box,
                from_=0,
                to=100,
                number_of_steps=100,
                width=360,
                progress_color=_np_pal["accent"],
                button_color=_np_pal["accent"],
                button_hover_color=_np_pal["accent_hover"],
                fg_color=_np_pal["border"],
                command=now_playing_volume_set
            )
            globals()["now_playing_volume_slider"].pack()
            now_playing_widget_kaydet("volume_slider", globals()["now_playing_volume_slider"], "slider")

            ctk.CTkLabel(
                volume_box,
                text=(volume_text("backend_pycaw") if volume_backend_name() == "pycaw" else (volume_text("backend_ctypes") if volume_backend_name() == "ctypes" else volume_text("backend_missing"))),
                text_color=_np_pal["dim"],
                font=("Segoe UI", 11)
            ).pack(pady=(5, 0))

            try:
                now_playing_volume_refresh()
            except Exception:
                pass

            sure = now_playing_get_max_seconds()
            sure_yazi = f"{sure // 60} min" if sure >= 60 and now_playing_lang() != "tr" else f"{sure // 60} dk" if sure >= 60 else f"{sure} sec" if now_playing_lang() != "tr" else f"{sure} sn"
            ctk.CTkLabel(
                center,
                text=f"{now_playing_text('auto_close')}: {sure_yazi} | {now_playing_text('close_hint')}",
                text_color=_np_pal["dim"],
                font=("Segoe UI", 13)
            ).pack(pady=(8, 0))

            now_playing_end_time = time.time() + sure
            now_playing_countdown_label = ctk.CTkLabel(
                center,
                text=f"{now_playing_text('countdown')}: --:--",
                text_color=_np_pal["accent"],
                font=("Segoe UI Semibold", 16)
            )
            now_playing_countdown_label.pack(pady=(8, 0))
            now_playing_widget_kaydet("countdown", now_playing_countdown_label, "accent_text")
            now_playing_countdown_loop()
            now_playing_theme_apply()

            _np_idle_now = time.time()
            globals()["now_playing_idle_last_activity"] = _np_idle_now
            globals()["now_playing_idle_deadline"] = _np_idle_now + max(1, now_playing_idle_seconds())
            now_playing_idle_bind_activity(win)
            now_playing_idle_watchdog()


            # NETO_V24_NOW_PLAYING_REVEAL_START
            try:
                from neto_motion_engine_v2 import get_motion_engine as _neto_np_get_motion_engine
                _neto_np_motion = _neto_np_get_motion_engine(root)
                _neto_np_motion.cancel("now-playing-popup-fade")
                _neto_np_motion.cancel("now-playing-popup-rise")

                if _neto_np_motion_mode == "off":
                    try:
                        win.attributes("-alpha", 1.0)
                    except Exception:
                        pass
                    try:
                        center.pack_configure(pady=30)
                    except Exception:
                        pass
                else:
                    _neto_np_start_pad = 64 if _neto_np_motion_mode == "normal" else 44
                    try:
                        center.pack_configure(pady=(_neto_np_start_pad, 30))
                    except Exception:
                        pass

                    _neto_np_motion.fade_toplevel(
                        win,
                        start=0.0,
                        end=1.0,
                        duration_ms=245,
                    )

                    def _neto_np_rise_update(progress):
                        try:
                            top_pad = round(_neto_np_start_pad + ((30 - _neto_np_start_pad) * float(progress)))
                            center.pack_configure(pady=(top_pad, 30))
                        except Exception:
                            pass

                    _neto_np_motion.tween(
                        "now-playing-popup-rise",
                        320,
                        _neto_np_rise_update,
                        easing="fluid_out",
                    )
            except Exception:
                try:
                    win.attributes("-alpha", 1.0)
                except Exception:
                    pass
                try:
                    center.pack_configure(pady=30)
                except Exception:
                    pass

            try:
                now_playing_stable_poll_loop()
            except Exception:
                pass

            win.after(sure * 1000, now_playing_overlay_kapat)

        except Exception as e:
            msg = str(e)
            if "bad window path name" not in msg:
                try:
                    print(f"[NOW_PLAYING] overlay error: {e}", flush=True)
                    now_playing_log(f"[OVERLAY_ERROR] {e}")
                except Exception:
                    pass

    def _now_playing_queue_latest(kind, payload=None):
        """Worker sonucunu kuyruğa koyar; eski sonuçları biriktirmez."""
        try:
            q = now_playing_monitor_queue
            while q.full():
                try:
                    q.get_nowait()
                except Exception:
                    break
            q.put_nowait((kind, payload, time.time()))
        except Exception:
            pass

    def now_playing_monitor_loop():
        """Yalnızca medya algılar. Tk widget'larına bu thread içinden dokunmaz."""
        misses = 0
        last_error_print = 0.0
        while not now_playing_monitor_stop.is_set():
            try:
                info = neto_now_playing.get_current_media(force_fresh=True)
                if now_playing_media_info_valid_basic(info):
                    misses = 0
                    _now_playing_queue_latest("media", dict(info))
                    wait_s = _neto_now_playing_interval("monitor_active_wait_s", 0.35)
                else:
                    if info and str(info.get("title") or "").strip():
                        try:
                            now_playing_log(f"[DETECTION_IGNORED_PLACEHOLDER] {info}")
                        except Exception:
                            pass
                    misses += 1
                    # Tek anlık Windows Media Session boşluğunda ekranı titreştirme.
                    # Yaklaşık 1-2 saniye üst üste sonuç yoksa eski şarkıyı temizle.
                    if misses >= 2:
                        _now_playing_queue_latest("clear", None)
                    wait_s = _neto_now_playing_interval("monitor_idle_wait_s", 0.55)

                if info and info.get("error") and time.time() - last_error_print > 30:
                    last_error_print = time.time()
                    now_playing_log(f"[DETECTION_ERROR] {info.get('error')}")

                now_playing_monitor_stop.wait(wait_s)
            except Exception as e:
                try:
                    now_playing_log(f"[MONITOR_ERROR] {e}")
                except Exception:
                    pass
                now_playing_monitor_stop.wait(
                    _neto_now_playing_interval("monitor_error_wait_s", 1.0)
                )

    def now_playing_ui_pump():
        """Kuyruktaki en yeni medya sonucunu güvenli biçimde Tk ana thread'inde uygular."""
        global now_playing_last_key, now_playing_current_key
        global now_playing_monitor_last_info, now_playing_monitor_last_seen, now_playing_ui_pump_job
        latest = None
        try:
            while True:
                latest = now_playing_monitor_queue.get_nowait()
        except queue.Empty:
            pass
        except Exception:
            pass

        try:
            if latest:
                kind, info, event_time = latest
                if kind == "media" and info:
                    key = now_playing_info_key(info)
                    previous_key = now_playing_last_key
                    now_playing_monitor_last_info = info
                    globals()["now_playing_current_info"] = info
                    globals()["now_playing_last_info"] = info
                    now_playing_monitor_last_seen = event_time
                    now_playing_save_last_media(info)
                    now_playing_sidebar_guncelle(info)

                    if now_playing_overlay_alive():
                        now_playing_overlay_update(info)
                        if now_playing_idle_active:
                            now_playing_idle_apply_info(info)

                    if key:
                        now_playing_current_key = key
                        now_playing_last_key = key

                    if key and key != previous_key:
                        now_playing_log(f"[TRACK_CHANGED] {previous_key!r} -> {key!r}")
                        if now_playing_auto_fullscreen_enabled() and not now_playing_overlay_alive():
                            now_playing_overlay_goster(info, force=False)

                elif kind == "clear":
                    # Yeni bir medya sonucu kuyrukta bunun arkasından geldiyse clear uygulanmaz;
                    # zaten yalnızca en yeni olay işlendiği için burada güvenle temizlenebilir.
                    now_playing_monitor_last_info = None
                    now_playing_monitor_last_seen = 0.0
                    now_playing_last_key = None
                    now_playing_current_key = None
                    now_playing_sidebar_guncelle(None)
                    if now_playing_overlay_alive():
                        empty_info = {
                            "title": now_playing_text("no_track"),
                            "artist": now_playing_text("not_found"),
                            "album": "",
                            "publisher": "NetOps",
                            "app": "Windows Media Session",
                            "source": "monitor",
                            "playback_status": "stopped",
                        }
                        now_playing_overlay_update(empty_info)
        except Exception as e:
            try:
                now_playing_log(f"[UI_PUMP_ERROR] {e}")
            except Exception:
                pass

        try:
            if root.winfo_exists() and not now_playing_monitor_stop.is_set():
                now_playing_ui_pump_job = root.after(
                    int(_neto_now_playing_interval("ui_pump_ms", 120)),
                    now_playing_ui_pump,
                )
        except Exception:
            pass

    def now_playing_monitor_baslat():
        global now_playing_monitor_started, now_playing_monitor_thread, now_playing_ui_pump_job
        try:
            if now_playing_monitor_thread and now_playing_monitor_thread.is_alive():
                return True
            now_playing_monitor_stop.clear()
            now_playing_monitor_thread = threading.Thread(
                target=now_playing_monitor_loop,
                name="NetoNowPlayingMonitor",
                daemon=True,
            )
            now_playing_monitor_thread.start()
            now_playing_monitor_started = True
            if not now_playing_ui_pump_job:
                now_playing_ui_pump_job = root.after(
                    max(16, int(_neto_now_playing_interval("ui_pump_ms", 120) * 0.66)),
                    now_playing_ui_pump,
                )
            print("[NOW_PLAYING] otomatik izleyici başladı", flush=True)
            return True
        except Exception as e:
            now_playing_monitor_started = False
            try:
                now_playing_log(f"[MONITOR_START_ERROR] {e}")
            except Exception:
                pass
            return False


    # ------------------------------------------------------------
    # NOW PLAYING MISSING FUNCTIONS HOTFIX v10.20
    # These functions must exist globally before overlay/manual click is used.
    # ------------------------------------------------------------
    def now_playing_info_key(info):
        """Stable key used to detect track changes and open/update the overlay."""
        try:
            if not info:
                return None
            app = str(info.get("app", "") or "")
            artist = str(info.get("artist", "") or "")
            title = str(info.get("title", "") or "")
            album = str(info.get("album", "") or "")
            return f"{app}|{artist}|{title}|{album}".strip()
        except Exception:
            return None

    def now_playing_safe_media_call(fn_name):
        try:
            fn = getattr(neto_now_playing, fn_name, None)
            if fn:
                return fn()
        except Exception as e:
            try:
                now_playing_log(f"[MEDIA_CONTROL_ERROR] {fn_name}: {e}")
            except Exception:
                pass
        return None

    def now_playing_play_pause(refresh_overlay=True):
        """Global media play/pause. Falls back silently if unsupported."""
        try:
            sonuc = now_playing_safe_media_call("media_play_pause")
            if not sonuc:
                try:
                    if pyautogui is not None:
                        pyautogui.press("playpause")
                    elif os.name == "nt":
                        ctypes.windll.user32.keybd_event(0xB3, 0, 0, 0)
                        ctypes.windll.user32.keybd_event(0xB3, 0, 2, 0)
                except Exception:
                    pass
            if refresh_overlay:
                try:
                    root.after(600, lambda: now_playing_manual_open(force=True))
                except Exception:
                    pass
        except Exception as e:
            try:
                now_playing_log(f"[PLAY_PAUSE_ERROR] {e}")
            except Exception:
                pass

    def now_playing_next_track():
        try:
            now_playing_safe_media_call("media_next")
            try:
                root.after(800, lambda: now_playing_manual_open(force=True))
            except Exception:
                pass
        except Exception as e:
            try:
                now_playing_log(f"[NEXT_ERROR] {e}")
            except Exception:
                pass

    def now_playing_prev_track():
        try:
            now_playing_safe_media_call("media_previous")
            try:
                root.after(800, lambda: now_playing_manual_open(force=True))
            except Exception:
                pass
        except Exception as e:
            try:
                now_playing_log(f"[PREV_ERROR] {e}")
            except Exception:
                pass


    crash_guard.boot("root oluşturulmadan önce")

    # Tema, CTk root oluşturulmadan önce hazırlanır. Böylece uygulama açılırken
    # bütün pencereyi koyudan açığa (veya tersine) yeniden çizme maliyeti oluşmaz.
    baslangic_ayar = veri_yukle()
    if baslangic_ayar.get("dil") in DIL_METINLERI:
        APP_LANG = baslangic_ayar.get("dil")
    tema_uygula(baslangic_ayar.get("tema", "dark"), baslangic_ayar.get("renk_temasi", "green"))

    # ------------------------------------------------------------
    # NOW PLAYING SAFE START v10.23
    # Auto monitor is disabled at startup to prevent silent launch crashes.
    # ------------------------------------------------------------
    def now_playing_safe_start():
        """Arka plan algılayıcısını yalnızca bir kez başlatır; kullanıcı tıklaması gerekmez."""
        try:
            fn = globals().get("now_playing_monitor_baslat")
            if callable(fn):
                ok = bool(fn())
                try:
                    btn = globals().get("btn_now_playing_baslat")
                    if btn:
                        btn.configure(text=now_playing_text("open_button"), command=lambda: now_playing_manual_open(force=True))
                except Exception:
                    pass
                return ok
        except Exception as e:
            try:
                now_playing_log(f"[AUTO_START_ERROR] {e}")
            except Exception:
                pass
        return False


    root = ctk.CTk()
    crash_guard.boot("root oluşturuldu")
    crash_guard.install_tk(root)
    root.title(T("app_title"))
    # Özel üst çubuk, eski Windows başlık çubuğunun yerine uygulamanın içinde yer alır.
    # İçerik yüksekliği küçülmesin diye pencere yüksekliği 44 px artırıldı.
    root.geometry("950x694")
    root.minsize(520, 644)
    root.configure(fg_color=aktif_palet["bg"])
    try:
        root.overrideredirect(True)
    except Exception:
        pass
    try:
        _ico = ICO_PATH if os.path.exists(ICO_PATH) else neto_safe_startup_logo_path()
        if _ico and os.path.exists(_ico) and _ico.lower().endswith(".ico"):
            root.iconbitmap(_ico)
    except Exception:
        pass

    # ------------------------------------------------------------
    # NETO CUSTOM TITLE BAR v14.8
    # - Vurgu rengine bağlı animasyonlu kapatma düğmesi
    # - Native Windows sürükleme / Snap / büyütme davranışı
    # - Küçült, büyüt/geri al ve kapat kontrolleri
    # - Daha belirgin Neto logosu ve vurgu çizgisi
    # ------------------------------------------------------------
    NETO_TITLEBAR_HEIGHT = 44
    _neto_titlebar_state = {
        "closing": False,
        "maximized": False,
        "jobs": {},
        "button_colors": {},
        "intro_job": None,
        "native_drag_job": None,
        "tray_info": False,
    }

    def _neto_titlebar_hwnd():
        if os.name != "nt":
            return 0
        try:
            import ctypes
            client = int(root.winfo_id())
            parent = int(ctypes.windll.user32.GetParent(client))
            return parent or client
        except Exception:
            return 0

    _neto_windows_icon_handles = {}

    def _neto_apply_windows_icon():
        """Set the real Win32 window icons used by the taskbar and Alt+Tab."""
        if os.name != "nt":
            return
        try:
            import ctypes
            from ctypes import wintypes

            hwnd = int(_neto_titlebar_hwnd() or 0)
            icon_path = ICO_PATH if os.path.exists(ICO_PATH) else neto_safe_startup_logo_path()
            if not hwnd or not icon_path or not os.path.exists(icon_path):
                return

            user32 = ctypes.WinDLL("user32", use_last_error=True)
            load_image = user32.LoadImageW
            load_image.argtypes = (
                wintypes.HINSTANCE,
                wintypes.LPCWSTR,
                wintypes.UINT,
                ctypes.c_int,
                ctypes.c_int,
                wintypes.UINT,
            )
            load_image.restype = wintypes.HANDLE
            send_message = user32.SendMessageW
            send_message.argtypes = (
                wintypes.HWND,
                wintypes.UINT,
                wintypes.WPARAM,
                wintypes.LPARAM,
            )
            send_message.restype = ctypes.c_ssize_t

            IMAGE_ICON = 1
            LR_LOADFROMFILE = 0x00000010
            LR_DEFAULTSIZE = 0x00000040
            WM_SETICON = 0x0080
            ICON_SMALL = 0
            ICON_BIG = 1
            flags = LR_LOADFROMFILE | LR_DEFAULTSIZE

            handles = _neto_windows_icon_handles
            if handles.get("path") != icon_path:
                handles.clear()
                handles["path"] = icon_path
                handles["small"] = load_image(None, icon_path, IMAGE_ICON, 16, 16, flags)
                handles["big"] = load_image(None, icon_path, IMAGE_ICON, 32, 32, flags)

            if handles.get("small"):
                send_message(hwnd, WM_SETICON, ICON_SMALL, handles["small"])
            if handles.get("big"):
                send_message(hwnd, WM_SETICON, ICON_BIG, handles["big"])
        except Exception as exc:
            try:
                crash_guard.log(f"[WINDOW_ICON_ERROR] {exc}")
            except Exception:
                pass

    def _neto_titlebar_apply_native_style():
        """Başlıksız görünümü korurken görev çubuğu, resize ve Windows Snap'i geri getirir."""
        if os.name != "nt":
            return
        try:
            import ctypes
            hwnd = _neto_titlebar_hwnd()
            if not hwnd:
                return
            GWL_STYLE = -16
            GWL_EXSTYLE = -20
            WS_CAPTION = 0x00C00000
            WS_THICKFRAME = 0x00040000
            WS_MINIMIZEBOX = 0x00020000
            WS_MAXIMIZEBOX = 0x00010000
            WS_SYSMENU = 0x00080000
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_APPWINDOW = 0x00040000
            SWP_NOSIZE = 0x0001
            SWP_NOMOVE = 0x0002
            SWP_NOZORDER = 0x0004
            SWP_NOACTIVATE = 0x0010
            SWP_FRAMECHANGED = 0x0020
            style = int(ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE))
            style &= ~WS_CAPTION
            style |= WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, style)
            exstyle = int(ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE))
            exstyle &= ~WS_EX_TOOLWINDOW
            exstyle |= WS_EX_APPWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, exstyle)
            ctypes.windll.user32.SetWindowPos(
                hwnd, 0, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED,
            )
            _neto_apply_windows_icon()
            # Windows 11 yuvarlak pencere köşeleri. Desteklenmeyen sistemlerde sessizce geçilir.
            try:
                preference = ctypes.c_int(2)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, 33, ctypes.byref(preference), ctypes.sizeof(preference)
                )
            except Exception:
                pass
        except Exception as exc:
            try:
                print(f"[TITLEBAR_STYLE_ERROR] {exc}", flush=True)
            except Exception:
                pass

    def _neto_titlebar_is_maximized():
        if os.name == "nt":
            try:
                import ctypes
                hwnd = _neto_titlebar_hwnd()
                return bool(hwnd and ctypes.windll.user32.IsZoomed(hwnd))
            except Exception:
                pass
        try:
            return str(root.state()).lower() == "zoomed"
        except Exception:
            return bool(_neto_titlebar_state.get("maximized"))

    def _neto_titlebar_sync_max_icon():
        maximized = _neto_titlebar_is_maximized()
        _neto_titlebar_state["maximized"] = maximized
        try:
            titlebar_max_btn.configure(text="❐" if maximized else "□")
        except Exception:
            pass
        # Neto Experience 3.0 (v1.40 eklentisi - YALNIZCA EKLEME):
        # metin sembolu yerine gercek Segoe Fluent ikonu. Ayar kapaliysa
        # apply_symbol_icon hicbir sey yapmaz ve yukaridaki semboller kalir.
        try:
            import neto_experience3 as _nx3_tb
            for _nx3_btn in (titlebar_max_btn, titlebar_min_btn, titlebar_close_btn, titlebar_quick_btn):
                _nx3_tb.apply_symbol_icon(_nx3_btn)
        except Exception:
            pass

    def _neto_titlebar_minimize():
        try:
            if os.name == "nt":
                import ctypes
                hwnd = _neto_titlebar_hwnd()
                if hwnd:
                    ctypes.windll.user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
                    return
            root.iconify()
        except Exception:
            pass

    def _neto_titlebar_toggle_maximize(event=None):
        try:
            if os.name == "nt":
                import ctypes
                hwnd = _neto_titlebar_hwnd()
                if hwnd:
                    ctypes.windll.user32.ShowWindow(hwnd, 9 if _neto_titlebar_is_maximized() else 3)
                else:
                    root.state("normal" if _neto_titlebar_is_maximized() else "zoomed")
            else:
                root.state("normal" if _neto_titlebar_is_maximized() else "zoomed")
        except Exception:
            try:
                root.state("normal" if _neto_titlebar_is_maximized() else "zoomed")
            except Exception:
                pass
        try:
            root.after(40, _neto_titlebar_sync_max_icon)
        except Exception:
            pass
        return "break"

    def _neto_titlebar_drag_start(event):
        # Native sürükleme mevcut Tk callback'i bittikten sonra asenkron başlatılır.
        try:
            if root is None or not bool(int(root.winfo_exists())):
                return "break"
            event_widget = getattr(event, "widget", None)
            if event_widget is not None and not bool(int(event_widget.winfo_exists())):
                return "break"
            _neto_titlebar_state["drag_x"] = int(event.x_root - root.winfo_x())
            _neto_titlebar_state["drag_y"] = int(event.y_root - root.winfo_y())
        except (tk.TclError, RuntimeError, AttributeError, TypeError, ValueError):
            return "break"
        except Exception as exc:
            crash_guard.log(f"[TITLEBAR_DRAG_PREPARE_ERROR] {exc}")
            return "break"

        if os.name != "nt":
            return None

        hwnd = int(_neto_titlebar_hwnd() or 0)
        if not hwnd:
            return None

        try:
            old_job = _neto_titlebar_state.get("native_drag_job")
            if old_job:
                root.after_cancel(old_job)
        except (tk.TclError, RuntimeError, AttributeError):
            pass

        def _neto_begin_native_drag(target_hwnd=hwnd):
            _neto_titlebar_state["native_drag_job"] = None
            try:
                import ctypes
                from ctypes import wintypes

                if root is None or not bool(int(root.winfo_exists())):
                    return
                user32 = ctypes.WinDLL("user32", use_last_error=True)
                release_capture = user32.ReleaseCapture
                release_capture.argtypes = ()
                release_capture.restype = wintypes.BOOL
                post_message = user32.PostMessageW
                post_message.argtypes = (
                    wintypes.HWND,
                    wintypes.UINT,
                    wintypes.WPARAM,
                    wintypes.LPARAM,
                )
                post_message.restype = wintypes.BOOL
                release_capture()
                if not post_message(target_hwnd, 0x00A1, 2, 0):
                    crash_guard.log(
                        f"[TITLEBAR_POST_MESSAGE_ERROR] winerror={ctypes.get_last_error()}"
                    )
            except (tk.TclError, RuntimeError, AttributeError):
                return
            except Exception as exc:
                crash_guard.log(f"[TITLEBAR_NATIVE_DRAG_ERROR] {exc}")

        try:
            _neto_titlebar_state["native_drag_job"] = root.after_idle(_neto_begin_native_drag)
        except (tk.TclError, RuntimeError, AttributeError) as exc:
            crash_guard.log(f"[TITLEBAR_DRAG_SCHEDULE_ERROR] {exc}")
        return "break"

    def _neto_titlebar_drag_motion(event):
        if os.name == "nt":
            return
        try:
            if _neto_titlebar_is_maximized():
                root.state("normal")
            x = int(event.x_root - _neto_titlebar_state.get("drag_x", 0))
            y = int(event.y_root - _neto_titlebar_state.get("drag_y", 0))
            root.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _neto_titlebar_cancel_job(name):
        from neto_motion_engine_v2 import get_motion_engine
        get_motion_engine(root).cancel(f"titlebar:{name}")

    def _neto_titlebar_button_anim(name, button, end_bg, end_text, end_border=None, steps=8):
        from neto_motion_engine_v2 import get_motion_engine
        from neto_widget_motion import color_value
        button._neto_custom_motion = True
        button.configure(hover=False)
        engine = get_motion_engine(root)
        options = {"fg_color": end_bg, "text_color": end_text}
        if end_border is not None:
            options["border_color"] = end_border
        starts = {key: color_value(button, button.cget(key)) for key in options}
        def update(progress):
            if not button.winfo_exists():
                engine.cancel(f"titlebar:{name}")
                return
            button.configure(**{key: _neto_hex_karistir(starts[key], value, progress)
                                for key, value in options.items()})
        engine.tween(f"titlebar:{name}", 140, update)

    def _neto_titlebar_control_enter(name, button):
        if name == "close":
            accent = aktif_palet["neon"]
            _neto_titlebar_button_anim(
                name, button, accent, _neto_kontrast_metin(accent), accent, steps=9
            )
        else:
            _neto_titlebar_button_anim(
                name, button, aktif_palet["card"], aktif_palet["text_main"], aktif_palet["entry_border"], steps=7
            )
        # Neto Experience 3.0 (v1.40 eklentisi - YALNIZCA EKLEME):
        # Kapat düğmesi hover'ı Windows 11 standardında kırmızı olur. Ayar
        # kapalıysa close_hover_colors() None döner ve yukarıdaki davranış kalır.
        try:
            import neto_experience3 as _nx3_ch
            _nx3_renk = _nx3_ch.close_hover_colors()
            if name == "close" and _nx3_renk:
                _neto_titlebar_button_anim(
                    name, button, _nx3_renk[0], _nx3_renk[1], _nx3_renk[0], steps=9
                )
        except Exception:
            pass

    def _neto_titlebar_control_leave(name, button):
        text_target = aktif_palet["neon"] if name == "close" else aktif_palet["text_dim"]
        border_target = aktif_palet["neon"] if name == "close" else aktif_palet["sidebar"]
        _neto_titlebar_button_anim(
            name, button, aktif_palet["sidebar"], text_target, border_target, steps=8
        )

    def _neto_pencereyi_goster():
        try:
            root.deiconify()
        except Exception:
            pass
        try:
            root.lift()
        except Exception:
            pass
        try:
            root.focus_force()
        except Exception:
            pass

    def _neto_tam_kapat():
        if _neto_titlebar_state.get("shutdown_started"):
            return
        _neto_titlebar_state["shutdown_started"] = True
        _neto_titlebar_state["closing"] = True
        try:
            live_mode_durdur()
        except Exception:
            pass
        _neto_timer_cancel()
        _neto_reminder_service_stop()
        try:
            _neto_tray_durdur()
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass

    def _neto_titlebar_close():
        if _neto_titlebar_state.get("closing"):
            return
        _neto_titlebar_state["closing"] = True
        accent = aktif_palet["neon"]
        flash = _neto_hex_karistir(accent, "#FFFFFF", 0.30)
        _neto_titlebar_button_anim(
            "close", titlebar_close_btn, flash, _neto_kontrast_metin(flash), flash, steps=5
        )
        def finish():
            _neto_tam_kapat()
        try:
            root.after(110, finish)
        except Exception:
            finish()

    titlebar = ctk.CTkFrame(
        root, height=NETO_TITLEBAR_HEIGHT, fg_color=aktif_palet["sidebar"],
        corner_radius=0, border_width=0
    )
    titlebar.pack(side="top", fill="x")
    titlebar.pack_propagate(False)

    titlebar_brand = ctk.CTkFrame(titlebar, fg_color="transparent", corner_radius=0)
    titlebar_brand.pack(side="left", fill="y", padx=(10, 0))

    _neto_titlebar_logo_image = None
    try:
        _tb_logo_path = get_asset_path("neto_titlebar_logo.png")
        if os.path.exists(_tb_logo_path):
            _neto_titlebar_logo_image = ctk.CTkImage(
                light_image=Image.open(_tb_logo_path).convert("RGBA"),
                dark_image=Image.open(_tb_logo_path).convert("RGBA"),
                size=(36, 36),
            )
    except Exception:
        _neto_titlebar_logo_image = None

    titlebar_logo = ctk.CTkLabel(
        titlebar_brand, text="" if _neto_titlebar_logo_image else "▲",
        image=_neto_titlebar_logo_image, width=38, height=38,
        text_color=aktif_palet["neon"], font=("Segoe UI Semibold", 22),
    )
    titlebar_logo.pack(side="left", padx=(0, 7), pady=3)

    titlebar_title = ctk.CTkLabel(
        titlebar_brand, text=APP_NAME, text_color=aktif_palet["text_main"],
        font=("Segoe UI Semibold", 13), anchor="w"
    )
    titlebar_title.pack(side="left", pady=(1, 0))
    titlebar_version = ctk.CTkLabel(
        titlebar_brand, text=APP_VERSION, text_color=aktif_palet["text_dim"],
        font=("Segoe UI", 10), anchor="w"
    )

    titlebar_version.pack(side="left", padx=(7, 0), pady=(3, 0))

    titlebar_controls = ctk.CTkFrame(titlebar, fg_color="transparent", corner_radius=0)
    titlebar_controls.pack(side="right", fill="y")

    def _make_titlebar_button(text, command, width=46, close=False):
        button = ctk.CTkButton(
            titlebar_controls, text=text, width=width, height=38, corner_radius=9,
            fg_color=aktif_palet["sidebar"], hover_color=aktif_palet["sidebar"],
            text_color=aktif_palet["neon"] if close else aktif_palet["text_dim"],
            border_width=1 if close else 0,
            border_color=aktif_palet["neon"] if close else aktif_palet["sidebar"],
            font=("Segoe UI Semibold", 16 if close else 15), command=command
        )
        # Titlebar buttons have their own color transition; avoid double binding.
        button._neto_custom_motion = True
        return button

    titlebar_min_btn = _make_titlebar_button("—", _neto_titlebar_minimize)
    titlebar_max_btn = _make_titlebar_button("□", _neto_titlebar_toggle_maximize)
    titlebar_close_btn = _make_titlebar_button("×", _neto_titlebar_close, width=52, close=True)
    titlebar_quick_btn = _make_titlebar_button("⚡", neto_quick_actions_penceresi_ac, width=42)
    titlebar_quick_btn.pack(side="left", padx=(1, 1), pady=3)
    titlebar_min_btn.pack(side="left", padx=(2, 1), pady=3)
    titlebar_max_btn.pack(side="left", padx=1, pady=3)
    titlebar_close_btn.pack(side="left", padx=(1, 5), pady=3)

    titlebar_accent_line = ctk.CTkFrame(
        titlebar, width=1, height=2, fg_color=aktif_palet["neon"], corner_radius=1
    )
    titlebar_accent_line.place(x=0, rely=1.0, relwidth=1.0, anchor="sw")

    # Ana uygulama yüzeyi titlebar'ın altında ayrı bir kapsayıcıda tutulur.
    app_content = ctk.CTkFrame(root, fg_color=aktif_palet["bg"], corner_radius=0)
    app_content.pack(side="top", fill="both", expand=True)

    for _drag_widget in (titlebar, titlebar_brand, titlebar_logo, titlebar_title, titlebar_version):
        try:
            _drag_widget.bind("<ButtonPress-1>", _neto_titlebar_drag_start)
            _drag_widget.bind("<B1-Motion>", _neto_titlebar_drag_motion)
            _drag_widget.bind("<Double-Button-1>", _neto_titlebar_toggle_maximize)
        except Exception:
            pass

    for _name, _button in (("quick", titlebar_quick_btn), ("min", titlebar_min_btn), ("max", titlebar_max_btn), ("close", titlebar_close_btn)):
        _neto_titlebar_state["button_colors"][_name] = {
            "bg": aktif_palet["sidebar"],
            "text": aktif_palet["neon"] if _name == "close" else aktif_palet["text_dim"],
            "border": aktif_palet["neon"] if _name == "close" else aktif_palet["sidebar"],
        }
        _button.bind("<Enter>", lambda e, n=_name, b=_button: _neto_titlebar_control_enter(n, b))
        _button.bind("<Leave>", lambda e, n=_name, b=_button: _neto_titlebar_control_leave(n, b))

    def _neto_titlebar_theme_refresh():
        try:
            titlebar.configure(fg_color=aktif_palet["sidebar"])
            app_content.configure(fg_color=aktif_palet["bg"])
            titlebar_title.configure(text_color=aktif_palet["text_main"])
            titlebar_version.configure(text_color=aktif_palet["text_dim"])
            titlebar_logo.configure(text_color=aktif_palet["neon"])
            titlebar_accent_line.configure(fg_color=aktif_palet["neon"])
            for name, button in (("quick", titlebar_quick_btn), ("min", titlebar_min_btn), ("max", titlebar_max_btn), ("close", titlebar_close_btn)):
                text = aktif_palet["neon"] if name == "close" else aktif_palet["text_dim"]
                border = aktif_palet["neon"] if name == "close" else aktif_palet["sidebar"]
                _neto_titlebar_state["button_colors"][name] = {
                    "bg": aktif_palet["sidebar"], "text": text, "border": border
                }
                button.configure(
                    fg_color=aktif_palet["sidebar"], hover_color=aktif_palet["sidebar"],
                    text_color=text, border_color=border
                )
        except Exception:
            pass

    def _neto_titlebar_intro(step=0):
        from neto_motion_engine_v2 import get_motion_engine
        engine = get_motion_engine(root)
        for button in (titlebar_close_btn, titlebar_min_btn, titlebar_max_btn):
            button._neto_custom_motion = True
        engine.color("titlebar-intro", titlebar_accent_line, "fg_color",
                     aktif_palet["sidebar"], aktif_palet["neon"], duration_ms=220)

    globals()["_neto_titlebar_theme_refresh"] = _neto_titlebar_theme_refresh
    globals()["_neto_titlebar_intro"] = _neto_titlebar_intro
    globals()["_neto_titlebar_apply_native_style"] = _neto_titlebar_apply_native_style

    try:
        root.protocol("WM_DELETE_WINDOW", _neto_titlebar_close)
        root.bind(
            "<Map>",
            lambda e: root.after(20, _neto_titlebar_apply_native_style) if e.widget == root else None,
            add="+",
        )
    except Exception:
        pass

    # Web/PWA ve tablet uyandırma köprüsü masaüstü ürününden çıkarıldı.
    # Eski Flask fonksiyonları geriye dönük kaynak olarak tutulur ancak normal
    # açılışta port dinlenmez ve hiçbir tarayıcı istemcisi başlatılmaz.

    # ------------------------------------------------------------
    # NETO STARTUP GATE v14.3
    # Ana pencere tamamen kurulana kadar gizli kalır. Giriş ekranı yalnızca
    # tek gerçek root.mainloop başladıktan sonra, non-blocking Toplevel olarak
    # gösterilir. wait_window / wait_variable / update / ikinci mainloop yoktur.
    # ------------------------------------------------------------
    NETO_LAUNCH_LOADING_WINDOW = None
    try:
        root.withdraw()
        root.attributes("-alpha", 1.0)
    except Exception:
        pass

    def _neto_launch_checkpoint(status=None, force=False):
        try:
            if status:
                print(f"[LAUNCH_BUILD] {status}", flush=True)
        except Exception:
            pass

    _neto_launch_checkpoint("Yerel web köprüsü devre dışı")
    _neto_launch_checkpoint(
        "Ana arayüz arka planda hazırlanıyor..." if str(dil_getir()).lower() == "tr" else "Preparing main interface in background...",
        force=True,
    )


    global side_panel, main_c, chat_container, input_container, giris_frame, not_alani
    global etiket, giris, btn_gonder, gif_ana_label, cpu_l, ram_l, btn_ayarlar, btn_gelismis, btn_anahtar, btn_netoai, btn_scenes, btn_updates, btn_dil, lbl_sistem_durumu, lbl_now_playing, lbl_now_playing_detay, lbl_notlar, lbl_sistem, lbl_magaza, lbl_welcome, compact_settings_btn
    btn_ayarlar = None
    btn_gelismis = None
    btn_updates = None
    btn_dil = None

    # ------------------------------------------------------------
    # ESKİ ARAYÜZ + HAMBURGER MINI EKRAN DÜZELTMESİ
    # - Eski sol panel düzeni korunur.
    # - Eklenti mağazası uygulamaları geri gelir.
    # - Küçük ekranda sol panel gizlenir.
    # - Hamburger'e basınca aynı sol panel açılır/kapanır.
    # ------------------------------------------------------------
    PANEL_WIDTH = 282
    MINI_LIMIT = 760
    sidebar_overlay_open = False
    mini_mode_active = False

    side_panel = ctk.CTkFrame(
        app_content,
        width=PANEL_WIDTH,
        fg_color=aktif_palet["sidebar"],
        corner_radius=18,
        border_width=1,
        border_color=aktif_palet["entry_border"],
    )
    side_panel.pack_propagate(False)

    # Sidebar''ın üstünde ayrı bir kontrol satırı: hamburger/X artık ana yüzeye
    # place edilmez ve içerik butonlarının üzerine taşamaz.
    sidebar_header = ctk.CTkFrame(
        side_panel,
        height=50,
        fg_color=aktif_palet["sidebar"],
        corner_radius=0,
    )
    sidebar_header.pack(fill="x", side="top")
    sidebar_header.pack_propagate(False)

    # Sol alttaki Ayarlar çubuğu içeriklerin üstüne binmesin diye menü gövdesi
    # ayrı ve kaydırılabilir tutulur. Alt 66 px yalnızca sabit Ayarlar sekmesine aittir.
    sidebar_content = ctk.CTkScrollableFrame(
        side_panel,
        width=PANEL_WIDTH,
        fg_color=aktif_palet["sidebar"],
        corner_radius=0,
        border_width=0,
        scrollbar_button_color=aktif_palet["card"],
        scrollbar_button_hover_color=aktif_palet["button_hover"],
    )
    sidebar_content.pack(fill="both", expand=True, pady=(0, 66))
    _neto_scrollable_frame_renklendir(sidebar_content, aktif_palet, "sidebar")

    agent_sidebar_content = ctk.CTkScrollableFrame(
        side_panel,
        width=PANEL_WIDTH,
        fg_color=aktif_palet["sidebar"],
        corner_radius=0,
        border_width=0,
        scrollbar_button_color=aktif_palet["card"],
        scrollbar_button_hover_color=aktif_palet["button_hover"],
    )
    _neto_scrollable_frame_renklendir(agent_sidebar_content, aktif_palet, "sidebar")
    agent_sidebar_content.pack_forget()

    sidebar_state = {
        "expanded": True,
        "job": None,
    }
    sidebar_compact_width = 104
    sidebar_brand = ctk.CTkFrame(side_panel, fg_color=aktif_palet["sidebar"], corner_radius=0)
    # Alt Ayarlar kapsülünün üstünde kalan NetOps marka satırı artık gösterilmiyor.
    sidebar_brand.pack_propagate(False)
    sidebar_brand.configure(height=82)

    sidebar_logo_image = None
    try:
        _sidebar_logo_path = get_asset_path("neto_titlebar_logo.png")
        if os.path.exists(_sidebar_logo_path):
            _sidebar_logo_img = Image.open(_sidebar_logo_path).convert("RGBA")
            sidebar_logo_image = ctk.CTkImage(
                light_image=_sidebar_logo_img,
                dark_image=_sidebar_logo_img,
                size=(52, 52),
            )
    except Exception:
        sidebar_logo_image = None

    sidebar_brand_logo = ctk.CTkLabel(
        sidebar_brand,
        text="" if sidebar_logo_image else "▲",
        image=sidebar_logo_image,
        width=56,
        height=56,
        text_color=aktif_palet["neon"],
        font=("Segoe UI Semibold", 24),
    )
    sidebar_brand_logo.pack(side="left", padx=(6, 10), pady=10)

    sidebar_brand_text_box = ctk.CTkFrame(sidebar_brand, fg_color="transparent")
    sidebar_brand_text_box.pack(side="left", fill="both", expand=True, pady=8)

    sidebar_brand_title = ctk.CTkLabel(
        sidebar_brand_text_box,
        text=APP_NAME,
        text_color=aktif_palet["text_main"],
        font=("Segoe UI Semibold", 15),
        anchor="w",
    )
    sidebar_brand_title.pack(fill="x")

    sidebar_brand_subtitle = ctk.CTkLabel(
        sidebar_brand_text_box,
        text=APP_VERSION,
        text_color=aktif_palet["text_dim"],
        font=("Segoe UI", 10),
        anchor="w",
    )
    sidebar_brand_subtitle.pack(fill="x")

    main_c = ctk.CTkFrame(app_content, fg_color=aktif_palet["bg"], corner_radius=0)
    _neto_launch_checkpoint("Sol menü hazırlanıyor..." if str(dil_getir()).lower() == "tr" else "Preparing sidebar...")

    # Hamburger menü üstte görünür kalır; tıklandığında sol menüyü ikon-rail ile
    # metinli görünüm arasında akıcı biçimde açıp kapatır.
    hamburger_btn = ctk.CTkButton(
        sidebar_header,
        text="☰",
        width=36,
        height=36,
        corner_radius=18,
        font=("Segoe UI", 20),
        fg_color="#17191F",
        hover_color="#242732",
        text_color="#D7DBE7",
        border_width=0,
        border_color="#17191F",
        command=lambda: hamburger_toggle(),
    )
    def _hamburger_konumla():
        """Keep the menu control in the sidebar header across every layout mode."""
        try:
            hamburger_btn.pack_configure(side="right", padx=(0, 8), pady=7)
            sidebar_header.lift()
        except Exception:
            try:
                hamburger_btn.pack(side="right", padx=(0, 8), pady=7)
            except Exception:
                pass
    _hamburger_konumla()

    def _button_style(btn):
        try:
            btn.configure(
                fg_color=aktif_palet["card"],
                hover_color=aktif_palet["button_hover"],
                text_color=aktif_palet["text_main"],
                border_width=0
            )
        except Exception:
            pass

    # --------------------
    # SOL PANEL İÇERİĞİ
    # --------------------
    _sidebar_metrics_ready = {"value": False}

    def _sidebar_istatistik_yaz(cpu_deger=None, ram_deger=None):
        if not K_PSUTIL:
            return
        try:
            compact = bool(sidebar_state.get("compact", False))
            if cpu_deger is None or ram_deger is None:
                if not _sidebar_metrics_ready["value"]:
                    measuring = "Ölçülüyor..." if str(dil_getir()).lower().startswith("tr") else "Measuring..."
                    if compact:
                        cpu_l.configure(text=f"CPU\n{measuring}")
                        ram_l.configure(text=f"RAM\n{measuring}")
                    else:
                        cpu_l.configure(text=f"CPU: {measuring}")
                        ram_l.configure(text=f"RAM: {measuring}")
                    return
                metrics = neto_system_metrics(force=False)
                cpu = float(metrics.get("cpu") or 0.0)
                ram = float(metrics.get("ram") or 0.0)
            else:
                _sidebar_metrics_ready["value"] = True
                cpu = float(cpu_deger)
                ram = float(ram_deger)
            if compact:
                cpu_l.configure(text=f"CPU\n%{cpu:.0f}")
                ram_l.configure(text=f"RAM\n%{ram:.0f}")
            else:
                cpu_l.configure(text=f"CPU: %{cpu:.0f}")
                ram_l.configure(text=f"RAM: %{ram:.0f}")
        except Exception:
            pass

    def istatistikleri_guncelle():
        if K_PSUTIL and side_panel.winfo_exists():
            try:
                metrics = neto_system_metrics(force=True)
                _sidebar_istatistik_yaz(metrics.get("cpu"), metrics.get("ram"))
            except Exception:
                pass
            root.after(2000, istatistikleri_guncelle)

    lbl_sistem_durumu = ctk.CTkLabel(
        sidebar_content,
        text=T("system_status"),
        text_color=aktif_palet["text_dim"],
        font=("Segoe UI Semibold", 13)
    )
    lbl_sistem_durumu.pack(pady=(20, 5))

    cpu_l = ctk.CTkLabel(
        sidebar_content,
        text=(
            "CPU: Ölçülüyor..."
            if str(dil_getir()).lower().startswith("tr")
            else "CPU: Measuring..."
        ),
        text_color=aktif_palet["text_main"],
        font=("Segoe UI Semibold", 12)
    )
    cpu_l.pack()

    ram_l = ctk.CTkLabel(
        sidebar_content,
        text=(
            "RAM: Ölçülüyor..."
            if str(dil_getir()).lower().startswith("tr")
            else "RAM: Measuring..."
        ),
        text_color=aktif_palet["text_main"],
        font=("Segoe UI Semibold", 12)
    )
    ram_l.pack()

    # v10.32: Volume control moved into Now Playing screen.


    lbl_now_playing = ctk.CTkLabel(
        sidebar_content,
        text=now_playing_text("none"),
        text_color=aktif_palet["neon"],
        font=("Segoe UI Semibold", 12),
        wraplength=230,
        justify="left",
        cursor="hand2"
    )
    lbl_now_playing.pack(pady=(8, 0), padx=18, fill="x")

    lbl_now_playing_detay = ctk.CTkLabel(
        sidebar_content,
        text="",
        text_color=aktif_palet["text_dim"],
        font=("Segoe UI", 11),
        wraplength=230,
        justify="left",
        cursor="hand2"
    )
    lbl_now_playing_detay.pack(pady=(2, 6), padx=18, fill="x")
    try:
        lbl_now_playing.bind("<Button-1>", lambda e: now_playing_manual_open(force=True))
        lbl_now_playing_detay.bind("<Button-1>", lambda e: now_playing_manual_open(force=True))
    except Exception:
        pass
    btn_now_playing_ayar = ctk.CTkButton(
        sidebar_content,
        text=now_playing_text("settings_short"),
        font=("Segoe UI Semibold", 11),
        fg_color=aktif_palet["card"],
        hover_color=aktif_palet["button_hover"],
        text_color=aktif_palet["text_main"],
        corner_radius=8,
        command=now_playing_open_settings_safe
    )
    btn_now_playing_ayar.pack(padx=20, fill="x", pady=(4, 4))

    btn_now_playing_baslat = ctk.CTkButton(
        sidebar_content,
        text=now_playing_text("open_button_short"),
        font=("Segoe UI Semibold", 11),
        fg_color=aktif_palet["card"],
        hover_color=aktif_palet["button_hover"],
        text_color=aktif_palet["text_main"],
        corner_radius=8,
        command=lambda: now_playing_manual_open(force=True)
    )
    btn_now_playing_baslat.pack(padx=20, fill="x", pady=(0, 8))

    if K_PSUTIL:
        # İlk psutil örneğini ana pencereyi kurarken değil, ölçüm metni görünürken al.
        root.after(120, istatistikleri_guncelle)

    lbl_notlar = ctk.CTkLabel(
        sidebar_content,
        text=T("notes"),
        text_color=aktif_palet["text_dim"],
        font=("Segoe UI Semibold", 13)
    )
    lbl_notlar.pack(pady=(15, 5))

    not_alani = ctk.CTkTextbox(
        sidebar_content,
        height=82,
        width=220,
        fg_color=aktif_palet["card"],
        text_color=aktif_palet["text_main"],
        corner_radius=12,
        border_width=0
    )
    not_alani.pack(padx=20, fill="x")

    lbl_sistem = ctk.CTkLabel(
        sidebar_content,
        text="Araçlar" if str(dil_getir()).lower().startswith("tr") else "Tools",
        text_color=aktif_palet["text_dim"],
        font=("Segoe UI Semibold", 13)
    )
    lbl_sistem.pack(pady=(15, 5))


    btn_netoai = ctk.CTkButton(
        sidebar_content,
        text=T("neto_ai"),
        font=("Segoe UI Semibold", 12),
        fg_color=aktif_palet["card"],
        hover_color=aktif_palet["button_hover"],
        corner_radius=8,
        command=neto_ai_baslat
    )
    btn_netoai.pack(padx=20, fill="x", pady=4)


    btn_android_device = ctk.CTkButton(
        sidebar_content,
        text=T("device_hub"),
        font=("Segoe UI Semibold", 12),
        fg_color=aktif_palet["card"],
        hover_color=aktif_palet["button_hover"],
        corner_radius=8,
        command=neto_device_hub_ac_safe
    )
    btn_android_device.pack(padx=20, fill="x", pady=4)
    btn_automation = ctk.CTkButton(
        sidebar_content,
        text="Otomasyon Merkezi",
        font=("Segoe UI Semibold", 12),
        fg_color=aktif_palet["card"],
        hover_color=aktif_palet["button_hover"],
        text_color=aktif_palet["text_main"],
        corner_radius=8,
        command=neto_otomasyon_merkezi_ac,
    )
    globals()["btn_automation"] = btn_automation
    btn_automation.pack(padx=20, fill="x", pady=4)

    btn_scenes = ctk.CTkButton(
        sidebar_content,
        text="Neto Hazırla",
        font=("Segoe UI Semibold", 12),
        fg_color=aktif_palet["card"],
        hover_color=aktif_palet["button_hover"],
        text_color=aktif_palet["text_main"],
        corner_radius=8,
        command=neto_sahneler_merkezi_ac,
    )
    btn_scenes.pack(padx=20, fill="x", pady=4, before=btn_automation)

    btn_profiles = ctk.CTkButton(
        sidebar_content,
        text="Profiller",
        font=("Segoe UI Semibold", 12),
        fg_color=aktif_palet["card"],
        hover_color=aktif_palet["button_hover"],
        text_color=aktif_palet["text_main"],
        corner_radius=8,
        command=netops_profiller_penceresi_ac,
    )
    btn_profiles.pack(padx=20, fill="x", pady=4)

    btn_reminders = ctk.CTkButton(
        sidebar_content,
        text="Hatırlatıcılar",
        font=("Segoe UI Semibold", 12),
        fg_color=aktif_palet["card"],
        hover_color=aktif_palet["button_hover"],
        text_color=aktif_palet["text_main"],
        corner_radius=8,
        command=netops_hatirlaticilar_penceresi_ac,
    )
    btn_reminders.pack(padx=20, fill="x", pady=4)



    def eklenti_durum_degis():
        global eklenti_aktif_mi
        if eklenti_aktif_mi:
            eklenti_aktif_mi = False
        else:
            eklenti_aktif_mi = True
        try:
            btn_anahtar.configure(
                fg_color="#00c46a" if eklenti_aktif_mi else "#b32424",
                hover_color="#00a85b" if eklenti_aktif_mi else "#8c1c1c",
                text_color="#000000" if eklenti_aktif_mi else "#ffffff",
            )
        except Exception:
            pass
        try:
            _sidebar_metinleri_yenile()
        except Exception:
            pass

    btn_anahtar = ctk.CTkButton(
        sidebar_content,
        text=T("extension_status_off"),
        font=("Segoe UI Semibold", 12),
        fg_color="#b32424",
        hover_color="#8c1c1c",
        corner_radius=8,
        command=eklenti_durum_degis
    )
    btn_anahtar.pack(padx=20, fill="x", pady=4)

    lbl_magaza = ctk.CTkLabel(
        sidebar_content,
        text=str(T("extension_store") or "Extension Store") + "  (Ctrl+E)",
        text_color=aktif_palet["text_dim"],
        font=("Segoe UI Semibold", 13)
    )
    lbl_magaza.pack(pady=(15, 5))

    # Eklenti mağazası uygulamaları geri eklendi.
    btn_store_panel = ctk.CTkButton(
        sidebar_content,
        text="Open Store  Ctrl+E",
        font=("Segoe UI Semibold", 11),
        fg_color=aktif_palet["neon"],
        hover_color=aktif_palet["button_hover"],
        text_color="#000000",
        corner_radius=8,
        height=30,
        command=lambda: eklenti_magazasi_panel_toggle()
    )
    btn_store_panel.pack(padx=20, fill="x", pady=(2, 6))

    # ------------------------------------------------------------
    # FIXED BOTTOM-LEFT SETTINGS / PROFILE BAR
    # Discord-like compact user bar. It remains at the bottom of the sidebar.
    # ------------------------------------------------------------
    # Bu alan profil değildir; doğrudan uygulama içi Ayarlar sekmesidir.
    _profile_name = "Ayarlar" if str(dil_getir()).lower().startswith("tr") else "Settings"
    _profile_initial = "⚙"
    _settings_subtitle = "Uygulama ayarları" if str(dil_getir()).lower().startswith("tr") else "App settings"

    settings_bottom_bar = ctk.CTkFrame(
        side_panel,
        height=58,
        width=PANEL_WIDTH,
        fg_color=aktif_palet["card"],
        corner_radius=26,
        border_width=1,
        border_color=aktif_palet["entry_border"],
        cursor="hand2",
    )
    settings_bottom_bar.pack_propagate(False)

    def _settings_bottom_bar_width():
        try:
            panel_width = int(sidebar_state.get("current_width") or side_panel.winfo_width() or side_panel.cget("width"))
        except Exception:
            panel_width = PANEL_WIDTH
        if panel_width <= 1:
            panel_width = PANEL_WIDTH
        if globals().get("_sidebar_icon_only_mode", False):
            return 34
        return max(84, panel_width - 20)

    def _settings_bottom_bar_place(x=10):
        try:
            width = _settings_bottom_bar_width()
            if globals().get("_sidebar_icon_only_mode", False):
                x = max(0, (int(side_panel.cget("width")) - width) // 2)
            settings_bottom_bar.place(
                x=int(x),
                rely=1.0,
                y=-10,
                anchor="sw",
            )
            settings_bottom_bar.place_configure(width=width)
        except Exception:
            try:
                settings_bottom_bar.place(
                    x=int(x),
                    rely=1.0,
                    y=-10,
                    anchor="sw",
                    width=_settings_bottom_bar_width(),
                )
            except Exception:
                pass

    _settings_bottom_bar_place()
    settings_bottom_bar.lift()

    settings_avatar = ctk.CTkLabel(
        settings_bottom_bar,
        text=_profile_initial,
        width=36,
        height=36,
        corner_radius=18,
        fg_color=aktif_palet["neon"],
        text_color=_tema_vurgu_metin_rengi(),
        font=("Segoe UI Semibold", 12),
        cursor="hand2",
    )
    settings_avatar.pack(side="left", padx=(12, 9), pady=11)

    settings_identity = ctk.CTkFrame(settings_bottom_bar, fg_color="transparent", cursor="hand2")
    settings_identity.pack(side="left", fill="both", expand=True, pady=8)

    settings_profile_name = ctk.CTkLabel(
        settings_identity,
        text=_profile_name,
        text_color=aktif_palet["text_main"],
        font=("Segoe UI Semibold", 12),
        anchor="w",
        cursor="hand2",
    )
    settings_profile_name.pack(fill="x")

    settings_title_label = ctk.CTkLabel(
        settings_identity,
        text=_settings_subtitle,
        text_color=aktif_palet["text_dim"],
        font=("Segoe UI", 10),
        anchor="w",
        cursor="hand2",
    )
    settings_title_label.pack(fill="x")

    # Sağdaki ikinci çark kaldırıldı. Soldaki vurgu renkli çark tek ayar simgesidir;
    # sağ tarafta yalnızca bu satırın bir sekme olduğunu anlatan sade yön oku bulunur.
    btn_ayarlar = None
    settings_chevron = ctk.CTkLabel(
        settings_bottom_bar,
        text="›",
        width=26,
        text_color=aktif_palet["text_dim"],
        font=("Segoe UI Semibold", 24),
        cursor="hand2",
    )
    settings_chevron.pack(side="right", padx=(4, 13), pady=10)

    _settings_motion = {
        "job": None,
        "leave_job": None,
        "bar_color": aktif_palet["card"],
        "avatar_color": aktif_palet["neon"],
    }

    def _settings_pointer_inside():
        try:
            px, py = root.winfo_pointerxy()
            x1, y1 = settings_bottom_bar.winfo_rootx(), settings_bottom_bar.winfo_rooty()
            x2 = x1 + settings_bottom_bar.winfo_width()
            y2 = y1 + settings_bottom_bar.winfo_height()
            return x1 <= px <= x2 and y1 <= py <= y2
        except Exception:
            return False

    def _settings_hover_animasyon(hovered):
        from neto_motion_engine_v2 import get_motion_engine
        from neto_widget_motion import color_value
        engine = get_motion_engine(root)
        targets = (
            (settings_bottom_bar, "fg_color", _neto_hex_karistir(aktif_palet["card"], aktif_palet["neon"], 0.10) if hovered else aktif_palet["card"]),
            (settings_avatar, "fg_color", aktif_palet.get("accent_hover", aktif_palet["neon"]) if hovered else aktif_palet["neon"]),
            (settings_chevron, "text_color", aktif_palet["neon"] if hovered else aktif_palet["text_dim"]),
        )
        for widget, option, target in targets:
            engine.color(f"settings-hover:{id(widget)}:{option}", widget, option,
                         color_value(widget, widget.cget(option)), target, duration_ms=160)

    def _settings_enter(event=None):
        try:
            pending = _settings_motion.get("leave_job")
            if pending:
                root.after_cancel(pending)
        except Exception:
            pass
        _settings_motion["leave_job"] = None
        _settings_hover_animasyon(True)

    def _settings_leave(event=None):
        def check():
            _settings_motion["leave_job"] = None
            if not _settings_pointer_inside():
                _settings_hover_animasyon(False)
        try:
            pending = _settings_motion.get("leave_job")
            if pending:
                root.after_cancel(pending)
            _settings_motion["leave_job"] = root.after(34, check)
        except Exception:
            check()

    def _settings_click_pulse(step=0):
        _settings_hover_animasyon(True)

    def _settings_bar_open(event=None):
        _settings_click_pulse()
        # Kullanıcı tıklama geri bildirimini görsün; sayfa yalnızca 70 ms sonra açılır.
        root.after(70, lambda: ayarlar_sayfasi_ac("general"))
        return "break"

    for _w in (
        settings_bottom_bar, settings_avatar, settings_identity,
        settings_profile_name, settings_title_label, settings_chevron,
    ):
        try:
            _w.bind("<Button-1>", _settings_bar_open)
            _w.bind("<Enter>", _settings_enter)
            _w.bind("<Leave>", _settings_leave)
        except Exception:
            pass

    # Sol panelin gizlendiği dar pencerelerde Ayarlar yine görünür kalır.
    compact_settings_btn = ctk.CTkButton(
        app_content,
        text="⚙  Ayarlar" if str(dil_getir()).lower().startswith("tr") else "⚙  Settings",
        width=118,
        height=38,
        corner_radius=11,
        fg_color=aktif_palet["card"],
        hover_color=aktif_palet["button_hover"],
        text_color=aktif_palet["text_main"],
        border_width=1,
        border_color=aktif_palet["entry_border"],
        font=("Segoe UI Semibold", 12),
        command=lambda: ayarlar_sayfasi_ac("general"),
    )

    sidebar_state = {
        "compact": False,
        "job": None,
        "animating": False,
        "current_width": PANEL_WIDTH,
        "last_applied_width": None,
    }
    sidebar_restore: dict[str, tuple[str, dict[str, Any]]] = {}
    sidebar_compact_width = 104

    def _sidebar_animasyonu_dondur():
        from neto_motion_engine_v2 import get_motion_engine
        get_motion_engine(root).cancel("sidebar-width")
        sidebar_state["job"] = None
        sidebar_state["animating"] = False

    def _sidebar_genislik_uygula(genislik, *, update_bottom=True):
        try:
            genislik = max(0, int(genislik))
        except Exception:
            genislik = PANEL_WIDTH
        sidebar_state["current_width"] = genislik
        width_changed = sidebar_state.get("last_applied_width") != genislik
        if width_changed:
            for widget in (side_panel, sidebar_header, sidebar_content, agent_sidebar_content, sidebar_brand):
                try:
                    widget.configure(width=genislik)
                except Exception:
                    pass
            sidebar_state["last_applied_width"] = genislik
        # The bottom bar does not need to be relaid out on every animation frame.
        # Deferring this anchor update removes a visible hitch while the sidebar moves.
        if update_bottom:
            try:
                _settings_bottom_bar_place()
            except Exception:
                pass

    def _sidebar_widget(name):
        return globals().get(name)

    _sidebar_icon_specs = {
        "btn_now_playing_ayar": "◷",
        "btn_now_playing_baslat": "♪",
        "btn_netoai": "◌",
        "btn_android_device": "▱",
        "btn_automation": "≋",
        "btn_scenes": "⌁",
        "btn_profiles": "♧",
        "btn_reminders": "◴",
        "btn_anahtar": "•••",
        "btn_store_panel": "▥",
        "settings_profile_name": "⚙",
    }

    _sidebar_icon_only_mode = False
    _sidebar_rail_bg = "#1B1B1D"
    _sidebar_icon_active_bg = "#2A2A2D"
    _sidebar_icon_fg = "#B8B8BC"
    _sidebar_hover_state = {}

    def _sidebar_icon_text(name, label, compact_label):
        return str(compact_label if sidebar_state.get("compact", False) else label)

    def _sidebar_text_yaz(name, buyuk, kucuk):
        widget = _sidebar_widget(name)
        if not widget:
            return
        # Neto Experience 3.0 (v1.40 eklentisi - YALNIZCA EKLEME):
        # kompakt modda "AUTO/NET/SHOP" kisaltmasi yerine gercek ikon.
        # Modul yoksa veya 3.0 kapaliysa asagidaki eski davranis aynen calisir.
        try:
            import neto_experience3
            if neto_experience3.apply_sidebar_widget(
                widget, name, bool(sidebar_state.get("compact", False))
            ):
                return
        except Exception:
            pass
        try:
            widget.configure(text=_sidebar_icon_text(name, buyuk, kucuk))
        except Exception:
            pass

    def _sidebar_icon_hover_bind(widget, primary=False, alert=False):
        if not widget:
            return
        if not _sidebar_icon_only_mode:
            return
        key = id(widget)
        if _sidebar_hover_state.get(key):
            return
        _sidebar_hover_state[key] = True

        def _enter(_event=None):
            try:
                widget.configure(
                    fg_color=_sidebar_icon_active_bg,
                )
            except Exception:
                pass

        def _leave(_event=None):
            try:
                if alert:
                    return
                widget.configure(fg_color="transparent")
            except Exception:
                pass

        try:
            widget.bind("<Enter>", _enter, add="+")
            widget.bind("<Leave>", _leave, add="+")
        except Exception:
            pass

    def _sidebar_pack_yeniden(widget, **pack_args):
        if not widget:
            return
        try:
            if widget.winfo_manager() == "pack":
                widget.pack_forget()
        except Exception:
            pass
        try:
            widget.pack(**pack_args)
        except Exception:
            pass

    def _sidebar_pack_ikon(widget, primary=False):
        if not widget:
            return
        try:
            widget._neto_custom_motion = False
            widget.configure(
                width=58,
                height=36,
                corner_radius=15,
                border_width=1,
                border_color=aktif_palet["neon"] if primary else aktif_palet["entry_border"],
                fg_color=aktif_palet["neon"] if primary else aktif_palet["card"],
                hover_color=aktif_palet.get("accent_hover", aktif_palet["button_hover"]) if primary else aktif_palet["button_hover"],
                text_color=_tema_vurgu_metin_rengi() if primary else aktif_palet["text_main"],
                font=("Segoe UI Semibold", 10, "bold"),
                anchor="center",
            )
        except Exception:
            pass
        # Neto Experience 3.0 (v1.40 eklentisi - YALNIZCA EKLEME):
        # Ray butonunu buyutup ikonu irileştirir. Ayar kapaliysa hicbir sey
        # olmaz ve yukaridaki varsayilan olculer (58x36, font 10) gecerli kalir.
        try:
            import neto_experience3 as _nx3_ray
            _nx3_metrik = _nx3_ray.rail_button_metrics()
            if _nx3_metrik:
                widget.configure(
                    height=_nx3_metrik["height"],
                    corner_radius=_nx3_metrik["radius"],
                    border_width=0,
                    font=(_nx3_metrik["font_family"], _nx3_metrik["font_size"], "bold"),
                )
                # 3.0: ray genisligi 104 px ve kaydirma cubugu ~16 px aliyor.
                # Varsayilan padx=22 ile butona ~44 px kaliyor ve buyuk ikon
                # kirpiliyor; bu yuzden ic bosluk kucultulur.
                _sidebar_pack_yeniden(
                    widget,
                    fill="none",
                    padx=_nx3_metrik.get("padx", 8),
                    pady=_nx3_metrik.get("pady", 5),
                )
        except Exception:
            pass
        try:
            _sidebar_pack_yeniden(widget, fill="none", padx=22, pady=6)
        except Exception:
            pass
        # Neto Experience 3.0 - SON SÖZ (v1.40 eklentisi, YALNIZCA EKLEME):
        # Yukarıdaki padx=22'lik paketleme, büyük ikon için gereken genişliği
        # geri alıp glifleri kırpıyor. Bu yüzden ölçüler uygulamanın
        # paketlemesinden SONRA bir kez daha yazılır.
        try:
            import neto_experience3 as _nx3_ray2
            _nx3_metrik2 = _nx3_ray2.rail_button_metrics()
            if _nx3_metrik2:
                widget.configure(
                    width=_nx3_metrik2.get("width", 58),
                    height=_nx3_metrik2["height"],
                    corner_radius=_nx3_metrik2["radius"],
                    border_width=0,
                    font=(_nx3_metrik2["font_family"], _nx3_metrik2["font_size"], "bold"),
                )
                _sidebar_pack_yeniden(
                    widget,
                    fill="none",
                    padx=_nx3_metrik2.get("padx", 8),
                    pady=_nx3_metrik2.get("pady", 5),
                )
        except Exception:
            pass
        _sidebar_icon_hover_bind(widget, primary=primary)

    def _sidebar_pack_genis(widget, primary=False):
        if not widget:
            return
        try:
            widget.configure(
                width=0,
                height=30,
                corner_radius=8,
                border_width=0,
                border_color=aktif_palet["entry_border"],
                fg_color=aktif_palet["neon"] if primary else aktif_palet["card"],
                hover_color=aktif_palet.get("accent_hover", aktif_palet["button_hover"]) if primary else aktif_palet["button_hover"],
                text_color=_tema_vurgu_metin_rengi() if primary else aktif_palet["text_main"],
                font=("Segoe UI Semibold", 12),
                anchor="w",
            )
        except Exception:
            pass
        try:
            _sidebar_pack_yeniden(widget, fill="x", padx=20, pady=4)
        except Exception:
            pass
        _sidebar_icon_hover_bind(widget, primary=primary)

    def _sidebar_pack_kompakt_stat(widget, vurgu=False, ilk=False):
        if not widget:
            return
        try:
            widget.configure(
                width=64,
                height=34,
                corner_radius=13,
                fg_color=_neto_hex_karistir(aktif_palet["sidebar"], aktif_palet["card"], 0.72),
                text_color=aktif_palet["neon"] if vurgu else aktif_palet["text_main"],
                font=("Segoe UI Semibold", 10),
                justify="center",
                anchor="center",
            )
        except Exception:
            pass
        try:
            _sidebar_pack_yeniden(widget, fill="none", padx=18, pady=((58, 4) if ilk else 4))
        except Exception:
            pass

    def _sidebar_pack_genis_label(widget, pady=None):
        if not widget:
            return
        try:
            widget.configure(
                width=0,
                height=0,
                fg_color="transparent",
                text_color=aktif_palet["text_main"],
                font=("Segoe UI Semibold", 12),
                justify="center",
                anchor="center",
            )
        except Exception:
            pass
        try:
            if pady is None:
                _sidebar_pack_yeniden(widget, fill="none", padx=0)
            else:
                _sidebar_pack_yeniden(widget, fill="none", padx=0, pady=pady)
        except Exception:
            pass

    def _sidebar_scrollbar_kompakt(aktif):
        try:
            if aktif:
                zemin = _sidebar_rail_bg if _sidebar_icon_only_mode else aktif_palet["sidebar"]
                iz = zemin if _sidebar_icon_only_mode else _neto_hex_karistir(aktif_palet["sidebar"], aktif_palet["entry_border"], 0.32)
                sidebar_content.configure(
                    width=sidebar_compact_width,
                    scrollbar_button_color=iz,
                    scrollbar_button_hover_color=iz,
                )
                scrollbar = getattr(sidebar_content, "_scrollbar", None)
                if scrollbar is not None:
                    scrollbar.configure(
                        width=1 if _sidebar_icon_only_mode else 5,
                        fg_color=zemin,
                        button_color=iz,
                        button_hover_color=iz,
                        corner_radius=5,
                    )
            else:
                sidebar_content.configure(
                    width=PANEL_WIDTH,
                    scrollbar_button_color=aktif_palet["card"],
                    scrollbar_button_hover_color=aktif_palet["button_hover"],
                )
                scrollbar = getattr(sidebar_content, "_scrollbar", None)
                if scrollbar is not None:
                    scrollbar.configure(
                        width=12,
                        fg_color=aktif_palet["sidebar"],
                        button_color=aktif_palet["card"],
                        button_hover_color=aktif_palet["button_hover"],
                        corner_radius=6,
                    )
        except Exception:
            pass

    def _sidebar_gizle(name):
        widget = _sidebar_widget(name)
        if not widget:
            return
        try:
            manager = widget.winfo_manager()
        except Exception:
            manager = ""
        if not manager:
            return
        try:
            if manager == "pack":
                sidebar_restore[name] = (manager, widget.pack_info())
                widget.pack_forget()
            elif manager == "grid":
                sidebar_restore[name] = (manager, widget.grid_info())
                widget.grid_forget()
            elif manager == "place":
                sidebar_restore[name] = (manager, widget.place_info())
                widget.place_forget()
        except Exception:
            pass

    def _sidebar_goster(name):
        widget = _sidebar_widget(name)
        if not widget:
            return
        try:
            if widget.winfo_manager():
                return
        except Exception:
            return
        try:
            manager, cfg = sidebar_restore.get(name, ("", {}))
            if manager == "pack":
                widget.pack(**cfg)
            elif manager == "grid":
                widget.grid(**cfg)
            elif manager == "place":
                widget.place(**cfg)
        except Exception:
            pass

    def _sidebar_metinleri_yenile():
        icon_mode = bool(sidebar_state.get("compact", False))
        tr_mode = str(dil_getir()).lower().startswith("tr")

        try:
            brand_text_box = _sidebar_widget("sidebar_brand_text_box")
            if brand_text_box:
                if icon_mode:
                    if brand_text_box.winfo_manager() == "pack":
                        brand_text_box.pack_forget()
                else:
                    if not brand_text_box.winfo_manager():
                        brand_text_box.pack(side="left", fill="both", expand=True, pady=8)
        except Exception:
            pass

        _sidebar_text_yaz("lbl_sistem_durumu", T("system_status"), "◉")
        _sidebar_text_yaz("cpu_l", "CPU: %0", "CPU")
        _sidebar_text_yaz("ram_l", "RAM: %0", "RAM")
        try:
            _sidebar_istatistik_yaz()
        except Exception:
            pass
        _sidebar_text_yaz("btn_now_playing_ayar", now_playing_text("settings_short"), "SET")
        _sidebar_text_yaz("btn_now_playing_baslat", now_playing_text("open_button_short"), "GO")
        _sidebar_text_yaz("lbl_notlar", T("notes"), "✎")
        _sidebar_text_yaz("lbl_sistem", "Araçlar" if tr_mode else "Tools", "🛠")
        _sidebar_text_yaz("btn_netoai", T("neto_ai"), "AI")
        _sidebar_text_yaz("btn_android_device", T("device_hub"), "QR")
        _sidebar_text_yaz("btn_automation", "Otomasyon Merkezi" if tr_mode else "Automation Center", "AUTO")
        _sidebar_text_yaz("btn_scenes", "Neto Hazırla" if tr_mode else "Neto Prepare", "NET")
        _sidebar_text_yaz("btn_profiles", "Profiller" if tr_mode else "Profiles", "PRO")
        _sidebar_text_yaz("btn_reminders", "Hatırlatıcılar" if tr_mode else "Reminders", "REM")

        try:
            anahtar_widget = _sidebar_widget("btn_anahtar")
            if anahtar_widget:
                if icon_mode:
                    anahtar_widget.configure(text="ON" if eklenti_aktif_mi else "OFF")
                else:
                    anahtar_widget.configure(
                        text=T("extension_status_on") if eklenti_aktif_mi else T("extension_status_off")
                    )
        except Exception:
            pass

        def _anahtar_renk_uygula():
            try:
                anahtar_widget = _sidebar_widget("btn_anahtar")
                if anahtar_widget:
                    if _sidebar_icon_only_mode:
                        anahtar_widget.configure(
                            fg_color="transparent",
                            hover_color="#2A2A2D",
                            text_color="#B8B8BC",
                            border_width=0,
                            border_color=aktif_palet["sidebar"],
                        )
                        return
                    anahtar_widget.configure(
                        fg_color="#00c46a" if eklenti_aktif_mi else "#b32424",
                        hover_color="#00a85b" if eklenti_aktif_mi else "#8c1c1c",
                        text_color="#000000" if eklenti_aktif_mi else "#ffffff",
                    )
            except Exception:
                pass

        _sidebar_text_yaz(
            "lbl_magaza",
            f"{str(T('extension_store') or 'Extension Store')}  (Ctrl+E)",
            "🛒",
        )
        _sidebar_text_yaz("btn_store_panel", "Open Store  Ctrl+E", "SHOP")
        _sidebar_text_yaz("settings_profile_name", "Ayarlar" if tr_mode else "Settings", "⚙")
        _sidebar_text_yaz(
            "settings_title_label",
            "Uygulama ayarları" if tr_mode else "App settings",
            "",
        )

        if _sidebar_icon_only_mode or icon_mode:
            try:
                for _rail_widget in (side_panel, sidebar_header, sidebar_content):
                    try:
                        _rail_widget.configure(fg_color=_sidebar_rail_bg, border_color=_sidebar_rail_bg)
                    except Exception:
                        pass
                _neto_scrollable_frame_renklendir(sidebar_content, aktif_palet, "sidebar")
                for _rail_widget in (side_panel, sidebar_header, sidebar_content):
                    try:
                        _rail_widget.configure(fg_color=_sidebar_rail_bg, border_color=_sidebar_rail_bg)
                    except Exception:
                        pass
                _sidebar_scrollbar_kompakt(True)
            except Exception:
                pass
            for gizlenecek in (
                "lbl_sistem_durumu",
                "cpu_l",
                "ram_l",
                "lbl_notlar",
                "lbl_sistem",
                "lbl_magaza",
            ):
                _sidebar_gizle(gizlenecek)
            if not _sidebar_icon_only_mode:
                _sidebar_goster("cpu_l")
                _sidebar_goster("ram_l")
                _sidebar_pack_kompakt_stat(_sidebar_widget("cpu_l"), vurgu=False, ilk=True)
                _sidebar_pack_kompakt_stat(_sidebar_widget("ram_l"), vurgu=True)
            else:
                _sidebar_gizle("cpu_l")
                _sidebar_gizle("ram_l")
            _sidebar_gizle("lbl_now_playing_detay")
            _sidebar_gizle("lbl_now_playing")
            _sidebar_gizle("not_alani")
            _sidebar_gizle("settings_identity")
            _sidebar_gizle("settings_chevron")
            _sidebar_gizle("settings_title_label")
            if not _sidebar_icon_only_mode:
                try:
                    lbl_now_playing.configure(
                        width=58,
                        height=28,
                        text_color=aktif_palet["neon"],
                        font=("Segoe UI Semibold", 17),
                        anchor="center",
                        justify="center",
                    )
                    _sidebar_pack_yeniden(lbl_now_playing, fill="none", padx=23, pady=(18, 5))
                except Exception:
                    pass
            _sidebar_pack_ikon(_sidebar_widget("btn_now_playing_ayar"), primary=False)
            _sidebar_pack_ikon(_sidebar_widget("btn_now_playing_baslat"), primary=False)
            _sidebar_pack_ikon(_sidebar_widget("btn_netoai"), primary=False)
            _sidebar_pack_ikon(_sidebar_widget("btn_android_device"), primary=False)
            _sidebar_pack_ikon(_sidebar_widget("btn_automation"), primary=False)
            _sidebar_pack_ikon(_sidebar_widget("btn_scenes"), primary=False)
            _sidebar_pack_ikon(_sidebar_widget("btn_profiles"), primary=False)
            _sidebar_pack_ikon(_sidebar_widget("btn_reminders"), primary=False)
            _sidebar_pack_ikon(_sidebar_widget("btn_anahtar"), primary=False)
            _sidebar_pack_ikon(_sidebar_widget("btn_store_panel"), primary=False)
            _anahtar_renk_uygula()
            try:
                settings_bottom_bar.configure(height=34, corner_radius=9, fg_color="transparent", border_width=0)
                settings_avatar.configure(width=34, height=34, corner_radius=9, fg_color="#2A2A2D")
                settings_avatar.pack_configure(padx=0, pady=0)
            except Exception:
                pass
            try:
                _sidebar_gizle("settings_identity")
                _sidebar_gizle("settings_chevron")
                settings_bottom_bar.configure(border_width=0)
            except Exception:
                pass
            try:
                _neto_scrollable_frame_renklendir(sidebar_content, aktif_palet, "sidebar")
                _sidebar_scrollbar_kompakt(True)
            except Exception:
                pass
        else:
            try:
                _neto_scrollable_frame_renklendir(sidebar_content, aktif_palet, "sidebar")
                _sidebar_scrollbar_kompakt(False)
            except Exception:
                pass
            _sidebar_goster("settings_identity")
            _sidebar_goster("settings_chevron")
            _sidebar_goster("settings_title_label")
            try:
                lbl_sistem_durumu.configure(
                    text_color=aktif_palet["text_dim"],
                    font=("Segoe UI Semibold", 13),
                    fg_color="transparent",
                )
                _sidebar_pack_yeniden(lbl_sistem_durumu, pady=(20, 5))
            except Exception:
                pass
            _sidebar_pack_genis_label(_sidebar_widget("cpu_l"))
            _sidebar_pack_genis_label(_sidebar_widget("ram_l"))
            try:
                lbl_now_playing.configure(
                    width=0,
                    height=0,
                    text_color=aktif_palet["neon"],
                    font=("Segoe UI Semibold", 12),
                    anchor="w",
                    justify="left",
                )
                _sidebar_pack_yeniden(lbl_now_playing, fill="x", padx=18, pady=(8, 0))
            except Exception:
                pass
            try:
                lbl_now_playing_detay.configure(
                    text_color=aktif_palet["text_dim"],
                    font=("Segoe UI", 11),
                    anchor="w",
                    justify="left",
                )
                _sidebar_pack_yeniden(lbl_now_playing_detay, fill="x", padx=18, pady=(2, 6))
            except Exception:
                pass
            _sidebar_pack_genis(_sidebar_widget("btn_now_playing_ayar"), primary=False)
            _sidebar_pack_genis(_sidebar_widget("btn_now_playing_baslat"), primary=True)
            try:
                lbl_notlar.configure(
                    text_color=aktif_palet["text_dim"],
                    font=("Segoe UI Semibold", 13),
                    fg_color="transparent",
                )
                _sidebar_pack_yeniden(lbl_notlar, pady=(15, 5))
            except Exception:
                pass
            try:
                _sidebar_pack_yeniden(not_alani, padx=20, fill="x")
            except Exception:
                pass
            try:
                lbl_sistem.configure(
                    text_color=aktif_palet["text_dim"],
                    font=("Segoe UI Semibold", 13),
                    fg_color="transparent",
                )
                _sidebar_pack_yeniden(lbl_sistem, pady=(15, 5))
            except Exception:
                pass
            _sidebar_pack_genis(_sidebar_widget("btn_netoai"), primary=False)
            _sidebar_pack_genis(_sidebar_widget("btn_android_device"), primary=False)
            _sidebar_pack_genis(_sidebar_widget("btn_automation"), primary=False)
            _sidebar_pack_genis(_sidebar_widget("btn_scenes"), primary=False)
            _sidebar_pack_genis(_sidebar_widget("btn_profiles"), primary=False)
            _sidebar_pack_genis(_sidebar_widget("btn_reminders"), primary=False)
            _sidebar_pack_genis(_sidebar_widget("btn_anahtar"), primary=False)
            try:
                lbl_magaza.configure(
                    text_color=aktif_palet["text_dim"],
                    font=("Segoe UI Semibold", 13),
                    fg_color="transparent",
                )
                _sidebar_pack_yeniden(lbl_magaza, pady=(15, 5))
            except Exception:
                pass
            _sidebar_pack_genis(_sidebar_widget("btn_store_panel"), primary=True)
            _anahtar_renk_uygula()
            try:
                settings_bottom_bar.configure(height=58, corner_radius=26)
                settings_avatar.configure(width=36, height=36, corner_radius=18)
                settings_avatar.pack_configure(padx=(12, 9), pady=11)
            except Exception:
                pass
            try:
                _neto_scrollable_frame_renklendir(sidebar_content, aktif_palet, "sidebar")
                _sidebar_scrollbar_kompakt(False)
            except Exception:
                pass

        try:
            hamburger_btn.configure(text="☰" if icon_mode else "×")
        except Exception:
            pass

        try:
            _sidebar_genislik_uygula(sidebar_compact_width if icon_mode else PANEL_WIDTH)
        except Exception:
            pass

        try:
            if not icon_mode:
                compact_settings_btn.place_forget()
        except Exception:
            pass

        try:
            settings_bottom_bar.lift()
            hamburger_btn.lift()
        except Exception:
            pass

        try:
            now_playing_sidebar_guncelle(globals().get("now_playing_last_info"))
        except Exception:
            pass

        try:
            _sidebar_istatistik_yaz()
        except Exception:
            pass

    def _sidebar_layout_uygula(expanded: bool, animate: bool = True, persist: bool = True):
        if _settings_overlay_aktif():
            return
        if sidebar_state.get("animating") and not animate:
            return
        from neto_motion_engine_v2 import get_motion_engine
        engine = get_motion_engine(root)
        engine.cancel("sidebar-width")
        if persist:
            sidebar_state["compact"] = not bool(expanded)
        target = sidebar_compact_width if _sidebar_icon_only_mode else (PANEL_WIDTH if expanded else sidebar_compact_width)
        start = int(sidebar_state.get("current_width", target))
        side_panel.pack_propagate(False)
        sidebar_state["animating"] = bool(animate and start != target)

        def finish():
            sidebar_state["job"] = None
            sidebar_state["animating"] = False
            _sidebar_genislik_uygula(target)
            _sidebar_metinleri_yenile()
            _neto_input_bar_konumla()

        if not sidebar_state["animating"]:
            finish()
            return
        # Short labels fit for the entire transition. Restore full labels once.
        desired = sidebar_state["compact"]
        sidebar_state["compact"] = True
        _sidebar_metinleri_yenile()
        sidebar_state["compact"] = desired
        last_width = [start]

        def update(value):
            width = round(value)
            if width != last_width[0]:
                _sidebar_genislik_uygula(width, update_bottom=False)
                last_width[0] = width

        sidebar_state["job"] = engine.number(
            "sidebar-width", start, target, update, duration_ms=240,
            easing="ease_in_out_cubic", on_complete=finish)
    def _neto_agent_panel_aksiyon(metin: str, acilis_mesaji: str | None = None):
        try:
            opener = globals().get("neto_ai_chat_uygulama_icinde_ac")
            if callable(opener):
                opener()
            else:
                raise RuntimeError("Agent sohbet yüzeyi henüz hazır değil.")
        except Exception:
            try:
                animasyonlu_yazi(metin)
            except Exception:
                pass

    agent_sidebar_header = ctk.CTkFrame(agent_sidebar_content, fg_color="transparent")
    agent_sidebar_header.pack(fill="x", padx=16, pady=(18, 8))

    agent_sidebar_title = ctk.CTkLabel(
        agent_sidebar_header,
        text=f"{APP_NAME} Agent",
        text_color=aktif_palet["text_main"],
        font=("Segoe UI Semibold", 17),
        anchor="w",
    )
    agent_sidebar_title.pack(side="left", fill="x", expand=True)

    agent_sidebar_close = ctk.CTkButton(
        agent_sidebar_header,
        text="n.ext",
        width=58,
        height=30,
        corner_radius=10,
        fg_color=aktif_palet["card"],
        hover_color=aktif_palet["button_hover"],
        text_color=aktif_palet["text_main"],
        font=("Segoe UI Semibold", 11),
        command=lambda: _neto_agent_modu_kapat(),
    )
    agent_sidebar_close.pack(side="right")

    agent_sidebar_desc = ctk.CTkLabel(
        agent_sidebar_content,
        text="Karar veren AI çalışma alanı" if str(dil_getir()).lower().startswith("tr") else "Decision-making AI workspace",
        text_color=aktif_palet["text_dim"],
        font=("Segoe UI", 12),
        anchor="w",
    )
    agent_sidebar_desc.pack(fill="x", padx=18, pady=(0, 12))

    agent_quick_title = ctk.CTkLabel(
        agent_sidebar_content,
        text="Kısayollar" if str(dil_getir()).lower().startswith("tr") else "Quick actions",
        text_color=aktif_palet["text_dim"],
        font=("Segoe UI Semibold", 13),
        anchor="w",
    )
    agent_quick_title.pack(fill="x", padx=18, pady=(8, 5))

    def _agent_menu_buton(text, command=None, accent=False):
        btn = ctk.CTkButton(
            agent_sidebar_content,
            text=text,
            font=("Segoe UI Semibold", 12),
            fg_color=aktif_palet["neon"] if accent else aktif_palet["card"],
            hover_color=aktif_palet.get("accent_hover", aktif_palet["button_hover"]),
            text_color=_tema_vurgu_metin_rengi() if accent else aktif_palet["text_main"],
            corner_radius=10,
            height=34,
            command=command or (lambda: None),
        )
        btn.pack(padx=18, fill="x", pady=4)
        return btn

    _agent_menu_buton("Yeni sohbet", lambda: _neto_agent_panel_aksiyon("Yeni sohbet açılıyor.", f"Yeni bir {APP_NAME} Agent sohbeti başlat."))
    _agent_menu_buton("Pull request'ler", lambda: _neto_agent_panel_aksiyon("Pull request'ler bölümü şimdilik hazırlık aşamasında."))
    _agent_menu_buton("Sites", lambda: _neto_agent_panel_aksiyon("Sites bölümü açılıyor.", "Sites ile ilgili bir görev oluştur."))
    _agent_menu_buton("Zamanlananlar", lambda: neto_otomasyon_merkezi_ac(), accent=True)
    _agent_menu_buton("Eklentiler", lambda: eklenti_magazasi_panel_toggle(), accent=True)

    def _agent_internet_yazi():
        try:
            return "İnternet: AÇIK" if neto_ai.internet_aktif_mi() else "İnternet: KAPALI"
        except Exception:
            return "İnternet"

    def _agent_internet_guncelle():
        try:
            acik = neto_ai.internet_aktif_mi()
        except Exception:
            acik = False
        try:
            agent_internet_btn.configure(
                text=_agent_internet_yazi(),
                fg_color="#00c46a" if acik else "#b32424",
                hover_color="#00a85b" if acik else "#8c1c1c",
                text_color="#000000" if acik else "#ffffff",
            )
        except Exception:
            pass

    def _agent_internet_toggle():
        try:
            acik = neto_ai.internet_durumu_degistir()
        except Exception:
            acik = False
        _agent_internet_guncelle()
        try:
            animasyonlu_yazi("İnternet açıldı." if acik else "İnternet kapatıldı.")
        except Exception:
            pass
        return "break"

    agent_internet_btn = ctk.CTkButton(
        agent_sidebar_content,
        text=_agent_internet_yazi(),
        font=("Segoe UI Semibold", 12),
        fg_color="#00c46a" if neto_ai.internet_aktif_mi() else "#b32424",
        hover_color="#00a85b" if neto_ai.internet_aktif_mi() else "#8c1c1c",
        text_color="#000000" if neto_ai.internet_aktif_mi() else "#ffffff",
        corner_radius=10,
        height=34,
        command=_agent_internet_toggle,
    )
    agent_internet_btn.pack(padx=18, fill="x", pady=(8, 4))

    agent_projects_title = ctk.CTkLabel(
        agent_sidebar_content,
        text="Projeler" if str(dil_getir()).lower().startswith("tr") else "Projects",
        text_color=aktif_palet["text_dim"],
        font=("Segoe UI Semibold", 13),
        anchor="w",
    )
    agent_projects_title.pack(fill="x", padx=18, pady=(18, 5))

    _agent_menu_buton("tablet", lambda: _neto_agent_panel_aksiyon("tablet projesi açılıyor.", "tablet projesi hakkında yardım istiyorum."))
    _agent_menu_buton("Root ve TWRP silinmesini incele", lambda: _neto_agent_panel_aksiyon("Root ve TWRP silinmesi inceleniyor.", "Root ve TWRP silinmesini incele."))
    _agent_menu_buton("RemoteLock uygulamasını geliştir", lambda: _neto_agent_panel_aksiyon("RemoteLock projesi açılıyor.", "RemoteLock uygulamasını geliştir."))

    agent_recent_title = ctk.CTkLabel(
        agent_sidebar_content,
        text="Yakın zamanlılar" if str(dil_getir()).lower().startswith("tr") else "Recent",
        text_color=aktif_palet["text_dim"],
        font=("Segoe UI Semibold", 13),
        anchor="w",
    )
    agent_recent_title.pack(fill="x", padx=18, pady=(18, 5))

    _agent_menu_buton("Projeyi ve klasörü özetle", lambda: _neto_agent_panel_aksiyon("Projeyi ve klasörü özetle.", "Projeyi ve klasörü özetle."))
    _agent_menu_buton("Cloudflare giriş hatasını bul", lambda: _neto_agent_panel_aksiyon("Cloudflare giriş hatası inceleniyor.", "Cloudflare giriş hatasını bul."))
    _agent_menu_buton("Bilgisayar şifresini kaldır", lambda: _neto_agent_panel_aksiyon("Bilgisayar şifresi konusu için yardım isteniyor.", "Bilgisayar şifresini kaldır."))

    agent_footer = ctk.CTkLabel(
        agent_sidebar_content,
        text="Agent modu açık. n.ext ile kapat." if str(dil_getir()).lower().startswith("tr") else "Agent mode is active. Use n.ext to close.",
        text_color=aktif_palet["text_dim"],
        font=("Segoe UI", 10),
        anchor="w",
        justify="left",
    )
    agent_footer.pack(fill="x", padx=18, pady=(18, 12))

    def _neto_agent_panellerini_guncelle(acik: bool | None = None):
        aktif = globals().get("_NETO_AGENT_MODU", False) if acik is None else bool(acik)
        try:
            if aktif:
                if sidebar_content.winfo_manager() == "pack":
                    sidebar_content.pack_forget()
                if settings_bottom_bar.winfo_manager() == "place":
                    settings_bottom_bar.place_forget()
                if settings_bottom_bar.winfo_manager() == "pack":
                    settings_bottom_bar.pack_forget()
                if not agent_sidebar_content.winfo_ismapped():
                    agent_sidebar_content.pack(fill="both", expand=True, pady=(0, 18))
                _agent_internet_guncelle()
                try:
                    compact_settings_btn.place_forget()
                except Exception:
                    pass
                try:
                    side_panel.configure(fg_color="#151515")
                except Exception:
                    pass
            else:
                if agent_sidebar_content.winfo_manager() == "pack":
                    agent_sidebar_content.pack_forget()
                if not sidebar_content.winfo_ismapped():
                    sidebar_content.pack(fill="both", expand=True, pady=(0, 66))
                try:
                    if settings_bottom_bar.winfo_manager() == "pack":
                        settings_bottom_bar.pack_forget()
                    _settings_bottom_bar_place()
                except Exception:
                    pass
                try:
                    side_panel.configure(fg_color=aktif_palet["sidebar"])
                except Exception:
                    pass
        except Exception:
            pass

    globals()["_neto_agent_panellerini_guncelle"] = _neto_agent_panellerini_guncelle

    # v10.27: Eski sol panel eklenti kısayol listesi kaldırıldı.
    # Sadece yeni Extension Store paneli kullanılacak.

    # --------------------
    # ANA SOHBET ALANI
    # --------------------
    chat_container = ctk.CTkFrame(main_c, fg_color=aktif_palet["bg"])
    chat_container.pack(side="top", expand=True, fill="both", padx=24, pady=(12, 6))

    # Ana karşılama alanı üstte sıkışmak yerine kullanılabilir alanın merkezinde durur.
    hero_content = ctk.CTkFrame(chat_container, fg_color="transparent", corner_radius=0)
    hero_content.pack(expand=True, fill="both")

    # Ana logo: kullanıcının verdiği animasyon, küçük logo alanında daha büyük ve okunabilir.
    gif_ana_label = ctk.CTkLabel(
        hero_content,
        text="",
        width=236,
        height=236,
        fg_color="transparent",
    )
    gif_ana_label.pack(pady=(0, 10))

    def _logo_kenar_arka_planini_temizle(image):
        """Köşelere bağlı tek renkli GIF zeminini saydamlaştırır.

        Sonrasında saydam kenarlar kırpılıp logo yeniden ortalanır. Böylece açık
        temada küçük/soluk logo ve koyu kare arka plan sorunu oluşmaz.
        """
        try:
            from collections import deque

            img = image.convert("RGBA")
            width, height = img.size
            px = img.load()
            corners = [
                px[0, 0][:3],
                px[width - 1, 0][:3],
                px[0, height - 1][:3],
                px[width - 1, height - 1][:3],
            ]
            bg = tuple(sum(c[i] for c in corners) // len(corners) for i in range(3))
            spread = max(sum(abs(c[i] - bg[i]) for i in range(3)) for c in corners)
            if spread <= 95:
                threshold = 42
                visited = set()
                queue_px = deque()
                for x in range(width):
                    queue_px.append((x, 0))
                    queue_px.append((x, height - 1))
                for y in range(height):
                    queue_px.append((0, y))
                    queue_px.append((width - 1, y))

                while queue_px:
                    x, y = queue_px.popleft()
                    if (x, y) in visited or x < 0 or y < 0 or x >= width or y >= height:
                        continue
                    visited.add((x, y))
                    r, g, b, a = px[x, y]
                    distance = abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2])
                    if distance > threshold or a == 0:
                        continue
                    px[x, y] = (r, g, b, 0)
                    queue_px.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))

            alpha = img.getchannel("A")
            bbox = alpha.getbbox()
            if bbox:
                img = img.crop(bbox)

            # İçeriği gerçekten görünür boyuta büyüt, sonra saydam kareye ortala.
            img.thumbnail((108, 108), Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
            x = (120 - img.width) // 2
            y = (120 - img.height) // 2
            canvas.alpha_composite(img, (x, y))
            return canvas
        except Exception:
            return image.convert("RGBA")

    def ana_gif_oynat():
        """Ana logoyu tema uyumlu, sabit boyutlu PNG karelerinden oynatır.

        Kaynak GIF önceden optimize edildiği için açılışta 800x800 kareler işlenmez;
        bu da arayüzün donmasını önler. Açık tema için koyu yazılı, koyu tema
        için beyaz yazılı kareler CTkImage çiftleri olarak kullanılır.
        """
        def oynatici(kareler, sureler, idx=0):
            if not kareler or not gif_ana_label.winfo_exists():
                return
            if not gif_ana_label.winfo_viewable():
                root.after(250, lambda: oynatici(kareler, sureler, idx))
                return
            try:
                frame_index = idx % len(kareler)
                gif_ana_label.configure(image=kareler[frame_index], text="")
                delay = sureler[frame_index] if frame_index < len(sureler) else 40
                root.after(max(25, int(delay)), lambda: oynatici(kareler, sureler, idx + 1))
            except Exception:
                pass

        try:
            frame_root = get_asset_path("neto_logo_frames")
            dark_dir = os.path.join(frame_root, "dark")
            light_dir = os.path.join(frame_root, "light")
            manifest_path = os.path.join(frame_root, "durations.json")

            dark_files = sorted(
                os.path.join(dark_dir, name)
                for name in os.listdir(dark_dir)
                if name.lower().endswith(".png")
            )
            light_files = sorted(
                os.path.join(light_dir, name)
                for name in os.listdir(light_dir)
                if name.lower().endswith(".png")
            )
            if not dark_files or len(dark_files) != len(light_files):
                raise FileNotFoundError("Tema uyumlu logo kareleri eksik")

            try:
                with open(manifest_path, "r", encoding="utf-8") as manifest_file:
                    sureler = json.load(manifest_file).get("durations", [])
            except Exception:
                sureler = [40] * len(dark_files)

            kareler = []
            for dark_path, light_path in zip(dark_files, light_files):
                dark_image = Image.open(dark_path).convert("RGBA")
                light_image = Image.open(light_path).convert("RGBA")
                kareler.append(
                    ctk.CTkImage(
                        light_image=light_image,
                        dark_image=dark_image,
                        size=(230, 230),
                    )
                )

            oynatici(kareler, sureler)
            print(f"[LOGO] Kullanıcı GIF'i yüklendi: {len(kareler)} kare, 230x230", flush=True)
            return
        except Exception as logo_error:
            try:
                print(f"[LOGO_FALLBACK] {logo_error}", flush=True)
            except Exception:
                pass

        # Paket kareleri bulunamazsa mevcut seçilebilir GIF sistemi çalışmaya devam eder.
        h = veri_yukle()
        gif_adi = h.get("secilen_gif", "yukleme.gif")
        yol = get_asset_path(gif_adi)
        if not os.path.exists(yol):
            yol = get_data_path(gif_adi)
        if not os.path.exists(yol):
            yol = GIF_PATH

        try:
            img = Image.open(yol)
            kareler = []
            sureler = []
            for f in ImageSequence.Iterator(img):
                kare = _logo_kenar_arka_planini_temizle(f.copy())
                kareler.append(ctk.CTkImage(light_image=kare, dark_image=kare, size=(220, 220)))
                sureler.append(f.info.get("duration", img.info.get("duration", 45)))
            if kareler:
                oynatici(kareler, sureler)
            else:
                raise ValueError("GIF karesi bulunamadı")
        except Exception:
            gif_ana_label.configure(
                text="NETOPS",
                image=None,
                text_color=aktif_palet["text_main"],
                font=("Segoe UI Semibold", 24),
            )

    ana_gif_oynat()

    lbl_welcome = ctk.CTkLabel(
        hero_content,
        text=T("main_question"),
        text_color=aktif_palet["text_main"],
        font=("Segoe UI Semibold", 26)
    )
    lbl_welcome.pack(pady=10)

    hero_status_frame = ctk.CTkFrame(
        hero_content,
        fg_color=aktif_palet["card"],
        corner_radius=15,
        border_width=1,
        border_color=aktif_palet["entry_border"],
    )
    hero_status_frame.pack(pady=(8, 0))

    etiket = ctk.CTkLabel(
        hero_status_frame,
        text="",
        wraplength=500,
        text_color=aktif_palet["neon"],
        font=("Segoe UI", 13, "italic")
    )
    etiket.pack(padx=18, pady=9)

    chat_bubble_shell = ctk.CTkFrame(
        hero_content,
        fg_color=aktif_palet["bg"],
        corner_radius=0,
        border_width=0,
    )
    chat_bubble_shell.pack_forget()

    chat_bubble_header = ctk.CTkFrame(chat_bubble_shell, fg_color="transparent", height=42)
    chat_bubble_header.pack(fill="x", padx=6, pady=(0, 6))
    chat_bubble_header.pack_propagate(False)

    chat_bubble_title = ctk.CTkLabel(
        chat_bubble_header,
        text="NETOPS CONVERSATION  ·  HARBILIG CORE",
        text_color=aktif_palet["neon"],
        font=("Segoe UI Semibold", 15),
        anchor="w",
    )
    chat_bubble_title.pack(side="left", fill="x", expand=True, padx=(2, 8))

    chat_bubble_clear = ctk.CTkButton(
        chat_bubble_header,
        text="CLEAR",
        width=82,
        height=30,
        corner_radius=12,
        fg_color=aktif_palet["card"],
        hover_color=aktif_palet["button_hover"],
        text_color=aktif_palet["neon"],
        font=("Segoe UI Semibold", 11),
        command=_neto_sohbet_temizle,
    )
    chat_bubble_clear.pack(side="right")

    chat_bubble_area = ctk.CTkScrollableFrame(
        chat_bubble_shell,
        height=360,
        fg_color=aktif_palet["bg"],
        corner_radius=0,
        border_width=0,
        scrollbar_button_color=aktif_palet["card"],
        scrollbar_button_hover_color=aktif_palet["button_hover"],
    )
    chat_bubble_area.pack(fill="both", expand=True, padx=0, pady=(0, 2))
    _neto_scrollable_frame_renklendir(chat_bubble_area, aktif_palet, "bg")
    home_now_playing_card = ctk.CTkFrame(
        hero_content,
        fg_color=aktif_palet["card"],
        corner_radius=18,
        border_width=1,
        border_color=aktif_palet["entry_border"],
    )
    # Now Playing ana ekranda yer kaplamasın; sol menü ve Dinamik Ada akışı kalır.
    home_now_playing_card.pack_forget()

    home_now_playing_body = ctk.CTkFrame(home_now_playing_card, fg_color="transparent")
    home_now_playing_body.pack(fill="x", padx=16, pady=14)
    home_now_playing_body.grid_columnconfigure(1, weight=1)

    home_now_playing_badge = ctk.CTkLabel(
        home_now_playing_body,
        text="♪",
        width=58,
        height=58,
        corner_radius=29,
        fg_color=aktif_palet["bg"],
        text_color=aktif_palet["neon"],
        font=("Segoe UI Semibold", 24),
    )
    home_now_playing_badge.grid(row=0, column=0, rowspan=2, padx=(0, 14), pady=2, sticky="n")

    home_now_playing_title = ctk.CTkLabel(
        home_now_playing_body,
        text=now_playing_text("home_idle_title"),
        text_color=aktif_palet["text_main"],
        font=("Segoe UI Semibold", 18),
        anchor="w",
    )
    home_now_playing_title.grid(row=0, column=1, sticky="ew", pady=(2, 0))

    home_now_playing_detail = ctk.CTkLabel(
        home_now_playing_body,
        text="",
        text_color=aktif_palet["text_dim"],
        font=("Segoe UI", 11),
        anchor="w",
        justify="left",
        wraplength=420,
    )
    home_now_playing_detail.grid(row=1, column=1, sticky="ew", pady=(3, 0))

    home_now_playing_actions = ctk.CTkFrame(home_now_playing_body, fg_color="transparent")
    home_now_playing_actions.grid(row=0, column=2, rowspan=2, padx=(16, 0), sticky="e")

    home_now_playing_settings = ctk.CTkButton(
        home_now_playing_actions,
        text=now_playing_text("settings_short"),
        width=118,
        height=34,
        corner_radius=11,
        fg_color=aktif_palet["card"],
        hover_color=aktif_palet["button_hover"],
        text_color=aktif_palet["text_main"],
        font=("Segoe UI Semibold", 11),
        command=now_playing_open_settings_safe,
    )
    home_now_playing_settings.pack(fill="x", pady=(0, 6))

    home_now_playing_open = ctk.CTkButton(
        home_now_playing_actions,
        text=now_playing_text("open_button_short"),
        width=118,
        height=34,
        corner_radius=11,
        fg_color=aktif_palet["neon"],
        hover_color=aktif_palet.get("accent_hover", aktif_palet["button_hover"]),
        text_color=_tema_vurgu_metin_rengi(),
        font=("Segoe UI Semibold", 11),
        command=lambda: now_playing_manual_open(force=True),
    )
    home_now_playing_open.pack(fill="x")

    home_now_playing_status = ctk.CTkLabel(
        home_now_playing_card,
        text=now_playing_text("home_idle_status"),
        text_color=aktif_palet["text_dim"],
        font=("Segoe UI", 10),
        anchor="w",
    )
    home_now_playing_status.pack(fill="x", padx=18, pady=(0, 12))

    now_playing_widget_kaydet("home_np_card", home_now_playing_card, "accent_frame")
    now_playing_widget_kaydet("home_np_badge", home_now_playing_badge, "accent_text")
    now_playing_widget_kaydet("home_np_title", home_now_playing_title, "title")
    now_playing_widget_kaydet("home_np_detail", home_now_playing_detail, "dim")
    now_playing_widget_kaydet("home_np_status", home_now_playing_status, "dim")
    now_playing_widget_kaydet("home_np_settings", home_now_playing_settings, "secondary")
    now_playing_widget_kaydet("home_np_open", home_now_playing_open, "primary")

    animasyonlu_yazi(T("main_hello"))

    # ------------------------------------------------------------
    # HAFİF ARAYÜZ HAREKETLERİ v14.6
    # Tema ağacını dolaşmaz, yalnızca görünen birkaç ana bileşeni kısa süre boyar.
    # Bu nedenle açılışı ve tema geçişini ağırlaştırmaz.
    # ------------------------------------------------------------
    _neto_intro_motion = {"job": None, "ran": False}

    def _neto_intro_animasyon_baslat(force=False):
        if _neto_intro_motion.get("ran") and not force:
            return
        _neto_intro_motion["ran"] = True
        try:
            old = _neto_intro_motion.get("job")
            if old:
                root.after_cancel(old)
        except Exception:
            pass

        bg = aktif_palet["bg"]
        text = aktif_palet["text_main"]
        accent = aktif_palet["neon"]
        card = aktif_palet["card"]
        border = aktif_palet["entry_border"]
        steps = 22

        try:
            lbl_welcome.configure(text_color=bg)
            etiket.configure(text_color=bg)
            hero_status_frame.configure(fg_color=bg, border_color=bg)
        except Exception:
            pass

        def tick(i=0):
            if not root.winfo_exists():
                return
            t = min(1.0, i / steps)
            expo = 1.0 - pow(2.0, -8.0 * t) if t < 1.0 else 1.0
            smooth = (t * t * t) * (t * ((t * 6.0) - 15.0) + 10.0)
            eased = max(0.0, min(1.0, (expo * 0.70) + (smooth * 0.30)))
            try:
                lbl_welcome.configure(text_color=_neto_hex_karistir(bg, text, eased))
                etiket.configure(text_color=_neto_hex_karistir(bg, accent, eased))
                hero_status_frame.configure(
                    fg_color=_neto_hex_karistir(bg, card, eased),
                    border_color=_neto_hex_karistir(bg, border, eased),
                )
            except Exception:
                return
            if i < steps:
                _neto_intro_motion["job"] = root.after(13, lambda: tick(i + 1))
            else:
                _neto_intro_motion["job"] = None
                _neto_input_accent_animasyon(0)

        tick()

    def _neto_input_accent_animasyon(step=0):
        """Keep the input border stable without a redundant 14 ms redraw loop."""
        try:
            if not giris_frame.winfo_exists():
                return
            if sidebar_state.get("animating"):
                try:
                    giris_frame.configure(border_width=0, border_color="#17191F")
                except Exception:
                    pass
                return
        except Exception:
            return
        try:
            giris_frame.configure(
                border_color=aktif_palet.get("entry_border", "#17191F"),
                border_width=0,
            )
        except Exception:
            pass

    def _neto_buton_tiklama_efekti(widget):
        from neto_widget_motion import bind_hover
        if widget is not None and widget.winfo_exists():
            bind_hover(widget, root)

    live_panel = ctk.CTkFrame(
        main_c,
        fg_color=aktif_palet["bg"],
        corner_radius=0,
        border_width=0
    )

    live_overlay = ctk.CTkFrame(
        live_panel,
        fg_color=aktif_palet["bg"],
        corner_radius=0
    )
    live_overlay.pack(fill="both", expand=True, padx=22, pady=22)

    live_top_row = ctk.CTkFrame(live_overlay, fg_color="transparent")
    live_top_row.pack(fill="x", pady=(4, 16))

    live_title = ctk.CTkLabel(
        live_top_row,
        text="🎤 NETOPS LIVE MODE",
        text_color=aktif_palet["text_main"],
        font=("Segoe UI Semibold", 28)
    )
    live_title.pack(side="left")

    live_close_btn = ctk.CTkButton(
        live_top_row,
        text="✕",
        width=42,
        height=36,
        corner_radius=12,
        fg_color=aktif_palet["card"],
        hover_color=aktif_palet["button_hover"],
        text_color=aktif_palet["text_main"],
        command=live_panel_gizle
    )
    live_close_btn.pack(side="right")

    live_main_area = ctk.CTkFrame(
        live_overlay,
        fg_color=aktif_palet["card"],
        corner_radius=26,
        border_width=1,
        border_color=aktif_palet["neon"]
    )
    live_main_area.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    live_status_pill = ctk.CTkFrame(
        live_main_area,
        fg_color=aktif_palet["bg"],
        corner_radius=18,
        border_width=1,
        border_color=aktif_palet["entry_border"]
    )
    live_status_pill.pack(pady=(26, 12), padx=20)

    live_durum_label = ctk.CTkLabel(
        live_status_pill,
        text="Off",
        text_color=aktif_palet["neon"],
        font=("Segoe UI Semibold", 14)
    )
    live_durum_label.pack(padx=18, pady=8)

    live_mic_circle = ctk.CTkFrame(
        live_main_area,
        width=170,
        height=170,
        corner_radius=85,
        fg_color=aktif_palet["bg"],
        border_width=4,
        border_color=aktif_palet["neon"]
    )
    live_mic_circle.pack(pady=(8, 10))
    live_mic_circle.pack_propagate(False)

    live_mic_icon = ctk.CTkLabel(
        live_mic_circle,
        text="🎤",
        text_color=aktif_palet["text_main"],
        font=("Segoe UI", 68)
    )
    live_mic_icon.pack(expand=True)

    live_wave = ctk.CTkLabel(
        live_main_area,
        text="▁▂▃▄▅▆▇▆▅▄▃▂▁",
        text_color=aktif_palet["neon"],
        font=("Segoe UI", 26)
    )
    live_wave.pack(pady=(4, 14))
    try:
        live_wave.configure(text="|   ||   ||   |")
    except Exception:
        pass

    live_mic_label = ctk.CTkLabel(
        live_main_area,
        text="Mikrofon: Bekleniyor",
        text_color=aktif_palet["text_dim"],
        font=("Segoe UI", 13)
    )
    live_mic_label.pack(pady=(0, 16))

    live_cards_row = ctk.CTkFrame(live_main_area, fg_color="transparent")
    live_cards_row.pack(fill="x", padx=24, pady=(0, 14))

    live_text_card = ctk.CTkFrame(
        live_cards_row,
        fg_color=aktif_palet["bg"],
        corner_radius=16,
        border_width=1,
        border_color=aktif_palet["entry_border"]
    )
    live_text_card.pack(side="left", fill="both", expand=True, padx=(0, 8))

    ctk.CTkLabel(
        live_text_card,
        text="Son Duyulan",
        text_color=aktif_palet["neon"],
        font=("Segoe UI Semibold", 13)
    ).pack(anchor="w", padx=14, pady=(12, 4))

    live_text_label = ctk.CTkLabel(
        live_text_card,
        text="Henüz konuşma algılanmadı.",
        wraplength=270,
        text_color=aktif_palet["text_main"],
        font=("Segoe UI", 13),
        justify="left"
    )
    live_text_label.pack(anchor="w", fill="x", padx=14, pady=(0, 14))

    live_answer_card = ctk.CTkFrame(
        live_cards_row,
        fg_color=aktif_palet["bg"],
        corner_radius=16,
        border_width=1,
        border_color=aktif_palet["entry_border"]
    )
    live_answer_card.pack(side="right", fill="both", expand=True, padx=(8, 0))

    ctk.CTkLabel(
        live_answer_card,
        text="Son Cevap",
        text_color=aktif_palet["neon"],
        font=("Segoe UI Semibold", 13)
    ).pack(anchor="w", padx=14, pady=(12, 4))

    live_answer_label = ctk.CTkLabel(
        live_answer_card,
        text="Henüz cevap yok.",
        wraplength=270,
        text_color=aktif_palet["text_main"],
        font=("Segoe UI", 13),
        justify="left"
    )
    live_answer_label.pack(anchor="w", fill="x", padx=14, pady=(0, 14))

    live_buttons = ctk.CTkFrame(live_main_area, fg_color="transparent")
    live_buttons.pack(fill="x", padx=24, pady=(4, 24))

    live_start_btn = ctk.CTkButton(
        live_buttons,
        text="▶ Başlat",
        height=46,
        corner_radius=14,
        fg_color=aktif_palet["neon"],
        text_color="#000000",
        hover_color=aktif_palet["button_hover"],
        command=live_mode_baslat
    )
    live_start_btn.pack(side="left", fill="x", expand=True, padx=(0, 8))

    live_stop_btn = ctk.CTkButton(
        live_buttons,
        text="⏸ Durdur",
        height=46,
        corner_radius=14,
        fg_color="#D92D2D",
        text_color="#ffffff",
        hover_color="#A82020",
        command=live_mode_durdur
    )
    live_stop_btn.pack(side="right", fill="x", expand=True, padx=(8, 0))

    input_container = ctk.CTkFrame(main_c, fg_color=aktif_palet["bg"])
    try:
        input_container.pack_propagate(False)
    except Exception:
        pass

    def _input_container_genislik_uygula(genislik=None):
        _neto_input_bar_konumla()

    def _neto_input_bar_konumla():
        # Pack owns the width. No nested event processing during transitions.
        if input_container.winfo_manager() == "place":
            input_container.place_forget()
        if input_container.winfo_manager() != "pack":
            input_container.configure(height=52)
            input_container.pack(side="bottom", fill="x", expand=False,
                                 padx=24, pady=(0, 10), anchor="s", before=chat_container)

    _neto_input_bar_konumla()

    ekli_resim_frame = ctk.CTkFrame(
        input_container,
        fg_color=aktif_palet["card"],
        corner_radius=12,
        border_width=1,
        border_color=aktif_palet["entry_border"]
    )
    lbl_resim_preview = ctk.CTkLabel(
        ekli_resim_frame,
        text="🖼",
        fg_color=aktif_palet["card"],
        text_color=aktif_palet["text_main"],
        font=("Segoe UI", 18),
        width=52,
        height=48
    )
    lbl_resim_preview.pack(side="left", padx=(10, 6), pady=8)
    lbl_resim_dosya = ctk.CTkLabel(
        ekli_resim_frame,
        text="",
        text_color=aktif_palet["text_main"],
        font=("Segoe UI Semibold", 12),
        anchor="w"
    )
    lbl_resim_dosya.pack(side="left", fill="x", expand=True, padx=4)
    btn_resim_kaldir = ctk.CTkButton(
        ekli_resim_frame,
        text="✕",
        width=34,
        height=30,
        corner_radius=8,
        fg_color=aktif_palet["card"],
        hover_color=aktif_palet["button_hover"],
        text_color=aktif_palet["text_main"],
        command=ekli_resim_karti_gizle
    )
    btn_resim_kaldir.pack(side="right", padx=10, pady=8)

    _INPUT_BAR_HEIGHT = 50
    _INPUT_BUTTON_SIZE = 30
    _INPUT_ICON_SIZE = 22
    _INPUT_BAR_BG = "#07080D"
    _INPUT_BAR_BORDER = "#242A38"
    _INPUT_TEXT = "#F2F5FF"
    _INPUT_PLACEHOLDER = "#8D96A8"
    _INPUT_ICON_COLOR = "#F2F5FF"
    _INPUT_AI_COLOR = "#BF8CFF"
    _INPUT_HOVER = "#1C2433"

    giris_frame = ctk.CTkFrame(
        input_container,
        fg_color=_INPUT_BAR_BG,
        corner_radius=25,
        height=_INPUT_BAR_HEIGHT,
        border_width=0,
        border_color=_INPUT_BAR_BORDER
    )
    giris_frame.pack(fill="x", ipady=0, pady=2)
    giris_frame.pack_propagate(False)

    # ------------------------------------------------------------
    # MODERN INLINE LIVE BAR v1.38
    # Yeni mantık:
    # - Live ayrı pencere/panel açmaz.
    # - Mikrofon basılınca input çubuğu animasyonla ortaya doğru kısalır.
    # - Normal butonlar kaybolur; ortada sadece "Dinliyor..." görünür.
    # - Çıkışta çubuk animasyonla eski genişliğine geri uzar.
    # - Live açılış sesi kullanıcı ses dosyasından çalınır.
    # ------------------------------------------------------------
    inline_live_state = {
        "active": False,
        "text_mode": False,
        "mic_available": False,
        "mic_name": "",
        "tablet_audio_path": "",
        "anim_id": None,
        "pulse_id": None,
        "pulse": 0,
        "saved_text": "",
        "normal_width": 0,
        "animating": False,
    }

    def inline_live_text():
        try:
            return "Dinliyor..." if dil_getir() == "tr" else "Listening..."
        except Exception:
            return "Dinliyor..."

    def inline_live_stop_text():
        try:
            return "Canlı dinleme durdu." if dil_getir() == "tr" else "Live listening stopped."
        except Exception:
            return "Canlı dinleme durdu."

    def inline_live_cleanup_animation():
        for key in ("anim_id", "pulse_id"):
            try:
                anim_id = inline_live_state.get(key)
                if anim_id:
                    root.after_cancel(anim_id)
                    inline_live_state[key] = None
            except Exception:
                pass

    def inline_live_ease(t):
        try:
            t = max(0.0, min(1.0, float(t)))
            expo = 1.0 - pow(2.0, -8.0 * t) if t < 1.0 else 1.0
            smooth = (t * t * t) * (t * ((t * 6.0) - 15.0) + 10.0)
            return max(0.0, min(1.0, (expo * 0.72) + (smooth * 0.28)))
        except Exception:
            return t

    def inline_live_target_width():
        try:
            root.update_idletasks()
            parent_w = max(300, int(input_container.winfo_width()))
            return max(300, min(520, parent_w - 170))
        except Exception:
            return 430

    def inline_live_normal_width():
        try:
            root.update_idletasks()
            return max(300, int(input_container.winfo_width()))
        except Exception:
            return 820

    def inline_live_set_fixed_pack(width):
        try:
            giris_frame.pack_forget()
        except Exception:
            pass
        try:
            giris_frame.pack(anchor="center", pady=(0, 0), ipady=0)
        except Exception:
            pass
        try:
            giris_frame.pack_propagate(False)
        except Exception:
            pass
        try:
            giris_frame.configure(width=int(width), height=_INPUT_BAR_HEIGHT)
        except Exception:
            pass

    def inline_live_restore_normal_pack():
        try:
            giris_frame.pack_forget()
        except Exception:
            pass
        try:
            giris_frame.pack(fill="x", ipady=0, pady=2)
        except Exception:
            pass
        try:
            giris_frame.pack_propagate(False)
            giris_frame.configure(height=_INPUT_BAR_HEIGHT)
        except Exception:
            pass

    def inline_live_animate_width(start_w, end_w, done=None, steps=20):
        from neto_motion_engine_v2 import get_motion_engine
        engine = get_motion_engine(root)
        inline_live_state["animating"] = True
        def update(value):
            width = max(1, min(round(value), max(1, input_container.winfo_width())))
            if width != int(giris_frame.cget("width")):
                giris_frame.configure(width=width)
        def finish():
            inline_live_state["animating"] = False
            inline_live_state["anim_id"] = None
            if callable(done):
                done()
        inline_live_state["anim_id"] = engine.number(
            "live-width", start_w, end_w, update, duration_ms=220, on_complete=finish)

    def inline_live_pulse():
        """Apply the live palette once; a hidden 90 ms pulse caused needless redraws."""
        if not inline_live_state.get("active"):
            return
        try:
            giris_frame.configure(fg_color=_INPUT_BAR_BG, border_color=_INPUT_BAR_BORDER, border_width=0, corner_radius=25)
            giris.configure(
                fg_color="transparent", text_color=_INPUT_TEXT,
                border_color=_INPUT_BAR_BORDER, border_width=0,
            )
            btn_live.configure(
                fg_color="transparent", text_color="#EAF0FF", hover_color=_INPUT_HOVER,
                border_width=0, width=_INPUT_BUTTON_SIZE, height=_INPUT_BUTTON_SIZE,
                corner_radius=_INPUT_BUTTON_SIZE // 2,
            )
            btn_gonder.configure(
                fg_color="transparent", hover_color=_INPUT_HOVER, text_color="#EAF0FF",
                border_width=0, width=_INPUT_BUTTON_SIZE, height=_INPUT_BUTTON_SIZE,
                corner_radius=_INPUT_BUTTON_SIZE // 2,
            )
        except Exception:
            pass

    def inline_live_play_open_sound():
        try:
            # Önce kullanıcının verdiği yeni ses.
            for name in ("live_open.mp3", "denielcz-done-463074.mp3"):
                try:
                    yol = get_asset_path(name)
                    if yol and os.path.exists(yol):
                        if K_PYGAME:
                            if not pygame.mixer.get_init():
                                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
                            s = pygame.mixer.Sound(yol)
                            s.set_volume(0.55)
                            s.play()
                        return
                except Exception:
                    pass
            # Eski live sesi fonksiyonu varsa yedek.
            try:
                live_acilis_sesi_oynat()
            except Exception:
                pass
        except Exception as e:
            try:
                print(f"[INLINE_LIVE_SOUND] {e}", flush=True)
            except Exception:
                pass

    def inline_live_enter_ui(text_mode=False, notice=""):
        """Modern live bar: voice mode shrinks; text mode stays editable."""
        try:
            inline_live_state["saved_text"] = giris.get()
        except Exception:
            inline_live_state["saved_text"] = ""

        try:
            root.update_idletasks()
            normal_w = inline_live_normal_width()
            inline_live_state["normal_width"] = normal_w
        except Exception:
            normal_w = 820

        # Normal butonları gizle.
        for w in (btn_resim, btn_model, btn_input_ai):
            try:
                w.pack_forget()
            except Exception:
                pass

        # Modern pill başlangıcı.
        try:
            inline_live_set_fixed_pack(normal_w)
            giris_frame.configure(
                fg_color=_INPUT_BAR_BG,
                border_color=_INPUT_BAR_BORDER,
                border_width=0,
                corner_radius=25
            )
        except Exception:
            pass

        try:
            btn_live.configure(
                text="",
                image=_neto_input_icon("waveform", _INPUT_ICON_SIZE, "#EAF0FF"),
                width=_INPUT_BUTTON_SIZE,
                height=_INPUT_BUTTON_SIZE,
                corner_radius=_INPUT_BUTTON_SIZE // 2,
                fg_color="transparent",
                text_color="#EAF0FF",
                hover_color=_INPUT_HOVER,
                border_width=0,
            )
        except Exception:
            pass

        inline_live_cleanup_animation()
        if text_mode:
            try:
                giris.configure(state="normal")
                try:
                    giris.configure(justify="left")
                except Exception:
                    pass
                giris.configure(
                    fg_color="transparent",
                    text_color=_INPUT_TEXT,
                    font=("Segoe UI", 15),
                    height=_INPUT_BAR_HEIGHT,
                    border_width=0,
                    border_color=_INPUT_BAR_BORDER,
                    placeholder_text=str(
                        notice or ("Komutunu yaz..." if dil_getir() == "tr" else "Type your command...")
                    ),
                )
            except Exception:
                pass

            try:
                btn_gonder.configure(
                    text="",
                    image=_neto_input_icon("send", _INPUT_ICON_SIZE, "#EAF0FF"),
                    width=_INPUT_BUTTON_SIZE,
                    height=_INPUT_BUTTON_SIZE,
                    corner_radius=_INPUT_BUTTON_SIZE // 2,
                    command=cevap_ver,
                    fg_color="transparent",
                    hover_color=_INPUT_HOVER,
                    text_color="#EAF0FF",
                    border_width=0,
                )
            except Exception:
                pass

            try:
                btn_live.configure(
                    text="",
                    image=_neto_input_icon("waveform", _INPUT_ICON_SIZE, "#EAF0FF"),
                    width=_INPUT_BUTTON_SIZE,
                    height=_INPUT_BUTTON_SIZE,
                    corner_radius=_INPUT_BUTTON_SIZE // 2,
                    fg_color="transparent",
                    text_color="#EAF0FF",
                    hover_color=_INPUT_HOVER,
                    border_width=0,
                )
            except Exception:
                pass

            inline_live_state["text_mode"] = True
            try:
                _neto_widget_focus_guvenli(giris, kaynak="inline_live_text_on")
            except Exception:
                pass
            try:
                inline_live_pulse()
            except Exception:
                pass
            return

        try:
            giris.configure(state="normal")
            giris.delete(0, tk.END)
            giris.insert(0, inline_live_text())
            try:
                giris.configure(justify="center")
            except Exception:
                pass
            giris.configure(
                state="disabled",
                fg_color="transparent",
                text_color=_INPUT_TEXT,
                border_width=0,
                border_color=_INPUT_BAR_BORDER,
                placeholder_text=""
            )
        except Exception:
            pass

        # Gönder butonu artık çıkış oku.
        try:
            btn_gonder.configure(
                text="",
                image=_neto_input_icon("send", _INPUT_ICON_SIZE, "#EAF0FF"),
                width=_INPUT_BUTTON_SIZE,
                height=_INPUT_BUTTON_SIZE,
                corner_radius=_INPUT_BUTTON_SIZE // 2,
                command=inline_live_stop,
                fg_color="transparent",
                hover_color=_INPUT_HOVER,
                text_color="#EAF0FF",
                border_width=0,
            )
        except Exception:
            pass

        inline_live_state["text_mode"] = False
        target = inline_live_target_width()
        inline_live_animate_width(normal_w, target, done=inline_live_pulse, steps=18)

    def inline_live_exit_ui():
        """Live'dan çıkarken bar animasyonla eski genişliğine döner."""
        inline_live_cleanup_animation()

        try:
            root.update_idletasks()
            current_w = max(360, int(giris_frame.winfo_width()))
        except Exception:
            current_w = inline_live_target_width()

        try:
            target_w = inline_live_normal_width()
        except Exception:
            target_w = inline_live_state.get("normal_width", 820) or 820

        def restore_after_grow():
            try:
                inline_live_restore_normal_pack()
            except Exception:
                pass

            # Live moddan çıkınca kontrolleri ilk açılıştaki sıraya geri koy.
            try:
                btn_resim.pack_forget()
                btn_model.pack_forget()
                btn_live.pack_forget()
                btn_gonder.pack_forget()
                btn_input_ai.pack_forget()
                giris.pack_forget()
            except Exception:
                pass
            try:
                btn_resim.pack(side="left", padx=(10, 2), pady=10)
                btn_live.pack(side="right", padx=(2, 10), pady=10)
                btn_gonder.pack(side="right", padx=2, pady=10)
                btn_input_ai.pack(side="right", padx=2, pady=10)
                giris.pack(side="left", fill="x", expand=True, padx=8, pady=0)
            except Exception:
                pass

            try:
                giris.configure(state="normal")
                giris.delete(0, tk.END)
                old = inline_live_state.get("saved_text", "")
                if old:
                    giris.insert(0, old)
                try:
                    giris.configure(justify="left")
                except Exception:
                    pass
                giris.configure(
                    fg_color="transparent",
                    text_color=_INPUT_TEXT,
                    font=("Segoe UI", 15),
                    height=_INPUT_BAR_HEIGHT,
                    border_width=0,
                    border_color=_INPUT_BAR_BORDER,
                    placeholder_text="Mesajını yaz...",
                    placeholder_text_color=_INPUT_PLACEHOLDER
                )
            except Exception:
                pass

            try:
                btn_live.configure(
                    text="",
                    image=_neto_input_icon("waveform", _INPUT_ICON_SIZE, "#EAF0FF"),
                    width=_INPUT_BUTTON_SIZE,
                    height=_INPUT_BUTTON_SIZE,
                    corner_radius=_INPUT_BUTTON_SIZE // 2,
                    fg_color="transparent",
                    text_color="#EAF0FF",
                    hover_color=_INPUT_HOVER,
                    border_width=0,
                )
            except Exception:
                pass

            try:
                btn_gonder.configure(
                    text="",
                    image=_neto_input_icon("send", _INPUT_ICON_SIZE, "#EAF0FF"),
                    width=_INPUT_BUTTON_SIZE,
                    height=_INPUT_BUTTON_SIZE,
                    corner_radius=_INPUT_BUTTON_SIZE // 2,
                    command=cevap_ver,
                    fg_color="transparent",
                    hover_color=_INPUT_HOVER,
                    text_color="#EAF0FF",
                    border_width=0,
                )
            except Exception:
                pass

            try:
                giris_frame.configure(
                    fg_color=_INPUT_BAR_BG,
                    border_color=_INPUT_BAR_BORDER,
                    border_width=0,
                    corner_radius=25,
                    height=_INPUT_BAR_HEIGHT,
                )
            except Exception:
                pass

            try:
                _neto_widget_focus_guvenli(giris, kaynak="inline_live_text_off")
            except Exception:
                pass

            inline_live_state["text_mode"] = False

        # Önce modern rengi koruyup uzat, sonra normal pack'e dön.
        try:
            inline_live_set_fixed_pack(current_w)
        except Exception:
            pass
        inline_live_animate_width(current_w, target_w, done=restore_after_grow, steps=16)

    def inline_live_start():
        """Start live listening without opening old live screens."""
        global live_mode_controller
        try:
            if inline_live_state.get("active"):
                return
            _netops_tablet_audio_stream_clear(remove_file=True)
            tablet_audio_path = ""
            try:
                if _netops_online_tablet_devices():
                    tablet_audio_path = _netops_tablet_audio_stream_path()
            except Exception:
                tablet_audio_path = ""

            preferred = ("AudioRelay", "Audio Relay", "WO Mic", "Microphone", "Mikrofon")
            mic_available = True
            mic_name = ""
            if not tablet_audio_path:
                try:
                    mic_available, _mic_index, mic_name = neto_live_mode.probe_input_device(list(preferred))
                except Exception as exc:
                    mic_available = False
                    mic_name = str(exc or "").strip()

            text_mode = not tablet_audio_path and not mic_available
            inline_live_state["active"] = True
            inline_live_state["text_mode"] = text_mode
            inline_live_state["mic_available"] = bool(mic_available)
            inline_live_state["mic_name"] = str(mic_name or ("Tablet mikrofonu" if tablet_audio_path else "Yok"))
            inline_live_state["tablet_audio_path"] = str(tablet_audio_path or "")

            inline_live_play_open_sound()
            inline_live_enter_ui(
                text_mode=text_mode,
                notice=(
                    "Komutunu yaz ve Enter'a bas."
                    if text_mode
                    else (T("entry_placeholder") if "T" in globals() else "Mesajını yaz...")
                ),
            )

            # Eski live panel ekranını göstermeden izole worker başlatılır.
            if text_mode:
                try:
                    live_mode_controller = None
                except Exception:
                    pass
                try:
                    live_mic_guncelle("Yok")
                except Exception:
                    pass
                try:
                    live_status_guncelle("Hazır. Komutunu yazabilirsin.")
                except Exception:
                    pass
                try:
                    animasyonlu_yazi("Mikrofon bulunamadı. Metin modu açık.")
                except Exception:
                    pass
                _netops_send_tablet_command(
                    "live_screen",
                    {"show": True, "title": "NETOPS LIVE MODE", "subtitle": "Mikrofon yok, metin modu aktif"},
                    broadcast=True,
                    reason="live",
                    async_dispatch=True,
                )
                return True

            if not live_mode_baslat():
                raise RuntimeError("Live yardımcı süreci başlatılamadı.")

            try:
                animasyonlu_yazi("Dinliyorum..." if dil_getir() == "tr" else "Listening...")
            except Exception:
                pass
        except Exception as e:
            inline_live_state["active"] = False
            inline_live_state["text_mode"] = False
            inline_live_exit_ui()
            try:
                animasyonlu_yazi(f"Live başlatılamadı: {e}")
            except Exception:
                pass

    def inline_live_stop():
        try:
            if not inline_live_state.get("active"):
                return
            inline_live_state["active"] = False
            inline_live_state["text_mode"] = False
            live_mode_durdur()
            inline_live_exit_ui()
            try:
                animasyonlu_yazi(inline_live_stop_text())
            except Exception:
                pass
        except Exception:
            try:
                inline_live_state["active"] = False
                inline_live_exit_ui()
            except Exception:
                pass

    def inline_live_force_stop(reason=""):
        """Restore the input bar when the isolated native worker exits/crashes."""
        try:
            was_active = bool(inline_live_state.get("active"))
            inline_live_state["active"] = False
            inline_live_state["text_mode"] = False
            if was_active:
                inline_live_exit_ui()
            message = (
                "Live motoru durdu; NetOps açık kaldı. "
                "Loglar: %LOCALAPPDATA%\\NetOps\\logs"
            )
            if reason:
                message += f"\n{reason}"
            animasyonlu_yazi(message)
        except Exception:
            try:
                inline_live_state["active"] = False
                inline_live_exit_ui()
            except Exception:
                pass

    def inline_live_toggle():
        if inline_live_state.get("active"):
            inline_live_stop()
        else:
            inline_live_start()

    globals()["inline_live_toggle"] = inline_live_toggle
    globals()["inline_live_start"] = inline_live_start
    globals()["inline_live_stop"] = inline_live_stop
    globals()["inline_live_force_stop"] = inline_live_force_stop

    # NetOps mesaj kapsülü: artı + şeffaf metin + gönder + dalga.
    btn_resim = ctk.CTkButton(
        giris_frame,
        text="",
        image=_neto_input_icon("plus", _INPUT_ICON_SIZE, "#EAF0FF"),
        fg_color="transparent",
        text_color="#EAF0FF",
        hover_color=_INPUT_HOVER,
        border_width=0,
        corner_radius=_INPUT_BUTTON_SIZE // 2,
        width=_INPUT_BUTTON_SIZE,
        height=_INPUT_BUTTON_SIZE,
        command=resim_yukle
    )
    btn_resim.pack(side="left", padx=(10, 2), pady=10)

    _aktif_model_text = "K1"
    btn_model = ctk.CTkButton(
        giris_frame,
        text=_aktif_model_text,
        font=("Segoe UI Semibold", 11),
        fg_color="#202A3E",
        text_color="#DCE7FF",
        hover_color="#2B3955",
        border_width=1,
        border_color="#43557A",
        corner_radius=14,
        width=40,
        height=34,
        command=kevra_model_degistir
    )
    # K1 seçimi korunur, ancak örnekteki temiz kapsülü bozmaması için
    # mesaj çubuğunda görünmez; model seçimi ayarlar/komut alanından sürer.
    btn_model.pack_forget()

    btn_live = ctk.CTkButton(
        giris_frame,
        text="",
        image=_neto_input_icon("waveform", _INPUT_ICON_SIZE, "#EAF0FF"),
        fg_color="transparent",
        text_color="#EAF0FF",
        hover_color=_INPUT_HOVER,
        border_width=0,
        corner_radius=_INPUT_BUTTON_SIZE // 2,
        width=_INPUT_BUTTON_SIZE,
        height=_INPUT_BUTTON_SIZE,
        command=inline_live_toggle
    )
    btn_live.pack(side="right", padx=(2, 10), pady=10)

    btn_gonder = ctk.CTkButton(
        giris_frame,
        text="",
        image=_neto_input_icon("send", _INPUT_ICON_SIZE, "#EAF0FF"),
        fg_color="transparent",
        text_color="#EAF0FF",
        hover_color=_INPUT_HOVER,
        border_width=0,
        corner_radius=_INPUT_BUTTON_SIZE // 2,
        width=_INPUT_BUTTON_SIZE,
        height=_INPUT_BUTTON_SIZE,
        command=cevap_ver
    )
    btn_gonder.pack(side="right", padx=2, pady=10)

    btn_input_ai = ctk.CTkButton(
        giris_frame,
        text="",
        image=_neto_input_icon("ai", _INPUT_ICON_SIZE, _INPUT_AI_COLOR),
        fg_color="transparent",
        text_color=_INPUT_AI_COLOR,
        hover_color=_INPUT_HOVER,
        border_width=0,
        corner_radius=_INPUT_BUTTON_SIZE // 2,
        width=_INPUT_BUTTON_SIZE,
        height=_INPUT_BUTTON_SIZE,
        command=neto_ai_baslat,
    )
    btn_input_ai.pack(side="right", padx=2, pady=10)

    # Bu üç kontrol kapsülün kendi görsel diline sahip; genel menü buton
    # katmanı bunların dairesel siyah yüzünü ezmemeli.
    for _capsule_button in (btn_resim, btn_live, btn_gonder, btn_input_ai):
        _capsule_button._neto_modern_skip = True

    # Neto Experience 3.0: kapsül butonlarını global bir sözlükte yayınla
    # (yalnızca ekleme). Açılış tamamlandıktan sonra 3.0 vurgusu bunlara
    # tekrar uygulanır; çünkü renkler açılışta paletten yeniden yazılır.
    globals()["_neto_capsule_buttons"] = {
        "plus": btn_resim,
        "live": btn_live,
        "send": btn_gonder,
        "ai": btn_input_ai,
    }

    # Neto Experience 3.0 (v1.40 eklentisi - YALNIZCA EKLEME):
    # Kapsül butonları bilinçli olarak genel stil katmanından muaftır
    # (yukarıdaki nota bakın). 3.0 katkısı burada hedefli biçimde eklenir:
    # ikonlara ipucu balonu + gönder butonuna vurgu rengi. Ayar kapalıysa
    # hiçbir şey değişmez.
    try:
        import neto_experience3 as _nx3
        if _nx3.is_enabled():
            _nx3.attach_tooltip(btn_resim, "Dosya veya görsel ekle")
            _nx3.attach_tooltip(btn_live, "Canlı dinleme (Live Mode)")
            _nx3.attach_tooltip(btn_gonder, "Gönder")
            _nx3.attach_tooltip(btn_input_ai, "Neto AI")
            try:
                btn_gonder.configure(
                    fg_color=_nx3.accent_color(),
                    hover_color=_nx3.accent_hover_color(),
                )
                btn_gonder.configure(image=_neto_input_icon("send", _INPUT_ICON_SIZE, "#0B0D12"))
            except Exception:
                pass
    except Exception as _nx3_kapsul_hata:
        try:
            print(f"[EXPERIENCE3_CAPSULE_ERROR] {_nx3_kapsul_hata}", flush=True)
        except Exception:
            pass

    giris = ctk.CTkEntry(
        giris_frame,
        font=("Segoe UI", 15),
        height=_INPUT_BAR_HEIGHT,
        fg_color="transparent",
        text_color=_INPUT_TEXT,
        border_width=0,
        border_color=_INPUT_BAR_BORDER,
        placeholder_text="Mesajını yaz...",
        placeholder_text_color=_INPUT_PLACEHOLDER
    )
    giris.pack(side="left", fill="x", expand=True, padx=8, pady=0)
    giris.bind("<Return>", lambda e: cevap_ver())
    try:
        _neto_input_bar_konumla()
    except Exception:
        pass

    # Ana eylemlerde kısa, hafif tıklama geri bildirimi.
    _neto_feedback_targets = (
        btn_gonder,
        btn_input_ai,
        
        btn_netoai,
        btn_android_device,
        btn_automation,
        btn_scenes,
        btn_profiles,
        btn_reminders,
        btn_now_playing_ayar,
        btn_now_playing_baslat,
        btn_store_panel,
    )
    for _feedback_widget in _neto_feedback_targets:
        try:
            _feedback_widget.bind(
                "<ButtonPress-1>",
                lambda _e, w=_feedback_widget: _neto_buton_tiklama_efekti(w),
                add="+",
            )
        except Exception:
            pass

    for _sohbet_widget in (giris_frame, giris, btn_resim, btn_model):
        try:
            _sohbet_widget.bind("<Button-1>", _neto_sohbet_modu_odakla, add="+")
        except Exception:
            pass

    try:
        _neto_sohbet_modu_odakla()
    except Exception:
        pass


    # ------------------------------------------------------------
    # BELİRGİN AMA HAFİF ARAYÜZ ANİMASYONLARI v14.7
    # Sadece görünen widget'ları küçük gruplar halinde hareket ettirir.
    # Tema ağacı taranmaz; ağır update()/mainloop çağrısı yapılmaz.
    # ------------------------------------------------------------
    _neto_motion_v147 = {
        "intro_job": None,
        "jelly_job": None,
        "page_cover": None,
        "button_jobs": {},
        "input_focus_job": None,
        "intro_ran": False,
        "jelly_ran": False,
    }

    def _neto_widget_var(widget):
        try:
            return widget is not None and bool(widget.winfo_exists())
        except Exception:
            return False

    def _neto_after_cancel_safe(job):
        if not job:
            return
        try:
            root.after_cancel(job)
        except Exception:
            pass

    def _neto_motion():
        try:
            from neto_motion_engine_v2 import get_motion_engine
            return get_motion_engine(root)
        except Exception:
            return None
    def _neto_widget_color_anim(widget, prop, baslangic, hedef, adim=0, toplam=12, on_done=None):
        if not _neto_widget_var(widget):
            return
        from neto_widget_motion import color_value
        engine = _neto_motion()
        start = color_value(widget, widget.cget(prop))
        target = color_value(widget, hedef)
        if engine is None:
            widget.configure(**{prop: hedef})
            if callable(on_done):
                on_done()
            return
        engine.tween(
            f"color:{id(widget)}:{prop}", 160,
            lambda p: widget.configure(**{prop: _neto_hex_karistir(start, target, p)})
            if widget.winfo_exists() else engine.cancel(f"color:{id(widget)}:{prop}"),
            on_complete=on_done,
        )

    def _neto_belirgin_button_bind(widget, primary=False):
        from neto_widget_motion import bind_hover
        if _neto_widget_var(widget):
            bind_hover(widget, root)

    for _v147_btn, _v147_primary in (
        (btn_now_playing_ayar, False),
        (btn_now_playing_baslat, True),
        
        (btn_netoai, False),
        (btn_android_device, False),
        (btn_automation, False),
        (btn_scenes, False),
        (btn_profiles, False),
        (btn_reminders, False),
        (btn_store_panel, True),
        (btn_gonder, True),
        (btn_resim, False),
        (btn_model, False),
        (btn_live, False),
    ):
        try:
            _neto_belirgin_button_bind(_v147_btn, _v147_primary)
        except Exception:
            pass

    def _neto_page_reveal(title=""):
        surface = globals().get("_neto_workspace_state", {}).get("surface")
        if _neto_widget_var(surface) and surface.winfo_manager() == "place":
            from neto_widget_motion import slide_surface
            slide_surface(root, surface, key="workspace-transition")

    globals()["_neto_page_reveal"] = _neto_page_reveal

    def _neto_modal_fade_slide(label="page", closing=False, on_mid=None):
        from neto_widget_motion import slide_surface
        surface = settings_page_controller.surface
        if _neto_widget_var(surface):
            slide_surface(root, surface, closing=closing, done=on_mid, key="settings-transition")
        elif callable(on_mid):
            on_mid()

    def _neto_bind_hover_tree(parent=None, limit=900):
        try:
            from neto_modern_ui import apply_tree
            apply_tree(parent or app_content, aktif_palet)
        except Exception:
            pass
        from neto_widget_motion import bind_hover_tree
        bind_hover_tree(parent or app_content, root, limit)

    globals()["_neto_bind_hover_tree"] = _neto_bind_hover_tree

    def _neto_sidebar_stagger():
        # Preserve padding and dimensions chosen by the responsive layout.
        _neto_bind_hover_tree(side_panel)
    def _neto_settings_bar_slide():
        try:
            bar_width = _settings_bottom_bar_width()
            start_x = -(bar_width + 18)
            end_x = 10
            _settings_bottom_bar_place(start_x)
        except Exception:
            return
        engine = _neto_motion()
        if engine is None:
            try:
                settings_bottom_bar.place_configure(x=end_x, width=_settings_bottom_bar_width())
            except Exception:
                pass
            return
        def update(x):
            if not _neto_widget_var(settings_bottom_bar):
                return
            try:
                settings_bottom_bar.place_configure(x=int(x), width=_settings_bottom_bar_width())
            except Exception:
                pass
        engine.number("settings-bar-slide", start_x, end_x, update, duration_ms=240, easing="ease_out_quart")

    def _neto_jelly_intro_baslat(force=False):
        """Reveal the ready main window with one shared, low-cost jelly tween.

        Geometry is changed only when the rounded size actually changes. This
        keeps the playful settle motion while avoiding the per-frame redraw
        storm that made the old startup feel shaky on slower machines.
        """
        state = _neto_motion_v147
        if state.get("jelly_ran") and not force:
            return
        state["jelly_ran"] = True
        engine = _neto_motion()
        if engine is None:
            try:
                root.attributes("-alpha", 1.0)
            except Exception:
                pass
            return

        try:
            root.update_idletasks()
            target_w = max(520, int(root.winfo_width()))
            target_h = max(644, int(root.winfo_height()))
            target_x = int(root.winfo_x())
            target_y = int(root.winfo_y())
            if str(root.state()).lower() in {"zoomed", "iconic"}:
                target_w = target_h = 0
        except Exception:
            target_w, target_h, target_x, target_y = 0, 0, 0, 0

        can_resize = target_w > 0 and target_h > 0
        start_scale = 0.965
        last_size = {"value": (0, 0, 0, 0)}

        if can_resize:
            try:
                start_w = max(480, round(target_w * start_scale))
                start_h = max(600, round(target_h * start_scale))
                start_x = target_x + (target_w - start_w) // 2
                start_y = target_y + (target_h - start_h) // 2
                root.geometry(f"{start_w}x{start_h}+{start_x}+{start_y}")
                last_size["value"] = (start_w, start_h, start_x, start_y)
            except Exception:
                can_resize = False

        try:
            root.attributes("-alpha", 0.72)
        except Exception:
            pass

        def update(progress):
            p = max(0.0, min(1.04, float(progress)))
            if can_resize:
                scale = start_scale + ((1.0 - start_scale) * p)
                width = max(480, round(target_w * scale))
                height = max(600, round(target_h * scale))
                x = target_x + (target_w - width) // 2
                y = target_y + (target_h - height) // 2
                current = (width, height, x, y)
                if current != last_size["value"]:
                    try:
                        root.geometry(f"{width}x{height}+{x}+{y}")
                        last_size["value"] = current
                    except Exception:
                        engine.cancel("neto-jelly-intro")
                        return
            try:
                root.attributes("-alpha", min(1.0, 0.72 + (0.28 * min(1.0, p))))
            except Exception:
                pass

        def finish():
            state["jelly_job"] = None
            if can_resize:
                try:
                    root.geometry(f"{target_w}x{target_h}+{target_x}+{target_y}")
                except Exception:
                    pass
            try:
                root.attributes("-alpha", 1.0)
            except Exception:
                pass

        state["jelly_job"] = engine.tween(
            "neto-jelly-intro",
            300,
            update,
            easing="spring_soft",
            on_complete=finish,
        )

    def _neto_hero_motion():
        if chat_bubble_shell.winfo_manager():
            _neto_sohbet_ekrani_ac()
            for widget in (gif_ana_label, lbl_welcome, hero_status_frame):
                try:
                    widget.pack_forget()
                except Exception:
                    pass
            return
        engine = _neto_motion()
        if engine is None:
            return
        def update(progress):
            if chat_bubble_shell.winfo_manager():
                engine.cancel("hero-intro")
                _neto_sohbet_ekrani_ac()
                for widget in (gif_ana_label, lbl_welcome, hero_status_frame):
                    try:
                        widget.pack_forget()
                    except Exception:
                        pass
                return
            lbl_welcome.configure(text_color=_neto_hex_karistir(
                aktif_palet["text_dim"], aktif_palet["text_main"], progress))
        _neto_motion_v147["intro_job"] = engine.tween("hero-intro", 200, update)
    def _neto_iddiali_intro_baslat(force=False):
        if _neto_motion_v147.get("intro_ran") and not force:
            return
        _neto_motion_v147["intro_ran"] = True
        _neto_after_cancel_safe(_neto_motion_v147.get("intro_job"))
        _neto_jelly_intro_baslat(force=force)
        _neto_settings_bar_slide()
        _neto_sidebar_stagger()
        _neto_hero_motion()

    globals()["_neto_iddiali_intro_baslat"] = _neto_iddiali_intro_baslat

    # Giriş kutusu odaklandığında sürekli değil, tek seferlik güçlü vurgu halkası.
    def _neto_input_focus(inside=True):
        engine = _neto_motion()
        try:
            if sidebar_state.get("animating"):
                giris_frame.configure(border_width=0)
                return
        except Exception:
            return
        start = aktif_palet["entry_border"] if inside else aktif_palet["neon"]
        end = aktif_palet["neon"] if inside else aktif_palet["entry_border"]
        try:
            giris_frame.configure(border_width=0)
        except Exception:
            return
        if engine is None:
            try:
                giris_frame.configure(border_color=end)
            except Exception:
                pass
            return
        _neto_motion_v147["input_focus_job"] = engine.color(
            "input-focus-ring",
            giris_frame,
            "border_color",
            start,
            end,
            duration_ms=170,
            easing="ease_in_out_cubic",
        )
    try:
        giris.bind("<FocusIn>", lambda e: _neto_input_focus(True), add=True)
        giris.bind("<FocusOut>", lambda e: _neto_input_focus(False), add=True)
    except Exception:
        pass

    # --------------------
    # MINI EKRAN + HAMBURGER - FINAL FIX
    # --------------------
    # Şüpheli eski sorunlar:
    # 1) Buton komutu sonradan configure ile bağlandığı için bazı CTk sürümlerinde çalışmayabiliyordu.
    # 2) Configure olayı paneli açıldıktan hemen sonra tekrar düzenleyip davranışı bozabiliyordu.
    # 3) pack/place geçişleri gerçek duruma göre değil değişkene göre kontrol edildiğinde takılabiliyordu.
    #
    # Bu sürüm:
    # - Açık/kapalı durumu side_panel.winfo_manager() ile kontrol eder.
    # - Buton command'i yukarıda buton oluşturulurken bağlanır.
    # - Ayrıca tıklama bind'i ve Ctrl+M yedek kısayolu vardır.
    # - Terminale [MENU] logu basar.

    def _menu_log(metin):
        try:
            print(f"[MENU] {metin}", flush=True)
        except Exception:
            pass

    def hamburger_panel_ac():
        try:
            _menu_log("panel açılıyor")

            if side_panel.winfo_manager() == "pack":
                side_panel.pack_forget()

            _sidebar_layout_uygula(True, animate=False, persist=False)

            # Overlay olarak aç.
            side_panel.configure(width=PANEL_WIDTH)
            side_panel.place(x=0, y=0, relheight=1)
            side_panel.lift()

            _hamburger_konumla()
            hamburger_btn.lift()
            hamburger_btn.configure(text="×")
            # Neto Experience 3.0: metin sembolu yerine gercek ikon.
            try:
                import neto_experience3 as _nx3_hb
                _nx3_hb.apply_symbol_icon(hamburger_btn)
            except Exception:
                pass

            root.update_idletasks()
            _menu_log("panel açıldı")

        except Exception as e:
            _menu_log(f"panel açma hata: {e}")

    def hamburger_panel_kapat():
        try:
            _menu_log("panel kapanıyor")

            if side_panel.winfo_manager() == "place":
                side_panel.place_forget()

            # Compact pencerede hamburger sidebar header''ının içinde kaldığı için
            # overlay kapanınca dar paneli yeniden monte et.
            try:
                if root.winfo_width() < MINI_LIMIT and side_panel.winfo_manager() != "pack":
                    side_panel.pack(side="left", fill="y", before=main_c)
            except Exception:
                pass

            _sidebar_layout_uygula(not sidebar_state.get("compact", False), animate=False, persist=False)

            _hamburger_konumla()
            hamburger_btn.lift()
            hamburger_btn.configure(text="☰")
            # Neto Experience 3.0: metin sembolu yerine gercek ikon.
            try:
                import neto_experience3 as _nx3_hb2
                _nx3_hb2.apply_symbol_icon(hamburger_btn)
            except Exception:
                pass

            root.update_idletasks()
            _menu_log("panel kapandı")

        except Exception as e:
            _menu_log(f"panel kapatma hata: {e}")

    def hamburger_toggle(event=None):
        try:
            w = root.winfo_width()
            _menu_log(f"tıklandı width={w}, side_manager={side_panel.winfo_manager()}")

            if w >= MINI_LIMIT:
                hedef_acik = sidebar_state.get("compact", False)
                _menu_log(f"masaüstü menü {'açılıyor' if hedef_acik else 'kapanıyor'}")
                if side_panel.winfo_manager() != "pack":
                    try:
                        side_panel.pack(side="left", fill="y", before=main_c)
                    except Exception:
                        pass
                _sidebar_layout_uygula(hedef_acik, animate=True, persist=True)
                return "break"

            if side_panel.winfo_manager() == "place":
                hamburger_panel_kapat()
            else:
                hamburger_panel_ac()

            return "break"

        except Exception as e:
            _menu_log(f"toggle hata: {e}")
            return "break"

    # CTkButton zaten command ile çalışıyor.
    # <Button-1> bind kaldırıldı; çünkü tek tıklamada iki kez toggle yapıp menüyü hemen kapatıyordu.
    try:
        root.bind("<Control-m>", hamburger_toggle)
        root.bind("<Control-M>", hamburger_toggle)
    except Exception:
        pass

    def mini_ekran_uygula(event=None):
        try:
            if _settings_overlay_aktif():
                return
            w = root.winfo_width()
            agent_modu = globals().get("_NETO_AGENT_MODU", False)
            sidebar_animating = bool(sidebar_state.get("animating"))

            if w < MINI_LIMIT:
                # Compact modda sidebar dar bir ikon rail olarak görünür kalır;
                # böylece hamburger/X her zaman kendi header''ında erişilebilir.
                try:
                    btn_text = hamburger_btn.cget("text")
                except Exception:
                    btn_text = "☰"

                if side_panel.winfo_manager() == "place" and btn_text == "×":
                    side_panel.configure(width=PANEL_WIDTH)
                    side_panel.lift()
                    hamburger_btn.lift()
                    _sidebar_layout_uygula(True, animate=False, persist=False)
                else:
                    if side_panel.winfo_manager() == "place":
                        side_panel.place_forget()
                    if side_panel.winfo_manager() != "pack":
                        side_panel.pack(side="left", fill="y", before=main_c)
                    hamburger_btn.configure(text="☰")
                    _sidebar_layout_uygula(False, animate=False, persist=True)

                _hamburger_konumla()
                hamburger_btn.lift()
                try:
                    compact_settings_btn.place_forget()
                except Exception:
                    pass

                if not sidebar_animating:
                    _neto_input_bar_konumla()
                    _input_container_genislik_uygula()
                lbl_welcome.configure(font=("Segoe UI Semibold", 23))
                etiket.configure(wraplength=max(280, w - 80), font=("Segoe UI", 13, "italic"))

            else:
                # Normal mod: sidebar geri gelir; hamburger menü artık dar/geniş geçişi yönetir.
                _hamburger_konumla()
                hamburger_btn.lift()
                compact_settings_btn.place_forget()

                if side_panel.winfo_manager() == "place":
                    try:
                        side_panel.place_forget()
                    except tk.TclError:
                        pass

                if not side_panel.winfo_ismapped():
                    side_panel.pack(side="left", fill="y", before=main_c)

                _sidebar_layout_uygula(not sidebar_state.get("compact", False), animate=False, persist=False)
                if not sidebar_animating:
                    _neto_input_bar_konumla()
                    _input_container_genislik_uygula()
                lbl_welcome.configure(font=("Segoe UI Semibold", 26))
                etiket.configure(wraplength=500, font=("Segoe UI", 14, "italic"))

            try:
                _settings_bottom_bar_place()
                settings_bottom_bar.lift()
            except Exception:
                pass
        except Exception as e:
            _menu_log(f"mini ekran hata: {e}")

    _resize_job = None

    def on_window_resize(event):
        global _resize_job
        if event.widget != root:
            return
        dimensions = (event.width, event.height)
        if getattr(root, "_neto_last_layout_size", None) == dimensions:
            return
        root._neto_last_layout_size = dimensions
        try:
            _neto_titlebar_sync_max_icon()
        except Exception:
            pass
        if _NETO_TEMA_DURUM.get("gecis_aktif"):
            return
        try:
            if _resize_job:
                root.after_cancel(_resize_job)
        except Exception:
            pass
        try:
            _resize_job = root.after(70, mini_ekran_uygula)
        except Exception:
            _resize_job = None

    root.bind("<Configure>", on_window_resize)
    root.after(300, mini_ekran_uygula)
    _neto_launch_checkpoint("Ana ekran hazırlanıyor..." if str(dil_getir()).lower() == "tr" else "Preparing home screen...", force=True)


    # ------------------------------------------------------------
    # UNIFIED IN-APP SETTINGS PAGE
    # NetOps Lab, Advanced Settings, Language, Security and Updates are embedded here.
    # ------------------------------------------------------------
    def _settings_main_content_hide():
        """Hide normal app content while the in-app Settings page is active."""
        try:
            if globals().get("extension_store_state", {}).get("open"):
                eklenti_magazasi_panel_kapat()
        except Exception:
            pass
        try:
            live_panel.pack_forget()
        except Exception:
            pass
        try:
            chat_container.pack_forget()
        except Exception:
            pass
        try:
            input_container.pack_forget()
        except Exception:
            pass

    def _settings_main_content_restore():
        """Restore the normal app surface after leaving Settings."""
        try:
            chat_container.pack(side="top", expand=True, fill="both", padx=24, pady=(12, 6))
        except Exception:
            pass

    def _neto_window_layout_apply():
        """Apply saved display assignments without opening extra app processes."""
        try:
            from neto_window_manager import apply_layout

            data = veri_yukle()
            windows = {"assistant": root}
            overlay = globals().get("now_playing_overlay")
            if overlay is not None:
                try:
                    if overlay.winfo_exists():
                        windows["now_playing"] = overlay
                except Exception:
                    pass
            page = globals().get("_NETO_AUTOMATION_PAGE")
            if page is not None:
                try:
                    if page.winfo_exists():
                        windows["automation"] = page
                except Exception:
                    pass
            apply_layout(root, data.get("neto_window_assignments"), windows=windows)
        except Exception as exc:
            try:
                print(f"[WINDOW_LAYOUT_ERROR] {exc}", flush=True)
            except Exception:
                pass
        try:
            _neto_input_bar_konumla()
            _input_container_genislik_uygula()
        except Exception:
            pass
        try:
            mini_ekran_uygula()
        except Exception:
            pass

    class _LazySettingsPageController:
        """Ayarların yüzlerce widget'ını yalnızca ilk kez açıldığında oluşturur."""
        def __init__(self):
            self._real = None
            self._creating = False

        @property
        def surface(self):
            return self._real.surface if self._real is not None else None

        @property
        def is_open(self):
            return bool(self._real is not None and self._real.is_open)

        def _ensure(self):
            if self._real is not None:
                self._real.request_close = lambda: _settings_page_close_sade()
                return self._real
            if self._creating:
                raise RuntimeError("Ayarlar hazırlanıyor; lütfen tekrar dene.")
            self._creating = True
            try:
                self._real = create_settings_page(
                    parent=app_content,
                    root=root,
                    load_data=veri_yukle,
                    save_data=veri_kaydet,
                    apply_theme=tema_uygula,
                    refresh_app_theme=lambda: globals().get("_neto_tema_yenile_planla", lambda **_k: None)(settings=True, delay=1),
                    get_asset_path=get_asset_path,
                    get_data_path=get_data_path,
                    save_language=dil_kaydet,
                    refresh_language=dil_uygula,
                    get_language=dil_getir,
                    exit_callback=root.destroy,
                    window_layout_callback=_neto_window_layout_apply,
                    on_open=_settings_main_content_hide,
                    on_close=_settings_main_content_restore,
                )
                self._real.request_close = lambda: _settings_page_close_sade()
                return self._real
            finally:
                self._creating = False

        def open(self, *args, **kwargs):
            return self._ensure().open(*args, **kwargs)

        def close(self, *args, **kwargs):
            if self._real is None:
                return None
            return self._real.close(*args, **kwargs)

        def refresh_language(self, *args, **kwargs):
            if self._real is None:
                return None
            return self._real.refresh_language(*args, **kwargs)

        def refresh_theme(self, *args, **kwargs):
            if self._real is None:
                return None
            return self._real.refresh_theme(*args, **kwargs)

    settings_page_controller = _LazySettingsPageController()
    _neto_launch_checkpoint("Ayarlar isteğe bağlı hazırlandı" if str(dil_getir()).lower() == "tr" else "Settings deferred until needed", force=True)

    def _settings_surface_bul():
        """Şu anda görünür olan uygulama içi Ayarlar kök yüzeyini bulur."""
        try:
            cached = globals().get("_settings_theme_state", {}).get("surface")
            if cached is not None and cached.winfo_exists() and cached.winfo_ismapped():
                return cached
        except Exception:
            pass
        try:
            for parent in (app_content, main_c):
                haric = {
                    globals().get("chat_container"),
                    globals().get("input_container"),
                    globals().get("live_panel"),
                    globals().get("extension_store_panel"),
                    globals().get("side_panel"),
                    globals().get("main_c"),
                }
                try:
                    children = list(parent.winfo_children())
                except Exception:
                    children = []
                for child in reversed(children):
                    if child in haric:
                        continue
                    try:
                        if not child.winfo_ismapped():
                            continue
                        if getattr(child, "_neto_surface_role", "") == "settings":
                            return child
                        texts = " | ".join(_widget_metinleri(child, limit=120)).lower()
                        if any(token in texts for token in ("ayarlar", "settings", "appearance", "görünüm", "security", "netolab")):
                            return child
                    except Exception:
                        continue
        except Exception:
            pass
        return None

    def _settings_overlay_aktif():
        try:
            if bool(globals().get("_NETO_SETTINGS_MODAL_OPEN", False)):
                return True
            surface_fn = globals().get("_settings_surface_bul")
            surface = surface_fn() if callable(surface_fn) else None
            return bool(surface is not None)
        except Exception:
            return False

    def _widget_alt_agaci(widget, limit=80):
        sonuc = []
        kuyruk = [widget]
        while kuyruk and len(sonuc) < limit:
            item = kuyruk.pop(0)
            sonuc.append(item)
            try:
                kuyruk.extend(list(item.winfo_children()))
            except Exception:
                pass
        return sonuc

    def _ctk_widget_mi(widget):
        try:
            return widget.__class__.__module__.startswith("customtkinter")
        except Exception:
            return False

    def _widget_metinleri(widget, limit=45):
        metinler = []
        for item in _widget_alt_agaci(widget, limit=limit):
            try:
                text = str(item.cget("text") or "").strip()
                if text:
                    metinler.append(text)
            except Exception:
                pass
        return metinler

    def _widget_baglam_metinleri(widget, yukari=4):
        metinler = []
        current = widget
        for _ in range(yukari + 1):
            if current is None:
                break
            metinler.extend(_widget_metinleri(current, limit=35))
            current = getattr(current, "master", None)
        return " | ".join(metinler).lower()

    def _renk_string(value):
        try:
            if isinstance(value, (list, tuple)) and value:
                # CTk iki appearance rengi döndürebilir.
                index = 1 if _neto_tema_adi(veri_yukle().get("tema")) == "dark" and len(value) > 1 else 0
                return str(value[index]).lower()
            return str(value).lower()
        except Exception:
            return ""

    _settings_theme_state = {
        "token": 0,
        "job": None,
        "schedule_job": None,
        "translate_job": None,
        "close_fallback_job": None,
        "transition_token": 0,
        "surface": None,
    }

    def _tema_deger_norm(value):
        try:
            if isinstance(value, (list, tuple)):
                return tuple(str(x).lower() for x in value)
            return str(value).lower()
        except Exception:
            return value

    def _widget_configure_degistiyse(widget, **kwargs):
        """Aynı renk zaten uygulanmışsa CTk redraw tetikleme."""
        degisecek = {}
        for key, value in kwargs.items():
            try:
                mevcut = widget.cget(key)
                if _tema_deger_norm(mevcut) == _tema_deger_norm(value):
                    continue
            except Exception:
                pass
            degisecek[key] = value
        if degisecek:
            widget.configure(**degisecek)

    def _widget_dogrudan_metinleri(widget, limit=12):
        metinler = []
        try:
            children = list(widget.winfo_children())[:limit]
        except Exception:
            children = []
        for item in children:
            try:
                text = str(item.cget("text") or "").strip()
                if text:
                    metinler.append(text)
            except Exception:
                pass
        return metinler

    def _widget_hafif_baglam(widget):
        metinler = []
        current = getattr(widget, "master", None)
        for _ in range(2):
            if current is None:
                break
            metinler.extend(_widget_dogrudan_metinleri(current, limit=14))
            current = getattr(current, "master", None)
        return " | ".join(metinler).lower()

    def _settings_widget_tema_uygula(widget, surface, palet):
        vurgu = palet.get("neon", "#22C55E")
        vurgu_hover = palet.get("accent_hover", palet["button_hover"])
        vurgu_text = palet.get("accent_text", _tema_vurgu_metin_rengi())
        nav_adlari = {
            "general", "genel", "appearance", "görünüm", "gorunum",
            "system", "sistem",
            "netolab", "security", "güvenlik", "guvenlik",
            "updates", "güncellemeler", "guncellemeler", "about", "hakkında", "hakkinda",
        }

        # CTk'nin kendi iç tk.Canvas nesnelerine dokunma. Sadece gerçekten dışarıdan
        # eklenmiş Tk widget'larını hafifçe güncelle.
        if not _ctk_widget_mi(widget):
            master = getattr(widget, "master", None)
            if _ctk_widget_mi(master):
                return
            try:
                if isinstance(widget, tk.Text):
                    widget.configure(bg=palet["entry_bg"], fg=palet["text_main"], insertbackground=palet["text_main"])
                elif isinstance(widget, tk.Entry):
                    widget.configure(bg=palet["entry_bg"], fg=palet["text_main"], insertbackground=palet["text_main"])
                elif isinstance(widget, tk.Label):
                    widget.configure(bg=palet["bg"], fg=palet["text_main"])
            except Exception:
                pass
            return

        if isinstance(widget, ctk.CTkScrollableFrame):
            _neto_scrollable_frame_renklendir(widget, palet, "bg")

        elif isinstance(widget, ctk.CTkFrame):
            current_fg = _renk_string(widget.cget("fg_color"))
            if current_fg == "transparent":
                return
            try:
                radius = int(float(widget.cget("corner_radius")))
            except Exception:
                radius = 0
            texts = " | ".join(_widget_dogrudan_metinleri(widget, limit=10)).lower()
            settings_header = any(k in texts for k in (
                "all neto assistant settings in one place",
                "tüm neto asistan ayarları tek yerde",
                "neto asistan'ın tüm ayarları tek yerde",
                "neto asistan’ın tüm ayarları tek yerde",
            ))
            hedef_fg = palet["bg"] if widget is surface or settings_header or radius < 8 else palet["card"]
            kwargs = {"fg_color": hedef_fg}
            try:
                if int(widget.cget("border_width")) > 0:
                    kwargs["border_color"] = palet["entry_border"]
            except Exception:
                pass
            _widget_configure_degistiyse(widget, **kwargs)

        elif isinstance(widget, ctk.CTkLabel):
            text = str(widget.cget("text") or "").strip()
            lower = text.lower()
            is_desc = (
                text.endswith(".") or len(text) > 34 or
                any(k in lower for k in ("seç.", "select ", "changes are", "değişiklik", "koyu veya", "dark or light", "ayarları tek yerde"))
            )
            _widget_configure_degistiyse(
                widget,
                fg_color="transparent",
                text_color=palet["text_dim"] if is_desc else palet["text_main"],
            )

        elif isinstance(widget, ctk.CTkButton):
            text = str(widget.cget("text") or "").strip()
            tail = re.sub(r"^[^A-Za-zÇĞİÖŞÜçğıöşü]+", "", text).strip().lower()
            current_fg = _renk_string(widget.cget("fg_color"))
            if tail in nav_adlari:
                selected = current_fg not in {"transparent", palet["bg"].lower(), palet["sidebar"].lower()}
                _widget_configure_degistiyse(
                    widget,
                    fg_color=vurgu if selected else "transparent",
                    hover_color=vurgu_hover if selected else palet["button_hover"],
                    text_color=vurgu_text if selected else palet["text_main"],
                )
            else:
                _widget_configure_degistiyse(widget, hover_color=palet["button_hover"], text_color=palet["text_main"])

        elif isinstance(widget, ctk.CTkOptionMenu):
            context = _widget_hafif_baglam(widget)
            is_accent = any(k in context for k in ("vurgu rengi", "accent color", "renk teması", "color theme"))
            kwargs = {
                "fg_color": palet["entry_bg"],
                "button_color": vurgu,
                "button_hover_color": vurgu_hover,
                "dropdown_fg_color": palet["card"],
                "dropdown_hover_color": palet["button_hover"],
                "text_color": palet["text_main"],
            }
            if is_accent:
                try:
                    widget.cget("border_color")
                    kwargs["border_color"] = vurgu
                except Exception:
                    pass
            _widget_configure_degistiyse(widget, **kwargs)
            try:
                dropdown = getattr(widget, "_dropdown_menu", None)
                if dropdown is not None:
                    dropdown.configure(
                        fg_color=palet["card"],
                        hover_color=palet["button_hover"],
                        text_color=palet["text_main"],
                    )
            except Exception:
                pass

        elif isinstance(widget, ctk.CTkComboBox):
            _widget_configure_degistiyse(
                widget,
                fg_color=palet["entry_bg"], border_color=palet["entry_border"],
                button_color=vurgu, button_hover_color=vurgu_hover,
                dropdown_fg_color=palet["card"], dropdown_hover_color=palet["button_hover"],
                text_color=palet["text_main"],
            )

        elif isinstance(widget, ctk.CTkSwitch):
            _widget_configure_degistiyse(
                widget,
                progress_color=vurgu,
                button_color=palet["entry_border"],
                button_hover_color=palet["button_hover"],
                text_color=palet["text_main"],
            )

        elif isinstance(widget, ctk.CTkSegmentedButton):
            _widget_configure_degistiyse(
                widget,
                fg_color=palet["entry_bg"], selected_color=vurgu,
                selected_hover_color=vurgu_hover, unselected_color=palet["card"],
                unselected_hover_color=palet["button_hover"], text_color=palet["text_main"],
            )

        elif isinstance(widget, ctk.CTkEntry):
            _widget_configure_degistiyse(widget, fg_color=palet["entry_bg"], border_color=palet["entry_border"], text_color=palet["text_main"])

        elif isinstance(widget, ctk.CTkTextbox):
            _widget_configure_degistiyse(widget, fg_color=palet["entry_bg"], border_color=palet["entry_border"], text_color=palet["text_main"])

        elif hasattr(ctk, "CTkScrollbar") and isinstance(widget, ctk.CTkScrollbar):
            _widget_configure_degistiyse(widget, button_color=palet["entry_border"], button_hover_color=palet["button_hover"])

    def _settings_tema_agaci_yenile():
        """Ayarlar ağacını küçük partilerde boyar; ana event loop kilitlenmez."""
        surface = _settings_surface_bul()
        if surface is None:
            return

        _settings_theme_state["token"] += 1
        token = _settings_theme_state["token"]
        try:
            old_job = _settings_theme_state.get("job")
            if old_job:
                root.after_cancel(old_job)
        except Exception:
            pass

        widgets = _widget_alt_agaci(surface, limit=900)
        palet = dict(aktif_palet)
        try:
            _widget_configure_degistiyse(surface, fg_color=palet["bg"])
        except Exception:
            pass

        chunk_size = 96

        def _parca(index=0):
            if token != _settings_theme_state.get("token"):
                return
            son = min(len(widgets), index + chunk_size)
            for widget in widgets[index:son]:
                try:
                    _settings_widget_tema_uygula(widget, surface, palet)
                except Exception:
                    pass
            if son < len(widgets):
                try:
                    _settings_theme_state["job"] = root.after(1, lambda: _parca(son))
                except Exception:
                    pass
            else:
                _settings_theme_state["job"] = None

        _parca(0)

    def _settings_duzeltmeleri_planla(translate=False, delay=14):
        """Art arda gelen tema/sekme olaylarını tek yenilemede birleştirir."""
        try:
            old = _settings_theme_state.get("schedule_job")
            if old:
                root.after_cancel(old)
        except Exception:
            pass
        try:
            _settings_theme_state["schedule_job"] = root.after(max(0, int(delay)), _settings_tema_agaci_yenile)
        except Exception:
            _settings_tema_agaci_yenile()

        if translate:
            try:
                old = _settings_theme_state.get("translate_job")
                if old:
                    root.after_cancel(old)
            except Exception:
                pass
            try:
                _settings_theme_state["translate_job"] = root.after(max(20, int(delay) + 24), _arayuz_metnini_derin_yenile)
            except Exception:
                pass

    _settings_page_open_original = settings_page_controller.open
    _settings_page_close_original = settings_page_controller.close
    _settings_page_language_original = settings_page_controller.refresh_language
    _settings_page_theme_original = settings_page_controller.refresh_theme

    def _settings_sidebar_prepare_hidden():
        """Place the sidebar offscreen while the settings surface is closing."""
        try:
            if root.winfo_width() < MINI_LIMIT or not side_panel.winfo_exists():
                return None
            target = PANEL_WIDTH if not sidebar_state.get("compact", False) else sidebar_compact_width
            engine = _neto_motion()
            if engine is not None:
                engine.cancel("settings-sidebar-reveal")
            if side_panel.winfo_manager() == "pack":
                side_panel.pack_forget()
            elif side_panel.winfo_manager() == "place":
                side_panel.place_forget()
            side_panel.configure(width=target)
            side_panel.place(x=-target, y=0, relheight=1)
            side_panel.lift()
            side_panel._neto_settings_slide = True
            return target
        except Exception:
            return None

    def _settings_sidebar_pack_visible():
        """Return the settings sidebar to the normal desktop pack layout."""
        side_panel.place_forget()
        try:
            side_panel.pack(side="left", fill="y", before=main_c)
        except Exception:
            # A transient Tk pack-order error must not leave the panel in place mode.
            try:
                side_panel.pack(side="left", fill="y")
            except Exception:
                pass

    def _settings_sidebar_restore_after_cancel():
        """Restore a prepared sidebar if settings is reopened mid-transition."""
        try:
            if not getattr(side_panel, "_neto_settings_slide", False):
                return
            engine = _neto_motion()
            if engine is not None:
                engine.cancel("settings-sidebar-reveal")
            _settings_sidebar_pack_visible()
            target = PANEL_WIDTH if not sidebar_state.get("compact", False) else sidebar_compact_width
            _sidebar_genislik_uygula(target)
            _sidebar_metinleri_yenile()
            side_panel._neto_settings_slide = False
        except Exception:
            pass

    def _settings_sidebar_reveal(target):
        """Reveal the normal sidebar from the left after settings closes."""
        if not target:
            mini_ekran_uygula()
            return
        engine = _neto_motion()
        finished = {"value": False}
        fallback_job = {"id": None}

        def finish():
            if finished["value"] or not getattr(side_panel, "_neto_settings_slide", False):
                return
            finished["value"] = True
            if fallback_job["id"] is not None:
                try:
                    root.after_cancel(fallback_job["id"])
                except Exception:
                    pass
            try:
                if not side_panel.winfo_exists():
                    return
                _settings_sidebar_pack_visible()
                _sidebar_genislik_uygula(target, update_bottom=False)
                side_panel._neto_settings_slide = False

                def settle_layout():
                    # Repack only after the slide has visually completed. The
                    # animation frame stays cheap and the final refresh happens once.
                    try:
                        if _settings_overlay_aktif() or getattr(side_panel, "_neto_settings_slide", False):
                            return
                        _sidebar_metinleri_yenile()
                        _settings_bottom_bar_place()
                        _neto_input_bar_konumla()
                        if root.winfo_width() < MINI_LIMIT:
                            mini_ekran_uygula()
                    except Exception:
                        pass

                root.after_idle(settle_layout)
            except Exception:
                pass

        if engine is None:
            finish()
            return

        def update(x):
            try:
                if side_panel.winfo_exists():
                    side_panel.place_configure(x=round(x))
            except Exception:
                engine.cancel("settings-sidebar-reveal")

        engine.number(
            "settings-sidebar-reveal",
            -target,
            0,
            update,
            duration_ms=190,
            easing="ease_out_quart",
            on_complete=finish,
        )
        # If the Tk clock is delayed by a heavy callback, complete the same
        # transition instead of leaving the sidebar in offscreen place mode.
        try:
            fallback_job["id"] = root.after(240, finish)
        except Exception:
            pass

    def _settings_page_open_sade(section="general"):
        workspace_close = globals().get("_neto_workspace_close")
        if callable(workspace_close) and globals().get("_neto_workspace_state", {}).get("surface") is not None:
            workspace_close(run_protocol=False)
        engine = _neto_motion()
        if engine is not None:
            engine.cancel("settings-transition")
            engine.cancel("settings-sidebar-reveal")
        try:
            pending = _settings_theme_state.get("close_fallback_job")
            if pending:
                root.after_cancel(pending)
        except Exception:
            pass
        _settings_theme_state["close_fallback_job"] = None
        _settings_theme_state["transition_token"] += 1
        _settings_sidebar_restore_after_cancel()
        _settings_theme_state["closing"] = False
        _sidebar_animasyonu_dondur()
        globals()["_NETO_SETTINGS_MODAL_OPEN"] = True
        result = _settings_page_open_original(section)
        if not result:
            globals()["_NETO_SETTINGS_MODAL_OPEN"] = False
            return result
        _settings_theme_state["surface"] = settings_page_controller.surface
        _neto_bind_hover_tree(settings_page_controller.surface)
        _neto_modal_fade_slide("settings-open")
        return result

    def _settings_page_close_sade():
        if _settings_theme_state.get("closing"):
            return True
        _settings_theme_state["closing"] = True
        _settings_theme_state["transition_token"] += 1
        transition_token = _settings_theme_state["transition_token"]
        for state_key in ("job", "schedule_job", "translate_job"):
            try:
                pending = _settings_theme_state.get(state_key)
                if pending:
                    root.after_cancel(pending)
            except Exception:
                pass
            _settings_theme_state[state_key] = None
        sidebar_target = _settings_sidebar_prepare_hidden()
        sidebar_reveal_started = False

        def reveal_sidebar_once():
            nonlocal sidebar_reveal_started
            if sidebar_reveal_started:
                return
            sidebar_reveal_started = True
            _settings_sidebar_reveal(sidebar_target)

        def close_now():
            if transition_token != _settings_theme_state.get("transition_token"):
                return
            engine = _neto_motion()
            if engine is not None:
                engine.cancel("settings-transition")
            try:
                _settings_page_close_original()
            except Exception:
                pass
            globals()["_NETO_SETTINGS_MODAL_OPEN"] = False
            _settings_theme_state["surface"] = None
            _settings_theme_state["closing"] = False
            _settings_theme_state["close_fallback_job"] = None
            reveal_sidebar_once()

        def force_close_if_stuck():
            if (
                _settings_theme_state.get("closing")
                and transition_token == _settings_theme_state.get("transition_token")
            ):
                close_now()

        # Start the sidebar reveal with the modal close so the two transitions
        # finish together instead of leaving a visible pause between them.
        try:
            root.after(0, reveal_sidebar_once)
        except Exception:
            reveal_sidebar_once()
        _neto_modal_fade_slide("settings-close", closing=True, on_mid=close_now)
        try:
            _settings_theme_state["close_fallback_job"] = root.after(420, force_close_if_stuck)
        except Exception:
            force_close_if_stuck()
        return True
    def _settings_page_language_sade():
        try:
            sonuc = _settings_page_language_original()
        except Exception:
            sonuc = None
        _settings_duzeltmeleri_planla(translate=True, delay=18)
        return sonuc

    def _settings_page_theme_sade():
        try:
            sonuc = _settings_page_theme_original()
        except Exception:
            sonuc = None
        _settings_duzeltmeleri_planla(translate=False, delay=8)
        return sonuc

    globals()["_neto_settings_page_open"] = _settings_page_open_sade
    globals()["_neto_settings_page_close"] = _settings_page_close_sade
    globals()["_neto_settings_page_refresh_language"] = _settings_page_language_sade
    globals()["_neto_settings_page_refresh_theme"] = _settings_page_theme_sade
    globals()["_neto_settings_theme_repair"] = _settings_tema_agaci_yenile

    def _settings_click_repair(event=None):
        # Section renderers own their palette; rewalking the tree caused flashes.
        if (
            _settings_overlay_aktif()
            and not _settings_theme_state.get("closing")
            and settings_page_controller.surface is not None
        ):
            if _settings_theme_state.get("hover_repair_job"):
                return

            def _run_hover_repair():
                _settings_theme_state["hover_repair_job"] = None
                if (
                    _settings_overlay_aktif()
                    and not _settings_theme_state.get("closing")
                    and settings_page_controller.surface is not None
                ):
                    _neto_bind_hover_tree(settings_page_controller.surface)

            try:
                _settings_theme_state["hover_repair_job"] = root.after(120, _run_hover_repair)
            except Exception:
                _settings_theme_state["hover_repair_job"] = None

    try:
        root.bind_all("<ButtonRelease-1>", _settings_click_repair, add="+")
    except Exception:
        pass


    # ------------------------------------------------------------
    # NETO CODE + NETO AI UYGULAMA İÇİ ÇALIŞMA ALANI
    # Eski modüller CTkToplevel oluştursa bile geçici bir uyumluluk katmanı
    # ile ana pencerenin orta alanına yerleştirilir.
    # ------------------------------------------------------------
    _neto_workspace_state = {
        "surface": None, "body": None, "title": None, "subtitle": None,
        "embedded": None, "selected": None, "close_protocol": None,
        "fallback": None, "closing": False, "theme_job": None,
    }

    def _neto_workspace_button_states(selected=None):
        for btn in (cast(Any, globals().get("btn_netoai")),):
            try:
                if btn is selected:
                    cast(Any, btn).configure(
                        fg_color=aktif_palet["neon"],
                        hover_color=aktif_palet.get("accent_hover", aktif_palet["button_hover"]),
                        text_color=_tema_vurgu_metin_rengi(),
                    )
                else:
                    cast(Any, btn).configure(
                        fg_color=aktif_palet["card"], hover_color=aktif_palet["button_hover"],
                        text_color=aktif_palet["text_main"],
                    )
            except Exception:
                pass

    def _neto_workspace_close(run_protocol=False):
        if _neto_workspace_state.get("closing"):
            return
        _neto_workspace_state["closing"] = True
        try:
            protocol = _neto_workspace_state.get("close_protocol")
            _neto_workspace_state["close_protocol"] = None
            if run_protocol and callable(protocol):
                try:
                    protocol()
                except Exception:
                    pass
            surface = _neto_workspace_state.get("surface")
            embedded = _neto_workspace_state.get("embedded")
            # neto_chat keeps a module-level singleton. Clear only the window
            # that belongs to this embedded surface, otherwise the next open
            # may focus a destroyed widget and leave an empty workspace.
            try:
                chat_module = sys.modules.get("neto_chat")
                chat_window = getattr(chat_module, "_NETO_CHAT_WINDOW", None)
                chat_widget = getattr(chat_window, "chat", None)
                if chat_module is not None and (
                    chat_widget is embedded
                    or chat_widget is None
                    or not chat_widget.winfo_exists()
                ):
                    chat_module._NETO_CHAT_WINDOW = None
            except Exception:
                pass
            if surface is not None:
                try:
                    ctk.CTkFrame.destroy(surface)
                except Exception:
                    try:
                        surface.destroy()
                    except Exception:
                        pass
            _neto_workspace_state.update({
                "surface": None, "body": None, "title": None, "subtitle": None,
                "embedded": None, "selected": None, "close_protocol": None,
                "fallback": None, "back": None, "header": None, "accent_line": None,
            })
            _neto_workspace_button_states(None)
            _settings_main_content_restore()
        finally:
            _neto_workspace_state["closing"] = False

    def _neto_workspace_create(title, subtitle="", selected=None):
        try:
            settings_page_controller.close()
        except Exception:
            pass
        try:
            if _neto_workspace_state.get("surface") is not None:
                _neto_workspace_close(run_protocol=False)
        except Exception:
            pass
        _settings_main_content_hide()

        surface = ctk.CTkFrame(main_c, fg_color=aktif_palet["bg"], corner_radius=0)
        try:
            setattr(surface, "_neto_surface_role", "workspace")
        except Exception:
            pass
        surface.pack(fill="both", expand=True, padx=24, pady=(18, 18))
        header = ctk.CTkFrame(surface, fg_color=aktif_palet["card"], corner_radius=14)
        header.pack(fill="x", pady=(0, 10))
        back = ctk.CTkButton(
            header, text="←", width=46, height=42, corner_radius=12,
            fg_color=aktif_palet["neon"],
            hover_color=aktif_palet.get("accent_hover", aktif_palet["button_hover"]),
            text_color=_tema_vurgu_metin_rengi(),
            command=lambda: _neto_workspace_close(run_protocol=True),
        )
        back.pack(side="left", padx=12, pady=12)
        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left", fill="x", expand=True, pady=9)
        title_label = ctk.CTkLabel(
            title_box, text=title, anchor="w", text_color=aktif_palet["text_main"],
            font=("Segoe UI Semibold", 24),
        )
        title_label.pack(fill="x")
        subtitle_label = ctk.CTkLabel(
            title_box, text=subtitle, anchor="w", text_color=aktif_palet["text_dim"],
            font=("Segoe UI", 11),
        )
        subtitle_label.pack(fill="x")
        body = ctk.CTkFrame(
            surface, fg_color=aktif_palet["sidebar"], corner_radius=14,
            border_width=1, border_color=aktif_palet["entry_border"],
        )
        body.pack(fill="both", expand=True)

        accent_line = ctk.CTkFrame(header, height=4, width=1, fg_color=aktif_palet["neon"], corner_radius=2)
        accent_line.place(x=0, rely=1.0, anchor="sw")
        _neto_workspace_state.update({
            "surface": surface, "body": body, "title": title_label,
            "subtitle": subtitle_label, "selected": selected,
            "back": back, "header": header, "accent_line": accent_line,
        })
        _neto_workspace_button_states(selected)
        def _workspace_line_anim(step=0):
            try:
                if not header.winfo_exists():
                    return
                header.update_idletasks()
                total = max(160, header.winfo_width())
                t = min(1.0, step / 18)
                eased = 1.0 - ((1.0 - t) ** 4)
                accent_line.configure(width=max(1, int(total * eased)))
                if step < 18:
                    root.after(12, lambda: _workspace_line_anim(step + 1))
            except Exception:
                pass
        root.after(12, _workspace_line_anim)
        root.after(12, lambda: _neto_page_reveal(title))
        return body

    class _NetoEmbeddedToplevel(ctk.CTkFrame):
        """CTkToplevel API'sinin uygulama içi CTkFrame uyumluluk karşılığı.

        Bu nesne gerçek bir *sınıf* olarak tutulur. Böylece kaldırılmış gömülü editör içindeki
        ``isinstance(pencere, ctk.CTkToplevel)`` kontrolleri bozulmaz. Eski
        sürüm CTkToplevel'i bir factory fonksiyonuyla değiştirdiği için
        ``isinstance() arg 2 must be a type`` hatası oluşuyordu.
        """
        def __new__(cls, *args, **kwargs):
            existing = _neto_workspace_state.get("embedded")
            try:
                if existing is not None and existing.winfo_exists():
                    return existing
            except Exception:
                pass
            return super().__new__(cls)

        def __init__(self, master=None, *args, **kwargs):
            # Bazı eski kaldırılmış gömülü editör sürümleri aynı açılış sırasında iki ayrı
            # CTkToplevel oluşturuyor. __new__ mevcut yüzeyi döndürürse ikinci
            # __init__ çağrısında widget'ı yeniden kurma.
            if getattr(self, "_neto_embedded_initialized", False):
                return
            body = _neto_workspace_state.get("body")
            if body is None:
                raise RuntimeError("NetOps çalışma alanı hazırlanmadı.")
            kwargs.pop("takefocus", None)
            kwargs.setdefault("fg_color", aktif_palet["sidebar"])
            kwargs.setdefault("corner_radius", 0)
            super().__init__(body, *args, **kwargs)
            self.pack(fill="both", expand=True)
            self._neto_title = ""
            self._neto_embedded_initialized = True
            _neto_workspace_state["embedded"] = self

        def title(self, value=None):
            if value is None:
                return self._neto_title
            self._neto_title = str(value)
            try:
                _neto_workspace_state["title"].configure(text=self._neto_title)
            except Exception:
                pass
            return None
        wm_title = title
        def geometry(self, value=None): return "" if value is None else None
        wm_geometry = geometry
        def resizable(self, *args, **kwargs): return None
        wm_resizable = resizable
        def minsize(self, *args, **kwargs): return None
        wm_minsize = minsize
        def maxsize(self, *args, **kwargs): return None
        wm_maxsize = maxsize
        def transient(self, *args, **kwargs): return None
        wm_transient = transient
        def grab_set(self, *args, **kwargs): return None
        def grab_release(self, *args, **kwargs): return None
        def attributes(self, *args, **kwargs): return None
        wm_attributes = attributes
        def iconbitmap(self, *args, **kwargs): return None
        wm_iconbitmap = iconbitmap
        def iconphoto(self, *args, **kwargs): return None
        wm_iconphoto = iconphoto
        def overrideredirect(self, *args, **kwargs): return None
        def mainloop(self, *args, **kwargs): return None
        def state(self, value=None): return "normal"
        wm_state = state
        def protocol(self, name=None, func=None):
            if str(name or "").upper() == "WM_DELETE_WINDOW" and callable(func):
                _neto_workspace_state["close_protocol"] = func
            return None
        wm_protocol = protocol
        def withdraw(self):
            try: self.pack_forget()
            except Exception: pass
        def deiconify(self):
            try: self.pack(fill="both", expand=True)
            except Exception: pass
        def focus(self):
            try: self.focus_set()
            except Exception: pass
        focus_force = focus
        def destroy(self):
            _neto_workspace_close(run_protocol=False)

    def _neto_workspace_show_fallback(title, detail):
        """Keep a failed workspace useful instead of showing an empty black page."""
        body = _neto_workspace_state.get("body")
        if body is None:
            return None
        try:
            for child in list(body.winfo_children()):
                child.destroy()
        except Exception:
            pass
        card = ctk.CTkFrame(
            body,
            fg_color=aktif_palet["card"],
            border_width=1,
            border_color=aktif_palet["entry_border"],
            corner_radius=18,
        )
        card.pack(fill="both", expand=True, padx=24, pady=24)
        ctk.CTkLabel(
            card,
            text=str(title),
            text_color=aktif_palet["text_main"],
            font=("Segoe UI Semibold", 20),
            anchor="w",
        ).pack(fill="x", padx=22, pady=(24, 8))
        ctk.CTkLabel(
            card,
            text=str(detail),
            text_color=aktif_palet["text_dim"],
            font=("Segoe UI", 12),
            justify="left",
            anchor="nw",
            wraplength=560,
        ).pack(fill="both", expand=True, padx=22, pady=(0, 18))
        ctk.CTkButton(
            card,
            text="Kapat",
            width=110,
            height=36,
            corner_radius=11,
            fg_color=aktif_palet["neon"],
            hover_color=aktif_palet.get("accent_hover", aktif_palet["button_hover"]),
            text_color=_tema_vurgu_metin_rengi(),
            command=lambda: _neto_workspace_close(run_protocol=False),
        ).pack(anchor="e", padx=22, pady=(0, 22))
        _neto_workspace_state["fallback"] = card
        return card

    def _neto_workspace_embed_call(open_fn, title, subtitle, selected, *args, **kwargs):
        _neto_workspace_create(title, subtitle, selected)
        function_globals = getattr(open_fn, "__globals__", {}) or {}
        restore = []

        # CTkToplevel/Toplevel yerine factory fonksiyonu değil gerçek sınıf
        # koyuyoruz. kaldırılmış gömülü editör kendi içinde isinstance(..., CTkToplevel)
        # kullandığında ikinci argüman type olarak kalır ve çökmez.
        embedded_class = _NetoEmbeddedToplevel

        for module_key, attr in (("ctk", "CTkToplevel"), ("tk", "Toplevel")):
            module = function_globals.get(module_key)
            if module is not None and hasattr(module, attr):
                try:
                    old = getattr(module, attr)
                    restore.append((module, attr, old))
                    setattr(module, attr, embedded_class)
                except Exception:
                    pass
        for direct_key in ("CTkToplevel", "Toplevel"):
            if direct_key in function_globals:
                try:
                    old = function_globals[direct_key]
                    restore.append((function_globals, direct_key, old))
                    function_globals[direct_key] = embedded_class
                except Exception:
                    pass

        try:
            result = open_fn(*args, **kwargs)
            try:
                root.update_idletasks()
            except Exception:
                pass
            if _neto_workspace_state.get("embedded") is None:
                raise RuntimeError("Modül uygulama içi yüzey oluşturmadı.")
            root.after(20, _neto_workspace_theme_refresh)
            return result
        except Exception as exc:
            try:
                print(f"[WORKSPACE_OPEN_ERROR] {title}: {exc}", flush=True)
            except Exception:
                pass
            # Leave a visible recovery card in the already-created workspace.
            # The old behavior destroyed the surface and exposed a black page.
            return _neto_workspace_show_fallback(
                title,
                "Agent sohbet yüzeyi hazırlanamadı. Ana ekran çalışmaya devam ediyor.\n\n"
                f"Teknik ayrıntı: {exc}",
            )
        finally:
            for target, attr, old in reversed(restore):
                try:
                    if isinstance(target, dict): target[attr] = old
                    else: setattr(target, attr, old)
                except Exception:
                    pass

    def _neto_workspace_theme_refresh():
        surface = _neto_workspace_state.get("surface")
        if surface is None:
            return
        try:
            surface.configure(fg_color=aktif_palet["bg"])
            _neto_workspace_state["header"].configure(fg_color=aktif_palet["card"])
            _neto_workspace_state["body"].configure(
                fg_color=aktif_palet["sidebar"], border_color=aktif_palet["entry_border"],
            )
            _neto_workspace_state["back"].configure(
                fg_color=aktif_palet["neon"],
                hover_color=aktif_palet.get("accent_hover", aktif_palet["button_hover"]),
                text_color=_tema_vurgu_metin_rengi(),
            )
            _neto_workspace_state["title"].configure(text_color=aktif_palet["text_main"])
            _neto_workspace_state["subtitle"].configure(text_color=aktif_palet["text_dim"])
            embedded = _neto_workspace_state.get("embedded")
            if embedded is not None and embedded.winfo_exists():
                embedded.configure(fg_color=aktif_palet["sidebar"])
        except Exception:
            pass
        _neto_workspace_button_states(_neto_workspace_state.get("selected"))


    def neto_ai_chat_uygulama_icinde_ac():
        chat_module = _neto_lazy_import("neto_chat")
        existing = getattr(chat_module, "_NETO_CHAT_WINDOW", None)
        current = _neto_workspace_state.get("embedded")
        try:
            if existing is not None and current is getattr(existing, "chat", None) and current.winfo_exists():
                existing.odakla()
                return existing
        except Exception:
            pass
        if existing is not None:
            try:
                if getattr(existing, "chat", None) is not None and existing.chat.winfo_exists():
                    existing._kapat()
            except Exception:
                pass
            try:
                chat_module._NETO_CHAT_WINDOW = None
            except Exception:
                pass
        return _neto_workspace_embed_call(
            chat_module.neto_chat_ac, f"{APP_NAME} Agent",
            "Yapay zekâ sohbeti ana uygulamanın içinde." if str(dil_getir()).lower().startswith("tr") else "AI chat embedded inside NetOps.",
            globals().get("btn_netoai"), root,
        )

    def _neto_ai_hazirlama_yuzeyi_ac():
        _neto_workspace_create(T("ai_start_title"), T("ai_preparing"), globals().get("btn_netoai"))
        return _NetoEmbeddedToplevel(root)

    globals()["neto_ai_chat_uygulama_icinde_ac"] = neto_ai_chat_uygulama_icinde_ac
    globals()["_neto_ai_hazirlama_yuzeyi_ac"] = _neto_ai_hazirlama_yuzeyi_ac
    globals()["_neto_workspace_theme_refresh"] = _neto_workspace_theme_refresh

    # ------------------------------------------------------------
    # ANA UYGULAMA İÇİ KAYDIRMALI EKLENTİ MAĞAZASI
    # v1.38: Kartlar yalnızca bir kez ve küçük partiler halinde oluşturulur.
    # Panel açılırken widget ağacını silip yeniden kurmadığı için takılma yapmaz.
    # ------------------------------------------------------------
    extension_store_state = {
        "open": False,
        "x": 0,
        "target": 0,
        "animating": False,
        "busy": False,
        "built": False,
        "building": False,
        "build_index": 0,
        "animation_token": 0,
        "search_job": None,
        "last_filter": None,
    }

    def store_lang():
        try:
            return "tr" if str(dil_getir()).lower().startswith("tr") else "en"
        except Exception:
            return "en"

    def store_text(key) -> str:
        texts = {
            "tr": {
                "description": "Uygulamaları Asistan içinde hızlıca aç.",
                "search": "Eklentilerde ara...",
                "hint": "Açmak için tıkla",
                "open": "Aç",
                "no_results": "Sonuç bulunamadı.",
                "loading": "Mağaza hazırlanıyor...",
                "extensions_off": "Eklentiler kapalı. Önce Eklenti Durumu'nu AÇIK yap.",
                "open_error": "Eklenti açılamadı: {error}",
            },
            "en": {
                "description": "Open apps quickly inside Assistant.",
                "search": "Search extensions...",
                "hint": "Click to open",
                "open": "Open",
                "no_results": "No results found.",
                "loading": "Preparing store...",
                "extensions_off": "Extensions are off. Turn Extension Status ON first.",
                "open_error": "Extension could not be opened: {error}",
            },
        }
        return str(texts.get(store_lang(), texts["en"]).get(key, key))

    extension_store_panel = ctk.CTkFrame(
        app_content,
        width=300,
        fg_color=aktif_palet["sidebar"],
        corner_radius=0,
        border_width=1,
        border_color=aktif_palet["card"]
    )
    extension_store_panel.pack_propagate(False)

    store_header = ctk.CTkFrame(extension_store_panel, fg_color="transparent")
    store_header.pack(fill="x", padx=16, pady=(18, 8))

    store_title = ctk.CTkLabel(
        store_header,
        text=T("extension_store"),
        text_color=aktif_palet["text_main"],
        font=("Segoe UI Semibold", 17),
        anchor="w"
    )
    store_title.pack(side="left", fill="x", expand=True)

    store_close_btn = ctk.CTkButton(
        store_header,
        text="✕",
        width=36,
        height=32,
        corner_radius=8,
        fg_color=aktif_palet["card"],
        hover_color=aktif_palet["button_hover"],
        text_color=aktif_palet["text_main"],
        command=lambda: eklenti_magazasi_panel_kapat()
    )
    store_close_btn.pack(side="right")

    store_desc_label = ctk.CTkLabel(
        extension_store_panel,
        text=store_text("description"),
        text_color=aktif_palet["text_dim"],
        font=("Segoe UI", 12),
        anchor="w"
    )
    store_desc_label.pack(fill="x", padx=18, pady=(0, 10))

    store_search = ctk.CTkEntry(
        extension_store_panel,
        placeholder_text=store_text("search"),
        fg_color=aktif_palet["entry_bg"],
        text_color=aktif_palet["text_main"],
        border_color=aktif_palet["entry_border"],
        height=34,
        corner_radius=10
    )
    store_search.pack(fill="x", padx=16, pady=(0, 10))

    store_apps_frame = ctk.CTkScrollableFrame(
        extension_store_panel,
        fg_color="transparent",
        height=360
    )
    store_apps_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
    _neto_scrollable_frame_renklendir(store_apps_frame, aktif_palet, "sidebar")

    # Mağaza uygulama listesi. Kartlar açılışta tekrar tekrar üretilmez.
    eklentiler = [
        (f"{APP_NAME} Browser", "https://www.google.com"),
        ("YouTube", "https://www.youtube.com"),
        ("WhatsApp", "https://web.whatsapp.com"),
        ("X", "https://twitter.com"),
        ("Instagram", "https://instagram.com"),
        ("Spotify", "https://open.spotify.com"),
        ("Twitch", "https://twitch.tv"),
        ("GitHub", "https://github.com"),
        ("Google Maps", "https://maps.google.com")
    ]

    store_icons = {
        f"{APP_NAME} Browser": "🌐",
        "YouTube": "▶️",
        "WhatsApp": "💬",
        "X": "𝕏",
        "Instagram": "📸",
        "Spotify": "🎵",
        "Twitch": "📹",
        "GitHub": "💻",
        "Google Maps": "🗺️",
    }

    store_app_cards = []

    store_loading_label = ctk.CTkLabel(
        store_apps_frame,
        text=store_text("loading"),
        text_color=aktif_palet["text_dim"],
        font=("Segoe UI", 12)
    )

    store_empty_label = ctk.CTkLabel(
        store_apps_frame,
        text=store_text("no_results"),
        text_color=aktif_palet["text_dim"],
        font=("Segoe UI", 12)
    )

    def store_app_ac(url):
        try:
            if not eklenti_aktif_mi:
                animasyonlu_yazi(store_text("extensions_off"))
                return
            neto_browser_ac(url)
        except Exception as e:
            animasyonlu_yazi(store_text("open_error").format(error=e))

    def _store_create_card(isim, url):
        ikon = store_icons.get(isim, "▣")

        card = ctk.CTkFrame(
            store_apps_frame,
            fg_color=aktif_palet["card"],
            corner_radius=12,
            border_width=1,
            border_color=aktif_palet["entry_border"]
        )
        card.pack(fill="x", padx=4, pady=6)

        icon_lbl = ctk.CTkLabel(
            card,
            text=ikon,
            font=("Segoe UI", 22),
            text_color=aktif_palet["text_main"],
            width=42
        )
        icon_lbl.pack(side="left", padx=(12, 6), pady=10)

        text_box = ctk.CTkFrame(card, fg_color="transparent")
        text_box.pack(side="left", fill="x", expand=True, pady=8)

        name_lbl = ctk.CTkLabel(
            text_box,
            text=isim,
            font=("Segoe UI Semibold", 13),
            text_color=aktif_palet["text_main"],
            anchor="w"
        )
        name_lbl.pack(fill="x")

        hint_lbl = ctk.CTkLabel(
            text_box,
            text=store_text("hint"),
            font=("Segoe UI", 11),
            text_color=aktif_palet["text_dim"],
            anchor="w"
        )
        hint_lbl.pack(fill="x")

        open_btn = ctk.CTkButton(
            card,
            text=store_text("open"),
            width=56,
            height=30,
            corner_radius=8,
            fg_color=aktif_palet["neon"],
            hover_color=aktif_palet["button_hover"],
            text_color=_tema_vurgu_metin_rengi(),
            command=lambda u=url: store_app_ac(u)
        )
        open_btn.pack(side="right", padx=10, pady=10)

        store_app_cards.append({
            "name": isim,
            "url": url,
            "card": card,
            "icon": icon_lbl,
            "name_label": name_lbl,
            "hint_label": hint_lbl,
            "open_button": open_btn,
        })

    def store_apps_render(filtre=None, force=False):
        """Var olan kartları filtreler; widget silip yeniden üretmez."""
        try:
            if filtre is None:
                filtre = store_search.get()
            q = str(filtre).casefold().strip()

            if not extension_store_state.get("built"):
                _store_build_cards_async()
                return

            if not force and extension_store_state.get("last_filter") == q:
                return
            extension_store_state["last_filter"] = q

            try:
                store_empty_label.pack_forget()
            except Exception:
                pass

            bulunan = 0
            # Pack sırası her filtrede sabit kalsın; sadece mevcut 9 kart taşınır.
            for meta in store_app_cards:
                try:
                    meta["card"].pack_forget()
                except Exception:
                    pass

            for meta in store_app_cards:
                if q and q not in meta["name"].casefold():
                    continue
                meta["card"].pack(fill="x", padx=4, pady=6)
                bulunan += 1

            if bulunan == 0:
                store_empty_label.configure(text=store_text("no_results"))
                store_empty_label.pack(pady=20)
        except Exception as e:
            try:
                print(f"[STORE] filtreleme hata: {e}", flush=True)
            except Exception:
                pass

    def _store_build_cards_async():
        """Kartları UI'yi dondurmadan küçük partiler halinde bir kez oluşturur."""
        try:
            if extension_store_state.get("built") or extension_store_state.get("building"):
                return

            extension_store_state["building"] = True
            extension_store_state["build_index"] = 0
            store_loading_label.configure(text=store_text("loading"))
            store_loading_label.pack(pady=20)

            def _next_batch():
                try:
                    index = int(extension_store_state.get("build_index", 0))
                    if index == 0:
                        try:
                            store_loading_label.pack_forget()
                        except Exception:
                            pass

                    # Her turda en fazla iki kart: panel animasyonu akıcı kalır.
                    bitis = min(index + 2, len(eklentiler))
                    while index < bitis:
                        isim, url = eklentiler[index]
                        _store_create_card(isim, url)
                        index += 1

                    extension_store_state["build_index"] = index
                    if index < len(eklentiler):
                        root.after(8, _next_batch)
                        return

                    extension_store_state["building"] = False
                    extension_store_state["built"] = True
                    extension_store_state["last_filter"] = None
                    store_apps_render(store_search.get(), force=True)
                    store_language_refresh()
                except Exception as e:
                    extension_store_state["building"] = False
                    try:
                        print(f"[STORE] kart oluşturma hata: {e}", flush=True)
                    except Exception:
                        pass

            root.after(0, _next_batch)
        except Exception:
            extension_store_state["building"] = False

    def _store_search_apply():
        extension_store_state["search_job"] = None
        store_apps_render(store_search.get(), force=True)

    def _store_search_changed(event=None):
        # Her tuşta dokuz kartı tekrar oluşturmak yerine 140 ms debounce uygula.
        try:
            onceki = extension_store_state.get("search_job")
            if onceki:
                root.after_cancel(onceki)
            extension_store_state["search_job"] = root.after(140, _store_search_apply)
        except Exception:
            store_apps_render(store_search.get(), force=True)

    try:
        store_search.bind("<KeyRelease>", _store_search_changed)
    except Exception:
        pass

    def store_language_refresh():
        try:
            store_title.configure(text=T("extension_store"))
            store_desc_label.configure(text=store_text("description"))
            store_search.configure(placeholder_text=store_text("search"))
            store_loading_label.configure(text=store_text("loading"))
            store_empty_label.configure(text=store_text("no_results"))
            for meta in store_app_cards:
                meta["hint_label"].configure(text=store_text("hint"))
                meta["open_button"].configure(text=store_text("open"))
        except Exception as e:
            try:
                print(f"[STORE] dil yenileme hata: {e}", flush=True)
            except Exception:
                pass

    def store_theme_refresh():
        try:
            extension_store_panel.configure(
                fg_color=aktif_palet["sidebar"],
                border_color=aktif_palet["card"],
            )
            store_title.configure(text_color=aktif_palet["text_main"])
            store_desc_label.configure(text_color=aktif_palet["text_dim"])
            store_close_btn.configure(
                fg_color=aktif_palet["card"],
                hover_color=aktif_palet["button_hover"],
                text_color=aktif_palet["text_main"],
            )
            store_search.configure(
                fg_color=aktif_palet["entry_bg"],
                text_color=aktif_palet["text_main"],
                border_color=aktif_palet["entry_border"],
            )
            _neto_scrollable_frame_renklendir(store_apps_frame, aktif_palet, "sidebar")
            store_loading_label.configure(text_color=aktif_palet["text_dim"])
            store_empty_label.configure(text_color=aktif_palet["text_dim"])
            for meta in store_app_cards:
                meta["card"].configure(
                    fg_color=aktif_palet["card"],
                    border_color=aktif_palet["entry_border"],
                )
                meta["icon"].configure(text_color=aktif_palet["text_main"])
                meta["name_label"].configure(text_color=aktif_palet["text_main"])
                meta["hint_label"].configure(text_color=aktif_palet["text_dim"])
                meta["open_button"].configure(
                    fg_color=aktif_palet["neon"],
                    hover_color=aktif_palet["button_hover"],
                    text_color=_tema_vurgu_metin_rengi(),
                )
        except Exception as e:
            try:
                print(f"[STORE] tema yenileme hata: {e}", flush=True)
            except Exception:
                pass

    # Dil ve tema motorları mağaza fonksiyonlarına güvenli şekilde erişsin.
    globals()["_neto_store_refresh_language"] = store_language_refresh
    globals()["_neto_store_refresh_theme"] = store_theme_refresh

    def eklenti_magazasi_panel_animasyon(hedef_x, on_complete=None):
        engine = _neto_motion()
        start = int(extension_store_state.get("x", hedef_x))
        extension_store_state["animating"] = True
        def update(value):
            x = round(value)
            if x != extension_store_state.get("x"):
                extension_store_state["x"] = x
                extension_store_panel.place(x=x, y=0, relheight=1)
        def finish():
            extension_store_state["x"] = hedef_x
            extension_store_state["animating"] = False
            if callable(on_complete):
                on_complete()
        if engine is None:
            update(hedef_x)
            finish()
            return
        engine.number("store-slide", start, hedef_x, update,
                      duration_ms=220, on_complete=finish)

    def eklenti_magazasi_panel_ac(event=None):
        try:
            w = max(root.winfo_width(), 320)
            panel_w = 300 if w >= 420 else max(280, w - 30)

            extension_store_panel.configure(width=panel_w)
            start_x = w + 4
            target_x = max(0, w - panel_w)

            extension_store_state["x"] = start_x
            extension_store_state["target"] = target_x
            extension_store_state["open"] = True

            # Panel önce görünür ve animasyon hemen başlar; kart hazırlığı bloklamaz.
            extension_store_panel.place(x=start_x, y=0, relheight=1)
            extension_store_panel.lift()
            hamburger_btn.lift()
            eklenti_magazasi_panel_animasyon(target_x)

            if extension_store_state.get("built"):
                store_apps_render(store_search.get(), force=True)
            else:
                root.after(0, _store_build_cards_async)

            root.after(35, lambda: store_search.focus_set() if store_search.winfo_exists() else None)
            return "break"

        except Exception as e:
            try:
                print(f"[STORE] panel açma hata: {e}", flush=True)
            except Exception:
                pass
            return "break"

    def eklenti_magazasi_panel_kapat(event=None):
        try:
            if not extension_store_state["open"]:
                return "break"

            w = max(root.winfo_width(), 320)
            extension_store_state["open"] = False

            def _gizle():
                try:
                    if not extension_store_state.get("open"):
                        extension_store_panel.place_forget()
                except Exception:
                    pass

            eklenti_magazasi_panel_animasyon(w + 4, on_complete=_gizle)
            return "break"

        except Exception as e:
            try:
                print(f"[STORE] panel kapatma hata: {e}", flush=True)
            except Exception:
                pass
            return "break"

    def eklenti_magazasi_panel_toggle(event=None):
        try:
            if extension_store_state.get("busy"):
                return "break"
            extension_store_state["busy"] = True
            if extension_store_state.get("open"):
                sonuc = eklenti_magazasi_panel_kapat(event)
            else:
                sonuc = eklenti_magazasi_panel_ac(event)
            # Eski 1500 ms kilit kaldırıldı; animasyon süresi kadar kilit yeterli.
            root.after(210, lambda: extension_store_state.update({"busy": False}))
            return sonuc
        except Exception:
            extension_store_state["busy"] = False
            return "break"

    try:
        root.bind("<Control-e>", eklenti_magazasi_panel_toggle)
        root.bind("<Control-E>", eklenti_magazasi_panel_toggle)
        root.bind("<Escape>", eklenti_magazasi_panel_kapat)
    except Exception:
        pass

    _neto_launch_checkpoint("Son arayüz kontrolleri..." if str(dil_getir()).lower() == "tr" else "Final interface checks...", force=True)

    # Uygulama açıldıktan sonra kartları gizli panelde parça parça önceden hazırla.
    # Kullanıcı mağazaya hemen basarsa panel yine beklemeden açılır ve kartlar akıcı yüklenir.
    try:
        root.after(3200, _store_build_cards_async)
    except Exception:
        pass


    _neto_theme_widget_cache = {"sidebar": [], "agent_sidebar": []}

    def arayuz_renklerini_yenile():
        try:
            root.configure(fg_color=aktif_palet["bg"])
        except Exception:
            pass

        try:
            _neto_titlebar_theme_refresh()
        except Exception:
            pass

        try:
            side_panel.configure(
                fg_color=aktif_palet["sidebar"],
                border_color=aktif_palet["entry_border"],
            )
        except Exception:
            pass

        try:
            sidebar_header.configure(fg_color=aktif_palet["sidebar"])
        except Exception:
            pass

        try:
            main_c.configure(fg_color=aktif_palet["bg"])
        except Exception:
            pass

        try:
            chat_container.configure(fg_color=aktif_palet["bg"])
        except Exception:
            pass

        try:
            input_container.configure(fg_color=aktif_palet["bg"])
        except Exception:
            pass

        try:
            if not globals().get("inline_live_toggle") or not locals().get("inline_live_state", {}).get("active"):
                giris_frame.configure(
                    fg_color=_INPUT_BAR_BG,
                    border_color=_INPUT_BAR_BORDER,
                    border_width=0,
                    corner_radius=25
                )
        except Exception:
            pass

        try:
            if not globals().get("inline_live_toggle") or not locals().get("inline_live_state", {}).get("active"):
                giris.configure(
                    fg_color="transparent",
                    text_color=_INPUT_TEXT,
                    border_color=_INPUT_BAR_BORDER,
                    border_width=0,
                    placeholder_text_color=_INPUT_PLACEHOLDER
                )
        except Exception:
            pass

        try:
            if not globals().get("inline_live_toggle") or not locals().get("inline_live_state", {}).get("active"):
                btn_gonder.configure(
                    fg_color="transparent",
                    hover_color=_INPUT_HOVER,
                    border_color="#4F6BFF",
                    border_width=0,
                    text_color="#EAF0FF",
                    image=_neto_input_icon("send", _INPUT_ICON_SIZE, "#EAF0FF"),
                    width=_INPUT_BUTTON_SIZE,
                    height=_INPUT_BUTTON_SIZE,
                    corner_radius=_INPUT_BUTTON_SIZE // 2,
                    text=""
                )
                btn_resim.configure(
                    fg_color="transparent",
                    hover_color=_INPUT_HOVER,
                    border_width=0,
                    text_color="#EAF0FF",
                    image=_neto_input_icon("plus", _INPUT_ICON_SIZE, "#EAF0FF"),
                    width=_INPUT_BUTTON_SIZE,
                    height=_INPUT_BUTTON_SIZE,
                    corner_radius=_INPUT_BUTTON_SIZE // 2,
                    text=""
                )
                btn_live.configure(
                    fg_color="transparent",
                    hover_color=_INPUT_HOVER,
                    border_width=0,
                    text_color="#EAF0FF",
                    image=_neto_input_icon("waveform", _INPUT_ICON_SIZE, "#EAF0FF"),
                    width=_INPUT_BUTTON_SIZE,
                    height=_INPUT_BUTTON_SIZE,
                    corner_radius=_INPUT_BUTTON_SIZE // 2,
                    text=""
                )
                btn_input_ai.configure(
                    fg_color="transparent",
                    hover_color=_INPUT_HOVER,
                    border_width=0,
                    text_color=_INPUT_AI_COLOR,
                    image=_neto_input_icon("ai", _INPUT_ICON_SIZE, _INPUT_AI_COLOR),
                    width=_INPUT_BUTTON_SIZE,
                    height=_INPUT_BUTTON_SIZE,
                    corner_radius=_INPUT_BUTTON_SIZE // 2,
                    text=""
                )
        except Exception:
            pass

        try:
            cast(Any, btn_gelismis).configure(
                fg_color=aktif_palet["card"],
                hover_color=aktif_palet["button_hover"]
            )
        except Exception:
            pass

        try:
            pass
        except Exception:
            pass

        try:
            cast(Any, btn_netoai).configure(
                fg_color=aktif_palet["card"],
                hover_color=aktif_palet["button_hover"]
            )
        except Exception:
            pass

        try:
            cast(Any, btn_updates).configure(
                fg_color=aktif_palet["card"],
                hover_color=aktif_palet["button_hover"]
            )
        except Exception:
            pass

        try:
            cast(Any, not_alani).configure(
                fg_color=aktif_palet["card"],
                text_color=aktif_palet["text_main"]
            )
        except Exception:
            pass

        try:
            cast(Any, chat_container).configure(fg_color=aktif_palet["bg"])
            cast(Any, hero_content).configure(fg_color="transparent")
            cast(Any, hero_status_frame).configure(
                fg_color=aktif_palet["card"],
                border_color=aktif_palet["entry_border"],
            )
            cast(Any, lbl_welcome).configure(text_color=aktif_palet["text_main"])
            cast(Any, etiket).configure(text_color=aktif_palet["neon"])
        except Exception:
            pass

        try:
            cast(Any, gif_ana_label).configure(fg_color="transparent", text_color=aktif_palet["text_main"])
        except Exception:
            pass

        try:
            _neto_scrollable_frame_renklendir(cast(Any, sidebar_content), aktif_palet, "sidebar")

            cached: list[Any] = list(_neto_theme_widget_cache.get("sidebar") or [])
            if not cached or any(not getattr(w, "winfo_exists", lambda: False)() for w in cached[:3]):
                cached = []
                stack: list[Any] = [cast(Any, sidebar_content)]
                while stack:
                    item = stack.pop()
                    try:
                        children = list(item.winfo_children())
                    except Exception:
                        children = []
                    cached.extend(children)
                    stack.extend(children)
                _neto_theme_widget_cache["sidebar"] = cached
            for child in cached:
                try:
                    if isinstance(child, ctk.CTkLabel):
                        _widget_configure_degistiyse(child, text_color=aktif_palet["text_dim"])
                    elif isinstance(child, ctk.CTkButton) and child not in {btn_anahtar, btn_automation}:
                        _widget_configure_degistiyse(
                            child, fg_color=aktif_palet["card"],
                            hover_color=aktif_palet["button_hover"],
                            text_color=aktif_palet["text_main"],
                        )
                except Exception:
                    pass
        except Exception:
            pass

        try:
            _neto_automation_button_refresh()
        except Exception:
            pass
        try:
            _neto_scene_button_refresh()
        except Exception:
            pass

        try:
            btn_profiles.configure(
                fg_color=aktif_palet["card"],
                hover_color=aktif_palet["button_hover"],
                text_color=aktif_palet["text_main"],
            )
        except Exception:
            pass

        try:
            btn_reminders.configure(
                fg_color=aktif_palet["card"],
                hover_color=aktif_palet["button_hover"],
                text_color=aktif_palet["text_main"],
            )
        except Exception:
            pass

        try:
            _neto_scrollable_frame_renklendir(cast(Any, agent_sidebar_content), aktif_palet, "sidebar")

            cached_agent: list[Any] = list(_neto_theme_widget_cache.get("agent_sidebar") or [])
            if not cached_agent or any(not getattr(w, "winfo_exists", lambda: False)() for w in cached_agent[:3]):
                cached_agent = []
                stack_agent: list[Any] = [cast(Any, agent_sidebar_content)]
                while stack_agent:
                    item = stack_agent.pop()
                    try:
                        children = list(item.winfo_children())
                    except Exception:
                        children = []
                    cached_agent.extend(children)
                    stack_agent.extend(children)
                _neto_theme_widget_cache["agent_sidebar"] = cached_agent
            for child in cached_agent:
                try:
                    if isinstance(child, ctk.CTkLabel):
                        _widget_configure_degistiyse(child, text_color=aktif_palet["text_dim"])
                    elif isinstance(child, ctk.CTkButton) and child not in {btn_anahtar, agent_internet_btn}:
                        _widget_configure_degistiyse(
                            child,
                            fg_color=aktif_palet["card"],
                            hover_color=aktif_palet["button_hover"],
                            text_color=aktif_palet["text_main"],
                        )
                except Exception:
                    pass
        except Exception:
            pass

        try:
            _agent_internet_guncelle()
        except Exception:
            pass

        # Sabit Ayarlar sekmesi ve dar pencere kısayolu tema değişirken tek parça yenilenir.
        try:
            settings_bottom_bar.configure(
                fg_color=aktif_palet["card"],
                border_color=aktif_palet["entry_border"],
            )
            settings_avatar.configure(
                fg_color=aktif_palet["neon"],
                text_color=_tema_vurgu_metin_rengi(),
            )
            settings_profile_name.configure(text_color=aktif_palet["text_main"])
            settings_title_label.configure(text_color=aktif_palet["text_dim"])
            # Sağdaki ikinci ayar butonu kaldırıldığı için yalnızca tek çark ve yön oku yenilenir.
            settings_chevron.configure(text_color=aktif_palet["text_dim"])
            if globals().get("_sidebar_icon_only_mode", False):
                try:
                    settings_bottom_bar.configure(fg_color="transparent", border_width=0, height=34, corner_radius=9)
                    settings_avatar.configure(text="⋮", fg_color="#2A2A2D", text_color="#FFFFFF", width=34, height=34, corner_radius=9)
                    settings_identity.pack_forget()
                    settings_chevron.pack_forget()
                except Exception:
                    pass
            _settings_motion["bar_color"] = aktif_palet["card"]
            _settings_motion["avatar_color"] = aktif_palet["neon"]
            compact_settings_btn.configure(
                fg_color=aktif_palet["card"],
                hover_color=aktif_palet["button_hover"],
                text_color=aktif_palet["text_main"],
                border_color=aktif_palet["entry_border"],
            )
            hamburger_btn.configure(
                fg_color="#2A2A2D",
                hover_color="#333337",
                text_color="#FFFFFF",
                border_color="#2A2A2D",
            )
            lbl_now_playing.configure(text_color=aktif_palet["neon"])
            if not globals().get("_sidebar_icon_only_mode", False):
                try:
                    btn_now_playing_ayar.configure(
                        fg_color=aktif_palet["card"],
                        hover_color=aktif_palet.get("accent_hover", aktif_palet["button_hover"]),
                        text_color=aktif_palet["neon"],
                        border_width=1, border_color=aktif_palet["neon"],
                    )
                    btn_now_playing_baslat.configure(
                        fg_color=aktif_palet["neon"],
                        hover_color=aktif_palet.get("accent_hover", aktif_palet["button_hover"]),
                        text_color=_tema_vurgu_metin_rengi(),
                    )
                except Exception:
                    pass
                btn_store_panel.configure(
                    fg_color=aktif_palet["neon"],
                    hover_color=aktif_palet.get("accent_hover", aktif_palet["button_hover"]),
                    text_color=_tema_vurgu_metin_rengi(),
                )
            settings_bottom_bar.lift()
            try:
                _sidebar_metinleri_yenile()
            except Exception:
                pass
        except Exception:
            pass

        try:
            fn = globals().get("_neto_store_refresh_theme")
            if callable(fn):
                fn()
            else:
                extension_store_panel.configure(
                    fg_color=aktif_palet["sidebar"],
                    border_color=aktif_palet["card"],
                )
                store_title.configure(text_color=aktif_palet["text_main"])
        except Exception:
            pass

        try:
            now_playing_theme_apply()
        except Exception:
            pass

        try:
            _workspace_theme = globals().get("_neto_workspace_theme_refresh")
            if callable(_workspace_theme):
                _workspace_theme()
        except Exception:
            pass

        # Panels such as the store and automation center create buttons lazily.
        # Re-apply the shared NetOps language after each theme refresh so they
        # never fall back to the old flat CustomTkinter defaults.
        try:
            from neto_modern_ui import apply_tree
            apply_tree(app_content, aktif_palet, force=True)
        except Exception:
            pass

        # Ayarlar sayfası ayrı, parçalara bölünmüş scheduler ile yenilenir.
        # Burada senkron tam-ağaç taraması veya update_idletasks yapılmaz.

    _neto_tema_refresh_state = {
        "token": 0,
        "main_job": None,
        "settings_job": None,
        "redraw_job": None,
        "redraw_suspended": False,
    }

    def _neto_window_redraw(enable=True):
        """Tema yenilemesini senkron Windows mesajı göndermeden tamamlar."""
        if os.name != "nt":
            return
        if not enable:
            _neto_tema_refresh_state["redraw_suspended"] = True
            return
        _neto_tema_refresh_state["redraw_suspended"] = False

        def _redraw_now():
            try:
                if root is None or not bool(int(root.winfo_exists())):
                    return
                import ctypes
                from ctypes import wintypes

                user32 = ctypes.WinDLL("user32", use_last_error=True)
                redraw_window = user32.RedrawWindow
                redraw_window.argtypes = (
                    wintypes.HWND,
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                    wintypes.UINT,
                )
                redraw_window.restype = wintypes.BOOL
                redraw_window(
                    int(root.winfo_id()),
                    None,
                    None,
                    0x0001 | 0x0100 | 0x0080,
                )
            except (tk.TclError, RuntimeError, AttributeError):
                return
            except Exception as exc:
                crash_guard.log(f"[WINDOW_REDRAW_ERROR] {exc}")

        try:
            root.after_idle(_redraw_now)
        except (tk.TclError, RuntimeError, AttributeError):
            return

    def _neto_window_redraw_guvenli_ac():
        _neto_tema_refresh_state["redraw_job"] = None
        _neto_window_redraw(True)
        _NETO_TEMA_DURUM["gecis_aktif"] = False

    def _neto_tema_yenile_planla(settings=True, delay=1):
        """Birden fazla tema callback'ini tek ana UI + tek Ayarlar turunda birleştirir."""
        _neto_tema_refresh_state["token"] += 1
        token = _neto_tema_refresh_state["token"]
        for key in ("main_job", "settings_job", "redraw_job"):
            try:
                job = _neto_tema_refresh_state.get(key)
                if job:
                    root.after_cancel(job)
            except Exception:
                pass
            _neto_tema_refresh_state[key] = None

        def _ana_tur():
            if token != _neto_tema_refresh_state.get("token"):
                return
            _neto_tema_refresh_state["main_job"] = None
            cover_active = False
            try:
                cover = _NETO_TEMA_DURUM.get("appearance_cover")
                cover_active = bool(cover is not None and cover.winfo_exists())
            except Exception:
                cover_active = False
            if not cover_active:
                _neto_window_redraw(False)
            try:
                arayuz_renklerini_yenile()
            except Exception as exc:
                try:
                    print(f"[THEME_REFRESH_ERROR] {exc}", flush=True)
                except Exception:
                    pass
            if settings and token == _neto_tema_refresh_state.get("token"):
                try:
                    _neto_tema_refresh_state["settings_job"] = root.after(
                        8,
                        lambda: _settings_duzeltmeleri_planla(translate=False, delay=1),
                    )
                except Exception:
                    pass
            # Tema örtüsü kullanılıyorsa Win32 redraw kilidine gerek yoktur.
            if cover_active:
                _NETO_TEMA_DURUM["gecis_aktif"] = False
            else:
                try:
                    _neto_tema_refresh_state["redraw_job"] = root.after(110, _neto_window_redraw_guvenli_ac)
                except Exception:
                    _neto_window_redraw_guvenli_ac()

        try:
            _neto_tema_refresh_state["main_job"] = root.after(max(0, int(delay)), _ana_tur)
        except Exception:
            _ana_tur()

    globals()["_neto_tema_yenile_planla"] = _neto_tema_yenile_planla

    # Eski responsive_sidebar_uygula bloğu kaldırıldı; hamburger mini mod ile çakışıyordu.
    side_panel.pack(side="left", fill="y")
    main_c.pack(side="left", fill="both", expand=True)
    try:
        _sidebar_layout_uygula(True, animate=False, persist=False)
    except Exception:
        pass
    # Neto Experience 3.0 (v1.40 eklentisi - YALNIZCA EKLEME):
    # Ayar aciksa kenar cubugu dar ikon rayina cevrilir. Uygulamanin KENDI
    # _sidebar_layout_uygula fonksiyonu kullanilir; boylece hover, aktif
    # renk ve animasyon davranislari aynen korunur.
    # ONEMLI: _sidebar_layout_uygula bazi durumlarda (animasyon surerken veya
    # ayar katmani acikken) sessizce geri donebilir. Bu yuzden sonuc
    # DOGRULANIR ve basarisizsa kisa araliklarla tekrar denenir.
    def _nx3_ray_uygula(deneme=0):
        try:
            # DOĞRULAMA: hem compact bayrağı hem GERÇEK genişlik kontrol edilir.
            # Açılış animasyonları paneli compact bayrağını değiştirmeden
            # genişletebiliyor; yalnızca bayrağa bakmak yetmez.
            try:
                genislik = int(side_panel.winfo_width())
            except Exception:
                genislik = 0
            hedef = int(sidebar_compact_width)
            if bool(sidebar_state.get("compact", False)) and genislik and abs(genislik - hedef) <= 26:
                return True
            _sidebar_layout_uygula(False, animate=False, persist=True)
            try:
                genislik2 = int(side_panel.winfo_width())
            except Exception:
                genislik2 = 0
            if bool(sidebar_state.get("compact", False)) and genislik2 and abs(genislik2 - hedef) <= 26:
                try:
                    print(f"[EXPERIENCE3] kenar cubugu ikon rayina cevrildi (genislik {genislik2})", flush=True)
                except Exception:
                    pass
                return True
            # Henüz oturmadı: kısa aralıkla tekrar dene. Açılış sonrası bazı
            # geçişler paneli compact bayrağını değiştirmeden genişletebiliyor;
            # bu yüzden sınırlı bir gözcü penceresi boyunca (90 sn) kontrol
            # edilir. Sonrasında kullanıcının kendi aç/kapa tercihi geçerlidir.
            if deneme < 45:
                try:
                    root.after(2000, lambda: _nx3_ray_uygula(deneme + 1))
                except Exception:
                    pass
            return False
        except Exception as _nx3_rail_hata:
            try:
                print(f"[EXPERIENCE3_RAIL_ERROR] {_nx3_rail_hata}", flush=True)
            except Exception:
                pass
            return False

    globals()["_nx3_ray_uygula"] = _nx3_ray_uygula
    try:
        import neto_experience3 as _nx3
        if _nx3.rail_sidebar_enabled():
            root.after(900, lambda: _nx3_ray_uygula(0))
    except Exception as _nx3_rail_kurulum:
        try:
            print(f"[EXPERIENCE3_RAIL_SETUP_ERROR] {_nx3_rail_kurulum}", flush=True)
        except Exception:
            pass
    try:
        # Şimdi Çalıyor algılayıcısı uygulamayla birlikte otomatik başlar.
        # Eski sürümdeki 2,5 saniye sonra zorla "Yok" yazan satır kaldırıldı.
        try:
            root.after(2400, now_playing_safe_start)
        except Exception as _np_auto_start_error:
            try:
                now_playing_log(f"[AUTO_SCHEDULE_ERROR] {_np_auto_start_error}")
            except Exception:
                pass
        # Launch gate closes only after the real main interface has completed construction.
        _neto_launch_checkpoint("Açıldı" if str(dil_getir()).lower() == "tr" else "Opened", force=True)
        try:
            root.after(80, lambda: None)
        except Exception:
            pass
        # Giriş ekranı, tam kurulmuş ana pencerenin üzerinde tek event loop ile açılır.
        # Başlat'a basılınca dil gizli ana arayüze uygulanır ve root tek karede gösterilir.
        def _neto_launch_started(selected_lang=None):
            # Birinci ses yalnızca Başlat düğmesinden sonra ve bir kez çalar.
            if not globals().get("_neto_start_sound_played", False):
                globals()["_neto_start_sound_played"] = True
                try:
                    ses_oynat("start")
                except Exception as _start_sound_error:
                    try:
                        print(f"[START_SOUND_ERROR] {_start_sound_error}", flush=True)
                    except Exception:
                        pass
            try:
                dil_uygula()
            except Exception as _lang_refresh_error:
                try:
                    print(f"[LAUNCH_LANGUAGE_REFRESH_ERROR] {_lang_refresh_error}", flush=True)
                except Exception:
                    pass
            try:
                arayuz_renklerini_yenile()
            except Exception:
                pass
            try:
                root.update_idletasks()
            except Exception:
                pass
            try:
                root.after(120, _neto_iddiali_intro_baslat)
                root.after(45, _neto_titlebar_apply_native_style)
                root.after(155, _neto_titlebar_intro)
            except Exception:
                pass

        try:
            NETO_LAUNCH_LOADING_WINDOW = run_launch_gate(
                root=root,
                get_asset_path=get_asset_path,
                veri_yukle=veri_yukle,
                veri_kaydet=veri_kaydet,
                dil_kaydet=dil_kaydet,
                on_started=_neto_launch_started,
            )
        except Exception as _launch_gate_error:
            try:
                print(f"[LAUNCH_GATE_ERROR] {_launch_gate_error}", flush=True)
            except Exception:
                pass
            try:
                root.attributes("-alpha", 1.0)
                root.state("normal")
                root.deiconify()
                root.after(45, _neto_titlebar_apply_native_style)
                root.after(120, _neto_iddiali_intro_baslat)
                root.after(155, _neto_titlebar_intro)
            except Exception:
                pass

        def _neto_start_update_services():
            # Güncelleme modüllerinin importu diskte ağır olabilir; ana Tk thread'inde yapılmaz.
            def _worker():
                try:
                    updater_mod = _neto_lazy_import("neto_updater")
                    update_ui_mod = _neto_lazy_import("neto_update_ui")
                    try:
                        updater_mod.mark_post_update_success_from_argv()
                    except Exception:
                        pass
                    def _schedule_ui_check():
                        try:
                            update_ui_mod.schedule_startup_check(root, notify_callback=animasyonlu_yazi)
                        except Exception as _update_check_error:
                            try:
                                print("[UPDATE_CHECK_ERROR]", _update_check_error, flush=True)
                            except Exception:
                                pass
                    root.after(0, _schedule_ui_check)
                except Exception as _update_import_error:
                    try:
                        print("[UPDATE_IMPORT_ERROR]", _update_import_error, flush=True)
                    except Exception:
                        pass
            threading.Thread(target=_worker, daemon=True).start()
        # Startup update checks can interrupt the welcome flow and should stay
        # opt-in so the app opens cleanly before any network work begins.
        if os.environ.get("NETO_ENABLE_STARTUP_UPDATE_CHECK", "").strip() == "1":
            root.after(4200, _neto_start_update_services)

        def _neto_start_component_update_services():
            # Component checks are delayed until the UI is settled and run in
            # their own worker; no GitHub request can block the main loop.
            try:
                component_updater = _neto_lazy_import("neto_component_updater")
                component_updater.schedule_startup_check(
                    root,
                    notify_callback=animasyonlu_yazi,
                    delay_ms=0,
                    auto_install=True,
                )
            except Exception as _component_update_error:
                print(f"[COMPONENT_UPDATE_ERROR] {_component_update_error}", flush=True)

        root.after(5200, _neto_start_component_update_services)

        def _neto_model_adini_gec_yukle():
            def _worker():
                try:
                    text = "K2" if neto_ai.aktif_modeli_getir() == "NetOps Agent K2" else "K1"
                    root.after(0, lambda: btn_model.configure(text=text) if btn_model.winfo_exists() else None)
                except Exception:
                    pass
            threading.Thread(target=_worker, daemon=True).start()
        root.after(2800, _neto_model_adini_gec_yukle)
        root.after(700, lambda: _neto_bind_hover_tree(app_content))
        root.after(1200, _netops_tts_isit)
        root.after(1550, _neto_mini_doctor_baslat)
        root.after(2200, _neto_arduino_izleyicisini_baslat)
        root.after(3000, neto_remote_hub_start_safe)

        def _neto_experience3_uygula(asama="ilk"):
            # Neto Experience 3.0 katmani (v1.40 eklentisi - YALNIZCA EKLEME).
            # Ayar dosyasinda enabled=false ise hicbir sey yapmaz ve mevcut
            # gorunum aynen korunur. Hata durumunda sessizce atlanir.
            try:
                import neto_experience3
                sonuc = neto_experience3.apply(root, palette=dict(aktif_palet))
                if sonuc.get("ok"):
                    print(
                        f"[EXPERIENCE3:{asama}] rounded={sonuc.get('rounded')} "
                        f"styled={sonuc.get('styled')} iconized={sonuc.get('iconized')} "
                        f"symbols={sonuc.get('symbols')} rail_fixed={sonuc.get('rail_fixed')} "
                        f"font={sonuc.get('icon_font') or 'yok'}",
                        flush=True,
                    )
                # Kapsül (mesaj çubuğu) vurgusu açılış sonrası tekrar uygulanır.
                try:
                    _nx3_kapsul = neto_experience3.apply_capsule_accents()
                    if _nx3_kapsul:
                        print(f"[EXPERIENCE3:{asama}] kapsul vurgusu uygulandi", flush=True)
                except Exception:
                    pass
                # Ray modu: ana arayüz görünür olduktan sonra tekrar doğrula
                # (açılış sırasındaki animasyonlar rayı geri genişletebilir).
                try:
                    _nx3_ray = globals().get("_nx3_ray_uygula")
                    if callable(_nx3_ray):
                        _nx3_ray(0)
                except Exception:
                    pass
            except Exception as _nx3_hata:
                print(f"[EXPERIENCE3_ERROR] {_nx3_hata}", flush=True)

        # Ilk gecis: arayuz kurulduktan hemen sonra.
        root.after(4300, lambda: _neto_experience3_uygula("ilk"))
        # Ikinci gecis: geç olusturulan panelleri de yakalar (idempotent).
        root.after(9500, lambda: _neto_experience3_uygula("gec"))
        if NETO_WAKE_LAUNCH:
            root.after(3200, telefondan_tetikle)

        try:
            if veri_yukle().get("start_live_mode_on_launch"):
                root.after(1800, inline_live_start)
        except Exception:
            pass


        def neto_music_slot_shortcut(slot):
            try:
                import neto_music_search
                result = neto_music_search.switch_to_slot(slot)
                label = globals().get("now_playing_search_status")
                text = result.get("message") if result.get("ok") else f"{APP_NAME}: {result.get('error', 'slot açılamadı')}"
                try:
                    if label and label.winfo_exists():
                        label.configure(text=text, text_color=now_playing_ui_palette()["accent"] if result.get("ok") else "#ffb3b3")
                except Exception:
                    pass
                try:
                    animasyonlu_yazi(text)
                except Exception:
                    pass
            except Exception as e:
                try:
                    animasyonlu_yazi(f"Music slot error: {e}")
                except Exception:
                    pass

        try:
            root.bind_all("<Control-Alt-Left>", lambda event: neto_music_slot_shortcut(1))
            root.bind_all("<Control-Alt-Right>", lambda event: neto_music_slot_shortcut(2))
            root.bind_all("<Control-Alt-Up>", lambda event: neto_music_slot_shortcut(1))
            root.bind_all("<Control-Alt-Down>", lambda event: neto_music_slot_shortcut(2))
        except Exception:
            pass


        # Android izleyicisi ana pencere tamamen yanıt verir hale geldikten sonra yüklenir.
        def _neto_android_watch_deferred():
            def _load_and_start():
                try:
                    import neto_android_device
                    android_alert_state = {"last_at": 0.0}
                    def _neto_android_crash_alert(serial, log_text):
                        try:
                            msg = f"Cihaz: {serial}\n\n" + str(log_text)
                            root.after(0, lambda: neto_android_device_ac_safe(crash_alert_log=msg))
                            now = time.monotonic()
                            if now - android_alert_state["last_at"] >= 60.0:
                                android_alert_state["last_at"] = now
                                root.after(0, lambda: animasyonlu_yazi("📱 Android crash yakalandı; kırmızı log açıldı."))
                        except Exception:
                            pass
                    neto_android_device.start_android_crash_watch(_neto_android_crash_alert, interval=8)
                except Exception as _android_watch_error:
                    try:
                        print("[ANDROID_CRASH_WATCH_ERROR]", _android_watch_error, flush=True)
                    except Exception:
                        pass
            threading.Thread(target=_load_and_start, daemon=True).start()
        root.after(5200, _neto_android_watch_deferred)
        if globals().get("VPN_KORUMA_AKTIF", True):
            try:
                root.after(6400, _neto_vpn_izleyicisini_baslat)
            except Exception:
                pass

        try:
            print(f"[BOOT] Startup fix active: {NETO_STARTUP_FIX_VERSION}", flush=True)
        except Exception:
            pass
        crash_guard.boot("mainloop öncesi")
        _neto_reminder_service_start()
        try:
            if _NETO_TRAY_AKTIF:
                _neto_tray_baslat(
                    neto_safe_startup_logo_path(),
                    T("app_title"),
                    T("tray_show"),
                    T("tray_exit"),
                    on_goster=lambda: root.after(0, _neto_pencereyi_goster),
                    on_cikis=lambda: root.after(0, _neto_tam_kapat),
                )
        except Exception:
            pass
        root.mainloop()
    except Exception as e:
        crash_guard.log('[MAINLOOP_CRASH] ' + str(e))
        import traceback as _traceback
        crash_guard.log(_traceback.format_exc())
        try:
            print(_traceback.format_exc(), flush=True)
        except Exception:
            pass





































