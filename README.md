# Engine Heater for Home Assistant

English · [Svenska](docs/README.sv.md)

Schedule an electric engine heater using the outdoor temperature and a departure time. Each car has its own Home Assistant-compatible smart plug or switch and departure schedule. Configuration, entities and the companion dashboard card support English and Swedish.

## Installation

Add `https://github.com/DanneG/ha-motorvarmare` as a custom repository in Marketplace or HACS with category **Integration**, then install it. Restart Home Assistant after updating. Under **Settings → Devices & services**, add **Motorvärmare** once for each car. Select the car's switch and an outdoor temperature sensor in °C or °F. A Google calendar is optional.

Also install the separate [Engine Heater dashboard card](https://github.com/DanneG/ha-motorvarmare-card) as a custom repository with category **Dashboard**. Add the card to a dashboard and select the car's status entity. See the card's installation instructions.

For a manual installation, copy `custom_components/motorvarmare` into the Home Assistant configuration's `custom_components` directory, including `translations` and `brand`, and restart Home Assistant. The card is installed separately.

## Departures and calendar

The card shows seven local calendar days at a time and can browse forward, with departures and estimated heater start and stop times. Start times are **estimates** and can change as the temperature changes. Departures may come from the weekly schedule, Google Calendar, or the integration's own calendar.

Select a day in the card to add one or more departure times. Choose a one-time departure or a daily, weekly, monthly or yearly recurrence with an interval and optional end date. Weekly recurrence can select several weekdays. These departures are stored in the car's own Home Assistant calendar; they are not written to Google Calendar. A single occurrence or the whole series can be removed. The existing weekly schedule and single manual-departure entity remain available. The nearest future departure controls the heater. Recurrences use Home Assistant's local time: a nonexistent spring-forward time is skipped, and the first occurrence of a repeated autumn time is used.

Local departures can be edited individually or as an entire series. Changing a series' start or recurrence rule clears its individual changes and exclusions; the card warns before applying this. Monthly recurrence follows the original day of the month and skips months without that date. The supported recurrence options are those listed above; rules such as “the second Monday” and editing “this and following” occurrences are not supported.

To use Google Calendar, first set up the [Google Calendar integration](https://www.home-assistant.io/integrations/google/), choose a calendar in the car's settings, and enter exact event titles and/or words or tags, separated by commas or line breaks. An event matches if its entire title equals one of the titles, **or** if any word or tag appears in its title or description. Matching ignores letter case. The event's start is the departure time; all-day events are ignored. Calendar changes can take time to reach Home Assistant.

Optionally choose a weather entity offering hourly forecasts. The calendar shows forecast-based estimates and labels their source; if a forecast is unavailable or outside its coverage, it uses the current measured temperature instead. Forecasts affect the calendar display only: actual switching is still based on the measured temperature. Weather access is checked for the current user.

Use **Skip next** to skip the next departure without changing the calendar, or pause automatic heating for one car until resumed manually or at the selected time. Pausing stops a scheduled session controlled by the integration; a manually started session remains independently controlled. Optional operational alerts warn about switch, sensor and calendar problems, in Home Assistant and through the selected notification entity. The stale-reading threshold is configurable; unavailable reporting timestamps are not interpreted as stale.

## Heating time and start now

The heating time follows [M Sverige's engine-focused recommendations based on Calix](https://msverige.se/allt-om-bilen/service-och-underhall/motorvarmare/): +10 °C and 0 °C → 60 minutes, −5 °C → 90 minutes, −10 °C → 120 minutes, and −20 °C → 180 minutes. Values between the listed temperatures are calculated by linear interpolation and rounded up to a whole minute. M Sverige does not specify times outside this range: this integration chooses no heating above +10 °C and caps heating at 180 minutes below −20 °C. Fahrenheit sensors are converted to °C first.

**Start now** uses the same calculation and turns the heater off when the calculated time has elapsed. An active session also stops if the outdoor temperature rises above +10 °C. After a temperature stop, scheduled heating can restart at +9.5 °C or below if the departure is still relevant, including after a Home Assistant restart. A manually started session does not restart automatically. An unavailable temperature reading does not stop a session already running. An optional per-car setting (off by default) keeps scheduled heating on for 30 extra minutes after departure, in addition to the calculated pre-departure heating time. It does not extend **Start now** sessions; the temperature limit still applies. **Stop** cancels a heating session controlled by the integration. If the switch is already on when scheduled heating should begin, the integration does not take ownership of it. Fixed run-time settings from earlier versions are no longer used.

## Optional power and energy monitoring

In each car's integration settings, optionally select the smart plug's power sensor in W or kW and its cumulative energy sensor in Wh or kWh. An energy sensor should have state class `total` or `total_increasing`. Save settings between heating sessions: saving reloads the integration and stops a session it controls. The card can show current power and the energy used during the current or last heating session. The energy reading uses the most recently reported values; if the plug reports its final value late, it may be too low. If a session reading cannot be calculated reliably, it is shown as unavailable rather than guessed.

With a power sensor selected and low-power alerts enabled, the integration warns when the switch is on but power stays below the configured threshold. The defaults are 10 W and five minutes; both can be changed, and alerts can be switched off separately. A notification appears in Home Assistant. You can also select an optional notification entity, such as a phone running the Home Assistant app, to receive it there. Each channel notifies at most once per switch-on period. No reading or an unavailable sensor is not treated as zero power. Low power can have other causes, including a thermostat; check the cable and equipment.

Optionally choose a fixed electricity price per kWh or a price sensor and currency. If a sensor is selected, its price at the session's end is used; no fixed-price fallback is silently substituted if that sensor is unavailable. The displayed cost is an **estimate**, not a time-weighted bill, and older sessions are not priced retroactively. Missing readings or mixed currencies are marked incomplete.

## Heating history

The integration stores up to the 1,000 most recent switch-on periods separately for each vehicle. The companion card shows their start, end, duration and measured energy when available. A switch-on period does not prove the heater was consuming power. History is collected from version 0.7.0 onward; older sessions are not reconstructed. Sessions can be recorded without an energy sensor, and unavailable or incomplete readings are not shown as zero.

Daily, weekly and monthly summaries use those recorded, completed sessions, grouped by their local end date. If a session crosses a period boundary, its energy cannot be split reliably; the affected periods are marked incomplete and the end-period sum can be too high. Missing measurements and incomplete history are also marked. Up to 366 daily, 104 weekly and 36 monthly periods are displayed.

## Operation and safety

Test both start and stop with the actual switch and heater before unattended use. Home Assistant must be able to communicate with the switch for the off command to reach the heater. Use an independent maximum-run timer and equipment rated for the load and environment. Follow the car and heater manufacturers' instructions.

The integration has isolated tests but has not yet been fully verified on actual equipment. Scheduling is checked about once a minute and may be affected by outages or calendar sync delays.

The status entity includes calendar-derived schedule details. Anyone allowed to read that entity can see those details; give it the same access protection as the calendar.

## License

[MIT](LICENSE).
