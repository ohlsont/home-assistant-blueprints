# Blockheat Home Assistant Integration

A Home Assistant custom integration for policy-driven heating control. Blockheat
decides when to save energy (based on electricity price, PV production, and time
windows) and computes temperature targets for a heat pump.

## Folder Layout

- `custom_components/blockheat/` -- HACS-compatible integration (config flow, runtime adapter, pure Python engine).
- `tests/` -- Unit tests collected by `pytest`.

## Installation

### Via HACS

1. Open HACS -> Integrations -> three-dot menu -> Custom repositories.
2. Add this repository URL as type **Integration**.
3. Search for **Blockheat** in HACS and install it.
4. Restart Home Assistant.
5. Go to **Settings -> Devices & Services -> Add Integration** and add **Blockheat**.

### Manual

```bash
mkdir -p /config/custom_components
cp -R custom_components/blockheat /config/custom_components/blockheat
```

Restart Home Assistant, then add Blockheat from Settings -> Devices & Services.

## Configuration

The config flow has two steps:

1. **Entity mapping** -- searchable, domain-filtered entity pickers for external
   inputs (price sensor, room/storage/outdoor sensors, PV), control output
   (writable number entity), and optional consumers (Daikin climate entity).
2. **Tuning wizard** -- policy window, saving/comfort targets, cold boost,
   forecast optimization, and optional Daikin section (shown only when enabled).

## Internal State Entities

Read-only entities exposed by the integration:

- `binary_sensor.blockheat_energy_saving_active`
- `sensor.blockheat_target_saving`
- `sensor.blockheat_target_comfort`
- `sensor.blockheat_target_final`

## Events

- `blockheat_policy_changed` -- fired on policy state transitions.
- `blockheat_snapshot` -- fired on every recompute with full diagnostics payload.

## Service

- `blockheat.recompute` -- force an immediate recompute. Supports optional
  `entry_id` parameter and response payloads.

## Testing

```bash
# Install dev dependencies
uv sync --group dev

# Run all tests
uv run python -m pytest tests -q

# Coverage gate (CI threshold: 80%)
uv run python -m pytest tests -q --cov=custom_components.blockheat --cov-branch --cov-report=term-missing --cov-fail-under=80
```

Shared fake Home Assistant test fixtures are defined in `tests/conftest.py`.

## Releases

Version must match in two files:

- `custom_components/blockheat/manifest.json`
- `pyproject.toml`

Release flow:

```bash
uv run python scripts/bump_version.py X.Y.Z
git add pyproject.toml custom_components/blockheat/manifest.json
git commit -m "chore: bump version to X.Y.Z"
git tag vX.Y.Z
git push && git push --tags
```

GitHub Actions creates the release with a HACS zip automatically.
