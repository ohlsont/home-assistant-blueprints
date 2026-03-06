# Task Plan: Fix Daikin Options Persistence and Add Live Config Diagnostics

## Goal
Reproduce the reported Daikin options persistence failure with a regression-first workflow, implement the minimum safe fix or diagnostic surface needed to explain it, and document the supported live-debug path.

## Current Phase
Phase 4

## Phases
### Phase 1: Root Cause Investigation
- [x] Inspect config flow, setup, runtime, and current tests
- [x] Confirm whether the options flow code looks internally consistent before editing
- [x] Identify gaps in the current test harness and runtime diagnostics
- **Status:** complete

### Phase 2: Regression And Diagnostics Tests
- [x] Add an options-flow-to-runtime regression test for Daikin enablement across reload
- [x] Add tests for service response payloads and `config_debug`
- [x] Run the targeted tests and record the first failure
- **Status:** complete

### Phase 3: Minimal Fix And Mirror Updates
- [x] Implement the minimum code change needed to satisfy the new tests
- [x] Mirror the same production changes into `homeassistant/custom_components/blockheat/`
- [x] Update `README.md` and service metadata if public behavior changed
- **Status:** complete

### Phase 4: Verification And Branch Hygiene
- [x] Run targeted tests, full tests, and coverage gate
- [ ] Commit with a conventional commit message
- [ ] Push the branch and update the open PR with verification notes
- **Status:** in_progress

## Key Questions
1. Can the current fake-HA harness reproduce the live persistence failure, or does it only prove that a saved `entry.options` would work?
2. If the regression does not fail locally, what diagnostic payload is missing that would let live HA confirm whether options were saved and merged into runtime config?
3. Can the existing service surface return diagnostics cleanly without adding new entities or config fields?
4. Do the docs need to explicitly describe the new service-response debugging path?

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Treat this as a root-cause exercise before writing fixes | The live symptom points to config persistence, but the code path itself is not obviously broken. |
| Keep Daikin compute logic out of scope unless a test proves persisted config still does not write | The compute rules already match the intended behavior and the user explicitly asked to avoid logic churn. |
| Add diagnostics on existing services instead of new entities | This keeps the public surface small and directly addresses the live-debug blind spot. |
| Reuse the current dedicated worktree/branch | The work is a direct follow-up on the same Blockheat remediation thread and the branch is already isolated. |
| Do not change the options-flow persistence code path | The new reload regression passes locally once `entry.options` is populated, so no repository evidence supports a persistence fix in `config_flow.py` or `async_setup_entry()`. |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| Local `uv run python` imports of `homeassistant.*` failed | 1 | Use the repository's fake-HA pytest harness rather than assuming Home Assistant is installed in the dev environment. |

## Notes
- Current code inspection shows `BlockheatOptionsFlow` returns `normalize_entry_data(current)` on the final step, and `async_setup_entry()` already merges `{**entry.data, **entry.options}`.
- The current local harness cannot model Home Assistant core's actual config-entry persistence layer; it can only simulate a config entry after options are already present.
- Existing services do not return data and the runtime snapshot does not currently expose raw/effective Daikin config, which explains why the live investigation had to infer state indirectly.
- The new in-repo regression demonstrates that once options are present on the config entry, reload plus recompute does issue the expected Daikin write. The implemented fix therefore focuses on visibility and service responses, not on rewriting the options flow.
