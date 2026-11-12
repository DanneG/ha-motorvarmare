"""Optional, independently supervised power and energy monitoring."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
import logging
import math
import time

from homeassistant.core import callback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
_POWER_UNITS = {"mW": 0.001, "W": 1.0, "kW": 1000.0, "MW": 1000000.0}
_ENERGY_UNITS = {"mWh": 0.000001, "Wh": 0.001, "kWh": 1.0, "MWh": 1000.0}
_HISTORY_LIMIT = 1000
_POWER_GRAPH_LIMIT = 512
_POWER_GRAPH_INTERVAL = timedelta(seconds=30)
_STARTUP_ALERT_RETRY_SECONDS = 5 * 60
_LEGACY_HISTORY_LIMIT = 100
_TOTAL_LIMITS = {"daily": 366, "weekly": 104, "monthly": 36}


def _period_start(day, kind):
    """Return the local calendar day starting a day, ISO week or month."""
    if kind == "weekly":
        return day - timedelta(days=day.weekday())
    if kind == "monthly":
        return day.replace(day=1)
    return day


def _next_period(day, kind):
    if kind == "weekly":
        return day + timedelta(days=7)
    if kind == "monthly":
        return date(day.year + (day.month == 12), day.month % 12 + 1, 1)
    return day + timedelta(days=1)


def _history_local_day(value, zone):
    """Parse one historical instant into the configured local date."""
    if not isinstance(value, str):
        return None
    try:
        parsed = dt_util.parse_datetime(value)
        return parsed.astimezone(zone).date() if parsed and parsed.tzinfo else None
    except (ValueError, TypeError, OverflowError):
        return None


def history_energy_totals(history, now, zone, previous_history_truncated=False):
    """Summarize recorded finished sessions without inventing energy data.

    The input is bounded session history, not a meter's lifetime total. All
    session energy is attributed to its local end date. Both periods touched
    by a boundary-crossing session are explicitly marked incomplete because
    a session total cannot safely be split between them.
    """
    today = now.astimezone(zone).date()
    groups = {kind: {} for kind in _TOTAL_LIMITS}
    observed_starts = []
    unknown_end_starts = []
    unknown_start_ends = []
    oldest_end = None

    def bucket(kind, day):
        key = _period_start(day, kind)
        return groups[kind].setdefault(key, {
            "period_start": key.isoformat(), "_values": [], "sessions": 0,
            "missing_energy": 0, "missing_cost": 0,
            "_costs": [], "_currencies": set(), "crossed_boundary": False,
            "truncated": False, "coverage_incomplete": False,
        })

    for kind in groups:
        bucket(kind, today)

    for index, item in enumerate(history):
        if not isinstance(item, dict):
            unknown_end_starts.append(None)
            continue
        start = _history_local_day(item.get("start"), zone)
        end = _history_local_day(item.get("end"), zone)
        if start:
            observed_starts.append(start)
        elif end:
            observed_starts.append(end)
            unknown_start_ends.append(end)
        if index == 0:
            oldest_end = end
        if not end or end > today:
            unknown_end_starts.append(start)
            continue
        value = item.get("energy_kwh")
        valid = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0
        cost, currency = item.get("estimated_cost"), item.get("cost_currency")
        valid_cost = (isinstance(cost, (int, float)) and not isinstance(cost, bool)
                      and math.isfinite(cost) and isinstance(currency, str)
                      and len(currency) == 3 and currency.isascii() and currency.isalpha()
                      and currency == currency.upper())
        for kind in groups:
            b = bucket(kind, end)
            b["sessions"] += 1
            if valid:
                b["_values"].append(float(value))
            else:
                b["missing_energy"] += 1
            if valid_cost:
                b["_costs"].append(float(cost))
                b["_currencies"].add(currency)
            else:
                b["missing_cost"] += 1
            if not item.get("complete"):
                b["coverage_incomplete"] = True
            if start and start <= end:
                first = _period_start(start, kind)
                last = _period_start(end, kind)
                if first != last:
                    # Mark both sides even if the earlier period has no other
                    # finished sessions. Bound corrupted or extremely long
                    # sessions; all existing buckets are then uncertain.
                    cursor, count = first, 0
                    while cursor <= last and count < 400:
                        bucket(kind, cursor)["crossed_boundary"] = True
                        try:
                            cursor = _next_period(cursor, kind)
                        except (ValueError, OverflowError):
                            count = 400
                            break
                        count += 1
                    if count >= 400 and cursor <= last:
                        for existing in groups[kind].values():
                            existing["coverage_incomplete"] = True
                        b["crossed_boundary"] = True
            elif start and start > end:
                b["coverage_incomplete"] = True

    result = {"scope": "recorded_completed_sessions", "history_limit": _HISTORY_LIMIT,
              "limits": dict(_TOTAL_LIMITS), "has_older": {}}
    first_observed = min(observed_starts) if observed_starts else None
    for kind, entries in groups.items():
        if oldest_end and (len(history) >= _HISTORY_LIMIT or previous_history_truncated):
            bucket(kind, oldest_end)["truncated"] = True
        elif len(history) >= _HISTORY_LIMIT or previous_history_truncated:
            # The oldest retained record has no known end, so its true period
            # and the point at which older sessions were dropped are unknown.
            for b in entries.values():
                b["truncated"] = True
        first_period = _period_start(first_observed, kind) if first_observed else None
        for period, b in entries.items():
            # We cannot establish coverage before the first observed session.
            if first_period is None or period <= first_period or not b["sessions"]:
                b["coverage_incomplete"] = True
            for start in unknown_end_starts:
                try:
                    after_start = start is None or _next_period(period, kind) > start
                except (ValueError, OverflowError):
                    after_start = True
                if after_start:
                    b["coverage_incomplete"] = True
            if any(period <= end for end in unknown_start_ends):
                b["coverage_incomplete"] = True
            values = b.pop("_values")
            try:
                total = math.fsum(values) if values else None
            except OverflowError:
                total = None
                b["coverage_incomplete"] = True
            if total is not None and not math.isfinite(total):
                total = None
                b["coverage_incomplete"] = True
            b["energy_kwh"] = round(total, 4) if total is not None else None
            b["incomplete"] = bool(b["missing_energy"] or b["crossed_boundary"]
                                    or b["truncated"] or b["coverage_incomplete"])
            costs, currencies = b.pop("_costs"), b.pop("_currencies")
            try:
                cost_total = math.fsum(costs) if costs and len(currencies) == 1 else None
            except OverflowError:
                cost_total = None
            if cost_total is not None and not math.isfinite(cost_total):
                cost_total = None
            b["estimated_cost"] = round(cost_total, 4) if cost_total is not None else None
            b["cost_currency"] = next(iter(currencies)) if len(currencies) == 1 else None
            b["cost_incomplete"] = bool(b["incomplete"] or b["missing_cost"] or len(currencies) > 1
                                        or (costs and cost_total is None))
        ordered = [entries[key] for key in sorted(entries, reverse=True)]
        result["has_older"][kind] = len(ordered) > _TOTAL_LIMITS[kind]
        result[kind] = ordered[:_TOTAL_LIMITS[kind]]
    return result


def _read_number(state, units, *, cumulative=False):
    """Read a finite, nonnegative measurement with a supported unit."""
    if state is None:
        return None
    attrs = state.attributes
    if cumulative and attrs.get("state_class") not in ("total", "total_increasing"):
        return None
    scale = units.get(attrs.get("unit_of_measurement"))
    if scale is None:
        return None
    try:
        result = float(state.state) * scale
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) and result >= 0 else None


def _read_temperature_c(state):
    """Read the configured outdoor temperature, allowing negative Celsius."""
    if state is None:
        return None
    try:
        value = float(state.state)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(value):
        return None
    unit = state.attributes.get("unit_of_measurement")
    if unit == "°F":
        value = (value - 32) * 5 / 9
    elif unit != "°C":
        return None
    return round(value, 2) if math.isfinite(value) else None


def _currency(value):
    """Validate the configured currency rather than guessing one from a sensor."""
    if not isinstance(value, str):
        return None
    result = value.strip().upper()
    return result if len(result) == 3 and result.isascii() and result.isalpha() else None


def _finite_number(value):
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _read_price(state, currency):
    """Read a price per kWh only when its unit agrees with the currency.

    A spot price can legitimately be negative. Ambiguous units or an
    unavailable sensor must not silently fall back to another price.
    """
    currency = _currency(currency)
    if state is None or currency is None:
        return None
    unit = state.attributes.get("unit_of_measurement")
    if not isinstance(unit, str):
        return None
    unit = "".join(unit.split())
    if "/" not in unit:
        return None
    numerator, denominator = unit.split("/", 1)
    if denominator not in ("kWh", "MWh"):
        return None
    scale = 1.0 if denominator == "kWh" else 0.001
    if numerator.upper() == currency:
        pass
    elif currency == "SEK" and numerator.casefold() in ("kr", "kronor"):
        pass
    elif currency == "SEK" and numerator.casefold() in ("öre", "ore"):
        scale *= 0.01
    elif (currency, numerator) in (("EUR", "€"), ("USD", "$"), ("GBP", "£")):
        pass
    else:
        return None
    value = _finite_number(state.state)
    result = value * scale if value is not None else None
    return result if result is not None and math.isfinite(result) else None


class EnergyMonitor:
    """Track switch sessions and report a sustained absence of load.

    This monitor never issues switch commands. Missing samples reset the low
    power timer, rather than proving that the load has been low throughout.
    """

    def __init__(self, hass, entry, config, notify, alerts_allowed=None):
        self.hass, self.entry, self.config, self._notify = hass, entry, config, notify
        self._alerts_allowed = alerts_allowed or (lambda: True)
        self._deferred_low_epoch = None
        self._deferred_low_deviation = False
        self._deferred_alert_retry_until = None
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.energy")
        self._lock = asyncio.Lock()
        self._unsub = None
        self._stopped = False
        self._stopping = False
        self._pending_updates = []
        self._session_active = False
        self._saw_off = False
        self._switch_changed = None
        self._baseline = None
        self._last_meter = None
        self._session_energy = None
        self._last_power = None
        self._last_power_at = None
        self._session_cost = None
        # The current session's bounded display samples are independent of
        # energy integration. A null sample explicitly breaks the graph.
        self._active_power_samples = []
        self._last_price = None
        self._cost_invalid = False
        self._invalid = False
        self._low_since = None
        self._persistent_sent = False
        self._mobile_sent = False
        self._last_attempt = {}
        self._power_epoch = 0
        # Low-power warnings belong to the observed start only. None means
        # closed (including after a restart or an unknown switch state).
        self._startup_started = None
        self._low_start_deadline = None
        self._deviation_low_deadline = None
        self.alarm_active = False
        self.deviation_alarm_active = False
        self._deviation_candidate = None
        self._deviation_since = None
        self._deviation_epoch = 0
        # Only incoming events advance this generation. Processing a queued
        # event must not make subsequent snapshots falsely stale.
        self._deviation_event_epoch = 0
        self._deviation_persistent_sent = set()
        self._deviation_mobile_sent = set()
        self._deviation_last_attempt = {}
        self._history = []
        self._history_may_be_truncated = False
        self._history_start = None
        self._history_temperature_at_start = None
        self._history_source = None
        self._history_time_complete = False
        self._observed_switch = None
        self._restored_session = False
        self._totals_cache_history = None
        self._totals_cache_length = None
        self._totals_cache_key = None
        self._totals_cache = None

    @property
    def heating_history(self):
        """Return recent completed sessions, newest first, without exposing internals."""
        return [dict(item) for item in reversed(self._history)]

    @property
    def history_energy_totals(self):
        """Return bounded local-calendar summaries, cached until history or day changes."""
        now = dt_util.utcnow()
        zone = dt_util.get_default_time_zone()
        key = (now.astimezone(zone).date(), str(zone))
        if (self._totals_cache_history is not self._history
                or self._totals_cache_length != len(self._history)
                or self._totals_cache_key != key):
            self._totals_cache = history_energy_totals(
                self._history, now, zone, self._history_may_be_truncated)
            self._totals_cache_history = self._history
            self._totals_cache_length = len(self._history)
            self._totals_cache_key = key
        return self._totals_cache

    @property
    def power_configured(self):
        return bool(self.config.get("power_entity"))

    @property
    def energy_configured(self):
        # Older installations may still have a cumulative meter configured.
        # A selected power sensor always takes precedence for new sessions.
        return self.power_configured or bool(self.config.get("energy_entity"))

    @property
    def _integrate_power(self):
        return self.power_configured

    @property
    def cost_configured(self):
        """Whether a price source and a valid currency were selected."""
        return bool(_currency(self.config.get("energy_currency", "SEK")) and
                    (self.config.get("energy_price_entity") or
                     _finite_number(self.config.get("energy_price")) is not None))

    def _cost_price(self, state=None):
        """Return a per-kWh estimate and source, without guessing unavailable data."""
        currency = _currency(self.config.get("energy_currency", "SEK"))
        if not currency:
            return None, None, None
        entity = self.config.get("energy_price_entity")
        if entity:
            if state is None:
                state = self.hass.states.get(entity)
            price = _read_price(state, currency)
            return price, currency, "sensor_at_end"
        return _finite_number(self.config.get("energy_price")), currency, "fixed"

    @property
    def power_w(self):
        return _read_number(self.hass.states.get(self.config.get("power_entity")), _POWER_UNITS) if self.power_configured else None

    @property
    def energy_meter_kwh(self):
        return _read_number(self.hass.states.get(self.config.get("energy_entity")), _ENERGY_UNITS, cumulative=True) if self.config.get("energy_entity") else None

    @property
    def energy_sensor_available(self):
        return self.power_w is not None if self._integrate_power else self.energy_meter_kwh is not None

    @property
    def session_energy_kwh(self):
        return round(self._session_energy, 4) if self._session_energy is not None and not self._invalid else None

    @property
    def active_power_samples(self):
        """Power observations in this run; null means an unknown interval."""
        if not self._session_active or not self.power_configured:
            return []
        return [dict(item) for item in self._active_power_samples]

    @property
    def active_measurement_started_at(self):
        """Observed switch-session start for the reported energy and cost.

        A clean integration reload may stop and resume the same scheduled
        heater run. Energy after that restart belongs to a new measurement
        session and must not appear to cover the earlier heater run. If the
        switch start was not observed, we cannot state a measurement start.
        """
        if not self._session_active or not self._history_time_complete:
            return None
        return self._history_start if self._history_datetime(self._history_start) else None

    @property
    def active_session_cost(self):
        """Estimate only where the session's full energy and price are known."""
        if not self._session_active or not self.cost_configured:
            return None
        energy = self.session_energy_kwh
        if energy is None:
            return None
        if self.config.get("energy_price_entity"):
            # A price integral is available only for a power-based session.
            # An end-price estimate cannot price a live variable-price run.
            value = self._session_cost if self._integrate_power and not self._cost_invalid else None
        else:
            price = _finite_number(self.config.get("energy_price"))
            value = energy * price if price is not None else None
        return round(value, 4) if isinstance(value, (int, float)) and math.isfinite(value) else None

    @property
    def active_session_currency(self):
        return _currency(self.config.get("energy_currency", "SEK")) if self.active_session_cost is not None else None

    def _append_power_sample(self, observed_at, power, *, force=False):
        """Append a bounded, downsampled observation without bridging gaps."""
        if not self.power_configured:
            return False
        instant = self._history_datetime(observed_at)
        if instant is None:
            return False
        if not isinstance(power, (int, float)) or isinstance(power, bool) or not math.isfinite(power) or power < 0:
            power = None
        else:
            power = round(power, 2)
        if self._active_power_samples:
            previous = self._active_power_samples[-1]
            previous_at = self._history_datetime(previous["at"])
            if previous_at and instant < previous_at:
                # A backwards timestamp cannot be placed reliably on this axis.
                # Drop its old points instead of drawing a misleading line.
                self._active_power_samples = []
            elif previous_at:
                if previous["watts"] is None and power is None:
                    return False
                if not force and power is not None and previous["watts"] is not None and instant - previous_at < _POWER_GRAPH_INTERVAL:
                    return False
        self._active_power_samples.append({"at": instant.isoformat(), "watts": power})
        self._active_power_samples = self._active_power_samples[-_POWER_GRAPH_LIMIT:]
        return True

    @property
    def energy_session_status(self):
        if not self.energy_configured:
            return "disabled"
        if self._invalid or (self._session_active and self._baseline is None):
            return "incomplete"
        if self._session_active:
            return "measuring"
        return "complete" if self._session_energy is not None else "no_session"

    @property
    def monitor_status(self):
        if not self.power_configured:
            return "disabled"
        switch = self.hass.states.get(self.config.get("switch_entity"))
        if self.power_w is None:
            return "power_unavailable"
        if not switch or switch.state != "on":
            return "waiting"
        return "low_power" if self.power_w < self._threshold() else "ok"

    def _threshold(self):
        try:
            value = float(self.config.get("power_min_watts", 10))
            return value if math.isfinite(value) and value >= 0 else 10
        except (ValueError, TypeError):
            return 10

    def _delay(self):
        try:
            value = float(self.config.get("power_delay_minutes", 5))
            return value if math.isfinite(value) and value >= 0 else 5
        except (ValueError, TypeError):
            return 5

    @property
    def deviation_direction(self):
        """Return the current alarm direction only after the full delay."""
        return self._deviation_candidate if self.deviation_alarm_active else None

    def _deviation_for_power(self, power):
        if not self.config.get("power_deviation_enabled", False) or power is None:
            return None
        low = _finite_number(self.config.get("power_expected_min_watts"))
        high = _finite_number(self.config.get("power_expected_max_watts"))
        if low is not None and low >= 0 and power < low:
            return "low"
        if high is not None and high >= 0 and power > high:
            return "high"
        return None

    def _deviation_delay(self):
        value = _finite_number(self.config.get("power_deviation_delay_minutes", 5))
        return value if value is not None and value >= 0 else 5

    def _startup_power_fresh(self, power_state, snapshot, observed):
        """Don't treat a pre-start high reading as proof the load started.

        A power change observed after switch-on is fresh even for a sensor
        that only reports changes. Home Assistant states also provide a
        report/update timestamp; stubs without one use direct observations.
        """
        if self._startup_started is None or observed is None or observed < self._startup_started:
            return False
        if snapshot is not None and snapshot.get("power_event"):
            return True
        reported = getattr(power_state, "last_reported", None) or getattr(power_state, "last_updated", None)
        if reported is not None and getattr(reported, "tzinfo", None):
            # Devices can deliver the power reading just before the switch
            # state event even though both describe the same physical start.
            return dt_util.as_utc(reported) >= self._startup_started - timedelta(seconds=5)
        return snapshot is None

    def _low_start_open(self, deadline, now):
        return bool(deadline is not None and self._startup_started is not None
                    and self._startup_started <= now <= deadline)

    def _snapshot(self):
        return {
            "switch_entity": self.config.get("switch_entity"),
            "power_entity": self.config.get("power_entity"),
            "notify_entity": self.config.get("notify_entity"),
            "energy_entity": self.config.get("energy_entity"),
            "energy_source": "power" if self._integrate_power else "meter",
            "session_active": self._session_active,
            "switch_changed": self._switch_changed,
            "baseline": self._baseline,
            "last_meter": self._last_meter,
            "session_energy": self._session_energy,
            "active_power_samples": self._active_power_samples[-_POWER_GRAPH_LIMIT:],
            "invalid": self._invalid,
            "persistent_sent": self._persistent_sent,
            "mobile_sent": self._mobile_sent,
            "deviation_persistent_sent": sorted(self._deviation_persistent_sent),
            "deviation_mobile_sent": sorted(self._deviation_mobile_sent),
            "heating_history": self._history[-_HISTORY_LIMIT:],
            "history_limit": _HISTORY_LIMIT,
            "history_may_be_truncated": self._history_may_be_truncated,
            "history_start": self._history_start,
            "history_temperature_at_start": self._history_temperature_at_start,
            "history_source": self._history_source,
            "history_time_complete": self._history_time_complete,
        }

    async def async_load(self):
        """Restore session data only for the same switch and energy sensor."""
        data = await self.store.async_load() or {}
        history = data.get("heating_history", [])
        if isinstance(history, list):
            self._history = [item for item in history if isinstance(item, dict)][-_HISTORY_LIMIT:]
            # Older releases only retained 100 sessions. Mark the oldest
            # retained period uncertain even after upgrading the limit.
            self._history_may_be_truncated = bool(data.get("history_may_be_truncated") or
                ("history_limit" not in data and len(history) >= _LEGACY_HISTORY_LIMIT) or
                len(history) > _HISTORY_LIMIT)
        source = data.get("history_source")
        if isinstance(source, dict):
            self._history_source = {key: value for key, value in source.items()
                                    if key in ("switch_entity", "energy_source", "power_entity", "energy_entity")
                                    and isinstance(value, str)}
        if data.get("switch_entity") != self.config.get("switch_entity"):
            # A changed switch cannot inherit an active run from the old
            # device. Preserve the observed start as an incomplete record.
            if data.get("session_active"):
                start = data.get("history_start")
                self._history_start = start if self._history_datetime(start) else None
                self._history_temperature_at_start = _finite_number(data.get("history_temperature_at_start"))
                self._finish_history(None)
                await self._save()
            return
        self._session_active = bool(data.get("session_active"))
        self._restored_session = self._session_active
        self._history_start = data.get("history_start") if isinstance(data.get("history_start"), str) else None
        self._history_temperature_at_start = _finite_number(data.get("history_temperature_at_start"))
        # While HA was stopped an unobserved switch cycle may have occurred.
        self._history_time_complete = False
        self._switch_changed = data.get("switch_changed")
        if data.get("power_entity") == self.config.get("power_entity"):
            samples = data.get("active_power_samples", [])
            if self._session_active and self.power_configured and isinstance(samples, list):
                # Validate persisted data and keep only ascending timestamps.
                for item in samples[-_POWER_GRAPH_LIMIT:]:
                    if not isinstance(item, dict) or "watts" not in item:
                        continue
                    value = item["watts"]
                    if value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool)
                                              or not math.isfinite(value) or value < 0):
                        continue
                    instant = self._history_datetime(item.get("at"))
                    if not instant:
                        continue
                    if self._active_power_samples and instant < self._history_datetime(self._active_power_samples[-1]["at"]):
                        continue
                    self._append_power_sample(instant.isoformat(), value, force=True)
            self._persistent_sent = bool(data.get("persistent_sent"))
            values = data.get("deviation_persistent_sent", [])
            self._deviation_persistent_sent = {v for v in values if isinstance(v, str) and v in ("low", "high")} if isinstance(values, list) else set()
            if data.get("notify_entity") == self.config.get("notify_entity"):
                self._mobile_sent = bool(data.get("mobile_sent"))
                values = data.get("deviation_mobile_sent", [])
                self._deviation_mobile_sent = {v for v in values if isinstance(v, str) and v in ("low", "high")} if isinstance(values, list) else set()
        if ((self._integrate_power and data.get("energy_source") == "power"
             and data.get("power_entity") == self.config.get("power_entity")) or
            (not self._integrate_power and data.get("energy_source", "meter") == "meter"
             and data.get("energy_entity") == self.config.get("energy_entity"))):
            for name, key in (("_baseline", "baseline"), ("_last_meter", "last_meter"), ("_session_energy", "session_energy")):
                value = data.get(key)
                if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0:
                    setattr(self, name, float(value))
            self._invalid = bool(data.get("invalid"))
            if self._session_active:
                # A meter may have reset while HA was stopped, even if its
                # later value exceeds our last saved sample. Do not assert a
                # complete session when continuity cannot be verified.
                self._invalid = True
                self._session_energy = None
        elif self._session_active and self.energy_configured:
            # A measurement made with a different source cannot be extended.
            self._invalid = True
            self._session_energy = None
        # Do not count unobserved downtime toward the low-power delay.
        self._low_since = None
        # Neither power consumption nor dynamic price can be reconstructed
        # during downtime, regardless of a persisted partial sum.
        if self._session_active:
            self._cost_invalid = True
            self._session_cost = None

    async def async_start(self):
        from homeassistant.helpers.event import async_track_state_change_event

        self._stopped = False
        self._stopping = False
        entities = {self.config.get("switch_entity"), self.config.get("power_entity")}
        if not self._integrate_power:
            entities.add(self.config.get("energy_entity"))
        elif self.config.get("energy_price_entity"):
            # Price changes need their own timestamp even when the plug's
            # power reading is unchanged throughout a heating session.
            entities.add(self.config.get("energy_price_entity"))
        current_switch = self.hass.states.get(self.config.get("switch_entity"))
        if current_switch and current_switch.state == "off":
            self._saw_off = True

        @callback
        def changed(event):
            entity = event.data.get("entity_id")
            if entity in entities and not self._stopped:
                # Snapshot the switch state in the event: an on/off pair must
                # not collapse into a single final state while tasks are queued.
                switch_event = entity == self.config.get("switch_entity")
                new_state = event.data.get("new_state")
                if switch_event and (new_state is None or new_state.state != "on"):
                    self._deferred_low_deviation = False
                    self._power_epoch += 1
                    self._low_since = None
                    self.alarm_active = False
                    self._deviation_epoch += 1
                    self._deviation_event_epoch += 1
                    self._deviation_candidate = self._deviation_since = None
                    self.deviation_alarm_active = False
                if entity == self.config.get("power_entity"):
                    power = _read_number(new_state, _POWER_UNITS)
                    if self._deviation_for_power(power) != "low":
                        self._deferred_low_deviation = False
                    if power is None or power >= self._threshold():
                        # Reset synchronously, even while a notification task
                        # is waiting; later queued events cannot preserve a
                        # fictitious uninterrupted low-power period.
                        self._power_epoch += 1
                        self._low_since = None
                        self.alarm_active = False
                    if self._deviation_for_power(power) != self._deviation_candidate:
                        self._deviation_epoch += 1
                        self._deviation_event_epoch += 1
                        self._deviation_candidate = self._deviation_since = None
                        self.deviation_alarm_active = False
                # Capture all three states at the instant of this event. A
                # rapid on -> energy update -> off must keep its real start
                # and stop readings even while notification I/O holds the lock.
                snapshot = {"switch": self.hass.states.get(self.config.get("switch_entity")),
                            "power": self.hass.states.get(self.config.get("power_entity")),
                            "energy": self.hass.states.get(self.config.get("energy_entity")),
                            "price": self.hass.states.get(self.config.get("energy_price_entity")),
                            "temperature": self.hass.states.get(self.config.get("temperature_entity")),
                            "observed_at": dt_util.utcnow().isoformat(),
                            "switch_event": switch_event,
                            "power_event": entity == self.config.get("power_entity"),
                            "power_epoch": self._power_epoch,
                            "deviation_event_epoch": self._deviation_event_epoch}
                if switch_event:
                    snapshot["switch"] = new_state
                elif entity == self.config.get("power_entity"):
                    snapshot["power"] = new_state
                elif entity == self.config.get("energy_entity"):
                    snapshot["energy"] = new_state
                elif entity == self.config.get("energy_price_entity"):
                    snapshot["price"] = new_state
                self._queue_update(snapshot)

        self._unsub = async_track_state_change_event(self.hass, [entity for entity in entities if entity], changed)
        # Do not delay the heater scheduler on storage or notification I/O.
        initial = {"switch": self.hass.states.get(self.config.get("switch_entity")),
                   "power": self.hass.states.get(self.config.get("power_entity")),
                   "energy": self.hass.states.get(self.config.get("energy_entity")),
                   "price": self.hass.states.get(self.config.get("energy_price_entity")),
                   "temperature": self.hass.states.get(self.config.get("temperature_entity")),
                   "observed_at": dt_util.utcnow().isoformat(), "initial": True}
        self._queue_update(initial)

    def _queue_update(self, snapshot):
        task = self.hass.async_create_task(self._safe_update(snapshot))
        if task is not None and hasattr(task, "add_done_callback"):
            self._pending_updates.append(task)
            task.add_done_callback(self._pending_updates.remove)

    async def _safe_update(self, *args):
        try:
            await self.async_update(*args)
        except Exception:
            _LOGGER.exception("Energy monitoring failed for %s", self.entry.title)

    async def async_shutdown(self):
        # Unsubscribe first and drain observations already captured before
        # recording the final state. Suppress new alerts while unloading.
        self._stopping = True
        self._deferred_low_epoch = None
        self._deferred_low_deviation = False
        self._deferred_alert_retry_until = None
        if self._unsub:
            self._unsub()
            self._unsub = None
        pending = tuple(self._pending_updates)
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        self._stopped = True
        await self.async_update(force=True)

    async def _save(self):
        await self.store.async_save(self._snapshot())

    @staticmethod
    def _changed_at(state):
        value = getattr(state, "last_changed", None)
        return value.isoformat() if value is not None else None

    @staticmethod
    def _history_datetime(value):
        if not isinstance(value, str):
            return None
        try:
            parsed = dt_util.parse_datetime(value)
            return dt_util.as_utc(parsed) if parsed and parsed.tzinfo else None
        except (ValueError, TypeError, OverflowError):
            return None

    def _integrate_power_until(self, observed_at, power, price=None):
        """Integrate the preceding power sample up to this observation.

        Values are held constant between reports. Missing readings, a changed
        clock or an overflow invalidate the whole session, never imply zero.
        """
        instant = self._history_datetime(observed_at)
        if (instant is None or power is None or self._last_power is None
                or self._last_power_at is None or instant < self._last_power_at):
            self._invalid = True
            self._session_energy = None
            self._cost_invalid = True
            self._session_cost = None
            return
        elapsed = (instant - self._last_power_at).total_seconds()
        value = self._session_energy + self._last_power * elapsed / 3_600_000
        if not math.isfinite(value):
            self._invalid = True
            self._session_energy = None
            self._cost_invalid = True
            self._session_cost = None
            return
        self._session_energy = value
        if self.cost_configured and self.config.get("energy_price_entity") and not self._cost_invalid:
            if price is None or self._last_price is None or self._session_cost is None:
                self._cost_invalid = True
                self._session_cost = None
            else:
                cost = self._session_cost + self._last_power * elapsed / 3_600_000 * self._last_price
                if not math.isfinite(cost):
                    self._cost_invalid = True
                    self._session_cost = None
                else:
                    self._session_cost = cost
            self._last_price = price
        self._last_power = power
        self._last_power_at = instant

    def _finish_history(self, end, price_state=None, *, has_price_snapshot=False):
        """Record only observations we can justify; unknown is not zero."""
        start_dt, end_dt = self._history_datetime(self._history_start), self._history_datetime(end)
        complete = bool(self._history_time_complete and start_dt and end_dt and end_dt >= start_dt)
        item = {
            "start": self._history_start,
            "end": end if end_dt else None,
            "duration_minutes": round((end_dt - start_dt).total_seconds() / 60, 1) if complete else None,
            "energy_kwh": self.session_energy_kwh if self.energy_configured else None,
            "complete": complete,
        }
        if self._history_temperature_at_start is not None:
            item["temperature_at_start_c"] = self._history_temperature_at_start
        if self._history_source:
            item.update(self._history_source)
        if self.cost_configured:
            energy = item["energy_kwh"]
            if self._integrate_power and self.config.get("energy_price_entity"):
                currency, basis = _currency(self.config.get("energy_currency", "SEK")), "power_price_integral"
                cost = self._session_cost if complete and energy is not None and not self._cost_invalid else None
            else:
                # Legacy cumulative meters cannot distribute consumption
                # across tariffs. Preserve the existing end-price estimate.
                if self.config.get("energy_price_entity") and has_price_snapshot and price_state is None:
                    price, currency, basis = None, _currency(self.config.get("energy_currency", "SEK")), "sensor_at_end"
                else:
                    price, currency, basis = self._cost_price(price_state)
                cost = energy * price if complete and energy is not None and price is not None else None
            item.update({"estimated_cost": round(cost, 4) if cost is not None and math.isfinite(cost) else None,
                         "cost_currency": currency, "cost_basis": basis})
        self._history.append(item)
        if len(self._history) > _HISTORY_LIMIT:
            self._history_may_be_truncated = True
        self._history = self._history[-_HISTORY_LIMIT:]
        self._history_start = None
        self._history_temperature_at_start = None
        self._history_source = None
        self._history_time_complete = False

    async def async_update(self, snapshot=None, force=False):
        """Process one observation. Called from events and the periodic tick."""
        if self._stopped and not force:
            return
        observed_at = (snapshot or {}).get("observed_at") or dt_util.utcnow().isoformat()
        async with self._lock:
            if self._stopped and not force:
                return
            if self._alerts_allowed() and (self._deferred_low_epoch is not None or self._deferred_low_deviation):
                await self._flush_deferred_startup_alerts_locked()
            switch = snapshot.get("switch") if snapshot is not None else self.hass.states.get(self.config.get("switch_entity"))
            on = switch is not None and switch.state == "on"
            off = switch is not None and switch.state == "off"
            meter = (_read_number(snapshot.get("energy"), _ENERGY_UNITS, cumulative=True)
                     if snapshot is not None and self.energy_configured
                     else self.energy_meter_kwh)
            power_state = snapshot.get("power") if snapshot is not None else self.hass.states.get(self.config.get("power_entity"))
            power = _read_number(power_state, _POWER_UNITS) if self.power_configured else None
            price_state = (snapshot.get("price") if snapshot is not None and "price" in snapshot
                           else self.hass.states.get(self.config.get("energy_price_entity")))
            price = _read_price(price_state, self.config.get("energy_currency", "SEK")) if self.config.get("energy_price_entity") else None
            changed = False
            if on:
                if self._restored_session and self._active_power_samples:
                    # Nothing during Home Assistant downtime is observed. End
                    # the prior line at its last known sample before resuming.
                    changed |= self._append_power_sample(self._active_power_samples[-1]["at"], None, force=True)
                changed_at = self._changed_at(switch)
                # A changed last_changed timestamp can reveal an off/on cycle
                # while HA was unavailable; do not reuse an old baseline.
                new_session = not self._session_active or (changed_at and self._switch_changed and changed_at != self._switch_changed)
                if new_session:
                    was_active = self._session_active
                    if not was_active:
                        self._active_power_samples = []
                    elif self._active_power_samples and not self._restored_session:
                        changed |= self._append_power_sample(observed_at, None, force=True)
                    saw_off_before = self._saw_off
                    observed = self._history_datetime(observed_at)
                    # Only a genuinely observed off->on starts low-power
                    # checks. Unknown/reloaded sessions cannot be certified.
                    self._startup_started = observed if saw_off_before and not was_active else None
                    self._low_start_deadline = (self._startup_started + timedelta(minutes=self._delay() + 5)
                                                if self._startup_started else None)
                    self._deviation_low_deadline = (self._startup_started + timedelta(minutes=self._deviation_delay() + 5)
                                                    if self._startup_started else None)
                    self._session_active = True
                    self._switch_changed = changed_at
                    # If HA first sees an already-on plug there is no known
                    # start reading; a partial measurement must not be
                    # presented as consumption for the whole session.
                    self._baseline = ((0.0 if power is not None else None) if self._integrate_power else meter) if saw_off_before else None
                    self._last_meter = self._baseline
                    self._session_energy = 0.0 if self._baseline is not None else None
                    self._invalid = self.energy_configured and self._baseline is None
                    self._last_power = power if self._integrate_power else None
                    self._last_power_at = self._history_datetime(observed_at) if self._integrate_power else None
                    dynamic_price = bool(self._integrate_power and self.config.get("energy_price_entity") and self.cost_configured)
                    self._last_price = price if dynamic_price else None
                    self._cost_invalid = bool(dynamic_price and (self._invalid or price is None))
                    self._session_cost = 0.0 if dynamic_price and not self._cost_invalid else None
                    if self._integrate_power and self._last_power_at is None:
                        self._invalid = True
                        self._session_energy = None
                    self._saw_off = False
                    self._low_since = None
                    self._persistent_sent = self._mobile_sent = False
                    self._last_attempt = {}
                    self.alarm_active = False
                    self._deviation_candidate = self._deviation_since = None
                    self.deviation_alarm_active = False
                    self._deviation_last_attempt = {}
                    if not was_active:
                        self._deviation_persistent_sent.clear()
                        self._deviation_mobile_sent.clear()
                    if not was_active:
                        # An already-on switch seen at startup has an unknown
                        # true start. Only an observed off->on establishes it.
                        self._history_start = (changed_at or observed_at) if saw_off_before else None
                        self._history_time_complete = self._history_start is not None
                        temp_state = (snapshot.get("temperature") if snapshot is not None and "temperature" in snapshot
                                      else self.hass.states.get(self.config.get("temperature_entity")))
                        self._history_temperature_at_start = _read_temperature_c(temp_state) if saw_off_before else None
                        if self.energy_configured and saw_off_before:
                            source_key = "power_entity" if self._integrate_power else "energy_entity"
                            self._history_source = {"switch_entity": self.config.get("switch_entity"),
                                                    "energy_source": "power" if self._integrate_power else "meter",
                                                    source_key: self.config.get(source_key)}
                        else:
                            self._history_source = None
                    else:
                        # on->unknown->on (or a restart) can hide a cycle;
                        # keep one uncertain record rather than inventing two.
                        self._history_time_complete = False
                    changed = True
                changed |= self._append_power_sample(observed_at, power)
                if self._integrate_power and not new_session and not self._invalid:
                    self._integrate_power_until(observed_at, power, price)
                    changed = True
                if not self._integrate_power and self.energy_configured and meter is None and not self._invalid:
                    # A reset can occur while a sensor is unavailable, so
                    # continuity cannot be established from later readings.
                    self._invalid = True
                    self._session_energy = None
                    changed = True
                if not self._integrate_power and meter is not None and self._baseline is not None and not self._invalid:
                    if self._last_meter is not None and meter + 1e-9 < self._last_meter:
                        self._invalid = True
                        self._session_energy = None
                        changed = True
                    else:
                        self._last_meter = meter
                        self._session_energy = max(0.0, meter - self._baseline)
                now = dt_util.utcnow()
                observed = self._history_datetime(observed_at)
                fresh = self._startup_power_fresh(power_state, snapshot, observed)
                # Once a fresh adequate value has arrived, later low readings
                # (for example a disconnected car) cannot start a new alert.
                if (not self._low_start_open(self._low_start_deadline, now)
                        or (fresh and power is not None and power >= self._threshold())):
                    self._low_start_deadline = None
                normal_min = _finite_number(self.config.get("power_expected_min_watts"))
                if (not self._low_start_open(self._deviation_low_deadline, now)
                        or (fresh and power is not None and normal_min is not None
                            and normal_min >= 0 and power >= normal_min)):
                    self._deviation_low_deadline = None
                current_low_snapshot = snapshot is None or snapshot.get("power_epoch", self._power_epoch) == self._power_epoch
                if (not self._stopped and self.config.get("power_alarm_enabled", True)
                        and self.power_configured and self._low_start_deadline is not None
                        and current_low_snapshot and power is not None and power < self._threshold()):
                    if self._low_since is None:
                        self._low_since = observed or now
                    qualified = now - self._low_since >= timedelta(minutes=self._delay())
                    if qualified and not self._alerts_allowed():
                        self._deferred_low_epoch = self._power_epoch
                    self.alarm_active = self._alerts_allowed() and qualified
                    if self.alarm_active:
                        await self._send_notifications(self._power_epoch)
                else:
                    self._low_since = None
                    self.alarm_active = False
                direction = self._deviation_for_power(power) if not self._stopped and not self._stopping else None
                if direction == "low" and self._deviation_low_deadline is None:
                    direction = None
                if snapshot is not None and snapshot.get("deviation_event_epoch", self._deviation_event_epoch) != self._deviation_event_epoch:
                    direction = None
                if direction != self._deviation_candidate:
                    self._deviation_epoch += 1
                    self._deviation_candidate = direction
                    self._deviation_since = now if direction else None
                    self.deviation_alarm_active = False
                if direction and self._deviation_since is not None:
                    if now < self._deviation_since:
                        # Never count an ambiguous backwards clock jump as
                        # uninterrupted abnormal power.
                        self._deviation_since = now
                    qualified = now - self._deviation_since >= timedelta(minutes=self._deviation_delay())
                    if qualified and direction == "low" and not self._alerts_allowed():
                        self._deferred_low_deviation = True
                    self.deviation_alarm_active = self._alerts_allowed() and qualified
                    if self.deviation_alarm_active:
                        await self._send_deviation_notifications(self._deviation_epoch, direction)
            elif off:
                self._saw_off = True
                self._startup_started = self._low_start_deadline = self._deviation_low_deadline = None
                if self._session_active:
                    if self._integrate_power and not self._invalid:
                        self._integrate_power_until(observed_at, power, price)
                    if not self._integrate_power and self.energy_configured and meter is None:
                        self._invalid = True
                        self._session_energy = None
                    if not self._integrate_power and meter is not None and self._baseline is not None and not self._invalid:
                        if self._last_meter is not None and meter + 1e-9 < self._last_meter:
                            self._invalid = True
                            self._session_energy = None
                        else:
                            self._last_meter = meter
                            self._session_energy = max(0.0, meter - self._baseline)
                    # The first off state after a restart, or after an unknown
                    # switch state, does not reveal when the switch went off.
                    end_known = not self._restored_session and self._observed_switch != "unknown"
                    end = (self._changed_at(switch) or observed_at) if end_known else None
                    self._finish_history(end, snapshot.get("price") if snapshot is not None else None,
                                         has_price_snapshot=snapshot is not None and "price" in snapshot)
                    self._session_active = False
                    self._active_power_samples = []
                    changed = True
                self._low_since = None
                self.alarm_active = False
                self._deviation_epoch += 1
                self._deviation_candidate = self._deviation_since = None
                self.deviation_alarm_active = False
            else:
                if self._session_active:
                    changed |= self._append_power_sample(observed_at, None)
                # A disconnected switch is not evidence of either an off
                # transition or continuously low power. It may have changed
                # state while unavailable, so the whole energy session can no
                # longer be certified complete.
                if self._session_active and self.energy_configured and not self._invalid:
                    self._invalid = True
                    self._session_energy = None
                    self._cost_invalid = True
                    self._session_cost = None
                    changed = True
                if self._session_active and self._history_time_complete:
                    self._history_time_complete = False
                    changed = True
                # An off reading before a connectivity gap does not prove
                # that a later on reading coincided with its actual start.
                self._saw_off = False
                self._startup_started = self._low_start_deadline = self._deviation_low_deadline = None
                self._low_since = None
                self.alarm_active = False
                self._deviation_epoch += 1
                self._deviation_candidate = self._deviation_since = None
                self.deviation_alarm_active = False
            self._observed_switch = "on" if on else "off" if off else "unknown"
            self._restored_session = False
            if changed:
                await self._save()
        self._notify()

    async def _flush_deferred_startup_alerts(self):
        """Send only startup-qualified faults that remain continuously low."""
        async with self._lock:
            await self._flush_deferred_startup_alerts_locked()

    async def _flush_deferred_startup_alerts_locked(self):
        if not self._alerts_allowed() or self._stopped or self._stopping:
            return
        if self._deferred_low_epoch is None and not self._deferred_low_deviation:
            self._deferred_alert_retry_until = None
            return
        now = time.monotonic()
        if self._deferred_alert_retry_until is None:
            self._deferred_alert_retry_until = now + _STARTUP_ALERT_RETRY_SECONDS
        elif now >= self._deferred_alert_retry_until:
            self._deferred_low_epoch, self._deferred_low_deviation = None, False
            self._deferred_alert_retry_until = None
            return
        switch = self.hass.states.get(self.config.get("switch_entity"))
        is_on = switch is not None and switch.state == "on"
        mobile = isinstance(self.config.get("notify_entity"), str) and self.config["notify_entity"].startswith("notify.")
        if self._deferred_low_epoch is not None:
            if (not is_on or self.power_w is None or self.power_w >= self._threshold()
                    or not self.config.get("power_alarm_enabled", True)
                    or self._deferred_low_epoch != self._power_epoch):
                self._deferred_low_epoch = None
            else:
                await self._send_notifications(self._deferred_low_epoch, deferred_startup=True)
                if self._persistent_sent and (not mobile or self._mobile_sent):
                    self._deferred_low_epoch = None
        if self._deferred_low_deviation:
            if not is_on or self._deviation_for_power(self.power_w) != "low":
                self._deferred_low_deviation = False
            else:
                await self._send_deviation_notifications(self._deviation_epoch, "low", deferred_startup=True)
                if "low" in self._deviation_persistent_sent and (not mobile or "low" in self._deviation_mobile_sent):
                    self._deferred_low_deviation = False
        if self._deferred_low_epoch is None and not self._deferred_low_deviation:
            self._deferred_alert_retry_until = None

    async def _send_notifications(self, power_epoch, deferred_startup=False):
        if not self._alerts_allowed():
            return
        language = str(getattr(getattr(self.hass, "config", None), "language", "en") or "en").lower()
        if language.startswith("sv"):
            title = f"Motorvärmare: {self.entry.title}"
            message = "Värmaren är på men effekten är låg. Kontrollera att motorvärmarkabeln är ansluten."
        else:
            title = f"Engine heater: {self.entry.title}"
            message = "The heater is on but power draw is low. Check that the engine heater cable is connected."
        targets = [("persistent", "persistent_notification", "create", {"title": title, "message": message, "notification_id": f"{DOMAIN}_{self.entry.entry_id}_low_power"})]
        entity = self.config.get("notify_entity")
        if isinstance(entity, str) and entity.startswith("notify."):
            targets.append(("mobile", "notify", "send_message", {"entity_id": entity, "title": title, "message": message}))
        for channel, domain, service, data in targets:
            current_switch = self.hass.states.get(self.config.get("switch_entity"))
            current_power = self.power_w
            if not self._alerts_allowed():
                return
            if (self._stopped or self._stopping or power_epoch != self._power_epoch or not current_switch or current_switch.state != "on"
                    or current_power is None or current_power >= self._threshold()
                    or (not deferred_startup and (self._low_since is None
                        or not self._low_start_open(self._low_start_deadline, dt_util.utcnow())))):
                self.alarm_active = False
                break
            attr = f"_{channel}_sent"
            if getattr(self, attr):
                continue
            now = time.monotonic()
            if now - self._last_attempt.get(channel, float("-inf")) < 60:
                continue
            self._last_attempt[channel] = now
            try:
                await asyncio.wait_for(self.hass.services.async_call(domain, service, data, blocking=True), timeout=10)
                setattr(self, attr, True)
                await self._save()
            except Exception:
                _LOGGER.warning("Unable to send %s low-power notification for %s", channel, self.entry.title, exc_info=True)

    async def _send_deviation_notifications(self, epoch, direction, deferred_startup=False):
        """Notify each channel once per direction and observed switch-on run."""
        if not self._alerts_allowed():
            return
        language = str(getattr(getattr(self.hass, "config", None), "language", "en") or "en").lower()
        if language.startswith("sv"):
            title = f"Motorvärmare: {self.entry.title}"
            message = ("Effekten har under en tid varit " + ("under" if direction == "low" else "över")
                       + " det inställda normalintervallet. Kontrollera värmaren och inställningarna.")
        else:
            title = f"Engine heater: {self.entry.title}"
            message = ("Power has been " + ("below" if direction == "low" else "above")
                       + " the configured normal range for a while. Check the heater and settings.")
        targets = [("persistent", "persistent_notification", "create", {
            "title": title, "message": message,
            "notification_id": f"{DOMAIN}_{self.entry.entry_id}_power_deviation_{direction}"})]
        entity = self.config.get("notify_entity")
        if isinstance(entity, str) and entity.startswith("notify."):
            targets.append(("mobile", "notify", "send_message", {
                "entity_id": entity, "title": title, "message": message}))
        for channel, domain, service, data in targets:
            if not self._alerts_allowed():
                return
            switch = self.hass.states.get(self.config.get("switch_entity"))
            if (self._stopped or self._stopping or epoch != self._deviation_epoch
                    or not switch or switch.state != "on"
                    or (not deferred_startup and self._deviation_since is None)
                    or (not deferred_startup and self._deviation_candidate != direction)
                    or self._deviation_for_power(self.power_w) != direction
                    or (not deferred_startup and direction == "low" and not self._low_start_open(self._deviation_low_deadline, dt_util.utcnow()))
                    or (not deferred_startup and dt_util.utcnow() - self._deviation_since < timedelta(minutes=self._deviation_delay()))):
                self.deviation_alarm_active = False
                break
            sent = getattr(self, f"_deviation_{channel}_sent")
            if direction in sent:
                continue
            now = time.monotonic()
            key = (channel, direction)
            if now - self._deviation_last_attempt.get(key, float("-inf")) < 60:
                continue
            self._deviation_last_attempt[key] = now
            try:
                await asyncio.wait_for(self.hass.services.async_call(domain, service, data, blocking=True), timeout=10)
                sent.add(direction)
                await self._save()
            except Exception:
                _LOGGER.warning("Unable to send %s power-deviation notification for %s", channel, self.entry.title, exc_info=True)
