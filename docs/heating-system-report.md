# Heating System Optimization Report — Home Assistant Implementation Guide

## System Overview

This document describes the heating equipment, efficiency characteristics, and control strategy for a ~190 m² home in the Gothenburg area of Sweden. The goal is to build Home Assistant automations that minimize electricity cost by dynamically choosing between the exhaust air heat pump (primary system) and two air-to-air heat pumps (supplementary), factoring in outdoor temperature, electricity spot price, and each unit's COP at any given moment.

---

## 1. Equipment Inventory

### 1.1 Qvantum ETK6500 — Exhaust Air Heat Pump (Frånluftsvärmepump)

| Parameter | Value |
|---|---|
| Model | Qvantum ETK6500 (TD2 manual, QCH SV 2317-7) |
| Type | Exhaust-air-to-water, variable-speed scroll compressor |
| Refrigerant | R-134a (1.1 kg) |
| Heating output at 35°C supply | 6.5 kW out / 1.7 kW electrical in → **COP 3.82** |
| Heating output at 50°C supply | 6.5 kW out / 2.2 kW electrical in → **COP 2.95** |
| Electric backup heater | 5 kW total (3 stages: 1 kW + 2 kW + 2 kW) |
| Max total output (compressor + backup) | 11.5 kW |
| ErP energy class (space heating) | A++ |
| Recommended floor area | 160–220 m² |
| Supply voltage | 3×400 VAC + N |
| Fuse | 16 A |
| Sound level (LWA) | 44 dB(A) |
| Distribution system | Hydronic (radiators and/or underfloor heating) |
| Hot water | Integrated accumulator tank with flow-through DHW (legionella-safe) |
| Ventilation | DN125 extract air duct, pressure-controlled A-class fan |

**Key characteristic:** The ETK6500 draws energy from indoor exhaust air (~21°C year-round). The compressor COP is therefore nearly constant — it varies only with the supply water temperature (heating curve), not outdoor temperature. However, total system efficiency drops sharply in cold weather because the electric backup heater (COP = 1.0) must cover any demand exceeding the compressor's 6.5 kW maximum.

### 1.2 Daikin Stylish XTH 30 — Air-to-Air Heat Pumps (x2 units)

| Parameter | Value |
|---|---|
| Model | Daikin Stylish XTH 30 (FTXTA30C / RXTA30C, "Optimised Heating" / Nepura+) |
| Type | Air-to-air, inverter-driven, wall-mounted split |
| Refrigerant | R-32 |
| Nominal heating capacity (7°C outdoor, 20°C indoor) | 3.2 kW |
| Max heating capacity | 7.1 kW |
| Min heating capacity | 0.8 kW |
| Nominal COP (7°C outdoor, 20°C indoor) | **5.01** (confirmed from Daikin spec sheet) |
| Heating capacity at -10°C (Pdh) | 3.0 kW (confirmed) |
| SCOP (seasonal, average climate) | 5.17 |
| SEER (cooling) | 8.75 |
| Energy class (heating, average climate) | A+++ |
| Min operating temperature (heating) | **-30°C** (guaranteed operation) |
| WiFi adapter | BRP069C4x (integrated, Daikin Onecta compatible) |
| Home Assistant integration | Daikin AC integration (firmware 2.8.0+, supported since HA 2025.9) |

**Key characteristic:** These are Nordic-optimized ("Optimised Heating 5+") air-to-air units. They deliver heat directly to room air — bypassing the hydronic system entirely. Their COP is excellent at moderate temperatures (5.0+ above 5°C) and remains competitive down to about -10°C (COP ~2.5), but degrades progressively in deep cold. Two units together can deliver up to ~14 kW max / ~6.4 kW nominal.

### 1.3 Ohmigo Controller

| Parameter | Value |
|---|---|
| Device | Ohmigo (https://www.ohmigo.io/) |
| Function | Digital indoor temperature sensor used to influence ETK6500 behavior |
| Control method | Setting a high temperature setpoint causes ETK6500 compressor to run harder; setting low causes it to reduce output |
| Integration | Used for electricity price optimization — run harder when electricity is cheap, coast when expensive |

**Current usage:** The Ohmigo is connected as the ETK6500's room temperature sensor. By programmatically adjusting the reported/setpoint temperature, the ETK6500's compressor output can be modulated indirectly.

---

## 2. Efficiency Data — COP vs. Outdoor Temperature

### 2.1 Daikin Stylish XTH 30 (single unit)

The COP varies with outdoor temperature because the unit extracts heat from outdoor air. Confirmed data points from Daikin spec sheet are marked; remaining points are estimated based on typical R32 Nordic heat pump performance curves.

| Outdoor Temp (°C) | COP | Heat Output (kW) | Elec. Input (kW) | Source |
|---|---|---|---|---|
| -25 | 1.3 | 2.6 | 2.00 | Estimated |
| -20 | 1.6 | 2.8 | 1.75 | Estimated |
| -15 | 2.0 | 2.9 | 1.45 | Estimated |
| -10 | 2.5 | 3.0 | 1.20 | **Confirmed** (Pdh at -10°C = 3.0 kW) |
| -7 | 2.8 | 3.1 | 1.11 | Estimated |
| -2 | 3.3 | 3.2 | 0.97 | Estimated |
| +2 | 3.9 | 3.2 | 0.82 | Estimated |
| +7 | 5.01 | 3.2 | 0.64 | **Confirmed** (nominal COP) |
| +12 | 6.0 | 3.0 | 0.50 | Estimated |
| +15 | 6.8 | 2.8 | 0.41 | Estimated |

With **two units**, multiply heat output and electrical input by 2. The COP remains the same per unit.

### 2.2 Qvantum ETK6500 — Compressor-Only COP

The compressor COP depends on the supply water temperature (heating curve), not outdoor temperature directly. However, outdoor temperature determines the heating curve setpoint.

| Outdoor Temp (°C) | Approx. Supply Temp (°C) | Compressor COP | Compressor Heat (kW) | Compressor Elec (kW) |
|---|---|---|---|---|
| -20 | 50 | 2.95 | 6.5 (maxed) | 2.20 |
| -15 | 48 | 3.07 | 6.5 (maxed) | 2.12 |
| -10 | 45 | 3.24 | 6.5 (maxed) | 2.01 |
| -5 | 42 | 3.41 | 6.5 (maxed) | 1.91 |
| 0 | 38 | 3.65 | 6.0 | 1.64 |
| +5 | 35 | 3.82 | 4.5 | 1.18 |
| +10 | 32 | 4.00 | 3.0 | 0.75 |
| +15 | 30 | 4.12 | 1.5 | 0.36 |

### 2.3 Qvantum ETK6500 — Total System COP (Compressor + Electric Backup)

When heat demand exceeds 6.5 kW, the electric backup (COP=1.0) kicks in, dragging down the system average.

| Outdoor Temp (°C) | Heat Demand (kW) | Compressor (kW) | Backup Heater (kW) | Total Elec (kW) | **System COP** |
|---|---|---|---|---|---|
| -20 | 12.0 | 6.5 | 5.0 (capped) | 7.20 | **1.67** |
| -15 | 10.5 | 6.5 | 4.0 | 6.12 | **1.72** |
| -10 | 9.0 | 6.5 | 2.5 | 4.51 | **2.00** |
| -5 | 7.5 | 6.5 | 1.0 | 2.91 | **2.58** |
| 0 | 6.0 | 6.0 | 0 | 1.64 | **3.65** |
| +5 | 4.5 | 4.5 | 0 | 1.18 | **3.82** |
| +10 | 3.0 | 3.0 | 0 | 0.75 | **4.00** |
| +15 | 1.5 | 1.5 | 0 | 0.36 | **4.12** |

*Note: Heat demand is estimated for a ~190 m² home. Actual demand depends on insulation, ventilation rate, DHW usage, and internal gains.*

---

## 3. Key Insight: Crossover Temperature

### 3.1 When are the Daikin units more efficient than the ETK6500 system?

Comparing the two system COPs:

| Outdoor Temp | ETK6500 System COP | Daikin XTH 30 COP | Winner |
|---|---|---|---|
| -20°C | 1.67 | 1.6 | Approximately even (ETK6500 slightly better) |
| -15°C | 1.72 | 2.0 | **Daikin** |
| -10°C | 2.00 | 2.5 | **Daikin** |
| -5°C | 2.58 | 3.3 | **Daikin** |
| 0°C | 3.65 | 3.9 | **Daikin** (marginal) |
| +2°C | 3.74 | 3.9 | **Daikin** (marginal) |
| +5°C | 3.82 | ~4.5 | **Daikin** |
| +7°C | 3.90 | 5.01 | **Daikin** |
| +10°C | 4.00 | 6.0 | **Daikin** |

**The Daikin units are more efficient than the ETK6500 system at virtually all outdoor temperatures above approximately -20°C.** The crossover is near -20°C; above that, the Daikins win — especially in the -15°C to +5°C range where the ETK6500 relies on its backup heater.

### 3.2 Important caveats

1. **The ETK6500 cannot be fully shut off** — it provides ventilation (mandatory FTX function) and domestic hot water (DHW). The ventilation fan must always run. The compressor can be modulated down but still needs to cycle for DHW.

2. **The Daikin units heat air, not water** — they cannot produce DHW or feed radiators/underfloor heating. They supplement the hydronic system by warming rooms directly.

3. **Optimal strategy is hybrid** — use the Daikins to reduce the ETK6500's heating load (and thus its backup heater usage), rather than replacing it entirely.

---

## 4. Recommended Control Strategy

### 4.1 Strategy Summary

The core idea: **use the Daikin air-to-air units to offload the ETK6500 whenever the Daikins' COP exceeds the ETK6500's marginal COP** (i.e., the COP of the next kW the ETK6500 would produce). When the ETK6500 is running on backup heater, its marginal COP is 1.0 — so any Daikin operation above COP 1.0 is beneficial.

### 4.2 Operating Modes

#### Mode A: Mild weather (outdoor > +5°C)
- ETK6500 compressor handles base hydronic heating and DHW at COP ~3.8+
- Daikin units: **off or minimal** (ETK6500 alone can handle the load without backup)
- Exception: if electricity is very cheap, Daikin can pre-heat rooms to reduce ETK6500 cycling

#### Mode B: Cool weather (outdoor -5°C to +5°C)
- ETK6500 compressor near or at max capacity
- Daikin units: **ON at moderate output** to prevent ETK6500 backup heater from activating
- Daikin COP in this range: 3.3-4.5 (much better than ETK6500 backup at COP 1.0)
- Use Ohmigo to lower ETK6500 room setpoint by 1-2°C to reduce compressor demand

#### Mode C: Cold weather (outdoor -15°C to -5°C)
- ETK6500 compressor maxed out, backup heater running 1-4 kW
- Daikin units: **ON at high output** — this is where they save the most electricity
- Daikin COP: 2.0-3.3 (still 2-3x better than backup heater COP 1.0)
- Use Ohmigo to reduce ETK6500 setpoint to force backup heater off or to lower stages
- Savings potential: replacing 2 kW of backup heater with Daikin at COP 2.5 saves ~1.2 kW electricity

#### Mode D: Extreme cold (outdoor < -15°C)
- All systems running at max
- Daikin COP approaching 1.5-2.0 — still better than backup heater COP 1.0
- Keep Daikins running unless COP drops below ~1.2 (approximately below -22°C)
- Below -22°C: consider Daikins off, let ETK6500 + full backup handle it

#### Mode E: Electricity price optimization
- **When spot price is very low** (e.g., bottom quartile): ETK6500 at full power via Ohmigo high setpoint, charge DHW tank to max (~60°C), Daikins can pre-heat rooms above normal setpoint
- **When spot price is very high** (e.g., top quartile): reduce ETK6500 via Ohmigo low setpoint, use stored DHW tank heat, coast on thermal mass, Daikins off unless they prevent backup heater activation
- **When spot price is moderate**: follow Mode A-D based on outdoor temperature

### 4.3 Decision Matrix (simplified)

```
INPUT: outdoor_temp, spot_price_quartile, etk6500_backup_active

IF spot_price == "very_high":
    daikin_mode = "off"
    ohmigo_setpoint = low (coast on thermal mass)

ELIF spot_price == "very_low":
    daikin_mode = "preheat" (set 1-2°C above normal)
    ohmigo_setpoint = high (charge tank, run compressor hard)

ELSE:  # normal pricing — optimize for COP
    IF outdoor_temp > 5:
        daikin_mode = "off"
        ohmigo_setpoint = normal

    ELIF outdoor_temp > -5:
        daikin_mode = "on"
        daikin_setpoint = normal room temp
        ohmigo_setpoint = normal or slightly reduced

    ELIF outdoor_temp > -15:
        daikin_mode = "on_high"
        daikin_setpoint = normal room temp
        ohmigo_setpoint = reduced by 1-2°C (force backup off)

    ELSE:  # below -15
        daikin_mode = "on_high"
        ohmigo_setpoint = normal (need all sources)
```

---

## 5. Home Assistant Implementation Notes

### 5.1 Required Integrations

| Integration | Purpose |
|---|---|
| Daikin AC | Control both Daikin XTH 30 units (via BRP069C4x WiFi adapters) |
| Weather integration or outdoor temp sensor | Get current outdoor temperature |
| Nordpool / Tibber / Entsoe | Get current and forecast electricity spot prices |
| Ohmigo | Control ETK6500 behavior via virtual room temperature setpoint |
| ETK6500 sensors (if available) | Monitor compressor status, backup heater stages, tank temp, return temp |

### 5.2 Key Entities to Create/Track

- `sensor.outdoor_temperature` — current outdoor temp
- `sensor.electricity_spot_price` — current spot price (SEK-cents/kWh)
- `sensor.electricity_price_quartile` — derived: which quartile of today's prices is current hour in
- `climate.daikin_unit_1` and `climate.daikin_unit_2` — Daikin AC entities
- `sensor.daikin_1_energy` and `sensor.daikin_2_energy` — Daikin energy consumption
- `input_number.ohmigo_setpoint` — virtual setpoint to send to Ohmigo/ETK6500
- `binary_sensor.etk6500_backup_active` — whether backup heater is running (derive from power monitoring if possible)
- `sensor.etk6500_compressor_frequency` — if available, shows how hard compressor is working

### 5.3 Automation Templates

The automations should run every 5-15 minutes (or on state change of outdoor temp / price) and adjust:

1. **Daikin on/off and setpoint** based on outdoor temp and price
2. **Ohmigo setpoint** to modulate ETK6500 demand
3. **Logging** of decisions for later analysis

### 5.4 COP Lookup Functions

Implement as template sensors or helper functions:

```yaml
# Daikin COP estimate based on outdoor temperature
# Linear interpolation between known data points
# Returns COP for a single Daikin XTH 30 unit
template:
  - sensor:
      - name: "Daikin Estimated COP"
        unit_of_measurement: ""
        state: >
          {% set t = states('sensor.outdoor_temperature') | float(0) %}
          {% set points = [(-25,1.3),(-20,1.6),(-15,2.0),(-10,2.5),(-7,2.8),(-2,3.3),(2,3.9),(7,5.01),(12,6.0),(15,6.8)] %}
          {% set ns = namespace(cop=1.0) %}
          {% if t <= points[0][0] %}
            {% set ns.cop = points[0][1] %}
          {% elif t >= points[-1][0] %}
            {% set ns.cop = points[-1][1] %}
          {% else %}
            {% for i in range(points | length - 1) %}
              {% if points[i][0] <= t < points[i+1][0] %}
                {% set frac = (t - points[i][0]) / (points[i+1][0] - points[i][0]) %}
                {% set ns.cop = points[i][1] + frac * (points[i+1][1] - points[i][1]) %}
              {% endif %}
            {% endfor %}
          {% endif %}
          {{ ns.cop | round(2) }}
```

```yaml
# ETK6500 system COP estimate (including backup heater penalty)
# Based on estimated heat demand curve for ~190m² home
template:
  - sensor:
      - name: "ETK6500 Estimated System COP"
        unit_of_measurement: ""
        state: >
          {% set t = states('sensor.outdoor_temperature') | float(0) %}
          {% set points = [(-20,1.67),(-15,1.72),(-10,2.0),(-5,2.58),(0,3.65),(5,3.82),(10,4.0),(15,4.12)] %}
          {% set ns = namespace(cop=1.5) %}
          {% if t <= points[0][0] %}
            {% set ns.cop = points[0][1] %}
          {% elif t >= points[-1][0] %}
            {% set ns.cop = points[-1][1] %}
          {% else %}
            {% for i in range(points | length - 1) %}
              {% if points[i][0] <= t < points[i+1][0] %}
                {% set frac = (t - points[i][0]) / (points[i+1][0] - points[i][0]) %}
                {% set ns.cop = points[i][1] + frac * (points[i+1][1] - points[i][1]) %}
              {% endif %}
            {% endfor %}
          {% endif %}
          {{ ns.cop | round(2) }}
```

### 5.5 Safety Constraints

- **Never turn off ETK6500 ventilation fan** — it provides mandatory building ventilation
- **Never let ETK6500 DHW tank drop below 45°C** — risk of inadequate hot water
- **Never let indoor temperature drop below 17°C** — ETK6500 requires minimum indoor temp for efficient defrost/operation
- **Daikin units should not run in heating mode below -30°C** — rated operational limit
- **Monitor Daikin defrost cycles** — below -10°C defrost frequency increases, reducing effective COP further
- **Respect ETK6500 return temperature limit** — must not exceed 48°C for radiator systems, 35°C for underfloor heating

---

## 6. Expected Savings Analysis

### 6.1 Scenario: -10°C outdoor, normal electricity price

**Without Daikins (ETK6500 alone):**
- Heat demand: ~9.0 kW
- Compressor: 6.5 kW heat @ COP 3.24 -> 2.01 kW elec
- Backup heater: 2.5 kW heat @ COP 1.0 -> 2.5 kW elec
- Total electricity: **4.51 kW** for 9.0 kW heat (system COP 2.0)

**With Daikins assisting (2 units @ ~1.5 kW heat each = 3.0 kW total):**
- Daikin heat: 3.0 kW @ COP 2.5 -> 1.2 kW elec
- Remaining for ETK6500: 6.0 kW heat
- ETK6500 compressor: 6.0 kW @ COP 3.24 -> 1.85 kW elec
- ETK6500 backup heater: 0 kW
- Total electricity: **3.05 kW** for 9.0 kW heat (system COP 2.95)

**Savings: 1.46 kW continuously at -10°C = ~32% reduction in electricity use.**

At 100 SEK-cents/kWh, that's **1.46 kr/hour** or roughly **35 kr/day** at sustained -10°C.

### 6.2 Break-even: when to NOT use Daikins

The Daikins are not beneficial when their COP drops below the ETK6500's *marginal* COP:
- If ETK6500 is NOT using backup -> marginal COP = compressor COP (~3.2-3.8)
- In this case, Daikins are only better above ~+2°C
- If ETK6500 IS using backup -> marginal COP = 1.0
- In this case, Daikins are better at any temperature above -25°C

**Rule of thumb: if the ETK6500 backup heater is active, always run the Daikins.**

---

## 7. Data Sources & Confidence

| Data Point | Confidence | Source |
|---|---|---|
| ETK6500 heat output / input at 35°C and 50°C | **Confirmed** | TD2 manual, page 4 |
| ETK6500 backup heater stages | **Confirmed** | TD2 manual, page 4 |
| Daikin COP at 7°C | **Confirmed** | Daikin spec sheet (daikin-ce.com) |
| Daikin Pdh at -10°C | **Confirmed** | Daikin spec sheet |
| Daikin SCOP | **Confirmed** | 5.17 (Daikin spec sheet) |
| Daikin COP at other temperatures | **Estimated** | Interpolated from confirmed points + typical R32 Nordic curves |
| Heat demand curve for 190 m² | **Estimated** | Generic Swedish house, needs calibration with actual data |
| ETK6500 system COP with backup | **Calculated** | From confirmed compressor data + estimated demand |

**Recommendation:** After implementing, log actual energy consumption (via Daikin energy sensors and whole-house power monitoring) to calibrate the COP curves and heat demand model with real data.

---

---

## 8. Blockheat Integration — Entity Mapping & Implementation Notes

### 8.1 HA Entity Mapping

| Algorithm Input | HA Entity | Notes |
|---|---|---|
| Outdoor temperature | `sensor.daikinap75809_climatecontrol_outdoor_temperature` | From Daikin outdoor unit sensor |
| Electricity price | `sensor.nordpool_kwh_se3_sek_3_10_025` | Current spot price (SEK/kWh) |
| Today's price array | Same sensor, `today` attribute | 96 quarter-hour slots |
| Tomorrow's prices | Same sensor, `tomorrow` attribute | Available after ~13:00 |
| Ohmigo control | `number.ohmigo_temperature_2` | ETK6500 virtual room setpoint |
| Daikin unit 1 | `climate.daikinap75809_room_temperature` | "AC Livingroom" |
| Daikin unit 2 | Not yet in HA | Installed, needs integration setup |
| Daikin energy | `sensor.daikinap75809_climatecontrol_heating_daily_electrical_consumption` | For future calibration |

### 8.2 Implementation Deviations from Ideal

1. **Single Daikin unit only** — second unit installed but not yet integrated into HA. Config supports one climate entity; design accommodates future expansion.
2. **ETK6500 backup heater manually disabled** — the crossover analysis in section 3 assumed backup was active. With backup off, ETK6500 compressor COP is 2.95-4.12 (not dragged down by backup). Daikins primarily provide **capacity supplementation** rather than COP arbitrage.
3. **No backup heater sensor** — since backup is off, outdoor temperature serves as capacity proxy. Below ~0°C the compressor alone may not keep up.
4. **Price quartile replaces simple policy_on** — Daikin decisions use `compute_price_quartile()` (very_low/low/high/very_high) from the Nordpool `today` array, enabling preheat during cheap periods and coast during expensive ones.

### 8.3 Daikin Decision Matrix (as implemented)

```
IF price_quartile == "very_high":
    → Daikin OFF (coast on thermal mass)

ELIF price_quartile == "very_low":
    → Daikin HEAT at (normal_temp + preheat_offset)
    → Pre-charge rooms while electricity is cheap

ELSE (normal pricing — decide by outdoor temp):
    IF no outdoor sensor:
        → Daikin HEAT at normal_temp (safe default)

    ELIF outdoor > mild_threshold (+5°C):
        → Daikin OFF
        → ETK6500 compressor handles everything at COP 3.8+

    ELSE:
        → Daikin HEAT at normal_temp
        → Supplement ETK6500 capacity at any cold temperature
```

### 8.4 Config Parameters

| Parameter | Default | Description |
|---|---|---|
| `daikin_normal_temperature` | 22.0°C | Target temp for normal heating mode |
| `daikin_preheat_offset` | 2.0°C | Added to normal_temp during very_low price preheat |
| `daikin_mild_threshold` | 5.0°C | Above this, Daikin off (ETK6500 handles it) |
| `daikin_min_temp_change` | 0.5°C | Deadband to avoid unnecessary writes |

---

*Report generated March 2026. Based on Qvantum ETK6500 manual (TD2, QCH SV 2317-7) and Daikin Stylish XTH 30 (FTXTA30C/RXTA30C) specifications.*
