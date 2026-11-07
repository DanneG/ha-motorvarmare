"""Cost estimates must not imply historical tariffs or readings we lack."""

from datetime import datetime, timedelta, timezone
import types
import unittest

import test_controller as mocks
from test_motorvarmare.energy import EnergyMonitor, _read_price, history_energy_totals


def meter(value):
    state = mocks.State(value, "kWh")
    state.attributes["state_class"] = "total_increasing"
    return state


class PriceTests(unittest.TestCase):
    def test_price_sensor_units_and_missing_values(self):
        self.assertEqual(_read_price(mocks.State("1.2", "SEK/kWh"), "SEK"), 1.2)
        self.assertEqual(_read_price(mocks.State("120", "öre/kWh"), "SEK"), 1.2)
        self.assertEqual(_read_price(mocks.State("1200", "SEK/MWh"), "SEK"), 1.2)
        self.assertEqual(_read_price(mocks.State("-0.5", "EUR/kWh"), "EUR"), -0.5)
        self.assertIsNone(_read_price(mocks.State("1", "EUR/kWh"), "SEK"))
        self.assertIsNone(_read_price(mocks.State("unknown", "SEK/kWh"), "SEK"))
        self.assertIsNone(_read_price(mocks.State("1", "SEK"), "SEK"))
        self.assertIsNone(_read_price(mocks.State("nan", "SEK/kWh"), "SEK"))
        self.assertIsNone(_read_price(mocks.State("1", "kr/kWh"), "NOK"))

    def test_cost_totals_are_conservative_and_do_not_mix_currencies(self):
        def record(cost, currency, energy=1.0):
            return {"start": "2026-11-02T06:00:00+00:00", "end": "2026-11-02T07:00:00+00:00",
                    "energy_kwh": energy, "complete": True,
                    "estimated_cost": cost, "cost_currency": currency}
        now = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)
        result = history_energy_totals([record(2.0, "SEK"), record(None, "SEK")], now, timezone.utc)["daily"][0]
        self.assertEqual(result["estimated_cost"], 2.0)
        self.assertEqual(result["missing_cost"], 1)
        self.assertTrue(result["cost_incomplete"])
        mixed = history_energy_totals([record(2.0, "SEK"), record(1.0, "EUR")], now, timezone.utc)["daily"][0]
        self.assertIsNone(mixed["estimated_cost"])
        self.assertIsNone(mixed["cost_currency"])
        self.assertTrue(mixed["cost_incomplete"])
        self.assertEqual(mixed["energy_kwh"], 2.0)


class RecordedCostTests(unittest.TestCase):
    def setUp(self):
        self.old_now = mocks.dt.utcnow
        self.now = datetime(2026, 11, 2, 5, tzinfo=timezone.utc)
        mocks.dt.utcnow = lambda: self.now
        self.hass = mocks.Hass()
        self.hass.states["sensor.energy"] = meter("100")
        self.entry = types.SimpleNamespace(entry_id="price-tests", title="Bil")
        self.config = {"switch_entity": "switch.heater", "energy_entity": "sensor.energy",
                       "energy_currency": "SEK", "energy_price": 2.5}
        self.monitor = EnergyMonitor(self.hass, self.entry, self.config, lambda: None)

    def tearDown(self):
        mocks.dt.utcnow = self.old_now

    async def run_session(self, *, price_snapshot=None, include_snapshot=False):
        self.hass.states["switch.heater"] = mocks.State("off")
        await self.monitor.async_update()
        self.hass.states["switch.heater"] = mocks.State("on")
        await self.monitor.async_update()
        self.now += timedelta(minutes=30)
        self.hass.states["sensor.energy"].state = "101.2"
        self.hass.states["switch.heater"] = mocks.State("off")
        if include_snapshot:
            await self.monitor.async_update({"switch": self.hass.states["switch.heater"],
                                             "energy": self.hass.states["sensor.energy"],
                                             "price": price_snapshot})
        else:
            await self.monitor.async_update()
        return self.monitor.heating_history[0]

    @mocks.sync_test
    async def test_fixed_price_is_saved_with_session_and_not_repriced(self):
        item = await self.run_session()
        self.assertEqual(item["energy_kwh"], 1.2)
        self.assertEqual(item["estimated_cost"], 3.0)
        self.assertEqual(item["cost_currency"], "SEK")
        self.assertEqual(item["cost_basis"], "fixed")
        self.config["energy_price"] = 100
        restored = EnergyMonitor(self.hass, self.entry, self.config, lambda: None)
        await restored.async_load()
        self.assertEqual(restored.heating_history[0]["estimated_cost"], 3.0)

    @mocks.sync_test
    async def test_sensor_snapshot_uses_price_at_end_not_later_or_fixed_price(self):
        self.config["energy_price_entity"] = "sensor.price"
        self.hass.states["sensor.price"] = mocks.State("4", "SEK/kWh")
        item = await self.run_session(price_snapshot=mocks.State("1", "SEK/kWh"), include_snapshot=True)
        self.assertEqual(item["estimated_cost"], 1.2)
        self.assertEqual(item["cost_basis"], "sensor_at_end")

    @mocks.sync_test
    async def test_unavailable_sensor_does_not_use_current_or_fixed_price(self):
        self.config["energy_price_entity"] = "sensor.price"
        self.hass.states["sensor.price"] = mocks.State("4", "SEK/kWh")
        item = await self.run_session(price_snapshot=None, include_snapshot=True)
        self.assertIsNone(item["estimated_cost"])
        self.assertEqual(item["cost_basis"], "sensor_at_end")

    @mocks.sync_test
    async def test_missing_energy_does_not_become_zero_cost(self):
        self.hass.states["sensor.energy"].state = "unavailable"
        item = await self.run_session()
        self.assertIsNone(item["energy_kwh"])
        self.assertIsNone(item["estimated_cost"])

    @mocks.sync_test
    async def test_legacy_history_is_preserved_and_marks_coverage_uncertain(self):
        old = [{"start": "2026-11-02T05:00:00+00:00", "end": "2026-11-02T05:30:00+00:00",
                "energy_kwh": 1.0, "complete": True} for _ in range(100)]
        self.hass.storage[self.monitor.store.key] = {"switch_entity": "switch.heater", "heating_history": old}
        await self.monitor.async_load()
        self.assertEqual(len(self.monitor.heating_history), 100)
        self.assertTrue(self.monitor.history_energy_totals["daily"][0]["truncated"])
        self.assertTrue(self.monitor.history_energy_totals["daily"][0]["cost_incomplete"])
        self.assertIsNone(self.monitor.history_energy_totals["daily"][0]["estimated_cost"])
        await self.monitor._save()
        restored = EnergyMonitor(self.hass, self.entry, self.config, lambda: None)
        await restored.async_load()
        self.assertTrue(restored.history_energy_totals["daily"][0]["truncated"])


if __name__ == "__main__":
    unittest.main()
