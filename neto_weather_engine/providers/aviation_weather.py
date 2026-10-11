from ..models import ProviderResult


class AviationWeatherProvider:
    name = "AviationWeather METAR"

    def fetch(self, http, location):
        lat = float(location["latitude"])
        lon = float(location["longitude"])
        delta = 1.0
        bbox = f"{lat - delta:.3f},{lon - delta:.3f},{lat + delta:.3f},{lon + delta:.3f}"
        params = {
            "bbox": bbox,
            "format": "json",
        }
        try:
            data = http.get_json(
                "https://aviationweather.gov/api/data/metar",
                params,
                timeout=8,
                ttl_seconds=900,
            )
            if isinstance(data, list):
                return ProviderResult(self.name, True, data={"stations": data[:5], "count": len(data)})
            # A valid query with no METAR in the search box is not a provider failure.
            if data is None:
                return ProviderResult(self.name, True, data={"stations": [], "count": 0, "note": "no recent METAR in bbox"})
            return ProviderResult(self.name, True, data={"stations": [], "count": 0})
        except Exception as exc:
            return ProviderResult(self.name, False, error=str(exc))
