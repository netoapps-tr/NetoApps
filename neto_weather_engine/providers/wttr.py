import urllib.parse

from ..models import ProviderResult


class WttrProvider:
    name = "wttr.in"

    def fetch(self, http, location):
        loc = f"{float(location['latitude']):.4f},{float(location['longitude']):.4f}"
        encoded = urllib.parse.quote(loc)
        try:
            data = http.get_json(
                f"https://wttr.in/{encoded}",
                {"format": "j1", "lang": "tr"},
                timeout=4,
                ttl_seconds=900,
                retries=0,
            )
            return ProviderResult(self.name, True, data=data)
        except Exception as exc:
            return ProviderResult(self.name, False, error=str(exc))
