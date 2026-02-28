"""Validation helper tests for Blockheat."""

from __future__ import annotations

import importlib
from types import SimpleNamespace


def _validate(blockheat_env: SimpleNamespace, values: dict[str, object]) -> str | None:
    validation = importlib.import_module(
        "homeassistant.custom_components.blockheat.validation"
    )
    return validation.validate_tuning_values(values)


def test_validate_tuning_values_rejects_invalid_control_range(
    blockheat_env: SimpleNamespace,
) -> None:
    assert (
        _validate(blockheat_env, {"control_min_c": 25.0, "control_max_c": 20.0})
        == "invalid_control_range"
    )


def test_validate_tuning_values_rejects_invalid_boost_slope(
    blockheat_env: SimpleNamespace,
) -> None:
    assert _validate(blockheat_env, {"boost_slope_c": 0}) == "invalid_boost_slope"


def test_validate_tuning_values_rejects_negative_non_negative_field(
    blockheat_env: SimpleNamespace,
) -> None:
    assert (
        _validate(blockheat_env, {"electric_fallback_minutes": -1})
        == "invalid_non_negative"
    )


def test_validate_tuning_values_accepts_valid_and_blank_values(
    blockheat_env: SimpleNamespace,
) -> None:
    assert (
        _validate(
            blockheat_env,
            {
                "control_min_c": 18,
                "control_max_c": 24,
                "boost_slope_c": 5,
                "electric_fallback_minutes": "",
                "floor_min_switch_interval_min": None,
            },
        )
        is None
    )
