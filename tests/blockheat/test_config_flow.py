"""Config flow tests for Blockheat."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest


def _schema_value(data_schema: Any, key: str) -> Any:
    for marker, value in data_schema.schema.items():
        marker_key = getattr(marker, "schema", marker)
        if marker_key == key:
            return value
    raise AssertionError(f"Schema key not found: {key}")


def _step1_user_input(const: Any) -> dict[str, Any]:
    return {
        const.CONF_TARGET_BOOLEAN: "input_boolean.block_heat_energy_saving",
        const.CONF_NORDPOOL_PRICE: "sensor.nordpool_price",
        const.CONF_COMFORT_ROOM_1_SENSOR: "sensor.comfort_room_1",
        const.CONF_COMFORT_ROOM_2_SENSOR: "sensor.comfort_room_2",
        const.CONF_STORAGE_ROOM_SENSOR: "sensor.storage_room",
        const.CONF_OUTDOOR_TEMPERATURE_SENSOR: "sensor.outdoor_temp",
        const.CONF_TARGET_SAVING_HELPER: "input_number.block_heat_target_saving",
        const.CONF_TARGET_COMFORT_HELPER: "input_number.block_heat_target_comfort",
        const.CONF_TARGET_FINAL_HELPER: "input_number.block_heat_target_final",
        const.CONF_FALLBACK_ACTIVE_BOOLEAN: "input_boolean.block_heat_fallback_active",
        const.CONF_ELECTRIC_FALLBACK_LAST_TRIGGER: "input_datetime.block_heat_fallback_last_trigger",
        const.CONF_CONTROL_NUMBER_ENTITY: "number.block_heat_control",
        const.CONF_PV_SENSOR: "",
        const.CONF_FLOOR_TEMP_SENSOR: "",
        const.CONF_ENABLE_DAIKIN_CONSUMER: False,
        const.CONF_DAIKIN_CLIMATE_ENTITY: "",
        const.CONF_DAIKIN_OUTDOOR_TEMP_SENSOR: "",
        const.CONF_ENABLE_FLOOR_CONSUMER: False,
        const.CONF_FLOOR_CLIMATE_ENTITY: "",
        const.CONF_FLOOR_COMFORT_SCHEDULE: "",
    }


@pytest.mark.asyncio
async def test_config_flow_single_instance_aborts(
    blockheat_env: SimpleNamespace,
) -> None:
    flow = blockheat_env.config_flow.BlockheatConfigFlow()
    flow._current_entries = [object()]
    result = await flow.async_step_user()
    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.asyncio
async def test_config_flow_rejects_invalid_required_entity(
    blockheat_env: SimpleNamespace,
) -> None:
    const = blockheat_env.const
    flow = blockheat_env.config_flow.BlockheatConfigFlow()
    invalid = _step1_user_input(const)
    invalid[const.CONF_TARGET_BOOLEAN] = "   "

    result = await flow.async_step_user(invalid)
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "invalid_required_entities"


@pytest.mark.asyncio
async def test_config_flow_creates_entry_with_merged_data(
    blockheat_env: SimpleNamespace,
) -> None:
    const = blockheat_env.const
    flow = blockheat_env.config_flow.BlockheatConfigFlow()
    result_step_1 = await flow.async_step_user(_step1_user_input(const))
    assert result_step_1["type"] == "form"
    assert result_step_1["step_id"] == "tuning"

    result_step_2 = await flow.async_step_tuning(
        {
            const.CONF_MINUTES_TO_BLOCK: 300,
            const.CONF_COMFORT_TARGET_C: 23.0,
        }
    )
    assert result_step_2["type"] == "create_entry"
    assert result_step_2["title"] == "Blockheat"
    assert result_step_2["data"][const.CONF_MINUTES_TO_BLOCK] == 300
    assert result_step_2["data"][const.CONF_COMFORT_TARGET_C] == 23.0
    assert (
        result_step_2["data"][const.CONF_TARGET_BOOLEAN]
        == "input_boolean.block_heat_energy_saving"
    )


@pytest.mark.asyncio
async def test_config_flow_uses_domain_filtered_entity_selectors(
    blockheat_env: SimpleNamespace,
) -> None:
    const = blockheat_env.const
    flow = blockheat_env.config_flow.BlockheatConfigFlow()
    result = await flow.async_step_user()

    target_selector = _schema_value(result["data_schema"], const.CONF_TARGET_BOOLEAN)
    control_selector = _schema_value(
        result["data_schema"], const.CONF_CONTROL_NUMBER_ENTITY
    )
    schedule_selector = _schema_value(
        result["data_schema"], const.CONF_FLOOR_COMFORT_SCHEDULE
    )

    assert target_selector.config.domain == "input_boolean"
    assert control_selector.config.domain == "number"
    assert schedule_selector.config.domain == ["schedule", "input_boolean"]


@pytest.mark.asyncio
async def test_options_flow_rejects_invalid_required_entities(
    blockheat_env: SimpleNamespace,
    build_config: Any,
) -> None:
    const = blockheat_env.const
    entry = blockheat_env.FakeConfigEntry("entry-1", data=build_config())
    flow = blockheat_env.config_flow.BlockheatOptionsFlow(entry)
    invalid = _step1_user_input(const)
    invalid[const.CONF_CONTROL_NUMBER_ENTITY] = ""

    result = await flow.async_step_init(invalid)
    assert result["type"] == "form"
    assert result["step_id"] == "init"
    assert result["errors"]["base"] == "invalid_required_entities"


@pytest.mark.asyncio
async def test_options_flow_persists_updates(
    blockheat_env: SimpleNamespace,
    build_config: Any,
) -> None:
    const = blockheat_env.const
    entry = blockheat_env.FakeConfigEntry("entry-1", data=build_config())
    flow = blockheat_env.config_flow.BlockheatOptionsFlow(entry)

    step_1 = await flow.async_step_init(_step1_user_input(const))
    assert step_1["type"] == "form"
    assert step_1["step_id"] == "tuning"

    step_2 = await flow.async_step_tuning({const.CONF_COMFORT_TARGET_C: 24.0})
    assert step_2["type"] == "create_entry"
    assert step_2["data"][const.CONF_COMFORT_TARGET_C] == 24.0
    assert (
        step_2["data"][const.CONF_TARGET_COMFORT_HELPER]
        == "input_number.block_heat_target_comfort"
    )
