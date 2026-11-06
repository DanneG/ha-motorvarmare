"""Permission and input checks for the schedule projection WebSocket."""
from datetime import datetime, timezone
import asyncio
import importlib
import sys
import types
import unittest
from unittest.mock import patch

import test_controller as mocks
import test_local_calendar as calendar_mocks


class Unauthorized(Exception):
    def __init__(self, **kwargs):
        self.entity_id = kwargs.get("entity_id")


class Registry:
    def async_get(self, entity_id):
        if entity_id == "sensor.car_status":
            return types.SimpleNamespace(config_entry_id="car1", platform="motorvarmare", unique_id="car1_status")
        if entity_id == "sensor.second_status":
            return types.SimpleNamespace(config_entry_id="car2", platform="motorvarmare", unique_id="car2_status")
        if entity_id == "sensor.other":
            return types.SimpleNamespace(config_entry_id="other", platform="other", unique_id="other")
        return None

    def async_get_entity_id(self, domain, platform, unique_id):
        if (domain, platform, unique_id) == ("calendar", "motorvarmare", "car1_departure_calendar"):
            return "calendar.car_local"
        if (domain, platform, unique_id) == ("calendar", "motorvarmare", "car2_departure_calendar"):
            return "calendar.second_local"
        return None


class Permissions:
    def __init__(self, allowed):
        self.allowed, self.checked = set(allowed), []

    def check_entity(self, entity_id, policy):
        self.checked.append((entity_id, policy))
        return entity_id in self.allowed


class Connection:
    def __init__(self, allowed):
        self.user = types.SimpleNamespace(permissions=Permissions(allowed))
        self.result, self.error = None, None

    def send_result(self, message_id, result):
        self.result = result

    def send_error(self, message_id, code, message):
        self.error = (code, message)


class ScheduleWebSocketTests(unittest.TestCase):
    def setUp(self):
        self.previous_wait_for = asyncio.wait_for
        asyncio.wait_for = mocks.immediate_wait_for
        self.hass = mocks.Hass()
        self.controller = mocks.new_controller(self.hass, calendar="calendar.private")
        self.hass.data = {"motorvarmare": {"car1": self.controller}}
        self.hass.events = [{"summary": "#bil1", "start": "2026-11-03T09:00:00+01:00"}]
        self.message = {"id": 1, "entity_id": "sensor.car_status", "start": "2026-11-02", "end": "2026-11-09"}
        vol = types.ModuleType("voluptuous")
        vol.Required = lambda key: key
        ws = types.ModuleType("homeassistant.components.websocket_api")
        ws.websocket_command = lambda schema: lambda func: func
        ws.async_response = lambda func: func
        cv = types.ModuleType("homeassistant.helpers.config_validation")
        cv.entity_domain = lambda domain: str
        registry = types.ModuleType("homeassistant.helpers.entity_registry")
        registry.async_get = lambda hass: Registry()
        policy = types.ModuleType("homeassistant.auth.permissions.const")
        policy.POLICY_READ = "read"
        auth = types.ModuleType("homeassistant.auth")
        auth.__path__ = []
        permissions = types.ModuleType("homeassistant.auth.permissions")
        permissions.__path__ = []
        self.modules = patch.dict(sys.modules, {"voluptuous": vol,
            "homeassistant.components.websocket_api": ws,
            "homeassistant.helpers.config_validation": cv,
            "homeassistant.helpers.entity_registry": registry,
            "homeassistant.auth": auth, "homeassistant.auth.permissions": permissions,
            "homeassistant.auth.permissions.const": policy})
        self.modules.start()
        self.ws_attr = patch.object(sys.modules["homeassistant.components"], "websocket_api", ws, create=True)
        self.ws_attr.start()
        self.cv_attr = patch.object(sys.modules["homeassistant.helpers"], "config_validation", cv, create=True)
        self.cv_attr.start()
        self.er_attr = patch.object(sys.modules["homeassistant.helpers"], "entity_registry", registry, create=True)
        self.er_attr.start()
        self.exc_attr = patch.object(sys.modules["homeassistant.exceptions"], "Unauthorized", Unauthorized, create=True)
        self.exc_attr.start()
        sys.modules.pop("test_motorvarmare.websocket", None)
        self.api = importlib.import_module("test_motorvarmare.websocket")

    def tearDown(self):
        sys.modules.pop("test_motorvarmare.websocket", None)
        self.exc_attr.stop(); self.er_attr.stop(); self.cv_attr.stop(); self.ws_attr.stop(); self.modules.stop()
        asyncio.wait_for = self.previous_wait_for

    @mocks.sync_test
    async def test_requires_sensor_and_local_calendar_permission(self):
        with self.assertRaises(Unauthorized) as sensor_error:
            await self.api.websocket_get_schedule(self.hass, Connection(set()), self.message)
        self.assertEqual(sensor_error.exception.entity_id, "sensor.car_status")
        with self.assertRaises(Unauthorized) as calendar_error:
            await self.api.websocket_get_schedule(self.hass, Connection({"sensor.car_status"}), self.message)
        self.assertEqual(calendar_error.exception.entity_id, "calendar.car_local")

    @mocks.sync_test
    async def test_private_external_calendar_is_not_queried_without_access(self):
        connection = Connection({"sensor.car_status", "calendar.car_local"})
        await self.api.websocket_get_schedule(self.hass, connection, self.message)
        self.assertTrue(connection.result["calendar_error"])
        self.assertEqual(connection.result["events"], [])
        self.assertFalse(any(domain == "calendar" for domain, action in self.hass.calls))
        allowed = Connection({"sensor.car_status", "calendar.car_local", "calendar.private"})
        await self.api.websocket_get_schedule(self.hass, allowed, self.message)
        self.assertFalse(allowed.result["calendar_error"])
        self.assertEqual(len(allowed.result["events"]), 1)

    @mocks.sync_test
    async def test_range_validation_and_wrong_entity(self):
        connection = Connection({"sensor.car_status", "calendar.car_local"})
        await self.api.websocket_get_schedule(self.hass, connection, {**self.message, "end": "2027-12-01"})
        self.assertEqual(connection.error[0], "invalid_format")
        await self.api.websocket_get_schedule(self.hass, connection, {**self.message, "start": "not-a-date"})
        self.assertEqual(connection.error[0], "invalid_format")
        other = Connection({"sensor.other"})
        await self.api.websocket_get_schedule(self.hass, other, {**self.message, "entity_id": "sensor.other"})
        self.assertEqual(other.error[0], "not_found")

    @mocks.sync_test
    async def test_cars_do_not_cross_permission_boundaries(self):
        self.hass.data["motorvarmare"]["car2"] = mocks.new_controller(self.hass)
        request = {**self.message, "entity_id": "sensor.second_status"}
        with self.assertRaises(Unauthorized) as err:
            await self.api.websocket_get_schedule(self.hass, Connection({"sensor.car_status", "calendar.car_local"}), request)
        self.assertEqual(err.exception.entity_id, "sensor.second_status")
        with self.assertRaises(Unauthorized) as err:
            await self.api.websocket_get_schedule(self.hass, Connection({"sensor.second_status", "calendar.car_local"}), request)
        self.assertEqual(err.exception.entity_id, "calendar.second_local")


if __name__ == "__main__":
    unittest.main()
