"""Pure forecast formatting and RFC 5545 serialization; no household data."""
from datetime import date, timedelta, timezone
import math
from .text import render

CONDITIONS = {
    "clear-night": ("🌙", "Clear"), "cloudy": ("☁️", "Cloudy"),
    "exceptional": ("⚠️", "Exceptional weather"), "fog": ("🌫️", "Fog"),
    "hail": ("🌨️", "Hail"), "lightning": ("🌩️", "Thunderstorms"),
    "lightning-rainy": ("⛈️", "Thunderstorms with rain"),
    "partlycloudy": ("⛅", "Partly cloudy"), "pouring": ("🌧️", "Heavy rain"),
    "rainy": ("🌧️", "Rain"), "snowy": ("❄️", "Snow"),
    "snowy-rainy": ("🌨️", "Rain and snow"), "sunny": ("☀️", "Sunny"),
    "windy": ("💨", "Windy"), "windy-variant": ("🌬️", "Windy and cloudy"),
}


def number(value):
    """Reject missing, nonfinite and malformed measurements."""
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def temperature(value, source, target):
    value = number(value)
    if value is None:
        return "–"
    if source != target:
        if (source, target) == ("°F", "°C"):
            value = (value - 32) * 5 / 9
        elif (source, target) == ("°C", "°F"):
            value = value * 9 / 5 + 32
    return str(round(value))


def wind_direction(bearing):
    degrees = number(bearing)
    return str(bearing) if degrees is None else ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][math.floor((degrees % 360) / 45 + 0.5) % 8]


def clock_time(value):
    """Compact local solar times without redundant timezone labels per row."""
    try:
        hour, minute = map(int, value.split(":"))
        return f"{hour % 12 or 12}:{minute:02} {'AM' if hour < 12 else 'PM'}"
    except (ValueError, AttributeError):
        return str(value)


def describe_day(forecast, extra, attributes, options, condition, sun, notices):
    """Group related daily values; reserve blank lines for the source footer."""
    if not options["show_details"]:
        return condition + ("\n\n" + forecast["forecast_source"] if forecast.get("forecast_source") else "")
    lines = [condition]

    def value(key):
        sample = number(forecast.get(key))
        return sample if sample is not None else number(extra.get(key))

    rain = []
    if (chance := value("precipitation_probability")) is not None:
        rain.append(f"Rain chance {math.floor(chance + 0.5)}%")
    if (amount := value("precipitation")) is not None and amount >= 0.01:
        display = f"{amount:.2f}" if amount < 0.1 else f"{amount:.1f}" if amount < 1 else str(math.floor(amount + 0.5))
        rain.append(f"{display} {attributes.get('precipitation_unit', '')}".rstrip())
    if rain:
        lines.append(" · ".join(rain))

    wind = []
    direction = wind_direction(forecast["wind_bearing"]) if forecast.get("wind_bearing") is not None else ""
    speed_unit = attributes.get("wind_speed_unit", "")
    if (speed := value("wind_speed")) is not None:
        wind.append(f"Wind {math.floor(speed + 0.5)} {speed_unit} {direction}".strip())
    elif direction:
        wind.append(f"Wind from {direction}")
    if (gust := value("wind_gust_speed")) is not None and (speed is None or math.floor(gust + 0.5) > math.floor(speed + 0.5)):
        wind.append(f"Gusts {math.floor(gust + 0.5)} {speed_unit}".rstrip())
    if wind:
        lines.append(" · ".join(wind))

    environment = []
    humidity = value("humidity")
    if humidity is None:
        humidity = number(extra.get("humidity_mean"))
        label = "Humidity (avg)"
    else:
        label = "Humidity"
    if humidity is not None:
        environment.append(f"{label} {math.floor(humidity + 0.5)}%")
    if (uv := value("uv_index")) is not None:
        environment.append(f"UV max {uv:.1f}")
    if environment:
        lines.append(" · ".join(environment))
    if (pressure := value("pressure")) is not None:
        lines.append(f"Pressure {pressure:g} {attributes.get('pressure_unit', '')}".rstrip())
    if (pm25 := number(extra.get("pm25_mean"))) is not None and pm25 >= 0:
        lines.append(f"Air Quality (avg) {math.floor(pm25 + 0.5)} PM2.5")

    if options["show_sun"]:
        if extra.get("sunrise") and extra.get("sunset"):
            sun = (extra["sunrise"], extra["sunset"])
        if sun:
            lines.append(f"Sunrise {clock_time(sun[0])} · Sunset {clock_time(sun[1])}")
    lines.extend(notices or [])
    footer = forecast.get("forecast_source", "Daily forecast")
    if options.get("dashboard_details"):
        footer += " · Open-Meteo / CAMS"
    return "\n".join(lines) + "\n\n" + footer


def build_events(forecasts, attributes, options, today, identity, sun_times=None, dashboard=None, notices=None):
    """Use daily date labels and exclusive DATE ends, including across DST.

    Neither current weather attributes nor current API readings supply event data.
    State attributes supply units only. Every event contains its own day forecast.
    """
    events = {}
    source = attributes.get("temperature_unit", "°C")
    target = options["temperature_unit"]
    target = source if target == "source" else target
    for forecast in forecasts:
        try:
            day = date.fromisoformat(str(forecast["datetime"])[:10])
        except (KeyError, ValueError, TypeError):
            continue
        if not today <= day < today + timedelta(days=options["days"]):
            continue
        icon, condition = CONDITIONS.get(forecast.get("condition"), ("🌡️", "Forecast"))
        low = temperature(forecast.get("templow"), source, target)
        high = temperature(forecast.get("temperature"), source, target)
        unit = target if options["show_units"] else "°"
        values = (low, high) if options["temperature_order"] == "low_high" else (high, low)
        title = f"{icon} {values[0]}{unit}/{values[1]}{unit}"
        extra = (dashboard or {}).get(day, {})
        description = describe_day(forecast, extra, attributes, options, condition,
                                   (sun_times or {}).get(day), notices)
        fields = {"icon": icon, "condition": condition, "high": high, "low": low,
                  "unit": unit, "location": options["location"], "date": day.isoformat(),
                  "details": description, "title": title}
        title = render(options.get("title_template"), fields, title)
        fields["title"] = title
        description = render(options.get("description_template"), fields, description)
        events[day] = {"start": day, "end": day + timedelta(days=1), "summary": title,
                       "description": description, "location": options["location"],
                       "uid": f"{identity}-{day.isoformat()}@weather-calendar"}
    return [events[day] for day in sorted(events)]


def escape(value):
    return str(value).replace("\\", "\\\\").replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n").replace(";", "\\;").replace(",", "\\,")


def fold(line):
    """Fold to 75 UTF-8 octets without splitting an emoji/codepoint."""
    parts, current = [], ""
    for char in line:
        if len((current + char).encode("utf-8")) > 75:
            parts.append(current)
            current = " "
        current += char
    return "\r\n".join([*parts, current])


def serialize_ics(events, name, updated):
    stamp = updated.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Weather Calendar//Home Assistant//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-CALNAME:" + escape(name), "REFRESH-INTERVAL;VALUE=DURATION:PT1H", "X-PUBLISHED-TTL:PT1H"]
    for event in events:
        lines.extend(["BEGIN:VEVENT", "UID:" + escape(event["uid"]), "DTSTAMP:" + stamp,
                      "LAST-MODIFIED:" + stamp, "DTSTART;VALUE=DATE:" + event["start"].strftime("%Y%m%d"),
                      "DTEND;VALUE=DATE:" + event["end"].strftime("%Y%m%d"),
                      "SUMMARY:" + escape(event["summary"]), "DESCRIPTION:" + escape(event["description"]),
                      "LOCATION:" + escape(event["location"]), "TRANSP:TRANSPARENT", "STATUS:CONFIRMED", "END:VEVENT"])
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(line) for line in lines) + "\r\n"
