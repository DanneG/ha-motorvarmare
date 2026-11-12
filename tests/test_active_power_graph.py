"""Current-run graph samples never invent values through missing intervals."""

from datetime import datetime, timedelta, timezone
import asyncio
import types
import unittest

import test_controller as mocks
from test_motorvarmare.energy import EnergyMonitor, _POWER_GRAPH_LIMIT


class ActivePowerGraphTests(unittest.TestCase):
    def setUp(self):
        self.previous_now = mocks.dt.utcnow
        self.now = datetime(2026, 11, 2, 5, tzinfo=timezone.utc)
        mocks.dt.utcnow = lambda: self.now
        self.hass = mocks.Hass()
        self.hass.states["sensor.power"] = mocks.State("1000", "W")
        self.entry = types.SimpleNamespace(entry_id="active-graph", title="Bil")
        self.config = {"switch_entity": "switch.heater", "power_entity": "sensor.power",
                       "energy_price": 2.5, "energy_currency": "SEK"}
        self.monitor = EnergyMonitor(self.hass, self.entry, self.config, lambda: None)

    def tearDown(self):
        mocks.dt.utcnow = self.previous_now

    async def start(self):
        await self.monitor.async_update()
        self.hass.states["switch.heater"].state = "on"
        await self.monitor.async_update()

    @mocks.sync_test
    async def test_samples_and_fixed_cost_are_current_and_isolated(self):
        await self.start()
        self.assertEqual(self.monitor.active_power_samples[0]["watts"], 1000)
        self.assertEqual(self.monitor.active_session_cost, 0)
        self.now += timedelta(minutes=30)
        self.hass.states["sensor.power"].state = "500"
        await self.monitor.async_update()
        self.assertEqual(self.monitor.active_power_samples[-1]["watts"], 500)
        self.assertEqual(self.monitor.session_energy_kwh, 0.5)
        self.assertEqual(self.monitor.active_session_cost, 1.25)
        self.assertEqual(self.monitor.active_session_currency, "SEK")
        samples = self.monitor.active_power_samples
        samples[0]["watts"] = 123
        self.assertEqual(self.monitor.active_power_samples[0]["watts"], 1000)
        self.hass.states["switch.heater"].state = "off"
        await self.monitor.async_update()
        self.assertEqual(self.monitor.active_power_samples, [])
        self.assertIsNone(self.monitor.active_session_cost)

    @mocks.sync_test
    async def test_outage_is_explicit_gap_not_zero_and_cost_is_unknown(self):
        await self.start()
        self.now += timedelta(minutes=1)
        self.hass.states["sensor.power"].state = "unavailable"
        await self.monitor.async_update()
        self.now += timedelta(minutes=1)
        self.hass.states["sensor.power"].state = "500"
        await self.monitor.async_update()
        self.assertEqual([p["watts"] for p in self.monitor.active_power_samples], [1000, None, 500])
        self.assertIsNone(self.monitor.session_energy_kwh)
        self.assertIsNone(self.monitor.active_session_cost)
        self.assertIsNone(self.monitor.active_session_currency)

    @mocks.sync_test
    async def test_restart_retains_samples_but_inserts_gap_for_downtime(self):
        await self.start()
        self.now += timedelta(minutes=1)
        await self.monitor.async_update()
        old_last = self.monitor.active_power_samples[-1]["at"]
        self.now += timedelta(minutes=10)
        restored = EnergyMonitor(self.hass, self.entry, self.config, lambda: None)
        await restored.async_load()
        await restored.async_update()
        points = restored.active_power_samples
        self.assertEqual(points[-2], {"at": old_last, "watts": None})
        self.assertEqual(points[-1]["watts"], 1000)
        self.assertIsNone(restored.active_session_cost)
        self.assertIsNone(restored.session_energy_kwh)

    @mocks.sync_test
    async def test_unknown_switch_breaks_graph_and_no_sensor_is_optional(self):
        await self.start()
        self.now += timedelta(minutes=1)
        self.hass.states["switch.heater"].state = "unavailable"
        await self.monitor.async_update()
        self.now += timedelta(minutes=1)
        self.hass.states["switch.heater"].state = "on"
        await self.monitor.async_update()
        self.assertEqual([p["watts"] for p in self.monitor.active_power_samples], [1000, None, 1000])
        no_power = EnergyMonitor(self.hass, self.entry, {"switch_entity": "switch.heater"}, lambda: None)
        await no_power.async_update()
        self.assertEqual(no_power.active_power_samples, [])
        self.assertIsNone(no_power.active_session_cost)

    @mocks.sync_test
    async def test_dynamic_price_is_integrated_without_guessing_gaps(self):
        self.config["energy_price_entity"] = "sensor.price"
        self.hass.states["sensor.price"] = mocks.State("2", "SEK/kWh")
        await self.start()
        self.now += timedelta(minutes=30)
        self.hass.states["sensor.price"].state = "3"
        await self.monitor.async_update()
        self.now += timedelta(minutes=30)
        await self.monitor.async_update()
        self.assertEqual(self.monitor.active_session_cost, 2.5)
        self.hass.states["sensor.price"].state = "unavailable"
        self.now += timedelta(minutes=1)
        await self.monitor.async_update()
        self.assertIsNone(self.monitor.active_session_cost)

    @mocks.sync_test
    async def test_samples_are_bounded_and_corrupt_storage_is_filtered(self):
        await self.start()
        for _ in range(_POWER_GRAPH_LIMIT + 10):
            self.now += timedelta(seconds=30)
            await self.monitor.async_update()
        self.assertEqual(len(self.monitor.active_power_samples), _POWER_GRAPH_LIMIT)
        data = self.hass.storage[self.monitor.store.key]
        data["active_power_samples"].extend([
            {"at": "invalid", "watts": 5}, {"at": self.now.isoformat(), "watts": float("nan")},
            {"at": "2020-01-01T00:00:00+00:00", "watts": 5},
        ])
        restored = EnergyMonitor(self.hass, self.entry, self.config, lambda: None)
        await restored.async_load()
        self.assertLessEqual(len(restored.active_power_samples), _POWER_GRAPH_LIMIT)
        self.assertTrue(all(item["watts"] == 1000 for item in restored.active_power_samples))

    @mocks.sync_test
    async def test_real_controller_clean_restart_labels_new_measurement_start(self):
        """Heating may resume, but the power monitor starts a new measurement."""
        original_wait, original_sleep = asyncio.wait_for, asyncio.sleep
        asyncio.wait_for, asyncio.sleep = mocks.immediate_wait_for, mocks.immediate_sleep
        try:
            for scheduled in (False, True):
                with self.subTest(scheduled=scheduled):
                    self.hass = mocks.Hass()
                    self.hass.states["sensor.power"] = mocks.State("1000", "W")
                    controller = mocks.new_controller(self.hass)
                    controller.energy.config["power_entity"] = "sensor.power"
                    controller.energy.config["energy_price"] = 2.0
                    await controller.energy.async_update()  # switch was observed off
                    heater_started = self.now
                    if scheduled:
                        await controller.async_add_local_departure(self.now + timedelta(minutes=20))
                    else:
                        await controller.async_start_now()
                        await controller.energy.async_update()
                    await controller.async_extend_30()
                    self.now += timedelta(minutes=10)
                    await controller.energy.async_update()
                    self.assertEqual(controller.energy.active_measurement_started_at, heater_started.isoformat())
                    self.assertGreater(controller.energy.session_energy_kwh, 0)
                    await controller.async_shutdown()
                    self.assertEqual(self.hass.states["switch.heater"].state, "off")
                    self.now += timedelta(minutes=2)
                    resumed = mocks.new_controller(self.hass)
                    resumed.energy.config["power_entity"] = "sensor.power"
                    resumed.energy.config["energy_price"] = 2.0
                    await resumed.async_load()
                    # EnergyMonitor.async_start observes the plug off before
                    # the controller resumes it; emulate that initial sample.
                    await resumed.energy.async_update()
                    await resumed.async_update()
                    self.assertTrue(resumed.owned)
                    self.assertEqual(resumed._started_at, heater_started)
                    self.assertEqual(resumed.energy.active_measurement_started_at, self.now.isoformat())
                    self.assertEqual(resumed.energy.session_energy_kwh, 0)
                    self.assertEqual(resumed.energy.active_session_cost, 0)
                    self.assertTrue(all(p["at"] >= self.now.isoformat() for p in resumed.energy.active_power_samples))
                    self.now += timedelta(minutes=10)
                    await resumed.energy.async_update()
                    self.assertEqual(resumed.energy.session_energy_kwh, 0.1667)
                    # The UI can identify that this is only the post-restart
                    # measurement, not energy from the original heater start.
                    self.assertNotEqual(resumed.energy.active_measurement_started_at, heater_started.isoformat())
        finally:
            asyncio.wait_for, asyncio.sleep = original_wait, original_sleep

    @mocks.sync_test
    async def test_unknown_measurement_start_is_not_claimed_after_unobserved_on(self):
        self.hass.states["switch.heater"].state = "on"
        await self.monitor.async_update()
        self.assertIsNone(self.monitor.active_measurement_started_at)
        self.assertIsNone(self.monitor.session_energy_kwh)
        self.assertIsNone(self.monitor.active_session_cost)


if __name__ == "__main__":
    unittest.main()
