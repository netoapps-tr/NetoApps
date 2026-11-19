# =========================================================
# NETO AI / KEVRA K1-K2
# HİBRİT PROFESYONEL SÜRÜM
# =========================================================

import random
import datetime
import requests
import difflib
import time
import re
import os
import sys
import shutil
import subprocess
import webbrowser
import base64
from html import unescape
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

try:
    from lang import T, get_lang
except Exception:
    def get_lang() -> str: return "tr"
    def T(key: str, **kwargs) -> str:
        return key.format(**kwargs) if kwargs else key

try:
    from config import KUFUR_LISTESI
except Exception:
    KUFUR_LISTESI = []


# =========================================================
# AYARLAR
# =========================================================

# NetOps now uses the local Harbilig engine as its canonical response path.
# Keep the legacy Ollama adapter available for rollback, but never start it
# implicitly or download a model during normal application use.
AI_MODEL_AKTIF = False

AI_MODEL_ADI = "gemma3:4b"

AI_URL = "http://localhost:11434/api/generate"
AI_TAGS_URL = "http://localhost:11434/api/tags"
OLLAMA_DOWNLOAD_URL = "https://ollama.com/download/windows"
AGENT_NAME = "NetOps Agent"
AGENT_MODEL_ALIASES = {
    "Kevra K1": "NetOps Agent K1",
    "Kevra K2": "NetOps Agent K2",
}

_MODEL_INDIRME_BASLADI = False
_OLLAMA_BASLATMA_DENENDI = False

MODEL_TIMEOUT_KISA = 240
MODEL_TIMEOUT_UZUN = 480

INTERNET_AKTIF = True

_OLLAMA_CACHE = {
    "sonuc": False,
    "zaman": 0
}

_OLLAMA_CACHE_SURE = 5

SON_BILGI = {
    "internet": None,
    "baslik": None,
    "govde": None,
    "kaynak": None,
    "automation_draft": None,
    "zaman": 0
}

SON_BILGI_SURE = 600
# NetOps One konum servisi uygulama açılışında bloklamadan hazırlanır.
try:
    from netops_one_engine import start_location_service as _netops_one_location_start
    _netops_one_location_start(os.path.dirname(os.path.abspath(__file__)))
except Exception:
    _netops_one_location_start = None


def internet_aktif_mi():
    return bool(INTERNET_AKTIF)


def internet_durum_ayarla(acik):
    global INTERNET_AKTIF
    INTERNET_AKTIF = bool(acik)
    return INTERNET_AKTIF


def internet_durumu_degistir():
    return internet_durum_ayarla(not INTERNET_AKTIF)


# =========================================================
# DUCKDUCKGO
# =========================================================

DDGS = None
try:
    from duckduckgo_search import DDGS
    DDG_AKTIF = True
except Exception:
    DDG_AKTIF = False


# =========================================================
# BİLGİ HAFIZASI
# =========================================================

BILGI = {
    "minecraft nedir":
        "Minecraft, bloklarla inşa yapabildiğin ve hayatta kalmaya çalıştığın sandbox oyunudur.",

    "meta eski adı":
        "Meta'nın eski adı Facebook'tur.",

    "facebook yeni adı":
        "Facebook şirketinin yeni adı Meta'dır.",

    "sen kimsin":
        "Ben NetOps Agent, NetOps Agent sisteminin sohbet motoruyum.",

    "seni kim yaptı":
        "Beni NetOps geliştirdi.",

    "seni kim yapti":
        "Beni NetOps geliştirdi.",

    "geliştiricin kim":
        "Beni NetOps geliştirdi.",

    "gelistiricin kim":
        "Beni NetOps geliştirdi.",

    "model adı":
        "Ben NetOps Agent model ailesinden çalışıyorum.",

    "model adi":
        "Ben NetOps Agent model ailesinden çalışıyorum.",

    "kevra sürümü":
        "Aktif NetOps Agent sürümü seçilen profile bağlıdır.",

    "kevra surumu":
        "Aktif NetOps Agent sürümü seçilen profile bağlıdır.",

    "eşek ayak":
        "Eşeklerin 4 ayağı vardır.",

    "eşşek ayak":
        "Eşeklerin 4 ayağı vardır.",
}


def bilgi_hafizasinda_ara(metin):
    metin = metin_temizle(metin)

    if not metin:
        return None

    try:
        for anahtar, cevap in BILGI.items():
            anahtar_temiz = metin_temizle(anahtar)

            if metin == anahtar_temiz:
                return cevap

            kelimeler = anahtar_temiz.split()

            if kelimeler and all(kelime in metin for kelime in kelimeler):
                return cevap

    except Exception:
        return None

    return None


# =========================================================
# KOMUTLAR
# =========================================================

KOMUTLAR = {
    "youtube aç": "youtube aç",
    "youtube'a gir": "youtube aç",

    "google aç": "google aç",
    "google'a gir": "google aç",

    "whatsapp aç": "whatsapp aç",
    "spotify aç": "spotify aç",
    "instagram aç": "instagram aç",
    "twitter aç": "twitter aç",
    "twitch aç": "twitch aç",
    "github aç": "github aç",

    "harita aç": "google maps aç",
    "google maps aç": "google maps aç",

    "bilgisayarı kapat": "bilgisayarı kapat",
    "pc'yi kapat": "bilgisayarı kapat",

    "bilgisayarı yeniden başlat": "bilgisayarı yeniden başlat",
    "pc'yi yeniden başlat": "bilgisayarı yeniden başlat",

    "bilgisayarı uyut": "bilgisayarı uyut",
    "uyku moduna al": "bilgisayarı uyut",

    "ekran görüntüsü al": "ekran görüntüsü",
    "ss al": "ekran görüntüsü",

    "görev yöneticisi": "görev yöneticisi",
    "denetim masası": "denetim masası",

    "çalıştır": "çalıştır",
    "cmd": "cmd",
    "powershell": "powershell",
    "not defteri": "not defteri",
    "hesap makinesi": "hesap makinesi",

    "ses ayarları": "ses ayarları",

    "masaüstü": "masaüstü",
    "belgeler": "belgeler",
    "indirilenler": "indirilenler",

    "ip adresim": "ip adresim",
    "internet kontrol": "internet kontrol",
    "sistem bilgisi": "sistem bilgisi",

    "neto code": "neto code",
    "kod editörü": "neto code",
    "neto lab": "netolab",

    "ayarlar": "ayarlar",
    "gelişmiş ayarlar": "gelişmiş ayarlar",

    "şifre oluştur": "şifre oluştur",
    "yazı tura": "yazı tura",

    "hava durumu": "__HAVA__",
    "hava nasıl": "__HAVA__",

    "sesi aç": "__SES__:85",
    "sesi kıs": "__SES__:15",
    "sesi artır": "__SES__:85",
    "sesi azalt": "__SES__:15",
}


# =========================================================
# SOHBET
# =========================================================

SOHBET = {
    "merhaba": ["ai_greeting_1", "ai_greeting_2", "ai_greeting_3"],
    "selam": ["ai_greeting_2", "ai_greeting_1", "ai_greeting_3"],
    "naber": ["ai_how_are_you_short", "ai_how_are_you_short_2"],
    "nasılsın": ["ai_how_are_you_short", "ai_how_are_you_short_2"],
    "teşekkür": ["ai_thanks_reply_short", "ai_thanks_reply_short_2"],
    "sağ ol": ["ai_thanks_reply_short", "ai_thanks_reply_short_2"],
    "görüşürüz": ["ai_goodbye_short", "ai_goodbye_short_2"],
}


VARSAYILAN = [
    "ai_default_1",
    "ai_default_2",
    "ai_default_3",
    "ai_default_4",
    "ai_default_5",
    "ai_default_6",
    "ai_default_7",
    "ai_default_8",
]


def _internet_sohbet_uygun_mu(metin):
    metin = metin_temizle(metin)
    if not metin:
        return False

    kapali_ifadeler = (
        "merhaba", "selam", "naber", "nasılsın", "teşekkür", "sağ ol",
        "görüşürüz", "hoşça kal", "adın ne", "ismin ne", "kimsin",
        "yanımda kız", "yanımda bir kız", "kız var", "kiz var",
        "laf at", "laf sok", "takıl", "takil", "flört", "flort",
    )
    if any(kelime in metin for kelime in kapali_ifadeler):
        return False

    if internet_gerekli_mi(metin):
        return True

    if metin.endswith("?"):
        return True

    acik_ifadeler = (
        "nasıl", "neden", "niye", "kim", "nedir", "ne demek", "hangi",
        "kaç", "kaçta", "kaç para", "öner", "tavsiye", "karşılaştır",
        "kıyasla", "incele", "yorumla", "haber", "gündem", "fiyat", "kur",
        "özellik", "yeni", "son durum", "güncel"
    )
    if any(kelime in metin for kelime in acik_ifadeler):
        return True

    return len(metin) >= 24


def _yerel_dual(tr: str, en: str) -> str:
    return en if get_lang() == "en" else tr


def _yerel_internet_ozeti(internet_bilgisi, cevap_modu="kisa"):
    raw = str(internet_bilgisi or "").strip()
    if not raw:
        return None

    bloklar = [blok.strip() for blok in raw.split("\n\n") if blok.strip()]
    if not bloklar:
        return None

    if cevap_modu == "uzun":
        parcalar = []
        for blok in bloklar[:3]:
            satirlar = [satir.strip() for satir in blok.splitlines() if satir.strip()]
            if not satirlar:
                continue
            baslik = satirlar[0]
            govde = ""
            kaynak = ""
            for satir in satirlar[1:]:
                if satir.lower().startswith("kaynak:"):
                    kaynak = satir
                elif not govde:
                    govde = satir
            parca = baslik
            if govde:
                parca += f" - {govde}"
            if kaynak:
                parca += f" ({kaynak})"
            parcalar.append(parca)
        if parcalar:
            return "\n\n".join(parcalar)

    ilk = bloklar[0]
    satirlar = [satir.strip() for satir in ilk.splitlines() if satir.strip()]
    if not satirlar:
        return None

    baslik = satirlar[0]
    govde = ""
    for satir in satirlar[1:]:
        if satir.lower().startswith("kaynak:"):
            continue
        govde = satir
        break

    if govde:
        return f"{baslik}. {govde}"
    return baslik


def _yerel_ai_cevabi_uret(mesaj, internet_bilgisi=None, cevap_modu="kisa", agent_modu=False):
    metin = metin_temizle(mesaj)
    if not metin:
        return T("ai_empty_input")

    if internet_bilgisi is None and internet_aktif_mi():
        arama_baslangiclari = (
            "kim ", "nedir ", "ne demek ", "nasıl ", "neden ", "niye ",
            "hangi ", "nerede ", "ne zaman ", "kaç ", "kaçta ", "kaçtır ",
        )
        if metin.endswith("?") or metin.startswith(arama_baslangiclari):
            try:
                internet_bilgisi = internette_ara(mesaj)
            except Exception:
                internet_bilgisi = None

    if internet_bilgisi:
        ozet = _yerel_internet_ozeti(internet_bilgisi, cevap_modu=cevap_modu)
        if ozet:
            return ozet

    flort_kelimeleri = (
        "yanımda kız", "yanımda bir kız", "kız var", "kiz var",
        "laf at", "laf sok", "takıl", "takil", "flört", "flort",
        "yürü", "yuru", "espri yap", "espri", "şaka yap", "saka yap",
    )
    if any(kelime in metin for kelime in flort_kelimeleri):
        if cevap_modu == "uzun":
            return _yerel_dual(
                "Kısa ve özgüvenli git: 'Sohbet iyi akıyor, ben de katılabilir miyim?' İstersen daha komik, daha cool ya da daha cesur 3 versiyon yazarım.",
                "Keep it short and confident: 'The conversation is flowing well, can I join in?' I can also write 3 versions that are funnier, cooler, or bolder."
            )
        return _yerel_dual(
            "Kısa ve özgüvenli git: 'Sohbet iyi akıyor, ben de katılabilir miyim?' İstersen daha komik ya da daha cesur bir versiyon da yazarım.",
            "Keep it short and confident: 'The conversation is flowing well, can I join in?' I can also write a funnier or bolder version."
        )

    if any(kelime in metin for kelime in ("mümkün mü", "olur mu", "yapılır mı", "yapılabilir mi", "yapabilir miyiz")):
        return _yerel_dual(
            "Evet, mümkün. Ama en doğru yolu netleştirelim; istersen adım adım plan çıkarayım.",
            "Yes, it is possible. Let's narrow down the best way; I can outline the steps."
        )

    if "nasıl" in metin or "şimdi ne yapayım" in metin or "ne yapayım" in metin:
        if cevap_modu == "uzun":
            return _yerel_dual(
                "Bunu adım adım yapabiliriz: önce hedefi netleştiririz, sonra küçük parçalara böleriz.",
                "We can do this step by step: first define the goal, then break it into small parts."
            )
        return _yerel_dual(
            "Bunu adım adım yapabiliriz.",
            "We can do this step by step."
        )

    if "neden" in metin or "niye" in metin:
        return _yerel_dual(
            "Bunun birkaç olası sebebi var; en mantıklı olanı önce test etmek gerekir.",
            "There are a few possible reasons; the best one to test first is usually the most likely."
        )

    if any(kelime in metin for kelime in ("kim", "nedir", "ne demek", "hangi", "nerede", "ne zaman", "kaç", "kaçta")):
        defaults = [T(k) for k in VARSAYILAN]
        secim = random.choice(defaults)
        if cevap_modu == "uzun":
            return _yerel_dual(
                f"{secim} İstersen bunu biraz daha açayım.",
                f"{secim} If you want, I can expand on it a bit more."
            )
        return secim

    if agent_modu:
        if cevap_modu == "uzun":
            return _yerel_dual(
                "Tamam, bunu birlikte çözeriz. Önce ne istediğini biraz daralt, sonra sana net bir yol çıkarayım.",
                "Okay, we can solve this together. Narrow down what you want first and I'll give you a clear path."
            )
        return _yerel_dual(
            "Tamam, bunu birlikte çözeriz.",
            "Okay, we can solve this together."
        )

    if cevap_modu == "uzun":
        return _yerel_dual(
            "Şu an kesin model cevabı yok ama boş da bırakmıyorum: birlikte netleştirebiliriz.",
            "I don't have a model answer right now, but I'm not leaving it blank: we can narrow it down together."
        )

    return T(random.choice(VARSAYILAN))


def _ozel_komut_mu(text):
    return isinstance(text, str) and (
        text.startswith("__KOMUT__:") or
        text.startswith("__SES__:") or
        text.startswith("__HESAPLA__:") or
        text.startswith("__HAVA__:")
    )


def _ai_dil_cevir(text):
    """Arayüz dili English ise yerel/sabit Türkçe cevapları İngilizceye çevirir. Özel komutları bozmaz."""
    if text is None:
        return text
    if _ozel_komut_mu(text):
        return text
    if get_lang() != "en":
        return text

    raw = str(text).strip()
    exact = {
        "Bir şey yazmadın.": T("ai_empty_input"),
        "Beni NetOps geliştirdi.": T("ai_developer"),
        "Elimde okunacak haber yok. Önce 'bugün haber var mı?' diye sor.": T("ai_no_news"),
        "Güncel bilgiye ulaşamadım. İnternet araması sonuç vermedi.": T("ai_current_info_failed"),
        "Model boş cevap verdi.": T("ai_empty_response"),
        "AI model modu kapalı. neto_ai.py içinde AI_MODEL_AKTIF = True yapılmalı.": T("ai_model_not_ready"),
        "Yerel cevap motoru şu an cevap vermiyor. Biraz bekleyip tekrar dene.": T("ai_ollama_service_not_running"),
        "Ben NetOps Agent K1 olarak çalışıyorum.": "I am running as NetOps Agent K1.",
        "Ben NetOps Agent K2 olarak çalışıyorum.": "I am running as NetOps Agent K2.",
        "Eşeklerin 4 ayağı vardır.": "Donkeys have 4 legs.",
        "Minecraft, bloklarla inşa yapabildiğin ve hayatta kalmaya çalıştığın sandbox oyunudur.": "Minecraft is a sandbox game where you build with blocks and try to survive.",
        "Meta'nın eski adı Facebook'tur.": "Meta's former name was Facebook.",
        "Facebook şirketinin yeni adı Meta'dır.": "Facebook's new company name is Meta.",
        "Ben NetOps Agent, NetOps Agent sisteminin sohbet motoruyum.": "I am NetOps Agent, the chat engine of the NetOps Agent system.",
        "Ben NetOps Agent model ailesinden çalışıyorum.": "I run on the NetOps Agent model family.",
        "Aktif NetOps Agent sürümü seçilen profile bağlıdır.": "The active NetOps Agent version depends on the selected profile.",
    }
    if raw in exact:
        return exact[raw]
    if raw.startswith("Şu an saat "):
        return raw.replace("Şu an saat", "The time is", 1)
    if raw.startswith("Bugün "):
        return raw.replace("Bugün", "Today is", 1)
    if raw.startswith("Model çok geç cevap verdi"):
        return T("ai_timeout")
    if raw.startswith("Model cevap vermedi. Hata kodu:"):
        return raw.replace("Model cevap vermedi. Hata kodu:", "The model did not respond. Error code:")
    if raw.startswith("Model hatası:"):
        return raw.replace("Model hatası:", "Model error:")
    return raw

# =========================================================
# TEMEL YARDIMCI FONKSİYONLAR
# =========================================================

def metin_temizle(metin):
    if not metin:
        return ""

    metin = str(metin).lower().strip()
    metin = re.sub(r"\s+", " ", metin)

    return metin


def _agresif_kufur_var_mi(metin):
    """Kufur filtresi sadece gercek token/ifade eslesmesine bakar.

    Eski surum tek kelimelik kufru normal kelimenin icinde de ariyordu;
    bu yuzden "beşiktaş" gibi masum sorgular yanlis engellenebiliyordu.
    """
    metin_lower = str(metin or "").casefold()
    kelimeler = re.findall(r"[a-z0-9çğıöşü]+", metin_lower)
    metin_aralikli = " " + " ".join(kelimeler) + " "
    guvenli_kelimeler = {"beşiktaş", "besiktas", "fenerbahçe", "fenerbahce", "galatasaray", "trabzonspor"}
    if set(kelimeler) & guvenli_kelimeler:
        return False
    for kufur in KUFUR_LISTESI:
        kufur_lower = str(kufur or "").casefold().strip()
        if not kufur_lower:
            continue
        kufur_kelimeler = re.findall(r"[a-z0-9çğıöşü]+", kufur_lower)
        if not kufur_kelimeler:
            continue
        if len(kufur_kelimeler) > 1:
            ifade = " ".join(kufur_kelimeler)
            if f" {ifade} " in metin_aralikli:
                return True
            continue
        token = kufur_kelimeler[0]
        if len(token) <= 2:
            continue
        if token in kelimeler:
            return True
    return False


def _saat():
    return T("ai_time_now", time=datetime.datetime.now().strftime('%H:%M'))


def _tarih():
    simdi = datetime.datetime.now()
    if get_lang() == "en":
        months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        return f"Today is {weekdays[simdi.weekday()]}, {months[simdi.month - 1]} {simdi.day}, {simdi.year}."
    aylar = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
    gunler = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
    return f"Bugün {gunler[simdi.weekday()]}, {simdi.day} {aylar[simdi.month - 1]} {simdi.year}."


def ollama_cli_var_mi():
    """Bilgisayarda ollama.exe PATH üzerinden bulunabiliyor mu?"""
    return shutil.which("ollama") is not None


def ollama_var_mi():
    """Yerel API çalışıyor mu? Çalışmıyorsa bir kez arka planda başlatmayı dener."""
    global _OLLAMA_BASLATMA_DENENDI

    simdi = time.time()

    if simdi - _OLLAMA_CACHE["zaman"] < _OLLAMA_CACHE_SURE:
        return _OLLAMA_CACHE["sonuc"]

    try:
        r = requests.get(AI_TAGS_URL, timeout=2)
        sonuc = r.status_code == 200

        _OLLAMA_CACHE["sonuc"] = sonuc
        _OLLAMA_CACHE["zaman"] = simdi

        return sonuc

    except Exception:
        pass

    # Yerel API açık değilse EXE içinden bir kez başlatmayı dene.
    if ollama_cli_var_mi() and not _OLLAMA_BASLATMA_DENENDI:
        _OLLAMA_BASLATMA_DENENDI = True

        try:
            flags = 0
            if os.name == "nt":
                flags = subprocess.CREATE_NO_WINDOW

            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags
            )

            time.sleep(2)

            try:
                r = requests.get(AI_TAGS_URL, timeout=3)
                sonuc = r.status_code == 200

                _OLLAMA_CACHE["sonuc"] = sonuc
                _OLLAMA_CACHE["zaman"] = time.time()

                return sonuc

            except Exception:
                pass

        except Exception:
            pass

    _OLLAMA_CACHE["sonuc"] = False
    _OLLAMA_CACHE["zaman"] = time.time()

    return False


def ollama_model_yuklu_mu():
    """Yerel servis çalışıyor mu ve AI_MODEL_ADI yüklü mü kontrol eder."""
    try:
        r = requests.get(AI_TAGS_URL, timeout=3)

        if r.status_code != 200:
            return False

        veri = r.json()
        modeller = veri.get("models", [])
        isimler = []

        for model in modeller:
            ad = model.get("name") or model.get("model") or ""
            if ad:
                isimler.append(ad)

        return AI_MODEL_ADI in isimler

    except Exception:
        return False


def ollama_model_indirmeyi_baslat():
    """
    EXE içinden model indirmeyi başlatır.
    Yerel motor yoksa kurulum sayfasını açar.
    Model indirme işlemi ayrı konsolda görünür; kullanıcı ilerlemeyi orada takip eder.
    """
    global _MODEL_INDIRME_BASLADI

    if not ollama_cli_var_mi():
        try:
            webbrowser.open(OLLAMA_DOWNLOAD_URL)
        except Exception:
            pass

        return (
            "Yerel cevap motoru bu bilgisayarda kurulu değil.\n\n"
            "Kurulum sayfasını açtım. Önce yerel motoru kur, sonra NetOps Agent butonuna tekrar bas.\n"
            "Adres: https://ollama.com/download/windows"
        )

    if _MODEL_INDIRME_BASLADI:
        return f"{AI_MODEL_ADI} modeli zaten indiriliyor. Açılan konsol penceresinde ilerlemeyi takip edebilirsin."

    _MODEL_INDIRME_BASLADI = True

    try:
        if os.name == "nt":
            subprocess.Popen(
                ["ollama", "pull", AI_MODEL_ADI],
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:
            subprocess.Popen(["ollama", "pull", AI_MODEL_ADI])

        return (
            f"{AI_MODEL_ADI} modeli indirilmeye başladı.\n\n"
            "Boyut yaklaşık 3.3 GB. İndirme bitince NetOps Agent penceresini kapatıp tekrar aç."
        )

    except Exception as e:
        _MODEL_INDIRME_BASLADI = False
        return f"Model indirme başlatılamadı: {e}"


def model_durum_mesaji(otomatik_indir=False):
    """Yerel cevap motorunun durumunu döndürür; dış model kurulumu istemez."""
    if not AI_MODEL_AKTIF:
        return "AI model modu kapalı. neto_ai.py içinde AI_MODEL_AKTIF = True yapılmalı."
    return None


def cevap_modu_belirle(metin):
    uzun_kelimeler = [
        "anlat",
        "açıkla",
        "detay",
        "detaylı",
        "uzun",
        "paragraf",
        "oku",
        "haberi oku",
        "ne yazmışlar",
        "ne yazıyor",
        "ne diyor",
        "haber",
        "gündem",
        "özetle",
        "özet çıkar",
        "rapor",
        "listele",
        "karşılaştır",
        "yorumla"
    ]

    if any(k in metin for k in uzun_kelimeler):
        return "uzun"

    return "kisa"


def karar_netlestirme_gerekli_mi(metin):
    """Belirsiz komutlarda tahmin etmek yerine kısa bir netleştirme sorusu sorar."""
    m = re.sub(r"[^\wçğıöşüâîû]+", " ", str(metin or "").lower()).strip()
    if not m:
        return None

    acma_ifadeleri = {
        "aç",
        "açsana",
        "başlat",
        "başlatsana",
        "çalıştır",
        "çalıştırsana",
        "open",
    }
    belirsiz_hedefler = {
        "bunu aç",
        "şunu aç",
        "onu aç",
        "bunu başlat",
        "şunu başlat",
        "onu başlat",
    }

    if m in acma_ifadeleri or m in belirsiz_hedefler:
        return "Hangi uygulamayı açmamı istiyorsun?"

    return None


def internet_gerekli_mi(metin):
    metin = metin_temizle(metin)

    try:
        import neto_sohbet_v2
        if neto_sohbet_v2.should_stay_offline(metin):
            return False
    except Exception:
        pass

    # Basit gün/saat/tarih soruları internete gitmemeli; yerel saatten cevaplanır.
    yerel_zaman_sorulari = (
        "bugün günlerden ne", "bugun gunlerden ne", "günlerden ne", "gunlerden ne",
        "bugün hangi gün", "bugun hangi gun", "hangi gündeyiz", "hangi gundeyiz",
        "bugün tarih ne", "bugun tarih ne", "bugünün tarihi", "bugunun tarihi",
        "saat kaç", "saat kac", "tarih ne",
    )
    if any(k in metin for k in yerel_zaman_sorulari):
        return False

    anahtarlar = [
        "bugün",
        "güncel",
        "haber",
        "son dakika",
        "son haber",
        "gündem",
        "2026",
        "şu an",
        "şuan",
        "ne olmuş",

        "altın",
        "gram altın",
        "çeyrek altın",
        "dolar",
        "euro",
        "borsa",
        "bist",
        "bitcoin",
        "btc",
        "fiyat",
        "kaç para",
        "kaç tl",
        "kur",
        "en iyi",
        "en uygun",
        "en ucuz",
        "öner",
        "öneri",
        "tavsiye",
        "karşılaştır",
        "kıyasla",
        "hangisi",
        "yorum",
        "incele",
        "özellik",
        "farkı",
        "ilaç",
        "araba",
        "araç",
        "otomobil",
        "telefon",
        "bilgisayar",
        "laptop",
        "tablet",
        "kulaklık",
        "monitör",
        "televizyon"
    ]

    if any(k in metin for k in anahtarlar):
        return True

    urunler = [
        "ilaç",
        "araba",
        "araç",
        "otomobil",
        "telefon",
        "bilgisayar",
        "laptop",
        "tablet",
        "kulaklık",
        "monitör",
        "televizyon",
        "kamera",
        "akıllı saat",
        "oyun konsolu",
    ]

    karar_kelimeleri = [
        "en iyi",
        "en uygun",
        "en ucuz",
        "öner",
        "öneri",
        "tavsiye",
        "karşılaştır",
        "kıyasla",
        "hangisi",
        "farkı",
        "incele",
        "yorum",
    ]

    if any(u in metin for u in urunler) and any(k in metin for k in karar_kelimeleri):
        return True

    return False


def son_bilgi_devami_mi(metin):
    anahtarlar = [
        "haberi oku",
        "haberi bana oku",
        "ne yazmışlar",
        "ne yazıyor",
        "ne diyor",
        "devam et",
        "oku",
        "anlat",
        "detay",
        "detayları",
        "haberin içeriği",
        "özetle",
        "ne olmuş"
    ]

    return any(k in metin for k in anahtarlar)


def son_bilgi_var_mi():
    bilgi = SON_BILGI.get("internet")

    if not bilgi:
        return False

    gecen_sure = time.time() - SON_BILGI.get("zaman", 0)

    return gecen_sure <= SON_BILGI_SURE


def son_bilgiyi_oku():
    if not son_bilgi_var_mi():
        return "Elimde okunacak güncel bilgi yok."

    baslik = SON_BILGI.get("baslik") or "Güncel bilgi"
    govde = SON_BILGI.get("govde") or SON_BILGI.get("internet")
    kaynak = SON_BILGI.get("kaynak") or ""

    cevap = f"{baslik}\n\nÖzet:\n{govde}"

    if kaynak:
        cevap += f"\n\nKaynak: {kaynak}"

    return cevap


LINUX_BRIDGE_KELIMELERI = (
    "linux",
    "ubuntu",
    "wsl",
    "bash",
    "shell",
    "terminal",
    "apt",
    "dpkg",
    "paket",
    "distro",
    "daemon",
    "systemctl",
    "kernel",
    "köprü",
    "bridge",
    "servis",
    "python3",
    "pip3",
    "repo",
    "kurulum",
)


def linux_bridge_gerekli_mi(metin):
    metin = metin_temizle(metin)

    if not metin:
        return False

    if any(kelime in metin for kelime in LINUX_BRIDGE_KELIMELERI):
        return True

    if any(
        metin.startswith(baslangic)
        for baslangic in (
            "ubuntu durumu",
            "linux durumu",
            "wsl durumu",
            "linux köprü",
            "linux bridge",
            "ubuntu sürüm",
            "wsl sürüm",
        )
    ):
        return True

    return False


def linux_bridge_cevabi_ara(soru, agent_modu=False):
    if os.environ.get("NETO_SKIP_LINUX_BRIDGE") == "1":
        return None

    metin = metin_temizle(soru)
    if not linux_bridge_gerekli_mi(metin):
        return None

    try:
        import neto_wsl_bridge
    except Exception:
        return None

    try:
        durum = neto_wsl_bridge.status()
        if not isinstance(durum, dict) or not durum.get("ready"):
            return None
    except Exception:
        return None

    try:
        cevap = neto_wsl_bridge.assistant_request(
            soru,
            agent_mode=agent_modu,
            allow_quick=True,
            mode="linux",
            timeout=6.0,
        )
    except Exception:
        return None

    if isinstance(cevap, dict):
        text = str(cevap.get("text") or "").strip()
        if text:
            return text
    elif isinstance(cevap, str):
        text = cevap.strip()
        if text:
            return text

    return None


# =========================================================
# ARAMA SORGUSU
# =========================================================

def arama_sorgusu_hazirla(soru):
    metin = metin_temizle(soru)

    if "gündem" in metin or "son dakika" in metin:
        return "Türkiye son dakika güncel haberler bugün"

    if "haber" in metin:
        return "Türkiye güncel haberler bugün son dakika"

    if "altın" in metin:
        return "gram altın fiyatı bugün kaç TL"

    if "dolar" in metin:
        return "dolar kuru bugün kaç TL"

    if "euro" in metin:
        return "euro kuru bugün kaç TL"

    if "bitcoin" in metin or "btc" in metin:
        return "bitcoin fiyatı bugün kaç dolar"

    if "borsa" in metin or "bist" in metin:
        return "BIST 100 bugün son durum"

    return soru


def sonuc_kategori_sayfasi_mi(baslik, govde, kaynak):
    metin = f"{baslik} {govde} {kaynak}".lower()

    yasakli = [
        "gündem haberleri",
        "son dakika haberleri",
        "en güncel gelişmeler",
        "haberler -",
        "gündem sayfası",
        "kategori",
        "etiket",
        "/gundem",
        "/son-dakika",
        "güncel haberler",
        "haber oku"
    ]

    return any(k in metin for k in yasakli)


def sonuc_kaliteli_mi(baslik, govde):
    if not baslik or not govde:
        return False

    if len(govde) < 45:
        return False

    return True


def _html_metin_temizle(metin):
    metin = unescape(str(metin or ""))
    metin = re.sub(r"<[^>]+>", " ", metin)
    metin = re.sub(r"\s+", " ", metin).strip()
    return metin


def _ddg_href_cozumle(href):
    if not href:
        return ""

    href = unescape(str(href))

    try:
        parsed = urlparse(href)
        sorgu = parse_qs(parsed.query)
        if "uddg" in sorgu and sorgu["uddg"]:
            return unquote(sorgu["uddg"][0])
    except Exception:
        pass

    return href


def _duckduckgo_html_sonuclari(sorgu, max_results=8):
    try:
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(sorgu)}&kl=tr-tr"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            )
        }
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return []

        html = r.text
        sonuclar = []
        a_pattern = re.compile(r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.S)

        for match in a_pattern.finditer(html):
            href = _ddg_href_cozumle(match.group(1).replace("&amp;", "&"))
            baslik = _html_metin_temizle(match.group(2))
            if not baslik:
                continue

            tail = html[match.end(): match.end() + 1500]
            snippet_match = re.search(r'class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</', tail, re.S)
            govde = _html_metin_temizle(snippet_match.group(1)) if snippet_match else ""
            sonuclar.append({
                "title": baslik,
                "body": govde,
                "href": href,
            })
            if len(sonuclar) >= max_results:
                break

        return sonuclar
    except Exception:
        return []


# =========================================================
# İNTERNET
# =========================================================

def internette_ara(soru):
    if not INTERNET_AKTIF:
        return None

    # Eski HTML/snippet yolu devre dışı; tüm çağrılar kanonik yapılandırılmış motora gider.
    try:
        from netops_one_engine import get_engine
        result = get_engine(
            project_dir=os.path.dirname(os.path.abspath(__file__)),
            internet_enabled=internet_aktif_mi,
            max_sources=3,
        ).search_web(str(soru or ""))
        if result.ok and result.text:
            return result.text
        return None
    except Exception:
        return None

    try:
        sorgu = arama_sorgusu_hazirla(soru)

        # NetOps Browser tool katmani: API kullanmadan mevcut browser'i gorunur sekilde kullanir.
        try:
            import browser_engine
            browser_sonuc = browser_engine.web_search(sorgu, max_sources=3, visible=False)
            if isinstance(browser_sonuc, dict) and browser_sonuc.get("ok") and browser_sonuc.get("text"):
                bilgi = str(browser_sonuc.get("text") or "").strip()
                kaynaklar = browser_sonuc.get("sources") or []
                ana = kaynaklar[0] if kaynaklar and isinstance(kaynaklar[0], dict) else {}
                SON_BILGI["internet"] = bilgi
                SON_BILGI["baslik"] = ana.get("title") or "Web arama sonucu"
                SON_BILGI["govde"] = str(ana.get("text") or bilgi)[:900]
                SON_BILGI["kaynak"] = ana.get("url") or browser_sonuc.get("search_url") or ""
                SON_BILGI["zaman"] = time.time()
                return bilgi
        except Exception as browser_exc:
            print("BROWSER TOOL ARAMA HATASI:", browser_exc)

        sonuclar = []

        if DDG_AKTIF and DDGS is not None:
            try:
                with DDGS() as ddgs:
                    sonuclar = list(
                        ddgs.text(
                            sorgu,
                            region="tr-tr",
                            max_results=8
                        )
                    )
            except Exception:
                sonuclar = []

        if not sonuclar:
            sonuclar = _duckduckgo_html_sonuclari(sorgu, max_results=8)

        if not sonuclar:
            return None

        secilenler = []

        for s in sonuclar:
            baslik = s.get("title", "").strip()
            govde = s.get("body", "").strip()
            kaynak = s.get("href", "").strip()

            if not sonuc_kaliteli_mi(baslik, govde):
                continue

            if sonuc_kategori_sayfasi_mi(baslik, govde, kaynak):
                continue

            secilenler.append({
                "baslik": baslik,
                "govde": govde,
                "kaynak": kaynak
            })

            if len(secilenler) >= 3:
                break

        if not secilenler:
            for s in sonuclar:
                baslik = s.get("title", "").strip()
                govde = s.get("body", "").strip()
                kaynak = s.get("href", "").strip()

                if sonuc_kaliteli_mi(baslik, govde):
                    secilenler.append({
                        "baslik": baslik,
                        "govde": govde,
                        "kaynak": kaynak
                    })

                if len(secilenler) >= 3:
                    break

        if not secilenler:
            return None

        ana = secilenler[0]

        metinler = []

        for i, sonuc in enumerate(secilenler, start=1):
            metinler.append(
                f"{i}) {sonuc['baslik']}\n"
                f"{sonuc['govde']}\n"
                f"Kaynak: {sonuc['kaynak']}"
            )

        bilgi = "\n\n".join(metinler)

        SON_BILGI["internet"] = bilgi
        SON_BILGI["baslik"] = ana["baslik"]
        SON_BILGI["govde"] = ana["govde"]
        SON_BILGI["kaynak"] = ana["kaynak"]
        SON_BILGI["zaman"] = time.time()

        return bilgi

    except Exception as e:
        print("İNTERNET ARAMA HATASI:", e)
        return None


# =========================================================
# MODEL TEMİZLEME
# =========================================================

def model_cevabini_temizle(cevap):
    if not cevap:
        return None

    cevap = str(cevap).strip()

    if "</think>" in cevap:
        cevap = cevap.split("</think>")[-1].strip()

    # Teknik etiketleri ve komut tokenlarını kullanıcıya gösterme.
    temizlenecekler = [
        "NetOps Agent K1:",
        "NetOps Agent K2:",
        "NetOps Agent:",
        "Kullanıcı:",
        "Asistan:",
        "Assistant:",
        "__KOMUT__:",
        "__SES__:",
        "__HESAPLA__:",
        "__HAVA__:"
    ]

    for parca in temizlenecekler:
        cevap = cevap.replace(parca, "")

    # Tekrarlı satırları temizle.
    satirlar = []
    gorulen = set()
    for satir in cevap.splitlines():
        s = satir.strip()
        if not s:
            continue
        anahtar = s.lower()
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        satirlar.append(s)

    cevap = "\n".join(satirlar).strip()

    if not cevap:
        return None

    return cevap


# =========================
# NETO AGENT MODEL PROFİLLERİ
# =========================

AKTIF_KEVRA_MODELI = "NetOps Agent K1"

KEVRA_MODELLERI = {
    "NetOps Agent K1": {
        "kimlik": "NetOps Agent K1",
                "temperature": 0.12,
        "top_p": 0.82,
        "num_ctx": 1536,
        "num_predict_kisa": 150,
        "num_predict_uzun": 280,
        "stil": """
NetOps Agent K1 modu:
- Hızlı, kısa ve net cevap ver.
- Gereksiz uzatma.
- Günlük kullanım ve komut odaklı çalış.
"""
    },

    "NetOps Agent K2": {
        "kimlik": "NetOps Agent K2",
                "temperature": 0.18,
        "top_p": 0.86,
        "num_ctx": 3072,
        "num_predict_kisa": 190,
        "num_predict_uzun": 380,
        "stil": """
NetOps Agent K2 modu:
- Daha detaylı ve daha akıllı cevap ver.
- Haber, gündem, analiz ve araştırma sorularında daha kapsamlı ol.
- Gerekirse maddeli anlat.
- Bilmediğin konuda uydurma.
"""
    }
}


def _normalize_model_name(model_adi):
    return AGENT_MODEL_ALIASES.get(model_adi, model_adi)


def aktif_model_ayari_al():
    model_adi = _normalize_model_name(AKTIF_KEVRA_MODELI)

    if model_adi not in KEVRA_MODELLERI:
        model_adi = "NetOps Agent K1"

    return KEVRA_MODELLERI[model_adi]


def aktif_modeli_ayarla(model_adi):
    global AKTIF_KEVRA_MODELI

    model_adi = _normalize_model_name(model_adi)
    if model_adi in KEVRA_MODELLERI:
        AKTIF_KEVRA_MODELI = model_adi

    return AKTIF_KEVRA_MODELI


def aktif_modeli_getir():
    return AKTIF_KEVRA_MODELI


def modele_sor(mesaj, internet_bilgisi=None, cevap_modu="kisa", agent_modu=False):
    """İnternet tabanlı yanıt üretir; model kullanmaz."""

    if internet_bilgisi is None and internet_aktif_mi() and _internet_sohbet_uygun_mu(mesaj):
        try:
            internet_bilgisi = internette_ara(mesaj)
        except Exception:
            internet_bilgisi = None

    if internet_bilgisi:
        ozet = _yerel_internet_ozeti(
            internet_bilgisi,
            cevap_modu=cevap_modu,
        )
        if ozet:
            return ozet

    return _yerel_ai_cevabi_uret(
        mesaj,
        internet_bilgisi=None,
        cevap_modu=cevap_modu,
        agent_modu=agent_modu,
    )

    if not AI_MODEL_AKTIF:
        return _yerel_ai_cevabi_uret(
            mesaj,
            internet_bilgisi=internet_bilgisi,
            cevap_modu=cevap_modu,
            agent_modu=agent_modu,
        )

    if not ollama_var_mi():
        return _yerel_ai_cevabi_uret(
            mesaj,
            internet_bilgisi=internet_bilgisi,
            cevap_modu=cevap_modu,
            agent_modu=agent_modu,
        )

    profil = aktif_model_ayari_al()

    kimlik_adi = profil.get("kimlik", "NetOps Agent K1")
    temperature = profil.get("temperature", 0.10)
    top_p = profil.get("top_p", 0.75)
    num_ctx = profil.get("num_ctx", 768)

    if cevap_modu == "uzun":
        num_predict = profil.get("num_predict_uzun", 160)
        timeout = MODEL_TIMEOUT_UZUN
        cevap_kurali = """
Cevap biçimi:
- Gerekirse 2-3 kısa paragraf yaz.
- Haber/gündem okuyorsan maddeli şekilde 2-4 sonucu ver.
- Fiyat/kurlar sorulursa bulunan bilgiyi kısa ve net özetle.
- En fazla 10-12 cümle yaz.
- Cevabı yarıda kesme.
- Elinde bilgi yoksa uydurma.
"""
    else:
        num_predict = profil.get("num_predict_kisa", 80)
        timeout = MODEL_TIMEOUT_KISA
        cevap_kurali = """
Cevap biçimi:
- Kısa ama tam cevap ver.
- En fazla 3-5 kısa cümle yaz.
- Cümleyi yarıda kesme.
- Gereksiz açıklama yapma.
"""

    ek_bilgi = ""

    if internet_bilgisi:
        ek_bilgi = f"""
GÜNCEL BİLGİ:
{internet_bilgisi}

Kural:
- Bu güncel bilgi verilmişse sadece buna dayan.
- Verilmeyen ayrıntıları uydurma.
- Birden fazla sonuç varsa hepsini kısa özetle.
"""

    if agent_modu:
        agent_kurali = """
Agent modu:
- Sadece sohbet et, uygulama açma komutu üretme.
- Türkçe, doğal ve güven verici konuş.
- Karar verirken kısa ama net ol.
- Belirsiz isteklerde tek bir netleştirme sorusu sor.
- Teknik tokenlar, __KOMUT__ benzeri işaretler ve launcher çıktıları yazma.
"""
    else:
        agent_kurali = ""

    if get_lang() == "en":
        dil_kurali = """
Language rule:
- Always answer in Turkish.
- If the user writes another language, still reply only in Turkish.
- Do not mix English into the answer unless the user explicitly asks for translation.
"""
    else:
        dil_kurali = """
Dil kuralı:
- Her zaman Türkçe cevap ver.
- Kullanıcı başka dilde yazsa bile yalnızca Türkçe cevap ver.
- İngilizce karıştırma.
"""

    karar_kurali = """
Karar mantığı:
- Önce niyeti ayır: sohbet, bilgi, eylem, güvenlik veya netleştirme.
- İstek belirsizse varsayım yapma, tek ve kısa bir netleştirme sorusu sor.
- Bir seçenek soruluyorsa en uygun olanı seç ve kısa bir gerekçe ver.
- Riskli, kararsız veya yanlış yönlendirecek işlerde temkinli davran.
- Kullanıcı açık karar istiyorsa kararlı bir cevap ver, ama uydurma yapma.
"""

    prompt = f"""
Senin adın {kimlik_adi}.
Seni NetOps geliştirdi.

Kimlik:
- NetOps One Engine çizgisinde çalışan sentetik masaüstü kontrol motorusun.
- Türkçe konuşursun.
- Kendini Gemma veya başka model olarak tanıtmazsın.
- Kendini sadece {kimlik_adi} olarak tanıtırsın.

{profil.get("stil", "")}

{dil_kurali}

{agent_kurali}

{karar_kurali}

Davranış:
- Kısa, teknik, doğrudan ve sentetik cevap ver.
- Cevabı yarıda bırakma; başladığın cümleyi tamamla.
- Bilmediğin konuda uydurma, tahmin yapıyorsan bunu açıkça belirt.
- Elinde bilgi yoksa kısa şekilde "Bunu kesin bilmiyorum." de.
- Aynı cümleleri tekrar etme.
- Nezaket dolgusu, gereksiz uzun giriş ve duygusal ifade kullanma.
- Komut çıktısı istenmediyse __KOMUT__ gibi özel işaret yazma.
- Kaba, saldırgan, aşağılayıcı veya hakaret içeren dil kullanma.
- Kullanıcı kaba konuşursa sakin kal, küfürü tekrar etme ve kibarca sınır koy.

{cevap_kurali}

{ek_bilgi}

Kullanıcı: {mesaj}

{kimlik_adi}:
"""

    try:
        r = requests.post(
            AI_URL,
            json={
                "model": AI_MODEL_ADI,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "top_p": top_p,
                    "num_ctx": num_ctx,
                    "num_predict": num_predict,
                    "num_thread": 6,
                    "repeat_penalty": 1.12,
                    "stop": ["\nKullanıcı:", "\nUser:", "\nAssistant:", "\nAsistan:"]
                }
            },
            timeout=timeout
        )

        if r.status_code != 200:
            return _yerel_ai_cevabi_uret(
                mesaj,
                internet_bilgisi=internet_bilgisi,
                cevap_modu=cevap_modu,
                agent_modu=agent_modu,
            )

        cevap = r.json().get("response", "")
        temiz = model_cevabini_temizle(cevap)

        if temiz:
            return temiz

        return _yerel_ai_cevabi_uret(
            mesaj,
            internet_bilgisi=internet_bilgisi,
            cevap_modu=cevap_modu,
            agent_modu=agent_modu,
        )

    except requests.exceptions.Timeout:
        # Sanal makinelerde veya ilk çalıştırmada Gemma geç ısınabilir.
        # Bu durumda daha hafif ayarlarla bir kez daha dener.
        try:
            r = requests.post(
                AI_URL,
                json={
                    "model": AI_MODEL_ADI,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.10,
                        "top_p": 0.75,
                        "num_ctx": 1024,
                        "num_predict": 120,
                        "num_thread": 4,
                        "repeat_penalty": 1.12,
                        "stop": ["\nKullanıcı:", "\nUser:", "\nAssistant:", "\nAsistan:"]
                    }
                },
                timeout=180
            )

            if r.status_code == 200:
                cevap = r.json().get("response", "")
                temiz = model_cevabini_temizle(cevap)
                if temiz:
                    return temiz

        except Exception:
            pass

        return _yerel_ai_cevabi_uret(
            mesaj,
            internet_bilgisi=internet_bilgisi,
            cevap_modu=cevap_modu,
            agent_modu=agent_modu,
        )

    except Exception as e:
        return _yerel_ai_cevabi_uret(
            mesaj,
            internet_bilgisi=internet_bilgisi,
            cevap_modu=cevap_modu,
            agent_modu=agent_modu,
        )

# =========================================================
# RESİM ANALİZİ / VISION
# =========================================================
def neto_ai_resim_analiz_et(soru, resim_yolu):
    if not resim_yolu or not os.path.exists(resim_yolu):
        return "Resim dosyası bulunamadı."

    return _yerel_dual(
        "Görsel analiz için şu an web tabanlı bir vision motoru bağlı değil. İstersen resmi kısaca tarif et, ben yorumlayayım.",
        "There is no web-based vision engine connected for image analysis right now. If you describe the image briefly, I can help."
    )

    try:
        with open(resim_yolu, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        return f"Resim okunamadı: {e}"

    profil = aktif_model_ayari_al()
    kimlik_adi = profil.get("kimlik", "NetOps Agent K1")

    prompt = f"""
Senin adın {kimlik_adi}.
Türkçe cevap ver.
Kullanıcının yüklediği resmi analiz et.
Resimde gerçekten ne görüyorsan onu söyle.
Emin olmadığın şeyi kesinmiş gibi söyleme.

Kullanıcının isteği:
{soru if soru else "Bu resmi analiz et."}

{kimlik_adi}:
"""

    try:
        r = requests.post(
            AI_URL,
            json={
                "model": AI_MODEL_ADI,
                "prompt": prompt,
                "stream": False,
                "images": [img_b64],
                "options": {
                    "temperature": 0.10,
                    "top_p": 0.80,
                    "num_ctx": 3072,
                    "num_predict": 360,
                    "num_thread": 6,
                    "repeat_penalty": 1.10
                }
            },
            timeout=MODEL_TIMEOUT_UZUN
        )

        if r.status_code != 200:
            return f"Resim analizi yapılamadı. Hata kodu: {r.status_code}\nModel görsel desteklemiyor olabilir."

        temiz = model_cevabini_temizle(r.json().get("response", ""))
        return temiz if temiz else "Resim analizi boş cevap verdi."

    except Exception as e:
        return f"Resim analizi hatası: {e}"

# =========================================================
# ÖZEL KOMUTLAR
# =========================================================

def ozel_ses_komutu(metin):
    if "ses" not in metin:
        return None

    if not any(
        k in metin
        for k in ["aç", "kıs", "artır", "azalt", "yap", "ayarla"]
    ):
        return None

    sayilar = re.findall(r"\d+", metin)

    if sayilar:
        oran = int(sayilar[0])
        oran = max(0, min(100, oran))

        return f"__SES__:{oran}"

    return None


def hesaplama_komutu(metin):
    if "hesapla" not in metin:
        return None

    islem = metin.replace("hesapla", "", 1).strip()

    if not islem:
        return None

    return f"__HESAPLA__:{islem}"


def hava_komutu(metin):
    if "hava" not in metin:
        return None

    sehir = metin
    sehir = sehir.replace("hava durumu", "")
    sehir = sehir.replace("hava nasıl", "")
    sehir = sehir.replace("hava", "")
    sehir = sehir.strip()

    if not sehir:
        sehir = "İstanbul"

    return f"__HAVA__:{sehir}"


def komut_ara(metin):
    if metin in KOMUTLAR:
        komut = KOMUTLAR[metin]

        if komut.startswith("__"):
            return komut

        return f"__KOMUT__:{komut}"

    bilgi_kelimeleri = [
        "nedir",
        "ne demek",
        "nasıl",
        "kimdir",
        "kaç",
        "neden",
        "ne işe yarar"
    ]

    for anahtar, komut in KOMUTLAR.items():
        if len(anahtar) < 4:
            continue

        if anahtar in metin:
            if any(k in metin for k in bilgi_kelimeleri):
                continue

            if komut.startswith("__"):
                return komut

            return f"__KOMUT__:{komut}"

    yakin_komut = difflib.get_close_matches(
        metin,
        KOMUTLAR.keys(),
        n=1,
        cutoff=0.78
    )

    if yakin_komut:
        if any(k in metin for k in bilgi_kelimeleri):
            return None

        komut = KOMUTLAR[yakin_komut[0]]

        if komut.startswith("__"):
            return komut

        return f"__KOMUT__:{komut}"

    return None


def sohbet_ara(metin):
    for anahtar, cevaplar in SOHBET.items():
        if anahtar in metin:
            secilen = random.choice(cevaplar)
            return T(secilen) if isinstance(secilen, str) and secilen.startswith("ai_") else secilen

    return None


def kimlik_cevabi_ara(metin):
    model_adi = aktif_modeli_getir()

    model_sorulari = (
        "model adı",
        "model adi",
        "hangi modelsin",
        "sen hangi modelsin",
        "kevra sürümü",
        "kevra surumu",
        "kevra kaç",
        "kevra kac",
        "sen şuan kevra kaçsın",
        "sen suan kevra kacsin",
        "adı ne",
        "adi ne",
        "adın ne",
        "adin ne",
        "ismin ne"
    )

    yapimci_sorulari = (
        "seni kim yaptı",
        "seni kim yapti",
        "kim yaptı",
        "kim yapti",
        "geliştiricin kim",
        "gelistiricin kim",
        "yapımcın kim",
        "yapimcin kim"
    )

    if metin in model_sorulari:
        return f"Ben {model_adi} olarak çalışıyorum."

    if metin in yapimci_sorulari:
        return "Beni NetOps geliştirdi."

    return None


# =========================================================
# ANA CEVAP FONKSİYONU
# =========================================================

_RAW_TRANSLATION_KEY_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$")
_SAFE_ANSWER_FALLBACK = (
    "Bu isteği işlerken güvenilir bir yanıt oluşturamadım. "
    "Konuyu daha kısa veya daha belirgin kelimelerle tekrar deneyebilir misin?"
)


def neto_ai_cevap_metnini_temizle(cevap):
    """Return one display-safe answer for every NetOps conversation surface."""
    text = str(cevap or "").strip()
    if not text:
        return _SAFE_ANSWER_FALLBACK

    # Older fallback routes can return language dictionary keys directly.
    # Resolve them when possible and never expose an implementation key to UI.
    if _RAW_TRANSLATION_KEY_RE.fullmatch(text):
        try:
            translated = str(T(text) or "").strip()
        except Exception:
            translated = ""
        text = translated if translated and translated != text else _SAFE_ANSWER_FALLBACK

    return text


def neto_ai_cevap_sonucu(soru, agent_modu=False):
    """Run the canonical Harbilig engine and retain safe reply metadata."""
    metin = metin_temizle(soru)

    if not metin:
        return {"text": "Bir şey yazmadın.", "intent": "empty", "source": "local"}

    try:
        from netops_one_engine import get_engine
        engine = get_engine(
            project_dir=os.path.dirname(os.path.abspath(__file__)),
            command_detector=(None if agent_modu else komut_ara),
            internet_enabled=internet_aktif_mi,
            max_sources=3,
        )
        sonuc = engine.answer(soru, agent_mode=agent_modu)
        if sonuc.intent == "automation_draft":
            SON_BILGI["automation_draft"] = getattr(sonuc, "metadata", None)
        else:
            SON_BILGI["automation_draft"] = None
        if sonuc.intent in {"web_search", "location_search", "location_data", "location_context"} and sonuc.text:
            SON_BILGI["internet"] = sonuc.text
            SON_BILGI["baslik"] = "NetOps Harbilig web sonucu"
            SON_BILGI["govde"] = sonuc.text[:900]
            SON_BILGI["kaynak"] = sonuc.source
            SON_BILGI["zaman"] = time.time()
        if sonuc.text:
            return {
                "text": neto_ai_cevap_metnini_temizle(sonuc.text),
                "intent": str(getattr(sonuc, "intent", "reply") or "reply"),
                "source": str(getattr(sonuc, "source", "netops_harbilig") or "netops_harbilig"),
                "cached": bool(getattr(sonuc, "cached", False)),
                "learned": bool(getattr(sonuc, "learned", False)),
            }
    except Exception as one_exc:
        try:
            print("NETOPS HARBILIG HATASI:", one_exc)
        except Exception:
            pass

    # If the canonical engine cannot load, retain a small local fallback
    # rather than switching a different model or exposing internal keys.
    sohbet = sohbet_ara(metin)
    if sohbet:
        return {"text": neto_ai_cevap_metnini_temizle(sohbet), "intent": "local_fallback", "source": "local"}

    bilgi = bilgi_hafizasinda_ara(metin)
    if bilgi:
        return {"text": neto_ai_cevap_metnini_temizle(bilgi), "intent": "memory_fallback", "source": "local"}

    return {"text": _SAFE_ANSWER_FALLBACK, "intent": "fallback", "source": "local"}


def _neto_ai_cevap_ver_core(soru, agent_modu=False):
    """Legacy string API backed by the canonical structured response."""
    return str(neto_ai_cevap_sonucu(soru, agent_modu=agent_modu).get("text") or _SAFE_ANSWER_FALLBACK)


def son_automation_draft():
    """Return the latest chat draft for the UI's explicit confirmation flow."""
    value = SON_BILGI.get("automation_draft")
    return value.copy() if isinstance(value, dict) else None


# Dil zorlayıcı dış fonksiyon
def neto_ai_cevap_ver(soru, agent_modu=False):
    response = _neto_ai_cevap_ver_core(soru, agent_modu=agent_modu)
    return neto_ai_cevap_metnini_temizle(_ai_dil_cevir(response))









