# Garden Irrigation

Drip irrigation for the hedges, lawn and terrace. Separate from Blockheat (heating) —
documented here because the automations live in the same Home Assistant instance.

## Plants

All three hedges are **Ilex crenata 'Caroline Upright'** — Japanese holly, Swedish
*japansk järnek*. Evergreen, slow-growing (20-30 cm/year), pruned twice a year.

This species drives the whole watering strategy, see
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

- The hedges have run on the daily schedule for an extended period and are **visibly
  healthy** (owner's direct observation, 2026-07-28). That is better evidence about
  plant health than a rule of thumb.
- Soil moisture telemetry does not support the over-watering claim either — see
  [Soil moisture sensors](#soil-moisture-sensors). The two hedge-end sensors show no
  response at all to daily irrigation.

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
drier, and the hedge ends are exactly where drought stress would first appear.

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

The resolution both the Swedish and UK/US sources agree on: **water deeply and
infrequently, never a little every day.**

Design rules that follow from that:

1. **Frequency over volume.** Mon/Wed/Fri rather than daily. Daily short runs keep the
   root zone permanently damp (rot risk) *and* keep roots shallow, which makes the hedge
   more fragile in the next dry spell — the opposite of what's wanted.
1. **Long soaks.** 25 min per zone rather than 10, so water reaches the root zone
   instead of wetting the top few centimetres. Buried sweating hose typically delivers
   ~2-5 l/m/h, so 10 min was only ~0.3-0.8 l/m.
1. **Early morning.** 06:00 start, as recommended, to cut evaporation. Buried drip
   also keeps foliage dry.
1. **Skip when rain is coming.** 3-day forecast ≥ 10 mm cancels the session.

Other care, not automated:

- **Mulch 5-8 cm** of organic material over the root zone — retains moisture, evens out
  soil temperature, and cuts how much irrigation is needed.
- **Feed once in spring** with a slow-release organic / evergreen fertiliser.
- **Prune 1-2× between May and September**, on an overcast day, with a sharp clean shear.
- **Don't forget autumn/winter.** Evergreens transpire year-round. Give a good soak in
  autumn before the ground freezes; the hedge can dry out and drop leaves over winter.
- **Drainage is the critical variable.** If a hedge line sits in heavy or compacted
  soil, reduce run times rather than increase them.

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

The hedges were healthy on the daily schedule, so this is **not fixing a problem** — it
is a test of whether the same hedges stay healthy on ~29 % of the water. Duration was
left alone on purpose: frequency is the safe lever, since at the measured ~11.6 L/min
a short run would water shallowly and unevenly, working against root depth.

**Revert is one line** — change `weekday: [mon, thu]` back to no weekday condition.

### What to watch

Ilex crenata signals drought stress before it dies: dull or slightly greyed foliage,
then leaf drop, worst at the far ends of the 23 m bottom hedge where end-of-line
pressure is lowest. Peak summer with a 3-4 day gap is the stress test. If anything looks
off, revert to daily first and diagnose after.

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

- `garden_watering_daily_unless_rain` — the main schedule above.
- `garden_valve_failsafe_auto_close_if_left_open` — forces the main valve closed if it
  has been open 20 min **while no watering run is active** (the trigger is gated on the
  watering automation's `current` attribute), plus a hard 70-min backstop regardless of
  state. Verified 2026-07-28 that this does not clip the 23-min bottom-hedge session:
  the per-zone session design keeps continuous main-valve open time to ~23 min 20 s, and
  the 20-min rule is suppressed while the run is in progress.
- `smart_valve_auto_off_all` — turns any valve off 30 min after it switches on
  (general backstop).

## Sources

- [Skötsel och beskärning av japansk järnek — Häckväxter Online](https://www.hackvaxteronline.se/skotsel-och-beskarning-av-japansk-jarnek)
- [Ilex crenata 'Convexa' (Japansk järnek) — Heijnen Växter](https://www.hackvaxter-heijnen.se/h%C3%A4ckv%C3%A4xter/japansk-j%C3%A4rnek/ilex-crenata-convexa)
- [Ilex crenata 'Caroline Upright' — Heijnen Plants](https://www.hedgeplants-heijnen.co.uk/japanese-holly/ilex-crenata-caroline-upright)
- [How to Grow and Care for Japanese Holly — Gardener's Path](https://gardenerspath.com/plants/ornamentals/grow-japanese-holly/)
- [Ilex crenata Seasonal Care Guide — Soto Gardens](https://www.sotogardens.com/blogs/seasonal-plant-care-guides/ilex-crenata)
- [Ilex crenata (Box-leaved Holly) — NC Extension Gardener Plant Toolbox](https://plants.ces.ncsu.edu/plants/ilex-crenata/)
- [Holly Diseases & Insect Pests — Clemson HGIC](https://hgic.clemson.edu/factsheet/holly-diseases-insect-pests/)
- [Phytophthora Root Rot — RHS](https://www.rhs.org.uk/disease/phytophthora-root-rot)
