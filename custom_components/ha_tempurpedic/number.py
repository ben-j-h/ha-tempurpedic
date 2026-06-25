"""Number platform for ha_tempurpedic — vibration intensity per zone."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode

from .const import VIB_ZONE_HEAD, VIB_ZONE_LEGS, VIB_ZONE_TORSO, build_vib_command
from .entity import TempurpedicEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import TempurpedicConfigEntry


@dataclass(frozen=True, kw_only=True)
class TempurpedicNumberDescription(NumberEntityDescription):
    zone: int


NUMBER_DESCRIPTIONS: tuple[TempurpedicNumberDescription, ...] = (
    TempurpedicNumberDescription(key="vib_head",  name="Head Vibration",  icon="mdi:vibrate", zone=VIB_ZONE_HEAD),
    TempurpedicNumberDescription(key="vib_torso", name="Torso Vibration", icon="mdi:vibrate", zone=VIB_ZONE_TORSO),
    TempurpedicNumberDescription(key="vib_legs",  name="Legs Vibration",  icon="mdi:vibrate", zone=VIB_ZONE_LEGS),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TempurpedicConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(
        TempurpedicVibrationNumber(entry=entry, description=desc)
        for desc in NUMBER_DESCRIPTIONS
    )


class TempurpedicVibrationNumber(TempurpedicEntity, NumberEntity):
    """Slider to set vibration intensity for one zone (1–10)."""

    entity_description: TempurpedicNumberDescription

    _attr_native_min_value = 1
    _attr_native_max_value = 10
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_native_value: float = 1

    def __init__(
        self,
        entry: TempurpedicConfigEntry,
        description: TempurpedicNumberDescription,
    ) -> None:
        super().__init__(entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        cmd = build_vib_command(self.entity_description.zone, int(value))
        client = self._entry.runtime_data.client
        await self.hass.async_add_executor_job(client.send_command, cmd)
        self.async_write_ha_state()
