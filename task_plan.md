# Task Plan: Block Heat diagnostics dashboard card

## Goal
Create a Home Assistant dashboard diagnostics card for the Block Heat blueprint, with clear computed feedback for screenshots, and document how to use it.

## Current Phase
Phase 4

## Phases

### Phase 1: Requirements & Discovery
- [x] Confirm desired output (dashboard card for diagnostics)
- [x] Review blueprint inputs and logic for derived values
- [x] Document findings in findings.md
- **Status:** complete

### Phase 2: Planning & Structure
- [x] Define diagnostics metrics and layout
- [x] Decide where to store card YAML
- [x] Document decisions with rationale
- **Status:** complete

### Phase 3: Implementation
- [x] Create diagnostics card YAML
- [x] Add README instructions and usage notes
- [x] Keep changes minimal and focused
- **Status:** complete

### Phase 4: Testing & Verification
- [x] Manual review of formulas against blueprint
- [x] Document verification notes in progress.md
- **Status:** complete

### Phase 5: Delivery
- [x] Summarize changes and next steps
- **Status:** complete

## Key Questions
1. Where should the diagnostics card live? (New YAML under blueprints/automation/blockheat/)
2. Should we avoid custom Lovelace cards? (Yes, use built-in markdown/entities)
3. What automation entity id will be used? (User will replace placeholder)

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Use markdown card templates for computed values | Built-in HA capability, no custom cards |
| Provide entity list as placeholders | Entities card does not accept templates |
| Store card YAML under dashboards/ | Keeps blueprint folder clean and intent clear |
| Read blueprint inputs from `blueprint_input` | Keeps card in sync with automation setup |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| rg not available in shell | 1 | Used grep instead |

## Notes
- Update phase status as you progress: pending → in_progress → complete
- Re-read this plan before major decisions (attention manipulation)
- Log ALL errors - they help avoid repetition
