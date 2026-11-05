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
        reg.mapping[('time', 'motorvarmare', 'car1_weekly_time_0')] = 'time.monday_renamed'
        reg.mapping[('switch', 'motorvarmare', 'car1_weekly_enabled_0')] = 'switch.monday_renamed'
        bus = types.SimpleNamespace()
        bus.async_listen = lambda event, callback: setattr(bus, 'listener', (event, callback)) or (lambda: None)
        hass = types.SimpleNamespace(registry=reg, bus=bus)
        c = types.SimpleNamespace(next_departure=None, planned_start=None, temperature=0,
                                  duration_minutes=60, source=None, error=None, owned=False,
                                  config={'switch_entity': 'switch.physical'})
        entry = types.SimpleNamespace(entry_id='car1',title='Bil 1')
        item = sensor.HeaterStatus(entry,c)
        item.hass, item.writes = hass, 0
        controls = item.extra_state_attributes['control_entities']
        self.assertEqual(controls['manual_departure'], 'datetime.manual_renamed')
        self.assertEqual(controls['clear_departure'], 'button.clear_renamed')
        self.assertEqual(controls['weekly_times'][0], 'time.monday_renamed')
        self.assertEqual(controls['weekly_enabled'][0], 'switch.monday_renamed')
        self.assertEqual(controls['heater_switch'], 'switch.physical')
        self.assertTrue(all(uid.startswith('car1_') for _,_,uid in reg.calls))
        self.assertEqual(len(reg.calls), 16)
        await item.async_added_to_hass()
        self.assertEqual(bus.listener[0], 'entity_registry_updated')
        reg.mapping[('time', 'motorvarmare', 'car1_weekly_time_0')] = 'time.renamed_again'
        bus.listener[1](None)
        self.assertEqual(item.writes, 1)
        self.assertEqual(item.extra_state_attributes['control_entities']['weekly_times'][0], 'time.renamed_again')


if __name__ == '__main__':
    unittest.main()
