# TEMPUR‑Ergo Adjustable Base — Network Protocol Reference

Derived from a `jadx` decompile of the official *TEMPUR‑Ergo* Android app
(`com.tempur.ergo`, package in `research/ergo/`). This supersedes the earlier
pcap‑only notes — the decompiled source gives exact bytes, checksums, ACK codes,
retry logic, and the full TCP/HTTP configuration surface.

All source paths below are relative to `research/ergo/sources/`.

---

## 1. Transports at a glance

The bed's Wi‑Fi module is a **Roving Networks** serial‑to‑Wi‑Fi module
(RN‑style, firmware `logicdata122` / reported version `1.2.2`). A second
hardware variant exists (**Marvell**, firmware `1.0.2`) that replaces the TCP
config channel with an HTTP one. Vendor is detected from the discovery beacon
(§2).

| Purpose | Transport | Port | Used by this integration? |
|---|---|---|---|
| **Motion + massage control** | UDP | **50007** | ✅ yes (this is the whole integration) |
| Discovery / presence beacon | UDP broadcast | **55555** | ❌ (could be — see §2) |
| Module config (Roving) | TCP, line‑oriented | **2000** | ❌ |
| Module config (Marvell) | HTTP | **80** | ❌ |
| Firmware image pull (Roving) | FTP (module is client) | 2021 | ❌ |

Key constants — `com/tempur/ergo/utils/Globals.java`:

```
DEFAULT_MODULE_UDP_PORT            = 50007
DEFAULT_MODULE_UDP_BROADCAST_PORT  = 55555
DEFAULT_MODULE_TCP_PORT            = 2000
DEFAULT_MODULE_UDP_TIMEOUT         = 150   (ms socket read timeout)
DEFAULT_MODULE_UDP_RETRY_ATTEMPTS  = 16
DEFAULT_COMMAND_UDP_WAITUNTILNEXTCOMMAND = 100 (ms between repeat cycles)
HTTP_PORT = 8080 (app's own server), module HTTP is plain :80
FTP_USER = FTP_PASSWORD = "logic1", FTP_PORT = 2021
SPACE_REPLACEMENT_CHAR = '^'   (spaces in TCP string args are sent as '^')
```

---

## 2. Discovery (UDP broadcast :55555)

`NetworkModuleManager.DiscoverModulesTask`:

* The app **only listens**. It binds `0.0.0.0:55555` (`SO_REUSEADDR`, broadcast
  enabled, 150 ms read timeout, multicast lock held) and waits. It never sends a
  probe — **the base emits beacons unsolicited** to the broadcast address.
* Each beacon is a **111‑byte** datagram. Parsed fields:

| Offset | Len | Meaning |
|---|---|---|
| 60 | 32 | ASCII `deviceId` + `hostname`, space‑padded |
| 92 | 1 | vendor flag: **non‑zero → Roving**, `0` → Marvell |

* `deviceId` / `hostname` split:
  * string starts with `"TEMPUR_"` → `deviceId = s[0:13]`, `hostname = s[13:].trim()`
  * otherwise (Roving `WMxxxxxx` style) → `deviceId = s[0:10]`, `hostname = s[10:].trim()`
* The bed's IP is simply the **source address** of the beacon packet.
* SSID pattern for a module still in soft‑AP mode
  (`NetworkModule.isModuleSsid`): `WM[A-Za-z0-9]{6}` or `TEMPUR_[A-Za-z0-9]{6}`.

**Reachability check** (`ModuleReachabilityUDPTask`): open UDP :50007, send
`GetMacAddressCommand` (`0x35`), expect `ACK5` + 6 MAC bytes, then confirm the
last 3 bytes of the MAC (as hex) match the last 6 chars of `deviceId`.

> This is almost certainly the source of the bogus "vibration session" in the
> current integration: a pcap of app start‑up shows `35 → ACK5…` (MAC probe) and,
> after any motion, `34 → ACK4` (kill‑auto‑send, §4). Those framed the massage
> traffic in the capture but are unrelated to it.

---

## 3. UDP control protocol (:50007)

### 3.1 Wire framing

Two shapes are used.

**A. LOGICDATA framed command — 9 bytes** (all motion, position, and massage):

```
 byte  0    1    2    3    4    5    6    7    8
      33   05   32   GG   94   FN   P1   P2   CK
      │    │    │    │    │    │    │    │    └─ checksum = b4 ^ b5 ^ b6 ^ b7
      │    │    │    │    │    │    └────┴──── parameters (zone / slot / level / flags)
      │    │    │    │    │    └────────────── function selector (see table)
      │    │    │    │    └─────────────────── 0x94  = LOGICDATA "write" opcode
      │    │    │    └──────────────────────── group byte: 0x03 set‑value · 0x0A one‑shot · 0x18 motor
      │    │    └───────────────────────────── 0x32  constant
      │    └────────────────────────────────── 0x05  constant (body length, bytes 4..8)
      └─────────────────────────────────────── 0x33  constant (frame start)
```

Checksum is **XOR of bytes 4,5,6,7** only. (The app sometimes writes it as
`P1 ^ 0x11 ^ P2` etc.; that is the same value because `0x94 ^ 0x85 = 0x11`,
`0x94 ^ 0x8E = 0x1A`, `0x94 ^ 0x8D ^ 0x78 = 0x61`, …)

**B. Raw single‑byte / bare‑ASCII commands** (wake‑up, kill‑auto‑send,
get‑MAC, LED):

| Bytes (hex) | ASCII | Command |
|---|---|---|
| `FE 4C4F4749434441544F50454E` | `0xFE` + `LOGICDATAOPEN` | Wake‑up / open (`WakeUpUDPCommand`) |
| `34` | `4` | Kill auto‑send (`KillAutoSendCommand`) |
| `35` | `5` | Get MAC (`GetMacAddressCommand`) |
| `30 pp pp dd` | — | LED blink (`LedCommand`, see §4) |

### 3.2 Responses

The module replies with a short datagram; only the first 4 bytes matter
(`handleResponse` reads into a 4‑byte buffer and loops until an empty datagram).

| Reply (hex) | ASCII | Meaning |
|---|---|---|
| `41 43 4B 33` | `ACK3` | framed command accepted (motion / massage / position) |
| `41 43 4B 34` | `ACK4` | kill‑auto‑send accepted |
| `41 43 4B 35` + 6 bytes | `ACK5`+MAC | get‑MAC reply |
| `41 43 4B FE` | `ACK` `0xFE` | wake‑up accepted |
| `41 43 4B 30` / `…31` | `ACK0` / `ACK1` | LED green / red accepted |

### 3.3 Send / retry algorithm (`NetworkModuleManager.SendUDPCommandTask`)

```
socket = new DatagramSocket(); socket.setReuseAddress(true)
socket.setSoTimeout(150)
socket.connect(ip, 50007)

for each command in list:
    attempt = 0
    loop:
        socket.send(bytes)
        read datagrams into 4‑byte buffer until an empty read   # drain
        if handleResponse(buffer):  break        # got ACKx
        # timeout / IOException path:
        if vendor == Roving and attempt == 0 and command != WakeUp:
            send WakeUpUDPCommand (LOGICDATAOPEN) once, check its ACK
        attempt++
        if attempt >= 16:  report failure; stop
    # continuous mode (hold‑to‑move): sleep 100 ms, repeat; maxCycles 0 = forever
```

Notes that matter for a re‑implementation:

* **No per‑command `LOGICDATAOPEN` prefix.** Wake‑up is sent **only after a
  timeout**, then the real command is retried. A healthy base ACKs the first
  packet directly.
* One socket per command *burst*; `connect()`ed, so it's a plain
  `send()`/`recv()`.
* Motion "hold" = the same `MoveCommand` resent every 100 ms until release;
  on release the app sends **one `KillAutoSendCommand` (`0x34`)** to stop the
  base's internal auto‑repeat. Without it the base keeps moving briefly after
  the last packet (the "overshoot" seen today).

---

## 4. UDP command catalogue (exact bytes)

Source: `com/tempur/ergo/networking/commands/udp/*.java`. Byte values were
resolved from the obfuscated `org.freepascal.rtl.system` / `SecureBlackbox`
constants (decode table in §7).

### 4.1 Position / motion

| Command | Class | Bytes (hex) | Notes |
|---|---|---|---|
| Flat (all zones to 0) | `FlatPositionCommand` | `33 05 32 0A 94 5C 04 00 CC` | one‑shot |
| Head up (motor) | `MoveCommand(Head,Up)` | `33 05 32 18 94 53 00 05 C2` | resend @100 ms while held |
| Head down | `MoveCommand(Head,Down)` | `33 05 32 18 94 54 00 05 C5` | |
| Legs up | `MoveCommand(Leg,Up)` | `33 05 32 18 94 51 01 00 C4` | |
| Legs down | `MoveCommand(Leg,Down)` | `33 05 32 18 94 52 01 00 C7` | |
| Stop motor (after hold) | `KillAutoSendCommand` | `34` | expect `ACK4` |
| Recall memory 1 | `MoveToMemoryPositionCommand(0)` | `33 05 32 03 94 5C 00 00 C8` | |
| Recall memory 2 | `…(1)` | `33 05 32 03 94 5C 01 00 C9` | |
| Recall memory 3 | `…(2)` | `33 05 32 03 94 5C 02 00 CA` | |
| Recall memory 4 | `…(3)` | `33 05 32 03 94 5C 03 00 CB` | |
| Save memory 1 | `SaveToMemoryPositionCommand(0)` | `33 05 32 03 94 5B 00 00 CF` | app triggers on 3 s long‑press |
| Save memory 2 | `…(1)` | `33 05 32 03 94 5B 01 00 CE` | |
| Save memory 3 | `…(2)` | `33 05 32 03 94 5B 02 00 CD` | |
| Save memory 4 | `…(3)` | `33 05 32 03 94 5B 03 00 CC` | |

`MoveCommand` param layout: FN = `0x51` legs‑up · `0x52` legs‑down · `0x53`
head‑up · `0x54` head‑down; for head P1=`0x00` P2=`0x05`, for legs P1=`0x01`
P2=`0x00`.

### 4.2 Massage / vibration  ← the part that's broken today

There are **two independent massage mechanisms**:

**(a) Per‑zone manual intensity — `ManualMassageCommand(zone, level)`**

```
33 05 32 03 94 85 ZZ LL CK
   ZZ = zone:  0x00 head · 0x01 lumbar/torso · 0x02 legs
   LL = level * 24  (0x18)   → level 0..10 ⇒ 0x00,0x18,0x30,0x48,0x60,0x78,0x90,0xA8,0xC0,0xD8,0xF0
   CK = 0x94 ^ 0x85 ^ ZZ ^ LL
```

* `level` is **absolute** (0 = that zone off). The app's UI steps ±1 per tap
  with a 500 ms debounce, but every packet still carries the absolute target —
  there is no protocol requirement to walk levels.
* Example — lumbar to level 5: `33 05 32 03 94 85 01 78 68`
  (`CK = 0x94^0x85^0x01^0x78 = 0x68`).
* When the *last* active zone drops to 0 the app sends a 2‑command burst:
  `ManualMassageCommand(zone,0)` **then** `StopMassageCommand`.

**(b) Whole‑body massage programs — `MassagePresetCommand(mode)`** (mode 0–3):

```
33 05 32 03 94 8D 0m 78 CK      m = 0..3,  CK = m ^ 0x61
  mode 0: 33 05 32 03 94 8D 00 78 61
  mode 1: 33 05 32 03 94 8D 01 78 60
  mode 2: 33 05 32 03 94 8D 02 78 63
  mode 3: 33 05 32 03 94 8D 03 78 62
```

**Stop all massage — `StopMassageCommand`:**

```
33 05 32 0A 94 86 00 00 12
```

**(c) `PresetMassageCommand(zone, level)`** — `FN = 0x8E`,
`CK = 0x94 ^ 0x8E ^ ZZ ^ LL`. Used *only* to nudge one zone's level while a
program from (b) is running. Not needed for a from‑scratch implementation.

All of the above are sent through the **ordinary §3.3 path** — a bare `send`,
read the 4‑byte reply, expect `ACK3`, wake‑up‑and‑retry on timeout. **No `0x35`,
no `0x34`, no session.**

### 4.3 Other

| Command | Bytes | Reply | Purpose |
|---|---|---|---|
| `WakeUpUDPCommand` | `FE` + `"LOGICDATAOPEN"` | `ACK` `0xFE` | nudge module out of sleep; also the integration's connectivity test |
| `GetMacAddressCommand` | `35` | `ACK5` + 6 MAC bytes | reachability / identity match |
| `KillAutoSendCommand` | `34` | `ACK4` | halt internal motor auto‑repeat |
| `LedCommand(color, periodMs, durMs)` | `CC pp pp dd` | `ACK0`/`ACK1` | blink module LED to identify it. `CC` = `0x30` green / `0x31` red; `pp = periodMs/125`; `dd = durMs/125`. Not LOGICDATA‑framed. |

---

## 5. TCP configuration channel (:2000, Roving)

Line protocol. Enter command mode, send `\r`‑terminated commands, exit.
Source: `com/tempur/ergo/networking/commands/tcp/*.java` +
`NetworkModuleManager.SendTCPCommandTask` (socket: `SO_REUSEADDR`, keep‑alive,
1500 ms timeout, 3 retries/command, 50 ms between cycles).

| Step | Send | Expected |
|---|---|---|
| Enter command mode | `$$$` (**no** CR) | contains `CMD` |
| Exit command mode | `exit\r` | contains `EXIT` |
| Commit to flash | `save\r` | `AOK` (or: no `ERR`) |
| Reboot | `reboot\r` | — (no reply expected) |
| Factory reset | `factory RESET\r` | echoes `factory RESET` |

Query commands:

| Send | Parses |
|---|---|
| `ver\r` | firmware — line `…Ver:X.Y.Z…` (`;`‑separated) |
| `get mac\r` | `Mac Addr=AA:BB:CC:DD:EE:FF` |
| `get wlan\r` | `SSID=…`, `Chan=…`, `Join=…` |
| `get option\r` | `DeviceId=…` (first 10 chars = id, remainder = module name) |
| `show rssi\r` | `RSSI=(-nn)` → % via linear map −80 dBm→0 %, −20 dBm→100 % |
| `scan <ms_per_channel>\r` | `SCAN:Found n` + CSV rows; SSID is field 8+. Response timeout `= ms*13 + 1500` |

Setters (all reply `AOK` / no `ERR`; spaces in values → `^`):

| Send | Meaning |
|---|---|
| `set opt deviceid <deviceId><hostname>\r` | device id + friendly name (combined ≤ 32 chars) |
| `set wlan ssid <ssid>\r` | target SSID (≤ 32) |
| `set wlan phrase <passphrase>\r` | WPA passphrase (≤ 64) |
| `set wlan join <n>\r` | 0 manual · 1 auto‑stored · 2 auto‑any · 4 create ad‑hoc · 7 create soft‑AP |
| `set wlan channel <n>\r` | 0 = auto |
| `set ip dhcp <n>\r` | 0 off (static) · 1 DHCP client · 4 DHCP server |
| `set ip address <a.b.c.d>\r` | static IP |
| `set ip netmask <a.b.c.d>\r` | static mask |
| `set ftp addr <ip>\r` / `set ftp remote <port>\r` / `set ftp user <u>\r` / `set ftp pass <p>\r` / `set ftp dir <d>\r` | firmware‑pull FTP target |
| `ftp update <image>\r` | pull + flash firmware; success line `UPDATE OK`, streamed progress via `FTP timeout=n` |

**Roving Wi‑Fi provisioning sequence** (`ModuleSetupActivity`, "Save"):

```
$$$
set opt deviceid <id><hostname>
set wlan join 1
set wlan ssid <ssid>
set wlan phrase <pass>            # only if a passphrase was entered
set wlan join 1
set wlan channel 0
# static IP:
set ip dhcp 0
set ip address <ip>
set ip netmask <mask>
# or DHCP:
set ip dhcp 1
save
reboot                           # only when the network actually changed
exit
```

Factory reset (Roving): `factory RESET` → `ver` → `reboot`.

---

## 6. HTTP configuration channel (:80, Marvell variant only)

Source: `com/tempur/ergo/networking/commands/http/*.java`.

| Method + path | Body | Returns |
|---|---|---|
| `GET /sys` | — | `interface` (`station`/`uap`), `connection.station.{configured,status,mac_addr}` |
| `GET /sys/interface` | — | `interface` |
| `GET /sys/network` | — | `ssid,bssid,channel,security,ip(0/1),ipaddr,ipmask` |
| `GET /sys/scan` | — | `networks: [[ssid], …]` |
| `GET /fw-version` | — | `fw_version` |
| `POST /sys/network` | `{ssid, security, key?, channel?, ip:0|1, ipaddr?, ipmask?, ipgw?}` | `{success}` / `{error,error_msg}` |
| `POST /sys/command` | `{"command":"reboot"}` | `{success}` |
| `POST /cfg/factory-reset` | — | `{success}` |
| `POST /cfg/ld-params` | `{"module_name": "<name>"}` | `{success}` |
| `POST /sys/updater` | `{"fw_url": "<url>"}` | `{success}` — 60 s timeout |

`security`: 0 open · 1 WEP · 3 WPA · 4 WPA2 · 5 WPA/WPA2. Static IP sets
`ip:0` and includes `ipaddr`/`ipmask`/`ipgw` (`ipgw` hard‑coded `127.0.0.1`).

---

## 7. Obfuscated‑constant decode table

`jadx` left many literals as symbolic names. Values used above:

| Symbol | Value | | Symbol | Value |
|---|---|---|---|---|
| `system.fpc_in_leave` | `0x33` | | `system.FPCJDynArrTypeJShort` | `0x53` `'S'` |
| `system.fpc_in_cycle` | `0x34` | | `system.FPCJDynArrTypeShortstring` | `0x54` `'T'` |
| `system.fpc_in_slice` | `0x35` | | `system.FPCJDynArrTypeRecord` | `0x52` `'R'` |
| `system.fpc_in_trunc_real` | `0x78` | | `system.FPCJDynArrTypeProcVar` | `0x50` `'P'` |
| `system.fpc_in_mmx_pcmpgtw` | `0xCC` | | `SBASN1Tree.SB_ASN1_A5_PRIMITIVE` | `0x85` |
| `system.fpc_in_popcnt_x` | `0x4F` `'O'` | | `SBASN1Tree.SB_ASN1_A6_PRIMITIVE` | `0x86` |
| `system.fpc_objc_encode_x` | `0x47` `'G'` | | `SBConstants.cSBPathSeparator` | `0x5C` `'\'` |
| `system.fpc_in_unbox_x_y` | `0x4E` `'N'` | | `Scheduler.MAX_GREEDY_SCHEDULER_LIMIT` | `200` (`0xC8`) |

---

## 8. Current integration vs. the app — findings & fixes

Files: `custom_components/ha_tempurpedic/`.

### 8.1 What's already correct

* Every hex string in `const.COMMANDS` matches the app byte‑for‑byte:
  `flat`, `head_up/down`, `legs_up/down`, `preset_1..4` (= recall memory),
  `vibrate_off` (= `StopMassageCommand`), `vibrate_1..4`
  (= `MassagePresetCommand` programs 0–3).
* `const.build_vib_command(zone, level)` is **identical** to
  `ManualMassageCommand` — bytes and checksum both right.
* `VIB_LEVELS` = `level * 24` — matches.
* `api.test_connection()` (send `LOGICDATAOPEN`, expect `ACK\xFE`) — matches
  `WakeUpUDPCommand`.

### 8.2 Bugs

| # | Where | Problem | Fix |
|---|---|---|---|
| 1 | `api.send_vib_session`, `const.VIB_PRE=0x35` / `VIB_POST=0x34` | Invented "session". `0x35` is **Get‑MAC** (`ACK5`), `0x34` is **Kill‑auto‑send** (`ACK4`). Wrapping massage packets in these does not correspond to anything the base expects — hence vibration never works. | Delete `send_vib_session`, `send_command_direct`, `VIB_PRE`, `VIB_POST`. Send massage commands via the **normal** path. |
| 2 | `number.async_set_native_value` | Sends the fabricated session **and** walks intermediate levels. | Send a single `build_vib_command(zone, target)` (absolute). For `target == 0` send `build_vib_command(zone, 0)` **then** `COMMANDS["vibrate_off"]`. Only re‑introduce stepping (≈150–300 ms apart, still plain sends) if hardware testing shows big jumps are ignored. |
| 3 | `button.async_press` `direct=True` branch | Routes `vibrate_*` through `send_command_direct` (the fake session). | Drop the `direct` flag; all buttons use the same sender. |
| 4 | `api.send_command` | Always `cmd → LOGICDATAOPEN → cmd`, i.e. **every** press actuates twice and every press pays a mandatory wake‑up round‑trip. | Match the app: send `cmd`, read reply; **only on timeout** send `LOGICDATAOPEN` and retry, up to ~16×. Expect `ACK3` (`b"ACK3"`, 4 bytes — don't require exact length/trailing). |
| 5 | `__init__.handle_stop_move` / hold loop | Loop just stops; base keeps auto‑repeating → overshoot. | After the move loop ends, send `KillAutoSendCommand` = `b"\x34"` once (expect `ACK4`). |
| 6 | `__init__.move_loop` | `await asyncio.sleep(0)` = tightest possible loop. | App uses **100 ms** between repeats (`DEFAULT_COMMAND_UDP_WAITUNTILNEXTCOMMAND`). |

### 8.3 Suggested `api.py` shape

```python
ACK_OK   = b"ACK3"
ACK_WAKE = b"ACK\xfe"

def send_command(self, command: bytes, *, retries: int = 16) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.settimeout(0.15)
        sock.connect((self._host, self._port))
        for attempt in range(retries):
            sock.send(command)
            try:
                if sock.recv(16)[:4] == ACK_OK:
                    return True
            except TimeoutError:
                pass
            if attempt == 0:                      # wake once, then retry
                with contextlib.suppress(OSError):
                    sock.send(LOGICDATAOPEN)
                    sock.recv(16)
        return False
    except OSError:
        return False
    finally:
        with contextlib.suppress(OSError):
            sock.close()

def stop_motor(self) -> bool:
    return self._one_shot(b"\x34", ACK4)          # after a hold loop
```

Massage then needs no special method — head/lumbar/leg sliders call
`send_command(build_vib_command(zone, level))`; `vibrate_off` and `vibrate_1..4`
call `send_command(COMMANDS[...])`.

### 8.4 Opportunities the decompile unlocks

* **Auto‑discovery** — listen on UDP `0.0.0.0:55555` for the 111‑byte beacon;
  pull IP from the packet source and `deviceId`/`hostname` from offset 60. Would
  replace manual IP entry in the config flow (with a DHCP‑reservation nudge
  still recommended).
* **Save‑to‑memory** buttons — `SaveToMemoryPositionCommand` (`…94 5B slot…`),
  currently unused; the app binds it to a 3 s long‑press on each preset.
* **Identify** — `LedCommand` to blink the module LED when configuring multiple
  beds.
* **Diagnostics sensors** (Roving, TCP :2000): firmware `ver`, RSSI `show rssi`
  (with the app's −80/−20 dBm → 0/100 % mapping), SSID/channel `get wlan`.
  These are the only genuine *read* paths — the UDP control channel is
  write‑only, so the static bed silhouette in the card can't be made live
  without external sensors.
* **Wi‑Fi provisioning** — full soft‑AP → home‑network onboarding is possible
  via the §5 sequence, but it's a large surface and rarely needed after initial
  setup; treat as optional.
