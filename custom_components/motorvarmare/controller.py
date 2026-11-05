"""Scheduling and ownership for one heater."""

from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta
import logging
import re
import time as monotonic_time

from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, UnitOfTemperature
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN, CONF_SWITCH, CONF_TEMPERATURE, CONF_CALENDAR, CONF_TAG,
    CONF_DURATION_WARM, CONF_DURATION_COOL, CONF_DURATION_COLD,
    DEFAULT_TAG, DEFAULT_DURATION_WARM, DEFAULT_DURATION_COOL, DEFAULT_DURATION_COLD,
)

_LOGGER = logging.getLogger(__name__)
_MAX_RUNTIME = timedelta(hours=4)
_CALENDAR_INTERVAL = 300
_CALENDAR_RETRY_INTERVAL = 30


def duration_for_temperature(temp: float, warm: int, cool: int, cold: int) -> int:
    """Use configurable runtimes and explicit inclusive boundaries."""
    if temp <= -15:
        return cold
    if temp <= 0:
        return cool
    if temp < 10:
        return warm
    return 0


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
        self.weekly_times = [time(7, 0) for _ in range(7)]
        self.weekly_enabled = [False] * 7
        self.status = "Väntar"
        self.next_departure = self.planned_start = self.temperature = None
        self.duration_minutes = 0
        self.source = self.error = None
        self.owned = False
        self._active_departure = self._started_at = None
        self._active_source = None
        self._suppressed = None
        self._calendar_events = []
        self._calendar_checked = float("-inf")
        self._calendar_ok = not bool(self.config.get(CONF_CALENDAR))
        self._calendar_error = None
        self._lock = asyncio.Lock()
        self._unsub = None

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
        self.manual_departure = self._parse(data.get("manual_departure"))
        for i, item in enumerate(data.get("weekly_times", [])[:7]):
            try:
                self.weekly_times[i] = time.fromisoformat(item)
            except (ValueError, TypeError):
                pass
        for i, item in enumerate(data.get("weekly_enabled", [])[:7]):
            self.weekly_enabled[i] = bool(item)
        self.owned = bool(data.get("owned"))
        self._active_departure = self._parse(data.get("active_departure"))
        self._started_at = self._parse(data.get("started_at"))
        self._active_source = data.get("active_source")
        self._suppressed = data.get("suppressed")

    async def _save(self):
        def iso(value):
            return value.isoformat() if value else None
        await self.store.async_save({
            "manual_departure": iso(self.manual_departure),
            "weekly_times": [t.isoformat() for t in self.weekly_times],
            "weekly_enabled": self.weekly_enabled,
            "owned": self.owned,
            "active_departure": iso(self._active_departure),
            "started_at": iso(self._started_at),
            "active_source": self._active_source,
            "suppressed": self._suppressed,
        })

    async def async_set_manual_departure(self, value):
        async with self._lock:
            self.manual_departure = self._parse(value)
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

    async def async_start(self):
        self._unsub = async_track_time_interval(self.hass, self._tick, timedelta(minutes=1))
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

    def _temperature(self):
        import math
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

    async def _update_locked(self):
        now = dt_util.utcnow()
        self.error = None
        if self.manual_departure and self.manual_departure <= now:
            self.manual_departure = None
            await self._save()
        # Expiry must never wait on a calendar server.
        if self.owned and (not self._active_departure or not self._started_at or
                           now >= self._active_departure or now >= self._started_at + _MAX_RUNTIME):
            if self._active_departure and self._active_source and self._started_at and now >= self._started_at + _MAX_RUNTIME:
                self._suppressed = f"{self._active_source}|{self._active_departure.isoformat()}"
            if not await self._turn_off():
                self.status, self.error = "Fel", "Kunde inte bekräfta att brytaren är av; försöker igen"
                return
        await self._read_calendar(now)
        now = dt_util.utcnow()
        candidates = self._candidates(now)
        switch = self.hass.states.get(self.config[CONF_SWITCH])
        if self.owned:
            expired = (not self._active_departure or not self._started_at or
                       now >= self._active_departure or now >= self._started_at + _MAX_RUNTIME)
            # A failed calendar read is not evidence that an event was removed.
            removed = (self._active_departure and self._active_source and
                       (self._active_departure, self._active_source) not in candidates and
                       (self._active_source != "Kalender" or self._calendar_ok))
            if expired or removed:
                if not await self._turn_off():
                    self.status, self.error = "Fel", "Kunde inte stänga av brytaren; försöker igen"
                    return
            elif switch and switch.state == STATE_OFF:
                # Respect a user turning it off during an active departure.
                self._suppressed = f"{self._active_source}|{self._active_departure.isoformat()}"
                self.owned = False
                self._active_departure = self._started_at = self._active_source = None
                await self._save()

        self.temperature = self._temperature()
        self.next_departure, self.source = candidates[0] if candidates else (None, None)
        self.duration_minutes = 0
        self.planned_start = None
        if self.temperature is not None and self.next_departure:
            self.duration_minutes = duration_for_temperature(self.temperature,
                int(self.config.get(CONF_DURATION_WARM, DEFAULT_DURATION_WARM)),
                int(self.config.get(CONF_DURATION_COOL, DEFAULT_DURATION_COOL)),
                int(self.config.get(CONF_DURATION_COLD, DEFAULT_DURATION_COLD)))
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
        elif self._suppressed == f"{self.source}|{self.next_departure.isoformat()}":
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
