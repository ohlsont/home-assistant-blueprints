# Blockheat Repository Map

Use this file to quickly locate the right module before editing.

## Blueprint Modules

- `blueprints/automation/blockheat/core/block-heat-target-saving.yaml`
  - Computes saving-mode target and writes saving helper target.
- `blueprints/automation/blockheat/core/block-heat-target-comfort.yaml`
  - Computes comfort-mode target and writes comfort helper target.
- `blueprints/automation/blockheat/core/block-heat-fallback-manager.yaml`
  - Manages electric fallback state and fallback last-trigger timestamp.
- `blueprints/automation/blockheat/core/block-heat.yaml`
  - Final arbiter/writer; reads policy and helper outputs, writes final target and control number.

## Policy and Consumers

- `blueprints/automation/blockheat/policy/energy_saving_policy_bool.yaml`
  - Produces policy boolean used by core and consumer automations.
- `blueprints/automation/blockheat/consumers/daikin-energy-saver.yaml`
  - Consumer of policy boolean for Daikin control.
- `blueprints/automation/blockheat/consumers/floor_heat_top_minutes_with_schedule.yaml`
  - Consumer of policy boolean for floor-heat runtime shaping.

## YAML-First Setup Files

- `homeassistant/configuration.yaml.packages-snippet.yaml`
  - Snippet for enabling packages in Home Assistant configuration.
- `homeassistant/packages/blockheat_modular.yaml`
  - Package-based helper and automation setup, including `REPLACE_*` placeholders.

## Dashboard

- `dashboards/blockheat/block-heat-diagnostics-card.yaml`
  - Diagnostics card for helper/routing observability.

## Canonical Helper Contract

Preserve these defaults unless migrating explicitly:
- `input_number.block_heat_target_saving`
- `input_number.block_heat_target_comfort`
- `input_number.block_heat_target_final`
- `input_boolean.block_heat_fallback_active`
- `input_datetime.block_heat_fallback_last_trigger`

## Editing Heuristics

- Keep final writer responsibility centralized in `core/block-heat.yaml`.
- Update README when behavior or required inputs change.
- Keep placeholders explicit in package templates.
