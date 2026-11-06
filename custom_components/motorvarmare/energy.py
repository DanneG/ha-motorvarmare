"""Optional, independently supervised power and energy monitoring."""

from __future__ import annotations

import asyncio
from datetime import timedelta
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
        self._session_active = False
        self._saw_off = False
        self._switch_changed = None
        self._baseline = None
        self._last_meter = None
        self._session_energy = None
        self._invalid = False
        self._low_since = None
        self._persistent_sent = False
        self._mobile_sent = False
        self._last_attempt = {}
        self._power_epoch = 0
        self.alarm_active = False

    @property
    def power_configured(self):
        return bool(self.config.get("power_entity"))

    @property
    def energy_configured(self):
        return bool(self.config.get("energy_entity"))

    @property
    def power_w(self):
        return _read_number(self.hass.states.get(self.config.get("power_entity")), _POWER_UNITS) if self.power_configured else None

    @property
    def energy_meter_kwh(self):
        return _read_number(self.hass.states.get(self.config.get("energy_entity")), _ENERGY_UNITS, cumulative=True) if self.energy_configured else None

    @property
    def energy_sensor_available(self):
        return self.energy_meter_kwh is not None

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
            "session_active": self._session_active,
            "switch_changed": self._switch_changed,
            "baseline": self._baseline,
            "last_meter": self._last_meter,
            "session_energy": self._session_energy,
            "invalid": self._invalid,
            "persistent_sent": self._persistent_sent,
            "mobile_sent": self._mobile_sent,
        }

    async def async_load(self):
        """Restore session data only for the same switch and energy sensor."""
        data = await self.store.async_load() or {}
        if data.get("switch_entity") != self.config.get("switch_entity"):
            return
        self._session_active = bool(data.get("session_active"))
        self._switch_changed = data.get("switch_changed")
        if data.get("power_entity") == self.config.get("power_entity"):
            self._persistent_sent = bool(data.get("persistent_sent"))
            if data.get("notify_entity") == self.config.get("notify_entity"):
                self._mobile_sent = bool(data.get("mobile_sent"))
        if data.get("energy_entity") == self.config.get("energy_entity"):
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
        # Do not count unobserved downtime toward the low-power delay.
        self._low_since = None

    async def async_start(self):
        if not (self.power_configured or self.energy_configured):
            return
        from homeassistant.helpers.event import async_track_state_change_event

        self._stopped = False
        entities = {self.config.get("switch_entity"), self.config.get("power_entity"), self.config.get("energy_entity")}
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
                            "energy": self.hass.states.get(self.config.get("energy_entity"))}
                if switch_event:
                    snapshot["switch"] = new_state
                elif entity == self.config.get("power_entity"):
                    snapshot["power"] = new_state
                elif entity == self.config.get("energy_entity"):
                    snapshot["energy"] = new_state
                self.hass.async_create_task(self._safe_update(snapshot))

        self._unsub = async_track_state_change_event(self.hass, [entity for entity in entities if entity], changed)
        # Do not delay the heater scheduler on storage or notification I/O.
        initial = {"switch": self.hass.states.get(self.config.get("switch_entity")),
                   "power": self.hass.states.get(self.config.get("power_entity")),
                   "energy": self.hass.states.get(self.config.get("energy_entity"))}
        self.hass.async_create_task(self._safe_update(initial))

    async def _safe_update(self, *args):
        try:
            await self.async_update(*args)
        except Exception:
            _LOGGER.exception("Energy monitoring failed for %s", self.entry.title)

    async def async_shutdown(self):
        self._stopped = True
        if self._unsub:
            self._unsub()
            self._unsub = None
        await self.async_update(force=True)

    async def _save(self):
        await self.store.async_save(self._snapshot())

    @staticmethod
    def _changed_at(state):
        value = getattr(state, "last_changed", None)
        return value.isoformat() if value is not None else None

    async def async_update(self, snapshot=None, force=False):
        """Process one observation. Called from events and the periodic tick."""
        if (self._stopped and not force) or not (self.power_configured or self.energy_configured):
            return
        async with self._lock:
            if self._stopped and not force:
                return
            switch = snapshot.get("switch") if snapshot is not None else self.hass.states.get(self.config.get("switch_entity"))
            on = switch is not None and switch.state == "on"
            off = switch is not None and switch.state == "off"
            meter = (_read_number(snapshot.get("energy"), _ENERGY_UNITS, cumulative=True)
                     if snapshot is not None and self.energy_configured
                     else self.energy_meter_kwh)
            changed = False
            if on:
                changed_at = self._changed_at(switch)
                # A changed last_changed timestamp can reveal an off/on cycle
                # while HA was unavailable; do not reuse an old baseline.
                new_session = not self._session_active or (changed_at and self._switch_changed and changed_at != self._switch_changed)
                if new_session:
                    self._session_active = True
                    self._switch_changed = changed_at
                    # If HA first sees an already-on plug there is no known
                    # start reading; a partial measurement must not be
                    # presented as consumption for the whole session.
                    self._baseline = meter if self._saw_off else None
                    self._last_meter = self._baseline
                    self._session_energy = 0.0 if self._baseline is not None else None
                    self._invalid = self.energy_configured and self._baseline is None
                    self._saw_off = False
                    self._low_since = None
                    self._persistent_sent = self._mobile_sent = False
                    self._last_attempt = {}
                    self.alarm_active = False
                    changed = True
                if self.energy_configured and meter is None and not self._invalid:
                    # A reset can occur while a sensor is unavailable, so
                    # continuity cannot be established from later readings.
                    self._invalid = True
                    self._session_energy = None
                    changed = True
                if meter is not None and self._baseline is not None and not self._invalid:
                    if self._last_meter is not None and meter + 1e-9 < self._last_meter:
                        self._invalid = True
                        self._session_energy = None
                        changed = True
                    else:
                        self._last_meter = meter
                        self._session_energy = max(0.0, meter - self._baseline)
                power = (_read_number(snapshot.get("power"), _POWER_UNITS)
                         if snapshot is not None and self.power_configured
                         else self.power_w)
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
                    if self.energy_configured and meter is None:
                        self._invalid = True
                        self._session_energy = None
                    if meter is not None and self._baseline is not None and not self._invalid:
                        if self._last_meter is not None and meter + 1e-9 < self._last_meter:
                            self._invalid = True
                            self._session_energy = None
                        else:
                            self._last_meter = meter
                            self._session_energy = max(0.0, meter - self._baseline)
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
                self._low_since = None
                self.alarm_active = False
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
            if (self._stopped or power_epoch != self._power_epoch or not current_switch or current_switch.state != "on"
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
