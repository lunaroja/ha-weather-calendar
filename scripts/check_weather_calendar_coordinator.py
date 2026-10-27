#!/usr/bin/env python3
"""Run the real coordinator with small HA/HTTP boundary fakes (no HA install)."""
import importlib.util
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def module(**values):
    return types.SimpleNamespace(**values)


class Coordinator:
    def __init__(self, hass, *args, **kwargs):
        self.hass = hass
        self.last_update_success = True
        self.data = None

    async def async_request_refresh(self):
        self.data = await self._async_update_data()


class HAError(Exception):
    pass


class Clock:
    instant = datetime.fromisoformat('2026-10-26T00:00:01+00:00')

    def now(self):
        return self.instant.astimezone(ZoneInfo('America/Los_Angeles'))

    def utcnow(self):
        return self.instant


class WeatherCalendarCoordinatorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.clock = Clock()
        self.requests = []
        self.attrs = {'temperature_unit':'°F','precipitation_unit':'in'}
        self.canonical = [{'datetime':f'2026-10-{day}T00:00:00Z','temperature':80,'templow':50} for day in range(26,32)]
        self.payload = {'daily_units':{'temperature_2m_max':'°F','temperature_2m_min':'°F','precipitation_sum':'inch'},
                        'daily':{'time':['2026-10-25'],'temperature_2m_max':[73],'temperature_2m_min':[48],
                                 'weather_code':[3],'precipitation_sum':[0]}}
        self.service = AsyncMock(side_effect=lambda *a, **k: {'weather.home':{'forecast':self.canonical}})
        self.hass = module(config=module(latitude=51.501,longitude=-0.121,time_zone='America/Los_Angeles'),
                           states=module(get=lambda _:module(state='cloudy',attributes=self.attrs)),
                           services=module(async_call=self.service))
        test = self

        class Response:
            async def __aenter__(self):
                return self
            async def __aexit__(self,*args):
                pass
            def raise_for_status(self):
                if test.fail_http:
                    raise HAError('provider unavailable')
            async def json(self):
                return test.payload

        def get(url, *, params, timeout):
            self.requests.append((url,params))
            return Response()

        self.fail_http = False
        self.entry = module(title='Weather',entry_id='stable',data={'weather_entity':'weather.home','dashboard_details':True,'show_sun':False},options={})
        fake = {
            'aiohttp':module(ClientError=HAError,ClientTimeout=lambda **kw:None,
                             web=module(Response=lambda **kw:module(**kw),HTTPServiceUnavailable=HAError,HTTPNotFound=HAError)),
            'homeassistant':module(),
            'homeassistant.components':module(),
            'homeassistant.components.http':module(HomeAssistantView=object),
            'homeassistant.const':module(Platform=module(CALENDAR='calendar')),
            'homeassistant.exceptions':module(HomeAssistantError=HAError),
            'homeassistant.helpers':module(),
            'homeassistant.helpers.aiohttp_client':module(async_get_clientsession=lambda _:module(get=get)),
            'homeassistant.helpers.sun':module(get_astral_event_date=lambda *a:None),
            'homeassistant.helpers.update_coordinator':module(DataUpdateCoordinator=Coordinator,UpdateFailed=HAError),
            'homeassistant.util':module(dt=self.clock),
        }
        path=ROOT/'custom_components/weather_calendar'
        spec=importlib.util.spec_from_file_location('weather_calendar_test',path/'__init__.py',submodule_search_locations=[str(path)])
        self.component=importlib.util.module_from_spec(spec)
        fake['weather_calendar_test']=self.component
        self.patcher=patch.dict(sys.modules,fake)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        spec.loader.exec_module(self.component)

    async def test_restart_after_utc_rollover_fetches_missing_local_day(self):
        for _ in range(2):  # A new coordinator has no prior-day memory or disk cache.
            self.requests.clear()
            coordinator=self.component.WeatherCalendarCoordinator(self.hass,self.entry)
            await coordinator.async_request_refresh()
            self.assertTrue(coordinator.fresh)
            self.assertEqual(coordinator.data[0]['start'].isoformat(),'2026-10-25')
            self.assertEqual(len(coordinator.data),7)
            self.assertEqual(coordinator.data[1]['summary'],'🌡️ 80°/50°')
            weather=self.requests[0][1]
            self.assertEqual(weather['timezone'],'America/Los_Angeles')
            self.assertEqual((weather['latitude'],weather['longitude']),(51.50,-0.12))
            self.assertEqual((weather['start_date'],weather['end_date']),('2026-10-25','2026-10-31'))
            self.assertEqual((weather['temperature_unit'],weather['precipitation_unit']),('fahrenheit','inch'))
            self.assertNotIn('current',weather)
            self.assertNotIn('temperature_2m',weather['hourly'])

    async def test_before_utc_rollover_uses_canonical_without_fallback(self):
        self.clock.instant=datetime.fromisoformat('2026-10-25T23:59:59+00:00')
        self.canonical.insert(0,{'datetime':'2026-10-25T00:00:00Z','temperature':74,'templow':49})
        coordinator=self.component.WeatherCalendarCoordinator(self.hass,self.entry)
        await coordinator.async_request_refresh()
        self.assertEqual(coordinator.data[0]['summary'],'🌡️ 74°/49°')
        self.assertNotIn('temperature_2m_max',self.requests[0][1]['daily'])
        self.assertNotIn('local-day forecast',coordinator.data[0]['description'])

    async def test_hidden_details_still_recovers_today_but_home_opt_out_does_not(self):
        self.entry.options={'show_details':False}
        coordinator=self.component.WeatherCalendarCoordinator(self.hass,self.entry)
        await coordinator.async_request_refresh()
        self.assertEqual(len(coordinator.data),7)
        self.assertEqual(len(self.requests),1)
        self.assertNotIn('hourly',self.requests[0][1])
        self.assertIn('Open-Meteo local-day forecast',coordinator.data[0]['description'])
        self.entry.options={'dashboard_details':False}
        self.requests.clear()
        coordinator=self.component.WeatherCalendarCoordinator(self.hass,self.entry)
        await coordinator.async_request_refresh()
        self.assertEqual(len(coordinator.data),6)
        self.assertEqual(self.requests,[])

    async def test_fallback_failure_keeps_canonical_days_without_relabeling(self):
        self.fail_http=True
        coordinator=self.component.WeatherCalendarCoordinator(self.hass,self.entry)
        await coordinator.async_request_refresh()
        self.assertEqual(len(coordinator.data),6)
        self.assertEqual(coordinator.data[0]['start'].isoformat(),'2026-10-26')
        self.assertIn('Local-day forecast temporarily unavailable',coordinator.data[0]['description'])

    async def test_local_midnight_invalidates_and_feed_refreshes_horizon(self):
        self.clock.instant=datetime.fromisoformat('2026-10-26T06:59:59+00:00')
        self.entry.options={'public_feed':True}
        coordinator=self.component.WeatherCalendarCoordinator(self.hass,self.entry)
        await coordinator.async_request_refresh()
        self.assertTrue(coordinator.fresh)
        self.clock.instant+=timedelta(seconds=1)
        self.assertFalse(coordinator.fresh)
        self.canonical.append({'datetime':'2026-11-01T00:00:00Z','temperature':72,'templow':48})
        self.hass.data={'weather_calendar':{'stable':coordinator}}
        result=await self.component.WeatherCalendarFeed().get(module(app={'hass':self.hass}),'stable')
        from icalendar import Calendar
        dates=[event.decoded('DTSTART').isoformat() for event in Calendar.from_ical(result.text).walk('VEVENT')]
        self.assertEqual(dates,['2026-10-26','2026-10-27','2026-10-28','2026-10-29','2026-10-30','2026-10-31','2026-11-01'])
        self.assertTrue(coordinator.fresh)


if __name__=='__main__':
    unittest.main()
