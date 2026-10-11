from __future__ import annotations

import urllib.parse

from ..models import ProviderResult


class SevenTimerProvider:
    name = "7Timer!"

    def fetch(self, http, location):
        params = {
            "lon": round(float(location["longitude"]), 3),
            "lat": round(float(location["latitude"]), 3),
            "product": "civil",
            "output": "json",
        }
        try:
            # HTTPS currently works although the public-apis row still marks HTTPS No.
            data = http.get_json("https://www.7timer.info/bin/api.pl", params, timeout=9, ttl_seconds=10800)
            return ProviderResult(self.name, True, data=data if isinstance(data, dict) else {"raw": data})
        except Exception as exc:
            return ProviderResult(self.name, False, error=str(exc))


class HongKongObservatoryProvider:
    name = "Hong Kong Observatory"

    def fetch(self, http, location):
        country = str(location.get("country") or "").casefold()
        if "hong kong" not in country and "香港" not in country:
            return ProviderResult(self.name, False, error="scope: Hong Kong only")
        try:
            data = http.get_json(
                "https://data.weather.gov.hk/weatherAPI/opendata/weather.php",
                {"dataType": "rhrread", "lang": "en"},
                timeout=8,
                ttl_seconds=600,
            )
            return ProviderResult(self.name, True, data=data)
        except Exception as exc:
            return ProviderResult(self.name, False, error=str(exc))


class IpmaProvider:
    name = "IPMA"

    def fetch(self, http, location):
        country = str(location.get("country") or "").casefold()
        if "portugal" not in country and "portekiz" not in country:
            return ProviderResult(self.name, False, error="scope: Portugal only")
        try:
            observations = http.get_json(
                "https://api.ipma.pt/open-data/observation/meteorology/stations/observations.json",
                timeout=8,
                ttl_seconds=1800,
            )
            warnings = http.get_json(
                "https://api.ipma.pt/open-data/forecast/warnings/warnings_www.json",
                timeout=8,
                ttl_seconds=1800,
            )
            return ProviderResult(self.name, True, data={"observations": observations, "warnings": warnings})
        except Exception as exc:
            return ProviderResult(self.name, False, error=str(exc))


class UsWeatherProvider:
    name = "US Weather / NWS"

    def fetch(self, http, location):
        country = str(location.get("country") or "").casefold()
        if not any(x in country for x in ("united states", "usa", "abd", "amerika")):
            return ProviderResult(self.name, False, error="scope: US only")
        lat = float(location["latitude"])
        lon = float(location["longitude"])
        try:
            point = http.get_json(
                f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}",
                timeout=9,
                ttl_seconds=21600,
                headers={"Accept": "application/geo+json"},
            )
            props = (point or {}).get("properties") or {}
            forecast_url = props.get("forecastHourly") or props.get("forecast")
            alerts = http.get_json(
                "https://api.weather.gov/alerts/active",
                {"point": f"{lat:.4f},{lon:.4f}"},
                timeout=9,
                ttl_seconds=300,
                headers={"Accept": "application/geo+json"},
            )
            forecast = {}
            if forecast_url:
                forecast = http.get_json(str(forecast_url), timeout=9, ttl_seconds=3600, headers={"Accept": "application/geo+json"})
            return ProviderResult(self.name, True, data={"point": point, "forecast": forecast, "alerts": alerts})
        except Exception as exc:
            return ProviderResult(self.name, False, error=str(exc))


class GoWeatherProvider:
    name = "weather-api / goweather.xyz"

    def fetch(self, http, location):
        city = str(location.get("name") or location.get("city") or "").strip()
        if not city:
            return ProviderResult(self.name, False, error="city name required")
        try:
            encoded = urllib.parse.quote(city)
            # Current project README points to goweather.xyz/v2/weather/{city}.
            data = http.get_json(f"https://goweather.xyz/v2/weather/{encoded}", timeout=8, ttl_seconds=1800)
            return ProviderResult(self.name, True, data=data)
        except Exception as exc:
            return ProviderResult(self.name, False, error=str(exc))


class WeatherTotalsProvider:
    name = "WeatherTotals"

    def fetch(self, http, location):
        country = str(location.get("country") or "").casefold()
        if not any(x in country for x in ("united states", "usa", "abd", "amerika")):
            return ProviderResult(self.name, False, error="scope: US only")
        try:
            yesterday = http.get_json("https://weathertotals.com/api/v1/yesterday", timeout=8, ttl_seconds=3600)
            hail = http.get_json("https://weathertotals.com/api/v1/hail/week", timeout=8, ttl_seconds=3600)
            snow = http.get_json("https://weathertotals.com/api/v1/snow/reports", timeout=8, ttl_seconds=1800)
            return ProviderResult(self.name, True, data={"yesterday": yesterday, "hail": hail, "snow": snow})
        except Exception as exc:
            return ProviderResult(self.name, False, error=str(exc))


class OdWeatherProvider:
    name = "ODWeather"

    def fetch(self, http, location):
        # public-apis still lists ODWeather as no-auth, but the old
        # /static/resources.json discovery URL currently returns 404. Try the
        # documented legacy webcam operation as a compatibility probe. If the
        # upstream service has retired its no-auth endpoints we report that
        # explicitly rather than pretending the adapter works.
        candidates = [
            "https://api.oceandrivers.com/v1.0/getWebCams/",
            "https://api.oceandrivers.com/static/resources.json",
        ]
        errors = []
        for url in candidates:
            try:
                data = http.get_json(url, timeout=8, ttl_seconds=21600, retries=0)
                return ProviderResult(self.name, True, data={"endpoint": url, "data": data})
            except Exception as exc:
                errors.append(f"{url}: {exc}")
        return ProviderResult(
            self.name,
            False,
            error="upstream no-auth ODWeather endpoint unavailable/retired; " + " | ".join(errors),
        )


class HailHistoryProvider:
    name = "Hail History"

    def fetch(self, http, location):
        country = str(location.get("country") or "").casefold()
        if not any(x in country for x in ("united states", "usa", "abd", "amerika")):
            return ProviderResult(self.name, False, error="scope: US only")
        params = {
            "lat": round(float(location["latitude"]), 5),
            "lon": round(float(location["longitude"]), 5),
            "detail": "top",
            "topN": 5,
        }
        try:
            data = http.get_json(
                "https://halfmilehail.com/.netlify/functions/hail-history",
                params,
                timeout=10,
                ttl_seconds=86400,
            )
            return ProviderResult(self.name, True, data=data)
        except Exception as exc:
            return ProviderResult(self.name, False, error=str(exc))


class WorldTimeWeatherProvider:
    name = "World Time & Weather"

    def fetch(self, http, location):
        try:
            data = http.get_json(
                "https://worldtimeweather.com/api/v1/cities.json",
                timeout=9,
                ttl_seconds=21600,
            )
            city = str(location.get("name") or location.get("city") or "").casefold().strip()
            match = None
            items = data if isinstance(data, list) else (data.get("cities") if isinstance(data, dict) else [])
            if isinstance(items, list) and city:
                for item in items:
                    if isinstance(item, dict) and city in str(item.get("name") or item.get("city") or "").casefold():
                        match = item
                        break
            return ProviderResult(self.name, True, data={"match": match, "count": len(items) if isinstance(items, list) else 0})
        except Exception as exc:
            return ProviderResult(self.name, False, error=str(exc))
