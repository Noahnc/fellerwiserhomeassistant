"""Platform for light integration."""

from __future__ import annotations

import asyncio
import json
import logging
import socket

import websockets

_LOGGER = logging.getLogger(__name__)

WISER_ENTITIES = []


async def establish_websocket(host, apikey):
    """Establishes a websocket connection to the Wiser API and updates entities based on the messages received."""

    while True:
        _LOGGER.info("Creating new websocket connection")
        try:
            async with websockets.connect(
                "ws://" + host + "/api",
                additional_headers={"authorization": "Bearer " + apikey},
                ping_timeout=None,
            ) as ws:
                while True:
                    await _handle_websocket_message(ws)

        except socket.gaierror:
            _LOGGER.error("Websocket connection error, retrying in 10 sec")
            await asyncio.sleep(10)
            continue
        except ConnectionRefusedError:
            _LOGGER.error("Configured host refused connection, retrying in 10 sec")
            await asyncio.sleep(10)
            continue
        except Exception as e:
            _LOGGER.error("Unhadled Exception occured in WebSocket loop: %s", e)
            continue


async def _handle_websocket_message(ws):
    try:
        result = await asyncio.wait_for(ws.recv(), timeout=None)
    except (TimeoutError, websockets.exceptions.ConnectionClosed):
        try:
            pong = await ws.ping()
            await asyncio.wait_for(pong, timeout=None)
            _LOGGER.info("Ping OK, keeping connection alive")
        except:
            _LOGGER.info("Ping error - retrying connection in 10 sec (Ctrl-C to quit)")
            await asyncio.sleep(10)
            return
    _LOGGER.debug("Reveived the following message form wiser: %s", result)
    message = json.loads(result)

    wiser_entity_id = _get_wiser_entity_id(message)

    if wiser_entity_id is None:
        return

    entity = [e for e in WISER_ENTITIES if e.wiser_entity_id == wiser_entity_id]

    if entity == []:
        _LOGGER.debug("No entity found for id %s", wiser_entity_id)
        return

    entity = entity[0]

    entity.update_from_websocket_message(message)


def _get_wiser_entity_id(message) -> str | None:
    if "load" in message:
        if "id" not in message["load"]:
            _LOGGER.debug("No id in websocket message for load, ignoring")
            return None
        return message["load"]["id"]

    if "hvacgroup" in message:
        if "id" not in message["hvacgroup"]:
            _LOGGER.debug("No id in websocket message for hvacgroup, ignoring")
            return None
        return message["hvacgroup"]["id"]

    return None
