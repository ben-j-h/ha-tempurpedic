# TEMPUR-Ergo Adjustable Base — Home Assistant Integration

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

Control your TEMPUR-Ergo adjustable base directly from Home Assistant over your local WiFi network. No cloud, no account — pure UDP to the bed's built-in WiFi module.

![icon](icon.png)

## Features

- **Position control** — Head up/down, legs up/down, flat, and a memory-preset value (0–4)
- **Per-zone massage control** — Vibration intensity values (head, lumbar, legs); each walks to the requested level one step at a time, the way the app does, plus a single massage-program value (0 = off, 1–4 = the bed's built-in programs)
- **Hold-to-move** — The integration sends a movement command in a loop while a direction is held
- **Position estimate** — Head/leg position sensors (0–100%) derived from hold-to-move tick counting, once calibrated
- **Power monitoring (optional)** — Point it at a metering plug and get `moving` / `massage_active` binary sensors, plus automatic invalidation of the position estimate when the wall remote is used
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
| `number.{name}_vib_head` | 0–10 | Head zone vibration intensity (walks one step at a time to the target) |
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
hold-to-move, so it drifts, is reset to 0 by **Flat**, and reads `unknown` once
an out-of-band move is detected (see below). It is only an estimate — the bed
reports nothing back.

### Binary sensors

| Entity | On when |
|---|---|
| `binary_sensor.{name}_moving` | a hold-to-move is running, or the plug shows a tilt-level draw |
| `binary_sensor.{name}_massage_active` | vibration/program is commanded, or the plug shows a massage-level draw |

`moving` carries `power_w`, `activity` (`idle`/`massage`/`tilting`/`unknown`) and
`position_trusted` as attributes.

## Calibration & power monitoring

Open the integration's **Configure** dialog.

**Position ticks.** Both sensors default to a **full-travel count of 40 ticks**,
measured on a real unit and believed standard for the TEMPUR-Ergo, so position
works out of the box. If your travel differs: press **Flat**, hold a section up
until the motor stops, read the tick count off the sensor, enter it as the max.
`0` disables that section's estimate.

**Power sensor (optional).** The base reports nothing, so a metering plug is the
only outside signal. Point `power_sensor` at your plug's power (W) entity and set
two thresholds:

- **Idle threshold** — at or below = bed idle
- **Tilt threshold** — at or above = a lift motor is running; between the two = massaging

Every bed and plug is different — start with the defaults (10 W / 45 W) and watch
the `moving` sensor's `power_w` attribute while you tilt vs. massage, then tune.
With a power sensor set, an unexpected tilt-level draw (someone used the wall
remote) marks the position estimate `unknown` until the next **Flat**, and the
tick counter stops if the motor is drawing idle current (hit its limit).

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
