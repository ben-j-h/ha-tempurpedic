"""Config flow for ha_tempurpedic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .api import TempurpedicClient
from .const import (
    CONF_HEAD_MAX,
    CONF_HOST,
    CONF_LEG_MAX,
    CONF_NAME,
    CONF_PORT,
    DEFAULT_HEAD_MAX,
    DEFAULT_LEG_MAX,
    DEFAULT_PORT,
    DOMAIN,
    LOGGER,
)

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult

STEP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


class TempurpedicFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Tempurpedic adjustable base."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,  # noqa: ARG004
    ) -> TempurpedicOptionsFlow:
        """Create options flow."""
        return TempurpedicOptionsFlow()

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle the initial configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            client = TempurpedicClient(
                host=user_input[CONF_HOST],
                port=user_input.get(CONF_PORT, DEFAULT_PORT),
            )
            reachable = await self.hass.async_add_executor_job(client.test_connection)
            if reachable:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
            LOGGER.warning("Could not reach bed at %s", user_input[CONF_HOST])
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_SCHEMA,
            errors=errors,
        )


class TempurpedicOptionsFlow(config_entries.OptionsFlow):
    """Options flow for calibrating position max ticks."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle options step."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_HEAD_MAX,
                    default=current.get(CONF_HEAD_MAX, DEFAULT_HEAD_MAX),
                ): int,
                vol.Optional(
                    CONF_LEG_MAX,
                    default=current.get(CONF_LEG_MAX, DEFAULT_LEG_MAX),
                ): int,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
