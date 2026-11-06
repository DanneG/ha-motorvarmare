"""Configuration flow for the motor heater integration."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_CALENDAR,
    CONF_EVENT_KEYWORDS,
    CONF_EVENT_TITLES,
    CONF_POWER_ENTITY,
    CONF_ENERGY_ENTITY,
    CONF_POWER_MIN_WATTS,
    CONF_POWER_DELAY_MINUTES,
    CONF_POWER_ALARM_ENABLED,
    CONF_NOTIFY_ENTITY,
    DEFAULT_POWER_MIN_WATTS,
    DEFAULT_POWER_DELAY_MINUTES,
    DEFAULT_POWER_ALARM_ENABLED,
    CONF_SWITCH,
    CONF_TAG,
    CONF_TEMPERATURE,
    DOMAIN,
)


def _schema(values: dict[str, Any] | None = None) -> vol.Schema:
    """Build the same configuration form for setup and options."""
    values = values or {}
    # Existing entries keep working until edited; suggest their legacy tag in
    # the new field the first time the options are opened.
    if CONF_EVENT_KEYWORDS not in values and values.get(CONF_TAG):
        values = {**values, CONF_EVENT_KEYWORDS: values[CONF_TAG]}
    calendar = values.get(CONF_CALENDAR)
    calendar_field = (
        vol.Optional(CONF_CALENDAR, description={"suggested_value": calendar})
        if calendar
        else vol.Optional(CONF_CALENDAR)
    )
    # Suggested values are displayed for editing but are not defaults on an
    # omitted key: clearing a field must remove it instead of restoring it.
    def text_field(key: str, initial: str = ""):
        value = values.get(key, initial)
        return (vol.Optional(key, description={"suggested_value": value})
                if value else vol.Optional(key))

    def optional_entity(key: str):
        """Suggest existing selections without re-adding a cleared field."""
        value = values.get(key)
        return (vol.Optional(key, description={"suggested_value": value})
                if value else vol.Optional(key))

    multiline = selector.TextSelector(selector.TextSelectorConfig(multiline=True))
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=values.get(CONF_NAME, "")): str,
            vol.Required(CONF_SWITCH, default=values.get(CONF_SWITCH, "")):
                selector.EntitySelector(selector.EntitySelectorConfig(domain="switch")),
            vol.Required(CONF_TEMPERATURE, default=values.get(CONF_TEMPERATURE, "")):
                selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            calendar_field: selector.EntitySelector(
                selector.EntitySelectorConfig(domain="calendar")
            ),
            text_field(CONF_EVENT_TITLES): multiline,
            text_field(CONF_EVENT_KEYWORDS): multiline,
            optional_entity(CONF_POWER_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            optional_entity(CONF_ENERGY_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(CONF_POWER_ALARM_ENABLED, default=values.get(CONF_POWER_ALARM_ENABLED, DEFAULT_POWER_ALARM_ENABLED)): bool,
            vol.Required(CONF_POWER_MIN_WATTS, default=values.get(CONF_POWER_MIN_WATTS, DEFAULT_POWER_MIN_WATTS)):
                selector.NumberSelector(selector.NumberSelectorConfig(
                    min=0.1, max=10000, step="any", mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="W",
                )),
            vol.Required(CONF_POWER_DELAY_MINUTES, default=values.get(CONF_POWER_DELAY_MINUTES, DEFAULT_POWER_DELAY_MINUTES)):
                selector.NumberSelector(selector.NumberSelectorConfig(
                    min=1, max=120, step=1, mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="min",
                )),
            optional_entity(CONF_NOTIFY_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="notify")
            ),
        }
    )


def _error(
    hass, user_input: dict[str, Any], own_entry_id: str | None = None,
    legacy_tag: str = "",
) -> str | None:
    """Validate calendar rules and prevent conflicting switch control."""
    user_input[CONF_NAME] = user_input[CONF_NAME].strip()
    for key in (CONF_EVENT_TITLES, CONF_EVENT_KEYWORDS):
        user_input[key] = (user_input.get(key) or "").strip()
    # Preserve the old tag's original substring semantics only while the same
    # item remains in the keyword field; clearing or replacing it disables it.
    keyword_items = {
        item.strip().casefold()
        for item in re.split(r"[,\n]", user_input[CONF_EVENT_KEYWORDS])
        if item.strip()
    }
    old_tag = (legacy_tag or "").strip()
    user_input[CONF_TAG] = old_tag if old_tag.casefold() in keyword_items else ""
    if not user_input[CONF_NAME]:
        return "invalid_name"
    if user_input.get(CONF_CALENDAR) and not any(
        user_input[key].replace(",", "").strip()
        for key in (CONF_EVENT_TITLES, CONF_EVENT_KEYWORDS)
    ):
        return "missing_calendar_rule"
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id == own_entry_id:
            continue
        values = {**entry.data, **entry.options}
        if values.get(CONF_SWITCH) == user_input[CONF_SWITCH]:
            return "duplicate_switch"
    return None


def _normalize_optional_entities(user_input: dict[str, Any]) -> None:
    """Store cleared values explicitly, so old entry data cannot reappear."""
    for key in (CONF_CALENDAR, CONF_POWER_ENTITY, CONF_ENERGY_ENTITY, CONF_NOTIFY_ENTITY):
        user_input[key] = user_input.get(key) or ""


class MotorvarmareConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create a separate entry for each car."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            error = _error(self.hass, user_input)
            if error is None:
                _normalize_optional_entities(user_input)
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
            return self.async_show_form(
                step_id="user", data_schema=_schema(user_input), errors={"base": error}
            )
        return self.async_show_form(step_id="user", data_schema=_schema())

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return MotorvarmareOptionsFlow(config_entry)


class MotorvarmareOptionsFlow(config_entries.OptionsFlow):
    """Edit all settings, with options overriding initial entry data."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            current = {**self._entry.data, **self._entry.options}
            error = _error(self.hass, user_input, self._entry.entry_id, current.get(CONF_TAG, ""))
            if error is None:
                _normalize_optional_entities(user_input)
                self.hass.config_entries.async_update_entry(
                    self._entry, title=user_input[CONF_NAME]
                )
                return self.async_create_entry(title="", data=user_input)
            return self.async_show_form(
                step_id="init", data_schema=_schema(user_input), errors={"base": error}
            )
        return self.async_show_form(
            step_id="init", data_schema=_schema({**self._entry.data, **self._entry.options})
        )
