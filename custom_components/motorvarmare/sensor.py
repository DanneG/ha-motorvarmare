"""Status for the engine heater."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import entity_registry as er

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
    async_add_entities([HeaterStatus(entry, controller)])


class HeaterStatus(SensorEntity):
    """Show the current decision and the information behind it."""

    _attr_has_entity_name = True
    _attr_translation_key = "status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(_STATUS_KEYS.values())
    _attr_icon = "mdi:car-defrost-front"
    _unrecorded_attributes = (getattr(SensorEntity, "_unrecorded_attributes", None) or frozenset()) | frozenset({"heating_history", "history_energy_totals"})

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
            "session_energy_kwh": energy.session_energy_kwh if energy else None,
            "energy_session_status": energy.energy_session_status if energy else "disabled",
            "energy_monitor_status": energy.monitor_status if energy else "disabled",
            "alarm_active": energy.alarm_active if energy else False,
            "heating_history": energy.heating_history if energy else [],
            "history_energy_totals": energy.history_energy_totals if energy else None,
            "schedule_query_supported": True,
            # Entity-registry lookups survive renames and keep cars separate.
            "control_entities": {
                "manual_departure": entity_id("datetime", "manual_departure"),
                "clear_departure": entity_id("button", "clear_departure"),
                "start_now": entity_id("button", "start_now"),
                "stop_now": entity_id("button", "stop_now"),
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
