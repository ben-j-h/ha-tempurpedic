"""Config flow for ha_tempurpedic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .api import TempurpedicClient
from .const import (
    CONF_DEVICE_ID,
    CONF_HEAD_MAX,
    CONF_HOST,
    CONF_HOSTNAME,
    CONF_LEG_MAX,
    CONF_NAME,
    CONF_PORT,
    CONF_POWER_IDLE_W,
    CONF_POWER_SENSOR,
    CONF_POWER_TILT_W,
    DEFAULT_HEAD_MAX,
    DEFAULT_LEG_MAX,
    DEFAULT_PORT,
    DEFAULT_POWER_IDLE_W,
    DEFAULT_POWER_TILT_W,
    DOMAIN,
    LOGGER,
)

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult
    from homeassistant.helpers.typing import DiscoveryInfoType

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

    def __init__(self) -> None:
        """Hold discovery details between steps."""
        self._discovered: dict[str, Any] = {}

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

    async def async_step_integration_discovery(
        self,
        discovery_info: DiscoveryInfoType,
    ) -> FlowResult:
        """Handle a base found via its UDP identity beacon."""
        device_id: str = discovery_info[CONF_DEVICE_ID]
        host: str = discovery_info[CONF_HOST]

        await self.async_set_unique_id(device_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})

        # Adopt an entry that was added manually before discovery existed.
        for entry in self._async_current_entries():
            if entry.data.get(CONF_HOST) == host:
                if entry.unique_id is None:
                    self.hass.config_entries.async_update_entry(
                        entry, unique_id=device_id
                    )
                return self.async_abort(reason="already_configured")

        self._discovered = dict(discovery_info)
        self.context["title_placeholders"] = {"name": self._discovered_name()}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Let the user name a discovered base and confirm adding it."""
        host: str = self._discovered[CONF_HOST]

        if user_input is not None:
            client = TempurpedicClient(host=host, port=DEFAULT_PORT)
            reachable = await self.hass.async_add_executor_job(client.test_connection)
            if not reachable:
                return self.async_abort(reason="cannot_connect")
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_HOST: host,
                    CONF_PORT: DEFAULT_PORT,
                },
            )

        return self.async_show_form(
            step_id="discovery_confirm",
            data_schema=vol.Schema(
                {vol.Required(CONF_NAME, default=self._discovered_name()): str}
            ),
            description_placeholders={
                "host": host,
                "device_id": self._discovered[CONF_DEVICE_ID],
            },
        )

    def _discovered_name(self) -> str:
        """Best-effort friendly name for a discovered base."""
        hostname: str = (self._discovered.get(CONF_HOSTNAME) or "").strip()
        if hostname:
            return hostname
        return f"TEMPUR-Ergo {self._discovered[CONF_DEVICE_ID][-6:]}"


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

        power_sensor_key = (
            vol.Optional(CONF_POWER_SENSOR, default=current[CONF_POWER_SENSOR])
            if current.get(CONF_POWER_SENSOR)
            else vol.Optional(CONF_POWER_SENSOR)
        )

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
                power_sensor_key: selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="power")
                ),
                vol.Optional(
                    CONF_POWER_IDLE_W,
                    default=current.get(CONF_POWER_IDLE_W, DEFAULT_POWER_IDLE_W),
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_POWER_TILT_W,
                    default=current.get(CONF_POWER_TILT_W, DEFAULT_POWER_TILT_W),
                ): vol.Coerce(float),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
