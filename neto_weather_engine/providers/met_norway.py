from ..models import ProviderResult


class MetNorwayProvider:
    name = "MET Norway"

    def fetch(self, http, location):
        params = {
            "lat": float(location["latitude"]),
            "lon": float(location["longitude"]),
        }
        try:
            data = http.get_json(
                "https://api.met.no/weatherapi/locationforecast/2.0/compact",
                params,
                timeout=9,
                ttl_seconds=900,
            )
            return ProviderResult(self.name, True, data=data)
        except Exception as exc:
            return ProviderResult(self.name, False, error=str(exc))
