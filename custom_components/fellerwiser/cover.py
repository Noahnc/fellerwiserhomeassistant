"""Platform for cover integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.cover import ATTR_POSITION, CoverEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import REQUEST_TIMEOUT_SECONDS
from .feller_client import FellerApiClient
from .main import WISER_ENTITIES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up all the Feller Climate Entities."""
    host = entry.data["host"]
    apikey = entry.data["apikey"]

    client = FellerApiClient(host, apikey, REQUEST_TIMEOUT_SECONDS)
    result = await client.get_all_loads_async()

    cover_entries = []
    for value in result.data:
        if value["type"] == "motor":
            if value["unused"]:
                continue
            cover_entries.append(FellerCover(value, client))

    WISER_ENTITIES.extend(cover_entries)

    async_add_entities(cover_entries, True)


class FellerCover(CoverEntity):
    """Represents an Feller Cover."""

    def __init__(self, data, client: FellerApiClient) -> None:
        """Initialize an Feller Cover."""
        self._state = None
        self._data = data
        self._name = data["name"]
        self._id = str(data["id"])
        self._wiser_id = data["id"]
        self._is_opening = False
        self._is_closing = False
        self._is_opened = False
        self._is_closed = False
        self._is_partially_opened = False
        self._position = None
        self._client: FellerApiClient = client

    @property
    def name(self) -> str:
        return self._name

    @property
    def unique_id(self):
        return "cover-" + self._id

    @property
    def wiser_entity_id(self):
        return self._wiser_id

    @property
    def current_cover_position(self):
        return self._position

    @property
    def is_opening(self) -> bool | None:
        return self._is_opening

    @property
    def is_closing(self) -> bool | None:
        return self._is_closing

    @property
    def is_opened(self) -> bool | None:
        return self._is_opened

    @property
    def is_closed(self) -> bool | None:
        return self._is_closed

    @property
    def is_partially_opened(self) -> bool | None:
        return self._is_partially_opened

    @property
    def should_poll(self) -> bool | None:
        return False

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self._position = kwargs.get(ATTR_POSITION, 100)
        result = await self._client.set_cover_level_async(self._wiser_id, 0)
        self._state = True
        self._position = 100 - (result.data["target_state"]["level"] / 100)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        self._position = kwargs.get(ATTR_POSITION, 100)
        result = await self._client.set_cover_level_async(self._wiser_id, 10000)
        self._state = True
        self._position = 100 - (result.data["target_state"]["level"] / 100)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        self._position = kwargs.get(ATTR_POSITION, 100)
        result = await self._client.set_cover_level_async(
            self._wiser_id, (100 - self._position) * 100
        )
        self._state = True
        self._position = 100 - (result.data["target_state"]["level"] / 100)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        await self._client.send_load_ctrl_event_async(
            self._wiser_id, {"button": "stop", "event": "click"}
        )

    async def async_update(self) -> None:
        result = await self._client.get_load_async(self._wiser_id)

        # ha: 100 = open, 0 = closed
        # feller: 10000 = closed, 0 = open
        self._position = 100 - (result.data["state"]["level"] / 100)

        if result.data["state"]["moving"] == "stop":
            self._is_closing = False
            self._is_opening = False
        if result.data["state"]["moving"] == "up":
            self._is_closing = False
            self._is_opening = True
        if result.data["state"]["moving"] == "down":
            self._is_closing = True
            self._is_opening = False

        if self._position >= 100:
            self._is_closed = False
            self._is_opened = True
            self._is_partially_opened = False
        elif self._position <= 0:
            self._is_closed = True
            self._is_opened = False
            self._is_partially_opened = False
        else:
            self._is_closed = False
            self._is_opened = False
            self._is_partially_opened = True

    def update_from_websocket_message(self, message):
        """Updates the cover state from an websocket message."""

        if "load" not in message:
            _LOGGER.debug(
                "No load in websocket message, skipping update of cover with id %s",
                self._id,
            )
            return

        message = message["load"]

        if "state" not in message:
            _LOGGER.debug(
                "No state in websocket message, skipping update of cover with id %s",
                self._id,
            )
            return

        position = message["state"]["level"]
        moving = message["state"]["moving"]

        self._position = 100 - (position / 100)

        if moving == "stop":
            self._is_closing = False
            self._is_opening = False
        if moving == "up":
            self._is_closing = False
            self._is_opening = True
        if moving == "down":
            self._is_closing = True
            self._is_opening = False

        if self._position >= 100:
            self._is_closed = False
            self._is_opened = True
            self._is_partially_opened = False
        elif self._position <= 0:
            self._is_closed = True
            self._is_opened = False
            self._is_partially_opened = False
        else:
            self._is_closed = False
            self._is_opened = False
            self._is_partially_opened = True

        self.schedule_update_ha_state()
