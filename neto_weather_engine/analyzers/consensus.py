from ..models import safe_float


def forecast_consensus(open_meteo, met_norway):
    """Cross-provider sanity check. This is not an ensemble probability."""
    current = (open_meteo or {}).get("current") or {}
    om_temp = safe_float(current.get("temperature_2m"))
    met_temp = None
    try:
        details = met_norway["properties"]["timeseries"][0]["data"]["instant"]["details"]
        met_temp = safe_float(details.get("air_temperature"))
    except Exception:
        met_temp = None

    if om_temp is None or met_temp is None:
        return ""
    diff = abs(om_temp - met_temp)
    if diff <= 2:
        return "Kaynak kontrolü: Open-Meteo ve MET Norway sıcaklıkları birbirine yakın."
    if diff <= 4:
        return "Kaynak kontrolü: Open-Meteo ve MET Norway arasında küçük sıcaklık farkı var."
    return "Kaynak kontrolü: Open-Meteo ve MET Norway arasında belirgin sıcaklık farkı var."
