# TEMPUR-Ergo Adjustable Base — Home Assistant Integration

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

Control your TEMPUR-Ergo adjustable base directly from Home Assistant over your local WiFi network. No cloud, no account — pure UDP to the bed's built-in WiFi module.

![icon](icon.png)

## Features

- **Position control** — Head up/down, legs up/down, flat, and a memory-preset value (0–4)
- **Absolute massage control** — Per-zone vibration intensity values (head, lumbar, legs) that jump straight to the requested level, plus a single massage-program value (0 = off, 1–4 = the bed's built-in programs)
- **Hold-to-move** — The integration sends a movement command in a loop while a direction is held
- **Position estimate** — Head/leg position sensors (0–100%) derived from hold-to-move tick counting, once calibrated
- **Auto-discovery** — Bases that are visible on the local network are found automatically
- **Split-king support** — Add the integration twice (once per side) for independent left/right control
- **Fully local** — All commands go directly to the bed over UDP port 50007; no Tempur-Pedic account or internet connection required

## Prerequisites

- TEMPUR-Ergo adjustable base connected to your WiFi network
- Home Assistant able to reach the bed's IP address on UDP port 50007
- Home Assistant 2024.9.3 or newer

## Installation

### HACS (recommended)

1. In HACS, go to **Integrations** → ⋮ → **Custom repositories**
2. Add `https://github.com/ben-j-h/ha-tempurpedic` → category: **Integration**
3. Install **Tempurpedic Adjustable Base Control**
4. Restart Home Assistant

### Manual

1. Copy the `custom_components/ha_tempurpedic/` directory into your HA `config/custom_components/` folder
2. Restart Home Assistant

## Configuration

### Automatic discovery

The bed's WiFi module broadcasts an identity beacon on the local network. If
Home Assistant can see that broadcast (host networking, or the same L2 segment),
a **Discovered** card appears under **Settings → Devices & Services** — just give
the side a name and confirm. Split-king beds are discovered once per side.

### Manual

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Tempurpedic Adjustable Base**
3. Enter:
   - **Device Name** — a friendly label, e.g. `Master Bedroom Left`. This becomes the device name and drives entity IDs.
   - **IP Address** — the bed's local IP (find it in your router's DHCP table; recommend setting a static lease)
   - **UDP Port** — default `50007`, leave as-is unless you have a reason to change it

Either way the integration tests connectivity on setup — if the bed doesn't
respond, setup fails with a "cannot connect" error. Discovery also refreshes the
stored IP automatically if the bed's address changes.

## Entities

Each configured side creates the following entities:

### Buttons

| Entity | Description |
|---|---|
| `button.{name}_flat` | Move to flat position |
| `button.{name}_head_up` | Head up (use via card hold or `start_move` service) |
| `button.{name}_head_down` | Head down |
| `button.{name}_legs_up` | Legs up |
| `button.{name}_legs_down` | Legs down |

Only momentary movement actions are buttons. Recalling a position and starting a
massage program are **values** — see below.

### Numbers

Every massage/preset control is a value: set it and the matching command is
sent. No banks of buttons.

| Entity | Range | Description |
|---|---|---|
| `number.{name}_vib_head` | 0–10 | Head zone vibration intensity, absolute (no ramp) |
| `number.{name}_vib_torso` | 0–10 | Lumbar zone vibration intensity |
| `number.{name}_vib_legs` | 0–10 | Leg zone vibration intensity |
| `number.{name}_massage_program` | 0–4 | `0` = massage off, `1`–`4` = the bed's built-in programs |
| `number.{name}_position_preset` | 0–4 | `0` = none, `1`–`4` = recall that memory position |

Cross-resets, matching the app:

- All three `vib_*` zones at `0` → a full massage-stop is sent.
- Setting `massage_program` to `1`–`4` parks the `vib_*` values at `5`; `0` clears them.
- Changing any `vib_*` value clears `massage_program` back to `0`.
- Any manual bed movement (a movement button or `start_move`) clears `position_preset` back to `0`. Recalling a preset does **not** clear it — it stays on the recalled number.

### Sensors

| Entity | Description |
|---|---|
| `sensor.{name}_head_position` | Estimated head elevation, 0–100% |
| `sensor.{name}_leg_position` | Estimated leg elevation, 0–100% |

Position is inferred by counting how long each section is driven during
hold-to-move, so it drifts and is reset to 0 by **Flat**. It is only an
estimate — the bed reports nothing back.

## Calibration

Both sensors default to a **full-travel count of 40 ticks**, measured on a real
unit and believed to be standard for the TEMPUR-Ergo — so position works out of
the box with no setup.

If your bed's travel differs, open the integration's **Configure** dialog and,
for each section:

1. Press **Flat**, wait for it to settle.
2. Hold the section up until the motor stops.
3. Read the tick count from the position sensor and enter it as the max.

Set a section to `0` to disable its estimate (sensor reports `unknown`).

## Services

### `ha_tempurpedic.start_move`

Begin continuously moving the bed. The integration sends the command in a loop until `stop_move` is called. Used by the Lovelace card for hold-to-move behavior.

| Field | Description |
|---|---|
| `entity_id` | A `head_up`, `head_down`, `legs_up`, or `legs_down` button entity |

### `ha_tempurpedic.stop_move`

Stop any active hold movement on all sides. No fields required.

## Lovelace Card

The companion card ([tempurpedic-bed-card](https://github.com/ben-j-h/tempurpedic-bed-card)) provides a touch-optimized control panel with hold-to-move buttons, vibration sliders, an animated bed silhouette driven by the position sensors, and a split-king side toggle with renameable labels.

## Split-King Setup

Add the integration twice — once for each side — giving each a distinct name (e.g. `Master Bedroom Left` and `Master Bedroom Right`). The Lovelace card's `left_prefix` / `right_prefix` config then targets each side independently, or both simultaneously.

## Notes

- The UDP control channel is effectively **write-only** — the bed never reports its head/leg angle, so the position sensors are a dead-reckoning estimate from tick counting, not a true reading.
- The bed's WiFi module also exposes a TCP config channel (port 2000) and, on some hardware, HTTP — WiFi setup, firmware, RSSI, etc. None of that is used here; see [`docs/ergo-base-protocol.md`](docs/ergo-base-protocol.md) for the full protocol reference.

---

[releases-shield]: https://img.shields.io/github/v/release/ben-j-h/ha-tempurpedic?style=for-the-badge
[releases]: https://github.com/ben-j-h/ha-tempurpedic/releases
[commits-shield]: https://img.shields.io/github/commit-activity/y/ben-j-h/ha-tempurpedic?style=for-the-badge
[commits]: https://github.com/ben-j-h/ha-tempurpedic/commits/main
[license-shield]: https://img.shields.io/github/license/ben-j-h/ha-tempurpedic?style=for-the-badge
