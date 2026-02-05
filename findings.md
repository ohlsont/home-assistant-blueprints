# Findings & Decisions

## Requirements
- Update block-heat blueprint to support two comfort rooms (min-of-rooms reference).
- Add storage/buffer room sensor with cap (default 25 C), not used for maintenance gating.
- Maintain comfort target (default 22 C) until both comfort rooms are satisfied.
- Add comfort-to-heatpump offset input (default 2 C).
- Add storage-to-heatpump offset input (default 2 C).
- Drop to maintenance target (default 20 C) when comfort rooms satisfied.
- Enforce maintenance minimum (default 19 C) unless electric assist is allowed.
- Add optional electric assist fallback after 30 minutes below target by 0.5 C, allow min 18 C.
- Electric assist fallback should always be allowed; remove toggle.
- Enforce electric assist cooldown using input_datetime helper (no delay-based cooldown).
- Allow storage room target to drive heating when comfort rooms are satisfied.
- Keep Energy Saving Policy override behavior unchanged.
- Update README.md with new topology, behavior, and defaults.
- Persist system notes in memory.md.

## Research Findings
- Qvantum ETK manual notes external room sensor option uses PT100; Ohmigo emulates PT100.
- Manual notes increases to compressor-affecting values are delayed (~3 minutes), decreases immediate; keep 5-minute update interval.

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| Min-of-rooms comfort reference | Keeps coldest comfort room on target |
| Storage cap does not gate comfort | Prevents comfort rooms from staying cold |
| Fixed offset input for heatpump target | Keeps heatpump value aligned with comfort target |
| Electric assist fallback optional | Allows compressor-only operation by default |
| Template trigger for fallback | Leverages built-in duration trigger in automation |
| Cooldown enforced via input_datetime | Avoids restart-mode canceling delay |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| uv run python session-catchup cache permission error | Reran command with escalation |

## Resources
- Qvantum ETK manual: https://www.qvantum.com/wp-content/uploads/2023/09/Qvantum-ETK-Manual.pdf
- Blueprint file: blueprints/automation/blockheat/block-heat.yaml
- Documentation: README.md
- System notes: memory.md

## Diagnostics Card Findings
- Blueprint inputs are available on the automation entity via the `blueprint_input` attribute.
- Lovelace markdown cards can render Jinja templates, which lets us compute diagnostics inline.
- Entities cards do not accept templates for entity ids, so the entity list must be manually filled in.
- Prefer built-in cards over custom cards to reduce setup friction.

## Visual/Browser Findings
- Manual specifies PT100 external room sensor wiring and notes compressor value increases are delayed (~3 min) while decreases are immediate.
