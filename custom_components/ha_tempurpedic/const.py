"""Constants for ha_tempurpedic."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "ha_tempurpedic"
CONF_NAME = "name"
CONF_HOST = "host"
CONF_PORT = "port"
DEFAULT_PORT = 50007

# The base periodically broadcasts a 111-byte identity beacon on this UDP port.
DISCOVERY_PORT = 55555
DISCOVERY_PACKET_LEN = 111
CONF_DEVICE_ID = "device_id"
CONF_HOSTNAME = "hostname"

CONF_HEAD_MAX = "head_max_ticks"
CONF_LEG_MAX = "leg_max_ticks"
DEFAULT_HEAD_MAX = 40
DEFAULT_LEG_MAX = 40

LOGICDATAOPEN = b"\xfeLOGICDATAOPEN"
KILL_AUTOSEND = b"\x34"  # halt the base's internal motor auto-repeat; expects "ACK4"

# Response prefix the base returns for an accepted LOGICDATA-framed command.
ACK_OK = b"ACK3"

VIB_MIN_LEVEL = 0
VIB_MAX_LEVEL = 10

# Massage program: 0 = off, 1..4 = the base's four built-in programs.
MASSAGE_PROGRAM_MIN = 0
MASSAGE_PROGRAM_MAX = 4
# Each zone slider parks here when a program is running (matches the app).
MASSAGE_PROGRAM_LEVEL = 5

# Position preset: 0 = none selected, 1..4 = recall memory position.
POSITION_PRESET_MIN = 0
POSITION_PRESET_MAX = 4

COMMANDS: dict[str, bytes] = {
    "flat": bytes.fromhex("3305320a945c0400cc"),
    "head_up": bytes.fromhex("3305321894530005c2"),
    "head_down": bytes.fromhex("3305321894540005c5"),
    "legs_up": bytes.fromhex("3305321894510100c4"),
    "legs_down": bytes.fromhex("3305321894520100c7"),
    "preset_1": bytes.fromhex("33053203945c0000c8"),
    "preset_2": bytes.fromhex("33053203945c0100c9"),
    "preset_3": bytes.fromhex("33053203945c0200ca"),
    "preset_4": bytes.fromhex("33053203945c0300cb"),
    "vibrate_off": bytes.fromhex("3305320a9486000012"),
    "vibrate_1": bytes.fromhex("33053203948d007861"),
    "vibrate_2": bytes.fromhex("33053203948d017860"),
    "vibrate_3": bytes.fromhex("33053203948d027863"),
    "vibrate_4": bytes.fromhex("33053203948d037862"),
}

VIB_ZONE_HEAD = 0x00
VIB_ZONE_TORSO = 0x01
VIB_ZONE_LEGS = 0x02


def build_vib_command(zone: int, level: int) -> bytes:
    """
    Build a 9-byte absolute vibration-intensity command (app's ManualMassageCommand).

    zone:  VIB_ZONE_HEAD / TORSO / LEGS
    level: 0 (off) .. 10 (max); the wire byte is level * 24 (0x00, 0x18 .. 0xF0)
    checksum = bytes[4] XOR bytes[5] XOR bytes[6] XOR bytes[7]
    """
    level = max(VIB_MIN_LEVEL, min(VIB_MAX_LEVEL, level))
    level_byte = level * 24
    checksum = 0x94 ^ 0x85 ^ zone ^ level_byte
    return bytes([0x33, 0x05, 0x32, 0x03, 0x94, 0x85, zone, level_byte, checksum])
