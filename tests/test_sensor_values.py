"""Individual Home Assistant sensor values and conservative forecasts."""
from datetime import datetime, timedelta, timezone
import math
import types
import unittest

import test_sensor_registry as registry_mocks

sensor, mocks = registry_mocks.sensor, registry_mocks.mocks
UTC = timezone.utc


class FakeEnergy:
    energy_configured = True
    energy_session_status = "complete"
    session_energy_kwh = 0.8
    power_configured = True
    power_w = 0.0
    energy_sensor_available = True
    monitor_status = "waiting"
    alarm_active = False
    deviation_alarm_active = True
    deviation_direction = "high"
    cost_configured = True

    def __init__(self, now):
        self.history = [{"start": (now-timedelta(hours=2)).isoformat(),
                         "end": (now-timedelta(hours=1)).isoformat(),
                         "duration_minutes": 60, "energy_kwh": 0.8, "complete": True,
                         "switch_entity": "switch.heater", "energy_source": "power", "power_entity": "sensor.power"}]
        self.price = (1.5, "SEK", "sensor_at_end")
        self.totals = {}

    @property
    def heating_history(self):
        return self.history

    @property
    def history_energy_totals(self):
        return self.totals

    def _cost_price(self):
        return self.price


class SensorValuesTests(unittest.TestCase):
    def setUp(self):
        self.saved_now = mocks.dt.utcnow
        self.now = datetime(2026, 11, 2, 5, 0, tzinfo=UTC)
        mocks.dt.utcnow = lambda: self.now
        self.hass = mocks.Hass()
        self.controller = mocks.new_controller(self.hass)
        self.controller.config["power_entity"] = "sensor.power"
        self.controller.energy = FakeEnergy(self.now)
        self.controller.status = "Väntar på start"
        self.controller.temperature = -5
        self.controller.next_departure = self.now + timedelta(hours=4)
        self.controller.duration_minutes = 90
        self.controller.planned_start = self.controller.next_departure - timedelta(minutes=90)
        self.controller.source = "Planerad"
        self.entry = types.SimpleNamespace(entry_id="car1", title="Bil 1")

    def tearDown(self):
        mocks.dt.utcnow = self.saved_now

    def metric(self, key):
        return sensor.HeaterMetric(self.entry, self.controller, key)

    @mocks.sync_test
    async def test_setup_registers_existing_status_and_all_unique_metrics(self):
        entities = []
        hass = types.SimpleNamespace(data={"motorvarmare": {"car1": self.controller}})
        await sensor.async_setup_entry(hass, self.entry, entities.extend)
        self.assertEqual(len(entities), 10)
        self.assertEqual(len({e._attr_unique_id for e in entities}), 10)
        self.assertTrue(all(e._attr_unique_id.startswith("car1_") for e in entities))
        self.assertEqual(entities[0]._attr_unique_id, "car1_status")
        self.assertEqual({e._attr_translation_key for e in entities[1:]}, set(sensor._METRIC_KEYS))
        for e in entities[1:]:
            if e.key in ("session_energy", "energy_today", "energy_week", "energy_month", "next_estimated_energy", "next_estimated_cost"):
                self.assertIsNone(getattr(e, "_attr_state_class", None))

    def test_timestamp_and_remaining_are_aware_and_only_during_owned_heating(self):
        self.assertEqual(self.metric("next_departure").native_value, self.controller.next_departure)
        self.assertEqual(self.metric("planned_start")._attr_device_class, "timestamp")
        self.assertIsNone(self.metric("remaining_heating").native_value)
        self.controller.owned = True
        self.controller._active_departure = self.now + timedelta(minutes=70, seconds=10)
        self.controller._active_source = "Planerad"
        self.controller.status = "Värmer"
        self.assertEqual(self.metric("remaining_heating").native_value, 71)
        self.controller.status = "Fel"
        self.assertFalse(self.metric("remaining_heating").available)
        self.controller.next_departure = datetime(2026, 11, 2, 10, 0)  # unknown zone
        self.assertFalse(self.metric("next_departure").available)

    def test_session_energy_not_zero_when_measurement_incomplete(self):
        metric = self.metric("session_energy")
        self.assertEqual(metric.native_value, 0.8)
        self.controller.energy.session_energy_kwh = 0.0
        self.assertEqual(metric.native_value, 0.0)
        self.controller.energy.energy_session_status = "incomplete"
        self.assertIsNone(metric.native_value)
        self.assertFalse(metric.available)

    def test_periods_respect_local_calendar_and_incomplete_coverage(self):
        self.controller.energy.totals = {
            "daily": [{"period_start":"2026-11-01","energy_kwh":7.0,"incomplete":False},
                      {"period_start":"2026-11-02","energy_kwh":1.25,"incomplete":False}],
            "weekly":[{"period_start":"2026-11-02","energy_kwh":2.0,"incomplete":True}],
            "monthly":[{"period_start":"2026-11-01","energy_kwh":4.0,"incomplete":False}],
        }
        self.assertEqual(self.metric("energy_today").native_value, 1.25)
        weekly = self.metric("energy_week")
        self.assertIsNone(weekly.native_value)
        self.assertEqual(weekly.extra_state_attributes["known_energy_kwh"], 2.0)
        self.assertTrue(weekly.extra_state_attributes["incomplete"])
        self.assertEqual(self.metric("energy_month").native_value, 4.0)
        self.now = datetime(2026, 11, 2, 23, 30, tzinfo=UTC)  # Nov 3 at home
        self.assertFalse(self.metric("energy_today").available)
        self.controller.energy.totals["daily"].append({"period_start":"2026-11-03", "energy_kwh":0.0, "incomplete":False})
        self.assertEqual(self.metric("energy_today").native_value, 0.0)

    def test_forecast_uses_last_complete_average_and_current_price(self):
        self.controller.config["post_departure_enabled"] = True
        estimate = sensor._next_estimate(self.controller)
        self.assertEqual(estimate["energy_kwh"], 1.6)  # 0.8 kW × two hours
        self.assertEqual(estimate["cost"], 2.4)
        self.assertEqual(estimate["currency"], "SEK")
        self.assertEqual(estimate["average_power_w"], 800.0)
        self.assertEqual(estimate["planned_duration_minutes"], 120)
        self.assertEqual(estimate["basis"], "latest_complete_session_average")
        self.assertEqual(self.metric("next_estimated_energy").native_value, 1.6)
        self.assertEqual(self.metric("next_estimated_cost").native_unit_of_measurement, "SEK")
        self.assertEqual(self.metric("next_estimated_cost").native_value, 2.4)
        self.assertEqual(self.metric("next_estimated_cost").extra_state_attributes["price_basis"], "current_price")

    def test_forecast_skips_missing_incomplete_zero_and_future_observations(self):
        self.controller.energy.history.insert(0, {"duration_minutes":20, "energy_kwh":0.3, "complete":False, "end":self.now.isoformat()})
        self.assertEqual(sensor._next_estimate(self.controller)["energy_kwh"], 1.2)
        source = {"switch_entity":"switch.heater", "energy_source":"power", "power_entity":"sensor.power"}
        self.controller.energy.history = [{"duration_minutes":60, "energy_kwh":0.0, "complete":True, "end":self.now.isoformat(), **source}]
        self.assertFalse(self.metric("next_estimated_energy").available)
        self.controller.energy.history = [{"duration_minutes":60, "energy_kwh":1.0, "complete":True, "end":(self.now+timedelta(hours=1)).isoformat(), **source}]
        self.assertFalse(self.metric("next_estimated_energy").available)
        self.controller.energy.history = []
        self.assertIsNone(self.metric("next_estimated_cost").native_value)

    def test_forecast_only_uses_history_from_current_plug_and_sensor(self):
        self.assertEqual(self.metric("next_estimated_energy").native_value, 1.2)
        self.controller.config["power_entity"] = "sensor.replacement"
        self.assertIsNone(self.metric("next_estimated_energy").native_value)
        self.controller.config["power_entity"] = "sensor.power"
        self.controller.config["switch_entity"] = "switch.replacement"
        self.assertIsNone(self.metric("next_estimated_energy").native_value)
        self.controller.config["switch_entity"] = "switch.heater"
        self.controller.energy.history[0].pop("energy_source")  # a pre-upgrade session
        self.assertIsNone(self.metric("next_estimated_energy").native_value)

    def test_forecast_does_not_assume_missing_price_or_skip_pause(self):
        self.controller.energy.price = (None, "SEK", "sensor_at_end")
        self.assertEqual(self.metric("next_estimated_energy").native_value, 1.2)
        self.assertIsNone(self.metric("next_estimated_cost").native_value)
        self.controller.automation_paused = True
        self.assertFalse(self.metric("next_estimated_energy").available)
        self.assertFalse(self.metric("planned_start").available)
        self.controller.automation_paused = False
        self.controller._temperature_blocked = True
        self.assertFalse(self.metric("next_estimated_energy").available)
        self.controller._temperature_blocked = False
        self.controller._suppressed.add(f"Planerad|{self.controller.next_departure.isoformat()}")
        self.assertFalse(self.metric("next_estimated_energy").available)
        self.assertFalse(self.metric("planned_start").available)
        self.controller._suppressed.clear()
        self.controller.error = "Kalendern kan inte läsas"
        self.assertFalse(self.metric("next_estimated_energy").available)
        self.controller.error = None
        self.controller.duration_minutes = 0
        self.assertFalse(self.metric("next_estimated_energy").available)
        self.assertFalse(self.metric("planned_start").available)

    def test_status_attributes_expose_forecast_and_deviation(self):
        self.hass.registry = registry_mocks.Registry()
        item = sensor.HeaterStatus(self.entry, self.controller)
        item.hass = self.hass
        data = item.extra_state_attributes
        self.assertEqual(data["next_estimated_energy_kwh"], 1.2)
        self.assertEqual(data["next_estimated_cost"], 1.8)
        self.assertEqual(data["next_estimated_currency"], "SEK")
        self.assertEqual(data["next_estimate_basis"], "latest_complete_session_average")
        self.assertTrue(data["power_deviation_active"])
        self.assertEqual(data["power_deviation_direction"], "high")


if __name__ == "__main__":
    unittest.main()
