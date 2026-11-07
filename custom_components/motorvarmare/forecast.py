"""Forecast-only estimates for calendar display; never controls the heater."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import logging
import math
import time as monotonic_time

_LOGGER = logging.getLogger(__name__)
_MAX_FORECAST_DISTANCE = timedelta(minutes=60)
_CACHE_SECONDS = 900


def _datetime(value):
    """Return an aware datetime or None for malformed/ambiguous values."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _forecast_points(response, entity_id, unit):
    """Validate hourly data, converting the weather entity's unit to Celsius."""
    if unit not in ("°C", "°F") or not isinstance(response, dict):
        return []
    entity = response.get(entity_id)
    if not isinstance(entity, dict) or not isinstance(entity.get("forecast"), list):
        return []
    points = []
    for item in entity["forecast"]:
        if not isinstance(item, dict):
            continue
        when = _datetime(item.get("datetime"))
        if isinstance(item.get("temperature"), bool):
            continue
        try:
            value = float(item.get("temperature"))
        except (TypeError, ValueError, OverflowError):
            continue
        if when is None or not math.isfinite(value):
            continue
        if unit == "°F":
            value = (value - 32) * 5 / 9
        points.append((when, value))
    return sorted(points, key=lambda point: point[0])


def _nearest(points, departure):
    """Use a nearby hourly forecast, never extrapolate beyond its coverage."""
    if not points or departure < points[0][0] or departure > points[-1][0]:
        return None
    when, value = min(points, key=lambda point: abs(point[0] - departure))
    return value if abs(when - departure) <= _MAX_FORECAST_DISTANCE else None


async def async_project_forecasts(hass, weather_entity, result, duration_for_temperature, *, blocked=False, now=None, end=None):
    """Return forecast estimates and trim boundary events; leave the scheduler untouched.

    The caller must check weather entity read permission before supplying its ID.
    A missing or unavailable forecast uses each event's existing current-temperature
    estimate. ``end`` is the UTC-aware exclusive end of the visible date window.
    """
    now = _datetime(now) if now is not None else datetime.now(timezone.utc)
    end = _datetime(end) if end is not None else None
    points = []
    if weather_entity:
        state = hass.states.get(weather_entity)
        if state and state.state not in ("unknown", "unavailable"):
            unit = state.attributes.get("temperature_unit")
            if unit in ("°C", "°F"):
                data = getattr(hass, "data", None)
                cache = data.setdefault("motorvarmare_forecast_cache", {}) if isinstance(data, dict) else None
                cache_key = (weather_entity, unit)
                cached = cache.get(cache_key) if cache is not None else None
                try:
                    if cached and monotonic_time.monotonic() - cached[0] < _CACHE_SECONDS:
                        points = cached[1]
                    else:
                        response = await asyncio.wait_for(hass.services.async_call(
                            "weather", "get_forecasts", {"entity_id": weather_entity, "type": "hourly"},
                            blocking=True, return_response=True), timeout=10)
                        points = _forecast_points(response, weather_entity, unit)
                        if cache is not None:
                            if points:
                                cache[cache_key] = (monotonic_time.monotonic(), points)
                            else:
                                cache.pop(cache_key, None)
                except Exception:
                    _LOGGER.debug("Hourly weather forecast unavailable; using current temperature", exc_info=True)
    events = []
    for original in result.get("events", []):
        event = dict(original)
        event["temperature_source"] = "current" if event.get("duration_minutes") is not None else "unavailable"
        departure = _datetime(event.get("departure"))
        value = _nearest(points, departure) if departure is not None and now is not None and departure > now else None
        if value is not None:
            value = round(value, 1)
            minutes = duration_for_temperature(value)
            event["forecast_temperature"] = value
            event["temperature_source"] = "forecast"
            event["duration_minutes"] = minutes
            event["start"] = (departure - timedelta(minutes=minutes)).isoformat() if minutes and not blocked else None
        start = _datetime(event.get("start"))
        if end is not None and departure is not None and departure >= end and (start is None or start >= end):
            continue
        events.append(event)
    return {**result, "events": events}
