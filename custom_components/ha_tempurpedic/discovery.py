"""
Passive UDP beacon discovery for the TEMPUR-Ergo base.

The base's WiFi module broadcasts a 111-byte identity beacon on
``DISCOVERY_PORT``. We bind that port, parse the device id / hostname out of the
fixed offsets the vendor app uses, and hand the sender's IP to a config-flow
discovery step. Nothing is ever sent.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback

from .const import (
    CONF_DEVICE_ID,
    CONF_HOSTNAME,
    DISCOVERY_PACKET_LEN,
    DISCOVERY_PORT,
    DOMAIN,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

_DISCOVERY_KEY = f"{DOMAIN}_discovery_transport"

# Byte offsets within the beacon (from the vendor app's DiscoverModulesTask).
_ID_START = 60
_ID_END = 92


def parse_beacon(data: bytes) -> tuple[str, str] | None:
    """Return ``(device_id, hostname)`` for a valid beacon, else ``None``."""
    if len(data) < DISCOVERY_PACKET_LEN:
        return None
    blob = data[_ID_START:_ID_END].decode("ascii", "ignore")
    if blob.startswith("TEMPUR_"):
        device_id, hostname = blob[:13], blob[13:]
    elif blob.startswith("WM"):
        device_id, hostname = blob[:10], blob[10:]
    else:
        return None
    device_id = device_id.strip(" \x00")
    hostname = hostname.strip(" \x00")
    if not device_id:
        return None
    return device_id, hostname


class _BeaconProtocol(asyncio.DatagramProtocol):
    """Fires a discovery flow the first time each base is heard."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._seen: set[str] = set()

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        parsed = parse_beacon(data)
        if parsed is None:
            return
        device_id, hostname = parsed
        host = addr[0]
        key = f"{device_id}@{host}"
        if key in self._seen:
            return
        self._seen.add(key)
        _LOGGER.debug(
            "Discovered TEMPUR-Ergo %s (%s) at %s", device_id, hostname or "?", host
        )
        self._hass.async_create_task(
            self._hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_INTEGRATION_DISCOVERY},
                data={
                    CONF_HOST: host,
                    CONF_DEVICE_ID: device_id,
                    CONF_HOSTNAME: hostname,
                },
            ),
            f"{DOMAIN}_discovery_{device_id}",
        )


async def async_start_discovery(hass: HomeAssistant) -> None:
    """Bind the beacon listener once for this Home Assistant instance."""
    if hass.data.get(_DISCOVERY_KEY) is not None:
        return

    loop = asyncio.get_running_loop()
    try:
        transport, _ = await loop.create_datagram_endpoint(
            lambda: _BeaconProtocol(hass),
            local_addr=("0.0.0.0", DISCOVERY_PORT),  # noqa: S104 -- must catch broadcasts
        )
    except OSError as err:
        _LOGGER.debug(
            "TEMPUR-Ergo beacon listener not started (port %s): %s",
            DISCOVERY_PORT,
            err,
        )
        return

    hass.data[_DISCOVERY_KEY] = transport

    @callback
    def _stop(_event: object) -> None:
        transport.close()
        hass.data.pop(_DISCOVERY_KEY, None)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop)
