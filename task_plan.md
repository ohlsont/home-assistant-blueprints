# Task Plan: Integration-Only Repository Cleanup

## Goal
Remove legacy automation assets and outdated references so the repository is clearly integration-only.

## Current Phase
Phase 4

## Phases

### Phase 1: Discovery
- [x] Identify all legacy asset files to remove
- [x] Identify all repository references and outdated terminology
- [x] Confirm runtime integration code path remains unaffected
- **Status:** complete

### Phase 2: Planning
- [x] Define hard purge scope and explicit exceptions
- [x] Define verification commands and acceptance criteria
- [x] Confirm commit/PR/check workflow
- **Status:** complete

### Phase 3: Implementation
- [x] Delete legacy asset files
- [x] Rewrite product-facing documentation to integration-only guidance
- [x] Update project metadata and mirrored comments
- [x] Sanitize planning/history documents
- **Status:** complete

### Phase 4: Testing & Verification
- [ ] Run strict terminology audit
- [ ] Run format, lint, type, and test suite checks
- [ ] Validate removed files are absent
- **Status:** in_progress

### Phase 5: Delivery
- [ ] Commit with Conventional Commit message
- [ ] Open pull request with verification summary
- [ ] Monitor PR checks to completion
- **Status:** pending

## Key Decisions
| Decision | Rationale |
|----------|-----------|
| Hard purge of legacy assets | Prevent conflicting setup paths in the same repository |
| Keep manifest URLs unchanged | Canonical repository links remain valid |
| Preserve notes files while sanitizing wording | Keeps useful project history without outdated guidance |

## Notes
- Keep runtime behavior unchanged.
- Keep mirrored integration files in sync.
- Treat this as repository hygiene and documentation cleanup, not control-logic work.
