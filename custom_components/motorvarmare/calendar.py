"""A calendar of one-time, locally stored vehicle departures."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.calendar import (
    EVENT_RRULE,
    EVENT_START,
    EVENT_SUMMARY,
    CalendarEntity,
    CalendarEntityFeature,
    CalendarEvent,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_EVENT_DURATION = timedelta(minutes=1)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create the local departure calendar for one car."""
    controller = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DepartureCalendar(entry, controller)])


class DepartureCalendar(CalendarEntity):
    """Expose one-time departures to the Home Assistant calendar UI.

    The event start is always the departure, not the heater start. End times
    are presentation-only: a departure is a point in time.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "departure_calendar"
    _attr_icon = "mdi:calendar-clock"
    _attr_should_poll = False
    _attr_supported_features = CalendarEntityFeature.CREATE_EVENT | CalendarEntityFeature.DELETE_EVENT

    def __init__(self, entry: ConfigEntry, controller) -> None:
        self.controller = controller
        self._signal = f"{DOMAIN}_{entry.entry_id}"
        self._attr_unique_id = f"{entry.entry_id}_departure_calendar"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name=entry.title)
        self._events_snapshot = None

    def _calendar_event(self, item: dict) -> CalendarEvent:
        start = dt_util.as_local(item["departure"])
        return CalendarEvent(
            start=start,
            end=dt_util.as_local(item["departure"] + _EVENT_DURATION),
            summary=item.get("summary") or "Departure",
            uid=item["uid"],
        )

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event in the local calendar."""
        now = dt_util.utcnow()
        upcoming = [item for item in self.controller.local_departures if item["departure"] + _EVENT_DURATION > now]
        if not upcoming:
            return None
        return self._calendar_event(min(upcoming, key=lambda item: item["departure"]))

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return every local departure that overlaps the requested window."""
        return [
            self._calendar_event(item)
            for item in sorted(self.controller.local_departures, key=lambda item: item["departure"])
            if item["departure"] < end_date and item["departure"] + _EVENT_DURATION > start_date
        ]

    async def async_create_event(self, **kwargs: Any) -> None:
        """Add a future timed event; recurring schedules use weekly controls."""
        if kwargs.get(EVENT_RRULE):
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="recurring_unsupported")
        start = kwargs.get(EVENT_START)
        if not isinstance(start, datetime):
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="timed_departure_required")
        if start.tzinfo is None:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="timezone_required")
        local_start = dt_util.as_local(start)
        if dt_util.as_local(dt_util.as_utc(local_start)).replace(tzinfo=None) != local_start.replace(tzinfo=None):
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="departure_nonexistent_time")
        try:
            await self.controller.async_add_local_departure(start, kwargs.get(EVENT_SUMMARY))
        except ValueError as exc:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key=str(exc)) from exc

    async def async_delete_event(
        self, uid: str, recurrence_id: str | None = None, recurrence_range: str | None = None
    ) -> None:
        """Delete just the specified local departure, not a Google event."""
        if recurrence_id or recurrence_range:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="recurring_unsupported")
        try:
            await self.controller.async_delete_local_departure(uid)
        except ValueError as exc:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key=str(exc)) from exc

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(self.hass, self._signal, self._on_controller_update))

    @callback
    def _on_controller_update(self) -> None:
        """Refresh event subscribers when the local departures change."""
        snapshot = tuple((item["uid"], item["departure"], item.get("summary")) for item in self.controller.local_departures)
        if snapshot != self._events_snapshot:
            self._events_snapshot = snapshot
            self.async_update_event_listeners()
        self.async_write_ha_state()
