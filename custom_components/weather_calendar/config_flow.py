"""UI configuration for a weather calendar without new provider credentials."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from .const import DEFAULTS, DOMAIN
from .text import validate_template


def schema(values):
    fields = {
        vol.Required("name", default=values["name"]): str,
        vol.Required("weather_entity", default=values["weather_entity"]): selector.EntitySelector(selector.EntitySelectorConfig(domain="weather")),
        vol.Required("location", default=values["location"]): str,
        vol.Required("days", default=values["days"]): vol.All(vol.Coerce(int), vol.Range(min=1, max=16)),
        vol.Required("temperature_unit", default=values["temperature_unit"]): vol.In(["source", "°F", "°C"]),
        vol.Required("temperature_order", default=values["temperature_order"]): vol.In(["low_high", "high_low"]),
        **{vol.Optional(key, default=values[key]): str for key in ("title_template", "description_template")},
        **{vol.Required(key, default=values[key]): bool for key in ("show_units", "show_details", "show_sun", "dashboard_details", "public_feed")},
    }
    return vol.Schema(fields)


def validate(hass, values):
    try:
        for key in ("title_template", "description_template"):
            validate_template(values.get(key, ""))
    except ValueError:
        return {"base": "invalid_template"}
    state = hass.states.get(values["weather_entity"])
    if not state or not state.entity_id.startswith("weather.") or not int(state.attributes.get("supported_features", 0)) & 1:
        return {"weather_entity": "daily_forecast_required"}
    if not values["name"].strip() or not values["location"].strip():
        return {"base": "empty_name"}
    return {}


class WeatherCalendarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            errors = validate(self.hass, user_input)
            if not errors:
                return self.async_create_entry(title=user_input["name"], data=user_input)
        return self.async_show_form(step_id="user", data_schema=schema({**DEFAULTS, **(user_input or {})}), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return WeatherCalendarOptionsFlow()


class WeatherCalendarOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            errors = validate(self.hass, user_input)
            if not errors:
                return self.async_create_entry(title="", data=user_input)
        values = {**DEFAULTS, **self.config_entry.data, **self.config_entry.options, **(user_input or {})}
        return self.async_show_form(step_id="init", data_schema=schema(values), errors=errors)
