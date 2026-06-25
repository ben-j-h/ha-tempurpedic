"""Tempurpedic adjustable base integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import Platform

from .api import TempurpedicClient
from .const import CONF_HOST, CONF_PORT, DEFAULT_PORT
from .data import TempurpedicData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

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
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: TempurpedicConfigEntry,
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
