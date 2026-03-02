# Findings & Decisions

## Requirements
- Keep the repository integration-first and reduce confusion from legacy assets.
- Preserve runtime behavior and configuration schema for the current integration.
- Keep mirrored component code synchronized between the root integration path and Home Assistant mirror path.
- Preserve project notes files while removing outdated implementation terminology.
- Keep manifest documentation and issue URLs unchanged.

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| Remove legacy automation asset files from source control | Eliminates stale setup paths that conflict with current integration guidance |
| Keep integration runtime code intact | Cleanup is documentation/repository scope, not behavior scope |
| Rewrite README to integration-only setup | Prevents mixed migration guidance and improves onboarding |
| Sanitize historical planning files | Preserves useful history while removing outdated terminology |
| Keep manifest URLs as-is | URLs point to the canonical repository and are intentionally unchanged |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| Git branch creation denied in sandbox due shared `.git` lock path | Reran command with escalation and created dedicated `codex/` branch |

## Resources
- Documentation: `README.md`
- Integration package metadata: `custom_components/blockheat/manifest.json`
- Home Assistant mirror metadata: `homeassistant/custom_components/blockheat/manifest.json`
- System notes: `memory.md`

## Cleanup Notes
- Legacy automation assets are removed.
- Repository documentation now describes only the integration path.
- Validation should focus on static checks and test suite parity, since runtime behavior was not changed.
