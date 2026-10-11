# =========================================================
# NETO LIVE COMMANDS v10.2
# Live Mode için hızlı yerel komut motoru
# =========================================================
import os
import sys
import subprocess
import webbrowser
import datetime
import platform
import neto_weather

def _run(*command):
    try:
        subprocess.Popen(list(command), shell=False)
        return True
    except (OSError, ValueError):
        return False

def _open_url(url):
    try:
        webbrowser.open(url)
        return True
    except Exception:
        return False

def normalize_text(text):
    t = str(text or "").lower().strip()
    repl = {
        "saat kaçtır": "saat kaç",
        "saat kac": "saat kaç",
        "saat kaç": "saat kaç",
        "saati söyle": "saat kaç",
        "tarih ne": "tarih",
        "bugünün tarihi": "tarih",
        "hesapmakinesi": "hesap makinesi",
        "notdefteri": "not defteri",
        "görev yöneticis": "görev yöneticisi",
        "gorev yoneticisi": "görev yöneticisi",
        "yutub": "youtube",
        "yutüp": "youtube",
        "yutup": "youtube",
        "gugıl": "google",
        "vatsap": "whatsapp",
        "spotifay": "spotify",
        "instigram": "instagram",
        "ekran görüntüs": "ekran görüntüsü",
        "ss al": "ekran görüntüsü al",
        "ses aç": "sesi aç",
        "ses kıs": "sesi kıs",
    }
    for a, b in repl.items():
        t = t.replace(a, b)
    return t

def handle_live_command(text):
    """
    Komutu işler.
    Return:
      None => NetOps Agent'e gönder
      str  => hızlı cevap
    """
    t = normalize_text(text)

    # Otomatik konum algılama
    try:
        if neto_weather.is_location_query(t):
            return neto_weather.location_answer(t)
    except Exception as e:
        return f"Konum alınamadı: {e}"

    # Hava durumu - Open-Meteo
    if neto_weather.is_weather_query(t):
        return neto_weather.weather_answer(t)

    # Saat / tarih gibi şeyler AI'ye gitmesin, anında cevap dönsün.
    now = datetime.datetime.now()
    if "saat kaç" in t or t == "saat":
        return f"Saat {now.strftime('%H:%M')}."

    if t == "tarih" or "bugün tarih" in t or "tarihi söyle" in t:
        return f"Bugünün tarihi {now.strftime('%d.%m.%Y')}."

    if "hangi gündeyiz" in t or "bugün günlerden ne" in t:
        gunler = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
        return f"Bugün {gunler[now.weekday()]}."

    # Web komutları
    if "youtube aç" in t or t == "youtube":
        _open_url("https://www.youtube.com/")
        return "YouTube açılıyor."

    if "google aç" in t or t == "google":
        _open_url("https://www.google.com/")
        return "Google açılıyor."

    if "whatsapp aç" in t or t == "whatsapp":
        _open_url("https://web.whatsapp.com/")
        return "WhatsApp Web açılıyor."

    if "instagram aç" in t or t == "instagram":
        _open_url("https://www.instagram.com/")
        return "Instagram açılıyor."

    if "spotify aç" in t or t == "spotify":
        _open_url("https://open.spotify.com/")
        return "Spotify açılıyor."

    # Windows komutları
    if "hesap makinesi" in t:
        _run("calc.exe")
        return "Hesap makinesi açılıyor."

    if "not defteri" in t:
        _run("notepad.exe")
        return "Not defteri açılıyor."

    if "görev yöneticisi" in t or "task manager" in t:
        _run("taskmgr.exe")
        return "Görev yöneticisi açılıyor."

    if t == "cmd" or "komut istemi" in t:
        _run("cmd.exe")
        return "Komut istemi açılıyor."

    if "powershell" in t:
        _run("powershell.exe")
        return "PowerShell açılıyor."

    if "denetim masası" in t:
        _run("control.exe")
        return "Denetim masası açılıyor."

    if "dosya gezgini" in t or "explorer aç" in t:
        _run("explorer.exe")
        return "Dosya gezgini açılıyor."

    # Güvenlik: bilgisayarı kapatma/yeniden başlatma Live'da direkt yapılmasın.
    if "bilgisayarı kapat" in t or "pc kapat" in t:
        return "Güvenlik için Live Mode'da bilgisayarı direkt kapatmıyorum."

    if "yeniden başlat" in t or "restart" in t:
        return "Güvenlik için Live Mode'da yeniden başlatma komutunu direkt çalıştırmıyorum."

    # Ses komutları: basit cevap, sistem sesi değiştirme riskli.
    if "sesi aç" in t:
        return "Ses açma komutu algılandı. Bu sürümde sistem sesi doğrudan değiştirmiyorum."

    if "sesi kıs" in t:
        return "Ses kısma komutu algılandı. Bu sürümde sistem sesi doğrudan değiştirmiyorum."

    if "sistem bilgisi" in t or "bilgisayar bilgisi" in t:
        return f"Sistem: {platform.system()} {platform.release()}."

    return None
