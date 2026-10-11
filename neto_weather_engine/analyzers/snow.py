from __future__ import annotations

from datetime import datetime, timedelta
import re

from ..models import safe_float, safe_int


_MEMBER_RE = re.compile(r"^(?P<var>.+?)(?P<suffix>_member\d+)?$")


def _dt(value):
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def _window_indices(hourly, target="next24", reference_time=None):
    times = hourly.get("time") or []
    if not times:
        return []

    now_value = _dt(reference_time) if reference_time else None
    if now_value is None and isinstance(hourly.get("_current_time"), str):
        now_value = _dt(hourly.get("_current_time"))
    now_value = now_value or datetime.now().replace(minute=0, second=0, microsecond=0)

    parsed = [_dt(x) for x in times]
    if target == "tomorrow":
        tomorrow = now_value.date() + timedelta(days=1)
        return [i for i, t in enumerate(parsed) if t and t.date() == tomorrow]

    start = 0
    for i, t in enumerate(parsed):
        if t and t >= now_value:
            start = i
            break
    return list(range(start, min(start + 24, len(times))))


def _value(hourly, name, i, default=None):
    values = hourly.get(name) or []
    if i >= len(values):
        return default
    return safe_float(values[i], default)


def _deterministic_analysis(open_meteo, target="next24"):
    hourly = (open_meteo or {}).get("hourly") or {}
    current = (open_meteo or {}).get("current") or {}
    hourly = dict(hourly)
    hourly["_current_time"] = current.get("time")
    indices = _window_indices(hourly, target=target, reference_time=current.get("time"))
    times = hourly.get("time") or []

    best = {
        "score": 0,
        "time": None,
        "temperature": None,
        "wet_bulb": None,
        "dew_point": None,
        "probability": 0,
        "snowfall": 0.0,
        "freezing_level": None,
        "snowfall_height": None,
        "surface_temperature": None,
        "soil_temperature": None,
        "temp_925": None,
        "temp_850": None,
        "temp_700": None,
        "temp_500": None,
        "cape": None,
    }

    for i in indices:
        temp = _value(hourly, "temperature_2m", i, 99)
        wet = _value(hourly, "wet_bulb_temperature_2m", i)
        dew = _value(hourly, "dew_point_2m", i)
        prob = safe_int((hourly.get("precipitation_probability") or [])[i] if i < len(hourly.get("precipitation_probability") or []) else None, 0) or 0
        snow = _value(hourly, "snowfall", i, 0) or 0
        freeze = _value(hourly, "freezing_level_height", i)
        snowline = _value(hourly, "snowfall_height", i)
        surface = _value(hourly, "surface_temperature", i)
        soil = _value(hourly, "soil_temperature_0cm", i)
        t925 = _value(hourly, "temperature_925hPa", i)
        t850 = _value(hourly, "temperature_850hPa", i)
        t700 = _value(hourly, "temperature_700hPa", i)
        t500 = _value(hourly, "temperature_500hPa", i)
        cape = _value(hourly, "cape", i)

        score = 0.0
        if snow >= 0.1:
            score += 25
        elif snow > 0:
            score += 15
        if wet is not None:
            if wet <= 0:
                score += 18
            elif wet <= 1:
                score += 12
            elif wet <= 1.5:
                score += 6
        if temp <= 0:
            score += 12
        elif temp <= 1:
            score += 9
        elif temp <= 2:
            score += 4
        if prob >= 70:
            score += 12
        elif prob >= 45:
            score += 7
        if freeze is not None:
            if freeze <= 300:
                score += 10
            elif freeze <= 600:
                score += 6
        if t850 is not None:
            if t850 <= -5:
                score += 8
            elif t850 <= -3:
                score += 4
        if t925 is not None and t925 <= -1:
            score += 5
        if surface is not None and surface <= 1:
            score += 4
        if soil is not None and soil <= 1:
            score += 3
        if snowline is not None and freeze is not None and snowline <= freeze:
            score += 3

        if score > best["score"]:
            best.update({
                "score": min(round(score), 100),
                "time": times[i] if i < len(times) else None,
                "temperature": temp,
                "wet_bulb": wet,
                "dew_point": dew,
                "probability": prob,
                "snowfall": snow,
                "freezing_level": freeze,
                "snowfall_height": snowline,
                "surface_temperature": surface,
                "soil_temperature": soil,
                "temp_925": t925,
                "temp_850": t850,
                "temp_700": t700,
                "temp_500": t500,
                "cape": cape,
            })
    return best


def _member_keys(hourly, variable):
    keys = []
    for key in hourly:
        if key == variable or key.startswith(variable + "_member"):
            keys.append(key)
    return sorted(keys, key=lambda x: (x != variable, x))


def _suffix(key, variable):
    return key[len(variable):] if key.startswith(variable) else ""


def ensemble_snow_analysis(ensemble_data, target="next24", reference_time=None):
    models = (ensemble_data or {}).get("models") or {}
    if not models:
        return {"ok": False, "models": {}, "consensus": None, "time": None}

    model_time_ratios = {}
    for model_name, data in models.items():
        hourly = (data or {}).get("hourly") or {}
        times = hourly.get("time") or []
        fake_hourly = dict(hourly)
        indices = _window_indices(fake_hourly, target=target, reference_time=reference_time)
        snow_keys = _member_keys(hourly, "snowfall")
        if not snow_keys or not times:
            continue

        wet_keys = set(_member_keys(hourly, "wet_bulb_temperature_2m"))
        temp_keys = set(_member_keys(hourly, "temperature_2m"))
        ratios = {}
        for i in indices:
            yes = 0
            valid = 0
            for snow_key in snow_keys:
                snow_values = hourly.get(snow_key) or []
                if i >= len(snow_values):
                    continue
                snow = safe_float(snow_values[i])
                if snow is None:
                    continue
                suffix = _suffix(snow_key, "snowfall")
                wet_key = "wet_bulb_temperature_2m" + suffix
                temp_key = "temperature_2m" + suffix
                wet = safe_float((hourly.get(wet_key) or [None] * (i + 1))[i]) if wet_key in wet_keys and i < len(hourly.get(wet_key) or []) else None
                temp = safe_float((hourly.get(temp_key) or [None] * (i + 1))[i]) if temp_key in temp_keys and i < len(hourly.get(temp_key) or []) else None
                valid += 1
                cold_enough = (wet is None or wet <= 1.5) and (temp is None or temp <= 3.0)
                if snow >= 0.05 and cold_enough:
                    yes += 1
            if valid:
                ratios[times[i]] = {"yes": yes, "total": valid, "ratio": yes / valid}
        if ratios:
            model_time_ratios[model_name] = ratios

    all_times = sorted({t for values in model_time_ratios.values() for t in values})
    if not all_times:
        return {"ok": False, "models": {}, "consensus": None, "time": None}

    best_time = None
    best_ratio = -1.0
    for t in all_times:
        yes = 0
        total = 0
        for ratios in model_time_ratios.values():
            item = ratios.get(t)
            if item:
                yes += item["yes"]
                total += item["total"]
        ratio = (yes / total) if total else 0.0
        if ratio > best_ratio:
            best_ratio = ratio
            best_time = t

    model_summary = {}
    yes_total = 0
    member_total = 0
    for model_name, ratios in model_time_ratios.items():
        item = ratios.get(best_time)
        if not item:
            continue
        model_summary[model_name] = item
        yes_total += item["yes"]
        member_total += item["total"]

    return {
        "ok": bool(model_summary),
        "models": model_summary,
        "consensus": (yes_total / member_total) if member_total else None,
        "yes": yes_total,
        "total": member_total,
        "time": best_time,
    }



def _risk_label(score):
    score = int(max(0, min(score, 100)))
    if score >= 80:
        return "ÇOK YÜKSEK"
    if score >= 65:
        return "YÜKSEK"
    if score >= 45:
        return "ORTA"
    if score >= 25:
        return "DÜŞÜK"
    return "ÇOK DÜŞÜK"


def _ground_hold_score(det, snow_score):
    """Yüzeyde tutma için açıklanabilir bir iç skor üretir.

    Bu resmi meteorolojik olasılık değildir; NetOps'un yüzey/toprak sıcaklığı,
    wet-bulb ve kar şiddetini birleştiren karar skorudur.
    """
    score = float(snow_score) * 0.30
    surface = det.get("surface_temperature")
    soil = det.get("soil_temperature")
    wet = det.get("wet_bulb")
    snow = det.get("snowfall") or 0.0

    if surface is not None:
        if surface <= 0:
            score += 30
        elif surface <= 1:
            score += 22
        elif surface <= 2:
            score += 12
        elif surface <= 4:
            score += 4
    if soil is not None:
        if soil <= 0:
            score += 20
        elif soil <= 1:
            score += 14
        elif soil <= 2:
            score += 7
    if wet is not None:
        if wet <= 0:
            score += 10
        elif wet <= 1:
            score += 6
    if snow >= 0.5:
        score += 10
    elif snow >= 0.1:
        score += 5

    # Kar riski yok denecek kadar azsa sıcak zeminin tek başına yüksek tutma skoru
    # üretmesini engelle.
    if snow_score < 15:
        score = min(score, 12)
    return max(0, min(round(score), 100))

def snow_risk(open_meteo, ensemble_data=None, target="next24"):
    det = _deterministic_analysis(open_meteo, target=target)
    ens = (
        ensemble_snow_analysis(
            ensemble_data,
            target=target,
            reference_time=((open_meteo or {}).get("current") or {}).get("time"),
        )
        if ensemble_data
        else {"ok": False}
    )

    score = det["score"]
    if ens.get("ok") and ens.get("consensus") is not None:
        # Ensemble olasılığı ana sinyal; deterministik fiziksel koşullar düzeltici.
        score = round((ens["consensus"] * 70.0) + (det["score"] * 0.30))
    score = max(0, min(int(score), 100))
    hold_score = _ground_hold_score(det, score)

    lines = [
        "KAR DEĞERLENDİRMESİ",
        f"Kar riski: %{score} ({_risk_label(score)})",
        f"Yerde tutma skoru: %{hold_score} ({_risk_label(hold_score)})",
    ]

    if ens.get("ok"):
        lines.extend(["", "ENSEMBLE MODEL MUTABAKATI"])
        # Sabit sıra okunabilirliği korur; yalnız başarıyla dönen modeller gösterilir.
        order = ["ECMWF", "GFS", "ICON", "WeatherNext"]
        shown = set()
        for name in order + list(ens["models"].keys()):
            if name in shown or name not in ens["models"]:
                continue
            shown.add(name)
            item = ens["models"][name]
            lines.append(
                f"{name}: {item['yes']}/{item['total']} üye kar gösteriyor "
                f"(%{round(item['ratio'] * 100)})"
            )
        if ens.get("consensus") is not None:
            lines.append(
                f"Genel mutabakat: {ens['yes']}/{ens['total']} üye (%{round(ens['consensus'] * 100)})"
            )
            if ens.get("time"):
                lines.append(f"En güçlü ortak kar saati: {ens['time']}")

    lines.extend(["", "ATMOSFER"])
    if det.get("time"):
        lines.append(f"Analiz saati: {det['time']}")
    if det.get("temperature") is not None:
        lines.append(f"2 m sıcaklık: {det['temperature']:.1f}°C")
    if det.get("wet_bulb") is not None:
        lines.append(f"Wet-bulb: {det['wet_bulb']:.1f}°C")
    if det.get("dew_point") is not None:
        lines.append(f"Çiy noktası: {det['dew_point']:.1f}°C")
    if det.get("temp_925") is not None:
        lines.append(f"925 hPa sıcaklık: {det['temp_925']:.1f}°C")
    if det.get("temp_850") is not None:
        lines.append(f"850 hPa sıcaklık: {det['temp_850']:.1f}°C")
    if det.get("temp_700") is not None:
        lines.append(f"700 hPa sıcaklık: {det['temp_700']:.1f}°C")
    if det.get("temp_500") is not None:
        lines.append(f"500 hPa sıcaklık: {det['temp_500']:.1f}°C")
    if det.get("freezing_level") is not None:
        lines.append(f"0°C seviyesi: {round(det['freezing_level'])} m")
    if det.get("snowfall_height") is not None:
        lines.append(f"Kar seviyesi: {round(det['snowfall_height'])} m")
    if det.get("cape") is not None:
        lines.append(f"CAPE: {round(det['cape'])} J/kg")
    if det.get("snowfall") is not None:
        lines.append(f"Saatlik kar: {det['snowfall']:.2f} cm")

    surface = det.get("surface_temperature")
    soil = det.get("soil_temperature")
    if surface is not None or soil is not None:
        lines.extend(["", "YÜZEY / TUTMA"])
        if surface is not None:
            lines.append(f"Yüzey sıcaklığı: {surface:.1f}°C")
        if soil is not None:
            lines.append(f"Toprak sıcaklığı: {soil:.1f}°C")

    return "\n".join(lines)

def deterministic_model_analysis(model_data, reference_time=None, target="next24"):
    models = (model_data or {}).get("models") or {}
    summary = {}
    for name, data in models.items():
        hourly = (data or {}).get("hourly") or {}
        times = hourly.get("time") or []
        indices = _window_indices(hourly, target=target, reference_time=reference_time)
        best = {"snowfall": 0.0, "time": None, "temperature": None, "wet_bulb": None, "temp_850": None}
        for i in indices:
            snow = _value(hourly, "snowfall", i, 0) or 0
            if snow >= best["snowfall"]:
                best = {
                    "snowfall": snow,
                    "time": times[i] if i < len(times) else None,
                    "temperature": _value(hourly, "temperature_2m", i),
                    "wet_bulb": _value(hourly, "wet_bulb_temperature_2m", i),
                    "temp_850": _value(hourly, "temperature_850hPa", i),
                }
        if times:
            summary[name] = best
    return summary


def deterministic_model_line(model_data, reference_time=None, target="next24"):
    summary = deterministic_model_analysis(model_data, reference_time=reference_time, target=target)
    if not summary:
        return ""
    lines = ["DETERMİNİSTİK MODELLER"]
    for name in ["ECMWF", "GFS", "ICON"] + list(summary.keys()):
        if name not in summary:
            continue
        item = summary.pop(name)
        snow = item.get("snowfall") or 0
        temp = item.get("temperature")
        wet = item.get("wet_bulb")
        t850 = item.get("temp_850")
        parts = [f"maks. kar {snow:.2f} cm/saat"]
        if temp is not None:
            parts.append(f"2 m {temp:.1f}°C")
        if wet is not None:
            parts.append(f"wet-bulb {wet:.1f}°C")
        if t850 is not None:
            parts.append(f"850 hPa {t850:.1f}°C")
        lines.append(f"{name}: " + ", ".join(parts))
    return "\n".join(lines)

