"""Diagnostics entity mapping tests."""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any

import pytest


def _seed_domain_data(
    blockheat_env: SimpleNamespace,
    fake_hass: Any,
    entry: Any,
    snapshot: dict[str, Any],
) -> None:
    coordinator = blockheat_env.coordinator.BlockheatCoordinator(fake_hass)
    coordinator.async_set_updated_data(snapshot)
    fake_hass.data.setdefault(blockheat_env.const.DOMAIN, {})
    fake_hass.data[blockheat_env.const.DOMAIN][entry.entry_id] = {
        "coordinator": coordinator
    }


@pytest.mark.asyncio
async def test_diagnostic_sensors_expose_snapshot_values(
    blockheat_env: SimpleNamespace,
    fake_hass: Any,
) -> None:
    sensor_module = importlib.import_module("homeassistant.custom_components.blockheat.sensor")
    entry = blockheat_env.FakeConfigEntry("entry-1")
    _seed_domain_data(
        blockheat_env,
        fake_hass,
        entry,
        {
            "policy": {"price": 9.0, "cutoff": 8.0, "transition": "on"},
            "fallback": {
                "comfort_min": 20.0,
                "trigger_threshold": 21.5,
                "release_threshold": 21.9,
            },
            "final_target_debug": {"source": "saving", "control_write_delta": 1.1},
            "daikin": {"debug": {"action": "write"}},
            "floor": {"debug": {"action": "set_on"}},
        },
    )

    added: list[Any] = []
    await sensor_module.async_setup_entry(fake_hass, entry, added.extend)
    by_entity_id = {entity.entity_id: entity for entity in added}

    assert by_entity_id["sensor.blockheat_policy_price"].native_value == 9.0
    assert by_entity_id["sensor.blockheat_policy_cutoff"].native_value == 8.0
    assert by_entity_id["sensor.blockheat_policy_transition"].native_value == "on"
    assert by_entity_id["sensor.blockheat_final_source"].native_value == "saving"
    assert by_entity_id["sensor.blockheat_daikin_action"].native_value == "write"
    assert by_entity_id["sensor.blockheat_floor_action"].native_value == "set_on"


@pytest.mark.asyncio
async def test_diagnostic_binary_sensors_expose_flags(
    blockheat_env: SimpleNamespace,
    fake_hass: Any,
) -> None:
    binary_sensor_module = importlib.import_module(
        "homeassistant.custom_components.blockheat.binary_sensor"
    )
    entry = blockheat_env.FakeConfigEntry("entry-1")
    _seed_domain_data(
        blockheat_env,
        fake_hass,
        entry,
        {
            "policy": {
                "blocked_now": True,
                "ignore_by_price": False,
                "ignore_by_pv": True,
                "below_min_floor": False,
                "enough_time_passed": True,
            },
            "fallback": {"arm_condition": True, "cooldown_ok": False},
            "final_target_debug": {"control_write_applied": True},
        },
    )

    added: list[Any] = []
    await binary_sensor_module.async_setup_entry(fake_hass, entry, added.extend)
    by_entity_id = {entity.entity_id: entity for entity in added}

    assert by_entity_id["binary_sensor.blockheat_policy_blocked_now"].is_on is True
    assert by_entity_id["binary_sensor.blockheat_policy_ignore_by_pv"].is_on is True
    assert by_entity_id["binary_sensor.blockheat_fallback_arm_condition"].is_on is True
    assert by_entity_id["binary_sensor.blockheat_control_write_applied"].is_on is True

