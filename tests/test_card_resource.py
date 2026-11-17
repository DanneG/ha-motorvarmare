"""Safe installation and migration of the bundled dashboard card."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

spec = importlib.util.spec_from_file_location(
    "motorvarmare_frontend_under_test",
    Path(__file__).parents[1] / "custom_components/motorvarmare/frontend.py",
)
frontend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frontend)


class Resources:
    def __init__(self, saved=(), *, fail_update=False):
        self.saved = [dict(item) for item in saved]
        self.items = []
        self.loaded = False
        self.fail_update = fail_update
        self.calls = []

    async def async_load(self):
        self.calls.append("load")
        self.items = [dict(item) for item in self.saved]

    async def async_get_info(self):
        if not self.loaded:
            await self.async_load()
            self.loaded = True
        return {"resources": len(self.items)}

    def async_items(self):
        if not self.loaded:
            raise AssertionError("Read before loading")
        return list(self.items)

    async def async_create_item(self, data):
        self.calls.append("create")
        self.items.append({"id": "new", "url": data["url"], "type": data["res_type"]})

    async def async_update_item(self, item_id, data):
        self.calls.append("update")
        if self.fail_update:
            raise RuntimeError("update failed")
        item = next(item for item in self.items if item["id"] == item_id)
        item.update(url=data["url"], type=data["res_type"])

    async def async_delete_item(self, item_id):
        self.calls.append("delete")
        self.items = [item for item in self.items if item["id"] != item_id]


def run(coroutine):
    """Run fake async calls, none of which perform real I/O."""
    try:
        coroutine.send(None)
    except StopIteration as result:
        return result.value
    raise AssertionError("Test coroutine unexpectedly suspended")


class CardResourceTests(unittest.TestCase):
    def test_new_install_loads_before_adding_and_keeps_other_resources(self):
        resources = Resources([{"id": "other", "url": "/local/other.js", "type": "module"}])
        data = SimpleNamespace(resource_mode="storage", resources=resources)
        run(frontend._async_register_resource(data, "/motorvarmare/ha-motorvarmare-card.js?v=1"))
        self.assertEqual(resources.calls, ["load", "create"])
        self.assertEqual([item["id"] for item in resources.items], ["other", "new"])

    def test_restart_migrates_and_deduplicates_known_old_urls(self):
        resources = Resources([
            {"id": "hacs", "url": "/hacsfiles/ha-motorvarmare-card/ha-motorvarmare-card.js?hacstag=1", "type": "module"},
            {"id": "manual", "url": "/local/ha-motorvarmare-card.js?v=1", "type": "module"},
            {"id": "external", "url": "https://example.org/local/ha-motorvarmare-card.js", "type": "module"},
        ])
        data = SimpleNamespace(resource_mode="storage", resources=resources)
        url = "/motorvarmare/ha-motorvarmare-card.js?v=0.12.0"
        run(frontend._async_register_resource(data, url))
        self.assertEqual(resources.calls, ["load", "update", "delete"])
        self.assertEqual(resources.items, [
            {"id": "hacs", "url": url, "type": "module"},
            {"id": "external", "url": "https://example.org/local/ha-motorvarmare-card.js", "type": "module"},
        ])
        run(frontend._async_register_resource(data, url))
        self.assertEqual(resources.calls, ["load", "update", "delete"])
        run(frontend._async_register_resource(data, url.replace("0.12.0", "0.12.1")))
        self.assertEqual(resources.calls[-1], "update")
        self.assertEqual(len(resources.items), 2)

    def test_update_failure_keeps_older_resources_intact(self):
        resources = Resources([
            {"id": "hacs", "url": "/hacsfiles/ha-motorvarmare-card/ha-motorvarmare-card.js", "type": "module"},
            {"id": "manual", "url": "/local/ha-motorvarmare-card.js", "type": "module"},
        ], fail_update=True)
        data = SimpleNamespace(resource_mode="storage", resources=resources)
        with self.assertRaises(RuntimeError):
            run(frontend._async_register_resource(data, "/motorvarmare/ha-motorvarmare-card.js?v=1"))
        self.assertEqual(resources.calls, ["load", "update"])
        self.assertEqual(len(resources.items), 2)

    def test_yaml_does_not_mutate_or_load_storage(self):
        resources = Resources()
        data = SimpleNamespace(resource_mode="yaml", resources=resources)
        with self.assertLogs(frontend._LOGGER, level="WARNING"):
            run(frontend._async_register_resource(data, "/motorvarmare/ha-motorvarmare-card.js?v=1"))
        self.assertEqual(resources.calls, [])


if __name__ == "__main__":
    unittest.main()
