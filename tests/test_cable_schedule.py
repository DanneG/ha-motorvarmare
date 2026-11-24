"""Local evening scheduling and temperature selection for optional cable checks."""
import asyncio
from datetime import datetime, timedelta
import importlib
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_controller as mocks

schedule = importlib.import_module("test_motorvarmare.cable_schedule")


class EveningWindowTests(unittest.TestCase):
    def test_window_uses_local_time_and_closes_after_five_minutes(self):
        start = datetime.fromisoformat("2026-11-02T21:00:00+01:00")
        for seconds, expected in [(-1, False), (0, True), (299, True), (300, False), (7200, False)]:
            with self.subTest(seconds=seconds):
                self.assertEqual(schedule.in_cable_test_window(start + timedelta(seconds=seconds), "21:00:00"), expected)
        self.assertTrue(schedule.in_cable_test_window(start, "20:57"))
        self.assertFalse(schedule.in_cable_test_window(start, "not a time"))
        self.assertFalse(schedule.in_cable_test_window(start, "21:00:00+02:00"))

    def test_window_never_carries_into_the_next_date(self):
        self.assertFalse(schedule.in_cable_test_window(datetime.fromisoformat("2026-11-03T00:01+01:00"), "23:59"))


class CableDepartureTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.fromisoformat("2026-11-02T20:00:00+00:00")
        self.first = datetime.fromisoformat("2026-11-03T06:00:00+00:00")
        self.second = self.first + timedelta(hours=2)
        self.hass = mocks.Hass()
        self.car = mocks.new_controller(self.hass)
        self.car.manual_departure = self.first
        self.enterContext(patch.object(schedule.dt_util, "utcnow", side_effect=lambda: self.now))
        self.enterContext(patch.object(asyncio, "wait_for", mocks.immediate_wait_for))

    def use_forecast(self, points):
        self.car.config["weather_entity"] = "weather.car"
        self.hass.states["weather.car"] = SimpleNamespace(state="cloudy", attributes={"temperature_unit": "°C"})
        async def call(domain, action, data, **kwargs):
            self.assertEqual((domain, action), ("weather", "get_forecasts"))
            self.assertEqual(data, {"entity_id":"weather.car", "type":"hourly"})
            return {"weather.car": {"forecast": [{"datetime": dt.isoformat(), "temperature": value} for dt, value in points]}}
        self.hass.services = SimpleNamespace(async_call=call)

    async def departure(self):
        return await schedule.async_cable_test_departure(self.car, self.now, mocks.controller.duration_for_temperature)

    @mocks.sync_test
    async def test_measured_temperature_threshold_and_unavailable(self):
        for state, expected in [("10", self.first), ("10.01", None), ("-15", self.first), ("unavailable", None)]:
            self.hass.states["sensor.outside"].state = state
            self.assertEqual(await self.departure(), expected, state)
        self.assertFalse(self.hass.calls)

    @mocks.sync_test
    async def test_configured_forecast_preferred_at_departure_and_fallback_outside_coverage(self):
        self.use_forecast([(self.first, 13)])
        self.assertIsNone(await self.departure())
        self.hass.states["sensor.outside"].state = "15"
        self.use_forecast([(self.first, -5)])
        self.assertEqual(await self.departure(), self.first)
        self.hass.states["sensor.outside"].state = "2"
        self.use_forecast([(self.second, 13)])
        self.assertEqual(await self.departure(), self.first)
        self.hass.states["sensor.outside"].state = "unavailable"
        self.assertIsNone(await self.departure())

    @mocks.sync_test
    async def test_earliest_eligible_local_weekly_calendar_or_manual_departure(self):
        self.car.local_departures = [{"departure": self.second, "uid": "school"}]
        self.car._calendar_ok = True
        earlier = self.first - timedelta(minutes=45)
        self.car._calendar_events = [(earlier, "Kalender")]
        self.assertEqual(await self.departure(), earlier)
        self.car._calendar_ok = False  # cached calendar data is unverified
        self.assertEqual(await self.departure(), self.first)
        self.car._skipped_departures.add(self.first.isoformat())
        self.assertEqual(await self.departure(), self.second)
        self.car._suppressed.add(f"Planerad|{self.second.isoformat()}")
        self.assertIsNone(await self.departure())
        self.car.weekly_enabled[1] = True  # Tuesday, 08:15 local
        self.car.weekly_times[1] = datetime.fromisoformat("2026-11-03T08:15:00").time()
        self.assertEqual(await self.departure(), self.first + timedelta(minutes=75))

    @mocks.sync_test
    async def test_tomorrow_is_local_date_not_utc_date(self):
        # Tuesday 00:30 in Stockholm is Monday 23:30 UTC.
        self.car.manual_departure = self.now.replace(hour=23, minute=30)
        self.assertEqual(await self.departure(), self.car.manual_departure)
        self.car.manual_departure = self.now.replace(hour=22, minute=50)
        self.assertIsNone(await self.departure())
        self.car.manual_departure = self.second + timedelta(days=1)
        self.assertIsNone(await self.departure())

    @mocks.sync_test
    async def test_forecast_must_not_trigger_yesterdays_check_after_local_midnight(self):
        self.now = self.now.replace(hour=22, minute=59, second=58)
        with patch.object(schedule.dt_util, "utcnow", return_value=self.now + timedelta(seconds=4)):
            self.assertIsNone(await self.departure())

    @mocks.sync_test
    async def test_paused_or_active_car_is_not_probed(self):
        self.car.automation_paused = True
        self.assertIsNone(await self.departure())
        self.car.automation_paused = False
        self.car.owned = True
        self.assertIsNone(await self.departure())

    @mocks.sync_test
    async def test_ordinary_heating_due_within_pulse_takes_priority(self):
        self.car.local_departures = [{"departure":self.now + timedelta(hours=1, seconds=5), "uid":"today"}]
        self.assertIsNone(await self.departure())
        self.car.local_departures[0]["departure"] += timedelta(minutes=3)
        self.assertEqual(await self.departure(), self.first)

    @mocks.sync_test
    async def test_no_forecast_fetch_for_an_empty_tomorrow(self):
        self.car.manual_departure = None
        self.car.config["weather_entity"] = "weather.car"
        self.hass.states["weather.car"] = SimpleNamespace(state="cloudy", attributes={"temperature_unit":"°C"})
        self.assertIsNone(await self.departure())
        self.assertFalse(self.hass.calls)
