"""Calendar totals must not present missing or ambiguous energy as exact."""

from datetime import datetime, timedelta, timezone
import types
import unittest

import test_controller as mocks
from test_motorvarmare.energy import EnergyMonitor, history_energy_totals, _HISTORY_LIMIT, _TOTAL_LIMITS


ZONE = timezone(timedelta(hours=1))
NOW = datetime(2027, 1, 2, 12, tzinfo=timezone.utc)


def session(start, end, energy, complete=True):
    return {"start": start, "end": end, "energy_kwh": energy, "complete": complete}


def get_period(summary, kind, day):
    return next(item for item in summary[kind] if item["period_start"] == day)


class EnergyTotalsTests(unittest.TestCase):
    def test_empty_history_is_not_invented_zero(self):
        totals = history_energy_totals([], NOW, ZONE)
        self.assertEqual(totals["scope"], "recorded_completed_sessions")
        for kind in ("daily", "weekly", "monthly"):
            self.assertEqual(totals[kind][0]["sessions"], 0)
            self.assertIsNone(totals[kind][0]["energy_kwh"])
            self.assertTrue(totals[kind][0]["incomplete"])

    def test_valid_zero_and_missing_energy_are_distinct(self):
        history = [
            session("2027-01-02T07:00:00+01:00", "2027-01-02T08:00:00+01:00", 0.0),
            session("2027-01-02T09:00:00+01:00", "2027-01-02T10:00:00+01:00", None),
            session("2027-01-02T10:10:00+01:00", "2027-01-02T11:00:00+01:00", 1.125),
        ]
        totals = history_energy_totals(history, NOW, ZONE)
        daily = get_period(totals, "daily", "2027-01-02")
        self.assertEqual(daily["sessions"], 3)
        self.assertEqual(daily["energy_kwh"], 1.125)
        self.assertEqual(daily["missing_energy"], 1)
        self.assertTrue(daily["incomplete"])
        zero = history_energy_totals(history[:1], NOW, ZONE)["daily"][0]
        self.assertEqual(zero["energy_kwh"], 0.0)

    def test_midnight_across_year_marks_both_days_and_months(self):
        history = [session("2026-12-31T23:50:00+01:00", "2027-01-01T00:20:00+01:00", 0.6)]
        totals = history_energy_totals(history, NOW, ZONE)
        for kind, old, new in (("daily", "2026-12-31", "2027-01-01"),
                               ("monthly", "2026-12-01", "2027-01-01")):
            old_period, new_period = get_period(totals, kind, old), get_period(totals, kind, new)
            self.assertTrue(old_period["crossed_boundary"])
            self.assertTrue(new_period["crossed_boundary"])
            self.assertTrue(old_period["incomplete"] and new_period["incomplete"])
            self.assertIsNone(old_period["energy_kwh"])
            self.assertEqual(new_period["energy_kwh"], 0.6)
        self.assertFalse(get_period(totals, "weekly", "2026-12-28")["crossed_boundary"])

    def test_week_boundary_uses_local_monday(self):
        history = [session("2026-11-01T23:40:00+01:00", "2026-11-02T00:10:00+01:00", 0.5)]
        totals = history_energy_totals(history, datetime(2026, 11, 2, 12, tzinfo=timezone.utc), ZONE)
        self.assertTrue(get_period(totals, "weekly", "2026-10-26")["crossed_boundary"])
        self.assertTrue(get_period(totals, "weekly", "2026-11-02")["crossed_boundary"])
        self.assertFalse(get_period(totals, "monthly", "2026-11-01")["crossed_boundary"])

    def test_unknown_dates_mark_affected_coverage_uncertain(self):
        history = [session("2026-12-30T07:00:00+01:00", "2026-12-30T08:00:00+01:00", 1.0),
                   session("2026-12-31T07:00:00+01:00", None, None, False),
                   session("2027-01-02T07:00:00+01:00", "2027-01-02T08:00:00+01:00", 1.0)]
        daily = get_period(history_energy_totals(history, NOW, ZONE), "daily", "2027-01-02")
        self.assertTrue(daily["coverage_incomplete"])
        self.assertTrue(daily["incomplete"])

    def test_capped_history_marks_oldest_period_and_limits_groups(self):
        history = []
        for i in range(_HISTORY_LIMIT):
            moment = datetime(2025, 11, 1, 8, tzinfo=ZONE) + timedelta(days=i * 400 // _HISTORY_LIMIT)
            history.append(session((moment-timedelta(minutes=30)).isoformat(), moment.isoformat(), 1.0))
        totals = history_energy_totals(history, NOW, ZONE)
        self.assertEqual(len(totals["daily"]), _TOTAL_LIMITS["daily"])
        self.assertTrue(totals["has_older"]["daily"])
        self.assertTrue(any(item["truncated"] for item in totals["weekly"]))

    def test_truncation_is_conservative_when_oldest_end_is_unknown(self):
        history = [session(None, None, None, False)] + [
            session("2027-01-02T07:00:00+01:00", "2027-01-02T08:00:00+01:00", 0.1)
            for _ in range(_HISTORY_LIMIT - 1)
        ]
        totals = history_energy_totals(history, NOW, ZONE)
        self.assertTrue(totals["daily"][0]["truncated"])
        self.assertTrue(totals["daily"][0]["incomplete"])

    def test_unrepresentable_sum_does_not_break_sensor_state(self):
        history = [session("2027-01-02T07:00:00+01:00", "2027-01-02T08:00:00+01:00", 1e308)] * 3
        daily = history_energy_totals(history, NOW, ZONE)["daily"][0]
        self.assertIsNone(daily["energy_kwh"])
        self.assertTrue(daily["incomplete"])

    def test_cache_updates_when_history_and_local_day_change(self):
        previous = mocks.dt.utcnow
        current = [datetime(2026, 11, 2, 5, tzinfo=timezone.utc)]
        mocks.dt.utcnow = lambda: current[0]
        try:
            monitor = EnergyMonitor(mocks.Hass(), types.SimpleNamespace(entry_id="totals", title="Bil"), {"switch_entity": "switch.test"}, lambda: None)
            initial = monitor.history_energy_totals
            self.assertIs(initial, monitor.history_energy_totals)
            monitor._history = [session("2026-11-02T06:00:00+01:00", "2026-11-02T07:00:00+01:00", 1.0)]
            updated = monitor.history_energy_totals
            self.assertIsNot(initial, updated)
            self.assertEqual(updated["daily"][0]["energy_kwh"], 1.0)
            current[0] += timedelta(days=1)
            self.assertIsNot(updated, monitor.history_energy_totals)
            self.assertEqual(monitor.history_energy_totals["daily"][0]["period_start"], "2026-11-03")
        finally:
            mocks.dt.utcnow = previous


if __name__ == "__main__":
    unittest.main()
