"""Config flow for ha_tempurpedic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries

from .api import TempurpedicClient
from .const import CONF_HOST, CONF_NAME, CONF_PORT, DEFAULT_PORT, DOMAIN, LOGGER

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
