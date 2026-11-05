"""Enable or disable each weekly departure."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .time import WEEKDAYS, WEEKDAY_KEYS


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add a schedule toggle for each day, starting with Monday."""
    controller = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        WeeklyDepartureSwitch(entry, controller, day, name)
        for day, name in enumerate(WEEKDAYS)
    )


class WeeklyDepartureSwitch(SwitchEntity):
    """Whether a day is included in the weekly schedule."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:calendar-check"

    def __init__(self, entry: ConfigEntry, controller, day: int, name: str) -> None:
        self.controller = controller
        self.day = day
        self._signal = f"{DOMAIN}_{entry.entry_id}"
        self._attr_translation_key = f"weekly_enabled_{WEEKDAY_KEYS[day]}"
        self._attr_unique_id = f"{entry.entry_id}_weekly_enabled_{day}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name=entry.title
        )

    @property
    def is_on(self) -> bool:
        """Return whether the day is enabled."""
        return self.controller.weekly_enabled[self.day]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the weekly departure for this day."""
        await self.controller.async_set_weekly_enabled(self.day, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the weekly departure for this day."""
        await self.controller.async_set_weekly_enabled(self.day, False)

    async def async_added_to_hass(self) -> None:
        """Listen for changes made by the controller."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._signal, self.async_write_ha_state)
        )
