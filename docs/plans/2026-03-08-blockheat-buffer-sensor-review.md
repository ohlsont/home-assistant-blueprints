# Blockheat Buffer Sensor Review Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Clarify the existing `storage_room_sensor` input as the preferred system-energy/buffer sensor and document how to validate a direct pipe-temperature sensor without changing runtime behavior or public interfaces.

**Architecture:** Keep the current Blockheat runtime and config schema unchanged. Update config-flow copy and README guidance so users understand that the storage input can be a hydronic buffer proxy, especially a direct pipe-temperature sensor, and add a focused test that locks the new copy in place.

**Tech Stack:** Python, pytest, Home Assistant integration translation JSON, Markdown docs

---

### Task 1: Lock the copy requirement with a test

**Files:**
- Modify: `tests/test_translation_coverage.py`

**Step 1: Write the failing test**
- Add an assertion that both config and options copy for `storage_room_sensor` mention `Buffer`, `pipe temperature`, and `system energy`.

**Step 2: Run test to verify it fails**
- Run: `uv run python -m pytest tests/test_translation_coverage.py -q`
- Expected: fail because the current label and description still say `Storage room sensor`.

### Task 2: Update onboarding copy in component and mirror files

**Files:**
- Modify: `custom_components/blockheat/strings.json`
- Modify: `custom_components/blockheat/translations/en.json`
- Modify: `homeassistant/custom_components/blockheat/strings.json`
- Modify: `homeassistant/custom_components/blockheat/translations/en.json`

**Step 1: Write minimal implementation**
- Change the `storage_room_sensor` label to describe a buffer/storage sensor.
- Change the description to prefer a direct pipe-temperature sensor as a system-energy proxy while keeping storage tank/storage room usage valid.

**Step 2: Run the focused test**
- Run: `uv run python -m pytest tests/test_translation_coverage.py -q`
- Expected: pass.

### Task 3: Update README guidance

**Files:**
- Modify: `README.md`

**Step 1: Add minimal doc updates**
- Clarify in installation/onboarding guidance that the storage input is best treated as a system-energy/buffer signal.
- Add validation guidance for trying a direct washroom pipe-temperature sensor in that slot.

**Step 2: Run docs-adjacent verification**
- Run: `uv run python -m pytest tests/test_translation_coverage.py tests/test_mirror_sync.py -q`
- Expected: pass.

### Task 4: Final verification and delivery

**Files:**
- Modify: `README.md`
- Modify: `custom_components/blockheat/strings.json`
- Modify: `custom_components/blockheat/translations/en.json`
- Modify: `homeassistant/custom_components/blockheat/strings.json`
- Modify: `homeassistant/custom_components/blockheat/translations/en.json`
- Modify: `tests/test_translation_coverage.py`

**Step 1: Run relevant verification**
- Run: `uv run python -m pytest tests/test_translation_coverage.py tests/test_mirror_sync.py tests/blockheat/test_config_flow.py -q`
- Expected: pass.

**Step 2: Commit**
- Run:
```bash
git add README.md docs/plans/2026-03-08-blockheat-buffer-sensor-review.md tests/test_translation_coverage.py custom_components/blockheat/strings.json custom_components/blockheat/translations/en.json homeassistant/custom_components/blockheat/strings.json homeassistant/custom_components/blockheat/translations/en.json
git commit -m "docs(blockheat): clarify buffer sensor guidance"
```
