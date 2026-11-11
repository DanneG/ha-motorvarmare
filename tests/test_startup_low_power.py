"""Low-power alerts are limited to an observed heater startup."""

import asyncio
from datetime import datetime, timedelta, timezone
import sys
import types
import unittest

import test_controller as mocks
from test_motorvarmare.energy import EnergyMonitor


class StartupLowPowerTests(unittest.TestCase):
    def setUp(self):
        self.old_now = mocks.dt.utcnow
        self.old_wait_for = asyncio.wait_for
        self.now = datetime(2026, 11, 11, 6, 0, tzinfo=timezone.utc)
        mocks.dt.utcnow = lambda: self.now
        asyncio.wait_for = mocks.immediate_wait_for
        self.hass = mocks.Hass()
        self.hass.config = types.SimpleNamespace(language="sv")
        self.hass.states["sensor.power"] = mocks.State("0", "W")
        self.config = {"switch_entity": "switch.heater", "power_entity": "sensor.power",
                       "power_min_watts": 10, "power_delay_minutes": 5}
        self.entry = types.SimpleNamespace(entry_id="car1", title="Bil")
        self.monitor = EnergyMonitor(self.hass, self.entry, self.config, lambda: None)
        self.monitor._saw_off = True

    def tearDown(self):
        mocks.dt.utcnow = self.old_now
        asyncio.wait_for = self.old_wait_for

    def advance(self, minutes):
        self.now += timedelta(minutes=minutes)

    async def switch(self, value):
        self.hass.states["switch.heater"].state = value
        await self.monitor.async_update()

    async def power(self, value):
        self.hass.states["sensor.power"].state = str(value)
        await self.monitor.async_update()

    @mocks.sync_test
    async def test_zero_at_start_alerts_after_five_minutes(self):
        # A sensor reporting only changes may still have its 0 W observation
        # from before switch-on; this must not suppress the unplugged warning.
        self.hass.states["sensor.power"].last_reported = self.now - timedelta(hours=1)
        await self.switch("on")
        self.advance(4)
        await self.monitor.async_update()
        self.assertEqual(self.hass.calls, [])
        self.advance(1)
        await self.monitor.async_update()
        self.assertEqual(self.hass.calls, [("persistent_notification", "create")])

    @mocks.sync_test
    async def test_early_departure_is_silent_and_new_run_rearms(self):
        await self.switch("on")
        self.advance(1)
        await self.power(500)
        self.advance(1)
        await self.power(0)
        self.advance(15)
        await self.monitor.async_update()
        self.assertFalse(self.monitor.alarm_active)
        self.assertEqual(self.hass.calls, [])
        await self.switch("off")
        await self.switch("on")
        self.advance(5)
        await self.monitor.async_update()
        self.assertEqual(self.hass.calls, [("persistent_notification", "create")])

    @mocks.sync_test
    async def test_low_limits_are_independent_and_high_alert_remains_enabled(self):
        self.config.update({"power_deviation_enabled": True, "power_expected_min_watts": 400,
                            "power_expected_max_watts": 1500, "power_deviation_delay_minutes": 5})
        self.hass.states["sensor.power"].state = "100"
        await self.switch("on")
        self.advance(5)
        await self.monitor.async_update()
        self.assertFalse(self.monitor.alarm_active)  # 100 W exceeds cable threshold
        self.assertEqual(self.monitor.deviation_direction, "low")  # but not 400 W
        self.assertEqual(len(self.hass.calls), 1)
        await self.power(1800)
        self.advance(5)
        await self.monitor.async_update()
        self.assertEqual(self.monitor.deviation_direction, "high")
        self.assertEqual(len(self.hass.calls), 2)
        await self.power(0)
        self.advance(10)
        await self.monitor.async_update()
        self.assertIsNone(self.monitor.deviation_direction)
        self.assertEqual(len(self.hass.calls), 2)

    @mocks.sync_test
    async def test_unavailable_sensor_does_not_extend_start_window(self):
        await self.switch("on")
        self.advance(4)
        await self.power("unavailable")
        self.advance(2)
        await self.power(0)
        self.advance(5)
        await self.monitor.async_update()
        self.assertFalse(self.monitor.alarm_active)
        self.assertEqual(self.hass.calls, [])

    @mocks.sync_test
    async def test_sensor_recovery_at_grace_boundary_allows_full_low_delay(self):
        self.hass.states["sensor.power"].state = "unavailable"
        await self.switch("on")
        self.advance(5)
        await self.power(0)
        self.advance(5)
        await self.monitor.async_update()
        self.assertTrue(self.monitor.alarm_active)
        self.assertEqual(len(self.hass.calls), 1)

    @mocks.sync_test
    async def test_first_observation_already_on_does_not_open_start_check(self):
        self.monitor._saw_off = False
        self.hass.states["switch.heater"].state = "on"
        await self.monitor.async_update()
        self.advance(5)
        await self.monitor.async_update()
        self.assertFalse(self.monitor.alarm_active)
        self.assertEqual(self.hass.calls, [])

    @mocks.sync_test
    async def test_restart_or_unknown_switch_does_not_rearm_an_active_run(self):
        await self.switch("on")
        self.advance(1)
        await self.power(500)
        await self.power("unavailable")  # energy history is now incomplete
        restored = EnergyMonitor(self.hass, self.entry, self.config, lambda: None)
        await restored.async_load()
        self.hass.states["sensor.power"].state = "0"
        await restored.async_update()
        self.advance(20)
        await restored.async_update()
        self.assertEqual(self.hass.calls, [])
        self.assertFalse(restored.alarm_active)
        self.hass.states["switch.heater"].state = "unavailable"
        await restored.async_update()
        self.hass.states["switch.heater"].state = "on"
        await restored.async_update()
        self.advance(6)
        await restored.async_update()
        self.assertEqual(self.hass.calls, [])
        self.hass.states["switch.heater"].state = "off"
        await restored.async_update()
        self.hass.states["switch.heater"].state = "on"
        await restored.async_update()
        self.advance(5)
        await restored.async_update()
        self.assertEqual(len(self.hass.calls), 1)

    @mocks.sync_test
    async def test_a_stale_high_reading_does_not_certify_start(self):
        power = self.hass.states["sensor.power"]
        power.state = "500"
        power.last_reported = self.now - timedelta(minutes=30)
        await self.switch("on")
        self.advance(1)
        power.state = "0"
        power.last_reported = self.now
        await self.monitor.async_update()
        self.advance(5)
        await self.monitor.async_update()
        self.assertTrue(self.monitor.alarm_active)
        self.assertEqual(len(self.hass.calls), 1)

    @mocks.sync_test
    async def test_near_simultaneous_power_then_switch_events_confirm_start(self):
        # A smart plug may publish power just before the on-state event.
        power = self.hass.states["sensor.power"]
        power.state = "500"
        power.last_reported = self.now - timedelta(seconds=2)
        await self.switch("on")
        self.advance(1)
        power.state = "0"
        power.last_reported = self.now
        await self.monitor.async_update()
        self.advance(5)
        await self.monitor.async_update()
        self.assertFalse(self.monitor.alarm_active)
        self.assertEqual(self.hass.calls, [])

    @mocks.sync_test
    async def test_price_event_queued_after_high_power_does_not_reset_high_alert(self):
        self.config.update({"power_deviation_enabled": True, "power_expected_max_watts": 1500,
                            "power_deviation_delay_minutes": 5, "energy_price_entity": "sensor.price",
                            "energy_currency": "SEK"})
        self.hass.states["sensor.power"].state = "1800"
        self.hass.states["sensor.price"] = mocks.State("1", "SEK/kWh")
        event_api = sys.modules["homeassistant.helpers.event"]
        previous = getattr(event_api, "async_track_state_change_event", None)
        queued = []
        self.hass.async_create_task = queued.append
        def track(hass, entities, callback):
            self.listener = callback
            return lambda: None
        event_api.async_track_state_change_event = track
        try:
            await self.monitor.async_start()
            while queued:
                await queued.pop(0)
            def emit(entity, value, unit=None):
                state = mocks.State(value, unit)
                self.hass.states[entity] = state
                self.listener(types.SimpleNamespace(data={"entity_id": entity, "new_state": state}))
            emit("switch.heater", "on")
            emit("sensor.price", "2", "SEK/kWh")
            while queued:
                await queued.pop(0)
            self.advance(5)
            await self.monitor.async_update()
            self.assertEqual(self.monitor.deviation_direction, "high")
            self.assertEqual(len(self.hass.calls), 1)
        finally:
            if previous is None:
                del event_api.async_track_state_change_event
            else:
                event_api.async_track_state_change_event = previous

    @mocks.sync_test
    async def test_queued_normal_then_zero_never_sends_delayed_warning(self):
        event_api = sys.modules["homeassistant.helpers.event"]
        previous = getattr(event_api, "async_track_state_change_event", None)
        queued = []
        self.hass.async_create_task = queued.append
        def track(hass, entities, callback):
            self.listener = callback
            return lambda: None
        event_api.async_track_state_change_event = track
        try:
            await self.monitor.async_start()
            while queued:
                await queued.pop(0)
            def emit(entity, value, unit=None):
                state = mocks.State(value, unit)
                self.hass.states[entity] = state
                self.listener(types.SimpleNamespace(data={"entity_id": entity, "new_state": state}))
            emit("switch.heater", "on")
            while queued:
                await queued.pop(0)
            self.advance(4)
            emit("sensor.power", "500", "W")
            emit("sensor.power", "0", "W")
            while queued:
                await queued.pop(0)
            self.advance(5)
            await self.monitor.async_update()
            self.assertEqual(self.hass.calls, [])
            self.assertFalse(self.monitor.alarm_active)
        finally:
            if previous is None:
                del event_api.async_track_state_change_event
            else:
                event_api.async_track_state_change_event = previous

    @mocks.sync_test
    async def test_adequate_power_during_notification_prevents_stale_mobile_message(self):
        self.config["notify_entity"] = "notify.phone"
        event_api = sys.modules["homeassistant.helpers.event"]
        previous = getattr(event_api, "async_track_state_change_event", None)
        queued = []
        self.hass.async_create_task = queued.append
        def track(hass, entities, callback):
            self.listener = callback
            return lambda: None
        event_api.async_track_state_change_event = track
        original_call = self.hass.async_call
        try:
            await self.monitor.async_start()
            while queued:
                await queued.pop(0)
            def emit(entity, value, unit=None):
                state = mocks.State(value, unit)
                self.hass.states[entity] = state
                self.listener(types.SimpleNamespace(data={"entity_id": entity, "new_state": state}))
            emit("switch.heater", "on")
            while queued:
                await queued.pop(0)
            async def changing_during_send(domain, service, data, **kwargs):
                result = await original_call(domain, service, data, **kwargs)
                if (domain, service) == ("persistent_notification", "create"):
                    emit("sensor.power", "500", "W")
                    emit("sensor.power", "0", "W")
                return result
            self.hass.async_call = changing_during_send
            self.advance(5)
            await self.monitor.async_update()
            while queued:
                await queued.pop(0)
            self.advance(6)
            await self.monitor.async_update()
            self.assertEqual(self.hass.calls, [("persistent_notification", "create")])
            self.assertFalse(self.monitor.alarm_active)
        finally:
            self.hass.async_call = original_call
            if previous is None:
                del event_api.async_track_state_change_event
            else:
                event_api.async_track_state_change_event = previous


if __name__ == "__main__":
    unittest.main()
