"""Regression tests for recorded heating sessions."""

from datetime import datetime, timedelta, timezone
import asyncio
import sys
import types
import unittest

import test_controller as mocks
from test_motorvarmare.energy import EnergyMonitor


class HeatingHistoryTests(unittest.TestCase):
    def setUp(self):
        self.old_now = mocks.dt.utcnow
        self.now = datetime(2026, 11, 2, 5, tzinfo=timezone.utc)
        mocks.dt.utcnow = lambda: self.now
        self.hass = mocks.Hass()
        self.entry = types.SimpleNamespace(entry_id="history", title="Bil")
        self.config = {"switch_entity": "switch.heater"}
        self.monitor = EnergyMonitor(self.hass, self.entry, self.config, lambda: None)

    def tearDown(self):
        mocks.dt.utcnow = self.old_now

    def advance(self, minutes):
        self.now += timedelta(minutes=minutes)

    async def state(self, value):
        self.hass.states["switch.heater"] = mocks.State(value)
        await self.monitor.async_update()

    @mocks.sync_test
    async def test_history_without_power_or_energy_sensor(self):
        await self.state("off")
        await self.state("on")
        self.advance(30)
        await self.state("off")
        self.assertEqual(self.monitor.heating_history, [{
            "start": "2026-11-02T05:00:00+00:00",
            "end": "2026-11-02T05:30:00+00:00",
            "duration_minutes": 30.0, "energy_kwh": None, "complete": True,
        }])
        restored = EnergyMonitor(self.hass, self.entry, self.config, lambda: None)
        await restored.async_load()
        self.assertEqual(restored.heating_history, self.monitor.heating_history)
        await restored.async_update()
        self.assertEqual(len(restored.heating_history), 1)

    @mocks.sync_test
    async def test_energy_and_sensor_reset_are_distinct_from_time_completeness(self):
        self.config["energy_entity"] = "sensor.energy"
        meter = mocks.State("1000", "Wh")
        meter.attributes["state_class"] = "total_increasing"
        self.hass.states["sensor.energy"] = meter
        await self.state("off")
        await self.state("on")
        meter.state = "1400"
        self.advance(30)
        await self.state("off")
        self.assertEqual(self.monitor.heating_history[0]["energy_kwh"], 0.4)
        await self.state("on")
        meter.state = "10"
        self.advance(10)
        await self.monitor.async_update()
        await self.state("off")
        self.assertIsNone(self.monitor.heating_history[0]["energy_kwh"])
        self.assertTrue(self.monitor.heating_history[0]["complete"])
        self.assertEqual(self.monitor.heating_history[0]["duration_minutes"], 10.0)

    @mocks.sync_test
    async def test_unknown_switch_and_restart_do_not_invent_times(self):
        await self.state("off")
        await self.state("on")
        self.advance(5)
        await self.state("unavailable")
        self.advance(10)
        await self.state("on")
        self.advance(5)
        await self.state("off")
        item = self.monitor.heating_history[0]
        self.assertFalse(item["complete"])
        self.assertIsNone(item["duration_minutes"])
        self.assertIsNotNone(item["start"])
        self.assertIsNotNone(item["end"])

        await self.state("on")
        restored = EnergyMonitor(self.hass, self.entry, self.config, lambda: None)
        await restored.async_load()
        self.advance(10)
        # First observation after restart is off: exact switch-off is unknown.
        self.hass.states["switch.heater"] = mocks.State("off")
        await restored.async_update()
        self.assertEqual(len(restored.heating_history), 2)
        self.assertFalse(restored.heating_history[0]["complete"])
        self.assertIsNone(restored.heating_history[0]["end"])

    @mocks.sync_test
    async def test_already_on_at_setup_and_unknown_to_off(self):
        await self.state("on")
        self.advance(15)
        await self.state("off")
        self.assertIsNone(self.monitor.heating_history[0]["start"])
        self.assertFalse(self.monitor.heating_history[0]["complete"])
        await self.state("on")
        await self.state("unknown")
        self.advance(5)
        await self.state("off")
        self.assertIsNone(self.monitor.heating_history[0]["end"])
        self.assertIsNone(self.monitor.heating_history[0]["duration_minutes"])

    @mocks.sync_test
    async def test_switch_change_keeps_old_history_without_old_active_session(self):
        await self.state("off")
        await self.state("on")
        self.advance(1)
        await self.state("off")
        await self.state("on")
        new = EnergyMonitor(self.hass, self.entry, {"switch_entity": "switch.new"}, lambda: None)
        await new.async_load()
        self.assertEqual(len(new.heating_history), 2)
        self.assertFalse(new.heating_history[0]["complete"])
        self.assertIsNone(new.heating_history[0]["end"])
        self.assertFalse(new._session_active)
        again = EnergyMonitor(self.hass, self.entry, {"switch_entity": "switch.new"}, lambda: None)
        await again.async_load()
        self.assertEqual(len(again.heating_history), 2)

    @mocks.sync_test
    async def test_switch_unavailable_before_start_does_not_invent_start(self):
        await self.state("off")
        await self.state("unavailable")
        self.advance(10)
        await self.state("on")
        self.advance(5)
        await self.state("off")
        self.assertIsNone(self.monitor.heating_history[0]["start"])
        self.assertFalse(self.monitor.heating_history[0]["complete"])

    @mocks.sync_test
    async def test_history_is_bounded_and_newest_first(self):
        await self.state("off")
        for _ in range(105):
            await self.state("on")
            self.advance(1)
            await self.state("off")
        items = self.monitor.heating_history
        self.assertEqual(len(items), 100)
        self.assertGreater(items[0]["start"], items[-1]["start"])
        restored = EnergyMonitor(self.hass, self.entry, self.config, lambda: None)
        await restored.async_load()
        self.assertEqual(restored.heating_history, items)

    @mocks.sync_test
    async def test_duration_uses_real_elapsed_time_across_fall_clock_change(self):
        await self.state("off")
        switch = mocks.State("on")
        switch.last_changed = datetime(2026, 10, 25, 2, 50, tzinfo=timezone(timedelta(hours=2)))
        self.hass.states["switch.heater"] = switch
        await self.monitor.async_update()
        switch = mocks.State("off")
        switch.last_changed = datetime(2026, 10, 25, 2, 10, tzinfo=timezone(timedelta(hours=1)))
        self.hass.states["switch.heater"] = switch
        await self.monitor.async_update()
        self.assertTrue(self.monitor.heating_history[0]["complete"])
        self.assertEqual(self.monitor.heating_history[0]["duration_minutes"], 20.0)

    @mocks.sync_test
    async def test_queued_events_capture_observation_time_without_sensor(self):
        api = sys.modules["homeassistant.helpers.event"]
        previous = getattr(api, "async_track_state_change_event", None)
        tasks = []
        self.hass.async_create_task = tasks.append
        def track(hass, entities, listener):
            self.assertEqual(entities, ["switch.heater"])
            self.listener = listener
            return lambda: None
        api.async_track_state_change_event = track
        try:
            await self.monitor.async_start()
            while tasks:
                await tasks.pop(0)
            def emit(value):
                new = mocks.State(value)
                self.hass.states["switch.heater"] = new
                self.listener(types.SimpleNamespace(data={"entity_id": "switch.heater", "new_state": new}))
            emit("on")
            self.advance(5)
            emit("off")
            self.advance(10)
            while tasks:
                await tasks.pop(0)
            self.assertEqual(self.monitor.heating_history[0]["duration_minutes"], 5.0)
        finally:
            if previous is None:
                del api.async_track_state_change_event
            else:
                api.async_track_state_change_event = previous


class HeatingHistoryShutdownTests(unittest.TestCase):
    @mocks.sync_test
    async def test_unload_drains_already_observed_switch_events(self):
        old_now = mocks.dt.utcnow
        current = [datetime(2026, 11, 2, 5, tzinfo=timezone.utc)]
        mocks.dt.utcnow = lambda: current[0]
        api = sys.modules["homeassistant.helpers.event"]
        previous = getattr(api, "async_track_state_change_event", None)
        listener = []
        def track(hass, entities, callback):
            listener.append(callback)
            return lambda: None
        api.async_track_state_change_event = track
        hass = mocks.Hass()
        tasks = []
        class FakeTask:
            def __init__(self, coroutine):
                self.coroutine = coroutine
                self.callback = None
            def add_done_callback(self, callback):
                self.callback = callback
            def __await__(self):
                async def run():
                    try:
                        return await self.coroutine
                    finally:
                        if self.callback:
                            self.callback(self)
                return run().__await__()
        def create_task(coroutine):
            task = FakeTask(coroutine)
            tasks.append(task)
            return task
        async def gather(*pending, return_exceptions=False):
            return [await task for task in pending]
        old_gather = asyncio.gather
        asyncio.gather = gather
        hass.async_create_task = create_task
        entry = types.SimpleNamespace(entry_id="history-drain", title="Bil")
        monitor = EnergyMonitor(hass, entry, {"switch_entity": "switch.heater"}, lambda: None)
        try:
            await monitor.async_start()
            await tasks.pop(0)  # initial off observation
            def emit(value):
                switch = mocks.State(value)
                hass.states["switch.heater"] = switch
                listener[0](types.SimpleNamespace(data={"entity_id": "switch.heater", "new_state": switch}))
            emit("on")
            current[0] += timedelta(minutes=5)
            emit("off")
            await monitor.async_shutdown()
            self.assertEqual(len(monitor.heating_history), 1)
            self.assertEqual(monitor.heating_history[0]["duration_minutes"], 5.0)
            self.assertTrue(monitor.heating_history[0]["complete"])
            self.assertEqual(hass.calls, [])
        finally:
            mocks.dt.utcnow = old_now
            asyncio.gather = old_gather
            if previous is None:
                del api.async_track_state_change_event
            else:
                api.async_track_state_change_event = previous
