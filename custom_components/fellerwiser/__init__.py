"""The Feller Wiser integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .main import establish_websocket

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)


PLATFORMS: list[Platform] = [Platform.COVER, Platform.LIGHT, Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Feller Wiser from a config entry."""
    host = entry.data["host"]
    apikey = entry.data["apikey"]
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info("----------------------blubb-------------------------")
    asyncio.get_event_loop().create_task(establish_websocket(host, apikey))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    for platform in PLATFORMS:
        await hass.config_entries.async_forward_entry_unload(entry, platform)

    return True
