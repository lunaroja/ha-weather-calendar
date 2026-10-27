# Weather Calendar — powered by Home Assistant

Self-hosted weather forecasts in the calendar app you already use. Choose a Home Assistant daily weather source, customize event text, and subscribe from Apple Calendar, Google Calendar, Outlook or another ICS client.

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=lunaroja&repository=ha-weather-calendar&category=integration)
[![Set up integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=weather_calendar)
[![Validation](https://github.com/lunaroja/ha-weather-calendar/actions/workflows/validate.yaml/badge.svg)](https://github.com/lunaroja/ha-weather-calendar/actions/workflows/validate.yaml)
[![Release](https://img.shields.io/github/v/release/lunaroja/ha-weather-calendar)](https://github.com/lunaroja/ha-weather-calendar/releases)

## Install

Requires Home Assistant **2026.10 or later** and an existing weather entity supporting daily forecasts. Its provider controls coverage, licensing and forecast horizon. No extra provider credentials are needed by this integration. Weather data comes from your selected provider; optional supplements use Open-Meteo internet APIs. Hosting the calendar yourself does not make the forecasts locally generated or cloud-free.

1. In HACS, open the menu → **Custom repositories**. Add `https://github.com/lunaroja/ha-weather-calendar`, category **Integration** (or use the HACS badge).
2. Download **Weather Calendar**, choosing the latest published release. Restart Home Assistant.
3. Open **Settings → Devices & services → Add integration → Weather Calendar** (or the setup badge).
4. Pick your daily forecast weather entity, calendar name and location label. Save. Your native `calendar` entity is immediately available in HA.

Custom-repository releases are available independently of HACS default-catalog review. A catalog submission is not approval or default inclusion.

Manual installation: copy only `custom_components/weather_calendar` from a [release](https://github.com/lunaroja/ha-weather-calendar/releases) into your HA `config/custom_components/` directory, then restart and follow steps 3–4. Do not copy repository tooling/tests into HA.

## Configure

Open the integration's **Configure** button to change options. Each saved change reloads only this calendar. Add multiple entries for multiple sources or formats.

| Option | Effect |
| --- | --- |
| Calendar name / location | Calendar label and event location; public when feed is enabled |
| Weather entity | Any HA source advertising daily forecasts; no provider-specific credentials here |
| Forecast days | 1–16; only available provider days appear, never fabricated extra days |
| Temperature unit / order | Source, °C or °F; high/low or low/high; optional explicit units |
| Forecast details | Daily rain, wind, humidity, UV and pressure when supplied; missing values omitted |
| Home sunrise/sunset | Uses HA's home coordinates and timezone; turn off for other locations |
| Open-Meteo home details and local-day fallback | Explicit opt-in: sends home coordinates rounded to 0.01° and timezone to Open-Meteo; adds UV, rain chance, complete-day humidity/PM2.5 averages, and recovers today's date only if the selected source omitted it. Use only with a home-location source |
| Public ICS | Off by default. Enables unauthenticated weather-only calendar subscription |
| Text templates | Optional title/description customization below; blank keeps the standard format |

Forecasts refresh every 30 minutes. Events use provider daily date labels and exclusive all-day ends across DST, with stable IDs per entry/date. Temperature conversion affects title values; rain/wind/pressure retain the source entity's units. PM2.5 is concentration, not AQI. Supplemental APIs supply up to 16 weather days and 7 air-quality days; incomplete daily averages are omitted. Missing supplement data keeps canonical forecasts with a brief unavailable note. A source failure or forecast older than two hours makes the native calendar unavailable and the feed return 503, rather than serving stale forecasts as fresh. At local midnight a request refreshes the horizon.

### Customize event text

Plain placeholders are supported in both templates: `{icon}`, `{condition}`, `{high}`, `{low}`, `{unit}`, `{location}`, `{date}`, `{title}`, `{details}`. Temperatures are converted/formatted using the unit options. `{title}` is the standard title in the title template and the final customized title in the description template. `{details}` is the standard description, respecting the details/sun/supplement toggles. `{{` and `}}` escape literal braces. No code, expressions, attributes, format modifiers or third-party entity access is evaluated. Maximum 2,000 characters per template.

Example title: `{icon} {location}: {high}{unit} / {low}{unit}`

Example description (literal newlines supported):

```text
Forecast for {location} on {date}
{details}
```

Keep private information out of every text field when enabling the public feed.

## Subscribe from another calendar app

**External subscription refresh requires internet-accessible HTTPS Home Assistant**, with a valid certificate and the feed path reachable by the calendar service. A local-only HA address cannot be refreshed by Google or another remote subscriber. This integration does not configure remote access, DNS, TLS or router forwarding.

Enable **Public ICS**. In Developer Tools → States, find the calendar's `subscription_path` attribute. Prefix it with your external HA HTTPS origin, for example `https://ha.example.com/api/weather_calendar/ENTRY_ID.ics`. Use Calendar → File → New Calendar Subscription on Mac, Google Calendar → Other calendars → From URL, or your client's subscription command. Subscribe to the URL; importing a downloaded `.ics` file does not update it. `webcal://` may be used if supported.

Clients control refresh/caching. The feed advertises an hourly refresh suggestion; it cannot force Google/Apple to refresh immediately. Preserve subscriptions during upgrades rather than recreating them to force refresh.

### Privacy and access

The endpoint deliberately requires **no HA login** so subscription services can poll it. The URL is an unlisted bearer-style sharing link, not an authentication boundary: anyone who obtains it can read the configured calendar name, location and generated text. It exports no other calendars, provider credentials or numeric coordinates. A location label or customized text can still identify your home; use a city-level label. Do not post subscription URLs publicly. HTTP caches may retain prior responses for up to five minutes and calendar clients may retain them longer.

Disable Public ICS to revoke future origin requests (404). Unknown/removed entries also return 404. Existing client/cached copies cannot be erased remotely. The entry ID keeps the URL stable across reloads, restarts and upgrades; creating a new entry changes it. There is no independent per-subscriber access control or link rotation in this release.

## Upgrade and recovery

HACS → Weather Calendar → Update, then restart HA. Existing version-1 config entries from the original bundled component upgrade in place: same domain, config entry, calendar unique ID, saved options, feed URL and per-date event IDs. New template fields default to standard text; no subscription recreation is required. Back up HA before updating. Roll back by restoring the previous release's component files and restarting; keep the existing config entry.

To uninstall, first remove entries through Settings → Devices & services, then remove Weather Calendar in HACS and restart HA. This removes feed access and the native entity. Remove obsolete external subscriptions yourself. It does not change physical devices or household automations.

## Troubleshooting

- **Not listed after download:** restart HA; confirm the directory is exactly `custom_components/weather_calendar`, then hard-refresh the browser.
- **Daily forecast required:** select a source supporting `weather.get_forecasts` with `type: daily`. Hourly-only sources are unsupported.
- **Fewer days / missing today:** check the provider's daily response and horizon. Do not shift tomorrow backward. The optional home-local fallback can recover today using a fresh Open-Meteo forecast, but only for a home-location source.
- **Unavailable / 503:** restore the source integration/network, then reload this calendar. Old forecasts are not advertised as fresh.
- **404:** verify Public ICS is enabled and use the exact subscription path for the existing entry.
- **Calendar app still shows old text:** confirm the feed in HA first; the remote calendar may still have its own cached copy.
- **Wrong sun times:** sun and supplements use HA's home location/timezone; disable for a remote weather source.
- **Bad template:** use only the plain placeholders listed above; leave empty to reset.

Report bugs with HA/integration versions, provider name and sanitized errors. Do not include feed URLs, HA tokens, exact coordinates, config-entry IDs or private calendar content.

## Inspiration, attribution and terms

Inspired by [Weather in Calendar](https://weather-in-calendar.com/) by **Andreas Vejnø Andersen**, which supplies emoji daily forecasts through ICS using OpenWeatherMap. This project does not claim to invent weather calendars and does not include that service's source code.

Your selected weather integration/provider supplies canonical forecasts; comply with its attribution, usage and redistribution terms. Optional [Open-Meteo weather](https://open-meteo.com/en/docs) and [air-quality](https://open-meteo.com/en/docs/air-quality-api) data carry their own attribution and [terms](https://open-meteo.com/en/terms). The free public APIs are for non-commercial use; commercial deployments must arrange permitted access. Air-quality data include CAMS forecasts. The standard supplemental footer identifies Open-Meteo / CAMS; preserve appropriate attribution if replacing description text. Software licensing does not license weather data.

Independent custom integration; not an official Home Assistant or Open Home Foundation product. “Powered by Home Assistant” describes the platform dependency. The original icon is a calendar with sun/cloud artwork and does not use Home Assistant branded images.

MIT licensed. See [LICENSE](LICENSE). [Contributing and testing](CONTRIBUTING.md).
