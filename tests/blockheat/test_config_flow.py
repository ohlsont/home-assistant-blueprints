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


def _schema_default(data_schema: Any, key: str) -> Any:
    for marker in data_schema.schema:
        marker_key = getattr(marker, "schema", marker)
        if marker_key == key:
            default = getattr(marker, "default", None)
            return default() if callable(default) else default
    raise AssertionError(f"Schema key not found: {key}")


def _step1_user_input(
    const: Any,
    *,
    enable_daikin: bool = False,
    enable_floor: bool = False,
) -> dict[str, Any]:
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
        const.CONF_ENABLE_DAIKIN_CONSUMER: enable_daikin,
        const.CONF_DAIKIN_CLIMATE_ENTITY: "climate.daikin" if enable_daikin else "",
        const.CONF_DAIKIN_OUTDOOR_TEMP_SENSOR: "sensor.daikin_outdoor"
        if enable_daikin
        else "",
        const.CONF_ENABLE_FLOOR_CONSUMER: enable_floor,
        const.CONF_FLOOR_CLIMATE_ENTITY: "climate.floor_heat" if enable_floor else "",
        const.CONF_FLOOR_COMFORT_SCHEDULE: "schedule.floor_comfort"
        if enable_floor
        else "",
    }


def _tuning_input(const: Any, step_id: str) -> dict[str, Any]:
    by_step: dict[str, dict[str, Any]] = {
        "tuning_policy": {
            const.CONF_MINUTES_TO_BLOCK: 210,
            const.CONF_PRICE_IGNORE_BELOW: 0.6,
            const.CONF_PV_IGNORE_ABOVE_W: 0.0,
            const.CONF_MIN_FLOOR_TEMP: 0.0,
            const.CONF_MIN_TOGGLE_INTERVAL_MIN: 15,
        },
        "tuning_saving": {
            const.CONF_HEATPUMP_SETPOINT: 20.0,
            const.CONF_SAVING_COLD_OFFSET_C: 1.0,
            const.CONF_VIRTUAL_TEMPERATURE: 20.0,
            const.CONF_ENERGY_SAVING_WARM_SHUTDOWN_OUTDOOR: 8.0,
        },
        "tuning_comfort": {
            const.CONF_COMFORT_TARGET_C: 22.0,
            const.CONF_COMFORT_TO_HEATPUMP_OFFSET_C: 2.0,
            const.CONF_STORAGE_TARGET_C: 24.5,
            const.CONF_STORAGE_TO_HEATPUMP_OFFSET_C: 2.0,
            const.CONF_MAINTENANCE_TARGET_C: 20.0,
            const.CONF_COMFORT_MARGIN_C: 0.25,
        },
        "tuning_boost": {
            const.CONF_COLD_THRESHOLD: 1.0,
            const.CONF_MAX_BOOST: 3.0,
            const.CONF_BOOST_SLOPE_C: 4.0,
        },
        "tuning_fallback": {
            const.CONF_ELECTRIC_FALLBACK_DELTA_C: 1.5,
            const.CONF_RELEASE_DELTA_C: 0.5,
            const.CONF_ELECTRIC_FALLBACK_MINUTES: 45,
            const.CONF_ELECTRIC_FALLBACK_COOLDOWN_MINUTES: 90,
        },
        "tuning_limits": {
            const.CONF_CONTROL_MIN_C: 10.0,
            const.CONF_CONTROL_MAX_C: 26.0,
            const.CONF_SAVING_HELPER_WRITE_DELTA_C: 0.05,
            const.CONF_COMFORT_HELPER_WRITE_DELTA_C: 0.05,
            const.CONF_FINAL_HELPER_WRITE_DELTA_C: 0.05,
            const.CONF_CONTROL_WRITE_DELTA_C: 0.2,
        },
        "tuning_daikin": {
            const.CONF_DAIKIN_NORMAL_TEMPERATURE: 22.0,
            const.CONF_DAIKIN_SAVING_TEMPERATURE: 20.0,
            const.CONF_DAIKIN_OUTDOOR_TEMP_THRESHOLD: -10.0,
            const.CONF_DAIKIN_MIN_TEMP_CHANGE: 0.5,
        },
        "tuning_floor": {
            const.CONF_FLOOR_COMFORT_TEMP_C: 22.0,
            const.CONF_FLOOR_PREFER_PRESET_MANUAL: True,
            const.CONF_FLOOR_HVAC_MODE_WHEN_ON: "heat",
            const.CONF_FLOOR_SOFT_OFF_TEMP_OVERRIDE_C: "",
            const.CONF_FLOOR_MIN_KEEP_TEMP_C: "",
            const.CONF_FLOOR_MIN_SWITCH_INTERVAL_MIN: 15,
        },
    }
    return by_step[step_id]


async def _walk_core_tuning_steps(flow: Any, const: Any) -> dict[str, Any]:
    result = await flow.async_step_tuning_policy(_tuning_input(const, "tuning_policy"))
    assert result["step_id"] == "tuning_saving"
    result = await flow.async_step_tuning_saving(_tuning_input(const, "tuning_saving"))
    assert result["step_id"] == "tuning_comfort"
    result = await flow.async_step_tuning_comfort(
        _tuning_input(const, "tuning_comfort")
    )
    assert result["step_id"] == "tuning_boost"
    result = await flow.async_step_tuning_boost(_tuning_input(const, "tuning_boost"))
    assert result["step_id"] == "tuning_fallback"
    result = await flow.async_step_tuning_fallback(
        _tuning_input(const, "tuning_fallback")
    )
    assert result["step_id"] == "tuning_limits"
    return result


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


@pytest.mark.parametrize(
    ("enable_daikin", "enable_floor", "expected_optional_steps"),
    [
        (False, False, []),
        (True, False, ["tuning_daikin"]),
        (False, True, ["tuning_floor"]),
        (True, True, ["tuning_daikin", "tuning_floor"]),
    ],
)
@pytest.mark.asyncio
async def test_config_flow_routes_through_expected_steps(
    blockheat_env: SimpleNamespace,
    enable_daikin: bool,
    enable_floor: bool,
    expected_optional_steps: list[str],
) -> None:
    const = blockheat_env.const
    flow = blockheat_env.config_flow.BlockheatConfigFlow()
    first = await flow.async_step_user(
        _step1_user_input(const, enable_daikin=enable_daikin, enable_floor=enable_floor)
    )
    assert first["type"] == "form"
    assert first["step_id"] == "tuning_policy"

    await _walk_core_tuning_steps(flow, const)

    result = await flow.async_step_tuning_limits(_tuning_input(const, "tuning_limits"))
    for step_id in expected_optional_steps:
        assert result["type"] == "form"
        assert result["step_id"] == step_id
        result = await getattr(flow, f"async_step_{step_id}")(
            _tuning_input(const, step_id)
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "Blockheat"
    assert (
        result["data"][const.CONF_TARGET_BOOLEAN]
        == "input_boolean.block_heat_energy_saving"
    )
    assert result["data"][const.CONF_MINUTES_TO_BLOCK] == 210
    assert result["data"][const.CONF_DAIKIN_SAVING_TEMPERATURE] == 20.0
    assert result["data"][const.CONF_STORAGE_TARGET_C] == 24.5


@pytest.mark.asyncio
async def test_config_flow_uses_domain_filtered_entity_selectors(
    blockheat_env: SimpleNamespace,
) -> None:
    const = blockheat_env.const
    flow = blockheat_env.config_flow.BlockheatConfigFlow()
    result = await flow.async_step_user()

    nordpool_selector = _schema_value(result["data_schema"], const.CONF_NORDPOOL_PRICE)
    target_selector = _schema_value(result["data_schema"], const.CONF_TARGET_BOOLEAN)
    control_selector = _schema_value(
        result["data_schema"], const.CONF_CONTROL_NUMBER_ENTITY
    )
    daikin_outdoor_selector = _schema_value(
        result["data_schema"], const.CONF_DAIKIN_OUTDOOR_TEMP_SENSOR
    )
    schedule_selector = _schema_value(
        result["data_schema"], const.CONF_FLOOR_COMFORT_SCHEDULE
    )

    assert nordpool_selector.config.domain == "sensor"
    assert target_selector.config.domain == "input_boolean"
    assert control_selector.config.domain == "number"
    assert daikin_outdoor_selector.config.domain == "sensor"
    assert schedule_selector.config.domain == ["schedule", "input_boolean"]


@pytest.mark.asyncio
async def test_config_flow_schema_defaults_reflect_new_baseline(
    blockheat_env: SimpleNamespace,
) -> None:
    const = blockheat_env.const

    flow = blockheat_env.config_flow.BlockheatConfigFlow()
    policy_step = await flow.async_step_user(_step1_user_input(const))
    assert policy_step["step_id"] == "tuning_policy"
    assert (
        _schema_default(policy_step["data_schema"], const.CONF_MINUTES_TO_BLOCK) == 180
    )
    assert (
        _schema_default(policy_step["data_schema"], const.CONF_PRICE_IGNORE_BELOW)
        == 0.6
    )

    saving_step = await flow.async_step_tuning_policy({})
    assert saving_step["step_id"] == "tuning_saving"
    assert (
        _schema_default(
            saving_step["data_schema"], const.CONF_ENERGY_SAVING_WARM_SHUTDOWN_OUTDOOR
        )
        == 8.0
    )

    comfort_step = await flow.async_step_tuning_saving({})
    assert comfort_step["step_id"] == "tuning_comfort"
    assert (
        _schema_default(comfort_step["data_schema"], const.CONF_STORAGE_TARGET_C)
        == 24.5
    )
    assert (
        _schema_default(comfort_step["data_schema"], const.CONF_COMFORT_MARGIN_C)
        == 0.25
    )

    boost_step = await flow.async_step_tuning_comfort({})
    assert boost_step["step_id"] == "tuning_boost"
    assert _schema_default(boost_step["data_schema"], const.CONF_COLD_THRESHOLD) == 1.0
    assert _schema_default(boost_step["data_schema"], const.CONF_BOOST_SLOPE_C) == 4.0

    fallback_step = await flow.async_step_tuning_boost({})
    assert fallback_step["step_id"] == "tuning_fallback"
    assert (
        _schema_default(
            fallback_step["data_schema"], const.CONF_ELECTRIC_FALLBACK_DELTA_C
        )
        == 1.5
    )
    assert (
        _schema_default(fallback_step["data_schema"], const.CONF_RELEASE_DELTA_C) == 0.5
    )
    assert (
        _schema_default(
            fallback_step["data_schema"], const.CONF_ELECTRIC_FALLBACK_COOLDOWN_MINUTES
        )
        == 90
    )

    daikin_flow = blockheat_env.config_flow.BlockheatConfigFlow()
    await daikin_flow.async_step_user(_step1_user_input(const, enable_daikin=True))
    await daikin_flow.async_step_tuning_policy({})
    await daikin_flow.async_step_tuning_saving({})
    await daikin_flow.async_step_tuning_comfort({})
    await daikin_flow.async_step_tuning_boost({})
    await daikin_flow.async_step_tuning_fallback({})
    daikin_step = await daikin_flow.async_step_tuning_limits({})
    assert daikin_step["step_id"] == "tuning_daikin"
    assert (
        _schema_default(
            daikin_step["data_schema"], const.CONF_DAIKIN_SAVING_TEMPERATURE
        )
        == 20.0
    )


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


@pytest.mark.parametrize(
    ("enable_daikin", "enable_floor", "expected_optional_steps"),
    [
        (False, False, []),
        (True, False, ["tuning_daikin"]),
        (False, True, ["tuning_floor"]),
        (True, True, ["tuning_daikin", "tuning_floor"]),
    ],
)
@pytest.mark.asyncio
async def test_options_flow_routes_through_expected_steps(
    blockheat_env: SimpleNamespace,
    build_config: Any,
    enable_daikin: bool,
    enable_floor: bool,
    expected_optional_steps: list[str],
) -> None:
    const = blockheat_env.const
    entry = blockheat_env.FakeConfigEntry("entry-1", data=build_config())
    flow = blockheat_env.config_flow.BlockheatOptionsFlow(entry)

    first = await flow.async_step_init(
        _step1_user_input(const, enable_daikin=enable_daikin, enable_floor=enable_floor)
    )
    assert first["type"] == "form"
    assert first["step_id"] == "tuning_policy"

    await _walk_core_tuning_steps(flow, const)

    result = await flow.async_step_tuning_limits(_tuning_input(const, "tuning_limits"))
    for step_id in expected_optional_steps:
        assert result["type"] == "form"
        assert result["step_id"] == step_id
        result = await getattr(flow, f"async_step_{step_id}")(
            _tuning_input(const, step_id)
        )

    assert result["type"] == "create_entry"
    assert result["data"][const.CONF_STORAGE_TARGET_C] == 24.5
    assert result["data"][const.CONF_DAIKIN_SAVING_TEMPERATURE] == 20.0
    assert (
        result["data"][const.CONF_TARGET_COMFORT_HELPER]
        == "input_number.block_heat_target_comfort"
    )
