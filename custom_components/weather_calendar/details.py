"""Normalize public Open-Meteo dashboard fields by local forecast date."""
from datetime import date
import math


def finite(value):
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def at(series, key, index):
    values = series.get(key, [])
    return values[index] if 0 <= index < len(values) else None


def daily_mean(series, field, day):
    # Keep local wall-clock labels. On DST days Open-Meteo can return 23/25 hours.
    samples = [finite(at(series, field, i)) for i, stamp in enumerate(series.get("time", [])) if str(stamp).startswith(day + "T")]
    values = [value for value in samples if value is not None]
    # Do not present a partial provider horizon as a complete daily average.
    return sum(values) / len(values) if len(values) >= 23 and len(values) == len(samples) else None


def dashboard_details(weather, air):
    """Return only allowlisted weather fields, never API location metadata."""
    daily, hourly = weather.get("daily", {}), weather.get("hourly", {})
    air_hourly = air.get("hourly", {})
    result = {}
    for i, stamp in enumerate(daily.get("time", [])):
        try:
            day = date.fromisoformat(stamp)
        except (ValueError, TypeError):
            continue
        fields = {}
        for source, target in (("uv_index_max", "uv_index"), ("precipitation_probability_max", "precipitation_probability")):
            value = finite(at(daily, source, i))
            if value is not None:
                fields[target] = value
        for key in ("sunrise", "sunset"):
            value = at(daily, key, i)
            if isinstance(value, str) and value.startswith(stamp + "T"):
                fields[key] = value[11:16]
        fields["humidity_mean"] = daily_mean(hourly, "relative_humidity_2m", stamp)
        fields["pm25_mean"] = (daily_mean(air_hourly, "pm2_5", stamp)
                               if air.get("hourly_units", {}).get("pm2_5") in ("μg/m³", "µg/m³") else None)
        result[day] = fields
    return result
