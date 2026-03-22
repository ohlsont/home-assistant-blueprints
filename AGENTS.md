# AGENTS.md

Shared project instructions for all AI agents (Claude Code, Codex, etc.).

## What This Is

Blockheat is an automations-based heating control system for Home Assistant. It decides when to save energy (based on electricity price, PV production, and time windows) and computes temperature targets for a heat pump. All logic is implemented as native HA automations in `automations/`.

## Home Hardware

The physical heating system is documented in [`docs/home-architecture.md`](docs/home-architecture.md).

Key points for development:
- **Heat pump**: Qvantum ETK6500 (exhaust-air). Manual: [`docs/Qvantum-ETK-Manual.pdf`](docs/Qvantum-ETK-Manual.pdf)
- **External sensor**: Ohmigo WiFi replaces the ETK6500's built-in room sensor. Blockheat writes its target to `number.ohmigo_temperature_2`, which the heat pump reads as room temperature.
- **Control method**: Indirect -- Blockheat manipulates the reported room temp to make the heat pump's own thermostat start/stop as desired.

## Ohmigo Control Model (critical)

The Ohmigo value written to `number.ohmigo_temperature_2` is a **fake room temperature**, NOT a desired setpoint. The heat pump compares it against its BOR-värde (built-in setpoint, 22 °C):

- **Ohmigo < BOR (22)** → heat pump thinks room is cold → **runs**
- **Ohmigo > BOR (22)** → heat pump thinks room is warm → **stops**
- **Ohmigo = BOR (22)** → at threshold → won't actively heat

This is **inverse** to a normal thermostat setpoint. To make the heat pump heat harder, write a **lower** value. To stop it, write a **higher** value. All automations that compute Ohmigo values must respect this relationship. See `docs/home-architecture.md` lines 23-29 for the full control loop.

## Structure

- Automation YAML files live under `automations/`. See [`automations/README.md`](automations/README.md) for setup and data flow.
- Hardware documentation lives under `docs/`.
- Update `README.md` when behavior or inputs change.

## Gotchas

- **No direct commits to main**: Pre-commit hook blocks `git commit` on the `main` branch. Always work on a feature branch.
- **Pre-commit runs automatically** on commit. To run manually: `uv run pre-commit run --all-files`

## Execution preferences

- Prefer non-interactive git commands.

## Thread workflow (Codex)

- Start every thread in a dedicated git worktree and branch (branch prefix: `codex/`).
- Do all edits, tests, and commits inside that worktree, not in the primary checkout.
- When implementation is complete, open a pull request before marking the thread done.
- After opening the PR, monitor CI/checks until they pass (or explicitly note that no checks are configured).
- Before closing the thread, verify whether behavior/input changes require documentation updates and apply them.
- Keep PRs focused to the thread scope and include verification results in the PR body.

## Conventions

- Conventional Commits for all commit messages.
- Keep changes minimal and focused. Avoid non-ASCII unless the file already uses it.
