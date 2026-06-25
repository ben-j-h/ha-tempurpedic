"""Button platform for ha_tempurpedic."""

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
    direct: bool = False  # single send (no LOGICDATAOPEN) — vibration commands only


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
    TempurpedicButtonDescription(
        key="preset_1",
        name="Position Preset 1",
        icon="mdi:numeric-1-box",
        command_key="preset_1",
    ),
    TempurpedicButtonDescription(
        key="preset_2",
        name="Position Preset 2",
        icon="mdi:numeric-2-box",
        command_key="preset_2",
    ),
    TempurpedicButtonDescription(
        key="preset_3",
        name="Position Preset 3",
        icon="mdi:numeric-3-box",
        command_key="preset_3",
    ),
    TempurpedicButtonDescription(
        key="preset_4",
        name="Position Preset 4",
        icon="mdi:numeric-4-box",
        command_key="preset_4",
    ),
    TempurpedicButtonDescription(
        key="vibrate_off",
        name="Vibration Off",
        icon="mdi:vibrate-off",
        command_key="vibrate_off",
        direct=True,
    ),
    TempurpedicButtonDescription(
        key="vibrate_1",
        name="Vibration Preset 1",
        icon="mdi:vibrate",
        command_key="vibrate_1",
        direct=True,
    ),
    TempurpedicButtonDescription(
        key="vibrate_2",
        name="Vibration Preset 2",
        icon="mdi:vibrate",
        command_key="vibrate_2",
        direct=True,
    ),
    TempurpedicButtonDescription(
        key="vibrate_3",
        name="Vibration Preset 3",
        icon="mdi:vibrate",
        command_key="vibrate_3",
        direct=True,
    ),
    TempurpedicButtonDescription(
        key="vibrate_4",
        name="Vibration Preset 4",
        icon="mdi:vibrate",
        command_key="vibrate_4",
        direct=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: TempurpedicConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities from a config entry."""
    async_add_entities(
        TempurpedicButton(entry=entry, description=desc)
        for desc in BUTTON_DESCRIPTIONS
    )


class TempurpedicButton(TempurpedicEntity, ButtonEntity):
    """A button that sends one command to the bed."""

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
        client = self._entry.runtime_data.client
        cmd = COMMANDS[self.entity_description.command_key]
        send = (
            client.send_command_direct
            if self.entity_description.direct
            else client.send_command
        )
        ok = await self.hass.async_add_executor_job(send, cmd)
        if not ok:
            if self.entity_description.hold:
                LOGGER.debug(
                    "%s: no ACK for %s (hold-overlap, bed likely moving)",
                    self._entry.title,
                    self.entity_description.key,
                )
            else:
                LOGGER.warning(
                    "%s: no ACK for %s command",
                    self._entry.title,
                    self.entity_description.key,
                )
