from ..models import ProviderResult


class OpenMeteoForecastProvider:
    name = "Open-Meteo Forecast"

    def fetch(self, http, location):
        params = {
            "latitude": float(location["latitude"]),
            "longitude": float(location["longitude"]),
            "current": ",".join([
                "temperature_2m",
                "relative_humidity_2m",
                "apparent_temperature",
                "precipitation",
                "rain",
                "showers",
                "snowfall",
                "weather_code",
                "cloud_cover",
                "pressure_msl",
                "surface_pressure",
                "wind_speed_10m",
                "wind_direction_10m",
                "wind_gusts_10m",
            ]),
            "hourly": ",".join([
                "temperature_2m",
                "relative_humidity_2m",
                "dew_point_2m",
                "wet_bulb_temperature_2m",
                "apparent_temperature",
                "precipitation_probability",
                "precipitation",
                "rain",
                "showers",
                "snowfall",
                "snow_depth",
                "weather_code",
                "cloud_cover",
                "visibility",
                "wind_speed_10m",
                "wind_direction_10m",
                "wind_gusts_10m",
                "freezing_level_height",
                "snowfall_height",
                "surface_temperature",
                "soil_temperature_0cm",
                "cape",
                "convective_inhibition",
                "temperature_925hPa",
                "temperature_850hPa",
                "temperature_700hPa",
                "temperature_500hPa",
                "relative_humidity_925hPa",
                "relative_humidity_850hPa",
                "relative_humidity_700hPa",
                "relative_humidity_500hPa",
                "geopotential_height_925hPa",
                "geopotential_height_850hPa",
                "geopotential_height_700hPa",
                "geopotential_height_500hPa",
            ]),
            "daily": ",".join([
                "weather_code",
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "rain_sum",
                "showers_sum",
                "snowfall_sum",
                "precipitation_probability_max",
                "wind_speed_10m_max",
                "wind_gusts_10m_max",
            ]),
            "timezone": "auto",
            "forecast_days": 7,
            "wind_speed_unit": "kmh",
        }
        try:
            data = http.get_json(
                "https://api.open-meteo.com/v1/forecast",
                params,
                timeout=10,
                ttl_seconds=600,
            )
            return ProviderResult(self.name, True, data=data)
        except Exception as exc:
            return ProviderResult(self.name, False, error=str(exc))


class OpenMeteoAirProvider:
    name = "Open-Meteo Air Quality"

    VARIABLES = [
        "pm10",
        "pm2_5",
        "carbon_monoxide",
        "carbon_dioxide",
        "nitrogen_dioxide",
        "sulphur_dioxide",
        "ozone",
        "ammonia",
        "methane",
        "aerosol_optical_depth",
        "dust",
        "uv_index",
        "european_aqi",
        "us_aqi",
        "alder_pollen",
        "birch_pollen",
        "grass_pollen",
        "mugwort_pollen",
        "olive_pollen",
        "ragweed_pollen",
    ]

    def fetch(self, http, location):
        variables = ",".join(self.VARIABLES)
        params = {
            "latitude": float(location["latitude"]),
            "longitude": float(location["longitude"]),
            "current": variables,
            "hourly": variables,
            "timezone": "auto",
            "forecast_days": 2,
        }
        try:
            data = http.get_json(
                "https://air-quality-api.open-meteo.com/v1/air-quality",
                params,
                timeout=9,
                ttl_seconds=900,
            )
            return ProviderResult(self.name, True, data=data)
        except Exception as exc:
            return ProviderResult(self.name, False, error=str(exc))


class OpenMeteoEnsembleProvider:
    """Fetch individual snow-relevant ensemble members from the major global models."""

    name = "Open-Meteo Ensemble"
    MODELS = {
        "ECMWF": "ecmwf_ifs025_ensemble",
        "GFS": "ncep_gefs025",
        "ICON": "dwd_icon_global_eps",
        "WeatherNext": "google_weathernext2_ensemble",
    }
    HOURLY = [
        "temperature_2m",
        "wet_bulb_temperature_2m",
        "snowfall",
        "snow_depth",
        "freezing_level_height",
        "snowfall_height",
        "temperature_925hPa",
        "temperature_850hPa",
    ]

    def fetch(self, http, location, forecast_hours=48):
        model_results = {}
        errors = {}
        for label, model in self.MODELS.items():
            params = {
                "latitude": float(location["latitude"]),
                "longitude": float(location["longitude"]),
                "models": model,
                "hourly": ",".join(self.HOURLY),
                "timezone": "auto",
                "forecast_hours": int(forecast_hours),
                "wind_speed_unit": "kmh",
            }
            try:
                model_results[label] = http.get_json(
                    "https://ensemble-api.open-meteo.com/v1/ensemble",
                    params,
                    timeout=15,
                    ttl_seconds=1800,
                )
            except Exception as exc:
                errors[label] = str(exc)

        if model_results:
            return ProviderResult(
                self.name,
                True,
                data={"models": model_results, "errors": errors},
            )
        return ProviderResult(self.name, False, error="; ".join(f"{k}: {v}" for k, v in errors.items()))


class OpenMeteoFloodProvider:
    name = "Open-Meteo Flood"

    def fetch(self, http, location):
        params = {
            "latitude": float(location["latitude"]),
            "longitude": float(location["longitude"]),
            "daily": ",".join([
                "river_discharge",
                "river_discharge_mean",
                "river_discharge_median",
                "river_discharge_max",
                "river_discharge_p25",
                "river_discharge_p75",
            ]),
            "forecast_days": 14,
            "timezone": "auto",
        }
        try:
            data = http.get_json(
                "https://flood-api.open-meteo.com/v1/flood",
                params,
                timeout=12,
                ttl_seconds=3600,
            )
            return ProviderResult(self.name, True, data=data)
        except Exception as exc:
            return ProviderResult(self.name, False, error=str(exc))


class OpenMeteoModelsProvider:
    """Fetch separate deterministic ECMWF/GFS/ICON forecasts for comparison."""

    name = "Open-Meteo Model Compare"
    MODELS = {
        "ECMWF": "ecmwf_ifs",
        "GFS": "ncep_gfs_global",
        "ICON": "icon_global",
    }
    HOURLY = [
        "temperature_2m",
        "wet_bulb_temperature_2m",
        "precipitation",
        "snowfall",
        "freezing_level_height",
        "snowfall_height",
        "temperature_925hPa",
        "temperature_850hPa",
    ]

    def fetch(self, http, location, forecast_hours=48):
        model_results = {}
        errors = {}
        for label, model in self.MODELS.items():
            params = {
                "latitude": float(location["latitude"]),
                "longitude": float(location["longitude"]),
                "models": model,
                "hourly": ",".join(self.HOURLY),
                "timezone": "auto",
                "forecast_hours": int(forecast_hours),
                "wind_speed_unit": "kmh",
            }
            try:
                model_results[label] = http.get_json(
                    "https://api.open-meteo.com/v1/forecast",
                    params,
                    timeout=12,
                    ttl_seconds=1800,
                )
            except Exception as exc:
                errors[label] = str(exc)
        if model_results:
            return ProviderResult(self.name, True, data={"models": model_results, "errors": errors})
        return ProviderResult(self.name, False, error="; ".join(f"{k}: {v}" for k, v in errors.items()))
