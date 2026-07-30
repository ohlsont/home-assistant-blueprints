# Garden Irrigation

Drip irrigation for the hedges, lawn and terrace. Separate from Blockheat (heating) —
documented here because the automations live in the same Home Assistant instance.

## Plants

All three hedges are **Ilex crenata 'Caroline Upright'** — Japanese holly, Swedish
*japansk järnek*. Evergreen, slow-growing (20-30 cm/year), pruned twice a year. Hardy to
roughly **-23 °C**.

**Planted autumn 2025. These are NOT established plants.** Establishment takes about two
years for this species, so through 2026 and into 2027 they are still in the
establishment phase. This matters more than anything else in this document:

- Established Ilex crenata is moderately drought-tolerant. **Newly planted Ilex crenata
  is not** — young plants must not dry out.
- Establishment-phase guidance is **deep watering once or twice a week** for the first
  two years, which is what the current schedule delivers.
- Any reasoning that starts "the hedges are established, so…" is wrong until roughly
  autumn 2027. An earlier version of this document made that mistake throughout.

They took **winter desiccation damage over the 2025/26 winter** and are still recovering
— see [Winter damage 2025/26](#winter-damage-202526).

This species and its establishment status drive the whole watering strategy, see
[Watering strategy](#watering-strategy) below.

## Topology

**Valve entity_ids do NOT match their real roles.** Trust the friendly name and this
table, never the entity_id string.

Water path: one outdoor tap → **garden main valve** (supplies all garden water) →
25 mm hose via a standard Gardena plug → three hedge outlets + one terrace outlet.
Each zone steps 25 mm → 20 mm → 15 mm microdrip / "sweating" hose buried just under
the soil.

| Zone             | Entity                                   | Friendly name             | Notes                                                                  |
| ---------------- | ---------------------------------------- | ------------------------- | ---------------------------------------------------------------------- |
| **Main**         | `switch.sonoff_swv_2`                    | Garden valve              | Feeds everything; also called the "garage" valve                       |
| **Top hedge**    | `switch.sonoff_valve_terrace`            | Hedge valve top           | 10 m. entity_id says "terrace" — it is the **top hedge**               |
| **Middle hedge** | `switch.sonoff_valve_back`               | SONOFF valve hedge middle | 10 m                                                                   |
| **Bottom hedge** | `switch.sonoff_swv`                      | Sonoff valve hedge bottom | 23 m, hose enters at the **centre** (~11.5 m each way)                 |
| **Terrace**      | `switch.outside_sonoff_hedge_down_right` | SONOFF valve terrace      | Manual only. entity_id says "hedge_down_right" — it is the **terrace** |

All are SONOFF SWV Zigbee valves.

**AquaPrecise** is a separate multi-contour drip controller teed into the line just
before the bottom-hedge valve:

- `select.aquaprecise_watering` — contour selection (`contour_1` = "Gräs"/lawn, `rest` = off)
- `number.aquaprecise_manual_watering_time` — run time in seconds

The terrace outlet is on-demand only: connect a hose to water the terrace, or a drip
hose for the tomato/strawberry urns.

### Drip hose

[Biltema Droppslang 1/2", 25 m, art. 14-5002](https://www.biltema.se/fritid/tradgard/bevattning/slangar/droppslang-12-25-m-2000057335),
bought in 25 m rolls and cut to length per zone.

| Spec                 | Value       |
| -------------------- | ----------- |
| Length (per roll)    | 25 m        |
| Diameter             | 22 mm       |
| Hose connection      | 1/2"        |
| **Working pressure** | **1.5 bar** |
| Material             | PE, PP, ABS |

Biltema's own description: *"För precis bevattning ovan eller under jord, rek djup
15–20 cm. Minskar vattenförbrukningen med upp till 70 %. Slangen kan användas
tillsammans med Biltemas reduceringsventil."* — i.e. recommended burial depth
**15-20 cm**, and it is explicitly meant to be paired with a **pressure reducer**.

No flow rate is published for this hose, so run times cannot be derived from the
spec sheet. They have been measured instead — see
[Measured water use](#measured-water-use).

## Measured water use

`sensor.cubic_secure_laundry_total_volume` (LK Systems Cubic Secure, whole-house
incoming meter, litres) captures garden watering, so actual consumption is measurable
rather than estimated. Hourly statistics, 2026-07-22 → 2026-07-28, on the old daily
06:00 schedule (lawn 15 / top 10 / middle 10 / bottom 23 min = 58 min of watering):

| Date       | 06:00 bucket | 07:00 bucket | Run total |
| ---------- | ------------ | ------------ | --------- |
| 2026-07-22 | 671 L        | 230 L        | 901 L\*   |
| 2026-07-23 | 550 L        | 113 L        | 663 L     |
| 2026-07-24 | 581 L        | 81 L         | 662 L     |
| 2026-07-25 | 638 L        | 52 L         | 690 L     |
| 2026-07-26 | 669 L        | 22 L         | 691 L     |
| 2026-07-28 | 662 L        | 17 L         | 679 L     |

\* likely includes household morning use. Baseline consumption in a quiet hour is
0-20 L, so the run itself is **~650-700 L**.

Derived, assuming total flow is roughly constant across zones (supply-limited rather
than emitter-limited, which is what running far above the hose's rated pressure
implies):

- **~11.6 L/min ≈ 700 L/h** while any one zone is open
- **~70 L/m/h** along the drip hose

| Zone         | Per run | Per week (daily schedule) |
| ------------ | ------- | ------------------------- |
| Lawn         | ~174 L  | ~1 220 L                  |
| Top hedge    | ~116 L  | ~810 L                    |
| Middle hedge | ~116 L  | ~810 L                    |
| Bottom hedge | ~267 L  | ~1 870 L                  |
| **Total**    | ~670 L  | **~4 700 L**              |

### The pressure problem

`sensor.cubic_secure_laundry_water_pressure` reads **~5 160 hPa = 5.16 bar** at the
incoming main. The drip hose is rated **1.5 bar**.

The pressure actually reaching the buried hose is lower than 5.16 bar — the reading is
at the house main, and the garden tap, the SONOFF valves and the 25 → 20 → 15 mm
step-downs all drop pressure, more so under flow. But the measured ~70 L/m/h is roughly
an order of magnitude above what this class of hose delivers at its rated pressure,
which is consistent with the line running well above 1.5 bar.

Consequences:

1. **Uneven distribution.** Above rated pressure the hose delivers hard near the feed
   and less at the far end, so run length matters more than it should. Worst on the
   23 m centre-fed bottom hedge.
1. **High water use.** ~4 700 L/week during the watering season.

**Burst risk is not a concern here — do not re-raise it.** Rated working pressure is a
continuous-duty figure carrying a safety margin, not burst pressure; burst is typically
2-3x working for this hose class. The system has run at this pressure for an extended
period without a failure (owner, 2026-07-28), on intermittent duty of about an hour a
day in cool ground. The 1.5 bar rating looks alarming next to 5.16 bar and invites the
conclusion that failure is imminent. It isn't.

### What the volume does NOT establish

The numbers above look like gross over-watering — ~810 L/week onto a 10 m hedge row is
several times a textbook figure. **Resist that conclusion.** It rests on a generic
20-25 mm/week target and an assumed 0.4-0.6 m wetted strip, neither of which has been
measured here.

Against it:

- **No sign of root rot.** The hedges ran the daily schedule through a full season with
  no wilting, no dieback, and no soft blackened roots. The yellowing they do show is
  [winter desiccation](#winter-damage-202526) — a *drought* symptom, the opposite of
  waterlogging.
- Soil moisture telemetry does not support the over-watering claim either — see
  [Soil moisture sensors](#soil-moisture-sensors). The two hedge-end sensors show no
  response at all to daily irrigation.
- These are **establishment-phase plants** recovering from winter damage. Their water
  requirement is at the high end, not the low end.

The likely reconciliation is that **the soil drains freely.** Phytophthora risk in Ilex
crenata is about water *sitting* around the roots, not volume passing through. Buried
drip at 15-20 cm into free-draining soil moves down and away, in which case high volume
is far less dangerous than the generic guidance implies.

**To settle it:** dig at hose depth, per
[Finding: the hedge ends show no response to irrigation](#finding-the-hedge-ends-show-no-response-to-irrigation).
Until then the volume figures are a water-cost fact, not a plant-health verdict.

**Optional fix: a pressure reducer** on the garden line, downstream of the main valve so
all zones benefit. Biltema sells one intended for this hose. With both the plant-health
and burst-risk arguments withdrawn, the remaining case for it is even distribution along
each run and lower water use — worth doing, not urgent.

**Re-measure if it is fitted.** The flow rate will change substantially, invalidating
every run time below.

## Soil moisture sensors

Three sensors are in the garden:

| Sensor                                       | Location                   | Status 2026-07-28                             |
| -------------------------------------------- | -------------------------- | --------------------------------------------- |
| `sensor.outdoor_flower_sensor_soil_moisture` | Black currant bush         | Reads 0.0 — almost certainly faulty           |
| `sensor.outside_garden_2_soil_moisture`      | End of a hedge run         | Working                                       |
| `sensor.outside_garden_3_soil_moisture`      | End of the other hedge run | `unavailable` since 2026-07-22 — flat battery |

(`sensor.palmen_soil_moisture_2` and `sensor.begonia_soil_moisture` are potted plants,
not garden ground.) Which of Garden 2 / Garden 3 is the middle hedge and which is the
top hedge is not yet recorded — worth pinning down and renaming the entities.

### Finding: the hedge ends show no response to irrigation

Both hedge-end sensors sat **completely flat through daily 06:00 watering**:

- `outside_garden_2`: 14-18 % all week to 2026-07-27, no daily spike. Then jumped to a
  max of **58 %** on 2026-07-27 afternoon — a rain event — and decayed back toward 25 %
  over the following hours.
- `outside_garden_3`: 16-20 % flat from 2026-07-16 until its battery died 2026-07-22.
  No daily spike either.

So a rain event moves the sensor by 40 points, while ten minutes of drip irrigation
moves it by zero. Two independent sensors at two different hedge ends agree.

Two explanations, not yet distinguished:

1. **Water is not reaching the hedge ends.** End-of-line pressure drop, or uneven
   perforation along the cut hose. This is the distribution problem in
   [The pressure problem](#the-pressure-problem), showing up as a real measurement
   rather than a theory.
1. **Sensor probes sit above the drip line.** The hose is buried 15-20 cm; these probes
   typically go in 5-10 cm. Rain wets top-down and registers strongly; sub-surface drip
   wets downward and laterally and may never reach the probe. Both sensors were
   presumably installed the same way, which makes a systematic mismatch plausible.

**How to distinguish — dig.** After a session, dig beside the drip line at a hedge end
and at the feed end of the same run, and feel for moisture at hose depth (15-20 cm).

- Feed end wet, far end dry → distribution problem, explanation 1.
- Both wet at hose depth → the sensors are simply too shallow, explanation 2, and the
  telemetry is not measuring the root zone.

This matters for the schedule: if the ends really are dry, cutting to Mon/Thu makes them
drier, and the hedge ends are exactly where drought stress would first appear. With
first-year plants already weakened by winter damage, dry run ends would kill plants
rather than merely stress them — **this is the highest-priority open question here.**

## Winter damage 2025/26

Planted autumn 2025, the hedges took **winter desiccation damage** over their first
winter. As of 2026-07-28 most plants were very yellow, with some starting to green.

**Mechanism, and why it is not a hardiness problem.** Ilex crenata is evergreen and keeps
transpiring through winter. When the ground freezes the roots cannot resupply water, so
the foliage dehydrates. Wind and winter sun drive it more than absolute cold does — and
since the species is hardy to about -23 °C, the winter probably did not kill by cold. It
dried them out. That is a siting and preparation problem, which is fixable, rather than
the wrong plant for the climate.

**Distinguishing the symptoms** — worth keeping straight, because they call for opposite
responses:

| Symptom pattern                                                                                                    | Cause                | Response                           |
| ------------------------------------------------------------------------------------------------------------------ | -------------------- | ---------------------------------- |
| Browning/bronzing at leaf tips and edges; worst on windward and sun-exposed sides and on tops; appears over winter | Winter desiccation   | Water, patience, winter protection |
| Yellow leaf blades with **veins staying green**; shows on new growth first                                         | Iron chlorosis (pH)  | Acid feed, chelated iron, sulphur  |
| Inner leaves yellowing and dropping                                                                                | Normal seasonal shed | Nothing                            |

**Recovery.** Winter-burned foliage does not regreen — dead tissue stays dead, and new
growth pushes it off. So recovery shows as new shoots, not as existing leaves changing
colour. Do not cut brown growth back until new growth has fully emerged (around end of
June); by late July it is safe to assess. Scratch a suspect stem with a thumbnail — green
under the bark means live, brown means dead. Cut back to live wood.

**Preventing a repeat, for autumn 2026:**

1. **Deep soak before the ground freezes.** The single most effective measure — the plant
   cannot draw water once the soil is frozen, so it must go into winter fully hydrated.
   The watering automations have no autumn/winter logic, see
   [No seasonal guard](#no-seasonal-guard).
1. **Mulch 5-8 cm** over the root zone. Insulates the roots and delays soil freezing, on
   top of the moisture and pH benefits.
1. **Windbreak on the exposed sides.** Burlap or screening. Winter sun is as damaging as
   wind, so south and west exposure matters as much as the prevailing wind direction.
1. **Do not prune in autumn.** Pruning stimulates growth that will not harden in time.

## Hardware and plumbing constraints

**One zone at a time.** All zones share one supply line, so running two at once halves
the pressure at each. Every watering is: open main → open one zone → wait → close zone
→ close main → next zone. The main valve is the only one allowed on alongside a zone.

**SONOFF SWV ~30-minute hardware auto-close.** Each valve closes itself roughly 30 min
after it opens. This is firmware flood-safety, is **not** exposed as a ZHA entity, and
cannot be disabled from HA. Verified 2026-07-12: the main valve opened at 06:00 and
hardware-closed at exactly 06:30, leaving the middle and bottom hedges dry.

Deliberately closing and reopening the valve **resets the timer** — a fresh open gives a
full ~30-min window. So no valve may be commanded open for more than ~25 min
continuously, and longer soaks must be split into two opens with a brief close between.

**End-of-line pressure drop.** The bottom hedge is 23 m fed from the centre, so the far
ends of that run see less pressure than the tee. It gets double the run time of the 10 m
hedges to compensate.

## Watering strategy

Ilex crenata sits in an awkward spot: it is **drought-sensitive** (shallow, fibrous
roots that dry out fast in a heatwave, and it drops leaves when it dries out) but it is
also **extremely prone to Phytophthora and black root rot in wet or poorly drained
soil** — over-watering is cited as the most common cause of shrub failure in this
species. Once root rot takes hold the plant rarely recovers.

**These are establishment-phase plants** (planted autumn 2025, see
[Plants](#plants)), which shifts the balance toward the drought side. Young plants have
not yet put roots out into the surrounding soil and cannot ride out a dry spell.

The resolution both the Swedish and UK/US sources agree on: **water deeply and
infrequently, never a little every day.** For the establishment phase specifically, the
guidance is **deep watering once or twice a week for the first two years**, and for
recovery from winter damage, *"a thorough soak (drip irrigation is best) twice a week."*

Design rules that follow:

1. **Deep and infrequent, not shallow and often.** Twice a week beats daily. Daily short
   runs keep the root zone permanently damp (rot risk) *and* keep roots shallow — and
   shallow roots are what made these plants vulnerable to winter desiccation in the first
   place. Building depth now is the long game.
1. **Long soaks.** Enough run time for water to reach the root zone rather than wetting
   the top few centimetres.
1. **Early morning.** 06:00 start, to cut evaporation. Buried drip also keeps foliage
   dry.
1. **Skip when rain is coming.** 3-day forecast ≥ 10 mm cancels the session.

Mon/Thu deep soaks satisfies both the establishment and the winter-recovery guidance. Do
not "fix" it by reverting to daily.

### Fertilising

Ilex crenata is an **acid-soil plant** — ideal pH **5.0-6.0**, and it does poorly in
calcareous soil. Use **surjordsgödsel / rhododendrongödsel** (the rhododendron, azalea
and blueberry category), slow-release, not a general häckgödsel. The one hard rule is
negative: **nothing lime-based near the hedge** — no trädgårdskalk, no wood ash, no
mortar or concrete washings.

Timing: **spring**, as growth starts. Once a year is enough. Avoid large nitrogen doses
after end of July in southern Sweden (mid-July further north) — soft late growth will not
harden before frost, which is the same failure mode as the winter damage. Slow-release
formulations soften this considerably but have a tail that keeps feeding for months, so a
late-July application is still feeding into September.

The soil pH has never been measured. It was not prepared before planting, and "unprepped"
is compatible with anything from ~5.5 to ~8 — natural ground in much of Sweden runs
mildly acidic, while builder's fill near a house carries mortar debris and runs alkaline.
An acid fertiliser is the right choice either way: correct at pH 6, mildly and usefully
acidifying at pH 7.

**Water hardness is worth checking.** Pushing 1 000+ L/week of hard municipal water into
the root zone of an acid-soil plant slowly raises pH. It is a free lookup from the water
utility and either dismisses the concern or makes the mulch more important.

#### Applied 2026-07-29

A slow-release rhododendron/blueberry fertiliser was applied to the hedges. Correct
product category and the lower-risk release form. It was watered in by the Mon/Thu run
the following morning (+631 L), which matters — fertiliser needs soil moisture for uptake
and quick-release products on dry soil can scorch the shallow feeder roots of evergreens.

**This doubles as a diagnostic.** These fertilisers typically carry iron and magnesium,
and interveinal chlorosis *can* reverse in existing leaves within 2-4 weeks once iron is
available. Winter burn cannot. So:

- **Existing yellow leaves gradually green up** → part of the yellowing was iron
  chlorosis, pH is a real factor, commit to the acidification path.
- **Only new shoots come through green, old leaves stay yellow and drop** → it was winter
  desiccation, pH is fine, the feed is just background nutrition.

Caveat on interpreting it: recovery was **already visibly underway before the application**
(some plants greening as of 2026-07-28), so general improvement cannot be attributed to
the fertiliser. Only the behaviour of *existing yellow leaves* is informative.

No further feeding in 2026. Hold off in spring 2027 too until it is clear how they came
through the winter.

### Other care, not automated

- **Mulch 5-8 cm** of organic material over the root zone — retains moisture, evens out
  soil temperature, insulates roots against freezing, and bark mulch (barkmull) is mildly
  acidifying as it breaks down.
- **Prune 1-2× between May and September**, on an overcast day, with a sharp clean shear.
  Not in autumn — see [Winter damage 2025/26](#winter-damage-202526).
- **Don't forget autumn/winter.** Evergreens transpire year-round. A deep soak before the
  ground freezes is the main defence against a repeat of the 2025/26 damage.
- **Drainage is the critical variable.** If a hedge line sits in heavy or compacted
  soil, reduce run times rather than increase them.
- **Watch for a soft growth flush in Aug/Sep 2026** following the July fertiliser. If it
  appears, do not prune it off — protect it instead.

## Schedule

**Deployed 2026-07-28. Mon/Thu — a deliberate water-saving trial, not a fix.**

Automation: `automation.garden_watering_daily_unless_rain`
(alias "Garden watering — Mon/Thu unless rain"). Deployable config:
[`garden-watering.yaml`](garden-watering.yaml).

Trigger 06:00, condition `weekday: [mon, thu]`, skipped if 3-day forecast rain ≥ 10 mm.

| #   | Session      | Zone                          | Run    |
| --- | ------------ | ----------------------------- | ------ |
| 1   | Lawn         | AquaPrecise `contour_1`       | 15 min |
| 2   | Top hedge    | `switch.sonoff_valve_terrace` | 10 min |
| 3   | Middle hedge | `switch.sonoff_valve_back`    | 10 min |
| 4   | Bottom hedge | `switch.sonoff_swv`           | 23 min |

Total run ≈ 06:00 → 07:06. Each session opens and closes the main valve independently,
so the main is never open longer than ~23 min 20 s.

**Durations are deliberately unchanged from the old daily schedule.** Only the frequency
dropped, 7 days/week → 2, taking weekly use from ~4 700 L to ~1 350 L.

Duration was left alone on purpose: frequency is the safe lever, since at the measured
~11.6 L/min a short run would water shallowly and unevenly, working against root depth.

**Twice-weekly deep soaks happens to be exactly right** for establishment-phase plants
recovering from winter damage — both the two-year establishment guidance and the
winter-burn recovery guidance specify a thorough soak twice a week. The schedule was
originally chosen to save water, before the planting date and winter damage were known;
it landed on the correct pattern for the wrong reason. **Do not revert to daily.**

**Revert is one line** if ever needed — change `weekday: [mon, thu]` back to no weekday
condition.

### Lawn evening top-up

Separate automation, added 2026-07-30 at the owner's request: the lawn was the one zone
whose weekly total fell when the schedule went from daily to Mon/Thu.

`automation.garden_watering_lawn_evening_top_up_mon_thu` — 19:00 Mon/Thu, **lawn only**
(AquaPrecise `contour_1`, 15 min). Config:
[`garden-watering-lawn-evening.yaml`](garden-watering-lawn-evening.yaml).

Lawn goes 15 → 30 min per watering day, 30 → 60 min/week. Weekly garden total ~1 340 →
~1 690 L.

Design notes:

- **Separate automation, not folded into the morning run.** Extending the morning
  sequence would need a ~13-hour `delay` inside a `mode: single` automation, which does
  not survive restarts.
- **Held to 15 min, and this is a trap.**
  `garden_valve_failsafe_auto_close_if_left_open` force-closes the main valve at 20 min,
  and its exemption checks **only** `automation.garden_watering_daily_unless_rain`'s
  `current` attribute. It does not know this automation exists. Anything over ~19 min in
  the evening slot gets silently chopped at 20 min while appearing to work. **Whitelist
  the new automation in the failsafe before lengthening this session.**
- **19:00 rather than later.** Evening watering is the standard thing turf advice warns
  against — grass staying wet overnight invites fungal disease. 19:00 leaves a couple of
  hours of drying before dark. Flagged to the owner, who chose to proceed.
- Enforces the one-zone-at-a-time rule with a native `condition: numeric_state` on the
  morning automation's `current` attribute.

### What to watch

Ilex crenata signals drought stress before it dies: dull or slightly greyed foliage,
then leaf drop, worst at the far ends of the 23 m bottom hedge where end-of-line
pressure is lowest. Peak summer with a 3-4 day gap is the stress test. Given these are
first-year plants already weakened by winter desiccation, treat any sign of it as urgent
rather than something to observe for a few weeks.

### Optional improvements, in rough priority order

1. **Dig at a hedge end after a session** to settle whether water reaches the run ends —
   see [Finding: the hedge ends show no response to irrigation](#finding-the-hedge-ends-show-no-response-to-irrigation).
   Everything else depends on the answer.
1. **Fix the two dead sensors.** `outside_garden_3` battery (flat since 2026-07-22) and
   the black currant sensor reading 0.0. Two of three garden sensors are currently
   useless, and the surviving one is doing all the work.
1. **Rename the garden sensors** once their locations are confirmed —
   `Garden 2` / `Garden 3` do not say which hedge they are on. Follow the entity-rename
   impact workflow; check dashboards and automations for consumers first.
1. **Fit a pressure reducer** downstream of the main valve (`switch.sonoff_swv_2`).
   Buys even distribution along each run and lower water use. Not urgent — but if the
   dig shows dry run ends, even distribution stops being cosmetic.
1. **Re-measure if it is fitted**, with `sensor.cubic_secure_laundry_total_volume` — run
   one zone alone and read the delta, per zone, so the per-metre rate is measured rather
   than derived. Then reset durations.

### Tuning

Once the reducer is in, calibrate empirically rather than from any spec: after a
session, dig a small hole next to the drip line and check how deep the water actually
reached. Aim for moisture through the root zone (~20-30 cm), not a wet surface over dry
subsoil. Cross-check the volume against the Cubic Secure meter.

- Water not reaching depth → raise the per-session run (max ~25 min per valve open;
  split into two opens rather than exceeding the hardware cap).
- Soil still wet at the next session → cut frequency before cutting duration.

### Alternative considered: Mon/Wed/Fri deep soaks

Mon/Wed/Fri with 25-min soaks (bottom hedge 2 × 25, split across two valve opens to stay
under the ~30-min hardware cap) would hold weekly volume roughly constant while making
each soak deeper — the textbook deep-and-infrequent pattern for Ilex crenata. It was
written and never deployed; Mon/Thu at unchanged durations was chosen instead, to test
the water saving first.

It remains the obvious next configuration if Mon/Thu proves too dry, and is the natural
target once a pressure reducer is fitted and durations are recalculated from a
re-measured flow rate.

## Related automations

- `garden_watering_daily_unless_rain` — the main morning schedule above. Note the
  entity_id still says "daily"; the alias is "Garden watering — Mon/Thu unless rain".
- `garden_watering_lawn_evening_top_up_mon_thu` — the lawn evening session above.
- `garden_valve_failsafe_auto_close_if_left_open` — forces the main valve closed if it
  has been open 20 min **while no watering run is active** (the trigger is gated on the
  morning automation's `current` attribute), plus a hard 70-min backstop regardless of
  state. Verified 2026-07-28 that this does not clip the 23-min bottom-hedge session:
  the per-zone session design keeps continuous main-valve open time to ~23 min 20 s, and
  the 20-min rule is suppressed while the run is in progress. **Its exemption covers only
  the morning automation** — see the trap noted under
  [Lawn evening top-up](#lawn-evening-top-up).
- `smart_valve_auto_off_all` — turns any valve off 30 min after it switches on
  (general backstop).

### No seasonal guard

Neither watering automation has any seasonal or freeze logic. Both are plain time
triggers with a weekday condition and a rain check, so as written they will attempt to
water in January. Whether that is handled manually (closing the outdoor tap, disabling
the automations) is not recorded.

Two things worth building, given the 2025/26 winter damage:

1. **A freeze guard** — skip the run when the ground is frozen or the forecast is below
   zero. Pushing water through outdoor SONOFF valves and a buried hose in freezing
   conditions risks the hardware as well as being useless to the plants.
1. **An autumn deep soak** before the ground freezes. This is the single most effective
   defence against a repeat of the winter desiccation, and it is currently nobody's job.

## Sources

- [Skötsel och beskärning av japansk järnek — Häckväxter Online](https://www.hackvaxteronline.se/skotsel-och-beskarning-av-japansk-jarnek)
- [Ilex crenata 'Convexa' (Japansk järnek) — Heijnen Växter](https://www.hackvaxter-heijnen.se/h%C3%A4ckv%C3%A4xter/japansk-j%C3%A4rnek/ilex-crenata-convexa)
- [Ilex crenata 'Caroline Upright' — Heijnen Plants](https://www.hedgeplants-heijnen.co.uk/japanese-holly/ilex-crenata-caroline-upright)
- [How to Grow and Care for Japanese Holly — Gardener's Path](https://gardenerspath.com/plants/ornamentals/grow-japanese-holly/)
- [Ilex crenata Seasonal Care Guide — Soto Gardens](https://www.sotogardens.com/blogs/seasonal-plant-care-guides/ilex-crenata)
- [Ilex crenata (Box-leaved Holly) — NC Extension Gardener Plant Toolbox](https://plants.ces.ncsu.edu/plants/ilex-crenata/)
- [Holly Diseases & Insect Pests — Clemson HGIC](https://hgic.clemson.edu/factsheet/holly-diseases-insect-pests/)
- [Phytophthora Root Rot — RHS](https://www.rhs.org.uk/disease/phytophthora-root-rot)
- [Holly Winter Burn Recovery Guide — Pryors](https://pryors.com/2026/04/04/holly-winter-burn-recovery-guide/)
- [Ilex crenata Problems UK — NetVol](https://netvol.co.uk/ilex-crenata-problems-uk-gardening-guide/)
- [Japanese Holly Care Guide — Yorkshire Bonsai](https://www.yorkshirebonsai.co.uk/blogs/advice-guides/japanese-holly-ilex-crenata-care-guide)
- [Fertilizing Trees and Shrubs — UNH Extension](https://extension.unh.edu/resource/fertilizing-trees-and-shrubs-fact-sheet)
- [Fertilizing Trees & Shrubs — Clemson HGIC](https://hgic.clemson.edu/factsheet/fertilizing-trees-shrubs/)
- [Gödsla häck — Plantinavia](https://www.plantinavia.se/blogg/godsla-hack/)
- [Optimalt pH för olika växter — Wexthuset](https://www.wexthuset.com/fakta-och-rad/om-odling-och-skotsel-av-tradgard-och-vaxter/om-jord-godsel-naring/optimalt-ph-for-odling-av-olika-vaxter)
- [(A)biotic stress in Ilex crenata: soil pH and black root rot — ISHS](https://www.ishs.org/news/abiotic-stress-ilex-crenata-solving-problems-soil-ph-and-black-root-rot)
