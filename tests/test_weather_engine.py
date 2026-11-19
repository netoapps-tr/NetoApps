from neto_weather_engine.engine import WeatherEngine
from neto_weather_engine.models import ProviderResult
from neto_weather_engine.providers.open_meteo import OpenMeteoForecastProvider
from neto_weather_engine.providers.wttr import WttrProvider


LOCATION = {
    "name": "Ankara",
    "country": "Türkiye",
    "latitude": 39.9334,
    "longitude": 32.8597,
}


FORECAST = {
    "current": {
        "temperature_2m": 18,
        "relative_humidity_2m": 55,
        "apparent_temperature": 17,
        "weather_code": 1,
        "wind_speed_10m": 12,
        "wind_gusts_10m": 20,
        "pressure_msl": 1015,
        "cloud_cover": 20,
        "precipitation": 0,
    },
    "daily": {
        "precipitation_probability_max": [10],
    },
}


class _CountingProvider:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def fetch(self, *args, **kwargs):
        self.calls += 1
        return self.result


def test_simple_weather_answer_does_not_wait_for_deep_sources():
    engine = WeatherEngine(http=object())
    engine.forecast = _CountingProvider(ProviderResult("forecast", True, data=FORECAST))
    engine.air = _CountingProvider(ProviderResult("air", True, data={}))
    engine.met = _CountingProvider(ProviderResult("met", True, data={}))

    answer = engine.answer("hava durumu", LOCATION, "Ankara")

    assert "Ankara için hava" in answer
    assert engine.forecast.calls == 1
    assert engine.air.calls == 0
    assert engine.met.calls == 0


def test_rain_question_keeps_deep_source_checks():
    engine = WeatherEngine(http=object())
    engine.forecast = _CountingProvider(ProviderResult("forecast", True, data=FORECAST))
    engine.air = _CountingProvider(ProviderResult("air", True, data={}))
    engine.met = _CountingProvider(ProviderResult("met", True, data={}))
    engine.radar = _CountingProvider(ProviderResult("radar", False, error="offline"))
    engine.seven_timer = _CountingProvider(ProviderResult("seven", False, error="offline"))
    engine.go_weather = _CountingProvider(ProviderResult("go", False, error="offline"))

    engine.answer("bugün yağmur var mı", LOCATION, "Ankara")

    assert engine.air.calls == 1
    assert engine.met.calls == 1
    assert engine.radar.calls == 1
    assert engine.seven_timer.calls == 1
    assert engine.go_weather.calls == 1


class _HttpRecorder:
    def __init__(self):
        self.calls = []

    def get_json(self, *args, **kwargs):
        self.calls.append(kwargs)
        return FORECAST


def test_weather_providers_bound_network_retries():
    http = _HttpRecorder()

    OpenMeteoForecastProvider().fetch(http, LOCATION)
    WttrProvider().fetch(http, LOCATION)

    assert len(http.calls) == 2
    assert all(call["timeout"] <= 5 for call in http.calls)
    assert all(call["retries"] == 0 for call in http.calls)
