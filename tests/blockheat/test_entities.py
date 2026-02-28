"""Entity platform tests for Blockheat."""

from __future__ import annotations

import importlib
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest


def _setup_entry_data(
    blockheat_env: SimpleNamespace, fake_hass: Any, entry_id: str, coordinator: Any
) -> Any:
    entry = blockheat_env.FakeConfigEntry(entry_id)
    fake_hass.data.setdefault(blockheat_env.const.DOMAIN, {})[entry.entry_id] = {
        blockheat_env.package.ENTRY_COORDINATOR: coordinator
    }
    return entry


@pytest.mark.asyncio
async def test_binary_sensor_entities_read_internal_state(
    blockheat_env: SimpleNamespace,
    fake_hass: Any,
) -> None:
    const = blockheat_env.const
    binary_sensor_module = importlib.import_module(
        "homeassistant.custom_components.blockheat.binary_sensor"
    )
    coordinator = blockheat_env.coordinator.BlockheatCoordinator(fake_hass)
    coordinator.async_set_updated_data(
        {
            "at": "2026-02-19T12:00:00+00:00",
            "reason": "unit_test",
            "internal_state": {
                const.STATE_POLICY_ON: True,
                const.STATE_FALLBACK_ACTIVE: False,
            },
        }
    )
    entry = _setup_entry_data(
        blockheat_env, fake_hass, "entry-entities-bin", coordinator
    )

    added: list[Any] = []
    await binary_sensor_module.async_setup_entry(
        fake_hass,
        entry,
        lambda entities: added.extend(entities),
    )

    assert len(added) == 2
    by_entity_id = {entity._attr_entity_id: entity for entity in added}

    policy = by_entity_id[const.ENTITY_ID_POLICY_ACTIVE]
    assert policy.available is True
    assert policy.is_on is True
    assert policy.extra_state_attributes["source"] == "blockheat_internal_state"
    assert policy.extra_state_attributes["raw"] is True

    fallback = by_entity_id[const.ENTITY_ID_FALLBACK_ACTIVE]
    assert fallback.available is True
    assert fallback.is_on is False
    assert fallback.extra_state_attributes["raw"] is False


@pytest.mark.asyncio
async def test_sensor_entities_read_internal_state_and_handle_bad_values(
    blockheat_env: SimpleNamespace,
    fake_hass: Any,
) -> None:
    const = blockheat_env.const
    sensor_module = importlib.import_module(
        "homeassistant.custom_components.blockheat.sensor"
    )
    coordinator = blockheat_env.coordinator.BlockheatCoordinator(fake_hass)
    coordinator.async_set_updated_data(
        {
            "at": "2026-02-19T12:30:00+00:00",
            "reason": "unit_test",
            "internal_state": {
                const.STATE_TARGET_SAVING: 19.5,
                const.STATE_TARGET_COMFORT: 20.5,
                const.STATE_TARGET_FINAL: 21.5,
                const.STATE_FALLBACK_LAST_TRIGGER: "2026-02-19T12:30:00+00:00",
            },
        }
    )
    entry = _setup_entry_data(
        blockheat_env, fake_hass, "entry-entities-sensor", coordinator
    )

    added: list[Any] = []
    await sensor_module.async_setup_entry(
        fake_hass,
        entry,
        lambda entities: added.extend(entities),
    )

    assert len(added) == 4
    by_entity_id = {entity._attr_entity_id: entity for entity in added}

    saving = by_entity_id[const.ENTITY_ID_TARGET_SAVING]
    comfort = by_entity_id[const.ENTITY_ID_TARGET_COMFORT]
    final = by_entity_id[const.ENTITY_ID_TARGET_FINAL]
    last_trigger = by_entity_id[const.ENTITY_ID_FALLBACK_LAST_TRIGGER]

    assert saving.native_value == 19.5
    assert comfort.native_value == 20.5
    assert final.native_value == 21.5
    assert last_trigger.native_value == datetime(2026, 2, 19, 12, 30, tzinfo=UTC)
    assert final.extra_state_attributes["source"] == "blockheat_internal_state"

    coordinator.async_set_updated_data(
        {
            "at": "2026-02-19T13:30:00+00:00",
            "reason": "bad_values",
            "internal_state": {
                const.STATE_TARGET_SAVING: "not-a-number",
                const.STATE_TARGET_COMFORT: None,
                const.STATE_TARGET_FINAL: "also-bad",
                const.STATE_FALLBACK_LAST_TRIGGER: "invalid-datetime",
            },
        }
    )

    assert saving.native_value is None
    assert comfort.native_value is None
    assert final.native_value is None
    assert last_trigger.native_value is None


@pytest.mark.asyncio
async def test_entities_unavailable_without_coordinator_data(
    blockheat_env: SimpleNamespace,
    fake_hass: Any,
) -> None:
    binary_sensor_module = importlib.import_module(
        "homeassistant.custom_components.blockheat.binary_sensor"
    )
    coordinator = blockheat_env.coordinator.BlockheatCoordinator(fake_hass)
    entry = _setup_entry_data(
        blockheat_env, fake_hass, "entry-entities-empty", coordinator
    )

    added: list[Any] = []
    await binary_sensor_module.async_setup_entry(
        fake_hass,
        entry,
        lambda entities: added.extend(entities),
    )

    assert added
    assert all(entity.available is False for entity in added)
