"""Isolated configuration/migration checks; not a Home Assistant integration test."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "motorvarmare"
PACKAGE = "test_motorvarmare_config_flow"
MISSING = object()


class Marker:
    def __init__(self, key, **kwargs):
        self.key, self.kwargs = key, kwargs


class Schema:
    def __init__(self, schema):
        self.schema = schema


class Selector:
    def __init__(self, *args, **kwargs):
        pass


class ConfigFlowBase:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()


def make_module(name, **attributes):
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    return module


def finish(coroutine):
    """Run a coroutine only when every mocked operation finishes immediately."""
    try:
        coroutine.send(None)
    except StopIteration as result:
        return result.value
    finally:
        coroutine.close()
    raise AssertionError("Mock operation unexpectedly suspended")


class ConfigFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        package = make_module(PACKAGE)
        package.__path__ = [str(ROOT)]
        voluptuous = make_module("voluptuous", Optional=Marker, Required=Marker, Schema=Schema)
        ha = make_module("homeassistant")
        ha.__path__ = []
        entries = make_module("homeassistant.config_entries", ConfigFlow=ConfigFlowBase,
                              OptionsFlow=type("OptionsFlow", (), {}), ConfigEntry=object)
        const = make_module("homeassistant.const", CONF_NAME="name")
        core = make_module("homeassistant.core", callback=lambda function: function)
        helpers = make_module("homeassistant.helpers")
        helpers.__path__ = []
        selector = make_module("homeassistant.helpers.selector", NumberSelector=Selector,
            NumberSelectorConfig=Selector, EntitySelector=Selector, EntitySelectorConfig=Selector,
            TextSelector=Selector, TextSelectorConfig=Selector,
            NumberSelectorMode=types.SimpleNamespace(BOX="box"))
        ha.config_entries = entries
        helpers.selector = selector
        mocks = {PACKAGE: package, "voluptuous": voluptuous, "homeassistant": ha,
                 entries.__name__: entries, const.__name__: const, core.__name__: core,
                 helpers.__name__: helpers, selector.__name__: selector}
        cls.previous = {name: sys.modules.get(name, MISSING) for name in mocks}
        sys.modules.update(mocks)
        cls.flow = importlib.import_module(f"{PACKAGE}.config_flow")

    @classmethod
    def tearDownClass(cls):
        for name in (f"{PACKAGE}.config_flow", f"{PACKAGE}.const"):
            sys.modules.pop(name, None)
        for name, previous in cls.previous.items():
            if previous is MISSING:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous

    def setUp(self):
        entries = types.SimpleNamespace(async_entries=lambda domain: [])
        self.hass = types.SimpleNamespace(config_entries=entries)

    def validate(self, *, keywords="", titles="", calendar="calendar.family", old=""):
        data = {"name": "Bil", "switch_entity": "switch.car", "calendar_entity": calendar,
                "event_keywords": keywords, "event_titles": titles}
        error = self.flow._error(self.hass, data, legacy_tag=old)
        return error, data

    def test_title_or_keywords_satisfy_selected_calendar(self):
        self.assertIsNone(self.validate(titles="TILL JOBBET")[0])
        self.assertIsNone(self.validate(keywords="#bil1, jobb")[0])
        self.assertEqual(self.validate(keywords=" , \n ")[0], "missing_calendar_rule")
        self.assertIsNone(self.validate(calendar="")[0])

    def test_post_departure_option_defaults_off_and_preserves_existing_selection(self):
        for values, expected in [({}, False), ({"post_departure_enabled": True}, True),
                                 ({"post_departure_enabled": False}, False)]:
            fields = {key.key: key.kwargs for key in self.flow._schema(values).schema}
            self.assertIs(fields["post_departure_enabled"]["default"], expected)

    def test_forecast_price_and_alert_settings_are_optional_and_clearable(self):
        fields = {key.key: key.kwargs for key in self.flow._schema({
            "weather_entity": "weather.home", "energy_price_entity": "sensor.price",
            "energy_price": 0, "energy_currency": "EUR",
        }).schema}
        self.assertEqual(fields["weather_entity"]["description"]["suggested_value"], "weather.home")
        self.assertEqual(fields["energy_price_entity"]["description"]["suggested_value"], "sensor.price")
        self.assertEqual(fields["energy_price"]["description"]["suggested_value"], 0)
        self.assertEqual(fields["energy_currency"]["default"], "EUR")
        self.assertFalse(fields["operation_alerts_enabled"]["default"])
        user_input = {"weather_entity": "", "energy_price": 0}
        self.flow._normalize_optional_entities(user_input)
        self.assertEqual(user_input["weather_entity"], "")
        self.assertEqual(user_input["energy_price"], 0)
        user_input = {}
        self.flow._normalize_optional_entities(user_input)
        self.assertIsNone(user_input["energy_price"])

    def test_currency_must_be_three_letters_and_is_normalized(self):
        data = {"name": "Bil", "switch_entity": "switch.car", "event_keywords": "", "event_titles": "", "energy_currency": " sek "}
        self.assertIsNone(self.flow._error(self.hass, data))
        self.assertEqual(data["energy_currency"], "SEK")
        data["energy_currency"] = "kr"
        self.assertEqual(self.flow._error(self.hass, data), "invalid_currency")

    def test_legacy_tag_remains_only_while_its_keyword_remains(self):
        error, result = self.validate(keywords="Annat, JOBB\n#bil1", old="jobb")
        self.assertIsNone(error)
        self.assertEqual(result["tag"], "jobb")
        self.assertEqual(self.validate(keywords="#bil1", old="jobb")[1]["tag"], "")
        self.assertEqual(self.validate(titles="TILL JOBBET", old="jobb")[1]["tag"], "")
        self.assertEqual(self.validate(keywords="jobb")[1]["tag"], "")

    def test_old_tag_is_suggested_once_and_not_exposed_as_an_extra_field(self):
        schema = self.flow._schema({"tag": "#bil1"}).schema
        fields = {key.key: key.kwargs.get("description", {}).get("suggested_value") for key in schema}
        self.assertEqual(fields["event_keywords"], "#bil1")
        self.assertNotIn("tag", fields)
        self.assertIsNone({key.key: key.kwargs.get("description", {}).get("suggested_value")
                           for key in self.flow._schema({"tag": "#bil1", "event_keywords": ""}).schema}
                          ["event_keywords"])

    def test_saving_options_preserves_and_then_removes_old_tag(self):
        entry = types.SimpleNamespace(entry_id="car1", title="Bil", data={"tag": "jobb"}, options={})
        self.hass.config_entries.async_update_entry = lambda *args, **kwargs: None
        options = self.flow.MotorvarmareOptionsFlow(entry)
        options.hass = self.hass
        options.async_create_entry = lambda **kwargs: kwargs
        base = {"name": "Bil", "switch_entity": "switch.car", "calendar_entity": "calendar.family",
                "event_titles": "", "event_keywords": "jobb, annat"}
        saved = finish(options.async_step_init(dict(base)))["data"]
        self.assertEqual(saved["tag"], "jobb")
        entry.options = saved
        base["event_keywords"] = "annat"
        saved_again = finish(options.async_step_init(dict(base)))["data"]
        self.assertEqual(saved_again["tag"], "")

    def test_monitoring_is_optional_and_existing_fields_are_suggested(self):
        schema = self.flow._schema({
            "power_entity": "sensor.plug_power",
            "energy_entity": "sensor.plug_energy",
            "notify_entity": "notify.my_phone",
        }).schema
        fields = {key.key: key.kwargs for key in schema}
        self.assertNotIn("energy_entity", fields)
        for key, value in (("power_entity", "sensor.plug_power"),
                           ("notify_entity", "notify.my_phone")):
            self.assertEqual(fields[key]["description"]["suggested_value"], value)
        self.assertEqual(fields["power_min_watts"]["default"], 10)
        self.assertEqual(fields["power_delay_minutes"]["default"], 5)
        self.assertIs(fields["power_alarm_enabled"]["default"], True)

        disabled = self.flow._schema({"power_alarm_enabled": False}).schema
        disabled_fields = {key.key: key.kwargs for key in disabled}
        self.assertIs(disabled_fields["power_alarm_enabled"]["default"], False)

    def test_clearing_optional_monitoring_fields_overrides_old_entry_data(self):
        entry = types.SimpleNamespace(entry_id="car1", title="Bil", data={
            "power_entity": "sensor.old_power", "energy_entity": "sensor.old_energy",
            "notify_entity": "notify.old_phone",
        }, options={})
        self.hass.config_entries.async_update_entry = lambda *args, **kwargs: None
        options = self.flow.MotorvarmareOptionsFlow(entry)
        options.hass = self.hass
        options.async_create_entry = lambda **kwargs: kwargs
        result = finish(options.async_step_init({
            "name": "Bil", "switch_entity": "switch.car",
            "temperature_entity": "sensor.outside",
            "power_min_watts": 12, "power_delay_minutes": 5,
            "power_alarm_enabled": False,
        }))["data"]
        self.assertEqual(result["power_entity"], "")
        self.assertEqual(result["energy_entity"], "")
        self.assertEqual(result["notify_entity"], "")
        merged = {**entry.data, **result}
        self.assertEqual(merged["power_entity"], "")
        self.assertEqual(merged["energy_entity"], "")
        self.assertEqual(merged["notify_entity"], "")
        self.assertEqual(merged["power_min_watts"], 12)
        self.assertIs(merged["power_alarm_enabled"], False)


if __name__ == "__main__":
    unittest.main()
