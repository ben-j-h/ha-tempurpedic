"""Number platform for ha_tempurpedic -- absolute vibration intensity per zone."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)

from .const import (
    COMMANDS,
    LOGGER,
    VIB_MAX_LEVEL,
    VIB_MIN_LEVEL,
    VIB_ZONE_HEAD,
    VIB_ZONE_LEGS,
    VIB_ZONE_TORSO,
    build_vib_command,
)
from .entity import TempurpedicEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import TempurpedicConfigEntry


@dataclass(frozen=True, kw_only=True)
class TempurpedicNumberDescription(NumberEntityDescription):
    """Description for a Tempurpedic vibration number entity."""

    zone: int


NUMBER_DESCRIPTIONS: tuple[TempurpedicNumberDescription, ...] = (
    TempurpedicNumberDescription(
        key="vib_head", name="Head Vibration", icon="mdi:vibrate", zone=VIB_ZONE_HEAD
    ),
    TempurpedicNumberDescription(
        key="vib_torso",
        name="Torso Vibration",
        icon="mdi:vibrate",
        zone=VIB_ZONE_TORSO,
    ),
    TempurpedicNumberDescription(
        key="vib_legs", name="Legs Vibration", icon="mdi:vibrate", zone=VIB_ZONE_LEGS
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: TempurpedicConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities from a config entry."""
    async_add_entities(
        TempurpedicVibrationNumber(entry=entry, description=desc)
        for desc in NUMBER_DESCRIPTIONS
    )


class TempurpedicVibrationNumber(TempurpedicEntity, NumberEntity):
    """Slider that sets one zone's vibration intensity absolutely (0-10)."""

    entity_description: TempurpedicNumberDescription

    _attr_native_min_value = VIB_MIN_LEVEL
    _attr_native_max_value = VIB_MAX_LEVEL
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_native_value: float = 0

    def __init__(
        self,
        entry: TempurpedicConfigEntry,
        description: TempurpedicNumberDescription,
    ) -> None:
        """Initialise vibration number entity."""
        super().__init__(entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        entry.runtime_data.vib_levels.setdefault(description.zone, 0)

    async def async_added_to_hass(self) -> None:
        """Register with runtime data so preset/off buttons can move this slider."""
        self._entry.runtime_data.vib_numbers.append(self)

    async def async_will_remove_from_hass(self) -> None:
        """Deregister from runtime data."""
        numbers = self._entry.runtime_data.vib_numbers
        if self in numbers:
            numbers.remove(self)

    def reflect_level(self, level: int) -> None:
        """Update the displayed level after a preset/off button (sends nothing)."""
        self._attr_native_value = level
        self._entry.runtime_data.vib_levels[self.entity_description.zone] = level
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Send one absolute intensity command for this zone."""
        zone = self.entity_description.zone
        target = int(max(VIB_MIN_LEVEL, min(VIB_MAX_LEVEL, value)))
        rd = self._entry.runtime_data

        self._attr_native_value = target
        rd.vib_levels[zone] = target

        client = rd.client
        ok = await self.hass.async_add_executor_job(
            client.send_command, build_vib_command(zone, target)
        )
        if not ok:
            LOGGER.warning(
                "%s: no ACK setting %s vibration to %d",
                self._entry.title,
                self.entity_description.key,
                target,
            )

        # Mirror the app: once every zone is at 0, send a full massage stop so the
        # base's motors actually spin down rather than idling at minimum.
        if target == 0 and not any(rd.vib_levels.values()):
            await self.hass.async_add_executor_job(
                client.send_command, COMMANDS["vibrate_off"]
            )

        self.async_write_ha_state()
