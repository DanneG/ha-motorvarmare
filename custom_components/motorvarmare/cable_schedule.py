"""Decide when an optional cable check is useful, without operating the switch."""
from __future__ import annotations

from datetime import datetime, time, timedelta

from homeassistant.util import dt as dt_util

from .const import CONF_WEATHER_ENTITY
from .forecast import async_forecast_temperature


def in_cable_test_window(local_now: datetime, configured_time: str) -> bool:
    """Allow the next scheduler tick, but never make up a missed evening later."""
    try:
        start_time = time.fromisoformat(configured_time)
    except (TypeError, ValueError):
        return False
    if start_time.tzinfo is not None:
        return False
    start = datetime.combine(local_now.date(), start_time)
    elapsed = local_now.replace(tzinfo=None) - start
    return timedelta(0) <= elapsed < timedelta(minutes=5)


async def async_cable_test_departure(controller, now, duration_for_temperature):
    """Return tomorrow's first eligible departure when its temperature calls for heating."""
    if controller.owned or controller.automation_paused:
        return None
    today = dt_util.as_local(now).date()
    tomorrow = today + timedelta(days=1)
    # _candidates includes all configured departure sources, in order, and omits skips.
    departures = [
        when for when, source in controller._candidates(now)
        if f"{source}|{when.isoformat()}" not in controller._suppressed
    ]
    departure = next((when for when in departures if dt_util.as_local(when).date() == tomorrow), None)
    if departure is None:
        return None
    forecast = await async_forecast_temperature(controller.hass, controller.config.get(CONF_WEATHER_ENTITY), departure)
    measured = controller._temperature()
    temperature = measured if forecast is None else forecast
    expected_minutes = duration_for_temperature(temperature) if temperature is not None else 0
    if not expected_minutes:
        return None

    # Leave enough time to switch off before normal heating starts, including
    # the switch round trips. The actual heater schedule uses the outdoor sensor.
    now = max(now, dt_util.utcnow())
    if dt_util.as_local(now).date() != today:
        return None
    probe_deadline = now + timedelta(seconds=30)
    measured_minutes = duration_for_temperature(measured) if measured is not None else 0
    if measured_minutes and departures[0] - timedelta(minutes=measured_minutes) <= probe_deadline:
        return None
    if departure - timedelta(minutes=expected_minutes) <= probe_deadline:
        return None
    return departure
