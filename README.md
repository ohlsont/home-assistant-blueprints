# Blockheat Home Assistant Blueprints

This repo contains Home Assistant automation blueprints for policy-driven heating.

## Folder Layout
- `blueprints/automation/blockheat/core/`
  - Block Heat modular control chain (target calculators, fallback manager, final writer).
- `blueprints/automation/blockheat/policy/`
  - Policy producer blueprints (shared energy-saving decision logic).
- `blueprints/automation/blockheat/consumers/`
  - Downstream policy consumers (Daikin and floor-heat control).

## YAML-First HA Setup (`configuration.yaml` + package)
If you want faster setup and reproducibility, use Home Assistant packages instead
of creating all helpers/automations in the UI.

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

## Blueprints
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

### Recommended Setup Order
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
  - boost = f(cold threshold, outdoor, slope, max)
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
| Policy OFF + comfort unsatisfied | `target_comfort = comfort path + boost` | Pending manual run | Requires HA runtime |
| Policy OFF + comfort satisfied + storage needs heat | `target_comfort = max(storage path, comfort path)` | Pending manual run | Requires HA runtime |
| Policy OFF + comfort satisfied + storage OK | `target_comfort = maintenance_target` | Pending manual run | Requires HA runtime |
| Extreme cold boost | `target_comfort` clamps at max | Pending manual run | Requires HA runtime |
| Extreme warm/low computed value | target clamps at min | Pending manual run | Requires HA runtime |
| Sustained below-target for fallback window | `fallback_active = on`, last trigger updated | Pending manual run | Requires HA runtime |
| Cooldown window not elapsed | fallback cannot re-arm | Pending manual run | Requires HA runtime |
| Recovery above release threshold | `fallback_active = off` | Pending manual run | Requires HA runtime |
| Final target delta below deadband | no control write | Pending manual run | Requires HA runtime |
| Final target delta above deadband | control entity updated | Pending manual run | Requires HA runtime |

## Local Structural Checks (This Repo Session)
- Added 4 Block Heat blueprints with isolated responsibilities.
- Final writer (`block-heat.yaml`) is the only Block Heat blueprint that calls
  `number.set_value` for the control number.
- Diagnostics card now reads helper/module outputs instead of re-implementing
  full control math.
