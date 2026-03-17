"""Validation helper tests for Blockheat."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import SimpleNamespace


def _validate(blockheat_env: SimpleNamespace, values: dict[str, object]) -> str | None:
    config_flow = importlib.import_module(
        "homeassistant.custom_components.blockheat.config_flow"
    )
    return config_flow.validate_tuning_values(values)


def test_validate_tuning_values_rejects_negative_non_negative_field(
    blockheat_env: SimpleNamespace,
) -> None:
    assert _validate(blockheat_env, {"minutes_to_block": -1}) == "invalid_non_negative"


def test_validate_tuning_values_accepts_valid_and_blank_values(
    blockheat_env: SimpleNamespace,
) -> None:
    assert (
        _validate(
            blockheat_env,
            {
                "minutes_to_block": 240,
                "price_ignore_below": 0.6,
                "pv_ignore_above_w": "",
            },
        )
        is None
    )
