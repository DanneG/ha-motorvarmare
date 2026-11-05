"""Status for the engine heater."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create a status sensor for one car."""
    controller = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([HeaterStatus(entry, controller)])


class HeaterStatus(SensorEntity):
    """Show the current decision and the information behind it."""

    _attr_has_entity_name = True
    _attr_name = "Status"
    _attr_icon = "mdi:car-defrost-front"

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
        return self.controller.status

    @property
    def extra_state_attributes(self) -> dict:
        """Expose the next decision and any problem."""
        controller = self.controller
        registry = er.async_get(self.hass)

        def entity_id(domain: str, suffix: str) -> str | None:
            return registry.async_get_entity_id(domain, DOMAIN, f"{self._entry_id}_{suffix}")

        return {
            "next_departure": controller.next_departure,
            "planned_start": controller.planned_start,
            "temperature": controller.temperature,
            "duration_minutes": controller.duration_minutes,
            "source": controller.source,
            "error": controller.error,
            "owned": controller.owned,
            # Entity-registry lookups survive renames and keep cars separate.
            "control_entities": {
                "manual_departure": entity_id("datetime", "manual_departure"),
                "clear_departure": entity_id("button", "clear_departure"),
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
