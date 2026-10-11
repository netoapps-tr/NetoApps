"""Snapshot of the Weather section of public-apis/public-apis (2026-09-22).

The registry is deliberately broader than the active adapters. Entries that require
credentials or whose linked page does not expose a stable machine endpoint remain in
the registry and are reported honestly instead of being guessed.
"""

WEATHER_APIS = [
    ("Weatherstack", "apiKey", "global", "WEATHERSTACK_API_KEY", "https://weatherstack.com/"),
    ("7Timer!", "No", "global", "", "http://www.7timer.info/doc.php?lang=en"),
    ("AccuWeather", "apiKey", "global", "ACCUWEATHER_API_KEY", "https://developer.accuweather.com/apis"),
    ("Aemet", "apiKey", "Spain", "AEMET_API_KEY", "https://opendata.aemet.es/centrodedescargas/inicio"),
    ("APIXU", "apiKey", "global", "APIXU_API_KEY", "https://www.apixu.com/doc/request.aspx"),
    ("AQICN", "apiKey", "global", "AQICN_API_KEY", "https://aqicn.org/api/"),
    ("AviationWeather", "No", "global aviation", "", "https://www.aviationweather.gov/dataserver"),
    ("ColorfulClouds", "apiKey", "global", "COLORFULCLOUDS_API_KEY", "https://open.caiyunapp.com/ColorfulClouds_Weather_API"),
    ("Euskalmet", "apiKey", "Basque Country", "EUSKALMET_API_KEY", "https://opendata.euskadi.eus/api-euskalmet/-/api-de-euskalmet/"),
    ("Foreca", "OAuth", "global", "FORECA_TOKEN", "https://developer.foreca.com"),
    ("Hail History", "No", "US", "", "https://hail-history-noaa.netlify.app/api-docs.html"),
    ("HG Weather", "apiKey", "Brazil", "HG_WEATHER_API_KEY", "https://hgbrasil.com/status/weather"),
    ("Hong Kong Observatory", "No", "Hong Kong", "", "https://www.hko.gov.hk/en/abouthko/opendata_intro.htm"),
    ("IPMA", "No", "Portugal", "", "https://api.ipma.pt/open-data/"),
    ("KNMI", "apiKey", "Netherlands", "KNMI_API_KEY", "https://developer.dataplatform.knmi.nl/"),
    ("Meltema", "No", "global", "", "https://meltema.com/docs"),
    ("Météo-France", "apiKey", "France", "METEO_FRANCE_API_KEY", "https://portail-api.meteofrance.fr/"),
    ("Meteorologisk Institutt", "User-Agent", "global", "", "https://api.met.no/weatherapi/documentation"),
    ("Micro Weather", "apiKey", "global", "M3O_API_KEY", "https://m3o.com/weather/api"),
    ("NASA POWER", "No", "global", "", "https://power.larc.nasa.gov/docs/"),
    ("ODWeather", "No", "regional/resources", "", "https://api.oceandrivers.com/docs"),
    ("Oikolab", "apiKey", "global", "OIKOLAB_API_KEY", "https://docs.oikolab.com"),
    ("Open-Meteo", "No", "global", "", "https://open-meteo.com/"),
    ("Open-Meteo Ensemble", "No", "global", "", "https://open-meteo.com/en/docs/ensemble-api"),
    ("openSenseMap", "No", "global sensors", "", "https://api.opensensemap.org/"),
    ("OpenUV", "apiKey", "global", "OPENUV_API_KEY", "https://www.openuv.io"),
    ("OpenWeatherMap", "apiKey", "global", "OPENWEATHER_API_KEY", "https://openweathermap.org/api"),
    # public-apis marks Pirate Weather as No, but current Pirate Weather docs require a key.
    ("Pirate Weather", "apiKey*", "global", "PIRATE_WEATHER_API_KEY", "https://pirateweather.net/en/latest/"),
    ("QWeather", "apiKey", "global", "QWEATHER_API_KEY", "https://dev.qweather.com/en/"),
    ("Rainbow Weather", "apiKey", "global nowcast", "RAINBOW_API_KEY", "https://developer.rainbow.ai/"),
    ("RainViewer", "No", "global radar", "", "https://www.rainviewer.com/api.html"),
    ("Storm Glass", "apiKey", "global marine", "STORMGLASS_API_KEY", "https://stormglass.io/"),
    ("Tomorrow", "apiKey", "global", "TOMORROW_API_KEY", "https://docs.tomorrow.io"),
    ("US Weather", "No", "US", "", "https://www.weather.gov/documentation/services-web-api"),
    ("Visual Crossing", "apiKey", "global", "VISUAL_CROSSING_API_KEY", "https://www.visualcrossing.com/weather-api"),
    ("weather-api", "No", "global city", "", "https://github.com/robertoduessmann/weather-api"),
    ("WeatherAPI", "apiKey", "global", "WEATHERAPI_API_KEY", "https://www.weatherapi.com/"),
    ("Weatherbit", "apiKey", "global", "WEATHERBIT_API_KEY", "https://www.weatherbit.io/api"),
    ("WeatherTotals", "No", "US", "", "https://weathertotals.com/api"),
    ("World Time & Weather", "No", "400 cities", "", "https://worldtimeweather.com/api.html"),
    ("wttr.in", "No", "global", "", "https://wttr.in/:help"),
    ("Yandex.Weather", "apiKey", "global", "YANDEX_WEATHER_API_KEY", "https://yandex.com/dev/weather/"),
]

ACTIVE_ADAPTERS = {
    "Open-Meteo", "Open-Meteo Ensemble", "AviationWeather", "Meteorologisk Institutt",
    "NASA POWER", "openSenseMap", "RainViewer", "wttr.in", "7Timer!", "Hong Kong Observatory",
    "IPMA", "US Weather", "weather-api", "WeatherTotals", "ODWeather", "Hail History", "World Time & Weather",
}


def rows():
    return [
        {"name": n, "auth": a, "scope": s, "key_env": k, "docs": d, "adapter": n in ACTIVE_ADAPTERS}
        for n, a, s, k, d in WEATHER_APIS
    ]


def summary():
    data = rows()
    return {
        "total": len(data),
        "active_adapters": sum(1 for x in data if x["adapter"]),
        "keyless_or_user_agent": sum(1 for x in data if x["auth"] in {"No", "User-Agent"}),
        "credentialed": sum(1 for x in data if x["auth"] not in {"No", "User-Agent"}),
    }
