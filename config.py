# config.py
import os
import sys

try:
    from neto_version import APP_VERSION as _NETO_VERSION
except Exception:
    _NETO_VERSION = "1.52.0"

try:
    from neto_fluent_design import FLUENT_DARK as FLUENT_DARK_PALET, FLUENT_LIGHT as FLUENT_LIGHT_PALET
except Exception:
    FLUENT_DARK_PALET = {}
    FLUENT_LIGHT_PALET = {}

# ------------------------------------------------------------
# 1. Dizin Yolları ve Yardımcı Fonksiyonlar
# ------------------------------------------------------------
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
    MEIPASS_DIR = getattr(sys, "_MEIPASS", BASE_DIR)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    MEIPASS_DIR = BASE_DIR

ASSET_DIR = MEIPASS_DIR


def get_asset_path(filename):
    """PyInstaller EXE içinde ve EXE yanındaki dosyalarda asset arar.

    Öncelik:
    1) PyInstaller tek dosya geçici klasörü: sys._MEIPASS
    2) EXE'nin bulunduğu klasör
    3) Çalışma klasörü
    Böylece hem --add-data ile gömülü dosyalar hem de EXE yanında duran
    Logo.png / yukleme.gif / ses dosyaları düzgün bulunur.
    """
    filename = str(filename)

    adaylar = []

    bundle_dir = getattr(sys, "_MEIPASS", None)
    if getattr(sys, "frozen", False) and bundle_dir:
        adaylar.append(os.path.join(bundle_dir, filename))

    adaylar.append(os.path.join(BASE_DIR, filename))
    adaylar.append(os.path.join(os.getcwd(), filename))

    # Alt klasör ihtimali için birkaç güvenli ek yol
    for klasor in ("assets", "static", "Templates", "temalar"):
        adaylar.append(os.path.join(BASE_DIR, klasor, filename))
        if getattr(sys, "frozen", False) and bundle_dir:
            adaylar.append(os.path.join(bundle_dir, klasor, filename))

    for yol in adaylar:
        if os.path.exists(yol):
            return yol

    # Bulunamazsa varsayılan olarak PyInstaller içindeki beklenen yolu döndür.
    # Kodun os.path.exists kontrolü zaten fallback yapıyor.
    if getattr(sys, "frozen", False) and bundle_dir:
        return os.path.join(bundle_dir, filename)

    return os.path.join(BASE_DIR, filename)


def get_user_data_dir():
    """Return the stable user data root used by settings, logs, and caches."""
    if getattr(sys, "frozen", False):
        appdata = os.getenv("APPDATA") or BASE_DIR
        base_dir = os.path.join(appdata, "NetoAsistan")
    else:
        base_dir = BASE_DIR

    if not os.path.exists(base_dir):
        try:
            os.makedirs(base_dir, exist_ok=True)
        except Exception:
            base_dir = BASE_DIR

    return base_dir


def get_data_path(filename):
    """Kullanıcı verilerini EXE içine değil APPDATA/NetoAsistan içine yazar."""
    base_dir = get_user_data_dir()
    return os.path.join(base_dir, filename)


def get_first_asset_path(*filenames):
    """İlk var olan asset yolunu döndürür. EXE ve .py modunda çalışır."""
    for name in filenames:
        try:
            yol = get_asset_path(name)
            if os.path.exists(yol):
                return yol
        except Exception:
            pass
    return get_asset_path(filenames[0]) if filenames else BASE_DIR

# ------------------------------------------------------------
# 2. Önemli Dosya Yolları
# ------------------------------------------------------------
FILE_PATH = get_data_path("hafiza.json")
LOGO_PATH = get_first_asset_path(
    "NetoAsistan.png",
    "Logo.png",
    "neto_default_logo_v12.png",
    "neto_brand_logo.png",
    "neto_logo.png",
    "fallback_logo.png",
    "neto_titlebar_logo.png",
    "yukleme.gif",
    "Neto.gif",
    "kevra.png",
    "kevr.png",
    "Logo.ico",
)
ICO_PATH = get_first_asset_path(
    "NetoAsistan.ico",
    "neto_titlebar_logo.ico",
    "Logo.ico",
    "neto_default_logo_v12.ico",
    "neto.ico",
    "neto_asistan.ico",
    "kevra.ico",
    "kevr.ico",
    "Logo.png",
)
GIF_PATH = get_first_asset_path("yukleme.gif", "Neto.gif", "Logo.png", "kevra.png", "kevr.png", "Logo.ico")
START_SOUND_DEFAULT = get_asset_path("freesound_community-start-computeraif-14572.mp3")
DONE_SOUND = get_asset_path("Done.mp3")
ERROR_SOUND = get_asset_path("Error.mp3")
LIVE_OPEN_SOUND = get_asset_path("denielcz-done-463074.mp3")

# ------------------------------------------------------------
# 3. Tarayıcı User-Agent (EKSİKTİ)
# ------------------------------------------------------------
CHROME_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

# ------------------------------------------------------------
# 4. Geçerli Renk Temaları
# ------------------------------------------------------------
VALID_COLOR_THEMES = ["green", "blue", "dark-blue"]

# ------------------------------------------------------------
# 5. Küfür Listesi (TAM LİSTE)
# ------------------------------------------------------------
KUFUR_LISTESI = [
    "abaza", "abazan", "ag", "ağzına sıçayım", "ahmak", "allah", "allahsız",
    "am", "amarım", "ambiti", "am biti", "amcığı", "amcığın", "amcığını",
    "amcığınızı", "amcık", "amcık hoşafı", "amcıklama", "amcıklandı", "amcik",
    "amck", "amckl", "amcklama", "amcklaryla", "amckta", "amcktan", "amcuk",
    "amık", "amına", "amınako", "amına koy", "amına koyarım", "amına koyayım",
    "amınakoyim", "amına koyyim", "amına s", "amına sikem", "amına sokam",
    "amın feryadı", "amını", "amını s", "amın oglu", "amınoğlu", "amın oğlu",
    "amısına", "amısını", "amina", "amina g", "amina k", "aminako",
    "aminakoyarim", "amina koyarim", "amina koyayım", "amina koyayim",
    "aminakoyim", "aminda", "amindan", "amindayken", "amini", "aminiyarraaniskiim",
    "aminoglu", "amin oglu", "amiyum", "amk", "amkafa", "amk çocuğu",
    "amlarnzn", "amlı", "amm", "ammak", "ammna", "amn", "amna", "amnda",
    "amndaki", "amngtn", "amnn", "amona", "amq", "amsız", "amsiz", "amsz",
    "amteri", "amugaa", "amuğa", "amuna", "ana", "anaaann", "anal", "analarn",
    "anam", "anamla", "anan", "anana", "anandan", "ananı", "ananı ",
    "ananın", "ananın am", "ananın amı", "ananın dölü", "ananınki",
    "ananısikerim", "ananı sikerim", "ananısikeyim", "ananı sikeyim",
    "ananızın", "ananızın am", "anani", "ananin", "ananisikerim",
    "anani sikerim", "ananisikeyim", "anani sikeyim", "anann", "ananz",
    "anas", "anasını", "anasının am", "anası orospu", "anasi", "anasinin",
    "anay", "anayin", "angut", "anneni", "annenin", "annesiz", "anuna",
    "aptal", "aq", "a.q", "a.q.", "aq.", "ass", "atkafası", "atmık",
    "attırdığım", "attrrm", "auzlu", "avrat", "ayklarmalrmsikerim",
    "azdım", "azdır", "azdırıcı", "babaannesi kaşar", "babanı", "babanın",
    "babani", "babası pezevenk", "bacağına sıçayım", "bacına", "bacını",
    "bacının", "bacini", "bacn", "bacndan", "bacy", "bastard", "basur",
    "beyinsiz", "bızır", "bitch", "biting", "bok", "boka", "bokbok",
    "bokça", "bokhu", "bokkkumu", "boklar", "boktan", "boku", "bokubokuna",
    "bokum", "bombok", "boner", "bosalmak", "boşalmak", "cenabet",
    "cibiliyetsiz", "cibilliyetini", "cibilliyetsiz", "cif", "cikar",
    "cim", "çük", "dalaksız", "dallama", "daltassak", "dalyarak", "dalyarrak",
    "dangalak", "dassagi", "diktim", "dildo", "dingil", "dingilini",
    "dinsiz", "dkerim", "domal", "domalan", "domaldı", "domaldın",
    "domalık", "domalıyor", "domalmak", "domalmış", "domalsın", "domalt",
    "domaltarak", "domaltıp", "domaltır", "domaltırım", "domaltip",
    "domaltmak", "dölü", "dönek", "düdük", "eben", "ebeni", "ebenin",
    "ebeninki", "ebleh", "ecdadını", "ecdadini", "embesil", "emi",
    "fahise", "fahişe", "feriştah", "ferre", "fuck", "fucker", "fuckin",
    "fucking", "gavad", "gavat", "geber", "geberik", "gebermek", "gebermiş",
    "gebertir", "gerızekalı", "gerizekalı", "gerizekali", "gerzek",
    "giberim", "giberler", "gibis", "gibiş", "gibmek", "gibtiler",
    "goddamn", "godoş", "godumun", "gotelek", "gotlalesi", "gotlu",
    "gotten", "gotundeki", "gotunden", "gotune", "gotunu", "gotveren",
    "goyiim", "goyum", "goyuyim", "goyyim", "göt", "göt deliği",
    "götelek", "göt herif", "götlalesi", "götlek", "götoğlanı",
    "göt oğlanı", "götoş", "götten", "götü", "götün", "götüne",
    "götünekoyim", "götüne koyim", "götünü", "götveren", "göt veren",
    "göt verir", "gtelek", "gtn", "gtnde", "gtnden", "gtne", "gtten",
    "gtveren", "hasiktir", "hassikome", "hassiktir", "has siktir",
    "hassittir", "haysiyetsiz", "hayvan herif", "hoşafı", "hödük",
    "hsktr", "huur", "ıbnelık", "ibina", "ibine", "ibinenin", "ibne",
    "ibnedir", "ibneleri", "ibnelik", "ibnelri", "ibneni", "ibnenin",
    "ibnerator", "ibnesi", "idiot", "idiyot", "imansz", "ipne", "iserim",
    "işerim", "itoğlu it", "kafam girsin", "kafasız", "kafasiz", "kahpe",
    "kahpenin", "kahpenin feryadı", "kaka", "kaltak", "kancık", "kancik",
    "kappe", "karhane", "kaşar", "kavat", "kavatn", "kaypak", "kayyum",
    "kerane", "kerhane", "kerhanelerde", "kevase", "kevaşe", "kevvase",
    "koca göt", "koduğmun", "koduğmunun", "kodumun", "kodumunun",
    "koduumun", "koyarm", "koyayım", "koyiim", "koyiiym", "koyim",
    "koyum", "koyyim", "krar", "kukudaym", "laciye boyadım", "lavuk",
    "liboş", "madafaka", "mal", "malafat", "malak", "manyak", "mcik",
    "meme", "memelerini", "mezveleli", "minaamcık", "mincikliyim", "mna",
    "monakkoluyum", "motherfucker", "mudik", "oc", "ocuu", "ocuun",
    "OÇ", "oç", "o. çocuğu", "oğlan", "oğlancı", "oğlu it",
    "orosbucocuu", "orospu", "orospucocugu", "orospu cocugu",
    "orospu çoc", "orospuçocuğu", "orospu çocuğu", "orospu çocuğudur",
    "orospu çocukları", "orospudur", "orospular", "orospunun",
    "orospunun evladı", "orospuydu", "orospuyuz", "orostoban",
    "orostopol", "orrospu", "oruspu", "oruspuçocuğu", "oruspu çocuğu",
    "osbir", "ossurduum", "ossurmak", "ossuruk", "osur", "osurduu",
    "osuruk", "osururum", "otuzbir", "öküz", "öşex", "patlak zar",
    "penis", "pezevek", "pezeven", "pezeveng", "pezevengi",
    "pezevengin evladı", "pezevenk", "pezo", "pic", "pici", "picler",
    "piç", "piçin oğlu", "piç kurusu", "piçler", "pipi", "pipiş",
    "pisliktir", "porno", "pussy", "puşt", "puşttur", "rahminde",
    "revizyonist", "s1kerim", "s1kerm", "s1krm", "sakso", "saksofon",
    "salaak", "salak", "saxo", "sekis", "serefsiz", "sevgi koyarım",
    "sevişelim", "sexs", "sıçarım", "sıçtığım", "sıecem", "sicarsin",
    "sie", "sik", "sikdi", "sikdiğim", "sike", "sikecem", "sikem",
    "siken", "sikenin", "siker", "sikerim", "sikerler", "sikersin",
    "sikertir", "sikertmek", "sikesen", "sikesicenin", "sikey",
    "sikeydim", "sikeyim", "sikeym", "siki", "sikicem", "sikici",
    "sikien", "sikienler", "sikiiim", "sikiiimmm", "sikiim", "sikiir",
    "sikiirken", "sikik", "sikil", "sikildiini", "sikilesice",
    "sikilmi", "sikilmie", "sikilmis", "sikilmiş", "sikilsin", "sikim",
    "sikimde", "sikimden", "sikime", "sikimi", "sikimiin", "sikimin",
    "sikimle", "sikimsonik", "sikimtrak", "sikin", "sikinde", "sikinden",
    "sikine", "sikini", "sikip", "sikis", "sikisek", "sikisen",
    "sikish", "sikismis", "sikiş", "sikişen", "sikişme", "sikitiin",
    "sikiyim", "sikiym", "sikiyorum", "sikkim", "sikko", "sikleri",
    "sikleriii", "sikli", "sikm", "sikmek", "sikmem", "sikmiler",
    "sikmisligim", "siksem", "sikseydin", "sikseyidin", "siksin",
    "siksinbaya", "siksinler", "siksiz", "siksok", "siksz", "sikt",
    "sikti", "siktigimin", "siktigiminin", "siktiğim", "siktiğimin",
    "siktiğiminin", "siktii", "siktiim", "siktiimin", "siktiiminin",
    "siktiler", "siktim", "siktim ", "siktimin", "siktiminin",
    "siktir", "siktir et", "siktirgit", "siktir git", "siktirir",
    "siktiririm", "siktiriyor", "siktir lan", "siktirolgit",
    "siktir ol git", "sittimin", "sittir", "skcem", "skecem", "skem",
    "sker", "skerim", "skerm", "skeyim", "skiim", "skik", "skim",
    "skime", "skmek", "sksin", "sksn", "sksz", "sktiimin", "sktrr",
    "skyim", "slaleni", "sokam", "sokarım", "sokarim", "sokarm",
    "sokarmkoduumun", "sokayım", "sokaym", "sokiim", "soktuğumunun",
    "sokuk", "sokum", "sokuş", "sokuyum", "soxum", "sulaleni",
    "sülaleni", "sülalenizi", "sürtük", "şerefsiz", "şıllık",
    "taaklarn", "taaklarna", "tarrakimin", "tasak", "tassak", "taşak",
    "taşşak", "tipini s.k", "tipinizi s.keyim", "tiyniyat", "toplarm",
    "topsun", "totoş", "vajina", "vajinanı", "veled", "veledizina",
    "veled i zina", "verdiimin", "weled", "weledizina", "whore",
    "xikeyim", "yaaraaa", "yalama", "yalarım", "yalarun", "yaraaam",
    "yarak", "yaraksız", "yaraktr", "yaram", "yaraminbasi", "yaramn",
    "yararmorospunun", "yarra", "yarraaaa", "yarraak", "yarraam",
    "yarraamı", "yarragi", "yarragimi", "yarragina", "yarragindan",
    "yarragm", "yarrağ", "yarrağım", "yarrağımı", "yarraimin", "yarrak",
    "yarram", "yarramin", "yarraminbaşı", "yarramn", "yarran", "yarrana",
    "yarrrak", "yavak", "yavş", "yavşak", "yavşaktır", "yavuşak",
    "yılışık", "yilisik", "yogurtlayam", "yoğurtlayam", "yrrak",
    "zıkkımım", "zibidi", "zigsin", "zikeyim", "zikiiim", "zikiim",
    "zikik", "zikim", "ziksiiin", "ziksiin", "zulliyetini", "zviyetini"
]

# ------------------------------------------------------------
# 5.1 VPN / Tünel Uygulamaları
# ------------------------------------------------------------
# Bu liste, VPN benzeri arka plan süreçlerini daha güvenli şekilde
# yakalamak için kullanılır. Gerektikçe genişletilebilir.
VPN_TESPIT_LISTESI = [
    {"etiket": "OpenVPN", "ipuclari": ["openvpn", "openvpn-gui", "openvpn-connect"]},
    {"etiket": "WireGuard", "ipuclari": ["wireguard"]},
    {"etiket": "Proton VPN", "ipuclari": ["protonvpn", "proton vpn"]},
    {"etiket": "NordVPN", "ipuclari": ["nordvpn"]},
    {"etiket": "Surfshark", "ipuclari": ["surfshark"]},
    {"etiket": "ExpressVPN", "ipuclari": ["expressvpn"]},
    {"etiket": "Windscribe", "ipuclari": ["windscribe"]},
    {"etiket": "CyberGhost", "ipuclari": ["cyberghost"]},
    {"etiket": "TunnelBear", "ipuclari": ["tunnelbear"]},
    {"etiket": "Cloudflare WARP", "ipuclari": ["warp-svc", "cloudflare warp", "cloudflarewarp"]},
    {"etiket": "Tailscale", "ipuclari": ["tailscale"]},
    {"etiket": "ZeroTier", "ipuclari": ["zerotier", "zerotier-one"]},
    {"etiket": "FortiClient", "ipuclari": ["forticlient"]},
    {"etiket": "AnyConnect", "ipuclari": ["anyconnect", "vpnagent", "vpnui"]},
    {"etiket": "GlobalProtect", "ipuclari": ["globalprotect", "pan gp", "pangpui"]},
    {"etiket": "SoftEther", "ipuclari": ["softether"]},
]

# NetOps sürümünde VPN koruma katmanı kapalı tutuluyor.
VPN_KORUMA_AKTIF = False

# ------------------------------------------------------------
# 6. Renk Paletleri (Tema Motoru İçin)
# ------------------------------------------------------------
DARK_PALET = {
    "bg": "#050505", "sidebar": "#0d0d0d", "card": "#1a1a1a",
    "neon": "#ffffff", "text_main": "#FFFFFF", "text_dim": "#888888",
    "entry_bg": "#0a0a0a", "entry_border": "#ffffff",
    "button_fg": "#1a1a1a", "button_hover": "#2b2b2b", "button_text": "#FFFFFF"
}
LIGHT_PALET = {
    "bg": "#f5f5f5", "sidebar": "#ffffff", "card": "#e8e8e8",
    "neon": "#1a1a1a", "text_main": "#000000", "text_dim": "#444444",
    "entry_bg": "#ffffff", "entry_border": "#1a1a1a",
    "button_fg": "#e0e0e0", "button_hover": "#cccccc", "button_text": "#000000"
}

VALID_SURFACE_STYLES = ["fluent", "classic", "liquid-glass", "experians", "experians3", "zenkamind"]

# ZenkaMind esintili çalışma alanı: siyaha yakın grafit yüzeyler, ince
# ayırıcılar ve tek bir elektrik mavisi vurgu. Mevcut görünümler korunur.
ZENKAMIND_DARK_PALET = {
    "bg": "#0B0D10",
    "sidebar": "#101318",
    "card": "#181C23",
    "neon": "#5B8CFF",
    "text_main": "#F4F7FC",
    "text_dim": "#8D97A8",
    "entry_bg": "#141820",
    "entry_border": "#2B3442",
    "button_fg": "#1B212B",
    "button_hover": "#252E3C",
    "button_text": "#F4F7FC",
}

ZENKAMIND_LIGHT_PALET = {
    "bg": "#F4F6FA",
    "sidebar": "#FFFFFF",
    "card": "#FFFFFF",
    "neon": "#316FEA",
    "text_main": "#172033",
    "text_dim": "#667085",
    "entry_bg": "#F8FAFD",
    "entry_border": "#D5DCE8",
    "button_fg": "#EEF3FB",
    "button_hover": "#E1E9F6",
    "button_text": "#172033",
}

LIQUID_GLASS_DARK_PALET = {
    "bg": "#07131B",
    "sidebar": "#0A1A26",
    "card": "#10283A",
    "neon": "#38BDF8",
    "text_main": "#F7FAFF",
    "text_dim": "#A8D5E8",
    "entry_bg": "#0B1F2D",
    "entry_border": "#4BBDEB",
    "button_fg": "#123044",
    "button_hover": "#18425E",
    "button_text": "#F7FAFF",
}

LIQUID_GLASS_LIGHT_PALET = {
    "bg": "#EAF8FF",
    "sidebar": "#F6FCFF",
    "card": "#FFFFFF",
    "neon": "#0EA5E9",
    "text_main": "#0B2239",
    "text_dim": "#486B82",
    "entry_bg": "#F2FBFF",
    "entry_border": "#9BDCF8",
    "button_fg": "#DFF5FF",
    "button_hover": "#CCEEFF",
    "button_text": "#10203A",
}

EXPERIANS_DARK_PALET = {
    "bg": "#0B1220",
    "sidebar": "#111827",
    "card": "#172033",
    "neon": "#3B82F6",
    "text_main": "#F8FAFC",
    "text_dim": "#AAB6CF",
    "entry_bg": "#101827",
    "entry_border": "#2E405F",
    "button_fg": "#1E293B",
    "button_hover": "#26364F",
    "button_text": "#F7FAFF",
}

EXPERIANS_LIGHT_PALET = {
    "bg": "#EEF3FB",
    "sidebar": "#F8FAFF",
    "card": "#FFFFFF",
    "neon": "#2F6BFF",
    "text_main": "#101828",
    "text_dim": "#667085",
    "entry_bg": "#F5F8FF",
    "entry_border": "#CED8EF",
    "button_fg": "#E9EFFC",
    "button_hover": "#DDE7FA",
    "button_text": "#101828",
}

EXPERIANS3_DARK_PALET = {
    "bg": "#0F1116",
    "sidebar": "#121419",
    "card": "#171A21",
    "neon": "#5B8CFF",
    "text_main": "#E8ECF5",
    "text_dim": "#8B94A7",
    "entry_bg": "#14171D",
    "entry_border": "#262A35",
    "button_fg": "#1B1E26",
    "button_hover": "#262A35",
    "button_text": "#E8ECF5",
}

EXPERIANS3_LIGHT_PALET = {
    "bg": "#F7F8FB",
    "sidebar": "#FFFFFF",
    "card": "#FFFFFF",
    "neon": "#3F68E8",
    "text_main": "#1A2030",
    "text_dim": "#667085",
    "entry_bg": "#FFFFFF",
    "entry_border": "#D3DAE6",
    "button_fg": "#F4F6FA",
    "button_hover": "#E7ECF5",
    "button_text": "#1A2030",
}

SURFACE_PALETS = {
    "fluent": {
        "dark": FLUENT_DARK_PALET,
        "light": FLUENT_LIGHT_PALET,
    },
    "classic": {
        "dark": DARK_PALET,
        "light": LIGHT_PALET,
    },
    "liquid-glass": {
        "dark": LIQUID_GLASS_DARK_PALET,
        "light": LIQUID_GLASS_LIGHT_PALET,
    },
    "experians": {
        "dark": EXPERIANS_DARK_PALET,
        "light": EXPERIANS_LIGHT_PALET,
    },
    "experians3": {
        "dark": EXPERIANS3_DARK_PALET,
        "light": EXPERIANS3_LIGHT_PALET,
    },
    "zenkamind": {
        "dark": ZENKAMIND_DARK_PALET,
        "light": ZENKAMIND_LIGHT_PALET,
    },
}
LIVE_GIF_PATH = get_first_asset_path("yukleme.gif", "Neto.gif")

APP_VERSION = f"v{str(_NETO_VERSION).lstrip('vV')}"
APP_NAME = "NetOps"
APP_UI_NAME = "Neto Experians"
APP_UI_EDITION = "2.5"
APP_DESIGN_LANGUAGE = APP_UI_NAME
APP_DESIGN_EDITION = APP_UI_EDITION
APP_DESIGN_FULL_TITLE = f"{APP_DESIGN_LANGUAGE} {APP_DESIGN_EDITION}"
APP_FULL_TITLE = f"{APP_NAME} {APP_VERSION}"


LIVE_LOG_PATH = get_asset_path("logs/live_error.log")
