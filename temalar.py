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

# Aktif paleti başlat
aktif_palet = DARK_PALET.copy()


def veri_yukle():
    """hafiza.json dosyasından ayarları okur (tema ve renk teması için)."""
    varsayilan = {"tema": "light", "renk_temasi": "blue", "arayuz_stili": "experians"}
    if os.path.exists(FILE_PATH):
        try:
            with open(FILE_PATH, "r", encoding="utf-8") as f:
                varsayilan.update(json.load(f))
        except Exception:
            pass
    if varsayilan.get("renk_temasi") not in VALID_COLOR_THEMES:
        varsayilan["renk_temasi"] = "green"
    varsayilan["arayuz_stili"] = _arayuz_stili_normalize(varsayilan.get("arayuz_stili", "experians"))
    return varsayilan


def _arayuz_stili_normalize(value):
    deger = str(value or "classic").strip().lower()
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
        "experians 3.0": "experians3",
        "experians3": "experians3",
        "experience 3.0": "experians3",
        "experience3": "experians3",
        "neto experience 3.0": "experians3",
        "neto experience3": "experians3",
        "klasik": "classic",
    }
    deger = aliases.get(deger, deger)
    if deger in VALID_SURFACE_STYLES:
        return deger
    return "classic"


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
            arayuz_stili = ayar.get("arayuz_stili", "classic")
    else:
        if arayuz_stili is None:
            arayuz_stili = veri_yukle().get("arayuz_stili", "classic")

    arayuz_stili = _arayuz_stili_normalize(arayuz_stili)

    # Paleti seç
    stil_haritasi = SURFACE_PALETS.get(arayuz_stili, SURFACE_PALETS["classic"])
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

    # Widget tipine göre güncelle
    if isinstance(widget, ctk.CTkFrame):
        if widget == g('side_panel'):
            widget.configure(fg_color=aktif_palet["sidebar"])
        elif widget in (g('main_c'), g('chat_container'), g('input_container')):
            widget.configure(fg_color=aktif_palet["bg"])
        elif widget == g('giris_frame'):
            widget.configure(fg_color=aktif_palet["card"], border_color=aktif_palet["neon"])
        else:
            try:
                widget.configure(fg_color=aktif_palet["card"])
            except:
                pass

    elif isinstance(widget, ctk.CTkButton):
        if widget == g('btn_anahtar'):
            pass  # Eklenti durum butonu özel renklerini korur
        elif widget == g('btn_gonder'):
            widget.configure(fg_color=aktif_palet["neon"],
                             text_color="#000000" if tema_adi == "dark" else "#FFFFFF",
                             hover_color="#18ab4c")
        else:
            widget.configure(fg_color=aktif_palet["button_fg"],
                             hover_color=aktif_palet["button_hover"],
                             text_color=aktif_palet["button_text"])

    elif isinstance(widget, ctk.CTkLabel):
        widget.configure(text_color=aktif_palet["text_main"])

    elif isinstance(widget, ctk.CTkTextbox):
        widget.configure(fg_color=aktif_palet["card"], text_color=aktif_palet["text_main"])

    elif isinstance(widget, ctk.CTkEntry):
        widget.configure(fg_color=aktif_palet["entry_bg"],
                         text_color=aktif_palet["text_main"],
                         border_color=aktif_palet["entry_border"])

    elif isinstance(widget, ctk.CTkSwitch):
        # Switch renkleri otomatik ayarlanır, müdahale etmiyoruz
        pass

    elif isinstance(widget, ctk.CTkOptionMenu):
        widget.configure(fg_color=aktif_palet["button_fg"],
                         button_color=aktif_palet["neon"],
                         button_hover_color=aktif_palet["button_hover"],
                         text_color=aktif_palet["text_main"])

    elif isinstance(widget, tk.Label):
        widget.configure(bg=aktif_palet["bg"], fg=aktif_palet["text_main"])

    # Alt widget'lara da uygula
    _tum_widgetlari_guncelle(widget, tema_adi)
