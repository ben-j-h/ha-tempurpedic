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
    # Last commanded vibration level per zone (VIB_ZONE_* -> 0..10). Shared across
    # the three zone sliders so "all zones off" can trigger a full stop.
    vib_levels: dict[int, int] = field(default_factory=dict)
    # The three zone-slider entities, so the program entity can move them.
    vib_numbers: list = field(default_factory=list)
    # The consolidated massage-program (0..4) and position-preset (0..4) entities,
    # plus their last values, so each can reset the other on manual input.
    massage_program: int = 0
    position_preset: int = 0
    program_number: object | None = field(default=None)
    preset_number: object | None = field(default=None)
