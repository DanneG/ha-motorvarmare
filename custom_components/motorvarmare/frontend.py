"""Serve and register the bundled Motorvärmare dashboard card."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
CARD_PATH = "/motorvarmare/ha-motorvarmare-card.js"
_LEGACY_PATHS = frozenset(
    {
        "/hacsfiles/ha-motorvarmare-card/ha-motorvarmare-card.js",
        "/local/community/ha-motorvarmare-card/ha-motorvarmare-card.js",
        "/local/ha-motorvarmare-card.js",
    }
)


def _our_resource(url: str) -> bool:
    """Only migrate known local versions of this card, never remote URLs."""
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    return not parsed.scheme and not parsed.netloc and parsed.path in (
        _LEGACY_PATHS | {CARD_PATH}
    )


async def async_register_card(hass: HomeAssistant, config: dict) -> None:
    """Serve the card once per integration setup and register its resource."""
    from homeassistant.components.http import StaticPathConfig
    from homeassistant.components.lovelace import LOVELACE_DATA
    from homeassistant.loader import async_get_integration
    from homeassistant.setup import async_setup_component

    card_file = Path(__file__).parent / "www" / "ha-motorvarmare-card.js"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_PATH, str(card_file), False)]
    )
    integration = await async_get_integration(hass, "motorvarmare")
    resource_url = f"{CARD_PATH}?v={integration.version}"

    if not await async_setup_component(hass, "lovelace", config):
        _LOGGER.warning("Dashboard setup failed; cannot register the Motorvärmare card")
        return
    lovelace = hass.data[LOVELACE_DATA]
    await _async_register_resource(lovelace, resource_url)


async def _async_register_resource(lovelace, resource_url: str) -> None:
    """Register or migrate known resources without touching unrelated entries."""
    resources = lovelace.resources
    if lovelace.resource_mode != "storage":
        _LOGGER.warning(
            "Dashboard resources are managed in YAML; configure the Motorvärmare "
            "card resource manually as a module at %s and remove any older card URL",
            resource_url,
        )
        return

    # async_items() does not load storage. Loading before inspecting the items is
    # essential to avoid overwriting existing resources after a restart.
    await resources.async_get_info()
    matches = [item for item in resources.async_items() if _our_resource(item.get("url", ""))]
    if not matches:
        await resources.async_create_item({"res_type": "module", "url": resource_url})
        return

    # Prefer the bundled entry so its ID stays stable when older entries exist.
    primary = next(
        (item for item in matches if urlsplit(item["url"]).path == CARD_PATH),
        matches[0],
    )
    if primary.get("url") != resource_url or primary.get("type") != "module":
        await resources.async_update_item(
            primary["id"], {"res_type": "module", "url": resource_url}
        )
    for duplicate in matches:
        if duplicate["id"] != primary["id"]:
            await resources.async_delete_item(duplicate["id"])
