"""Runtime data types for ha_tempurpedic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .api import TempurpedicClient

type TempurpedicConfigEntry = ConfigEntry[TempurpedicData]


@dataclass
class TempurpedicData:
    """Runtime data stored in config entry."""

    client: TempurpedicClient
