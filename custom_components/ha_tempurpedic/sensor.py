"""Sensor platform for ha_tempurpedic -- position tracking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE

from .const import CONF_HEAD_MAX, CONF_LEG_MAX, DEFAULT_HEAD_MAX, DEFAULT_LEG_MAX
from .entity import TempurpedicEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import TempurpedicConfigEntry


@dataclass(frozen=True, kw_only=True)
class TempurpedicSensorDescription(SensorEntityDescription):
    """Description for a Tempurpedic position sensor."""

    zone: str


SENSOR_DESCRIPTIONS: tuple[TempurpedicSensorDescription, ...] = (
    TempurpedicSensorDescription(
        key="head_position",
        name="Head Position",
        icon="mdi:angle-acute",
        zone="head",
    ),
    TempurpedicSensorDescription(
        key="leg_position",
        name="Leg Position",
        icon="mdi:angle-acute",
        zone="leg",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: TempurpedicConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up position sensor entities from a config entry."""
    async_add_entities(
        TempurpedicPositionSensor(entry=entry, description=desc)
        for desc in SENSOR_DESCRIPTIONS
    )


class TempurpedicPositionSensor(TempurpedicEntity, SensorEntity):
    """Reports head or leg elevation as a percentage of maximum travel."""

    entity_description: TempurpedicSensorDescription

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        entry: TempurpedicConfigEntry,
        description: TempurpedicSensorDescription,
    ) -> None:
        """Initialise position sensor."""
        super().__init__(entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    async def async_added_to_hass(self) -> None:
        """Register with runtime data so the move loop can push updates."""
        self._entry.runtime_data.position_sensors.append(self)

    async def async_will_remove_from_hass(self) -> None:
        """Deregister from runtime data."""
        sensors = self._entry.runtime_data.position_sensors
        if self in sensors:
            sensors.remove(self)

    @property
    def native_value(self) -> float | None:
        """Return position as 0-100%, or None if uncalibrated."""
        rd = self._entry.runtime_data
        if self.entity_description.zone == "head":
            ticks = rd.head_ticks
            max_ticks: int = self._entry.options.get(CONF_HEAD_MAX, DEFAULT_HEAD_MAX)
        else:
            ticks = rd.leg_ticks
            max_ticks = self._entry.options.get(CONF_LEG_MAX, DEFAULT_LEG_MAX)
        if not max_ticks:
            return None
        return round((ticks / max_ticks) * 100)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose raw tick count for calibration."""
        rd = self._entry.runtime_data
        ticks = (
            rd.head_ticks
            if self.entity_description.zone == "head"
            else rd.leg_ticks
        )
        return {"ticks": ticks}
