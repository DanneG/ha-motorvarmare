"""Behavioural tests for extending a running heater session."""
import asyncio
from datetime import datetime, timedelta
import unittest

import test_controller as mocks


class ExtendSessionTests(unittest.TestCase):
    def setUp(self):
        self.wait_for, self.sleep = asyncio.wait_for, asyncio.sleep
        asyncio.wait_for, asyncio.sleep = mocks.immediate_wait_for, mocks.immediate_sleep
        self.now = datetime(2026, 11, 2, 5, 0, tzinfo=mocks.UTC)
        mocks.dt.utcnow = lambda: self.now
        self.hass = mocks.Hass()
        self.item = mocks.new_controller(self.hass)

    def tearDown(self):
        asyncio.wait_for, asyncio.sleep = self.wait_for, self.sleep

    @mocks.sync_test
    async def test_manual_extension_is_bounded_and_survives_a_restart(self):
        await self.item.async_start_now()
        initial = self.item.active_until
        await self.item.async_extend_30()
        self.assertEqual(self.item.active_until, initial + timedelta(minutes=30))
        reloaded = mocks.new_controller(self.hass)
        await reloaded.async_load()
        await reloaded.async_update()
        self.assertEqual(reloaded.active_until, initial + timedelta(minutes=30))
        while reloaded.can_extend:
            await reloaded.async_extend_30()
        self.assertEqual(reloaded.active_until, self.now + timedelta(hours=4))
        with self.assertRaisesRegex(ValueError, 'cannot_extend'):
            await reloaded.async_extend_30()
        self.now += timedelta(hours=4)
        await reloaded.async_update()
        self.assertFalse(reloaded.owned)
        self.assertEqual(self.hass.states['switch.heater'].state, 'off')

    @mocks.sync_test
    async def test_scheduled_extension_continues_after_departure_cleanup(self):
        departure = self.now + timedelta(minutes=10)
        await self.item.async_add_local_departure(departure)
        await self.item.async_extend_30()
        self.assertEqual(self.item.active_until, departure + timedelta(minutes=30))
        self.now = departure + timedelta(minutes=5)
        await self.item.async_update()
        self.assertTrue(self.item.owned)
        self.assertEqual(self.item.local_departures, [])
        self.now = departure + timedelta(minutes=30)
        await self.item.async_update()
        self.assertFalse(self.item.owned)
        self.assertEqual(self.hass.states['switch.heater'].state, 'off')

    @mocks.sync_test
    async def test_clean_restart_resumes_extended_session_on_same_switch(self):
        await self.item.async_start_now()
        await self.item.async_extend_30()
        end = self.item.active_until
        self.now += timedelta(minutes=10)
        await self.item.async_shutdown()
        self.assertEqual(self.hass.states['switch.heater'].state, 'off')
        reloaded = mocks.new_controller(self.hass)
        await reloaded.async_load()
        await reloaded.async_update()
        self.assertTrue(reloaded.owned)
        self.assertEqual(reloaded.active_until, end)
        self.assertEqual(self.hass.states['switch.heater'].state, 'on')

    @mocks.sync_test
    async def test_stop_and_temperature_protection_override_extension(self):
        await self.item.async_start_now()
        await self.item.async_extend_30()
        await self.item.async_stop_now()
        self.assertFalse(self.item.owned)
        with self.assertRaisesRegex(ValueError, 'cannot_extend'):
            await self.item.async_extend_30()
        await self.item.async_start_now()
        await self.item.async_extend_30()
        self.hass.states['sensor.outside'].state = '11'
        self.assertFalse(self.item.can_extend)
        await self.item.async_update()
        self.assertFalse(self.item.owned)
        self.assertEqual(self.hass.states['switch.heater'].state, 'off')

    @mocks.sync_test
    async def test_refuses_external_switch_and_rolls_back_failed_save(self):
        self.hass.states['switch.heater'].state = 'on'
        with self.assertRaisesRegex(ValueError, 'cannot_extend'):
            await self.item.async_extend_30()
        self.hass.states['switch.heater'].state = 'off'
        await self.item.async_start_now()
        original_end = self.item.active_until
        original_save = self.item._save
        async def fail_save():
            raise OSError('storage failed')
        self.item._save = fail_save
        with self.assertRaises(OSError):
            await self.item.async_extend_30()
        self.assertEqual(self.item.active_until, original_end)
        self.assertIsNone(self.item._extended_until)
        self.item._save = original_save

    @mocks.sync_test
    async def test_partial_extension_and_external_off(self):
        self.hass.states['sensor.outside'].state = '-20'
        await self.item.async_start_now()
        await self.item.async_extend_30()
        self.item._extended_until = self.item._started_at + timedelta(hours=3, minutes=50)
        await self.item.async_extend_30()
        self.assertEqual(self.item.active_until, self.item._started_at + timedelta(hours=4))
        self.assertFalse(self.item.can_extend)
        self.hass.states['switch.heater'].state = 'off'
        await self.item.async_update()
        self.assertFalse(self.item.owned)
        self.assertIsNone(self.item._extended_until)

    @mocks.sync_test
    async def test_graceful_restart_does_not_resume_if_too_warm_or_switch_changed(self):
        await self.item.async_start_now()
        await self.item.async_extend_30()
        await self.item.async_shutdown()
        self.hass.states['sensor.outside'].state = '11'
        restored = mocks.new_controller(self.hass)
        await restored.async_load()
        await restored.async_update()
        self.assertFalse(restored.owned)
        self.assertIsNone(restored._resume_extended_until)
        self.hass.states['sensor.outside'].state = '0'
        await restored.async_update()
        self.assertEqual(self.hass.states['switch.heater'].state, 'off')

        await restored.async_start_now()
        await restored.async_extend_30()
        await restored.async_shutdown()
        replacement = mocks.new_controller(self.hass)
        replacement.config['switch_entity'] = 'switch.other'
        self.hass.states['switch.other'] = mocks.State('off')
        await replacement.async_load()
        await replacement.async_update()
        self.assertFalse(replacement.owned)
        self.assertEqual(self.hass.states['switch.other'].state, 'off')
        self.assertIsNone(replacement._resume_extended_until)

    @mocks.sync_test
    async def test_extended_run_remains_until_overlapping_future_departure(self):
        first = self.now + timedelta(minutes=10)
        await self.item.async_add_local_departure(first)
        await self.item.async_extend_30()
        second = first + timedelta(minutes=45)
        await self.item.async_add_local_departure(second)
        self.now = first + timedelta(minutes=30)
        await self.item.async_update()
        self.assertTrue(self.item.owned)
        self.assertEqual(self.item.active_until, second)
        start = self.item._started_at
        self.now = first + timedelta(minutes=35)
        await self.item.async_shutdown()
        restored = mocks.new_controller(self.hass)
        await restored.async_load()
        await restored.async_update()
        self.assertTrue(restored.owned)
        self.assertEqual(restored.active_until, second)
        self.assertEqual(restored._started_at, start)
        # A scheduled run cannot extend the four-hour hard stop.
        self.assertLessEqual(restored.active_until, restored._started_at + timedelta(hours=4))


if __name__ == '__main__':
    unittest.main()
