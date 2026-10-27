# Contributing

Use Python 3.14 and an isolated virtual environment:

```sh
python3.14 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/python -m pytest -q
.venv/bin/python scripts/check_weather_calendar.py
.venv/bin/python scripts/check_weather_calendar_coordinator.py
```

The HA suite runs real config/options flows, coordinator/entity setup, HTTP calendar/ICS, reload, feed revocation and removal. Pure tests cover DST/date boundaries, unit conversion, independent ICS parsing, supplemental failures and UTC/local-day recovery. Tests use synthetic locations and forecast responses; do not add home data, live credentials or feed identifiers. Optional manual provider/UI smoke tests belong in an isolated HA instance, never a contributor's production home.

CI also runs official hassfest and HACS validation without ignores. Release only after validation passes. Keep version-1 config-entry compatibility, entry-based URLs and stable date UIDs. Test source/provider failures without serving stale forecasts. Every release must document tested versions and any unverified client behavior.
