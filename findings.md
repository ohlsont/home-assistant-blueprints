# Findings & Decisions

## Requirements
- Reproduce the Daikin options persistence failure with a regression-first workflow.
- Fix the options/config path only if the new regression proves it is broken in-repo.
- Add diagnostics to the existing `blockheat.recompute` and `blockheat.dump_diagnostics` services so live config state is inspectable without guessing.
- Update the README and mirror integration tree for any public behavior changes.

## Research Findings
- `BlockheatOptionsFlow` currently returns `async_create_entry(title=\"\", data=normalize_entry_data(current))` after the final tuning step.
- `async_setup_entry()` already constructs runtime config as `{**entry.data, **entry.options}` before instantiating `BlockheatRuntime`.
- `BlockheatRuntime._async_apply_daikin()` only skips Daikin writes when the consumer is disabled, the climate entity is missing, or the engine decides no temperature write is needed.
- Given the live state that was observed earlier (`policy off`, Daikin climate target `19`, default normal temperature `22`), runtime would have issued a `climate.set_temperature` call if `enable_daikin_consumer` had been present in effective config.
- The current pytest harness uses fake Home Assistant modules from `tests/conftest.py`; it can simulate a config entry with options, but it does not simulate Home Assistant core's real options-flow persistence machinery.
- A new integration-level regression now proves that when an options-flow result is applied to `entry.options`, then reloaded, then recomputed, Blockheat writes the expected Daikin target. That means the repository code path is internally consistent once options are actually present.
- Existing tests cover:
  - config-flow step routing and saved payload shape
  - runtime Daikin write behavior when config is already enabled
  - service registration and basic recompute dispatch
- Existing tests do not cover:
  - options flow completion plus config-entry reload plus runtime write
  - service response payloads
  - runtime snapshots exposing raw/effective Daikin config
- Existing services are fire-and-forget only. They do not return diagnostics, and `services.yaml` documents no response payloads.

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| Add the end-to-end-ish regression anyway, even if the harness may not reproduce the live issue | It proves whether the integration code path is internally consistent and prevents future regressions once diagnostics are added. |
| Expand the runtime snapshot with `config_debug` instead of adding a new entity | The coordinator already stores snapshots and the services already trigger recompute/diagnostics paths. |
| Make service responses optional and keyed by entry id | This preserves current behavior for normal use while enabling targeted live inspection. |
| Keep the fix minimal and focused on visibility because the persistence bug did not reproduce locally | The new regression shows the current repository code behaves correctly when `entry.options` are populated, so the immediate blocker is live visibility into saved vs effective config. |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| No actual Home Assistant package is importable in the repo dev environment | Use the fake-HA pytest environment and adapt tests there. |
| The fake service layer does not currently support response payloads | Extend the fake harness only as needed for the new service tests. |

## Resources
- Config flow: `custom_components/blockheat/config_flow.py`
- Setup/services: `custom_components/blockheat/__init__.py`
- Runtime snapshot path: `custom_components/blockheat/runtime.py`
- Fake HA harness: `tests/conftest.py`
- Service docs: `custom_components/blockheat/services.yaml`
- Public docs: `README.md`
