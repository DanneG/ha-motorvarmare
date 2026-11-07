"""Buttons to control a heater and its one-time departure."""

from homeassistant.components.button import ButtonEntity
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    controller = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        ClearDepartureButton(controller, entry),
        StartNowButton(controller, entry),
        StopNowButton(controller, entry),
        SkipNextButton(controller, entry),
    ])


class ClearDepartureButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "clear_departure"
    _attr_icon = "mdi:calendar-remove"

    def __init__(self, controller, entry):
        self._controller = controller
        self._attr_unique_id = f"{entry.entry_id}_clear_departure"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name=entry.title)

    async def async_press(self):
        await self._controller.async_set_manual_departure(None)


class StartNowButton(ButtonEntity):
    """Start an owned, time-limited heating session."""

    _attr_has_entity_name = True
    _attr_translation_key = "start_now"
    _attr_icon = "mdi:play-circle-outline"

    def __init__(self, controller, entry):
        self._controller = controller
        self._attr_unique_id = f"{entry.entry_id}_start_now"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name=entry.title)

    async def async_press(self):
        try:
            await self._controller.async_start_now()
        except ValueError as err:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key=str(err)) from err


class StopNowButton(ButtonEntity):
    """Stop heating owned by the integration."""

    _attr_has_entity_name = True
    _attr_translation_key = "stop_now"
    _attr_icon = "mdi:stop-circle-outline"

    def __init__(self, controller, entry):
        self._controller = controller
        self._attr_unique_id = f"{entry.entry_id}_stop_now"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name=entry.title)

    async def async_press(self):
        try:
            await self._controller.async_stop_now()
        except ValueError as err:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key=str(err)) from err


class SkipNextButton(ButtonEntity):
    """Skip the next departure without deleting the calendar event."""
    _attr_has_entity_name = True
    _attr_translation_key = "skip_next"
    _attr_icon = "mdi:calendar-arrow-right"

    def __init__(self, controller, entry):
        self._controller = controller
        self._attr_unique_id = f"{entry.entry_id}_skip_next"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name=entry.title)

    async def async_press(self):
        try:
            await self._controller.async_skip_next()
        except ValueError as err:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key=str(err)) from err
