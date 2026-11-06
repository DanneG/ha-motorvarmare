"""Editing local departures must be atomic and preserve instance identity."""
from datetime import datetime, timedelta, timezone
import asyncio
import types
import unittest
from unittest.mock import patch

import test_controller as mocks
import test_local_calendar as calendar_mocks
from test_recurrence import recurrence


class EditTests(unittest.TestCase):
    def setUp(self):
        self.zone, self.clock = mocks.LOCAL, mocks.dt.utcnow
        self.wait, self.sleep = asyncio.wait_for, asyncio.sleep
        mocks.LOCAL = timezone(timedelta(hours=1))
        self.now = datetime(2026, 11, 2, 5, tzinfo=timezone.utc)
        mocks.dt.utcnow = lambda: self.now
        asyncio.wait_for, asyncio.sleep = mocks.immediate_wait_for, mocks.immediate_sleep
        self.hass = mocks.Hass()
        self.c = mocks.new_controller(self.hass)

    def tearDown(self):
        mocks.LOCAL, mocks.dt.utcnow = self.zone, self.clock
        asyncio.wait_for, asyncio.sleep = self.wait, self.sleep

    @mocks.sync_test
    async def test_move_occurrence_persists_across_ranges_and_deletes(self):
        first = self.now + timedelta(hours=2)
        uid = await self.c.async_add_local_departure(first, "Trip", "FREQ=DAILY")
        moved = first + timedelta(days=40, hours=1)
        await self.c.async_update_local_departure(uid, moved, "Changed", recurrence_id=first.isoformat())
        self.assertNotIn(first, [x["departure"] for x in self.c.local_events_between(first, first + timedelta(hours=1))])
        rows = self.c.local_events_between(moved, moved + timedelta(minutes=1))
        self.assertEqual([(x["uid"], x["recurrence_id"], x["summary"]) for x in rows],
                         [(uid, first.isoformat(), "Changed")])
        self.assertEqual(rows[0]["series_summary"], "Trip")
        projected = await self.c.async_schedule_between(moved.date(), moved.date() + timedelta(days=1))
        self.assertEqual(next(x for x in projected["events"] if x["recurrence_id"] == first.isoformat())["series_summary"], "Trip")
        restored = mocks.new_controller(self.hass)
        await restored.async_load()
        self.assertEqual(restored.local_events_between(moved, moved + timedelta(minutes=1))[0]["departure"], moved)
        await restored.async_update_local_departure(uid, moved + timedelta(hours=1), "Again", recurrence_id=first.isoformat())
        await restored.async_delete_local_departure(uid, first.isoformat())
        self.assertEqual(restored.local_events_between(moved, moved + timedelta(hours=2)), [])
        self.assertEqual(restored.local_events_between(first, first + timedelta(hours=1)), [])

    @mocks.sync_test
    async def test_next_occurrence_finds_override_after_rule_ends(self):
        first = self.now + timedelta(hours=2)
        uid = await self.c.async_add_local_departure(first, "Trip", "FREQ=DAILY;UNTIL=20261102")
        moved = first + timedelta(days=40)
        await self.c.async_update_local_departure(uid, moved, "Trip", recurrence_id=first.isoformat())
        self.assertEqual(recurrence.next_occurrence(self.c.recurring_departures[0], self.now)["departure"], moved)
        self.assertIn((moved, "Planerad"), self.c._candidates(self.now))

    @mocks.sync_test
    async def test_series_changes_preserve_or_clear_exceptions_and_convert(self):
        first = self.now + timedelta(hours=2)
        uid = await self.c.async_add_local_departure(first, "Trip", "FREQ=DAILY")
        await self.c.async_update_local_departure(uid, first + timedelta(hours=1), "Special", recurrence_id=first.isoformat())
        await self.c.async_update_local_departure(uid, first, "New title", "FREQ=DAILY")
        self.assertEqual(len(self.c.recurring_departures[0]["overrides"]), 1)
        await self.c.async_update_local_departure(uid, first, "New title", "FREQ=WEEKLY")
        self.assertEqual(self.c.recurring_departures[0]["exceptions"], [])
        self.assertEqual(self.c.recurring_departures[0]["overrides"], [])
        await self.c.async_update_local_departure(uid, first, "Single")
        self.assertEqual(self.c.recurring_departures, [])
        self.assertEqual(self.c.local_departures[0]["uid"], uid)
        await self.c.async_update_local_departure(uid, first, "Repeating", "FREQ=YEARLY")
        self.assertEqual(self.c.recurring_departures[0]["uid"], uid)

    @mocks.sync_test
    async def test_rejects_invalid_edit_without_mutation_and_rolls_back_failed_save(self):
        first = self.now + timedelta(hours=2)
        uid = await self.c.async_add_local_departure(first, "Trip")
        saved = list(self.c.local_departures)
        with self.assertRaises(ValueError):
            await self.c.async_update_local_departure(uid, first, "Trip", "FREQ=DAILY;UNTIL=20261101")
        self.assertEqual(self.c.local_departures, saved)
        async def fail():
            raise RuntimeError("save failed")
        with patch.object(self.c, "_save", fail), self.assertRaises(RuntimeError):
            await self.c.async_update_local_departure(uid, first + timedelta(hours=1), "Changed")
        self.assertEqual(self.c.local_departures, saved)
        self.assertEqual(self.c.recurring_departures, [])

    @mocks.sync_test
    async def test_past_series_anchor_and_override_rollback(self):
        first = self.now + timedelta(hours=2)
        uid = await self.c.async_add_local_departure(first, "Trip", "FREQ=DAILY")
        past_anchor = first - timedelta(days=2)
        await self.c.async_update_local_departure(uid, past_anchor, "Trip", "FREQ=DAILY")
        self.assertEqual(self.c.recurring_departures[0]["departure"], past_anchor)
        previous = self.c.recurring_departures[0].copy()
        async def fail():
            raise RuntimeError("save failed")
        with patch.object(self.c, "_save", fail), self.assertRaises(RuntimeError):
            await self.c.async_update_local_departure(uid, first + timedelta(hours=1), "Moved", recurrence_id=first.isoformat())
        self.assertEqual(self.c.recurring_departures[0], previous)
        restored = mocks.new_controller(self.hass)
        await restored.async_load()
        self.assertEqual(restored.recurring_departures[0]["departure"], past_anchor)
        self.assertEqual(restored.recurring_departures[0]["overrides"], [])
        with patch.object(self.c, "_save", fail), self.assertRaises(RuntimeError):
            await self.c.async_delete_local_departure(uid, first.isoformat())
        self.assertEqual(self.c.recurring_departures[0], previous)

    @mocks.sync_test
    async def test_moving_active_instance_stops_heater(self):
        first = self.now + timedelta(minutes=30)
        uid = await self.c.async_add_local_departure(first, "Trip", "FREQ=DAILY")
        self.assertTrue(self.c.owned)
        await self.c.async_update_local_departure(uid, first + timedelta(hours=2), "Trip", recurrence_id=first.isoformat())
        self.assertFalse(self.c.owned)
        self.assertEqual(self.hass.states["switch.heater"].state, "off")

    @mocks.sync_test
    async def test_move_occurrence_across_daylight_saving_change(self):
        try:
            from zoneinfo import ZoneInfo
            zone = ZoneInfo("Europe/Stockholm")
        except Exception:
            self.skipTest("Time-zone data unavailable")
        mocks.LOCAL = zone
        first = datetime(2027, 3, 21, 9, tzinfo=zone).astimezone(timezone.utc)
        moved = datetime(2027, 4, 1, 9, tzinfo=zone).astimezone(timezone.utc)
        uid = await self.c.async_add_local_departure(first, "Trip", "FREQ=WEEKLY")
        await self.c.async_update_local_departure(uid, moved, "Trip", recurrence_id=first.isoformat())
        restored = mocks.new_controller(self.hass)
        await restored.async_load()
        rows = restored.local_events_between(moved, moved + timedelta(minutes=1))
        self.assertEqual(rows[0]["recurrence_id"], first.isoformat())
        self.assertEqual(rows[0]["departure"].astimezone(zone).hour, 9)

    @mocks.sync_test
    async def test_calendar_update_validates_and_preserves_uid(self):
        first = self.now + timedelta(hours=2)
        uid = await self.c.async_add_local_departure(first, "Trip")
        entity = calendar_mocks.calendar.DepartureCalendar(types.SimpleNamespace(entry_id="car1", title="Car"), self.c)
        self.assertTrue(entity._attr_supported_features & calendar_mocks.FakeFeatures.UPDATE_EVENT)
        await entity.async_update_event(uid, {"dtstart": first + timedelta(hours=1), "summary": "Changed"})
        self.assertEqual(self.c.local_departures[0]["uid"], uid)
        with self.assertRaises(calendar_mocks.exceptions.ServiceValidationError):
            await entity.async_update_event(uid, {"dtstart": first}, recurrence_range="THISANDFUTURE")


if __name__ == "__main__":
    unittest.main()
