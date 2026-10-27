#!/usr/bin/env python3
"""Exercise calendar day boundaries, missing data, updates and real ICS parsing."""
import importlib.util
from datetime import date, datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
import unittest
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'custom_components/weather_calendar' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
package = types.ModuleType("weather_calendar_pure")
package.__path__ = [str(ROOT / "custom_components/weather_calendar")]
sys.modules[package.__name__] = package
spec = importlib.util.spec_from_file_location("weather_calendar_pure.forecast", ROOT / "custom_components/weather_calendar/forecast.py")
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)
DEFAULTS = load('const').DEFAULTS

class WeatherCalendarTests(unittest.TestCase):
    def events(self, forecasts=None, **options):
        return f.build_events(forecasts if forecasts is not None else [{'datetime':'2026-11-01T00:00:00Z','temperature':76,'templow':49,'condition':'cloudy','precipitation':0,'wind_bearing':225}], {'temperature_unit':'°F','precipitation_unit':'in','humidity':99,'pressure':30}, {**DEFAULTS, **options}, date(2026,11,1), 'stable')

    def test_daily_date_does_not_shift_to_previous_day_at_dst(self):
        event = self.events()[0]
        self.assertEqual(event['start'],date(2026,11,1))
        self.assertEqual(event['end'],date(2026,11,2))
        self.assertEqual(event['summary'],'☁️ 76°/49°')
        self.assertEqual(self.events(temperature_order='low_high')[0]['summary'],'☁️ 49°/76°')

    def test_options_and_conversion(self):
        self.assertEqual(self.events(temperature_unit='°C',show_units=True,temperature_order='high_low')[0]['summary'],'☁️ 24°C/9°C')
        self.assertNotIn('Wind',self.events(show_details=False)[0]['description'])

    def test_forecast_only_missing_values_and_bounds(self):
        description = self.events()[0]['description']
        self.assertNotIn('Humidity',description)
        self.assertNotIn('Pressure',description)
        self.assertNotIn('Precipitation 0 in',description)
        self.assertNotIn('°',description)
        self.assertIn('Wind from SW',description)
        self.assertEqual(self.events([{'datetime':'bad'},{'datetime':'2026-10-31'},{'datetime':'2026-11-08'}]),[])
        self.assertIn('–°/–°',self.events([{'datetime':'2026-11-01','temperature':float('nan')}])[0]['summary'])

    def test_stable_uid_and_deduplication(self):
        a=self.events()[0]
        b=self.events([{'datetime':'2026-11-01','temperature':80}])[0]
        self.assertEqual(a['uid'],b['uid'])
        self.assertNotEqual(a['summary'],b['summary'])
        self.assertEqual(len(self.events([{'datetime':'2026-11-01'}]*2)),1)

    def test_dashboard_details_local_dates_and_means(self):
        details = load('details')
        times = [f'2026-11-01T{h:02}:00' for h in range(24)] + ['2026-11-02T00:00']
        weather = {'daily': {'time':['2026-11-01'], 'uv_index_max':[2.5], 'precipitation_probability_max':[0], 'sunrise':['2026-11-01T06:30'], 'sunset':['2026-11-01T17:00']},
                   'hourly': {'time':times, 'temperature_2m':[68]*24+[50], 'relative_humidity_2m':[40]*24+[80]}}
        air = {'hourly':{'time':times,'pm2_5':[5]*24+[100]},'hourly_units':{'pm2_5':'μg/m³'}}
        extra = details.dashboard_details(weather, air)
        day = date(2026,11,1)
        self.assertEqual(extra[day]['humidity_mean'],40)
        self.assertEqual(extra[day]['pm25_mean'],5)
        self.assertNotIn('temperatures',extra[day])
        forecasts = [{'datetime':'2026-11-01','temperature':76,'templow':49}, {'datetime':'2026-11-02','temperature':70,'templow':50}]
        events = f.build_events(forecasts, {'temperature_unit':'°F'}, {**DEFAULTS,'dashboard_details':True}, day, 'stable', None, extra)
        for text in ['UV max 2.5','Rain chance 0%','Humidity (avg) 40%','Air Quality (avg) 5 PM2.5','Sunrise 6:30 AM']:
            self.assertIn(text,events[0]['description'])
        self.assertNotIn('Current',events[0]['description'])
        self.assertNotIn('Current',events[1]['description'])
        self.assertNotIn('42%',events[1]['description'])
        self.assertEqual(details.daily_mean({'time':times[:5],'pm2_5':[5]*5},'pm2_5','2026-11-01'),None)
        weather['hourly']['relative_humidity_2m'][0] = None
        self.assertIsNone(details.dashboard_details(weather,air)[day]['humidity_mean'])
        air['hourly_units']['pm2_5'] = 'invalid'
        self.assertIsNone(details.dashboard_details(weather,air)[day]['pm25_mean'])

    def test_compact_forecast_groups_and_no_current_data(self):
        day = date(2026,11,1)
        forecasts = [{'datetime':'2026-11-01','condition':'cloudy','temperature':73,'templow':46,
                      'precipitation_probability':0,'precipitation':0,'wind_speed':6.03,
                      'wind_gust_speed':6.96,'wind_bearing':90,'uv_index':4.65}]
        extra = {day:{'humidity_mean':69,'pm25_mean':27.4,'sunrise':'07:26','sunset':'18:16',
                      'temperatures':[('8 AM',47),('12 PM',64),('4 PM',71),('8 PM',59),('12 AM next day',56)]}}
        attributes = {'temperature_unit':'°F','precipitation_unit':'in','wind_speed_unit':'mph',
                      'humidity':1,'temperature':100,'pressure':99}
        event = f.build_events(forecasts,attributes,{**DEFAULTS,'dashboard_details':True},day,'stable',None,extra)[0]
        self.assertEqual(event['description'], "\n".join([
            'Cloudy',
            'Rain chance 0%',
            'Wind 6 mph E · Gusts 7 mph',
            'Humidity (avg) 69% · UV max 4.7',
            'Air Quality (avg) 27 PM2.5',
            'Sunrise 7:26 AM · Sunset 6:16 PM',
            '', 'Daily forecast · Open-Meteo / CAMS']))
        self.assertNotIn('Current',event['description'])
        self.assertNotIn('weather.',event['description'])
        self.assertNotIn('°',event['description'])
        self.assertNotIn('Midnight',event['description'])
        self.assertNotIn('µg',event['description'])
        self.assertEqual(event['summary'],'☁️ 73°/46°')
        self.assertNotIn('Pressure',event['description'])

    def test_dashboard_rain_precision_and_wind_rounding(self):
        for amount, rendered in [(0,None),(0.005,None),(0.01,'0.01 in'),(0.05,'0.05 in'),(0.24,'0.2 in'),(1.7,'2 in')]:
            event=self.events([{'datetime':'2026-11-01','precipitation':amount,'wind_speed':6.1,'wind_gust_speed':6.2,'wind_bearing':335}],dashboard_details=True)[0]
            if rendered:
                self.assertIn(rendered,event['description'])
            else:
                self.assertNotIn(' in',event['description'])
            self.assertNotIn('Gusts',event['description'])
        self.assertEqual(f.wind_direction(335),'NW')
        self.assertEqual(f.wind_direction(350),'N')


    def test_local_today_fallback_units_dates_and_canonical_priority(self):
        local = load('local_day')
        today = date(2026,10,25)
        attrs = {'temperature_unit':'°F','precipitation_unit':'in'}
        payload = {'daily_units':{'temperature_2m_max':'°F','temperature_2m_min':'°F','precipitation_sum':'inch'},
                   'daily':{'time':['2026-10-25','2026-10-26'],'temperature_2m_max':[73,90],
                            'temperature_2m_min':[48,60],'weather_code':[3,0],'precipitation_sum':[0.2,0]}}
        tomorrow = {'datetime':'2026-10-26T00:00:00Z','temperature':90}
        rows = local.add_local_today([tomorrow], payload, today, attrs)
        self.assertEqual(rows[0],tomorrow)
        self.assertEqual(rows[1]['temperature'],73)
        self.assertEqual(rows[1]['datetime'],'2026-10-25')
        opts = {**DEFAULTS,'temperature_unit':'°C','dashboard_details':True}
        events = f.build_events(rows, attrs, opts, today, 'stable')
        self.assertEqual(events[0]['summary'],'☁️ 23°/9°')
        self.assertIn('Open-Meteo local-day forecast',events[0]['description'])
        self.assertNotIn('°',events[0]['description'])
        self.assertIn('Open-Meteo local-day forecast', f.build_events(rows,attrs,{**opts,'show_details':False},today,'stable')[0]['description'])
        canonical = {'datetime':'2026-10-25T00:00:00Z','temperature':74}
        self.assertIs(local.add_local_today([canonical,tomorrow],payload,today,attrs)[0],canonical)
        for broken in [None,{}, {**payload,'daily_units':{}}, {**payload,'daily_units':{**payload['daily_units'],'precipitation_sum':'mm'}}, {**payload,'daily':{**payload['daily'],'time':['2026-10-24','2026-10-26']}},
                       {**payload,'daily':{**payload['daily'],'temperature_2m_max':[float('nan'),90]}},
                       {**payload,'daily':{**payload['daily'],'weather_code':[100,0]}}]:
            self.assertEqual(local.add_local_today([tomorrow],broken,today,attrs),[tomorrow])
        self.assertIsNone(local.today_request(today,{'temperature_unit':'K','precipitation_unit':'in'}))
        metric={'temperature_unit':'°C','precipitation_unit':'mm'}
        self.assertEqual(local.today_request(today,metric)['temperature_unit'],'celsius')
        self.assertEqual(local.today_request(today,metric)['precipitation_unit'],'mm')
        metric_payload={**payload,'daily_units':{'temperature_2m_max':'°C','temperature_2m_min':'°C','precipitation_sum':'mm'}}
        self.assertIsNotNone(local.local_today(metric_payload,today,metric))

    def test_utc_rollover_local_midnight_and_dst_horizons(self):
        from icalendar import Calendar
        local = load('local_day')
        zone = ZoneInfo('America/Los_Angeles')
        attrs = {'temperature_unit':'°F','precipitation_unit':'in'}
        # Immediately before/after UTC midnight, local midnight and both DST changes.
        instants = ['2026-10-25T23:59:59+00:00','2026-10-26T00:00:00+00:00',
                    '2026-10-26T06:59:59+00:00','2026-10-26T07:00:00+00:00',
                    '2026-11-01T06:59:59+00:00','2026-11-01T07:00:00+00:00',
                    '2026-11-01T08:59:59+00:00','2026-11-01T09:00:00+00:00',
                    '2026-11-02T07:59:59+00:00','2026-11-02T08:00:00+00:00',
                    '2026-03-08T07:59:59+00:00','2026-03-08T08:00:00+00:00',
                    '2026-03-08T09:59:59+00:00','2026-03-08T10:00:00+00:00',
                    '2026-03-09T06:59:59+00:00','2026-03-09T07:00:00+00:00']
        identities = {}
        for value in instants:
            instant=datetime.fromisoformat(value)
            today=instant.astimezone(zone).date()
            first=instant.date()  # The provider's UTC date labels.
            rows=[{'datetime':(first+timedelta(days=i)).isoformat(),'temperature':80,'templow':50} for i in range(7)]
            payload={'daily_units':{'temperature_2m_max':'°F','temperature_2m_min':'°F','precipitation_sum':'inch'},
                     'daily':{'time':[today.isoformat()],'temperature_2m_max':[73],'temperature_2m_min':[48],'weather_code':[3],'precipitation_sum':[0]}}
            events=f.build_events(local.add_local_today(rows,payload,today,attrs),attrs,DEFAULTS,today,'stable')
            self.assertEqual([e['start'] for e in events],[today+timedelta(days=i) for i in range(7)],value)
            parsed=Calendar.from_ical(f.serialize_ics(events,'Weather',instant)).walk('VEVENT')
            self.assertEqual([e.decoded('DTSTART') for e in parsed],[e['start'] for e in events])
            for event in events:
                self.assertEqual(event['end'],event['start']+timedelta(days=1))
                self.assertEqual(identities.setdefault(event['start'],event['uid']),event['uid'])
            if today in [date(2026,3,8),date(2026,11,1)]:
                start=datetime.combine(today,datetime.min.time(),zone)
                end=datetime.combine(today+timedelta(days=1),datetime.min.time(),zone)
                self.assertEqual((end.astimezone(timezone.utc)-start.astimezone(timezone.utc)).total_seconds()/3600,23 if today.month==3 else 25)

    def test_ics_roundtrip_folding_escaping_and_all_day(self):
        from icalendar import Calendar
        events=self.events(location='City, test; ☁️\n' + '🌧️'*90)
        text=f.serialize_ics(events,'Weather\nInjected: no',datetime.now(timezone.utc))
        self.assertTrue(all(len(line.encode())<=75 for line in text.split('\r\n')))
        cal=Calendar.from_ical(text)
        event=cal.walk('VEVENT')[0]
        self.assertEqual(event.decoded('DTSTART'),events[0]['start'])
        self.assertEqual(event.decoded('DTEND'),events[0]['end'])
        self.assertEqual(str(event['LOCATION']),events[0]['location'])
        self.assertEqual(str(event['SUMMARY']),events[0]['summary'])
        self.assertEqual(len(cal.walk('VEVENT')),1)

if __name__=='__main__':
    unittest.main()
