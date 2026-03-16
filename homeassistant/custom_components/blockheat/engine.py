"""Pure computation engine for Blockheat."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

DEFAULT_POLICY_CUTOFF = 9999.0
DEFAULT_MISSING_OUTDOOR = 999.0


def as_float(value: Any, default: float | None = None) -> float | None:
    """Convert a value to float or return default."""
    if value is None:
        return default
    if isinstance(value, str) and value.strip() == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: int = 0) -> int:
    """Convert a value to int or return default."""
    if value is None:
        return default
    if isinstance(value, str) and value.strip() == "":
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def clamp(value: float, min_value: float, max_value: float) -> float:
    """Clamp a value."""
    return min(max_value, max(min_value, value))


@dataclass(slots=True)
class PolicyComputation:
    target_on: bool
    should_turn_on: bool
    should_turn_off: bool
    enough_time_passed: bool
    current_on: bool
    blocked_now: bool
    cutoff: float
    price: float
    pv_now: float
    ignore_by_price: bool
    ignore_by_pv: bool
    cop_weighting_active: bool = False
    current_true_cost: float | None = None


@dataclass(slots=True)
class ComfortComputation:
    target: float
    comfort_satisfied: bool
    storage_needs_heat: bool
    boost_clamped: float
    comfort_target_unclamped: float
    storage_target_unclamped: float


@dataclass(slots=True)
class FinalTargetComputation:
    target: float
    source: str


@dataclass(slots=True)
class DaikinComputation:
    target_temp: float | None
    target_hvac_mode: str | None
    should_write_temp: bool
    should_write_mode: bool
    outdoor_ok: bool
    current_temp: float
    current_hvac_mode: str
    mode: str
    price_quartile: str


COP_FLOOR = 1.5
COP_BASE = 3.0
COP_SLOPE = 0.08


def estimate_cop(t_outdoor: float) -> float:
    """Estimate heat pump COP from outdoor temperature (linear model)."""
    return max(COP_FLOOR, COP_BASE + COP_SLOPE * t_outdoor)


def true_cost(price: float, t_outdoor: float) -> float:
    """Compute true cost per unit of heat: price / COP."""
    return price / estimate_cop(t_outdoor)


def rank_slots_true_cost(
    prices: list[float],
    outdoor_temps: list[float | None],
    minutes_to_block: int,
) -> tuple[float, list[float]]:
    """Rank price slots by COP-weighted true cost.

    Returns (cutoff_true_cost, effective_costs) where effective_costs is
    parallel to prices and outdoor_temps.
    """
    effective_costs: list[float] = []
    for i, p in enumerate(prices):
        temp = outdoor_temps[i] if i < len(outdoor_temps) else None
        if temp is not None:
            effective_costs.append(true_cost(p, temp))
        else:
            effective_costs.append(p)

    # minutes_to_block is a per-day budget.  When the price window spans
    # more than 24 slots (today + tomorrow), scale the blocking budget
    # proportionally so "block 4 h/day" stays 4 h/day, not 4 h across 2 days.
    nslots_per_day = as_int(minutes_to_block, 240) // 15
    num_days = max(1, len(effective_costs) // 24) if effective_costs else 1
    nslots = nslots_per_day * num_days
    sorted_desc = sorted(effective_costs, reverse=True)
    if nslots > 0 and len(sorted_desc) >= nslots:
        cutoff = sorted_desc[nslots - 1]
    else:
        cutoff = DEFAULT_POLICY_CUTOFF

    return cutoff, effective_costs


def compute_policy(
    *,
    price: float | None,
    prices_today: Sequence[object] | None,
    minutes_to_block: int,
    price_ignore_below: float,
    pv_now: float | None,
    pv_ignore_above_w: float,
    current_on: bool,
    last_changed: datetime | None,
    now: datetime,
    min_toggle_interval_min: int,
    use_cop_weighting: bool = False,
    outdoor_temps_by_slot: list[float | None] | None = None,
    current_hour_index: int | None = None,
) -> PolicyComputation:
    """Compute policy ON/OFF decision matching integration behavior."""
    current_price = as_float(price, 0.0) or 0.0
    current_pv = as_float(pv_now, 0.0) or 0.0

    normalized_prices: list[float] = []
    for raw in prices_today or []:
        numeric = as_float(raw)
        if numeric is not None:
            normalized_prices.append(numeric)

    cop_active = False
    current_true_cost: float | None = None

    if use_cop_weighting and outdoor_temps_by_slot is not None:
        cutoff, effective_costs = rank_slots_true_cost(
            normalized_prices, outdoor_temps_by_slot, minutes_to_block
        )
        cop_active = True

        hour_idx = current_hour_index if current_hour_index is not None else now.hour
        if 0 <= hour_idx < len(effective_costs):
            current_true_cost = effective_costs[hour_idx]
            blocked_now = current_true_cost >= cutoff
        else:
            blocked_now = current_price >= cutoff
    else:
        nslots = as_int(minutes_to_block, 240) // 15
        sorted_desc = sorted(normalized_prices, reverse=True)
        if nslots > 0 and len(sorted_desc) >= nslots:
            cutoff = sorted_desc[nslots - 1]
        else:
            cutoff = DEFAULT_POLICY_CUTOFF
        blocked_now = current_price >= cutoff
    ignore_by_price = price_ignore_below > 0 and current_price < price_ignore_below
    ignore_by_pv = pv_ignore_above_w > 0 and current_pv >= pv_ignore_above_w
    target_on = (not (ignore_by_price or ignore_by_pv)) and blocked_now

    if last_changed is None:
        enough_time_passed = True
    else:
        elapsed = (now - last_changed).total_seconds()
        enough_time_passed = elapsed >= (min_toggle_interval_min * 60)

    should_turn_on = target_on and (not current_on) and enough_time_passed
    should_turn_off = (not target_on) and current_on and enough_time_passed

    return PolicyComputation(
        target_on=target_on,
        should_turn_on=should_turn_on,
        should_turn_off=should_turn_off,
        enough_time_passed=enough_time_passed,
        current_on=current_on,
        blocked_now=blocked_now,
        cutoff=cutoff,
        price=current_price,
        pv_now=current_pv,
        ignore_by_price=ignore_by_price,
        ignore_by_pv=ignore_by_pv,
        cop_weighting_active=cop_active,
        current_true_cost=current_true_cost,
    )


def compute_saving_target(
    *,
    outdoor_temp: float | None,
    heatpump_setpoint: float,
    saving_cold_offset_c: float,
    warm_shutdown_outdoor: float,
    control_min_c: float,
    control_max_c: float,
) -> float:
    """Compute saving mode target."""
    if outdoor_temp is not None and outdoor_temp >= warm_shutdown_outdoor:
        target_unclamped = heatpump_setpoint + 1.0
    else:
        target_unclamped = heatpump_setpoint - saving_cold_offset_c
    return clamp(target_unclamped, control_min_c, control_max_c)


def compute_comfort_target(
    *,
    room1_temp: float | None,
    room2_temp: float | None,
    storage_temp: float | None,
    outdoor_temp: float | None,
    comfort_target_c: float,
    storage_target_c: float,
    heatpump_offset_c: float,
    heatpump_setpoint: float,
    comfort_margin_c: float,
    cold_threshold: float,
    max_boost: float,
    boost_slope_c: float,
    control_min_c: float,
    control_max_c: float,
) -> ComfortComputation:
    """Compute comfort mode target."""
    comfort_satisfied = (
        room1_temp is not None
        and room2_temp is not None
        and room1_temp >= (comfort_target_c - comfort_margin_c)
        and room2_temp >= (comfort_target_c - comfort_margin_c)
    )

    if outdoor_temp is not None and outdoor_temp < cold_threshold:
        if boost_slope_c > 0:
            boost_raw = (cold_threshold - outdoor_temp) / boost_slope_c
        else:
            boost_raw = max_boost
    else:
        boost_raw = 0.0
    boost_clamped = clamp(boost_raw, 0.0, max_boost)

    comfort_target_unclamped = (comfort_target_c - heatpump_offset_c) + boost_clamped
    storage_target_unclamped = (storage_target_c - heatpump_offset_c) + boost_clamped

    storage_needs_heat = storage_temp is not None and storage_temp < (
        storage_target_c - comfort_margin_c
    )

    if comfort_satisfied and storage_needs_heat:
        target_unclamped = max(storage_target_unclamped, comfort_target_unclamped)
    elif comfort_satisfied:
        target_unclamped = heatpump_setpoint
    else:
        target_unclamped = comfort_target_unclamped

    target = clamp(target_unclamped, control_min_c, control_max_c)
    return ComfortComputation(
        target=target,
        comfort_satisfied=comfort_satisfied,
        storage_needs_heat=storage_needs_heat,
        boost_clamped=boost_clamped,
        comfort_target_unclamped=comfort_target_unclamped,
        storage_target_unclamped=storage_target_unclamped,
    )


def compute_final_target(
    *,
    policy_on: bool,
    saving_target: float | None,
    comfort_target: float | None,
    control_current: float | None,
    control_min_c: float,
    control_max_c: float,
) -> FinalTargetComputation:
    """Compute final routed target for control writer."""
    if policy_on:
        if saving_target is not None:
            selected_unclamped = saving_target
            source = "saving"
        elif control_current is not None:
            selected_unclamped = control_current
            source = "control_current"
        else:
            selected_unclamped = control_min_c
            source = "control_min_default"
    else:
        if comfort_target is not None:
            selected_unclamped = comfort_target
            source = "comfort"
        elif control_current is not None:
            selected_unclamped = control_current
            source = "control_current"
        else:
            selected_unclamped = control_min_c
            source = "control_min_default"

    return FinalTargetComputation(
        target=clamp(selected_unclamped, control_min_c, control_max_c),
        source=source,
    )


def compute_price_quartile(current_price: float, prices: Sequence[float]) -> str:
    """Return price quartile based on position in today's prices.

    Returns 'very_low', 'low', 'high', or 'very_high'.
    """
    if not prices:
        return "low"

    sorted_prices = sorted(prices)
    n = len(sorted_prices)
    q25 = sorted_prices[n // 4]
    q75 = sorted_prices[(3 * n) // 4]

    if current_price <= q25:
        return "very_low"
    if current_price >= q75:
        return "very_high"
    median = sorted_prices[n // 2]
    if current_price <= median:
        return "low"
    return "high"


def compute_daikin(
    *,
    current_temp: float | None,
    current_hvac_mode: str | None,
    normal_temperature: float,
    preheat_offset: float,
    min_temp_change: float,
    outdoor_temp: float | None,
    mild_threshold: float,
    cold_threshold: float,
    disable_threshold: float,
    outdoor_sensor_defined: bool,
    price_quartile: str,
) -> DaikinComputation:
    """Compute Daikin consumer action based on price quartile and outdoor temp."""
    cur_temp = as_float(current_temp, 0.0) or 0.0
    cur_mode = current_hvac_mode or "off"

    if outdoor_sensor_defined:
        parsed = as_float(outdoor_temp)
        out_temp = parsed if parsed is not None else DEFAULT_MISSING_OUTDOOR
    else:
        out_temp = DEFAULT_MISSING_OUTDOOR

    outdoor_ok = out_temp >= disable_threshold or out_temp == DEFAULT_MISSING_OUTDOOR

    target_temp: float | None = None
    target_hvac_mode: str | None = None
    mode: str = "off"

    if price_quartile == "very_high":
        target_hvac_mode = "off"
        mode = "off"
    elif price_quartile == "very_low":
        target_temp = normal_temperature + preheat_offset
        target_hvac_mode = "heat"
        mode = "preheat"
    elif not outdoor_ok:
        target_hvac_mode = "off"
        mode = "off"
    elif out_temp == DEFAULT_MISSING_OUTDOOR:
        target_temp = normal_temperature
        target_hvac_mode = "heat"
        mode = "normal"
    elif out_temp > mild_threshold:
        target_hvac_mode = "off"
        mode = "off"
    elif out_temp > cold_threshold:
        target_temp = normal_temperature
        target_hvac_mode = "heat"
        mode = "normal"
    else:
        target_temp = normal_temperature
        target_hvac_mode = "heat"
        mode = "capacity_assist"

    should_write_temp = (
        target_temp is not None and abs(cur_temp - target_temp) >= min_temp_change
    )
    should_write_mode = target_hvac_mode is not None and target_hvac_mode != cur_mode

    return DaikinComputation(
        target_temp=target_temp,
        target_hvac_mode=target_hvac_mode,
        should_write_temp=should_write_temp,
        should_write_mode=should_write_mode,
        outdoor_ok=outdoor_ok,
        current_temp=cur_temp,
        current_hvac_mode=cur_mode,
        mode=mode,
        price_quartile=price_quartile,
    )
