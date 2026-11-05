"""Clear the one-time departure."""

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([ClearDepartureButton(hass.data[DOMAIN][entry.entry_id], entry)])


class ClearDepartureButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_name = "Rensa manuell avresa"
    _attr_icon = "mdi:calendar-remove"

    def __init__(self, controller, entry):
        self._controller = controller
        self._attr_unique_id = f"{entry.entry_id}_clear_departure"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name=entry.title)

    async def async_press(self):
        await self._controller.async_set_manual_departure(None)
