"""Platform for light integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, LightEntity

from .const import REQUEST_TIMEOUT_SECONDS

# Import the device class from the component that you want to support
from .feller_client import FellerApiClient, FellerApiException
from .main import WISER_ENTITIES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    host = entry.data["host"]
    apikey = entry.data["apikey"]

    client = FellerApiClient(host, apikey, REQUEST_TIMEOUT_SECONDS)
    result = await client.get_all_loads_async()

    light_entities = []
    for value in result.data:
        if value["type"] in ["dim", "dali", "onoff"]:
            if value["unused"] == True:
                continue
            light_entities.append(FellerLight(value, client))

    WISER_ENTITIES.extend(light_entities)

    async_add_entities(light_entities, True)


class FellerLight(LightEntity):
    """Representation of an Feller Light."""

    def __init__(self, data, client: FellerApiClient) -> None:
        """Initialize an Feller Light."""
        self._name = data["name"]
        self._id = str(data["id"])
        self._wiser_id = data["id"]
        self._attr_unique_id = f"light.{self._id}"
        self._is_on = None
        self._brightness = None
        self._client: FellerApiClient = client
        self._type = data["type"]

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._name

    @property
    def wiser_entity_id(self):
        return self._wiser_id

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        return self._is_on

    @property
    def should_poll(self) -> bool | None:
        return False

    @property
    def color_mode(self) -> str | None:
        if self._type == "onoff":
            return "onoff"
        return "brightness"

    @property
    def supported_color_modes(self) -> set | None:
        if self._type == "onoff":
            return {"onoff"}
        return {"brightness"}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on.

        You can skip the brightness part if your light does not support
        brightness control.
        """

        if not kwargs:
            await self._client.send_load_ctrl_event_async(
                load_id=self._wiser_id, body={"button": "on", "event": "click"}
            )
            self._is_on = True
            result = await self._client.get_load_async(self._wiser_id)
            self._brightness = result.data["state"]["bri"] / 39.22
            return

        self._brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
        convertedBrightness = round(self._brightness * 39.22)

        if convertedBrightness > 10000:
            convertedBrightness = 10000

        result = await self._client.set_light_brightness_async(
            self._wiser_id, convertedBrightness
        )
        self._is_on = True
        self._brightness = result.data["target_state"]["bri"] / 39.22

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""

        await self._client.send_load_ctrl_event_async(
            load_id=self._wiser_id, body={"button": "off", "event": "click"}
        )
        self._is_on = False
        result = await self._client.get_load_async(self._wiser_id)
        self._brightness = result.data["state"]["bri"] / 39.22

    async def async_update(self) -> None:
        """Fetches the current state of the ligth."""

        result = await self._client.get_load_async(self._wiser_id)

        _LOGGER.debug("Got the following state for light %s: %s", self._id, result.data)

        if "state" not in result.data:
            _LOGGER.debug("No state in update response for light %s", self._id)
            return

        if result.data["state"]["bri"] is None:
            self._brightness = 0
            self._is_on = False
            return

        if result.data["state"]["bri"] > 0:
            self._is_on = True
        else:
            self._is_on = False
        self._brightness = result.data["state"]["bri"] / 39.22

    def update_from_websocket_message(self, message):
        """Updates the ligth from an websocket message."""

        if "load" not in message:
            _LOGGER.debug(
                "No load in websocket message, skipping update of light with id %s",
                self._id,
            )
            return

        message = message["load"]

        if "state" not in message:
            _LOGGER.debug(
                "No state in websocket message, skipping update of light with id %s",
                self._id,
            )
            return

        try:
            if message["state"]["flags"]["fading"] == 1:
                # Skip update since light is in fading updateExternal
                return
        except KeyError:
            pass

        if "bri" not in message["state"]:
            _LOGGER.debug(
                "No bri in websocket message, skipping update of light with id %s",
                self._id,
            )
            return

        if message["state"]["bri"] is None:
            self._brightness = 0
            self._is_on = False
            self.schedule_update_ha_state()
            return

        if message["state"]["bri"] == 0:
            self._is_on = False
            self._brightness = 0
            self.schedule_update_ha_state()
            return

        self._brightness = message["state"]["bri"] / 39.22
        self._is_on = True
        self.schedule_update_ha_state()
