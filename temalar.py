# temalar.py
import tkinter as tk
import customtkinter as ctk
import json
import os

# config.py'deki paletleri ve yolları içe aktar
from config import (
    DARK_PALET, LIGHT_PALET, SURFACE_PALETS, VALID_COLOR_THEMES, VALID_SURFACE_STYLES,
    FILE_PATH, BASE_DIR
)
from neto_fluent_design import FLUENT_DARK, fluent_card_style, fluent_control_style, fluent_input_style
from neto_astryx_design import astryx_card_style, astryx_control_style, astryx_input_style

# Aktif paleti başlat
# Start in Fluent even before the first settings read. This prevents a brief
# legacy black/green flash in secondary windows opened during startup.
aktif_palet = dict(FLUENT_DARK)


def veri_yukle():
    """hafiza.json dosyasından ayarları okur (tema ve renk teması için)."""
    varsayilan = {"tema": "dark", "renk_temasi": "blue", "arayuz_stili": "fluent"}
    if os.path.exists(FILE_PATH):
        try:
            with open(FILE_PATH, "r", encoding="utf-8") as f:
                varsayilan.update(json.load(f))
        except Exception:
            pass
    if varsayilan.get("renk_temasi") not in VALID_COLOR_THEMES:
        varsayilan["renk_temasi"] = "green"
    varsayilan["arayuz_stili"] = _arayuz_stili_normalize(varsayilan.get("arayuz_stili", "fluent"))
    return varsayilan


def _arayuz_stili_normalize(value):
    deger = str(value or "fluent").strip().lower()
    aliases = {
        "glass": "fluent",
        "liquid glass": "fluent",
        "liquid_glass": "fluent",
        "liquid-glass": "fluent",
        "sıvı cam": "fluent",
        "sivi cam": "fluent",
        "cam": "fluent",
        "fluent design": "fluent",
        "microsoft fluent": "fluent",
        "fluent": "fluent",
        "experians 2.5": "fluent",
        "neto experians": "fluent",
        "experians": "fluent",
        "experians 3.0": "fluent",
        "experians3": "fluent",
        "experience 3.0": "fluent",
        "experience3": "fluent",
        "neto experience 3.0": "fluent",
        "neto experience3": "fluent",
        "zenka": "fluent",
        "zenkamind ai": "fluent",
        "zenkamind": "fluent",
        "klasik": "fluent",
        "classic": "fluent",
    }
    deger = aliases.get(deger, deger)
    if deger in VALID_SURFACE_STYLES:
        return deger
    return "fluent"


def tema_uygula(tema_adi=None, renk_temasi=None, arayuz_stili=None):
    """
    Tüm arayüzü belirtilen temaya göre günceller.
    tema_adi: "dark" veya "light"
    renk_temasi: "green", "blue", "dark-blue"
    """
    global aktif_palet

    # Eğer parametre verilmemişse kayıtlı ayarları kullan
    if tema_adi is None or renk_temasi is None:
        ayar = veri_yukle()
        if tema_adi is None:
            tema_adi = ayar.get("tema", "dark")
        if renk_temasi is None:
            renk_temasi = ayar.get("renk_temasi", "green")
        if arayuz_stili is None:
            arayuz_stili = ayar.get("arayuz_stili", "fluent")
    else:
        if arayuz_stili is None:
            arayuz_stili = veri_yukle().get("arayuz_stili", "fluent")

    arayuz_stili = _arayuz_stili_normalize(arayuz_stili)

    # Paleti seç
    stil_haritasi = SURFACE_PALETS.get(arayuz_stili, SURFACE_PALETS["fluent"])
    if tema_adi == "light":
        aktif_palet = dict(stil_haritasi.get("light", LIGHT_PALET))
    else:
        aktif_palet = dict(stil_haritasi.get("dark", DARK_PALET))

    # CustomTkinter görünüm modunu ayarla
    ctk.set_appearance_mode(tema_adi)
    if renk_temasi in VALID_COLOR_THEMES:
        ctk.set_default_color_theme(renk_temasi)

    # Ana pencereyi ve tüm alt widget'ları güncelle
    import __main__ as main_mod
    if hasattr(main_mod, 'root') and main_mod.root.winfo_exists():
        main_mod.root.configure(fg_color=aktif_palet["bg"])
        _tum_widgetlari_guncelle(main_mod.root, tema_adi)
        # Açık Toplevel pencereleri de güncelle
        for win in main_mod.root.winfo_children():
            if isinstance(win, ctk.CTkToplevel):
                win.configure(fg_color=aktif_palet["bg"])
                _tum_widgetlari_guncelle(win, tema_adi)
        main_mod.root.update_idletasks()

        # Neto Experience 3.0 katmanı (yalnızca ekleme).
        # Ayar dosyasinda enabled=false ise bu cagri hicbir sey yapmaz.
        try:
            import neto_experience3
            neto_experience3.apply(main_mod.root, palette=dict(aktif_palet))
        except Exception:
            pass


def _tum_widgetlari_guncelle(ebeveyn, tema_adi):
    """Verilen ebeveyn widget'ın tüm çocuklarını recursive olarak günceller."""
    for widget in ebeveyn.winfo_children():
        _widget_guncelle(widget, tema_adi)


def _widget_guncelle(widget, tema_adi):
    """Tek bir widget'ı temaya göre günceller ve alt öğelerine iner."""
    # Global widget referanslarına güvenli erişim
    import __main__ as main_mod

    def g(name):
        return getattr(main_mod, name, None)

    use_astryx = aktif_palet.get("design_language") == "astryx"
    card_style = astryx_card_style if use_astryx else fluent_card_style
    control_style = astryx_control_style if use_astryx else fluent_control_style
    input_style = astryx_input_style if use_astryx else fluent_input_style
    control_radius = 8 if use_astryx else 6

    # Widget tipine göre güncelle
    if isinstance(widget, ctk.CTkFrame):
        role = getattr(widget, "_neto_surface_role", "")
        try:
            current_color = widget.cget("fg_color")
        except Exception:
            current_color = None
        if current_color == "transparent":
            pass
        elif widget == g('side_panel') or widget == g('unified_sidebar') or role in {"sidebar", "settings_sidebar"}:
            widget.configure(fg_color=aktif_palet["sidebar"])
        elif widget in (g('main_c'), g('chat_container'), g('input_container')) or role in {"root", "content"}:
            widget.configure(fg_color=aktif_palet["bg"])
        elif widget == g('giris_frame') or role in {"card", "dialog"}:
            widget.configure(**card_style(aktif_palet), border_color=aktif_palet["neon"] if widget == g('giris_frame') else aktif_palet["entry_border"])
        else:
            try:
                widget.configure(**card_style(aktif_palet))
            except Exception:
                pass

    elif isinstance(widget, ctk.CTkButton):
        if widget == g('btn_anahtar'):
            pass  # Eklenti durum butonu özel renklerini korur
        elif widget == g('btn_gonder'):
            widget.configure(fg_color=aktif_palet["neon"],
                             text_color=aktif_palet["accent_text"],
                             hover_color=aktif_palet["accent_hover"],
                             border_width=1,
                             border_color=aktif_palet["neon"],
                             corner_radius=control_radius)
        else:
            try:
                widget.configure(**control_style(aktif_palet))
            except Exception:
                pass

    elif isinstance(widget, ctk.CTkLabel):
        widget.configure(text_color=aktif_palet["text_main"])

    elif isinstance(widget, ctk.CTkTextbox):
        try:
            widget.configure(**input_style(aktif_palet))
        except Exception:
            pass

    elif isinstance(widget, ctk.CTkEntry):
        try:
            widget.configure(**input_style(aktif_palet))
        except Exception:
            pass

    elif isinstance(widget, ctk.CTkSwitch):
        try:
            widget.configure(progress_color=aktif_palet["accent"],
                             button_color=aktif_palet["text_main"],
                             button_hover_color=aktif_palet["accent_hover"],
                             fg_color=aktif_palet["entry_border"],
                             text_color=aktif_palet["text_main"])
        except Exception:
            pass

    elif isinstance(widget, ctk.CTkOptionMenu):
        widget.configure(fg_color=aktif_palet["button_fg"],
                         button_color=aktif_palet["accent"],
                         button_hover_color=aktif_palet["button_hover"],
                         text_color=aktif_palet["text_main"],
                         corner_radius=control_radius)

    elif isinstance(widget, ctk.CTkSegmentedButton):
        try:
            widget.configure(fg_color=aktif_palet["entry_bg"],
                             selected_color=aktif_palet["accent"],
                             selected_hover_color=aktif_palet["accent_hover"],
                             unselected_color=aktif_palet["button_fg"],
                             unselected_hover_color=aktif_palet["button_hover"],
                             text_color=aktif_palet["text_main"],
                             corner_radius=control_radius)
        except Exception:
            pass

    elif isinstance(widget, ctk.CTkProgressBar):
        try:
            widget.configure(progress_color=aktif_palet["accent"],
                             fg_color=aktif_palet["entry_border"])
        except Exception:
            pass

    elif isinstance(widget, tk.Label):
        widget.configure(bg=aktif_palet["bg"], fg=aktif_palet["text_main"])

    # Alt widget'lara da uygula
    _tum_widgetlari_guncelle(widget, tema_adi)
