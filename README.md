# Engine Heater for Home Assistant

English · [Svenska](docs/README.sv.md)

Schedule an electric engine heater using the outdoor temperature and a departure time. Each car has its own Home Assistant-compatible smart plug or switch and departure schedule. Configuration, entities and the companion dashboard card support English and Swedish.

## Installation

Add `https://github.com/DanneG/ha-motorvarmare` as a custom repository in Marketplace or HACS with category **Integration**, then install it. Restart Home Assistant after updating. Under **Settings → Devices & services**, add **Motorvärmare** once for each car. Select the car's switch and an outdoor temperature sensor in °C or °F. A Google calendar is optional.

Also install the separate [Engine Heater dashboard card](https://github.com/DanneG/ha-motorvarmare-card) as a custom repository with category **Dashboard**. Add the card to a dashboard and select the car's status entity. See the card's installation instructions.

For a manual installation, copy `custom_components/motorvarmare` into the Home Assistant configuration's `custom_components` directory, including `translations` and `brand`, and restart Home Assistant. The card is installed separately.

## Departures and calendar

The card shows the next seven local calendar days, with departures and estimated heater start and stop times. Start times are **estimates using the current outdoor temperature**, not a weather forecast, and can change as the temperature changes. Departures may come from the weekly schedule, Google Calendar, or the integration's own calendar.

Select a day in the card to add one or more departure times. These are stored in the car's own Home Assistant calendar and can be removed individually. They are not written to Google Calendar. The existing weekly schedule and single manual-departure entity remain available. The nearest future departure controls the heater.

To use Google Calendar, first set up the [Google Calendar integration](https://www.home-assistant.io/integrations/google/), choose a calendar in the car's settings, and enter exact event titles and/or words or tags, separated by commas or line breaks. An event matches if its entire title equals one of the titles, **or** if any word or tag appears in its title or description. Matching ignores letter case. The event's start is the departure time; all-day events are ignored. Calendar changes can take time to reach Home Assistant.

## Heating time and start now

The run time in minutes is **30 − 1.5 × outdoor temperature in °C**. The result is rounded up to a whole minute and limited to 0–240 minutes. Examples: +10 °C → 15 minutes, 0 °C → 30 minutes, −10 °C → 45 minutes, and −20 °C → 60 minutes. At +20 °C or above the result is zero. Fahrenheit sensors are converted to °C first.

**Start now** uses the same formula and turns the heater off when the calculated time has elapsed. **Stop** cancels a heating session controlled by the integration. If the switch is already on when scheduled heating should begin, the integration does not take ownership of it. Fixed run-time settings from earlier versions are no longer used.

## Optional power and energy monitoring

In each car's integration settings, optionally select the smart plug's power sensor in W or kW and its cumulative energy sensor in Wh or kWh. An energy sensor should have state class `total` or `total_increasing`. Save settings between heating sessions: saving reloads the integration and stops a session it controls. The card can show current power and the energy used during the current or last heating session. The energy reading uses the most recently reported values; if the plug reports its final value late, it may be too low. If a session reading cannot be calculated reliably, it is shown as unavailable rather than guessed.

With a power sensor selected and low-power alerts enabled, the integration warns when the switch is on but power stays below the configured threshold. The defaults are 10 W and five minutes; both can be changed, and alerts can be switched off separately. A notification appears in Home Assistant. You can also select an optional notification entity, such as a phone running the Home Assistant app, to receive it there. Each channel notifies at most once per switch-on period. No reading or an unavailable sensor is not treated as zero power. Low power can have other causes, including a thermostat; check the cable and equipment.

## Heating history

The integration stores up to the 100 most recent switch-on periods separately for each vehicle. The companion card shows their start, end, duration and measured energy when available. A switch-on period does not prove the heater was consuming power. History is collected from version 0.7.0 onward; older sessions are not reconstructed. Sessions can be recorded without an energy sensor, and unavailable or incomplete readings are not shown as zero.

## Operation and safety

Test both start and stop with the actual switch and heater before unattended use. Home Assistant must be able to communicate with the switch for the off command to reach the heater. Use an independent maximum-run timer and equipment rated for the load and environment. Follow the car and heater manufacturers' instructions.

The integration has isolated tests but has not yet been fully verified on actual equipment. Scheduling is checked about once a minute and may be affected by outages or calendar sync delays.

## License

[MIT](LICENSE).
