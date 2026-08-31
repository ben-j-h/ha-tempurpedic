"""
Binary sensors for ha_tempurpedic.

Both work off what the integration commanded; when a ``power_sensor`` is
configured they also fold in what the bed's plug is actually drawing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)

from .const import ACTIVITY_MASSAGE, ACTIVITY_TILTING
from .entity import TempurpedicEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import TempurpedicConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: TempurpedicConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors from a config entry."""
    async_add_entities(
        [
            TempurpedicMovingBinarySensor(entry),
            TempurpedicMassageBinarySensor(entry),
        ]
    )


class _Base(TempurpedicEntity, BinarySensorEntity):
    """Shared registration with runtime data."""

    def __init__(self, entry: TempurpedicConfigEntry, key: str) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_{key}"

    async def async_added_to_hass(self) -> None:
        """Register so the power watcher can push updates."""
        self._entry.runtime_data.binary_sensors.append(self)

    async def async_will_remove_from_hass(self) -> None:
        """Deregister from runtime data."""
        sensors = self._entry.runtime_data.binary_sensors
        if self in sensors:
            sensors.remove(self)


class TempurpedicMovingBinarySensor(_Base):
    """On while a lift motor is running."""

    _attr_name = "Moving"
    _attr_device_class = BinarySensorDeviceClass.MOVING

    def __init__(self, entry: TempurpedicConfigEntry) -> None:
        """Initialise the moving binary sensor."""
        super().__init__(entry, "moving")

    @property
    def is_on(self) -> bool:
        """True if we're driving a move, or the plug shows a tilt-level draw."""
        rd = self._entry.runtime_data
        by_us = rd.move_task is not None and not rd.move_task.done()
        return by_us or rd.activity == ACTIVITY_TILTING

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the raw power reading and classification for tuning."""
        rd = self._entry.runtime_data
        return {
            "power_w": rd.power_w,
            "activity": rd.activity,
            "position_trusted": rd.position_trusted,
        }


class TempurpedicMassageBinarySensor(_Base):
    """On while vibration is commanded, or the plug shows a massage-level draw."""

    _attr_name = "Massage Active"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, entry: TempurpedicConfigEntry) -> None:
        """Initialise the massage binary sensor."""
        super().__init__(entry, "massage_active")

    @property
    def is_on(self) -> bool:
        """True from commanded state or a massage-band power draw."""
        rd = self._entry.runtime_data
        commanded = rd.massage_program != 0 or any(rd.vib_levels.values())
        return commanded or rd.activity == ACTIVITY_MASSAGE
