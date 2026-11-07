"""Regression coverage for optional automation controls and alerts."""
from datetime import timedelta
import asyncio
import unittest

from test_controller import (Hass, dt,
                             immediate_sleep, immediate_wait_for, new_controller, sync_test)


class AutomationControlsTests(unittest.TestCase):
    def setUp(self):
        self.old_wait_for, self.old_sleep = asyncio.wait_for, asyncio.sleep
        asyncio.wait_for, asyncio.sleep = immediate_wait_for, immediate_sleep
        from datetime import datetime, timezone
        self.now = datetime(2026, 11, 2, 5, 0, tzinfo=timezone.utc)
        dt.utcnow = lambda: self.now
        self.hass = Hass()
        self.item = new_controller(self.hass)

    def tearDown(self):
        asyncio.wait_for, asyncio.sleep = self.old_wait_for, self.old_sleep

    @sync_test
    async def test_skip_active_and_simultaneous_sources_without_deleting(self):
        moment = self.now + timedelta(minutes=30)
        self.item.manual_departure = moment
        await self.item.async_add_local_departure(moment)
        self.assertTrue(self.item.owned)
        await self.item.async_skip_next()
        self.assertFalse(self.item.owned)
        self.assertEqual(self.hass.states["switch.heater"].state, "off")
        self.assertEqual(self.item.manual_departure, moment)
        self.assertEqual(len(self.item.local_departures), 1)
        self.assertEqual(self.item.skipped_departure, moment)
        self.assertFalse(self.item._candidates(self.now))
        self.assertTrue(all(event["suppressed"] for event in self.item.schedule_7_days))
        restored = new_controller(self.hass)
        await restored.async_load()
        await restored.async_update()
        self.assertEqual(restored.skipped_departure, moment)
        self.assertFalse(restored.owned)

    @sync_test
    async def test_skip_can_be_used_on_multiple_departures(self):
        first, second = self.now + timedelta(hours=2), self.now + timedelta(hours=4)
        await self.item.async_add_local_departure(first)
        await self.item.async_add_local_departure(second)
        await self.item.async_skip_next()
        await self.item.async_skip_next()
        self.assertEqual(self.item._candidates(self.now), [])
        self.assertEqual(len(self.item.local_departures), 2)

    @sync_test
    async def test_pause_stops_schedule_but_allows_manual_and_survives_restart(self):
        departure = self.now + timedelta(minutes=30)
        await self.item.async_add_local_departure(departure)
        self.assertTrue(self.item.owned)
        await self.item.async_set_paused(True)
        self.assertFalse(self.item.owned)
        self.assertEqual(self.item.status, "Pausad")
        restored = new_controller(self.hass)
        await restored.async_load()
        await restored.async_update()
        self.assertTrue(restored.automation_paused)
        self.assertFalse(restored.owned)
        await restored.async_start_now()
        self.assertTrue(restored.owned)
        await restored.async_stop_now()
        await restored.async_update()
        self.assertFalse(restored.owned)
        self.assertEqual(restored.status, "Pausad")

    @sync_test
    async def test_resume_time_auto_reenables_schedule(self):
        departure = self.now + timedelta(minutes=45)
        await self.item.async_add_local_departure(departure)
        await self.item.async_set_pause_until(self.now + timedelta(minutes=5))
        await self.item.async_set_paused(True)
        self.assertFalse(self.item.owned)
        self.now += timedelta(minutes=5)
        await self.item.async_update()
        self.assertFalse(self.item.automation_paused)
        self.assertIsNone(self.item.pause_until)
        self.assertTrue(self.item.owned)

    @sync_test
    async def test_failed_pause_stop_cannot_create_restart_resume_marker(self):
        self.item.config["post_departure_enabled"] = True
        self.item.manual_departure = self.now + timedelta(minutes=10)
        await self.item.async_update()
        self.now += timedelta(minutes=15)
        await self.item.async_update()
        self.hass.stop_no_effect = True
        await self.item.async_set_paused(True)
        self.assertTrue(self.item.owned)
        self.assertTrue(self.item._stop_requested)
        self.assertFalse(await self.item.async_shutdown())
        self.assertIsNone(self.item._resume_departure)
        self.hass.stop_no_effect = False
        restored = new_controller(self.hass)
        restored.config["post_departure_enabled"] = True
        await restored.async_load()
        await restored.async_update()
        self.assertFalse(restored.owned)
        self.assertTrue(restored.automation_paused)
        self.assertIsNone(restored._resume_departure)

    @sync_test
    async def test_old_resume_time_rejected_and_unpause_clears_it(self):
        with self.assertRaisesRegex(ValueError, "pause_until_past"):
            await self.item.async_set_pause_until(self.now)
        await self.item.async_set_pause_until(self.now + timedelta(days=2))
        await self.item.async_set_paused(True)
        await self.item.async_set_paused(False)
        self.assertIsNone(self.item.pause_until)

    @sync_test
    async def test_switch_on_must_be_confirmed_and_is_switched_back_off(self):
        original = self.hass.async_call
        async def no_effect(domain, service, data, **kwargs):
            if domain == "switch" and service == "turn_on":
                self.hass.calls.append((domain, service))
                return
            return await original(domain, service, data, **kwargs)
        self.hass.async_call = no_effect
        with self.assertRaisesRegex(ValueError, "turn_on_failed"):
            await self.item.async_start_now()
        self.assertTrue(self.item.owned)
        self.assertTrue(self.item._stop_requested)
        self.assertTrue(self.item._start_unconfirmed)
        self.assertEqual(self.hass.states["switch.heater"].state, "off")
        self.assertIn(("switch", "turn_off"), self.hass.calls)
        # A delayed ON after the failed confirmation must be actively stopped,
        # including after a restart. The safety hold keeps ownership meanwhile.
        self.hass.states["switch.heater"].state = "on"
        restored = new_controller(self.hass)
        await restored.async_load()
        await restored.async_update()
        self.assertTrue(restored.owned)
        self.assertEqual(self.hass.states["switch.heater"].state, "off")
        self.now += timedelta(minutes=2)
        await restored.async_update()
        self.assertFalse(restored.owned)

    @sync_test
    async def test_optional_alerts_are_deduplicated_and_rearm_on_recovery(self):
        self.item.config["operation_alerts_enabled"] = True
        self.hass.states["sensor.outside"].state = "unavailable"
        await self.item.async_update()
        await self.item.async_update()
        alerts = [x for x in self.hass.calls if x == ("persistent_notification", "create")]
        self.assertEqual(len(alerts), 1)
        self.hass.states["sensor.outside"].state = "0"
        await self.item.async_update()
        self.hass.states["sensor.outside"].state = "unavailable"
        await self.item.async_update()
        alerts = [x for x in self.hass.calls if x == ("persistent_notification", "create")]
        self.assertEqual(len(alerts), 2)

    @sync_test
    async def test_staleness_uses_last_reported_and_never_last_changed(self):
        state = self.hass.states["sensor.outside"]
        state.last_changed = self.now - timedelta(days=10)
        self.assertNotIn("temperature_stale", self.item._operational_problems())
        state.last_reported = self.now - timedelta(hours=13)
        self.assertIn("temperature_stale", self.item._operational_problems())
        self.item.config["temperature_max_age_hours"] = 0
        self.assertNotIn("temperature_stale", self.item._operational_problems())

