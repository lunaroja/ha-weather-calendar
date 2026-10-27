"""Recover a missing home-local day from a fresh, explicitly dated forecast."""
import math


def has_day(forecasts, today):
    return any(str(row.get("datetime", ""))[:10] == today.isoformat() for row in forecasts)


def today_request(today, attributes):
    """Request the source entity's units; never guess unsupported units."""
    temperature = {"°F": "fahrenheit", "°C": "celsius"}.get(attributes.get("temperature_unit"))
    precipitation = {"in": "inch", "mm": "mm"}.get(attributes.get("precipitation_unit"))
    if temperature is None or precipitation is None:
        return None
    return {
        "start_date": today.isoformat(), "end_date": today.isoformat(),
        "temperature_unit": temperature, "precipitation_unit": precipitation,
        "daily": "temperature_2m_max,temperature_2m_min,weather_code,precipitation_sum",
    }


def local_today(payload, today, attributes):
    """Accept only the requested date and verified units, without observations."""
    if not payload or not today_request(today, attributes):
        return None
    units = payload.get("daily_units", {})
    if (units.get("temperature_2m_max") != attributes["temperature_unit"]
            or units.get("temperature_2m_min") != attributes["temperature_unit"]
            or units.get("precipitation_sum") != today_request(today, attributes)["precipitation_unit"]):
        return None
    daily = payload.get("daily", {})
    try:
        index = daily.get("time", []).index(today.isoformat())
        high, low, code = (daily[key][index] for key in
                           ("temperature_2m_max", "temperature_2m_min", "weather_code"))
        if any(isinstance(value, bool) or not isinstance(value, (int, float))
               or not math.isfinite(value) for value in (high, low, code)):
            return None
        # WMO codes, including mixed precipitation and freezing rain.
        condition = (
            "sunny" if code == 0 else "partlycloudy" if code in (1, 2) else
            "cloudy" if code == 3 else "fog" if code in (45, 48) else
            "rainy" if code in (51, 53, 55, 61, 63, 65, 80, 81, 82) else
            "snowy-rainy" if code in (56, 57, 66, 67) else
            "snowy" if code in (71, 73, 75, 77, 85, 86) else
            "lightning-rainy" if code in (95, 96, 99) else None)
        if condition is None:
            return None
        row = {"datetime": today.isoformat(), "temperature": high, "templow": low,
               "condition": condition, "forecast_source": "Open-Meteo local-day forecast"}
        amount = daily.get("precipitation_sum", [])[index]
        if isinstance(amount, (int, float)) and not isinstance(amount, bool) and math.isfinite(amount) and amount >= 0:
            row["precipitation"] = amount
        return row
    except (ValueError, KeyError, IndexError, TypeError):
        return None


def add_local_today(forecasts, payload, today, attributes):
    """Canonical daily labels always win; never move another day's forecast."""
    if has_day(forecasts, today):
        return forecasts
    row = local_today(payload, today, attributes)
    return [*forecasts, row] if row else forecasts
