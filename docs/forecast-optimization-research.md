# Forecast Optimization Research

> Synthesized design brief for smarter heating decisions using weather forecast and price data.
> Date: 2026-03-15

---

## 1. Current System Health

The Blockheat integration is verified working:

- **Control entity**: `number.ohmigo_temperature_2` receives computed target temperatures
- **Price source**: Nordpool SE3 via `sensor.nordpool_kwh_se3_sek_3_10_025` — `today` attribute holds 96 quarter-hour slots, `tomorrow` populates after ~13:00
- **Policy toggling**: saving/comfort modes alternate correctly based on per-day price ranking
- **Sensor data**: outdoor temp, indoor room temps, and storage temp all read successfully
- **Daikin mode selection** (implemented): `compute_price_quartile()` classifies current price as very_low/low/high/very_high from the Nordpool `today` array. Daikin decisions combine price quartile + outdoor temperature to select between off, normal, preheat, and capacity_assist modes
- **Daikin preheat** (implemented): during `very_low` price slots, the Daikin preheats rooms at `normal_temp + preheat_offset` (default +2.0). HVAC mode control via `climate.turn_on`/`climate.turn_off`

The system works and now has basic price-aware Daikin control, but leaves further money on the table — it ranks slots within a single calendar day, uses simple quartile boundaries rather than COP-weighted true cost, and ignores thermal dynamics entirely.

---

## 2. Thermal Pre-Charging

### Problem
Hydronic floor heating has a **4–8 hour time constant** (τ). The current system toggles saving mode at the boundary of expensive slots, but the thermal mass means:
- Temperature drops are barely felt during short saving windows (wasted opportunity to save harder)
- Temperature hasn't recovered when comfort is needed after a long saving window

### Strategy
**Pre-heat before expensive periods** — push the building slightly above setpoint during cheap hours so it can coast through expensive ones.

Key formula for cooling prediction:

```
T(t) = T_outdoor + (T_start - T_outdoor) × e^(-t/τ)
```

Where:
- `T_start` = indoor temperature at start of saving period
- `T_outdoor` = outdoor temperature (or forecast)
- `τ` = building time constant (hours), initially configured, later auto-calibrated

**Maximum saving duration** before hitting minimum acceptable temperature:

```
t_max = τ × ln((T_start - T_outdoor) / (T_min - T_outdoor))
```

### Example
With τ=6h, T_start=22°C, T_outdoor=-5°C, T_min=19°C:
```
t_max = 6 × ln((22-(-5)) / (19-(-5))) = 6 × ln(27/24) = 6 × 0.118 = 0.7h
```
At -5°C the building cools fast — only ~42 minutes of saving is safe. At +5°C the same calculation yields ~2.4h.

### Pre-heat parameters
- `preheat_lead_minutes` (default: 60) — how far before an expensive window to start boosting
- `preheat_target_offset_c` (default: 1.5) — degrees above normal setpoint during pre-heat

> **Status**: Basic Daikin preheat is implemented via `daikin_preheat_offset` (default 2.0) triggered by `very_low` price quartile. This section describes the more sophisticated *hydronic* pre-charging with lead time awareness and thermal prediction, which would build on top of the existing Daikin preheat.

---

## 3. Rolling Price + Weather Optimization

### Problem
The current engine ranks price slots within `today` only. This creates boundary artifacts:
- The cheapest slot of tomorrow at 01:00 may be cheaper than the most expensive "cheap" slot today
- No ability to shift load across the midnight boundary

### Strategy
Replace per-day ranking with a **36-hour rolling window** combining `today` + `tomorrow` price arrays (when available).

```
window = today_prices[now:] + tomorrow_prices[:]   # up to 36h ahead
ranked = sort(window, key=lambda slot: score(slot))
```

Joint ranking signal incorporating thermal demand:

```
score(slot) = price(slot) × thermal_demand_factor(slot)
```

Where `thermal_demand_factor` increases when it's cold (more kWh needed per degree), making expensive cold slots even more expensive in real terms.

### Data sources
- **Price**: Nordpool sensor `today` (list of 96 values), `tomorrow` (list, available after ~13:00)
- **Weather forecast**: `weather.*` entity → `forecast` attribute (Met.no provides hourly forecasts)
- Fallback: use current outdoor temp as flat forecast when no forecast entity is configured

### Suggested config
- `forecast_lookahead_hours` (default: 36) — rolling window size
- `weather_entity` — HA weather entity ID for forecast data

---

## 4. COP-Aware True Cost

### Problem
Raw electricity price ignores heat pump efficiency. A heat pump at 0°C outdoor has COP ≈ 3.0 (3 kWh heat per 1 kWh electricity). At -15°C, COP drops to ~1.8. Heating during cold periods costs almost twice as much per unit of heat.

### Strategy
Rank slots by **true cost of heat**, not raw electricity price:

```
true_cost(t) = price(t) / COP(T_outdoor(t))
```

### COP model
Linear approximation sufficient for ranking purposes:

```
COP(T_out) ≈ 3.0 + 0.08 × (T_out - 0)
```

| T_outdoor | COP  | Price 1.00 SEK/kWh → true_cost |
|-----------|------|-------------------------------|
| -15°C     | 1.80 | 0.556 SEK/kWh_thermal         |
| -5°C      | 2.60 | 0.385 SEK/kWh_thermal         |
| 0°C       | 3.00 | 0.333 SEK/kWh_thermal         |
| +10°C     | 3.80 | 0.263 SEK/kWh_thermal         |

This reshuffles slot rankings significantly: a "cheap" electricity slot during extreme cold may actually be more expensive for heating than a "medium" slot during mild weather.

### Refinement path
The linear COP model can later be replaced with a manufacturer-specific curve or auto-calibrated from `energy` sensor data vs outdoor temp.

---

## 5. Heat Loss Model

### Problem
Without knowing how fast the building loses heat, the engine can't predict whether a saving window is safe (will temperature stay above minimum?) or how much pre-heat is needed.

### Strategy
Simple **UA-value model** auto-calibrated from sensor history:

```
Q_loss = UA × (T_indoor - T_outdoor)    [watts]
```

Where UA (W/K) is the building's overall heat loss coefficient.

### Auto-calibration
During stable periods (no heating, no solar gain), temperature decay reveals UA:

```
UA = m_thermal × c_p × (ΔT_indoor / Δt) / (T_indoor - T_outdoor)
```

Practically, the system can estimate τ from observed cooling curves:
1. Detect saving periods where heating is off
2. Fit exponential decay to indoor temperature readings
3. Extract τ, then `UA = C_thermal / τ`

The thermal mass `C_thermal` (J/K) can be configured or co-estimated. For ranking and prediction purposes, only τ is needed.

### Application
Given τ and the cooling model, the engine can:
- **Predict** indoor temperature at end of any proposed saving window
- **Reject** saving windows that would breach T_min
- **Size** pre-heat — calculate how many degrees above setpoint to target before an expensive window

---

## 6. Architecture Sketch

### Design principles
- **Engine stays pure**: all new computations go into `engine.py` as stateless functions
- **Runtime orchestrates**: `runtime.py` fetches forecast data and passes it to engine functions
- **Opt-in**: behind `enable_forecast_optimization` boolean, existing behavior unchanged when disabled

### New engine functions

```python
# engine.py additions (sketch)

def estimate_cop(t_outdoor: float) -> float:
    """Linear COP approximation."""
    return max(1.5, 3.0 + 0.08 * t_outdoor)

def true_cost(price: float, t_outdoor: float) -> float:
    """Cost per kWh of thermal energy."""
    return price / estimate_cop(t_outdoor)

def predict_cooling(
    t_start: float, t_outdoor: float, tau_hours: float, duration_hours: float
) -> float:
    """Predict indoor temp after duration_hours of no heating."""
    import math
    return t_outdoor + (t_start - t_outdoor) * math.exp(-duration_hours / tau_hours)

def max_saving_duration(
    t_start: float, t_outdoor: float, t_min: float, tau_hours: float
) -> float:
    """Max hours of saving before hitting t_min."""
    import math
    if t_start <= t_min or t_start <= t_outdoor:
        return 0.0
    ratio = (t_start - t_outdoor) / (t_min - t_outdoor)
    if ratio <= 1.0:
        return 0.0
    return tau_hours * math.log(ratio)

def rank_slots_rolling(
    prices: list[float],
    outdoor_temps: list[float],
    saving_ratio: float,
) -> list[bool]:
    """Rank slots by true cost over rolling window, return saving mask."""
    costs = [true_cost(p, t) for p, t in zip(prices, outdoor_temps)]
    threshold_idx = int(len(costs) * saving_ratio)
    sorted_costs = sorted(range(len(costs)), key=lambda i: costs[i], reverse=True)
    saving_slots = set(sorted_costs[:threshold_idx])
    return [i in saving_slots for i in range(len(costs))]
```

### Runtime changes

```python
# runtime.py additions (sketch)

async def _fetch_forecast(self) -> list[tuple[float, float]]:
    """Fetch (price, outdoor_temp) tuples for rolling window."""
    # 1. Read today + tomorrow prices from Nordpool sensor
    # 2. Read hourly forecast from weather entity
    # 3. Align timestamps, interpolate as needed
    # 4. Return merged slot list
    ...

async def _apply_forecast_optimization(self) -> None:
    """Override saving mask with forecast-aware ranking."""
    if not self._config.get(CONF_ENABLE_FORECAST):
        return
    slots = await self._fetch_forecast()
    prices, temps = zip(*slots)
    mask = engine.rank_slots_rolling(list(prices), list(temps), self._saving_ratio)
    # Apply mask + thermal safety checks
    ...
```

### Config flow additions
Step 2 (tuning wizard) gets a new **Forecast** section:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `weather_entity` | entity selector | — | HA weather entity for forecast |
| `forecast_lookahead_hours` | int | 36 | Rolling window size |
| `preheat_lead_minutes` | int | 60 | Pre-heat start before expensive window |
| `preheat_target_offset_c` | float | 1.5 | Degrees above setpoint during pre-heat |
| `enable_forecast_optimization` | bool | false | Master switch for forecast features |

### Data flow (extended)

```
HA entity states (price, outdoor temp, room temps, PV)
  + weather forecast (hourly outdoor temps)
  + Nordpool tomorrow prices
  → runtime reads states + forecast
  → engine.rank_slots_rolling() → COP-aware saving mask
  → engine.predict_cooling() → thermal safety check
  → engine.compute_comfort() → comfort target (possibly with pre-heat offset)
  → engine.compute_final() → final target + deadband check
  → runtime writes control entity + fires events
  → coordinator publishes snapshot → sensors update
```

---

## 7. Implementation Roadmap

### Phase 0 — Price-aware Daikin control (DONE)
- `compute_price_quartile()` classifies current price vs today's 96-slot array
- Daikin mode selection: very_high -> off, very_low -> preheat, else outdoor-temp-based (off/normal/capacity_assist)
- HVAC mode control (`climate.turn_on`/`turn_off`) + temperature writes
- Config: `daikin_preheat_offset`, `daikin_mild_threshold`, `daikin_cold_threshold`, `daikin_disable_threshold`

### Phase 1 — True cost ranking (low risk)
- Add `estimate_cop()` and `true_cost()` to engine
- Replace simple quartile classification with COP-weighted true-cost ranking
- Config: `weather_entity` (optional, for forecast temps)
- No thermal model needed yet

### Phase 2 — Rolling window (medium risk)
- Merge `today` + `tomorrow` prices into rolling window
- Align with forecast temperatures
- Config: `forecast_lookahead_hours`

### Phase 3 — Thermal pre-charging (higher complexity)
- Add cooling prediction and max saving duration
- Implement pre-heat logic with offset
- Auto-calibrate τ from observed cooling curves
- Config: `preheat_lead_minutes`, `preheat_target_offset_c`

### Phase 4 — Closed-loop calibration
- Track actual vs predicted indoor temperatures
- Auto-tune τ and COP model parameters
- Dashboard card showing optimization savings estimate

---

## Appendix: Available HA Data Sources

| Source | Entity pattern | Key attributes |
|--------|---------------|----------------|
| Nordpool SE3 prices | `sensor.nordpool_kwh_se3_*` | `today` (list[96]), `tomorrow` (list[96]), `current_price` |
| Weather forecast | `weather.*` | `forecast` (list of hourly dicts with `temperature`) |
| Outdoor temp | Configured in Blockheat | Current state as float |
| Indoor temps | Configured in Blockheat | Room sensor states |
| Storage temp | Configured in Blockheat | Buffer/tank temperature |
