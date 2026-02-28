"""Pure computation engine for Blockheat."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

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


def min_numeric(values: Iterable[float | None]) -> float | None:
    """Return minimum numeric value from iterable."""
    candidates = [value for value in values if value is not None]
    return min(candidates) if candidates else None


def to_lower_list(values: Sequence[object] | None) -> list[str]:
    """Normalize list values to lower-case strings."""
    if not values:
        return []
    result: list[str] = []
    for value in values:
        if value is None:
            continue
        result.append(str(value).lower())
    return result


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
    floor_temp: float
    ignore_by_price: bool
    ignore_by_pv: bool
    below_min_floor: bool


@dataclass(slots=True)
class ComfortComputation:
    target: float
    comfort_satisfied: bool
    storage_needs_heat: bool
    boost_clamped: float
    comfort_target_unclamped: float
    storage_target_unclamped: float


@dataclass(slots=True)
class FallbackConditions:
    arm_condition: bool
    release_by_policy: bool
    release_by_recovery: bool
    comfort_min: float | None
    trigger_threshold: float
    release_threshold: float
    cooldown_ok: bool


@dataclass(slots=True)
class FinalTargetComputation:
    target: float
    source: str


@dataclass(slots=True)
class DaikinComputation:
    target_temp: float | None
    should_write: bool
    outdoor_ok: bool
    current_temp: float


@dataclass(slots=True)
class FloorComputation:
    action: str | None
    desired_temp: float
    soft_off_target: float
    use_manual_preset: bool
    hvac_mode_final: str
    schedule_on: bool
    policy_saving: bool


def compute_policy(
    *,
    price: float | None,
    prices_today: Sequence[object] | None,
    minutes_to_block: int,
    price_ignore_below: float,
    pv_now: float | None,
    pv_ignore_above_w: float,
    floor_temp: float | None,
    min_floor_temp: float,
    current_on: bool,
    last_changed: datetime | None,
    now: datetime,
    min_toggle_interval_min: int,
) -> PolicyComputation:
    """Compute policy ON/OFF decision matching blueprint behavior."""
    current_price = as_float(price, 0.0) or 0.0
    current_pv = as_float(pv_now, 0.0) or 0.0
    current_floor = as_float(floor_temp, 0.0) or 0.0

    normalized_prices: list[float] = []
    for raw in prices_today or []:
        numeric = as_float(raw)
        if numeric is not None:
            normalized_prices.append(numeric)

    nslots = as_int(minutes_to_block, 240) // 15
    sorted_desc = sorted(normalized_prices, reverse=True)
    if nslots > 0 and len(sorted_desc) >= nslots:
        cutoff = sorted_desc[nslots - 1]
    else:
        cutoff = DEFAULT_POLICY_CUTOFF

    blocked_now = current_price >= cutoff
    ignore_by_price = price_ignore_below > 0 and current_price < price_ignore_below
    ignore_by_pv = pv_ignore_above_w > 0 and current_pv >= pv_ignore_above_w
    below_min_floor = min_floor_temp > 0 and current_floor < min_floor_temp
    target_on = (
        not (ignore_by_price or ignore_by_pv or below_min_floor)
    ) and blocked_now

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
        floor_temp=current_floor,
        ignore_by_price=ignore_by_price,
        ignore_by_pv=ignore_by_pv,
        below_min_floor=below_min_floor,
    )


def compute_saving_target(
    *,
    outdoor_temp: float | None,
    heatpump_setpoint: float,
    saving_cold_offset_c: float,
    virtual_temperature: float,
    warm_shutdown_outdoor: float,
    control_min_c: float,
    control_max_c: float,
) -> float:
    """Compute saving mode target."""
    if outdoor_temp is not None and outdoor_temp >= warm_shutdown_outdoor:
        target_unclamped = virtual_temperature
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
    comfort_to_heatpump_offset_c: float,
    storage_target_c: float,
    storage_to_heatpump_offset_c: float,
    maintenance_target_c: float,
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
        boost_raw = (cold_threshold - outdoor_temp) / boost_slope_c
    else:
        boost_raw = 0.0
    boost_clamped = clamp(boost_raw, 0.0, max_boost)

    comfort_target_unclamped = (
        comfort_target_c - comfort_to_heatpump_offset_c
    ) + boost_clamped
    storage_target_unclamped = (
        storage_target_c - storage_to_heatpump_offset_c
    ) + boost_clamped

    storage_needs_heat = storage_temp is not None and storage_temp < (
        storage_target_c - comfort_margin_c
    )

    if comfort_satisfied and storage_needs_heat:
        target_unclamped = max(storage_target_unclamped, comfort_target_unclamped)
    elif comfort_satisfied:
        target_unclamped = maintenance_target_c
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


def compute_fallback_conditions(
    *,
    policy_on: bool,
    fallback_active: bool,
    room1_temp: float | None,
    room2_temp: float | None,
    comfort_target_c: float,
    trigger_delta_c: float,
    release_delta_c: float,
    cooldown_minutes: int,
    last_trigger: datetime | None,
    now: datetime,
) -> FallbackConditions:
    """Compute fallback manager conditions."""
    comfort_min = min_numeric((room1_temp, room2_temp))
    trigger_threshold = comfort_target_c - trigger_delta_c
    release_threshold = comfort_target_c - release_delta_c

    if last_trigger is None:
        cooldown_ok = True
    else:
        cooldown_ok = (now - last_trigger).total_seconds() >= (cooldown_minutes * 60)

    arm_condition = (
        (not policy_on)
        and comfort_min is not None
        and comfort_min < trigger_threshold
        and cooldown_ok
        and (not fallback_active)
    )

    release_by_policy = policy_on and fallback_active
    release_by_recovery = (
        (not policy_on)
        and fallback_active
        and comfort_min is not None
        and comfort_min >= release_threshold
    )

    return FallbackConditions(
        arm_condition=arm_condition,
        release_by_policy=release_by_policy,
        release_by_recovery=release_by_recovery,
        comfort_min=comfort_min,
        trigger_threshold=trigger_threshold,
        release_threshold=release_threshold,
        cooldown_ok=cooldown_ok,
    )


def compute_final_target(
    *,
    policy_on: bool,
    fallback_active: bool,
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
            source = "control_min_fallback"
    elif fallback_active:
        selected_unclamped = control_min_c
        source = "fallback_min"
    else:
        if comfort_target is not None:
            selected_unclamped = comfort_target
            source = "comfort"
        elif control_current is not None:
            selected_unclamped = control_current
            source = "control_current"
        else:
            selected_unclamped = control_min_c
            source = "control_min_fallback"

    return FinalTargetComputation(
        target=clamp(selected_unclamped, control_min_c, control_max_c),
        source=source,
    )


def compute_daikin(
    *,
    policy_on: bool,
    current_temp: float | None,
    normal_temperature: float,
    saving_temperature: float,
    min_temp_change: float,
    outdoor_temp: float | None,
    outdoor_temp_threshold: float,
    outdoor_sensor_defined: bool,
) -> DaikinComputation:
    """Compute optional Daikin consumer action."""
    cur_temp = as_float(current_temp, 0.0) or 0.0
    if outdoor_sensor_defined:
        out_temp = (
            as_float(outdoor_temp, DEFAULT_MISSING_OUTDOOR) or DEFAULT_MISSING_OUTDOOR
        )
    else:
        out_temp = DEFAULT_MISSING_OUTDOOR

    outdoor_ok = (
        out_temp >= outdoor_temp_threshold or out_temp == DEFAULT_MISSING_OUTDOOR
    )

    if policy_on and outdoor_ok:
        target_temp = saving_temperature
    elif not policy_on:
        target_temp = normal_temperature
    else:
        target_temp = None

    should_write = (
        target_temp is not None and abs(cur_temp - target_temp) >= min_temp_change
    )

    return DaikinComputation(
        target_temp=target_temp,
        should_write=should_write,
        outdoor_ok=outdoor_ok,
        current_temp=cur_temp,
    )


def compute_floor(
    *,
    policy_on: bool,
    cur_temp: float | None,
    dev_min: float,
    comfort_temp_c: float,
    prefer_preset_manual: bool,
    hvac_mode_when_on: str,
    supported_hvac_modes: Sequence[object] | None,
    preset_modes: Sequence[object] | None,
    soft_off_temp_override_c: object,
    min_keep_temp_c: object,
    schedule_defined: bool,
    schedule_on: bool,
    last_changed: datetime | None,
    min_switch_interval_min: int,
    now: datetime,
) -> FloorComputation:
    """Compute optional floor consumer action."""
    override_raw = (
        "" if soft_off_temp_override_c is None else str(soft_off_temp_override_c)
    )
    if override_raw.strip() != "":
        soft_off_target = as_float(soft_off_temp_override_c, dev_min) or dev_min
    else:
        soft_off_target = dev_min

    cur = as_float(cur_temp, 999.0) or 999.0

    min_keep_raw = "" if min_keep_temp_c is None else str(min_keep_temp_c)
    min_keep_defined = min_keep_raw.strip() != ""
    if min_keep_defined:
        min_keep_temp = as_float(min_keep_temp_c, soft_off_target) or soft_off_target
    else:
        min_keep_temp = soft_off_target

    if policy_on:
        desired_temp = soft_off_target
    elif schedule_on:
        desired_temp = comfort_temp_c
    elif min_keep_defined:
        desired_temp = min_keep_temp
    else:
        desired_temp = soft_off_target

    if last_changed is None:
        enough_time_passed = True
    else:
        enough_time_passed = (now - last_changed).total_seconds() >= (
            min_switch_interval_min * 60
        )

    target_on = desired_temp > (soft_off_target + 0.2)
    currently_soft_off = cur <= (soft_off_target + 0.2)
    need_temp_change = abs(cur - desired_temp) > 0.05

    supported_hvac = to_lower_list(supported_hvac_modes)
    hvac_candidate = (hvac_mode_when_on or "").lower()
    if hvac_candidate and hvac_candidate in supported_hvac:
        hvac_mode_final = hvac_candidate
    elif "heat" in supported_hvac:
        hvac_mode_final = "heat"
    elif "auto" in supported_hvac:
        hvac_mode_final = "auto"
    elif "heat_cool" in supported_hvac:
        hvac_mode_final = "heat_cool"
    elif supported_hvac:
        hvac_mode_final = supported_hvac[0]
    else:
        hvac_mode_final = "heat"

    preset_values = to_lower_list(preset_modes)
    manual_supported = "manual" in preset_values

    action: str | None
    if target_on and (currently_soft_off or need_temp_change) and enough_time_passed:
        action = "set_on"
        use_manual_preset = prefer_preset_manual and manual_supported
    elif (not target_on) and (not currently_soft_off) and enough_time_passed:
        action = "set_soft_off"
        use_manual_preset = manual_supported
    else:
        action = None
        use_manual_preset = False

    return FloorComputation(
        action=action,
        desired_temp=desired_temp,
        soft_off_target=soft_off_target,
        use_manual_preset=use_manual_preset,
        hvac_mode_final=hvac_mode_final,
        schedule_on=schedule_on if schedule_defined else True,
        policy_saving=policy_on,
    )
