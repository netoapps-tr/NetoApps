# =========================================================
# NETOPS - SISTEM TEPSISI MODULU
# pystray tabanli. pystray kurulu degilse TRAY_AKTIF False olur
# ve ana program tepsi olmadan calismaya devam eder.
# =========================================================

import os
import threading

try:
    import pystray
    from pystray import Menu as _Menu
    from pystray import MenuItem as _MenuItem
    from PIL import Image, ImageDraw
    TRAY_AKTIF = True
except Exception:
    TRAY_AKTIF = False

_icon = None
_thread = None


def _varsayilan_simge():
    """Logo bulunamazsa kullanilan basit NetOps simgesi (64x64)."""
    img = Image.new("RGB", (64, 64), (30, 215, 96))
    ciz = ImageDraw.Draw(img)
    ciz.rectangle([6, 6, 57, 57], outline=(0, 0, 0), width=4)
    ciz.text((20, 15), "N", fill=(0, 0, 0))
    return img


def _simge_yukle(logo_yolu=None):
    if logo_yolu and os.path.exists(logo_yolu):
        try:
            return Image.open(logo_yolu)
        except Exception:
            pass
    return _varsayilan_simge()


def tray_baslat(logo_yolu=None, baslik="NetOps", goster_yazisi="Göster",
                cikis_yazisi="Çıkış", on_goster=None, on_cikis=None):
    """Tepsi simgesini ayri bir daemon thread'de baslatir. Basariliysa True."""
    global _icon, _thread

    if not TRAY_AKTIF or _icon is not None:
        return False

    def _goster(icon, item):
        try:
            if callable(on_goster):
                on_goster()
        except Exception:
            pass

    def _cikis(icon, item):
        try:
            if callable(on_cikis):
                on_cikis()
        except Exception:
            pass

    try:
        menu = _Menu(
            _MenuItem(goster_yazisi, _goster, default=True),
            _MenuItem(cikis_yazisi, _cikis),
        )
        _icon = pystray.Icon("netops", _simge_yukle(logo_yolu), baslik, menu)
        _thread = threading.Thread(target=_icon.run, daemon=True)
        _thread.start()
        return True
    except Exception:
        _icon = None
        return False


def tray_durdur():
    """Tepsi simgesini kaldirir (tam cikis oncesi cagrilir)."""
    global _icon
    try:
        if _icon is not None:
            _icon.stop()
    except Exception:
        pass
    finally:
        _icon = None
