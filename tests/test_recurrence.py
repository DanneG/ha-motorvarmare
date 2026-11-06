"""Regression tests for local recurring departures and schedule projection."""
from datetime import date, datetime, timedelta, timezone
import asyncio
import importlib
import sys
import types
import unittest
from unittest.mock import patch

import test_controller as mocks
import test_local_calendar as calendar_mocks

recurrence = importlib.import_module("test_motorvarmare.recurrence")
UTC = timezone.utc


class RecurrenceTests(unittest.TestCase):
    def setUp(self):
        self.original_zone, self.original_now = mocks.LOCAL, mocks.dt.utcnow
        self.original_wait_for, self.original_sleep = asyncio.wait_for, asyncio.sleep
        mocks.LOCAL = timezone(timedelta(hours=1))
        self.now = datetime(2026, 11, 2, 5, 0, tzinfo=UTC)
        mocks.dt.utcnow = lambda: self.now
        asyncio.wait_for, asyncio.sleep = mocks.immediate_wait_for, mocks.immediate_sleep
        self.hass = mocks.Hass()
        self.item = mocks.new_controller(self.hass)

    def tearDown(self):
        mocks.LOCAL, mocks.dt.utcnow = self.original_zone, self.original_now
        asyncio.wait_for, asyncio.sleep = self.original_wait_for, self.original_sleep

    def series(self, start, rule):
        return {"uid": "series", "departure": start, "rrule": rule, "summary": "Trip", "exceptions": []}

    def test_daily_interval_and_inclusive_until_date(self):
        series = self.series(datetime(2026, 11, 2, 8, tzinfo=UTC), "FREQ=DAILY;INTERVAL=2;UNTIL=20261106")
        items = recurrence.expand_series(series, self.now, self.now + timedelta(days=10))
        self.assertEqual([mocks.dt.as_local(i["departure"]).day for i in items], [2, 4, 6])
        self.assertIsNone(recurrence.next_occurrence(series, datetime(2026, 11, 7, tzinfo=UTC)))

    def test_weekly_selected_days_and_no_implicit_start_day(self):
        # Start Monday, but only Tuesday and Thursday should occur.
        series = self.series(datetime(2026, 11, 2, 8, tzinfo=UTC), "FREQ=WEEKLY;INTERVAL=2;BYDAY=TU,TH")
        items = recurrence.expand_series(series, self.now, self.now + timedelta(days=18))
        self.assertEqual([mocks.dt.as_local(i["departure"]).date() for i in items],
                         [date(2026, 11, 3), date(2026, 11, 5), date(2026, 11, 17), date(2026, 11, 19)])
        self.assertEqual(recurrence.next_occurrence(series, self.now)["departure"], items[0]["departure"])

    def test_monthly_and_leap_year_skip_missing_dates(self):
        monthly = self.series(datetime(2027, 1, 31, 8, tzinfo=UTC), "FREQ=MONTHLY")
        events = recurrence.expand_series(monthly, datetime(2027, 1, 1, tzinfo=UTC), datetime(2027, 6, 1, tzinfo=UTC))
        self.assertEqual([mocks.dt.as_local(x["departure"]).date() for x in events],
                         [date(2027, 1, 31), date(2027, 3, 31), date(2027, 5, 31)])
        leap = self.series(datetime(2028, 2, 29, 8, tzinfo=UTC), "FREQ=YEARLY")
        self.assertEqual(mocks.dt.as_local(recurrence.next_occurrence(leap, datetime(2029, 1, 1, tzinfo=UTC))["departure"]).date(), date(2032, 2, 29))

    def test_next_long_interval_and_old_daily_are_fast_and_correct(self):
        old = self.series(datetime(2000, 1, 1, 8, tzinfo=UTC), "FREQ=DAILY")
        self.assertEqual(mocks.dt.as_local(recurrence.next_occurrence(old, datetime(2100, 1, 2, tzinfo=UTC))["departure"]).date(), date(2100, 1, 2))
        yearly = self.series(datetime(2026, 11, 2, 8, tzinfo=UTC), "FREQ=YEARLY;INTERVAL=10")
        self.assertEqual(mocks.dt.as_local(recurrence.next_occurrence(yearly, datetime(2027, 1, 1, tzinfo=UTC))["departure"]).date(), date(2036, 11, 2))
        self.item.recurring_departures = [yearly]
        self.assertEqual(self.item._candidates(datetime(2027, 1, 1, tzinfo=UTC))[0][0].year, 2036)

    def test_unsupported_rules_fail_closed(self):
        for rule in ("FREQ=HOURLY", "FREQ=DAILY;COUNT=5", "FREQ=MONTHLY;BYDAY=MO", "FREQ=WEEKLY;BYDAY=1MO", "FREQ=DAILY;INTERVAL=0", "FREQ=DAILY;UNTIL=garbage"):
            with self.subTest(rule=rule), self.assertRaises(ValueError):
                recurrence.parse_rule(rule)

    def test_stockholm_dst_and_last_day(self):
        try:
            from zoneinfo import ZoneInfo
            zone = ZoneInfo("Europe/Stockholm")
        except Exception:
            self.skipTest("Time-zone data unavailable")
        mocks.LOCAL = zone
        base = datetime(2027, 3, 22, 9, tzinfo=zone).astimezone(UTC)
        series = self.series(base, "FREQ=WEEKLY;BYDAY=TU,TH;UNTIL=20270401")
        events = recurrence.expand_series(series, base, datetime(2027, 4, 3, tzinfo=UTC))
        local = [x["departure"].astimezone(zone) for x in events]
        self.assertEqual([x.date() for x in local], [date(2027, 3, 23), date(2027, 3, 25), date(2027, 3, 30), date(2027, 4, 1)])
        self.assertTrue(all(x.hour == 9 for x in local))
        self.assertNotEqual(local[0].utcoffset(), local[-1].utcoffset())
        spring = self.series(datetime(2027, 3, 21, 2, 30, tzinfo=zone).astimezone(UTC), "FREQ=WEEKLY")
        events = recurrence.expand_series(spring, spring["departure"], datetime(2027, 4, 6, tzinfo=UTC))
        self.assertEqual([x["departure"].astimezone(zone).date() for x in events], [date(2027, 3, 21), date(2027, 4, 4)])
        autumn = self.series(datetime(2027, 10, 24, 2, 30, tzinfo=zone).astimezone(UTC), "FREQ=WEEKLY")
        events = recurrence.expand_series(autumn, autumn["departure"], datetime(2027, 11, 3, tzinfo=UTC))
        repeated = events[-1]["departure"].astimezone(zone)
        self.assertEqual((repeated.date(), repeated.hour, repeated.fold), (date(2027, 10, 31), 2, 0))

    @mocks.sync_test
    async def test_series_persists_individual_deletion_and_active_stop(self):
        first = self.now + timedelta(minutes=30)
        uid = await self.item.async_add_local_departure(first, "Trip", "FREQ=DAILY")
        self.assertTrue(self.item.owned)
        self.assertEqual(self.hass.states["switch.heater"].state, "on")
        row = self.item.schedule_7_days[0]
        self.assertEqual(row["uid"], uid)
        self.assertEqual(row["recurrence_id"], first.isoformat())
        await self.item.async_delete_local_departure(uid, first.isoformat())
        self.assertFalse(self.item.owned)
        self.assertEqual(self.hass.states["switch.heater"].state, "off")
        restored = mocks.new_controller(self.hass)
        await restored.async_load()
        future = restored.local_events_between(self.now, self.now + timedelta(days=3))
        self.assertEqual([x["departure"] for x in future], [first + timedelta(days=1), first + timedelta(days=2)])
        await restored.async_delete_local_departure(uid)
        self.assertEqual(restored.recurring_departures, [])

    @mocks.sync_test
    async def test_rule_without_any_occurrence_is_not_saved(self):
        with self.assertRaises(ValueError):
            await self.item.async_add_local_departure(self.now + timedelta(days=1), "Trip", "FREQ=DAILY;UNTIL=20261101")
        self.assertEqual(self.item.recurring_departures, [])

    @mocks.sync_test
    async def test_deleting_whole_active_series_stops_and_overlap_stays_suppressed(self):
        first = self.now + timedelta(minutes=30)
        uid = await self.item.async_add_local_departure(first, "First", "FREQ=DAILY")
        self.assertTrue(self.item.owned)
        await self.item.async_delete_local_departure(uid)
        self.assertFalse(self.item.owned)
        self.assertEqual(self.hass.states["switch.heater"].state, "off")
        await self.item.async_add_local_departure(first, "First", "FREQ=DAILY")
        await self.item.async_add_local_departure(first + timedelta(minutes=10), "Second", "FREQ=DAILY")
        self.assertTrue(self.item.owned)
        await self.item.async_stop_now()
        await self.item.async_update()
        self.assertFalse(self.item.owned)
        self.assertEqual(self.hass.states["switch.heater"].state, "off")

    @mocks.sync_test
    async def test_renaming_stopped_series_or_instance_does_not_restart_heater(self):
        departure = self.now + timedelta(minutes=30)
        uid = await self.item.async_add_local_departure(departure, "Trip", "FREQ=DAILY")
        self.assertTrue(self.item.owned)
        await self.item.async_stop_now()
        self.assertEqual(self.hass.states["switch.heater"].state, "off")
        await self.item.async_update_local_departure(uid, departure, "New series title", "FREQ=DAILY")
        self.assertFalse(self.item.owned)
        self.assertEqual(self.hass.states["switch.heater"].state, "off")
        await self.item.async_update_local_departure(uid, departure, "New instance title", recurrence_id=departure.isoformat())
        self.assertFalse(self.item.owned)
        self.assertEqual(self.hass.states["switch.heater"].state, "off")

    @mocks.sync_test
    async def test_projection_combines_sources_and_marks_calendar_error(self):
        self.item.config["calendar_entity"] = "calendar.google"
        self.item.config["tag"] = "#bil1"
        self.item.weekly_enabled[0] = True
        local = self.now + timedelta(hours=2)
        await self.item.async_add_local_departure(local, "Local", "FREQ=DAILY")
        self.hass.events = [{"summary": "Work #bil1", "start": "2026-11-02T10:00:00+01:00"},
                            {"summary": "Unrelated", "start": "2026-11-02T11:00:00+01:00"},
                            {"summary": "All day #bil1", "start": "2026-11-02"}]
        projection = await self.item.async_schedule_between(date(2026, 11, 2), date(2026, 11, 9))
        self.assertEqual(set(x["source"] for x in projection["events"]), {"Planerad", "Veckoschema", "Kalender"})
        self.assertFalse(projection["calendar_error"])
        self.assertEqual(sum(x["source"] == "Kalender" for x in projection["events"]), 1)
        denied = await self.item.async_schedule_between(date(2026, 11, 2), date(2026, 11, 9), include_external=False)
        self.assertTrue(denied["calendar_error"])
        self.assertFalse(any(x["source"] == "Kalender" for x in denied["events"]))
        with self.assertRaises(ValueError):
            await self.item.async_schedule_between(date(2026, 1, 1), date(2026, 3, 1))


if __name__ == "__main__":
    unittest.main()
