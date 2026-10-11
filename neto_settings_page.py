import os
import sys
import threading
import webbrowser
import platform
import subprocess
import time
import json
import shutil
import importlib.util
from datetime import datetime
from pathlib import Path
from typing import Any, cast
import re

import customtkinter as ctk
from tkinter import filedialog, messagebox

try:
    from config import APP_NAME, APP_UI_NAME, APP_UI_EDITION, APP_DESIGN_FULL_TITLE
except Exception:
    APP_NAME = "NetOps"
    APP_UI_NAME = "Neto Experians"
    APP_UI_EDITION = "2.5"
    APP_DESIGN_FULL_TITLE = f"{APP_UI_NAME} {APP_UI_EDITION}"

try:
    from neto_system_control import render_system_control
except Exception:
    render_system_control = None


try:
    from neto_branding import add_header_logo as _neto_add_header_logo_impl
except Exception:
    _neto_add_header_logo_impl = None


def _neto_add_header_logo(*args, **kwargs):
    if callable(_neto_add_header_logo_impl):
        return _neto_add_header_logo_impl(*args, **kwargs)
    return None


def _sync_scrollable_surface(widget, palette, bg_key="bg"):
    bg = palette.get(bg_key) or palette.get("bg", "#09090B")
    scroll = palette.get("border", palette.get("entry", bg))
    hover = palette.get("hover", scroll)
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


def _normalize_surface_style(value):
    raw = str(value or "experians").strip().lower()
    aliases = {
        "liquid-glass": "liquid-glass",
        "liquid glass": "liquid-glass",
        "liquid_glass": "liquid-glass",
        "glass": "liquid-glass",
        "sıvı cam": "liquid-glass",
        "sivi cam": "liquid-glass",
        "cam": "liquid-glass",
        "experians": "experians",
        "experians 2.5": "experians",
        "neto experians": "experians",
        "klasik": "classic",
        "classic": "classic",
    }
    return aliases.get(raw, "experians")

TEXTS = {
    "tr": {
        "title": "Ayarlar",
        "subtitle": f"Tüm {APP_NAME} ayarları tek yerde.",
        "settings": "AYARLAR",
        "general": "Genel",
        "window_manager": "Neto Pencere Yönetimi",
        "appearance": "Görünüm",
        "system": "Sistem",
        "system_title": "Sistem ve Performans",
        "system_desc": "Performans profilleri, servisler, izinler ve kurtarma.",
        "netolab": f"{APP_NAME} Lab",
        "security": "Güvenlik",
        "updates": "Güncellemeler",
        "about": "Hakkında",
        "general_title": "Genel",
        "general_desc": "Temel uygulama davranışları ve dil.",
        "language": "Uygulama dili",
        "language_desc": "Dil değişikliği aynı ekranda anında uygulanır.",
        "startup": "Başlangıç davranışı",
        "startup_desc": "Uygulamayla hangi özelliklerin başlayacağını seç.",
        "live_auto": "Live Mode başlangıçta otomatik açılsın",
        "learning": "Öğrenme modu",
        "local": "Yerel çalışma",
        "local_desc": "Android cihaz raporları ve kişisel ayarlar yerel tutulur.",
        "local_api": "Yerel API",
        "local_api_desc": "Yerel asistan API'sini açık tut.",
        "linux_bridge": "Linux köprüsü (WSL)",
        "linux_bridge_desc": "Windows içinde Linux araçlarını kullanmak için WSL2 tabanlı köprü.",
        "appearance_title": "Görünüm",
        "appearance_desc": "Tema ve görsel tercihleri.",
        "theme": "Tema modu",
        "theme_desc": f"{APP_NAME} arayüzü için koyu veya açık görünümü seç.",
        "dark": "Koyu",
        "light": "Açık",
        "surface_style": "Tasarım dili",
        "surface_style_desc": f"{APP_NAME} arayüzünün tasarım dilini seç.",
        "classic": "Klasik",
        "liquid_glass": "Liquid Glass",
        "experians": APP_DESIGN_FULL_TITLE,
        "startup_media": "Açılış animasyonu ve sesi",
        "startup_media_desc": "Başlangıç animasyonunu ve açılış sesini yönet.",
        "startup_animation": "Açılış animasyonu",
        "startup_sound": "Açılış sesi",
        "active_gif": "Aktif GIF",
        "active_sound": "Aktif ses",
        "select_gif": "Yeni GIF seç",
        "select_sound": "Yeni ses seç",
        "factory": "Fabrika ayarları",
        "factory_desc": "Görünüm ve başlangıç tercihlerini varsayılanlara döndür.",
        "restore": "Varsayılanları geri yükle",
        "netolab_title": f"{APP_NAME} Lab",
        "netolab_desc": f"Deneysel ve gelişmiş {APP_NAME} özellikleri.",
        "experimental": "Deneysel özellikler",
        "experimental_desc": "Henüz geliştirilmekte olan özellikleri etkinleştir.",
        "agent_mode": f"{APP_NAME} Agent görev modu",
        "android_watch": "Android cihaz izleyicisi",
        "diagnostics": "Ayrıntılı teşhis kayıtları",
        "performance": "Performans",
        "performance_desc": "Düşük donanımlı sistemler için yükü azalt.",
        "low_resource": "Düşük kaynak modu",
        "security_title": "Güvenlik",
        "security_desc": "Güvenlik ve filtreleme tercihleri.",
        "swear_filter": "Küfür filtresi",
        "swear_desc": "Uygunsuz ifadeleri filtrele.",
        "local_only": "Yalnızca yerel bağlantılar",
        "local_only_desc": "Yerel API'yi yalnızca bu bilgisayardan erişilebilir tut.",
        "safe_actions": "Tehlikeli işlemlerde onay iste",
        "safe_actions_desc": "Silme, kapatma ve sistem değişikliklerinden önce onay göster.",
        "updates_title": "Güncellemeler",
        "updates_desc": f"{APP_NAME}'i güncel tut.",
        "current_version": "Mevcut sürüm",
        "latest_version": "En son sürüm",
        "unknown": "Bilinmiyor",
        "check_updates": "Güncellemeleri kontrol et",
        "checking": "Güncellemeler kontrol ediliyor...",
        "up_to_date": "Güncelleme kontrolü tamamlandı.",
        "update_unavailable": "Güncelleme modülü bu kurtarılan projede hazır değil.",
        "about_title": "Hakkında",
        "about_desc": "Uygulama bilgileri.",
        "product": APP_NAME,
        "edition": "Tasarım dili",
        "python": "Python sürümü",
        "data_location": "Yerel veri konumu",
        "open_data": "Veri klasörünü aç",
        "close": "Geri",
        "saved": "Kaydedildi",
        "select_file_error": "Dosya seçilemedi",
        "reset_confirm_title": "Fabrika ayarları",
        "reset_confirm": "Görünüm ve başlangıç ayarları varsayılanlara döndürülsün mü?",
        "window_manager_title": "Neto Pencere Yönetimi",
        "window_manager_desc": "NetOps bölümlerini bağlı ekranlara ata. Tek ekranlı bilgisayarda güvenli şekilde birinci ekran kullanılır.",
        "display": "Ekran",
        "screen_assignment": "Açılacak bölüm",
        "apply_window_layout": "Yerleşimi uygula",
        "window_layout_saved": "Ekran yerleşimi kaydedildi.",
    },
    "en": {
        "title": "Settings",
        "subtitle": f"All {APP_NAME} settings in one place.",
        "settings": "SETTINGS",
        "general": "General",
        "window_manager": "Neto Window Management",
        "appearance": "Appearance",
        "system": "System",
        "system_title": "System and Performance",
        "system_desc": "Performance profiles, services, permissions, and recovery.",
        "netolab": f"{APP_NAME} Lab",
        "security": "Security",
        "updates": "Updates",
        "about": "About",
        "general_title": "General",
        "general_desc": "Basic application behavior and language.",
        "language": "Application language",
        "language_desc": "Language changes are applied instantly on the same screen.",
        "startup": "Startup behavior",
        "startup_desc": "Choose which features start with the app.",
        "live_auto": "Start Live Mode automatically",
        "learning": "Learning mode",
        "local": "Local operation",
        "local_desc": "Android device reports and personal settings stay local.",
        "local_api": "Local API",
        "local_api_desc": "Keep the local assistant API enabled.",
        "linux_bridge": "Linux bridge (WSL)",
        "linux_bridge_desc": "A WSL2 bridge for using Linux tools inside Windows.",
        "appearance_title": "Appearance",
        "appearance_desc": "Theme and visual preferences.",
        "theme": "Theme mode",
        "theme_desc": f"Choose dark or light appearance for {APP_NAME}.",
        "dark": "Dark",
        "light": "Light",
        "surface_style": "Design language",
        "surface_style_desc": f"Choose the design language for the {APP_NAME} interface.",
        "classic": "Classic",
        "liquid_glass": "Liquid Glass",
        "experians": APP_DESIGN_FULL_TITLE,
        "startup_media": "Startup animation and sound",
        "startup_media_desc": "Manage the startup animation and sound.",
        "startup_animation": "Startup animation",
        "startup_sound": "Startup sound",
        "active_gif": "Active GIF",
        "active_sound": "Active sound",
        "select_gif": "Select new GIF",
        "select_sound": "Select new sound",
        "factory": "Factory settings",
        "factory_desc": "Restore appearance and startup preferences.",
        "restore": "Restore defaults",
        "netolab_title": f"{APP_NAME} Lab",
        "netolab_desc": f"Experimental and advanced {APP_NAME} features.",
        "experimental": "Experimental features",
        "experimental_desc": "Enable features that are still being developed.",
        "agent_mode": f"{APP_NAME} Agent task mode",
        "android_watch": "Android device watcher",
        "diagnostics": "Detailed diagnostic logs",
        "performance": "Performance",
        "performance_desc": "Reduce load on low-resource systems.",
        "low_resource": "Low resource mode",
        "security_title": "Security",
        "security_desc": "Safety and filtering preferences.",
        "swear_filter": "Swear filter",
        "swear_desc": "Filter inappropriate expressions.",
        "local_only": "Local connections only",
        "local_only_desc": "Keep the local API accessible only from this computer.",
        "safe_actions": "Confirm dangerous actions",
        "safe_actions_desc": "Ask before deletion, shutdown, or system changes.",
        "updates_title": "Updates",
        "updates_desc": f"Keep {APP_NAME} up to date.",
        "current_version": "Current version",
        "latest_version": "Latest version",
        "unknown": "Unknown",
        "check_updates": "Check for updates",
        "checking": "Checking for updates...",
        "up_to_date": "Update check completed.",
        "update_unavailable": "The update module is unavailable in this recovered project.",
        "about_title": "About",
        "about_desc": "Application information.",
        "product": APP_NAME,
        "edition": "Design language",
        "python": "Python version",
        "data_location": "Local data location",
        "open_data": "Open data folder",
        "close": "Back",
        "saved": "Saved",
        "select_file_error": "Could not select the file",
        "reset_confirm_title": "Factory settings",
        "reset_confirm": "Restore appearance and startup settings to defaults?",
        "window_manager_title": "Neto Window Management",
        "window_manager_desc": "Assign NetOps sections to connected displays. A single-display computer safely uses display one.",
        "display": "Display",
        "screen_assignment": "Section to open",
        "apply_window_layout": "Apply layout",
        "window_layout_saved": "Display layout saved.",
    },
}


DARK = {
    "bg": "#09090B",
    "sidebar": "#1A1A1F",
    "card": "#1B1B20",
    "entry": "#141418",
    "border": "#383841",
    "text": "#F5F5F7",
    "muted": "#AAAABD",
    "accent": "#22C55E",
    "hover": "#292930",
    "switch_off": "#41414B",
}

LIGHT = {
    "bg": "#F4F5F7",
    "sidebar": "#FFFFFF",
    "card": "#FFFFFF",
    "entry": "#F0F1F4",
    "border": "#C8CDD6",
    "text": "#17171B",
    "muted": "#666674",
    "accent": "#22C55E",
    "hover": "#E4E7EC",
    "switch_off": "#B8BEC9",
}


def _version_key(value):
    import re
    match = re.search(r"(?<!\d)(\d+(?:\.\d+){1,5})(?!\d)", str(value or ""))
    if not match:
        return ()
    try:
        parts = tuple(int(part) for part in match.group(1).split("."))
        return parts + (0,) * (6 - len(parts))
    except Exception:
        return ()


def _app_version():
    try:
        from neto_version import get_app_version

        version = str(get_app_version() or "").strip().lstrip("vV")
        if _version_key(version):
            return version
    except Exception:
        pass

    try:
        from config import APP_VERSION

        version = str(APP_VERSION or "").strip().lstrip("vV")
        if _version_key(version):
            return version
    except Exception:
        pass

    return "1.38"


def _local_data_dir():
    base = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or str(Path.home())
    return Path(base) / "NetoAssistant"


class NetoSettingsPage:
    def __init__(
        self,
        parent,
        root,
        load_data,
        save_data,
        apply_theme,
        refresh_app_theme,
        get_asset_path,
        get_data_path,
        save_language,
        refresh_language,
        get_language,
        exit_callback=None,
        on_open=None,
        on_close=None,
        **_kwargs,
    ):
        self.parent = parent
        self.root = root
        self.load_data = load_data
        self.save_data = save_data
        self.apply_theme_callback = apply_theme
        self.refresh_app_theme_callback = refresh_app_theme
        self.get_asset_path = get_asset_path
        self.get_data_path = get_data_path
        self.save_language_callback = save_language
        self.refresh_language_callback = refresh_language
        self.get_language_callback = get_language
        self.exit_callback = exit_callback
        self.on_open = on_open
        self.on_close = on_close
        self.window_layout_callback = _kwargs.get("window_layout_callback")

        self.surface = None
        self.header = None
        self.body = None
        self.sidebar = None
        self.content_shell = None
        self.content = None
        self.nav_buttons = {}
        self.section = "general"
        self.is_open = False
        self._rendering = False
        self._pending_section = None
        self._render_token = 0
        self._hover_bind_job = None
        self.data = self._load()
        self.lang = self._language()
        self.palette = self._palette()

    def _load(self):
        try:
            value = self.load_data()
            return dict(value) if isinstance(value, dict) else {}
        except Exception:
            return {}

    def _save(self):
        try:
            return bool(self.save_data(dict(self.data)))
        except Exception:
            return False

    def _language(self):
        try:
            value = str(self.get_language_callback() or "").lower()
        except Exception:
            value = str(self.data.get("dil", "tr")).lower()
        return "tr" if value.startswith("tr") else "en"

    def _text(self, key) -> str:
        texts = TEXTS.get(self.lang) or TEXTS["tr"]
        return str(texts.get(key, key))

    def _palette(self):
        mode = str(self.data.get("tema", "dark")).strip().lower()
        base = dict(LIGHT if mode in {"light", "açık", "acik"} else DARK)
        try:
            from temalar import aktif_palet
            if isinstance(aktif_palet, dict):
                mapping = {
                    "bg": "bg",
                    "sidebar": "sidebar",
                    "card": "card",
                    "entry": "entry_bg",
                    "border": "entry_border",
                    "text": "text_main",
                    "muted": "text_dim",
                    "accent": "neon",
                    "hover": "button_hover",
                }
                for local_key, external_key in mapping.items():
                    value = aktif_palet.get(external_key)
                    if isinstance(value, str) and value:
                        base[local_key] = value
        except Exception:
            pass
        return base

    def _clear(self, widget):
        if widget is None:
            return
        for child in widget.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass

    def _build(self):
        self.palette = self._palette()
        p = self.palette

        self.surface = ctk.CTkFrame(self.parent, fg_color=p["bg"], corner_radius=0)
        self.surface.place(relx=0, rely=0, relwidth=1, relheight=1)
        try:
            setattr(self.surface, "_neto_surface_role", "settings")
        except Exception:
            pass

        self.header = ctk.CTkFrame(self.surface, height=68, fg_color=p["bg"], corner_radius=0)
        self.header.pack(fill="x", padx=28, pady=(0, 0))
        self.header.pack_propagate(False)
        try:
            _neto_add_header_logo(self.header, size=34, position="right", padx=10)
        except Exception:
            pass

        back = ctk.CTkButton(
            self.header,
            text="←",
            width=48,
            height=42,
            corner_radius=13,
            fg_color=p["card"],
            hover_color=p["hover"],
            text_color=p["text"],
            font=("Segoe UI Semibold", 17),
            command=lambda: getattr(self, "request_close", self.close)(),
        )
        back.pack(side="left", pady=(8, 0))

        title_box = ctk.CTkFrame(self.header, fg_color="transparent")
        title_box.pack(side="left", padx=(14, 0), pady=(0, 0))
        ctk.CTkLabel(
            title_box,
            text=self._text("title"),
            text_color=p["text"],
            font=("Segoe UI Semibold", 25),
            anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_box,
            text=self._text("subtitle"),
            text_color=p["muted"],
            font=("Segoe UI", 12),
            anchor="w",
        ).pack(anchor="w", pady=(1, 0))

        self.body = ctk.CTkFrame(self.surface, fg_color=p["bg"], corner_radius=0)
        self.body.pack(fill="both", expand=True, padx=28, pady=(5, 16))
        self.body.grid_columnconfigure(1, weight=1)
        self.body.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(
            self.body,
            width=182,
            fg_color=p["sidebar"],
            border_width=1,
            border_color=p["border"],
            corner_radius=20,
        )
        self.sidebar.grid(row=0, column=0, sticky="nsw", padx=(0, 14))
        self.sidebar.grid_propagate(False)

        ctk.CTkLabel(
            self.sidebar,
            text=self._text("settings"),
            text_color=p["text"],
            font=("Segoe UI Semibold", 10),
            anchor="w",
        ).pack(fill="x", padx=14, pady=(23, 10))

        nav = [
            ("general", "⌂", "general"),
            ("system", "⚡", "system"),
            ("appearance", "◐", "appearance"),
            ("window_manager", "▣", "window_manager"),
            ("netolab", "◇", "netolab"),
            ("security", "⊙", "security"),
            ("updates", "↑", "updates"),
            ("about", "ⓘ", "about"),
        ]
        self.nav_buttons = {}
        for section, icon, key in nav:
            button = ctk.CTkButton(
                self.sidebar,
                text=f"{icon}   {self._text(key)}",
                height=41,
                corner_radius=12,
                anchor="w",
                border_spacing=10,
                fg_color="transparent",
                hover_color=p["hover"],
                text_color=p["text"],
                font=("Segoe UI Semibold", 12),
                command=lambda selected=section: self.show_section(selected),
            )
            button.pack(fill="x", padx=10, pady=2)
            self.nav_buttons[section] = button

        version_box = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        version_box.pack(side="bottom", fill="x", padx=15, pady=17)
        ctk.CTkLabel(
            version_box,
            text=f"{APP_NAME}\nv{_app_version()} · {APP_DESIGN_FULL_TITLE}",
            justify="left",
            anchor="w",
            text_color=p["muted"],
            font=("Segoe UI", 9),
        ).pack(fill="x")

        self.content_shell = ctk.CTkFrame(
            self.body,
            fg_color=p["card"],
            border_width=1,
            border_color=p["border"],
            corner_radius=20,
        )
        self.content_shell.grid(row=0, column=1, sticky="nsew")
        self.content_shell.grid_rowconfigure(0, weight=1)
        self.content_shell.grid_columnconfigure(0, weight=1)

        self.content = ctk.CTkScrollableFrame(
            self.content_shell,
            fg_color=p["bg"],
            corner_radius=15,
            scrollbar_button_color=p["border"],
            scrollbar_button_hover_color=p["hover"],
        )
        self.content.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        _sync_scrollable_surface(self.content, p, "bg")

        self.show_section(self.section)

    def _heading(self, title_key, desc_key):
        p = self.palette
        ctk.CTkLabel(
            self.content,
            text=self._text(title_key),
            text_color=p["text"],
            font=("Segoe UI Semibold", 23),
            anchor="w",
        ).pack(fill="x", padx=15, pady=(12, 0))
        ctk.CTkLabel(
            self.content,
            text=self._text(desc_key),
            text_color=p["muted"],
            font=("Segoe UI", 12),
            anchor="w",
        ).pack(fill="x", padx=15, pady=(4, 15))

    def _card(self, title_key, desc_key=None):
        p = self.palette
        frame = ctk.CTkFrame(
            self.content,
            fg_color=p["card"],
            border_width=1,
            border_color=p["border"],
            corner_radius=17,
        )
        frame.pack(fill="x", padx=13, pady=(0, 13))
        ctk.CTkLabel(
            frame,
            text=self._text(title_key),
            text_color=p["text"],
            font=("Segoe UI Semibold", 15),
            anchor="w",
        ).pack(fill="x", padx=16, pady=(15, 0))
        if desc_key:
            ctk.CTkLabel(
                frame,
                text=self._text(desc_key),
                text_color=p["muted"],
                font=("Segoe UI", 11),
                anchor="w",
                wraplength=520,
                justify="left",
            ).pack(fill="x", padx=16, pady=(5, 10))
        return frame

    def _switch_row(self, parent, key, data_key, default=False, command=None):
        p = self.palette
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(4, 8))
        variable = ctk.BooleanVar(value=bool(self.data.get(data_key, default)))

        ctk.CTkLabel(
            row,
            text=self._text(key),
            text_color=p["text"],
            font=("Segoe UI", 12),
            anchor="w",
        ).pack(side="left", fill="x", expand=True)

        def changed():
            self.data[data_key] = bool(variable.get())
            self._save()
            if callable(command):
                try:
                    command(bool(variable.get()))
                except Exception:
                    pass

        switch = ctk.CTkSwitch(
            row,
            text="",
            width=36,
            switch_width=34,
            switch_height=18,
            progress_color=p["accent"],
            button_color=p["text"],
            button_hover_color=p["text"],
            fg_color=p["switch_off"],
            variable=variable,
            command=changed,
        )
        switch.pack(side="right")
        return switch

    def _button(self, parent, text_key, command, primary=False):
        p = self.palette
        return ctk.CTkButton(
            parent,
            text=self._text(text_key),
            height=36,
            corner_radius=10,
            fg_color=p["accent"] if primary else p["entry"],
            hover_color=p["hover"],
            border_width=0 if primary else 1,
            border_color=p["border"],
            text_color="#FFFFFF" if primary else p["text"],
            font=("Segoe UI Semibold", 11),
            command=command,
        )

    def _set_language(self, language):
        self.lang = "tr" if language == "tr" else "en"
        self.data["dil"] = self.lang
        self._save()
        try:
            self.save_language_callback(self.lang)
        except Exception:
            pass
        try:
            self.refresh_language_callback()
        except Exception:
            pass
        self.refresh_language()

    def _set_theme(self, theme):
        self.data["tema"] = "light" if theme == "light" else "dark"
        self._save()
        try:
            self.apply_theme_callback(
                self.data["tema"],
                self.data.get("renk_temasi", "green"),
                _normalize_surface_style(self.data.get("arayuz_stili", "experians")),
            )
        except TypeError:
            try:
                self.apply_theme_callback(self.data["tema"])
            except Exception:
                pass
        except Exception:
            pass
        try:
            self.refresh_app_theme_callback()
        except Exception:
            pass
        self.refresh_theme()

    def _set_surface_style(self, style):
        self.data["arayuz_stili"] = _normalize_surface_style(style)
        self._save()
        try:
            self.apply_theme_callback(
                self.data.get("tema", "dark"),
                self.data.get("renk_temasi", "green"),
                self.data["arayuz_stili"],
            )
        except TypeError:
            try:
                self.apply_theme_callback(self.data.get("tema", "dark"), self.data.get("renk_temasi", "green"))
            except Exception:
                pass
        except Exception:
            pass
        try:
            self.refresh_app_theme_callback()
        except Exception:
            pass
        self.refresh_theme()

    def _select_media(self, kind):
        patterns = [("GIF files", "*.gif")] if kind == "gif" else [("Audio files", "*.mp3 *.wav")]
        try:
            path = filedialog.askopenfilename(parent=self.root, filetypes=patterns)
            if not path:
                return
            if kind == "gif":
                self.data["secilen_gif"] = path
            else:
                self.data["secilen_ses"] = path
            self._save()
            self.show_section("appearance")
        except Exception as exc:
            messagebox.showerror(self._text("select_file_error"), str(exc), parent=self.root)

    def _sync_linux_bridge(self, enabled):
        def worker():
            try:
                from neto_runtime_core import get_runtime

                runtime = get_runtime()
                if runtime is None:
                    return
                runtime.set_custom_feature("linux_bridge", bool(enabled))
            except Exception:
                pass

        threading.Thread(
            target=worker,
            daemon=True,
            name="NetoLinuxBridgeToggle",
        ).start()

    def _reset_defaults(self):
        if not messagebox.askyesno(
            self._text("reset_confirm_title"),
            self._text("reset_confirm"),
            parent=self.root,
        ):
            return
        self.data.update({
            "tema": "dark",
            "renk_temasi": "green",
            "arayuz_stili": "experians",
            "secilen_gif": "yukleme.gif",
            "secilen_ses": "varsayilan",
            "startup_animation_enabled": True,
            "startup_sound_enabled": True,
            "live_mode_otomatik_baslat": False,
            "linux_bridge_enabled": False,
        })
        self._save()
        self._set_theme("dark")

    def _render_general(self):
        self._heading("general_title", "general_desc")

        card = self._card("language", "language_desc")
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(2, 15))
        segmented = ctk.CTkSegmentedButton(
            row,
            values=["Türkçe", "English"],
            selected_color=self.palette["accent"],
            selected_hover_color=self.palette["accent"],
            unselected_color=self.palette["entry"],
            unselected_hover_color=self.palette["hover"],
            text_color=self.palette["text"],
            command=lambda value: self._set_language("tr" if value == "Türkçe" else "en"),
        )
        segmented.pack(side="left")
        segmented.set("Türkçe" if self.lang == "tr" else "English")

        card = self._card("startup", "startup_desc")
        self._switch_row(card, "live_auto", "live_mode_otomatik_baslat", False)
        self._switch_row(card, "learning", "ogrenme_modu_acik", False)

        card = self._card("local", "local_desc")
        self._switch_row(card, "local_api", "local_api_enabled", True)

    def _render_appearance(self):
        self._heading("appearance_title", "appearance_desc")

        card = self._card("theme", "theme_desc")
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(2, 15))
        theme = ctk.CTkSegmentedButton(
            row,
            values=[self._text("dark"), self._text("light")],
            selected_color=self.palette["accent"],
            selected_hover_color=self.palette["accent"],
            unselected_color=self.palette["entry"],
            unselected_hover_color=self.palette["hover"],
            text_color=self.palette["text"],
            command=lambda value: self._set_theme(
                "light" if value == self._text("light") else "dark"
            ),
        )
        theme.pack(side="left")
        theme.set(self._text("light") if self.data.get("tema") == "light" else self._text("dark"))

        card = self._card("surface_style", "surface_style_desc")
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(2, 15))
        style = ctk.CTkSegmentedButton(
            row,
            values=[self._text("classic"), self._text("liquid_glass"), self._text("experians")],
            selected_color=self.palette["accent"],
            selected_hover_color=self.palette["accent"],
            unselected_color=self.palette["entry"],
            unselected_hover_color=self.palette["hover"],
            text_color=self.palette["text"],
            command=lambda value: self._set_surface_style(
                "liquid-glass"
                if value == self._text("liquid_glass")
                else "experians"
                if value == self._text("experians")
                else "classic"
            ),
        )
        style.pack(side="left")
        active_style = _normalize_surface_style(self.data.get("arayuz_stili", "experians"))
        style.set(
            self._text("experians")
            if active_style == "experians"
            else self._text("liquid_glass")
            if active_style == "liquid-glass"
            else self._text("classic")
        )

        card = self._card("startup_media", "startup_media_desc")
        self._switch_row(card, "startup_animation", "startup_animation_enabled", True)
        self._switch_row(card, "startup_sound", "startup_sound_enabled", True)

        media = ctk.CTkFrame(card, fg_color="transparent")
        media.pack(fill="x", padx=16, pady=(3, 15))
        media.grid_columnconfigure((0, 1), weight=1)

        gif_name = os.path.basename(str(self.data.get("secilen_gif", "yukleme.gif")))
        sound_name = os.path.basename(str(self.data.get("secilen_ses", "varsayilan")))

        gif_box = ctk.CTkFrame(media, fg_color=self.palette["entry"], corner_radius=12)
        gif_box.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkLabel(
            gif_box,
            text=f"{self._text('active_gif')}\n{gif_name}",
            text_color=self.palette["text"],
            font=("Segoe UI", 11),
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 6))
        self._button(gif_box, "select_gif", lambda: self._select_media("gif")).pack(
            fill="x", padx=10, pady=(0, 10)
        )

        sound_box = ctk.CTkFrame(media, fg_color=self.palette["entry"], corner_radius=12)
        sound_box.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        ctk.CTkLabel(
            sound_box,
            text=f"{self._text('active_sound')}\n{sound_name}",
            text_color=self.palette["text"],
            font=("Segoe UI", 11),
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 6))
        self._button(sound_box, "select_sound", lambda: self._select_media("sound")).pack(
            fill="x", padx=10, pady=(0, 10)
        )

        card = self._card("factory", "factory_desc")
        self._button(card, "restore", self._reset_defaults).pack(
            anchor="w", padx=16, pady=(2, 15)
        )

    def _render_system(self):
        if render_system_control is None:
            card = self._card("system_title", "system_desc")
            ctk.CTkLabel(
                card,
                text=(
                    "neto_system_control.py yüklenemedi."
                    if self.lang == "tr"
                    else "neto_system_control.py could not be loaded."
                ),
                text_color=self.palette["muted"],
                font=("Segoe UI", 11),
                anchor="w",
            ).pack(fill="x", padx=16, pady=(3, 15))
            return

        project_dir = Path(__file__).resolve().parent
        try:
            render_system_control(
                parent=self.content,
                root=self.root,
                palette=self.palette,
                lang=self.lang,
                project_dir=project_dir,
            )
        except Exception as exc:
            card = self._card("system_title", "system_desc")
            ctk.CTkLabel(
                card,
                text=(
                    f"Sistem paneli yüklenemedi:\n{exc}"
                    if self.lang == "tr"
                    else f"System panel could not be loaded:\n{exc}"
                ),
                text_color="#EF4444",
                font=("Segoe UI", 11),
                anchor="w",
                justify="left",
                wraplength=680,
            ).pack(fill="x", padx=16, pady=(3, 15))

    def _render_netolab(self):
        self._heading("netolab_title", "netolab_desc")
        card = self._card("experimental", "experimental_desc")
        self._switch_row(card, "agent_mode", "agent_mode_enabled", True)
        self._switch_row(card, "android_watch", "android_watch_enabled", True)
        self._switch_row(card, "diagnostics", "detailed_diagnostics", False)

        card = self._card("linux_bridge", "linux_bridge_desc")
        self._switch_row(card, "linux_bridge", "linux_bridge_enabled", False, command=self._sync_linux_bridge)

        card = self._card("performance", "performance_desc")
        self._switch_row(card, "low_resource", "low_resource_mode", False)

    def _render_window_manager(self):
        self._heading("window_manager_title", "window_manager_desc")
        try:
            from neto_window_manager import WINDOW_OPTIONS, monitors, normalize_assignments
            screens = monitors(self.root)
            assignments = normalize_assignments(
                self.data.get("neto_window_assignments"), len(screens)
            )
        except Exception:
            screens = [{"width": 0, "height": 0}]
            assignments = {"1": "assistant"}
            WINDOW_OPTIONS = (("assistant", "Asistan"), ("now_playing", "Now Playing"), ("automation", "Otomasyon"), ("none", "Boş"))

        card = self._card("window_manager_title", "window_manager_desc")
        option_values = [label for _value, label in WINDOW_OPTIONS]
        option_map = {label: value for value, label in WINDOW_OPTIONS}
        reverse_map = {value: label for value, label in WINDOW_OPTIONS}
        for index, screen in enumerate(screens, start=1):
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=(4, 4))
            label = f"{self._text('display')} {index}"
            if screen.get("width"):
                label += f"  ·  {screen['width']}×{screen['height']}"
            ctk.CTkLabel(row, text=label, text_color=self.palette["text"], anchor="w").pack(side="left", fill="x", expand=True)
            menu = ctk.CTkOptionMenu(
                row, values=option_values, width=150, height=32,
                fg_color=self.palette["entry"], button_color=self.palette["accent"],
                button_hover_color=self.palette["hover"], text_color=self.palette["text"],
            )
            selected = reverse_map.get(assignments.get(str(index), "none"), option_values[-1])
            menu.set(selected)

            def changed(value, key=str(index), selector=menu):
                self.data.setdefault("neto_window_assignments", {})[key] = option_map.get(value, "none")
                self._save()
                callback = self.window_layout_callback
                if callable(callback):
                    try:
                        callback()
                    except Exception:
                        pass

            menu.configure(command=changed)
            menu.pack(side="right")

        self._button(card, "apply_window_layout", lambda: self.window_layout_callback() if callable(self.window_layout_callback) else None, primary=True).pack(anchor="w", padx=16, pady=(12, 8))

    def _render_security(self):
        self._heading("security_title", "security_desc")
        card = self._card("swear_filter", "swear_desc")
        self._switch_row(card, "swear_filter", "kufur_filtresi", True)

        card = self._card("local_only", "local_only_desc")
        self._switch_row(card, "local_only", "local_api_loopback_only", True)

        card = self._card("safe_actions", "safe_actions_desc")
        self._switch_row(card, "safe_actions", "dangerous_actions_confirmation", True)

    def _render_updates(self):
        tr = self.lang == "tr"
        p = self.palette
        project_dir = Path(__file__).resolve().parent
        current_version = _app_version()

        text = {
            "title": "Güncellemeler" if tr else "Updates",
            "desc": (
                "Sürüm, bileşenler, yayın kanalı ve güncelleme işlemleri."
                if tr else
                "Version, components, release channel, and update operations."
            ),
            "overview": "Sürüm özeti" if tr else "Version overview",
            "overview_desc": (
                f"Kurulu {APP_NAME} sürümü ve çalışma ortamı."
                if tr else
                f"Installed {APP_NAME} version and runtime environment."
            ),
            "current": "Mevcut sürüm" if tr else "Current version",
            "edition": "Tasarım dili" if tr else "Design language",
            "channel": "Yayın kanalı" if tr else "Release channel",
            "python": "Python" if tr else "Python",
            "stable": "Kararlı" if tr else "Stable",
            "preview": "Önizleme" if tr else "Preview",
            "ready": "Kontrole hazır" if tr else "Ready to check",
            "check": "Güncellemeleri kontrol et" if tr else "Check for updates",
            "checking": "Yayınlar kontrol ediliyor…" if tr else "Checking releases…",
            "download": "Güncellemeyi indir" if tr else "Download update",
            "install": "İndirilen güncellemeyi kur" if tr else "Install downloaded update",
            "release": "Yayın sayfasını aç" if tr else "Open release page",
            "components": "Bileşen sağlığı" if tr else "Component health",
            "components_desc": (
                f"{APP_NAME}'un önemli modüllerinin kurulum ve erişim durumu."
                if tr else
                f"Installation and availability of important {APP_NAME} modules."
            ),
            "system": "Sistem ve teşhis" if tr else "System and diagnostics",
            "system_desc": (
                "Çalışma ortamı, klasörler ve onarım araçları."
                if tr else
                "Runtime environment, folders, and repair tools."
            ),
            "notes": "Bu sürümde" if tr else "In this build",
            "notes_desc": (
                "Kurtarılan projeye eklenen başlıca iyileştirmeler."
                if tr else
                "Main improvements added to the recovered project."
            ),
            "auto": "Uygulama açıldığında otomatik kontrol et" if tr else "Check automatically at startup",
            "refresh": "Bileşenleri yenile" if tr else "Refresh components",
            "open_project": "Proje klasörünü aç" if tr else "Open project folder",
            "open_data": "Veri klasörünü aç" if tr else "Open data folder",
            "doctor": f"{APP_NAME} Doktor'u çalıştır" if tr else f"Run {APP_NAME} Doctor",
            "last_check": "Son kontrol" if tr else "Last check",
            "never": "Henüz kontrol edilmedi" if tr else "Not checked yet",
            "installed": "Kurulu" if tr else "Installed",
            "missing": "Eksik" if tr else "Missing",
        }

        self._heading("updates_title", "updates_desc")

        summary = self._card("current_version", "updates_desc")

        grid = ctk.CTkFrame(summary, fg_color="transparent")
        grid.pack(fill="x", padx=16, pady=(4, 10))
        grid.grid_columnconfigure((0, 1), weight=1)

        def stat_card(column, label, value, accent=False):
            frame = ctk.CTkFrame(
                grid,
                fg_color=p["entry"],
                border_width=1,
                border_color=p["border"],
                corner_radius=12,
            )
            frame.grid(row=0 if column < 2 else 1, column=column % 2, sticky="ew",
                       padx=(0, 5) if column % 2 == 0 else (5, 0), pady=5)
            ctk.CTkLabel(
                frame,
                text=label,
                text_color=p["muted"],
                font=("Segoe UI", 10),
                anchor="w",
            ).pack(fill="x", padx=12, pady=(9, 1))
            ctk.CTkLabel(
                frame,
                text=value,
                text_color=p["accent"] if accent else p["text"],
                font=("Segoe UI Semibold", 14),
                anchor="w",
            ).pack(fill="x", padx=12, pady=(0, 9))

        channel_value = str(self.data.get("update_channel", "stable")).lower()
        stat_card(0, text["current"], f"v{current_version}", True)
        stat_card(1, text["edition"], APP_DESIGN_FULL_TITLE)
        stat_card(2, text["channel"], text["preview"] if channel_value == "preview" else text["stable"])
        stat_card(3, text["python"], f"{sys.version.split()[0]} · {platform.machine()}")

        controls = ctk.CTkFrame(summary, fg_color="transparent")
        controls.pack(fill="x", padx=16, pady=(0, 8))
        controls.grid_columnconfigure(1, weight=1)

        channel_label = ctk.CTkLabel(
            controls,
            text=text["channel"],
            text_color=p["muted"],
            font=("Segoe UI", 10),
        )
        channel_label.grid(row=0, column=0, sticky="w", padx=(0, 9))

        channel = ctk.CTkSegmentedButton(
            controls,
            values=[text["stable"], text["preview"]],
            selected_color=p["accent"],
            selected_hover_color=p["accent"],
            unselected_color=p["entry"],
            unselected_hover_color=p["hover"],
            text_color=p["text"],
            command=lambda value: self._set_update_channel(
                "preview" if value == text["preview"] else "stable"
            ),
        )
        channel.grid(row=0, column=1, sticky="w")
        channel.set(text["preview"] if channel_value == "preview" else text["stable"])

        auto_var = ctk.BooleanVar(value=bool(self.data.get("auto_update_check", True)))

        def save_auto():
            self.data["auto_update_check"] = bool(auto_var.get())
            self._save()

        auto_switch = ctk.CTkSwitch(
            controls,
            text=text["auto"],
            variable=auto_var,
            command=save_auto,
            progress_color=p["accent"],
            button_color=p["text"],
            button_hover_color=p["text"],
            fg_color=p["switch_off"],
            text_color=p["text"],
            font=("Segoe UI", 10),
        )
        auto_switch.grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 2))

        status_frame = ctk.CTkFrame(
            summary,
            fg_color=p["entry"],
            border_width=1,
            border_color=p["border"],
            corner_radius=12,
        )
        status_frame.pack(fill="x", padx=16, pady=(4, 8))

        status_title = ctk.CTkLabel(
            status_frame,
            text=text["ready"],
            text_color=p["text"],
            font=("Segoe UI Semibold", 12),
            anchor="w",
        )
        status_title.pack(fill="x", padx=12, pady=(10, 1))

        status_detail = ctk.CTkLabel(
            status_frame,
            text="",
            text_color=p["muted"],
            font=("Segoe UI", 10),
            anchor="w",
            justify="left",
            wraplength=600,
        )
        status_detail.pack(fill="x", padx=12, pady=(0, 8))

        progress = ctk.CTkProgressBar(
            status_frame,
            height=7,
            progress_color=p["accent"],
            fg_color=p["border"],
        )
        progress.pack(fill="x", padx=12, pady=(0, 11))
        progress.set(0)

        action_row = ctk.CTkFrame(summary, fg_color="transparent")
        action_row.pack(fill="x", padx=16, pady=(0, 12))

        check_button = self._button(action_row, "check_updates", lambda: None, primary=True)
        check_button.configure(text=text["check"])
        check_button.pack(side="left", padx=(0, 6))

        download_button = self._button(action_row, "check_updates", lambda: None)
        download_button.configure(text=text["download"], state="disabled")
        download_button.pack(side="left", padx=3)

        install_button = self._button(action_row, "check_updates", lambda: None)
        install_button.configure(text=text["install"], state="disabled")
        install_button.pack(side="left", padx=3)

        release_button = self._button(action_row, "check_updates", lambda: None)
        release_button.configure(text=text["release"], state="disabled")
        release_button.pack(side="left", padx=3)

        last_check_value = self.data.get("last_update_check_at")
        if last_check_value:
            try:
                last_check_text = datetime.fromtimestamp(float(last_check_value)).strftime("%d.%m.%Y %H:%M")
            except Exception:
                last_check_text = text["never"]
        else:
            last_check_text = text["never"]

        last_check_label = ctk.CTkLabel(
            summary,
            text=f"{text['last_check']}: {last_check_text}",
            text_color=p["muted"],
            font=("Segoe UI", 9),
            anchor="w",
        )
        last_check_label.pack(fill="x", padx=16, pady=(0, 13))

        notes_box = ctk.CTkTextbox(
            summary,
            height=120,
            fg_color=p["entry"],
            text_color=p["text"],
            border_width=1,
            border_color=p["border"],
            font=("Segoe UI", 10),
            wrap="word",
        )
        notes_box.pack(fill="x", padx=16, pady=(0, 14))
        notes_box.insert(
            "1.0",
            (
                "Yayın notları güncelleme kontrolünden sonra burada gösterilir."
                if tr else
                "Release notes will appear here after checking for updates."
            ),
        )
        notes_box.configure(state="disabled")

        self._update_last_result = None
        self._update_downloaded_path = None

        def set_notes(value):
            notes_box.configure(state="normal")
            notes_box.delete("1.0", "end")
            notes_box.insert("1.0", str(value or ""))
            notes_box.configure(state="disabled")

        def finish_check(result):
            check_button.configure(state="normal")
            progress.stop()
            progress.set(1)

            if not isinstance(result, dict):
                result = {"error": str(result), "message": str(result)}

            self._update_last_result = result
            now = time.time()
            self.data["last_update_check_at"] = now
            self._save()
            last_check_label.configure(
                text=f"{text['last_check']}: {datetime.fromtimestamp(now).strftime('%d.%m.%Y %H:%M')}"
            )

            error = str(result.get("error") or "")
            available = bool(
                result.get("available")
                or result.get("update_available")
                or result.get("is_available")
            )
            latest = str(
                result.get("latest_version")
                or result.get("tag_name")
                or current_version
            ).lstrip("vV")
            message = str(result.get("message") or "")

            if error:
                status_title.configure(
                    text="Kontrol başarısız" if tr else "Check failed",
                    text_color="#EF4444",
                )
                status_detail.configure(text=message or error)
                set_notes(error)
                return

            release_button.configure(state="normal")
            if available:
                status_title.configure(
                    text=(
                        f"Yeni sürüm bulundu · v{latest}"
                        if tr else
                        f"New version available · v{latest}"
                    ),
                    text_color=p["accent"],
                )
                status_detail.configure(
                    text=message or (
                        "Güncelleme indirilmeye hazır."
                        if tr else
                        "The update is ready to download."
                    )
                )
                download_button.configure(
                    state="normal" if result.get("download_url") else "disabled"
                )
            else:
                status_title.configure(
                    text=f"{APP_NAME} güncel" if tr else f"{APP_NAME} is up to date",
                    text_color=p["accent"],
                )
                status_detail.configure(
                    text=message or f"v{current_version}"
                )

            body = str(result.get("body") or "")
            set_notes(
                body
                or (
                    "Bu yayın için ayrıntılı sürüm notu bulunamadı."
                    if tr else
                    "No detailed release notes were provided for this release."
                )
            )

        def run_check():
            check_button.configure(state="disabled")
            download_button.configure(state="disabled")
            install_button.configure(state="disabled")
            release_button.configure(state="disabled")
            status_title.configure(text=text["checking"], text_color=p["text"])
            status_detail.configure(text="")
            progress.set(0)
            progress.start()

            def worker():
                try:
                    import neto_updater
                    include_preview = str(self.data.get("update_channel", "stable")) == "preview"
                    checker = getattr(neto_updater, "check_for_updates", None)
                    if not callable(checker):
                        checker = getattr(neto_updater, "check_update", None)
                    if not callable(checker):
                        raise RuntimeError(
                            "neto_updater güncelleme kontrol fonksiyonu sunmuyor."
                        )
                    result = checker(
                        force=True,
                        include_prerelease=include_preview,
                    )
                except Exception as exc:
                    result = {
                        "error": str(exc),
                        "message": (
                            f"Güncelleme kontrolü başarısız: {exc}"
                            if tr else
                            f"Update check failed: {exc}"
                        ),
                    }
                try:
                    self.root.after(0, lambda: finish_check(result))
                except Exception:
                    pass

            threading.Thread(target=worker, daemon=True, name="NetoSettingsUpdateCheck").start()

        def download_update():
            result = self._update_last_result
            if not isinstance(result, dict):
                return
            download_button.configure(state="disabled")
            check_button.configure(state="disabled")
            status_title.configure(
                text="Güncelleme indiriliyor…" if tr else "Downloading update…",
                text_color=p["text"],
            )
            progress.set(0)

            def progress_callback(done, total=0):
                value = (float(done) / float(total)) if total else 0
                try:
                    self.root.after(0, lambda: progress.set(max(0, min(1, value))))
                except Exception:
                    pass

            def worker():
                try:
                    import neto_updater
                    path = neto_updater.download_update(
                        result,
                        progress_callback=progress_callback,
                    )
                    error = ""
                except Exception as exc:
                    path = ""
                    error = str(exc)

                def finish():
                    check_button.configure(state="normal")
                    if error:
                        status_title.configure(
                            text="İndirme başarısız" if tr else "Download failed",
                            text_color="#EF4444",
                        )
                        status_detail.configure(text=error)
                        download_button.configure(state="normal")
                        return
                    self._update_downloaded_path = path
                    progress.set(1)
                    status_title.configure(
                        text="Güncelleme indirildi" if tr else "Update downloaded",
                        text_color=p["accent"],
                    )
                    status_detail.configure(text=str(path))
                    install_button.configure(state="normal")
                    download_button.configure(state="normal")

                try:
                    self.root.after(0, finish)
                except Exception:
                    pass

            threading.Thread(target=worker, daemon=True, name="NetoUpdateDownload").start()

        def install_update():
            path = self._update_downloaded_path
            if not path:
                return
            if not messagebox.askyesno(
                text["install"],
                (
                    f"{APP_NAME} kapatılıp indirilen güncelleme kurulsun mu?"
                    if tr else
                    f"Close {APP_NAME} and install the downloaded update?"
                ),
                parent=self.root,
            ):
                return
            try:
                import neto_updater
                result = neto_updater.install_update(path)
                status_detail.configure(text=str(result))
                status_title.configure(
                    text="Kurulum başlatıldı" if tr else "Installation started",
                    text_color=p["accent"],
                )
            except Exception as exc:
                messagebox.showerror(
                    text["install"],
                    str(exc),
                    parent=self.root,
                )

        def open_release():
            result = self._update_last_result
            try:
                import neto_updater
                neto_updater.open_release_page(result)
            except Exception:
                url = ""
                if isinstance(result, dict):
                    url = str(result.get("html_url") or "")
                if url:
                    webbrowser.open(url)

        check_button.configure(command=run_check)
        download_button.configure(command=download_update)
        install_button.configure(command=install_update)
        release_button.configure(command=open_release)

        components = self._card("updates_title", "updates_desc")
        components.winfo_children()[0].configure(text=text["components"])
        try:
            components.winfo_children()[1].configure(text=text["components_desc"])
        except Exception:
            pass

        component_list = ctk.CTkFrame(components, fg_color="transparent")
        component_list.pack(fill="x", padx=16, pady=(2, 8))

        component_defs = [
            (f"{APP_NAME} Core", "asistan beta.py"),
            ("Ayarlar", "neto_settings_page.py"),
            ("Güncelleyici", "neto_updater.py"),
            ("Live Mode", "neto_live_mode.py"),
            ("Now Playing", "neto_now_playing.py"),
            (f"{APP_NAME} Agent", "neto_agent.py"),
            ("Android", "neto_android_device.py"),
        ]
        component_labels = []

        def refresh_components():
            for widget in component_labels:
                try:
                    widget.destroy()
                except Exception:
                    pass
            component_labels.clear()

            for index, (name, filename) in enumerate(component_defs):
                exists = (project_dir / filename).is_file()
                row = ctk.CTkFrame(
                    component_list,
                    fg_color=p["entry"],
                    corner_radius=10,
                )
                row.pack(fill="x", pady=3)
                ctk.CTkLabel(
                    row,
                    text=name,
                    text_color=p["text"],
                    font=("Segoe UI Semibold", 10),
                    anchor="w",
                ).pack(side="left", padx=11, pady=8)
                ctk.CTkLabel(
                    row,
                    text=text["installed"] if exists else text["missing"],
                    text_color=p["accent"] if exists else "#EF4444",
                    font=("Segoe UI Semibold", 9),
                ).pack(side="right", padx=11, pady=8)
                component_labels.append(row)

        refresh_components()
        refresh_button = self._button(components, "check_updates", refresh_components)
        refresh_button.configure(text=text["refresh"])
        refresh_button.pack(anchor="w", padx=16, pady=(0, 13))

        system = self._card("about_title", "about_desc")
        system.winfo_children()[0].configure(text=text["system"])
        try:
            system.winfo_children()[1].configure(text=text["system_desc"])
        except Exception:
            pass

        system_rows = [
            ("İşletim sistemi" if tr else "Operating system", f"{platform.system()} {platform.release()}"),
            ("Mimari" if tr else "Architecture", platform.machine()),
            ("Python", sys.version.split()[0]),
            ("Proje" if tr else "Project", str(project_dir)),
            ("Yerel veri" if tr else "Local data", str(_local_data_dir())),
        ]

        for label, value in system_rows:
            row = ctk.CTkFrame(system, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=3)
            ctk.CTkLabel(
                row,
                text=label,
                text_color=p["muted"],
                font=("Segoe UI", 9),
                anchor="w",
            ).pack(side="left")
            ctk.CTkLabel(
                row,
                text=value,
                text_color=p["text"],
                font=("Consolas", 9),
                anchor="e",
            ).pack(side="right", padx=(10, 0))

        system_actions = ctk.CTkFrame(system, fg_color="transparent")
        system_actions.pack(fill="x", padx=16, pady=(10, 14))

        def open_path(path):
            try:
                path = Path(path)
                path.mkdir(parents=True, exist_ok=True)
                if os.name == "nt":
                    os.startfile(str(path))
                else:
                    webbrowser.open(path.as_uri())
            except Exception as exc:
                messagebox.showerror(text["system"], str(exc), parent=self.root)

        def run_doctor():
            doctor = project_dir / "neto_doctor.py"
            if not doctor.is_file():
                messagebox.showerror(
                    text["doctor"],
                    (
                        "neto_doctor.py proje klasöründe bulunamadı."
                        if tr else
                        "neto_doctor.py was not found in the project folder."
                    ),
                    parent=self.root,
                )
                return
            try:
                subprocess.Popen(
                    [sys.executable, str(doctor), "--project", str(project_dir)],
                    cwd=str(project_dir),
                )
            except Exception as exc:
                messagebox.showerror(text["doctor"], str(exc), parent=self.root)

        project_button = self._button(system_actions, "open_data", lambda: open_path(project_dir))
        project_button.configure(text=text["open_project"])
        project_button.pack(side="left", padx=(0, 5))

        data_button = self._button(system_actions, "open_data", lambda: open_path(_local_data_dir()))
        data_button.configure(text=text["open_data"])
        data_button.pack(side="left", padx=5)

        doctor_button = self._button(system_actions, "open_data", run_doctor)
        doctor_button.configure(text=text["doctor"])
        doctor_button.pack(side="left", padx=5)

        changes = self._card("product", "about_desc")
        changes.winfo_children()[0].configure(text=text["notes"])
        try:
            changes.winfo_children()[1].configure(text=text["notes_desc"])
        except Exception:
            pass

        items = [
            "Kapsamlı kaldırılmış gömülü editör proje editörü" if tr else "Comprehensive kaldırılmış gömülü editör project editor",
            "Gerçek güncelleme kontrolü, indirme ve kurulum akışı" if tr else "Real update check, download, and installation flow",
            "Bileşen sağlık ve eksik dosya görünümü" if tr else "Component health and missing-file view",
            "Zorla hızlı ve normal başlatma profilleri" if tr else "Forced-fast and normal startup profiles",
            "Ayarlar, güvenlik ve marka bütünlüğü" if tr else "Settings, security, and branding consistency",
        ]
        for item in items:
            ctk.CTkLabel(
                changes,
                text="• " + item,
                text_color=p["text"],
                font=("Segoe UI", 10),
                anchor="w",
                justify="left",
            ).pack(fill="x", padx=16, pady=3)
        ctk.CTkFrame(changes, height=8, fg_color="transparent").pack()

    def _set_update_channel(self, channel):
        self.data["update_channel"] = "preview" if channel == "preview" else "stable"
        self._save()

    def _render_about(self):
        self._heading("about_title", "about_desc")
        card = self._card("product", "about_desc")

        rows = [
            (self._text("product"), APP_NAME),
            (self._text("current_version"), f"v{_app_version()}"),
            (self._text("edition"), APP_DESIGN_FULL_TITLE),
            (self._text("python"), sys.version.split()[0]),
            (self._text("data_location"), str(_local_data_dir())),
        ]
        for label, value in rows:
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=(4, 6))
            ctk.CTkLabel(
                row,
                text=label,
                text_color=self.palette["muted"],
                font=("Segoe UI", 11),
                anchor="w",
            ).pack(side="left")
            ctk.CTkLabel(
                row,
                text=value,
                text_color=self.palette["text"],
                font=("Segoe UI Semibold", 11),
                anchor="e",
            ).pack(side="right", padx=(10, 0))

        def open_data():
            path = _local_data_dir()
            path.mkdir(parents=True, exist_ok=True)
            try:
                if os.name == "nt":
                    os.startfile(str(path))
                else:
                    webbrowser.open(path.as_uri())
            except Exception:
                pass

        self._button(card, "open_data", open_data).pack(anchor="w", padx=16, pady=(8, 15))

    def show_section(self, section="general"):
        """Render one section at a time and coalesce rapid navigation clicks."""
        requested = section if section in {
            "general", "system", "appearance", "window_manager", "netolab", "security", "updates", "about"
        } else "general"
        if self._rendering:
            self._pending_section = requested
            return False
        self._rendering = True
        try:
            return self._show_section_now(requested)
        finally:
            self._rendering = False
            pending = self._pending_section
            self._pending_section = None
            if pending is not None and pending != self.section:
                try:
                    self.root.after_idle(lambda selected=pending: self.show_section(selected))
                except Exception:
                    pass

    def _show_section_now(self, section="general"):
        from neto_widget_motion import reset_hover_tree, bind_hover_tree
        self._render_token += 1
        render_token = self._render_token
        try:
            if self._hover_bind_job:
                self.root.after_cancel(self._hover_bind_job)
        except Exception:
            pass
        self._hover_bind_job = None
        reset_hover_tree(self.surface)
        self.section = section if section in {
            "general", "system", "appearance", "window_manager", "netolab", "security", "updates", "about"
        } else "general"

        for key, button in self.nav_buttons.items():
            selected = key == self.section
            button.configure(
                fg_color=self.palette["accent"] if selected else "transparent",
                hover_color=self.palette["accent"] if selected else self.palette["hover"],
                text_color="#FFFFFF" if selected else self.palette["text"],
            )

        self._clear(self.content)
        try:
            _sync_scrollable_surface(self.content, self.palette, "bg")
        except Exception:
            pass
        renderers = {
            "general": self._render_general,
            "system": self._render_system,
            "appearance": self._render_appearance,
            "window_manager": self._render_window_manager,
            "netolab": self._render_netolab,
            "security": self._render_security,
            "updates": self._render_updates,
            "about": self._render_about,
        }
        renderers[self.section]()

        def _bind_hover_later():
            self._hover_bind_job = None
            if render_token != self._render_token:
                return
            try:
                bind_hover_tree(self.surface, self.root)
            except Exception:
                pass

        try:
            delay = 80 if self.section == "system" else 1
            self._hover_bind_job = self.root.after(delay, _bind_hover_later)
        except Exception:
            _bind_hover_later()

        try:
            canvas = getattr(self.content, "_parent_canvas", None)
            if canvas is not None:
                canvas.yview_moveto(0)
        except Exception:
            pass
        return True

    def open(self, section="general"):
        previous_lang, previous_palette = self.lang, self.palette
        self.data = self._load()
        self.lang = self._language()
        self.palette = self._palette()
        target = section or "general"
        if callable(self.on_open):
            self.on_open()
        rebuild = self.surface is None or not self.surface.winfo_exists()
        if not rebuild and (previous_lang != self.lang or previous_palette != self.palette):
            self.surface.destroy()
            self.surface = None
            rebuild = True
        if rebuild:
            self.section = target
            self._build()
        else:
            self.surface.place(relx=0, rely=0, relwidth=1, relheight=1)
            if target != self.section:
                self.show_section(target)
        self.is_open = True
        self.surface.lift()
        return True

    def close(self):
        if self.surface is not None:
            try:
                self.surface.place_forget()
            except Exception:
                pass
        self.is_open = False
        if callable(self.on_close):
            try:
                self.on_close()
            except Exception:
                pass
        return True

    def refresh_language(self):
        self.lang = self._language()
        was_open = self.is_open
        section = self.section
        if self.surface is not None:
            try:
                self.surface.destroy()
            except Exception:
                pass
            self.surface = None
        if was_open:
            self._build()
            self.section = section
            self.show_section(section)
        return True

    def refresh_theme(self):
        self.data = self._load()
        self.palette = self._palette()
        was_open = self.is_open
        section = self.section
        if self.surface is not None:
            try:
                self.surface.destroy()
            except Exception:
                pass
            self.surface = None
        if was_open:
            self._build()
            self.section = section
            self.show_section(section)
        return True


def create_settings_page(*args, **kwargs):
    return NetoSettingsPage(*args, **kwargs)
