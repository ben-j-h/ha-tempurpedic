"""Tempurpedic adjustable base integration."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.const import Platform
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event

from .api import TempurpedicClient
from .const import (
    ACTIVITY_IDLE,
    ACTIVITY_MASSAGE,
    ACTIVITY_TILTING,
    ACTIVITY_UNKNOWN,
    COMMANDS,
    CONF_HEAD_MAX,
    CONF_HOST,
    CONF_LEG_MAX,
    CONF_PORT,
    CONF_POWER_IDLE_W,
    CONF_POWER_SENSOR,
    CONF_POWER_TILT_W,
    DEFAULT_PORT,
    DEFAULT_POWER_IDLE_W,
    DEFAULT_POWER_TILT_W,
    DOMAIN,
    LOGGER,
)
from .data import TempurpedicData
from .discovery import async_start_discovery

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import Event, HomeAssistant, ServiceCall
    from homeassistant.helpers.typing import ConfigType

    from .data import TempurpedicConfigEntry

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SENSOR,
]

_UNAVAILABLE_STATES = ("unknown", "unavailable", "", "none")

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(
    hass: HomeAssistant,
    config: ConfigType,  # noqa: ARG001
) -> bool:
    """Start passive UDP discovery of bases on the network."""
    await async_start_discovery(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TempurpedicConfigEntry,
) -> bool:
    """Set up Tempurpedic from a config entry."""
    client = TempurpedicClient(
        host=entry.data[CONF_HOST],
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
    )
    entry.runtime_data = TempurpedicData(client=client)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.runtime_data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if not hass.services.has_service(DOMAIN, "start_move"):
        _async_register_services(hass)

    power_sensor = entry.options.get(CONF_POWER_SENSOR)
    if power_sensor:
        entry.async_on_unload(
            async_track_state_change_event(
                hass, [power_sensor], _make_power_handler(entry)
            )
        )

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    return True


def _make_power_handler(
    entry: TempurpedicConfigEntry,
) -> Callable[[Event], None]:
    """Build the plug-power state listener for one config entry."""

    @callback
    def _handle(event: Event) -> None:
        rd = entry.runtime_data
        new = event.data.get("new_state")
        if new is None or str(new.state).lower() in _UNAVAILABLE_STATES:
            rd.power_w = None
            rd.activity = ACTIVITY_UNKNOWN
        else:
            try:
                watts = float(new.state)
            except (TypeError, ValueError):
                return
            idle_w = float(entry.options.get(CONF_POWER_IDLE_W, DEFAULT_POWER_IDLE_W))
            tilt_w = float(entry.options.get(CONF_POWER_TILT_W, DEFAULT_POWER_TILT_W))
            rd.power_w = watts
            if watts >= tilt_w:
                rd.activity = ACTIVITY_TILTING
            elif watts > idle_w:
                rd.activity = ACTIVITY_MASSAGE
            else:
                rd.activity = ACTIVITY_IDLE

            moving_by_us = rd.move_task is not None and not rd.move_task.done()
            if rd.activity == ACTIVITY_TILTING and not moving_by_us:
                # Someone used the wall remote / another app -- our tick count is
                # now meaningless until the next Flat.
                rd.position_trusted = False

        for ent in (*rd.position_sensors, *rd.binary_sensors):
            ent.async_write_ha_state()

    return _handle


async def async_unload_entry(
    hass: HomeAssistant,
    entry: TempurpedicConfigEntry,
) -> bool:
    """Unload a config entry."""
    entry_data = hass.data[DOMAIN].pop(entry.entry_id, None)
    if entry_data and entry_data.move_task and not entry_data.move_task.done():
        entry_data.move_task.cancel()

    if not hass.data[DOMAIN]:
        hass.services.async_remove(DOMAIN, "start_move")
        hass.services.async_remove(DOMAIN, "stop_move")

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(
    hass: HomeAssistant,
    entry: TempurpedicConfigEntry,
) -> None:
    """Reload so calibration and the power-sensor subscription re-apply."""
    await hass.config_entries.async_reload(entry.entry_id)


def _async_register_services(hass: HomeAssistant) -> None:
    async def handle_start_move(call: ServiceCall) -> None:
        entity_id: str = call.data["entity_id"]
        ent_reg = er.async_get(hass)
        entity_entry = ent_reg.async_get(entity_id)
        if not entity_entry or not entity_entry.config_entry_id:
            LOGGER.warning("start_move: unknown entity %s", entity_id)
            return

        entry_id = entity_entry.config_entry_id
        entry_data = hass.data[DOMAIN].get(entry_id)
        if not entry_data:
            return

        # Holding a direction is manual movement -> clear the position preset.
        if entry_data.preset_number is not None:
            entry_data.preset_number.reflect_value(0)
        # We are the one moving it now, so the estimate is meaningful again.
        entry_data.position_trusted = True

        # unique_id format: "{entry_id}_{command_key}"
        command_key = entity_entry.unique_id[len(entry_id) + 1 :]
        command = COMMANDS.get(command_key)
        if not command:
            LOGGER.warning("start_move: no command for key %s", command_key)
            return

        if entry_data.move_task and not entry_data.move_task.done():
            entry_data.move_task.cancel()

        async def move_loop() -> None:
            while True:
                await hass.async_add_executor_job(
                    entry_data.client.send_command, command
                )
                ce = hass.config_entries.async_get_entry(entry_id)
                opts = ce.options if ce else {}
                head_max: int = opts.get(CONF_HEAD_MAX, 0)
                leg_max: int = opts.get(CONF_LEG_MAX, 0)

                # If a power sensor says the motor has stopped (hit its limit),
                # don't keep counting ticks for commands the bed is ignoring.
                counting = (
                    not opts.get(CONF_POWER_SENSOR)
                    or entry_data.activity != ACTIVITY_IDLE
                )
                if counting and command_key == "head_up":
                    entry_data.head_ticks = min(
                        entry_data.head_ticks + 1,
                        head_max if head_max else 999_999,
                    )
                elif counting and command_key == "head_down":
                    entry_data.head_ticks = max(entry_data.head_ticks - 1, 0)
                elif counting and command_key == "legs_up":
                    entry_data.leg_ticks = min(
                        entry_data.leg_ticks + 1,
                        leg_max if leg_max else 999_999,
                    )
                elif counting and command_key == "legs_down":
                    entry_data.leg_ticks = max(entry_data.leg_ticks - 1, 0)

                for sensor in entry_data.position_sensors:
                    sensor.async_write_ha_state()

                await asyncio.sleep(0)

        entry_data.move_task = hass.async_create_task(move_loop())

    async def handle_stop_move(_call: ServiceCall) -> None:
        for entry_data in hass.data[DOMAIN].values():
            if entry_data.move_task and not entry_data.move_task.done():
                entry_data.move_task.cancel()
                entry_data.move_task = None

    hass.services.async_register(
        DOMAIN,
        "start_move",
        handle_start_move,
        schema=vol.Schema({vol.Required("entity_id"): cv.entity_id}),
    )
    hass.services.async_register(
        DOMAIN,
        "stop_move",
        handle_stop_move,
        schema=vol.Schema({}),
    )
