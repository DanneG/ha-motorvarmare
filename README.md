# Engine Heater for Home Assistant

English · [Svenska](docs/README.sv.md)

<!-- ha-marketplace:exclude-start -->
[![Marketplace: available](https://img.shields.io/badge/Marketplace-available-03A9F4?style=for-the-badge&logo=homeassistant&logoColor=white)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=DanneG&repository=ha-motorvarmare&category=integration)
[![HACS Default](https://img.shields.io/badge/HACS-Default-orange?style=for-the-badge)](https://github.com/hacs/default)
[![Latest release](https://img.shields.io/github/v/release/DanneG/ha-motorvarmare?style=for-the-badge&label=release)](https://github.com/DanneG/ha-motorvarmare/releases/latest)
[![Validation on main](https://img.shields.io/github/actions/workflow/status/DanneG/ha-motorvarmare/validate.yml?branch=main&style=for-the-badge&label=validation)](https://github.com/DanneG/ha-motorvarmare/actions/workflows/validate.yml)
[![License](https://img.shields.io/github/license/DanneG/ha-motorvarmare?style=for-the-badge&label=license)](https://github.com/DanneG/ha-motorvarmare/blob/main/LICENSE)
<!-- ha-marketplace:exclude-end -->

Choose a departure time. Motorvärmare calculates when to switch on each car's heater from the outdoor temperature. At −5 °C, heating starts at 06:00 for a 07:30 departure.

## Installation

<!-- ha-marketplace:exclude-start -->
- **Home Assistant 2026.11 or later** — Install **Motorvärmare** from **Settings → Marketplace**.
- **Earlier versions** — Search for **Motorvärmare** in HACS. [Open in HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=DanneG&repository=ha-motorvarmare&category=integration)
- If missing from the catalog, add `https://github.com/DanneG/ha-motorvarmare` as a custom repository of type **Integration**.

[![Open in Home Assistant Marketplace](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=DanneG&repository=ha-motorvarmare&category=integration)
<!-- ha-marketplace:exclude-end -->

1. Restart Home Assistant after installing or updating.
2. Under **Settings → Devices & services**, add **Motorvärmare** once per car. Select its switch and an outdoor temperature sensor (°C or °F).
3. Reload your dashboard. Add the included **Motorvärmare** card and choose the car's status sensor. For multiple cars, use **Motorvärmare – översikt / Engine heaters**.

<details>
<summary>Manual installation, YAML or the old standalone card</summary>

- **Manual install.** Copy the whole `custom_components/motorvarmare` folder into Home Assistant's `custom_components` directory, then follow the steps above.
- **Standalone card.** With dashboard resources managed by Home Assistant, the standard HACS and `/local/ha-motorvarmare-card.js` URLs migrate automatically. Once the bundled card works, remove the standalone HACS package and any custom URL for the old card.
- **YAML resources.** Add the following item to your existing `lovelace.resources` list, replacing the old card entry. Set `VERSION` to the installed integration version after each update.

```yaml
- url: /motorvarmare/ha-motorvarmare-card.js?v=VERSION
  type: module
```

</details>

## Schedule departures

- **From the card.** Select a date and add a departure. Today has a ring. The filled date is your selection. Check the date and time on the save button.
- **Recurring trips.** Choose daily, weekly, monthly or yearly, with an interval and optional end date. You can add multiple departures per day, edit one occurrence or the series, and skip the next trip. Changing a series' start or repeat rule clears its exceptions.
- **From Google Calendar.** Connect Google Calendar to Home Assistant and select the calendar in the car's settings. Enter exact titles (e.g. `EKA JOBB`), or words and tags (e.g. `office, #car1`). Any match counts, ignoring case. Words and tags match the title or description. The event's start time is the departure time. All-day events are skipped. [Google Calendar setup](https://www.home-assistant.io/integrations/google/)

## Heating time

| Outdoor temperature | Preheating |
| --- | --- |
| Above +10 °C | Off |
| 0 to +10 °C | 1 h |
| −5 °C | 1 h 30 min |
| −10 °C | 2 h |
| −20 °C or colder | 3 h |

Below zero, add 6 minutes per degree and round up to a whole minute. An optional hourly forecast estimates future start times. Scheduled heating uses the measured temperature. [M Sverige / Calix](https://msverige.se/allt-om-bilen/service-och-underhall/motorvarmare/)

- **Start now** uses the same heating time. **Extend 30 minutes** extends the current session, up to 4 hours total.
- Optionally keep scheduled heating on for 30 minutes after departure. Heating stops above +10 °C.

## Energy and alerts

- **Power sensor (optional).** Select the plug's sensor in W or kW to see live power and estimated kWh. Add a fixed price per kWh or a price sensor for estimated costs.
- **Cable reminder.** If fresh power readings stay below 10 W for 5 minutes after switch-on, Home Assistant can notify you to check the cable. Both limits are adjustable. The check ends when power reaches the threshold. Mobile notifications are optional.
- **Evening cable check (off by default).** In the car's settings, choose a power sensor and enable the check. Run it at 21:00 (adjustable) or press **Test heater cable** from the card or an automation. If tomorrow's first departure needs heating, the check switches the plug on and requests switch-off within 10 seconds. The check uses the hourly forecast if available, otherwise the outdoor sensor. Low power triggers one reminder per day. A missing or stale reading is inconclusive.
- **History.** View start, stop and duration for the last 1,000 sessions per car. Energy totals by day, week and month use the local stop date. Missing readings or sessions spanning periods can leave totals incomplete.

## Before unattended use

Test start and stop with the car connected. Use equipment rated for the load and an independent maximum-run timer. Home Assistant needs a connection to the switch to turn it off. Save integration settings between sessions because reloading stops a session it controls.

The car's status sensor contains departure details. Give it the same access permissions as the calendar.

![Example car with heater controls, a power graph and the previous evening’s cable check.](docs/demo-card-en.png)

[MIT license](LICENSE)
