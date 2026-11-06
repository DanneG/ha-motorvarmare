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
    DEFAULT_TAG,
)
from .energy import EnergyMonitor

_LOGGER = logging.getLogger(__name__)
_MAX_RUNTIME = timedelta(hours=4)
_CALENDAR_INTERVAL = 300
_CALENDAR_RETRY_INTERVAL = 30


def duration_for_temperature(temp: float) -> int:
    """Calculate minutes from Celsius, bounded by the four-hour limit."""
    return max(0, min(240, math.ceil(30 - 1.5 * temp)))


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
        self.weekly_times = [time(7, 0) for _ in range(7)]
        self.weekly_enabled = [False] * 7
        self.status = "Väntar"
        self.next_departure = self.planned_start = self.temperature = None
        self.duration_minutes = 0
        self.source = self.error = None
        self.owned = False
        self._stop_requested = False
        self._active_departure = self._started_at = None
        self._active_source = None
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
        for i, item in enumerate(data.get("weekly_times", [])[:7]):
            try:
                self.weekly_times[i] = time.fromisoformat(item)
            except (ValueError, TypeError):
                pass
        for i, item in enumerate(data.get("weekly_enabled", [])[:7]):
            self.weekly_enabled[i] = bool(item)
        self.owned = bool(data.get("owned"))
        self._stop_requested = bool(data.get("stop_requested"))
        self._active_departure = self._parse(data.get("active_departure"))
        self._started_at = self._parse(data.get("started_at"))
        self._active_source = data.get("active_source")
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
            "weekly_times": [t.isoformat() for t in self.weekly_times],
            "weekly_enabled": self.weekly_enabled,
            "owned": self.owned,
            "stop_requested": self._stop_requested,
            "active_departure": iso(self._active_departure),
            "started_at": iso(self._started_at),
            "active_source": self._active_source,
            "suppressed": sorted(self._suppressed),
            "suppression_until": iso(self._suppression_until),
            "suppression_exempt": sorted(self._suppression_exempt),
        })

    async def async_set_manual_departure(self, value):
        async with self._lock:
            self.manual_departure = self._parse(value)
            await self._save()
        await self.async_update()

    async def async_add_local_departure(self, moment, summary=None):
        """Add one departure in the integration's own calendar."""
        if not isinstance(moment, datetime):
            raise ValueError("departure_invalid")
        moment = dt_util.as_utc(moment)
        if moment <= dt_util.utcnow():
            raise ValueError("departure_past")
        title = summary.strip() if isinstance(summary, str) and summary.strip() else "Avresa"
        uid = str(uuid4())
        async with self._lock:
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

    async def async_delete_local_departure(self, uid):
        """Remove an event owned by this car, never an external event."""
        async with self._lock:
            remaining = [item for item in self.local_departures if item["uid"] != uid]
            if len(remaining) == len(self.local_departures):
                raise ValueError("departure_not_found")
            self.local_departures = remaining
            await self._save()
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
        return self._active_departure if self.owned else None

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
            self.owned = True
            self._stop_requested = False
            self._active_departure = now + timedelta(minutes=duration)
            self._started_at = now
            self._active_source = "Starta nu"
            await self._save()
            try:
                await asyncio.wait_for(
                    self.hass.services.async_call("switch", "turn_on", {ATTR_ENTITY_ID: self.config[CONF_SWITCH]}, blocking=True),
                    timeout=10,
                )
            except Exception as exc:
                await self._turn_off()
                self.status = "Fel"
                self.error = "Kunde inte slå på brytaren"
                self._notify()
                raise ValueError("turn_on_failed") from exc
            self.temperature = temperature
            self.status = "Värmer"
            self.error = None
            self._notify()

    def _suppress_current_run(self, now, candidates):
        """Keep an explicit stop effective across connected heating windows."""
        self._suppression_exempt.clear()
        self._suppression_until = max(now, self._active_departure or now)
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
                        if departure > self._suppression_until:
                            self._suppression_until = departure
            if now >= self._suppression_until:
                self._suppression_until = None
        def still_future(key):
            try:
                departure = self._parse(key.rsplit("|", 1)[1])
                return departure is not None and departure > now
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
            if self.owned and not await self._turn_off():
                self.error = "Kunde inte stänga av brytaren"
                self._notify()
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
        try:
            if not state or state.state != STATE_OFF:
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
                return False
        except Exception:
            _LOGGER.exception("Unable to turn off heater for %s", self.entry.title)
            return False
        self.owned = False
        self._stop_requested = False
        self._active_departure = self._started_at = None
        self._active_source = None
        await self._save()
        return True

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
                    "start_date_time": now.isoformat(),
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
                if moment and moment > now and calendar_event_matches(
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

    def _candidates(self, now):
        # An unverified cached event must not block a valid manual departure.
        result = [(moment, src) for moment, src in self._calendar_events if moment > now] if self._calendar_ok else []
        if self.manual_departure and self.manual_departure > now:
            result.append((self.manual_departure, "Manuell"))
        result.extend((item["departure"], "Planerad") for item in self.local_departures
                      if item["departure"] > now)
        local_now = dt_util.as_local(now)
        for offset in range(8):
            day = local_now.date() + timedelta(days=offset)
            weekday = day.weekday()
            if self.weekly_enabled[weekday]:
                local = datetime.combine(day, self.weekly_times[weekday], tzinfo=dt_util.get_default_time_zone())
                moment = dt_util.as_utc(local)
                # A spring-forward time may not exist. Skip that occurrence.
                if dt_util.as_local(moment).replace(tzinfo=None) != local.replace(tzinfo=None):
                    continue
                if moment > now:
                    result.append((moment, "Veckoschema"))
        return sorted(result, key=lambda item: item[0])

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
        for item in self.local_departures:
            locals_by_time.setdefault(item["departure"], []).append(item)
        schedule = []
        for departure, source in self._candidates(now):
            start = departure - timedelta(minutes=minutes) if minutes else None
            # Include a departure just beyond the display range when its
            # heating interval starts on the final visible local day.
            if departure >= end and (start is None or start >= end):
                continue
            local = locals_by_time[departure].pop(0) if source == "Planerad" else None
            schedule.append({
                "departure": departure.isoformat(),
                "start": start.isoformat() if start else None,
                "source": source,
                "duration_minutes": minutes,
                "uid": local["uid"] if local else None,
                "summary": local.get("summary", "Avresa") if local else "Avresa",
                "removable": local is not None,
                "suppressed": f"{source}|{departure.isoformat()}" in self._suppressed,
            })
        return schedule

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
        if self.energy.power_configured or self.energy.energy_configured:
            try:
                await self.energy.async_update()
            except Exception:
                _LOGGER.exception("Error monitoring energy for %s", self.entry.title)

    async def _update_locked(self):
        now = dt_util.utcnow()
        self.error = None
        if self.manual_departure and self.manual_departure <= now:
            self.manual_departure = None
            await self._save()
        remaining = [item for item in self.local_departures if item["departure"] > now]
        if len(remaining) != len(self.local_departures):
            self.local_departures = remaining
            await self._save()
        # Expiry must never wait on a calendar server.
        if self.owned and (self._stop_requested or not self._active_departure or not self._started_at or
                           now >= self._active_departure or now >= self._started_at + _MAX_RUNTIME):
            if self._active_departure and self._active_source and self._started_at and now >= self._started_at + _MAX_RUNTIME:
                self._suppress_current_run(now, self._candidates(now))
            if not await self._turn_off():
                self.status, self.error = "Fel", "Kunde inte bekräfta att brytaren är av; försöker igen"
                return
        await self._read_calendar(now)
        now = dt_util.utcnow()
        candidates = self._candidates(now)
        if self._reconcile_suppression(now, candidates):
            await self._save()
        switch = self.hass.states.get(self.config[CONF_SWITCH])
        if self.owned:
            expired = (not self._active_departure or not self._started_at or
                       now >= self._active_departure or now >= self._started_at + _MAX_RUNTIME)
            # A failed calendar read is not evidence that an event was removed.
            removed = (self._active_departure and self._active_source and
                       self._active_source != "Starta nu" and
                       (self._active_departure, self._active_source) not in candidates and
                       (self._active_source != "Kalender" or self._calendar_ok))
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
        elif not self.next_departure:
            self.status = "Ingen avresa"
        elif not self.duration_minutes:
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
            self._active_departure, self._active_source, self._started_at = self.next_departure, self.source, now
            await self._save()
            try:
                await asyncio.wait_for(
                    self.hass.services.async_call("switch", "turn_on", {ATTR_ENTITY_ID: self.config[CONF_SWITCH]}, blocking=True),
                    timeout=10,
                )
                self.status = "Värmer"
            except Exception:
                self.status, self.error = "Fel", "Kunde inte slå på brytaren; försöker stänga av"
                await self._turn_off()
        if not self._calendar_ok:
            self.error = (self.error + "; " if self.error else "") + (self._calendar_error or "Kalendern kan inte läsas")
