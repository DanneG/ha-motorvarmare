"""Exercise the plug pulse against a simulated switch and power sensor."""
import asyncio
from contextlib import nullcontext
from datetime import datetime, timedelta
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

import test_controller as mocks
from test_motorvarmare import cable_test


class CableTestTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.fromisoformat("2026-11-02T20:00:00+00:00")
        self.seconds = 0
        self.hass = mocks.Hass()
        self.item = mocks.new_controller(self.hass)
        self.item.config.update(cable_test_enabled=True, power_entity="sensor.watts",
                                notify_entity="notify.car")
        self.item._alerts_after = 0
        self.item.manual_departure = self.now + timedelta(hours=11)
        self.hass.states["sensor.watts"] = mocks.State("0", "W")
        self.hass.states["sensor.watts"].last_reported = self.now - timedelta(days=1)
        self.on_sleep = None
        self.switch_events = None
        self.before_command = None
        self.notifications = []
        self.loop = SimpleNamespace(time=lambda: self.seconds, call_later=Mock(return_value=Mock()))
        original_call = self.hass.async_call

        async def command(domain, action, data, **kwargs):
            if domain == "switch" and self.before_command:
                self.before_command(action)
            await original_call(domain, action, data, **kwargs)
            if domain == "switch":
                plug = self.hass.states[data["entity_id"]]
                plug.last_changed = self.now
                if self.switch_events:
                    self.switch_events(data["entity_id"], plug)
            else:
                self.notifications.append((domain, data))

        async def tick(seconds):
            self.seconds += seconds
            self.now += timedelta(seconds=seconds)
            if self.on_sleep:
                await self.on_sleep()

        self.hass.async_call = command
        for change in (patch.object(mocks.dt, "utcnow", lambda: self.now),
                       patch.object(asyncio, "get_running_loop", lambda: self.loop),
                       patch.object(asyncio, "wait_for", mocks.immediate_wait_for),
                       patch.object(asyncio, "timeout_at", lambda deadline: nullcontext()),
                       patch.object(asyncio, "sleep", tick)):
            change.start()
            self.addCleanup(change.stop)

    def report(self, value, unit="W"):
        power = mocks.State(value, unit)
        power.last_reported = self.now
        self.hass.states["sensor.watts"] = power
        if self.switch_events:
            self.switch_events("sensor.watts", power)

    @mocks.sync_test
    async def test_fresh_kw_stops_early_and_test_is_absent_from_heating_history(self):
        events = sys.modules["homeassistant.helpers.event"]
        snapshots = []
        def track(hass, entities, callback):
            self.switch_events = lambda entity, state: callback(SimpleNamespace(data={"entity_id": entity, "new_state": state}))
            return lambda: None
        self.item.energy._queue_update = snapshots.append
        with patch.object(events, "async_track_state_change_event", track, create=True):
            await self.item.energy.async_start()
        async def sample():
            self.report("0" if self.seconds < 1 else "1.1", "kW")
            await self.item.energy.async_update()
        self.on_sleep = sample

        def check_journal(action):
            if action == "turn_on":
                saved = self.hass.storage["motorvarmare.car1"]
                self.assertEqual(saved["cable_test"]["switch"], "switch.heater")
                self.assertFalse(saved["owned"])
        self.before_command = check_journal
        await self.item.async_test_cable()
        for snapshot in snapshots:
            await self.item.energy.async_update(snapshot)
        self.assertEqual(self.item.cable_test_result, "connected")
        self.assertLess(self.seconds, 10)
        self.assertFalse(self.item.owned)
        self.assertFalse(self.item.energy.heating_history)
        self.assertEqual(self.hass.states["switch.heater"].state, "off")
        self.assertFalse(self.notifications)
        # A later genuine switch-on is observed normally.
        self.before_command = None
        await self.hass.async_call("switch", "turn_on", {"entity_id": "switch.heater"})
        await self.item.energy.async_update(snapshots[-1])
        self.assertTrue(self.item.energy._session_active)

    @mocks.sync_test
    async def test_repeated_zero_report_reminds_once_after_switch_off_and_survives_reload(self):
        async def sample():
            self.report("0")  # Same numeric state as before ON, but a new report.
        self.on_sleep = sample
        await self.item.async_update()
        await self.item.async_test_cable()
        restored = mocks.new_controller(self.hass)
        restored.config.update(self.item.config)
        restored._alerts_after = 0
        await restored.async_load()
        await restored.async_update()
        self.assertEqual(restored.cable_test_at, self.item.cable_test_at)
        self.assertEqual(restored.cable_test_result, "low_power")
        self.assertEqual(self.seconds, 10)
        self.assertEqual(self.hass.calls, [("switch", "turn_on"), ("switch", "turn_off"),
                                          ("persistent_notification", "create"), ("notify", "send_message")])

    @mocks.sync_test
    async def test_manual_recheck_after_cooldown_auto_and_reminder_are_daily(self):
        async def sample_low():
            self.report("0")
        self.on_sleep = sample_low
        await self.item.async_test_cable()
        await self.item.async_test_cable()
        self.now += timedelta(minutes=1)
        await self.item.async_update()
        self.assertEqual(self.hass.calls.count(("switch", "turn_on")), 1)
        await self.item.async_test_cable()
        self.assertEqual(self.hass.calls.count(("switch", "turn_on")), 2)
        self.assertEqual(len(self.notifications), 2)  # HA and the optional mobile.
        self.now += timedelta(minutes=1)
        async def sample_high():
            self.report("600")
        self.on_sleep = sample_high
        await self.item.async_test_cable()
        self.assertEqual(self.item.cable_test_result, "connected")
        self.assertEqual(self.hass.calls[-1], ("persistent_notification", "dismiss"))

    @mocks.sync_test
    async def test_early_zero_without_another_report_is_inconclusive(self):
        async def sample_once():
            if self.seconds >= 2:
                self.report("0")
                self.on_sleep = None
        self.on_sleep = sample_once
        await self.item.async_test_cable()
        self.assertEqual(self.item.cable_test_result, "inconclusive")
        self.assertFalse(self.notifications)

    @mocks.sync_test
    async def test_one_late_zero_is_low_even_with_zero_threshold(self):
        self.item.config["power_min_watts"] = 0
        async def sample_once():
            if self.seconds >= 7:
                self.report("0")
                self.on_sleep = None
        self.on_sleep = sample_once
        await self.item.async_test_cable()
        self.assertEqual(self.item.cable_test_result, "low_power")

    @mocks.sync_test
    async def test_stale_nonzero_or_zero_and_unavailable_are_inconclusive(self):
        for reading in ("0", "1000", "unavailable"):
            self.item._cable.at = None
            self.hass.states["sensor.watts"].state = reading
            if reading == "unavailable":
                async def sample():
                    self.report("unavailable")
                self.on_sleep = sample
            await self.item.async_test_cable()
            self.assertEqual(self.item.cable_test_result, "inconclusive", reading)
        self.assertFalse(self.notifications)

    @mocks.sync_test
    async def test_grace_disabled_unconfigured_external_on_and_routine_only(self):
        self.item._alerts_after = float("inf")
        await self.item.async_test_cable()
        self.item._alerts_after = 0
        for change in ({"cable_test_enabled": False}, {"power_entity": None}):
            with patch.dict(self.item.config, change):
                await self.item.async_test_cable()
        self.hass.states["switch.heater"].state = "on"
        await self.item.async_test_cable()
        self.hass.states["switch.heater"].state = "off"
        self.item.config["cable_test_automatic"] = False
        await self.item.async_update()
        self.assertFalse(self.hass.calls)
        await self.item.async_test_cable()
        self.assertEqual(self.hass.calls, [("switch", "turn_on"), ("switch", "turn_off")])

    @mocks.sync_test
    async def test_failed_storage_or_external_on_during_save_never_operates_plug(self):
        with patch.object(self.item, "_save", AsyncMock(side_effect=OSError)):
            with self.assertRaises(OSError):
                await self.item.async_test_cable()
        self.assertIsNone(self.item.cable_test_at)
        save = self.item._save
        async def competing_start():
            await save()
            self.hass.states["switch.heater"].state = "on"
        with patch.object(self.item, "_save", competing_start):
            await self.item.async_test_cable()
        self.assertFalse(self.hass.calls)
        self.assertIsNone(self.hass.storage["motorvarmare.car1"]["cable_test"]["switch"])

    @mocks.sync_test
    async def test_unconfirmed_stop_retried_even_after_disabled_reload_on_different_switch(self):
        self.hass.stop_no_effect = True
        await self.item.async_test_cable()
        self.assertEqual(self.item.cable_test_result, "pending")
        self.assertFalse(await self.item.async_shutdown())
        self.assertTrue(self.loop.call_later.called)
        self.now += timedelta(minutes=3)
        self.hass.stop_no_effect = False
        self.hass.states["switch.other"] = mocks.State("on")
        restored = mocks.new_controller(self.hass)
        restored.config.update(switch_entity="switch.other", cable_test_enabled=False)
        await restored.async_load()
        await restored.async_update()
        self.assertEqual(restored.cable_test_result, "inconclusive")
        self.assertIsNone(self.hass.storage["motorvarmare.car1"]["cable_test"]["switch"])
        self.assertEqual(self.hass.states["switch.heater"].state, "off")
        self.assertEqual(self.hass.states["switch.other"].state, "on")

    @mocks.sync_test
    async def test_measured_low_survives_failed_stop_and_reminds_once_when_recovered(self):
        async def sample():
            self.report("0.005", "kW")
        self.on_sleep = sample
        self.hass.stop_no_effect = True
        await self.item.async_test_cable()
        self.assertEqual(self.item.cable_test_result, "pending")
        self.assertFalse(self.notifications)
        self.now += timedelta(minutes=3)
        self.hass.stop_no_effect = False
        restored = mocks.new_controller(self.hass)
        restored.config.update(self.item.config)
        restored._alerts_after = 0
        await restored.async_load()
        await restored.async_update()
        await restored.async_update()
        self.assertEqual(restored.cable_test_result, "low_power")
        self.assertEqual(len(self.notifications), 2)

    @mocks.sync_test
    async def test_failed_on_keeps_guard_for_late_on_and_blocks_manual_heat(self):
        self.hass.fail.add(("switch", "turn_on"))
        with self.assertLogs(cable_test.__name__, "WARNING"):
            await self.item.async_test_cable()
        self.assertEqual(self.item.cable_test_result, "pending")
        with self.assertRaisesRegex(ValueError, "already_on"):
            await self.item.async_start_now()
        self.hass.states["switch.heater"].state = "on"  # Delayed plug response.
        self.now += timedelta(minutes=3)
        await self.item.async_update()
        self.assertEqual(self.hass.states["switch.heater"].state, "off")
        self.assertEqual(self.item.cable_test_result, "inconclusive")
        self.assertFalse(self.notifications)

    @mocks.sync_test
    async def test_cancelling_while_sampling_immediately_stops(self):
        async def cancel():
            raise asyncio.CancelledError
        self.on_sleep = cancel
        with self.assertRaises(asyncio.CancelledError):
            await self.item.async_test_cable()
        self.assertEqual(self.hass.states["switch.heater"].state, "off")
        self.assertEqual(self.item.cable_test_result, "inconclusive")

    @mocks.sync_test
    async def test_ha_shutdown_does_not_operate_ordinary_heat_or_start_another_test(self):
        self.hass.states["switch.heater"].state = "on"
        await self.item.async_stop_cable_tests()
        self.hass.states["switch.heater"].state = "off"
        await self.item.async_test_cable()
        self.assertFalse(self.hass.calls)

    @mocks.sync_test
    async def test_ha_shutdown_stops_an_interrupted_test_before_plugin_teardown(self):
        self.item._cable.restore({"switch": "switch.heater", "result": "pending",
                                  "at": (self.now - timedelta(minutes=5)).isoformat()})
        self.hass.states["switch.heater"].state = "on"
        await self.item.async_stop_cable_tests()
        self.assertEqual(self.hass.states["switch.heater"].state, "off")
        self.assertIsNone(self.item._cable.switch)
