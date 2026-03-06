# Blockheat Home Assistant Integration

This repository ships a Home Assistant custom integration for policy-driven
heating control.

## Folder Layout
- `custom_components/blockheat/`
  - HACS-compatible integration path (`config_flow`, runtime adapter, pure Python engine).
- `homeassistant/custom_components/blockheat/`
  - Local development/testing mirror of the integration code.
- `dashboards/blockheat/`
  - Optional diagnostics card YAML for Lovelace.
- `tests/`
  - Unit and parity tests collected by `pytest`.

## Primary Path: Custom Integration (Config Entry UI)
The recommended runtime is `custom_components/blockheat` with one config entry
that owns policy, target calculators, final writer, and optional
Daikin consumer control.

### Install via HACS (GitHub)
1. Open HACS -> Integrations -> three-dot menu -> Custom repositories.
2. Add this repository URL as type **Integration**.
3. Search for **Blockheat** in HACS and install it.
4. Restart Home Assistant.
5. Go to **Settings -> Devices & Services -> Add Integration** and add **Blockheat**.
6. Complete both config steps:
   - Step 1: entity mapping with searchable, domain-filtered entity pickers for external inputs, control output, optional signals, and optional consumers. Legacy helper/boolean mappings are internal-only.
   - Step 2: tuning wizard split into sections:
     - Policy window and guards
     - Saving target
     - Comfort target
     - Cold boost
     - Limits and deadbands
     - Optional Daikin section (only when enabled)

### Install Manually to Home Assistant
From this repo:

```bash
mkdir -p /config/custom_components
cp -R custom_components/blockheat /config/custom_components/blockheat
```

Then in Home Assistant:
1. Restart Home Assistant.
2. Go to **Settings -> Devices & Services -> Add Integration**.
3. Add **Blockheat**.
4. Complete both config steps:
   - Step 1: entity mapping with searchable, domain-filtered entity pickers for external inputs, control output, optional signals, and optional consumers. Legacy helper/boolean mappings are internal-only.
   - Step 2: tuning wizard split into sections:
     - Policy window and guards
     - Saving target
     - Comfort target
     - Cold boost
     - Limits and deadbands
     - Optional Daikin section (only when enabled)

### Sectioned Tuning Baseline (Integration Defaults)
The integration defaults are a balanced profile tuned for Swedish price-driven
operation, `22 C` comfort target, and reduced risk of auxiliary electric heat.

| Section | Defaults |
|---|---|
| Policy window and guards | `minutes_to_block=240`, `price_ignore_below=0.6`, `pv_ignore_above_w=0.0`, `min_toggle_interval_min=15` |
| Saving target | `heatpump_setpoint=20.0`, `saving_cold_offset_c=1.0`, `virtual_temperature=20.0`, `energy_saving_warm_shutdown_outdoor=8.0` |
| Comfort target | `comfort_target_c=22.0`, `comfort_to_heatpump_offset_c=2.0`, `storage_target_c=24.5`, `storage_to_heatpump_offset_c=2.0`, `maintenance_target_c=20.0`, `comfort_margin_c=0.25` |
| Cold boost | `cold_threshold=1.0`, `max_boost=3.0`, `boost_slope_c=4.0` |
| Limits and deadbands | `control_min_c=10.0`, `control_max_c=26.0`, `saving_helper_write_delta_c=0.05`, `comfort_helper_write_delta_c=0.05`, `final_helper_write_delta_c=0.05`, `control_write_delta_c=0.2` |
| Optional Daikin | `daikin_normal_temperature=22.0`, `daikin_saving_temperature=20.0`, `daikin_outdoor_temp_threshold=-10.0`, `daikin_min_temp_change=0.5` |

Quick adjustment rails:
- Policy strength: raise `minutes_to_block` to `255-300` for stronger savings, or lower to `120-210` for comfort-first behavior.
- Saving aggressiveness: reduce `saving_cold_offset_c` to `0.5-0.8` if rooms dip too much, or increase to `1.2-1.5` for stronger savings.
- Comfort tightness: lower `comfort_margin_c` to `0.15-0.2` for tighter control, or increase to `0.3` to reduce churn.
- Cold-weather response: lower `boost_slope_c` to `3.0` for stronger recovery, or raise to `5.0-6.0` if too aggressive.
- Write frequency: increase `control_write_delta_c` to `0.25-0.3` only if control writes are too frequent.

## Testing
Install dev dependencies once:

```bash
uv sync --group dev
```

Run the full suite:

```bash
uv run python -m pytest tests -q
```

Run the coverage gate used by CI:

```bash
uv run python -m pytest tests -q --cov=homeassistant.custom_components.blockheat --cov-branch --cov-report=term-missing --cov-fail-under=80
```

Notes:
- Existing `unittest` test modules under `tests/blockheat/` are collected and run by `pytest`.
- Shared fake Home Assistant test fixtures are defined in `tests/conftest.py`.

## Releases
Release metadata lives in three files and must stay in sync:

- `custom_components/blockheat/manifest.json`
- `homeassistant/custom_components/blockheat/manifest.json`
- `pyproject.toml`

Release flow:
1. Update the version in all three files in the release PR.
2. Merge that PR to `main`.
3. GitHub Actions reruns mirror sync, tests, formatting/lint, and mypy on `main`.
4. If everything passes, GitHub publishes release tag `vX.Y.Z` with autogenerated notes.

Important:
- If the three version files do not match, the release workflow fails.
- If `vX.Y.Z` already exists, the release workflow fails instead of silently skipping.
- Non-release merges to `main` must not reuse an already released version.

## Internal State Contract (v1)
The integration exposes policy/target state as read-only entities:

- `binary_sensor.blockheat_energy_saving_active`
- `sensor.blockheat_target_saving`
- `sensor.blockheat_target_comfort`
- `sensor.blockheat_target_final`

Legacy helper/boolean mappings (`target_boolean`, `target_*_helper`) are hidden from the
config UI and stripped from saved config/options on save. Runtime still seeds
from those legacy entities when no persisted internal state exists, to keep
existing installs migration-safe.

Compatibility events:
- `energy_saving_state_changed` (legacy compatibility)
- `blockheat_policy_changed` (namespaced event)
- `blockheat_snapshot` (diagnostics snapshot event)

## Migration / Cutover (Big-Bang)
Pre-cutover:
1. Backup current helper + automation YAML/state.
2. Run parity tests from this repo:
   - `uv run python -m pytest tests/blockheat/test_engine.py tests/blockheat/test_parity_suite.py -q`
3. Confirm config entry values map 1:1 to existing legacy automation inputs.

Cutover:
1. Disable all legacy Blockheat automations at once.
2. Enable the Blockheat config entry.
3. Verify helper writes and control number writes for at least one full periodic cycle.

Rollback:
1. Disable the Blockheat config entry.
2. Re-enable prior legacy automations.
3. No helper renaming is required.

## Known Non-Goals (v1)
- No control-logic redesign; behavior is parity-focused.
- No action-sequence hooks for enable/disable transitions.

## Diagnostics Card
A helper-driven diagnostics card is available at:
- `dashboards/blockheat/block-heat-diagnostics-card.yaml`

To use it:
1. Copy YAML into a Lovelace manual card or view YAML editor.
2. Replace placeholder entities where noted.

## Validation Matrix (Block Heat)
The table below is the acceptance matrix for manual verification in Home
Assistant Developer Tools by forcing helper/sensor states.

| Scenario | Expected | Status | Notes |
|---|---|---|---|
| Policy ON + outdoor >= warm threshold | `target_saving = virtual_temperature`, `target_final` matches | Pending manual run | Requires HA runtime |
| Policy ON + outdoor < warm threshold | `target_saving = setpoint - saving_cold_offset_c` | Pending manual run | Requires HA runtime |
| Policy OFF + comfort unsatisfied | `target_comfort = comfort path + boost` | Pending manual run | Requires HA runtime |
| Policy OFF + comfort satisfied + storage needs heat | `target_comfort = max(storage path, comfort path)` | Pending manual run | Requires HA runtime |
| Policy OFF + comfort satisfied + storage OK | `target_comfort = maintenance_target` | Pending manual run | Requires HA runtime |
| Extreme cold boost | `target_comfort` clamps at max | Pending manual run | Requires HA runtime |
| Extreme warm/low computed value | target clamps at min | Pending manual run | Requires HA runtime |
| Final target delta below deadband | no control write | Pending manual run | Requires HA runtime |
| Final target delta above deadband | control entity updated | Pending manual run | Requires HA runtime |

## Spreadsheet Simulation Workbook
The workbook `blockheat_scenarios_with_graphs.xlsx` contains a deterministic
timeline simulation of the Blockheat control chain.

- Purpose:
  - Validate how outdoor cooling affects room/storage temperatures and routing
    through saving, comfort, and final write-deadband logic.
- Editable sheet:
  - `Inputs` (parameters and per-day `energy_saving_override` toggles).
- Computed sheet:
  - `Simulation` (14-day formulas for thermal response, target selection,
    final target, and control-write behavior).
- Chart sheet:
  - `Graphs` (system overview trends for temperatures, targets/signals, binary
    policy/write states, and comfort deficit vs cold boost).

Default assumptions in the workbook:
- Outdoor profile is linear from `20 C` to `-20 C` over 14 days.
- Time step is daily (`1440` minutes).
- Thermal response uses moderate coefficients (room/storage coupling constants
  in `Inputs`).
