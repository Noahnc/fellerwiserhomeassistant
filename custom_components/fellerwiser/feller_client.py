import asyncio
import logging

import aiohttp

_LOGGER = logging.getLogger(__name__)


class FellerApiResult:
    """Result of a Feller API request."""

    def __init__(self, status_code: int, data: dict | None) -> None:
        """Result initialization."""
        self._status_code = status_code
        self._data = data

    @property
    def status_code(self) -> int:
        """Get the status code of the request."""
        return self._status_code

    @property
    def data(self) -> dict:
        """Get the data of the request."""
        return self._data


class FellerApiException(Exception):
    """Exception raised when a Feller API request fails."""

    def __init__(self, message: str) -> None:
        """Exception initialization."""
        super().__init__(message)


class FellerApiClient:
    """Client for communicate with Feller Wiser API."""

    def __init__(self, host: str, apiKey: str, request_timeout_seconds: int) -> None:
        """Client initialization."""
        self._host = host
        self._apiKey = apiKey
        self._request_timeout_seconds = request_timeout_seconds

    async def get_all_loads_async(self) -> FellerApiResult:
        """Get all loads from the Wiser API."""
        return await self._send_request_async(endpoint="loads")

    async def get_all_hvac_groups_async(self) -> FellerApiResult:
        """Get all hvac groups from the Wiser API."""
        return await self._send_request_async(endpoint="hvacgroups")

    async def get_hvac_group_async(
        self, group_id: int, retry_count: int = 5
    ) -> FellerApiResult:
        """Get an hvac group from the Wiser API."""
        return await self._send_request_with_retry_async(
            endpoint=f"hvacgroups/{group_id}", retry_count=retry_count
        )

    async def get_load_async(
        self, load_id: int, retry_count: int = 5
    ) -> FellerApiResult:
        """Get a load from the Wiser API."""
        return await self._send_request_with_retry_async(
            endpoint=f"loads/{load_id}", retry_count=retry_count
        )

    async def set_hvac_group_temperature_async(
        self, group_id: int, target_temperature: float
    ) -> FellerApiResult:
        """Set the target temperature for an hvac group."""
        return await self._send_request_async(
            endpoint=f"hvacgroups/{group_id}/target_state",
            method="PUT",
            data={"target_temperature": target_temperature},
        )

    async def set_hvac_group_state_async(
        self, group_id: int, on: bool
    ) -> FellerApiResult:
        """Set the state for an hvac group."""
        return await self._send_request_async(
            endpoint=f"hvacgroups/{group_id}/target_state",
            method="PUT",
            data={"on": on},
        )

    async def send_load_ctrl_event_async(
        self, load_id: int, body: dict
    ) -> FellerApiResult:
        """Send a button control event to the Wiser API."""
        return await self._send_request_async(
            endpoint=f"loads/{load_id}/ctrl",
            method="PUT",
            data=body,
        )

    async def set_light_brightness_async(
        self, light_id: int, brightness: float
    ) -> FellerApiResult:
        """Set the brightness for a light."""
        return await self._send_request_async(
            endpoint=f"loads/{light_id}/target_state",
            method="PUT",
            data={"bri": brightness},
        )

    async def set_cover_level_async(self, cover_id: int, level: int) -> FellerApiResult:
        """Set the level for a cover."""
        return await self._send_request_async(
            endpoint=f"loads/{cover_id}/target_state",
            method="PUT",
            data={"level": level},
        )

    async def _send_request_with_retry_async(
        self,
        endpoint: str,
        retry_count: int,
        method: str = "GET",
        data: dict | None = None,
    ) -> None | FellerApiResult:
        """Send request to Feller Wiser API with retry."""
        for i in range(retry_count):
            try:
                return await self._send_request_async(endpoint, method, data)
            except FellerApiException as e:
                await asyncio.sleep(i + 1)

        raise FellerApiException(
            f"Wiser API Request to {endpoint} failed after {retry_count} retries"
        )

    async def _send_request_async(
        self, endpoint: str, method: str = "GET", data: dict | None = None
    ) -> None | FellerApiResult:
        """Send request to Feller Wiser API."""
        url = f"http://{self._host}/api/{endpoint}"
        headers = {"authorization": f"Bearer {self._apiKey}"}

        _LOGGER.debug("Sending request to %s", url)
        try:
            async with (
                aiohttp.ClientSession() as session,
                session.request(
                    method,
                    url,
                    headers=headers,
                    json=data,
                    timeout=self._request_timeout_seconds,
                ) as response,
            ):
                if response.status >= 400:
                    _LOGGER.error(
                        "Wiser API request to endpoint %s with method %s was unsuccessful: response code %s",
                        endpoint,
                        method,
                        response.status,
                    )
                    raise FellerApiException(
                        f"Wiser API Request to {url} failed with status {response.status}"
                    )
                data = await response.json()

                if data["status"] == "success":
                    _LOGGER.debug(
                        "Wiser API request to endpoint %s with method %s was successful",
                        endpoint,
                        method,
                    )
                    return FellerApiResult(
                        status_code=response.status,
                        data=data["data"],
                    )

                _LOGGER.error(
                    "Wiser API request to endpoint %s with method %s was unsuccessful: response code %s",
                    endpoint,
                    method,
                    response.status,
                )
                raise FellerApiException(
                    f"Wiser API Request to {url} failed with status {response.status}"
                )
        except aiohttp.ClientError as e:
            _LOGGER.error(
                "Wiser API request to endpoint %s with method %s failed: %s",
                endpoint,
                method,
                e,
            )
            raise FellerApiException(
                f"Wiser API Request to {url} failed with error {e}"
            ) from e
