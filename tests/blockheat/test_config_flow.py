"""Config flow tests for Blockheat."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from types import SimpleNamespace


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


def _schema_keys(data_schema: Any) -> set[str]:
    return {getattr(marker, "schema", marker) for marker in data_schema.schema}


def _step1_user_input(
    const: Any,
    *,
    enable_daikin: bool = False,
) -> dict[str, Any]:
    return {
        const.CONF_NORDPOOL_PRICE: "sensor.nordpool_price",
        const.CONF_COMFORT_ROOM_1_SENSOR: "sensor.comfort_room_1",
        const.CONF_COMFORT_ROOM_2_SENSOR: "sensor.comfort_room_2",
        const.CONF_STORAGE_ROOM_SENSOR: "sensor.storage_room",
        const.CONF_OUTDOOR_TEMPERATURE_SENSOR: "sensor.outdoor_temp",
        const.CONF_CONTROL_NUMBER_ENTITY: "number.block_heat_control",
        const.CONF_PV_SENSOR: "",
        const.CONF_ENABLE_DAIKIN_CONSUMER: enable_daikin,
        const.CONF_DAIKIN_CLIMATE_ENTITY: "climate.daikin" if enable_daikin else "",
    }


def _tuning_input(
    const: Any,
    step_id: str,
    *,
    enable_forecast: bool = False,
    weather_entity: str = "",
) -> dict[str, Any]:
    by_step: dict[str, dict[str, Any]] = {
        "tuning_targets": {
            const.CONF_MINUTES_TO_BLOCK: 210,
            const.CONF_PRICE_IGNORE_BELOW: 0.6,
            const.CONF_PV_IGNORE_ABOVE_W: 0.0,
            const.CONF_HEATPUMP_SETPOINT: 21.0,
            const.CONF_SAVING_COLD_OFFSET_C: 1.0,
            const.CONF_ENERGY_SAVING_WARM_SHUTDOWN_OUTDOOR: 8.0,
            const.CONF_COMFORT_TARGET_C: 22.0,
            const.CONF_STORAGE_TARGET_C: 25.0,
            const.CONF_COLD_THRESHOLD: 2.0,
            const.CONF_MAX_BOOST: 3.0,
            const.CONF_ENABLE_FORECAST_OPTIMIZATION: enable_forecast,
            const.CONF_WEATHER_ENTITY: weather_entity,
        },
        "tuning_daikin": {
            const.CONF_DAIKIN_NORMAL_TEMPERATURE: 22.0,
            const.CONF_DAIKIN_PREHEAT_OFFSET: 2.0,
            const.CONF_DAIKIN_MILD_THRESHOLD: 5.0,
        },
    }
    return by_step[step_id]


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
    invalid[const.CONF_NORDPOOL_PRICE] = "   "

    result = await flow.async_step_user(invalid)
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "invalid_required_entities"


@pytest.mark.parametrize(
    ("enable_daikin", "expected_optional_steps"),
    [(False, []), (True, ["tuning_daikin"])],
)
@pytest.mark.asyncio
async def test_config_flow_routes_through_expected_steps(
    blockheat_env: SimpleNamespace,
    enable_daikin: bool,
    expected_optional_steps: list[str],
) -> None:
    const = blockheat_env.const
    flow = blockheat_env.config_flow.BlockheatConfigFlow()
    first = await flow.async_step_user(
        _step1_user_input(const, enable_daikin=enable_daikin)
    )
    assert first["type"] == "form"
    assert first["step_id"] == "tuning_targets"

    result = await flow.async_step_tuning_targets(
        _tuning_input(const, "tuning_targets")
    )

    for step_id in expected_optional_steps:
        assert result["type"] == "form"
        assert result["step_id"] == step_id
        result = await getattr(flow, f"async_step_{step_id}")(
            _tuning_input(const, step_id)
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "Blockheat"
    assert result["data"][const.CONF_MINUTES_TO_BLOCK] == 210
    assert result["data"][const.CONF_DAIKIN_PREHEAT_OFFSET] == 2.0
    assert result["data"][const.CONF_STORAGE_TARGET_C] == 25.0


@pytest.mark.asyncio
async def test_config_flow_uses_domain_filtered_entity_selectors(
    blockheat_env: SimpleNamespace,
) -> None:
    const = blockheat_env.const
    flow = blockheat_env.config_flow.BlockheatConfigFlow()
    result = await flow.async_step_user()

    nordpool_selector = _schema_value(result["data_schema"], const.CONF_NORDPOOL_PRICE)
    control_selector = _schema_value(
        result["data_schema"], const.CONF_CONTROL_NUMBER_ENTITY
    )

    assert nordpool_selector.config.domain == "sensor"
    assert control_selector.config.domain == "number"


@pytest.mark.asyncio
async def test_config_flow_schema_defaults_reflect_new_baseline(
    blockheat_env: SimpleNamespace,
) -> None:
    const = blockheat_env.const

    flow = blockheat_env.config_flow.BlockheatConfigFlow()
    targets_step = await flow.async_step_user(_step1_user_input(const))
    assert targets_step["step_id"] == "tuning_targets"
    assert (
        _schema_default(targets_step["data_schema"], const.CONF_MINUTES_TO_BLOCK) == 240
    )
    assert (
        _schema_default(targets_step["data_schema"], const.CONF_PRICE_IGNORE_BELOW)
        == 0.6
    )
    assert (
        _schema_default(
            targets_step["data_schema"], const.CONF_ENERGY_SAVING_WARM_SHUTDOWN_OUTDOOR
        )
        == 8.0
    )
    assert (
        _schema_default(targets_step["data_schema"], const.CONF_STORAGE_TARGET_C)
        == 25.0
    )
    assert (
        _schema_default(targets_step["data_schema"], const.CONF_COLD_THRESHOLD) == 2.0
    )
    assert _schema_default(targets_step["data_schema"], const.CONF_MAX_BOOST) == 3.0

    daikin_flow = blockheat_env.config_flow.BlockheatConfigFlow()
    await daikin_flow.async_step_user(_step1_user_input(const, enable_daikin=True))
    daikin_step = await daikin_flow.async_step_tuning_targets(
        _tuning_input(const, "tuning_targets")
    )
    assert daikin_step["step_id"] == "tuning_daikin"
    assert (
        _schema_default(daikin_step["data_schema"], const.CONF_DAIKIN_PREHEAT_OFFSET)
        == 2.0
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
    ("enable_daikin", "expected_optional_steps"),
    [(False, []), (True, ["tuning_daikin"])],
)
@pytest.mark.asyncio
async def test_options_flow_routes_through_expected_steps(
    blockheat_env: SimpleNamespace,
    build_config: Any,
    enable_daikin: bool,
    expected_optional_steps: list[str],
) -> None:
    const = blockheat_env.const
    entry = blockheat_env.FakeConfigEntry("entry-1", data=build_config())
    flow = blockheat_env.config_flow.BlockheatOptionsFlow(entry)

    first = await flow.async_step_init(
        _step1_user_input(const, enable_daikin=enable_daikin)
    )
    assert first["type"] == "form"
    assert first["step_id"] == "tuning_targets"

    result = await flow.async_step_tuning_targets(
        _tuning_input(const, "tuning_targets")
    )

    for step_id in expected_optional_steps:
        assert result["type"] == "form"
        assert result["step_id"] == step_id
        result = await getattr(flow, f"async_step_{step_id}")(
            _tuning_input(const, step_id)
        )

    assert result["type"] == "create_entry"
    assert result["data"][const.CONF_STORAGE_TARGET_C] == 25.0
    assert result["data"][const.CONF_DAIKIN_PREHEAT_OFFSET] == 2.0


@pytest.mark.asyncio
async def test_config_flow_round_trip_with_forecast_optimization(
    blockheat_env: SimpleNamespace,
) -> None:
    """Forecast optimization fields survive a full config flow round-trip."""
    const = blockheat_env.const
    flow = blockheat_env.config_flow.BlockheatConfigFlow()

    await flow.async_step_user(_step1_user_input(const))
    result = await flow.async_step_tuning_targets(
        _tuning_input(
            const,
            "tuning_targets",
            enable_forecast=True,
            weather_entity="weather.smhi",
        )
    )

    assert result["type"] == "create_entry"
    assert result["data"][const.CONF_ENABLE_FORECAST_OPTIMIZATION] is True
    assert result["data"][const.CONF_WEATHER_ENTITY] == "weather.smhi"
