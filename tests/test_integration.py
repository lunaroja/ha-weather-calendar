"""Exercise real HA config flows, entity platform, HTTP, reload and removal."""
from datetime import timedelta
from unittest.mock import AsyncMock, patch
import pytest
from icalendar import Calendar
from homeassistant import config_entries
from homeassistant.core import SupportsResponse
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry
from custom_components.weather_calendar.const import DEFAULTS
from custom_components.weather_calendar.text import validate_template

@pytest.fixture
async def source(hass):
    from homeassistant.setup import async_setup_component
    assert await async_setup_component(hass, "weather", {})
    hass.states.async_set("weather.sample", "cloudy", {"supported_features": 1, "temperature_unit": "°C", "precipitation_unit": "mm", "wind_speed_unit": "km/h"})
    today = dt_util.now().date()
    data = [{"datetime": (today + timedelta(days=n)).isoformat() + "T00:00:00+00:00", "condition": "cloudy", "temperature": 20 + n, "templow": 10, "precipitation": 1.2} for n in range(3)]
    async def forecasts(call):
        return {entity: {"forecast": data} for entity in ([call.data["entity_id"]] if isinstance(call.data["entity_id"], str) else call.data["entity_id"])}
    hass.services.async_register("weather", "get_forecasts", forecasts, supports_response=SupportsResponse.ONLY)
    return data

def values(**kw):
    return {**DEFAULTS, "weather_entity": "weather.sample", "location": "Sample City", **kw}

async def setup(hass, **kw):
    entry = MockConfigEntry(domain="weather_calendar", title="Weather Calendar", data=values(**kw), version=1)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry

async def test_real_user_and_options_flow(hass, source):
    result = await hass.config_entries.flow.async_init("weather_calendar", context={"source": config_entries.SOURCE_USER})
    assert result["type"] == "form"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], values(weather_entity="weather.missing"))
    assert result["errors"] == {"weather_entity": "daily_forecast_required"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], values(title_template="{high.__class__}"))
    assert result["errors"] == {"base": "invalid_template"}
    with patch("custom_components.weather_calendar.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], values(title_template="{location}: {icon} {high}{unit}"))
        assert result["type"] == "create_entry"
        entry = result["result"]
        await hass.async_block_till_done()
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    assert flow["type"] == "form"
    with patch("custom_components.weather_calendar.async_options_updated", new=AsyncMock()):
        result = await hass.config_entries.options.async_configure(flow["flow_id"], values(description_template="{date}\n{details}"))
        assert result["type"] == "create_entry"
        assert entry.options["description_template"] == "{date}\n{details}"

async def test_native_and_subscribable_ics_reload_disable_uninstall(hass, source, hass_client):
    entry = await setup(hass, public_feed=True, show_sun=False, title_template="{location}: {icon} {high}{unit}/{low}{unit}", description_template="Forecast for {date}\n{details}")
    state = hass.states.get("calendar.weather_calendar")
    assert state.state == "on"
    client = await hass_client()
    path = state.attributes["subscription_path"]
    response = await client.get(path)
    assert response.status == 200
    ics = Calendar.from_ical(await response.text())
    events = ics.walk("VEVENT")
    assert len(events) == 3  # Never invent the requested remaining horizon.
    assert str(events[0]["SUMMARY"]) == "Sample City: ☁️ 20°/10°"
    assert "Forecast for" in str(events[0]["DESCRIPTION"])
    native = await client.get("/api/calendars/calendar.weather_calendar", params={"start": dt_util.start_of_local_day().isoformat(), "end": (dt_util.start_of_local_day()+timedelta(days=7)).isoformat()})
    assert native.status == 200
    native_events = await native.json()
    assert native_events[0]["summary"] == str(events[0]["SUMMARY"])
    uid = str(events[0]["UID"])
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("calendar.weather_calendar").attributes["subscription_path"] == path
    response = await client.get(path)
    assert str(Calendar.from_ical(await response.text()).walk("VEVENT")[0]["UID"]) == uid
    hass.config_entries.async_update_entry(entry, options={"public_feed": False})
    await hass.async_block_till_done()
    assert (await client.get(path)).status == 404
    assert (await client.get("/api/weather_calendar/nonexistent.ics")).status == 404
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert (await client.get(path)).status == 404
    assert hass.states.get("calendar.weather_calendar") is None

async def test_provider_switch_units_and_bundled_upgrade(hass, source):
    entry = await setup(hass, show_sun=False)
    identity = entry.entry_id
    hass.states.async_set("weather.second", "sunny", {"supported_features":1,"temperature_unit":"°F", "precipitation_unit":"in"})
    # Saved version-1 bundled entries lack templates; defaults preserve identity.
    hass.config_entries.async_update_entry(entry, options={"weather_entity":"weather.second", "temperature_unit":"°C", "temperature_order":"low_high", "show_units":True})
    await hass.async_block_till_done()
    state = hass.states.get("calendar.weather_calendar")
    assert entry.entry_id == identity
    assert state.attributes["weather_entity"] == "weather.second"
    assert state.attributes["message"] == "☁️ -12°C/-7°C"

async def test_failure_and_stale_data_never_served_as_fresh(hass, source, hass_client):
    entry = await setup(hass, public_feed=True, show_sun=False)
    coordinator = hass.data["weather_calendar"][entry.entry_id]
    coordinator.updated -= timedelta(hours=3)
    hass.states.async_set("weather.sample", "unavailable")
    client = await hass_client()
    response = await client.get(f"/api/weather_calendar/{entry.entry_id}.ics")
    assert response.status == 503
    assert response.headers["Retry-After"] == "300"
    assert not coordinator.fresh
    assert not hass.states.get("calendar.weather_calendar").state == "on"

@pytest.mark.parametrize("text", ["{high.__class__}", "{high[0]}", "{high!r}", "{high:>100000000}", "{unknown}", "{", "x"*2001])
def test_templates_reject_expressions(text):
    with pytest.raises(ValueError):
        validate_template(text)
