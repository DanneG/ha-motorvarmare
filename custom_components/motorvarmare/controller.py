"""Scheduling and ownership for one heater."""

from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta
import logging
import math
import re
import time as monotonic_time
from uuid import uuid4

from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, UnitOfTemperature
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN, CONF_SWITCH, CONF_TEMPERATURE, CONF_CALENDAR, CONF_TAG,
    DEFAULT_TAG, CONF_POST_DEPARTURE_ENABLED,
)
from .energy import EnergyMonitor
from .recurrence import expand_series, next_occurrence, parse_rule

_LOGGER = logging.getLogger(__name__)
_MAX_RUNTIME = timedelta(hours=4)
_CALENDAR_INTERVAL = 300
_CALENDAR_RETRY_INTERVAL = 30


def duration_for_temperature(temp: float) -> int:
    """Estimate minutes from Calix's temperature recommendations in Celsius."""
    if temp > 10:
        return 0
    if temp >= 0:
        return 60
    return min(180, math.ceil(60 - 6 * temp))


def tagged(text: str, tag: str) -> bool:
    """Do not mistake #bil10 for #bil1."""
    return bool(isinstance(text, str) and isinstance(tag, str) and tag
                and re.search(re.escape(tag) + r"(?![\w])", text, re.IGNORECASE))


def _calendar_terms(value):
    """Split comma- or newline-separated settings into nonempty terms."""
    if not isinstance(value, str):
        return []
    return [part.strip() for part in re.split(r"[,\r\n]+", value) if part.strip()]


def calendar_event_matches(summary, description, exact_titles, keywords, legacy_tag):
    """Match a complete title or a whole word/phrase/tag in event text.

    The legacy tag and hash tags preserve historical matching semantics.
    Other keywords require both word boundaries.
    """
    summary = summary if isinstance(summary, str) else ""
    description = description if isinstance(description, str) else ""
    title = summary.strip().casefold()
    if title and any(title == term.casefold() for term in _calendar_terms(exact_titles)):
        return True
    content = f"{summary}\n{description}"
    for term in _calendar_terms(keywords):
        # Hash tags keep the older tag boundary rule, including x#bil1.
        if term.startswith("#") and tagged(content, term):
            return True
        if not term.startswith("#") and re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", content, re.IGNORECASE):
            return True
    return tagged(content, legacy_tag)


class HeaterController:
    def __init__(self, hass, entry):
        self.hass, self.entry = hass, entry
        self.config = {**entry.data, **entry.options}
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self.manual_departure = None
        self.local_departures = []
        self.recurring_departures = []
        self.weekly_times = [time(7, 0) for _ in range(7)]
        self.weekly_enabled = [False] * 7
        self.status = "Väntar"
        self.next_departure = self.planned_start = self.temperature = None
        self.duration_minutes = 0
        self.source = self.error = None
        self.owned = False
        self._stop_requested = False
        self._temperature_blocked = False
        self.automation_paused = False
        self.pause_until = None
        self._skipped_departures = set()
        self._operational_active = set()
        self._operational_pending = set()
        self._operational_sent = set()
        self._start_unconfirmed = False
        self._stop_unconfirmed = False
        self._uncertain_start_until = None
        self._active_departure = self._started_at = None
        self._active_source = None
        self._extended_until = None
        self._resume_extended_until = None
        self._resume_switch = None
        self._resume_departure = self._resume_source = self._resume_started_at = None
        self._suppressed = set()
        self._suppression_until = None
        self._suppression_exempt = set()
        self._calendar_events = []
        self._calendar_checked = float("-inf")
        self._calendar_ok = not bool(self.config.get(CONF_CALENDAR))
        self._calendar_error = None
        self._lock = asyncio.Lock()
        self._unsub = None
        self.energy = EnergyMonitor(hass, entry, self.config, self._notify)

    def _notify(self):
        async_dispatcher_send(self.hass, f"{DOMAIN}_{self.entry.entry_id}")

    @staticmethod
    def _parse(value):
        if not value:
            return None
        parsed = dt_util.parse_datetime(value) if isinstance(value, str) else value
        return dt_util.as_utc(parsed) if parsed else None

    async def async_load(self):
        data = await self.store.async_load() or {}
        try:
            await self.energy.async_load()
        except Exception:
            _LOGGER.exception("Unable to restore energy monitoring for %s", self.entry.title)
        self.manual_departure = self._parse(data.get("manual_departure"))
        self.local_departures = []
        for item in data.get("local_departures", []):
            if not isinstance(item, dict) or not isinstance(item.get("uid"), str):
                continue
            try:
                departure = self._parse(item.get("departure"))
            except (TypeError, ValueError):
                continue
            if departure:
                summary = item.get("summary")
                self.local_departures.append({"uid": item["uid"], "departure": departure,
                                              "summary": summary if isinstance(summary, str) and summary.strip() else "Avresa"})
        self.recurring_departures = []
        for item in data.get("recurring_departures", []):
            if not isinstance(item, dict) or not isinstance(item.get("uid"), str):
                continue
            try:
                departure = self._parse(item.get("departure"))
                parse_rule(item.get("rrule"))
            except (TypeError, ValueError, OverflowError):
                continue
            if departure:
                exceptions = item.get("exceptions")
                overrides = []
                stored_overrides = item.get("overrides")
                for override in stored_overrides if isinstance(stored_overrides, list) else []:
                    try:
                        original = self._parse(override.get("recurrence_id"))
                        moved = self._parse(override.get("departure"))
                        if original and moved:
                            overrides.append({"recurrence_id": original.isoformat(), "departure": moved,
                                              "summary": override.get("summary") or "Avresa"})
                    except (AttributeError, TypeError, ValueError):
                        continue
                self.recurring_departures.append({"uid": item["uid"], "departure": departure,
                    "summary": item.get("summary") or "Avresa", "rrule": item["rrule"],
                    "exceptions": [x for x in exceptions if isinstance(x, str)] if isinstance(exceptions, list) else [],
                    "overrides": overrides})
        for i, item in enumerate(data.get("weekly_times", [])[:7]):
            try:
                self.weekly_times[i] = time.fromisoformat(item)
            except (ValueError, TypeError):
                pass
        for i, item in enumerate(data.get("weekly_enabled", [])[:7]):
            self.weekly_enabled[i] = bool(item)
        self.owned = bool(data.get("owned"))
        self._stop_requested = bool(data.get("stop_requested"))
        self._temperature_blocked = bool(data.get("temperature_blocked"))
        self._uncertain_start_until = self._parse(data.get("uncertain_start_until"))
        self.automation_paused = bool(data.get("automation_paused"))
        self.pause_until = self._parse(data.get("pause_until"))
        self._skipped_departures = {item for item in data.get("skipped_departures", []) if isinstance(item, str)}
        self._active_departure = self._parse(data.get("active_departure"))
        self._started_at = self._parse(data.get("started_at"))
        self._active_source = data.get("active_source")
        self._extended_until = self._parse(data.get("extended_until"))
        self._resume_extended_until = self._parse(data.get("resume_extended_until"))
        self._resume_switch = data.get("resume_switch")
        self._resume_departure = self._parse(data.get("resume_departure"))
        self._resume_source = data.get("resume_source")
        self._resume_started_at = self._parse(data.get("resume_started_at"))
        stored = data.get("suppressed")
        self._suppressed = ({stored} if isinstance(stored, str) else
                            {item for item in stored if isinstance(item, str)} if isinstance(stored, list) else set())
        exempt = data.get("suppression_exempt")
        self._suppression_exempt = {item for item in exempt if isinstance(item, str)} if isinstance(exempt, list) else set()
        try:
            self._suppression_until = self._parse(data.get("suppression_until"))
        except (TypeError, ValueError):
            self._suppression_until = None
        # Older versions stored only one suppressed source/time string.
        if self._suppression_until is None:
            for key in self._suppressed:
                try:
                    moment = self._parse(key.rsplit("|", 1)[1])
                except (IndexError, TypeError, ValueError):
                    continue
                if moment and (self._suppression_until is None or moment > self._suppression_until):
                    self._suppression_until = moment

    async def _save(self):
        def iso(value):
            return value.isoformat() if value else None
        await self.store.async_save({
            "manual_departure": iso(self.manual_departure),
            "local_departures": [{"uid": item["uid"], "departure": iso(item["departure"]),
                                  "summary": item.get("summary", "Avresa")}
                                 for item in self.local_departures],
            "recurring_departures": [{"uid": item["uid"], "departure": iso(item["departure"]),
                "summary": item.get("summary", "Avresa"), "rrule": item["rrule"],
                "exceptions": list(item.get("exceptions", [])),
                "overrides": [{"recurrence_id": override["recurrence_id"],
                               "departure": iso(override["departure"]), "summary": override["summary"]}
                              for override in item.get("overrides", [])]} for item in self.recurring_departures],
            "weekly_times": [t.isoformat() for t in self.weekly_times],
            "weekly_enabled": self.weekly_enabled,
            "owned": self.owned,
            "stop_requested": self._stop_requested,
            "temperature_blocked": self._temperature_blocked,
            "uncertain_start_until": iso(self._uncertain_start_until),
            "automation_paused": self.automation_paused,
            "pause_until": iso(self.pause_until),
            "skipped_departures": sorted(self._skipped_departures),
            "active_departure": iso(self._active_departure),
            "started_at": iso(self._started_at),
            "active_source": self._active_source,
            "extended_until": iso(self._extended_until),
            "resume_extended_until": iso(self._resume_extended_until),
            "resume_switch": self._resume_switch,
            "resume_departure": iso(self._resume_departure),
            "resume_source": self._resume_source,
            "resume_started_at": iso(self._resume_started_at),
            "suppressed": sorted(self._suppressed),
            "suppression_until": iso(self._suppression_until),
            "suppression_exempt": sorted(self._suppression_exempt),
        })

    async def async_set_manual_departure(self, value):
        async with self._lock:
            self.manual_departure = self._parse(value)
            await self._save()
        await self.async_update()

    @property
    def skipped_departure(self):
        """Return the next intentionally skipped departure for display."""
        moments = [self._parse(item) for item in self._skipped_departures]
        return min((item for item in moments if item is not None), default=None)

    async def async_skip_next(self):
        """Skip the next scheduled departure without changing any calendar."""
        async with self._lock:
            now = dt_util.utcnow()
            candidates = self._candidates(now)
            if not candidates:
                raise ValueError("no_departure_to_skip")
            moment = candidates[0][0]
            self._skipped_departures.add(moment.isoformat())
            if self.owned and self._active_source != "Starta nu" and self._active_departure == moment:
                self._stop_requested = True
                self._resume_departure = self._resume_source = self._resume_started_at = None
                self._resume_extended_until = self._resume_switch = None
            await self._save()
        await self.async_update()

    async def async_set_pause_until(self, value):
        """Set an optional automatic resume time; it does not start a pause."""
        moment = self._parse(value)
        if moment and moment <= dt_util.utcnow():
            raise ValueError("pause_until_past")
        async with self._lock:
            self.pause_until = moment
            await self._save()
        await self.async_update()

    async def async_set_paused(self, value):
        """Pause scheduled starts while retaining manual Start now."""
        async with self._lock:
            self.automation_paused = bool(value)
            if not value or (self.pause_until and self.pause_until <= dt_util.utcnow()):
                self.pause_until = None
            if value:
                self._resume_departure = self._resume_source = self._resume_started_at = None
                self._resume_extended_until = self._resume_switch = None
                if self.owned and self._active_source != "Starta nu":
                    self._stop_requested = True
            await self._save()
        await self.async_update()

    async def async_add_local_departure(self, moment, summary=None, rrule=None):
        """Add one departure in the integration's own calendar."""
        if not isinstance(moment, datetime):
            raise ValueError("departure_invalid")
        moment = dt_util.as_utc(moment)
        if moment <= dt_util.utcnow():
            raise ValueError("departure_past")
        title = summary.strip() if isinstance(summary, str) and summary.strip() else "Avresa"
        if rrule:
            parse_rule(rrule)
            if not next_occurrence({"uid": "validation", "departure": moment, "summary": title,
                                    "rrule": rrule, "exceptions": []}, moment):
                raise ValueError("recurring_unsupported")
        uid = str(uuid4())
        async with self._lock:
            if rrule:
                self.recurring_departures.append({"uid": uid, "departure": moment, "summary": title,
                                                  "rrule": rrule, "exceptions": []})
            else:
                self.local_departures.append({"uid": uid, "departure": moment, "summary": title})
                self.local_departures.sort(key=lambda item: item["departure"])
            key = f"Planerad|{moment.isoformat()}"
            if self._suppression_until is not None and self._suppression_until > dt_util.utcnow():
                # A newly created event is an explicit request to schedule it,
                # including when its interval overlaps a previously stopped run.
                self._suppressed.discard(key)
                self._suppression_exempt.add(key)
            await self._save()
        await self.async_update()
        return uid

    def local_events_between(self, start, end):
        """Return local one-off and recurring departures in a bounded interval."""
        events = [dict(item) for item in self.local_departures if start <= item["departure"] < end]
        for item in self.recurring_departures:
            events.extend(expand_series(item, start, end))
        return sorted(events, key=lambda item: item["departure"])

    async def async_update_local_departure(self, uid, moment, summary=None, rrule=None, recurrence_id=None):
        """Replace an event or one instance in a single storage transaction."""
        if not isinstance(moment, datetime) or moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("departure_invalid")
        moment = dt_util.as_utc(moment)
        title = summary.strip() if isinstance(summary, str) and summary.strip() else "Avresa"
        if rrule:
            parse_rule(rrule)
        now = dt_util.utcnow()
        async with self._lock:
            oneoffs = list(self.local_departures)
            series_list = list(self.recurring_departures)
            series = next((item for item in series_list if item["uid"] == uid), None)
            oneoff = next((item for item in oneoffs if item["uid"] == uid), None)
            if series is None and oneoff is None:
                raise ValueError("departure_not_found")
            if recurrence_id:
                if series is None or (rrule and rrule != series["rrule"]):
                    raise ValueError("recurring_unsupported")
                try:
                    original = self._parse(recurrence_id)
                    if original is None:
                        raise ValueError
                    key = original.isoformat()
                    old_override = next((x for x in series.get("overrides", []) if x["recurrence_id"] == key), None)
                    if not old_override and not expand_series(series, original, original + timedelta(microseconds=1)):
                        raise ValueError
                except (TypeError, ValueError, OverflowError) as exc:
                    raise ValueError("departure_not_found") from exc
                if moment <= now:
                    raise ValueError("departure_past")
                modified = dict(series)
                exceptions = [x for x in series.get("exceptions", []) if x != key]
                overrides = [x for x in series.get("overrides", []) if x["recurrence_id"] != key]
                if moment != original or title != series.get("summary"):
                    exceptions.append(key)
                    overrides.append({"recurrence_id": key, "departure": moment, "summary": title})
                modified.update(exceptions=exceptions, overrides=overrides)
                series_list[series_list.index(series)] = modified
            elif rrule:
                modified = {"uid": uid, "departure": moment, "summary": title, "rrule": rrule,
                            "exceptions": [], "overrides": []}
                if series is not None and series["departure"] == moment and series["rrule"] == rrule:
                    modified["exceptions"] = list(series.get("exceptions", []))
                    modified["overrides"] = list(series.get("overrides", []))
                future = next_occurrence(modified, now + timedelta(microseconds=1))
                if not future:
                    raise ValueError("recurring_unsupported")
                if series is not None:
                    series_list[series_list.index(series)] = modified
                else:
                    oneoffs.remove(oneoff)
                    series_list.append(modified)
            else:
                if moment <= now:
                    raise ValueError("departure_past")
                modified = {"uid": uid, "departure": moment, "summary": title}
                if series is not None:
                    series_list.remove(series)
                    oneoffs.append(modified)
                else:
                    oneoffs[oneoffs.index(oneoff)] = modified
            oneoffs.sort(key=lambda item: item["departure"])
            old_oneoffs, old_series = self.local_departures, self.recurring_departures
            self.local_departures, self.recurring_departures = oneoffs, series_list
            try:
                await self._save()
            except BaseException:
                self.local_departures, self.recurring_departures = old_oneoffs, old_series
                raise
        await self.async_update()

    async def async_delete_local_departure(self, uid, recurrence_id=None):
        """Remove an event owned by this car, never an external event."""
        async with self._lock:
            series = next((item for item in self.recurring_departures if item["uid"] == uid), None)
            if series is not None:
                if recurrence_id:
                    try:
                        moment = self._parse(recurrence_id)
                        key = moment.isoformat() if moment else None
                        override = next((x for x in series.get("overrides", []) if x["recurrence_id"] == key), None)
                        if not moment or (not override and not expand_series(series, moment, moment + timedelta(microseconds=1))):
                            raise ValueError("departure_not_found")
                    except (TypeError, ValueError, OverflowError) as exc:
                        raise ValueError("departure_not_found") from exc
                    modified = dict(series)
                    modified["exceptions"] = list(series.get("exceptions", []))
                    if key not in modified["exceptions"]:
                        modified["exceptions"].append(key)
                    modified["overrides"] = [x for x in series.get("overrides", []) if x["recurrence_id"] != key]
                    changed = [modified if x is series else x for x in self.recurring_departures]
                else:
                    changed = [x for x in self.recurring_departures if x is not series]
                previous, self.recurring_departures = self.recurring_departures, changed
                try:
                    await self._save()
                except BaseException:
                    self.recurring_departures = previous
                    raise
            else:
                if recurrence_id:
                    raise ValueError("departure_not_found")
                remaining = [item for item in self.local_departures if item["uid"] != uid]
                if len(remaining) == len(self.local_departures):
                    raise ValueError("departure_not_found")
                previous, self.local_departures = self.local_departures, remaining
                try:
                    await self._save()
                except BaseException:
                    self.local_departures = previous
                    raise
        await self.async_update()

    async def async_set_weekly_time(self, day, value):
        async with self._lock:
            self.weekly_times[day] = value.replace(tzinfo=None)
            await self._save()
        await self.async_update()

    async def async_set_weekly_enabled(self, day, value):
        async with self._lock:
            self.weekly_enabled[day] = value
            await self._save()
        await self.async_update()

    @property
    def active_until(self):
        """When an owned heating session should end, including Starta nu."""
        if not self.owned:
            return None
        end = self._heating_end(self._active_departure, self._active_source)
        if end is None or self._started_at is None:
            return end
        if self._extended_until:
            end = max(end, self._extended_until)
        return min(end, self._started_at + _MAX_RUNTIME)

    @property
    def can_extend(self):
        """Allow extension only for a confirmed, currently running owned session."""
        now = dt_util.utcnow()
        state = self.hass.states.get(self.config[CONF_SWITCH])
        temp = self._temperature()
        return bool(self.owned and not self._stop_requested and not self._temperature_blocked
                    and state and state.state == STATE_ON and temp is not None and temp <= 10
                    and self._started_at and self.active_until and now < self.active_until
                    and self.active_until < self._started_at + _MAX_RUNTIME)

    async def async_extend_30(self):
        """Extend this run by up to 30 minutes without changing a departure."""
        async with self._lock:
            if not self.can_extend:
                raise ValueError("cannot_extend")
            previous = self._extended_until
            self._extended_until = min(self.active_until + timedelta(minutes=30), self._started_at + _MAX_RUNTIME)
            try:
                await self._save()
            except BaseException:
                self._extended_until = previous
                raise
            self._notify()

    @property
    def post_departure_minutes(self):
        return 30 if self.config.get(CONF_POST_DEPARTURE_ENABLED, False) else 0

    def _heating_end(self, departure, source):
        if not departure:
            return None
        return departure + timedelta(minutes=self.post_departure_minutes if source != "Starta nu" else 0)

    async def async_start_now(self):
        """Start one bounded session and persist ownership before the command."""
        async with self._lock:
            state = self.hass.states.get(self.config[CONF_SWITCH])
            if not state or state.state not in (STATE_ON, STATE_OFF):
                raise ValueError("switch_unavailable")
            if state.state == STATE_ON or self.owned:
                raise ValueError("already_on")
            temperature = self._temperature()
            if temperature is None:
                raise ValueError("temperature_unavailable")
            duration = duration_for_temperature(temperature)
            if duration <= 0:
                raise ValueError("zero_runtime")
            now = dt_util.utcnow()
            self._resume_departure = self._resume_source = self._resume_started_at = None
            self._extended_until = self._resume_extended_until = self._resume_switch = None
            self.owned = True
            self._stop_requested = False
            self._active_departure = now + timedelta(minutes=duration)
            self._started_at = now
            self._active_source = "Starta nu"
            await self._save()
            try:
                if not await self._turn_on_confirmed():
                    raise RuntimeError("Switch did not confirm on")
            except Exception as exc:
                await self._abort_unconfirmed_start()
                self.status = "Fel"
                self.error = "Kunde inte slå på brytaren"
                self._notify()
                self._schedule_operational_alerts()
                raise ValueError("turn_on_failed") from exc
            self.temperature = temperature
            self.status = "Värmer"
            self.error = None
            self._notify()

    def _suppress_current_run(self, now, candidates):
        """Keep an explicit stop effective across connected heating windows."""
        self._resume_departure = self._resume_source = self._resume_started_at = None
        self._resume_extended_until = self._resume_switch = None
        self._suppression_exempt.clear()
        self._suppression_until = max(now, self.active_until or now)
        if self._active_source and self._active_source != "Starta nu" and self._active_departure:
            self._suppressed.add(f"{self._active_source}|{self._active_departure.isoformat()}")
        self._reconcile_suppression(now, candidates)

    def _reconcile_suppression(self, now, candidates):
        """Extend a stopped interval when scheduled heating windows overlap.

        Re-evaluating on every tick covers later calendar changes and a falling
        temperature moving a planned start earlier. Unknown temperatures never
        start the heater, and the stop is reconciled when a reading returns.
        """
        previous = (self._suppression_until, frozenset(self._suppressed), frozenset(self._suppression_exempt))
        if self._suppression_until is not None:
            temperature = self._temperature()
            minutes = duration_for_temperature(temperature) if temperature is not None else 0
            # Cache can still tell us about a heating window when the external
            # calendar is temporarily unavailable; do not start from it.
            entries = list(candidates)
            if not self._calendar_ok:
                entries.extend((moment, source) for moment, source in self._calendar_events if moment > now)
            if minutes:
                for departure, source in sorted(entries, key=lambda item: item[0]):
                    key = f"{source}|{departure.isoformat()}"
                    if key not in self._suppression_exempt and departure - timedelta(minutes=minutes) <= self._suppression_until:
                        self._suppressed.add(key)
                        end = self._heating_end(departure, source)
                        if end > self._suppression_until:
                            self._suppression_until = end
            if now >= self._suppression_until:
                self._suppression_until = None
        def still_future(key):
            try:
                departure = self._parse(key.rsplit("|", 1)[1])
                source = key.rsplit("|", 1)[0]
                return departure is not None and self._heating_end(departure, source) > now
            except (IndexError, TypeError, ValueError):
                return False
        self._suppressed = {key for key in self._suppressed if still_future(key)}
        self._suppression_exempt = {key for key in self._suppression_exempt if still_future(key)}
        return previous != (self._suppression_until, frozenset(self._suppressed), frozenset(self._suppression_exempt))

    async def async_stop_now(self):
        """Stop only an owned session and persist a retry if it fails."""
        async with self._lock:
            if not self.owned:
                raise ValueError("not_owned")
            now = dt_util.utcnow()
            self._suppress_current_run(now, self._candidates(now))
            self._stop_requested = True
            await self._save()
            if not await self._turn_off():
                self.status = "Fel"
                self.error = "Kunde inte stänga av brytaren; försöker igen"
                self._notify()
                self._schedule_operational_alerts()
                raise ValueError("turn_off_failed")
            self.status = "Avstängd"
            self.error = None
            self._notify()

    async def async_start(self):
        self._unsub = async_track_time_interval(self.hass, self._tick, timedelta(minutes=1))
        try:
            await self.energy.async_start()
        except Exception:
            _LOGGER.exception("Unable to start energy monitoring for %s", self.entry.title)
        await self.async_update()

    @callback
    def _tick(self, _now):
        self.hass.async_create_task(self.async_update())

    async def async_shutdown(self):
        async with self._lock:
            now = dt_util.utcnow()
            if (self.owned and not self._stop_requested and not self._temperature_blocked
                    and (not self.automation_paused or self._active_source == "Starta nu")
                    and self._extended_until and self.active_until and self.active_until > now
                    and self._active_departure and self._active_source and self._started_at
                    and now < self._started_at + _MAX_RUNTIME):
                self._resume_departure, self._resume_source, self._resume_started_at = (
                    self._active_departure, self._active_source, self._started_at)
                # A later overlapping departure can extend the natural end
                # past the explicit extension; retain the actual planned end.
                self._resume_extended_until = self.active_until
                self._resume_switch = self.config[CONF_SWITCH]
                await self._save()
            elif (self.owned and not self._stop_requested and not self.automation_paused and not self._temperature_blocked
                    and self.post_departure_minutes and self._active_source != "Starta nu"
                    and self._active_departure and self._started_at
                    and self._active_departure <= now < self._heating_end(self._active_departure, self._active_source)
                    and now < self._started_at + _MAX_RUNTIME):
                self._resume_departure, self._resume_source, self._resume_started_at = (
                    self._active_departure, self._active_source, self._started_at)
                await self._save()
            if self.owned and not await self._turn_off():
                self.error = "Kunde inte stänga av brytaren"
                self._notify()
                self._schedule_operational_alerts()
                return False
            if self._unsub:
                self._unsub()
                self._unsub = None
            try:
                await self.energy.async_shutdown()
            except Exception:
                _LOGGER.exception("Unable to stop energy monitoring for %s", self.entry.title)
            return True

    async def _turn_off(self):
        entity_id = self.config[CONF_SWITCH]
        state = self.hass.states.get(entity_id)
        uncertain = self._uncertain_start_until is not None
        try:
            if uncertain or not state or state.state != STATE_OFF:
                await asyncio.wait_for(
                    self.hass.services.async_call("switch", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True),
                    timeout=10,
                )
                # Allow state updates from the integration to arrive; do not
                # discard ownership merely because a service call succeeded.
                for _ in range(10):
                    state = self.hass.states.get(entity_id)
                    if state and state.state == STATE_OFF:
                        break
                    await asyncio.sleep(0.3)
            if not state or state.state != STATE_OFF:
                self._stop_unconfirmed = True
                return False
        except Exception:
            self._stop_unconfirmed = True
            _LOGGER.exception("Unable to turn off heater for %s", self.entry.title)
            return False
        # A reported OFF may predate a delayed ON command. Keep ownership and
        # actively repeat OFF while that outcome remains uncertain.
        if uncertain and dt_util.utcnow() < self._uncertain_start_until:
            self._stop_unconfirmed = True
            return False
        self._uncertain_start_until = None
        self._stop_unconfirmed = False
        self.owned = False
        self._stop_requested = False
        self._active_departure = self._started_at = None
        self._active_source = None
        self._extended_until = None
        await self._save()
        return True

    async def _abort_unconfirmed_start(self):
        """Persist a pending stop and actively cancel a possibly delayed ON."""
        self._stop_requested = True
        self._uncertain_start_until = dt_util.utcnow() + timedelta(minutes=2)
        try:
            await self._save()
        except Exception:
            _LOGGER.exception("Unable to persist unconfirmed start for %s", self.entry.title)
        return await self._turn_off()

    async def _turn_on_confirmed(self):
        """Request switch-on and verify the physical entity reports on."""
        entity_id = self.config[CONF_SWITCH]
        try:
            await asyncio.wait_for(self.hass.services.async_call(
                "switch", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True), timeout=10)
            for _ in range(10):
                state = self.hass.states.get(entity_id)
                if state and state.state == STATE_ON:
                    self._start_unconfirmed = False
                    return True
                await asyncio.sleep(0.3)
        except Exception:
            _LOGGER.warning("Unable to confirm heater switch on for %s", self.entry.title, exc_info=True)
        self._start_unconfirmed = True
        return False

    async def _read_calendar(self, now):
        entity_id = self.config.get(CONF_CALENDAR)
        if not entity_id:
            self._calendar_events = []
            self._calendar_ok = True
            self._calendar_error = None
            return
        interval = _CALENDAR_INTERVAL if self._calendar_ok else _CALENDAR_RETRY_INTERVAL
        if monotonic_time.monotonic() - self._calendar_checked < interval:
            return
        self._calendar_checked = monotonic_time.monotonic()
        try:
            response = await asyncio.wait_for(self.hass.services.async_call(
                "calendar", "get_events", {ATTR_ENTITY_ID: entity_id,
                    "start_date_time": (now - timedelta(minutes=self.post_departure_minutes)).isoformat(),
                    "end_date_time": (now + timedelta(days=8)).isoformat()},
                blocking=True, return_response=True), timeout=10)
            if not isinstance(response, dict) or entity_id not in response:
                raise ValueError("Kalendern gav inget svar")
            raw = response[entity_id]["events"]
            result = []
            for event in raw:
                if not isinstance(event, dict):
                    continue
                start = event.get("start")
                # Dates without a time are all-day events, not departures.
                # Calendar responses may use a space instead of T as separator.
                if not isinstance(start, datetime) and not (
                    isinstance(start, str) and re.match(r"^\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}", start)
                ):
                    continue
                try:
                    moment = self._parse(start)
                except (ValueError, TypeError):
                    continue
                if moment and moment > now - timedelta(minutes=self.post_departure_minutes) and calendar_event_matches(
                    event.get("summary"), event.get("description"),
                    self.config.get("event_titles"), self.config.get("event_keywords"),
                    self.config.get(CONF_TAG, DEFAULT_TAG),
                ):
                    result.append((moment, "Kalender"))
            self._calendar_events = result
            self._calendar_ok = True
            self._calendar_error = None
        except TimeoutError:
            self._calendar_ok = False
            self._calendar_error = "Kalendern svarade inte i tid; försöker igen"
            _LOGGER.warning("Calendar %s timed out when reading events", entity_id)
        except Exception:
            self._calendar_ok = False
            self._calendar_error = "Kalendern kan inte läsas; se Home Assistants logg"
            _LOGGER.warning("Could not read calendar %s", entity_id, exc_info=True)

    def _candidates(self, now, include_recent=False, include_skipped=False):
        # An unverified cached event must not block a valid manual departure.
        cutoff = now - timedelta(minutes=self.post_departure_minutes) if include_recent else now
        result = [(moment, src) for moment, src in self._calendar_events if moment > cutoff] if self._calendar_ok else []
        if self.manual_departure and self.manual_departure > cutoff:
            result.append((self.manual_departure, "Manuell"))
        result.extend((item["departure"], "Planerad") for item in self.local_departures
                      if item["departure"] > cutoff)
        for series in self.recurring_departures:
            occurrences = expand_series(series, cutoff + timedelta(microseconds=1), now + timedelta(days=9))
            if not occurrences:
                next_item = next_occurrence(series, now + timedelta(microseconds=1))
                occurrences = [next_item] if next_item else []
            result.extend((item["departure"], "Planerad") for item in occurrences)
        local_now = dt_util.as_local(now)
        for offset in range(-1 if include_recent and self.post_departure_minutes else 0, 8):
            day = local_now.date() + timedelta(days=offset)
            weekday = day.weekday()
            if self.weekly_enabled[weekday]:
                local = datetime.combine(day, self.weekly_times[weekday], tzinfo=dt_util.get_default_time_zone())
                moment = dt_util.as_utc(local)
                # A spring-forward time may not exist. Skip that occurrence.
                if dt_util.as_local(moment).replace(tzinfo=None) != local.replace(tzinfo=None):
                    continue
                if moment > cutoff:
                    result.append((moment, "Veckoschema"))
        if (not include_recent and not self.owned and self._resume_departure and self._resume_source and self._resume_started_at
                and self._resume_departure <= now < self._heating_end(self._resume_departure, self._resume_source)
                and now < self._resume_started_at + _MAX_RUNTIME
                and (self._resume_departure, self._resume_source) in self._candidates(now, include_recent=True)):
            result.append((self._resume_departure, self._resume_source))
        return sorted((item for item in result if include_skipped or item[0].isoformat() not in self._skipped_departures), key=lambda item: item[0])

    def _handoff_overlapping_departure(self, now):
        """Extend an owned scheduled run only into a connected heating window."""
        if (not self.owned or not self._active_departure or not self._started_at
                or self._active_source == "Starta nu" or now >= self._started_at + _MAX_RUNTIME):
            return False
        temperature = self._temperature()
        minutes = duration_for_temperature(temperature) if temperature is not None else 0
        if not minutes or self._temperature_blocked:
            return False
        changed = False
        for departure, source in self._candidates(now, include_recent=True):
            key = f"{source}|{departure.isoformat()}"
            if (departure > self._active_departure and self._heating_end(departure, source) > now and key not in self._suppressed
                    and departure - timedelta(minutes=minutes) <= min(now, self.active_until)):
                self._active_departure, self._active_source = departure, source
                changed = True
        return changed

    @property
    def schedule_7_days(self):
        """Upcoming departures through the next seven local calendar days.

        Planned starts use the latest available temperature, not a forecast.
        """
        now = dt_util.utcnow()
        local_now = dt_util.as_local(now)
        end_date = local_now.date() + timedelta(days=7)
        end = dt_util.as_utc(datetime.combine(end_date, time.min, tzinfo=dt_util.get_default_time_zone()))
        temperature = self._temperature()
        minutes = duration_for_temperature(temperature) if temperature is not None else None
        locals_by_time = {}
        for item in self.local_events_between(now - timedelta(minutes=self.post_departure_minutes), end + _MAX_RUNTIME):
            locals_by_time.setdefault(item["departure"], []).append(item)
        schedule = []
        candidates = self._candidates(now, include_skipped=True)
        if (self.owned and self._active_source != "Starta nu" and self._active_departure
                and self._active_departure <= now < self.active_until):
            candidates.append((self._active_departure, self._active_source))
        for departure, source in sorted(candidates):
            start = departure - timedelta(minutes=minutes) if minutes and not self._temperature_blocked else None
            # Include a departure just beyond the display range when its
            # heating interval starts on the final visible local day.
            if departure >= end and (start is None or start >= end):
                continue
            local = locals_by_time[departure].pop(0) if source == "Planerad" and locals_by_time.get(departure) else None
            schedule.append({
                "departure": departure.isoformat(),
                "start": start.isoformat() if start else None,
                "end": self._heating_end(departure, source).isoformat(),
                "source": source,
                "duration_minutes": minutes,
                "uid": local["uid"] if local else None,
                "recurrence_id": local.get("recurrence_id") if local else None,
                "rrule": local.get("rrule") if local else None,
                "series_start": local.get("series_start") if local else None,
                "series_summary": local.get("series_summary") if local else None,
                "exceptions_count": local.get("exceptions_count", 0) if local else 0,
                "summary": local.get("summary", "Avresa") if local else "Avresa",
                "removable": local is not None,
                "suppressed": departure.isoformat() in self._skipped_departures or f"{source}|{departure.isoformat()}" in self._suppressed,
            })
        return schedule

    async def async_schedule_between(self, first_day, last_day, include_external=True, include_boundary_candidates=False):
        """Project a short local-date window without changing heater control.

        The end date is exclusive. External-calendar errors do not change the
        scheduler cache and are explicitly returned to the requesting client.
        """
        if not 1 <= (last_day - first_day).days <= 31:
            raise ValueError("invalid_schedule_range")
        zone = dt_util.get_default_time_zone()
        start = dt_util.as_utc(datetime.combine(first_day, time.min, tzinfo=zone))
        end = dt_util.as_utc(datetime.combine(last_day, time.min, tzinfo=zone))
        query_end = end + _MAX_RUNTIME
        query_start = start - timedelta(minutes=self.post_departure_minutes)
        entries = [(item["departure"], "Planerad", item) for item in self.local_events_between(query_start, query_end)]
        if self.manual_departure and query_start <= self.manual_departure < query_end:
            entries.append((self.manual_departure, "Manuell", None))
        day = first_day - timedelta(days=1) if self.post_departure_minutes else first_day
        # Include early next-day departures whose heating starts before end.
        while day <= last_day:
            weekday = day.weekday()
            if self.weekly_enabled[weekday]:
                local = datetime.combine(day, self.weekly_times[weekday], tzinfo=zone)
                moment = dt_util.as_utc(local)
                if (dt_util.as_local(moment).replace(tzinfo=None) == local.replace(tzinfo=None)
                        and query_start <= moment < query_end):
                    entries.append((moment, "Veckoschema", None))
            day += timedelta(days=1)
        calendar_error = False
        entity_id = self.config.get(CONF_CALENDAR)
        if entity_id and not include_external:
            calendar_error = True
        elif entity_id:
            try:
                response = await asyncio.wait_for(self.hass.services.async_call(
                    "calendar", "get_events", {ATTR_ENTITY_ID: entity_id,
                        "start_date_time": query_start.isoformat(), "end_date_time": query_end.isoformat()},
                    blocking=True, return_response=True), timeout=10)
                raw_events = response[entity_id]["events"]
                for event in raw_events:
                    if not isinstance(event, dict):
                        continue
                    raw = event.get("start")
                    if not isinstance(raw, datetime) and not (isinstance(raw, str) and
                            re.match(r"^\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}", raw)):
                        continue
                    try:
                        moment = self._parse(raw)
                    except (ValueError, TypeError):
                        continue
                    if moment and query_start <= moment < query_end and calendar_event_matches(
                            event.get("summary"), event.get("description"),
                            self.config.get("event_titles"), self.config.get("event_keywords"),
                            self.config.get(CONF_TAG, DEFAULT_TAG)):
                        entries.append((moment, "Kalender", {"summary": event.get("summary") or "Avresa"}))
            except Exception:
                calendar_error = True
                _LOGGER.warning("Could not load projected calendar for %s", self.entry.title, exc_info=True)
        temperature = self._temperature()
        minutes = duration_for_temperature(temperature) if temperature is not None else None
        result = []
        for departure, source, local in sorted(entries, key=lambda x: x[0]):
            planned = departure - timedelta(minutes=minutes) if minutes and not self._temperature_blocked else None
            heating_end = self._heating_end(departure, source)
            if departure < start and (planned is None or heating_end <= start):
                continue
            if not include_boundary_candidates and departure >= end and (planned is None or planned >= end):
                continue
            owned_local = source == "Planerad" and local is not None
            result.append({"departure": departure.isoformat(), "start": planned.isoformat() if planned else None,
                           "end": heating_end.isoformat(),
                           "source": source, "duration_minutes": minutes,
                           "uid": local.get("uid") if owned_local else None,
                           "recurrence_id": local.get("recurrence_id") if owned_local else None,
                           "rrule": local.get("rrule") if owned_local else None,
                           "series_start": local.get("series_start") if owned_local else None,
                           "series_summary": local.get("series_summary") if owned_local else None,
                           "exceptions_count": local.get("exceptions_count", 0) if owned_local else 0,
                           "summary": local.get("summary", "Avresa") if local else "Avresa",
                           "removable": owned_local,
                           "suppressed": departure.isoformat() in self._skipped_departures or f"{source}|{departure.isoformat()}" in self._suppressed})
        return {"events": result, "calendar_error": calendar_error}

    def _temperature(self):
        state = self.hass.states.get(self.config[CONF_TEMPERATURE])
        if state is None:
            return None
        try:
            value = float(state.state)
        except (ValueError, TypeError):
            return None
        if not math.isfinite(value):
            return None
        unit = state.attributes.get("unit_of_measurement")
        if unit == UnitOfTemperature.FAHRENHEIT:
            value = (value - 32) * 5 / 9
        elif unit != UnitOfTemperature.CELSIUS:
            return None
        return value

    async def async_update(self):
        async with self._lock:
            try:
                await self._update_locked()
            except Exception:
                self.error = "Ett oväntat fel uppstod; kontrollera loggen"
                self.status = "Fel"
                _LOGGER.exception("Error updating heater for %s", self.entry.title)
            self._notify()
        # Monitoring is independent: a missing sensor or notification service
        # must never prevent the heater scheduler from running or switching off.
        try:
            await self.energy.async_update()
        except Exception:
            _LOGGER.exception("Error monitoring energy for %s", self.entry.title)
        await self._update_operational_alerts()

    def _operational_problems(self):
        """Gather active problems without assuming a constant value is stale."""
        problems = set()
        switch = self.hass.states.get(self.config.get(CONF_SWITCH))
        if not switch or switch.state not in (STATE_ON, STATE_OFF):
            problems.add("switch_unavailable")
        error = self.error or ""
        if self._start_unconfirmed or "Kunde inte slå på" in error:
            problems.add("start_failed")
        if self._stop_unconfirmed or "Kunde inte stänga av" in error or "Kunde inte bekräfta att brytaren är av" in error:
            problems.add("stop_failed")
        if self._temperature() is None:
            problems.add("temperature_unavailable")
        else:
            state = self.hass.states.get(self.config.get(CONF_TEMPERATURE))
            reported = getattr(state, "last_reported", None)
            try:
                age_limit = float(self.config.get("temperature_max_age_hours", 12))
                if age_limit > 0 and isinstance(reported, datetime) and dt_util.utcnow() - dt_util.as_utc(reported) > timedelta(hours=age_limit):
                    problems.add("temperature_stale")
            except (TypeError, ValueError, OverflowError):
                pass
        if self.config.get(CONF_CALENDAR) and not self._calendar_ok:
            problems.add("calendar_unavailable")
        return problems

    def _schedule_operational_alerts(self):
        if self.config.get("operation_alerts_enabled", False):
            self.hass.async_create_task(self._update_operational_alerts())

    async def _update_operational_alerts(self):
        """Send at most one notification per active problem and channel."""
        if not self.config.get("operation_alerts_enabled", False):
            self._operational_active.clear()
            self._operational_sent.clear()
            return
        problems = self._operational_problems()
        self._operational_active = problems
        self._operational_sent = {item for item in self._operational_sent if item[0] in problems}
        language = str(getattr(getattr(self.hass, "config", None), "language", "en") or "en").lower()
        sv = language.startswith("sv")
        messages = {
            "switch_unavailable": ("Brytaren är inte tillgänglig. Kontrollera anslutningen.", "The switch is unavailable. Check its connection."),
            "start_failed": ("Värmaren kunde inte bekräftas påslagen. Kontrollera brytaren.", "The heater switch did not confirm turning on. Check the switch."),
            "stop_failed": ("Värmaren kunde inte bekräftas avstängd. Kontrollera brytaren.", "The heater switch did not confirm turning off. Check the switch."),
            "temperature_unavailable": ("Utetemperaturen är inte tillgänglig. Kontrollera sensorn.", "Outdoor temperature is unavailable. Check the sensor."),
            "temperature_stale": ("Temperatursensorn verkar inte ha rapporterat på länge. Kontrollera sensorn.", "The temperature sensor has not reported recently. Check the sensor."),
            "calendar_unavailable": ("Kalendern kan inte läsas. Kontrollera kalenderanslutningen.", "The calendar cannot be read. Check its connection."),
        }
        title = ("Motorvärmare: " if sv else "Engine heater: ") + self.entry.title
        notify_entity = self.config.get("notify_entity")
        for problem in sorted(problems):
            message = messages[problem][0 if sv else 1]
            targets = [("persistent", "persistent_notification", "create", {"title": title, "message": message,
                       "notification_id": f"{DOMAIN}_{self.entry.entry_id}_{problem}"})]
            if isinstance(notify_entity, str) and notify_entity.startswith("notify."):
                targets.append(("mobile", "notify", "send_message", {"entity_id": notify_entity, "title": title, "message": message}))
            for channel, domain, service, data in targets:
                token = (problem, channel)
                if token in self._operational_sent or token in self._operational_pending or problem not in self._operational_active:
                    continue
                self._operational_pending.add(token)
                try:
                    await asyncio.wait_for(self.hass.services.async_call(domain, service, data, blocking=True), timeout=10)
                    if problem in self._operational_active:
                        self._operational_sent.add(token)
                except Exception:
                    _LOGGER.warning("Unable to send %s operational alert for %s", channel, self.entry.title, exc_info=True)
                finally:
                    self._operational_pending.discard(token)

    async def _update_locked(self):
        now = dt_util.utcnow()
        self.error = None
        if self.automation_paused and self.pause_until and now >= self.pause_until:
            self.automation_paused = False
            self.pause_until = None
            await self._save()
        retained_skips = {item for item in self._skipped_departures if (self._parse(item) or now) + timedelta(minutes=self.post_departure_minutes) > now}
        if retained_skips != self._skipped_departures:
            self._skipped_departures = retained_skips
            await self._save()
        retain_after = timedelta(minutes=self.post_departure_minutes)
        if self.manual_departure and self.manual_departure + retain_after <= now:
            self.manual_departure = None
            await self._save()
        remaining = [item for item in self.local_departures if item["departure"] + retain_after > now]
        if len(remaining) != len(self.local_departures):
            self.local_departures = remaining
            await self._save()
        # Extend only to already-connected windows before considering expiry.
        if (self.owned and self._active_departure and self.active_until and now >= self.active_until
                and self._handoff_overlapping_departure(now)):
            await self._save()
        # Expiry must never wait on a calendar server.
        if self.owned and (self._stop_requested or not self._active_departure or not self._started_at or
                           now >= self.active_until or now >= self._started_at + _MAX_RUNTIME):
            if self._active_departure and self._active_source and self._started_at and now >= self._started_at + _MAX_RUNTIME:
                self._suppress_current_run(now, self._candidates(now))
            if not await self._turn_off():
                self.status, self.error = "Fel", "Kunde inte bekräfta att brytaren är av; försöker igen"
                return
        temperature = self._temperature()
        if self._temperature_blocked and temperature is not None and temperature <= 9.5 and not self.owned:
            self._temperature_blocked = False
            await self._save()
        switch = self.hass.states.get(self.config[CONF_SWITCH])
        # Do not mistake a physical user stop for a temperature stop: the
        # existing manual-stop handling below must suppress the departure.
        if (self.owned and temperature is not None and temperature > 10
                and (not switch or switch.state != STATE_OFF)):
            self._temperature_blocked = True
            self._stop_requested = True
            self._resume_departure = self._resume_source = self._resume_started_at = None
            self._resume_extended_until = self._resume_switch = None
            try:
                # Record the pending stop before yielding to the switch, so
                # an interruption during the service call resumes shutdown.
                await self._save()
            except Exception:
                # A storage failure must never prevent the physical stop.
                _LOGGER.exception("Unable to persist temperature stop for %s", self.entry.title)
            if not await self._turn_off():
                await self._save()
                self.status, self.error = "Fel", "Kunde inte bekräfta att brytaren är av; försöker igen"
                return
        await self._read_calendar(now)
        now = dt_util.utcnow()
        # On a clean unload, the plug was switched off deliberately. Restore
        # an explicitly extended session only on the same configured plug.
        if self._resume_extended_until:
            resume_end = min(self._resume_extended_until, self._resume_started_at + _MAX_RUNTIME) if self._resume_started_at else None
            if (self._resume_switch != self.config[CONF_SWITCH] or not self._resume_departure
                    or not self._resume_source or not resume_end or now >= resume_end):
                self._resume_departure = self._resume_source = self._resume_started_at = None
                self._resume_extended_until = self._resume_switch = None
                await self._save()
            else:
                state = self.hass.states.get(self.config[CONF_SWITCH])
                temp = self._temperature()
                scheduled_valid = (self._resume_source == "Starta nu" or self._resume_departure <= now or
                                   (self._resume_departure, self._resume_source) in self._candidates(now, include_recent=True))
                if ((state and state.state == STATE_ON) or (temp is not None and temp > 10)
                        or (not scheduled_valid and (self._resume_source != "Kalender" or self._calendar_ok))):
                    self._resume_departure = self._resume_source = self._resume_started_at = None
                    self._resume_extended_until = self._resume_switch = None
                    await self._save()
                    scheduled_valid = False
                if (not self.owned and not self._stop_requested and not self._temperature_blocked
                        and (not self.automation_paused or self._resume_source == "Starta nu")
                        and state and state.state == STATE_OFF and temp is not None and temp <= 10 and scheduled_valid):
                    self.owned = True
                    self._active_departure, self._active_source, self._started_at = (
                        self._resume_departure, self._resume_source, self._resume_started_at)
                    self._extended_until = self._resume_extended_until
                    self._resume_departure = self._resume_source = self._resume_started_at = None
                    self._resume_extended_until = self._resume_switch = None
                    await self._save()
                    if not await self._turn_on_confirmed():
                        await self._abort_unconfirmed_start()
                        self.status, self.error = "Fel", "Kunde inte slå på brytaren; försöker stänga av"
                        return
        candidates = self._candidates(now)
        if self._reconcile_suppression(now, candidates):
            await self._save()
        switch = self.hass.states.get(self.config[CONF_SWITCH])
        if self.owned:
            expired = (not self._active_departure or not self._started_at or
                       now >= self.active_until or now >= self._started_at + _MAX_RUNTIME)
            # A failed calendar read is not evidence that an event was removed.
            removed = (self._active_departure and self._active_source and
                       self._active_source != "Starta nu" and
                       (self._active_departure, self._active_source) not in self._candidates(now, include_recent=True) and
                       (self._active_source != "Kalender" or self._calendar_ok))
            if (self._active_source == "Planerad" and self._active_departure and self._active_departure <= now
                    and not self.local_events_between(self._active_departure, self._active_departure + timedelta(microseconds=1))):
                removed = True
            # Expired calendar events are routinely pruned, but an explicitly
            # extended run remains valid until its chosen stop time.
            if (removed and self._active_departure and self._active_departure <= now
                    and self._extended_until and now < self._extended_until):
                removed = False
            if expired or removed:
                if not await self._turn_off():
                    self.status, self.error = "Fel", "Kunde inte stänga av brytaren; försöker igen"
                    return
            elif switch and switch.state == STATE_OFF:
                # Respect a user turning it off during an active departure.
                self._suppress_current_run(now, candidates)
                self.owned = False
                self._stop_requested = False
                self._active_departure = self._started_at = self._active_source = None
                self._extended_until = None
                await self._save()

        self.temperature = self._temperature()
        # An older suppressed departure must not hide a later event that the
        # user explicitly added and that is allowed to run.
        eligible = [(departure, source) for departure, source in candidates
                    if f"{source}|{departure.isoformat()}" not in self._suppressed]
        self.next_departure, self.source = (eligible or candidates)[0] if candidates else (None, None)
        self.duration_minutes = 0
        self.planned_start = None
        if self.temperature is not None and self.next_departure:
            self.duration_minutes = duration_for_temperature(self.temperature)
            if self.duration_minutes and not self._temperature_blocked:
                self.planned_start = self.next_departure - timedelta(minutes=self.duration_minutes)
        if self.owned:
            if not switch or switch.state not in (STATE_ON, STATE_OFF):
                self.status, self.error = "Fel", "Brytarens tillstånd är okänt"
            else:
                self.status = "Värmer"
        elif not switch or switch.state not in (STATE_ON, STATE_OFF):
            self.status, self.error = "Fel", "Brytaren är inte tillgänglig"
        elif self.temperature is None:
            self.status, self.error = "Fel", "Utetemperaturen är inte tillgänglig eller saknar temperaturenhet"
        elif self.automation_paused:
            self.status = "Pausad"
        elif not self.next_departure:
            self.status = "Ingen avresa"
        elif not self.duration_minutes:
            self.status = "Ingen uppvärmning behövs"
        elif self._temperature_blocked:
            self.status = "Ingen uppvärmning behövs"
        elif now < self.planned_start:
            self.status = "Väntar på start"
        elif switch.state == STATE_ON:
            self.status = "Brytaren var redan på"
        elif f"{self.source}|{self.next_departure.isoformat()}" in self._suppressed:
            self.status = "Manuellt avstängd för denna avresa"
        elif self.source == "Kalender" and not self._calendar_ok:
            self.status, self.error = "Fel", "Kalendern kan inte läsas"
        else:
            # Persist ownership first so a restart during the call can still turn it off.
            self.owned = True
            resumed = (self.next_departure == self._resume_departure and self.source == self._resume_source)
            self._active_departure, self._active_source = self.next_departure, self.source
            self._started_at = self._resume_started_at if resumed else now
            self._extended_until = None
            self._resume_departure = self._resume_source = self._resume_started_at = None
            await self._save()
            try:
                if not await self._turn_on_confirmed():
                    raise RuntimeError("Switch did not confirm on")
                self.status = "Värmer"
            except Exception:
                self.status, self.error = "Fel", "Kunde inte slå på brytaren; försöker stänga av"
                await self._abort_unconfirmed_start()
        if not self._calendar_ok:
            self.error = (self.error + "; " if self.error else "") + (self._calendar_error or "Kalendern kan inte läsas")
