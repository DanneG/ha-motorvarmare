"""Weekly departure times for one car."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

WEEKDAYS = ("Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag", "Lördag", "Söndag")
WEEKDAY_KEYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add one departure time for each day, starting with Monday."""
    controller = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        WeeklyDepartureTime(entry, controller, day, name)
        for day, name in enumerate(WEEKDAYS)
    )


class WeeklyDepartureTime(TimeEntity):
    """A time of day persisted by the controller."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:clock-outline"

    def __init__(self, entry: ConfigEntry, controller, day: int, name: str) -> None:
        self.controller = controller
        self.day = day
        self._signal = f"{DOMAIN}_{entry.entry_id}"
        self._attr_translation_key = f"weekly_time_{WEEKDAY_KEYS[day]}"
        self._attr_unique_id = f"{entry.entry_id}_weekly_time_{day}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name=entry.title
        )

    @property
    def native_value(self) -> time:
        """Return the configured local departure time."""
        return self.controller.weekly_times[self.day]

    async def async_set_value(self, value: time) -> None:
        """Update the time through the controller."""
        await self.controller.async_set_weekly_time(self.day, value)

    async def async_added_to_hass(self) -> None:
        """Listen for changes made by the controller."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._signal, self.async_write_ha_state)
        )
