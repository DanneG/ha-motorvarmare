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


if __name__ == "__main__":
    unittest.main()
