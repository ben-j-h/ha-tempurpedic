"""
Button platform for ha_tempurpedic -- momentary bed-movement actions only.

Position presets and massage programs are number entities now (see number.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription

from .const import COMMANDS, LOGGER
from .entity import TempurpedicEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import TempurpedicConfigEntry


@dataclass(frozen=True, kw_only=True)
class TempurpedicButtonDescription(ButtonEntityDescription):
    """Description for a Tempurpedic button entity."""

    command_key: str
    hold: bool = False


BUTTON_DESCRIPTIONS: tuple[TempurpedicButtonDescription, ...] = (
    TempurpedicButtonDescription(
        key="flat", name="Flat", icon="mdi:bed-empty", command_key="flat"
    ),
    TempurpedicButtonDescription(
        key="head_up",
        name="Head Up",
        icon="mdi:arrow-up-bold",
        command_key="head_up",
        hold=True,
    ),
    TempurpedicButtonDescription(
        key="head_down",
        name="Head Down",
        icon="mdi:arrow-down-bold",
        command_key="head_down",
        hold=True,
    ),
    TempurpedicButtonDescription(
        key="legs_up",
        name="Legs Up",
        icon="mdi:arrow-up-bold",
        command_key="legs_up",
        hold=True,
    ),
    TempurpedicButtonDescription(
        key="legs_down",
        name="Legs Down",
        icon="mdi:arrow-down-bold",
        command_key="legs_down",
        hold=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: TempurpedicConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities from a config entry."""
    async_add_entities(
        TempurpedicButton(entry=entry, description=desc) for desc in BUTTON_DESCRIPTIONS
    )


class TempurpedicButton(TempurpedicEntity, ButtonEntity):
    """A button that sends one movement command to the bed."""

    entity_description: TempurpedicButtonDescription

    def __init__(
        self,
        entry: TempurpedicConfigEntry,
        description: TempurpedicButtonDescription,
    ) -> None:
        """Initialise button entity."""
        super().__init__(entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    async def async_press(self) -> None:
        """Send the command to the bed."""
        rd = self._entry.runtime_data
        key = self.entity_description.key

        # Flat is the hard sync point: cancel movement and reset position state.
        if key == "flat":
            if rd.move_task and not rd.move_task.done():
                rd.move_task.cancel()
                rd.move_task = None
            rd.head_ticks = 0
            rd.leg_ticks = 0
            rd.position_trusted = True
            for sensor in rd.position_sensors:
                sensor.async_write_ha_state()

        cmd = COMMANDS[self.entity_description.command_key]
        ok = await self.hass.async_add_executor_job(rd.client.send_command, cmd)
        if not ok:
            if self.entity_description.hold:
                LOGGER.debug(
                    "%s: no ACK for %s (hold-overlap, bed likely moving)",
                    self._entry.title,
                    key,
                )
            else:
                LOGGER.warning("%s: no ACK for %s command", self._entry.title, key)

        # Any manual movement clears the active position preset.
        if rd.preset_number is not None:
            rd.preset_number.reflect_value(0)
