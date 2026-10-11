# =========================================================
# NETO WEATHER v10.7 - Auto/Manual/Temporary Location Mode
# Open-Meteo + IP tabanlı otomatik konum
# =========================================================
import json
import os
import urllib.parse
import urllib.request
import traceback
import re

HAFIZA_DOSYA = "hafiza.json"

DEFAULT_LOCATION = {
    "name": "Bahçelievler",
    "admin1": "İstanbul",
    "country": "Türkiye",
    "latitude": 41.0,
    "longitude": 28.85,
    "source": "default"
}

WEATHER_CODES_TR = {
    0: "açık", 1: "çoğunlukla açık", 2: "parçalı bulutlu", 3: "kapalı",
    45: "sisli", 48: "kırağılı sis",
    51: "hafif çisenti", 53: "orta çisenti", 55: "yoğun çisenti",
    61: "hafif yağmur", 63: "yağmur", 65: "şiddetli yağmur",
    66: "hafif donan yağmur", 67: "yoğun donan yağmur",
    71: "hafif kar", 73: "kar", 75: "yoğun kar", 77: "kar taneleri",
    80: "hafif sağanak", 81: "sağanak", 82: "şiddetli sağanak",
    85: "hafif kar sağanağı", 86: "yoğun kar sağanağı",
    95: "gök gürültülü fırtına", 96: "dolu ihtimalli fırtına", 99: "şiddetli dolu ihtimalli fırtına",
}

def _log(msg):
    try:
        os.makedirs("logs", exist_ok=True)
        with open("logs/weather.log", "a", encoding="utf-8") as f:
            f.write(str(msg) + "\n")
    except Exception:
        pass

def _load_memory():
    try:
        if os.path.exists(HAFIZA_DOSYA):
            with open(HAFIZA_DOSYA, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except Exception as e:
        _log(f"[MEMORY_LOAD_ERR] {e}")
    return {}

def _save_memory(data):
    try:
        with open(HAFIZA_DOSYA, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        _log(f"[MEMORY_SAVE_ERR] {e}")

def _http_json(url, timeout=7):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 Neto-Asistan/10.7",
            "Accept": "application/json,text/plain,*/*"
        }
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", errors="replace")
        return json.loads(raw)

def _valid_loc(loc):
    return isinstance(loc, dict) and loc.get("latitude") is not None and loc.get("longitude") is not None

def _location_label(loc):
    name = str(loc.get("name") or loc.get("city") or "Konum").strip()
    admin = str(loc.get("admin1") or loc.get("region") or "").strip()
    if admin and admin.lower() not in name.lower():
        return f"{name}, {admin}"
    return name

def _normalize_query(q):
    q = str(q or "").lower().strip()
    q = q.replace("ş", "s").replace("ı", "i").replace("ğ", "g").replace("ü", "u").replace("ö", "o").replace("ç", "c")
    return q

def auto_detect_location(save=True, silent_fail=False):
    services = [
        ("ipapi", "https://ipapi.co/json/"),
        ("ipwho", "https://ipwho.is/"),
    ]
    last_error = None

    for name, url in services:
        try:
            data = _http_json(url, timeout=6)
            if name == "ipapi":
                lat = data.get("latitude")
                lon = data.get("longitude")
                city = data.get("city") or data.get("region") or "Konum"
                region = data.get("region") or ""
                country = data.get("country_name") or data.get("country") or ""
            else:
                if data.get("success") is False:
                    raise RuntimeError(data.get("message") or "ipwho başarısız")
                lat = data.get("latitude")
                lon = data.get("longitude")
                city = data.get("city") or data.get("region") or "Konum"
                region = data.get("region") or ""
                country = data.get("country") or ""

            if lat is None or lon is None:
                raise RuntimeError("latitude/longitude boş")

            loc = {
                "name": city,
                "admin1": region,
                "country": country,
                "latitude": float(lat),
                "longitude": float(lon),
                "source": "ip",
                "auto": True
            }

            if save:
                mem = _load_memory()
                mem["location_mode"] = mem.get("location_mode", "auto")
                mem["auto_location"] = loc
                # Geriye uyumluluk
                if mem.get("location_mode") == "auto":
                    mem["konum"] = loc
                _save_memory(mem)

            return loc

        except Exception as e:
            last_error = f"{name}: {e}"
            _log(f"[AUTO_LOCATION_ERR] {last_error}")

    if silent_fail:
        return None
    raise RuntimeError(last_error or "Otomatik konum alınamadı")

def geocode_location(name):
    name = str(name or "").strip()
    if not name:
        return None
    q = urllib.parse.quote(name)
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={q}&count=1&language=tr&format=json"
    data = _http_json(url, timeout=7)
    results = data.get("results") or []
    if not results:
        return None
    r = results[0]
    return {
        "name": r.get("name") or name,
        "admin1": r.get("admin1") or "",
        "country": r.get("country") or "",
        "latitude": r.get("latitude"),
        "longitude": r.get("longitude"),
        "source": "manual_lookup",
        "auto": False
    }

def get_active_location(auto_if_missing=True):
    mem = _load_memory()
    mode = mem.get("location_mode", "auto")

    if mode == "manual":
        loc = mem.get("manual_location")
        if _valid_loc(loc):
            return loc

    # auto mode
    loc = mem.get("auto_location")
    if _valid_loc(loc):
        return loc

    # Eski sürüm uyumluluğu
    old = mem.get("konum") or mem.get("location")
    if _valid_loc(old):
        assert isinstance(old, dict)
        if old.get("source") == "manual":
            mem["manual_location"] = old
            mem["location_mode"] = "manual"
        else:
            mem["auto_location"] = old
            mem["location_mode"] = "auto"
        _save_memory(mem)
        return old

    if auto_if_missing:
        loc = auto_detect_location(save=True, silent_fail=True)
        if _valid_loc(loc):
            return loc

    return DEFAULT_LOCATION.copy()

def set_manual_location(name):
    loc = geocode_location(name)
    if not loc:
        return None
    loc["source"] = "manual"
    mem = _load_memory()
    mem["location_mode"] = "manual"
    mem["manual_location"] = loc
    mem["konum"] = loc
    _save_memory(mem)
    return loc

def switch_to_auto_location():
    mem = _load_memory()
    loc = auto_detect_location(save=True, silent_fail=True)
    if not _valid_loc(loc):
        loc = mem.get("auto_location")
    if not _valid_loc(loc):
        loc = DEFAULT_LOCATION.copy()
    mem["location_mode"] = "auto"
    mem["auto_location"] = loc
    mem["konum"] = loc
    _save_memory(mem)
    return loc

def update_auto_location():
    loc = auto_detect_location(save=True, silent_fail=True)
    if not _valid_loc(loc):
        return None
    mem = _load_memory()
    mem["auto_location"] = loc
    if mem.get("location_mode", "auto") == "auto":
        mem["konum"] = loc
    _save_memory(mem)
    return loc

def location_answer(query=""):
    q = _normalize_query(query)

    if "otomatik konuma don" in q or "cihaz konumuna don" in q or "otomatik konum" in q:
        loc = switch_to_auto_location()
        return f"Otomatik konuma dönüldü. Aktif konum: {_location_label(loc)}."

    if "guncelle" in q or "yenile" in q or "bul" in q or "neredeyim" in q or "nerdeyim" in q:
        loc = update_auto_location()
        if loc:
            return f"Cihaz konumu güncellendi: {_location_label(loc)}. Bu bilgi IP tabanlı yaklaşık konumdur."
        return "Cihaz konumu otomatik alınamadı. Kayıtlı konum veya varsayılan konum kullanılacak."

    loc = get_active_location(auto_if_missing=True)
    if not _valid_loc(loc):
        return "Aktif konum bulunamadı. Önce konumunu ayarlayabilirsin."
    assert isinstance(loc, dict)
    mem = _load_memory()
    mode = mem.get("location_mode", "auto")
    if mode == "manual":
        return f"Aktif konum manuel: {_location_label(loc)}."
    if loc.get("source") == "ip":
        return f"Aktif konum cihaz/IP konumu: {_location_label(loc)}. Bu kesin adres değildir."
    return f"Aktif konum: {_location_label(loc)}."

def _fetch_forecast(loc):
    params = {
        "latitude": float(loc["latitude"]),
        "longitude": float(loc["longitude"]),
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
        "timezone": "auto",
        "forecast_days": 7,
    }
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
    return _http_json(url, timeout=8)

def _current_summary(data, loc):
    cur = data.get("current") or {}
    daily = data.get("daily") or {}
    code = int(cur.get("weather_code", 0) or 0)
    desc = WEATHER_CODES_TR.get(code, "hava durumu bilinmiyor")
    label = _location_label(loc)

    parts = [f"{label} için hava {desc}."]
    temp = cur.get("temperature_2m")
    feels = cur.get("apparent_temperature")
    hum = cur.get("relative_humidity_2m")
    wind = cur.get("wind_speed_10m")
    precip = cur.get("precipitation")

    if temp is not None:
        parts.append(f"Sıcaklık {round(float(temp))} derece.")
    if feels is not None:
        parts.append(f"Hissedilen {round(float(feels))} derece.")
    if hum is not None:
        parts.append(f"Nem %{int(hum)}.")
    if wind is not None:
        parts.append(f"Rüzgar {round(float(wind))} km/sa.")

    try:
        rain = (daily.get("precipitation_probability_max") or [None])[0]
    except Exception:
        rain = None

    if rain is not None:
        parts.append(f"Yağış ihtimali %{int(rain)}.")
    elif precip is not None and float(precip) > 0:
        parts.append("Şu an yağış var.")

    if loc.get("source") == "ip":
        parts.append("Konum cihaz/IP üzerinden yaklaşık alındı.")
    elif loc.get("source") == "default":
        parts.append("Otomatik konum alınamadığı için varsayılan konum kullanıldı.")

    return " ".join(parts)

def _tomorrow_summary(data, loc):
    daily = data.get("daily") or {}
    label = _location_label(loc)
    try:
        code = int((daily.get("weather_code") or [0, 0])[1])
        desc = WEATHER_CODES_TR.get(code, "hava durumu bilinmiyor")
        tmax = (daily.get("temperature_2m_max") or [None, None])[1]
        tmin = (daily.get("temperature_2m_min") or [None, None])[1]
        rain = (daily.get("precipitation_probability_max") or [None, None])[1]
    except Exception:
        return "Yarın için hava tahmini alınamadı."

    msg = f"Yarın {label} için hava {desc}."
    if tmin is not None and tmax is not None:
        msg += f" Sıcaklık {round(float(tmin))} ile {round(float(tmax))} derece arası."
    if rain is not None:
        msg += f" Yağış ihtimali %{int(rain)}."
    return msg

def _week_summary(data, loc):
    daily = data.get("daily") or {}
    label = _location_label(loc)
    maxs = daily.get("temperature_2m_max") or []
    mins = daily.get("temperature_2m_min") or []
    rains = daily.get("precipitation_probability_max") or []
    if not maxs:
        return "Haftalık hava tahmini alınamadı."
    try:
        avg_max = round(sum(float(x) for x in maxs if x is not None) / len(maxs))
        avg_min = round(sum(float(x) for x in mins if x is not None) / len(mins)) if mins else None
        max_rain = max(int(x) for x in rains if x is not None) if rains else None
    except Exception:
        return "Haftalık hava verisi yorumlanamadı."
    msg = f"Bu hafta {label} için ortalama en yüksek sıcaklık {avg_max} derece"
    if avg_min is not None:
        msg += f", ortalama en düşük {avg_min} derece"
    msg += "."
    if max_rain is not None:
        msg += f" En yüksek yağış ihtimali %{max_rain}."
    return msg

def _umbrella_answer(data, loc):
    daily = data.get("daily") or {}
    cur = data.get("current") or {}
    label = _location_label(loc)
    try:
        rain = (daily.get("precipitation_probability_max") or [None])[0]
    except Exception:
        rain = None
    precip_now = float(cur.get("precipitation") or 0)
    code = int(cur.get("weather_code", 0) or 0)
    if precip_now > 0 or code in (51,53,55,61,63,65,80,81,82,95,96,99):
        return f"{label} için şemsiye al. Şu an yağış görünüyor."
    if rain is not None and int(rain) >= 40:
        return f"{label} için şemsiye almak mantıklı. Bugünkü yağış ihtimali %{int(rain)}."
    if rain is not None:
        return f"Bugün şemsiye şart görünmüyor. {label} için yağış ihtimali %{int(rain)}."
    return "Şemsiye için yağış ihtimali alınamadı."

def extract_temporary_location(query):
    """Sorgunun başındaki geçici şehir/ilçe adını ayıklar.

    Örnekler:
      Ankara'da yarın kar yağacak mı? -> Ankara
      yarın İstanbul'da hava nasıl?   -> İstanbul
      Bursa yağmur var mı?            -> Bursa

    Bu fonksiyon yalnızca aday adı çıkarır; asıl doğrulama Open-Meteo geocoding ile
    weather_answer() içinde yapılır.
    """
    raw = str(query or "").strip()
    if not raw:
        return None
    q = _normalize_query(raw)

    # En erken hava terimini bul. Böylece "Ankara'da yarın kar ..." içinde
    # aday bölüm "Ankara'da yarın" olur; aşağıda zaman kelimesi temizlenir.
    triggers = [
        " hava durumu", " hava", " kac derece", " yağmur", " yagmur",
        " kar", " radar", " firtina", " simsek", " dolu", " sis",
        " buzlanma", " buz", " donma", " don", " aqi", " hava kalitesi",
        " polen", " basinc", " ruzgar", " semsiye", " sel", " taskin",
        " nehir", " metar",
    ]
    hits = [(q.find(t), t) for t in triggers if q.find(t) >= 0]
    if not hits:
        return None
    trigger_pos, _ = min(hits, key=lambda item: item[0])
    if trigger_pos <= 0:
        return None

    # _normalize_query karakterleri bire bir dönüştürdüğü için bu indeks raw metne
    # de uygulanabilir.
    candidate = raw[:trigger_pos].strip(" ,;:-")

    # Başta/sonda yer alan zaman ifadeleri şehir adı değildir.
    time_words = (
        r"bugün|bugun|yarın|yarin|bu\s+gece|bu\s+akşam|bu\s+aksam|"
        r"yarın\s+gece|yarin\s+gece|yarın\s+sabah|yarin\s+sabah|"
        r"sabah|öğlen|oglen|öğle|ogle|akşam|aksam|gece"
    )
    previous = None
    while candidate and candidate != previous:
        previous = candidate
        candidate = re.sub(rf"^(?:{time_words})\s+", "", candidate, flags=re.IGNORECASE).strip()
        candidate = re.sub(rf"\s+(?:{time_words})$", "", candidate, flags=re.IGNORECASE).strip()

    # Türkçede şehir adından sonra kullanılan kesmeli bulunma eki:
    # Ankara'da, İzmir'de, Çerkezköy'de ...
    candidate = re.sub(r"[’'](?:da|de|ta|te)$", "", candidate, flags=re.IGNORECASE).strip()
    candidate = candidate.strip(" ,;:-.?!")

    if not candidate:
        return None
    if _normalize_query(candidate) in {"bugun", "yarin", "bu hafta", "hava"}:
        return None
    return candidate

def weather_answer(query):
    q = _normalize_query(query)

    try:
        # Kalıcı manuel konum
        manual_patterns = ["konumumu ", "konumu ", "konumum ", "hava konum "]
        for key in manual_patterns:
            if key in q:
                name = q.split(key, 1)[1].strip()
                for tail in [" yap", " ayarla", " olarak ayarla", " sec", " seç"]:
                    if name.endswith(tail):
                        name = name[:-len(tail)].strip()
                if name in ["otomatik", "otomatik konum", "cihaz", "cihaz konumu"]:
                    loc = switch_to_auto_location()
                    return f"Otomatik konuma dönüldü. Aktif konum: {_location_label(loc)}."
                loc = set_manual_location(name)
                if loc:
                    return f"Konum manuel olarak {_location_label(loc)} yapıldı."
                return "Konum bulunamadı."

        # Sadece bu sorgu için geçici şehir
        temp_name = extract_temporary_location(query)
        loc = None
        if temp_name:
            loc = geocode_location(temp_name)
            # Turkish location suffix fallback: "Ankara'da kar..." -> "Ankara".
            # First try the user's exact text so real place names ending in -da/-de are not damaged.
            if not loc:
                cleaned_name = re.sub(r"[’'](?:da|de|ta|te)$", "", str(temp_name), flags=re.IGNORECASE).strip()
                if cleaned_name != temp_name:
                    loc = geocode_location(cleaned_name)
            if loc:
                loc["source"] = "temporary"

        if not _valid_loc(loc):
            loc = get_active_location(auto_if_missing=True)

        # Yeni Weather Engine: public-apis Weather listesindeki ücretsiz/no-key
        # kaynakları sağlayıcı bazlı dener. Hata alırsa eski Open-Meteo akışı
        # çalışmaya devam eder.
        try:
            from neto_weather_engine import WeatherEngine

            engine_answer = WeatherEngine().answer(query, loc, _location_label(loc))
            if engine_answer and isinstance(engine_answer, str):
                return engine_answer
        except Exception as e:
            _log("[WEATHER_ENGINE_ERR] " + str(e))
            _log(traceback.format_exc())

        try:
            data = _fetch_forecast(loc)
        except Exception as e:
            _log("[FORECAST_ERR] " + str(e))
            return f"Hava durumu servisine ulaşılamadı: {e}. Kullanılan konum: {_location_label(loc)}."

        if "yarin" in q or "yarın" in str(query).lower():
            return _tomorrow_summary(data, loc)
        if "hafta" in q or "7 gun" in q or "yedi gun" in q:
            return _week_summary(data, loc)
        if "semsiye" in q or "şemsiye" in str(query).lower() or "yagmur" in q or "yağmur" in str(query).lower() or "yagacak mi" in q:
            return _umbrella_answer(data, loc)
        return _current_summary(data, loc)

    except Exception as e:
        _log("[WEATHER_ERR] " + str(e))
        _log(traceback.format_exc())
        return f"Hava durumu alınamadı: {e}"

def is_weather_query(text):
    q = _normalize_query(text)
    keys = [
        "hava", "hava durumu", "kac derece", "kaç derece",
        "yagmur", "yağmur", "kar", "karla karisik", "karla karışık",
        "radar", "firtina", "fırtına", "simsek", "şimşek", "dolu",
        "sis", "buz", "buzlanma", "don", "donma",
        "semsiye", "şemsiye", "disarisi", "dışarısı",
        "ruzgar", "rüzgar", "nem", "basinc", "basınç",
        "uv", "aqi", "hava kalitesi", "polen", "metar",
        "sel", "taskin", "taşkın", "nehir"
    ]
    return any(k in q for k in keys)

def is_location_query(text):
    q = _normalize_query(text)
    keys = [
        "konumumu bul", "konumu bul", "konumumu guncelle", "konumu guncelle",
        "konumu yenile", "konum yenile", "neredeyim", "nerdeyim",
        "bulundugum sehir", "hangi sehirdeyim",
        "otomatik konuma don", "cihaz konumuna don", "otomatik konum"
    ]
    return any(k in q for k in keys)
