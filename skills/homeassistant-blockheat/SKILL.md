---
name: homeassistant-blockheat
description: Edit and review Home Assistant YAML for the Blockheat project. Use when tasks involve creating, debugging, or refactoring files under blueprints/automation/blockheat/, homeassistant/packages/, homeassistant/configuration snippets, or dashboards/blockheat/, especially when validating helper contracts, routing precedence, and placeholder entity wiring.
---

# Home Assistant Blockheat

## Overview

Implement safe, minimal YAML changes for Blockheat automations and package wiring. Favor deterministic repository edits over speculative runtime advice.

## Quick Start

1. Identify request scope: blueprint logic, package wiring, diagnostics card, or setup docs.
2. Read `references/repo-map.md` for file routing and helper contracts.
3. Inspect only impacted files plus directly-related upstream/downstream modules.
4. Apply narrow edits that preserve established YAML style and entity naming.
5. Validate statically where possible, then provide explicit manual runtime checks for Home Assistant.

## Workflow

### 1. Classify the task

Classify requests into one or more categories:
- Blueprint behavior change in `blueprints/automation/blockheat/...`.
- Package/setup wiring in `homeassistant/...`.
- Dashboard diagnostics update in `dashboards/blockheat/...`.
- Documentation update in `README.md` when behavior or required inputs change.

### 2. Gather only required context

Load these in order:
1. Target files from the request.
2. `references/repo-map.md` for helper/entity contracts.
3. Adjacent blueprint modules when precedence or helper writes are involved.

Avoid full-repo reads unless the request spans multiple modules.

### 3. Edit with safety rules

Apply these rules on every change:
- Keep one writer per output entity when architecture expects single-writer behavior.
- Keep helper entity ids stable unless the user explicitly requests a migration.
- Preserve clamp/deadband/hysteresis semantics unless asked to change control behavior.
- Keep placeholders (`REPLACE_*`) explicit in templates; never silently hardcode site-specific ids.
- Prefer additive defaults and backward-compatible inputs.

### 4. Validate before handoff

Perform lightweight checks:
- YAML parse sanity for changed files (if lint tooling is unavailable).
- Quick scan that trigger/condition/action blocks still align with updated inputs.
- Confirm README/setup instructions are updated when behavior or inputs changed.

If runtime validation is required, provide a short matrix of manual HA checks instead of guessing outcomes.

## Request Patterns

Handle common requests with this playbook:
- "Tune comfort/saving behavior": update target calculators and note helper/output impact.
- "Fix fallback flapping": adjust fallback manager timing or thresholds and mention regression risks.
- "Add input to blueprint": add blueprint input, wire it through logic, and document required helper/entity changes.
- "YAML-first install help": edit package/snippet files and keep README setup steps synchronized.

## MCP and Runtime Notes

If Home Assistant runtime tools are available, use them for read-only verification and state checks. If runtime tools are unavailable, stay repository-first and clearly separate:
- What was statically verified in code.
- What must be validated inside a live Home Assistant instance.
