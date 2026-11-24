"""A short, journalled plug test, separate from heating sessions."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging

from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.util import dt as dt_util

from .const import CONF_NOTIFY_ENTITY, CONF_POWER_ENTITY, CONF_SWITCH, DOMAIN, cable_test_configured

_LOGGER = logging.getLogger(__name__)
_PULSE_SECONDS = 10
_SAMPLE_SECONDS = 0.25
_LOW_POWER_SETTLING = timedelta(seconds=2)
_SINGLE_LOW_AFTER = timedelta(seconds=7)
_LATE_ON_GUARD = timedelta(minutes=2)


def _reported(state):
    stamp = getattr(state, "last_reported", None) or getattr(state, "last_updated", None)
    return dt_util.as_utc(stamp) if isinstance(stamp, datetime) else None


class CableTest:
    def __init__(self, controller):
        self.controller = controller
        self.switch = None
        self.at = None
        self.result = None
        self.closing = False
        self._armed = False
        self._outcome = "inconclusive"
        self._reminded_on = None
        self._notice_open = False
        self._uncertain_until = None
        self._retry_timer = None

    def restore(self, data):
        if not isinstance(data, dict):
            return
        self.at = self.controller._parse(data.get("at"))
        self.result = data.get("result")
        self._reminded_on = data.get("reminded_on")
        self._notice_open = bool(data.get("notice_open"))
        switch = data.get("switch")
        if isinstance(switch, str) and switch.startswith("switch."):
            self.switch = switch
            self._armed = True
            self.result = "pending"
            if data.get("outcome") in ("low_power", "connected"):
                self._outcome = data["outcome"]
            self._uncertain_until = (self.at or dt_util.utcnow()) + _LATE_ON_GUARD

    def snapshot(self):
        return {"switch": self.switch, "at": self.at.isoformat() if self.at else None,
                "result": self.result, "outcome": self._outcome if self.switch else None,
                "reminded_on": self._reminded_on, "notice_open": self._notice_open}

    def measuring(self):
        return self._armed and self.switch == self.controller.config.get(CONF_SWITCH)

    def _state(self):
        return self.controller.hass.states.get(self.switch)

    async def _command(self, action):
        await self.controller.hass.services.async_call(
            "switch", action, {ATTR_ENTITY_ID: self.switch}, blocking=True)

    async def _measure(self, before, requested_at, deadline):
        """Only accept an observation made after this plug confirmed ON."""
        controller = self.controller
        loop = asyncio.get_running_loop()
        confirmed_at = None
        first_low = None
        while True:
            confirmed_low = False
            switch = self._state()
            if switch and switch.state == STATE_ON:
                if confirmed_at is None:
                    changed = getattr(switch, "last_changed", None)
                    confirmed_at = (max(requested_at, dt_util.as_utc(changed))
                                    if isinstance(changed, datetime) else dt_util.utcnow())
                    self._uncertain_until = None
                if self.closing:
                    return "inconclusive"
                power_state = controller.hass.states.get(controller.config[CONF_POWER_ENTITY])
                stamp = _reported(power_state)
                fresh = stamp and confirmed_at <= stamp <= dt_util.utcnow() and (before is None or stamp > before)
                watts = controller.energy.power_w if fresh else None
                if watts is not None and watts > 0 and watts >= controller.energy._threshold():
                    return "connected"
                if watts is None:
                    first_low = None
                else:
                    first_low = first_low or stamp
                    since_on = stamp - confirmed_at
                    confirmed_low = (since_on >= _SINGLE_LOW_AFTER or
                                     (stamp > first_low and since_on >= _LOW_POWER_SETTLING))
            elif confirmed_at is not None:
                # An external stop or an unavailable plug ends this observation.
                return "inconclusive"
            remaining = deadline - loop.time()
            if remaining <= 0:
                return "low_power" if confirmed_low else "inconclusive"
            await asyncio.sleep(min(_SAMPLE_SECONDS, remaining))

    async def run(self, now):
        """Caller holds the controller lock and has checked eligibility."""
        controller = self.controller
        previous = self.at, self.result
        self._outcome = "inconclusive"
        self.at, self.result, self.switch = now, "pending", controller.config[CONF_SWITCH]
        try:
            await controller._save()
        except BaseException:
            self.at, self.result = previous
            self.switch = None
            raise
        state = self._state()
        requested_at = dt_util.utcnow()
        if self.closing or not state or state.state != STATE_OFF or requested_at - now > timedelta(seconds=10):
            # Another owner may have started the plug during the storage write.
            self.switch = None
            self.at, self.result = previous
            await controller._save_stop_state()
            return
        before = _reported(controller.hass.states.get(controller.config[CONF_POWER_ENTITY]))
        self._uncertain_until = requested_at + _LATE_ON_GUARD
        self._armed = True
        try:
            controller._notify()
            deadline = asyncio.get_running_loop().time() + _PULSE_SECONDS
            async with asyncio.timeout_at(deadline):
                await self._command("turn_on")
            self._outcome = await self._measure(before, requested_at, deadline)
        except Exception:
            _LOGGER.warning("Cable test failed for %s", controller.entry.title, exc_info=True)
        finally:
            await self.stop()

    async def stop(self):
        """Release ownership only after a confirmed OFF and any late ON guard."""
        if self.switch is None:
            return True
        controller = self.controller
        try:
            state = self._state()
            if self._uncertain_until or not state or state.state != STATE_OFF:
                await asyncio.wait_for(self._command("turn_off"), timeout=5)
                for _ in range(8):
                    state = self._state()
                    if state and state.state == STATE_OFF:
                        break
                    await asyncio.sleep(0.25)
            if (state and state.state == STATE_OFF
                    and (not self._uncertain_until or dt_util.utcnow() >= self._uncertain_until)):
                self.switch, self._uncertain_until, self.result = None, None, self._outcome
                self._armed = False
                if self._retry_timer is not None:
                    self._retry_timer.cancel()
                    self._retry_timer = None
                await controller._save_stop_state()
                controller._notify()
                return True
        except Exception:
            _LOGGER.warning("Unable to confirm cable test stop for %s", controller.entry.title, exc_info=True)
        finally:
            if self.switch is not None and self._retry_timer is None:
                self._retry_timer = asyncio.get_running_loop().call_later(3, self._retry)
        controller.status, controller.error = "Fel", "Kunde inte bekräfta att brytaren är av"
        await controller._save_stop_state()
        controller._notify()
        controller._schedule_operational_alerts()
        return False

    def _retry(self):
        self._retry_timer = None
        self.controller._tick(None)

    async def notify_if_due(self):
        controller = self.controller
        if (self.closing or not self.at or controller._alerts_after is None or not controller._alerts_allowed()
                or not cable_test_configured(controller.config)):
            return
        notification_id = f"{DOMAIN}_{controller.entry.entry_id}_cable_test"
        if self.result == "connected" and self._notice_open:
            try:
                await asyncio.wait_for(controller.hass.services.async_call(
                    "persistent_notification", "dismiss", {"notification_id": notification_id}, blocking=True), timeout=10)
                self._notice_open = False
                await controller._save_stop_state()
            except Exception:
                _LOGGER.warning("Unable to clear cable test reminder for %s", controller.entry.title, exc_info=True)
        if self.result != "low_power":
            return
        day = dt_util.as_local(self.at).date().isoformat()
        if self._reminded_on == day or day != dt_util.as_local(dt_util.utcnow()).date().isoformat():
            return
        previous = self._reminded_on, self._notice_open
        self._reminded_on = day
        self._notice_open = True
        try:
            await controller._save()
        except BaseException:
            self._reminded_on, self._notice_open = previous
            raise
        sv = str(getattr(getattr(controller.hass, "config", None), "language", "en")).lower().startswith("sv")
        title = ("Motorvärmare: " if sv else "Engine heater: ") + controller.entry.title
        message = ("Kabeltestet visade låg effekt. Kontrollera kabeln inför morgondagens avresa."
                   if sv else "The cable test measured low power. Check the cable before tomorrow’s departure.")
        targets = [("persistent_notification", "create", {"title": title, "message": message,
                    "notification_id": notification_id})]
        entity = controller.config.get(CONF_NOTIFY_ENTITY)
        if isinstance(entity, str) and entity.startswith("notify."):
            targets.append(("notify", "send_message", {ATTR_ENTITY_ID: entity, "title": title, "message": message}))
        for domain, service, data in targets:
            if not controller._alerts_allowed():
                return
            try:
                await asyncio.wait_for(controller.hass.services.async_call(domain, service, data, blocking=True), timeout=10)
            except Exception:
                _LOGGER.warning("Unable to send cable test reminder for %s", controller.entry.title, exc_info=True)
