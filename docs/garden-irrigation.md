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

1. **Gross over-watering.** ~810 L/week on a 10 m hedge row is several times what an
   established hedge needs. For Ilex crenata this is the dangerous direction — see
   [Watering strategy](#watering-strategy).
1. **Uneven distribution.** Above rated pressure the hose delivers hard near the feed
   and less at the far end, so run length matters more than it should. Worst on the
   23 m centre-fed bottom hedge.
1. **Mechanical risk.** PE/PP/ABS well over working pressure, at cut ends and
   quick-couplings, risks splitting.

**Fix: fit a pressure reducer** on the garden line, downstream of the main valve so all
zones benefit. Biltema sells one intended for this hose and recommends it in the product
description. Until that is fitted, run times cannot be tuned meaningfully — a deep soak
and a sensible weekly volume are not simultaneously achievable at this flow rate, since
the target volume is reached in a few minutes.

**Re-measure after fitting it.** The flow rate will change substantially, invalidating
every run time below.

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

> **Status: NOT DEPLOYED.** The schedule below was designed to hold weekly volumes
> roughly constant while switching to deep+infrequent soaks. The measurements in
> [Measured water use](#measured-water-use) came later and show the *existing* weekly
> volume is already ~5x too high, so holding it constant is the wrong target. Fit the
> pressure reducer, re-measure, then set run times from the new flow rate. The live
> automation is still on the old daily schedule.

Automation: `automation.garden_watering_daily_unless_rain`
(alias "Garden watering — Mon/Wed/Fri unless rain"). Deployable config:
[`garden-watering.yaml`](garden-watering.yaml).

Trigger 06:00, condition `weekday: [mon, wed, fri]`, skipped if 3-day forecast rain
≥ 10 mm.

| #   | Session      | Zone                          | Soak   |
| --- | ------------ | ----------------------------- | ------ |
| 1   | Lawn         | AquaPrecise `contour_1`       | 25 min |
| 2   | Top hedge    | `switch.sonoff_valve_terrace` | 25 min |
| 3   | Middle hedge | `switch.sonoff_valve_back`    | 25 min |
| 4   | Bottom hedge | `switch.sonoff_swv`           | 25 min |
| 5   | Bottom hedge | `switch.sonoff_swv`           | 25 min |

Sessions 4 and 5 are one 50-minute soak split across two valve opens, because 50 min
exceeds the hardware cap. The ~20 s gap between them resets the valve timer but is far
too short for the soil to notice.

Total run ≈ 06:00 → 08:15. Each session opens and closes the main valve independently,
so the main is never open longer than ~25 min 20 s.

### Weekly totals vs. the previous schedule

| Zone         | Was (daily)      | Now (Mon/Wed/Fri) |
| ------------ | ---------------- | ----------------- |
| Lawn         | 15 min × 7 = 105 | 25 min × 3 = 75   |
| Top hedge    | 10 min × 7 = 70  | 25 min × 3 = 75   |
| Middle hedge | 10 min × 7 = 70  | 25 min × 3 = 75   |
| Bottom hedge | 23 min × 7 = 161 | 50 min × 3 = 150  |

Hedge volumes are roughly unchanged; what changed is that the same water now arrives in
3 deep soaks instead of 7 shallow ones. The lawn drops ~30 %, which is the one figure
worth watching — grass browns before it dies, so raise session 1 if it suffers.

### Tuning

Run times are set conservatively because the sweating-hose flow rating and the soil type
are not known. **Calibrate empirically:** after a session, dig a small hole next to the
drip line and check how deep the water actually reached. Aim for moisture through the
root zone (~20-30 cm), not a wet surface over dry subsoil.

- Water not reaching depth → raise the per-session soak (max ~25 min per open; add a
  second open like the bottom hedge rather than exceeding it).
- Soil still wet at the next session → drop to Mon/Thu, or shorten the soaks.

## Related automations

- `garden_watering_daily_unless_rain` — the main schedule above.
- `garden_valve_failsafe_auto_close_if_left_open` — forces the main valve closed if it
  has been open more than 20 min.
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
