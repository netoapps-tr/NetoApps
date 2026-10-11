# ayarlar.py
import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog
from PIL import Image, ImageTk, ImageSequence
import os
import shutil
import json

from config import (
    ICO_PATH, GIF_PATH, VALID_COLOR_THEMES,
    get_asset_path, get_data_path
)
from temalar import tema_uygula as _temalar_tema_uygula, aktif_palet
import temalar as _temalar_modulu

# Tema ve vurgu motoru. Ana uygulamayla aynı renk mantığını kullanır.
_orijinal_tema_uygula = _temalar_tema_uygula
NETO_TEMA_TABAN_PALETLERI = {
    "dark": {
        "bg": "#09090B", "sidebar": "#111114", "card": "#1B1B20",
        "entry_bg": "#141418", "entry_border": "#34343C",
        "text_main": "#F4F4F5", "text_dim": "#A1A1AA", "button_hover": "#2A2A31",
    },
    "light": {
        "bg": "#F4F5F7", "sidebar": "#FFFFFF", "card": "#E8EAEF",
        "entry_bg": "#FFFFFF", "entry_border": "#C8CDD6",
        "text_main": "#18181B", "text_dim": "#64646F", "button_hover": "#D9DDE5",
    },
}
NETO_VURGU_RENKLERI = {
    "green": "#22C55E", "blue": "#3B82F6", "dark-blue": "#2563EB",
    "purple": "#8B5CF6", "violet": "#8B5CF6", "pink": "#EC4899",
    "red": "#EF4444", "orange": "#F97316", "yellow": "#EAB308",
    "teal": "#14B8A6", "cyan": "#06B6D4",
}

def _tema_adi(secim=None):
    return "light" if str(secim or "dark").strip().lower() in {"light", "açık", "acik", "white", "beyaz"} else "dark"

def _vurgu_adi(secim=None):
    deger = str(secim or "green").strip().lower().replace("_", "-")
    try:
        valid = {str(x).strip().lower() for x in VALID_COLOR_THEMES}
    except Exception:
        valid = set(NETO_VURGU_RENKLERI)
    return deger if deger in valid or deger in NETO_VURGU_RENKLERI else "green"

def _karistir(hex_renk, hedef, oran=0.16):
    try:
        a, b = hex_renk.lstrip("#"), hedef.lstrip("#")
        x = [int(a[i:i+2], 16) for i in (0,2,4)]
        y = [int(b[i:i+2], 16) for i in (0,2,4)]
        out = [round(p + (q-p)*oran) for p,q in zip(x,y)]
        return "#" + "".join(f"{v:02X}" for v in out)
    except Exception:
        return hex_renk

def _kontrast(hex_renk):
    try:
        h = hex_renk.lstrip("#")
        r,g,b = [int(h[i:i+2],16) for i in (0,2,4)]
        return "#111114" if 0.299*r + 0.587*g + 0.114*b >= 155 else "#FFFFFF"
    except Exception:
        return "#FFFFFF"

def tema_uygula(secim=None, renk_temasi=None):
    # Ana uygulama açıksa tek ve optimize edilmiş tema motorunu kullan.
    try:
        import __main__ as main_mod
        ana_motor = getattr(main_mod, "tema_uygula", None)
        if callable(ana_motor) and ana_motor is not tema_uygula:
            return ana_motor(secim, renk_temasi)
    except Exception:
        pass

    h = _veri_yukle() if "_veri_yukle" in globals() else {"tema":"dark", "renk_temasi":"green"}
    raw = str(secim).strip().lower() if secim is not None else ""
    if raw and raw not in {"dark","light","koyu","açık","acik","white","beyaz"} and renk_temasi is None:
        renk_temasi, secim = raw, None
    mod = _tema_adi(secim if secim is not None else h.get("tema", "dark"))
    vurgu_adi = _vurgu_adi(renk_temasi if renk_temasi is not None else h.get("renk_temasi", "green"))
    try:
        ctk.set_appearance_mode("Light" if mod == "light" else "Dark")
    except Exception:
        pass
    try:
        _orijinal_tema_uygula(mod, vurgu_adi)
    except TypeError:
        try: _orijinal_tema_uygula(mod)
        except Exception: pass
    except Exception:
        pass
    palet = dict(NETO_TEMA_TABAN_PALETLERI[mod])
    vurgu = NETO_VURGU_RENKLERI.get(vurgu_adi, NETO_VURGU_RENKLERI["green"])
    palet.update({
        "neon": vurgu, "accent": vurgu,
        "accent_hover": _karistir(vurgu, "#FFFFFF" if mod == "dark" else "#000000"),
        "accent_text": _kontrast(vurgu),
        "button_fg": palet["card"], "button_text": palet["text_main"],
    })
    for hedef in (aktif_palet, getattr(_temalar_modulu, "aktif_palet", None)):
        if isinstance(hedef, dict):
            hedef.clear(); hedef.update(palet)
    try: _temalar_modulu.aktif_palet = aktif_palet
    except Exception: pass
    return aktif_palet

try:
    from lang import T
except Exception:
    def T(key: str, **kwargs) -> str:
        text = {
            "advanced_settings_title":"Gelişmiş Ayarlar", "settings_tab_general":"Genel", "settings_tab_appearance":"Görünüm", "settings_tab_security":"Güvenlik",
            "learning_mode":"Öğrenme Modu", "switch_on_off":"Açık/Kapalı", "theme_mode":"Tema Modu", "color_theme":"Renk Teması",
            "swear_filter":"Küfür Filtresi", "switch_active":"Aktif", "close":"Kapat", "netolab_title":"NetOps Lab",
            "netolab_system":"NetOps özelleştirme sistemi", "live_animation":"Canlı Animasyon", "active_gif":"Aktif GIF: {name}",
            "select_new_gif":"➕ Yeni GIF Seç", "active_sound":"Aktif Ses: {name}", "select_new_sound":"🎵 ➕ Yeni Ses Seç",
            "factory_reset":"Fabrika Ayarlarına Dön", "select_startup_gif_title":"Açılış GIF\'i Seçin", "animated_gif_files":"Animasyonlu GIF",
            "select_startup_sound_title":"Açılış Sesi Seçin", "sound_files":"Ses Dosyaları", "reset_done":"Tüm sistem varsayılana sıfırlandı.",
            "new_gif_saved":"Yeni açılış animasyonu başarıyla tanımlandı!", "new_sound_saved":"Yeni açılış müziği kaydedildi!",
            "json_save_failed":"JSON kaydedilemedi!", "gif_copy_error":"GIF kopyalama hatası: {error}", "sound_copy_error":"Ses kopyalama hatası: {error}"
        }.get(key, key)
        text = str(text or key)
        try: return text.format(**kwargs)
        except Exception: return text

# ------------------------------------------------------------
# Hafıza işlemleri (yardımcı)
# ------------------------------------------------------------
def _veri_yukle():
    from config import FILE_PATH
    varsayilan = {
        "ogrenme_modu_acik": False,
        "kufur_filtresi": True,
        "tema": "dark",
        "renk_temasi": "green",
        "secilen_gif": "yukleme.gif",
        "secilen_ses": "varsayilan"
    }
    if os.path.exists(FILE_PATH):
        try:
            with open(FILE_PATH, "r", encoding="utf-8") as f:
                varsayilan.update(json.load(f))
        except Exception: pass
    varsayilan["renk_temasi"] = _vurgu_adi(varsayilan.get("renk_temasi", "green"))
    return varsayilan

def _veri_kaydet(hafiza):
    from config import FILE_PATH
    try:
        hafiza = dict(hafiza or {})
        hafiza["renk_temasi"] = _vurgu_adi(hafiza.get("renk_temasi", "green"))
        with open(FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(hafiza, f, ensure_ascii=False, indent=4)
        return True
    except Exception: return False

# ------------------------------------------------------------
# Gelişmiş Ayarlar Penceresi
# ------------------------------------------------------------
def gelismis_ayarlar_penceresi_ac(root):
    ayar = ctk.CTkToplevel(root)
    ayar.title(T("advanced_settings_title"))
    ayar.geometry("600x500")
    ayar.configure(fg_color=aktif_palet["bg"])
    ayar.resizable(False, False)
    ayar.focus()

    tabview = ctk.CTkTabview(ayar, fg_color=aktif_palet["bg"])
    tabview.pack(fill="both", expand=True, padx=10, pady=10)

    tab_genel = tabview.add(T("settings_tab_general"))
    tab_gorunum = tabview.add(T("settings_tab_appearance"))
    tab_guvenlik = tabview.add(T("settings_tab_security"))

    h = _veri_yukle()

    # --- Genel ---
    ogrenme_var = ctk.BooleanVar(value=h.get("ogrenme_modu_acik", False))
    def ogrenme_toggle():
        h_updated = _veri_yukle()
        h_updated["ogrenme_modu_acik"] = ogrenme_var.get()
        _veri_kaydet(h_updated)
    ctk.CTkLabel(tab_genel, text=T("learning_mode"), font=("Segoe UI", 14)).pack(pady=(15,5))
    ctk.CTkSwitch(tab_genel, text=T("switch_on_off"), variable=ogrenme_var, command=ogrenme_toggle).pack(pady=5)

    # --- Görünüm ---
    ctk.CTkLabel(tab_gorunum, text=T("theme_mode"), font=("Segoe UI", 14)).pack(pady=(15,5))
    tema_var = ctk.StringVar(value=h.get("tema", "dark"))
    renk_var = ctk.StringVar(value=h.get("renk_temasi", "green"))

    def pencere_temasini_yenile():
        try:
            def boya(widget):
                for child in widget.winfo_children():
                    try:
                        if isinstance(child, ctk.CTkFrame):
                            current = str(child.cget("fg_color")).lower()
                            if current != "transparent":
                                child.configure(fg_color=aktif_palet["card"])
                        elif isinstance(child, ctk.CTkLabel):
                            child.configure(fg_color="transparent", text_color=aktif_palet["text_main"])
                        elif isinstance(child, ctk.CTkButton):
                            child.configure(fg_color=aktif_palet["card"], hover_color=aktif_palet["button_hover"], text_color=aktif_palet["text_main"])
                        elif isinstance(child, ctk.CTkOptionMenu):
                            child.configure(
                                fg_color=aktif_palet["entry_bg"], button_color=aktif_palet["neon"],
                                button_hover_color=aktif_palet.get("accent_hover", aktif_palet["button_hover"]),
                                dropdown_fg_color=aktif_palet["card"], dropdown_hover_color=aktif_palet["button_hover"],
                                text_color=aktif_palet["text_main"],
                            )
                        elif isinstance(child, ctk.CTkSwitch):
                            child.configure(progress_color=aktif_palet["neon"], text_color=aktif_palet["text_main"])
                    except Exception:
                        pass
                    boya(child)
            ayar.configure(fg_color=aktif_palet["bg"])
            tabview.configure(fg_color=aktif_palet["bg"])
            for tab in (tab_genel, tab_gorunum, tab_guvenlik):
                tab.configure(fg_color=aktif_palet["bg"])
            boya(ayar)
        except Exception:
            pass

    def ana_arayuzu_yenile():
        try:
            import __main__ as main_mod
            planla = getattr(main_mod, "_neto_tema_yenile_planla", None)
            if callable(planla):
                planla(settings=True, delay=1)
                return
            yenile = getattr(main_mod, "arayuz_renklerini_yenile", None)
            if callable(yenile):
                root.after_idle(yenile)
        except Exception:
            pass

    def tema_degistir(secim):
        secim = _tema_adi(secim)
        tema_uygula(secim, renk_var.get())
        h_updated = _veri_yukle()
        h_updated["tema"] = secim
        h_updated["renk_temasi"] = _vurgu_adi(renk_var.get())
        _veri_kaydet(h_updated)
        try: ayar.after_idle(pencere_temasini_yenile)
        except Exception: pass
        ana_arayuzu_yenile()

    tema_menu = ctk.CTkOptionMenu(
        tab_gorunum, values=["dark", "light"], variable=tema_var, command=tema_degistir,
        fg_color=aktif_palet["entry_bg"], button_color=aktif_palet["neon"],
        button_hover_color=aktif_palet.get("accent_hover", aktif_palet["button_hover"]),
        text_color=aktif_palet["text_main"],
    )
    tema_menu.pack(pady=5)

    ctk.CTkLabel(tab_gorunum, text=T("color_theme"), font=("Segoe UI", 14)).pack(pady=(18,5))

    def renk_degistir(secim):
        secim = _vurgu_adi(secim)
        renk_var.set(secim)
        tema_uygula(tema_var.get(), secim)
        h_updated = _veri_yukle()
        h_updated["tema"] = _tema_adi(tema_var.get())
        h_updated["renk_temasi"] = secim
        _veri_kaydet(h_updated)
        try: ayar.after_idle(pencere_temasini_yenile)
        except Exception: pass
        ana_arayuzu_yenile()

    renk_menu = ctk.CTkOptionMenu(
        tab_gorunum, values=list(VALID_COLOR_THEMES), variable=renk_var, command=renk_degistir,
        fg_color=aktif_palet["entry_bg"], button_color=aktif_palet["neon"],
        button_hover_color=aktif_palet.get("accent_hover", aktif_palet["button_hover"]),
        text_color=aktif_palet["text_main"],
    )
    renk_menu.pack(pady=5)

    # --- Güvenlik ---
    ctk.CTkLabel(tab_guvenlik, text=T("swear_filter"), font=("Segoe UI", 14)).pack(pady=(15,5))
    kufur_var = ctk.BooleanVar(value=h.get("kufur_filtresi", True))
    def kufur_toggle():
        h_updated = _veri_yukle()
        h_updated["kufur_filtresi"] = kufur_var.get()
        _veri_kaydet(h_updated)
    ctk.CTkSwitch(tab_guvenlik, text=T("switch_active"), variable=kufur_var, command=kufur_toggle).pack(pady=5)

    ctk.CTkButton(ayar, text=T("close"), command=ayar.destroy, fg_color=aktif_palet["card"], corner_radius=8).pack(pady=15)


# ------------------------------------------------------------
# NetOps Lab Özelleştirme Penceresi
# ------------------------------------------------------------
def ozel_ayarlar_penceresi_ac(root):
    ayar_penceresi = ctk.CTkToplevel(root)
    ayar_penceresi.title(T("netolab_title"))
    ayar_penceresi.geometry("550x500")
    ayar_penceresi.configure(fg_color=aktif_palet["bg"])
    ayar_penceresi.resizable(False, False)
    ayar_penceresi.focus()

    ctk.CTkLabel(ayar_penceresi, text=T("netolab_system"), text_color=aktif_palet["text_main"],
                 font=("Segoe UI Semibold", 18)).pack(pady=15)

    kontrol_frame = ctk.CTkFrame(ayar_penceresi, fg_color=aktif_palet["bg"])
    kontrol_frame.pack(side="left", fill="both", expand=True, padx=20)

    onizleme_frame = ctk.CTkFrame(ayar_penceresi, fg_color=aktif_palet["card"], corner_radius=15,
                                   border_width=1, border_color=aktif_palet["neon"])
    onizleme_frame.pack(side="right", padx=20, pady=10)

    # Pencere ikonu
    try:
        if os.path.exists(ICO_PATH):
            icon_img = ImageTk.PhotoImage(file=ICO_PATH)
            getattr(ayar_penceresi, "iconphoto")(True, icon_img)
            setattr(ayar_penceresi, "icon", icon_img)
    except: pass

    ctk.CTkLabel(onizleme_frame, text=T("live_animation"), text_color=aktif_palet["text_dim"],
                 font=("Segoe UI Semibold", 12)).pack(pady=10)

    gif_ekrani = tk.Label(onizleme_frame, bg=aktif_palet["card"])
    gif_ekrani.pack(padx=15, pady=10)

    preview_kareler = []
    def onizleme_oynat(indeks=0):
        if not ayar_penceresi.winfo_exists(): return
        if preview_kareler:
            gif_ekrani.config(image=preview_kareler[indeks])
            ayar_penceresi.after(40, onizleme_oynat, (indeks + 1) % len(preview_kareler))

    def onizleme_guncelle():
        nonlocal preview_kareler
        preview_kareler.clear()
        h = _veri_yukle()
        gif_adi = h.get("secilen_gif", "yukleme.gif")
        yol = get_asset_path(gif_adi)
        if not os.path.exists(yol): yol = get_data_path(gif_adi)
        if not os.path.exists(yol): yol = GIF_PATH
        try:
            img = Image.open(yol)
            for f in ImageSequence.Iterator(img):
                preview_kareler.append(ImageTk.PhotoImage(f.copy().convert("RGBA").resize((150, 150), Image.Resampling.LANCZOS)))
        except Exception: pass

    onizleme_guncelle()
    onizleme_oynat()

    h_mevcut = _veri_yukle()
    gif_lbl = ctk.CTkLabel(kontrol_frame, text=T("active_gif", name=h_mevcut.get("secilen_gif", "yukleme.gif")),
                           text_color=aktif_palet["text_dim"], font=("Segoe UI", 12), anchor="w")
    gif_lbl.pack(fill="x", pady=5)

    def varsayilan_yap():
        h = _veri_yukle()
        h["secilen_gif"], h["secilen_ses"] = "yukleme.gif", "varsayilan"
        if _veri_kaydet(h):
            gif_lbl.configure(text=T("active_gif", name="yukleme.gif"))
            ses_lbl.configure(text=T("active_sound", name="varsayilan"))
            onizleme_guncelle()
            # Ana modülden animasyonlu_yazi çağrılır
            import __main__ as main_mod
            if hasattr(main_mod, 'animasyonlu_yazi'):
                main_mod.animasyonlu_yazi(T("reset_done"))

    def yeni_gif_ekle():
        dosya_yolu = filedialog.askopenfilename(title=T("select_startup_gif_title"), filetypes=[(T("animated_gif_files"), "*.gif")])
        if dosya_yolu:
            dosya_adi = os.path.basename(dosya_yolu)
            hedef_konum = get_data_path(dosya_adi)
            try:
                if os.path.abspath(dosya_yolu) != os.path.abspath(hedef_konum):
                    shutil.copy2(dosya_yolu, hedef_konum)
                h = _veri_yukle()
                h["secilen_gif"] = dosya_adi
                if _veri_kaydet(h):
                    gif_lbl.configure(text=T("active_gif", name=dosya_adi))
                    onizleme_guncelle()
                    import __main__ as main_mod
                    if hasattr(main_mod, 'animasyonlu_yazi'):
                        main_mod.animasyonlu_yazi(T("new_gif_saved"))
                else:
                    import __main__ as main_mod
                    if hasattr(main_mod, 'animasyonlu_yazi'):
                        main_mod.animasyonlu_yazi(T("json_save_failed"))
            except Exception as e:
                import __main__ as main_mod
                if hasattr(main_mod, 'animasyonlu_yazi'):
                    main_mod.animasyonlu_yazi(T("gif_copy_error", error=str(e)))

    ctk.CTkButton(kontrol_frame, text=T("select_new_gif"), font=("Segoe UI", 12),
                  fg_color=aktif_palet["card"], hover_color=aktif_palet["button_hover"],
                  corner_radius=8, command=yeni_gif_ekle).pack(fill="x", pady=5)

    ctk.CTkFrame(kontrol_frame, height=2, fg_color=aktif_palet["neon"]).pack(fill="x", pady=15)

    ses_lbl = ctk.CTkLabel(kontrol_frame, text=T("active_sound", name=h_mevcut.get("secilen_ses", "varsayilan")),
                           text_color=aktif_palet["text_dim"], font=("Segoe UI", 12), anchor="w")
    ses_lbl.pack(fill="x", pady=5)

    def yeni_ses_ekle():
        dosya_yolu = filedialog.askopenfilename(title=T("select_startup_sound_title"), filetypes=[(T("sound_files"), "*.mp3 *.wav")])
        if dosya_yolu:
            dosya_adi = os.path.basename(dosya_yolu)
            hedef_konum = get_data_path(dosya_adi)
            try:
                if os.path.abspath(dosya_yolu) != os.path.abspath(hedef_konum):
                    shutil.copy2(dosya_yolu, hedef_konum)
                h = _veri_yukle()
                h["secilen_ses"] = dosya_adi
                if _veri_kaydet(h):
                    ses_lbl.configure(text=T("active_sound", name=dosya_adi))
                    import __main__ as main_mod
                    if hasattr(main_mod, 'animasyonlu_yazi'):
                        main_mod.animasyonlu_yazi(T("new_sound_saved"))
                else:
                    import __main__ as main_mod
                    if hasattr(main_mod, 'animasyonlu_yazi'):
                        main_mod.animasyonlu_yazi(T("json_save_failed"))
            except Exception as e:
                import __main__ as main_mod
                if hasattr(main_mod, 'animasyonlu_yazi'):
                    main_mod.animasyonlu_yazi(T("sound_copy_error", error=str(e)))

    ctk.CTkButton(kontrol_frame, text=T("select_new_sound"), font=("Segoe UI", 12),
                  fg_color=aktif_palet["card"], hover_color=aktif_palet["button_hover"],
                  corner_radius=8, command=yeni_ses_ekle).pack(fill="x", pady=5)

    ctk.CTkButton(kontrol_frame, text=T("factory_reset"), font=("Segoe UI Semibold", 12),
                  fg_color="#b32424", hover_color="#8c1c1c", corner_radius=8,
                  command=varsayilan_yap).pack(fill="x", side="bottom", pady=15)
