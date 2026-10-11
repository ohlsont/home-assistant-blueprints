# Master Bedroom Adjustable Bed

## Hardware

- Two separate Linak beds (Bed 1 and Bed 2), each with its own control box
- Control box: Linak TD5 TWINDRIVE, type `TD500000B62450X`, item `TD50003-01`, model TDA
  - Manufactured 2026-04-09, software `3002009 Ver. 1.22`, config `CFGTD50003V2-01`
  - Max angles: head 62, leg 45; duty cycle 10% (max 1 min on / 9 min off)
- Each bed has a physical remote and under-bed lights

## Home Assistant Integration

- Integration: Adjustable Bed (HACS, https://github.com/kristofferR/ha-adjustable-bed), v4.1.1 as of 2026-10-10
- Devices: `Bed 1`, `Bed 2` (area `master_bedroom`), plus a combined `Bed` device
  - Per-bed entities: `*.master_bedroom_bed_<1|2>_*` (back/legs covers and positions, flat, memory 1-4, save to memory 1-4, stop, connect, disconnect, wake, under-bed light, BLE connection)
  - Combined entities: `*.bed_*` (positions are the average of both beds; `button.bed_flat` etc. are untested)
- Linak beds do NOT need Bluetooth pairing/bonding. After each new connection the controller rejects writes with `Insufficient authentication` for up to ~12 s; the integration retries for up to 15 s.

## Bluetooth Path

- Only connectable proxy: `bluetooth proxy with antenna` (ESP32-S3), in the master bedroom about 2 m from the bed. Also serves the Gardena water controller.
- `lamp-ble-proxy` (kitchen) is passive only (0 connection slots).
- The old `Bluetooth proxy axels` (58bb60) no longer exists; its HA entries are stale (removal pending as of 2026-10-10).

## Latency and Conflicts

Measured 2026-10-07 and 2026-10-10:

- Cold command (no open connection): BLE connect ~1.2-1.5 s, motor starts ~3.5-4.5 s after the press.
- Warm command (connection still open): motor starts ~0.3 s after the press.
- The integration drops the connection ~10 s after the last command, so most commands are cold.
- Pressing again while waiting sends overlapping commands and causes `key_error` protocol errors and stop-start motion. Press once and wait ~5 s.
- The bed accepts one BLE connection at a time; while HA is connected the remote/app may be blocked.
- HA only sees positions while connected, so remote-only movements show up on the next HA connection.

## Memory Slots

| Slot | Use                                                                                |
| ---- | ---------------------------------------------------------------------------------- |
| 1    | Unknown (one of 1, 2 or 4 holds the bed's zero-gravity preset)                     |
| 2    | Unknown                                                                            |
| 3    | TV mode (set 2026-10-10): Bed 1 back 46.8 / legs 15.5, Bed 2 back 46.7 / legs 16.3 |
| 4    | Unknown                                                                            |

To re-save TV mode: move each bed to the desired angles, then press `button.master_bedroom_bed_<n>_save_to_memory_3`.

## Automations (IKEA dual button, master bedroom)

| Button | Press  | Automation                              | Action                                      |
| ------ | ------ | --------------------------------------- | ------------------------------------------- |
| 1      | single | `automation.beds_down` ("Beds TV mode") | Memory 3 on both beds (`continue_on_error`) |
| 2      | single | `automation.beds_flat` ("Beds flat")    | Flat on both beds                           |

The automations live in HA only (not in this repo). Event entities: `event.master_bedroom_ikea_dual_button_button_<1|2>`, event type `multi_press_1`.

## Troubleshooting

- **Bed stuck: connects but positions stay `unknown`, commands fail with `Insufficient authentication` / "Linak control stayed unavailable after 15 s"**: unplug the bed's power supply for 30 s, plug back in, wait ~15 s, and leave the remote alone for a minute. Fixed Bed 1 on 2026-10-10.
- **Moving only the legs on Bed 1 via HA also moved the back** (seen 2026-10-10). Memory recall is not affected; use memories rather than the individual sliders for presets.
- Integration docs: Linak (`docs/beds/linak.md`), troubleshooting (`docs/TROUBLESHOOTING.md`) in the integration repo.
