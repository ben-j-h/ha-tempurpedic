"""Runtime data types for ha_tempurpedic."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    import asyncio

    from .api import TempurpedicClient

type TempurpedicConfigEntry = ConfigEntry[TempurpedicData]


@dataclass
class TempurpedicData:
    """Runtime data stored in config entry."""

    client: TempurpedicClient
    move_task: asyncio.Task | None = field(default=None)
    head_ticks: int = 0
    leg_ticks: int = 0
    position_sensors: list = field(default_factory=list)
