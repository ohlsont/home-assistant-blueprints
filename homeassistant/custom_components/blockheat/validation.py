"""Validation helpers for Blockheat config tuning."""

from __future__ import annotations

from typing import Any

_NON_NEGATIVE_KEYS: tuple[str, ...] = (
    "minutes_to_block",
    "price_ignore_below",
    "pv_ignore_above_w",
    "min_toggle_interval_min",
    "saving_helper_write_delta_c",
    "comfort_helper_write_delta_c",
    "final_helper_write_delta_c",
    "control_write_delta_c",
    "electric_fallback_delta_c",
    "release_delta_c",
    "electric_fallback_minutes",
    "electric_fallback_cooldown_minutes",
    "daikin_min_temp_change",
    "floor_min_switch_interval_min",
)


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def validate_tuning_values(values: dict[str, Any]) -> str | None:
    """Return an error key when cross-field tuning values are invalid."""
    control_min = _as_float(values.get("control_min_c"))
    control_max = _as_float(values.get("control_max_c"))
    if (
        control_min is not None
        and control_max is not None
        and control_min > control_max
    ):
        return "invalid_control_range"

    boost_slope = _as_float(values.get("boost_slope_c"))
    if boost_slope is not None and boost_slope <= 0:
        return "invalid_boost_slope"

    for key in _NON_NEGATIVE_KEYS:
        value = _as_float(values.get(key))
        if value is not None and value < 0:
            return "invalid_non_negative"

    return None
