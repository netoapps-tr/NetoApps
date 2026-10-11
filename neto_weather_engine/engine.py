from .analyzers import deterministic_model_line, forecast_consensus, snow_risk
from .http_client import HttpClient
from .models import ProviderResult, safe_float, safe_int
from .providers import (
    AviationWeatherProvider,
    MetNorwayProvider,
    NasaPowerProvider,
    OpenMeteoAirProvider,
    OpenMeteoEnsembleProvider,
    OpenMeteoFloodProvider,
    OpenMeteoForecastProvider,
    OpenMeteoModelsProvider,
    OpenSenseMapProvider,
    RainViewerProvider,
    WttrProvider,
    GoWeatherProvider,
    HongKongObservatoryProvider,
    IpmaProvider,
    OdWeatherProvider,
    SevenTimerProvider,
    UsWeatherProvider,
    WeatherTotalsProvider,
    HailHistoryProvider,
    WorldTimeWeatherProvider,
)
from .weather_catalog import rows as weather_catalog_rows, summary as weather_catalog_summary


WEATHER_CODES_TR = {
    0: "açık",
    1: "çoğunlukla açık",
    2: "parçalı bulutlu",
    3: "kapalı",
    45: "sisli",
    48: "kırağılı sis",
    51: "hafif çisenti",
    53: "orta çisenti",
    55: "yoğun çisenti",
    61: "hafif yağmur",
    63: "yağmur",
    65: "şiddetli yağmur",
    66: "hafif donan yağmur",
    67: "yoğun donan yağmur",
    71: "hafif kar",
    73: "kar",
    75: "yoğun kar",
    77: "kar taneleri",
    80: "hafif sağanak",
    81: "sağanak",
    82: "şiddetli sağanak",
    85: "hafif kar sağanağı",
    86: "yoğun kar sağanağı",
    95: "gök gürültülü fırtına",
    96: "dolu ihtimalli fırtına",
    99: "şiddetli dolu ihtimalli fırtına",
}


class WeatherEngine:
    def __init__(self, http=None):
        self.http = http or HttpClient()
        self.forecast = OpenMeteoForecastProvider()
        self.air = OpenMeteoAirProvider()
        self.ensemble = OpenMeteoEnsembleProvider()
        self.models = OpenMeteoModelsProvider()
        self.flood = OpenMeteoFloodProvider()
        self.met = MetNorwayProvider()
        self.radar = RainViewerProvider()
        self.aviation = AviationWeatherProvider()
        self.nasa = NasaPowerProvider()
        self.sense = OpenSenseMapProvider()
        self.wttr = WttrProvider()
        self.seven_timer = SevenTimerProvider()
        self.hko = HongKongObservatoryProvider()
        self.ipma = IpmaProvider()
        self.us_weather = UsWeatherProvider()
        self.go_weather = GoWeatherProvider()
        self.weather_totals = WeatherTotalsProvider()
        self.od_weather = OdWeatherProvider()
        self.hail_history = HailHistoryProvider()
        self.world_time_weather = WorldTimeWeatherProvider()

    def answer(self, query, location, location_label):
        q = self._normalize(query)
        if self._wants_api_status(q):
            return self._format_api_status()
        results = {}

        forecast = self.forecast.fetch(self.http, location)
        results["forecast"] = forecast
        if not forecast.ok:
            wttr = self.wttr.fetch(self.http, location)
            results["wttr"] = wttr
            if wttr.ok:
                return self._format_wttr(wttr.data, location_label)
            return "Hava durumu servisleri şu an cevap vermedi. Biraz sonra tekrar deneyebilirsin."

        deep = self._wants_deep_context(q)
        snow_query = "kar" in q or "snow" in q

        # Simple summaries can return immediately. Deep weather questions such as
        # "yarın kar yağacak mı" must continue to ensemble/radar analysis.
        if self._wants_week(q) and not deep:
            return self._format_week(forecast.data, location_label)
        if self._wants_tomorrow(q) and not deep:
            return self._format_tomorrow(forecast.data, location_label)

        air = self.air.fetch(self.http, location)
        met = self.met.fetch(self.http, location)
        results["air"] = air
        results["met"] = met

        if deep:
            results["radar"] = self.radar.fetch(self.http, location)
            # Additional no-key public-apis sources. Region-specific adapters fail
            # closed outside their coverage instead of fabricating global data.
            results["seven_timer"] = self.seven_timer.fetch(self.http, location)
            results["go_weather"] = self.go_weather.fetch(self.http, location)
            for key, provider in (
                ("hko", self.hko),
                ("ipma", self.ipma),
                ("us_weather", self.us_weather),
                ("weather_totals", self.weather_totals),
                ("hail_history", self.hail_history),
            ):
                result = provider.fetch(self.http, location)
                if result.ok:
                    results[key] = result
        if snow_query:
            results["ensemble"] = self.ensemble.fetch(self.http, location, forecast_hours=48)
            results["models"] = self.models.fetch(self.http, location, forecast_hours=48)
        if self._wants_flood(q):
            results["flood"] = self.flood.fetch(self.http, location)
        if self._wants_aviation(q):
            results["aviation"] = self.aviation.fetch(self.http, location)
        if self._wants_sensors(q):
            results["sense"] = self.sense.fetch(self.http, location)
        if self._wants_climate(q):
            results["nasa"] = self.nasa.fetch(self.http, location)
        if self._wants_all_sources(q):
            results["od_weather"] = self.od_weather.fetch(self.http, location)
            results["world_time_weather"] = self.world_time_weather.fetch(self.http, location)

        if self._wants_tomorrow(q):
            return self._format_tomorrow_deep(query, location, location_label, results)
        return self._format_current(query, location, location_label, results)

    @staticmethod
    def _normalize(text):
        text = str(text or "").lower()
        return (
            text.replace("ş", "s")
            .replace("ı", "i")
            .replace("ğ", "g")
            .replace("ü", "u")
            .replace("ö", "o")
            .replace("ç", "c")
        )

    @staticmethod
    def _wants_api_status(q):
        return ("api" in q and any(x in q for x in ["durum", "liste", "kaynak", "hepsi", "butun", "tum"])) or "hava apileri" in q

    @staticmethod
    def _wants_all_sources(q):
        return any(x in q for x in ["butun api", "tum api", "hepsi", "tum kaynak", "butun kaynak"])

    @staticmethod
    def _wants_tomorrow(q):
        return "yarin" in q

    @staticmethod
    def _wants_week(q):
        return "hafta" in q or "7 gun" in q or "yedi gun" in q

    @staticmethod
    def _wants_climate(q):
        return any(x in q for x in ["iklim", "normal", "mevsim", "gecmis"])

    @staticmethod
    def _wants_flood(q):
        return any(x in q for x in ["sel", "taskin", "nehir", "river", "flood"])

    @staticmethod
    def _wants_deep_context(q):
        return any(x in q for x in [
            "yagmur",
            "kar",
            "radar",
            "firtina",
            "simsek",
            "dolu",
            "sel",
            "taskin",
            "buz",
            "don",
            "sis",
        ])

    @staticmethod
    def _wants_aviation(q):
        return any(x in q for x in ["metar", "ucus", "havaalani", "pist"])

    @staticmethod
    def _wants_sensors(q):
        return any(x in q for x in ["sensor", "olcum", "istasyon", "gozlem"])

    def _format_current(self, query, location, label, results):
        data = results["forecast"].data
        cur = data.get("current") or {}
        daily = data.get("daily") or {}
        code = safe_int(cur.get("weather_code"), 0) or 0
        desc = WEATHER_CODES_TR.get(code, "hava durumu bilinmiyor")
        temp = safe_int(cur.get("temperature_2m"))
        feels = safe_int(cur.get("apparent_temperature"))
        hum = safe_int(cur.get("relative_humidity_2m"))
        wind = safe_int(cur.get("wind_speed_10m"))
        gust = safe_int(cur.get("wind_gusts_10m"))
        pressure = safe_int(cur.get("pressure_msl"))
        cloud = safe_int(cur.get("cloud_cover"))
        precip = safe_float(cur.get("precipitation"), 0) or 0
        rain_prob = None
        try:
            rain_prob = safe_int((daily.get("precipitation_probability_max") or [None])[0])
        except Exception:
            rain_prob = None

        lines = [f"{label} için hava {desc}."]
        details = []
        if temp is not None:
            details.append(f"sıcaklık {temp} derece")
        if feels is not None:
            details.append(f"hissedilen {feels} derece")
        if hum is not None:
            details.append(f"nem %{hum}")
        if wind is not None:
            wind_text = f"rüzgar {wind} km/sa"
            if gust is not None and gust > wind:
                wind_text += f", hamle {gust} km/sa"
            details.append(wind_text)
        if pressure is not None:
            details.append(f"basınç {pressure} hPa")
        if cloud is not None:
            details.append(f"bulutluluk %{cloud}")
        if details:
            lines.append("Özet: " + ", ".join(details) + ".")

        if precip > 0:
            lines.append(f"Şu an yağış ölçülüyor: {precip:.1f} mm.")
        elif rain_prob is not None:
            if rain_prob >= 50:
                lines.append(f"Bugün yağış ihtimali belirgin: %{rain_prob}. Şemsiye mantıklı.")
            else:
                lines.append(f"Bugünkü yağış ihtimali düşük/orta: %{rain_prob}.")

        air_text = self._air_quality_line(results.get("air"))
        if air_text:
            lines.append(air_text)

        q = self._normalize(query)
        if "kar" in q:
            # Kar sorgularında debug satırları yerine okunabilir, bölümlü bir rapor üret.
            lines = ["❄ KAR RİSK ANALİZİ", f"Konum: {label}", "", *lines]
            ensemble_data = None
            if results.get("ensemble") and results["ensemble"].ok:
                ensemble_data = results["ensemble"].data
            lines.extend(["", snow_risk(data, ensemble_data=ensemble_data, target="next24")])
            if results.get("models") and results["models"].ok:
                model_line = deterministic_model_line(
                    results["models"].data,
                    reference_time=(data.get("current") or {}).get("time"),
                    target="next24",
                )
                if model_line:
                    lines.append(model_line)

        atmosphere = self._atmosphere_line(data)
        if atmosphere and self._wants_deep_context(q) and "kar" not in q:
            lines.append(atmosphere)

        consensus = forecast_consensus(data, results.get("met").data if results.get("met") and results.get("met").ok else None)
        if consensus:
            if "kar" in q:
                lines.extend(["", "KAYNAK KONTROLÜ", consensus.replace("Kaynak kontrolü: ", "")])
            else:
                lines.append(consensus)

        if results.get("radar") and results["radar"].ok:
            radar_line = self._radar_line(results["radar"].data)
            if radar_line:
                if "kar" in q:
                    lines.extend(["", "RADAR", radar_line.replace("Radar: ", "")])
                else:
                    lines.append(radar_line)
        extra_sources = self._extra_sources_line(results)
        if extra_sources and self._wants_deep_context(q):
            lines.append(extra_sources)

        if results.get("flood") and results["flood"].ok:
            flood_line = self._flood_line(results["flood"].data)
            if flood_line:
                lines.append(flood_line)
        if results.get("aviation") and results["aviation"].ok:
            aviation_line = self._aviation_line(results["aviation"].data)
            if aviation_line:
                lines.append(aviation_line)
        if results.get("sense") and results["sense"].ok:
            sense_line = self._sense_line(results["sense"].data)
            if sense_line:
                lines.append(sense_line)
        if results.get("nasa") and results["nasa"].ok:
            nasa_line = self._nasa_line(results["nasa"].data)
            if nasa_line:
                lines.append(nasa_line)

        if location.get("source") == "ip":
            lines.append("Konum IP üzerinden yaklaşık alındı.")
        elif location.get("source") == "default":
            lines.append("Otomatik konum alınamadığı için varsayılan konum kullanıldı.")

        return "\n".join(lines)

    def _format_tomorrow_deep(self, query, location, label, results):
        q = self._normalize(query)
        if "kar" in q:
            lines = ["❄ KAR RİSK ANALİZİ", f"Konum: {label}", "", self._format_tomorrow(results["forecast"].data, label)]
        else:
            lines = [self._format_tomorrow(results["forecast"].data, label)]
        if "kar" in q:
            ensemble_data = None
            if results.get("ensemble") and results["ensemble"].ok:
                ensemble_data = results["ensemble"].data
            forecast_data = results["forecast"].data
            lines.extend(["", snow_risk(forecast_data, ensemble_data=ensemble_data, target="tomorrow")])
            if results.get("models") and results["models"].ok:
                model_line = deterministic_model_line(
                    results["models"].data,
                    reference_time=(forecast_data.get("current") or {}).get("time"),
                    target="tomorrow",
                )
                if model_line:
                    lines.append(model_line)
        atmosphere = self._atmosphere_line(results["forecast"].data, target="tomorrow")
        if atmosphere and "kar" not in q:
            lines.append(atmosphere)
        if results.get("radar") and results["radar"].ok:
            radar_line = self._radar_line(results["radar"].data)
            if radar_line:
                if "kar" in q:
                    lines.extend(["", "RADAR", radar_line.replace("Radar: ", "")])
                else:
                    lines.append(radar_line)
        consensus = forecast_consensus(
            results["forecast"].data,
            results.get("met").data if results.get("met") and results.get("met").ok else None,
        )
        if consensus:
            if "kar" in q:
                lines.extend(["", "KAYNAK KONTROLÜ", consensus.replace("Kaynak kontrolü: ", "")])
            else:
                lines.append(consensus)
        return "\n".join(lines)

    def _format_tomorrow(self, data, label):
        daily = data.get("daily") or {}
        try:
            code = safe_int((daily.get("weather_code") or [0, 0])[1], 0) or 0
            desc = WEATHER_CODES_TR.get(code, "hava durumu bilinmiyor")
            tmax = safe_int((daily.get("temperature_2m_max") or [None, None])[1])
            tmin = safe_int((daily.get("temperature_2m_min") or [None, None])[1])
            rain = safe_int((daily.get("precipitation_probability_max") or [None, None])[1])
            wind = safe_int((daily.get("wind_speed_10m_max") or [None, None])[1])
            snow = safe_float((daily.get("snowfall_sum") or [None, None])[1])
        except Exception:
            return "Yarın için hava tahmini yorumlanamadı."
        parts = [f"Yarın {label} için hava {desc}."]
        if tmin is not None and tmax is not None:
            parts.append(f"Sıcaklık {tmin}-{tmax} derece aralığında.")
        if rain is not None:
            parts.append(f"Yağış ihtimali %{rain}.")
        if snow is not None and snow > 0:
            parts.append(f"Model kar toplamı yaklaşık {snow:.1f} cm.")
        if wind is not None:
            parts.append(f"En yüksek rüzgar yaklaşık {wind} km/sa.")
        return " ".join(parts)

    def _format_week(self, data, label):
        daily = data.get("daily") or {}
        maxs = [safe_float(x) for x in (daily.get("temperature_2m_max") or []) if safe_float(x) is not None]
        mins = [safe_float(x) for x in (daily.get("temperature_2m_min") or []) if safe_float(x) is not None]
        rains = [safe_int(x) for x in (daily.get("precipitation_probability_max") or []) if safe_int(x) is not None]
        if not maxs:
            return "Haftalık hava tahmini alınamadı."
        avg_max = round(sum(maxs) / len(maxs))
        avg_min = round(sum(mins) / len(mins)) if mins else None
        max_rain = max(rains) if rains else None
        text = f"Bu hafta {label} için ortalama en yüksek sıcaklık {avg_max} derece"
        if avg_min is not None:
            text += f", ortalama en düşük {avg_min} derece"
        text += "."
        if max_rain is not None:
            text += f" Haftanın en yüksek yağış ihtimali %{max_rain}."
        return text

    @staticmethod
    def _extra_sources_line(results):
        names = []
        mapping = [
            ("seven_timer", "7Timer"),
            ("go_weather", "weather-api"),
            ("hko", "Hong Kong Observatory"),
            ("ipma", "IPMA"),
            ("us_weather", "US Weather/NWS"),
            ("weather_totals", "WeatherTotals"),
            ("hail_history", "Hail History"),
            ("od_weather", "ODWeather"),
            ("world_time_weather", "World Time & Weather"),
        ]
        for key, label in mapping:
            result = results.get(key)
            if result is not None and getattr(result, "ok", False):
                names.append(label)
        return "Ek ücretsiz kaynaklar: " + ", ".join(names) + "." if names else ""

    def _format_api_status(self):
        import os
        info = weather_catalog_summary()
        lines = [
            "NETOPS WEATHER API REGISTRY",
            f"public-apis Weather girdileri: {info['total']}",
            f"Gerçek adapter bağlı: {info['active_adapters']}",
            f"Anahtarsız/User-Agent: {info['keyless_or_user_agent']}",
            f"Kimlik bilgisi isteyen: {info['credentialed']}",
            "",
        ]
        for row in weather_catalog_rows():
            if row['adapter']:
                state = "AKTİF ADAPTER"
            elif row['key_env'] and os.getenv(row['key_env']):
                state = f"ANAHTAR VAR ({row['key_env']})"
            elif row['key_env']:
                state = f"ANAHTAR GEREKİYOR ({row['key_env']})"
            else:
                state = "KATALOG / ENDPOINT DOĞRULAMA GEREKİYOR"
            lines.append(f"• {row['name']} — {state} — kapsam: {row['scope']}")
        lines.append("Not: 'adapter bağlı' gerçek veri çağrısı yapabildiğimiz kaynak demektir; katalog girdileri uydurma endpoint ile çağrılmaz.")
        return "\n".join(lines)

    def _format_wttr(self, data, label):
        current = (data.get("current_condition") or [{}])[0]
        temp = current.get("temp_C")
        feels = current.get("FeelsLikeC")
        desc = ""
        try:
            desc = (current.get("lang_tr") or current.get("weatherDesc") or [{}])[0].get("value") or ""
        except Exception:
            desc = ""
        parts = [f"{label} için hava bilgisi yedek kaynaktan alındı."]
        if desc:
            parts.append(f"Durum: {desc}.")
        if temp is not None:
            parts.append(f"Sıcaklık {temp} derece.")
        if feels is not None:
            parts.append(f"Hissedilen {feels} derece.")
        return " ".join(parts)

    @staticmethod
    def _air_quality_line(result):
        if not isinstance(result, ProviderResult) or not result.ok:
            return ""
        current = result.data.get("current") or {}
        hourly = result.data.get("hourly") or {}

        def value(name):
            if current.get(name) is not None:
                return current.get(name)
            values = hourly.get(name) or []
            return values[0] if values else None

        aqi = safe_int(value("european_aqi"))
        pm25 = safe_float(value("pm2_5"))
        pm10 = safe_float(value("pm10"))
        dust = safe_float(value("dust"))
        uv = safe_float(value("uv_index"))
        pollen = max(
            [safe_float(value(x), 0) or 0 for x in ["grass_pollen", "olive_pollen", "ragweed_pollen", "birch_pollen"]],
            default=0,
        )
        parts = []
        if aqi is not None:
            parts.append(f"Avrupa AQI {aqi}")
        if pm25 is not None:
            parts.append(f"PM2.5 {pm25:.1f}")
        if pm10 is not None:
            parts.append(f"PM10 {pm10:.1f}")
        if dust is not None:
            parts.append(f"toz {dust:.1f}")
        if uv is not None:
            parts.append(f"UV {uv:.1f}")
        if pollen > 0:
            parts.append(f"polen {pollen:.1f}")
        if not parts:
            return ""
        return "Hava kalitesi: " + ", ".join(parts) + "."

    @staticmethod
    def _radar_line(data):
        radar = data.get("radar") or {}
        past = radar.get("past") or []
        if past:
            return f"Radar: son {len(past)} geçmiş radar karesi mevcut; hareket analizi için veri hazır."
        return "Radar verisi şu an boş döndü."

    @staticmethod
    def _atmosphere_line(data, target="current"):
        hourly = data.get("hourly") or {}
        times = hourly.get("time") or []
        if not times:
            return ""
        current_time = str((data.get("current") or {}).get("time") or "")
        idx = 0
        if target == "tomorrow":
            try:
                from datetime import datetime, timedelta
                current_dt = datetime.fromisoformat(current_time)
                tomorrow = current_dt.date() + timedelta(days=1)
                for i, stamp in enumerate(times):
                    if datetime.fromisoformat(stamp).date() == tomorrow:
                        idx = i
                        break
            except Exception:
                idx = min(24, len(times) - 1)
        else:
            for i, stamp in enumerate(times):
                if stamp >= current_time:
                    idx = i
                    break

        fields = [
            ("wet_bulb_temperature_2m", "wet-bulb", "°C", 1),
            ("dew_point_2m", "çiy", "°C", 1),
            ("temperature_925hPa", "925 hPa sıcaklık", "°C", 1),
            ("temperature_850hPa", "850 hPa sıcaklık", "°C", 1),
            ("temperature_700hPa", "700 hPa sıcaklık", "°C", 1),
            ("temperature_500hPa", "500 hPa sıcaklık", "°C", 1),
            ("freezing_level_height", "0°C seviyesi", "m", 0),
            ("snowfall_height", "kar seviyesi", "m", 0),
            ("cape", "CAPE", "J/kg", 0),
        ]
        parts = []
        for key, label, unit, decimals in fields:
            vals = hourly.get(key) or []
            if idx >= len(vals):
                continue
            val = safe_float(vals[idx])
            if val is None:
                continue
            if decimals:
                parts.append(f"{label} {val:.1f}{unit}")
            else:
                parts.append(f"{label} {round(val)} {unit}".replace("  ", " "))
        return "Atmosfer: " + ", ".join(parts) + "." if parts else ""

    @staticmethod
    def _flood_line(data):
        daily = data.get("daily") or {}
        current = daily.get("river_discharge") or []
        maximum = daily.get("river_discharge_max") or []
        if not current and not maximum:
            return ""
        parts = []
        if current:
            v = safe_float(current[0])
            if v is not None:
                parts.append(f"nehir debisi {v:.1f} m³/s")
        if maximum:
            v = safe_float(maximum[0])
            if v is not None:
                parts.append(f"ensemble üst senaryo {v:.1f} m³/s")
        return "Taşkın modeli: " + ", ".join(parts) + "." if parts else ""

    @staticmethod
    def _aviation_line(data):
        stations = data.get("stations") or []
        if not stations:
            return ""
        station = stations[0]
        ident = station.get("icaoId") or station.get("station_id") or "yakın istasyon"
        temp = station.get("temp")
        dew = station.get("dewp")
        parts = [f"yakın METAR {ident}"]
        if temp is not None:
            parts.append(f"{temp}°C")
        if dew is not None:
            parts.append(f"çiy {dew}°C")
        return "Gözlem: " + ", ".join(parts) + "."

    @staticmethod
    def _sense_line(data):
        boxes = data.get("boxes") or []
        if not boxes:
            return ""
        return f"Yakında {len(boxes)} açık sensör istasyonu bulundu; yerel ölçüm desteği hazır."

    @staticmethod
    def _nasa_line(data):
        params = (((data.get("properties") or {}).get("parameter") or {}))
        if not params:
            return ""
        temp_data = params.get("T2M") or {}
        rain_data = params.get("PRECTOTCORR") or {}
        temp_values = [safe_float(v) for v in temp_data.values() if safe_float(v) is not None]
        rain_values = [safe_float(v) for v in rain_data.values() if safe_float(v) is not None]
        parts = []
        if temp_values:
            parts.append(f"NASA POWER yakın geçmiş sıcaklık {temp_values[-1]:.1f} derece")
        if rain_values:
            parts.append(f"yağış {rain_values[-1]:.1f} mm")
        if not parts:
            return ""
        return "Geçmiş referansı: " + ", ".join(parts) + "."
