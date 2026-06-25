# TEMPUR-Ergo Adjustable Base — Home Assistant Integration

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

Control your TEMPUR-Ergo adjustable base directly from Home Assistant over your local WiFi network. No cloud, no account — pure UDP to the bed's built-in WiFi module.

![icon](icon.png)

## Features

- **Position control** — Head up/down, legs up/down, flat, and four memory presets
- **Massage control** — Per-zone vibration intensity (head, lumbar, legs) and four vibration presets
- **Hold-to-move** — The integration runs a continuous loop while a direction is held, matching the app's behavior exactly
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

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Tempurpedic Adjustable Base**
3. Enter:
   - **Device Name** — a friendly label, e.g. `Master Bedroom Left`. This becomes the device name and drives entity IDs.
   - **IP Address** — the bed's local IP (find it in your router's DHCP table; recommend setting a static lease)
   - **UDP Port** — default `50007`, leave as-is unless you have a reason to change it

The integration tests connectivity on setup — if the bed doesn't respond, setup will fail with a "cannot connect" error.

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
| `button.{name}_preset_1` … `preset_4` | Recall memory position 1–4 |
| `button.{name}_vibrate_off` | Stop all vibration |
| `button.{name}_vibrate_1` … `vibrate_4` | Vibration presets 1–4 |

### Number sliders

| Entity | Description |
|---|---|
| `number.{name}_vib_head` | Head zone vibration intensity (1–10) |
| `number.{name}_vib_torso` | Lumbar zone vibration intensity (1–10) |
| `number.{name}_vib_legs` | Leg zone vibration intensity (1–10) |

## Services

### `ha_tempurpedic.start_move`

Begin continuously moving the bed. The integration sends the command in a loop until `stop_move` is called. Used by the Lovelace card for hold-to-move behavior.

| Field | Description |
|---|---|
| `entity_id` | A `head_up`, `head_down`, `legs_up`, or `legs_down` button entity |

### `ha_tempurpedic.stop_move`

Stop any active hold movement on all sides. No fields required.

## Lovelace Card

The companion card ([tempurpedic-bed-card](https://github.com/ben-j-h/tempurpedic-bed-card)) provides a touch-optimized control panel with hold-to-move buttons, vibration sliders, and LEFT/BOTH/RIGHT split-king toggle.

## Split-King Setup

Add the integration twice — once for each side — giving each a distinct name (e.g. `Master Bedroom Left` and `Master Bedroom Right`). The Lovelace card's `left_prefix` / `right_prefix` config then targets each side independently, or both simultaneously.

## Notes

- The bed's protocol is **write-only**. There is no way to read back the current head/leg position over UDP. The bed silhouette in the Lovelace card is static; animated position would require external tilt sensors.
- The bed's WiFi module (Roving Networks) also exposes TCP port 2000, but this is not used by the integration.

---

[releases-shield]: https://img.shields.io/github/v/release/ben-j-h/ha-tempurpedic?style=for-the-badge
[releases]: https://github.com/ben-j-h/ha-tempurpedic/releases
[commits-shield]: https://img.shields.io/github/commit-activity/y/ben-j-h/ha-tempurpedic?style=for-the-badge
[commits]: https://github.com/ben-j-h/ha-tempurpedic/commits/main
[license-shield]: https://img.shields.io/github/license/ben-j-h/ha-tempurpedic?style=for-the-badge
