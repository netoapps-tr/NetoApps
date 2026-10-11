from ..models import ProviderResult


class OpenSenseMapProvider:
    name = "openSenseMap"

    def fetch(self, http, location):
        lat = float(location["latitude"])
        lon = float(location["longitude"])
        params = {
            "near": f"{lat},{lon}",
            "maxDistance": 10000,
        }
        try:
            data = http.get_json(
                "https://api.opensensemap.org/boxes",
                params,
                timeout=8,
                ttl_seconds=1800,
            )
            boxes = data if isinstance(data, list) else []
            return ProviderResult(self.name, True, data={"boxes": boxes[:5]})
        except Exception as exc:
            return ProviderResult(self.name, False, error=str(exc))
