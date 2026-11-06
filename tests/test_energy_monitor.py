"""Tests for optional energy monitoring and low-power alerts."""

import asyncio
from datetime import datetime, timedelta, timezone
import sys
import types
import unittest

import test_controller as mocks

from test_motorvarmare.energy import EnergyMonitor, _ENERGY_UNITS, _POWER_UNITS, _read_number


def state(value, unit, state_class=None):
    result = mocks.State(value, unit)
    if state_class:
        result.attributes["state_class"] = state_class
    return result


class EnergyMonitorTests(unittest.TestCase):
    def setUp(self):
        self.previous_wait_for = asyncio.wait_for
        asyncio.wait_for = mocks.immediate_wait_for
        self.previous_now = mocks.dt.utcnow
        self.now = datetime(2026, 11, 2, 5, 0, tzinfo=timezone.utc)
        mocks.dt.utcnow = lambda: self.now
        self.hass = mocks.Hass()
        self.hass.config = types.SimpleNamespace(language="sv")
        self.hass.states["sensor.power"] = state("0", "W")
        self.hass.states["sensor.energy"] = state("1000", "Wh", "total_increasing")
        self.config = {"switch_entity": "switch.heater", "power_entity": "sensor.power",
                       "energy_entity": "sensor.energy", "power_min_watts": 10,
                       "power_delay_minutes": 5, "notify_entity": "notify.phone"}
        self.entry = types.SimpleNamespace(entry_id="car1", title="Bil 1")
        self.monitor = EnergyMonitor(self.hass, self.entry, self.config, lambda: None)
        self.monitor._saw_off = True  # observed off before the session

    def tearDown(self):
        asyncio.wait_for = self.previous_wait_for
        mocks.dt.utcnow = self.previous_now

    def advance(self, minutes):
        self.now += timedelta(minutes=minutes)

    async def switch(self, value):
        self.hass.states["switch.heater"].state = value
        await self.monitor.async_update()

    @mocks.sync_test
    async def test_power_alarm_waits_and_sends_once_per_real_on_session(self):
        await self.switch("on")
        self.assertEqual(self.monitor.monitor_status, "low_power")
        self.assertFalse(self.monitor.alarm_active)
        self.advance(4)
        await self.monitor.async_update()
        self.assertEqual(self.hass.calls, [])
        self.advance(1)
        await self.monitor.async_update()
        self.assertTrue(self.monitor.alarm_active)
        self.assertEqual(self.hass.calls, [("persistent_notification", "create"), ("notify", "send_message")])
        await self.monitor.async_update()
        self.hass.states["sensor.power"].state = "500"
        await self.monitor.async_update()
        self.assertFalse(self.monitor.alarm_active)
        self.hass.states["sensor.power"].state = "0"
        await self.monitor.async_update()
        self.advance(6)
        await self.monitor.async_update()
        self.assertEqual(len(self.hass.calls), 2)  # no duplicate in same run
        await self.switch("off")
        self.assertFalse(self.monitor.alarm_active)
        await self.switch("on")
        self.advance(5)
        await self.monitor.async_update()
        self.assertEqual(len(self.hass.calls), 4)

    @mocks.sync_test
    async def test_sensor_outage_resets_delay_and_does_not_imply_zero(self):
        await self.switch("on")
        self.advance(4)
        self.hass.states["sensor.power"].state = "unavailable"
        await self.monitor.async_update()
        self.assertIsNone(self.monitor.power_w)
        self.assertEqual(self.monitor.monitor_status, "power_unavailable")
        self.assertFalse(self.monitor.alarm_active)
        self.hass.states["sensor.power"].state = "0"
        await self.monitor.async_update()
        self.advance(4)
        await self.monitor.async_update()
        self.assertFalse(self.monitor.alarm_active)
        self.advance(1)
        await self.monitor.async_update()
        self.assertTrue(self.monitor.alarm_active)

    @mocks.sync_test
    async def test_energy_delta_and_freeze_on_off(self):
        await self.switch("on")
        self.assertEqual(self.monitor.energy_session_status, "measuring")
        self.hass.states["sensor.energy"] = state("1.3", "kWh", "total")
        await self.monitor.async_update()
        self.assertAlmostEqual(self.monitor.session_energy_kwh, 0.3)
        self.hass.states["sensor.energy"].state = "1.4"
        await self.switch("off")
        self.assertEqual(self.monitor.energy_session_status, "complete")
        self.assertAlmostEqual(self.monitor.session_energy_kwh, 0.4)
        self.hass.states["sensor.energy"].state = "1.9"
        await self.monitor.async_update()
        self.assertAlmostEqual(self.monitor.session_energy_kwh, 0.4)

    @mocks.sync_test
    async def test_energy_reset_or_missing_sample_marks_session_incomplete(self):
        await self.switch("on")
        self.hass.states["sensor.energy"].state = "1100"
        await self.monitor.async_update()
        self.hass.states["sensor.energy"].state = "2"
        await self.monitor.async_update()
        self.assertEqual(self.monitor.energy_session_status, "incomplete")
        self.assertIsNone(self.monitor.session_energy_kwh)
        await self.switch("off")
        await self.switch("on")
        self.hass.states["sensor.energy"].state = "unavailable"
        await self.monitor.async_update()
        self.assertFalse(self.monitor.energy_sensor_available)
        self.hass.states["sensor.energy"].state = "3"
        await self.monitor.async_update()
        self.assertIsNone(self.monitor.session_energy_kwh)
        self.assertEqual(self.monitor.energy_session_status, "incomplete")

    @mocks.sync_test
    async def test_starting_without_baseline_or_already_on_is_not_complete(self):
        self.hass.states["sensor.energy"].state = "unknown"
        await self.switch("on")
        self.hass.states["sensor.energy"].state = "1100"
        await self.monitor.async_update()
        self.assertIsNone(self.monitor.session_energy_kwh)
        self.assertEqual(self.monitor.energy_session_status, "incomplete")
        fresh = EnergyMonitor(self.hass, self.entry, self.config, lambda: None)
        await fresh.async_update()  # initially observed on; start is unknown
        self.assertIsNone(fresh.session_energy_kwh)
        self.assertEqual(fresh.energy_session_status, "incomplete")

    @mocks.sync_test
    async def test_unavailable_switch_invalidates_energy_session_and_resets_alarm_delay(self):
        await self.switch("on")
        self.advance(4)
        await self.switch("unavailable")
        self.assertFalse(self.monitor.alarm_active)
        self.assertEqual(self.monitor.energy_session_status, "incomplete")
        await self.switch("on")
        self.advance(1)
        await self.monitor.async_update()
        self.assertFalse(self.monitor.alarm_active)
        await self.switch("off")
        self.assertEqual(self.monitor.energy_session_status, "incomplete")
        self.assertIsNone(self.monitor.session_energy_kwh)

    @mocks.sync_test
    async def test_restart_does_not_repeat_alert_or_count_unobserved_low_time(self):
        await self.switch("on")
        self.advance(5)
        await self.monitor.async_update()
        self.assertEqual(len(self.hass.calls), 2)
        restored = EnergyMonitor(self.hass, self.entry, self.config, lambda: None)
        await restored.async_load()
        self.assertIsNone(restored.session_energy_kwh)
        self.assertEqual(restored.energy_session_status, "incomplete")
        self.advance(60)
        await restored.async_update()
        self.assertFalse(restored.alarm_active)
        self.advance(5)
        await restored.async_update()
        self.assertTrue(restored.alarm_active)
        self.assertEqual(len(self.hass.calls), 2)

    @mocks.sync_test
    async def test_one_notification_failure_does_not_block_the_other(self):
        self.hass.fail.add(("persistent_notification", "create"))
        await self.switch("on")
        self.advance(5)
        await self.monitor.async_update()
        self.assertIn(("notify", "send_message"), self.hass.calls)
        self.assertTrue(self.monitor.alarm_active)

    @mocks.sync_test
    async def test_monitor_error_does_not_block_scheduled_heater_start_or_stop(self):
        controller = mocks.new_controller(self.hass)
        controller.config["power_entity"] = "sensor.power"
        controller.manual_departure = self.now + timedelta(minutes=20)
        async def broken_monitor():
            raise RuntimeError("sensor monitoring failed")
        controller.energy.async_update = broken_monitor
        await controller.async_update()
        self.assertEqual(self.hass.states["switch.heater"].state, "on")
        self.advance(21)
        await controller.async_update()
        self.assertEqual(self.hass.states["switch.heater"].state, "off")

    @mocks.sync_test
    async def test_alarm_can_be_disabled_without_disabling_readings(self):
        self.config["power_alarm_enabled"] = False
        await self.switch("on")
        self.advance(10)
        await self.monitor.async_update()
        self.assertFalse(self.monitor.alarm_active)
        self.assertEqual(self.monitor.power_w, 0)
        self.assertEqual(self.monitor.energy_session_status, "measuring")
        self.assertEqual(self.hass.calls, [])

    @mocks.sync_test
    async def test_fast_events_preserve_energy_and_low_power_interruptions(self):
        event_api = sys.modules["homeassistant.helpers.event"]
        previous = getattr(event_api, "async_track_state_change_event", None)
        queued = []
        self.hass.async_create_task = queued.append
        def track(hass, entities, callback):
            self.assertEqual(set(entities), {"switch.heater", "sensor.energy", "sensor.power"})
            self.listener = callback
            return lambda: None
        event_api.async_track_state_change_event = track
        try:
            await self.monitor.async_start()
            while queued:
                await queued.pop(0)
            def emit(entity, new_state):
                self.hass.states[entity] = new_state
                self.listener(types.SimpleNamespace(data={"entity_id": entity, "new_state": new_state}))

            emit("switch.heater", state("on", None))
            emit("sensor.energy", state("1500", "Wh", "total_increasing"))
            emit("switch.heater", state("off", None))
            while queued:
                await queued.pop(0)
            self.assertEqual(self.monitor.energy_session_status, "complete")
            self.assertAlmostEqual(self.monitor.session_energy_kwh, 0.5)

            emit("switch.heater", state("on", None))
            while queued:
                await queued.pop(0)
            self.advance(4)
            emit("sensor.power", state("1000", "W"))
            emit("sensor.power", state("0", "W"))
            while queued:
                await queued.pop(0)
            self.advance(1)
            await self.monitor.async_update()
            self.assertFalse(self.monitor.alarm_active)
            self.assertEqual(self.hass.calls, [])

            # A short reset between two queued energy events is not lost.
            emit("sensor.energy", state("10", "Wh", "total_increasing"))
            emit("sensor.energy", state("1600", "Wh", "total_increasing"))
            while queued:
                await queued.pop(0)
            self.assertEqual(self.monitor.energy_session_status, "incomplete")
            self.assertIsNone(self.monitor.session_energy_kwh)

            # Events queued before unloading cannot send a stale alert later.
            self.advance(10)
            emit("sensor.power", state("0", "W"))
            await self.monitor.async_shutdown()
            while queued:
                await queued.pop(0)
            self.assertFalse(self.monitor.alarm_active)
            self.assertEqual(self.hass.calls, [])
        finally:
            if previous is None:
                del event_api.async_track_state_change_event
            else:
                event_api.async_track_state_change_event = previous

    def test_units_and_unknown_values(self):
        self.assertEqual(_read_number(state("1.5", "kW"), _POWER_UNITS), 1500)
        self.assertEqual(_read_number(state("250", "Wh", "total_increasing"), _ENERGY_UNITS, cumulative=True), 0.25)
        for sample in (state("unavailable", "W"), state("nan", "W"), state("-5", "W"), state("2", "A")):
            self.assertIsNone(_read_number(sample, _POWER_UNITS))
        self.assertIsNone(_read_number(state("2", "kWh"), _ENERGY_UNITS, cumulative=True))


if __name__ == "__main__":
    unittest.main()
