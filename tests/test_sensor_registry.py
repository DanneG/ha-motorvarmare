"""Entity-registry lookup and refresh with lightweight Home Assistant mocks."""
import importlib
import types
import unittest

import test_controller as mocks

mocks.module('homeassistant.components')
sensor_api = mocks.module('homeassistant.components.sensor')


class SensorEntity:
    async def async_added_to_hass(self):
        pass

    def async_on_remove(self, callback):
        pass

    def async_write_ha_state(self):
        self.writes += 1


sensor_api.SensorEntity = SensorEntity
sensor_api.SensorDeviceClass = types.SimpleNamespace(ENUM='enum')
mocks.module('homeassistant.config_entries').ConfigEntry = type('ConfigEntry', (), {})
mocks.core.HomeAssistant = type('HomeAssistant', (), {})
mocks.module('homeassistant.helpers.device_registry').DeviceInfo = lambda **kwargs: kwargs
mocks.module('homeassistant.helpers.entity_platform').AddEntitiesCallback = object
sys_dispatcher = importlib.import_module('homeassistant.helpers.dispatcher')
sys_dispatcher.async_dispatcher_connect = lambda *args: lambda: None
registry_module = mocks.module('homeassistant.helpers.entity_registry')
registry_module.EVENT_ENTITY_REGISTRY_UPDATED = 'entity_registry_updated'
registry_module.async_get = lambda hass: hass.registry
sensor = importlib.import_module('test_motorvarmare.sensor')


class Registry:
    def __init__(self):
        self.mapping = {}
        self.calls = []

    def async_get_entity_id(self, domain, platform, unique_id):
        self.calls.append((domain, platform, unique_id))
        return self.mapping.get((domain, platform, unique_id))


class SensorRegistryTests(unittest.TestCase):
    @mocks.sync_test
    async def test_car_scoped_lookup_and_registry_event_refresh(self):
        reg = Registry()
        reg.mapping[('datetime', 'motorvarmare', 'car1_manual_departure')] = 'datetime.manual_renamed'
        reg.mapping[('button', 'motorvarmare', 'car1_clear_departure')] = 'button.clear_renamed'
        reg.mapping[('button', 'motorvarmare', 'car1_start_now')] = 'button.start_renamed'
        reg.mapping[('button', 'motorvarmare', 'car1_stop_now')] = 'button.stop_renamed'
        reg.mapping[('button', 'motorvarmare', 'car1_extend_30')] = 'button.extend_renamed'
        reg.mapping[('button', 'motorvarmare', 'car1_skip_next')] = 'button.skip_renamed'
        reg.mapping[('switch', 'motorvarmare', 'car1_automation_paused')] = 'switch.pause_renamed'
        reg.mapping[('datetime', 'motorvarmare', 'car1_pause_until')] = 'datetime.pause_renamed'
        reg.mapping[('calendar', 'motorvarmare', 'car1_departure_calendar')] = 'calendar.departures_renamed'
        reg.mapping[('time', 'motorvarmare', 'car1_weekly_time_0')] = 'time.monday_renamed'
        reg.mapping[('switch', 'motorvarmare', 'car1_weekly_enabled_0')] = 'switch.monday_renamed'
        bus = types.SimpleNamespace()
        bus.async_listen = lambda event, callback: setattr(bus, 'listener', (event, callback)) or (lambda: None)
        hass = types.SimpleNamespace(registry=reg, bus=bus)
        c = types.SimpleNamespace(next_departure=None, planned_start=None, temperature=0,
                                  duration_minutes=60, source=None, error=None, owned=False,
                                  _temperature_blocked=False, post_departure_minutes=0,
                                  active_until=None, schedule_7_days=[], status='Värmer',
                                  config={'switch_entity': 'switch.physical'})
        entry = types.SimpleNamespace(entry_id='car1',title='Bil 1')
        item = sensor.HeaterStatus(entry,c)
        item.hass, item.writes = hass, 0
        self.assertEqual(item.native_value, 'heating')
        self.assertEqual(item.extra_state_attributes['current_duration_minutes'], 60)
        self.assertFalse(item.extra_state_attributes['temperature_blocked'])
        item.controller._temperature_blocked = True
        self.assertTrue(item.extra_state_attributes['temperature_blocked'])
        self.assertEqual(item.extra_state_attributes['current_duration_minutes'], 60)
        item.controller._temperature_blocked = False
        c.temperature = -10
        self.assertEqual(item.extra_state_attributes['current_duration_minutes'], 120)
        c.temperature = None
        self.assertIsNone(item.extra_state_attributes['current_duration_minutes'])
        reg.calls.clear()
        controls = item.extra_state_attributes['control_entities']
        self.assertEqual(controls['manual_departure'], 'datetime.manual_renamed')
        self.assertEqual(controls['clear_departure'], 'button.clear_renamed')
        self.assertEqual(controls['start_now'], 'button.start_renamed')
        self.assertEqual(controls['stop_now'], 'button.stop_renamed')
        self.assertEqual(controls['extend_30'], 'button.extend_renamed')
        self.assertEqual(controls['skip_next'], 'button.skip_renamed')
        self.assertEqual(controls['automation_paused'], 'switch.pause_renamed')
        self.assertEqual(controls['pause_until'], 'datetime.pause_renamed')
        self.assertEqual(controls['calendar'], 'calendar.departures_renamed')
        self.assertEqual(controls['weekly_times'][0], 'time.monday_renamed')
        self.assertEqual(controls['weekly_enabled'][0], 'switch.monday_renamed')
        self.assertEqual(controls['heater_switch'], 'switch.physical')
        self.assertTrue(all(uid.startswith('car1_') for _,_,uid in reg.calls))
        await item.async_added_to_hass()
        self.assertEqual(bus.listener[0], 'entity_registry_updated')
        reg.mapping[('time', 'motorvarmare', 'car1_weekly_time_0')] = 'time.renamed_again'
        bus.listener[1](None)
        self.assertEqual(item.writes, 1)
        self.assertEqual(item.extra_state_attributes['control_entities']['weekly_times'][0], 'time.renamed_again')

    def test_active_measurement_start_and_graph_fields_are_exposed(self):
        from datetime import datetime, timedelta, timezone
        start = datetime(2026, 11, 12, 6, 0, tzinfo=timezone.utc)
        samples = [{'at': start.isoformat(), 'watts': 750.0}]
        energy = types.SimpleNamespace(
            power_configured=True, energy_configured=True, cost_configured=True,
            energy_sensor_available=True, power_w=750.0, session_energy_kwh=0.25,
            energy_session_status='measuring', monitor_status='ok', alarm_active=False,
            active_power_samples=samples, active_measurement_started_at=start.isoformat(),
            active_session_cost=0.5, active_session_currency='SEK', heating_history=[],
            history_energy_totals=None,
        )
        c = types.SimpleNamespace(next_departure=None, planned_start=None, temperature=0,
            duration_minutes=60, source=None, error=None, owned=True, _started_at=start,
            _temperature_blocked=False, post_departure_minutes=0, can_extend=True,
            active_until=start+timedelta(hours=1), schedule_7_days=[], status='Värmer',
            config={'switch_entity':'switch.heater'}, energy=energy)
        item = sensor.HeaterStatus(types.SimpleNamespace(entry_id='car1',title='Bil 1'), c)
        item.hass = types.SimpleNamespace(registry=Registry())
        attrs = item.extra_state_attributes
        self.assertEqual(attrs['active_started_at'], start)
        self.assertEqual(attrs['active_max_until'], start+timedelta(hours=4))
        self.assertTrue(attrs['can_extend'])
        self.assertEqual(attrs['active_measurement_started_at'], start.isoformat())
        self.assertEqual(attrs['active_power_samples'], samples)
        self.assertEqual(attrs['active_session_cost'], 0.5)
        self.assertEqual(attrs['active_session_currency'], 'SEK')
        self.assertIn('active_power_samples', item._unrecorded_attributes)


if __name__ == '__main__':
    unittest.main()
