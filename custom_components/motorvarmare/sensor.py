"""Status for the engine heater."""

from __future__ import annotations

from datetime import datetime, timedelta
import math

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .controller import duration_for_temperature

_STATUS_KEYS = {
    "Väntar": "waiting",
    "Fel": "error",
    "Värmer": "heating",
    "Avstängd": "stopped",
    "Ingen avresa": "no_departure",
    "Ingen uppvärmning behövs": "no_heating_needed",
    "Väntar på start": "waiting_to_start",
    "Brytaren var redan på": "already_on",
    "Manuellt avstängd för denna avresa": "manually_stopped",
    "Pausad": "paused",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create a status sensor for one car."""
    controller = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([HeaterStatus(entry, controller)] + [
        HeaterMetric(entry, controller, key) for key in _METRIC_KEYS
    ])


def _number(value, *, positive=False):
    """Only accept measured finite numbers, never a boolean or a guessed zero."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        valid = math.isfinite(value)
    except OverflowError:
        return None
    if not valid or value < 0 or (positive and value == 0):
        return None
    return float(value)


def _aware_datetime(value):
    """Read an aware observation; don't invent the timezone of old data."""
    if isinstance(value, str):
        try:
            value = dt_util.parse_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
    return value if isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None else None


def _scheduled_start(controller):
    """An upcoming start only when the controller can actually schedule it."""
    now = dt_util.utcnow()
    departure = _aware_datetime(getattr(controller, "next_departure", None))
    start = _aware_datetime(getattr(controller, "planned_start", None))
    if (getattr(controller, "status", None) != "Väntar på start"
            or getattr(controller, "owned", False) or getattr(controller, "automation_paused", False)
            or getattr(controller, "_temperature_blocked", False) or getattr(controller, "error", None)
            or _number(getattr(controller, "duration_minutes", None), positive=True) is None
            or not departure or not start or departure <= now or start <= now or start > departure):
        return None
    source = getattr(controller, "source", None)
    if f"{source}|{departure.isoformat()}" in getattr(controller, "_suppressed", set()):
        return None
    skipped = _aware_datetime(getattr(controller, "skipped_departure", None))
    return None if skipped == departure else start


def _next_estimate(controller):
    """Estimate a future run from the latest complete session's mean power.

    The previous session is the only available evidence of load when a smart
    plug is off.  A live zero while off, an incomplete session, or a missing
    price never becomes a made-up forecast.
    """
    empty = {"energy_kwh": None, "cost": None, "currency": None,
             "basis": None, "history_end": None, "average_power_w": None,
             "planned_duration_minutes": None, "price_basis": None}
    energy = getattr(controller, "energy", None)
    now = dt_util.utcnow()
    departure = _aware_datetime(getattr(controller, "next_departure", None))
    start = _scheduled_start(controller)
    duration = _number(getattr(controller, "duration_minutes", None), positive=True)
    after = _number(getattr(controller, "post_departure_minutes", None))
    if (energy is None or not getattr(energy, "energy_configured", False)
            or not departure or not start or duration is None or after is None):
        return empty
    config = getattr(controller, "config", {})
    switch_entity = config.get("switch_entity")
    source_kind = "power" if getattr(energy, "power_configured", False) else "meter"
    source_key = "power_entity" if source_kind == "power" else "energy_entity"
    source_entity = config.get(source_key)
    if not switch_entity or not source_entity:
        return empty
    for item in getattr(energy, "heating_history", []):  # newest first
        if not isinstance(item, dict) or item.get("complete") is not True:
            continue
        # History belongs to a car, but changing its plug or sensor must not
        # silently use power measured from an earlier piece of equipment.
        if (item.get("switch_entity") != switch_entity or item.get("energy_source") != source_kind
                or item.get(source_key) != source_entity):
            continue
        observed_energy = _number(item.get("energy_kwh"), positive=True)
        observed_minutes = _number(item.get("duration_minutes"), positive=True)
        ended = _aware_datetime(item.get("end"))
        if observed_energy is None or observed_minutes is None or not ended or ended > now:
            continue
        average_w = observed_energy * 60_000 / observed_minutes
        total_minutes = duration + after
        forecast = average_w * total_minutes / 60_000
        if not math.isfinite(average_w) or not math.isfinite(forecast):
            continue
        price, currency = None, None
        if getattr(energy, "cost_configured", False):
            getter = getattr(energy, "_cost_price", None)
            if getter:
                price, currency, _ = getter()
        cost = forecast * price if isinstance(price, (int, float)) and not isinstance(price, bool) and math.isfinite(price) else None
        if cost is not None and not math.isfinite(cost):
            cost = None
        if not isinstance(currency, str) or len(currency) != 3 or not currency.isascii() or not currency.isalpha() or currency != currency.upper():
            cost, currency = None, None
        return {"energy_kwh": round(forecast, 4), "cost": round(cost, 4) if cost is not None else None,
                "currency": currency, "basis": "latest_complete_session_average",
                "history_end": ended.isoformat(), "average_power_w": round(average_w, 2),
                "planned_duration_minutes": total_minutes, "price_basis": "current_price" if cost is not None else None}
    return empty


_METRIC_KEYS = ("next_departure", "planned_start", "remaining_heating", "session_energy",
                "energy_today", "energy_week", "energy_month", "next_estimated_energy", "next_estimated_cost")


class HeaterMetric(SensorEntity):
    """Expose individual, car-scoped values for dashboards and automations."""

    _attr_has_entity_name = True

    def __init__(self, entry, controller, key):
        self.controller, self.key = controller, key
        self._signal = f"{DOMAIN}_{entry.entry_id}"
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name=entry.title)
        if key in ("next_departure", "planned_start"):
            self._attr_device_class = getattr(SensorDeviceClass, "TIMESTAMP", "timestamp")
            self._attr_icon = "mdi:calendar-clock"
        elif key == "remaining_heating":
            self._attr_native_unit_of_measurement = "min"
            self._attr_state_class = "measurement"
            self._attr_icon = "mdi:timer-outline"
        elif key == "next_estimated_cost":
            self._attr_device_class = getattr(SensorDeviceClass, "MONETARY", "monetary")
            self._attr_icon = "mdi:cash-clock"
        else:
            self._attr_device_class = getattr(SensorDeviceClass, "ENERGY", "energy")
            self._attr_native_unit_of_measurement = "kWh"
            self._attr_icon = "mdi:lightning-bolt"

    @property
    def native_unit_of_measurement(self):
        if self.key == "next_estimated_cost":
            currency = str(self.controller.config.get("energy_currency", "SEK")).strip().upper()
            return currency if len(currency) == 3 and currency.isascii() and currency.isalpha() else None
        return getattr(self, "_attr_native_unit_of_measurement", None)

    def _period(self):
        energy = getattr(self.controller, "energy", None)
        if not energy or not getattr(energy, "energy_configured", False):
            return None
        today = dt_util.as_local(dt_util.utcnow()).date()
        kind, period = {"energy_today": ("daily", today),
                        "energy_week": ("weekly", today - timedelta(days=today.weekday())),
                        "energy_month": ("monthly", today.replace(day=1))}[self.key]
        data = energy.history_energy_totals
        rows = data.get(kind, []) if isinstance(data, dict) else []
        return next((row for row in rows if isinstance(row, dict) and row.get("period_start") == period.isoformat()), None)

    @property
    def native_value(self):
        energy = getattr(self.controller, "energy", None)
        if self.key == "next_departure":
            return _aware_datetime(getattr(self.controller, self.key, None))
        if self.key == "planned_start":
            return _scheduled_start(self.controller)
        if self.key == "remaining_heating":
            end = _aware_datetime(getattr(self.controller, "active_until", None))
            if not getattr(self.controller, "owned", False) or getattr(self.controller, "status", None) != "Värmer" or not end:
                return None
            return max(0, math.ceil((end - dt_util.utcnow()).total_seconds() / 60))
        if self.key == "session_energy":
            if not energy or not getattr(energy, "energy_configured", False) or energy.energy_session_status not in ("measuring", "complete"):
                return None
            return _number(energy.session_energy_kwh)
        if self.key in ("energy_today", "energy_week", "energy_month"):
            item = self._period()
            return _number(item.get("energy_kwh")) if item and not item.get("incomplete", True) else None
        estimate = _next_estimate(self.controller)
        return estimate["energy_kwh"] if self.key == "next_estimated_energy" else estimate["cost"]

    @property
    def available(self):
        """Unknown or incomplete data must not appear as a valid zero."""
        return self.native_value is not None

    @property
    def extra_state_attributes(self):
        if self.key in ("energy_today", "energy_week", "energy_month"):
            item = self._period()
            if item:
                return {"period_start": item.get("period_start"), "incomplete": bool(item.get("incomplete", True)),
                        "known_energy_kwh": _number(item.get("energy_kwh"))}
        if self.key in ("next_estimated_energy", "next_estimated_cost"):
            result = _next_estimate(self.controller)
            return {"estimate_basis": result["basis"], "history_end": result["history_end"],
                    "average_power_w": result["average_power_w"],
                    "planned_duration_minutes": result["planned_duration_minutes"],
                    "price_basis": result["price_basis"]}
        return {}

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(self.hass, self._signal, self.async_write_ha_state))


class HeaterStatus(SensorEntity):
    """Show the current decision and the information behind it."""

    _attr_has_entity_name = True
    _attr_translation_key = "status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(_STATUS_KEYS.values())
    _attr_icon = "mdi:car-defrost-front"
    _unrecorded_attributes = (getattr(SensorEntity, "_unrecorded_attributes", None) or frozenset()) | frozenset({"heating_history", "history_energy_totals", "active_power_samples"})

    def __init__(self, entry: ConfigEntry, controller) -> None:
        """Bind the sensor to its car."""
        self.controller = controller
        self._entry_id = entry.entry_id
        self._signal = f"{DOMAIN}_{entry.entry_id}"
        self._attr_unique_id = f"{entry.entry_id}_status"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name=entry.title
        )

    @property
    def native_value(self) -> str | None:
        """Return the human-readable status."""
        return _STATUS_KEYS.get(self.controller.status, "error")

    @property
    def extra_state_attributes(self) -> dict:
        """Expose the next decision and any problem."""
        controller = self.controller
        registry = er.async_get(self.hass)
        energy = getattr(controller, "energy", None)
        estimate = _next_estimate(controller)

        def entity_id(domain: str, suffix: str) -> str | None:
            return registry.async_get_entity_id(domain, DOMAIN, f"{self._entry_id}_{suffix}")

        return {
            "next_departure": controller.next_departure,
            "planned_start": controller.planned_start,
            "temperature": controller.temperature,
            "duration_minutes": controller.duration_minutes,
            "temperature_blocked": controller._temperature_blocked,
            "post_departure_minutes": controller.post_departure_minutes,
            "current_duration_minutes": (
                duration_for_temperature(controller.temperature)
                if controller.temperature is not None else None
            ),
            "source": controller.source,
            "error": controller.error,
            "owned": controller.owned,
            "active_until": controller.active_until,
            "active_started_at": getattr(controller, "_started_at", None) if controller.owned else None,
            "active_max_until": (controller._started_at + timedelta(hours=4)) if controller.owned and getattr(controller, "_started_at", None) else None,
            "can_extend": getattr(controller, "can_extend", False),
            "automation_paused": getattr(controller, "automation_paused", False),
            "pause_until": getattr(controller, "pause_until", None),
            "skipped_departure": getattr(controller, "skipped_departure", None),
            "operational_problems": sorted(getattr(controller, "_operational_problems", lambda: set())()),
            "weather_enabled": bool(controller.config.get("weather_entity")),
            "schedule_7_days": controller.schedule_7_days,
            "power_sensor_configured": energy.power_configured if energy else False,
            "energy_sensor_configured": energy.energy_configured if energy else False,
            "cost_configured": energy.cost_configured if energy else False,
            "energy_sensor_available": energy.energy_sensor_available if energy else False,
            "power_w": energy.power_w if energy else None,
            "active_power_samples": getattr(energy, "active_power_samples", []) if energy else [],
            "active_measurement_started_at": getattr(energy, "active_measurement_started_at", None) if energy else None,
            "active_session_cost": getattr(energy, "active_session_cost", None) if energy else None,
            "active_session_currency": getattr(energy, "active_session_currency", None) if energy else None,
            "session_energy_kwh": energy.session_energy_kwh if energy else None,
            "energy_session_status": energy.energy_session_status if energy else "disabled",
            "energy_monitor_status": energy.monitor_status if energy else "disabled",
            "alarm_active": energy.alarm_active if energy else False,
            "power_deviation_active": getattr(energy, "deviation_alarm_active", False) if energy else False,
            "power_deviation_direction": getattr(energy, "deviation_direction", None) if energy else None,
            "next_estimated_energy_kwh": estimate["energy_kwh"],
            "next_estimated_cost": estimate["cost"],
            "next_estimated_currency": estimate["currency"],
            "next_estimate_basis": estimate["basis"],
            "next_estimate_history_end": estimate["history_end"],
            "next_estimate_average_power_w": estimate["average_power_w"],
            "next_estimate_duration_minutes": estimate["planned_duration_minutes"],
            "heating_history": energy.heating_history if energy else [],
            "history_energy_totals": energy.history_energy_totals if energy else None,
            "schedule_query_supported": True,
            # Entity-registry lookups survive renames and keep cars separate.
            "control_entities": {
                "manual_departure": entity_id("datetime", "manual_departure"),
                "clear_departure": entity_id("button", "clear_departure"),
                "start_now": entity_id("button", "start_now"),
                "stop_now": entity_id("button", "stop_now"),
                "extend_30": entity_id("button", "extend_30"),
                "skip_next": entity_id("button", "skip_next"),
                "automation_paused": entity_id("switch", "automation_paused"),
                "pause_until": entity_id("datetime", "pause_until"),
                "calendar": entity_id("calendar", "departure_calendar"),
                "heater_switch": controller.config.get("switch_entity"),
                "weekly_times": [entity_id("time", f"weekly_time_{day}") for day in range(7)],
                "weekly_enabled": [entity_id("switch", f"weekly_enabled_{day}") for day in range(7)],
            },
        }

    async def async_added_to_hass(self) -> None:
        """Listen for changes made by the controller."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._signal, self.async_write_ha_state)
        )
        self.async_on_remove(
            self.hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, self._registry_updated)
        )

    @callback
    def _registry_updated(self, event) -> None:
        """Refresh card targets after entity creation, rename, or removal."""
        self.async_write_ha_state()
