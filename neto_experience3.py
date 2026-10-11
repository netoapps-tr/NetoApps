"""Neto Experience 3.0 — arayüz dili katmanı.

Bu modül SADECE EKLEME amaçlıdır. Mevcut widget'ları yeniden oluşturmaz,
hiçbir şeyi silmez. Oluşturulmuş butonların üzerine 3.0 görsel dilini uygular:

  * Daha oval (hap/pill) butonlar
  * Sade, oyuncak gibi olmayan yüzeyler
  * Yazı yerine ikon (Segoe Fluent Icons — Windows ile gelir, dosya gerekmez)
  * İkon modunda ipucu (tooltip) — ikon tek başına anlaşılmazsa açıklama
  * Tamamen geri alınabilir: tek ayarla yazılar geri gelir
  * Kullanıcı tarafından özelleştirilebilir (JSON)

Tasarım ilkeleri
----------------
* Var olanı bozmaz: `neto_modern_ui` önce çalışır (renk/varyant kararı yazıya
  göre verilir), ikon değişimi ondan SONRA yapılır. Böylece "birincil/tehlike"
  renkleri doğru kalır.
* Geri alınabilir: orijinal yazı `_nx3_text` içinde saklanır.
* Sessiz: hiçbir fonksiyon istisna fırlatmaz; hata olursa mevcut görünüm kalır.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable

APP_FOLDER = "NetoAssistant"
CONFIG_FILE = "ui_experience3.json"

# ---------------------------------------------------------------------------
# Tasarım belirteçleri (design tokens)
# ---------------------------------------------------------------------------

# Yarıçap ölçeği. "pill" = yüksekliğin yarısı → tam hap biçimi.
RADIUS_SCALE = {
    "sharp": 4,
    "soft": 10,
    "round": 16,
    "pill": "pill",
}

SPACING = {
    "compact": {"pad_x": 10, "pad_y": 5, "font": 12, "height": 34},
    "comfortable": {"pad_x": 14, "pad_y": 7, "font": 13, "height": 40},
    "spacious": {"pad_x": 18, "pad_y": 10, "font": 14, "height": 46},
}

# Experience 3.0 için sade renk yüzeyleri (mevcut paletin üzerine ince ayar)
SURFACE = {
    "dark": {
        "button_fg": "#1B1E26",
        "button_hover": "#262A35",
        "button_border": "#2E3341",
        "button_text": "#E8ECF5",
        "accent": "#5B8CFF",
        "accent_hover": "#7AA2FF",
    },
    "light": {
        "button_fg": "#F4F6FA",
        "button_hover": "#E7ECF5",
        "button_border": "#D3DAE6",
        "button_text": "#1A2030",
        "accent": "#3F68E8",
        "accent_hover": "#5C82F4",
    },
}

DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": False,          # 3.0 kapalı başlar; kullanıcı açar
    "icon_only": True,         # yazı yerine ikon
    "button_radius": "pill",   # sharp | soft | round | pill
    "density": "comfortable",  # compact | comfortable | spacious
    "accent": "",              # boşsa palet rengi kullanılır
    "show_tooltips": True,     # ikon modunda ipucu göster
    "restyle_sidebar": True,
    "sidebar_rail": True,      # kenar çubuğu dar ikon rayı olsun mu
    "rail_button_width": 64,   # ray buton genişliği (px)
    "rail_button_height": 46,  # ray buton yüksekliği (px)
    "rail_icon_size": 26,      # ray ikon yazı boyutu (px)
    "rail_padx": 8,            # ray iç boşluğu — büyükse ikon kırpılır
    "rail_pady": 5,            # ray dikey boşluğu
    "close_hover_red": True,   # kapat düğmesi hover'ı Windows 11 kırmızısı
    "animations": True,        # mevcut animasyonları koru (kapatma seçeneği)
}

# ---------------------------------------------------------------------------
# İkon sistemi — Segoe Fluent Icons (Windows 11) / Segoe MDL2 Assets (Windows 10)
# ---------------------------------------------------------------------------

ICON_FONTS = ("Segoe Fluent Icons", "Segoe MDL2 Assets")

# Anlamsal ad -> glif. Kod noktaları görsel olarak doğrulanmıştır.
ICONS: dict[str, str] = {
    "settings": "\ue713",
    "chat": "\ue8bd",
    "globe": "\ue774",
    "web": "\ue774",
    "device": "\ue8ea",
    "phone": "\ue8ea",
    "qr": "\ued14",
    "automation": "\ue945",
    "lightning": "\ue945",
    "play": "\ue768",
    "prepare": "\ue768",
    "people": "\ue716",
    "profiles": "\ue716",
    "clock": "\ue823",
    "reminders": "\ue823",
    "calendar": "\ue787",
    "store": "\ue719",
    "shop": "\ue719",
    "star": "\ue734",
    "mic": "\ue720",
    "send": "\ue724",
    "attach": "\ue723",
    "camera": "\ue722",
    "plus": "\ue710",
    "close": "\ue8bb",
    "cancel": "\ue711",
    "wifi": "\ue701",
    "network": "\ue968",
    "shield": "\uea18",
    "folder": "\ue8b7",
    "music": "\ue8d6",
    "weather": "\ue706",
    "refresh": "\ue72c",
    "list": "\ue8fd",
    "check": "\ue73e",
    "search": "\ue721",
    "home": "\ue80f",
    "delete": "\ue74d",
    "save": "\ue74e",
    "info": "\ue946",
    "warning": "\ue7ba",
    "bulb": "\uea80",
    "ai": "\uea80",
    "power": "\ue7e8",
    "volume": "\ue767",
    "monitor": "\ue7f4",
    "laptop": "\ue7f8",
    "emoji": "\ue76e",
    "download": "\ue896",
    "eye": "\ue7b3",
    "language": "\ue774",
    "lock": "\ue72e",
    "unlock": "\ue785",
    "user": "\ue77b",
    "arrow_right": "\ue72a",
    "arrow_left": "\ue72b",
    "wand": "\uec4a",
    "robot": "\ue99a",
    "chart": "\ue9d2",    "filter": "\ue71c",
    "link": "\ue71b",
    "edit": "\ue70f",
    "pin": "\ue718",
    "sync": "\ue895",
    "cloud": "\ue753",
    "keyboard": "\ue765",
    "grid": "\ue80a",
    "moon": "\ue708",
    "sun": "\ue706",
    # --- Başlık çubuğu (Windows 11 ile aynı glifler) ---
    "minimize": "\ue921",
    "maximize": "\ue922",
    "restore": "\ue923",
    "menu": "\ue700",
    "more": "\ue712",
}

# İkon moduna ÇEVRİLMEYECEK butonlar: durum göstergeleri, sayaçlar, uzun
# açıklama satırları. Bunlar yazı olarak kalır (ikon tek başına anlamsız olur).
SKIP_ICON_TEXT = (
    "durumu",
    "status",
    "yükleniyor",
    "yukleniyor",
    "hazırlanıyor",
    "hazirlaniyor",
    "indiriliyor",
    "yükleniyor…",
)

# Buton yazısındaki anahtar kelime -> ikon adı.
# Sıra önemlidir: ilk eşleşen kazanır (özel olanlar üstte).
TEXT_TO_ICON: tuple[tuple[tuple[str, ...], str], ...] = (
    # --- En özel kurallar önce gelir; ilk eşleşen kazanır. ---
    (("qr", "kare kod", "eşleştir", "eslestir"), "qr"),
    (("cihaz bağla", "cihaz bagla", "android", "telefon", "device"), "device"),
    # "Ağ tarayıcı", "tarayıcı" (browser) kuralından ÖNCE gelmeli.
    (("ağ tara", "ag tara", "ağ tarayıcı", "ag tarayici", "ağ paneli", "ag paneli",
      "network", "lan tara", "lan tarayıcı"), "network"),
    (("otomasyon", "automation"), "automation"),
    (("hazırla", "hazirla", "sahne", "scene", "prepare"), "prepare"),
    (("profil", "profile", "kişi", "kisi"), "profiles"),
    (("hatırlat", "hatirlat", "remind", "alarm"), "clock"),
    (("mağaza", "magaza", "store", "shop", "eklenti"), "store"),
    (("takvim", "calendar"), "calendar"),
    # "Yenile", "yeni" (plus) kuralından ÖNCE gelmeli.
    (("yenile", "refresh", "güncelle", "guncelle", "eşitle", "esitle", "sync"), "refresh"),
    (("sil", "delete", "kaldır", "kaldir"), "delete"),
    (("kapat", "close", "iptal", "cancel"), "close"),
    (("kaydet", "save"), "save"),
    (("gönder", "gonder", "send"), "send"),
    (("ekle", "yeni ekle", "yeni kayıt", "add", "artı", "arti"), "plus"),
    (("ara", "search", "bul"), "search"),
    (("web sohbet", "web chat", "tarayıcı", "tarayici", "browser", "internet"), "globe"),
    (("ayar", "setting", "config"), "settings"),
    (("neto ai", "yapay zeka", "asistan", "assistant"), "ai"),
    (("sohbet", "chat", "mesaj", "message"), "chat"),
    (("liste", "list"), "list"),
    (("müzik", "muzik", "music"), "music"),
    (("hava", "weather"), "weather"),
    (("güvenlik", "guvenlik", "security", "kalkan"), "shield"),
    (("klasör", "klasor", "folder", "dosya"), "folder"),
    (("bilgi", "info", "hakkında", "hakkinda"), "info"),
    (("uyarı", "uyari", "warning", "dikkat"), "warning"),
    (("kilit", "lock"), "lock"),
    (("kullanıcı", "kullanici", "user", "hesap"), "user"),
    (("güç", "guc", "power"), "power"),
    (("ses", "volume", "sessiz"), "volume"),
    (("ekran", "monitor", "screen"), "monitor"),
    (("indir", "download"), "download"),
    (("görünüm", "gorunum", "view", "önizleme", "onizleme"), "eye"),
    (("dil", "language", "türkçe", "turkce"), "language"),
    (("yıldız", "yildiz", "favori", "star"), "star"),
    (("şifre", "sifre", "parola", "password"), "lock"),
    (("not", "note", "defter"), "edit"),
)

_FONT_FAMILY: str | None = None


def icon_font_family() -> str:
    """Kullanılabilir ikon fontunun ailesini döndürür (yoksa boş).

    Tk font listesi için bir kök pencere gerekir. Uygulama başlarken kök
    henüz hazır değilse geçici bir gizli kök oluşturulur; böylece font
    tespiti her koşulda çalışır.
    """
    global _FONT_FAMILY
    if _FONT_FAMILY is not None:
        return _FONT_FAMILY
    try:
        from tkinter import font as tkfont
        import tkinter as tk

        temporary = None
        root = getattr(tk, "_default_root", None)
        if root is None:
            try:
                temporary = tk.Tk()
                temporary.withdraw()
            except Exception:
                temporary = None
        try:
            available = {str(name) for name in tkfont.families()}
        finally:
            if temporary is not None:
                try:
                    temporary.destroy()
                except Exception:
                    pass
    except Exception:
        available = set()
    for candidate in ICON_FONTS:
        if candidate in available:
            _FONT_FAMILY = candidate
            return _FONT_FAMILY
    _FONT_FAMILY = ""
    return _FONT_FAMILY


def has_icon_font() -> bool:
    return bool(icon_font_family())


def glyph(name: str) -> str:
    return ICONS.get(str(name or "").lower(), "")


# --- Glif → görüntü (geniş sidebar için ikon + yazı) -----------------------
# Bir CTkButton tek font kullanır; ikon glifi ile normal yazıyı aynı metinde
# birleştirmek yazıyı bozar. Bu yüzden geniş modda ikon, Segoe Fluent
# glifinden PIL ile çizilip CTkImage olarak verilir (compound="left").

_ICON_FONT_FILES = {
    "Segoe Fluent Icons": "SegoeIcons.ttf",
    "Segoe MDL2 Assets": "segmdl2.ttf",
}
_GLYPH_IMAGE_CACHE: dict[tuple[str, int, str], Any] = {}
_LEADING_SYMBOL_RE = re.compile(r"^[^\w]+", re.UNICODE)


def icon_font_path() -> str:
    """İkon fontunun .ttf dosya yolunu döndürür (yoksa boş)."""
    name = _ICON_FONT_FILES.get(icon_font_family())
    if not name:
        return ""
    path = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", name)
    return path if os.path.isfile(path) else ""


def glyph_image(name: str, size: int = 18, color: str = "#E8ECF5") -> Any:
    """Anlamsal ikon adını (veya doğrudan glifi) CTkImage olarak döndürür."""
    raw = str(name or "")
    symbol = raw if (len(raw) == 1 and ord(raw[0]) >= 0xE000) else glyph(raw)
    if not symbol:
        return None
    key = (symbol, int(size), str(color))
    cached = _GLYPH_IMAGE_CACHE.get(key)
    if cached is not None:
        return cached
    path = icon_font_path()
    if not path:
        return None
    try:
        from PIL import Image, ImageDraw, ImageFont
        import customtkinter as ctk

        scale = 8
        canvas = max(32, int(size) * scale)
        image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype(path, int(canvas * 0.72))
        draw.text((canvas // 2, canvas // 2), symbol, font=font, fill=color, anchor="mm")
        image = image.resize((int(size), int(size)), Image.Resampling.LANCZOS)
        result = ctk.CTkImage(light_image=image, dark_image=image, size=(int(size), int(size)))
        _GLYPH_IMAGE_CACHE[key] = result
        return result
    except Exception:
        return None


def clean_label(text: str) -> str:
    """Etiketin başındaki emoji/sembolleri temizler.

    İkon artık görsel olarak geldiği için metindeki emoji tekrarına gerek
    yoktur; ayrıca emoji ile ikon yan yana çirkin durur.
    """
    original = str(text or "").strip()
    cleaned = _LEADING_SYMBOL_RE.sub("", original).strip()
    return cleaned or original


def icon_for_text(text: str, fallback: str = "grid") -> str:
    """Buton yazısından uygun ikonu seçer."""
    lowered = str(text or "").casefold()
    for keywords, name in TEXT_TO_ICON:
        for keyword in keywords:
            if keyword in lowered:
                return glyph(name)
    return glyph(fallback)


# ---------------------------------------------------------------------------
# Metin sembollerini gerçek ikonlara çevirme (başlık çubuğu + panel kapatma)
# ---------------------------------------------------------------------------
# Uygulama başlık çubuğunda ve panellerde ikon yerine METİN SEMBOLÜ kullanıyor:
# "—" "□" "❐" "×" "✕" "⚡" "☰". Bunlar ikon fontuyla çizilmediği için
# düzensiz ve soluk görünür. 3.0 bunları Windows 11 ile aynı Segoe Fluent
# gliflerine çevirir.
SYMBOL_ICONS: dict[str, str] = {
    "—": "minimize",
    "–": "minimize",
    "−": "minimize",
    "-": "minimize",
    "□": "maximize",
    "▢": "maximize",
    "❐": "restore",
    "🗗": "restore",
    "×": "close",
    "✕": "close",
    "✖": "close",
    "╳": "close",
    "⚡": "lightning",
    "☰": "menu",
    "⋯": "more",
    "•••": "more",
}


def apply_symbol_icon(button: Any) -> bool:
    """Tek bir butondaki metin sembolünü gerçek ikona çevirir.

    Renklere DOKUNMAZ: başlık çubuğu renklerini uygulamanın kendi hover
    animasyon sistemi yönetir; burada yalnızca glif, font, yarıçap ve
    çirkin çerçeve düzeltilir.
    """
    if not is_enabled() or button is None:
        return False
    family = icon_font_family()
    if not family:
        return False
    try:
        text = str(getattr(button, "_nx3_sym", None) or _original_text(button)).strip()
        key = SYMBOL_ICONS.get(text)
        if not key:
            return False
        symbol = glyph(key)
        if not symbol:
            return False
        try:
            height = int(button.cget("height"))
        except Exception:
            height = 36
        button._nx3_sym = text
        button._nx3_text = text
        button.configure(
            text=symbol,
            font=(family, max(12, min(30, int(height * 0.46)))),
            corner_radius=max(8, height // 2),
            border_width=0,
        )
        button._nx3_symbolized = True
        return True
    except Exception:
        return False


def renew_all_icons(root: Any) -> int:
    """Ağaçtaki tüm metin sembolü butonlarını gerçek ikona çevirir.

    Başlık çubuğu (küçült/büyüt/geri yükle/kapat/hızlı işlem) ve panel
    kapatma düğmeleri bu kapsamdadır. Kaç butonun değiştiğini döndürür.
    """
    if not is_enabled():
        return 0
    changed = 0
    for button in _buttons(root):
        try:
            if _is_reserved(button):
                continue
            if apply_symbol_icon(button):
                changed += 1
        except Exception:
            continue
    return changed


# ---------------------------------------------------------------------------
# Sidebar (kenar çubuğu) entegrasyonu
# ---------------------------------------------------------------------------
# Uygulamanın kendi kompakt (ray) modunda kısaltma gösterilir: AUTO, NET, SHOP…
# Experience 3.0 bu kısaltmalar yerine gerçek Segoe Fluent ikonlarını koyar.
# Anahtar = uygulamadaki widget adı, değer = ICONS içindeki anlamsal ad.

SIDEBAR_ICONS: dict[str, str] = {
    "btn_now_playing_ayar": "settings",
    "btn_now_playing_baslat": "music",
    "btn_netoai": "ai",
    "btn_android_device": "device",
    "btn_automation": "automation",
    "btn_scenes": "play",
    "btn_profiles": "profiles",
    "btn_reminders": "clock",
    "btn_anahtar": "store",
    "btn_store_panel": "store",
    "btn_network_scan": "network",
    "settings_profile_name": "settings",
}

_ENABLED_CACHE: bool | None = None


def is_enabled(refresh: bool = False) -> bool:
    """3.0 açık mı? Sonuç süreç başına önbelleğe alınır (yeniden başlatma gerekir)."""
    global _ENABLED_CACHE
    if _ENABLED_CACHE is None or refresh:
        try:
            _ENABLED_CACHE = bool(load_config().get("enabled"))
        except Exception:
            _ENABLED_CACHE = False
    return bool(_ENABLED_CACHE)


def reset_enabled_cache() -> None:
    global _ENABLED_CACHE
    _ENABLED_CACHE = None


def _is_glyph_text(text: str) -> bool:
    """Metin tek bir ikon glifi mi? (Segoe Fluent özel kullanım alanı)"""
    text = str(text or "")
    return len(text) == 1 and ord(text[0]) >= 0xE000


def sidebar_glyph(name: str, label: str = "") -> str:
    """Sidebar widget adı için ikon glifini döndürür (3.0 kapalıysa boş).

    ``label``: butonun gerçek yazısı. Durum bildiren butonlarda (ör. eklenti
    durumu) ikon bu yazıya göre seçilir; böylece "KAPALI" iken uyarı,
    "AÇIK" iken onay ikonu gösterilir.
    """
    if not is_enabled():
        return ""
    key = str(name or "")
    # Durum butonu: sabit ikon yanıltıcı olur, metne göre karar verilir.
    if key == "btn_anahtar":
        low = str(label or "").casefold()
        if not low or _is_glyph_text(label):
            return ""
        if "kapal" in low or "off" in low:
            return glyph("warning")
        return glyph("check")
    mapped = SIDEBAR_ICONS.get(key)
    return glyph(mapped) if mapped else ""


# Ray moduna alınmış sidebar butonlarının kaydı. Uygulamanın yerleşim
# fonksiyonları bu butonların yüksekliğini sonradan küçültebildiği için,
# açılış tamamlandıktan sonra ölçüler bu kayıt üzerinden tazelenir.
_RAIL_WIDGETS: list[Any] = []


def _register_rail_widget(widget: Any) -> None:
    try:
        for existing in _RAIL_WIDGETS:
            if existing is widget:
                return
        _RAIL_WIDGETS.append(widget)
    except Exception:
        pass


def refresh_rail_metrics() -> int:
    """Kayıtlı ray butonlarının ölçü ve fontunu yeniden uygular.

    Yerleşim animasyonları buton yüksekliğini küçültürse glifler kırpılır;
    bu fonksiyon ölçüleri tutarlı hâle getirir. 3.0 veya ray kapalıysa
    hiçbir şey yapmaz.
    """
    try:
        metrics = rail_button_metrics()
    except Exception:
        return 0
    if not metrics:
        return 0
    family = icon_font_family() or "Segoe UI Semibold"
    fixed = 0
    for widget in list(_RAIL_WIDGETS):
        try:
            widget.configure(
                height=int(metrics["height"]),
                corner_radius=int(metrics["radius"]),
                border_width=0,
                font=(family, int(metrics["font_size"])),
            )
            fixed += 1
        except Exception:
            continue
    return fixed


def apply_sidebar_widget(widget: Any, name: str, compact: bool, size: int | None = None) -> bool:
    """Kompakt sidebar butonuna gerçek ikon yerleştirir.

    ``True`` dönerse yazı zaten ayarlanmıştır; çağıran taraf varsayılan
    kısaltmayı yazmamalıdır. ``False`` dönerse hiçbir şey değişmemiştir ve
    çağıran taraf eski davranışı aynen uygular.

    ``size`` verilmezse ray ölçülerinden (`rail_icon_size`) okunur.
    """
    if not compact or widget is None:
        return False
    # Durum butonları için gerçek yazıyı hatırla (glif yazıldıktan sonra da
    # doğru karar verebilmek için).
    try:
        raw_text = str(widget.cget("text") or "").strip()
    except Exception:
        raw_text = ""
    if raw_text and not _is_glyph_text(raw_text):
        widget._nx3_state_label = raw_text
    state_label = str(getattr(widget, "_nx3_state_label", "") or raw_text)

    symbol = sidebar_glyph(name, state_label)
    if not symbol:
        return False
    family = icon_font_family()
    if not family:
        return False
    if size is None:
        try:
            metrics = rail_button_metrics()
            size = int(metrics["font_size"]) if metrics else 19
        except Exception:
            metrics = None
            size = 19
    else:
        try:
            metrics = rail_button_metrics()
        except Exception:
            metrics = None

    # ÖNEMLİ: font ve yükseklik BİRLİKTE ayarlanır. Bu fonksiyon sidebar
    # metinlerini yenileyen son adımdır; yalnızca fontu büyütüp yüksekliği
    # uygulamanın küçük varsayılanına (36 px) bırakırsak glifler dikeyde
    # kırpılır. Bu yüzden ölçüler her seferinde tutarlı biçimde yazılır.
    try:
        if metrics:
            widget.configure(
                text=symbol,
                font=(family, int(size)),
                height=int(metrics["height"]),
                corner_radius=int(metrics["radius"]),
                border_width=0,
            )
        else:
            widget.configure(text=symbol, font=(family, int(size)))
        _register_rail_widget(widget)
        return True
    except Exception:
        return False


def sidebar_widget_names() -> set[str]:
    """Uygulamada sidebar'a ait widget adlarını döndürür."""
    return set(SIDEBAR_ICONS.keys())


def rail_sidebar_enabled() -> bool:
    """Kenar çubuğu dar ikon rayı olarak başlasın mı?"""
    try:
        if not is_enabled():
            return False
        return bool(load_config().get("sidebar_rail", True))
    except Exception:
        return False


def rail_button_metrics() -> dict[str, Any] | None:
    """Ray butonlarının ölçüleri.

    3.0 kapalıysa veya ray modu kapalıysa ``None`` döner; çağıran taraf
    uygulamanın kendi (küçük) varsayılanlarını aynen kullanır.
    """
    try:
        if not (is_enabled() and rail_sidebar_enabled()):
            return None
        config = load_config()
        height = int(config.get("rail_button_height", 46) or 46)
        height = max(36, min(76, height))
        size = int(config.get("rail_icon_size", 26) or 26)
        size = max(14, min(44, size))
        return {
            "width": int(config.get("rail_button_width", 64) or 64),
            "height": height,
            "radius": max(12, height // 2),
            "font_family": icon_font_family() or "Segoe UI Semibold",
            "font_size": size,
            # KRİTİK: ray genişliği 104 px ve kaydırma çubuğu ~16 px alıyor.
            # Uygulamanın varsayılan padx=22'si ile butona yalnızca ~44 px
            # kalıyor; 26 pt glif sığmayıp kırpılıyor. Bu yüzden 3.0 modunda
            # iç boşluk küçültülür.
            "padx": int(config.get("rail_padx", 8) or 8),
            "pady": int(config.get("rail_pady", 5) or 5),
        }
    except Exception:
        return None


def attach_tooltip(widget: Any, text: str) -> bool:
    """Bir widget'a 3.0 ipucu balonu ekler (3.0 kapalıysa hiçbir şey yapmaz).

    Özel tasarımlı (``_neto_modern_skip``) butonlar genel stil geçişinden
    muaftır; onlara 3.0 katkısı bu fonksiyonla, bilinçli ve hedefli olarak
    eklenir.
    """
    try:
        if not is_enabled() or widget is None:
            return False
        config = load_config()
        if not bool(config.get("show_tooltips", True)):
            return False
        if getattr(widget, "_nx3_tooltip", None) is not None:
            return False
        widget._nx3_tooltip = Tooltip(widget, str(text or ""))
        return True
    except Exception:
        return False


def accent_color() -> str:
    """3.0 vurgu rengini döndürür."""
    try:
        return surface_colors(load_config())["accent"]
    except Exception:
        return "#5B8CFF"


def accent_hover_color() -> str:
    try:
        return surface_colors(load_config())["accent_hover"]
    except Exception:
        return "#7AA2FF"


# Windows 11 kapat düğmesi hover rengi ve üzerindeki metin rengi.
CLOSE_HOVER_BG = "#E81123"
CLOSE_HOVER_TEXT = "#FFFFFF"


def close_hover_colors() -> tuple[str, str] | None:
    """Kapat düğmesi için (zemin, metin) hover rengi. 3.0 kapalıysa None."""
    if not is_enabled():
        return None
    try:
        if not bool(load_config().get("close_hover_red", True)):
            return None
    except Exception:
        pass
    return CLOSE_HOVER_BG, CLOSE_HOVER_TEXT


def apply_capsule_accents() -> int:
    """Mesaj kapsülü butonlarına 3.0 vurgusunu uygular.

    Bu butonlar `_neto_modern_skip` ile genel stil geçişinden muaftır ve
    renkleri uygulama açılışında paletten yeniden yazılır. Bu yüzden vurgu
    açılış TAMAMLANDIKTAN sonra, bu fonksiyonla tekrar uygulanır.
    Uygulama `_neto_capsule_buttons` sözlüğünü yayınlamıyorsa hiçbir şey
    yapılmaz.
    """
    if not is_enabled():
        return 0
    applied = 0
    try:
        main = sys.modules.get("__main__")
        capsule = getattr(main, "_neto_capsule_buttons", None)
        if not isinstance(capsule, dict):
            return 0
        send = capsule.get("send")
        if send is not None:
            send.configure(fg_color=accent_color(), hover_color=accent_hover_color())
            send._nx3_surface = True
            applied += 1
    except Exception:
        return applied
    return applied


# ---------------------------------------------------------------------------
# Yapılandırma
# ---------------------------------------------------------------------------

def _config_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / APP_FOLDER / CONFIG_FILE


def load_config() -> dict[str, Any]:
    """3.0 ayarlarını okur. Bozuk/eksikse varsayılana düşer (asla hata vermez)."""
    config = dict(DEFAULT_CONFIG)
    try:
        raw = _config_path().read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict):
            for key, value in data.items():
                if key in DEFAULT_CONFIG:
                    config[key] = value
    except Exception:
        pass
    return config


def save_config(config: dict[str, Any]) -> bool:
    """Ayarları diske yazar; başarı durumunu döndürür."""
    merged = dict(DEFAULT_CONFIG)
    if isinstance(config, dict):
        merged.update({k: v for k, v in config.items() if k in DEFAULT_CONFIG})
    try:
        path = _config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, path)
        return True
    except Exception:
        return False


def resolve_radius(radius: Any, height: int | float) -> int:
    """Yarıçap değerini piksele çevirir. 'pill' → yüksekliğin yarısı."""
    if isinstance(radius, str):
        if radius.lower() == "pill":
            return max(6, int(float(height) / 2))
        return int(RADIUS_SCALE.get(radius.lower(), 12))
    try:
        return max(0, int(radius))
    except Exception:
        return 12


def _is_dark() -> bool:
    try:
        import customtkinter as ctk

        return str(ctk.get_appearance_mode()).lower() == "dark"
    except Exception:
        return True


def surface_colors(config: dict[str, Any] | None = None) -> dict[str, str]:
    """3.0 yüzey renklerini döndürür (vurgu rengi özelleştirilebilir)."""
    colors = dict(SURFACE["dark" if _is_dark() else "light"])
    accent = str((config or {}).get("accent") or "").strip()
    if accent.startswith("#") and len(accent) in (4, 7):
        colors["accent"] = accent
    return colors


# ---------------------------------------------------------------------------
# İpucu (tooltip) — ikon modunda açıklama
# ---------------------------------------------------------------------------

class Tooltip:
    """Basit, kesilebilir ipucu balonu. Hata durumunda sessizce devre dışı kalır."""

    def __init__(self, widget: Any, text: str, delay: int = 450) -> None:
        self.widget = widget
        self.text = str(text or "")
        self.delay = int(delay)
        self._after_id: str | None = None
        self._window: Any = None
        if not self.text:
            return
        for sequence, handler in (
            ("<Enter>", self._schedule),
            ("<Leave>", self._hide),
            ("<ButtonPress>", self._hide),
        ):
            try:
                widget.bind(sequence, handler, add="+")
            except Exception:
                pass

    def _schedule(self, _event: Any = None) -> None:
        self._cancel()
        try:
            self._after_id = self.widget.after(self.delay, self._show)
        except Exception:
            self._after_id = None

    def _cancel(self) -> None:
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self) -> None:
        if self._window is not None or not self.text:
            return
        try:
            import tkinter as tk

            x = self.widget.winfo_rootx() + int(self.widget.winfo_width() / 2)
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
            window = tk.Toplevel(self.widget)
            window.wm_overrideredirect(True)
            window.wm_geometry(f"+{x}+{y}")
            window.attributes("-topmost", True)
            label = tk.Label(
                window,
                text=self.text,
                background="#111318",
                foreground="#E8ECF5",
                relief="solid",
                borderwidth=0,
                font=("Segoe UI", 9),
                padx=8,
                pady=4,
            )
            label.pack()
            self._window = window
        except Exception:
            self._window = None

    def _hide(self, _event: Any = None) -> None:
        self._cancel()
        window = self._window
        self._window = None
        if window is not None:
            try:
                window.destroy()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Widget ağacı yardımcıları
# ---------------------------------------------------------------------------

def walk(parent: Any) -> Iterable[Any]:
    """Ebeveynin altındaki tüm widget'ları gezer (güvenli)."""
    try:
        children = list(parent.winfo_children())
    except Exception:
        return
    for child in children:
        yield child
        yield from walk(child)


def _buttons(root: Any) -> list[Any]:
    try:
        import customtkinter as ctk

        return [w for w in walk(root) if isinstance(w, ctk.CTkButton)]
    except Exception:
        return []


def _original_text(button: Any) -> str:
    """Butonun orijinal (ikon değişiminden önceki) yazısını döndürür."""
    stored = getattr(button, "_nx3_text", None)
    if stored is not None:
        return str(stored)
    try:
        return str(button.cget("text") or "")
    except Exception:
        return ""


def _is_reserved(button: Any) -> bool:
    """Uygulamanın kendi özel tasarımlı butonlarını tespit eder.

    `asistan beta.py` mesaj kapsülü butonlarını (artı, dalga, gönder, AI)
    `_neto_modern_skip = True` ile işaretler ve "genel menü buton katmanı
    bunların dairesel yüzünü ezmemeli" der. Experience 3.0 bu karara saygı
    duyar; aksi hâlde ikonların etrafında istenmeyen kutular oluşur.
    Bu butonlar için 3.0, aşağıdaki `attach_tooltip` ve kapsül süslemesi
    ile ayrı ve bilinçli biçimde uygulanır.
    """
    return bool(getattr(button, "_neto_modern_skip", False))


# ---------------------------------------------------------------------------
# Uygulama
# ---------------------------------------------------------------------------

def round_buttons(
    root: Any,
    radius: Any = "pill",
    density: str = "comfortable",
) -> int:
    """Tüm butonları daha oval hale getirir. Değişen buton sayısını döndürür."""
    metrics = SPACING.get(str(density), SPACING["comfortable"])
    changed = 0
    for button in _buttons(root):
        try:
            if _is_reserved(button):
                continue
            height = metrics["height"]
            try:
                current = button.cget("height")
                if isinstance(current, (int, float)) and current > 0:
                    height = int(current)
            except Exception:
                pass
            value = resolve_radius(radius, height)
            button.configure(corner_radius=value)
            button._nx3_radius = value
            changed += 1
        except Exception:
            continue
    return changed


def apply_icon_mode(
    root: Any,
    show_tooltips: bool = True,
    font_delta: int = 3,
    skip_names: set[str] | None = None,
) -> int:
    """Buton yazılarını ikonla değiştirir; orijinal yazı saklanır.

    Yazı `_nx3_text` içinde tutulur, böylece `restore_text()` ile geri
    alınabilir. İpucu metni de orijinal yazıdan üretilir.

    `skip_names`: uygulamanın kendi yönettiği sidebar widget adları. Bunlar
    atlanır; çünkü onların ikonunu uygulamanın kendi yazı fonksiyonu
    (`_sidebar_text_yaz` → `apply_sidebar_widget`) yönetir.
    """
    family = icon_font_family()
    if not family:
        return 0

    skip_ids: set[int] = set()
    if skip_names:
        try:
            main = sys.modules.get("__main__")
            for name in skip_names:
                widget = getattr(main, name, None)
                if widget is not None:
                    skip_ids.add(id(widget))
        except Exception:
            skip_ids = set()

    changed = 0
    for button in _buttons(root):
        try:
            if getattr(button, "_nx3_iconized", False):
                continue
            if _is_reserved(button):
                continue
            if getattr(button, "_nx3_symbolized", False):
                # Başlık çubuğu / kapatma sembolü — kendi dönüşümü uygulandı.
                continue
            if skip_ids and id(button) in skip_ids:
                continue
            text = _original_text(button)
            if not text.strip():
                continue
            lowered = text.casefold()
            if any(skip in lowered for skip in SKIP_ICON_TEXT):
                # Durum/sayaç butonları yazı olarak kalır.
                continue
            symbol = icon_for_text(text)
            if not symbol:
                continue
            button._nx3_text = text
            size = 16
            try:
                current_font = button.cget("font")
                if isinstance(current_font, (tuple, list)) and len(current_font) >= 2:
                    size = int(current_font[1]) + int(font_delta)
            except Exception:
                size = 16
            button.configure(text=symbol, font=(family, max(12, size)))
            button._nx3_iconized = True
            if show_tooltips:
                Tooltip(button, text)
            changed += 1
        except Exception:
            continue
    return changed


def restore_text(root: Any) -> int:
    """İkon modunu geri alır: orijinal yazıları yerine koyar."""
    restored = 0
    for button in _buttons(root):
        try:
            if not getattr(button, "_nx3_iconized", False):
                continue
            text = getattr(button, "_nx3_text", None)
            if text is None:
                continue
            button.configure(text=str(text))
            button._nx3_iconized = False
            restored += 1
        except Exception:
            continue
    return restored


def style_surfaces(
    root: Any,
    config: dict[str, Any] | None = None,
    only_untouched: bool = True,
) -> int:
    """Buton yüzeylerini 3.0 diline çeker (sade, düşük kontrastlı).

    `only_untouched=True` iken yalnızca kendi işaretlediğimiz butonlara
    dokunur; böylece uygulamanın özel renkli butonları (örn. durum
    göstergeleri) korunur.
    """
    colors = surface_colors(config)
    changed = 0
    for button in _buttons(root):
        try:
            if _is_reserved(button):
                continue
            variant = str(getattr(button, "_neto_modern_variant", "") or "")
            if variant in {"primary", "danger"}:
                # Vurgu ve tehlike renkleri korunur; yalnızca yarıçap zaten ayarlandı.
                continue
            button.configure(
                fg_color=colors["button_fg"],
                hover_color=colors["button_hover"],
                border_color=colors["button_border"],
                text_color=colors["button_text"],
            )
            button._nx3_surface = True
            changed += 1
        except Exception:
            continue
    return changed


def apply(
    root: Any,
    config: dict[str, Any] | None = None,
    palette: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Experience 3.0'ı uygular. Asla istisna fırlatmaz.

    Sıra önemlidir: önce `neto_modern_ui` (yazıya göre varyant kararı),
    sonra ovalleştirme, sonra yüzey, en son ikon değişimi.
    """
    result = {
        "ok": False,
        "rounded": 0,
        "styled": 0,
        "iconized": 0,
        "icon_font": "",
        "enabled": False,
        "error": "",
    }
    try:
        config = dict(config or load_config())
        result["enabled"] = bool(config.get("enabled"))
        if not result["enabled"]:
            return result

        # 1) Renk/varyant katmanı — yazı hâlâ yerindeyken çalışmalı.
        try:
            from neto_modern_ui import apply_tree

            apply_tree(root, palette=palette)
        except Exception:
            pass

        # 2) Yüzeyler
        if config.get("restyle_sidebar", True):
            result["styled"] = style_surfaces(root, config)

        # 3) Ovalleştirme
        result["rounded"] = round_buttons(
            root,
            radius=config.get("button_radius", "pill"),
            density=config.get("density", "comfortable"),
        )

        # 4) İkon modu
        family = icon_font_family()
        result["icon_font"] = family
        if config.get("icon_only") and family:
            result["iconized"] = apply_icon_mode(
                root,
                show_tooltips=bool(config.get("show_tooltips", True)),
                skip_names=sidebar_widget_names(),
            )
        elif not config.get("icon_only"):
            restore_text(root)

        result["ok"] = True
        # Başlık çubuğu ve panel kapatma düğmelerindeki metin sembollerini
        # gerçek ikonlara çevir (küçült / büyüt / geri yükle / kapat / hızlı).
        try:
            result["symbols"] = renew_all_icons(root)
        except Exception:
            result["symbols"] = 0
        # Ray butonlarının ölçülerini tazele (yerleşim animasyonları
        # yüksekliği küçültmüş olabilir; aksi hâlde glifler kırpılır).
        try:
            result["rail_fixed"] = refresh_rail_metrics()
        except Exception:
            result["rail_fixed"] = 0
        return result
    except Exception as exc:
        result["error"] = str(exc)
        return result


def refresh(root: Any, config: dict[str, Any] | None = None, palette: dict[str, Any] | None = None) -> dict[str, Any]:
    """Ayar değişikliğinden sonra yeniden uygular (ikon modunu sıfırlayarak)."""
    try:
        restore_text(root)
        for button in _buttons(root):
            for attribute in ("_nx3_iconized", "_nx3_surface"):
                if hasattr(button, attribute):
                    delattr(button, attribute)
    except Exception:
        pass
    return apply(root, config=config, palette=palette)


# ---------------------------------------------------------------------------
# Canlı önizleme penceresi
# ---------------------------------------------------------------------------

# Uygulamanın gerçek sidebar yazıları — önizleme birebir bunları gösterir.
PREVIEW_ITEMS: tuple[tuple[str, str], ...] = (
    ("Web Sohbeti", "web sohbeti"),
    ("Cihaz Bağla / QR", "cihaz bağla"),
    ("Otomasyon Merkezi", "otomasyon"),
    ("Neto Hazırla", "hazırla"),
    ("Profiller", "profiller"),
    ("Hatırlatıcılar", "hatırlatıcılar"),
    ("Ağ Tarayıcı", "ağ tarayıcı"),
    ("Eklenti Mağazası", "mağaza"),
    ("Ayarlar", "ayarlar"),
)

ACCENT_PRESETS = ("#5B8CFF", "#22C55E", "#F59E0B", "#EC4899", "#8B5CF6", "#06B6D4")

_preview_ref: Any = None


def preview_window(parent: Any = None, palette: dict[str, Any] | None = None, standalone: bool = False):
    """Experience 3.0 canlı önizlemesi.

    `parent` verilmezse kendi penceresini kurar. `standalone=True` iken
    mainloop'u da çalıştırır (bağımsız demo).
    """
    global _preview_ref
    import customtkinter as ctk

    colors = dict(palette or {})
    background = colors.get("bg", "#0F1116")
    card = colors.get("card", "#171A21")

    owns_root = parent is None
    if owns_root:
        ctk.set_appearance_mode("dark")
        window = ctk.CTk()
    else:
        window = ctk.CTkToplevel(parent)

    _preview_ref = window
    window.title("Neto Experience 3.0 — Önizleme")
    window.geometry("980x680")
    window.configure(fg_color=background)
    try:
        window.transient(parent) if parent is not None else None
    except Exception:
        pass

    state = dict(load_config())
    state["enabled"] = True

    header = ctk.CTkFrame(window, fg_color="transparent")
    header.pack(fill="x", padx=24, pady=(20, 6))
    ctk.CTkLabel(
        header,
        text="Neto Experience 3.0",
        font=("Segoe UI Semibold", 26),
        text_color="#FFFFFF",
    ).pack(anchor="w")
    ctk.CTkLabel(
        header,
        text="Oval butonlar · ikon öncelikli · sade yüzeyler · tamamen özelleştirilebilir",
        font=("Segoe UI", 12),
        text_color="#9BA4B5",
    ).pack(anchor="w")

    body = ctk.CTkFrame(window, fg_color="transparent")
    body.pack(fill="both", expand=True, padx=24, pady=(10, 0))

    # --- Sol: ikon rayı (rail) ---
    rail = ctk.CTkFrame(body, fg_color=card, corner_radius=20, width=76)
    rail.pack(side="left", fill="y", padx=(0, 14))
    rail.pack_propagate(False)
    rail_buttons: list[Any] = []
    for label, _key in PREVIEW_ITEMS:
        button = ctk.CTkButton(
            rail,
            text=label,
            width=44,
            height=44,
            corner_radius=22,
            fg_color="#1B1E26",
            hover_color="#262A35",
            text_color="#E8ECF5",
            font=("Segoe UI Semibold", 13),
        )
        button.pack(pady=3)
        rail_buttons.append(button)

    # --- Orta: karşılaştırma ---
    centre = ctk.CTkFrame(body, fg_color="transparent")
    centre.pack(side="left", fill="both", expand=True)

    def section(title: str, subtitle: str) -> Any:
        box = ctk.CTkFrame(centre, fg_color=card, corner_radius=18)
        box.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(box, text=title, font=("Segoe UI Semibold", 15),
                     text_color="#FFFFFF").pack(anchor="w", padx=16, pady=(12, 0))
        ctk.CTkLabel(box, text=subtitle, font=("Segoe UI", 11),
                     text_color="#8B94A7").pack(anchor="w", padx=16, pady=(0, 8))
        row = ctk.CTkFrame(box, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 14))
        return row

    old_row = section("Experience 2.0", "Mevcut görünüm — köşe yarıçapı 8, yazı etiketli")
    old_buttons: list[Any] = []
    for label in ("Otomasyon Merkezi", "Profiller", "Ayarlar"):
        button = ctk.CTkButton(
            old_row, text=label, corner_radius=8, height=34,
            fg_color="#202633", hover_color="#2B3548",
            text_color="#F3F6FF", font=("Segoe UI Semibold", 12),
        )
        button.pack(side="left", padx=(0, 8))
        old_buttons.append(button)

    new_row = section("Experience 3.0", "Hap biçimi köşeler, ikon öncelikli, düşük kontrast")
    new_buttons: list[tuple[Any, str]] = []
    for label in ("Otomasyon Merkezi", "Profiller", "Ayarlar", "Sil", "Kaydet"):
        button = ctk.CTkButton(
            new_row, text=label, width=54, height=54,
            fg_color="#1B1E26", hover_color="#262A35",
            text_color="#E8ECF5", font=("Segoe UI Semibold", 13),
        )
        button.pack(side="left", padx=(0, 10))
        new_buttons.append((button, label))

    input_row = section("Giriş çubuğu", "Yazı yerine ikon — üzerine gelince açıklama çıkar")
    for name in ("plus", "mic", "attach", "camera", "emoji", "send"):
        button = ctk.CTkButton(
            input_row, text="", width=44, height=44, corner_radius=22,
            fg_color="#1B1E26", hover_color="#262A35",
            text_color="#E8ECF5", font=(icon_font_family() or "Segoe UI", 20),
        )
        button.pack(side="left", padx=(0, 8))
        button._nx3_fixed_icon = glyph(name)
        new_buttons.append((button, glyph(name) and {"plus": "Ekle", "mic": "Mikrofon",
                                                     "attach": "Dosya ekle", "camera": "Kamera",
                                                     "emoji": "Emoji", "send": "Gönder"}[name] or name))

    # --- Alt: kontroller ---
    controls = ctk.CTkFrame(window, fg_color=card, corner_radius=18)
    controls.pack(fill="x", padx=24, pady=(14, 20))

    status = ctk.CTkLabel(controls, text="", font=("Segoe UI", 11), text_color="#8B94A7")

    def redraw(*_args: Any) -> None:
        family = icon_font_family()
        radius = state.get("button_radius", "pill")
        icon_only = bool(state.get("icon_only"))
        # 3.0 butonları
        for button, label in new_buttons:
            fixed = getattr(button, "_nx3_fixed_icon", None)
            try:
                height = int(button.cget("height"))
            except Exception:
                height = 40
            value = resolve_radius(radius, height)
            target = fixed if fixed else (icon_for_text(label) if icon_only else label)
            size = int(height * 0.42) if (fixed or icon_only) else 13
            try:
                button.configure(
                    text=target,
                    corner_radius=value,
                    font=(family if (fixed or icon_only) else "Segoe UI Semibold", size),
                )
            except Exception:
                pass
        for button in rail_buttons:
            try:
                rail_height = int(button.cget("height"))
            except Exception:
                rail_height = 44
            value = resolve_radius(radius, rail_height)
            label = _original_text(button) if getattr(button, "_nx3_text", None) else str(button.cget("text"))
            if getattr(button, "_nx3_label", None) is None:
                button._nx3_label = label
            shown = icon_for_text(button._nx3_label) if icon_only else button._nx3_label
            try:
                button.configure(
                    text=shown,
                    corner_radius=value,
                    font=(family if icon_only else "Segoe UI Semibold",
                          int(rail_height * 0.45) if icon_only else 12),
                )
            except Exception:
                pass
        status.configure(
            text=f"Yarıçap: {radius} · İkon modu: {'açık' if icon_only else 'kapalı'} · "
                 f"Yoğunluk: {state.get('density')} · Font: {family or 'yok'}"
        )

    def on_radius(value: float) -> None:
        nearest = min(RADIUS_SCALE.keys(), key=lambda k: abs(resolve_radius(k, 40) - int(value)))
        state["button_radius"] = nearest if abs(resolve_radius(nearest, 40) - int(value)) <= 3 else int(value)
        redraw()

    def on_icon(value: Any = None) -> None:
        state["icon_only"] = bool(icon_switch.get())
        redraw()

    def on_density(choice: str) -> None:
        state["density"] = str(choice).lower()
        redraw()

    def on_accent(choice: str) -> None:
        state["accent"] = "" if choice == "Varsayılan" else choice
        redraw()

    def do_save() -> None:
        state["enabled"] = True
        ok = save_config(state)
        status.configure(text="Kaydedildi ✔  (Neto'yu yeniden başlatınca etkin olur)"
                         if ok else "Kaydedilemedi — klasör izni olabilir.")

    def do_reset() -> None:
        state.update(dict(DEFAULT_CONFIG))
        state["enabled"] = True
        try:
            icon_switch.deselect()
        except Exception:
            pass
        redraw()

    left = ctk.CTkFrame(controls, fg_color="transparent")
    left.pack(side="left", padx=16, pady=12)

    ctk.CTkLabel(left, text="Köşe yuvarlaklığı", font=("Segoe UI", 11),
                 text_color="#8B94A7").grid(row=0, column=0, sticky="w")
    slider = ctk.CTkSlider(left, from_=4, to=24, number_of_steps=20, width=190, command=on_radius)
    slider.set(resolve_radius(state.get("button_radius", "pill"), 40))
    slider.grid(row=1, column=0, pady=(2, 8), sticky="w")

    icon_switch = ctk.CTkSwitch(left, text="Yazı yerine ikon", command=on_icon,
                                font=("Segoe UI", 12))
    if state.get("icon_only"):
        icon_switch.select()
    icon_switch.grid(row=2, column=0, sticky="w")

    mid = ctk.CTkFrame(controls, fg_color="transparent")
    mid.pack(side="left", padx=16, pady=12)
    ctk.CTkLabel(mid, text="Yoğunluk", font=("Segoe UI", 11), text_color="#8B94A7").pack(anchor="w")
    density_menu = ctk.CTkOptionMenu(mid, values=["Compact", "Comfortable", "Spacious"],
                                     width=140, command=on_density)
    density_menu.set(str(state.get("density", "comfortable")).capitalize())
    density_menu.pack(pady=(2, 8))
    ctk.CTkLabel(mid, text="Vurgu rengi", font=("Segoe UI", 11), text_color="#8B94A7").pack(anchor="w")
    accent_menu = ctk.CTkOptionMenu(mid, values=["Varsayılan", *ACCENT_PRESETS],
                                    width=140, command=on_accent)
    accent_menu.set("Varsayılan")
    accent_menu.pack(pady=(2, 0))

    right = ctk.CTkFrame(controls, fg_color="transparent")
    right.pack(side="right", padx=16, pady=12)
    ctk.CTkButton(right, text="Kaydet", width=110, height=38, corner_radius=19,
                  fg_color=surface_colors(state)["accent"], text_color="#0B0D12",
                  font=("Segoe UI Semibold", 12), command=do_save).pack(pady=(0, 6))
    ctk.CTkButton(right, text="Sıfırla", width=110, height=34, corner_radius=17,
                  fg_color="#1B1E26", hover_color="#262A35", text_color="#E8ECF5",
                  font=("Segoe UI", 11), command=do_reset).pack()

    status.pack(side="bottom", pady=(0, 10))
    redraw()

    if owns_root and standalone:
        window.mainloop()
    return window


__all__ = [
    "ACCENT_PRESETS",
    "DEFAULT_CONFIG",
    "ICONS",
    "PREVIEW_ITEMS",
    "SIDEBAR_ICONS",
    "SYMBOL_ICONS",
    "SPACING",
    "SURFACE",
    "Tooltip",
    "accent_color",
    "accent_hover_color",
    "apply",
    "apply_capsule_accents",
    "apply_icon_mode",
    "apply_sidebar_widget",
    "apply_symbol_icon",
    "attach_tooltip",
    "close_hover_colors",
    "glyph",
    "has_icon_font",
    "icon_font_family",
    "icon_for_text",
    "is_enabled",
    "load_config",
    "preview_window",
    "rail_button_metrics",
    "rail_sidebar_enabled",
    "refresh",
    "renew_all_icons",
    "reset_enabled_cache",
    "resolve_radius",
    "restore_text",
    "round_buttons",
    "save_config",
    "sidebar_glyph",
    "sidebar_widget_names",
    "style_surfaces",
    "surface_colors",
]
