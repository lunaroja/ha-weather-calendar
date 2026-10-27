# Release 1.4.0 validation

Validated October 27, 2026. The isolated environment uses a sample London location, no household data and a localhost-only server. Screenshot: actual Home Assistant calendar event, not a mockup.

| Path | Evidence |
| --- | --- |
| Clean manual install | Copied the integration into an empty HA 2026.10.4 config, started HA, added provider/config entries through HA APIs |
| Real providers | Official HA Met.no (six available daily dates) and Open-Meteo (seven), actual network forecast requests and native calendars; provider horizons preserved |
| UI | Opened actual config/options form; saved multiline customized description through UI; reopened native event and read back customized text |
| Restart | Stopped/restarted the isolated HA process; entries, entities, feed paths and options reloaded |
| Automated HA suite | 11 cases covering real config/options flows, unsupported sources, template rejection, provider switch, units, bundled version-1 entries, native calendar vs independently parsed anonymous ICS, stable URLs/UIDs, reload, disable, missing IDs, removal and stale/source failures |
| Formatter/coordinator | 15 cases: provider date labels, DST exclusive all-day ends, units, missing/nonfinite data, duplicate dates, stable UIDs, ICS escaping/folding, complete local-day means, supplement failures, local-today fallback validation and UTC/local midnight refresh |
| Publishing | Official hassfest and HACS CI without validation ignores; Linux and macOS test runs |

Actual calendar-client background refresh is controlled by each client. No claim is made that Google, Apple or Outlook refreshed cached content during these tests. Fixed-clock tests cover DST/midnight; the system clock was not changed and the test did not wait for future transitions. The real-provider sample is evidence for those current provider responses, not a guarantee for every HA weather provider.

HACS release installation and the production bundled-to-release upgrade are verified separately by the installation owner; preserve config-entry and entity identity and compare external ICS before and after. No physical devices need to change for this integration.
