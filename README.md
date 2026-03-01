# Blockheat Home Assistant Integration

This repo now ships a custom Home Assistant integration for policy-driven heating,
plus legacy blueprint references.

## Folder Layout
- `custom_components/blockheat/`
  - HACS-compatible integration path (`config_flow`, runtime adapter, pure Python engine).
- `homeassistant/custom_components/blockheat/`
  - Local development/testing mirror of the integration code.
- `blueprints/automation/blockheat/core/`
  - Legacy Block Heat core blueprint chain (reference only during migration).
- `blueprints/automation/blockheat/policy/`
  - Legacy policy producer blueprint (reference).
- `blueprints/automation/blockheat/consumers/`
  - Legacy consumer blueprints (reference).

## Primary Path: Custom Integration (Config Entry UI)
The recommended runtime is now `custom_components/blockheat` with one config
entry that owns policy, target calculators, final writer, and optional
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
operation, `22°C` comfort target, and reduced risk of auxiliary electric heat.

| Section | Defaults |
|---|---|
| Policy window and guards | `minutes_to_block=180`, `price_ignore_below=0.6`, `pv_ignore_above_w=0.0`, `min_toggle_interval_min=15` |
| Saving target | `heatpump_setpoint=20.0`, `saving_cold_offset_c=1.0`, `virtual_temperature=20.0`, `energy_saving_warm_shutdown_outdoor=8.0` |
| Comfort target | `comfort_target_c=22.0`, `comfort_to_heatpump_offset_c=2.0`, `storage_target_c=24.5`, `storage_to_heatpump_offset_c=2.0`, `maintenance_target_c=20.0`, `comfort_margin_c=0.25` |
| Cold boost | `cold_threshold=1.0`, `max_boost=3.0`, `boost_slope_c=4.0` |
| Limits and deadbands | `control_min_c=10.0`, `control_max_c=26.0`, `saving_helper_write_delta_c=0.05`, `comfort_helper_write_delta_c=0.05`, `final_helper_write_delta_c=0.05`, `control_write_delta_c=0.2` |
| Optional Daikin | `daikin_normal_temperature=22.0`, `daikin_saving_temperature=20.0`, `daikin_outdoor_temp_threshold=-10.0`, `daikin_min_temp_change=0.5` |

Quick adjustment rails:
- Policy strength: raise `minutes_to_block` to `210-240` for stronger savings, or lower to `120-150` for comfort-first behavior.
- Saving aggressiveness: reduce `saving_cold_offset_c` to `0.5-0.8` if rooms dip too much, or increase to `1.2-1.5` for stronger savings.
- Comfort tightness: lower `comfort_margin_c` to `0.15-0.2` for tighter control, or increase to `0.3` to reduce churn.
- Cold-weather response: lower `boost_slope_c` to `3.0` for stronger recovery, or raise to `5.0-6.0` if too aggressive.
- Write frequency: increase `control_write_delta_c` to `0.25-0.3` only if control writes are too frequent.

### Testing
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

### Internal State Contract (v1)
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

### Migration / Cutover (Big-Bang)
Pre-cutover:
1. Backup current helper + automation YAML/state.
2. Run parity tests from this repo:
   - `uv run python -m pytest tests/blockheat/test_engine.py tests/blockheat/test_parity_suite.py -q`
3. Confirm config entry values map 1:1 to existing blueprint inputs.

Cutover:
1. Disable all Blockheat blueprint automations at once.
2. Enable the Blockheat config entry.
3. Verify helper writes and control number writes for at least one full periodic cycle.

Rollback:
1. Disable the Blockheat config entry.
2. Re-enable prior blueprint automations.
3. No helper renaming is required.

### Known Non-Goals (v1)
- No control-logic redesign; behavior is parity-focused.
- No action-sequence hooks equivalent to blueprint `on_enable_actions` / `on_disable_actions`.

## Legacy Path: YAML-First Blueprints (`configuration.yaml` + package)
If you want faster setup and reproducibility, use Home Assistant packages instead
of creating helpers/automations in the UI. This remains available as a legacy
reference path during migration.

### Files in this repo for YAML-first setup
- `homeassistant/configuration.yaml.packages-snippet.yaml`
  - Snippet to enable packages in `/config/configuration.yaml`.
- `homeassistant/packages/blockheat_modular.yaml`
  - Authoritative helper + automation package using blueprint paths under
    `blockheat/{core,policy,consumers}`.

### Quick copy commands (run from this repo)
```bash
cp -R blueprints/automation/blockheat /config/blueprints/automation/
mkdir -p /config/packages
cp homeassistant/packages/blockheat_modular.yaml /config/packages/blockheat_modular.yaml
```

### `configuration.yaml` wiring
Add this under the existing top-level `homeassistant:` block in
`/config/configuration.yaml`:
```yaml
packages: !include_dir_named packages
```
If `homeassistant:` does not exist, use the full snippet from:
`homeassistant/configuration.yaml.packages-snippet.yaml`.

### Required placeholder replacement before reload
In `/config/packages/blockheat_modular.yaml`, replace all `REPLACE_*` entities,
especially:
- `input_boolean.REPLACE_energy_saving`
- `sensor.REPLACE_nordpool_price`
- `sensor.REPLACE_outdoor_temperature`
- `sensor.REPLACE_comfort_room_1`
- `sensor.REPLACE_comfort_room_2`
- `sensor.REPLACE_storage_room`
- `number.REPLACE_control_temperature`

Optional consumer placeholders are in commented blocks for Daikin.

## Legacy Blueprints (Reference)
- `blueprints/automation/blockheat/core/block-heat-target-saving.yaml`
  - Saving-mode target calculator for Block Heat.
  - Writes to `input_number` saving-target helper.
- `blueprints/automation/blockheat/core/block-heat-target-comfort.yaml`
  - Comfort-mode target calculator for Block Heat.
  - Writes to `input_number` comfort-target helper.
- `blueprints/automation/blockheat/core/block-heat.yaml`
  - Final arbiter/writer for Block Heat.
  - Reads helper outputs and is the only module writing the control `number`.
- `blueprints/automation/blockheat/consumers/daikin-energy-saver.yaml`
  - Direct Daikin climate control driven by the policy boolean.
- `blueprints/automation/blockheat/policy/energy_saving_policy_bool.yaml`
  - Produces shared energy-saving policy boolean from price/PV inputs.

## Block Heat Architecture (Modular)
Block Heat is now split into three independent automations:

1. Saving target calculator (`block-heat-target-saving.yaml`)
2. Comfort target calculator (`block-heat-target-comfort.yaml`)
3. Final arbiter and writer (`block-heat.yaml`)

The final arbiter applies this precedence:
- Policy ON -> use saving target helper
- Policy OFF -> use comfort target helper

Only the final arbiter writes the control number.

### Canonical Helper Contract
Use these helper entity ids unless you have an existing naming convention:

- `input_number.block_heat_target_saving`
- `input_number.block_heat_target_comfort`
- `input_number.block_heat_target_final`

### Recommended Setup Order (Legacy Blueprint Path)
1. Create helper entities listed above.
2. Create automation from `blueprints/automation/blockheat/core/block-heat-target-saving.yaml`.
3. Create automation from `blueprints/automation/blockheat/core/block-heat-target-comfort.yaml`.
4. Create automation from `blueprints/automation/blockheat/core/block-heat.yaml` (final arbiter/writer).
5. Verify all helper entities are updated before checking control-number writes.

## Block Heat Module Behavior

### Saving Target Calculator
- Inputs: policy boolean, outdoor temperature, setpoint, `saving_cold_offset_c`, warm shutdown threshold, virtual temperature.
- Formula:
  - outdoor >= warm shutdown -> target = virtual temperature
  - otherwise -> target = setpoint - saving cold offset
- Output: writes clamped target to saving helper.

### Comfort Target Calculator
- Inputs: two comfort sensors, storage sensor, outdoor sensor, comfort/storage/maintenance settings, cold boost settings.
- Formula:
  - boost (pull-down) = f(cold threshold, outdoor, slope, max)
  - comfort path = `(comfort_target - comfort_offset) - boost`
  - storage path = `(storage_target - storage_offset) - boost`
  - comfort unsatisfied -> comfort path
  - comfort satisfied + storage needs heat -> max(storage path, comfort path)
  - comfort satisfied + storage OK -> maintenance target
- Output: writes clamped target to comfort helper.

### Final Arbiter and Writer
- Reads policy boolean + helper targets.
- Applies precedence and final clamp.
- Writes final helper target.
- Writes control number only when delta >= configured write threshold.

## Diagnostics Card
A helper-driven diagnostics card is available at:
- `dashboards/blockheat/block-heat-diagnostics-card.yaml`

The markdown card reads helper outputs and state routing directly from the final
arbiter inputs. It does not duplicate target formulas.

To use it:
1. Copy YAML into a Lovelace manual card or view YAML editor.
2. Replace `auto` in the markdown card with your final arbiter automation id.
3. Replace placeholder entities in ApexCharts/entities card where noted.

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
- Outdoor profile is linear from `20°C` to `-20°C` over 14 days.
- Time step is daily (`1440` minutes).
- Thermal response uses moderate coefficients (room/storage coupling constants
  in `Inputs`).

## Local Structural Checks (This Repo Session)
- Added 3 Block Heat blueprints with isolated responsibilities.
- Final writer (`block-heat.yaml`) is the only Block Heat blueprint that calls
  `number.set_value` for the control number.
- Diagnostics card now reads helper/module outputs instead of re-implementing
  full control math.
