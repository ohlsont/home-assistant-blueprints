---
name: homeassistant-blockheat
description: Edit and review the Blockheat Home Assistant custom integration. Use when tasks involve creating, debugging, or refactoring files under custom_components/blockheat/ (or its homeassistant/ mirror), dashboards/blockheat/, or configuration flow and engine logic, especially when validating helper contracts, routing precedence, and sensor/control entity wiring.
---

# Home Assistant Blockheat

## Overview

Implement safe, minimal changes for the Blockheat custom integration. Favor deterministic repository edits over speculative runtime advice.

## Quick Start

1. Identify request scope: engine logic, runtime adapter, config flow, dashboard, or documentation.
2. Read `references/repo-map.md` for file routing and helper contracts.
3. Inspect only impacted files plus directly-related upstream/downstream modules.
4. Apply narrow edits that preserve established code style and entity naming.
5. Keep both directory mirrors in sync (`custom_components/blockheat/` and `homeassistant/custom_components/blockheat/`).
6. Validate with tests and linting, then provide explicit manual runtime checks for Home Assistant.

## Workflow

### 1. Classify the task

Classify requests into one or more categories:
- Engine/computation change in `engine.py`.
- Runtime/HA adapter change in `runtime.py` or `coordinator.py`.
- Config flow or validation change in `config_flow.py` / `validation.py`.
- Dashboard diagnostics update in `dashboards/blockheat/...`.
- Documentation update in `README.md` when behavior or required inputs change.

### 2. Gather only required context

Load these in order:
1. Target files from the request.
2. `references/repo-map.md` for helper/entity contracts.
3. Adjacent modules when precedence or helper writes are involved.

Avoid full-repo reads unless the request spans multiple modules.

### 3. Edit with safety rules

Apply these rules on every change:
- Keep one writer per output entity when architecture expects single-writer behavior.
- Keep helper entity ids stable unless the user explicitly requests a migration.
- Preserve clamp/deadband/hysteresis semantics unless asked to change control behavior.
- Prefer additive defaults and backward-compatible inputs.
- Update both directory mirrors for any integration code change.

### 4. Validate before handoff

Perform lightweight checks:
- Run `uv run python -m pytest tests -q` to verify tests pass.
- Run `uv run ruff check` and `uv run ruff format --check` for lint/format.
- Confirm README/setup instructions are updated when behavior or inputs changed.

If runtime validation is required, provide a short matrix of manual HA checks instead of guessing outcomes.

## Request Patterns

Handle common requests with this playbook:
- "Tune comfort/saving behavior": update engine target calculators and note helper/output impact.
- "Fix control flapping": adjust timing, thresholds, or deadband in engine/runtime and mention regression risks.
- "Add config parameter": add to `const.py`, wire through `config_flow.py`, `engine.py`, and `runtime.py`; update both mirrors.
- "Change Daikin behavior": update `compute_daikin` in engine and Daikin runtime logic.

## MCP and Runtime Notes

If Home Assistant runtime tools are available, use them for read-only verification and state checks. If runtime tools are unavailable, stay repository-first and clearly separate:
- What was statically verified in code.
- What must be validated inside a live Home Assistant instance.
