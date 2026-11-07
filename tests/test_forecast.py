"""Forecast estimates are read-only and must fall back safely."""
from datetime import datetime, timezone
import asyncio
import importlib
import types
import unittest
from unittest.mock import patch

import test_controller as mocks
import test_schedule_websocket as websocket_mocks

forecast = importlib.import_module("test_motorvarmare.forecast")


class ForecastTests(unittest.TestCase):
    def setUp(self):
        self.old_wait = asyncio.wait_for
        asyncio.wait_for = mocks.immediate_wait_for
        self.hass = mocks.Hass()
        self.hass.states["weather.home"] = types.SimpleNamespace(
            state="cloudy", attributes={"temperature_unit": "°C"})
        self.now = datetime.fromisoformat("2026-11-02T20:00:00+00:00")
        self.events = {"calendar_error": False, "events": [{
            "departure": "2026-11-03T00:30:00+01:00", "start": "2026-11-02T22:30:00+00:00",
            "end": "2026-11-02T23:30:00+00:00", "duration_minutes": 60,
        }]}
        self.response = {"weather.home": {"forecast": [
            {"datetime": "2026-11-02T23:00:00+00:00", "temperature": -5},
            {"datetime": "2026-11-03T00:00:00Z", "temperature": -10},
        ]}}
        self.calls = []
        self.hass.services = types.SimpleNamespace(async_call=self.call)

    async def call(self, domain, action, data, **kwargs):
        self.calls.append((domain, action, data, kwargs))
        return self.response

    async def project(self, weather="weather.home", **kwargs):
        return await forecast.async_project_forecasts(self.hass, weather, self.events,
            mocks.controller.duration_for_temperature, now=self.now, **kwargs)

    def tearDown(self):
        asyncio.wait_for = self.old_wait

    @mocks.sync_test
    async def test_hourly_forecast_and_cross_midnight_utc(self):
        result = await self.project()
        event = result["events"][0]
        self.assertEqual(event["temperature_source"], "forecast")
        self.assertEqual(event["forecast_temperature"], -5)
        self.assertEqual(event["duration_minutes"], 90)
        self.assertEqual(event["start"], "2026-11-02T22:00:00+00:00")
        self.assertEqual(self.events["events"][0]["duration_minutes"], 60)
        self.assertEqual(self.calls[0][:3], ("weather", "get_forecasts", {"entity_id": "weather.home", "type": "hourly"}))

    @mocks.sync_test
    async def test_fahrenheit_and_rounding_are_consistent(self):
        self.hass.states["weather.home"].attributes["temperature_unit"] = "°F"
        self.response["weather.home"]["forecast"][0]["temperature"] = 22.82  # -5.1 C
        event = (await self.project())["events"][0]
        self.assertEqual(event["forecast_temperature"], -5.1)
        self.assertEqual(event["duration_minutes"], 91)

    @mocks.sync_test
    async def test_ambiguous_autumn_clock_times_are_distinct_instants(self):
        self.now = datetime.fromisoformat("2026-10-24T20:00:00+00:00")
        self.events["events"] = [
            {"departure": "2026-10-25T02:30:00+02:00", "duration_minutes": 60},
            {"departure": "2026-10-25T02:30:00+01:00", "duration_minutes": 60},
        ]
        self.response["weather.home"]["forecast"] = [
            {"datetime": "2026-10-25T00:30:00+00:00", "temperature": -5},
            {"datetime": "2026-10-25T01:30:00+00:00", "temperature": -10},
        ]
        events = (await self.project())["events"]
        self.assertEqual([e["duration_minutes"] for e in events], [90, 120])
        self.assertEqual([e["start"] for e in events],
                         ["2026-10-24T23:00:00+00:00", "2026-10-24T23:30:00+00:00"])

    @mocks.sync_test
    async def test_missing_unavailable_or_unauthorized_forecast_falls_back_without_fetch(self):
        event = (await self.project(weather=None))["events"][0]
        self.assertEqual(event["temperature_source"], "current")
        self.assertEqual(event["duration_minutes"], 60)

        self.assertFalse(self.calls)
        self.hass.states["weather.home"].state = "unavailable"
        event = (await self.project())["events"][0]
        self.assertEqual(event["temperature_source"], "current")
        self.assertFalse(self.calls)

    @mocks.sync_test
    async def test_forecast_unavailable_outside_coverage_or_missing_units(self):
        self.events["events"][0]["departure"] = "2026-11-03T04:00:00+00:00"
        event = (await self.project())["events"][0]
        self.assertEqual(event["temperature_source"], "current")
        self.hass.states["weather.home"].attributes.clear()
        self.calls.clear()
        event = (await self.project())["events"][0]
        self.assertEqual(event["temperature_source"], "current")
        self.assertFalse(self.calls)

    @mocks.sync_test
    async def test_invalid_data_is_ignored_and_temperature_block_does_not_make_start(self):
        self.response["weather.home"]["forecast"].extend([
            {"datetime": "nope", "temperature": -12},
            {"datetime": "2026-11-02T23:30:00Z", "temperature": "nan"},
            {"datetime": "2026-11-02T23:30:00", "temperature": -20},
        ])
        event = (await self.project(blocked=True))["events"][0]
        self.assertEqual(event["temperature_source"], "forecast")
        self.assertEqual(event["duration_minutes"], 90)
        self.assertIsNone(event["start"])

    @mocks.sync_test
    async def test_boundary_candidate_retained_only_if_heating_crosses_end(self):
        end = datetime.fromisoformat("2026-11-02T23:00:00+00:00")
        event = (await self.project(end=end))["events"][0]
        self.assertLess(datetime.fromisoformat(event["start"]), end)
        self.response["weather.home"]["forecast"][0]["temperature"] = 11
        result = await self.project(end=end)
        self.assertEqual(result["events"], [])

    @mocks.sync_test
    async def test_action_failure_keeps_current_estimate(self):
        async def failing(*args, **kwargs):
            raise RuntimeError("unavailable")
        self.hass.services.async_call = failing
        event = (await self.project())["events"][0]
        self.assertEqual(event["temperature_source"], "current")
        self.assertEqual(event["duration_minutes"], 60)

    @mocks.sync_test
    async def test_valid_forecast_cached_for_fifteen_minutes_without_bypassing_permissions(self):
        self.hass.data = {}
        with patch.object(forecast.monotonic_time, "monotonic", return_value=100):
            self.assertEqual((await self.project())["events"][0]["temperature_source"], "forecast")
            self.assertEqual((await self.project())["events"][0]["temperature_source"], "forecast")
            self.assertEqual((await self.project(weather=None))["events"][0]["temperature_source"], "current")
            self.assertEqual(len(self.calls), 1)
        with patch.object(forecast.monotonic_time, "monotonic", return_value=1001):
            self.assertEqual((await self.project())["events"][0]["temperature_source"], "forecast")
            self.assertEqual(len(self.calls), 2)

    @mocks.sync_test
    async def test_forecast_cache_separates_entities_and_home_assistant_instances(self):
        self.hass.data = {}
        other = mocks.Hass()
        other.data = {}
        other.states["weather.home"] = types.SimpleNamespace(state="cloudy", attributes={"temperature_unit": "°C"})
        other_calls = []

        async def other_call(*args, **kwargs):
            other_calls.append(args)
            return self.response

        other.services = types.SimpleNamespace(async_call=other_call)
        with patch.object(forecast.monotonic_time, "monotonic", return_value=100):
            await self.project()
            await forecast.async_project_forecasts(other, "weather.home", self.events,
                mocks.controller.duration_for_temperature, now=self.now)
            self.assertEqual(len(self.calls), 1)
            self.assertEqual(len(other_calls), 1)
            self.hass.states["weather.other"] = types.SimpleNamespace(state="cloudy", attributes={"temperature_unit": "°C"})
            self.response["weather.other"] = self.response["weather.home"]
            await self.project(weather="weather.other")
            self.assertEqual(len(self.calls), 2)

    @mocks.sync_test
    async def test_failed_forecast_is_not_cached(self):
        self.hass.data = {}
        self.response = {"weather.home": {"forecast": []}}
        with patch.object(forecast.monotonic_time, "monotonic", return_value=100):
            await self.project()
            await self.project()
        self.assertEqual(len(self.calls), 2)


class ForecastPermissionTests(unittest.TestCase):
    def setUp(self):
        self.base = websocket_mocks.ScheduleWebSocketTests("test_requires_sensor_and_local_calendar_permission")
        self.base.setUp()
        self.base.controller.config["weather_entity"] = "weather.private"
        self.base.hass.states["weather.private"] = types.SimpleNamespace(
            state="cloudy", attributes={"temperature_unit": "°C"})
        self.weather_calls = []
        original_call = self.base.hass.async_call

        async def call(domain, action, data, **kwargs):
            if domain != "weather":
                return await original_call(domain, action, data, **kwargs)
            self.weather_calls.append((domain, action))
            return {"weather.private": {"forecast": [
                {"datetime": "2026-11-03T07:00:00+00:00", "temperature": -5},
                {"datetime": "2026-11-03T08:00:00+00:00", "temperature": -5},
            ]}}
        self.base.hass.services = types.SimpleNamespace(async_call=call)
        original_projection = self.base.api.async_project_forecasts

        async def project(*args, **kwargs):
            return await original_projection(*args, now=datetime(2026, 11, 2, 5, tzinfo=timezone.utc), **kwargs)
        self.projection = patch.object(self.base.api, "async_project_forecasts", project)
        self.projection.start()

    def tearDown(self):
        self.projection.stop()
        self.base.tearDown()

    @mocks.sync_test
    async def test_private_weather_is_never_queried_or_revealed_without_permission(self):
        allowed = {"sensor.car_status", "calendar.car_local", "calendar.private"}
        connection = websocket_mocks.Connection(allowed)
        await self.base.api.websocket_get_schedule(self.base.hass, connection, self.base.message)
        self.assertEqual(self.weather_calls, [])
        self.assertEqual(connection.result["events"][0]["temperature_source"], "current")
        self.assertNotIn("forecast_temperature", connection.result["events"][0])
        connection = websocket_mocks.Connection(allowed | {"weather.private"})
        await self.base.api.websocket_get_schedule(self.base.hass, connection, self.base.message)
        self.assertEqual(self.weather_calls, [("weather", "get_forecasts")])
        self.assertEqual(connection.result["events"][0]["temperature_source"], "forecast")
        self.assertEqual(connection.result["events"][0]["forecast_temperature"], -5)


if __name__ == "__main__":
    unittest.main()
