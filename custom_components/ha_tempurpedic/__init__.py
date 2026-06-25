"""Tempurpedic adjustable base integration."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.const import Platform
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er

from .api import TempurpedicClient
from .const import COMMANDS, CONF_HOST, CONF_PORT, DEFAULT_PORT, DOMAIN, LOGGER
from .data import TempurpedicData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

    from .data import TempurpedicConfigEntry

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.NUMBER]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TempurpedicConfigEntry,
) -> bool:
    """Set up Tempurpedic from a config entry."""
    client = TempurpedicClient(
        host=entry.data[CONF_HOST],
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
    )
    entry.runtime_data = TempurpedicData(client=client)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.runtime_data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if not hass.services.has_service(DOMAIN, "start_move"):
        _async_register_services(hass)

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: TempurpedicConfigEntry,
) -> bool:
    """Unload a config entry."""
    entry_data = hass.data[DOMAIN].pop(entry.entry_id, None)
    if entry_data and entry_data.move_task and not entry_data.move_task.done():
        entry_data.move_task.cancel()

    if not hass.data[DOMAIN]:
        hass.services.async_remove(DOMAIN, "start_move")
        hass.services.async_remove(DOMAIN, "stop_move")

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _async_register_services(hass: HomeAssistant) -> None:
    async def handle_start_move(call: ServiceCall) -> None:
        entity_id: str = call.data["entity_id"]
        ent_reg = er.async_get(hass)
        entity_entry = ent_reg.async_get(entity_id)
        if not entity_entry or not entity_entry.config_entry_id:
            LOGGER.warning("start_move: unknown entity %s", entity_id)
            return

        entry_id = entity_entry.config_entry_id
        entry_data = hass.data[DOMAIN].get(entry_id)
        if not entry_data:
            return

        # unique_id format: "{entry_id}_{command_key}"
        command_key = entity_entry.unique_id[len(entry_id) + 1:]
        command = COMMANDS.get(command_key)
        if not command:
            LOGGER.warning("start_move: no command for key %s", command_key)
            return

        if entry_data.move_task and not entry_data.move_task.done():
            entry_data.move_task.cancel()

        async def move_loop() -> None:
            while True:
                await hass.async_add_executor_job(
                    entry_data.client.send_command, command
                )
                await asyncio.sleep(0)

        entry_data.move_task = hass.async_create_task(move_loop())

    async def handle_stop_move(_call: ServiceCall) -> None:
        for entry_data in hass.data[DOMAIN].values():
            if entry_data.move_task and not entry_data.move_task.done():
                entry_data.move_task.cancel()
                entry_data.move_task = None

    hass.services.async_register(
        DOMAIN,
        "start_move",
        handle_start_move,
        schema=vol.Schema({vol.Required("entity_id"): cv.entity_id}),
    )
    hass.services.async_register(
        DOMAIN,
        "stop_move",
        handle_stop_move,
        schema=vol.Schema({}),
    )
