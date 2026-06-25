"""Constants for ha_tempurpedic."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "ha_tempurpedic"
CONF_NAME = "name"
CONF_HOST = "host"
CONF_PORT = "port"
DEFAULT_PORT = 50007

CONF_HEAD_MAX = "head_max_ticks"
CONF_LEG_MAX = "leg_max_ticks"
DEFAULT_HEAD_MAX = 40
DEFAULT_LEG_MAX = 40

LOGICDATAOPEN = b"\xfeLOGICDATAOPEN"

COMMANDS: dict[str, bytes] = {
    "flat":         bytes.fromhex("3305320a945c0400cc"),
    "head_up":      bytes.fromhex("3305321894530005c2"),
    "head_down":    bytes.fromhex("3305321894540005c5"),
    "legs_up":      bytes.fromhex("3305321894510100c4"),
    "legs_down":    bytes.fromhex("3305321894520100c7"),
    "preset_1":     bytes.fromhex("33053203945c0000c8"),
    "preset_2":     bytes.fromhex("33053203945c0100c9"),
    "preset_3":     bytes.fromhex("33053203945c0200ca"),
    "preset_4":     bytes.fromhex("33053203945c0300cb"),
    "vibrate_off":  bytes.fromhex("3305320a9486000012"),
    "vibrate_1":    bytes.fromhex("33053203948d007861"),
    "vibrate_2":    bytes.fromhex("33053203948d017860"),
    "vibrate_3":    bytes.fromhex("33053203948d027863"),
    "vibrate_4":    bytes.fromhex("33053203948d037862"),
}

# Vibration intensity levels (10 steps, mapped from 1-10)
# Checksum = bytes[4] XOR bytes[5] XOR bytes[6] XOR bytes[7]
VIB_LEVELS = [0x18, 0x30, 0x48, 0x60, 0x78, 0x90, 0xA8, 0xC0, 0xD8, 0xF0]
VIB_ZONE_HEAD  = 0x00
VIB_ZONE_TORSO = 0x01
VIB_ZONE_LEGS  = 0x02


def build_vib_command(zone: int, level: int) -> bytes:
    """
    Build a 9-byte vibration intensity command.

    zone: VIB_ZONE_HEAD / TORSO / LEGS
    level: 1-10
    """
    level_byte = VIB_LEVELS[max(0, min(9, level - 1))]
    checksum = 0x94 ^ 0x85 ^ zone ^ level_byte
    return bytes([0x33, 0x05, 0x32, 0x03, 0x94, 0x85, zone, level_byte, checksum])
