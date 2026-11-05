"""Manual departure time for the engine heater."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.datetime import DateTimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create the manual departure entity for one car."""
    controller = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ManualDeparture(entry, controller)])


class ManualDeparture(DateTimeEntity, RestoreEntity):
    """An optional one-off departure, persisted by the controller."""

    _attr_has_entity_name = True
    _attr_name = "Manuell avresa"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, entry: ConfigEntry, controller) -> None:
        """Bind the entity to its car."""
        self.controller = controller
        self._signal = f"{DOMAIN}_{entry.entry_id}"
        self._attr_unique_id = f"{entry.entry_id}_manual_departure"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name=entry.title
        )

    @property
    def native_value(self) -> datetime | None:
        """Display the controller's persisted time in the local time zone."""
        value = self.controller.manual_departure
        return dt_util.as_local(value) if value is not None else None

    async def async_set_value(self, value: datetime) -> None:
        """Store the departure as an aware UTC datetime."""
        await self.controller.async_set_manual_departure(dt_util.as_utc(value))

    async def async_added_to_hass(self) -> None:
        """Listen for changes made by the controller."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._signal, self.async_write_ha_state)
        )
