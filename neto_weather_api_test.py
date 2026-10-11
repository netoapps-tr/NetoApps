from __future__ import annotations

import json
import os
import time
from pathlib import Path

from neto_weather_engine.http_client import HttpClient
from neto_weather_engine.providers import (
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
from neto_weather_engine.weather_catalog import rows as catalog_rows

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "weather_api_test_report.json"

LOCATIONS = {
    "global": {"name": "Ankara", "country": "Türkiye", "latitude": 39.9334, "longitude": 32.8597},
    "hongkong": {"name": "Hong Kong", "country": "Hong Kong", "latitude": 22.3193, "longitude": 114.1694},
    "portugal": {"name": "Lisbon", "country": "Portugal", "latitude": 38.7223, "longitude": -9.1393},
    "us": {"name": "Washington", "country": "United States", "latitude": 38.9072, "longitude": -77.0369},
}


def cases():
    return [
        ("Open-Meteo", OpenMeteoForecastProvider(), LOCATIONS["global"], {}),
        ("Open-Meteo Air", OpenMeteoAirProvider(), LOCATIONS["global"], {}),
        ("Open-Meteo Ensemble", OpenMeteoEnsembleProvider(), LOCATIONS["global"], {"forecast_hours": 12}),
        ("Open-Meteo Models", OpenMeteoModelsProvider(), LOCATIONS["global"], {"forecast_hours": 12}),
        ("Open-Meteo Flood", OpenMeteoFloodProvider(), LOCATIONS["global"], {}),
        ("AviationWeather", AviationWeatherProvider(), LOCATIONS["global"], {}),
        ("Meteorologisk Institutt", MetNorwayProvider(), LOCATIONS["global"], {}),
        ("NASA POWER", NasaPowerProvider(), LOCATIONS["global"], {}),
        ("openSenseMap", OpenSenseMapProvider(), LOCATIONS["global"], {}),
        ("RainViewer", RainViewerProvider(), LOCATIONS["global"], {}),
        ("wttr.in", WttrProvider(), LOCATIONS["global"], {}),
        ("7Timer!", SevenTimerProvider(), LOCATIONS["global"], {}),
        ("weather-api", GoWeatherProvider(), LOCATIONS["global"], {}),
        ("Hong Kong Observatory", HongKongObservatoryProvider(), LOCATIONS["hongkong"], {}),
        ("IPMA", IpmaProvider(), LOCATIONS["portugal"], {}),
        ("US Weather", UsWeatherProvider(), LOCATIONS["us"], {}),
        ("WeatherTotals", WeatherTotalsProvider(), LOCATIONS["us"], {}),
        ("Hail History", HailHistoryProvider(), LOCATIONS["us"], {}),
        ("World Time & Weather", WorldTimeWeatherProvider(), LOCATIONS["global"], {}),
        ("ODWeather", OdWeatherProvider(), LOCATIONS["global"], {}),
    ]


def main():
    http = HttpClient(user_agent="NetOps-One/10.39 weather-api-selftest")
    results = []
    print("NETOPS WEATHER API SELF TEST")
    print("=" * 72)
    for label, provider, location, kwargs in cases():
        started = time.perf_counter()
        try:
            result = provider.fetch(http, location, **kwargs)
            ok = bool(result.ok)
            error = result.error or ""
        except Exception as exc:
            ok = False
            error = f"{type(exc).__name__}: {exc}"
        ms = round((time.perf_counter() - started) * 1000)
        upstream_unavailable = (not ok and "upstream no-auth ODWeather endpoint unavailable/retired" in error)
        state = "PASS" if ok else ("DEAD" if upstream_unavailable else "FAIL")
        print(f"{state:4} {label:30} {ms:6} ms {error[:120]}")
        results.append({
            "name": label, "ok": ok, "latency_ms": ms, "error": error,
            "upstream_unavailable": upstream_unavailable,
        })

    tested_names = {r[0] for r in cases()}
    live_by_name = {r["name"]: r for r in results}
    catalog = []
    print("\nCATALOG / CREDENTIAL STATUS")
    print("=" * 72)
    for row in catalog_rows():
        name = row["name"]
        live = live_by_name.get(name)
        if live and live.get("upstream_unavailable"):
            status = "DEAD"
        elif name in tested_names or (name == "Open-Meteo" and "Open-Meteo" in tested_names):
            status = "TESTED"
        elif row["key_env"]:
            status = "KEY-READY" if os.getenv(row["key_env"]) else "SKIP-NO-KEY"
        elif row["adapter"]:
            status = "ADAPTER"
        else:
            status = "CATALOG-ONLY"
        print(f"{status:12} {name:28} {row['auth']:10} {row['scope']}")
        catalog.append({**row, "status": status})

    payload = {
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "live_tests": results,
        "catalog": catalog,
        "pass": sum(1 for x in results if x["ok"]),
        "fail": sum(1 for x in results if not x["ok"] and not x.get("upstream_unavailable")),
        "upstream_unavailable": sum(1 for x in results if x.get("upstream_unavailable")),
        "note": "Credential-required providers are not called without user-owned keys. DEAD means the public-apis catalog entry exists but its upstream no-auth endpoint is unavailable/retired; this is not counted as a NetOps test failure.",
    }
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nReport: {REPORT}")
    return 0 if payload["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
