"""Generate a native calendar and optional weather-only ICS subscription."""
import asyncio
from datetime import timedelta
import logging
from aiohttp import ClientError, ClientTimeout, web
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import Platform
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from .const import DEFAULTS, DOMAIN
from .forecast import build_events, serialize_ics
from .details import dashboard_details
from .local_day import add_local_today, has_day, today_request

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.CALENDAR]


class WeatherCalendarCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(hass, _LOGGER, name=entry.title, update_interval=timedelta(minutes=30), config_entry=entry)
        self.entry = entry
        self.options = {**DEFAULTS, **entry.data, **entry.options}
        self.updated = None
        self.local_day = None

    @property
    def fresh(self):
        return (self.last_update_success and self.updated is not None
                and self.local_day == dt_util.now().date()
                and dt_util.utcnow() - self.updated < timedelta(hours=2))

    async def _dashboard_payloads(self, today, attributes, missing_today):
        """Match the dashboard's coarse location and public providers."""
        params = {"latitude": round(self.hass.config.latitude, 2),
                  "longitude": round(self.hass.config.longitude, 2),
                  "timezone": self.hass.config.time_zone}
        session = async_get_clientsession(self.hass)

        async def fetch(url, fields):
            try:
                async with session.get(url, params={**params, **fields}, timeout=ClientTimeout(total=15)) as response:
                    response.raise_for_status()
                    return await response.json()
            except (ClientError, TimeoutError, ValueError):
                # Do not log URLs containing the configured coordinates.
                _LOGGER.warning("Weather Calendar dashboard supplement temporarily unavailable")
                return None

        fields = {
            "daily": "uv_index_max,sunrise,sunset,precipitation_probability_max",
            "hourly": "relative_humidity_2m",
            "forecast_days": self.options["days"]}
        fallback = today_request(today, attributes) if missing_today else None
        if fallback:
            # Keep the full supplement horizon while explicitly selecting today's
            # local date. Future canonical forecasts are never replaced.
            fields.update({key: value for key, value in fallback.items() if key != "daily"})
            fields["end_date"] = (today + timedelta(days=self.options["days"] - 1)).isoformat()
            fields.pop("forecast_days")
            fields["daily"] += "," + fallback["daily"]
        if not self.options["show_details"]:
            if not fallback:
                return None, None
            fields.pop("hourly", None)
            fields["daily"] = fallback["daily"]
        weather, air = await asyncio.gather(
            fetch("https://api.open-meteo.com/v1/forecast", {
                **fields}),
            fetch("https://air-quality-api.open-meteo.com/v1/air-quality", {
                "hourly": "pm2_5",
                "forecast_days": min(7, self.options["days"])})
            if self.options["show_details"] else asyncio.sleep(0, result=None),
        )
        return weather, air

    async def _async_update_data(self):
        source = self.options["weather_entity"]
        state = self.hass.states.get(source)
        if state is None or state.state in ("unknown", "unavailable"):
            raise UpdateFailed("Source weather entity is not ready")
        try:
            response = await self.hass.services.async_call(
                "weather", "get_forecasts", {"entity_id": source, "type": "daily"},
                blocking=True, return_response=True)
            forecasts = (response or {}).get(source, {}).get("forecast", [])
            today = dt_util.now().date()
            sun = {}
            if self.options["show_sun"]:
                for offset in range(self.options["days"]):
                    day = today + timedelta(days=offset)
                    rise = get_astral_event_date(self.hass, "sunrise", day)
                    setting = get_astral_event_date(self.hass, "sunset", day)
                    if rise and setting:
                        sun[day] = (dt_util.as_local(rise).strftime("%H:%M"), dt_util.as_local(setting).strftime("%H:%M"))
            extra, notices = {}, []
            missing_today = not has_day(forecasts, today)
            if self.options["dashboard_details"] and (self.options["show_details"] or missing_today):
                weather, air = await self._dashboard_payloads(today, state.attributes, missing_today)
                forecasts = add_local_today(forecasts, weather, today, state.attributes)
                if missing_today and not has_day(forecasts, today):
                    notices.append("Local-day forecast temporarily unavailable.")
                if self.options["show_details"]:
                    extra = dashboard_details(weather or {}, air or {})
                if weather is None and self.options["show_details"]:
                    notices.append("UV, rain chance and humidity forecast temporarily unavailable.")
                if air is None and self.options["show_details"]:
                    notices.append("Outdoor air-quality forecast temporarily unavailable.")
            events = build_events(forecasts, state.attributes, self.options, today, self.entry.entry_id, sun,
                                  extra, notices)
            if not events:
                raise UpdateFailed("Source returned no usable daily forecasts")
            self.updated = dt_util.utcnow()
            self.local_day = today
            return events
        except HomeAssistantError as error:
            raise UpdateFailed("Unable to read source daily forecast") from error


class WeatherCalendarFeed(HomeAssistantView):
    """Explicit opt-in public feed; never exports other HA calendars or tokens."""
    url = "/api/weather_calendar/{entry_id}.ics"
    name = "api:weather_calendar:feed"
    requires_auth = False

    async def get(self, request, entry_id):
        hass = request.app["hass"]
        coordinator = hass.data.get(DOMAIN, {}).get(entry_id)
        if coordinator is None or not coordinator.options["public_feed"]:
            raise web.HTTPNotFound()
        if not coordinator.fresh:
            await coordinator.async_request_refresh()
        if not coordinator.fresh:
            # Do not silently advertise an old forecast as current weather.
            raise web.HTTPServiceUnavailable(text="Weather forecast temporarily unavailable", headers={"Retry-After": "300"})
        return web.Response(
            text=serialize_ics(coordinator.data, coordinator.options["name"], coordinator.updated),
            content_type="text/calendar", charset="utf-8",
            headers={"Cache-Control": "public, max-age=300", "X-Content-Type-Options": "nosniff"})


async def async_setup_entry(hass, entry):
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
        hass.http.register_view(WeatherCalendarFeed())
    coordinator = WeatherCalendarCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_options_updated(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id, None)
        return True
    return False
