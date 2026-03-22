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
