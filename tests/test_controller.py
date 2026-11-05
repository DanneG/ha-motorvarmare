"""Isolated scheduling tests; these do not replace testing in Home Assistant."""
from __future__ import annotations

import copy
import asyncio
from datetime import datetime, time, timedelta, timezone
import importlib
import logging
from pathlib import Path
import sys
import types
import unittest


ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "motorvarmare"
LOCAL = timezone(timedelta(hours=1))  # Stockholm in November; DST is not tested here.
UTC = timezone.utc


def module(name):
    result = types.ModuleType(name)
    sys.modules[name] = result
    return result


# Only Home Assistant APIs needed by the controller are replaced here.
module("homeassistant")
const = module("homeassistant.const")
const.ATTR_ENTITY_ID, const.STATE_ON, const.STATE_OFF = "entity_id", "on", "off"
const.UnitOfTemperature = types.SimpleNamespace(CELSIUS="°C", FAHRENHEIT="°F")
core = module("homeassistant.core")
core.callback = lambda function: function
module("homeassistant.helpers")
module("homeassistant.helpers.dispatcher").async_dispatcher_send = lambda *args: None
module("homeassistant.helpers.event").async_track_time_interval = lambda *args: lambda: None
module("homeassistant.util")
dt = module("homeassistant.util.dt")
dt.utcnow = lambda: datetime(2026, 11, 2, 5, 0, tzinfo=UTC)
dt.get_default_time_zone = lambda: LOCAL
dt.as_utc = lambda value: (value if value.tzinfo else value.replace(tzinfo=LOCAL)).astimezone(UTC)
dt.as_local = lambda value: (value if value.tzinfo else value.replace(tzinfo=LOCAL)).astimezone(LOCAL)
dt.parse_datetime = lambda value: datetime.fromisoformat(value.replace("Z", "+00:00"))


class Store:
    def __init__(self, hass, version, key):
        self.hass, self.key = hass, key

    async def async_load(self):
        return copy.deepcopy(self.hass.storage.get(self.key))

    async def async_save(self, data):
        self.hass.storage[self.key] = copy.deepcopy(data)


module("homeassistant.helpers.storage").Store = Store
package = module("test_motorvarmare")
package.__path__ = [str(ROOT)]
controller = importlib.import_module("test_motorvarmare.controller")
logging.getLogger(controller.__name__).disabled = True


class State:
    def __init__(self, state, unit=None):
        self.state = state
        self.attributes = {} if unit is None else {"unit_of_measurement": unit}


class Hass:
    def __init__(self):
        self.storage = {}
        self.states = {"switch.heater": State("off"), "sensor.outside": State("0", "°C")}
        self.services = self
        self.calls = []
        self.fail = set()
        self.events = []
        self.stop_no_effect = False

    async def async_call(self, domain, action, data, **kwargs):
        self.calls.append((domain, action))
        if (domain, action) in self.fail:
            raise RuntimeError("Simulated service failure")
        if domain == "switch":
            if action != "turn_off" or not self.stop_no_effect:
                self.states[data["entity_id"]].state = "on" if action == "turn_on" else "off"
        if domain == "calendar":
            return {data["entity_id"]: {"events": self.events}}


def new_controller(hass, calendar=""):
    entry = types.SimpleNamespace(
        entry_id="car1", title="Bil 1", options={},
        data={"switch_entity": "switch.heater", "temperature_entity": "sensor.outside",
              "calendar_entity": calendar, "tag": "#bil1"},
    )
    instance = controller.HeaterController(hass, entry)
    instance._calendar_checked = float("-inf")
    return instance


class HelperTests(unittest.TestCase):
    def test_temperature_boundaries(self):
        for temperature, expected in [(-200, 240), (-20, 60), (-15, 53), (-14.9, 53),
                                      (0, 30), (0.1, 30), (9.9, 16), (10, 15), (20, 0), (25, 0)]:
            with self.subTest(temperature=temperature):
                self.assertEqual(controller.duration_for_temperature(temperature), expected)

    def test_tag_matching_case_and_suffix(self):
        self.assertTrue(controller.tagged("Kör #BIL1!", "#bil1"))
        self.assertFalse(controller.tagged("Kör #bil10", "#bil1"))
        self.assertFalse(controller.tagged("Vad som helst", ""))

    def test_exact_calendar_title_is_whole_title_case_insensitive(self):
        match = controller.calendar_event_matches
        self.assertTrue(match("  till jobbet  ", "", "TILL JOBBET, ÅK HEM", "", ""))
        self.assertTrue(match("ÅK HEM", "", "TILL JOBBET\nåk hem", "", ""))
        self.assertFalse(match("TILL JOBBET extra", "", "TILL JOBBET", "", ""))
        self.assertFalse(match("TILL  JOBBET", "", "TILL JOBBET", "", ""))
        self.assertFalse(match("RESA", "TILL JOBBET", "TILL JOBBET", "", ""))

    def test_multiple_keywords_use_word_boundaries_in_both_fields(self):
        match = controller.calendar_event_matches
        keywords = "#bil1, ÅK, till jobbet\n#värmare"
        self.assertTrue(match("Åk till stan", "", "", keywords, ""))
        self.assertTrue(match("RESA", "På väg till jobbet!", "", keywords, ""))
        self.assertTrue(match("RESA", "#VÄRMARE", "", keywords, ""))
        self.assertFalse(match("Biljobb", "#bil10", "", keywords, ""))
        self.assertFalse(match("Åker", "till jobbetextra", "", keywords, ""))
        # Migrated legacy hash tags retain the earlier matching behavior.
        self.assertTrue(match("x#bil1", "", "", keywords, ""))

    def test_legacy_tag_and_invalid_values(self):
        match = controller.calendar_event_matches
        # Existing tags keep their earlier preceding-character semantics.
        self.assertTrue(match("RESA", "x#bil1!", "", "", "#bil1"))
        self.assertFalse(match("RESA", "#bil10", "", "", "#bil1"))
        self.assertFalse(match(None, None, None, "none", None))
        self.assertFalse(match(42, [], ["42"], 42, 42))
        self.assertTrue(match("Åk", None, [], "åk", None))


def sync_test(function):
    """Run a coroutine whose mocked I/O completes synchronously, with no sockets."""
    def wrapper(self):
        coroutine = function(self)
        try:
            coroutine.send(None)
        except StopIteration:
            return
        finally:
            coroutine.close()
        raise AssertionError("A mock unexpectedly suspended the coroutine")
    return wrapper


async def immediate_wait_for(awaitable, timeout):
    return await awaitable


async def immediate_sleep(seconds):
    pass


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.original_wait_for = asyncio.wait_for
        self.original_sleep = asyncio.sleep
        asyncio.wait_for = immediate_wait_for
        asyncio.sleep = immediate_sleep
        self.now = datetime(2026, 11, 2, 5, 0, tzinfo=UTC)  # Monday 06:00 locally
        dt.utcnow = lambda: self.now
        self.hass = Hass()
        self.item = new_controller(self.hass)

    def tearDown(self):
        asyncio.wait_for = self.original_wait_for
        asyncio.sleep = self.original_sleep

    @sync_test
    async def test_weekly_and_manual_are_sorted_and_local(self):
        self.item.weekly_enabled[0] = True
        self.item.weekly_times[0] = time(7, 0)
        self.item.manual_departure = self.now + timedelta(minutes=15)
        results = self.item._candidates(self.now)
        self.assertEqual(results[0], (self.item.manual_departure, "Manuell"))
        self.assertEqual(results[1], (self.now + timedelta(hours=1), "Veckoschema"))

    @sync_test
    async def test_multiple_local_departures_persist_and_can_be_removed_individually(self):
        first = self.now + timedelta(hours=1)
        second = self.now + timedelta(hours=3)
        first_id = await self.item.async_add_local_departure(first, "Jobb")
        second_id = await self.item.async_add_local_departure(second, "Ärende")
        self.assertNotEqual(first_id, second_id)
        replacement = new_controller(self.hass)
        await replacement.async_load()
        self.assertEqual([item["uid"] for item in replacement.local_departures], [first_id, second_id])
        schedule = replacement.schedule_7_days
        self.assertEqual([item["departure"] for item in schedule], [first.isoformat(), second.isoformat()])
        self.assertEqual(schedule[0]["start"], (first - timedelta(minutes=30)).isoformat())
        self.assertEqual(schedule[1]["summary"], "Ärende")
        self.assertTrue(all(item["removable"] for item in schedule))
        await replacement.async_delete_local_departure(first_id)
        self.assertEqual([item["uid"] for item in replacement.local_departures], [second_id])
        with self.assertRaisesRegex(ValueError, "departure_not_found"):
            await replacement.async_delete_local_departure(first_id)

    @sync_test
    async def test_local_calendar_rejects_past_and_deleting_active_departure_stops(self):
        with self.assertRaisesRegex(ValueError, "departure_past"):
            await self.item.async_add_local_departure(self.now - timedelta(minutes=1))
        event_id = await self.item.async_add_local_departure(self.now + timedelta(minutes=5))
        self.assertTrue(self.item.owned)
        await self.item.async_delete_local_departure(event_id)
        self.assertFalse(self.item.owned)
        self.assertEqual(self.hass.states["switch.heater"].state, "off")

    @sync_test
    async def test_zero_duration_has_no_planned_start(self):
        self.hass.states["sensor.outside"].state = "20"
        await self.item.async_add_local_departure(self.now + timedelta(hours=2))
        self.assertEqual(self.item.schedule_7_days[0]["duration_minutes"], 0)
        self.assertIsNone(self.item.schedule_7_days[0]["start"])
        self.assertNotIn(("switch", "turn_on"), self.hass.calls)

    @sync_test
    async def test_manual_start_then_stop_and_persist(self):
        self.item.manual_departure = self.now + timedelta(minutes=25)
        await self.item.async_update()
        self.assertTrue(self.item.owned)
        self.assertEqual(self.hass.states["switch.heater"].state, "on")
        self.assertTrue(next(iter(self.hass.storage.values()))["owned"])
        self.now += timedelta(minutes=26)
        await self.item.async_update()
        self.assertFalse(self.item.owned)
        self.assertEqual(self.hass.states["switch.heater"].state, "off")
        self.assertFalse(next(iter(self.hass.storage.values()))["owned"])

    @sync_test
    async def test_failed_stop_keeps_ownership_and_retries(self):
        self.item.manual_departure = self.now + timedelta(minutes=5)
        await self.item.async_update()
        self.hass.fail.add(("switch", "turn_off"))
        self.now += timedelta(minutes=6)
        await self.item.async_update()
        self.assertTrue(self.item.owned)
        self.assertEqual(self.hass.states["switch.heater"].state, "on")
        self.assertIn("brytaren", self.item.error)
        self.hass.fail.clear()
        await self.item.async_update()
        self.assertFalse(self.item.owned)
        self.assertEqual(self.hass.states["switch.heater"].state, "off")

    @sync_test
    async def test_unconfirmed_stop_retains_ownership(self):
        self.item.manual_departure = self.now + timedelta(minutes=5)
        await self.item.async_update()
        self.hass.stop_no_effect = True
        self.now += timedelta(minutes=6)
        await self.item.async_update()
        self.assertTrue(self.item.owned)
        self.assertTrue(next(iter(self.hass.storage.values()))["owned"])
        self.assertEqual(self.hass.states["switch.heater"].state, "on")
        self.hass.stop_no_effect = False
        await self.item.async_update()
        self.assertFalse(self.item.owned)
        self.assertEqual(self.hass.states["switch.heater"].state, "off")

    @sync_test
    async def test_manual_off_suppresses_restart_for_same_departure(self):
        self.item.manual_departure = self.now + timedelta(minutes=30)
        await self.item.async_update()
        self.hass.states["switch.heater"].state = "off"
        await self.item.async_update()
        await self.item.async_update()
        self.assertFalse(self.item.owned)
        self.assertEqual(self.hass.calls.count(("switch", "turn_on")), 1)

    @sync_test
    async def test_failed_calendar_retains_active_departure_until_due(self):
        self.item = new_controller(self.hass, "calendar.test")
        departure = self.now + timedelta(minutes=30)
        self.hass.events = [{"start": departure.isoformat(), "summary": "Åk #bil1"}]
        await self.item.async_update()
        self.assertTrue(self.item.owned)
        self.hass.fail.add(("calendar", "get_events"))
        self.item._calendar_checked = float("-inf")
        self.now += timedelta(minutes=5)
        await self.item.async_update()
        self.assertTrue(self.item.owned)
        self.assertFalse(self.item._calendar_ok)
        self.assertEqual(self.hass.states["switch.heater"].state, "on")
        self.now = departure + timedelta(seconds=1)
        await self.item.async_update()
        self.assertFalse(self.item.owned)
        self.assertEqual(self.hass.states["switch.heater"].state, "off")

    @sync_test
    async def test_calendar_ignores_all_day_and_nonmatching_events(self):
        self.item = new_controller(self.hass, "calendar.test")
        self.hass.events = [
            {"start": "2026-11-02", "summary": "#bil1"},
            {"start": (self.now + timedelta(minutes=10)).isoformat(), "summary": "#bil10"},
            {"start": (self.now + timedelta(hours=3)).isoformat(), "description": "#BIL1"},
        ]
        await self.item.async_update()
        self.assertEqual(self.item.next_departure, self.now + timedelta(hours=3))
        self.assertEqual(self.item.source, "Kalender")
        self.assertFalse(self.item.owned)

    @sync_test
    async def test_calendar_accepts_iso_and_space_datetime_but_not_dates(self):
        self.item = new_controller(self.hass, "calendar.test")
        departure = self.now + timedelta(hours=3)
        self.hass.events = [
            {"start": departure.date().isoformat(), "summary": "#bil1"},
            {"start": departure.isoformat(sep=" "), "summary": "#bil1"},
            {"start": departure + timedelta(hours=1), "summary": "#bil1"},
        ]
        await self.item._read_calendar(self.now)
        self.assertTrue(self.item._calendar_ok)
        self.assertEqual(self.item._calendar_events, [
            (departure, "Kalender"), (departure + timedelta(hours=1), "Kalender")
        ])

    @sync_test
    async def test_failed_calendar_retries_sooner_and_clears_error(self):
        self.item = new_controller(self.hass, "calendar.test")
        self.hass.fail.add(("calendar", "get_events"))
        await self.item.async_update()
        self.assertIn("Kalendern kan inte läsas", self.item.error)
        self.assertFalse(self.item._calendar_ok)
        self.hass.fail.clear()
        # After a failure, retry on the next scheduled minute, not after 5 min.
        self.item._calendar_checked -= 31
        await self.item.async_update()
        self.assertTrue(self.item._calendar_ok)
        self.assertIsNone(self.item.error)
        self.assertEqual(self.hass.calls.count(("calendar", "get_events")), 2)

    @sync_test
    async def test_calendar_timeout_produces_explanatory_error(self):
        self.item = new_controller(self.hass, "calendar.test")
        async def timeout(*args, **kwargs):
            raise TimeoutError()
        self.hass.async_call = timeout
        await self.item.async_update()
        self.assertFalse(self.item._calendar_ok)
        self.assertIn("svarade inte i tid", self.item.error)

    @sync_test
    async def test_calendar_matches_exact_titles_or_keywords_or_legacy_tag(self):
        self.item = new_controller(self.hass, "calendar.test")
        self.item.config.update({"event_titles": "TILL JOBBET, TILL HEMMET", "event_keywords": "#bil2, tjänsteresa"})
        self.hass.events = [
            None,
            {"start": "2026-11-02", "summary": "TILL JOBBET"},
            {"start": (self.now + timedelta(minutes=10)).isoformat(), "summary": "TILL JOBBET extra"},
            {"start": (self.now + timedelta(minutes=20)).isoformat(), "summary": "Åk på tjänsteresande"},
            {"start": (self.now + timedelta(minutes=30)).isoformat(), "summary": " till jobbet "},
            {"start": (self.now + timedelta(minutes=40)).isoformat(), "description": "#BIL2"},
            {"start": (self.now + timedelta(minutes=50)).isoformat(), "summary": "#bil1"},
        ]
        await self.item._read_calendar(self.now)
        self.assertEqual(self.item._calendar_events, [
            (self.now + timedelta(minutes=30), "Kalender"),
            (self.now + timedelta(minutes=40), "Kalender"),
            (self.now + timedelta(minutes=50), "Kalender"),
        ])

    @sync_test
    async def test_blank_legacy_tag_does_not_use_default_tag(self):
        self.item = new_controller(self.hass, "calendar.test")
        self.item.config.update({"tag": "", "event_titles": "TILL JOBBET", "event_keywords": ""})
        self.hass.events = [
            {"start": (self.now + timedelta(minutes=5)).isoformat(), "summary": "#motorvarmare"},
            {"start": (self.now + timedelta(minutes=10)).isoformat(), "summary": "TILL JOBBET"},
        ]
        await self.item._read_calendar(self.now)
        self.assertEqual(self.item._calendar_events, [(self.now + timedelta(minutes=10), "Kalender")])

    @sync_test
    async def test_preexisting_on_switch_is_not_claimed(self):
        self.hass.states["switch.heater"].state = "on"
        self.item.manual_departure = self.now + timedelta(minutes=10)
        await self.item.async_update()
        self.assertFalse(self.item.owned)
        self.assertNotIn(("switch", "turn_on"), self.hass.calls)
        self.now += timedelta(minutes=11)
        await self.item.async_update()
        self.assertEqual(self.hass.states["switch.heater"].state, "on")

    @sync_test
    async def test_invalid_temperature_prevents_start(self):
        self.hass.states["sensor.outside"] = State("unavailable", "°C")
        self.item.manual_departure = self.now + timedelta(minutes=5)
        await self.item.async_update()
        self.assertFalse(self.item.owned)
        self.assertNotIn(("switch", "turn_on"), self.hass.calls)

    @sync_test
    async def test_fahrenheit_temperature_is_converted(self):
        self.hass.states["sensor.outside"] = State("32", "°F")
        self.item.manual_departure = self.now + timedelta(minutes=25)
        await self.item.async_update()
        self.assertEqual(self.item.temperature, 0)
        self.assertEqual(self.item.duration_minutes, 30)
        self.assertTrue(self.item.owned)

    @sync_test
    async def test_start_now_uses_formula_and_stops_after_restart(self):
        self.hass.states["sensor.outside"] = State("-10", "°C")
        await self.item.async_start_now()
        self.assertTrue(self.item.owned)
        self.assertEqual(self.item.active_until, self.now + timedelta(minutes=45))
        replacement = new_controller(self.hass)
        await replacement.async_load()
        self.assertTrue(replacement.owned)
        self.now += timedelta(minutes=20)
        await replacement.async_update()
        self.assertTrue(replacement.owned)
        self.assertEqual(self.hass.states["switch.heater"].state, "on")
        self.now += timedelta(minutes=25)
        await replacement.async_update()
        self.assertFalse(replacement.owned)
        self.assertEqual(self.hass.states["switch.heater"].state, "off")

    @sync_test
    async def test_start_now_rejects_existing_on_unavailable_and_zero_duration(self):
        self.hass.states["switch.heater"].state = "on"
        with self.assertRaisesRegex(ValueError, "already_on"):
            await self.item.async_start_now()
        self.assertFalse(self.item.owned)
        self.hass.states["switch.heater"].state = "off"
        self.hass.states["sensor.outside"].state = "unavailable"
        with self.assertRaisesRegex(ValueError, "temperature_unavailable"):
            await self.item.async_start_now()
        self.hass.states["sensor.outside"].state = "20"
        with self.assertRaisesRegex(ValueError, "zero_runtime"):
            await self.item.async_start_now()
        self.assertNotIn(("switch", "turn_on"), self.hass.calls)

    @sync_test
    async def test_start_now_does_not_leave_ownership_when_start_fails_off(self):
        self.hass.fail.add(("switch", "turn_on"))
        with self.assertRaisesRegex(ValueError, "turn_on_failed"):
            await self.item.async_start_now()
        self.assertFalse(self.item.owned)
        self.assertEqual(self.hass.states["switch.heater"].state, "off")

    @sync_test
    async def test_stop_now_prevents_restarting_scheduled_run(self):
        self.item.manual_departure = self.now + timedelta(minutes=10)
        await self.item.async_update()
        await self.item.async_stop_now()
        self.assertFalse(self.item.owned)
        await self.item.async_update()
        self.assertEqual(self.hass.states["switch.heater"].state, "off")
        self.assertEqual(self.hass.calls.count(("switch", "turn_on")), 1)

    @sync_test
    async def test_stop_suppresses_simultaneous_sources_and_overlapping_later_departure(self):
        self.item = new_controller(self.hass, "calendar.test")
        first = self.now + timedelta(minutes=20)
        second = self.now + timedelta(minutes=40)
        later = self.now + timedelta(minutes=100)
        self.item.manual_departure = first
        self.item.weekly_enabled[0] = True
        self.item.weekly_times[0] = time(6, 20)
        self.hass.events = [
            {"start": first.isoformat(), "summary": "#bil1"},
            {"start": second.isoformat(), "summary": "#bil1"},
            {"start": later.isoformat(), "summary": "#bil1"},
        ]
        await self.item.async_add_local_departure(first)
        self.assertTrue(self.item.owned)
        await self.item.async_stop_now()
        schedule = self.item.schedule_7_days
        self.assertTrue(all(row["suppressed"] for row in schedule if row["departure"] in (first.isoformat(), second.isoformat())))
        self.assertFalse(next(row for row in schedule if row["departure"] == later.isoformat())["suppressed"])
        replacement = new_controller(self.hass, "calendar.test")
        await replacement.async_load()
        self.now += timedelta(minutes=21)
        await replacement.async_update()
        self.assertFalse(replacement.owned)
        self.assertEqual(self.hass.calls.count(("switch", "turn_on")), 1)
        self.now += timedelta(minutes=20)
        await replacement.async_update()
        self.assertFalse(replacement.owned)
        self.now += timedelta(minutes=30)
        await replacement.async_update()
        self.assertTrue(replacement.owned)
        self.assertEqual(self.hass.calls.count(("switch", "turn_on")), 2)

    @sync_test
    async def test_temperature_drop_extends_suppression_to_newly_overlapping_window(self):
        first = self.now + timedelta(minutes=20)
        second = self.now + timedelta(minutes=65)
        await self.item.async_add_local_departure(first)
        await self.item.async_add_local_departure(second)
        await self.item.async_stop_now()
        self.assertFalse(next(row for row in self.item.schedule_7_days if row["departure"] == second.isoformat())["suppressed"])
        # At 0 C the next start has a gap; at -10 C it touches the first end.
        self.hass.states["sensor.outside"].state = "-10"
        self.now += timedelta(minutes=21)
        await self.item.async_update()
        self.assertTrue(next(row for row in self.item.schedule_7_days if row["departure"] == second.isoformat())["suppressed"])
        self.assertFalse(self.item.owned)
        self.assertEqual(self.hass.calls.count(("switch", "turn_on")), 1)

    @sync_test
    async def test_physical_switch_off_suppresses_overlapping_schedules(self):
        first = self.now + timedelta(minutes=20)
        second = self.now + timedelta(minutes=40)
        await self.item.async_add_local_departure(first)
        await self.item.async_add_local_departure(second)
        self.assertTrue(self.item.owned)
        self.hass.states["switch.heater"].state = "off"
        await self.item.async_update()
        self.now += timedelta(minutes=21)
        await self.item.async_update()
        self.assertFalse(self.item.owned)
        self.assertEqual(self.hass.calls.count(("switch", "turn_on")), 1)

    @sync_test
    async def test_calendar_outage_keeps_overlapping_departure_suppressed_after_recovery(self):
        self.item = new_controller(self.hass, "calendar.test")
        first = self.now + timedelta(minutes=20)
        second = self.now + timedelta(minutes=40)
        self.hass.events = [{"start": moment.isoformat(), "summary": "#bil1"} for moment in (first, second)]
        await self.item.async_update()
        self.assertTrue(self.item.owned)
        self.hass.fail.add(("calendar", "get_events"))
        self.item._calendar_checked = float("-inf")
        await self.item.async_update()
        self.assertFalse(self.item._calendar_ok)
        await self.item.async_stop_now()
        self.hass.fail.clear()
        self.item._calendar_checked = float("-inf")
        self.now += timedelta(minutes=21)
        await self.item.async_update()
        self.assertTrue(self.item._calendar_ok)
        self.assertFalse(self.item.owned)
        self.assertEqual(self.hass.calls.count(("switch", "turn_on")), 1)

    @sync_test
    async def test_manual_start_stop_also_suppresses_overlapping_future_departure(self):
        departure = self.now + timedelta(minutes=40)
        await self.item.async_add_local_departure(departure)
        await self.item.async_start_now()
        await self.item.async_stop_now()
        self.now += timedelta(minutes=11)
        await self.item.async_update()
        self.assertFalse(self.item.owned)
        self.assertEqual(self.hass.calls.count(("switch", "turn_on")), 1)

    @sync_test
    async def test_readding_stopped_local_departure_is_explicit_rescheduling(self):
        departure = self.now + timedelta(minutes=10)
        first = await self.item.async_add_local_departure(departure)
        await self.item.async_stop_now()
        await self.item.async_delete_local_departure(first)
        await self.item.async_add_local_departure(departure)
        self.assertTrue(self.item.owned)
        self.assertEqual(self.hass.calls.count(("switch", "turn_on")), 2)

    @sync_test
    async def test_new_overlapping_departure_is_not_hidden_by_stopped_earlier_event(self):
        first = self.now + timedelta(minutes=10)
        new_departure = self.now + timedelta(minutes=15)
        await self.item.async_add_local_departure(first)
        await self.item.async_stop_now()
        await self.item.async_add_local_departure(new_departure)
        self.assertTrue(self.item.owned)
        self.assertEqual(self.item._active_departure, new_departure)
        self.assertEqual(self.hass.calls.count(("switch", "turn_on")), 2)
        schedule = self.item.schedule_7_days
        self.assertTrue(next(row for row in schedule if row["departure"] == first.isoformat())["suppressed"])
        self.assertFalse(next(row for row in schedule if row["departure"] == new_departure.isoformat())["suppressed"])

    @sync_test
    async def test_legacy_single_suppression_is_loaded_and_honoured(self):
        departure = self.now + timedelta(minutes=10)
        self.hass.storage["motorvarmare.car1"] = {
            "manual_departure": departure.isoformat(),
            "suppressed": f"Manuell|{departure.isoformat()}",
        }
        await self.item.async_load()
        await self.item.async_update()
        self.assertFalse(self.item.owned)
        self.assertNotIn(("switch", "turn_on"), self.hass.calls)

    @sync_test
    async def test_stop_now_failure_is_persisted_and_retried_on_restart(self):
        await self.item.async_start_now()
        self.hass.fail.add(("switch", "turn_off"))
        with self.assertRaisesRegex(ValueError, "turn_off_failed"):
            await self.item.async_stop_now()
        self.assertTrue(self.item.owned)
        replacement = new_controller(self.hass)
        await replacement.async_load()
        self.assertTrue(replacement._stop_requested)
        self.hass.fail.clear()
        await replacement.async_update()
        self.assertFalse(replacement.owned)
        self.assertFalse(replacement._stop_requested)
        self.assertEqual(self.hass.states["switch.heater"].state, "off")

    @sync_test
    async def test_stop_now_does_not_turn_off_externally_started_switch(self):
        self.hass.states["switch.heater"].state = "on"
        with self.assertRaisesRegex(ValueError, "not_owned"):
            await self.item.async_stop_now()
        self.assertNotIn(("switch", "turn_off"), self.hass.calls)

    @sync_test
    async def test_switching_off_start_now_suppresses_due_scheduled_departure(self):
        self.item.manual_departure = self.now + timedelta(minutes=10)
        await self.item.async_start_now()
        self.hass.states["switch.heater"].state = "off"
        await self.item.async_update()
        await self.item.async_update()
        self.assertEqual(self.hass.calls.count(("switch", "turn_on")), 1)
        self.assertFalse(self.item.owned)

    @sync_test
    async def test_owned_departure_restores_after_restart(self):
        self.item.manual_departure = self.now + timedelta(minutes=5)
        await self.item.async_update()
        replacement = new_controller(self.hass)
        await replacement.async_load()
        self.assertTrue(replacement.owned)
        self.now += timedelta(minutes=6)
        await replacement.async_update()
        self.assertFalse(replacement.owned)
        self.assertEqual(self.hass.states["switch.heater"].state, "off")


if __name__ == "__main__":
    unittest.main()
