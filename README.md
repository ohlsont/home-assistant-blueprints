# Blockheat Home Assistant Integration

This repo now ships a custom Home Assistant integration for policy-driven heating,
plus legacy blueprint references.

## Codex Thread Workflow (Required)
To keep agent work isolated and fast, use this workflow for every thread:
1. Create a dedicated worktree and branch before changing files.
2. Use branch names with the `codex/` prefix.
3. Complete implementation and verification in that worktree.
4. Commit and open a PR before considering the thread complete.
5. Monitor PR CI/checks until they pass (or explicitly note if no checks are configured).
6. Before closing the thread, check whether behavior/input changes require documentation updates and apply them.

Example setup:
```bash
git worktree add .worktrees/codex/<topic> -b codex/<topic>
cd .worktrees/codex/<topic>
```

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
entry that owns policy, target calculators, fallback, final writer, and optional
Daikin/floor consumers.

### Install via HACS (GitHub)
1. Open HACS -> Integrations -> three-dot menu -> Custom repositories.
2. Add this repository URL as type **Integration**.
3. Search for **Blockheat** in HACS and install it.
4. Restart Home Assistant.
5. Go to **Settings -> Devices & Services -> Add Integration** and add **Blockheat**.
6. Complete both config steps:
   - Step 1: entity mapping with searchable, domain-filtered entity pickers (policy sensors/helpers/control + optional consumers)
   - Step 2: tuning values (policy windows, target/fallback thresholds, deadbands)

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
   - Step 1: entity mapping with searchable, domain-filtered entity pickers (policy sensors/helpers/control + optional consumers)
   - Step 2: tuning values (policy windows, target/fallback thresholds, deadbands)

### Runtime Behavior (Current Integration)
- The config flow is single-instance: only one `blockheat` config entry is supported.
- Recompute runs on:
  - Home Assistant startup
  - Any state change on mapped required/optional entities
  - A periodic 5-minute interval (`DEFAULT_RECOMPUTE_MINUTES = 5`)
- Recompute always updates the diagnostics coordinator payload and fires `blockheat_snapshot`.
- Policy transitions also fire:
  - `energy_saving_state_changed`
  - `blockheat_policy_changed`

### Integration Services
Services are exposed under the `blockheat` domain:
- `blockheat.recompute`
  - Forces an immediate full compute/write pass.
- `blockheat.dump_diagnostics`
  - Forces recompute and emits a diagnostics snapshot payload.

Both services accept optional `entry_id` (text). If omitted, all Blockheat entries are targeted.

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

Mirror sync guard:
- Run `uv run python scripts/check_component_mirror_sync.py` to verify that
  `custom_components/blockheat` and `homeassistant/custom_components/blockheat`
  are byte-identical when the mirror directory exists.

Config tuning validation:
- The config entry tuning step enforces bounded numeric ranges and rejects
  invalid cross-field combinations such as `control_min_c > control_max_c`.

### Compatibility Contract (v1)
The integration keeps these helper ids as the stable interface:

- `input_number.block_heat_target_saving`
- `input_number.block_heat_target_comfort`
- `input_number.block_heat_target_final`
- `input_boolean.block_heat_fallback_active`
- `input_datetime.block_heat_fallback_last_trigger`

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

Optional consumer placeholders are in commented blocks for Daikin and floor heat.

## Legacy Blueprints (Reference)
- `blueprints/automation/blockheat/core/block-heat-target-saving.yaml`
  - Saving-mode target calculator for Block Heat.
  - Writes to `input_number` saving-target helper.
- `blueprints/automation/blockheat/core/block-heat-target-comfort.yaml`
  - Comfort-mode target calculator for Block Heat.
  - Writes to `input_number` comfort-target helper.
- `blueprints/automation/blockheat/core/block-heat-fallback-manager.yaml`
  - Electric assist fallback state manager.
  - Writes to fallback `input_boolean` and last-trigger `input_datetime`.
- `blueprints/automation/blockheat/core/block-heat.yaml`
  - Final arbiter/writer for Block Heat.
  - Reads helper outputs and is the only module writing the control `number`.
- `blueprints/automation/blockheat/consumers/daikin-energy-saver.yaml`
  - Direct Daikin climate control driven by the policy boolean.
- `blueprints/automation/blockheat/policy/energy_saving_policy_bool.yaml`
  - Produces shared energy-saving policy boolean from price/PV/floor inputs.
- `blueprints/automation/blockheat/consumers/floor_heat_top_minutes_with_schedule.yaml`
  - Floor heat control driven by policy boolean and optional comfort schedule.

## Block Heat Architecture (Modular)
Block Heat is now split into four independent automations:

1. Saving target calculator (`block-heat-target-saving.yaml`)
2. Comfort target calculator (`block-heat-target-comfort.yaml`)
3. Fallback manager (`block-heat-fallback-manager.yaml`)
4. Final arbiter and writer (`block-heat.yaml`)

The final arbiter applies this precedence:
- Policy ON -> use saving target helper
- Policy OFF and fallback active -> force control minimum
- Policy OFF and fallback inactive -> use comfort target helper

Only the final arbiter writes the control number.

### Canonical Helper Contract
Use these helper entity ids unless you have an existing naming convention:

- `input_number.block_heat_target_saving`
- `input_number.block_heat_target_comfort`
- `input_number.block_heat_target_final`
- `input_boolean.block_heat_fallback_active`
- `input_datetime.block_heat_fallback_last_trigger`

### Recommended Setup Order (Legacy Blueprint Path)
1. Create helper entities listed above.
2. Create automation from `blueprints/automation/blockheat/core/block-heat-target-saving.yaml`.
3. Create automation from `blueprints/automation/blockheat/core/block-heat-target-comfort.yaml`.
4. Create automation from `blueprints/automation/blockheat/core/block-heat-fallback-manager.yaml`.
5. Create automation from `blueprints/automation/blockheat/core/block-heat.yaml` (final arbiter/writer).
6. Verify all helper entities are updated before checking control-number writes.

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

### Fallback Manager
- Activation (turn ON fallback boolean):
  - policy OFF
  - coldest comfort room below `(comfort_target - electric_fallback_delta_c)`
    for `electric_fallback_minutes`
  - cooldown satisfied since `block_heat_fallback_last_trigger`
- Deactivation:
  - policy ON, or
  - coldest comfort room recovers above `(comfort_target - release_delta_c)`

### Final Arbiter and Writer
- Reads policy boolean + fallback boolean + helper targets.
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
| Policy OFF + comfort unsatisfied | `target_comfort = comfort path` | Pending manual run | Requires HA runtime |
| Policy OFF + comfort satisfied + storage needs heat | `target_comfort = max(storage path, comfort path)` | Pending manual run | Requires HA runtime |
| Policy OFF + comfort satisfied + storage OK | `target_comfort = maintenance_target` | Pending manual run | Requires HA runtime |
| Extreme cold boost | `target_comfort` clamps at max | Pending manual run | Requires HA runtime |
| Extreme warm/low computed value | target clamps at min | Pending manual run | Requires HA runtime |
| Sustained below-target for fallback window | `fallback_active = on`, last trigger updated | Pending manual run | Requires HA runtime |
| Cooldown window not elapsed | fallback cannot re-arm | Pending manual run | Requires HA runtime |
| Recovery above release threshold | `fallback_active = off` | Pending manual run | Requires HA runtime |
| Final target delta below deadband | no control write | Pending manual run | Requires HA runtime |
| Final target delta above deadband | control entity updated | Pending manual run | Requires HA runtime |

## Spreadsheet Simulation Workbook
The workbook `blockheat_scenarios_with_graphs.xlsx` contains a deterministic
timeline simulation of the Blockheat control chain.

- Purpose:
  - Validate how outdoor cooling affects room/storage temperatures and routing
    through saving, comfort, fallback, and final write-deadband logic.
- Editable sheet:
  - `Inputs` (parameters and per-day `energy_saving_override` toggles).
- Computed sheet:
  - `Simulation` (14-day formulas for thermal response, target selection,
    fallback activation/release, final target, and control-write behavior).
- Chart sheet:
  - `Graphs` (system overview trends for temperatures, targets/signals, binary
    policy/fallback/write states, and comfort deficit vs cold boost).

Default assumptions in the workbook:
- Outdoor profile is linear from `20°C` to `-20°C` over 14 days.
- Time step is daily (`1440` minutes).
- Thermal response uses moderate coefficients (room/storage coupling constants
  in `Inputs`).

## Local Structural Checks (This Repo Session)
- Added 4 Block Heat blueprints with isolated responsibilities.
- Final writer (`block-heat.yaml`) is the only Block Heat blueprint that calls
  `number.set_value` for the control number.
- Diagnostics card now reads helper/module outputs instead of re-implementing
  full control math.
