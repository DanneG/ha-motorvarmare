"""Permission-checked read-only schedule projection for the dashboard card."""
from __future__ import annotations

from datetime import date
import re

import voluptuous as vol
from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.components import websocket_api
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import CONF_CALENDAR, DOMAIN


@websocket_api.websocket_command({
    vol.Required("type"): "motorvarmare/get_schedule",
    vol.Required("entity_id"): cv.entity_domain("sensor"),
    vol.Required("start"): str,
    vol.Required("end"): str,
})
@websocket_api.async_response
async def websocket_get_schedule(hass, connection, msg):
    """Return a <=31 day schedule after checking all relevant permissions."""
    entity_id = msg["entity_id"]
    if not connection.user.permissions.check_entity(entity_id, POLICY_READ):
        raise Unauthorized(entity_id=entity_id)
    registry = er.async_get(hass)
    registry_entry = registry.async_get(entity_id)
    entry_id = registry_entry.config_entry_id if registry_entry else None
    controller = hass.data.get(DOMAIN, {}).get(entry_id)
    if (not registry_entry or registry_entry.platform != DOMAIN or not controller
            or registry_entry.unique_id != f"{entry_id}_status"):
        connection.send_error(msg["id"], "not_found", "Motor heater status entity not found")
        return
    local_calendar = registry.async_get_entity_id("calendar", DOMAIN, f"{entry_id}_departure_calendar")
    if not local_calendar:
        connection.send_error(msg["id"], "not_found", "Motor heater calendar entity not found")
        return
    if not connection.user.permissions.check_entity(local_calendar, POLICY_READ):
        raise Unauthorized(entity_id=local_calendar)
    try:
        if not all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", msg[key]) for key in ("start", "end")):
            raise ValueError
        start, end = date.fromisoformat(msg["start"]), date.fromisoformat(msg["end"])
        if not 1 <= (end - start).days <= 31 or end.year >= 9999:
            raise ValueError
    except ValueError:
        connection.send_error(msg["id"], "invalid_format", "Expected a date range of 1 to 31 days")
        return
    external = controller.config.get(CONF_CALENDAR)
    permitted = not external or connection.user.permissions.check_entity(external, POLICY_READ)
    try:
        result = await controller.async_schedule_between(start, end, include_external=permitted)
    except (ValueError, OverflowError):
        connection.send_error(msg["id"], "invalid_format", "Invalid schedule date range")
        return
    connection.send_result(msg["id"], result)
