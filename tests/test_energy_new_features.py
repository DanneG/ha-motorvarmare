"""Behavioral tests for observed temperature, timed tariff and power alarms."""

import asyncio
from datetime import datetime, timedelta, timezone
import sys
import types
import unittest

import test_controller as mocks
from test_motorvarmare.energy import EnergyMonitor, _read_temperature_c


class NewEnergyFeaturesTests(unittest.TestCase):
    def setUp(self):
        self.old_now = mocks.dt.utcnow
        self.old_wait_for = asyncio.wait_for
        self.now = datetime(2026, 11, 2, 5, tzinfo=timezone.utc)
        mocks.dt.utcnow = lambda: self.now
        asyncio.wait_for = mocks.immediate_wait_for
        self.hass = mocks.Hass()
        self.hass.config = types.SimpleNamespace(language="sv")
        self.hass.states["sensor.power"] = mocks.State("1000", "W")
        self.hass.states["sensor.price"] = mocks.State("1", "SEK/kWh")
        self.hass.states["sensor.outside"] = mocks.State("23", "°F")
        self.entry = types.SimpleNamespace(entry_id="new", title="Bil")
        self.config = {"switch_entity": "switch.heater", "power_entity": "sensor.power",
                       "temperature_entity": "sensor.outside", "energy_currency": "SEK",
                       "energy_price_entity": "sensor.price", "energy_price": 100,
                       "power_alarm_enabled": False}
        self.monitor = EnergyMonitor(self.hass, self.entry, self.config, lambda: None)
        self.monitor._saw_off = True
        self.notifications = []

        async def call(domain, action, data, **kwargs):
            self.notifications.append((domain, action, dict(data)))
        self.hass.async_call = call

    def tearDown(self):
        mocks.dt.utcnow = self.old_now
        asyncio.wait_for = self.old_wait_for

    def advance(self, minutes):
        self.now += timedelta(minutes=minutes)

    async def switch(self, value):
        self.hass.states["switch.heater"].state = value
        await self.monitor.async_update()

    @mocks.sync_test
    async def test_dynamic_tariff_integrates_each_price_and_power_interval(self):
        await self.switch("on")
        self.advance(30)
        self.hass.states["sensor.price"] = mocks.State("3", "SEK/kWh")
        await self.monitor.async_update()
        self.advance(30)
        self.hass.states["sensor.power"] = mocks.State("0", "W")
        self.hass.states["sensor.outside"] = mocks.State("4", "°C")
        await self.switch("off")
        item = self.monitor.heating_history[0]
        self.assertEqual(item["energy_kwh"], 1.0)
        self.assertEqual(item["estimated_cost"], 2.0)
        self.assertEqual(item["cost_basis"], "power_price_integral")
        self.assertEqual(item["cost_currency"], "SEK")
        self.assertEqual(item["temperature_at_start_c"], -5.0)
        self.assertEqual(item["switch_entity"], "switch.heater")
        self.assertEqual(item["energy_source"], "power")
        self.assertEqual(item["power_entity"], "sensor.power")

    @mocks.sync_test
    async def test_negative_price_is_not_clamped_to_zero(self):
        self.hass.states["sensor.price"] = mocks.State("-1", "SEK/kWh")
        await self.switch("on")
        self.advance(30)
        self.hass.states["sensor.power"] = mocks.State("0", "W")
        await self.switch("off")
        self.assertEqual(self.monitor.heating_history[0]["estimated_cost"], -0.5)

    @mocks.sync_test
    async def test_price_outage_or_missing_start_never_uses_fixed_fallback(self):
        await self.switch("on")
        self.advance(10)
        self.hass.states["sensor.price"] = mocks.State("unavailable", "SEK/kWh")
        await self.monitor.async_update()
        self.advance(10)
        self.hass.states["sensor.price"] = mocks.State("4", "SEK/kWh")
        await self.monitor.async_update()
        self.advance(10)
        await self.switch("off")
        item = self.monitor.heating_history[0]
        self.assertEqual(item["energy_kwh"], 0.5)
        self.assertIsNone(item["estimated_cost"])
        self.assertEqual(item["cost_basis"], "power_price_integral")

        self.hass.states["sensor.price"] = mocks.State("unknown", "SEK/kWh")
        await self.switch("on")
        self.advance(10)
        self.hass.states["sensor.price"] = mocks.State("4", "SEK/kWh")
        await self.monitor.async_update()
        self.advance(10)
        await self.switch("off")
        self.assertIsNone(self.monitor.heating_history[0]["estimated_cost"])

    @mocks.sync_test
    async def test_restart_during_session_does_not_invent_cost(self):
        await self.switch("on")
        self.advance(10)
        await self.monitor.async_update()
        restored = EnergyMonitor(self.hass, self.entry, self.config, lambda: None)
        await restored.async_load()
        self.advance(10)
        self.hass.states["switch.heater"].state = "off"
        await restored.async_update()
        item = restored.heating_history[0]
        self.assertIsNone(item["energy_kwh"])
        self.assertIsNone(item["estimated_cost"])
        self.assertFalse(item["complete"])
        self.assertEqual(item["temperature_at_start_c"], -5.0)
        self.assertEqual(item["power_entity"], "sensor.power")

    @mocks.sync_test
    async def test_switch_change_records_old_source_for_incomplete_session(self):
        await self.switch("on")
        self.advance(10)
        await self.monitor.async_update()
        changed = dict(self.config, switch_entity="switch.other", power_entity="sensor.other")
        restored = EnergyMonitor(self.hass, self.entry, changed, lambda: None)
        await restored.async_load()
        item = restored.heating_history[0]
        self.assertFalse(item["complete"])
        self.assertEqual(item["switch_entity"], "switch.heater")
        self.assertEqual(item["power_entity"], "sensor.power")

    @mocks.sync_test
    async def test_queued_price_change_and_temperature_snapshot_preserve_event_values(self):
        event_api = sys.modules["homeassistant.helpers.event"]
        previous = getattr(event_api, "async_track_state_change_event", None)
        queued = []
        self.hass.async_create_task = queued.append

        def track(hass, entities, callback):
            self.assertEqual(set(entities), {"switch.heater", "sensor.power", "sensor.price"})
            self.listener = callback
            return lambda: None
        event_api.async_track_state_change_event = track
        try:
            await self.monitor.async_start()
            def emit(entity, new_state):
                self.hass.states[entity] = new_state
                self.listener(types.SimpleNamespace(data={"entity_id": entity, "new_state": new_state}))
            emit("switch.heater", mocks.State("on"))
            self.advance(30)
            emit("sensor.price", mocks.State("3", "SEK/kWh"))
            self.hass.states["sensor.outside"] = mocks.State("5", "°C")
            self.advance(30)
            emit("switch.heater", mocks.State("off"))
            while queued:
                await queued.pop(0)
            item = self.monitor.heating_history[0]
            self.assertEqual(item["estimated_cost"], 2.0)
            self.assertEqual(item["temperature_at_start_c"], -5.0)
        finally:
            if previous is None:
                del event_api.async_track_state_change_event
            else:
                event_api.async_track_state_change_event = previous

    @mocks.sync_test
    async def test_deviation_delay_recovery_and_low_high_alerts(self):
        self.config.update({"power_deviation_enabled": True, "power_expected_min_watts": 400,
                            "power_expected_max_watts": 1500, "power_deviation_delay_minutes": 5,
                            "notify_entity": "notify.phone"})
        self.hass.states["sensor.power"].state = "1800"
        await self.switch("on")
        self.advance(4)
        await self.monitor.async_update()
        self.assertFalse(self.monitor.deviation_alarm_active)
        self.advance(1)
        await self.monitor.async_update()
        self.assertTrue(self.monitor.deviation_alarm_active)
        self.assertEqual(self.monitor.deviation_direction, "high")
        self.assertEqual(len(self.notifications), 2)
        self.assertIn("över", self.notifications[0][2]["message"])
        self.assertNotIn("kabel", self.notifications[0][2]["message"].lower())
        await self.monitor.async_update()
        self.assertEqual(len(self.notifications), 2)
        self.hass.states["sensor.power"].state = "1000"
        await self.monitor.async_update()
        self.assertFalse(self.monitor.deviation_alarm_active)
        self.hass.states["sensor.power"].state = "300"
        await self.monitor.async_update()
        self.advance(5)
        await self.monitor.async_update()
        self.assertEqual(self.monitor.deviation_direction, "low")
        self.assertEqual(len(self.notifications), 4)
        self.assertIn("under", self.notifications[-1][2]["message"])
        await self.switch("off")
        self.assertFalse(self.monitor.deviation_alarm_active)

    @mocks.sync_test
    async def test_unavailable_power_interrupts_deviation_timer_and_restart(self):
        self.config.update({"power_deviation_enabled": True, "power_expected_max_watts": 1500,
                            "power_deviation_delay_minutes": 5})
        self.hass.states["sensor.power"].state = "1800"
        await self.switch("on")
        self.advance(4)
        self.hass.states["sensor.power"].state = "unavailable"
        await self.monitor.async_update()
        self.hass.states["sensor.power"].state = "1800"
        await self.monitor.async_update()
        self.advance(1)
        await self.monitor.async_update()
        self.assertFalse(self.monitor.deviation_alarm_active)
        restored = EnergyMonitor(self.hass, self.entry, self.config, lambda: None)
        await restored.async_load()
        self.advance(10)
        await restored.async_update()
        self.assertFalse(restored.deviation_alarm_active)

    @mocks.sync_test
    async def test_deviation_sent_state_survives_restart_and_does_not_notify_twice(self):
        self.config.update({"power_deviation_enabled": True, "power_expected_max_watts": 1500,
                            "power_deviation_delay_minutes": 5})
        self.hass.states["sensor.power"].state = "1800"
        await self.switch("on")
        self.advance(5)
        await self.monitor.async_update()
        self.assertEqual(len(self.notifications), 1)
        restored = EnergyMonitor(self.hass, self.entry, self.config, lambda: None)
        await restored.async_load()
        await restored.async_update()
        self.advance(5)
        await restored.async_update()
        self.assertTrue(restored.deviation_alarm_active)
        self.assertEqual(len(self.notifications), 1)

    @mocks.sync_test
    async def test_queued_return_to_normal_resets_deviation_delay(self):
        self.config.update({"power_deviation_enabled": True, "power_expected_max_watts": 1500,
                            "power_deviation_delay_minutes": 5})
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
            def emit(entity, new_state):
                self.hass.states[entity] = new_state
                self.listener(types.SimpleNamespace(data={"entity_id": entity, "new_state": new_state}))
            emit("sensor.power", mocks.State("1800", "W"))
            emit("switch.heater", mocks.State("on"))
            while queued:
                await queued.pop(0)
            self.advance(4)
            emit("sensor.power", mocks.State("1000", "W"))
            emit("sensor.power", mocks.State("1800", "W"))
            while queued:
                await queued.pop(0)
            self.advance(1)
            await self.monitor.async_update()
            self.assertFalse(self.monitor.deviation_alarm_active)
            self.assertEqual(self.notifications, [])
        finally:
            if previous is None:
                del event_api.async_track_state_change_event
            else:
                event_api.async_track_state_change_event = previous

    def test_temperature_units_and_unknown_values(self):
        self.assertEqual(_read_temperature_c(mocks.State("14", "°F")), -10.0)
        self.assertEqual(_read_temperature_c(mocks.State("-5", "°C")), -5.0)
        for bad in (None, mocks.State("unavailable", "°C"), mocks.State("nan", "°C"), mocks.State("5", "%")):
            self.assertIsNone(_read_temperature_c(bad))


if __name__ == "__main__":
    unittest.main()
