# Findings & Decisions

## Requirements
- Update block-heat blueprint to support two comfort rooms (min-of-rooms reference).
- Add storage/buffer room sensor with cap (default 25 C), not used for maintenance gating.
- Remove storage room cap; rely on storage target only.
- Maintain comfort target (default 22 C) until both comfort rooms are satisfied.
- Add comfort-to-heatpump offset input (default 2 C).
- Fix comfort satisfied margin at 0.2 C (no input).
- Add storage-to-heatpump offset input (default 2 C).
- Drop to maintenance target (default 20 C) when comfort rooms satisfied.
- Enforce maintenance minimum (default 19 C) under low-comfort conditions.
- Add optional low-temperature recovery path after 30 minutes below target by 0.5 C.
- Remove direct minimum override and drive to mirror minimum only through core routing.
- Remove warm margin; cold boost is always applied based on outdoor temperature.
- Remove min write delta input; hardcode threshold at 0.2 °C.
- Remove limits inputs; clamp control temperature to 10..26 °C.
- Remove maintenance minimum input and safety section header.
- Enforce cooldown using input_datetime helper (no delay-based cooldown).
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
| Recovery path optional | Allows compressor-only operation by default |
| Template trigger for delayed arm | Leverages built-in duration trigger in automation |
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
