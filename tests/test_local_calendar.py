"""Local calendar behavior with small Home Assistant API mocks."""
import importlib
from datetime import datetime, timedelta, timezone, tzinfo
import types
import unittest
from unittest.mock import patch

import test_controller as mocks

mocks.module("homeassistant.components")
calendar_api = mocks.module("homeassistant.components.calendar")
calendar_api.EVENT_START = "dtstart"
calendar_api.EVENT_RRULE = "rrule"
calendar_api.EVENT_SUMMARY = "summary"


class FakeCalendarEntity:
    async def async_added_to_hass(self):
        pass

    def async_on_remove(self, callback):
        pass

    def async_write_ha_state(self):
        self.writes += 1

    def async_update_event_listeners(self):
        self.event_updates += 1


class FakeCalendarEvent:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeFeatures:
    CREATE_EVENT = 1
    DELETE_EVENT = 2
    UPDATE_EVENT = 4


calendar_api.CalendarEntity = FakeCalendarEntity
calendar_api.CalendarEntityFeature = FakeFeatures
calendar_api.CalendarEvent = FakeCalendarEvent
mocks.module("homeassistant.config_entries").ConfigEntry = object
mocks.core.HomeAssistant = object
mocks.module("homeassistant.helpers.device_registry").DeviceInfo = lambda **kwargs: kwargs
mocks.module("homeassistant.helpers.entity_platform").AddEntitiesCallback = object
dispatcher = importlib.import_module("homeassistant.helpers.dispatcher")
dispatcher.async_dispatcher_connect = lambda *args: lambda: None
exceptions = mocks.module("homeassistant.exceptions")
class FakeServiceValidationError(Exception):
    def __init__(self, *args, **kwargs):
        self.translation_key = kwargs.get("translation_key")
        super().__init__(*args)


exceptions.ServiceValidationError = FakeServiceValidationError
calendar = importlib.import_module("test_motorvarmare.calendar")


class LocalCalendarTests(unittest.TestCase):
    @mocks.sync_test
    async def test_rejects_nonexistent_spring_clock_time(self):
        class SpringClock(tzinfo):
            def utcoffset(self, value):
                return timedelta(hours=2 if value.hour >= 3 else 1)

            def dst(self, value):
                return self.utcoffset(value) - timedelta(hours=1)

            def fromutc(self, value):
                return value + timedelta(hours=2 if value.hour >= 1 else 1)

        zone = SpringClock()
        hass = mocks.Hass()
        c = mocks.new_controller(hass)
        entity = calendar.DepartureCalendar(types.SimpleNamespace(entry_id="car1", title="Car"), c)
        with patch.object(mocks, "LOCAL", zone):
            with self.assertRaises(exceptions.ServiceValidationError) as err:
                await entity.async_create_event(dtstart=datetime(2027, 3, 28, 2, 30, tzinfo=zone))
            self.assertEqual(err.exception.translation_key, "departure_nonexistent_time")
            await entity.async_create_event(dtstart=datetime(2027, 3, 28, 3, 30, tzinfo=zone))
        self.assertEqual(len(c.local_departures), 1)

    @mocks.sync_test
    async def test_multiple_same_day_events_survive_reload_and_delete_by_id(self):
        hass = mocks.Hass()
        controller = mocks.new_controller(hass)
        entry = types.SimpleNamespace(entry_id="car1", title="Car 1")
        entity = calendar.DepartureCalendar(entry, controller)
        first = datetime(2026, 11, 2, 8, 0, tzinfo=timezone.utc)
        second = first + timedelta(hours=4)
        await entity.async_create_event(dtstart=first, summary="Work")
        await entity.async_create_event(dtstart=second, summary="Shopping")
        events = await entity.async_get_events(hass, first - timedelta(hours=1), second + timedelta(hours=1))
        self.assertEqual([item.summary for item in events], ["Work", "Shopping"])
        self.assertNotEqual(events[0].uid, events[1].uid)
        self.assertEqual(events[0].start.astimezone(timezone.utc), first)
        self.assertEqual(entity.event.uid, events[0].uid)

        restored = mocks.new_controller(hass)
        await restored.async_load()
        self.assertEqual(len(restored.local_departures), 2)
        entity.controller = restored
        await entity.async_delete_event(events[0].uid)
        self.assertEqual([item["uid"] for item in restored.local_departures], [events[1].uid])
        self.assertEqual(restored._candidates(mocks.dt.utcnow())[0], (second, "Planerad"))

    @mocks.sync_test
    async def test_invalid_events_and_unknown_uid_are_reported(self):
        hass = mocks.Hass()
        c = mocks.new_controller(hass)
        entity = calendar.DepartureCalendar(types.SimpleNamespace(entry_id="car1", title="Car"), c)
        future = datetime(2026, 11, 2, 8, tzinfo=timezone.utc)
        with self.assertRaises(exceptions.ServiceValidationError):
            await entity.async_create_event(dtstart=future.date(), summary="All day")
        with self.assertRaises(exceptions.ServiceValidationError):
            await entity.async_create_event(dtstart=future.replace(tzinfo=None), summary="No zone")
        with self.assertRaises(exceptions.ServiceValidationError):
            await entity.async_create_event(dtstart=future, summary="Recurring", rrule="FREQ=HOURLY")
        with self.assertRaises(exceptions.ServiceValidationError):
            await entity.async_delete_event("missing")
        self.assertEqual(c.local_departures, [])

    @mocks.sync_test
    async def test_calendar_notifies_only_when_event_list_changes(self):
        hass = mocks.Hass()
        c = mocks.new_controller(hass)
        entity = calendar.DepartureCalendar(types.SimpleNamespace(entry_id="car1", title="Car"), c)
        entity.writes = entity.event_updates = 0
        entity._on_controller_update()
        entity._on_controller_update()
        self.assertEqual(entity.event_updates, 1)
        c.local_departures.append({"uid": "id", "departure": datetime(2026, 11, 2, 8, tzinfo=timezone.utc)})
        entity._on_controller_update()
        self.assertEqual(entity.event_updates, 2)
        self.assertEqual(entity.writes, 3)


if __name__ == "__main__":
    unittest.main()
