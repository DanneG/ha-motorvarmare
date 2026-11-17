"""Schedule an engine heater around departures."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .controller import HeaterController

PLATFORMS = [Platform.DATETIME, Platform.SENSOR, Platform.BUTTON, Platform.TIME, Platform.SWITCH, Platform.CALENDAR]
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register the read-only schedule API once for all cars."""
    from homeassistant.components import websocket_api
    from .frontend import async_register_card
    from .websocket import websocket_get_schedule

    websocket_api.async_register_command(hass, websocket_get_schedule)
    try:
        await async_register_card(hass, config)
    except Exception:
        # A dashboard failure must not prevent the heater itself from starting.
        _LOGGER.exception("Unable to register the Motorvärmare dashboard card")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one car."""
    controller = HeaterController(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = controller
    await controller.async_load()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await controller.async_start()
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    controller = hass.data[DOMAIN][entry.entry_id]
    # Stop any heater we own before unloading or changing its switch.
    if not await controller.async_shutdown():
        return False
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded
