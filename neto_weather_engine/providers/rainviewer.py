from ..models import ProviderResult


class RainViewerProvider:
    name = "RainViewer Radar"

    def fetch(self, http, location):
        try:
            data = http.get_json(
                "https://api.rainviewer.com/public/weather-maps.json",
                timeout=7,
                ttl_seconds=600,
            )
            return ProviderResult(self.name, True, data=data)
        except Exception as exc:
            return ProviderResult(self.name, False, error=str(exc))
