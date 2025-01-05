"""Platform for light integration."""

from __future__ import annotations

import logging

# Import the device class from the component that you want to support
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature

from .const import REQUEST_TIMEOUT_SECONDS
from .feller_client import FellerApiClient
from .main import WISER_ENTITIES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up all the Feller Climate Entities."""
    host = entry.data["host"]
    apikey = entry.data["apikey"]

    client = FellerApiClient(host, apikey, REQUEST_TIMEOUT_SECONDS)
    result = await client.get_all_hvac_groups_async()

    climate_entities = []
    for group in result.data:
        climate_entities.append(FellerHvacGroup(group, client))

    WISER_ENTITIES.extend(climate_entities)

    async_add_entities(climate_entities, True)


class FellerHvacGroup(ClimateEntity):
    """Representation of an Feller Climate Controller Channel."""

    def __init__(self, group: dict, client: FellerApiClient) -> None:
        """Initialize an Feller Hvac Group."""
        self._name: str = group["name"]
        self._id: str = str(group["id"])
        self._wiser_id: int = group["id"]
        self._load_ids: list[int] = group["loads"]
        self._attr_unique_id = f"climate.{self._id}"
        self.entity_id = self._attr_unique_id
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )
        self._client: FellerApiClient = client
        self._current_temperature: float | None = None
        self._target_temperature: float | None = None
        self._hvac_mode: HVACMode | None = None
        self._hvac_action: HVACAction | None = None
        self._min_temp: float | None = None
        self._max_temp: float | None = None
        self._hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
        self._temp_mode = UnitOfTemperature.CELSIUS

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._name

    @property
    def wiser_entity_id(self):
        return self._wiser_id

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def target_temperature(self):
        """Return the target temperature."""
        return self._target_temperature

    @property
    def hvac_mode(self):
        """Return the current operation mode."""
        return self._hvac_mode

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return self._hvac_modes

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self._min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._max_temp

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._temp_mode

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temperature = kwargs.get("temperature")
        await self._client.set_hvac_group_temperature_async(
            group_id=self._wiser_id, target_temperature=target_temperature
        )
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""

        if hvac_mode == self._hvac_mode:
            return

        if hvac_mode == HVACMode.HEAT:
            await self.async_turn_on()
        elif hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        else:
            _LOGGER.error("Unknown hvac mode %s", hvac_mode)

    async def async_turn_on(self) -> None:
        """Turn on the climate entity."""
        await self._client.set_hvac_group_state_async(group_id=self._wiser_id, on=True)
        self._hvac_mode = HVACMode.HEAT
        self.async_write_ha_state()

    async def async_turn_off(self):
        """Turn off the climate entity."""
        await self._client.set_hvac_group_state_async(group_id=self._wiser_id, on=False)
        self._hvac_mode = HVACMode.OFF
        self.async_write_ha_state()

    async def async_update(self):
        """Update the state of the hvac group."""
        result = await self._client.get_hvac_group_async(self._wiser_id)
        self._update_from_state(result.data["state"])

        self._min_temp = result.data["min_temperature"]
        self._max_temp = result.data["max_temperature"]

    def update_from_websocket_message(self, message):
        if "hvacgroup" not in message:
            _LOGGER.debug(
                "No hvacgroup in websocket message, skipping update of hvacgroup with id %s",
                self._id,
            )
            return

        message = message["hvacgroup"]

        if "state" not in message:
            _LOGGER.debug(
                "No state in websocket message, skipping update of cover with id %s",
                self._id,
            )
            return
        self._update_from_state(message["state"])
        self.schedule_update_ha_state()

    def _update_from_state(self, state: dict):
        self._current_temperature = state["ambient_temperature"]
        self._target_temperature = state["target_temperature"]

        if state["on"]:
            self._hvac_mode = HVACMode.HEAT
        else:
            self._hvac_mode = HVACMode.OFF

        heating_level = state["heating_cooling_level"]

        if heating_level > 0:
            self._hvac_action = HVACAction.HEATING
        else:
            self._hvac_action = HVACAction.IDLE
