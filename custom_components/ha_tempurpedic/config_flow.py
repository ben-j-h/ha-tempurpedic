"""Config flow for ha_tempurpedic."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .api import TempurpedicClient
from .const import CONF_HOST, CONF_PORT, DEFAULT_PORT, DOMAIN, LOGGER

STEP_SCHEMA = vol.Schema(
    {
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
        errors: dict[str, str] = {}

        if user_input is not None:
            client = TempurpedicClient(
                host=user_input[CONF_HOST],
                port=user_input.get(CONF_PORT, DEFAULT_PORT),
            )
            reachable = await self.hass.async_add_executor_job(client.test_connection)
            if reachable:
                title = f"Tempurpedic ({user_input[CONF_HOST]})"
                return self.async_create_entry(title=title, data=user_input)
            LOGGER.warning("Could not reach bed at %s", user_input[CONF_HOST])
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_SCHEMA,
            errors=errors,
        )
