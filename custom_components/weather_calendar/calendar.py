"""Read-only native weather calendar."""
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([WeatherCalendar(hass.data[DOMAIN][entry.entry_id], entry)])


class WeatherCalendar(CoordinatorEntity, CalendarEntity):
    _attr_icon = "mdi:weather-partly-cloudy"
    _attr_initial_color = "#F4C430"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_name = coordinator.options["name"]
        self._attr_unique_id = entry.entry_id

    @property
    def available(self):
        return self.coordinator.fresh

    @property
    def extra_state_attributes(self):
        options = self.coordinator.options
        return {
            "weather_entity": options["weather_entity"],
            "forecast_updated": self.coordinator.updated.isoformat() if self.coordinator.updated else None,
            "subscription_path": f"/api/weather_calendar/{self.coordinator.entry.entry_id}.ics" if options["public_feed"] else None,
        }

    @property
    def event(self):
        today = dt_util.now().date()
        return next((CalendarEvent(**event) for event in (self.coordinator.data or []) if event["end"] > today), None)

    async def async_get_events(self, hass, start_date, end_date):
        # Compare midnights as instants to honor exclusive ranges and DST.
        if not self.coordinator.fresh:
            await self.coordinator.async_request_refresh()
        if not self.coordinator.fresh:
            from homeassistant.exceptions import HomeAssistantError
            raise HomeAssistantError("Weather forecast temporarily unavailable")
        return [CalendarEvent(**event) for event in self.coordinator.data
                if CalendarEvent(**event).start_datetime_local < end_date
                and CalendarEvent(**event).end_datetime_local > start_date]
