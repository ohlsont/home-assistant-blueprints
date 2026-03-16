"""Validation helpers for Blockheat config tuning."""

from __future__ import annotations

from typing import Any

_NON_NEGATIVE_KEYS: tuple[str, ...] = (
    "minutes_to_block",
    "price_ignore_below",
    "pv_ignore_above_w",
    "daikin_preheat_offset",
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
    """Return an error key when tuning values are invalid."""
    for key in _NON_NEGATIVE_KEYS:
        value = _as_float(values.get(key))
        if value is not None and value < 0:
            return "invalid_non_negative"

    return None
