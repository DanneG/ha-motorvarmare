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

    def __init__(self, hass, entry, config, notify):
        self.hass, self.entry, self.config, self._notify = hass, entry, config, notify
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
        self._invalid = False
        self._low_since = None
        self._persistent_sent = False
        self._mobile_sent = False
        self._last_attempt = {}
        self._power_epoch = 0
        self.alarm_active = False
        self._history = []
        self._history_may_be_truncated = False
        self._history_start = None
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
            "invalid": self._invalid,
            "persistent_sent": self._persistent_sent,
            "mobile_sent": self._mobile_sent,
            "heating_history": self._history[-_HISTORY_LIMIT:],
            "history_limit": _HISTORY_LIMIT,
            "history_may_be_truncated": self._history_may_be_truncated,
            "history_start": self._history_start,
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
        if data.get("switch_entity") != self.config.get("switch_entity"):
            # A changed switch cannot inherit an active run from the old
            # device. Preserve the observed start as an incomplete record.
            if data.get("session_active"):
                start = data.get("history_start")
                self._history_start = start if self._history_datetime(start) else None
                self._finish_history(None)
                await self._save()
            return
        self._session_active = bool(data.get("session_active"))
        self._restored_session = self._session_active
        self._history_start = data.get("history_start") if isinstance(data.get("history_start"), str) else None
        # While HA was stopped an unobserved switch cycle may have occurred.
        self._history_time_complete = False
        self._switch_changed = data.get("switch_changed")
        if data.get("power_entity") == self.config.get("power_entity"):
            self._persistent_sent = bool(data.get("persistent_sent"))
            if data.get("notify_entity") == self.config.get("notify_entity"):
                self._mobile_sent = bool(data.get("mobile_sent"))
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

    async def async_start(self):
        from homeassistant.helpers.event import async_track_state_change_event

        self._stopped = False
        self._stopping = False
        entities = {self.config.get("switch_entity"), self.config.get("power_entity")}
        if not self._integrate_power:
            entities.add(self.config.get("energy_entity"))
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
                    self._power_epoch += 1
                    self._low_since = None
                    self.alarm_active = False
                if entity == self.config.get("power_entity"):
                    power = _read_number(new_state, _POWER_UNITS)
                    if power is None or power >= self._threshold():
                        # Reset synchronously, even while a notification task
                        # is waiting; later queued events cannot preserve a
                        # fictitious uninterrupted low-power period.
                        self._power_epoch += 1
                        self._low_since = None
                        self.alarm_active = False
                # Capture all three states at the instant of this event. A
                # rapid on -> energy update -> off must keep its real start
                # and stop readings even while notification I/O holds the lock.
                snapshot = {"switch": self.hass.states.get(self.config.get("switch_entity")),
                            "power": self.hass.states.get(self.config.get("power_entity")),
                            "energy": self.hass.states.get(self.config.get("energy_entity")),
                            "price": self.hass.states.get(self.config.get("energy_price_entity")),
                            "observed_at": dt_util.utcnow().isoformat(),
                            "switch_event": switch_event}
                if switch_event:
                    snapshot["switch"] = new_state
                elif entity == self.config.get("power_entity"):
                    snapshot["power"] = new_state
                elif entity == self.config.get("energy_entity"):
                    snapshot["energy"] = new_state
                self._queue_update(snapshot)

        self._unsub = async_track_state_change_event(self.hass, [entity for entity in entities if entity], changed)
        # Do not delay the heater scheduler on storage or notification I/O.
        initial = {"switch": self.hass.states.get(self.config.get("switch_entity")),
                   "power": self.hass.states.get(self.config.get("power_entity")),
                   "energy": self.hass.states.get(self.config.get("energy_entity")),
                   "price": self.hass.states.get(self.config.get("energy_price_entity")),
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

    def _integrate_power_until(self, observed_at, power):
        """Integrate the preceding power sample up to this observation.

        Values are held constant between reports. Missing readings, a changed
        clock or an overflow invalidate the whole session, never imply zero.
        """
        instant = self._history_datetime(observed_at)
        if (instant is None or power is None or self._last_power is None
                or self._last_power_at is None or instant < self._last_power_at):
            self._invalid = True
            self._session_energy = None
            return
        elapsed = (instant - self._last_power_at).total_seconds()
        value = self._session_energy + self._last_power * elapsed / 3_600_000
        if not math.isfinite(value):
            self._invalid = True
            self._session_energy = None
            return
        self._session_energy = value
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
        if self.cost_configured:
            # Capture the spot price at the off observation; never re-price
            # an older session using today's tariff. It is an estimate when a
            # price sensor changes during the run, not a timed energy integral.
            if self.config.get("energy_price_entity") and has_price_snapshot and price_state is None:
                price, currency, basis = None, _currency(self.config.get("energy_currency", "SEK")), "sensor_at_end"
            else:
                price, currency, basis = self._cost_price(price_state)
            energy = item["energy_kwh"]
            cost = energy * price if complete and energy is not None and price is not None else None
            item.update({"estimated_cost": round(cost, 4) if cost is not None and math.isfinite(cost) else None,
                         "cost_currency": currency, "cost_basis": basis})
        self._history.append(item)
        if len(self._history) > _HISTORY_LIMIT:
            self._history_may_be_truncated = True
        self._history = self._history[-_HISTORY_LIMIT:]
        self._history_start = None
        self._history_time_complete = False

    async def async_update(self, snapshot=None, force=False):
        """Process one observation. Called from events and the periodic tick."""
        if self._stopped and not force:
            return
        observed_at = (snapshot or {}).get("observed_at") or dt_util.utcnow().isoformat()
        async with self._lock:
            if self._stopped and not force:
                return
            switch = snapshot.get("switch") if snapshot is not None else self.hass.states.get(self.config.get("switch_entity"))
            on = switch is not None and switch.state == "on"
            off = switch is not None and switch.state == "off"
            meter = (_read_number(snapshot.get("energy"), _ENERGY_UNITS, cumulative=True)
                     if snapshot is not None and self.energy_configured
                     else self.energy_meter_kwh)
            power_state = snapshot.get("power") if snapshot is not None else self.hass.states.get(self.config.get("power_entity"))
            power = _read_number(power_state, _POWER_UNITS) if self.power_configured else None
            changed = False
            if on:
                changed_at = self._changed_at(switch)
                # A changed last_changed timestamp can reveal an off/on cycle
                # while HA was unavailable; do not reuse an old baseline.
                new_session = not self._session_active or (changed_at and self._switch_changed and changed_at != self._switch_changed)
                if new_session:
                    was_active = self._session_active
                    saw_off_before = self._saw_off
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
                    if self._integrate_power and self._last_power_at is None:
                        self._invalid = True
                        self._session_energy = None
                    self._saw_off = False
                    self._low_since = None
                    self._persistent_sent = self._mobile_sent = False
                    self._last_attempt = {}
                    self.alarm_active = False
                    if not was_active:
                        # An already-on switch seen at startup has an unknown
                        # true start. Only an observed off->on establishes it.
                        self._history_start = (changed_at or observed_at) if saw_off_before else None
                        self._history_time_complete = self._history_start is not None
                    else:
                        # on->unknown->on (or a restart) can hide a cycle;
                        # keep one uncertain record rather than inventing two.
                        self._history_time_complete = False
                    changed = True
                if self._integrate_power and not new_session and not self._invalid:
                    self._integrate_power_until(observed_at, power)
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
                if not self._stopped and self.config.get("power_alarm_enabled", True) and self.power_configured and power is not None and power < self._threshold():
                    now = dt_util.utcnow()
                    if self._low_since is None:
                        self._low_since = now
                    self.alarm_active = now - self._low_since >= timedelta(minutes=self._delay())
                    if self.alarm_active:
                        await self._send_notifications(self._power_epoch)
                else:
                    self._low_since = None
                    self.alarm_active = False
            elif off:
                self._saw_off = True
                if self._session_active:
                    if self._integrate_power and not self._invalid:
                        self._integrate_power_until(observed_at, power)
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
                    changed = True
                self._low_since = None
                self.alarm_active = False
            else:
                # A disconnected switch is not evidence of either an off
                # transition or continuously low power. It may have changed
                # state while unavailable, so the whole energy session can no
                # longer be certified complete.
                if self._session_active and self.energy_configured and not self._invalid:
                    self._invalid = True
                    self._session_energy = None
                    changed = True
                if self._session_active and self._history_time_complete:
                    self._history_time_complete = False
                    changed = True
                # An off reading before a connectivity gap does not prove
                # that a later on reading coincided with its actual start.
                self._saw_off = False
                self._low_since = None
                self.alarm_active = False
            self._observed_switch = "on" if on else "off" if off else "unknown"
            self._restored_session = False
            if changed:
                await self._save()
        self._notify()

    async def _send_notifications(self, power_epoch):
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
            if (self._stopped or self._stopping or power_epoch != self._power_epoch or not current_switch or current_switch.state != "on"
                    or current_power is None or current_power >= self._threshold() or self._low_since is None):
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
