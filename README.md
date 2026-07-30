# Blockheat

Automations-based heating control for Home Assistant. Blockheat decides when to
save energy (based on electricity price, PV production, and time windows) and
computes temperature targets for a heat pump.

## How It Works

All logic is implemented as native Home Assistant automations. See
[`automations/README.md`](automations/README.md) for setup instructions, data
flow, and configuration details.

## Hardware

The physical heating system (Qvantum ETK6500 heat pump, Ohmigo WiFi sensor) is
documented in [`docs/home-architecture.md`](docs/home-architecture.md).

## Garden Irrigation

Unrelated to heating, but lives in the same Home Assistant instance. Valve topology,
the Ilex crenata 'Caroline Upright' hedges, measured water use, and the watering
schedule are documented in
[`docs/garden-irrigation.md`](docs/garden-irrigation.md). Deployable automation configs:
[`docs/garden-watering.yaml`](docs/garden-watering.yaml) (morning, all zones) and
[`docs/garden-watering-lawn-evening.yaml`](docs/garden-watering-lawn-evening.yaml)
(lawn evening top-up).

## Energy Savings Dashboard

`homeassistant/solar_savings.yaml` (template/integration/utility-meter sensors)
and `homeassistant/card.yaml` (a Lovelace card) report what the solar + battery
system saves. These are deployed into the Home Assistant config separately from
the automations.

The battery is operated by **Checkwatt** for FCR-D grid services, so its cycling
is not home arbitrage — battery charge/discharge are deliberately excluded from
the savings totals. Net savings sum three non-overlapping streams:

1. **Solar self-consumed (full retail)** — solar serving house load, valued at
   the avoided all-in import price (`electricity_price` + grid fee). Self-consumed
   power is `max(min(PV_AC, home_load), 0)`, robust to Checkwatt's grid cycling.
1. **Grid export reward** — Tibber's payment for exported energy.
1. **Checkwatt income** — battery FCR revenue (already net).

Totals are exposed as `sensor.savings_total_today`,
`sensor.savings_total_monthly`, and `sensor.total_annual_savings`.

**Required helper:** `input_number.solar_grid_fee_sek_kwh` — the grid-side avoided
cost per kWh (Vattenfall variable transfer fee + energy tax, incl VAT; default
`0.93`). Tune it to match your tariff.

Yearly utility meters count since their last reset, not necessarily since 1 Jan.
