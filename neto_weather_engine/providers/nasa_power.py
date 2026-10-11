from datetime import datetime, timedelta

from ..models import ProviderResult


class NasaPowerProvider:
    name = "NASA POWER"

    def fetch(self, http, location):
        day = datetime.utcnow().date() - timedelta(days=2)
        stamp = day.strftime("%Y%m%d")
        params = {
            "parameters": "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR",
            "community": "AG",
            "longitude": float(location["longitude"]),
            "latitude": float(location["latitude"]),
            "start": stamp,
            "end": stamp,
            "format": "JSON",
        }
        try:
            data = http.get_json(
                "https://power.larc.nasa.gov/api/temporal/daily/point",
                params,
                timeout=10,
                ttl_seconds=43200,
            )
            return ProviderResult(self.name, True, data=data)
        except Exception as exc:
            return ProviderResult(self.name, False, error=str(exc))
