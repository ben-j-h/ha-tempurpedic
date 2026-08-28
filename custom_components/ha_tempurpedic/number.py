"""
Number platform for ha_tempurpedic.

Vibration and the two "preset" concepts are all modelled as values rather than
piles of buttons:

* three zone sliders  -- ``vib_head`` / ``vib_torso`` / ``vib_legs`` (0..10)
* one massage program -- ``massage_program`` (0 = off, 1..4 = built-in programs)
* one position preset -- ``position_preset`` (0 = none, 1..4 = recall memory pos)

Setting any of them sends the matching command. Manual vibration input clears the
massage program; manual bed movement clears the position preset.
"""

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
    MASSAGE_PROGRAM_LEVEL,
    MASSAGE_PROGRAM_MAX,
    MASSAGE_PROGRAM_MIN,
    POSITION_PRESET_MAX,
    POSITION_PRESET_MIN,
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
    """Description for a Tempurpedic vibration-zone number entity."""

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
    entities: list[NumberEntity] = [
        TempurpedicVibrationNumber(entry=entry, description=desc)
        for desc in NUMBER_DESCRIPTIONS
    ]
    entities.append(TempurpedicMassageProgramNumber(entry))
    entities.append(TempurpedicPositionPresetNumber(entry))
    async_add_entities(entities)


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
        """Register so the program entity can move this slider."""
        self._entry.runtime_data.vib_numbers.append(self)

    async def async_will_remove_from_hass(self) -> None:
        """Deregister from runtime data."""
        numbers = self._entry.runtime_data.vib_numbers
        if self in numbers:
            numbers.remove(self)

    def reflect_level(self, level: int) -> None:
        """Update the displayed level without sending anything."""
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

        # All zones at 0 -> full stop, like the app.
        if target == 0 and not any(rd.vib_levels.values()):
            await self.hass.async_add_executor_job(
                client.send_command, COMMANDS["vibrate_off"]
            )

        # Manual intensity input drops any running program.
        if rd.program_number is not None:
            rd.program_number.reflect_value(0)

        self.async_write_ha_state()


class TempurpedicMassageProgramNumber(TempurpedicEntity, NumberEntity):
    """Which built-in massage program is running: 0 = off, 1-4 = program."""

    _attr_name = "Massage Program"
    _attr_icon = "mdi:sine-wave"
    _attr_native_min_value = MASSAGE_PROGRAM_MIN
    _attr_native_max_value = MASSAGE_PROGRAM_MAX
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_native_value: float = 0

    def __init__(self, entry: TempurpedicConfigEntry) -> None:
        """Initialise massage-program entity."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_massage_program"

    async def async_added_to_hass(self) -> None:
        """Register so vibration input can reset this."""
        self._entry.runtime_data.program_number = self

    async def async_will_remove_from_hass(self) -> None:
        """Deregister from runtime data."""
        if self._entry.runtime_data.program_number is self:
            self._entry.runtime_data.program_number = None

    def reflect_value(self, value: int) -> None:
        """Update the displayed program without sending anything."""
        self._attr_native_value = value
        self._entry.runtime_data.massage_program = value
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Start a program (1-4) or stop massage (0)."""
        target = int(max(MASSAGE_PROGRAM_MIN, min(MASSAGE_PROGRAM_MAX, value)))
        rd = self._entry.runtime_data

        self._attr_native_value = target
        rd.massage_program = target

        cmd = COMMANDS["vibrate_off"] if target == 0 else COMMANDS[f"vibrate_{target}"]
        ok = await self.hass.async_add_executor_job(rd.client.send_command, cmd)
        if not ok:
            LOGGER.warning(
                "%s: no ACK setting massage program to %d", self._entry.title, target
            )

        # Mirror the app: off clears the zone sliders, a program parks them at 5.
        level = 0 if target == 0 else MASSAGE_PROGRAM_LEVEL
        for number in rd.vib_numbers:
            number.reflect_level(level)

        self.async_write_ha_state()


class TempurpedicPositionPresetNumber(TempurpedicEntity, NumberEntity):
    """Which memory position is active: 0 = none, 1-4 = recall that preset."""

    _attr_name = "Position Preset"
    _attr_icon = "mdi:bed"
    _attr_native_min_value = POSITION_PRESET_MIN
    _attr_native_max_value = POSITION_PRESET_MAX
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_native_value: float = 0

    def __init__(self, entry: TempurpedicConfigEntry) -> None:
        """Initialise position-preset entity."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_position_preset"

    async def async_added_to_hass(self) -> None:
        """Register so bed movement can reset this."""
        self._entry.runtime_data.preset_number = self

    async def async_will_remove_from_hass(self) -> None:
        """Deregister from runtime data."""
        if self._entry.runtime_data.preset_number is self:
            self._entry.runtime_data.preset_number = None

    def reflect_value(self, value: int) -> None:
        """Update the displayed preset without sending anything."""
        self._attr_native_value = value
        self._entry.runtime_data.position_preset = value
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Recall memory position 1-4; 0 just clears the indicator."""
        target = int(max(POSITION_PRESET_MIN, min(POSITION_PRESET_MAX, value)))
        rd = self._entry.runtime_data

        self._attr_native_value = target
        rd.position_preset = target

        if target >= 1:
            ok = await self.hass.async_add_executor_job(
                rd.client.send_command, COMMANDS[f"preset_{target}"]
            )
            if not ok:
                LOGGER.warning(
                    "%s: no ACK recalling position preset %d",
                    self._entry.title,
                    target,
                )

        self.async_write_ha_state()
