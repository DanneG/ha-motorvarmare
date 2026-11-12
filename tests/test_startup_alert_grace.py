"""Startup notification grace does not delay heater safety or hide real faults."""
import asyncio
from datetime import datetime, timedelta, timezone
import sys
import types
import unittest

import test_controller as mocks
from test_motorvarmare import controller
from test_motorvarmare.energy import EnergyMonitor


class FakeTimer:
    def __init__(self):
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def cancelled(self):
        return self._cancelled


class FakeLoop:
    def call_later(self, delay, callback):
        return FakeTimer()


class StartupGraceTests(unittest.TestCase):
    def setUp(self):
        self.old_now, self.old_clock = mocks.dt.utcnow, controller._alert_clock
        self.old_wait, self.old_loop = asyncio.wait_for, asyncio.get_running_loop
        asyncio.wait_for = mocks.immediate_wait_for
        asyncio.get_running_loop = lambda: FakeLoop()
        self.now = datetime(2026, 11, 2, 5, 0, tzinfo=timezone.utc)
        self.clock = 1000.0
        mocks.dt.utcnow = lambda: self.now
        controller._alert_clock = lambda: self.clock
        self.events = sys.modules["homeassistant.helpers.event"]
        self.old_track = getattr(self.events, "async_track_state_change_event", None)
        self.listener = None

        def track(hass, entities, callback):
            self.listener = callback
            return lambda: None

        self.events.async_track_state_change_event = track
        self.hass = mocks.Hass()
        self.tasks = []
        self.hass.async_create_task = self.tasks.append
        self.hass.config = types.SimpleNamespace(language="sv")
        self.item = mocks.new_controller(self.hass)
        self.item.config.update({"operation_alerts_enabled": True, "notify_entity": "notify.phone"})

    def tearDown(self):
        if self.item._alert_grace_timer:
            self.item._alert_grace_timer.cancel()
        if self.old_track is None:
            delattr(self.events, "async_track_state_change_event")
        else:
            self.events.async_track_state_change_event = self.old_track
        mocks.dt.utcnow, controller._alert_clock = self.old_now, self.old_clock
        asyncio.wait_for, asyncio.get_running_loop = self.old_wait, self.old_loop
        for task in self.tasks:
            task.close()

    async def drain(self):
        while self.tasks:
            await self.tasks.pop(0)

    @mocks.sync_test
    async def test_current_fault_only_after_grace_and_deduplicated(self):
        self.hass.states["sensor.outside"].state = "unavailable"
        await self.item.async_start()
        await self.drain()
        self.assertEqual(self.hass.calls, [])
        self.assertIn("temperature_unavailable", self.item._operational_problems())
        self.clock += 299
        await self.item._update_operational_alerts()
        self.assertEqual(self.hass.calls, [])
        self.clock += 1
        self.item._recheck_alerts_after_startup()
        await self.drain()
        self.assertEqual(self.hass.calls.count(("persistent_notification", "create")), 1)
        self.assertEqual(self.hass.calls.count(("notify", "send_message")), 1)
        await self.item._update_operational_alerts()
        self.assertEqual(len(self.hass.calls), 2)

    @mocks.sync_test
    async def test_recovered_fault_not_sent_and_new_fault_after_grace_is_sent(self):
        self.hass.states["sensor.outside"].state = "unavailable"
        await self.item.async_start()
        self.hass.states["sensor.outside"].state = "0"
        self.clock += 300
        self.item._recheck_alerts_after_startup()
        await self.drain()
        self.assertEqual(self.hass.calls, [])
        self.hass.states["sensor.outside"].state = "unavailable"
        await self.item._update_operational_alerts()
        self.assertEqual(len(self.hass.calls), 2)

    @mocks.sync_test
    async def test_shutdown_cancels_timer_and_blocks_queued_alerts(self):
        await self.item.async_start()
        await self.drain()
        timer = self.item._alert_grace_timer
        self.assertIsNotNone(timer)
        self.assertTrue(await self.item.async_shutdown())
        self.assertTrue(timer.cancelled())
        self.hass.states["sensor.outside"].state = "unavailable"
        self.clock += 400
        await self.item._update_operational_alerts()
        self.item._recheck_alerts_after_startup()
        await self.drain()
        self.assertEqual(self.hass.calls, [])

    @mocks.sync_test
    async def test_safety_stop_does_not_wait_for_grace(self):
        await self.item.async_start()
        await self.drain()
        await self.item.async_start_now()
        self.assertTrue(self.item.owned)
        self.hass.states["sensor.outside"].state = "11"
        await self.item.async_update()
        self.assertEqual(self.hass.states["switch.heater"].state, "off")
        self.assertIn(("switch", "turn_off"), self.hass.calls)
        self.assertFalse(any(domain in ("persistent_notification", "notify") for domain, _ in self.hass.calls))

    @mocks.sync_test
    async def test_qualified_startup_low_waits_and_is_not_lost_after_window(self):
        allowed = False
        self.hass.states["sensor.power"] = mocks.State("0", "W")
        config = {"switch_entity": "switch.heater", "power_entity": "sensor.power",
                  "power_min_watts": 10, "power_delay_minutes": 0,
                  "power_deviation_enabled": True, "power_expected_min_watts": 20,
                  "power_deviation_delay_minutes": 0, "notify_entity": "notify.phone"}
        monitor = EnergyMonitor(self.hass, self.item.entry, config, lambda: None, lambda: allowed)
        monitor._saw_off = True
        self.hass.states["switch.heater"].state = "on"
        await monitor.async_update()
        self.assertFalse(monitor.alarm_active)
        self.assertFalse(monitor.deviation_alarm_active)
        self.assertEqual(self.hass.calls, [])
        self.now += timedelta(minutes=6)  # short startup windows have expired
        await monitor.async_update()
        allowed = True
        await monitor._flush_deferred_startup_alerts()
        self.assertEqual(self.hass.calls.count(("persistent_notification", "create")), 2)
        self.assertEqual(self.hass.calls.count(("notify", "send_message")), 2)
        await monitor._flush_deferred_startup_alerts()
        self.assertEqual(len(self.hass.calls), 4)

    @mocks.sync_test
    async def test_low_that_recovers_during_grace_never_reappears(self):
        allowed = False
        self.hass.states["sensor.power"] = mocks.State("0", "W")
        config = {"switch_entity": "switch.heater", "power_entity": "sensor.power",
                  "power_min_watts": 10, "power_delay_minutes": 0,
                  "power_deviation_enabled": True, "power_expected_min_watts": 20,
                  "power_deviation_delay_minutes": 0}
        monitor = EnergyMonitor(self.hass, self.item.entry, config, lambda: None, lambda: allowed)
        await monitor.async_start()
        self.hass.states["switch.heater"].state = "on"
        await monitor.async_update()
        self.hass.states["sensor.power"].state = "100"
        self.listener(types.SimpleNamespace(data={"entity_id": "sensor.power", "new_state": self.hass.states["sensor.power"]}))
        await self.drain()
        self.hass.states["sensor.power"].state = "0"  # later unplug is not a startup warning
        self.listener(types.SimpleNamespace(data={"entity_id": "sensor.power", "new_state": self.hass.states["sensor.power"]}))
        await self.drain()
        self.now += timedelta(minutes=6)
        allowed = True
        await monitor._flush_deferred_startup_alerts()
        self.assertEqual(self.hass.calls, [])
        await monitor.async_shutdown()

    @mocks.sync_test
    async def test_failed_mobile_retries_without_duplicate_persistent_alert(self):
        allowed = False
        self.hass.states["sensor.power"] = mocks.State("0", "W")
        config = {"switch_entity": "switch.heater", "power_entity": "sensor.power",
                  "power_min_watts": 10, "power_delay_minutes": 0,
                  "notify_entity": "notify.phone"}
        monitor = EnergyMonitor(self.hass, self.item.entry, config, lambda: None, lambda: allowed)
        monitor._saw_off = True
        self.hass.states["switch.heater"].state = "on"
        await monitor.async_update()
        self.now += timedelta(minutes=6)
        await monitor.async_update()
        self.hass.fail.add(("notify", "send_message"))
        allowed = True
        await monitor._flush_deferred_startup_alerts()
        self.assertTrue(monitor._persistent_sent)
        self.assertFalse(monitor._mobile_sent)
        self.assertIsNotNone(monitor._deferred_low_epoch)
        self.hass.fail.clear()
        monitor._last_attempt["mobile"] = float("-inf")  # after retry interval
        await monitor.async_update()
        self.assertTrue(monitor._mobile_sent)
        self.assertIsNone(monitor._deferred_low_epoch)
        self.assertEqual(self.hass.calls.count(("persistent_notification", "create")), 1)
        self.assertEqual(self.hass.calls.count(("notify", "send_message")), 2)

    @mocks.sync_test
    async def test_deferred_startup_alert_retry_expires(self):
        allowed = False
        self.hass.states["sensor.power"] = mocks.State("0", "W")
        config = {"switch_entity": "switch.heater", "power_entity": "sensor.power",
                  "power_min_watts": 10, "power_delay_minutes": 0,
                  "notify_entity": "notify.phone"}
        monitor = EnergyMonitor(self.hass, self.item.entry, config, lambda: None, lambda: allowed)
        monitor._saw_off = True
        self.hass.states["switch.heater"].state = "on"
        await monitor.async_update()
        self.now += timedelta(minutes=6)
        allowed = True
        self.hass.fail.add(("notify", "send_message"))
        await monitor._flush_deferred_startup_alerts()
        self.assertIsNotNone(monitor._deferred_low_epoch)
        monitor._deferred_alert_retry_until = float("-inf")
        self.hass.fail.clear()
        monitor._last_attempt["mobile"] = float("-inf")
        await monitor.async_update()
        self.assertIsNone(monitor._deferred_low_epoch)
        self.assertFalse(monitor._mobile_sent)
        self.assertEqual(self.hass.calls.count(("notify", "send_message")), 1)

    @mocks.sync_test
    async def test_high_power_is_rechecked_after_grace(self):
        allowed = False
        self.hass.states["sensor.power"] = mocks.State("1000", "W")
        config = {"switch_entity": "switch.heater", "power_entity": "sensor.power",
                  "power_alarm_enabled": False, "power_deviation_enabled": True,
                  "power_expected_max_watts": 500, "power_deviation_delay_minutes": 0,
                  "notify_entity": "notify.phone"}
        monitor = EnergyMonitor(self.hass, self.item.entry, config, lambda: None, lambda: allowed)
        monitor._saw_off = True
        self.hass.states["switch.heater"].state = "on"
        await monitor.async_update()
        self.assertFalse(monitor.deviation_alarm_active)
        self.assertEqual(self.hass.calls, [])
        self.now += timedelta(minutes=5)
        allowed = True
        await monitor.async_update()
        self.assertTrue(monitor.deviation_alarm_active)
        self.assertEqual(self.hass.calls.count(("persistent_notification", "create")), 1)
        self.assertEqual(self.hass.calls.count(("notify", "send_message")), 1)

    @mocks.sync_test
    async def test_calendar_is_refreshed_before_notification_after_grace(self):
        self.item.config["calendar_entity"] = "calendar.work"
        self.hass.fail.add(("calendar", "get_events"))
        await self.item.async_start()
        await self.drain()
        self.assertFalse(self.item._calendar_ok)
        self.hass.calls.clear()
        self.hass.fail.clear()
        self.clock += 300
        self.item._recheck_alerts_after_startup()
        await self.drain()
        self.assertTrue(self.item._calendar_ok)
        self.assertFalse(any(domain in ("persistent_notification", "notify") for domain, _ in self.hass.calls))


if __name__ == "__main__":
    unittest.main()
